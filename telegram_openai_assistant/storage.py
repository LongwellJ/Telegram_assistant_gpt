# storage.py
# Persists the mapping of Telegram chat_id -> last OpenAI Responses API response_id,
# so conversation continuity survives process restarts/redeploys.
import sqlite3
from datetime import datetime, timezone

from .config import sqlite_db_path


def init_db():
    """Create the conversations table if it doesn't already exist. Call once at startup."""
    with sqlite3.connect(sqlite_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                chat_id INTEGER PRIMARY KEY,
                last_response_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def get_last_response_id(chat_id: int) -> str | None:
    with sqlite3.connect(sqlite_db_path) as conn:
        row = conn.execute(
            "SELECT last_response_id FROM conversations WHERE chat_id = ?", (chat_id,)
        ).fetchone()
    return row[0] if row else None


def set_last_response_id(chat_id: int, response_id: str) -> None:
    with sqlite3.connect(sqlite_db_path) as conn:
        conn.execute(
            """
            INSERT INTO conversations (chat_id, last_response_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                last_response_id = excluded.last_response_id,
                updated_at = excluded.updated_at
            """,
            (chat_id, response_id, datetime.now(timezone.utc).isoformat()),
        )
