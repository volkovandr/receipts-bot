"""
Receipt Detail Screen - Shows receipt header and all items.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static
from textual.containers import Container, VerticalScroll
from textual.binding import Binding
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ReceiptDetailScreen(Screen):
    """Screen showing receipt details and items."""

    BINDINGS = [
        Binding("a", "add_item", "Add Item", show=True),
        Binding("e", "edit_item", "Edit Item", show=True),
        Binding("d", "delete_item", "Delete Item", show=True),
        Binding("u", "undelete_item", "Undelete Item", show=True),
        Binding("escape", "back", "Back to List", show=True),
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(self, db, user_id: int, receipt_id: int, receipt_data: dict):
        """
        Initialize receipt detail screen.

        Args:
            db: Database instance
            user_id: User ID
            receipt_id: Receipt ID to display
            receipt_data: Receipt row data from list (for header)
        """
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.receipt_id = receipt_id
        self.receipt_data = receipt_data
        self.items = []

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static(id="receipt_header"),
            DataTable(id="items_table"),
            id="detail_container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Set up the screen when mounted."""
        # Display receipt header
        self.show_receipt_header()

        # Set up items table
        table = self.query_one("#items_table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        table.add_column("ID", key="id", width=6)
        table.add_column("Name", key="name", width=40)
        table.add_column("Category", key="category", width=25)
        table.add_column("Qty", key="quantity", width=8)
        table.add_column("Unit Price", key="unit_price", width=12)
        table.add_column("Total", key="total", width=12)
        table.add_column("Deleted", key="deleted", width=10)

        # Load items
        self.load_items()

    def show_receipt_header(self) -> None:
        """Display receipt header information with current totals calculated from items."""
        header = self.query_one("#receipt_header", Static)

        # Format header text
        date_str = self.receipt_data.get('transaction_date', 'N/A')
        time_str = self.receipt_data.get('transaction_time', '')
        merchant = self.receipt_data.get('merchant_name', 'Unknown')
        city = self.receipt_data.get('merchant_city', '')
        currency = self.receipt_data.get('currency', 'EUR')
        total_receipt = self.receipt_data.get('total_receipt', 0)  # Original receipt total
        status = self.receipt_data.get('processing_status', 'unknown')

        # Calculate current total from non-deleted items
        current_total_items = Decimal('0.00')
        for item in self.items:
            if not item.get('is_deleted', False):
                total_price = item.get('total_price', 0)
                if total_price:
                    current_total_items += Decimal(str(total_price))

        # Format amounts
        total_items_str = f"{float(current_total_items):.2f}"

        if isinstance(total_receipt, Decimal):
            total_receipt_str = f"{float(total_receipt):.2f}"
        else:
            total_receipt_str = f"{total_receipt:.2f}" if total_receipt else "0.00"

        # Check for discrepancy (tolerance: 0.01)
        has_discrepancy = abs(current_total_items - Decimal(str(total_receipt))) > Decimal('0.01')

        discrepancy_warning = ""
        if has_discrepancy:
            discrepancy_warning = " ⚠️  DISCREPANCY DETECTED"

        header_text = f"""
[bold]Receipt #{self.receipt_id}[/bold]
Merchant: {merchant} ({city})
Date: {date_str} {time_str}
Status: {status}
Total (Items): {currency} {total_items_str}
Total (Receipt): {currency} {total_receipt_str}{discrepancy_warning}
        """

        header.update(header_text.strip())

    def load_items(self, preserve_cursor: bool = False) -> None:
        """Load items from database and populate table.

        Args:
            preserve_cursor: If True, restore cursor to the same row index after reload
        """
        table = self.query_one("#items_table", DataTable)

        # Save cursor position if requested
        saved_cursor_row = table.cursor_row if preserve_cursor else None

        table.clear()

        try:
            self.items = self.db.get_receipt_items_for_console(self.receipt_id, self.user_id)

            for item in self.items:
                item_id = str(item['item_id'])
                name = item['item_name']
                category = item['category_name']

                # Format numeric values
                quantity = item['quantity']
                if isinstance(quantity, Decimal):
                    qty_str = f"{float(quantity):.2f}"
                else:
                    qty_str = f"{quantity:.2f}" if quantity is not None else "N/A"

                unit_price = item['unit_price']
                if isinstance(unit_price, Decimal):
                    unit_price_str = f"{float(unit_price):.2f}"
                else:
                    unit_price_str = f"{unit_price:.2f}" if unit_price is not None else "N/A"

                total_price = item['total_price']
                if isinstance(total_price, Decimal):
                    total_str = f"{float(total_price):.2f}"
                else:
                    total_str = f"{total_price:.2f}" if total_price else "0.00"

                is_deleted = item['is_deleted']
                deleted_str = "YES" if is_deleted else ""

                # Apply strikethrough styling to deleted items
                if is_deleted:
                    item_id = f"[strike dim]{item_id}[/strike dim]"
                    name = f"[strike dim]{name}[/strike dim]"
                    category = f"[strike dim]{category}[/strike dim]"
                    qty_str = f"[strike dim]{qty_str}[/strike dim]"
                    unit_price_str = f"[strike dim]{unit_price_str}[/strike dim]"
                    total_str = f"[strike dim]{total_str}[/strike dim]"
                    deleted_str = "[red]DELETED[/red]"

                # Add row
                table.add_row(
                    item_id,
                    name,
                    category,
                    qty_str,
                    unit_price_str,
                    total_str,
                    deleted_str,
                    key=str(item['item_id'])
                )

            # Restore cursor position if requested
            if saved_cursor_row is not None and len(table.rows) > 0:
                # Make sure cursor position is within bounds
                cursor_row = min(saved_cursor_row, len(table.rows) - 1)
                table.move_cursor(row=cursor_row)

            # Update header with new totals
            self.show_receipt_header()

        except Exception as e:
            # Show error in table
            table.add_row(
                "ERROR",
                str(e),
                "", "", "", "", "",
                key="error"
            )

    def action_add_item(self) -> None:
        """Open modal to add a new item to the receipt."""
        try:
            # Get all categories for the dropdown
            all_categories = self.db.get_all_categories_with_ids()

            # Import the modal (lazy import to avoid circular dependencies)
            from console_ui.widgets.item_creator import ItemCreatorModal

            # Run the modal opening in a worker
            self.run_worker(self._open_add_modal(all_categories))

        except Exception as e:
            logger.error(f"Error preparing add item modal: {e}")
            self.notify(f"Error: {e}", severity="error")

    async def _open_add_modal(self, all_categories: list) -> None:
        """Worker method to open the add item modal and handle the result."""
        try:
            from console_ui.widgets.item_creator import ItemCreatorModal

            # Show the modal and wait for result
            result = await self.app.push_screen_wait(ItemCreatorModal(self.db, self.user_id, self.receipt_id, all_categories))

            # If item was created, refresh the items list
            if result:
                logger.info(f"New item created for receipt {self.receipt_id}, refreshing list")
                self.load_items(preserve_cursor=False)
                # Don't show notification here - the modal already shows it

        except Exception as e:
            logger.error(f"Error in add item modal: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_edit_item(self) -> None:
        """Open edit modal for the selected item."""
        table = self.query_one("#items_table", DataTable)

        # Get selected row
        if table.cursor_row is None or table.cursor_row >= len(table.rows):
            self.notify("No item selected!", severity="warning")
            return

        # Get the row key (which is the item_id)
        row_key = table.ordered_rows[table.cursor_row].key
        if row_key == "error":
            self.notify("Cannot edit error row!", severity="error")
            return

        item_id = int(row_key.value)

        # Find the item in our items list
        selected_item = None
        for item in self.items:
            if item['item_id'] == item_id:
                selected_item = item
                break

        if not selected_item:
            self.notify("Item not found!", severity="error")
            return

        # Check if item is deleted
        if selected_item.get('is_deleted', False):
            self.notify("Cannot edit deleted items!", severity="warning")
            return

        # Get all categories for the dropdown
        try:
            all_categories = self.db.get_all_categories_with_ids()

            # Import the modal (lazy import to avoid circular dependencies)
            from console_ui.widgets.item_editor import ItemEditorModal

            # Run the modal opening in a worker
            self.run_worker(self._open_edit_modal(selected_item, all_categories, item_id))

        except Exception as e:
            logger.error(f"Error preparing edit modal: {e}")
            self.notify(f"Error: {e}", severity="error")

    async def _open_edit_modal(self, selected_item: dict, all_categories: list, item_id: int) -> None:
        """Worker method to open the edit modal and handle the result."""
        try:
            from console_ui.widgets.item_editor import ItemEditorModal

            # Show the modal and wait for result
            result = await self.app.push_screen_wait(ItemEditorModal(self.db, self.user_id, selected_item, all_categories))

            # If changes were made, refresh the items list
            if result:
                logger.info(f"Item {item_id} was edited, refreshing list")
                self.load_items(preserve_cursor=True)
                self.notify("Item updated successfully!", severity="information")

        except Exception as e:
            logger.error(f"Error in edit modal: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_delete_item(self) -> None:
        """Delete (soft delete) the selected item."""
        table = self.query_one("#items_table", DataTable)

        # Get selected row
        if table.cursor_row is None or table.cursor_row >= len(table.rows):
            self.notify("No item selected!", severity="warning")
            return

        # Get the row key (which is the item_id)
        row_key = table.ordered_rows[table.cursor_row].key
        if row_key == "error":
            self.notify("Cannot delete error row!", severity="error")
            return

        item_id = int(row_key.value)

        # Find the item in our items list
        selected_item = None
        for item in self.items:
            if item['item_id'] == item_id:
                selected_item = item
                break

        if not selected_item:
            self.notify("Item not found!", severity="error")
            return

        # Check if already deleted
        if selected_item.get('is_deleted', False):
            self.notify("Item is already deleted!", severity="warning")
            return

        # Delete the item (no confirmation needed - we have undelete!)
        try:
            success = self.db.mark_item_as_deleted(item_id, self.receipt_id, self.user_id)
            if success:
                logger.info(f"Item {item_id} deleted by user {self.user_id}")
                self.load_items(preserve_cursor=True)
                self.notify(f"Item '{selected_item['item_name']}' deleted", severity="information")
            else:
                self.notify("Failed to delete item!", severity="error")
        except Exception as e:
            logger.error(f"Error deleting item: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_undelete_item(self) -> None:
        """Restore (undelete) the selected item."""
        table = self.query_one("#items_table", DataTable)

        # Get selected row
        if table.cursor_row is None or table.cursor_row >= len(table.rows):
            self.notify("No item selected!", severity="warning")
            return

        # Get the row key (which is the item_id)
        row_key = table.ordered_rows[table.cursor_row].key
        if row_key == "error":
            self.notify("Cannot undelete error row!", severity="error")
            return

        item_id = int(row_key.value)

        # Find the item in our items list
        selected_item = None
        for item in self.items:
            if item['item_id'] == item_id:
                selected_item = item
                break

        if not selected_item:
            self.notify("Item not found!", severity="error")
            return

        # Check if not deleted
        if not selected_item.get('is_deleted', False):
            self.notify("Item is not deleted!", severity="warning")
            return

        # Undelete the item
        try:
            success = self.db.undelete_item(item_id, self.receipt_id, self.user_id)
            if success:
                logger.info(f"Item {item_id} restored by user {self.user_id}")
                self.load_items(preserve_cursor=True)
                self.notify(f"Item '{selected_item['item_name']}' restored", severity="information")
            else:
                self.notify("Failed to restore item!", severity="error")
        except Exception as e:
            logger.error(f"Error restoring item: {e}")
            self.notify(f"Error: {e}", severity="error")

    def action_back(self) -> None:
        """Go back to receipt list."""
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
