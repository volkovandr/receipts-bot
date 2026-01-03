# Development Notes for Claude AI

## Project Overview

This is a Telegram bot for processing receipt images and financial documents. The bot uses Claude AI for image analysis and text extraction. Additionally, a console-based UI (using Textual framework) provides a local interface for bulk editing and managing receipts.

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

5. **Console UI** (`textual`)
   - Terminal-based user interface for receipt management
   - Full CRUD operations on receipts and items
   - Sorting, filtering, and bulk editing capabilities
   - Works over SSH for remote access

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
8. ✅ Claude AI integration for receipt processing
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
  - `pdf2image==1.17.0` for PDF document support
  - `textual==1.0.0` for console UI
- ✅ Basic bot with authorization implemented
  - User whitelist via `allowed_user_ids` in config.ini
  - `@authorized_only` decorator for command handlers
  - `/start` and `/hello` commands working
- ✅ **Configuration module** (`config.py`)
  - Centralized configuration management
  - Loads from config.ini file
  - Handles Telegram, Database, Anthropic, Prometheus, and Receipt Processing settings
  - Receipt processing: `default_category` for uncategorized items
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
- ✅ **Image handling** (`handlers/images.py`, `bot.py`)
  - Handles photo messages (camera), document messages (gallery), and PDF files
  - **PDF support**: Converts PDF documents to high-quality images (300 DPI)
  - Downloads files to `./images/orig/` directory
  - Generates unique filenames: `{user_id}_{timestamp}.{ext}`
  - Stores image metadata in database (file_id, path, size, mime_type)
  - Creates receipt record with status 'created' when image is received
  - Links receipt to image and user
  - **User notes**: Extracts caption from photo/document message as user-provided notes
  - **Requires**: `poppler-utils` system package for PDF conversion (`sudo apt install poppler-utils`)
- ✅ **User-Provided Notes** (`schema.sql`, `handlers/images.py`, `handlers/messages.py`, `services/claude_service.py`, `services/receipt_analyzer.py`)
  - Users can add optional text notes when sending receipt images
  - **Two methods**:
    1. **Caption method**: Add caption to photo/document in Telegram
    2. **Preceding message method**: Send text message, then share image from external app (within 10 seconds)
  - Caption is stored in `receipt.user_notes` field in database
  - Notes are passed to Claude AI to guide analysis
  - **Use cases**:
    - Override category detection: "mark everything as Food"
    - Clarify unclear items: "the coffee was for a business meeting"
    - Add context: "this receipt has items for two different projects"
  - Notes appear as "USER NOTE:" prefix in Claude prompt
  - Helps Claude make better decisions about categorization and extraction
  - **Technical details**:
    - Text messages stored temporarily in `context.user_data` with timestamp
    - 10-second window for matching text with subsequent image
    - Automatic cleanup of old pending notes
- ✅ **Image pre-processing** (`services/image_processor.py`)
  - **Grayscale conversion** - Converts to grayscale first for optimal processing
  - **Smart cropping** - Skip cropping for PDFs (already scanned), apply to photos
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
- ✅ **Skew Detection and Correction** (`services/skew_detector.py`, `services/deskew_service.py`, `handlers/images.py`, `handlers/callbacks.py`)
  - **Automatic skew detection** - Analyzes images after pre-processing using Text Line Contours method
  - **Regional analysis** - Splits images into regions to detect non-uniform skew (curved receipts)
  - **Smart threshold** - Configurable threshold (default: 1.0°) to trigger user warning
  - **User choice workflow** - When significant skew detected (> threshold):
    - Shows warning with skew angle and affected region (upper/middle/lower/entire)
    - Three options: "🔄 Deskew & Process", "▶️ Process As-Is", "🗑️ Discard & Rescan"
  - **Shear transformation** - Corrects skew using vertical shear (preserves width, no expansion)
  - **PDF vs Photo handling**:
    - PDF source: Creates new processed file after deskewing
    - Photo source: Replaces existing processed image in-place
  - **Authorization checks** - All operations verify user ownership at SQL and application level
  - **Configurable parameters** (`config.ini`):
    - `threshold`: Skew angle threshold in degrees (default: 1.0)
    - `min_contours`: Minimum text line contours for reliable detection (default: 3)
    - `kernel_width/height`: Morphological kernel size for text line detection (50x2)
  - **Performance**: Adds ~0.5-2 seconds to processing, deskewing is fast (< 0.1 seconds)
  - **Seamless flow**: Minimal skew (≤ threshold) continues automatically to Claude analysis
- ✅ **User management** (`handlers/commands.py`)
  - `/start` command inserts/updates user in database
  - Uses Telegram username or falls back to first name/full name
  - Updates username if changed on subsequent `/start` commands
- ✅ **Claude AI Integration** (`services/claude_service.py`)
  - Vision API integration with configurable model selection
  - Automatic prompt template loading with category injection
  - Extracts structured data: merchant, transaction, items with index-based categories
  - **Optimized output format**: Separate items and categories arrays to reduce token usage
  - Returns token usage (input/output) for cost tracking
  - Handles markdown code blocks in responses
  - Robust error handling for API failures and refusals
  - Graceful handling of content policy refusals (QR codes, tax IDs, etc.)
  - **Smart prompt**: Emphasizes extracting LOCAL branch address (not headquarters)
- ✅ **Merchant Deduplication** (`repositories/merchant_repository.py`)
  - Case-insensitive name matching (`REWE` = `rewe` = `Rewe`)
  - Fuzzy address matching using PostgreSQL `pg_trgm` extension
  - Similarity threshold: 30% (prevents duplicates from minor address variations)
  - SQL-based fuzzy matching for performance
- ✅ **Receipt Total Consistency Check** (`services/receipt_analyzer.py`, `repositories/receipt_repository.py`)
  - Validates receipt total against sum of individual items
  - Tolerance: 0.01 currency units for floating-point errors
  - Status `completed/inconsistent` if totals don't match
  - Shows detailed mismatch information to user
- ✅ **Category Breakdown Display** (`services/receipt_analyzer.py`, `repositories/receipt_repository.py`)
  - Groups items by category with totals
  - Shows item count per category
  - Sorted by spending amount (highest first)
  - Clear, formatted summary message
- ✅ **Soft Delete Feature** (`handlers/callbacks.py`, `repositories/receipt_repository.py`, `schema.sql`)
  - Inline "🗑️ Delete this receipt" button in summary
  - Sets `is_deleted = TRUE` (data preserved in database)
  - User-friendly confirmation message
  - Authorization: users can only delete their own receipts
- ✅ **View Processed Image** (`handlers/callbacks.py`, `repositories/receipt_repository.py`)
  - Inline "🔍 View processed image" button in summary
  - Sends the exact image analyzed by Claude AI
  - Helps troubleshoot cropping issues
  - Authorization: users can only view their own receipt images
- ✅ **Security & Authorization** (`bot.py`, `handlers/callbacks.py`, `repositories/receipt_repository.py`)
  - All receipt operations verify ownership (user_id check)
  - SQL-level authorization: `WHERE receipt_id = %s AND user_id = %s`
  - Application-level checks in callback handlers
  - Audit logging for unauthorized access attempts
  - Defense in depth: both database and application layers verify ownership
- ✅ **Code Architecture Refactoring**
  - Clean separation into handlers/, services/, repositories/
  - Repository pattern for all data access operations
  - Facade pattern in database.py for backward compatibility
  - Single Responsibility Principle - each module has one clear purpose
  - Maximum file size reduced from 794 to 394 lines
- ✅ **AI Category Notes** (`schema.sql`, `repositories/category_repository.py`, `services/claude_service.py`)
  - Added `ai_notes` field to category table for custom AI instructions
  - Categories with notes are injected into Claude AI prompt
  - Allows fine-tuning category assignments without code changes
  - Example: "Use Child: Food for Haribo Bears instead of Food: Sweets"
  - Notes fetched via `get_categories_with_notes()` and passed to Claude
  - Prompt emphasizes prioritizing category-specific notes over general logic
- ✅ **Receipt Editing Feature** (`handlers/callbacks.py`, `handlers/messages.py`, `services/receipt_formatter.py`)
  - **View Items button**: Read-only display of all receipt items (no button limit issues)
  - **Edit Receipt button**: Paginated interface showing ONE item at a time
  - **Pagination**: Previous/Next buttons to navigate between items (works with 30+ items)
  - **Delete items**: Soft delete with `is_deleted` flag, returns to edit view
  - **Edit amounts**: Conversational flow, validates input (0.01-99999.99), returns to edit view
  - **Change categories**: Fuzzy search with 30% similarity threshold using pg_trgm
  - **Create categories**: Users can create new categories on-the-fly (title-cased)
  - **Total consistency**: Compares original receipt total with non-deleted items sum
  - **Receipt formatter**: Reusable summary generation in `services/receipt_formatter.py`
  - **Smart navigation**: Edit operations return to item view; only "Back to summary" exits to summary
  - **Conversation state**: Uses `context.user_data` for multi-step editing flows
  - **Authorization**: All operations verify user ownership at SQL and application level
- ✅ **Receipt Listing Command** (`handlers/commands.py`, `repositories/receipt_repository.py`)
  - `/receipts` command shows recent receipts (default: 3 receipts)
  - Optional argument: `/receipts N` to show N receipts (max 10)
  - Sorted by creation date (most recent first)
  - Only shows non-deleted receipts owned by the user
  - User-friendly error messages for invalid input
- ✅ **Prompt Optimization for Token Reduction** (`prompt.txt`, `services/receipt_validator.py`, `config.py`)
  - **Index-based category assignment**: Items separated from category assignments to eliminate repetition
  - **Category ID-based assignment**: Claude returns category IDs instead of names for additional token savings
  - **Removed unused fields**: Eliminated `article_number` and `suggested_category` (~5-10 tokens per item)
  - **Optional quantity/unit_price**: Only included when quantity > 1 (~10-15 tokens saved per single-quantity item)
  - **Token savings**: 25-35% reduction on average receipts, 35-45% on large receipts (40+ items)
  - **Cost impact**: ~$500-750 annual savings at 100K receipts/year
  - **New output format**:
    - Items array: `[{"name": "Milk", "total_price": 1.99}, ...]`
    - Categories array: `[{"id": 23, "items": [0, 1, 2]}, ...]` (uses category IDs instead of names)
  - **Validation module** (`services/receipt_validator.py`):
    - Validates category IDs exist in database before assignment
    - Validates category indices (bounds checking, type checking, duplicate detection)
    - Enriches items with both category name and category_id fields after validation
    - Defaults quantity to 1 and calculates unit_price when missing
    - Assigns default category to uncategorized items
    - Raises `ValueError` for validation failures (invalid IDs, out-of-bounds, duplicates)
  - **Configuration**: `[receipt_processing]` section with `default_category` setting
  - **Database storage**: `ai_analysis.raw_data` stores Claude's optimized response (before enrichment)
  - **Backward compatibility**: No database schema changes, enrichment happens in-memory
- ✅ **Console UI for Receipt Management** (`console_ui/`)
  - **Terminal-based interface** using Textual framework (works over SSH)
  - **Receipt list view**: DataTable with 13 columns (ID, Date, Time, Merchant, City, Items, Currency, Totals, Discrepancy, Status, Category, Deleted)
  - **Receipt detail view**: Shows receipt header and all items with full details
  - **Item editing** (press 'Enter'): Modal dialog to edit name, amount, category
  - **Item CRUD**: Add ('a'), delete ('Delete'), undelete ('Ctrl+Delete') items
  - **Receipt delete/undelete**: Soft delete receipts ('Delete'/'Ctrl+Delete'), toggle visibility ('h')
  - **Merchant editing** (press 'm'): Update merchant info (affects all receipts from that merchant)
  - **Merchant switching** (press 'Shift+M'): Switch receipt to different merchant with search or create new
  - **Date/time editing** (press 't'): Edit receipt transaction date and time with validation
  - **Total amount editing** (press 'Shift+T'): Edit receipt total amount with validation
  - **Sorting** (press 's'): Cycle through Date/Merchant/Total/Status, toggle direction (↓/↑)
  - **Filtering** (press 'f'): Filter by merchant name (partial match) and status
  - **Receipt count**: Shows filtered/total count at top of list
  - **Real-time updates**: Header totals and discrepancy indicators update immediately
  - **Visual discrepancy indicators**: Receipt detail view shows discrepancy amount and uses color-coded background (red for discrepancy, green when resolved)
  - **Cursor preservation**: Selection stays on same item/receipt after operations
  - **Authorization**: All operations verify user ownership at database level
  - See [ADDING_UI.md](ADDING_UI.md) for complete implementation details

### Project Structure
```
receipts-bot-2/
├── bot.py                  # Main application entry point & handler registration
├── config.py               # Configuration management (50 lines)
├── database.py             # Unified database interface - facade pattern (150 lines)
├── schema.sql              # Database schema
├── prompt.txt              # Claude AI prompt template
├── config.ini              # Configuration file (gitignored)
├── requirements.txt        # Python dependencies
│
├── handlers/               # Telegram bot handlers (Telegram interaction layer)
│   ├── commands.py        # Command handlers (/start, /hello, /receipts)
│   ├── images.py          # Image upload handlers (photo & document)
│   ├── callbacks.py       # Inline button callback handlers (view, edit, delete)
│   └── messages.py        # Text message handlers (editing workflows)
│
├── services/               # Business logic layer
│   ├── claude_service.py     # Claude AI integration
│   ├── image_processor.py    # Image pre-processing
│   ├── skew_detector.py      # Skew detection using Text Line Contours method
│   ├── deskew_service.py     # Deskewing using shear transformation
│   ├── receipt_analyzer.py   # Receipt analysis orchestration
│   ├── receipt_validator.py  # Receipt data validation & enrichment
│   └── receipt_formatter.py  # Receipt summary formatting (reusable)
│
├── repositories/           # Data access layer (Repository pattern)
│   ├── database_connection.py    # Connection & schema management
│   ├── user_repository.py        # User data operations
│   ├── image_repository.py       # Image data operations
│   ├── category_repository.py    # Category data operations
│   ├── merchant_repository.py    # Merchant data operations
│   ├── transaction_repository.py # Transaction data operations
│   ├── ai_analysis_repository.py # AI analysis data operations
│   └── receipt_repository.py     # Receipt & items data operations
│
├── console_ui/             # Console UI (Textual TUI)
│   ├── app.py             # Main TUI application entry point
│   ├── screens/           # TUI screens
│   │   ├── receipt_list.py    # Receipt list view (DataTable)
│   │   └── receipt_detail.py  # Receipt detail view with items
│   └── widgets/           # Reusable UI components
│       ├── item_editor.py          # Item editing modal
│       ├── item_creator.py         # Item creation modal
│       ├── merchant_editor.py      # Merchant editing modal
│       ├── merchant_switcher.py    # Merchant switching modal (search existing)
│       ├── merchant_creator.py     # Merchant creation modal (create new)
│       ├── receipt_date_editor.py  # Receipt date/time editing modal
│       ├── receipt_total_editor.py # Receipt total amount editing modal
│       └── filter_dialog.py        # Filtering modal
│
├── images/                 # Image storage (gitignored)
│   ├── orig/              # Original uploaded images
│   └── processed/         # Pre-processed images (cropped, grayscale, resized)
│
└── venv/                  # Virtual environment
```

### Architecture Layers

The codebase follows a clean **three-tier architecture**:

```
┌─────────────────────────────────────────────┐
│  bot.py (Entry Point)                       │
│  - Application initialization               │
│  - Handler registration                     │
│  - Authorization decorator                  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  handlers/ (Presentation Layer)             │
│  - Telegram message/command handlers        │
│  - User interaction & feedback              │
│  - Input validation                         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  services/ (Business Logic Layer)           │
│  - Receipt analysis orchestration           │
│  - Image processing                         │
│  - Claude AI integration                    │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  database.py (Facade)                       │
│  - Unified interface to repositories        │
│  - Maintains backward compatibility         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  repositories/ (Data Access Layer)          │
│  - Specialized data operations              │
│  - SQL queries & database logic             │
│  - Connection management                    │
└─────────────────────────────────────────────┘
```

**Key Design Patterns:**
- **Repository Pattern**: Separates data access logic from business logic
- **Facade Pattern**: `database.py` provides a simple interface to complex repository layer
- **Dependency Injection**: Repositories receive database connection in constructor
- **Single Responsibility**: Each module has one clear purpose

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

### Running the Console UI

The console UI provides a local terminal interface for managing receipts:

```bash
# Run with specific user ID
./venv/bin/python console_ui/app.py <user_id>

# Or use first allowed user from config.ini
./venv/bin/python console_ui/app.py
```

**Key Bindings:**
- `Enter` - View receipt details (in list) / Edit item (in detail view)
- `Escape` - Go back / Quit
- `a` - Add new item
- `Delete` - Delete item/receipt (soft delete)
- `Ctrl+Delete` - Undelete item/receipt
- `m` - Edit merchant information
- `Shift+M` - Switch receipt to different merchant (search or create new)
- `t` - Edit receipt date and time
- `Shift+T` - Edit receipt total amount
- `s` - Cycle sort column / toggle direction
- `f` - Open filter dialog
- `h` - Toggle deleted receipts visibility
- `q` - Quit application

**Features:**
- Works over SSH (no GUI needed)
- Zebra-striped tables for readability
- Real-time total calculations
- Cursor preservation during operations
- All changes persist to PostgreSQL database

See [ADDING_UI.md](ADDING_UI.md) for detailed implementation notes.

## Database Schema

The database uses schema `app_receipts_bot` with the following entities:

1. **user** - Telegram users interacting with the bot
   - Primary key: `user_id` (Telegram user ID)
   - Tracks username, timestamps

2. **category** - Item categories for expense tracking (71 predefined categories)
   - Used to classify receipt items (groceries, utilities, car expenses, etc.)
   - Assigned to individual items, not whole receipts
   - **ai_notes** field: Optional custom instructions for Claude AI on category assignment
   - Example: Guide Claude to use "Child: Food" for Haribo Bears instead of "Food: Sweets"

3. **merchant** - Store/business information
   - Contains: name, city, country, address, logo_description
   - Normalized to avoid duplication

4. **image** - Uploaded receipt images
   - Stores both original and processed file paths
   - References: user
   - Contains Telegram `file_id` for re-downloading
   - Tracks file size, mime type

5. **transaction** - Financial transaction details
   - Contains: date, time, currency, amounts (net, vat, brutto)
   - Payment information: method, card number (last 4 digits)

6. **ai_analysis** - Claude AI processing results
   - Tracks: model_name, extraction_status, input/output tokens
   - Stores optimized JSON response (separate items and categories arrays) for debugging
   - Records Claude's actual response before validation/enrichment
   - Records error messages for failed analyses
   - **Token tracking**: Records input_tokens and output_tokens for cost monitoring

7. **receipt** - Receipt records
   - References: image, user, merchant, transaction, ai_analysis
   - Processing status tracking: created → pre-processed → processing → completed/failed/completed/inconsistent
   - Status 'created' is set when image is first received
   - Status 'pre-processed' is set when image is prepared for AI analysis
   - Status 'completed' is set after successful AI analysis with matching totals
   - Status 'completed/inconsistent' is set when receipt total doesn't match items sum
   - **user_notes** field: Optional user-provided notes from image caption
   - **Soft delete**: `is_deleted` boolean field (default: FALSE)

8. **receipt_item** - Individual line items from receipts
   - References: receipt, category (optional)
   - Contains: item name, article_number, quantity, unit price, total price
   - **Soft delete**: `is_deleted` boolean field (default: FALSE) for user edits
   - `updated_at` tracked for audit trail

All tables include `created_at` and `updated_at` timestamps (TIMESTAMPTZ).
Full schema definition in [schema.sql](schema.sql).

## Claude AI Integration Details

### Prompt Strategy
The bot uses Claude's vision capabilities to analyze receipt images. The prompt (stored in `prompt.txt`):
- Requests structured JSON output with optimized format for token efficiency
- Extracts: merchant info, transaction details, all items with prices
- **Category ID-based assignment**: Claude returns category IDs (integers) instead of names for maximum token efficiency
- **Index-based item assignment**: Uses 0-based indices to map items to categories
- **Optional fields**: Only includes quantity/unit_price when quantity > 1
- Categories injected as: `- [23] Food: Groceries` (ID in brackets, name after)
- **Category-specific notes**: Categories with `ai_notes` are injected with special instructions
- Prioritizes category notes over general categorization logic
- Handles tax IDs, QR codes, payment information
- Marks uncertain fields for user review
- Supports multiple languages (keeps item names in original language)

### Model Configuration
- **Configurable model**: Set via `config.ini` → `[anthropic]` → `model`
- **Default**: `claude-sonnet-4-5-20250929`
- **Token tracking**: All API calls log input/output tokens to database and console
- **Cost monitoring**: Token usage stored in `ai_analysis` table for analytics

### Error Handling
- **Refusal handling**: Detects when Claude refuses to process images (sensitive data, QR codes, tax IDs)
- **User feedback**: Provides specific guidance when analysis fails
- **Database tracking**: All failures recorded with error messages in `ai_analysis` table
- **Fallback**: Original images used if pre-processing fails

### Processing Flow
1. User uploads receipt image (optionally with caption as user notes)
2. Image metadata and user notes saved to database
3. Image pre-processed (cropped, grayscale, resized)
4. Categories with IDs, category notes, merchant notes, and user notes fetched from database
5. Prompt prepared with categories (formatted as `[ID] Name`) and all notes injected
6. Claude analyzes with vision API (model configurable)
   - User notes passed as additional context with "USER NOTE:" prefix
   - Returns optimized format: `{"items": [...], "categories": [{"id": 23, "items": [0,1]}]}`
7. Response parsed and AI analysis record saved to database (raw optimized format)
8. Items validated and enriched:
   - Category IDs validated against database (existence check)
   - Category indices validated (bounds, types, duplicates)
   - Items enriched with both category name and category_id fields
   - Quantity defaulted to 1 if missing, unit_price calculated
   - Uncategorized items assigned to default category
9. Data saved to database:
   - Merchant record (normalized)
   - Transaction record (financial details)
   - Receipt items (with enriched category_id assignments)
10. User receives summary with warnings for uncertain fields

## Next Steps

When ready to continue development:
1. ✅ ~~Set up Claude AI integration with vision API~~
2. ✅ ~~Process receipt images and extract data~~
3. ✅ ~~Update receipt records with extracted data~~
4. Implement Excel export functionality
5. Add user commands for viewing and exporting receipts
6. Add user feedback flow for uncertain/missing data
7. Implement analytics and reporting

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
