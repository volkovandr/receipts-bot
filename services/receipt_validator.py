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
    categories_lookup: Dict[int, str],
    default_category_id: int,
    default_category_name: str
) -> List[Dict]:
    """
    Validate category IDs and indices, then enrich items with category assignments.

    Args:
        items: List of item dicts from Claude response
        categories_data: List of category dicts with item indices from Claude (format: {"id": 23, "items": [0,1]})
        categories_lookup: Dict mapping category_id to category_name from database
        default_category_id: Category ID to use for uncategorized items
        default_category_name: Category name to use for uncategorized items

    Returns:
        List of items enriched with 'category', 'category_id', 'quantity', 'unit_price' fields

    Raises:
        ValueError: If validation fails (invalid category IDs, out-of-bounds indices, duplicate assignments)
    """

    # Track which items have been categorized
    item_categories = {}  # {item_index: category_name}
    item_category_ids = {}  # {item_index: category_id}
    duplicate_assignments = []  # Track duplicates for logging
    out_of_bounds_indices = []  # Track invalid indices
    invalid_category_ids = []  # Track unknown category IDs

    # Phase 1: Build index-to-category mapping with validation
    # Support two formats:
    # - Old format (JSON): categories_data = [{id: 36, items: [0,1,2]}]
    # - New format (TOON): category_id directly in each item, categories_data = []

    # Check if using new format (TOON) where category_id is in items
    using_new_format = False
    if not categories_data or len(categories_data) == 0:
        # Check if items have category_id field
        if items and len(items) > 0 and 'category_id' in items[0]:
            using_new_format = True
            logger.info("Using new TOON format: category_id embedded in items")

    if using_new_format:
        # New format: Extract category_id directly from items
        for idx, item in enumerate(items):
            category_id = item.get('category_id')

            if category_id is None:
                # Item has no category - will be assigned default later
                continue

            # Validate category ID type
            if not isinstance(category_id, int):
                logger.error(f"Invalid category ID type in item {idx}: {category_id} (type: {type(category_id)})")
                raise ValueError(f"Invalid category ID type: must be integer, got {type(category_id)}")

            # Validate category exists in database
            if category_id not in categories_lookup:
                invalid_category_ids.append({
                    'id': category_id,
                    'valid_ids': sorted(categories_lookup.keys())[:10]
                })
                logger.error(f"Unknown category ID in item {idx}: {category_id} (not in database)")
                continue

            category_name = categories_lookup[category_id]
            item_categories[idx] = category_name
            item_category_ids[idx] = category_id
    else:
        # Old format: Use separate categories array with index mapping
        for cat_group in categories_data:
            category_id = cat_group.get('id')

            # Validate category ID exists and is correct type
            if category_id is None:
                logger.warning(f"Category group missing 'id' field: {cat_group}")
                continue

            if not isinstance(category_id, int):
                logger.error(f"Invalid category ID type: {category_id} (type: {type(category_id)})")
                raise ValueError(f"Invalid category ID type: must be integer, got {type(category_id)}")

            # Validate category exists in database
            if category_id not in categories_lookup:
                invalid_category_ids.append({
                    'id': category_id,
                    'valid_ids': sorted(categories_lookup.keys())[:10]  # Show first 10 for brevity
                })
                logger.error(f"Unknown category ID: {category_id} (not in database)")
                continue  # Don't raise yet, collect all errors first

            category_name = categories_lookup[category_id]
            item_indices = cat_group.get('items', [])

            for idx in item_indices:
                # Validate index type
                if not isinstance(idx, int):
                    logger.error(f"Invalid index type in category [{category_id}] '{category_name}': {idx} (type: {type(idx)})")
                    raise ValueError(f"Invalid index type: {idx} must be integer, got {type(idx)}")

                # Validate index bounds
                if idx < 0 or idx >= len(items):
                    out_of_bounds_indices.append({
                        'index': idx,
                        'category': category_name,
                        'category_id': category_id,
                        'valid_range': f"0-{len(items)-1}"
                    })
                    logger.error(f"Out-of-bounds index in category [{category_id}] '{category_name}': {idx} (valid range: 0-{len(items)-1})")
                    continue  # Don't raise yet, collect all errors first

                # Check for duplicate assignments
                if idx in item_categories:
                    duplicate_assignments.append({
                        'index': idx,
                        'first_category': item_categories[idx],
                        'first_category_id': item_category_ids[idx],
                        'duplicate_category': category_name,
                        'duplicate_category_id': category_id
                    })
                    logger.error(f"Duplicate index assignment: item {idx} assigned to both [{item_category_ids[idx]}] '{item_categories[idx]}' and [{category_id}] '{category_name}'")
                    continue  # Don't raise yet, collect all errors first

                # Valid assignment
                item_categories[idx] = category_name
                item_category_ids[idx] = category_id

    # Raise error if we found validation issues
    if invalid_category_ids or out_of_bounds_indices or duplicate_assignments:
        error_parts = []
        if invalid_category_ids:
            error_parts.append(f"{len(invalid_category_ids)} invalid category IDs")
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
        logger.info(f"Found {uncategorized_count} uncategorized items, will assign to [{default_category_id}] '{default_category_name}'")

    # Phase 2: Enrich items with category and defaults
    for idx, item in enumerate(items):
        # Add category name and ID (from mapping or default)
        item['category'] = item_categories.get(idx, default_category_name)
        item['category_id'] = item_category_ids.get(idx, default_category_id)

        # Ensure numeric fields are actually numeric (type coercion for safety)
        # This handles cases where parser might return strings
        if 'total_price' in item:
            item['total_price'] = float(item['total_price'])
        if 'quantity' in item:
            item['quantity'] = float(item['quantity'])
        if 'unit_price' in item:
            item['unit_price'] = float(item['unit_price'])

        # Default quantity to 1 if not present
        if 'quantity' not in item:
            item['quantity'] = 1

        # Calculate unit_price if not present
        if 'unit_price' not in item:
            item['unit_price'] = item['total_price'] / item['quantity']

    return items
