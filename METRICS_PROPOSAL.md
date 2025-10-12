# Prometheus Metrics Implementation Plan

## Overview

This document outlines the implementation plan for adding Prometheus metrics to the receipts bot. The bot will expose metrics about receipt processing, token usage, and system health.

## Requirements

### Metrics to Track

1. **Receipt Metrics**
   - Total count of receipts processed
   - Count of receipts by status (created, pre-processed, completed, failed, completed/inconsistent)
   - Count of receipts by user
   - Total value of receipts (in various currencies)

2. **Receipt Item Metrics**
   - Total count of receipt items extracted
   - Total value of items (in various currencies)
   - Count of items by category

3. **Token Usage Metrics**
   - Total input tokens consumed
   - Total output tokens consumed
   - Token counts by model
   - Cache read tokens (prompt caching)
   - Cache creation tokens (prompt caching)

4. **System Health Metrics**
   - Image processing duration
   - Claude API call duration

## Implementation Plan

### Phase 1: Dependencies and Configuration

**File**: `requirements.txt`
- Add `prometheus-client>=0.23.0`

**File**: `config.ini`
- Add new `[prometheus]` section:
  ```ini
  [prometheus]
  enabled = true
  port = 8000
  ```

**File**: `config.py`
- Add Prometheus configuration parsing
- Add `prometheus_enabled` and `prometheus_port` properties

### Phase 2: Metrics Module

**New File**: `services/metrics_service.py`

This module will define and manage all Prometheus metrics

### Phase 3: Integration Points

#### 3.1 Bot Initialization (`bot.py`)

```python
from services.metrics_service import MetricsService

def main():
    config = Config('config.ini')

    # Initialize Prometheus metrics
    if config.prometheus_enabled:
        MetricsService.initialize(port=config.prometheus_port)
        logger.info("Prometheus metrics enabled")

    # ... rest of bot initialization
```

#### 3.2 Claude Service Integration (`services/claude_service.py`)

Update `analyze_receipt()` method to record token usage:

```python
def analyze_receipt(self, image_path, categories, category_notes=None):
    # ... existing code ...

    # Extract token usage from response
    usage = response.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens

    # Record metrics
    MetricsService.record_tokens(
        model=self.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=getattr(usage, 'cache_read_input_tokens', 0),
        cache_creation_tokens=getattr(usage, 'cache_creation_input_tokens', 0)
    )

    # ... rest of method
```

#### 3.3 Receipt Analyzer Integration (`services/receipt_analyzer.py`)

Update `analyze_receipt()` to record receipt and item metrics:

```python
async def analyze_receipt(receipt_id: int, user_id: int, ...):
    # ... existing processing code ...

    # Record receipt completion
    final_status = 'completed' if items_total_match else 'completed/inconsistent'
    MetricsService.record_receipt(
        status=final_status,
        user_id=user_id,
        value=float(receipt_data['transaction']['amounts']['brutto']),
        currency=receipt_data['transaction']['currency']
    )

    # Record each item
    for item in receipt_data['items']:
        MetricsService.record_item(
            category=item.get('category', 'Uncategorized'),
            user_id=user_id,
            value=float(item['total']),
            currency=receipt_data['transaction']['currency']
        )
```

#### 3.4 Image Processing Integration (`services/image_processor.py`)

Add timing metrics:

```python
from services.metrics_service import MetricsService

def process_image(input_path, output_path):
    with MetricsService.image_processing_duration.time():
        # ... existing processing code ...
```

## Implementation Order

1. ✅ Phase 1: Dependencies and Configuration
2. ✅ Phase 2: Metrics Module (core implementation)
3. ✅ Phase 3: Integration Points (instrument existing code)
7. ✅ Phase 4: Testing
8. ✅ Phase 5: Documentation

## Security Considerations

- Metrics endpoint should be internal-only (not exposed to internet)
- Consider adding basic auth if metrics contain sensitive data
- User IDs in labels should be anonymized if needed for privacy
- Rate limiting on metrics endpoint to prevent DoS

## Performance Considerations

- Metrics collection has minimal overhead (~microseconds per metric update)
- Use labels judiciously (high cardinality can cause memory issues)
- Consider aggregating user_id labels if user base grows large
- Histogram buckets should be tuned based on actual data distribution

## Future Enhancements

- Add alerting rules (e.g., high error rate, token budget exceeded)
- Create Grafana dashboard templates
- Add SLA metrics (e.g., processing time percentiles)
- Track API quota usage and remaining quota
- Add business metrics (daily/weekly spending trends)
