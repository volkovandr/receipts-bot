"""
TOON parser for Claude AI responses.

This module provides a custom parser for TOON (Token-Optimized Object Notation)
format, specifically designed to handle the format specification in
prompt_output_format_specification.txt.

TOON (Token-Optimized Object Notation) is a minimal syntax format that reduces
token usage compared to JSON while maintaining the same data structure when parsed.

Example TOON format for receipts:
    extraction_status: complete

    merchant:
      name: REWE
      city: Dortmund

    transaction:
      date: 2025-10-11
      total: 21.74

    items[3]{name,total_price,category_id,quantity,unit_price,notes}:
      Milk,2.99,36
      Bread,1.49,36,2,0.75
      Eggs,3.19,36,,,organic

The parse_toon() function converts TOON strings from Claude AI into Python dicts
that match the structure of our JSON format, ensuring no downstream code changes
are needed.
"""
import logging
import re
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


def parse_toon(toon_string: str) -> Dict[str, Any]:
    """
    Parse TOON format string into Python dict.

    This custom parser handles the TOON format specification including:
    - Simple fields (key: value)
    - Nested objects (2-space indentation)
    - Tabular arrays with optional fields (items[N]{fields}: csv_rows)
    - Simple arrays (array[N]: val1,val2)
    - Empty arrays (array[0]:)

    Args:
        toon_string: TOON format string from Claude AI response

    Returns:
        Parsed dict matching JSON structure used throughout the application.
        The structure will contain receipt data with keys like:
        - extraction_status (str)
        - merchant (dict with name, address, city, country)
        - transaction (dict with date, time, currency, amounts, payment info)
        - items (list of dicts with name, total_price, category_id, etc.)
        - processing_notes (dict, optional)
        - uncertain_fields (list, optional)
        - need_clarification (list, optional)

    Raises:
        ValueError: If TOON parsing fails

    Example:
        >>> toon_str = '''extraction_status: complete
        ... merchant:
        ...   name: REWE
        ...   city: Dortmund
        ... items[2]{name,total_price,category_id}:
        ...   Milk,2.99,36
        ...   Bread,1.49,36'''
        >>> result = parse_toon(toon_str)
        >>> print(result['extraction_status'])
        'complete'
        >>> print(result['merchant']['name'])
        'REWE'
        >>> print(len(result['items']))
        2
        >>> print(result['items'][0]['name'])
        'Milk'
    """
    try:
        lines = toon_string.strip().split('\n')
        result, _ = _parse_object(lines, 0, 0)

        # Validate result is dict (receipt data should be object, not array)
        if not isinstance(result, dict):
            raise ValueError(f"Expected dict at root level, got {type(result).__name__}")

        logger.debug(f"Parsed TOON into dict with {len(result)} top-level keys")
        return result

    except Exception as e:
        logger.error(f"TOON parsing failed: {e}")
        logger.error(f"TOON string (first 500 chars): {toon_string[:500]}")
        raise ValueError(f"Failed to parse TOON response: {e}") from e


def _get_indent(line: str) -> int:
    """Get indentation level (number of leading spaces)."""
    return len(line) - len(line.lstrip(' '))


def _parse_value(value: str) -> Any:
    """
    Parse a value string into appropriate Python type.

    Handles: strings, numbers (int/float), booleans (true/false), quoted strings.
    """
    value = value.strip()

    # Empty value
    if not value:
        return None

    # Quoted string - remove quotes and return as-is
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]

    # Boolean
    if value == 'true':
        return True
    if value == 'false':
        return False

    # Number (int or float)
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # Default: string
    return value


def _parse_array_header(header: str) -> Optional[Tuple[str, int, Optional[List[str]]]]:
    """
    Parse array header to extract array name, count, and optional field names.

    Formats:
        - items[3]{name,price,qty}:  -> ('items', 3, ['name', 'price', 'qty'])
        - uncertain_fields[2]:       -> ('uncertain_fields', 2, None)
        - quality_issues[0]:         -> ('quality_issues', 0, None)

    Returns:
        Tuple of (array_name, count, field_names) or None if not an array header
    """
    # Pattern: name[count]{fields}: or name[count]:
    match = re.match(r'^([a-z_]+)\[(\d+)\](?:\{([^}]+)\})?:\s*(.*)$', header)
    if not match:
        return None

    array_name = match.group(1)
    count = int(match.group(2))
    fields_str = match.group(3)
    remainder = match.group(4).strip()

    # Parse field names if present
    fields = None
    if fields_str:
        fields = [f.strip() for f in fields_str.split(',')]

    # If remainder exists on same line, it's a simple array (all values on one line)
    # Otherwise it's a tabular array (values on following lines)
    return (array_name, count, fields, remainder)


def _parse_tabular_row(row: str, fields: List[str]) -> Dict[str, Any]:
    """
    Parse a single row of a tabular array into a dict.

    Handles:
    - Quoted values containing commas
    - Missing trailing optional fields
    - Empty middle fields (consecutive commas)

    Example:
        row = 'Milk,2.99,36,,,organic'
        fields = ['name', 'total_price', 'category_id', 'quantity', 'unit_price', 'notes']
        -> {'name': 'Milk', 'total_price': 2.99, 'category_id': 36, 'notes': 'organic'}
    """
    # Split by comma, but respect quoted strings
    # IMPORTANT: Only treat quotes as delimiters if they're at the START of a value
    # This prevents apostrophes in names like "M und M's" from breaking parsing
    values = []
    current = []
    in_quotes = False
    quote_char = None
    value_start = True  # Track if we're at the start of a value

    for char in row:
        # Quote handling: only start quote mode if at beginning of value
        if char in ('"', "'"):
            if not in_quotes and value_start:
                # Starting a quoted string
                in_quotes = True
                quote_char = char
                current.append(char)
                value_start = False
            elif in_quotes and char == quote_char:
                # Ending a quoted string
                in_quotes = False
                quote_char = None
                current.append(char)
            else:
                # Quote in middle of unquoted text (like "M und M's")
                current.append(char)
                value_start = False
        elif char == ',' and not in_quotes:
            values.append(''.join(current))
            current = []
            value_start = True  # Reset for next value
        elif char == ' ' and value_start and len(current) == 0:
            # Skip leading spaces
            continue
        else:
            current.append(char)
            value_start = False

    # Add last value
    values.append(''.join(current))

    # Build dict, preserving field-to-value mapping
    # Important: We must match field indices to value indices correctly
    # Empty values (consecutive commas) should be skipped but maintain position
    result = {}
    for i, field in enumerate(fields):
        if i < len(values):
            value = values[i].strip()
            if value:  # Only include non-empty values
                result[field] = _parse_value(value)
        # If i >= len(values), field is missing entirely (trailing fields omitted)

    # Defensive validation: detect obvious field misalignment
    # If category_id is a float, it's likely that the item name contains an unquoted comma
    if 'category_id' in result and isinstance(result['category_id'], float):
        logger.warning(f"Detected float category_id ({result['category_id']}) - possible unquoted comma in item name")
        logger.warning(f"Raw row: {row}")
        logger.warning(f"Parsed values: {values}")
        # Try to provide helpful context for debugging
        if 'name' in result:
            logger.warning(f"Item name: {result['name']} (may be incomplete)")
        raise ValueError(
            f"Field misalignment detected: category_id is {result['category_id']} (float). "
            f"This usually means the item name contains an unquoted comma. "
            f"Expected format: \"Item 1,5L\",7.14,36 but got: {row}"
        )

    return result


def _parse_simple_array(values_str: str) -> List[Any]:
    """Parse simple array (comma-separated values on one line)."""
    if not values_str.strip():
        return []

    values = []
    current = []
    in_quotes = False
    quote_char = None
    value_start = True

    for char in values_str:
        # Quote handling: only start quote mode if at beginning of value
        if char in ('"', "'"):
            if not in_quotes and value_start:
                in_quotes = True
                quote_char = char
                current.append(char)
                value_start = False
            elif in_quotes and char == quote_char:
                in_quotes = False
                quote_char = None
                current.append(char)
            else:
                current.append(char)
                value_start = False
        elif char == ',' and not in_quotes:
            values.append(_parse_value(''.join(current)))
            current = []
            value_start = True
        elif char == ' ' and value_start and len(current) == 0:
            continue
        else:
            current.append(char)
            value_start = False

    # Add last value
    if current:
        values.append(_parse_value(''.join(current)))

    return values


def _parse_object(lines: List[str], start_idx: int, base_indent: int) -> Tuple[Dict[str, Any], int]:
    """
    Parse lines into a dictionary object, starting at start_idx with base indentation.

    Returns:
        Tuple of (parsed_dict, next_line_index)
    """
    result = {}
    i = start_idx

    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        indent = _get_indent(line)

        # If indentation decreased, we're done with this object
        if indent < base_indent:
            break

        # Skip lines with deeper indentation (belong to previous key)
        if indent > base_indent:
            i += 1
            continue

        # Parse key: value
        stripped = line.strip()

        # Check if this is an array header
        array_info = _parse_array_header(stripped)
        if array_info:
            array_name, count, fields, remainder = array_info

            # Empty array
            if count == 0:
                result[array_name] = []
                i += 1
                continue

            # Simple array (all values on same line)
            if remainder:
                result[array_name] = _parse_simple_array(remainder)
                i += 1
                continue

            # Tabular array - read following lines
            array_values = []
            i += 1
            while i < len(lines) and _get_indent(lines[i]) > base_indent:
                row_line = lines[i].strip()
                if row_line:
                    if fields:
                        # Tabular format with field names
                        array_values.append(_parse_tabular_row(row_line, fields))
                    else:
                        # Simple values, one per line
                        array_values.append(_parse_value(row_line))
                i += 1

            result[array_name] = array_values
            continue

        # Regular key: value
        if ':' not in stripped:
            i += 1
            continue

        key, value = stripped.split(':', 1)
        key = key.strip()
        value = value.strip()

        # If value is empty, next lines might be nested object
        if not value:
            # Check if next line has deeper indentation (nested object)
            if i + 1 < len(lines):
                next_indent = _get_indent(lines[i + 1])
                if next_indent > base_indent:
                    nested_obj, next_i = _parse_object(lines, i + 1, next_indent)
                    result[key] = nested_obj
                    i = next_i
                    continue
            # Empty value
            result[key] = None
        else:
            # Simple value
            result[key] = _parse_value(value)

        i += 1

    return result, i
