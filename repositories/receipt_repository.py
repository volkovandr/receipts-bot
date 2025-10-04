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
        Calculate the sum of all non-deleted item total prices for a receipt.

        Args:
            receipt_id: Receipt ID

        Returns:
            Sum of all non-deleted item total_price values, or 0.0 if no items
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(total_price), 0.0)
                    FROM receipt_item
                    WHERE receipt_id = %s AND is_deleted = FALSE;
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
        Get receipt items grouped by category with totals (excludes deleted items).

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
                    WHERE ri.receipt_id = %s AND ri.is_deleted = FALSE
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

    def get_receipt_items_detailed(self, receipt_id: int, user_id: int = None) -> list[dict]:
        """
        Get detailed list of receipt items (excludes deleted items).

        Args:
            receipt_id: Receipt ID
            user_id: Optional user ID for ownership verification

        Returns:
            List of item dictionaries with keys:
            - item_id: int
            - item_name: str
            - category_name: str (or 'Uncategorized')
            - quantity: float
            - total_price: float

        Raises:
            RuntimeError: If database not connected
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Build query with optional user_id check
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT ri.item_id, ri.item_name,
                               COALESCE(c.category_name, 'Uncategorized') as category_name,
                               ri.quantity, ri.total_price
                        FROM receipt_item ri
                        LEFT JOIN category c ON ri.category_id = c.category_id
                        JOIN receipt r ON ri.receipt_id = r.receipt_id
                        WHERE ri.receipt_id = %s
                          AND r.user_id = %s
                          AND ri.is_deleted = FALSE
                        ORDER BY ri.item_id;
                        """,
                        (receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT ri.item_id, ri.item_name,
                               COALESCE(c.category_name, 'Uncategorized') as category_name,
                               ri.quantity, ri.total_price
                        FROM receipt_item ri
                        LEFT JOIN category c ON ri.category_id = c.category_id
                        WHERE ri.receipt_id = %s AND ri.is_deleted = FALSE
                        ORDER BY ri.item_id;
                        """,
                        (receipt_id,)
                    )

                results = cursor.fetchall()
                items = [
                    {
                        'item_id': row[0],
                        'item_name': row[1],
                        'category_name': row[2],
                        'quantity': float(row[3]) if row[3] is not None else None,
                        'total_price': float(row[4]) if row[4] is not None else 0.0
                    }
                    for row in results
                ]
                logger.debug(f"Retrieved {len(items)} items for receipt {receipt_id}")
                return items
        except psycopg2.Error as e:
            logger.error(f"Failed to get receipt items: {e}")
            raise

    def mark_item_as_deleted(self, item_id: int, receipt_id: int, user_id: int = None) -> bool:
        """
        Mark receipt item as deleted (soft delete).

        Args:
            item_id: Item ID
            receipt_id: Receipt ID (for authorization)
            user_id: Optional user ID for ownership verification

        Returns:
            True if item was marked as deleted, False if not found or not authorized
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Build query with ownership verification
                if user_id is not None:
                    cursor.execute(
                        """
                        UPDATE receipt_item
                        SET is_deleted = TRUE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE item_id = %s
                          AND receipt_id = %s
                          AND receipt_id IN (
                              SELECT receipt_id FROM receipt
                              WHERE receipt_id = %s AND user_id = %s
                          )
                        RETURNING item_id;
                        """,
                        (item_id, receipt_id, receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE receipt_item
                        SET is_deleted = TRUE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE item_id = %s AND receipt_id = %s
                        RETURNING item_id;
                        """,
                        (item_id, receipt_id)
                    )

                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Item {item_id} marked as deleted")
                    return True
                else:
                    logger.warning(f"Item {item_id} not found or not authorized for receipt {receipt_id}")
                    return False
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to mark item as deleted: {e}")
            raise

    def update_item_amount(self, item_id: int, receipt_id: int, new_amount: float, user_id: int = None) -> bool:
        """
        Update receipt item total price.

        Args:
            item_id: Item ID
            receipt_id: Receipt ID (for authorization)
            new_amount: New total price
            user_id: Optional user ID for ownership verification

        Returns:
            True if item was updated, False if not found or not authorized
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Build query with ownership verification
                if user_id is not None:
                    cursor.execute(
                        """
                        UPDATE receipt_item
                        SET total_price = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE item_id = %s
                          AND receipt_id = %s
                          AND is_deleted = FALSE
                          AND receipt_id IN (
                              SELECT receipt_id FROM receipt
                              WHERE receipt_id = %s AND user_id = %s
                          )
                        RETURNING item_id;
                        """,
                        (new_amount, item_id, receipt_id, receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE receipt_item
                        SET total_price = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE item_id = %s AND receipt_id = %s AND is_deleted = FALSE
                        RETURNING item_id;
                        """,
                        (new_amount, item_id, receipt_id)
                    )

                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Item {item_id} amount updated to {new_amount}")
                    return True
                else:
                    logger.warning(f"Item {item_id} not found or not authorized for receipt {receipt_id}")
                    return False
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update item amount: {e}")
            raise

    def update_item_category(self, item_id: int, receipt_id: int, category_id: int, user_id: int = None) -> bool:
        """
        Update receipt item category.

        Args:
            item_id: Item ID
            receipt_id: Receipt ID (for authorization)
            category_id: New category ID
            user_id: Optional user ID for ownership verification

        Returns:
            True if item was updated, False if not found or not authorized
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Build query with ownership verification
                if user_id is not None:
                    cursor.execute(
                        """
                        UPDATE receipt_item
                        SET category_id = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE item_id = %s
                          AND receipt_id = %s
                          AND is_deleted = FALSE
                          AND receipt_id IN (
                              SELECT receipt_id FROM receipt
                              WHERE receipt_id = %s AND user_id = %s
                          )
                        RETURNING item_id;
                        """,
                        (category_id, item_id, receipt_id, receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE receipt_item
                        SET category_id = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE item_id = %s AND receipt_id = %s AND is_deleted = FALSE
                        RETURNING item_id;
                        """,
                        (category_id, item_id, receipt_id)
                    )

                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Item {item_id} category updated to {category_id}")
                    return True
                else:
                    logger.warning(f"Item {item_id} not found or not authorized for receipt {receipt_id}")
                    return False
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update item category: {e}")
            raise

    def get_receipt_summary_data(self, receipt_id: int, user_id: int = None) -> dict | None:
        """
        Get receipt summary data for formatting.

        Args:
            receipt_id: Receipt ID
            user_id: Optional user ID for ownership verification

        Returns:
            Dictionary with keys:
            - merchant_name: str
            - transaction_date: str
            - currency: str
            - brutto_amount: float
            - uncertain_fields: list
            - need_clarification: list
            - has_edits: bool (True if any items have been modified)

            Returns None if receipt not found or not authorized
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Build query with optional user_id check
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT
                            COALESCE(m.name, 'Unknown') as merchant_name,
                            COALESCE(t.date::text, 'N/A') as transaction_date,
                            COALESCE(t.currency, 'EUR') as currency,
                            t.brutto_amount,
                            a.raw_data,
                            EXISTS(
                                SELECT 1 FROM receipt_item
                                WHERE receipt_id = r.receipt_id
                                AND updated_at > created_at
                            ) as has_edits
                        FROM receipt r
                        LEFT JOIN merchant m ON r.merchant_id = m.merchant_id
                        LEFT JOIN transaction t ON r.transaction_id = t.transaction_id
                        LEFT JOIN ai_analysis a ON r.ai_analysis_id = a.analysis_id
                        WHERE r.receipt_id = %s AND r.user_id = %s;
                        """,
                        (receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT
                            COALESCE(m.name, 'Unknown') as merchant_name,
                            COALESCE(t.date::text, 'N/A') as transaction_date,
                            COALESCE(t.currency, 'EUR') as currency,
                            t.brutto_amount,
                            a.raw_data,
                            EXISTS(
                                SELECT 1 FROM receipt_item
                                WHERE receipt_id = r.receipt_id
                                AND updated_at > created_at
                            ) as has_edits
                        FROM receipt r
                        LEFT JOIN merchant m ON r.merchant_id = m.merchant_id
                        LEFT JOIN transaction t ON r.transaction_id = t.transaction_id
                        LEFT JOIN ai_analysis a ON r.ai_analysis_id = a.analysis_id
                        WHERE r.receipt_id = %s;
                        """,
                        (receipt_id,)
                    )

                result = cursor.fetchone()

                if result:
                    raw_data = result[4] if result[4] else {}
                    return {
                        'merchant_name': result[0],
                        'transaction_date': result[1],
                        'currency': result[2],
                        'brutto_amount': float(result[3]) if result[3] is not None else None,
                        'uncertain_fields': raw_data.get('uncertain_fields', []),
                        'need_clarification': raw_data.get('need_clarification', []),
                        'has_edits': result[5]
                    }
                else:
                    if user_id is not None:
                        logger.warning(f"Receipt {receipt_id} not found or not owned by user {user_id}")
                    else:
                        logger.warning(f"Receipt {receipt_id} not found")
                    return None
        except psycopg2.Error as e:
            logger.error(f"Failed to get receipt summary data: {e}")
            raise
