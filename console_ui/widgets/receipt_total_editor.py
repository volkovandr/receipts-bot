"""
Receipt Total Editor Modal - Dialog for editing receipt total amount.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)


class ReceiptTotalEditorModal(ModalScreen):
    """Modal dialog for editing receipt total amount."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db, receipt_id: int, user_id: int, current_total: float | None, currency: str = "EUR"):
        """
        Initialize receipt total editor modal.

        Args:
            db: Database instance
            receipt_id: Receipt ID
            user_id: User ID (for authorization)
            current_total: Current receipt total (may be None)
            currency: Currency code (default: EUR)
        """
        super().__init__()
        self.db = db
        self.receipt_id = receipt_id
        self.user_id = user_id
        self.current_total = current_total
        self.currency = currency

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Format current value for display
        total_str = f"{self.current_total:.2f}" if self.current_total is not None else ""

        yield Container(
            Vertical(
                Static(f"[bold]Edit Receipt Total[/bold]", id="modal_title"),
                Static(f"Receipt ID: {self.receipt_id}", id="receipt_info"),
                Static(""),
                Label(f"Total Amount ({self.currency}):"),
                Input(value=total_str, placeholder="0.00", id="total_input"),
                Static(""),
                Static("[dim]Enter the total amount shown on the receipt[/dim]", id="hint"),
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
        """Focus total input when mounted."""
        total_input = self.query_one("#total_input", Input)
        total_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save_button":
            self.action_save()
        elif event.button.id == "cancel_button":
            self.action_cancel()

    def action_save(self) -> None:
        """Save changes to database."""
        try:
            # Get form value
            total_input = self.query_one("#total_input", Input)
            total_str = total_input.value.strip()

            # Validation - amount is required
            if not total_str:
                self.app.notify("Total amount is required", severity="error")
                total_input.focus()
                return

            # Parse amount
            try:
                new_total = Decimal(total_str)
            except (ValueError, InvalidOperation):
                self.app.notify("Invalid amount format. Use numbers only (e.g., 25.50)", severity="error")
                total_input.focus()
                return

            # Validate amount is reasonable
            if new_total < 0:
                self.app.notify("Total amount cannot be negative", severity="error")
                total_input.focus()
                return

            if new_total > 999999.99:
                self.app.notify("Total amount too large (max: 999999.99)", severity="error")
                total_input.focus()
                return

            # Check if value actually changed
            if self.current_total is not None:
                current_decimal = Decimal(str(self.current_total))
                if abs(new_total - current_decimal) < Decimal('0.01'):
                    self.app.notify("No change detected", severity="warning")
                    self.dismiss(False)
                    return

            # Update receipt total
            success = self.db.update_receipt_transaction_total(
                self.receipt_id,
                float(new_total),
                self.user_id
            )

            if success:
                self.app.notify(
                    f"Receipt total updated: {self.currency} {float(new_total):.2f}",
                    severity="information"
                )
                self.dismiss(True)
            else:
                self.app.notify("Failed to update receipt total", severity="error")
                self.dismiss(False)

        except ValueError as e:
            self.app.notify(f"Validation error: {str(e)}", severity="error")
        except Exception as e:
            logger.error(f"Error saving receipt total: {e}", exc_info=True)
            self.app.notify(f"Error: {str(e)}", severity="error")

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(False)
