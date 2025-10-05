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
    """
    List recent receipts for the user.

    Usage:
        /receipts - Show last 3 receipts (default)
        /receipts N - Show last N receipts (max 10)
    """
    user_id = update.effective_user.id
    db = context.bot_data.get('database')

    if not db:
        await update.message.reply_text('❌ Error: Database not available')
        return

    # Parse argument for number of receipts
    limit = 3  # default
    if context.args:
        try:
            limit = int(context.args[0])
            if limit < 1:
                await update.message.reply_text('❌ Please provide a positive number.')
                return
            if limit > 10:
                limit = 10  # cap at 10
        except ValueError:
            await update.message.reply_text('❌ Please provide a valid number.\n\nUsage: /receipts [N]')
            return

    try:
        from services.receipt_formatter import format_receipt_summary

        # Get recent receipt IDs
        receipt_ids = db.get_recent_receipts(user_id, limit)

        if not receipt_ids:
            await update.message.reply_text('You don\'t have any receipts yet. Upload a receipt image to get started!')
            return

        # Send summary for each receipt
        for receipt_id in receipt_ids:
            try:
                summary_text, reply_markup = format_receipt_summary(db, receipt_id, user_id)
                await update.message.reply_text(summary_text, reply_markup=reply_markup)
            except ValueError:
                logger.warning(f"Receipt {receipt_id} not accessible for user {user_id}")
                continue

        logger.info(f"Showed {len(receipt_ids)} receipts to user {user_id}")

    except Exception as e:
        logger.error(f"Error in receipts command: {e}")
        await update.message.reply_text('❌ Error retrieving receipts. Please try again later.')
