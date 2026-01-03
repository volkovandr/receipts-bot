"""
Merchant Switcher Modal - Dialog for switching a receipt to a different merchant.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, ListView, ListItem
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
import logging

logger = logging.getLogger(__name__)


class MerchantSwitcherModal(ModalScreen):
    """Modal dialog for switching receipt to a different merchant."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db, receipt_id: int, current_merchant: dict | None):
        """
        Initialize merchant switcher modal.

        Args:
            db: Database instance
            receipt_id: Receipt ID to switch merchant for
            current_merchant: Current merchant data (or None if no merchant)
        """
        super().__init__()
        self.db = db
        self.receipt_id = receipt_id
        self.current_merchant = current_merchant
        self.current_merchant_id = current_merchant['merchant_id'] if current_merchant else None
        self.search_results = []
        self.selected_merchant_id = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        current_name = self.current_merchant['name'] if self.current_merchant else "None"

        yield Container(
            Vertical(
                Static(f"[bold]Switch Merchant[/bold]", id="modal_title"),
                Static(f"Current merchant: [cyan]{current_name}[/cyan]", id="current_merchant"),
                Static(""),
                Label("Search for merchant (name or city):"),
                Input(placeholder="Type to search...", id="search_input"),
                Static(""),
                Static("Search results:", id="results_label"),
                ListView(id="results_list"),
                Static(""),
                Horizontal(
                    Button("Create New", variant="default", id="create_button"),
                    Button("Switch", variant="primary", id="switch_button", disabled=True),
                    Button("Cancel", variant="default", id="cancel_button"),
                    id="button_row"
                ),
                id="editor_content"
            ),
            id="editor_dialog"
        )

    def on_mount(self) -> None:
        """Set up the modal when mounted."""
        # Focus search input
        search_input = self.query_one("#search_input", Input)
        search_input.focus()

        # Load all merchants initially
        self._search_merchants("")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search_input":
            search_term = event.value.strip()
            self._search_merchants(search_term)

    def _search_merchants(self, search_term: str) -> None:
        """Search for merchants matching the search term."""
        try:
            # Get all merchants
            all_merchants = self.db.get_all_merchants()

            # Filter by search term (case-insensitive)
            if search_term:
                search_lower = search_term.lower()
                self.search_results = [
                    m for m in all_merchants
                    if (m['name'] and search_lower in m['name'].lower()) or
                       (m['city'] and search_lower in m['city'].lower()) or
                       (m['address'] and search_lower in m['address'].lower())
                ]
            else:
                self.search_results = all_merchants

            # Sort by name
            self.search_results.sort(key=lambda m: (m['name'] or "").lower())

            # Update results list
            results_list = self.query_one("#results_list", ListView)
            results_list.clear()

            if not self.search_results:
                results_list.append(ListItem(Label("[dim]No merchants found[/dim]")))
            else:
                for merchant in self.search_results:
                    name = merchant['name'] or "Unnamed"
                    city = merchant['city'] or ""
                    address = merchant['address'] or ""

                    # Build display text
                    display_parts = [f"[bold]{name}[/bold]"]
                    if city:
                        display_parts.append(city)
                    if address:
                        display_parts.append(f"[dim]{address}[/dim]")

                    display_text = " | ".join(display_parts)

                    # Mark current merchant
                    if merchant['merchant_id'] == self.current_merchant_id:
                        display_text = f"✓ {display_text} [yellow](current)[/yellow]"

                    item = ListItem(Label(display_text))
                    item.merchant_id = merchant['merchant_id']  # Store merchant_id on the item
                    results_list.append(item)

            # Update results label
            results_label = self.query_one("#results_label", Static)
            count = len(self.search_results)
            results_label.update(f"Search results: {count} merchant(s)")

        except Exception as e:
            logger.error(f"Error searching merchants: {e}", exc_info=True)
            self.app.notify(f"Error: {str(e)}", severity="error")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle merchant selection from list."""
        try:
            # Get merchant_id from the selected item
            if hasattr(event.item, 'merchant_id'):
                self.selected_merchant_id = event.item.merchant_id

                # Enable switch button
                switch_button = self.query_one("#switch_button", Button)
                switch_button.disabled = False

                logger.debug(f"Selected merchant_id: {self.selected_merchant_id}")
        except Exception as e:
            logger.error(f"Error handling selection: {e}", exc_info=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "switch_button":
            self.action_switch()
        elif event.button.id == "create_button":
            self.action_create_new()
        elif event.button.id == "cancel_button":
            self.action_cancel()

    def action_switch(self) -> None:
        """Switch receipt to selected merchant."""
        if self.selected_merchant_id is None:
            self.app.notify("No merchant selected", severity="warning")
            return

        if self.selected_merchant_id == self.current_merchant_id:
            self.app.notify("Selected merchant is already current", severity="warning")
            return

        try:
            # Update receipt's merchant
            success = self.db.update_receipt_merchant(self.receipt_id, self.selected_merchant_id)

            if success:
                # Find selected merchant name for notification
                selected_merchant = next(
                    (m for m in self.search_results if m['merchant_id'] == self.selected_merchant_id),
                    None
                )
                merchant_name = selected_merchant['name'] if selected_merchant else "selected merchant"

                self.app.notify(f"Receipt switched to {merchant_name}", severity="information")
                self.dismiss(True)  # Return True to indicate success
            else:
                self.app.notify("Failed to switch merchant", severity="error")
                self.dismiss(False)

        except Exception as e:
            logger.error(f"Error switching merchant: {e}", exc_info=True)
            self.app.notify(f"Error: {str(e)}", severity="error")
            self.dismiss(False)

    def action_create_new(self) -> None:
        """Create a new merchant and switch to it."""
        try:
            # Get search term as default name
            search_input = self.query_one("#search_input", Input)
            default_name = search_input.value.strip()

            # Dismiss this modal and return a special value to indicate "create new"
            self.dismiss(("create_new", default_name))

        except Exception as e:
            logger.error(f"Error initiating create new: {e}", exc_info=True)
            self.app.notify(f"Error: {str(e)}", severity="error")

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(False)
