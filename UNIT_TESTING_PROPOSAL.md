# Unit Testing Proposal

## Overview

This document outlines the testing strategy for the receipts-bot-2 project. The approach follows the existing three-tier architecture and focuses on testing each layer independently.

## Testing Strategy

### 1. Layer-by-Layer Testing

Test each architectural layer independently:

- **Repositories**: Mock database connections, test SQL logic and data operations
- **Services**: Mock repositories, test business logic and orchestration
- **Handlers**: Mock services + Telegram context, test user interaction flows

### 2. Testing Framework and Tools

**Primary Framework: pytest**

Required dependencies:
- `pytest` - Core test framework
- `pytest-asyncio` - Async/await test support
- `pytest-mock` - Enhanced mocking utilities
- `pytest-cov` - Coverage reports
- `unittest.mock` - Built-in Python mocking

### 3. Test Structure

```
tests/
├── unit/
│   ├── repositories/
│   │   ├── test_receipt_repository.py
│   │   ├── test_merchant_repository.py
│   │   ├── test_category_repository.py
│   │   ├── test_user_repository.py
│   │   ├── test_image_repository.py
│   │   ├── test_transaction_repository.py
│   │   └── test_ai_analysis_repository.py
│   ├── services/
│   │   ├── test_claude_service.py
│   │   ├── test_image_processor.py
│   │   ├── test_receipt_analyzer.py
│   │   └── test_receipt_formatter.py
│   └── handlers/
│       ├── test_commands.py
│       ├── test_callbacks.py
│       └── test_messages.py
├── integration/
│   ├── test_receipt_flow.py
│   └── test_database_integration.py
├── fixtures/
│   ├── sample_receipts/
│   │   ├── receipt_01.jpg
│   │   └── receipt_01_response.json
│   └── test_images/
└── conftest.py  # Shared fixtures
```

### 4. Priority Testing Areas

#### High Priority (Critical Business Logic)
1. **Receipt analysis orchestration** (`services/receipt_analyzer.py`)
   - Total consistency validation (tolerance: 0.01)
   - Status transitions (created → pre-processed → processing → completed)
   - Error handling and recovery

2. **Category assignment and parsing** (`services/claude_service.py`)
   - JSON response parsing (with/without markdown code blocks)
   - Category notes injection into prompts
   - Token tracking accuracy

3. **Financial calculations** (`repositories/receipt_repository.py`)
   - Item sum calculations
   - Category breakdown totals
   - Discrepancy detection

4. **Merchant deduplication** (`repositories/merchant_repository.py`)
   - Case-insensitive name matching
   - Fuzzy address matching (30% threshold)
   - SQL similarity logic

5. **Repository CRUD operations** (all repositories)
   - Data integrity (foreign keys, constraints)
   - Soft delete behavior
   - Authorization checks (user ownership)

#### Medium Priority (Supporting Features)
6. **Image processing** (`services/image_processor.py`)
   - Multi-strategy cropping logic
   - Fallback to original on failure
   - PDF vs photo detection

7. **Authorization checks** (`bot.py`, handlers)
   - `@authorized_only` decorator
   - User ownership verification

8. **Receipt formatting** (`services/receipt_formatter.py`)
   - Summary generation
   - Category grouping display

#### Low Priority (Best Tested via Integration)
9. Telegram handler routing
10. Database schema migrations

### 5. Testing Patterns and Examples

#### Example: Repository Test with Mocked Database

```python
# tests/unit/repositories/test_receipt_repository.py
import pytest
from unittest.mock import Mock, MagicMock
from repositories.receipt_repository import ReceiptRepository

@pytest.fixture
def mock_db_connection():
    """Mock database connection with cursor context manager"""
    conn = Mock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = None
    return conn

def test_get_receipt_by_id_success(mock_db_connection):
    # Arrange
    repo = ReceiptRepository(mock_db_connection)
    cursor = mock_db_connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (1, 123, 'completed', 15.99)

    # Act
    result = repo.get_receipt_by_id(1, 123)

    # Assert
    assert result is not None
    assert result['receipt_id'] == 1
    cursor.execute.assert_called_once()

def test_get_receipt_by_id_not_found(mock_db_connection):
    # Arrange
    repo = ReceiptRepository(mock_db_connection)
    cursor = mock_db_connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None

    # Act
    result = repo.get_receipt_by_id(999, 123)

    # Assert
    assert result is None

def test_get_receipt_by_id_wrong_user(mock_db_connection):
    # Test authorization: user can't access other user's receipt
    repo = ReceiptRepository(mock_db_connection)
    cursor = mock_db_connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None  # SQL query filters by user_id

    result = repo.get_receipt_by_id(1, 999)
    assert result is None
```

#### Example: Service Test with Mocked Repository

```python
# tests/unit/services/test_receipt_analyzer.py
import pytest
from unittest.mock import Mock, patch
from services.receipt_analyzer import analyze_receipt

@pytest.mark.asyncio
async def test_analyze_receipt_success(mock_claude_response):
    # Arrange
    receipt_id = 1
    user_id = 123
    mock_db = Mock()

    with patch('services.receipt_analyzer.claude_service') as mock_claude:
        mock_claude.analyze_image.return_value = mock_claude_response

        # Act
        result = await analyze_receipt(receipt_id, user_id, mock_db)

        # Assert
        assert result['status'] == 'completed'
        assert result['total'] == 15.99

@pytest.mark.asyncio
async def test_analyze_receipt_inconsistent_total():
    # Arrange
    receipt_id = 1
    user_id = 123
    mock_db = Mock()

    # Mock Claude response where items don't sum to total
    mock_response = {
        'transaction': {'brutto': 20.00},
        'items': [{'total': 10.50}, {'total': 5.00}]  # Sum: 15.50
    }

    with patch('services.receipt_analyzer.claude_service') as mock_claude:
        mock_claude.analyze_image.return_value = mock_response

        # Act
        result = await analyze_receipt(receipt_id, user_id, mock_db)

        # Assert
        assert result['status'] == 'completed/inconsistent'
        assert abs(result['discrepancy'] - 4.50) < 0.01
```

#### Example: Handler Test with Mocked Telegram Context

```python
# tests/unit/handlers/test_commands.py
import pytest
from unittest.mock import AsyncMock, Mock
from handlers.commands import start_command

@pytest.mark.asyncio
async def test_start_command_new_user():
    # Arrange
    update = Mock()
    update.effective_user.id = 123
    update.effective_user.username = "testuser"
    update.message.reply_text = AsyncMock()

    context = Mock()
    context.user_data = {}

    # Act
    await start_command(update, context)

    # Assert
    update.message.reply_text.assert_called_once()
    assert "Welcome" in update.message.reply_text.call_args[0][0]
```

### 6. Mocking Strategies

#### Database Connection Mock
```python
# tests/conftest.py
import pytest
from unittest.mock import Mock, MagicMock

@pytest.fixture
def mock_db_connection():
    """Mock database connection with cursor context manager"""
    conn = Mock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = None
    return conn
```

#### Claude AI Response Mock
```python
@pytest.fixture
def mock_claude_response():
    """Mock successful Claude AI analysis response"""
    return {
        'merchant': {
            'name': 'REWE',
            'city': 'Berlin',
            'address': 'Hauptstraße 123'
        },
        'transaction': {
            'date': '2025-01-15',
            'time': '14:30:00',
            'currency': 'EUR',
            'brutto': 15.99
        },
        'items': [
            {
                'name': 'Milk',
                'quantity': 1.0,
                'unit_price': 1.29,
                'total': 1.29,
                'category': 'Food: Dairy'
            },
            {
                'name': 'Bread',
                'quantity': 2.0,
                'unit_price': 2.50,
                'total': 5.00,
                'category': 'Food: Bakery'
            }
        ],
        'tokens': {'input': 1500, 'output': 800}
    }
```

### 7. What NOT to Test

- **External APIs directly**: Mock Claude API and Telegram API calls
- **Database SQL syntax**: Trust psycopg2 library implementation
- **Third-party library internals**: Don't test Pillow, OpenCV, Textual internals
- **Configuration loading**: Config parsing is trivial, focus on business logic
- **Logging statements**: Don't assert on log output unless critical for debugging

### 8. Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock pytest-cov

# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html --cov-report=term

# Run specific test file
pytest tests/unit/services/test_receipt_analyzer.py

# Run tests matching pattern
pytest -k "test_receipt"

# Run with verbose output
pytest -v

# Run and stop on first failure
pytest -x
```

### 9. Coverage Goals

- **Target: 80% overall coverage**
- **Critical paths: 95%+ coverage**
  - Receipt analysis flow
  - Financial calculations
  - Authorization checks
  - Merchant deduplication

### 10. Continuous Integration

Recommend setting up GitHub Actions or similar CI:

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.13
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-asyncio pytest-mock pytest-cov
      - run: pytest --cov=. --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## Components to Test

### Repositories Layer (7 modules)

1. **receipt_repository.py**
   - ✅ `create_receipt()` - Creates receipt with user/image association
   - ✅ `get_receipt_by_id()` - Retrieves with authorization check
   - ✅ `update_receipt_status()` - Status transitions
   - ✅ `get_receipt_with_items()` - Joins items with categories
   - ✅ `calculate_items_total()` - Financial calculation accuracy
   - ✅ `get_category_breakdown()` - Category grouping and totals
   - ✅ `soft_delete_receipt()` - Soft delete with authorization
   - ✅ `get_recent_receipts()` - Listing with filters

2. **merchant_repository.py**
   - ✅ `find_existing_merchant()` - Fuzzy matching logic (30% threshold)
   - ✅ `create_merchant()` - Normalization (case-insensitive)
   - ✅ `get_merchant_by_id()` - Retrieval
   - ✅ `update_merchant()` - Updates affect all receipts

3. **category_repository.py**
   - ✅ `get_all_categories()` - Returns all 71 categories
   - ✅ `get_categories_with_notes()` - Filters categories with AI notes
   - ✅ `find_category_by_name()` - Exact match
   - ✅ `search_categories_fuzzy()` - 30% similarity threshold
   - ✅ `create_category()` - Title-cased naming

4. **user_repository.py**
   - ✅ `upsert_user()` - Insert/update logic
   - ✅ `get_user_by_id()` - Retrieval
   - ✅ `update_username()` - Username changes

5. **image_repository.py**
   - ✅ `create_image()` - File metadata storage
   - ✅ `get_image_by_id()` - Retrieval with authorization
   - ✅ `update_processed_image()` - Processed path update

6. **transaction_repository.py**
   - ✅ `create_transaction()` - Financial data storage
   - ✅ `get_transaction_by_id()` - Retrieval

7. **ai_analysis_repository.py**
   - ✅ `create_ai_analysis()` - Token tracking accuracy
   - ✅ `update_ai_analysis_status()` - Status updates
   - ✅ `get_ai_analysis_by_id()` - Retrieval

### Services Layer (4 modules)

8. **receipt_analyzer.py**
   - ✅ `analyze_receipt()` - End-to-end orchestration
   - ✅ Total consistency check (0.01 tolerance)
   - ✅ Status transitions (pre-processed → processing → completed)
   - ✅ Error handling (Claude refusal, parsing errors)
   - ✅ Database transaction integrity

9. **claude_service.py**
   - ✅ `analyze_receipt_image()` - API call with token tracking
   - ✅ `_prepare_prompt()` - Category injection with notes
   - ✅ `_parse_response()` - JSON parsing (with/without markdown blocks)
   - ✅ Error handling (refusals, malformed JSON)
   - ✅ Token extraction from response

10. **image_processor.py**
    - ✅ `preprocess_image()` - Multi-strategy cropping
    - ✅ PDF detection (skip cropping)
    - ✅ Crop validation (20-90% of original area)
    - ✅ Fallback to original on failure
    - ✅ File size calculations

11. **receipt_formatter.py**
    - ✅ `format_receipt_summary()` - Summary generation
    - ✅ Category breakdown display
    - ✅ Inconsistency warnings
    - ✅ Formatting consistency

### Handlers Layer (3 modules)

12. **commands.py**
    - ✅ `start_command()` - User upsert
    - ✅ `receipts_command()` - Listing with argument parsing
    - ✅ Authorization enforcement

13. **callbacks.py**
    - ✅ `handle_delete_receipt()` - Soft delete with authorization
    - ✅ `handle_view_image()` - Image retrieval with authorization
    - ✅ `handle_edit_receipt()` - Edit flow initialization
    - ✅ `handle_delete_item()` - Item soft delete
    - ✅ Callback data parsing

14. **messages.py**
    - ✅ `handle_amount_input()` - Amount validation (0.01-99999.99)
    - ✅ `handle_category_search()` - Fuzzy search + create flow
    - ✅ Conversation state management (`context.user_data`)

### Core Modules

15. **bot.py**
    - ✅ `authorized_only` decorator - Whitelist enforcement
    - ⚠️ Handler registration (low priority - integration test)

16. **config.py**
    - ⚠️ Configuration loading (low priority - trivial)

17. **database.py**
    - ⚠️ Facade methods (covered by repository tests)

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

**Goal**: Set up testing infrastructure and shared fixtures

#### Tasks:
1. ✅ Install test dependencies
   ```bash
   pip install pytest pytest-asyncio pytest-mock pytest-cov
   ```

2. ✅ Create test directory structure
   ```
   tests/
   ├── unit/
   │   ├── repositories/
   │   ├── services/
   │   └── handlers/
   ├── integration/
   ├── fixtures/
   └── conftest.py
   ```

3. ✅ Write `conftest.py` with shared fixtures:
   - `mock_db_connection` - Database connection mock
   - `mock_cursor` - Database cursor mock
   - `mock_claude_response` - Sample AI response
   - `mock_update` - Telegram update object
   - `mock_context` - Telegram context object

4. ✅ Create `pytest.ini` configuration:
   ```ini
   [pytest]
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*
   asyncio_mode = auto
   ```

5. ✅ Add sample test data fixtures:
   - `fixtures/sample_receipts/receipt_01_response.json`
   - `fixtures/test_images/test_receipt.jpg`

**Deliverable**: Working test infrastructure with basic fixtures

---

### Phase 2: Repository Layer Tests (Week 2)

**Goal**: Test all data access operations with 90%+ coverage

#### Priority Order:
1. **receipt_repository.py** (most critical - 300+ lines)
   - Test CRUD operations
   - Test authorization checks
   - Test financial calculations
   - Test soft delete behavior

2. **merchant_repository.py** (critical - fuzzy matching)
   - Test fuzzy matching with various similarity scores
   - Test case-insensitive name matching
   - Test address normalization

3. **category_repository.py** (important for AI)
   - Test fuzzy search
   - Test category creation
   - Test notes filtering

4. **Other repositories** (straightforward CRUD)
   - user_repository.py
   - image_repository.py
   - transaction_repository.py
   - ai_analysis_repository.py

**Deliverable**: 90%+ coverage for repositories layer

---

### Phase 3: Services Layer Tests (Week 3)

**Goal**: Test business logic with mocked repositories

#### Priority Order:
1. **receipt_analyzer.py** (most critical)
   - Test successful analysis flow
   - Test total consistency validation (matching vs mismatched)
   - Test error handling (Claude refusal, parsing errors)
   - Test status transitions
   - Test database rollback on failure

2. **claude_service.py** (critical AI integration)
   - Test prompt preparation (category injection)
   - Test response parsing (with/without markdown)
   - Test token extraction
   - Test error handling (API errors, refusals)

3. **image_processor.py** (important preprocessing)
   - Test multi-strategy cropping
   - Test PDF detection
   - Test fallback logic
   - Test crop validation

4. **receipt_formatter.py** (UI formatting)
   - Test summary generation
   - Test category breakdown
   - Test inconsistency warnings

**Deliverable**: 85%+ coverage for services layer

---

### Phase 4: Handlers Layer Tests (Week 4)

**Goal**: Test user interaction flows

#### Priority Order:
1. **callbacks.py** (complex flows)
   - Test delete receipt callback
   - Test view image callback
   - Test edit receipt navigation
   - Test authorization enforcement

2. **messages.py** (conversation flows)
   - Test amount input validation
   - Test category search flow
   - Test conversation state management

3. **commands.py** (command handlers)
   - Test start command
   - Test receipts command with arguments
   - Test authorization decorator

**Deliverable**: 80%+ coverage for handlers layer

---

### Phase 5: Integration Tests (Week 5)

**Goal**: Test end-to-end flows with real database (test environment)

#### Tests:
1. **Receipt processing flow**
   - Upload image → preprocess → analyze → save → format

2. **Receipt editing flow**
   - View → edit item → change category → update total

3. **Database integration**
   - Test real SQL queries with test database
   - Test transaction rollbacks
   - Test foreign key constraints

**Deliverable**: Critical paths tested end-to-end

---

### Phase 6: Coverage and CI (Week 6)

**Goal**: Achieve 80% overall coverage and automate testing

#### Tasks:
1. ✅ Generate coverage report
   ```bash
   pytest --cov=. --cov-report=html --cov-report=term-missing
   ```

2. ✅ Identify untested code paths
   - Review HTML coverage report
   - Add tests for gaps in critical paths

3. ✅ Set up GitHub Actions CI (optional)
   - Run tests on every push
   - Report coverage to Codecov

4. ✅ Document testing guidelines
   - Add testing section to README
   - Create CONTRIBUTING.md with test requirements

**Deliverable**: 80%+ overall coverage, automated CI

---

## Success Metrics

- ✅ **80% overall code coverage**
- ✅ **95%+ coverage for critical paths**:
  - Receipt analysis orchestration
  - Financial calculations
  - Merchant deduplication
  - Authorization checks
- ✅ **All tests pass in CI**
- ✅ **Test execution time < 30 seconds**
- ✅ **Zero flaky tests** (tests pass consistently)

---

## Maintenance Plan

1. **Test-Driven Development**: Write tests before implementing new features
2. **Coverage monitoring**: Block PRs with <80% coverage
3. **Regular review**: Review and update tests when refactoring
4. **Documentation**: Keep this document updated with new test patterns

---

## References

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
