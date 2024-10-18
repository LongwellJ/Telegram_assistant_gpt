import openai as client
import time
import os
import sys
import argparse

# Load environment variables or replace with your own method of storing sensitive information.
client.api_key = os.getenv("CLIENT_API_KEY")
assistant_id = os.getenv("ASSISTANT_ID")

def get_assistant_response(message_str):
    """Sends a message to the OpenAI Assistant and returns the response."""
    try:
        # Create a thread for the conversation
        thread = client.beta.threads.create()

        # Send the user's message to the thread
        client.beta.threads.messages.create(
            thread_id=thread.id, role="user", content=message_str
        )

        # Start a new run for the assistant to process the message
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id,
        )

        # Poll the API until the assistant has completed processing
        while True:
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run.status == "completed":
                break
            time.sleep(1)

        # Get the list of messages from the thread
        messages = client.beta.threads.messages.list(thread_id=thread.id)

        # Use model_dump() to extract the assistant's response
        response = messages.model_dump()["data"][0]["content"][0]["text"]["value"]
        return response

    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    # Command-line argument parser
    parser = argparse.ArgumentParser(description="Test OpenAI Assistant interaction.")
    parser.add_argument("message", type=str, help="The message to send to the assistant.")
    args = parser.parse_args()

    # Send the message and get the assistant's response
    response = get_assistant_response(args.message)
    
    if response:
        print(f"Assistant's Response: {response}")
    else:
        print("Failed to retrieve a response from the assistant.")

if __name__ == "__main__":
    # Ensure API keys and Assistant ID are set
    if not client.api_key or not assistant_id:
        print("Error: Missing OpenAI API Key or Assistant ID. Please set them via environment variables.")
        sys.exit(1)

    main()