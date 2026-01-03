"""
Callback query handlers for inline keyboard buttons.
"""
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from services.receipt_formatter import format_receipt_summary

logger = logging.getLogger(__name__)


async def show_edit_item_view(query, db, receipt_id: int, item_index: int, user_id: int, message_prefix: str = "") -> None:
    """
    Helper function to show the edit view for a specific item.

    Args:
        query: Telegram callback query
        db: Database instance
        receipt_id: Receipt ID
        item_index: Index of item to show (0-based)
        user_id: User ID for authorization
        message_prefix: Optional prefix to add to message (e.g., "✅ Amount updated!\n\n")
    """
    # Get receipt items with user verification
    items = db.get_receipt_items_detailed(receipt_id, user_id)

    if not items:
        await query.edit_message_text(
            f"❌ No items found for this receipt!\n\n"
            f"Receipt ID: {receipt_id}"
        )
        return

    # Ensure item_index is within bounds
    if item_index < 0 or item_index >= len(items):
        item_index = 0

    # Get current item
    item = items[item_index]
    item_id = item['item_id']
    item_name = item['item_name']
    category_name = item['category_name']
    quantity = item['quantity']
    total_price = item['total_price']

    # Build message for single item
    message_text = message_prefix + (
        f'✏️ Editing Receipt Items\n\n'
        f'Item {item_index + 1} of {len(items)}:\n\n'
        f'📦 {item_name}\n'
        f'🏷️ Category: {category_name}\n'
    )

    if quantity is not None:
        message_text += f'📊 Quantity: {quantity}\n'

    message_text += f'💰 Price: {total_price:.2f}\n'

    # Build keyboard with action buttons
    keyboard = []

    # Action buttons for current item
    # Note: item_name is NOT included in callback_data to avoid Telegram's 64-byte limit
    keyboard.append([
        InlineKeyboardButton("❌ Delete", callback_data=f"del_item_{item_id}_{receipt_id}_{item_index}"),
        InlineKeyboardButton("💰 Edit amount", callback_data=f"edit_amt_{item_id}_{receipt_id}_{item_index}"),
    ])
    keyboard.append([
        InlineKeyboardButton("🏷️ Change category", callback_data=f"edit_cat_{item_id}_{receipt_id}_{item_index}")
    ])

    # Navigation buttons
    nav_buttons = []
    if item_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"edit_receipt_{receipt_id}_{item_index - 1}"))
    if item_index < len(items) - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"edit_receipt_{receipt_id}_{item_index + 1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Back to summary button
    keyboard.append([InlineKeyboardButton("⬅️ Back to summary", callback_data=f"back_summary_{receipt_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(message_text, reply_markup=reply_markup)
        logger.info(f"Showing item {item_index + 1}/{len(items)} for receipt {receipt_id} to user {user_id}")
    except BadRequest as edit_error:
        # Handle "message not modified" error - just acknowledge silently
        if "message is not modified" in str(edit_error).lower():
            logger.debug(f"Message not modified for receipt {receipt_id} item {item_index}")
        else:
            # Log detailed debug information for any BadRequest error
            logger.error(f"BadRequest error editing message: {edit_error}")
            logger.error(f"Receipt ID: {receipt_id}, Item index: {item_index}, User ID: {user_id}")
            logger.error(f"Message text length: {len(message_text)} characters")
            logger.error(f"Keyboard structure: {len(keyboard)} rows, {sum(len(row) for row in keyboard)} total buttons")

            # Log all callback_data for debugging
            all_callback_data = []
            for row_idx, row in enumerate(keyboard):
                for btn_idx, button in enumerate(row):
                    all_callback_data.append(button.callback_data)
                    logger.error(f"  Row {row_idx}, Button {btn_idx}: text='{button.text}', callback_data='{button.callback_data}' ({len(button.callback_data)} bytes)")

            # Check for duplicates
            if len(all_callback_data) != len(set(all_callback_data)):
                logger.error(f"WARNING: Duplicate callback_data detected!")
                logger.error(f"All callback_data: {all_callback_data}")

            logger.error(f"Message text preview (first 200 chars): {message_text[:200]}")
            raise
    except Exception as edit_error:
        logger.error(f"Unexpected error editing message: {edit_error}")
        logger.error(f"Exception type: {type(edit_error).__name__}")
        raise


async def handle_view_items_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks view items button - shows read-only list of all items."""
    query = update.callback_query
    await query.answer()

    # Extract receipt_id from callback_data
    callback_data = query.data
    if not callback_data.startswith("view_items_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        receipt_id = int(callback_data.replace("view_items_", ""))
    except ValueError:
        logger.error(f"Failed to parse receipt_id from callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid receipt ID")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Get receipt items with user verification
    try:
        items = db.get_receipt_items_detailed(receipt_id, user_id)

        if not items:
            await query.edit_message_text(
                f"❌ No items found for this receipt!\n\n"
                f"Receipt ID: {receipt_id}"
            )
            logger.warning(f"No items found for receipt {receipt_id} for user {user_id}")
            return

        # Build message with all items (read-only)
        message_text = f'📋 Receipt Items ({len(items)} total)\n\n'

        for idx, item in enumerate(items, 1):
            item_name = item['item_name']
            category_name = item['category_name']
            quantity = item['quantity']
            total_price = item['total_price']

            message_text += f'{idx}. {item_name}\n'
            message_text += f'   {category_name}'

            if quantity is not None:
                message_text += f' • Qty: {quantity}'

            message_text += f' • {total_price:.2f}\n\n'

        # Simple keyboard with just back button
        keyboard = [[InlineKeyboardButton("⬅️ Back to summary", callback_data=f"back_summary_{receipt_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message_text, reply_markup=reply_markup)
        logger.info(f"Showed {len(items)} items (read-only) for receipt {receipt_id} to user {user_id}")

    except Exception as e:
        logger.error(f"Error viewing items for receipt {receipt_id}: {e}")
        await query.edit_message_text(
            f"❌ Error loading items!\n\n"
            f"An error occurred while trying to load the items. Please try again later."
        )


async def handle_view_image_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks view processed image button."""
    query = update.callback_query
    await query.answer()

    # Extract receipt_id from callback_data
    callback_data = query.data
    if not callback_data.startswith("view_image_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        receipt_id = int(callback_data.replace("view_image_", ""))
    except ValueError:
        logger.error(f"Failed to parse receipt_id from callback_data: {callback_data}")
        await query.answer("❌ Error: Invalid receipt ID", show_alert=True)
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.answer("❌ Error: Database not available", show_alert=True)
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Get processed image path with user verification
    try:
        image_path = db.get_receipt_processed_image_path(receipt_id, user_id)

        if image_path and Path(image_path).exists():
            # Send the processed image to the user
            with open(image_path, 'rb') as photo_file:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=photo_file,
                    caption=f"🔍 Processed image for receipt ID: {receipt_id}\n"
                            f"This is the image that was sent to Claude AI for analysis."
                )
            logger.info(f"Sent processed image for receipt {receipt_id} to user {user_id}")
        elif image_path:
            await query.answer(f"❌ Image file not found", show_alert=True)
            logger.warning(f"Image file not found for receipt {receipt_id}: {image_path}")
        else:
            await query.answer("❌ Receipt not found or access denied", show_alert=True)
            logger.warning(f"Receipt {receipt_id} not found or user {user_id} not authorized")

    except Exception as e:
        logger.error(f"Error sending image for receipt {receipt_id}: {e}")
        await query.answer("❌ Error retrieving image. Please try again later.", show_alert=True)


async def handle_delete_receipt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks delete receipt button."""
    query = update.callback_query
    await query.answer()

    # Extract receipt_id from callback_data
    callback_data = query.data
    if not callback_data.startswith("delete_receipt_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        receipt_id = int(callback_data.replace("delete_receipt_", ""))
    except ValueError:
        logger.error(f"Failed to parse receipt_id from callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid receipt ID")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Mark receipt as deleted with user verification
    try:
        success = db.mark_receipt_as_deleted(receipt_id, user_id)

        if success:
            # Update message to show deletion confirmation
            await query.edit_message_text(
                f"🗑️ Receipt deleted successfully!\n\n"
                f"Receipt ID: {receipt_id}\n"
                f"The receipt data has been marked as deleted and will not be included in reports."
            )
            logger.info(f"Receipt {receipt_id} deleted by user {user_id}")
        else:
            await query.edit_message_text(
                f"❌ Receipt not found or access denied!\n\n"
                f"Receipt ID: {receipt_id}\n"
                f"You can only delete your own receipts."
            )
            logger.warning(f"User {user_id} attempted to delete receipt {receipt_id} - not found or not authorized")
    except Exception as e:
        logger.error(f"Error deleting receipt {receipt_id}: {e}")
        await query.edit_message_text(
            f"❌ Error deleting receipt!\n\n"
            f"An error occurred while trying to delete the receipt. Please try again later."
        )


async def handle_edit_receipt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks edit receipt button - shows ONE item at a time with pagination."""
    query = update.callback_query
    await query.answer()

    # Extract receipt_id and item_index from callback_data: edit_receipt_{receipt_id}_{item_index}
    callback_data = query.data
    if not callback_data.startswith("edit_receipt_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        parts = callback_data.replace("edit_receipt_", "").split("_")
        receipt_id = int(parts[0])
        item_index = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        logger.error(f"Failed to parse callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid data")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Use helper function to show item view
    try:
        await show_edit_item_view(query, db, receipt_id, item_index, user_id)
    except Exception as e:
        logger.error(f"Error getting items for receipt {receipt_id}: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
        try:
            await query.edit_message_text(
                f"❌ Error loading items!\n\n"
                f"An error occurred while trying to load the items. Please try again later."
            )
        except:
            # If we can't edit the message, send a new one
            await query.message.reply_text(
                f"❌ Error loading items!\n\n"
                f"An error occurred while trying to load the items. Please try again later."
            )


async def handle_delete_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks delete item button."""
    query = update.callback_query
    await query.answer()

    # Extract item_id, receipt_id, and item_index from callback_data: del_item_{item_id}_{receipt_id}_{item_index}
    callback_data = query.data
    if not callback_data.startswith("del_item_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        parts = callback_data.replace("del_item_", "").split("_")
        item_id = int(parts[0])
        receipt_id = int(parts[1])
        item_index = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        logger.error(f"Failed to parse callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid data")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Delete item with user verification
    try:
        success = db.mark_item_as_deleted(item_id, receipt_id, user_id)

        if success:
            logger.info(f"Item {item_id} deleted by user {user_id}")

            # Return to edit view at the same position (or previous if this was the last item)
            try:
                await show_edit_item_view(query, db, receipt_id, item_index, user_id, message_prefix="✅ Item deleted!\n\n")
            except Exception as e:
                # If no items left or error, show summary
                logger.error(f"Failed to show edit view after deletion: {e}")
                summary_text, reply_markup = format_receipt_summary(db, receipt_id, user_id)
                await query.edit_message_text(
                    f'✅ Item deleted!\n\n{summary_text}',
                    reply_markup=reply_markup
                )
        else:
            await query.edit_message_text(
                f"❌ Failed to delete item!\n\n"
                f"Item not found or access denied."
            )
            logger.warning(f"User {user_id} failed to delete item {item_id} - not authorized or not found")

    except Exception as e:
        logger.error(f"Error deleting item {item_id}: {e}")
        await query.edit_message_text(
            f"❌ Error deleting item!\n\n"
            f"An error occurred while trying to delete the item. Please try again later."
        )


async def handle_edit_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks edit amount button."""
    query = update.callback_query
    await query.answer()

    # Extract item_id, receipt_id, and item_index from callback_data: edit_amt_{item_id}_{receipt_id}_{item_index}
    callback_data = query.data
    if not callback_data.startswith("edit_amt_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        parts = callback_data.replace("edit_amt_", "").split("_")
        item_id = int(parts[0])
        receipt_id = int(parts[1])
        item_index = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        logger.error(f"Failed to parse callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid data")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Fetch item details to get the name
    try:
        items = db.get_receipt_items_detailed(receipt_id, user_id)
        item = next((i for i in items if i['item_id'] == item_id), None)

        if not item:
            await query.edit_message_text("❌ Item not found or access denied")
            logger.warning(f"User {user_id} attempted to edit item {item_id} - not found or not authorized")
            return

        item_name = item['item_name']
    except Exception as e:
        logger.error(f"Error fetching item details: {e}")
        await query.edit_message_text("❌ Error loading item details")
        return

    # Set editing mode in user context
    context.user_data['editing_mode'] = 'amount'
    context.user_data['editing_item_id'] = item_id
    context.user_data['editing_receipt_id'] = receipt_id
    context.user_data['editing_item_index'] = item_index
    context.user_data['editing_item_name'] = item_name

    # Ask user for new amount
    await query.edit_message_text(
        f'💰 Edit amount for: {item_name}\n\n'
        f'Please enter the new amount (e.g., 12.50):'
    )

    logger.info(f"User {query.from_user.id} started editing amount for item {item_id}")


async def handle_edit_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks edit category button."""
    query = update.callback_query
    await query.answer()

    # Extract item_id, receipt_id, and item_index from callback_data: edit_cat_{item_id}_{receipt_id}_{item_index}
    callback_data = query.data
    if not callback_data.startswith("edit_cat_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        parts = callback_data.replace("edit_cat_", "").split("_")
        item_id = int(parts[0])
        receipt_id = int(parts[1])
        item_index = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        logger.error(f"Failed to parse callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid data")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Fetch item details to get the name
    try:
        items = db.get_receipt_items_detailed(receipt_id, user_id)
        item = next((i for i in items if i['item_id'] == item_id), None)

        if not item:
            await query.edit_message_text("❌ Item not found or access denied")
            logger.warning(f"User {user_id} attempted to edit item {item_id} - not found or not authorized")
            return

        item_name = item['item_name']
    except Exception as e:
        logger.error(f"Error fetching item details: {e}")
        await query.edit_message_text("❌ Error loading item details")
        return

    # Set editing mode in user context
    context.user_data['editing_mode'] = 'category'
    context.user_data['editing_item_id'] = item_id
    context.user_data['editing_receipt_id'] = receipt_id
    context.user_data['editing_item_index'] = item_index
    context.user_data['editing_item_name'] = item_name

    # Ask user for category search term
    await query.edit_message_text(
        f'🏷️ Change category for: {item_name}\n\n'
        f'Please enter category name or keywords to search:'
    )

    logger.info(f"User {query.from_user.id} started editing category for item {item_id}")


async def handle_category_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user selects a category from search results."""
    query = update.callback_query
    await query.answer()

    # Extract item_id, receipt_id, and category_id from callback_data: select_cat_{item_id}_{receipt_id}_{category_id}
    callback_data = query.data
    if not callback_data.startswith("select_cat_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        parts = callback_data.replace("select_cat_", "").split("_")
        item_id = int(parts[0])
        receipt_id = int(parts[1])
        category_id = int(parts[2])
    except (ValueError, IndexError):
        logger.error(f"Failed to parse callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid data")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Get item_index from context (set when "Change category" was clicked)
    item_index = context.user_data.get('editing_item_index', 0)

    # Update item category with user verification
    try:
        success = db.update_item_category(item_id, receipt_id, category_id, user_id)

        if success:
            logger.info(f"User {user_id} updated item {item_id} category to {category_id}")

            # Return to edit view for same item
            try:
                await show_edit_item_view(query, db, receipt_id, item_index, user_id,
                                         message_prefix="✅ Category updated!\n\n")
            except Exception as e:
                logger.error(f"Failed to show edit view after category update: {e}")
                await query.edit_message_text(
                    f'✅ Category updated!\n\nReceipt ID: {receipt_id}'
                )
        else:
            await query.edit_message_text(
                f"❌ Failed to update category!\n\n"
                f"Item not found or access denied."
            )
            logger.warning(f"User {user_id} failed to update item {item_id} category - not authorized or not found")

    except Exception as e:
        logger.error(f"Error updating item category: {e}")
        await query.edit_message_text(
            f"❌ Error updating category!\n\n"
            f"An error occurred while trying to update the category. Please try again later."
        )
    finally:
        # Clear editing state
        context.user_data.clear()


async def handle_category_create_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user wants to create a new category."""
    query = update.callback_query
    await query.answer()

    # Extract item_id, receipt_id, and category_name from callback_data: create_cat_{item_id}_{receipt_id}_{category_name}
    callback_data = query.data
    if not callback_data.startswith("create_cat_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        parts = callback_data.replace("create_cat_", "").split("_", 2)
        item_id = int(parts[0])
        receipt_id = int(parts[1])
        category_name = parts[2] if len(parts) > 2 else "New Category"
    except (ValueError, IndexError):
        logger.error(f"Failed to parse callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid data")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID for authorization check
    user_id = query.from_user.id

    # Get item_index from context (set when "Change category" was clicked)
    item_index = context.user_data.get('editing_item_index', 0)

    # Create new category and assign it to item
    try:
        # Create category
        category_id = db.create_category(category_name)
        logger.info(f"User {user_id} created new category: {category_name} (ID: {category_id})")

        # Assign to item
        success = db.update_item_category(item_id, receipt_id, category_id, user_id)

        if success:
            logger.info(f"User {user_id} assigned new category {category_id} to item {item_id}")

            # Return to edit view for same item
            try:
                await show_edit_item_view(query, db, receipt_id, item_index, user_id,
                                         message_prefix=f'✅ New category created!\nCategory: {category_name.title()}\n\n')
            except Exception as e:
                logger.error(f"Failed to show edit view after category creation: {e}")
                await query.edit_message_text(
                    f'✅ New category created and assigned!\n\n'
                    f'Category: {category_name.title()}\n'
                    f'Receipt ID: {receipt_id}'
                )
        else:
            await query.edit_message_text(
                f"❌ Category created but failed to assign!\n\n"
                f"Category: {category_name.title()}\n"
                f"Item not found or access denied."
            )
            logger.warning(f"User {user_id} created category but failed to assign to item {item_id}")

    except Exception as e:
        logger.error(f"Error creating category: {e}")
        await query.edit_message_text(
            f"❌ Error creating category!\n\n"
            f"An error occurred. The category may already exist or there was a database error."
        )
    finally:
        # Clear editing state
        context.user_data.clear()


async def handle_back_to_summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user clicks back to summary button."""
    query = update.callback_query
    await query.answer()

    # Extract receipt_id from callback_data: back_summary_{receipt_id}
    callback_data = query.data
    if not callback_data.startswith("back_summary_"):
        logger.warning(f"Invalid callback data: {callback_data}")
        return

    try:
        receipt_id = int(callback_data.replace("back_summary_", ""))
    except ValueError:
        logger.error(f"Failed to parse receipt_id from callback_data: {callback_data}")
        await query.edit_message_text("❌ Error: Invalid receipt ID")
        return

    # Get database from context
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text("❌ Error: Database not available")
        return

    # Get user ID
    user_id = query.from_user.id

    # Show receipt summary
    try:
        summary_text, reply_markup = format_receipt_summary(db, receipt_id, user_id)
        await query.edit_message_text(summary_text, reply_markup=reply_markup)
        logger.info(f"User {user_id} navigated back to summary for receipt {receipt_id}")
    except ValueError as e:
        logger.error(f"Failed to format summary: {e}")
        await query.edit_message_text(
            f"❌ Receipt not found or access denied!\n\n"
            f"Receipt ID: {receipt_id}"
        )


async def handle_cancel_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user cancels editing."""
    query = update.callback_query
    await query.answer()

    # Clear editing state
    context.user_data.clear()

    await query.edit_message_text(
        "❌ Editing cancelled.\n\n"
        "Use /start to see available commands."
    )

    logger.info(f"User {query.from_user.id} cancelled editing")


async def handle_deskew_proceed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user chooses to deskew and process the image."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    receipt_id = int(query.data.split('_')[-1])

    logger.info(f"User {user_id} chose to deskew receipt {receipt_id}")

    # Get database connection
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text('❌ Database not available.')
        return

    # Verify receipt ownership
    if not db.verify_receipt_owner(receipt_id, user_id):
        await query.edit_message_text('❌ Receipt not found or access denied.')
        logger.warning(f"Unauthorized access attempt: user {user_id} tried to deskew receipt {receipt_id}")
        return

    # Get pending skew analysis data
    skew_data = context.user_data.get('pending_skew_analysis')
    if not skew_data or skew_data['receipt_id'] != receipt_id:
        await query.edit_message_text('❌ Skew analysis data not found. Please try uploading the image again.')
        logger.error(f"Skew data not found for receipt {receipt_id}")
        return

    processed_image_path = skew_data['processed_image_path']
    is_pdf_source = skew_data['is_pdf_source']
    skew_analysis = skew_data['skew_analysis']
    image_id = skew_data['image_id']
    angle = skew_analysis['max_skew_angle']

    # Update user: deskewing in progress
    await query.edit_message_text('🔄 Deskewing image...')

    # Import deskewing service
    from services import deskew_service

    # Determine output path based on source type
    if is_pdf_source:
        # PDF source: create new processed image
        processed_path_obj = Path(processed_image_path)
        filename_parts = processed_path_obj.stem.split('_', 1)
        if len(filename_parts) > 1:
            new_filename = f"{receipt_id}_{filename_parts[1]}.jpg"
        else:
            new_filename = f"{receipt_id}_{processed_path_obj.stem}.jpg"
        output_path = str(processed_path_obj.parent / new_filename)
    else:
        # Photo source: replace existing processed image
        output_path = processed_image_path

    # Apply deskewing
    success, result = deskew_service.deskew_image_by_angle(processed_image_path, angle, output_path)

    if not success:
        error_msg = result.get('error', 'Unknown error')
        await query.edit_message_text(f'❌ Deskewing failed: {error_msg}\n\nPlease try again or choose "Process As-Is".')
        logger.error(f"Deskewing failed for receipt {receipt_id}: {error_msg}")
        return

    # Update database if PDF source (new file created)
    if is_pdf_source and output_path != processed_image_path:
        import os
        processed_size = os.path.getsize(output_path)
        db.update_image_processed(image_id, output_path, processed_size)
        logger.info(f"Updated image {image_id} with deskewed path: {output_path}")

    # Update user: deskewing complete
    await query.edit_message_text(
        '✅ Image deskewed. Processing...'
    )

    # Continue with Claude analysis
    from services.receipt_analyzer import analyze_receipt_with_claude

    # Use the status message for updates
    status_message = query.message

    await analyze_receipt_with_claude(
        context, db, receipt_id, image_id, output_path, status_message
    )

    # Clean up temporary data
    context.user_data.pop('pending_skew_analysis', None)


async def handle_proceed_skewed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user chooses to process the image as-is (with skew)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    receipt_id = int(query.data.split('_')[-1])

    logger.info(f"User {user_id} chose to proceed with skewed receipt {receipt_id}")

    # Get database connection
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text('❌ Database not available.')
        return

    # Verify receipt ownership
    if not db.verify_receipt_owner(receipt_id, user_id):
        await query.edit_message_text('❌ Receipt not found or access denied.')
        logger.warning(f"Unauthorized access attempt: user {user_id} tried to process receipt {receipt_id}")
        return

    # Get pending skew analysis data
    skew_data = context.user_data.get('pending_skew_analysis')
    if not skew_data or skew_data['receipt_id'] != receipt_id:
        await query.edit_message_text('❌ Analysis data not found. Please try uploading the image again.')
        logger.error(f"Skew data not found for receipt {receipt_id}")
        return

    processed_image_path = skew_data['processed_image_path']
    image_id = skew_data['image_id']

    # Update user: processing
    await query.edit_message_text('🤖 Analyzing with AI...')

    # Continue with Claude analysis (using existing processed image)
    from services.receipt_analyzer import analyze_receipt_with_claude

    # Use the status message for updates
    status_message = query.message

    await analyze_receipt_with_claude(
        context, db, receipt_id, image_id, processed_image_path, status_message
    )

    # Clean up temporary data
    context.user_data.pop('pending_skew_analysis', None)


async def handle_skew_discard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback when user chooses to discard the receipt and rescan (from skew warning)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    receipt_id = int(query.data.split('_')[-1])

    logger.info(f"User {user_id} chose to discard receipt {receipt_id}")

    # Get database connection
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database connection not available")
        await query.edit_message_text('❌ Database not available.')
        return

    # Verify receipt ownership and delete
    success = db.mark_receipt_as_deleted(receipt_id, user_id)

    if success:
        await query.edit_message_text(
            '✅ Receipt discarded. Please rescan and send a new image.'
        )
        logger.info(f"Receipt {receipt_id} soft-deleted by user {user_id}")
    else:
        await query.edit_message_text('❌ Receipt not found or access denied.')
        logger.warning(f"Unauthorized delete attempt: user {user_id} tried to delete receipt {receipt_id}")

    # Clean up temporary data
    context.user_data.pop('pending_skew_analysis', None)
