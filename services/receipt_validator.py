"""
Receipt validation service.
Validates and enriches receipt data from Claude AI response.
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def validate_and_enrich_items(
    items: List[Dict],
    categories_data: List[Dict],
    default_category: str
) -> List[Dict]:
    """
    Validate category indices and enrich items with category assignments.

    Args:
        items: List of item dicts from Claude response
        categories_data: List of category dicts with item indices
        default_category: Category name to use for uncategorized items

    Returns:
        List of items enriched with 'category', 'quantity', 'unit_price' fields

    Raises:
        ValueError: If validation fails (out-of-bounds indices, duplicate assignments)
    """

    # Track which items have been categorized
    item_categories = {}  # {item_index: category_name}
    duplicate_assignments = []  # Track duplicates for logging
    out_of_bounds_indices = []  # Track invalid indices

    # Phase 1: Build index-to-category mapping with validation
    for cat_group in categories_data:
        category_name = cat_group.get('name')
        if not category_name:
            logger.warning(f"Category group missing 'name' field: {cat_group}")
            continue

        item_indices = cat_group.get('items', [])

        for idx in item_indices:
            # Validate index type
            if not isinstance(idx, int):
                logger.error(f"Invalid index type in category '{category_name}': {idx} (type: {type(idx)})")
                raise ValueError(f"Invalid index type: {idx} must be integer, got {type(idx)}")

            # Validate index bounds
            if idx < 0 or idx >= len(items):
                out_of_bounds_indices.append({
                    'index': idx,
                    'category': category_name,
                    'valid_range': f"0-{len(items)-1}"
                })
                logger.error(f"Out-of-bounds index in category '{category_name}': {idx} (valid range: 0-{len(items)-1})")
                continue  # Don't raise yet, collect all errors first

            # Check for duplicate assignments
            if idx in item_categories:
                duplicate_assignments.append({
                    'index': idx,
                    'first_category': item_categories[idx],
                    'duplicate_category': category_name
                })
                logger.error(f"Duplicate index assignment: item {idx} assigned to both '{item_categories[idx]}' and '{category_name}'")
                continue  # Don't raise yet, collect all errors first

            # Valid assignment
            item_categories[idx] = category_name

    # Raise error if we found validation issues
    if out_of_bounds_indices or duplicate_assignments:
        error_parts = []
        if out_of_bounds_indices:
            error_parts.append(f"{len(out_of_bounds_indices)} out-of-bounds indices")
        if duplicate_assignments:
            error_parts.append(f"{len(duplicate_assignments)} duplicate assignments")

        error_msg = f"Category validation failed: {', '.join(error_parts)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Log summary of categorization
    uncategorized_count = len(items) - len(item_categories)
    if uncategorized_count > 0:
        logger.info(f"Found {uncategorized_count} uncategorized items, will assign to '{default_category}'")

    # Phase 2: Enrich items with category and defaults
    for idx, item in enumerate(items):
        # Add category (from mapping or default)
        item['category'] = item_categories.get(idx, default_category)

        # Default quantity to 1 if not present
        if 'quantity' not in item:
            item['quantity'] = 1

        # Calculate unit_price if not present
        if 'unit_price' not in item:
            item['unit_price'] = item['total_price'] / item['quantity']

    return items
