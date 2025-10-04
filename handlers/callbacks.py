"""
Callback query handlers for inline keyboard buttons.
"""
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_view_image_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks view processed image button."""
    query = update.callback_query
    await query.answer()

    # Extract receipt_id from callback_data
    callback_data = query.data
    if not callback_data.startswith("view_image_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        receipt_id = int(callback_data.replace("view_image_", ""))
    except ValueError:
        logger.error(f"Failed to parse receipt_id from callback_data: {callback_data}")
        await query.answer("❌ Error: Invalid receipt ID", show_alert=True)
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.answer("❌ Error: Database not available", show_alert=True)
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Get processed image path with user verification
    try:
        image_path = db.get_receipt_processed_image_path(receipt_id, user_id)

        if image_path and Path(image_path).exists():
            # Send the processed image to the user
            with open(image_path, 'rb') as photo_file:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=photo_file,
                    caption=f"🔍 Processed image for receipt ID: {receipt_id}\n"
                            f"This is the image that was sent to Claude AI for analysis."
                )
            logger.info(f"Sent processed image for receipt {receipt_id} to user {user_id}")
        elif image_path:
            await query.answer(f"❌ Image file not found", show_alert=True)
            logger.warning(f"Image file not found for receipt {receipt_id}: {image_path}")
        else:
            await query.answer("❌ Receipt not found or access denied", show_alert=True)
            logger.warning(f"Receipt {receipt_id} not found or user {user_id} not authorized")

    except Exception as e:
        logger.error(f"Error sending image for receipt {receipt_id}: {e}")
        await query.answer("❌ Error retrieving image. Please try again later.", show_alert=True)


async def handle_delete_receipt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks delete receipt button."""
    query = update.callback_query
    await query.answer()

    # Extract receipt_id from callback_data
    callback_data = query.data
    if not callback_data.startswith("delete_receipt_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        receipt_id = int(callback_data.replace("delete_receipt_", ""))
    except ValueError:
        logger.error(f"Failed to parse receipt_id from callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid receipt ID")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Mark receipt as deleted with user verification
    try:
        success = db.mark_receipt_as_deleted(receipt_id, user_id)

        if success:
            # Update message to show deletion confirmation
            await query.edit_message_text(
                f"🗑️ Receipt deleted successfully!\n\n"
                f"Receipt ID: {receipt_id}\n"
                f"The receipt data has been marked as deleted and will not be included in reports."
            )
            logger.info(f"Receipt {receipt_id} deleted by user {user_id}")
        else:
            await query.edit_message_text(
                f"❌ Receipt not found or access denied!\n\n"
                f"Receipt ID: {receipt_id}\n"
                f"You can only delete your own receipts."
            )
            logger.warning(f"User {user_id} attempted to delete receipt {receipt_id} - not found or not authorized")
    except Exception as e:
        logger.error(f"Error deleting receipt {receipt_id}: {e}")
        await query.edit_message_text(
            f"❌ Error deleting receipt!\n\n"
            f"An error occurred while trying to delete the receipt. Please try again later."
        )
