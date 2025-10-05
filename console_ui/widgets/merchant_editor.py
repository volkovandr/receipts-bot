"""
Merchant Editor Modal - Dialog for editing merchant information.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
import logging

logger = logging.getLogger(__name__)


class MerchantEditorModal(ModalScreen):
    """Modal dialog for editing merchant information."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db, merchant: dict, receipt_count: int):
        """
        Initialize merchant editor modal.

        Args:
            db: Database instance
            merchant: Merchant data dictionary (from get_merchant_by_id)
            receipt_count: Number of receipts that reference this merchant
        """
        super().__init__()
        self.db = db
        self.merchant = merchant
        self.receipt_count = receipt_count
        self.merchant_id = merchant['merchant_id']
        self.original_name = merchant['name'] or ''
        self.original_city = merchant['city'] or ''
        self.original_country = merchant['country'] or ''
        self.original_address = merchant['address'] or ''
        self.original_logo_desc = merchant['logo_description'] or ''

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Warning message about affected receipts
        warning_msg = f"⚠️  Changes will affect {self.receipt_count} receipt(s)" if self.receipt_count > 1 else ""

        yield Container(
            Vertical(
                Static(f"[bold]Edit Merchant Information[/bold]", id="modal_title"),
                Static(f"[yellow]{warning_msg}[/yellow]", id="warning_msg") if warning_msg else Static(""),
                Static(""),
                Label("Merchant Name:"),
                Input(value=self.original_name, placeholder="Merchant name", id="name_input"),
                Static(""),
                Label("City:"),
                Input(value=self.original_city, placeholder="City", id="city_input"),
                Static(""),
                Label("Country:"),
                Input(value=self.original_country, placeholder="Country", id="country_input"),
                Static(""),
                Label("Address:"),
                Input(value=self.original_address, placeholder="Full address", id="address_input"),
                Static(""),
                Label("Logo Description:"),
                Input(value=self.original_logo_desc, placeholder="Logo description", id="logo_input"),
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
            city_input = self.query_one("#city_input", Input)
            country_input = self.query_one("#country_input", Input)
            address_input = self.query_one("#address_input", Input)
            logo_input = self.query_one("#logo_input", Input)

            new_name = name_input.value.strip()
            new_city = city_input.value.strip()
            new_country = country_input.value.strip()
            new_address = address_input.value.strip()
            new_logo_desc = logo_input.value.strip()

            # Validation
            if not new_name or len(new_name) < 1:
                self.app.notify("Merchant name is required", severity="error")
                return

            if len(new_name) > 200:
                self.app.notify("Merchant name too long (max 200 characters)", severity="error")
                return

            # Check what changed
            changes = {}
            if new_name != self.original_name:
                changes['name'] = new_name
            if new_city != self.original_city:
                changes['city'] = new_city if new_city else None
            if new_country != self.original_country:
                changes['country'] = new_country if new_country else None
            if new_address != self.original_address:
                changes['address'] = new_address if new_address else None
            if new_logo_desc != self.original_logo_desc:
                changes['logo_description'] = new_logo_desc if new_logo_desc else None

            if not changes:
                self.app.notify("No changes detected", severity="warning")
                self.dismiss(False)
                return

            # Update merchant
            success = self.db.update_merchant(
                self.merchant_id,
                name=changes.get('name'),
                city=changes.get('city'),
                country=changes.get('country'),
                address=changes.get('address'),
                logo_description=changes.get('logo_description')
            )

            if success:
                msg = f"Merchant updated"
                if self.receipt_count > 1:
                    msg += f" ({self.receipt_count} receipts affected)"
                self.app.notify(msg, severity="information")
                self.dismiss(True)
            else:
                self.app.notify("Failed to update merchant", severity="error")
                self.dismiss(False)

        except ValueError as e:
            self.app.notify(f"Validation error: {str(e)}", severity="error")
        except Exception as e:
            logger.error(f"Error saving merchant: {e}", exc_info=True)
            self.app.notify(f"Error: {str(e)}", severity="error")

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(False)
