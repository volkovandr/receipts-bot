"""
Receipt List Screen - Displays all receipts in a table.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static
from textual.containers import Container
from textual.binding import Binding
from decimal import Decimal
from datetime import date, time
import logging

# Set up logging
logging.basicConfig(
    filename='/tmp/receipts_ui.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReceiptListScreen(Screen):
    """Screen showing all receipts in a table."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
        Binding("delete", "delete_receipt", "Delete"),
        Binding("ctrl+delete", "undelete_receipt", "Undelete"),
        Binding("h", "toggle_deleted", "Hide/Show Deleted"),
        Binding("m", "edit_merchant", "Edit Merchant"),
        Binding("M", "switch_merchant", "Switch Merchant"),
        Binding("t", "edit_date", "Edit Date/Time"),
        Binding("T", "edit_total", "Edit Total"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("f", "filter", "Filter"),
    ]

    def __init__(self, db, user_id: int):
        """
        Initialize receipt list screen.

        Args:
            db: Database instance
            user_id: User ID to fetch receipts for
        """
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.receipts = []
        self.show_deleted = True  # Show deleted receipts by default
        # Sorting state
        self.sort_columns = ["date", "merchant", "total_receipt", "status"]
        self.sort_column_idx = 0  # Start with date
        self.sort_reverse = True  # Most recent first by default
        # Filtering state
        self.filters = {}  # Active filters: {merchant_name: str, status: str}

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Static("", id="receipt-count")
        yield DataTable()
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table when screen is mounted."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Add columns
        table.add_column("ID", key="id", width=8)
        table.add_column("Date", key="date", width=12)
        table.add_column("Time", key="time", width=10)
        table.add_column("Merchant", key="merchant", width=20)
        table.add_column("City", key="city", width=15)
        table.add_column("Items", key="items", width=7)
        table.add_column("Cur", key="currency", width=5)
        table.add_column("Total(Items)", key="total_items", width=13)
        table.add_column("Total(Rcpt)", key="total_receipt", width=13)
        table.add_column("Disc", key="discrepancy", width=6)
        table.add_column("Status", key="status", width=15)
        table.add_column("Top Category", key="top_category", width=20)
        table.add_column("Del", key="deleted", width=8)

        # Load receipts from database
        self.load_receipts()

    def on_screen_resume(self) -> None:
        """Called when returning to this screen from detail view - refresh data."""
        logger.info("Receipt list screen resumed - reloading receipts to reflect any changes")
        self.load_receipts(preserve_cursor=True)

    def load_receipts(self, preserve_cursor: bool = False) -> None:
        """Load receipts from database and populate table.

        Args:
            preserve_cursor: If True, restore cursor to the same receipt_id after reload
        """
        table = self.query_one(DataTable)

        # Save current receipt_id if cursor preservation is requested
        saved_receipt_id = None
        if preserve_cursor and table.cursor_row is not None and table.cursor_row < len(table.rows):
            try:
                row_key = table.ordered_rows[table.cursor_row].key
                saved_receipt_id = int(row_key.value)
                logger.debug(f"Preserving cursor on receipt {saved_receipt_id}")
            except (ValueError, AttributeError, IndexError):
                pass

        table.clear()

        try:
            self.receipts = self.db.get_all_receipts_for_list(self.user_id, include_deleted=self.show_deleted)

            # Apply filters
            if self.filters:
                filtered_receipts = []
                for receipt in self.receipts:
                    # Check merchant name filter
                    if "merchant_name" in self.filters:
                        merchant_filter = self.filters["merchant_name"].lower()
                        merchant_name = (receipt['merchant_name'] or "").lower()
                        if merchant_filter not in merchant_name:
                            continue

                    # Check status filter
                    if "status" in self.filters:
                        if receipt['processing_status'] != self.filters["status"]:
                            continue

                    # All filters passed
                    filtered_receipts.append(receipt)

                self.receipts = filtered_receipts

            # Apply sorting
            sort_key = self.sort_columns[self.sort_column_idx]
            if sort_key == "date":
                self.receipts.sort(key=lambda r: (r['transaction_date'] or date.min, r['transaction_time'] or time.min), reverse=self.sort_reverse)
            elif sort_key == "merchant":
                self.receipts.sort(key=lambda r: (r['merchant_name'] or "").lower(), reverse=self.sort_reverse)
            elif sort_key == "total_receipt":
                self.receipts.sort(key=lambda r: r['total_receipt'] or 0, reverse=self.sort_reverse)
            elif sort_key == "status":
                self.receipts.sort(key=lambda r: r['processing_status'] or "", reverse=self.sort_reverse)

            for receipt in self.receipts:
                # Format values
                receipt_id = str(receipt['receipt_id'])

                # Format date
                trans_date = receipt['transaction_date']
                if isinstance(trans_date, date):
                    date_str = trans_date.strftime('%Y-%m-%d')
                else:
                    date_str = str(trans_date) if trans_date else 'N/A'

                # Format time
                trans_time = receipt['transaction_time']
                if isinstance(trans_time, time):
                    time_str = trans_time.strftime('%H:%M:%S')
                else:
                    time_str = str(trans_time) if trans_time else ''

                merchant = receipt['merchant_name']
                city = receipt['merchant_city']
                items = str(receipt['item_count'])
                currency = receipt['currency']

                # Format monetary values
                total_items = receipt['total_items']
                if isinstance(total_items, Decimal):
                    total_items_str = f"{float(total_items):.2f}"
                else:
                    total_items_str = f"{total_items:.2f}" if total_items else "0.00"

                total_receipt = receipt['total_receipt']
                if isinstance(total_receipt, Decimal):
                    total_receipt_str = f"{float(total_receipt):.2f}"
                else:
                    total_receipt_str = f"{total_receipt:.2f}" if total_receipt else "0.00"

                # Discrepancy indicator
                has_discrepancy = receipt['has_discrepancy']
                discrepancy_str = "⚠️ YES" if has_discrepancy else "NO"

                status = receipt['processing_status']
                top_category = receipt['top_category']
                is_deleted = receipt.get('is_deleted', False)

                # Apply styling for deleted receipts (strike dim, consistent with deleted items)
                deleted_marker = ""
                if is_deleted:
                    receipt_id = f"[strike dim]{receipt_id}[/strike dim]"
                    date_str = f"[strike dim]{date_str}[/strike dim]"
                    time_str = f"[strike dim]{time_str}[/strike dim]"
                    merchant = f"[strike dim]{merchant}[/strike dim]"
                    city = f"[strike dim]{city}[/strike dim]"
                    items = f"[strike dim]{items}[/strike dim]"
                    currency = f"[strike dim]{currency}[/strike dim]"
                    total_items_str = f"[strike dim]{total_items_str}[/strike dim]"
                    total_receipt_str = f"[strike dim]{total_receipt_str}[/strike dim]"
                    discrepancy_str = f"[strike dim]{discrepancy_str}[/strike dim]"
                    status = f"[strike dim]{status}[/strike dim]"
                    top_category = f"[strike dim]{top_category}[/strike dim]"
                    deleted_marker = "[red]DELETED[/red]"

                # Add row
                table.add_row(
                    receipt_id,
                    date_str,
                    time_str,
                    merchant,
                    city,
                    items,
                    currency,
                    total_items_str,
                    total_receipt_str,
                    discrepancy_str,
                    status,
                    top_category,
                    deleted_marker,
                    key=str(receipt['receipt_id'])
                )

            # Restore cursor position if requested
            if saved_receipt_id is not None and len(table.rows) > 0:
                # Find the row with the saved receipt_id
                for idx, row in enumerate(table.ordered_rows):
                    try:
                        if int(row.key.value) == saved_receipt_id:
                            table.move_cursor(row=idx)
                            logger.debug(f"Cursor restored to row {idx} (receipt {saved_receipt_id})")
                            break
                    except (ValueError, AttributeError):
                        continue

            # Update receipt count display
            count_widget = self.query_one("#receipt-count", Static)
            receipt_count = len(self.receipts)
            filter_info = ""
            if self.filters:
                filter_parts = []
                if "merchant_name" in self.filters:
                    filter_parts.append(f"merchant: '{self.filters['merchant_name']}'")
                if "status" in self.filters:
                    filter_parts.append(f"status: '{self.filters['status']}'")
                filter_info = f" (filtered: {', '.join(filter_parts)})"
            count_widget.update(f"Showing {receipt_count} receipt(s){filter_info}")

        except Exception as e:
            # Show error in table (13 columns now)
            table.add_row(
                "ERROR",
                str(e),
                "", "", "", "", "", "", "", "", "", "", "",
                key="error"
            )
            # Update count display
            count_widget = self.query_one("#receipt-count", Static)
            count_widget.update("Error loading receipts")

    def action_select_receipt(self) -> None:
        """Handle Enter key - select receipt for viewing."""
        logger.info("action_select_receipt called")
        table = self.query_one(DataTable)
        logger.debug(f"cursor_row: {table.cursor_row}, row_count: {table.row_count}")

        if table.cursor_row is not None and table.row_count > 0:
            # Get the row key from ordered_rows using cursor position
            try:
                logger.debug(f"Attempting to get row at index {table.cursor_row}")
                row = table.ordered_rows[table.cursor_row]
                receipt_id_str = str(row.key.value)
                logger.info(f"Row key value: {receipt_id_str}")

                if receipt_id_str != "error":
                    receipt_id = int(receipt_id_str)
                    logger.info(f"Looking for receipt_id: {receipt_id}")
                    # Find the receipt data
                    receipt_data = None
                    for receipt in self.receipts:
                        if receipt['receipt_id'] == receipt_id:
                            receipt_data = receipt
                            break

                    if receipt_data:
                        logger.info(f"Found receipt data, pushing detail screen")
                        # Import here to avoid circular imports
                        from console_ui.screens.receipt_detail import ReceiptDetailScreen
                        # Push detail screen
                        self.app.push_screen(ReceiptDetailScreen(
                            self.db, self.user_id, receipt_id, receipt_data
                        ))
                    else:
                        logger.warning(f"Receipt data not found for ID {receipt_id}")
            except (ValueError, AttributeError, IndexError) as e:
                # Log error but don't crash
                logger.error(f"Error in action_select_receipt: {e}", exc_info=True)
        else:
            logger.warning(f"Cursor or row count invalid: cursor={table.cursor_row}, count={table.row_count}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        logger.info(f"Row selected event: {event.row_key}")

        try:
            receipt_id_str = str(event.row_key.value)
            logger.info(f"Receipt ID from row key: {receipt_id_str}")

            if receipt_id_str != "error":
                receipt_id = int(receipt_id_str)
                # Find the receipt data
                receipt_data = None
                for receipt in self.receipts:
                    if receipt['receipt_id'] == receipt_id:
                        receipt_data = receipt
                        break

                if receipt_data:
                    logger.info(f"Found receipt data, pushing detail screen")
                    # Import here to avoid circular imports
                    from console_ui.screens.receipt_detail import ReceiptDetailScreen
                    # Push detail screen
                    self.app.push_screen(ReceiptDetailScreen(
                        self.db, self.user_id, receipt_id, receipt_data
                    ))
                else:
                    logger.warning(f"Receipt data not found for ID {receipt_id}")
        except (ValueError, AttributeError) as e:
            logger.error(f"Error in on_data_table_row_selected: {e}", exc_info=True)

    def action_delete_receipt(self) -> None:
        """Delete selected receipt (soft delete)."""
        table = self.query_one(DataTable)

        if table.cursor_row is not None and table.row_count > 0:
            try:
                row = table.ordered_rows[table.cursor_row]
                receipt_id = int(row.key.value)

                # Find receipt data to check if already deleted
                receipt_data = None
                for receipt in self.receipts:
                    if receipt['receipt_id'] == receipt_id:
                        receipt_data = receipt
                        break

                if receipt_data:
                    is_deleted = receipt_data.get('is_deleted', False)
                    if is_deleted:
                        self.notify("Receipt is already deleted", severity="warning")
                        return

                    # Mark as deleted
                    success = self.db.mark_receipt_as_deleted(receipt_id, self.user_id)
                    if success:
                        self.notify(f"Receipt {receipt_id} deleted", severity="information")
                        # Reload to show updated status
                        self.load_receipts(preserve_cursor=True)
                    else:
                        self.notify("Failed to delete receipt", severity="error")
            except (ValueError, AttributeError, IndexError) as e:
                logger.error(f"Error in action_delete_receipt: {e}", exc_info=True)

    def action_undelete_receipt(self) -> None:
        """Restore a deleted receipt."""
        table = self.query_one(DataTable)

        if table.cursor_row is not None and table.row_count > 0:
            try:
                row = table.ordered_rows[table.cursor_row]
                receipt_id = int(row.key.value)

                # Find receipt data to check if deleted
                receipt_data = None
                for receipt in self.receipts:
                    if receipt['receipt_id'] == receipt_id:
                        receipt_data = receipt
                        break

                if receipt_data:
                    is_deleted = receipt_data.get('is_deleted', False)
                    if not is_deleted:
                        self.notify("Receipt is not deleted", severity="warning")
                        return

                    # Restore receipt
                    success = self.db.undelete_receipt(receipt_id, self.user_id)
                    if success:
                        self.notify(f"Receipt {receipt_id} restored", severity="information")
                        # Reload to show updated status
                        self.load_receipts(preserve_cursor=True)
                    else:
                        self.notify("Failed to restore receipt", severity="error")
            except (ValueError, AttributeError, IndexError) as e:
                logger.error(f"Error in action_undelete_receipt: {e}", exc_info=True)

    def action_toggle_deleted(self) -> None:
        """Toggle visibility of deleted receipts."""
        self.show_deleted = not self.show_deleted
        status = "shown" if self.show_deleted else "hidden"
        self.notify(f"Deleted receipts {status}", severity="information")
        # Reload with new filter
        self.load_receipts(preserve_cursor=True)

    def action_edit_merchant(self) -> None:
        """Edit merchant information for selected receipt."""
        table = self.query_one(DataTable)

        if table.cursor_row is not None and table.row_count > 0:
            try:
                row = table.ordered_rows[table.cursor_row]
                receipt_id = int(row.key.value)

                # Find receipt data to get merchant_id
                receipt_data = None
                for receipt in self.receipts:
                    if receipt['receipt_id'] == receipt_id:
                        receipt_data = receipt
                        break

                if not receipt_data:
                    self.notify("Receipt data not found", severity="error")
                    return

                merchant_id = receipt_data.get('merchant_id')
                if not merchant_id:
                    self.notify("No merchant associated with this receipt", severity="warning")
                    return

                # Get merchant details
                merchant = self.db.get_merchant_by_id(merchant_id)
                if not merchant:
                    self.notify("Merchant not found", severity="error")
                    return

                # Get count of receipts for this merchant
                receipt_count = self.db.get_receipt_count_by_merchant(merchant_id)

                # Use run_worker to handle async modal
                self.run_worker(self._edit_merchant_worker(merchant, receipt_count), exclusive=True)

            except (ValueError, AttributeError, IndexError) as e:
                logger.error(f"Error in action_edit_merchant: {e}", exc_info=True)
                self.notify(f"Error: {str(e)}", severity="error")

    async def _edit_merchant_worker(self, merchant: dict, receipt_count: int) -> None:
        """Worker to handle merchant editing modal."""
        from console_ui.widgets.merchant_editor import MerchantEditorModal

        result = await self.app.push_screen_wait(
            MerchantEditorModal(self.db, merchant, receipt_count)
        )

        if result:
            # Reload receipts to show updated merchant info
            self.load_receipts(preserve_cursor=True)

    def action_switch_merchant(self) -> None:
        """Switch receipt to a different merchant."""
        table = self.query_one(DataTable)

        if table.cursor_row is not None and table.row_count > 0:
            try:
                row = table.ordered_rows[table.cursor_row]
                receipt_id = int(row.key.value)

                # Find receipt data to get current merchant
                receipt_data = None
                for receipt in self.receipts:
                    if receipt['receipt_id'] == receipt_id:
                        receipt_data = receipt
                        break

                if not receipt_data:
                    self.notify("Receipt data not found", severity="error")
                    return

                # Get current merchant details (may be None)
                current_merchant = None
                merchant_id = receipt_data.get('merchant_id')
                if merchant_id:
                    current_merchant = self.db.get_merchant_by_id(merchant_id)

                # Use run_worker to handle async modal
                self.run_worker(self._switch_merchant_worker(receipt_id, current_merchant), exclusive=True)

            except (ValueError, AttributeError, IndexError) as e:
                logger.error(f"Error in action_switch_merchant: {e}", exc_info=True)
                self.notify(f"Error: {str(e)}", severity="error")

    async def _switch_merchant_worker(self, receipt_id: int, current_merchant: dict | None) -> None:
        """Worker to handle merchant switching modal."""
        from console_ui.widgets.merchant_switcher import MerchantSwitcherModal
        from console_ui.widgets.merchant_creator import MerchantCreatorModal

        result = await self.app.push_screen_wait(
            MerchantSwitcherModal(self.db, receipt_id, current_merchant)
        )

        if result:
            # Check if we need to create a new merchant
            if isinstance(result, tuple) and result[0] == "create_new":
                default_name = result[1]
                # Open merchant creator modal
                create_result = await self.app.push_screen_wait(
                    MerchantCreatorModal(self.db, receipt_id, default_name)
                )

                if create_result:
                    # Reload receipts to show updated merchant info
                    self.load_receipts(preserve_cursor=True)
            else:
                # Merchant was switched successfully
                # Reload receipts to show updated merchant info
                self.load_receipts(preserve_cursor=True)

    def action_edit_date(self) -> None:
        """Edit receipt date and time."""
        table = self.query_one(DataTable)

        if table.cursor_row is not None and table.row_count > 0:
            try:
                row = table.ordered_rows[table.cursor_row]
                receipt_id = int(row.key.value)

                # Find receipt data to get current date/time
                receipt_data = None
                for receipt in self.receipts:
                    if receipt['receipt_id'] == receipt_id:
                        receipt_data = receipt
                        break

                if not receipt_data:
                    self.notify("Receipt data not found", severity="error")
                    return

                current_date = receipt_data.get('transaction_date')
                current_time = receipt_data.get('transaction_time')

                # Use run_worker to handle async modal
                self.run_worker(self._edit_date_worker(receipt_id, current_date, current_time), exclusive=True)

            except (ValueError, AttributeError, IndexError) as e:
                logger.error(f"Error in action_edit_date: {e}", exc_info=True)
                self.notify(f"Error: {str(e)}", severity="error")

    async def _edit_date_worker(self, receipt_id: int, current_date, current_time) -> None:
        """Worker to handle date/time editing modal."""
        from console_ui.widgets.receipt_date_editor import ReceiptDateEditorModal

        result = await self.app.push_screen_wait(
            ReceiptDateEditorModal(self.db, receipt_id, self.user_id, current_date, current_time)
        )

        if result:
            # Reload receipts to show updated date/time
            self.load_receipts(preserve_cursor=True)

    def action_edit_total(self) -> None:
        """Edit receipt total amount."""
        table = self.query_one(DataTable)

        if table.cursor_row is not None and table.row_count > 0:
            try:
                row = table.ordered_rows[table.cursor_row]
                receipt_id = int(row.key.value)

                # Find receipt data to get current total and currency
                receipt_data = None
                for receipt in self.receipts:
                    if receipt['receipt_id'] == receipt_id:
                        receipt_data = receipt
                        break

                if not receipt_data:
                    self.notify("Receipt data not found", severity="error")
                    return

                current_total = receipt_data.get('total_receipt')
                currency = receipt_data.get('currency', 'EUR')

                # Use run_worker to handle async modal
                self.run_worker(self._edit_total_worker(receipt_id, current_total, currency), exclusive=True)

            except (ValueError, AttributeError, IndexError) as e:
                logger.error(f"Error in action_edit_total: {e}", exc_info=True)
                self.notify(f"Error: {str(e)}", severity="error")

    async def _edit_total_worker(self, receipt_id: int, current_total, currency: str) -> None:
        """Worker to handle total editing modal."""
        from console_ui.widgets.receipt_total_editor import ReceiptTotalEditorModal

        result = await self.app.push_screen_wait(
            ReceiptTotalEditorModal(self.db, receipt_id, self.user_id, current_total, currency)
        )

        if result:
            # Reload receipts to show updated total
            self.load_receipts(preserve_cursor=True)

    def action_cycle_sort(self) -> None:
        """Cycle through sorting options or toggle direction."""
        # Store previous column to detect if we're cycling or toggling
        prev_column_idx = self.sort_column_idx

        # Cycle to next sort column
        self.sort_column_idx = (self.sort_column_idx + 1) % len(self.sort_columns)

        # If we wrapped back to the first column, toggle direction instead
        if self.sort_column_idx == 0 and prev_column_idx == len(self.sort_columns) - 1:
            # We've cycled through all columns, toggle direction
            self.sort_reverse = not self.sort_reverse

        # Get column name for display
        column_names = {
            "date": "Date",
            "merchant": "Merchant",
            "total_receipt": "Total",
            "status": "Status"
        }
        sort_col = self.sort_columns[self.sort_column_idx]
        direction = "↓" if self.sort_reverse else "↑"

        self.notify(f"Sorting by {column_names[sort_col]} {direction}", severity="information")
        self.load_receipts(preserve_cursor=True)

    def action_filter(self) -> None:
        """Show filter dialog."""
        self.run_worker(self._filter_worker(), exclusive=True)

    async def _filter_worker(self) -> None:
        """Worker to handle filter dialog."""
        from console_ui.widgets.filter_dialog import FilterDialog

        result = await self.app.push_screen_wait(FilterDialog(self.filters))

        if result is not None:  # None means cancelled
            self.filters = result

            # Build filter description
            filter_parts = []
            if "merchant_name" in self.filters:
                filter_parts.append(f"merchant: '{self.filters['merchant_name']}'")
            if "status" in self.filters:
                filter_parts.append(f"status: '{self.filters['status']}'")

            if filter_parts:
                self.notify(f"Filters applied: {', '.join(filter_parts)}", severity="information")
            else:
                self.notify("All filters cleared", severity="information")

            # Reload receipts with new filters
            self.load_receipts(preserve_cursor=False)

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
