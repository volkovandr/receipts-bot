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
        Categories with AI notes are returned first, then alphabetically.

        Returns:
            List of category names (strings)
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT category_name
                    FROM category
                    ORDER BY
                        ai_notes IS NULL,
                        category_name;
                    """
                )
                categories = [row[0] for row in cursor.fetchall()]
                logger.debug(f"Retrieved {len(categories)} categories from database")
                return categories
        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve categories: {e}")
            raise

    def get_all_categories_with_ids(self) -> list[tuple[int, str]]:
        """
        Get all categories with their IDs.

        Returns:
            List of tuples (category_id, category_name) sorted by name
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT category_id, category_name FROM category ORDER BY category_name;")
                categories = cursor.fetchall()
                logger.debug(f"Retrieved {len(categories)} categories with IDs from database")
                return categories
        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve categories with IDs: {e}")
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

    def get_categories_with_notes(self) -> list[tuple[str, str]]:
        """
        Get categories that have AI notes defined.

        Returns:
            List of tuples (category_name, ai_notes) where ai_notes is not NULL
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT category_name, ai_notes FROM category "
                    "WHERE ai_notes IS NOT NULL "
                    "ORDER BY category_name;"
                )
                category_notes = cursor.fetchall()
                logger.debug(f"Retrieved {len(category_notes)} categories with AI notes from database")
                return category_notes
        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve categories with notes: {e}")
            raise

    def search_categories_fuzzy(self, search_term: str, similarity_threshold: float = 0.3) -> list[tuple[int, str]]:
        """
        Search categories using fuzzy matching (case-insensitive).

        Uses PostgreSQL pg_trgm extension for trigram similarity matching.

        Args:
            search_term: Search keyword(s)
            similarity_threshold: Minimum similarity score (0.0-1.0), default 0.3

        Returns:
            List of tuples (category_id, category_name) ordered by similarity (best match first)
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT category_id, category_name,
                           SIMILARITY(LOWER(category_name), LOWER(%s)) as sim
                    FROM category
                    WHERE SIMILARITY(LOWER(category_name), LOWER(%s)) > %s
                    ORDER BY sim DESC
                    LIMIT 10;
                    """,
                    (search_term, search_term, similarity_threshold)
                )
                results = cursor.fetchall()
                matches = [(row[0], row[1]) for row in results]
                logger.debug(f"Found {len(matches)} category matches for '{search_term}'")
                return matches
        except psycopg2.Error as e:
            logger.error(f"Failed to search categories: {e}")
            raise

    def create_category(self, category_name: str, description: str = None) -> int:
        """
        Create a new category.

        Args:
            category_name: Name of the category (will be title-cased)
            description: Optional description

        Returns:
            category_id of the newly created category

        Raises:
            psycopg2.IntegrityError: If category name already exists
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        # Title-case the category name for consistency
        category_name = category_name.strip().title()

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO category (category_name, description)
                    VALUES (%s, %s)
                    RETURNING category_id;
                    """,
                    (category_name, description)
                )
                category_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Created new category: '{category_name}' with ID {category_id}")
                return category_id
        except psycopg2.IntegrityError as e:
            self.connection.rollback()
            logger.warning(f"Category '{category_name}' already exists")
            raise
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to create category: {e}")
            raise
