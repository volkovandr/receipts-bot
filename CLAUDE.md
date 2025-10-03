# Development Notes for Claude AI

## Project Overview

This is a Telegram bot for processing receipt images and financial documents. The bot uses Claude AI for image analysis and text extraction.

## Architecture

### Core Components

1. **Telegram Bot Interface** (`python-telegram-bot`)
   - Handles user interactions
   - Receives images from users
   - Sends responses and generated files

2. **Claude AI Integration** (`anthropic`)
   - Processes receipt images
   - Extracts structured data (date, store, items, prices, total)
   - Returns JSON-formatted results

3. **PostgreSQL Database** (`psycopg2-binary`)
   - Stores receipt data
   - User information
   - Transaction history

4. **Excel Generator** (`openpyxl`)
   - Creates formatted Excel reports
   - Generates summaries and analytics

## Development Strategy

**IMPORTANT**: Features are being implemented incrementally, one at a time. Do not implement everything at once.

### Implementation Order

1. ✅ Environment setup
2. ⏳ Basic bot structure with image handling
3. ⏳ Claude AI integration for receipt processing
4. ⏳ Database schema and connection
5. ⏳ Data storage functionality
6. ⏳ Excel report generation
7. ⏳ Error handling and logging
8. ⏳ User commands and help system

## Current State

- Virtual environment created (Python 3.13)
- Dependencies installed successfully
  - `python-telegram-bot==21.10` for Python 3.13 compatibility
  - `psycopg2-binary==2.9.10` for Python 3.13 compatibility
- Basic bot with authorization implemented
  - User whitelist via `allowed_user_ids` in config.ini
  - `@authorized_only` decorator for command handlers
- Bot configuration in a file (config.ini.example)

## Development Environment

**Python Version**: 3.13
**Virtual Environment**: `venv/`

### Running the Bot
Always use the virtual environment Python interpreter:
```bash
./venv/bin/python bot.py
```

Or activate the environment first:
```bash
source venv/bin/activate
python bot.py
```

**IMPORTANT for Claude Code**: When the user asks to start the bot:
- Always run it in the background using the Bash tool with `run_in_background: true`
- This allows Claude to remain interactive and continue working
- Stop the bot when asked using `pkill -f "python bot.py"` or by finding the process ID

Example:
```bash
# Start in background
./venv/bin/python bot.py  # with run_in_background: true

# Stop when asked
pkill -f "python bot.py"
```

## Database Schema (Planned)

```sql
-- Users table
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Receipts table
CREATE TABLE receipts (
    receipt_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    image_file_id VARCHAR(255),
    store_name VARCHAR(255),
    receipt_date DATE,
    total_amount DECIMAL(10, 2),
    currency VARCHAR(10),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB
);

-- Receipt items table
CREATE TABLE receipt_items (
    item_id SERIAL PRIMARY KEY,
    receipt_id INTEGER REFERENCES receipts(receipt_id) ON DELETE CASCADE,
    item_name VARCHAR(255),
    quantity DECIMAL(10, 3),
    unit_price DECIMAL(10, 2),
    total_price DECIMAL(10, 2)
);
```

## Claude AI Prompt Strategy (Planned)

The bot will use Claude's vision capabilities to analyze receipt images. The prompt should:
- Request structured JSON output
- Specify fields to extract (store, date, items, prices, total)
- Handle various receipt formats
- Deal with poor image quality gracefully

## Next Steps

When ready to continue development:
1. Implement image handling in the bot
2. Set up Claude AI integration with vision API
3. Test receipt processing with sample images
4. Design and implement database schema
5. Add data persistence
6. Implement Excel export functionality

## Security & Best Practices

### User Authorization
- **IMPORTANT**: Always use the `@authorized_only` decorator for ALL command handlers and message handlers
- The decorator checks if the user is in the whitelist (config: `allowed_user_ids`)
- If no whitelist is configured, all users are allowed (development mode)
- Unauthorized users receive a rejection message automatically

Example:
```python
@authorized_only
async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Your command implementation
    pass
```

## Notes

- Keep error messages user-friendly
- Log all errors for debugging
- Handle rate limits for both Telegram and Claude APIs
- Consider adding receipt image preprocessing (rotation, contrast adjustment)
- Future: Add support for multiple currencies
- Future: Category classification for items
- Future: Monthly/weekly spending summaries
