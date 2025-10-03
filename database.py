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
