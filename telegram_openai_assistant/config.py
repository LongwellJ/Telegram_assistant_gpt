# config.py
from dotenv import load_dotenv
import os

# Load the environment variables from the .env file. override=True ensures .env takes
# precedence over any same-named variable already present in the shell/system environment
# (e.g. an unrelated global OPENAI_API_KEY set for another tool on this machine).
load_dotenv(override=True)

# Retrieve the variables from the environment.
telegram_token = os.getenv("TELEGRAM_TOKEN")
openai_api_key = os.getenv("OPENAI_API_KEY")
vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")
sqlite_db_path = os.getenv("SQLITE_DB_PATH", "./bot_state.db")
data_dir = os.getenv("DATA_DIR", ".")

REQUIRED_VARS = {
    "TELEGRAM_TOKEN": telegram_token,
    "OPENAI_API_KEY": openai_api_key,
    "OPENAI_VECTOR_STORE_ID": vector_store_id,
}


def validate_config():
    """Fail fast at startup if any required env var is missing."""
    missing = [name for name, value in REQUIRED_VARS.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variable(s): {', '.join(missing)}")
