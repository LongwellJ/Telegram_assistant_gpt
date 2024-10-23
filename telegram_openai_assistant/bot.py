# bot.py
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from .config import telegram_token
from .handlers import start, help_command, process_message, process_group_message, chat_command
import logging
from telegram import Update
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

application = Application.builder().token(telegram_token).build()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a message to notify the user."""
    logging.error(f"Error: {context.error}")  # Log error to console
    await update.message.reply_text("Oops! Something went wrong. Please try again later.")

def setup_handlers(app):
    """Sets up the command and message handlers for the bot."""
    
    # Handler for group messages
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, process_group_message))

    # Handler for private messages
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, process_message))

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chat", chat_command))  # Add the new /chat command

    
def main():
    """Main function to run the bot."""
    logger.info("Starting bot...")
    setup_handlers(application)
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
