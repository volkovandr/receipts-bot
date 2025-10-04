"""
Image repository - Image-related database operations.
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


class ImageRepository:
    """Handles image-related database operations."""

    def __init__(self, connection, user_repository):
        """
        Initialize repository with database connection.

        Args:
            connection: psycopg2 connection object
            user_repository: UserRepository instance for user operations
        """
        self.connection = connection
        self.user_repository = user_repository

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
            self.user_repository.ensure_user_exists(user_id)

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

    def update_image_processed(self, image_id: int, processed_file_path: str, processed_file_size: int) -> None:
        """
        Update image record with processed file information.

        Args:
            image_id: ID of the image record
            processed_file_path: Path to processed image file
            processed_file_size: Size of processed file in bytes
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE image
                    SET processed_file_path = %s,
                        processed_file_size = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE image_id = %s;
                    """,
                    (processed_file_path, processed_file_size, image_id)
                )
                self.connection.commit()
                logger.info(f"Image {image_id} updated with processed file: {processed_file_path}")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update image: {e}")
            raise
