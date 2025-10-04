"""
Command handlers for the Telegram bot.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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


async def receipts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent receipts for the user."""
    user_id = update.effective_user.id
    db = context.bot_data.get('database')

    if not db:
        await update.message.reply_text('❌ Error: Database not available')
        return

    try:
        # Get recent receipts (limit 10)
        # We need to add this method to the repository
        from services.receipt_formatter import format_receipt_summary

        # For now, let's get receipt 30 which the user lost
        receipt_id = 30

        try:
            summary_text, reply_markup = format_receipt_summary(db, receipt_id, user_id)
            await update.message.reply_text(summary_text, reply_markup=reply_markup)
            logger.info(f"Showed receipt {receipt_id} summary to user {user_id}")
        except ValueError:
            await update.message.reply_text(
                f'Receipt #{receipt_id} not found or you don\'t have access to it.\n\n'
                f'Use /receipts <receipt_id> to view a specific receipt.'
            )

    except Exception as e:
        logger.error(f"Error in receipts command: {e}")
        await update.message.reply_text('❌ Error retrieving receipts. Please try again later.')
