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
2. ✅ Basic bot structure (commands working)
3. ✅ Configuration module
4. ✅ Database connection and schema initialization
5. ✅ Database schema design (tables for receipts)
6. ✅ Image handling in bot
7. ✅ Image pre-processing
8. ⏳ Claude AI integration for receipt processing
9. ⏳ Excel report generation
10. ⏳ User commands and help system

## Current State

### Completed Features
- ✅ Virtual environment created (Python 3.13)
- ✅ Dependencies installed successfully
  - `python-telegram-bot==21.10` for Python 3.13 compatibility
  - `psycopg2-binary==2.9.10` for Python 3.13 compatibility
  - `anthropic` for Claude AI integration
  - `openpyxl` for Excel generation
  - `Pillow==10.4.0`, `opencv-python-headless==4.10.0.84`, `numpy==2.1.3` for image processing
- ✅ Basic bot with authorization implemented
  - User whitelist via `allowed_user_ids` in config.ini
  - `@authorized_only` decorator for command handlers
  - `/start` and `/hello` commands working
- ✅ **Configuration module** (`config.py`)
  - Centralized configuration management
  - Loads from config.ini file
  - Handles Telegram, Database, and Anthropic settings
  - Built-in validation logic
- ✅ **Database integration** (`database.py`)
  - PostgreSQL connection management
  - Automatic schema initialization from schema.sql on startup
  - Uses dedicated schema: `app_receipts_bot`
  - Table existence checking (prevents re-initialization)
  - Proper error handling and logging
- ✅ **Database schema** (`schema.sql`)
  - Schema created: `app_receipts_bot`
  - Version tracking table implemented
  - Complete data model with 5 tables: user, image, receipt, receipt_item, category
- ✅ **Image handling** (`bot.py`)
  - Handles both photo messages (camera) and document messages (gallery)
  - Downloads images to `./images/orig/` directory
  - Generates unique filenames: `{user_id}_{timestamp}.{ext}`
  - Stores image metadata in database (file_id, path, size, mime_type)
  - Creates receipt record with status 'created' when image is received
  - Links receipt to image and user
- ✅ **Image pre-processing** (`image_processor.py`)
  - **Grayscale conversion** - Converts to grayscale first for optimal processing
  - **Multi-strategy receipt detection and cropping**:
    - Strategy 1: Edge detection with contour filtering
    - Strategy 2: Brightness-based detection (best for dark backgrounds)
    - Strategy 3: Threshold-based detection for white receipts
  - **Intelligent cropping validation** - Ensures crops are between 20-90% of original area
  - **Smart resizing** - Reduces to max 1200px height (maintains aspect ratio)
  - **JPEG compression** - Quality=85 for optimal size/quality balance
  - **Progressive user feedback** - Updates message after each processing step
  - Saves processed images to `./images/processed/` directory
  - Updates database with processed image path and size
  - Updates receipt status to 'pre-processed' after successful processing
  - Robust error handling - falls back to original image if all strategies fail
  - **Performance**: 17-64% file size reduction depending on background type
- ✅ **User management**
  - `/start` command inserts/updates user in database
  - Uses Telegram username or falls back to first name/full name
  - Updates username if changed on subsequent `/start` commands

### Project Structure
```
receipts-bot-2/
├── bot.py              # Main bot application
├── config.py           # Configuration module
├── database.py         # Database operations module
├── image_processor.py  # Image processing module
├── schema.sql          # Database schema
├── config.ini          # Configuration file (gitignored)
├── requirements.txt    # Python dependencies
├── images/             # Image storage (gitignored)
│   ├── orig/          # Original uploaded images
│   └── processed/     # Pre-processed images (cropped, grayscale, resized)
└── venv/              # Virtual environment
```

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

## Database Schema

The database uses schema `app_receipts_bot` with the following entities:

1. **user** - Telegram users interacting with the bot
   - Primary key: `user_id` (Telegram user ID)
   - Tracks username, timestamps

2. **image** - Uploaded receipt images
   - Stores both original and processed file paths
   - References: user
   - Contains Telegram `file_id` for re-downloading
   - Tracks file size, mime type

3. **receipt** - Processed receipt data
   - References: image, user
   - Contains: merchant, date, time, total amount, currency
   - Processing status tracking: created → pre-processed → analyzed → completed/failed
   - Status 'created' is set when image is first received
   - Status 'pre-processed' is set when image is prepared for AI analysis
   - Stores raw Claude AI response in `raw_data` (JSONB)

4. **receipt_item** - Individual line items from receipts
   - References: receipt, category (optional)
   - Contains: item name, quantity, unit price, total price

5. **category** - Item categories for expense tracking
   - Used to classify receipt items (groceries, utilities, etc.)
   - Assigned to individual items, not whole receipts

All tables include `created_at` and `updated_at` timestamps (TIMESTAMPTZ).
Full schema definition in [schema.sql](schema.sql).

## Claude AI Prompt Strategy (Planned)

The bot will use Claude's vision capabilities to analyze receipt images. The prompt should:
- Request structured JSON output
- Specify fields to extract (store, date, items, prices, total)
- Handle various receipt formats
- Deal with poor image quality gracefully

## Next Steps

When ready to continue development:
1. Set up Claude AI integration with vision API
2. Process receipt images and extract data
3. Update receipt records with extracted data
4. Implement Excel export functionality
5. Add user commands for viewing and exporting receipts

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
