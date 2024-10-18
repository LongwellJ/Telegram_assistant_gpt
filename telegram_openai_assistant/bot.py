# bot.py
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from .config import telegram_token
from .handlers import start, help_command, process_message, process_group_message
from telegram import Update
from telegram.ext import ContextTypes
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

application = Application.builder().token(telegram_token).build()



async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a message to notify the user."""
    print(f"Error: {context.error}")  # Log error to console
    await update.message.reply_text("Oops! Something went wrong. Please try again later.")



def setup_handlers(app):
    """Sets up the command and message handlers for the bot."""
    # Add a handler for direct messages and group messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))

    # Add a handler for group messages
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, process_group_message))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

def main():
    """Main function to run the bot."""
    logger.info("Starting bot...")
    setup_handlers(application)
    application.run_polling()

if __name__ == "__main__":
    main()
