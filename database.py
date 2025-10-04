"""
Database module for receipts bot.
Handles all database interactions and initialization.
"""

import psycopg2
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """Database connection and operations handler."""

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        """Initialize database connection parameters."""
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None

    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            # Set default schema
            with self.connection.cursor() as cursor:
                cursor.execute("SET search_path TO app_receipts_bot, public")
            self.connection.commit()
            logger.info("Database connection established")
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

    def initialize_schema(self, schema_file: str = "schema.sql") -> None:
        """
        Initialize database schema from SQL file.
        Checks if tables exist and creates them if needed.
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        # Check if test table exists
        if self._table_exists("version"):
            logger.info("Database schema already initialized")
            return

        # Read and execute schema file
        schema_path = Path(schema_file)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(schema_sql)
            self.connection.commit()
            logger.info("Database schema initialized successfully")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to initialize schema: {e}")
            raise

    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'app_receipts_bot'
                        AND table_name = %s
                    );
                    """,
                    (table_name,)
                )
                return cursor.fetchone()[0]
        except psycopg2.Error as e:
            logger.error(f"Error checking table existence: {e}")
            return False

    def insert_image(self, user_id: int, telegram_file_id: str, file_path: str,
                     file_size: int, mime_type: str) -> int:
        """
        Insert image record into database.

        Args:
            user_id: Telegram user ID
            telegram_file_id: Telegram's file_id for the image
            file_path: Local file system path where image is stored
            file_size: Size of the file in bytes
            mime_type: MIME type of the image

        Returns:
            image_id: The ID of the inserted image record
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            # First, ensure user exists
            self._ensure_user_exists(user_id)

            # Insert image record
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO image (user_id, file_id, orig_file_path, orig_file_size, mime_type)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING image_id;
                    """,
                    (user_id, telegram_file_id, file_path, file_size, mime_type)
                )
                image_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Image record inserted with ID: {image_id}")
                return image_id
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to insert image: {e}")
            raise

    def insert_receipt(self, image_id: int, user_id: int, status: str = 'created') -> int:
        """
        Insert receipt record into database.

        Args:
            image_id: ID of the associated image
            user_id: Telegram user ID
            status: Processing status (default: 'created')

        Returns:
            receipt_id: The ID of the inserted receipt record
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO receipt (image_id, user_id, processing_status)
                    VALUES (%s, %s, %s)
                    RETURNING receipt_id;
                    """,
                    (image_id, user_id, status)
                )
                receipt_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Receipt record inserted with ID: {receipt_id}")
                return receipt_id
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to insert receipt: {e}")
            raise

    def _ensure_user_exists(self, user_id: int) -> None:
        """
        Ensure user exists in database. Insert if not present.

        Args:
            user_id: Telegram user ID
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO "user" (user_id)
                    VALUES (%s)
                    ON CONFLICT (user_id) DO NOTHING;
                    """,
                    (user_id,)
                )
                self.connection.commit()
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to ensure user exists: {e}")
            raise

    def upsert_user(self, user_id: int, username: str = None) -> None:
        """
        Insert or update user in database.
        Updates username if it has changed.

        Args:
            user_id: Telegram user ID
            username: Telegram username (optional)
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO "user" (user_id, username)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE "user".username IS DISTINCT FROM EXCLUDED.username;
                    """,
                    (user_id, username)
                )
                self.connection.commit()
                logger.info(f"User {user_id} upserted with username: {username}")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to upsert user: {e}")
            raise

    def update_image_processed(self, image_id: int, processed_file_path: str, processed_file_size: int) -> None:
        """
        Update image record with processed file information.

        Args:
            image_id: ID of the image record
            processed_file_path: Path to processed image file
            processed_file_size: Size of processed file in bytes
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE image
                    SET processed_file_path = %s,
                        processed_file_size = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE image_id = %s;
                    """,
                    (processed_file_path, processed_file_size, image_id)
                )
                self.connection.commit()
                logger.info(f"Image {image_id} updated with processed file: {processed_file_path}")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update image: {e}")
            raise

    def update_receipt_status(self, receipt_id: int, status: str) -> None:
        """
        Update receipt processing status.

        Args:
            receipt_id: ID of the receipt record
            status: New processing status (e.g., 'pre-processed', 'processing', 'completed', 'failed')
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE receipt
                    SET processing_status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE receipt_id = %s;
                    """,
                    (status, receipt_id)
                )
                self.connection.commit()
                logger.info(f"Receipt {receipt_id} status updated to: {status}")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update receipt status: {e}")
            raise

    def get_all_categories(self) -> list:
        """
        Get all category names from database.

        Returns:
            List of category names (strings)
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT category_name FROM category ORDER BY category_name;")
                categories = [row[0] for row in cursor.fetchall()]
                logger.debug(f"Retrieved {len(categories)} categories from database")
                return categories
        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve categories: {e}")
            raise

    def get_category_id_by_name(self, category_name: str) -> int | None:
        """
        Get category ID by name.

        Args:
            category_name: Name of the category

        Returns:
            category_id or None if not found
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT category_id FROM category WHERE category_name = %s;",
                    (category_name,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except psycopg2.Error as e:
            logger.error(f"Failed to get category ID: {e}")
            raise

    def insert_or_get_merchant(self, name: str, city: str = None, country: str = None,
                                address: str = None, logo_description: str = None) -> int:
        """
        Insert merchant or get existing one by name.

        Args:
            name: Merchant name
            city: City (optional)
            country: Country (optional)
            address: Full address (optional)
            logo_description: Logo description if name unclear (optional)

        Returns:
            merchant_id
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Try to find existing merchant by name
                cursor.execute(
                    "SELECT merchant_id FROM merchant WHERE name = %s;",
                    (name,)
                )
                result = cursor.fetchone()

                if result:
                    merchant_id = result[0]
                    logger.debug(f"Merchant '{name}' already exists with ID: {merchant_id}")
                    return merchant_id

                # Insert new merchant
                cursor.execute(
                    """
                    INSERT INTO merchant (name, city, country, address, logo_description)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING merchant_id;
                    """,
                    (name, city, country, address, logo_description)
                )
                merchant_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Merchant '{name}' inserted with ID: {merchant_id}")
                return merchant_id
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to insert/get merchant: {e}")
            raise

    def insert_transaction(self, date: str = None, time: str = None, currency: str = 'EUR',
                          net_amount: float = None, vat_amount: float = None,
                          brutto_amount: float = None, payment_method: str = None,
                          card_number: str = None) -> int:
        """
        Insert transaction record.

        Args:
            date: Transaction date (YYYY-MM-DD)
            time: Transaction time (HH:MM:SS)
            currency: Currency code (default: EUR)
            net_amount: Net amount before tax
            vat_amount: VAT/tax amount
            brutto_amount: Total/gross amount
            payment_method: Payment method (card, cash, paypal, etc.)
            card_number: Last 4 digits of card

        Returns:
            transaction_id
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO transaction (date, time, currency, net_amount, vat_amount,
                                            brutto_amount, payment_method, card_number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING transaction_id;
                    """,
                    (date, time, currency, net_amount, vat_amount, brutto_amount,
                     payment_method, card_number)
                )
                transaction_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Transaction inserted with ID: {transaction_id}")
                return transaction_id
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to insert transaction: {e}")
            raise

    def insert_ai_analysis(self, model_name: str, extraction_status: str,
                          input_tokens: int, output_tokens: int,
                          raw_data: dict = None, error_message: str = None) -> int:
        """
        Insert AI analysis record.

        Args:
            model_name: Name of the AI model used
            extraction_status: Status (complete, partial, needs_review, failed, refused)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            raw_data: Full JSON response from Claude (optional)
            error_message: Error message if analysis failed (optional)

        Returns:
            analysis_id
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            import json
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_analysis (model_name, extraction_status, input_tokens,
                                           output_tokens, raw_data, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING analysis_id;
                    """,
                    (model_name, extraction_status, input_tokens, output_tokens,
                     json.dumps(raw_data) if raw_data else None, error_message)
                )
                analysis_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"AI analysis inserted with ID: {analysis_id}, model: {model_name}, "
                          f"tokens: {input_tokens} in / {output_tokens} out")
                return analysis_id
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to insert AI analysis: {e}")
            raise

    def update_receipt_with_analysis(self, receipt_id: int, merchant_id: int,
                                     transaction_id: int, ai_analysis_id: int) -> None:
        """
        Update receipt with analysis results from Claude.

        Args:
            receipt_id: Receipt ID
            merchant_id: Merchant ID
            transaction_id: Transaction ID
            ai_analysis_id: AI Analysis ID
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE receipt
                    SET merchant_id = %s,
                        transaction_id = %s,
                        ai_analysis_id = %s,
                        processing_status = 'completed',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE receipt_id = %s;
                    """,
                    (merchant_id, transaction_id, ai_analysis_id, receipt_id)
                )
                self.connection.commit()
                logger.info(f"Receipt {receipt_id} updated with analysis results")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update receipt with analysis: {e}")
            raise

    def insert_receipt_items(self, receipt_id: int, items: list) -> None:
        """
        Insert receipt items in batch.

        Args:
            receipt_id: Receipt ID
            items: List of item dictionaries with keys:
                   name, quantity, unit_price, total_price, category, article_number
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                for item in items:
                    # Get category_id from category name
                    category_id = None
                    if item.get('category'):
                        category_id = self.get_category_id_by_name(item['category'])

                    cursor.execute(
                        """
                        INSERT INTO receipt_item (receipt_id, category_id, item_name,
                                                 article_number, quantity, unit_price, total_price)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """,
                        (receipt_id, category_id, item.get('name'),
                         item.get('article_number'), item.get('quantity'),
                         item.get('unit_price'), item.get('total_price'))
                    )

                self.connection.commit()
                logger.info(f"Inserted {len(items)} items for receipt {receipt_id}")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to insert receipt items: {e}")
            raise
