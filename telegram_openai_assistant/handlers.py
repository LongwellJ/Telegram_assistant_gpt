import asyncio
import datetime
import logging

from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext
from telegram import Update

from . import openai_client, storage
from .telegram_markdown import to_telegram_html
from .utils import get_message_count, update_message_count, save_qa

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
# Conservative: we split the raw markdown at this length, then convert each piece to
# HTML, which grows it somewhat (**x** -> <b>x</b>). Leaves headroom under the real
# 4096-char Telegram limit for that markup overhead.
MARKDOWN_SPLIT_LIMIT = 3000
# Telegram's "typing…" indicator auto-expires after ~5s (or on the next sent message),
# so it has to be re-sent periodically to stay visible for the duration of a slower call.
TYPING_REFRESH_SECONDS = 4

# We resend the *entire* conversation history as input on every turn (that's how
# continuity works here -- see storage.py), so a thread gets more expensive and slower
# with every message, and can eventually exceed the model's context window outright.
# MAX_CONVERSATION_TURNS/CONVERSATION_TIMEOUT_SECONDS retire a thread entirely (rare --
# genuinely stale or runaway conversations). MAX_CONTEXT_TOKENS instead trims the oldest
# turns FIFO to stay under budget, so a long-running conversation keeps recent context
# instead of losing everything at once.
MAX_CONVERSATION_TURNS = 40
CONVERSATION_TIMEOUT_SECONDS = 6 * 60 * 60  # 6h of inactivity is treated as a new topic
MAX_CONTEXT_TOKENS = 400_000
# No tokenizer dependency: file_search's retrieved-document tokens are invisible to us
# until after the call anyway and dominate the real total, so a precise local count of
# just the conversational text wouldn't meaningfully improve this estimate.
CHARS_PER_TOKEN_ESTIMATE = 4

RESET_NOTICE = "\U0001F504 This conversation has grown long, so I'm starting a fresh one from here."


def _split_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Splits text into chunks that fit within Telegram's per-message character limit,
    preferring to break on a paragraph/line/word boundary over mid-word."""
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def _send_long_message(context: CallbackContext, chat_id, text: str) -> None:
    """Sends text as one or more messages (splitting if it exceeds Telegram's 4096-char
    limit), rendering the model's Markdown as Telegram HTML so bold/italic/links/lists
    actually show up formatted. Falls back to plain text if HTML parsing ever fails,
    e.g. from an edge case the converter didn't anticipate, so a reply is never lost."""
    for chunk in _split_message(text, limit=MARKDOWN_SPLIT_LIMIT):
        html_chunk = to_telegram_html(chunk)
        try:
            await context.bot.send_message(chat_id=chat_id, text=html_chunk, parse_mode=ParseMode.HTML)
        except BadRequest as e:
            logging.error(f"Telegram rejected HTML message, falling back to plain text: {e}")
            await context.bot.send_message(chat_id=chat_id, text=chunk)


async def help_command(update: Update, context: CallbackContext) -> None:
    """Sends a help message to the user."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Just send me a question and I'll try to answer it.",
    )


def _conversation_key(chat_id, user_id) -> str:
    """Scopes each conversation thread to a (chat, user) pair rather than just chat_id,
    so multiple people in the same group each get their own context instead of sharing
    -- and confusing -- one another's."""
    return f"{chat_id}:{user_id}"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def _trim_to_token_budget(history: list[dict], budget: int = MAX_CONTEXT_TOKENS) -> list[dict]:
    """Evicts the oldest turns (FIFO) until the estimated size of the remaining history
    fits the budget, instead of wiping the whole conversation once it's exceeded.
    Prefers dropping a whole user/assistant pair at a time to keep turns aligned."""
    def total_tokens() -> int:
        return sum(_estimate_tokens(m["content"]) for m in history)

    while total_tokens() > budget and len(history) > 2:
        del history[0:2]
    # Fallback for a single turn so large it alone is near/over budget: still keep the
    # newest entry so the conversation isn't left completely empty.
    while total_tokens() > budget and len(history) > 1:
        history.pop(0)
    return history


def _resolve_history(state: dict | None) -> tuple[list[dict], str | None]:
    """Decides whether to continue an existing thread or start a new one, based on turn
    count and inactivity (the token budget is handled separately via FIFO trimming, not
    a full reset). Returns (history, reset_reason); reset_reason is None when continuing
    normally, otherwise a short human-readable reason for logging/notice."""
    if state is None:
        return [], None

    if len(state["history"]) // 2 >= MAX_CONVERSATION_TURNS:
        return [], "turn limit reached"

    updated_at = datetime.datetime.fromisoformat(state["updated_at"])
    age_seconds = (datetime.datetime.now(datetime.timezone.utc) - updated_at).total_seconds()
    if age_seconds >= CONVERSATION_TIMEOUT_SECONDS:
        return [], "inactive too long"

    return state["history"], None


async def get_reply(context: CallbackContext, chat_id, user_id, message_text):
    """Get a reply from the model, continuing the caller's existing conversation history
    when it's still valid, and persisting the updated history so continuity survives
    restarts. History is trimmed FIFO to a token budget rather than sending an
    ever-growing conversation to the model."""
    key = _conversation_key(chat_id, user_id)
    state = await asyncio.to_thread(storage.get_conversation_state, key)
    history, reset_reason = _resolve_history(state)

    if reset_reason is not None:
        logging.info(f"Resetting conversation {key}: {reset_reason}")
        await context.bot.send_message(chat_id=chat_id, text=RESET_NOTICE)

    history.append({"role": "user", "content": message_text})
    history = _trim_to_token_budget(history)

    result = await openai_client.get_answer(history)

    if result.response_id is not None:
        history.append({"role": "assistant", "content": result.text})
        history = _trim_to_token_budget(history)
        await asyncio.to_thread(storage.save_history, key, history)
    else:
        logging.error(f"No response returned for conversation {key}; state not updated")

    return result.text


async def _get_reply_with_typing(context: CallbackContext, chat_id, user_id, message_text: str) -> str:
    """Same as get_reply, but shows Telegram's "typing…" indicator for as long as the
    request is in flight, re-sending it every few seconds since it expires on its own."""
    async def _keep_typing():
        try:
            while True:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                await asyncio.sleep(TYPING_REFRESH_SECONDS)
        except asyncio.CancelledError:
            pass

    typing_task = asyncio.create_task(_keep_typing())
    try:
        return await get_reply(context, chat_id, user_id, message_text)
    finally:
        typing_task.cancel()
        await asyncio.gather(typing_task, return_exceptions=True)


async def handle_mention(update: Update, context: CallbackContext):
    """Handles the logic for when the bot is mentioned or called via /chat."""
    message_text = update.message.text
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    logging.info(f"Received message: {message_text}")

    if "/chat" in message_text:
        # Extract the user's message
        user_message = message_text.replace("/chat", "").strip()

        if user_message:
            response = await _get_reply_with_typing(context, chat_id, user_id, user_message)
            await _send_long_message(context, chat_id, response)
        else:
            await context.bot.send_message(chat_id=chat_id, text="Hello! How can I assist you?")
    else:
        logging.info(f"Ignored message: {message_text}")


async def chat_command(update: Update, context: CallbackContext) -> None:
    """Command handler for /chat. It passes the message to the mention handler."""
    if update.message.text.strip():
        await handle_mention(update, context)
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please provide a message after the /chat command."
        )


async def process_group_message(update: Update, context: CallbackContext):
    """Processes a message in a group chat and responds if the bot is mentioned."""
    await handle_mention(update, context)


async def start(update: Update, context: CallbackContext):
    """Handles /start command in both private and group chats."""
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm here to help. Mention me in a group using @PnRGPTbot.")


async def process_message(update: Update, context: CallbackContext) -> None:
    message_data = await asyncio.to_thread(get_message_count)
    count = message_data["count"]
    date = message_data["date"]
    today = str(datetime.date.today())

    if date != today:
        count = 0

    if count >= 100:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, I've reached my daily message limit. Please try again tomorrow."
        )
        return

    answer = await _get_reply_with_typing(
        context,
        update.effective_chat.id,
        update.effective_user.id,
        update.message.text
    )

    await _send_long_message(context, update.effective_chat.id, answer)

    await asyncio.to_thread(update_message_count, count + 1)

    await asyncio.to_thread(
        save_qa,
        update.effective_user.id,
        update.effective_user.username,
        update.message.text,
        answer,
    )
