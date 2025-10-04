"""
Command handlers for the Telegram bot.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the /start command is issued."""
    # Save/update user in database
    user_id = update.effective_user.id
    # Use username if available, otherwise use first name or full name
    username = (update.effective_user.username or
                update.effective_user.first_name or
                update.effective_user.full_name)

    db = context.bot_data.get('database')
    if db:
        try:
            db.upsert_user(user_id, username)
        except Exception as e:
            logger.error(f"Failed to upsert user on /start: {e}")

    await update.message.reply_text(
        'Hello! I am your receipts bot. 🤖\n'
        'The environment is working correctly!\n\n'
        'Available commands:\n'
        '/start - Show this message\n'
        '/hello - Get a greeting'
    )


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a hello message when the /hello command is issued."""
    user_name = update.effective_user.first_name
    await update.message.reply_text(f'Hello {user_name}! 👋')
