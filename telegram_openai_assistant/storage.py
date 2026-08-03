# storage.py
# Persists per-conversation message history (as a JSON list of {"role", "content"} turns)
# so continuity survives process restarts/redeploys. We manage history ourselves rather
# than using the Responses API's previous_response_id chaining, because that's an opaque
# server-side thread we can't selectively trim from -- owning the list lets handlers.py
# evict the oldest turns (FIFO) once a conversation gets too large, instead of having to
# wipe it entirely.
import json
import sqlite3
from datetime import datetime, timezone

from .config import sqlite_db_path


def _needs_migration(conn: sqlite3.Connection) -> bool:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(conversations)")}
    return bool(cols) and "history_json" not in cols


def init_db():
    """Create the conversations table if it doesn't already exist. Call once at startup.
    If an older schema (response_id-chained, from before self-managed FIFO history) is
    found, it's dropped and recreated -- this table only holds resumable session state,
    not data worth preserving across a schema change."""
    with sqlite3.connect(sqlite_db_path) as conn:
        if _needs_migration(conn):
            conn.execute("DROP TABLE conversations")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_key TEXT PRIMARY KEY,
                history_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def get_conversation_state(conversation_key: str) -> dict | None:
    """Returns the stored state for a conversation, or None if it has no history yet."""
    with sqlite3.connect(sqlite_db_path) as conn:
        row = conn.execute(
            "SELECT history_json, updated_at FROM conversations WHERE conversation_key = ?",
            (conversation_key,),
        ).fetchone()

    if row is None:
        return None
    return {"history": json.loads(row[0]), "updated_at": row[1]}


def save_history(conversation_key: str, history: list[dict]) -> None:
    with sqlite3.connect(sqlite_db_path) as conn:
        conn.execute(
            """
            INSERT INTO conversations (conversation_key, history_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(conversation_key) DO UPDATE SET
                history_json = excluded.history_json,
                updated_at = excluded.updated_at
            """,
            (conversation_key, json.dumps(history), datetime.now(timezone.utc).isoformat()),
        )
