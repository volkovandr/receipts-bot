"""
AI Analysis repository - AI analysis-related database operations.
"""

import psycopg2
import json
import logging

logger = logging.getLogger(__name__)


class AIAnalysisRepository:
    """Handles AI analysis-related database operations."""

    def __init__(self, connection):
        """
        Initialize repository with database connection.

        Args:
            connection: psycopg2 connection object
        """
        self.connection = connection

    def insert_ai_analysis(self, model_name: str, extraction_status: str,
                          input_tokens: int, output_tokens: int,
                          raw_data: dict = None, error_message: str = None) -> int:
        """
        Insert AI analysis record.

        Args:
            model_name: Name of the AI model used
            extraction_status: Status (complete, partial, needs_review, failed, refused)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            raw_data: Parsed JSON response from Claude (dict, will be stored as JSONB)
            error_message: Error message if analysis failed (optional)

        Returns:
            analysis_id
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ai_analysis (model_name, extraction_status, input_tokens,
                                           output_tokens, raw_data, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING analysis_id;
                    """,
                    (model_name, extraction_status, input_tokens, output_tokens,
                     json.dumps(raw_data) if raw_data else None, error_message)
                )
                analysis_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"AI analysis inserted with ID: {analysis_id}, model: {model_name}, "
                          f"tokens: {input_tokens} in / {output_tokens} out")
                return analysis_id
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to insert AI analysis: {e}")
            raise

    def update_ai_analysis_error(self, analysis_id: int, error_message: str) -> None:
        """
        Update AI analysis record with error message and set status to failed.

        Args:
            analysis_id: The analysis record ID to update
            error_message: Error message to store
        """
        if not self.connection:
            raise RuntimeError("Database not connected")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ai_analysis
                    SET extraction_status = 'failed',
                        error_message = %s
                    WHERE analysis_id = %s;
                    """,
                    (error_message, analysis_id)
                )
                self.connection.commit()
                logger.info(f"AI analysis {analysis_id} updated with error: {error_message[:100]}")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"Failed to update AI analysis error: {e}")
            raise
