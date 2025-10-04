"""
Receipt repository - Receipt-related database operations.
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


class ReceiptRepository:
    """Handles receipt-related database operations."""

    def __init__(self, connection, category_repository):
        """
        Initialize repository with database connection.

        Args:
            connection: psycopg2 connection object
            category_repository: CategoryRepository instance for category lookups
        """
        self.connection = connection
        self.category_repository = category_repository

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
                        category_id = self.category_repository.get_category_id_by_name(item['category'])

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

    def get_receipt_items_sum(self, receipt_id: int) -> float:
        """
        Calculate the sum of all item total prices for a receipt.

        Args:
            receipt_id: Receipt ID

        Returns:
            Sum of all item total_price values, or 0.0 if no items
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(total_price), 0.0)
                    FROM receipt_item
                    WHERE receipt_id = %s;
                    """,
                    (receipt_id,)
                )
                result = cursor.fetchone()[0]
                logger.debug(f"Receipt {receipt_id} items sum: {result}")
                return float(result) if result else 0.0
        except psycopg2.Error as e:
            logger.error(f"Failed to calculate receipt items sum: {e}")
            raise

    def get_receipt_items_by_category(self, receipt_id: int) -> list:
        """
        Get receipt items grouped by category with totals.

        Args:
            receipt_id: Receipt ID

        Returns:
            List of tuples: (category_name, item_count, total_amount)
            Ordered by total_amount descending
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        COALESCE(c.category_name, 'Uncategorized') as category_name,
                        COUNT(ri.item_id) as item_count,
                        COALESCE(SUM(ri.total_price), 0.0) as total_amount
                    FROM receipt_item ri
                    LEFT JOIN category c ON ri.category_id = c.category_id
                    WHERE ri.receipt_id = %s
                    GROUP BY c.category_name
                    ORDER BY total_amount DESC;
                    """,
                    (receipt_id,)
                )
                results = cursor.fetchall()
                logger.debug(f"Receipt {receipt_id} has {len(results)} categories")
                return [(row[0], int(row[1]), float(row[2])) for row in results]
        except psycopg2.Error as e:
            logger.error(f"Failed to get receipt items by category: {e}")
            raise

    def mark_receipt_as_deleted(self, receipt_id: int, user_id: int = None) -> bool:
        """
        Mark receipt as deleted (soft delete).

        Args:
            receipt_id: Receipt ID
            user_id: Optional user ID for ownership verification

        Returns:
            True if receipt was marked as deleted, False if not found or not authorized
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Build query with optional user_id check
                if user_id is not None:
                    cursor.execute(
                        """
                        UPDATE receipt
                        SET is_deleted = TRUE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE receipt_id = %s AND user_id = %s
                        RETURNING receipt_id;
                        """,
                        (receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE receipt
                        SET is_deleted = TRUE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE receipt_id = %s
                        RETURNING receipt_id;
                        """,
                        (receipt_id,)
                    )

                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Receipt {receipt_id} marked as deleted by user {user_id if user_id else 'N/A'}")
                    return True
                else:
                    if user_id is not None:
                        logger.warning(f"Receipt {receipt_id} not found or not owned by user {user_id}")
                    else:
                        logger.warning(f"Receipt {receipt_id} not found")
                    return False
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to mark receipt as deleted: {e}")
            raise

    def verify_receipt_owner(self, receipt_id: int, user_id: int) -> bool:
        """
        Verify that a receipt belongs to a specific user.

        Args:
            receipt_id: Receipt ID
            user_id: Telegram user ID

        Returns:
            True if receipt belongs to user, False otherwise
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id
                    FROM receipt
                    WHERE receipt_id = %s;
                    """,
                    (receipt_id,)
                )
                result = cursor.fetchone()

                if result:
                    receipt_owner_id = result[0]
                    is_owner = (receipt_owner_id == user_id)
                    if not is_owner:
                        logger.warning(f"User {user_id} attempted to access receipt {receipt_id} owned by {receipt_owner_id}")
                    return is_owner
                else:
                    logger.warning(f"Receipt {receipt_id} not found during ownership check")
                    return False
        except psycopg2.Error as e:
            logger.error(f"Failed to verify receipt ownership: {e}")
            raise

    def get_receipt_processed_image_path(self, receipt_id: int, user_id: int = None) -> str | None:
        """
        Get the processed image path for a receipt.

        Args:
            receipt_id: Receipt ID
            user_id: Optional user ID for ownership verification

        Returns:
            Path to processed image file, or None if not found or not authorized
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Build query with optional user_id check
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT i.processed_file_path, i.orig_file_path
                        FROM receipt r
                        JOIN image i ON r.image_id = i.image_id
                        WHERE r.receipt_id = %s AND r.user_id = %s;
                        """,
                        (receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT i.processed_file_path, i.orig_file_path
                        FROM receipt r
                        JOIN image i ON r.image_id = i.image_id
                        WHERE r.receipt_id = %s;
                        """,
                        (receipt_id,)
                    )

                result = cursor.fetchone()

                if result:
                    # Return processed path if available, otherwise original
                    processed_path = result[0]
                    original_path = result[1]
                    path = processed_path if processed_path else original_path
                    logger.debug(f"Receipt {receipt_id} image path: {path}")
                    return path
                else:
                    if user_id is not None:
                        logger.warning(f"Receipt {receipt_id} not found or not owned by user {user_id}")
                    else:
                        logger.warning(f"Receipt {receipt_id} not found")
                    return None
        except psycopg2.Error as e:
            logger.error(f"Failed to get receipt image path: {e}")
            raise
