"""
Image handling for receipt photos and documents.
"""
import logging
import os
from pathlib import Path
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Image storage directory
IMAGES_DIR = Path("images/orig")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle receipt photos sent by users (camera images)."""
    await process_image(update, context, is_document=False)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle receipt photos sent as documents (gallery images)."""
    # Only process image documents
    if update.message.document.mime_type and update.message.document.mime_type.startswith('image/'):
        await process_image(update, context, is_document=True)
    else:
        await update.message.reply_text('Please send image files only.')


async def process_image(update: Update, context: ContextTypes.DEFAULT_TYPE, is_document: bool) -> None:
    """
    Process and save receipt image.

    Args:
        update: Telegram update object
        context: Telegram context
        is_document: True if image was sent as document, False if sent as photo
    """
    try:
        # Get the file object
        if is_document:
            file = await update.message.document.get_file()
            file_size = update.message.document.file_size
            mime_type = update.message.document.mime_type
        else:
            # For photos, get the largest available size
            photo = update.message.photo[-1]
            file = await photo.get_file()
            file_size = photo.file_size
            mime_type = 'image/jpeg'

        # Create images directory if it doesn't exist
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        user_id = update.effective_user.id
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = Path(file.file_path).suffix or '.jpg'
        filename = f"{user_id}_{timestamp}{file_extension}"
        file_path = IMAGES_DIR / filename

        # Download and save the file
        await file.download_to_drive(file_path)
        logger.info(f"Image saved: {file_path}")

        # Get database connection from context
        db = context.bot_data.get('database')
        if not db:
            logger.error("Database connection not available")
            await update.message.reply_text('Error: Database not available.')
            return

        # Save image metadata to database
        image_id = db.insert_image(
            user_id=user_id,
            telegram_file_id=file.file_id,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=mime_type
        )

        # Create receipt record with status 'created'
        receipt_id = db.insert_receipt(
            image_id=image_id,
            user_id=user_id,
            status='created'
        )

        logger.info(f"Receipt {receipt_id} created for image {image_id}")

        # Initial confirmation to user
        status_message = await update.message.reply_text(
            '✅ Image received!\n'
            '🔄 Pre-processing image...'
        )

        # Process the image (crop, grayscale, resize)
        image_processor = context.bot_data.get('image_processor')
        if image_processor:
            processed_path = image_processor.process_receipt_image(str(file_path))

            if processed_path:
                # Get file size of processed image
                processed_size = os.path.getsize(processed_path)

                # Update database with processed image info
                db.update_image_processed(image_id, processed_path, processed_size)

                # Update receipt status to 'pre-processed'
                db.update_receipt_status(receipt_id, 'pre-processed')

                logger.info(f"Image {image_id} processed successfully, receipt {receipt_id} status: pre-processed")

                # Update user with success
                await status_message.edit_text(
                    '✅ Image received!\n'
                    '✅ Pre-processing complete!\n'
                    '📸 Receipt detected and optimized\n'
                    '🤖 Analyzing with AI...'
                )

                # Import here to avoid circular dependency
                from services.receipt_analyzer import analyze_receipt_with_claude

                # Analyze with Claude using processed image
                await analyze_receipt_with_claude(
                    context, db, receipt_id, image_id, processed_path, status_message
                )
            else:
                logger.warning(f"Image processing failed for image {image_id}, using original")

                # Update user with fallback
                await status_message.edit_text(
                    '✅ Image received!\n'
                    '⚠️ Using original image\n'
                    '🤖 Analyzing with AI...'
                )

                # Import here to avoid circular dependency
                from services.receipt_analyzer import analyze_receipt_with_claude

                # Analyze with Claude using original image
                await analyze_receipt_with_claude(
                    context, db, receipt_id, image_id, str(file_path), status_message
                )
        else:
            logger.error("Image processor not available")
            await status_message.edit_text(
                '❌ Image processor not available. Please contact admin.'
            )

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await update.message.reply_text(
            '❌ Sorry, there was an error processing your image. Please try again.'
        )
