#!/usr/bin/env python3
"""
Simple Hello World Telegram Bot
This script verifies that the environment is set up correctly.
"""

import configparser
import logging
from functools import wraps
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from database import Database

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

TELEGRAM_BOT_TOKEN = config.get('telegram', 'bot_token', fallback=None)
ALLOWED_USER_IDS = set()

# Parse allowed user IDs
allowed_ids_str = config.get('telegram', 'allowed_user_ids', fallback='')
if allowed_ids_str:
    ALLOWED_USER_IDS = set(int(uid.strip()) for uid in allowed_ids_str.split(',') if uid.strip())

# Database configuration
DB_HOST = config.get('database', 'host', fallback='localhost')
DB_PORT = config.getint('database', 'port', fallback=5432)
DB_NAME = config.get('database', 'name', fallback='receipts_db')
DB_USER = config.get('database', 'user', fallback='')
DB_PASSWORD = config.get('database', 'password', fallback='')


def authorized_only(func):
    """Decorator to restrict command access to authorized users only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        # If whitelist is configured, check authorization
        if ALLOWED_USER_IDS and user_id not in ALLOWED_USER_IDS:
            await update.message.reply_text('Sorry, you are not authorized to use this bot.')
            return

        return await func(update, context)
    return wrapper


@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the /start command is issued."""
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


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in config.ini file")
        logger.info("Please copy config.ini.example to config.ini and add your bot token")
        return

    # Initialize database
    db = Database(DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
    try:
        db.connect()
        db.initialize_schema()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.error("Could not connect to database. Check your config.ini settings.")
        return

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hello", hello))

    # Start the bot
    logger.info("Bot is starting...")
    if ALLOWED_USER_IDS:
        logger.info(f"Authorized users: {len(ALLOWED_USER_IDS)} user(s)")
    else:
        logger.warning("No user whitelist configured - all users can use the bot")
    logger.info("Press Ctrl+C to stop")

    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        db.close()


if __name__ == '__main__':
    main()
