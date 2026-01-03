"""
Transaction repository - Transaction-related database operations.
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


class TransactionRepository:
    """Handles transaction-related database operations."""

    def __init__(self, connection):
        """
        Initialize repository with database connection.

        Args:
            connection: psycopg2 connection object
        """
        self.connection = connection

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

    def update_transaction_datetime(self, transaction_id: int, date, time) -> bool:
        """
        Update transaction date and time.

        Args:
            transaction_id: Transaction ID
            date: New date (date object or None)
            time: New time (time object or None)

        Returns:
            True if updated successfully, False if transaction not found
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE transaction
                    SET date = %s,
                        time = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE transaction_id = %s
                    RETURNING transaction_id;
                    """,
                    (date, time, transaction_id)
                )
                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Transaction {transaction_id} date/time updated to {date} {time}")
                    return True
                else:
                    logger.warning(f"Transaction {transaction_id} not found")
                    return False

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update transaction datetime: {e}")
            raise

    def update_transaction_total(self, transaction_id: int, brutto_amount: float) -> bool:
        """
        Update transaction brutto (total) amount.

        Args:
            transaction_id: Transaction ID
            brutto_amount: New brutto/total amount

        Returns:
            True if updated successfully, False if transaction not found
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE transaction
                    SET brutto_amount = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE transaction_id = %s
                    RETURNING transaction_id;
                    """,
                    (brutto_amount, transaction_id)
                )
                result = cursor.fetchone()
                self.connection.commit()

                if result:
                    logger.info(f"Transaction {transaction_id} total amount updated to {brutto_amount}")
                    return True
                else:
                    logger.warning(f"Transaction {transaction_id} not found")
                    return False

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update transaction total: {e}")
            raise
