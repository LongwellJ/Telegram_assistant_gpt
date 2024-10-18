# storage.py
# Handles storing and retrieving questions/answers
import json
from pathlib import Path
from datetime import datetime

qa_file = Path("questions_answers.json")

if not qa_file.is_file():
    with open(qa_file, "w") as file:
        json.dump([], file)

def save_qa(telegram_id, username, question, answer):
    """Save question and answer pairs to a file along with user information and timestamp."""
    try:
        with open(qa_file, "r+") as file:
            data = json.load(file)
            data.append({
                "telegram_id": telegram_id,
                "username": username,
                "question": question,
                "answer": answer,
                "timestamp": datetime.now().isoformat()  # Add timestamp
            })
            file.seek(0)
            json.dump(data, file, indent=4)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error saving Q&A data: {e}")

