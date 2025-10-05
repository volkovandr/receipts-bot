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

    def get_category_id_by_name(self, category_name: str) -> int | None:
        """Get category ID by name."""
        return self.category_repo.get_category_id_by_name(category_name)

    def get_categories_with_notes(self) -> list[tuple[str, str]]:
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

    # Transaction operations
    def insert_transaction(self, date: str = None, time: str = None, currency: str = 'EUR',
                          net_amount: float = None, vat_amount: float = None,
                          brutto_amount: float = None, payment_method: str = None,
                          card_number: str = None) -> int:
        """Insert transaction record."""
        return self.transaction_repo.insert_transaction(
            date, time, currency, net_amount, vat_amount, brutto_amount, payment_method, card_number
        )

    # AI Analysis operations
    def insert_ai_analysis(self, model_name: str, extraction_status: str,
                          input_tokens: int, output_tokens: int,
                          raw_data: dict = None, error_message: str = None) -> int:
        """Insert AI analysis record."""
        return self.ai_analysis_repo.insert_ai_analysis(
            model_name, extraction_status, input_tokens, output_tokens, raw_data, error_message
        )

    # Receipt operations
    def insert_receipt(self, image_id: int, user_id: int, status: str = 'created') -> int:
        """Insert receipt record."""
        return self.receipt_repo.insert_receipt(image_id, user_id, status)

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

    def update_item_amount(self, item_id: int, receipt_id: int, new_amount: float, user_id: int = None) -> bool:
        """Update receipt item total price."""
        return self.receipt_repo.update_item_amount(item_id, receipt_id, new_amount, user_id)

    def update_item_category(self, item_id: int, receipt_id: int, category_id: int, user_id: int = None) -> bool:
        """Update receipt item category."""
        return self.receipt_repo.update_item_category(item_id, receipt_id, category_id, user_id)

    def get_recent_receipts(self, user_id: int, limit: int = 3) -> list[int]:
        """Get recent receipt IDs for a user."""
        return self.receipt_repo.get_recent_receipts(user_id, limit)

    def get_receipt_summary_data(self, receipt_id: int, user_id: int = None) -> dict | None:
        """Get receipt summary data for formatting."""
        return self.receipt_repo.get_receipt_summary_data(receipt_id, user_id)
