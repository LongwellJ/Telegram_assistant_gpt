import logging
import re
from dataclasses import dataclass

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from .assistant_config import INSTRUCTIONS, MODEL, TEMPERATURE
from .config import openai_api_key, vector_store_id

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=openai_api_key, timeout=60.0, max_retries=2)

_CITATION_MARKER_RE = re.compile(r"【.*?】")


@dataclass
class ResponseResult:
    text: str
    response_id: str | None
    total_tokens: int | None = None


def _clean(text: str) -> str:
    """Strips OpenAI's file_search citation markers (e.g. 【4:0†source】) from the response text."""
    return _CITATION_MARKER_RE.sub("", text).strip()


async def get_answer(messages: list[dict[str, str]]) -> ResponseResult:
    """Get an answer from the model, given the full conversation so far as a list of
    {"role": "user"|"assistant", "content": ...} turns (handlers.py owns trimming this
    to a token budget). response_id is None on failure so callers know not to persist
    the turn that triggered it."""
    try:
        response = await client.responses.create(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=messages,
            tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
            temperature=TEMPERATURE,
        )
    except APITimeoutError:
        logger.error("OpenAI request timed out")
        return ResponseResult("Sorry, the request is taking too long. Please try again later.", None)
    except RateLimitError:
        logger.error("OpenAI rate limit hit")
        return ResponseResult("Sorry, I'm getting too many requests right now. Please try again in a moment.", None)
    except APIConnectionError:
        logger.error("OpenAI connection error")
        return ResponseResult("Sorry, I couldn't reach the AI service. Please try again later.", None)
    except APIStatusError as e:
        logger.error(f"OpenAI API error: {e}")
        return ResponseResult("Sorry, there was an issue processing your request. Please try again later.", None)

    total_tokens = response.usage.total_tokens if response.usage is not None else None
    return ResponseResult(_clean(response.output_text), response.id, total_tokens)
