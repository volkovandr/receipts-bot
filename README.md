# Receipts Bot

A Telegram bot that processes receipt images using Claude AI vision capabilities, stores structured data in PostgreSQL, and provides interactive receipt management.

## Features

### ✅ Implemented
- 📸 **Image Processing**: Accept receipt images from camera or gallery
- 🔍 **Smart Pre-processing**: Automatic cropping, grayscale conversion, and optimization
- 🤖 **AI Analysis**: Claude AI vision API extracts merchant, items, prices, and categories
- 💾 **Data Storage**: PostgreSQL database with normalized schema
- 📊 **Category Management**: predefined categories with AI fine-tuning notes
- 🏪 **Merchant Deduplication**: Fuzzy matching to prevent duplicate merchants
- ✏️ **Receipt Editing**: Interactive interface to edit items, amounts, and categories
- 🗂️ **Receipt Listing**: View recent receipts with `/receipts` command
- 🗑️ **Soft Delete**: Delete receipts and items without losing data
- 🔒 **Authorization**: Whitelist-based access control
- 💰 **Total Validation**: Automatic consistency checks between receipt total and item sum

### 🚧 Planned
- 📊 Excel report generation
- 📈 Spending analytics and summaries
- 📅 Date range filtering
- 💱 Multi-currency support

## Setup

### 1. Prerequisites

- Python 3.13 or higher
- PostgreSQL 13+ with `pg_trgm` extension (for fuzzy matching)
- Telegram Bot Token ([get one from BotFather](https://t.me/botfather))
- Anthropic API Key ([get one from Anthropic](https://console.anthropic.com/))

### 2. Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd receipts-bot-2
```

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

5. Set up configuration:
```bash
cp config.ini.example config.ini
```

Edit `config.ini` and configure:

```ini
[telegram]
bot_token = YOUR_BOT_TOKEN
allowed_user_ids = 123456789,987654321  # Optional: whitelist user IDs

[database]
host = localhost
port = 5432
database = receipts_db
user = postgres
password = YOUR_DB_PASSWORD

[anthropic]
api_key = YOUR_ANTHROPIC_API_KEY
model = claude-sonnet-4-5-20250929  # or any Claude model with vision
```

### 3. Database Setup

The bot automatically creates the schema on first run, but you need to:

1. Create the PostgreSQL database:
```sql
CREATE DATABASE receipts_db;
```

2. Enable the pg_trgm extension (for fuzzy matching):
```sql
\c receipts_db
CREATE EXTENSION pg_trgm;
```

3. Add your categories in the `category` table after the bot has been started and created the schema.

### 4. Run the Bot

```bash
python bot.py
```

Or run in background (recommended for development):
```bash
./venv/bin/python bot.py &
```

## Usage

### Commands

- `/start` - Initialize and show welcome message
- `/hello` - Get a friendly greeting
- `/receipts` - Show last 3 receipts (default)
- `/receipts N` - Show last N receipts (max 10)

### Processing Receipts

1. Send a receipt image to the bot (photo or document)
2. Bot automatically:
   - Pre-processes the image (crop, grayscale, resize)
   - Analyzes with Claude AI
   - Extracts merchant, items, prices, categories
   - Validates total consistency
   - Sends formatted summary with buttons

3. Interact with receipt:
   - 📋 **View items** - See all items in read-only mode
   - ✏️ **Edit receipt** - Navigate items, edit amounts, change categories
   - 🗑️ **Delete receipt** - Soft delete (preserves data)
   - 🔍 **View processed image** - See the exact image analyzed by AI

### Editing Receipts

1. Click "✏️ Edit receipt" button
2. Navigate items with Previous/Next buttons
3. For each item you can:
   - Delete item (soft delete)
   - Edit amount (validates 0.01-99999.99)
   - Change category (fuzzy search with 30% similarity)
   - Create new category on-the-fly

## Project Structure

```
receipts-bot-2/
├── bot.py                  # Main application entry point
├── config.py               # Configuration management
├── database.py             # Unified database interface (facade pattern)
├── schema.sql              # PostgreSQL schema definition
├── prompt.txt              # Claude AI prompt template
├── config.ini              # Configuration file (gitignored)
├── requirements.txt        # Python dependencies
│
├── handlers/               # Telegram bot handlers
│   ├── commands.py        # Command handlers (/start, /hello, /receipts)
│   ├── images.py          # Image upload handlers
│   ├── callbacks.py       # Inline button callbacks
│   └── messages.py        # Text message handlers (editing workflows)
│
├── services/               # Business logic layer
│   ├── claude_service.py    # Claude AI integration
│   ├── image_processor.py   # Image pre-processing
│   ├── receipt_analyzer.py  # Receipt analysis orchestration
│   └── receipt_formatter.py # Receipt summary formatting
│
├── repositories/           # Data access layer
│   ├── database_connection.py    # Connection & schema management
│   ├── user_repository.py        # User operations
│   ├── image_repository.py       # Image operations
│   ├── category_repository.py    # Category operations
│   ├── merchant_repository.py    # Merchant operations
│   ├── transaction_repository.py # Transaction operations
│   ├── ai_analysis_repository.py # AI analysis tracking
│   └── receipt_repository.py     # Receipt & items operations
│
├── images/                 # Image storage (gitignored)
│   ├── orig/              # Original uploaded images
│   └── processed/         # Pre-processed images
│
└── migrations/            # Database migrations
    └── 001_add_receipt_item_is_deleted.sql
```

## Architecture

The project follows a **clean three-tier architecture**:

- **Presentation Layer** (`handlers/`) - Telegram interaction
- **Business Logic Layer** (`services/`) - Processing and orchestration
- **Data Access Layer** (`repositories/`) - Database operations

Key design patterns:
- **Repository Pattern** - Separates data access from business logic
- **Facade Pattern** - `database.py` provides simple interface to repositories
- **Dependency Injection** - Repositories receive connection in constructor

## Database Schema

- `user` - Telegram users
- `category` - Item categories (71 predefined + user-created)
- `merchant` - Store information (with deduplication)
- `image` - Uploaded receipt images (original + processed)
- `transaction` - Financial transaction details
- `ai_analysis` - Claude AI processing results (with token tracking)
- `receipt` - Receipt records (with soft delete)
- `receipt_item` - Individual line items (with soft delete)

All tables use TIMESTAMPTZ for `created_at` and `updated_at` fields.

## Development

See [CLAUDE.md](CLAUDE.md) for detailed development notes and architecture documentation.

### Running in Development

```bash
# Start bot in background
./venv/bin/python bot.py &

# Stop bot
pkill -f "python bot.py"
```

## Security

- **Whitelist Authorization**: Configure `allowed_user_ids` in config.ini
- **Receipt Ownership**: All operations verify user owns the receipt
- **SQL-Level Security**: Database queries include user_id checks
- **Application-Level Checks**: Handlers verify authorization

## Token Tracking

All Claude AI API calls are tracked in the `ai_analysis` table:
- `input_tokens` - Tokens sent to API
- `output_tokens` - Tokens received from API
- Useful for cost monitoring and optimization

## License

Please refer to the [LICENSE](./LICENSE) file.

This project is for personal use.
