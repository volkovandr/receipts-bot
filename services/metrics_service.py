"""
Prometheus metrics service for receipts bot.
Tracks receipt processing, token usage, and system health metrics.
"""

import logging
from typing import Optional
from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for collecting and exposing Prometheus metrics."""

    # Flag to track if metrics are enabled
    _initialized = False

    # Receipt Metrics
    receipts_total = Counter(
        'receipts_total',
        'Total number of receipts processed',
        ['status', 'user_id']
    )

    receipts_value = Counter(
        'receipts_value_total',
        'Total value of receipts processed',
        ['currency', 'user_id']
    )

    receipts_by_status = Gauge(
        'receipts_by_status',
        'Current count of receipts by status',
        ['status']
    )

    # Receipt Item Metrics
    receipt_items_total = Counter(
        'receipt_items_total',
        'Total number of receipt items extracted',
        ['category', 'user_id']
    )

    receipt_items_value = Counter(
        'receipt_items_value_total',
        'Total value of receipt items',
        ['category', 'currency', 'user_id']
    )

    # Token Usage Metrics
    tokens_input = Counter(
        'claude_tokens_input_total',
        'Total input tokens consumed',
        ['model']
    )

    tokens_output = Counter(
        'claude_tokens_output_total',
        'Total output tokens consumed',
        ['model']
    )

    tokens_cache_read = Counter(
        'claude_tokens_cache_read_total',
        'Total cache read tokens (prompt caching)',
        ['model']
    )

    tokens_cache_creation = Counter(
        'claude_tokens_cache_creation_total',
        'Total cache creation tokens (prompt caching)',
        ['model']
    )

    # System Health Metrics
    image_processing_duration = Histogram(
        'image_processing_duration_seconds',
        'Time spent processing receipt images',
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
    )

    claude_api_duration = Histogram(
        'claude_api_duration_seconds',
        'Time spent in Claude API calls',
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 60.0]
    )

    @classmethod
    def initialize(cls, port: int = 8000) -> None:
        """
        Initialize Prometheus metrics server.

        Args:
            port: Port to expose metrics on (default: 8000)
        """
        if cls._initialized:
            logger.warning("Metrics service already initialized")
            return

        try:
            start_http_server(port)
            cls._initialized = True
            logger.info(f"Prometheus metrics server started on port {port}")
            logger.info(f"Metrics available at http://localhost:{port}/metrics")
        except Exception as e:
            logger.error(f"Failed to start Prometheus metrics server: {e}")
            raise

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if metrics collection is enabled."""
        return cls._initialized

    @classmethod
    def record_receipt(
        cls,
        status: str,
        user_id: int,
        value: float,
        currency: str
    ) -> None:
        """
        Record a processed receipt.

        Args:
            status: Receipt status (completed, failed, etc.)
            user_id: Telegram user ID
            value: Receipt total value
            currency: Currency code (EUR, USD, etc.)
        """
        if not cls._initialized:
            return

        try:
            cls.receipts_total.labels(status=status, user_id=str(user_id)).inc()
            # Use absolute value for counter (Prometheus counters can only be non-negative)
            cls.receipts_value.labels(currency=currency, user_id=str(user_id)).inc(abs(value))
            cls.receipts_by_status.labels(status=status).inc()
        except Exception as e:
            logger.error(f"Failed to record receipt metric: {e}")

    @classmethod
    def record_item(
        cls,
        category: str,
        user_id: int,
        value: float,
        currency: str
    ) -> None:
        """
        Record a receipt item.

        Args:
            category: Item category
            user_id: Telegram user ID
            value: Item total value (can be negative for refunds/discounts)
            currency: Currency code
        """
        if not cls._initialized:
            return

        try:
            cls.receipt_items_total.labels(category=category, user_id=str(user_id)).inc()
            # Use absolute value for counter (Prometheus counters can only be non-negative)
            # This tracks transaction volume regardless of direction (purchase vs refund)
            cls.receipt_items_value.labels(
                category=category,
                currency=currency,
                user_id=str(user_id)
            ).inc(abs(value))
        except Exception as e:
            logger.error(f"Failed to record item metric: {e}")

    @classmethod
    def record_tokens(
        cls,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0
    ) -> None:
        """
        Record token usage from Claude API.

        Args:
            model: Model name (e.g., claude-sonnet-4-5-20250929)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_read_tokens: Number of cache read tokens (prompt caching)
            cache_creation_tokens: Number of cache creation tokens (prompt caching)
        """
        if not cls._initialized:
            return

        try:
            cls.tokens_input.labels(model=model).inc(input_tokens)
            cls.tokens_output.labels(model=model).inc(output_tokens)

            if cache_read_tokens > 0:
                cls.tokens_cache_read.labels(model=model).inc(cache_read_tokens)

            if cache_creation_tokens > 0:
                cls.tokens_cache_creation.labels(model=model).inc(cache_creation_tokens)
        except Exception as e:
            logger.error(f"Failed to record token metric: {e}")
