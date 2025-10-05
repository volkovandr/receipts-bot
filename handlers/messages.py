"""
Message handlers for text input during editing workflows.

Handles conversation flows for:
- Amount editing (user enters new amount)
- Category search (user enters search term)
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle amount input during item editing.

    Expected context.user_data:
    - editing_mode: 'amount'
    - editing_item_id: int
    - editing_receipt_id: int
    - editing_item_name: str (for display)
    """
    # Check if user is in editing mode
    if context.user_data.get('editing_mode') != 'amount':
        return  # Not in amount editing mode, ignore

    user_id = update.effective_user.id
    message_text = update.message.text.strip()

    # Get editing context
    item_id = context.user_data.get('editing_item_id')
    receipt_id = context.user_data.get('editing_receipt_id')
    item_index = context.user_data.get('editing_item_index', 0)
    item_name = context.user_data.get('editing_item_name', 'item')

    # Validate amount input
    try:
        new_amount = float(message_text.replace(',', '.'))  # Handle both , and . as decimal separator

        if new_amount < 0.01 or new_amount > 99999.99:
            await update.message.reply_text(
                f'❌ Invalid amount!\n\n'
                f'Amount must be between 0.01 and 99999.99.\n'
                f'Please try again:'
            )
            return
    except ValueError:
        await update.message.reply_text(
            f'❌ Invalid amount format!\n\n'
            f'Please enter a valid number (e.g., 12.50):'
        )
        return

    # Get database
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database not available")
        await update.message.reply_text('❌ Error: Database not available')
        # Clear editing state
        context.user_data.clear()
        return

    # Update item amount
    try:
        success = db.update_item_amount(item_id, receipt_id, new_amount, user_id)

        if success:
            logger.info(f"User {user_id} updated item {item_id} amount to {new_amount}")

            # Return to edit view for same item
            try:
                from handlers.callbacks import show_edit_item_view
                from telegram import CallbackQuery

                # Create a mock query object to reuse the helper
                class MockQuery:
                    async def edit_message_text(self, text, reply_markup=None):
                        await update.message.reply_text(text, reply_markup=reply_markup)

                mock_query = MockQuery()
                await show_edit_item_view(mock_query, db, receipt_id, item_index, user_id,
                                         message_prefix=f'✅ Amount updated to {new_amount:.2f}!\n\n')
            except Exception as e:
                logger.error(f"Failed to show edit view after amount update: {e}")
                await update.message.reply_text(
                    f'✅ Amount updated!\n\n'
                    f'Item: {item_name}\n'
                    f'New amount: {new_amount:.2f}'
                )
        else:
            await update.message.reply_text(
                '❌ Failed to update amount!\n\n'
                'Item not found or access denied.'
            )
            logger.warning(f"User {user_id} failed to update item {item_id} - not authorized or not found")
    except Exception as e:
        logger.error(f"Error updating item amount: {e}")
        await update.message.reply_text(
            '❌ Error updating amount!\n\n'
            'Please try again later.'
        )
    finally:
        # Clear editing state
        context.user_data.clear()


async def handle_category_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle category search input during item editing.

    Expected context.user_data:
    - editing_mode: 'category'
    - editing_item_id: int
    - editing_receipt_id: int
    - editing_item_name: str (for display)
    """
    # Check if user is in editing mode
    if context.user_data.get('editing_mode') != 'category':
        return  # Not in category editing mode, ignore

    user_id = update.effective_user.id
    search_term = update.message.text.strip()

    # Get editing context
    item_id = context.user_data.get('editing_item_id')
    receipt_id = context.user_data.get('editing_receipt_id')
    item_name = context.user_data.get('editing_item_name', 'item')

    # Validate search term
    if len(search_term) < 2:
        await update.message.reply_text(
            '❌ Search term too short!\n\n'
            'Please enter at least 2 characters:'
        )
        return

    if len(search_term) > 100:
        await update.message.reply_text(
            '❌ Search term too long!\n\n'
            'Please enter maximum 100 characters:'
        )
        return

    # Get database
    db = context.bot_data.get('database')
    if not db:
        logger.error("Database not available")
        await update.message.reply_text('❌ Error: Database not available')
        # Clear editing state
        context.user_data.clear()
        return

    # Search categories
    try:
        matches = db.search_categories_fuzzy(search_term)

        if matches:
            # Build keyboard with category options
            keyboard = []
            message_text = f'🔍 Found {len(matches)} matching categories:\n\n'

            for idx, (category_id, category_name) in enumerate(matches, 1):
                message_text += f'{idx}. {category_name}\n'
                keyboard.append([
                    InlineKeyboardButton(
                        f'✅ {category_name}',
                        callback_data=f'select_cat_{item_id}_{receipt_id}_{category_id}'
                    )
                ])

            # Add cancel button
            keyboard.append([InlineKeyboardButton('❌ Cancel', callback_data='cancel_edit')])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message_text, reply_markup=reply_markup)

            logger.info(f"User {user_id} searched for '{search_term}', found {len(matches)} categories")
        else:
            # No matches found - offer to create new category
            keyboard = [
                [InlineKeyboardButton(
                    f'✅ Create "{search_term.title()}"',
                    callback_data=f'create_cat_{item_id}_{receipt_id}_{search_term}'
                )],
                [InlineKeyboardButton('❌ Cancel', callback_data='cancel_edit')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f'🔍 No categories found for "{search_term}".\n\n'
                f'Would you like to create a new category?',
                reply_markup=reply_markup
            )

            logger.info(f"User {user_id} searched for '{search_term}', no matches found")

        # Keep editing state - will be cleared when user selects/cancels

    except Exception as e:
        logger.error(f"Error searching categories: {e}")
        await update.message.reply_text(
            '❌ Error searching categories!\n\n'
            'Please try again later.'
        )
        # Clear editing state
        context.user_data.clear()


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Route text messages to appropriate handlers based on editing mode.
    """
    editing_mode = context.user_data.get('editing_mode')

    if editing_mode == 'amount':
        await handle_amount_input(update, context)
    elif editing_mode == 'category':
        await handle_category_search_input(update, context)
    # If no editing mode, ignore the message (other handlers may process it)
