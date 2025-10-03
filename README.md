# Receipts Bot

A Telegram bot that processes receipt images and financial documents using Claude AI, stores the data in PostgreSQL, and generates Excel reports.

## Features (In Development)

- 📸 Accept receipt images from users
- 🤖 Process images using Claude AI for text extraction
- 💾 Store receipt data in PostgreSQL database
- 📊 Generate Excel reports on demand

## Setup

### 1. Prerequisites

- Python 3.8 or higher
- PostgreSQL database
- Telegram Bot Token ([get one from BotFather](https://t.me/botfather))
- Anthropic API Key ([get one from Anthropic](https://console.anthropic.com/))

### 2. Installation

1. Clone the repository and navigate to the project directory

2. Create a virtual environment:
```bash
python3 -m venv venv
```

3. Activate the virtual environment:
```bash
# On Linux/Mac
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Set up environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `ANTHROPIC_API_KEY`: Your Claude API key
- Database credentials

### 3. Test the Setup

Run the hello world bot to verify everything is working:

```bash
python hello_bot.py
```

If successful, you should see "Bot is starting..." and be able to interact with your bot on Telegram using `/start` and `/hello` commands.

## Project Structure

```
receipts-bot-2/
├── hello_bot.py          # Simple test bot
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
├── .gitignore           # Git ignore rules
├── README.md            # This file
└── CLAUDE.md            # Development notes for Claude AI
```

## Development

This project is being developed incrementally. Features will be added step by step.

## License

This project is for personal use.
