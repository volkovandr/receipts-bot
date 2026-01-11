"""
Database module - Unified interface to all repositories.

This module provides a single Database class that encapsulates all repository operations.
It maintains backward compatibility with the original Database class interface.
"""

from repositories.database_connection import DatabaseConnection
from repositories.user_repository import UserRepository
from repositories.image_repository import ImageRepository
from repositories.category_repository import CategoryRepository
from repositories.merchant_repository import MerchantRepository
from repositories.transaction_repository import TransactionRepository
from repositories.ai_analysis_repository import AIAnalysisRepository
from repositories.receipt_repository import ReceiptRepository


class Database:
    """
    Unified database interface that delegates to specialized repositories.
    Maintains backward compatibility with the original Database class.
    """

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        """Initialize database connection and all repositories."""
        # Create connection manager
        self.db_connection = DatabaseConnection(host, port, database, user, password)

        # Initialize all repositories (will be created after connection is established)
        self.user_repo = None
        self.category_repo = None
        self.image_repo = None
        self.merchant_repo = None
        self.transaction_repo = None
        self.ai_analysis_repo = None
        self.receipt_repo = None

    def connect(self) -> None:
        """Establish database connection and initialize repositories."""
        self.db_connection.connect()

        # Get connection for all repositories
        conn = self.db_connection.connection

        # Initialize repositories in order (some depend on others)
        self.user_repo = UserRepository(conn)
        self.category_repo = CategoryRepository(conn)
        self.image_repo = ImageRepository(conn, self.user_repo)
        self.merchant_repo = MerchantRepository(conn)
        self.transaction_repo = TransactionRepository(conn)
        self.ai_analysis_repo = AIAnalysisRepository(conn)
        self.receipt_repo = ReceiptRepository(conn, self.category_repo)

    def close(self) -> None:
        """Close database connection."""
        self.db_connection.close()

    def initialize_schema(self, schema_file: str = "schema.sql") -> None:
        """Initialize database schema from SQL file."""
        self.db_connection.initialize_schema(schema_file)

    # User operations
    def upsert_user(self, user_id: int, username: str = None) -> None:
        """Insert or update user."""
        return self.user_repo.upsert_user(user_id, username)

    # Image operations
    def insert_image(self, user_id: int, telegram_file_id: str, file_path: str,
                     file_size: int, mime_type: str) -> int:
        """Insert image record."""
        return self.image_repo.insert_image(user_id, telegram_file_id, file_path, file_size, mime_type)

    def update_image_processed(self, image_id: int, processed_file_path: str, processed_file_size: int) -> None:
        """Update image with processed file information."""
        return self.image_repo.update_image_processed(image_id, processed_file_path, processed_file_size)

    # Category operations
    def get_all_categories(self) -> list:
        """Get all category names."""
        return self.category_repo.get_all_categories()

    def get_all_categories_with_ids(self) -> list[tuple[int, str]]:
        """Get all categories with their IDs."""
        return self.category_repo.get_all_categories_with_ids()

    def get_category_id_by_name(self, category_name: str) -> int | None:
        """Get category ID by name."""
        return self.category_repo.get_category_id_by_name(category_name)

    def get_categories_with_notes(self) -> list[tuple[int, str, str]]:
        """Get categories that have AI notes defined."""
        return self.category_repo.get_categories_with_notes()

    def search_categories_fuzzy(self, search_term: str, similarity_threshold: float = 0.3) -> list[tuple[int, str]]:
        """Search categories using fuzzy matching."""
        return self.category_repo.search_categories_fuzzy(search_term, similarity_threshold)

    def create_category(self, category_name: str, description: str = None) -> int:
        """Create a new category."""
        return self.category_repo.create_category(category_name, description)

    # Merchant operations
    def insert_or_get_merchant(self, name: str, city: str = None, country: str = None,
                                address: str = None, logo_description: str = None) -> int:
        """Insert merchant or get existing one."""
        return self.merchant_repo.insert_or_get_merchant(name, city, country, address, logo_description)

    def get_merchant_by_id(self, merchant_id: int) -> dict | None:
        """Get merchant details by ID."""
        return self.merchant_repo.get_merchant_by_id(merchant_id)

    def update_merchant(self, merchant_id: int, name: str = None, city: str = None,
                       country: str = None, address: str = None, logo_description: str = None) -> bool:
        """Update merchant information."""
        return self.merchant_repo.update_merchant(merchant_id, name, city, country, address, logo_description)

    def get_receipt_count_by_merchant(self, merchant_id: int) -> int:
        """Get count of receipts for a merchant."""
        return self.merchant_repo.get_receipt_count_by_merchant(merchant_id)

    def get_all_merchants(self) -> list[dict]:
        """Get all merchants."""
        return self.merchant_repo.get_all_merchants()

    def find_merchant_by_name(self, name: str) -> dict | None:
        """Find merchant by name (case-insensitive)."""
        return self.merchant_repo.find_merchant_by_name(name)

    def create_merchant(self, name: str, city: str = None, country: str = None,
                       address: str = None, logo_description: str = None) -> int | None:
        """Create a new merchant."""
        return self.merchant_repo.create_merchant(name, city, country, address, logo_description)

    def get_merchants_with_notes(self) -> list[tuple[str, str, str, str]]:
        """Get merchants that have AI notes defined."""
        return self.merchant_repo.get_merchants_with_notes()

    # Transaction operations
    def insert_transaction(self, date: str = None, time: str = None, currency: str = 'EUR',
                          net_amount: float = None, vat_amount: float = None,
                          brutto_amount: float = None, payment_method: str = None,
                          card_number: str = None) -> int:
        """Insert transaction record."""
        return self.transaction_repo.insert_transaction(
            date, time, currency, net_amount, vat_amount, brutto_amount, payment_method, card_number
        )

    def update_transaction_datetime(self, transaction_id: int, date, time) -> bool:
        """Update transaction date and time."""
        return self.transaction_repo.update_transaction_datetime(transaction_id, date, time)

    def update_transaction_total(self, transaction_id: int, brutto_amount: float) -> bool:
        """Update transaction brutto (total) amount."""
        return self.transaction_repo.update_transaction_total(transaction_id, brutto_amount)

    # AI Analysis operations
    def insert_ai_analysis(self, model_name: str, extraction_status: str,
                          input_tokens: int, output_tokens: int,
                          raw_data: str = None, error_message: str = None) -> int:
        """Insert AI analysis record. Raw data should be string (JSON or TOON format)."""
        return self.ai_analysis_repo.insert_ai_analysis(
            model_name, extraction_status, input_tokens, output_tokens, raw_data, error_message
        )

    def update_ai_analysis_error(self, analysis_id: int, error_message: str) -> None:
        """Update AI analysis record with error message."""
        return self.ai_analysis_repo.update_ai_analysis_error(analysis_id, error_message)

    # Receipt operations
    def insert_receipt(self, image_id: int, user_id: int, status: str = 'created', user_notes: str = None) -> int:
        """Insert receipt record."""
        return self.receipt_repo.insert_receipt(image_id, user_id, status, user_notes)

    def update_receipt_status(self, receipt_id: int, status: str) -> None:
        """Update receipt processing status."""
        return self.receipt_repo.update_receipt_status(receipt_id, status)

    def update_receipt_with_analysis(self, receipt_id: int, merchant_id: int,
                                     transaction_id: int, ai_analysis_id: int) -> None:
        """Update receipt with analysis results."""
        return self.receipt_repo.update_receipt_with_analysis(
            receipt_id, merchant_id, transaction_id, ai_analysis_id
        )

    def insert_receipt_items(self, receipt_id: int, items: list) -> None:
        """Insert receipt items in batch."""
        return self.receipt_repo.insert_receipt_items(receipt_id, items)

    def get_receipt_items_sum(self, receipt_id: int) -> float:
        """Calculate sum of all item prices for a receipt."""
        return self.receipt_repo.get_receipt_items_sum(receipt_id)

    def get_receipt_items_by_category(self, receipt_id: int) -> list:
        """Get receipt items grouped by category with totals."""
        return self.receipt_repo.get_receipt_items_by_category(receipt_id)

    def mark_receipt_as_deleted(self, receipt_id: int, user_id: int = None) -> bool:
        """Mark receipt as deleted (soft delete)."""
        return self.receipt_repo.mark_receipt_as_deleted(receipt_id, user_id)

    def undelete_receipt(self, receipt_id: int, user_id: int = None) -> bool:
        """Restore a soft-deleted receipt."""
        return self.receipt_repo.undelete_receipt(receipt_id, user_id)

    def verify_receipt_owner(self, receipt_id: int, user_id: int) -> bool:
        """Verify that a receipt belongs to a user."""
        return self.receipt_repo.verify_receipt_owner(receipt_id, user_id)

    def get_receipt_processed_image_path(self, receipt_id: int, user_id: int = None) -> str | None:
        """Get processed image path for a receipt."""
        return self.receipt_repo.get_receipt_processed_image_path(receipt_id, user_id)

    def get_receipt_items_detailed(self, receipt_id: int, user_id: int = None) -> list[dict]:
        """Get detailed list of receipt items."""
        return self.receipt_repo.get_receipt_items_detailed(receipt_id, user_id)

    def mark_item_as_deleted(self, item_id: int, receipt_id: int, user_id: int = None) -> bool:
        """Mark receipt item as deleted (soft delete)."""
        return self.receipt_repo.mark_item_as_deleted(item_id, receipt_id, user_id)

    def undelete_item(self, item_id: int, receipt_id: int, user_id: int = None) -> bool:
        """Restore a deleted receipt item (undelete)."""
        return self.receipt_repo.undelete_item(item_id, receipt_id, user_id)

    def update_item_name(self, item_id: int, receipt_id: int, new_name: str, user_id: int = None) -> bool:
        """Update receipt item name."""
        return self.receipt_repo.update_item_name(item_id, receipt_id, new_name, user_id)

    def update_item_amount(self, item_id: int, receipt_id: int, new_amount: float, user_id: int = None) -> bool:
        """Update receipt item total price."""
        return self.receipt_repo.update_item_amount(item_id, receipt_id, new_amount, user_id)

    def update_item_category(self, item_id: int, receipt_id: int, category_id: int | None, user_id: int = None) -> bool:
        """Update receipt item category (category_id can be None for uncategorized)."""
        return self.receipt_repo.update_item_category(item_id, receipt_id, category_id, user_id)

    def create_item(self, receipt_id: int, user_id: int, item_name: str,
                    quantity: float, unit_price: float, total_price: float,
                    category_id: int = None, article_number: str = None) -> int:
        """Create a new receipt item."""
        return self.receipt_repo.create_item(receipt_id, user_id, item_name, quantity, unit_price, total_price, category_id, article_number)

    def get_recent_receipts(self, user_id: int, limit: int = 3) -> list[int]:
        """Get recent receipt IDs for a user."""
        return self.receipt_repo.get_recent_receipts(user_id, limit)

    def get_all_receipts_for_list(self, user_id: int, include_deleted: bool = False) -> list[dict]:
        """Get all receipts for display in list view (console UI)."""
        return self.receipt_repo.get_all_receipts_for_list(user_id, include_deleted)

    def get_receipt_summary_data(self, receipt_id: int, user_id: int = None) -> dict | None:
        """Get receipt summary data for formatting."""
        return self.receipt_repo.get_receipt_summary_data(receipt_id, user_id)

    def get_receipt_items_for_console(self, receipt_id: int, user_id: int = None) -> list[dict]:
        """Get all receipt items for console UI (includes deleted items)."""
        return self.receipt_repo.get_receipt_items_for_console(receipt_id, user_id)

    def update_receipt_merchant(self, receipt_id: int, merchant_id: int, user_id: int = None) -> bool:
        """Update receipt's merchant."""
        return self.receipt_repo.update_receipt_merchant(receipt_id, merchant_id, user_id)

    def update_receipt_transaction_datetime(self, receipt_id: int, date, time, user_id: int = None) -> bool:
        """
        Update receipt's transaction date and time.

        Args:
            receipt_id: Receipt ID
            date: New date
            time: New time
            user_id: User ID (for authorization)

        Returns:
            True if successful, False otherwise
        """
        # Get transaction_id with authorization check
        transaction_id = self.receipt_repo.get_receipt_transaction_id(receipt_id, user_id)

        if transaction_id is None:
            return False

        # Update transaction datetime
        return self.transaction_repo.update_transaction_datetime(transaction_id, date, time)

    def update_receipt_transaction_total(self, receipt_id: int, brutto_amount: float, user_id: int = None) -> bool:
        """
        Update receipt's transaction total amount.

        Args:
            receipt_id: Receipt ID
            brutto_amount: New brutto/total amount
            user_id: User ID (for authorization)

        Returns:
            True if successful, False otherwise
        """
        # Get transaction_id with authorization check
        transaction_id = self.receipt_repo.get_receipt_transaction_id(receipt_id, user_id)

        if transaction_id is None:
            return False

        # Update transaction total
        return self.transaction_repo.update_transaction_total(transaction_id, brutto_amount)

    def get_user_notes_by_receipt_id(self, receipt_id: int) -> str | None:
        """Get user notes for a receipt."""
        return self.receipt_repo.get_user_notes_by_receipt_id(receipt_id)
