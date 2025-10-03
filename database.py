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
