#!/usr/bin/env python3
"""
Telegram Receipts Bot
Main application entry point.
"""

import logging
from functools import wraps
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import Config
from database import Database
from services.image_processor import ImageProcessor
from services.claude_service import ClaudeService
from handlers.commands import start, hello, receipts
from handlers.images import handle_photo, handle_document
from handlers.callbacks import (
    handle_view_items_callback, handle_view_image_callback, handle_delete_receipt_callback,
    handle_edit_receipt_callback, handle_delete_item_callback,
    handle_edit_amount_callback, handle_edit_category_callback,
    handle_category_select_callback, handle_category_create_callback,
    handle_back_to_summary_callback, handle_cancel_edit_callback
)
from handlers.messages import handle_text_message

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load configuration
config = Config()


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

    # Initialize Claude service
    claude_service = None
    if config.anthropic_api_key:
        claude_service = ClaudeService(
            api_key=config.anthropic_api_key,
            model=config.anthropic_model,
            prompt_template_path=config.anthropic_prompt_template
        )
        logger.info(f"Claude AI service initialized - Model: {config.anthropic_model}, "
                   f"Prompt: {config.anthropic_prompt_template}")
    else:
        logger.warning("Anthropic API key not configured - AI analysis will not be available")

    # Create the Application
    application = Application.builder().token(config.telegram_bot_token).build()

    # Store database, image processor, and claude service in bot_data for handlers to access
    application.bot_data['database'] = db
    application.bot_data['image_processor'] = image_processor
    application.bot_data['claude_service'] = claude_service

    # Wrap handlers with authorization decorator
    authorized_start = authorized_only(start)
    authorized_hello = authorized_only(hello)
    authorized_receipts = authorized_only(receipts)
    authorized_photo = authorized_only(handle_photo)
    authorized_document = authorized_only(handle_document)

    # Register command handlers
    application.add_handler(CommandHandler("start", authorized_start))
    application.add_handler(CommandHandler("hello", authorized_hello))
    application.add_handler(CommandHandler("receipts", authorized_receipts))

    # Register callback query handlers
    application.add_handler(CallbackQueryHandler(handle_view_items_callback, pattern="^view_items_"))
    application.add_handler(CallbackQueryHandler(handle_view_image_callback, pattern="^view_image_"))
    application.add_handler(CallbackQueryHandler(handle_delete_receipt_callback, pattern="^delete_receipt_"))
    application.add_handler(CallbackQueryHandler(handle_edit_receipt_callback, pattern="^edit_receipt_"))
    application.add_handler(CallbackQueryHandler(handle_delete_item_callback, pattern="^del_item_"))
    application.add_handler(CallbackQueryHandler(handle_edit_amount_callback, pattern="^edit_amt_"))
    application.add_handler(CallbackQueryHandler(handle_edit_category_callback, pattern="^edit_cat_"))
    application.add_handler(CallbackQueryHandler(handle_category_select_callback, pattern="^select_cat_"))
    application.add_handler(CallbackQueryHandler(handle_category_create_callback, pattern="^create_cat_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_summary_callback, pattern="^back_summary_"))
    application.add_handler(CallbackQueryHandler(handle_cancel_edit_callback, pattern="^cancel_edit"))

    # Register message handlers
    application.add_handler(MessageHandler(filters.PHOTO, authorized_photo))
    application.add_handler(MessageHandler(filters.Document.IMAGE, authorized_document))
    # Text message handler for editing workflows (must be registered AFTER specific handlers)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

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
