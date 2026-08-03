# OpenAI Responses API Telegram Bot

This repository provides a general framework for integrating an OpenAI model (via the Responses API, with `file_search` over a vector store) with a Telegram bot. It allows users to interact with the OpenAI-powered conversational agent through the Telegram platform.

> **This is a fork.** The original project was created by [efelem](https://github.com/efelem/telegram_openai_assistant) and used the OpenAI Assistants API. This fork ([LongwellJ/Telegram_assistant_gpt](https://github.com/LongwellJ/Telegram_assistant_gpt)) has since been reworked to migrate off the Assistants API (fully sunset by OpenAI on August 26, 2026) onto the Responses API, and adds SQLite-backed conversation persistence, formatted Telegram replies, and a few other production fixes described below. See [Credits](#credits).

## Features

- Real-time response to user queries, grounded via `file_search` over an OpenAI vector store.
- Per-chat conversation continuity (via the Responses API's `previous_response_id` chaining), persisted in SQLite so it survives restarts.
- Replies are rendered as formatted Telegram messages (bold, italics, links, lists, blockquotes) instead of raw markdown, and are automatically split across multiple messages if they exceed Telegram's 4096-character limit.
- A "typing…" indicator is shown for the full duration of a request, not just the first few seconds.
- Daily message count tracking.
- Storage of question and answer pairs for future retrieval and analysis.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- You have a `Python` environment running version 3.11+.
- You have a Telegram account and have created a bot with `@BotFather` to obtain a token.
- You have an `OpenAI` account to obtain your API key.

You also need

- An OpenAI API key: https://platform.openai.com/api-keys
- An OpenAI vector store id (for `file_search` grounding): https://platform.openai.com/storage/vector_stores
- A telegram token: use BotFather directly from Telegram to create your bot and get the telegram token

## Installation

Clone the repository to your local machine:

```bash
git clone https://github.com/LongwellJ/Telegram_assistant_gpt
cd Telegram_assistant_gpt
```

Install the packages:

```bash
pip install -e .
```

## Configuration

Create a `.env` file in the root directory and fill in your OpenAI and Telegram credentials:

```env
TELEGRAM_TOKEN=your-telegram-bot-token
OPENAI_API_KEY=your-openai-api-key
OPENAI_VECTOR_STORE_ID=your-vector-store-id
SQLITE_DB_PATH=./bot_state.db
```

`SQLITE_DB_PATH` is where per-chat conversation state (chat_id -> last response id) is persisted. Locally this can stay as a relative path; in production it must point at durable storage (see Deployment below), otherwise conversation memory is lost on every restart.

The model, temperature, and system instructions used to ground the assistant live in code at `telegram_openai_assistant/assistant_config.py` rather than in `.env`, since they're multi-paragraph and belong in version control.

## Usage

To start the bot, run the following command in your terminal:

```bash
chatbot
```

The bot should now be running and can be interacted with through your Telegram bot interface.

## Deployment (Railway)

This bot is deployed on [Railway](https://railway.app) via `nixpacks.toml` + `Procfile` (`python -m telegram_openai_assistant.bot`), using long-polling — no webhook or public HTTP endpoint is required.

1. Set the four env vars from the Configuration section above in the Railway project's variables.
2. **Attach a Railway Volume** to the service (e.g. mounted at `/data`) and set `SQLITE_DB_PATH=/data/bot_state.db` so conversation state survives redeploys — Railway's default filesystem is ephemeral per-deploy, so without a volume this state is wiped every time the service restarts.
3. Deploy. Nixpacks runs `pip install -r requirements.txt` and starts the bot with the command in `Procfile`.

## Contributions

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (\`git checkout -b feature/AmazingFeature\`)
3. Commit your Changes (\`git commit -m 'Add some AmazingFeature'\`)
4. Push to the Branch (\`git push origin feature/AmazingFeature\`)
5. Open a Pull Request

## License

Distributed under the MIT License. See \`LICENSE\` for more information.

## Credits

- Original project: [efelem/telegram_openai_assistant](https://github.com/efelem/telegram_openai_assistant)
- This fork: [LongwellJ/Telegram_assistant_gpt](https://github.com/LongwellJ/Telegram_assistant_gpt)

## Contact

Project Link: [https://github.com/LongwellJ/Telegram_assistant_gpt](https://github.com/LongwellJ/Telegram_assistant_gpt)
