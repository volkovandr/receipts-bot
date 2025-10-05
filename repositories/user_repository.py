"""
User repository - User-related database operations.
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Handles user-related database operations."""

    def __init__(self, connection):
        """
        Initialize repository with database connection.

        Args:
            connection: psycopg2 connection object
        """
        self.connection = connection

    def ensure_user_exists(self, user_id: int) -> None:
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
