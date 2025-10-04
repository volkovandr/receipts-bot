"""
Merchant repository - Merchant-related database operations.
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


class MerchantRepository:
    """Handles merchant-related database operations."""

    def __init__(self, connection):
        """
        Initialize repository with database connection.

        Args:
            connection: psycopg2 connection object
        """
        self.connection = connection

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
                # Enable pg_trgm extension if not already enabled (safe - does nothing if exists)
                try:
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                    self.connection.commit()
                except psycopg2.Error:
                    # Extension might already exist or user lacks permissions
                    # Continue without failing
                    pass

                # Strategy 1: Case-insensitive name match with fuzzy address similarity
                if address:
                    cursor.execute(
                        """
                        SELECT merchant_id, address, similarity(address, %s) as sim
                        FROM merchant
                        WHERE LOWER(name) = LOWER(%s)
                          AND address IS NOT NULL
                          AND similarity(address, %s) >= 0.3
                        ORDER BY sim DESC
                        LIMIT 1;
                        """,
                        (address, name, address)
                    )
                    result = cursor.fetchone()

                    if result:
                        merchant_id = result[0]
                        logger.debug(f"Merchant '{name}' found by name+address fuzzy match "
                                   f"(ID: {merchant_id}, similarity: {result[2]:.2f})")
                        return merchant_id

                # Strategy 2: Case-insensitive name match only (fallback)
                cursor.execute(
                    "SELECT merchant_id FROM merchant WHERE LOWER(name) = LOWER(%s) LIMIT 1;",
                    (name,)
                )
                result = cursor.fetchone()

                if result:
                    merchant_id = result[0]
                    logger.debug(f"Merchant '{name}' found by name-only match (ID: {merchant_id})")
                    return merchant_id

                # No match found - insert new merchant
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
                logger.info(f"New merchant '{name}' inserted with ID: {merchant_id}")
                return merchant_id
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to insert/get merchant: {e}")
            raise
