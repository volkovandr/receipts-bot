"""
Item Creator Modal - Dialog for adding new receipt items.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ItemCreatorModal(ModalScreen):
    """Modal dialog for creating a new item."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db, user_id: int, receipt_id: int, all_categories: list[tuple[int, str]]):
        """
        Initialize item creator modal.

        Args:
            db: Database instance
            user_id: User ID
            receipt_id: Receipt ID to add item to
            all_categories: List of (category_id, category_name) tuples
        """
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.receipt_id = receipt_id
        self.all_categories = all_categories

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Prepare category options - start with "Uncategorized" option for NULL category_id
        # Format: (label, value) where label is displayed and value is stored
        category_options = [("Uncategorized", "0")]
        category_options.extend([(cat_name, str(cat_id)) for cat_id, cat_name in self.all_categories])

        yield Container(
            Vertical(
                Static(f"[bold]Add New Item[/bold]", id="modal_title"),
                Static(""),
                Label("Item Name:"),
                Input(value="", placeholder="Item name", id="name_input"),
                Static(""),
                Label("Quantity:"),
                Input(value="1.00", placeholder="1.00", id="quantity_input"),
                Static(""),
                Label("Unit Price:"),
                Input(value="0.00", placeholder="0.00", id="unit_price_input"),
                Static(""),
                Label("Total Amount (calculated):"),
                Static("0.00", id="total_display"),
                Static(""),
                Label("Category:"),
                Select(
                    options=category_options,
                    allow_blank=False,
                    id="category_select",
                    value="0"  # Default to Uncategorized
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

    def on_mount(self) -> None:
        """Set up input handlers after mount."""
        # Add watchers for quantity and unit price to update total
        quantity_input = self.query_one("#quantity_input", Input)
        unit_price_input = self.query_one("#unit_price_input", Input)

        quantity_input.watch(self, 'value', self.update_total)
        unit_price_input.watch(self, 'value', self.update_total)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes to update total display."""
        if event.input.id in ("quantity_input", "unit_price_input"):
            self.update_total()

    def update_total(self) -> None:
        """Update the total display based on quantity and unit price."""
        try:
            quantity_input = self.query_one("#quantity_input", Input)
            unit_price_input = self.query_one("#unit_price_input", Input)
            total_display = self.query_one("#total_display", Static)

            qty_str = quantity_input.value.strip().replace(',', '.')
            price_str = unit_price_input.value.strip().replace(',', '.')

            if qty_str and price_str:
                qty = float(qty_str)
                price = float(price_str)
                total = qty * price
                total_display.update(f"{total:.2f}")
            else:
                total_display.update("0.00")
        except (ValueError, AttributeError):
            # If parsing fails, show 0.00
            try:
                total_display = self.query_one("#total_display", Static)
                total_display.update("0.00")
            except:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save_button":
            self.action_save()
        elif event.button.id == "cancel_button":
            self.action_cancel()

    def action_save(self) -> None:
        """Save new item to database."""
        try:
            # Get form values
            name_input = self.query_one("#name_input", Input)
            quantity_input = self.query_one("#quantity_input", Input)
            unit_price_input = self.query_one("#unit_price_input", Input)
            category_select = self.query_one("#category_select", Select)

            name = name_input.value.strip()
            quantity_str = quantity_input.value.strip()
            unit_price_str = unit_price_input.value.strip()

            # Convert "0" (Uncategorized) to None, otherwise parse as int
            category_value = category_select.value
            if category_value == "0":
                category_id = None
            else:
                category_id = int(category_value) if category_value else None

            # Validate name
            if not name:
                self.notify("Item name cannot be empty!", severity="error")
                return

            if len(name) > 200:
                self.notify("Item name too long (max 200 characters)!", severity="error")
                return

            # Validate quantity
            try:
                quantity = float(quantity_str.replace(',', '.'))
                if quantity == 0:
                    self.notify("Quantity cannot be zero!", severity="error")
                    return
                if quantity < -99999.99 or quantity > 99999.99:
                    self.notify("Quantity must be between -99999.99 and 99999.99 (excluding 0)!", severity="error")
                    return
            except ValueError:
                self.notify("Invalid quantity format! Please enter a number.", severity="error")
                return

            # Validate unit price
            try:
                unit_price = float(unit_price_str.replace(',', '.'))
                if abs(unit_price) > 99999.99:
                    self.notify("Unit price must be between -99999.99 and 99999.99!", severity="error")
                    return
            except ValueError:
                self.notify("Invalid unit price format! Please enter a number.", severity="error")
                return

            # Calculate total
            total_price = quantity * unit_price
            if total_price == 0:
                self.notify("Total price cannot be zero!", severity="error")
                return
            if abs(total_price) > 99999.99:
                self.notify("Total price must be between -99999.99 and 99999.99 (excluding 0)!", severity="error")
                return

            # Create item in database
            item_id = self.db.create_item(
                receipt_id=self.receipt_id,
                user_id=self.user_id,
                item_name=name,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                category_id=category_id
            )

            if item_id:
                logger.info(f"Created item {item_id} for receipt {self.receipt_id}: '{name}' x {quantity} @ {unit_price} = {total_price}")
                self.notify("Item created successfully!", severity="information")
                self.dismiss(True)  # Return True to indicate item was created
            else:
                self.notify("Failed to create item!", severity="error")
                self.dismiss(False)

        except Exception as e:
            logger.error(f"Error creating item: {e}")
            self.notify(f"Error creating item: {e}", severity="error")

    def action_cancel(self) -> None:
        """Cancel creation and close modal."""
        self.dismiss(False)  # Return False to indicate no item was created
