"""
Receipt summary formatting service.

Generates formatted receipt summaries with inline keyboard buttons.
Used after analysis, edits, and deletions for consistent messaging.
"""
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def format_receipt_summary(db, receipt_id: int, user_id: int = None) -> tuple[str, InlineKeyboardMarkup]:
    """
    Generate formatted receipt summary with inline keyboard.

    Args:
        db: Database instance
        receipt_id: Receipt ID
        user_id: Optional user ID for authorization (recommended)

    Returns:
        Tuple of (message_text, reply_markup)

    Raises:
        ValueError: If receipt not found or user not authorized
    """
    # Get receipt data from database
    receipt_data = db.get_receipt_summary_data(receipt_id, user_id)

    if not receipt_data:
        raise ValueError(f"Receipt {receipt_id} not found or access denied")

    merchant_name = receipt_data.get('merchant_name', 'Unknown')
    transaction_date = receipt_data.get('transaction_date', 'N/A')
    currency = receipt_data.get('currency', 'EUR')
    brutto_amount = receipt_data.get('brutto_amount')

    # Get category breakdown (excludes deleted items)
    category_breakdown = db.get_receipt_items_by_category(receipt_id)
    total_items = sum(count for _, count, _ in category_breakdown)

    # Calculate sum of non-deleted items
    items_sum = db.get_receipt_items_sum(receipt_id)

    # Check total consistency
    is_consistent = True
    if brutto_amount is not None and abs(float(brutto_amount) - items_sum) > 0.01:
        is_consistent = False

    # Build message
    message_text = (
        '✅ Receipt Summary\n\n'
        f'🏪 Merchant: {merchant_name}\n'
        f'📅 Date: {transaction_date}\n'
        f'📝 Items: {total_items}\n'
    )

    # Add category breakdown
    if category_breakdown:
        message_text += '\n💶 Breakdown by category:\n'
        for category_name, item_count, total_amount in category_breakdown:
            message_text += f'  • {category_name}: {total_amount:.2f} {currency} ({item_count} item{"s" if item_count > 1 else ""})\n'

    # Add grand total
    message_text += f'\n💰 Grand Total: {brutto_amount if brutto_amount is not None else "N/A"} {currency}\n'

    # Add consistency warning if totals don't match
    if not is_consistent and brutto_amount is not None:
        difference = abs(float(brutto_amount) - items_sum)
        message_text += (
            f'\n⚠️ Total mismatch!\n'
            f'   Receipt total: {brutto_amount:.2f}\n'
            f'   Items sum: {items_sum:.2f}\n'
            f'   Difference: {difference:.2f}\n'
        )

    # Check if receipt has uncertain fields or needs clarification
    uncertain_fields = receipt_data.get('uncertain_fields', [])
    need_clarification = receipt_data.get('need_clarification', [])

    if uncertain_fields:
        message_text += f'\n⚠️ Uncertain fields: {", ".join(uncertain_fields)}'

    if need_clarification:
        message_text += '\n\n❓ Needs clarification:\n'
        for item in need_clarification:
            message_text += f'  • {item.get("name")}: {item.get("reason")}\n'

    # Add edit indicator if items have been modified
    if receipt_data.get('has_edits'):
        message_text += '\n✏️ (edited)'

    # Build inline keyboard
    keyboard = [
        [InlineKeyboardButton("📋 View items", callback_data=f"view_items_{receipt_id}")],
        [InlineKeyboardButton("🔍 View processed image", callback_data=f"view_image_{receipt_id}")],
        [InlineKeyboardButton("✏️ Edit receipt", callback_data=f"edit_receipt_{receipt_id}_0")],  # Start at item 0
        [InlineKeyboardButton("🗑️ Delete this receipt", callback_data=f"delete_receipt_{receipt_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    logger.debug(f"Formatted summary for receipt {receipt_id}: {total_items} items, consistent={is_consistent}")

    return message_text, reply_markup
