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

    def undelete_receipt(self, receipt_id: int, user_id: int = None) -> bool:
        """
        Restore a soft-deleted receipt.

        Args:
            receipt_id: Receipt ID
            user_id: Optional Telegram user ID for authorization (if None, no ownership check)

        Returns:
            True if receipt was restored, False if not found or not authorized
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
                        SET is_deleted = FALSE,
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
                        SET is_deleted = FALSE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE receipt_id = %s
                        RETURNING receipt_id;
                        """,
                        (receipt_id,)
                    )

                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Receipt {receipt_id} restored by user {user_id if user_id else 'N/A'}")
                    return True
                else:
                    if user_id is not None:
                        logger.warning(f"Receipt {receipt_id} not found or not owned by user {user_id}")
                    else:
                        logger.warning(f"Receipt {receipt_id} not found")
                    return False
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to restore receipt: {e}")
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

    def get_receipt_items_for_console(self, receipt_id: int, user_id: int = None) -> list[dict]:
        """
        Get all receipt items for console UI (includes deleted items, more details).

        Args:
            receipt_id: Receipt ID
            user_id: Optional user ID for ownership verification

        Returns:
            List of item dictionaries with keys:
            - item_id: int
            - receipt_id: int
            - item_name: str
            - category_id: int (or None)
            - category_name: str (or 'Uncategorized')
            - quantity: Decimal
            - unit_price: Decimal
            - total_price: Decimal
            - is_deleted: bool

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
                        SELECT ri.item_id, ri.receipt_id, ri.item_name, ri.category_id,
                               COALESCE(c.category_name, 'Uncategorized') as category_name,
                               ri.quantity, ri.unit_price, ri.total_price, ri.is_deleted
                        FROM receipt_item ri
                        LEFT JOIN category c ON ri.category_id = c.category_id
                        JOIN receipt r ON ri.receipt_id = r.receipt_id
                        WHERE ri.receipt_id = %s AND r.user_id = %s
                        ORDER BY ri.item_id;
                        """,
                        (receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT ri.item_id, ri.receipt_id, ri.item_name, ri.category_id,
                               COALESCE(c.category_name, 'Uncategorized') as category_name,
                               ri.quantity, ri.unit_price, ri.total_price, ri.is_deleted
                        FROM receipt_item ri
                        LEFT JOIN category c ON ri.category_id = c.category_id
                        WHERE ri.receipt_id = %s
                        ORDER BY ri.item_id;
                        """,
                        (receipt_id,)
                    )

                columns = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                logger.debug(f"Retrieved {len(results)} items for receipt {receipt_id} (console UI)")
                return results
        except psycopg2.Error as e:
            logger.error(f"Failed to get receipt items for console: {e}")
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

    def undelete_item(self, item_id: int, receipt_id: int, user_id: int = None) -> bool:
        """
        Restore a deleted receipt item (undelete).

        Args:
            item_id: Item ID
            receipt_id: Receipt ID (for authorization)
            user_id: Optional user ID for ownership verification

        Returns:
            True if item was restored, False if not found or not authorized
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
                        SET is_deleted = FALSE,
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
                        SET is_deleted = FALSE,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE item_id = %s AND receipt_id = %s
                        RETURNING item_id;
                        """,
                        (item_id, receipt_id)
                    )

                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Item {item_id} restored (undeleted)")
                    return True
                else:
                    logger.warning(f"Item {item_id} not found or not authorized for receipt {receipt_id}")
                    return False
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to restore item: {e}")
            raise

    def update_item_name(self, item_id: int, receipt_id: int, new_name: str, user_id: int = None) -> bool:
        """
        Update receipt item name.

        Args:
            item_id: Item ID
            receipt_id: Receipt ID (for authorization)
            new_name: New item name
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
                        SET item_name = %s,
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
                        (new_name, item_id, receipt_id, receipt_id, user_id)
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE receipt_item
                        SET item_name = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE item_id = %s AND receipt_id = %s AND is_deleted = FALSE
                        RETURNING item_id;
                        """,
                        (new_name, item_id, receipt_id)
                    )

                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Item {item_id} name updated to '{new_name}'")
                    return True
                else:
                    logger.warning(f"Item {item_id} not found or not authorized for receipt {receipt_id}")
                    return False
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update item name: {e}")
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

    def update_item_category(self, item_id: int, receipt_id: int, category_id: int | None, user_id: int = None) -> bool:
        """
        Update receipt item category.

        Args:
            item_id: Item ID
            receipt_id: Receipt ID (for authorization)
            category_id: New category ID (or None for uncategorized)
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

    def get_recent_receipts(self, user_id: int, limit: int = 3) -> list[int]:
        """
        Get recent receipt IDs for a user (non-deleted, sorted by creation date).

        Args:
            user_id: Telegram user ID
            limit: Number of receipts to retrieve (default: 3)

        Returns:
            List of receipt IDs, most recent first
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT receipt_id
                    FROM receipt
                    WHERE user_id = %s AND is_deleted = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (user_id, limit)
                )
                results = cursor.fetchall()
                receipt_ids = [row[0] for row in results]
                logger.debug(f"Retrieved {len(receipt_ids)} recent receipts for user {user_id}")
                return receipt_ids
        except psycopg2.Error as e:
            logger.error(f"Failed to get recent receipts: {e}")
            raise

    def get_all_receipts_for_list(self, user_id: int, include_deleted: bool = False) -> list[dict]:
        """
        Get all receipts for display in a list view (console UI).

        Args:
            user_id: Telegram user ID
            include_deleted: If True, include soft-deleted receipts in results

        Returns:
            List of dicts with keys:
            - receipt_id: int
            - transaction_date: date
            - transaction_time: time
            - merchant_name: str
            - merchant_city: str
            - item_count: int
            - currency: str
            - total_items: Decimal (sum of items)
            - total_receipt: Decimal (receipt brutto amount)
            - has_discrepancy: bool
            - processing_status: str
            - top_category: str (category with highest spending)
            - is_deleted: bool
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Build WHERE clause based on include_deleted parameter
                where_clause = "r.user_id = %s"
                if not include_deleted:
                    where_clause += " AND r.is_deleted = FALSE"

                query = f"""
                    WITH category_totals AS (
                        SELECT
                            ri.receipt_id,
                            c.category_name,
                            SUM(ri.total_price) AS category_total,
                            ROW_NUMBER() OVER (
                                PARTITION BY ri.receipt_id
                                ORDER BY SUM(ri.total_price) DESC
                            ) AS rn
                        FROM receipt_item ri
                        LEFT JOIN category c ON ri.category_id = c.category_id
                        WHERE ri.is_deleted = FALSE
                        GROUP BY ri.receipt_id, c.category_name
                    )
                    SELECT
                        r.receipt_id,
                        r.merchant_id,
                        COALESCE(t.date, r.created_at::date) AS transaction_date,
                        t.time AS transaction_time,
                        COALESCE(m.name, 'Unknown') AS merchant_name,
                        COALESCE(m.city, '') AS merchant_city,
                        COUNT(DISTINCT ri.item_id) AS item_count,
                        COALESCE(t.currency, 'EUR') AS currency,
                        COALESCE(SUM(ri.total_price), 0) AS total_items,
                        COALESCE(t.brutto_amount, 0) AS total_receipt,
                        (ABS(COALESCE(SUM(ri.total_price), 0) - COALESCE(t.brutto_amount, 0)) > 0.01) AS has_discrepancy,
                        r.processing_status,
                        COALESCE(ct.category_name, '') AS top_category,
                        r.is_deleted
                    FROM receipt r
                    LEFT JOIN merchant m ON r.merchant_id = m.merchant_id
                    LEFT JOIN transaction t ON r.transaction_id = t.transaction_id
                    LEFT JOIN receipt_item ri ON r.receipt_id = ri.receipt_id AND ri.is_deleted = FALSE
                    LEFT JOIN category_totals ct ON r.receipt_id = ct.receipt_id AND ct.rn = 1
                    WHERE {where_clause}
                    GROUP BY
                        r.receipt_id,
                        t.date,
                        t.time,
                        m.name,
                        m.city,
                        t.currency,
                        t.brutto_amount,
                        r.processing_status,
                        r.created_at,
                        ct.category_name,
                        r.is_deleted
                    ORDER BY COALESCE(t.date, r.created_at::date) DESC, COALESCE(t.time, r.created_at::time) DESC;
                """

                cursor.execute(query, (user_id,))
                columns = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                logger.debug(f"Retrieved {len(results)} receipts for list view")
                return results
        except psycopg2.Error as e:
            logger.error(f"Failed to get receipts for list: {e}")
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

    def create_item(self, receipt_id: int, user_id: int, item_name: str,
                    quantity: float, unit_price: float, total_price: float,
                    category_id: int = None, article_number: str = None) -> int:
        """
        Create a new receipt item.

        Args:
            receipt_id: Receipt ID
            user_id: User ID (for authorization)
            item_name: Item name
            quantity: Item quantity
            unit_price: Unit price
            total_price: Total price
            category_id: Optional category ID
            article_number: Optional article number

        Returns:
            item_id: The ID of the created item, or None if failed

        Raises:
            RuntimeError: If database not connected
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Verify user owns this receipt
                cursor.execute(
                    """
                    SELECT user_id FROM receipt WHERE receipt_id = %s;
                    """,
                    (receipt_id,)
                )
                result = cursor.fetchone()

                if not result:
                    logger.warning(f"Receipt {receipt_id} not found")
                    return None

                if result[0] != user_id:
                    logger.warning(f"User {user_id} attempted to create item for receipt {receipt_id} owned by user {result[0]}")
                    return None

                # Create the item
                cursor.execute(
                    """
                    INSERT INTO receipt_item (receipt_id, item_name, article_number, quantity, unit_price, total_price, category_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING item_id;
                    """,
                    (receipt_id, item_name, article_number, quantity, unit_price, total_price, category_id)
                )
                item_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Created item {item_id} for receipt {receipt_id}: '{item_name}' x {quantity} @ {unit_price} = {total_price}")
                return item_id

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to create item: {e}")
            return None

    def update_receipt_merchant(self, receipt_id: int, merchant_id: int, user_id: int = None) -> bool:
        """
        Update receipt's merchant.

        Args:
            receipt_id: Receipt ID
            merchant_id: New merchant ID
            user_id: User ID (for authorization, optional)

        Returns:
            True if updated successfully, False otherwise
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Verify user owns this receipt (if user_id provided)
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT user_id FROM receipt WHERE receipt_id = %s;
                        """,
                        (receipt_id,)
                    )
                    result = cursor.fetchone()

                    if not result:
                        logger.warning(f"Receipt {receipt_id} not found")
                        return False

                    if result[0] != user_id:
                        logger.warning(f"User {user_id} attempted to update merchant for receipt {receipt_id} owned by user {result[0]}")
                        return False

                # Update merchant
                cursor.execute(
                    """
                    UPDATE receipt
                    SET merchant_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE receipt_id = %s
                    RETURNING receipt_id;
                    """,
                    (merchant_id, receipt_id)
                )
                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Receipt {receipt_id} merchant updated to {merchant_id}")
                    return True
                else:
                    logger.warning(f"Receipt {receipt_id} not found")
                    return False

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update receipt merchant: {e}")
            raise

    def get_receipt_transaction_id(self, receipt_id: int, user_id: int = None) -> int | None:
        """
        Get transaction_id for a receipt.

        Args:
            receipt_id: Receipt ID
            user_id: User ID (for authorization, optional)

        Returns:
            transaction_id or None if not found or not authorized
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                # Verify user owns this receipt (if user_id provided)
                if user_id is not None:
                    cursor.execute(
                        """
                        SELECT transaction_id, user_id
                        FROM receipt
                        WHERE receipt_id = %s;
                        """,
                        (receipt_id,)
                    )
                    result = cursor.fetchone()

                    if not result:
                        logger.warning(f"Receipt {receipt_id} not found")
                        return None

                    if result[1] != user_id:
                        logger.warning(f"User {user_id} attempted to access receipt {receipt_id} owned by user {result[1]}")
                        return None

                    return result[0]
                else:
                    cursor.execute(
                        """
                        SELECT transaction_id
                        FROM receipt
                        WHERE receipt_id = %s;
                        """,
                        (receipt_id,)
                    )
                    result = cursor.fetchone()
                    return result[0] if result else None

        except psycopg2.Error as e:
            logger.error(f"Failed to get receipt transaction_id: {e}")
            raise
