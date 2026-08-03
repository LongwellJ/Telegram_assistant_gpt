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


def _clean(text: str) -> str:
    """Strips OpenAI's file_search citation markers (e.g. 【4:0†source】) from the response text."""
    return _CITATION_MARKER_RE.sub("", text).strip()


async def get_answer(previous_response_id: str | None, message_str: str) -> ResponseResult:
    """Get an answer from the model, chaining conversation state via previous_response_id.
    response_id is None on failure so callers know not to persist it."""
    try:
        response = await client.responses.create(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=message_str,
            tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
            previous_response_id=previous_response_id,
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

    return ResponseResult(_clean(response.output_text), response.id)
