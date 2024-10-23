#bot.py
from collections import defaultdict
import time
import datetime
from telegram.ext import CallbackContext
from telegram import Update
from openai import OpenAI
import asyncio
from .config import assistant_id, client_api_key
from .utils import get_message_count, update_message_count, save_qa
import logging
import re


client = OpenAI(api_key=client_api_key)
thread_ids = defaultdict(lambda: None)



def clean_response(response_text):
    """
    Removes any text enclosed within 【】 characters from the given string.
    """
    # Regular expression to match text inside 【 】 brackets
    cleaned_text = re.sub(r'【.*?】', '', response_text)
    
    # Optionally, strip any extra whitespace that may be left after removing the brackets
    return cleaned_text.strip()

def get_or_create_thread(chat_id):
    """Retrieves the existing thread_id or creates a new one."""
    thread_id = thread_ids[chat_id]
    
    if thread_id is None:
        # Create a new thread if no existing thread_id
        thread = client.beta.threads.create()
        thread_id = thread.id
        thread_ids[chat_id] = thread_id
        logging.info(f"Created new thread for chat_id {chat_id}: {thread_id}")
    else:
        logging.info(f"Using existing thread for chat_id {chat_id}: {thread_id}")

    return thread_id

async def help_command(update: Update, context: CallbackContext) -> None:
    """Sends a help message to the user."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Just send me a question and I'll try to answer it.",
    )

def get_answer(chat_id, message_str):
    """Get answer from assistant within a thread, handling errors and retries."""
    try:
        # Get or create the thread for the given chat_id
        thread_id = get_or_create_thread(chat_id)

        # Send the user's message to the thread
        client.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=message_str
        )

        # Start a new run for the assistant to process the message
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
        )

        # Poll the API until the assistant has completed processing
        max_retries = 10
        retry_interval = 3
        retries = 0

        while retries < max_retries:
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            logging.info(f"Run status: {run.status}")
            logging.info(f"Full response data: {run}")
            
            if run.status == "completed":
                break
            elif run.status == "failed":
                logging.error(f"Run failed: {run}")
                return "Sorry, there was an issue processing your request. Please try again later."
            
            time.sleep(retry_interval)
            retries += 1

        if retries >= max_retries:
            logging.error("The request timed out after multiple retries.")
            return "Sorry, the request is taking too long. Please try again later."

        # Get the list of messages from the thread once the run is completed
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        logging.info(f"Full messages data: {messages}")

        # Extract the assistant's response
        response = messages.model_dump()["data"][0]["content"][0]["text"]["value"]
        return clean_response(response)

    except Exception as e:
        logging.error(f"Error while getting the answer: {e}")
        return "Sorry, I encountered an issue while processing your request."

async def handle_mention(message_text, chat_id, context: CallbackContext):
    """Handles the logic for when the bot is mentioned or called via /chat."""
    logging.info(f"Received message: {message_text}")

    if "/chat" in message_text:
        # Extract the user's message
        user_message = message_text.replace("/chat", "").strip()
        
        if user_message:
            response = get_answer(chat_id, user_message)  # Call your OpenAI function
            await context.bot.send_message(chat_id=chat_id, text=response)
        else:
            await context.bot.send_message(chat_id=chat_id, text="Hello! How can I assist you?")
    else:
        logging.info(f"Ignored message: {message_text}")

async def chat_command(update: Update, context: CallbackContext) -> None:
    """Command handler for /chat. It passes the message to the mention handler."""
    user_message = update.message.text.strip()
    if user_message:
        await handle_mention(user_message, update.effective_chat.id, context)
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please provide a message after the /chat command."
        )
        
async def process_group_message(update: Update, context: CallbackContext):
    """Processes a message in a group chat and responds if the bot is mentioned."""
    message_text = update.message.text
    await handle_mention(message_text, update.effective_chat.id, context)

async def start(update: Update, context: CallbackContext):
    """Handles /start command in both private and group chats."""
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm here to help. Mention me in a group using @PnRGPTbot.")

async def process_message(update: Update, context: CallbackContext) -> None:
    """Processes a message from the user, gets an answer, and sends it back."""
    message_data = get_message_count()
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

    # Call `get_answer` synchronously
    answer = get_answer(update.message.text)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=answer)
    update_message_count(count + 1)
    save_qa(
        update.effective_user.id,
        update.effective_user.username,
        update.message.text,
        answer,
    )
