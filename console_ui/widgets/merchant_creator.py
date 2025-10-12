"""
Merchant Creator Modal - Dialog for creating a new merchant.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
import logging

logger = logging.getLogger(__name__)


class MerchantCreatorModal(ModalScreen):
    """Modal dialog for creating a new merchant."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db, receipt_id: int, default_name: str = ""):
        """
        Initialize merchant creator modal.

        Args:
            db: Database instance
            receipt_id: Receipt ID to associate with new merchant
            default_name: Default merchant name (from search)
        """
        super().__init__()
        self.db = db
        self.receipt_id = receipt_id
        self.default_name = default_name

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Container(
            Vertical(
                Static(f"[bold]Create New Merchant[/bold]", id="modal_title"),
                Static(""),
                Label("Merchant Name: (required)"),
                Input(value=self.default_name, placeholder="Merchant name", id="name_input"),
                Static(""),
                Label("City:"),
                Input(placeholder="City", id="city_input"),
                Static(""),
                Label("Country:"),
                Input(placeholder="Country", id="country_input"),
                Static(""),
                Label("Address:"),
                Input(placeholder="Full address", id="address_input"),
                Static(""),
                Label("Logo Description:"),
                Input(placeholder="Logo description", id="logo_input"),
                Static(""),
                Horizontal(
                    Button("Create & Switch", variant="primary", id="create_button"),
                    Button("Cancel", variant="default", id="cancel_button"),
                    id="button_row"
                ),
                id="editor_content"
            ),
            id="editor_dialog"
        )

    def on_mount(self) -> None:
        """Focus name input when mounted."""
        name_input = self.query_one("#name_input", Input)
        name_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "create_button":
            self.action_create()
        elif event.button.id == "cancel_button":
            self.action_cancel()

    def action_create(self) -> None:
        """Create new merchant and switch receipt to it."""
        try:
            # Get form values
            name_input = self.query_one("#name_input", Input)
            city_input = self.query_one("#city_input", Input)
            country_input = self.query_one("#country_input", Input)
            address_input = self.query_one("#address_input", Input)
            logo_input = self.query_one("#logo_input", Input)

            name = name_input.value.strip()
            city = city_input.value.strip()
            country = country_input.value.strip()
            address = address_input.value.strip()
            logo_desc = logo_input.value.strip()

            # Validation
            if not name or len(name) < 1:
                self.app.notify("Merchant name is required", severity="error")
                name_input.focus()
                return

            if len(name) > 200:
                self.app.notify("Merchant name too long (max 200 characters)", severity="error")
                return

            # Check if merchant with this name already exists (case-insensitive)
            existing = self.db.find_merchant_by_name(name)
            if existing:
                self.app.notify(
                    f"Merchant '{existing['name']}' already exists. Use search to select it.",
                    severity="warning"
                )
                return

            # Create merchant
            merchant_id = self.db.create_merchant(
                name=name,
                city=city if city else None,
                country=country if country else None,
                address=address if address else None,
                logo_description=logo_desc if logo_desc else None
            )

            if merchant_id:
                # Switch receipt to new merchant
                success = self.db.update_receipt_merchant(self.receipt_id, merchant_id)

                if success:
                    self.app.notify(f"Created merchant '{name}' and switched receipt", severity="information")
                    self.dismiss(True)  # Return True to indicate success
                else:
                    self.app.notify(f"Merchant created but failed to switch receipt", severity="warning")
                    self.dismiss(False)
            else:
                self.app.notify("Failed to create merchant", severity="error")
                self.dismiss(False)

        except ValueError as e:
            self.app.notify(f"Validation error: {str(e)}", severity="error")
        except Exception as e:
            logger.error(f"Error creating merchant: {e}", exc_info=True)
            self.app.notify(f"Error: {str(e)}", severity="error")

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(False)
