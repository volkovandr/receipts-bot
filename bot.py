#!/usr/bin/env python3
"""
Simple Hello World Telegram Bot
This script verifies that the environment is set up correctly.
"""

import logging
import os
from functools import wraps
from pathlib import Path
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import Config
from database import Database
from image_processor import ImageProcessor

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load configuration
config = Config()

# Image storage directory
IMAGES_DIR = Path("images/orig")


def authorized_only(func):
    """Decorator to restrict command access to authorized users only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        # If whitelist is configured, check authorization
        if config.allowed_user_ids and user_id not in config.allowed_user_ids:
            await update.message.reply_text('Sorry, you are not authorized to use this bot.')
            return

        return await func(update, context)
    return wrapper


@authorized_only
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


@authorized_only
async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a hello message when the /hello command is issued."""
    user_name = update.effective_user.first_name
    await update.message.reply_text(f'Hello {user_name}! 👋')


@authorized_only
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle receipt photos sent by users (camera images)."""
    await _process_image(update, context, is_document=False)


@authorized_only
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle receipt photos sent as documents (gallery images)."""
    # Only process image documents
    if update.message.document.mime_type and update.message.document.mime_type.startswith('image/'):
        await _process_image(update, context, is_document=True)
    else:
        await update.message.reply_text('Please send image files only.')


async def _process_image(update: Update, context: ContextTypes.DEFAULT_TYPE, is_document: bool) -> None:
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
                    '⏳ Ready for AI analysis...'
                )
            else:
                logger.warning(f"Image processing failed for image {image_id}")

                # Update user with fallback
                await status_message.edit_text(
                    '✅ Image received!\n'
                    '⚠️ Using original image\n'
                    '⏳ Ready for processing...'
                )
        else:
            # No image processor available
            await status_message.edit_text(
                '✅ Image received and saved!\n'
                '⏳ Ready for processing...'
            )

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await update.message.reply_text(
            '❌ Sorry, there was an error processing your image. Please try again.'
        )


def main() -> None:
    """Start the bot."""
    # Validate configuration
    if not config.validate():
        return

    # Initialize database
    db = Database(config.db_host, config.db_port, config.db_name, config.db_user, config.db_password)
    try:
        db.connect()
        db.initialize_schema()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.error("Could not connect to database. Check your config.ini settings.")
        return

    # Initialize image processor
    image_processor = ImageProcessor()
    logger.info("Image processor initialized")

    # Create the Application
    application = Application.builder().token(config.telegram_bot_token).build()

    # Store database and image processor in bot_data for handlers to access
    application.bot_data['database'] = db
    application.bot_data['image_processor'] = image_processor

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hello", hello))

    # Register message handlers
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))

    # Start the bot
    logger.info("Bot is starting...")
    if config.allowed_user_ids:
        logger.info(f"Authorized users: {len(config.allowed_user_ids)} user(s)")
    else:
        logger.warning("No user whitelist configured - all users can use the bot")
    logger.info("Press Ctrl+C to stop")

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        db.close()


if __name__ == '__main__':
    main()
