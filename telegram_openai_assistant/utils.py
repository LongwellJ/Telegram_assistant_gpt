import json
from pathlib import Path
import datetime
from filelock import FileLock

# Paths to the files
message_count_file = Path("message_count.json")
qa_file = Path("questions_answers.json")
lock_file = Path("file.lock")  # Lock file for safe file operations

def get_message_count():
    """Retrieve the current message count."""
    try:
        if not message_count_file.exists():
            return {"date": str(datetime.date.today()), "count": 0}
        
        with open(message_count_file, 'r') as file:
            return json.load(file)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading message count: {e}")
        return {"date": str(datetime.date.today()), "count": 0}

def update_message_count(new_count):
    """Update the message count in the file."""
    try:
        with FileLock(str(lock_file)):
            with open(message_count_file, 'w') as file:
                json.dump({"date": str(datetime.date.today()), "count": new_count}, file)
    except IOError as e:
        print(f"Error updating message count: {e}")

def save_qa(telegram_id, username, question, answer):
    """Save question and answer pairs to a file with user information."""
    try:
        with FileLock(str(lock_file)):
            # Ensure the QA file exists
            if not qa_file.exists():
                with open(qa_file, 'w') as file:
                    json.dump([], file)

            # Read, append, and save the new Q&A entry
            with open(qa_file, 'r+') as file:
                data = json.load(file)
                data.append({
                    "telegram_id": telegram_id,
                    "username": username,
                    "question": question,
                    "answer": answer,
                    "timestamp": str(datetime.datetime.now())  # Add timestamp
                })
                file.seek(0)
                json.dump(data, file, indent=4)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error saving Q&A: {e}")
