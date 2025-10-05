"""
Item Editor Modal - Dialog for editing receipt items.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ItemEditorModal(ModalScreen):
    """Modal dialog for editing an item."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db, user_id: int, item: dict, all_categories: list[tuple[int, str]]):
        """
        Initialize item editor modal.

        Args:
            db: Database instance
            user_id: User ID
            item: Item data dictionary (from get_receipt_items_for_console)
            all_categories: List of (category_id, category_name) tuples
        """
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.item = item
        self.all_categories = all_categories
        self.original_name = item['item_name']
        self.original_amount = float(item['total_price']) if item['total_price'] else 0.0
        self.original_category_id = item['category_id']
        # Store current category for setting after mount
        self.current_category = str(self.original_category_id) if self.original_category_id else "0"

    def on_mount(self) -> None:
        """Set the initial category value after mount."""
        category_select = self.query_one("#category_select", Select)
        category_select.value = self.current_category

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Prepare category options - start with "Uncategorized" option for NULL category_id
        # Format: (label, value) where label is displayed and value is stored
        category_options = [("Uncategorized", "0")]
        category_options.extend([(cat_name, str(cat_id)) for cat_id, cat_name in self.all_categories])

        # Format current values
        amount_str = f"{self.original_amount:.2f}"

        yield Container(
            Vertical(
                Static(f"[bold]Edit Item[/bold]", id="modal_title"),
                Static(""),
                Label("Item Name:"),
                Input(value=self.original_name, placeholder="Item name", id="name_input"),
                Static(""),
                Label("Total Amount:"),
                Input(value=amount_str, placeholder="0.00", id="amount_input"),
                Static(""),
                Label("Category:"),
                Select(
                    options=category_options,
                    allow_blank=False,
                    id="category_select"
                ),
                Static(""),
                Horizontal(
                    Button("Save", variant="primary", id="save_button"),
                    Button("Cancel", variant="default", id="cancel_button"),
                    id="button_row"
                ),
                id="editor_content"
            ),
            id="editor_dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save_button":
            self.action_save()
        elif event.button.id == "cancel_button":
            self.action_cancel()

    def action_save(self) -> None:
        """Save changes to database."""
        try:
            # Get form values
            name_input = self.query_one("#name_input", Input)
            amount_input = self.query_one("#amount_input", Input)
            category_select = self.query_one("#category_select", Select)

            new_name = name_input.value.strip()
            new_amount_str = amount_input.value.strip()
            # Convert "0" (Uncategorized) to None, otherwise parse as int
            category_value = category_select.value
            if category_value == "0":
                new_category_id = None
            else:
                new_category_id = int(category_value) if category_value else None

            # Validate name
            if not new_name:
                self.notify("Item name cannot be empty!", severity="error")
                return

            if len(new_name) > 200:
                self.notify("Item name too long (max 200 characters)!", severity="error")
                return

            # Validate amount
            try:
                new_amount = float(new_amount_str.replace(',', '.'))
                if new_amount < 0.01 or new_amount > 99999.99:
                    self.notify("Amount must be between 0.01 and 99999.99!", severity="error")
                    return
            except ValueError:
                self.notify("Invalid amount format! Please enter a number.", severity="error")
                return

            # Note: category_id can be None (uncategorized), so no validation needed

            # Check what changed
            name_changed = new_name != self.original_name
            amount_changed = abs(new_amount - self.original_amount) > 0.001
            category_changed = new_category_id != self.original_category_id

            if not (name_changed or amount_changed or category_changed):
                self.notify("No changes detected.", severity="warning")
                self.dismiss(False)  # No changes
                return

            # Update database
            item_id = self.item['item_id']
            receipt_id = self.item['receipt_id']
            changes_made = False

            # Update name if changed
            if name_changed:
                success = self.db.update_item_name(item_id, receipt_id, new_name, self.user_id)
                if not success:
                    self.notify("Failed to update item name!", severity="error")
                    return
                changes_made = True
                logger.info(f"Updated item {item_id} name: '{self.original_name}' → '{new_name}'")

            # Update amount if changed
            if amount_changed:
                success = self.db.update_item_amount(item_id, receipt_id, new_amount, self.user_id)
                if not success:
                    self.notify("Failed to update item amount!", severity="error")
                    return
                changes_made = True
                logger.info(f"Updated item {item_id} amount: {self.original_amount:.2f} → {new_amount:.2f}")

            # Update category if changed
            if category_changed:
                success = self.db.update_item_category(item_id, receipt_id, new_category_id, self.user_id)
                if not success:
                    self.notify("Failed to update item category!", severity="error")
                    return
                changes_made = True
                logger.info(f"Updated item {item_id} category: {self.original_category_id} → {new_category_id}")

            # Success!
            self.notify("Item updated successfully!", severity="information")
            self.dismiss(True)  # Return True to indicate changes were made

        except Exception as e:
            logger.error(f"Error saving item: {e}")
            self.notify(f"Error saving item: {e}", severity="error")

    def action_cancel(self) -> None:
        """Cancel editing and close modal."""
        self.dismiss(False)  # Return False to indicate no changes
