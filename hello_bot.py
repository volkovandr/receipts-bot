#!/usr/bin/env python3
"""
Simple Hello World Telegram Bot
This script verifies that the environment is set up correctly.
"""

import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the /start command is issued."""
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


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        print("Please copy .env.example to .env and add your bot token")
        return

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hello", hello))

    # Start the bot
    print("Bot is starting...")
    print("Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
