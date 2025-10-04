"""
Category repository - Category-related database operations.
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


class CategoryRepository:
    """Handles category-related database operations."""

    def __init__(self, connection):
        """
        Initialize repository with database connection.

        Args:
            connection: psycopg2 connection object
        """
        self.connection = connection

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
