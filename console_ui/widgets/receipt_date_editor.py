"""
Receipt Date/Time Editor Modal - Dialog for editing receipt transaction date and time.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from datetime import date, time, datetime
import logging

logger = logging.getLogger(__name__)


class ReceiptDateEditorModal(ModalScreen):
    """Modal dialog for editing receipt date and time."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, db, receipt_id: int, user_id: int, current_date: date | None, current_time: time | None):
        """
        Initialize receipt date/time editor modal.

        Args:
            db: Database instance
            receipt_id: Receipt ID
            user_id: User ID (for authorization)
            current_date: Current transaction date (may be None)
            current_time: Current transaction time (may be None)
        """
        super().__init__()
        self.db = db
        self.receipt_id = receipt_id
        self.user_id = user_id
        self.current_date = current_date
        self.current_time = current_time

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Format current values for display
        date_str = self.current_date.strftime('%Y-%m-%d') if self.current_date else ""
        time_str = self.current_time.strftime('%H:%M:%S') if self.current_time else ""

        yield Container(
            Vertical(
                Static(f"[bold]Edit Receipt Date & Time[/bold]", id="modal_title"),
                Static(f"Receipt ID: {self.receipt_id}", id="receipt_info"),
                Static(""),
                Label("Date (YYYY-MM-DD):"),
                Input(value=date_str, placeholder="2025-10-12", id="date_input"),
                Static(""),
                Label("Time (HH:MM:SS):"),
                Input(value=time_str, placeholder="14:30:00", id="time_input"),
                Static(""),
                Static("[dim]Leave time blank to clear it[/dim]", id="hint"),
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
        """Focus date input when mounted."""
        date_input = self.query_one("#date_input", Input)
        date_input.focus()

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
            date_input = self.query_one("#date_input", Input)
            time_input = self.query_one("#time_input", Input)

            date_str = date_input.value.strip()
            time_str = time_input.value.strip()

            # Validation - date is required
            if not date_str:
                self.app.notify("Date is required", severity="error")
                date_input.focus()
                return

            # Parse date
            try:
                new_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.app.notify("Invalid date format. Use YYYY-MM-DD", severity="error")
                date_input.focus()
                return

            # Validate date is not in the future
            if new_date > date.today():
                self.app.notify("Date cannot be in the future", severity="warning")
                date_input.focus()
                return

            # Parse time (optional)
            new_time = None
            if time_str:
                try:
                    new_time = datetime.strptime(time_str, '%H:%M:%S').time()
                except ValueError:
                    # Try without seconds
                    try:
                        new_time = datetime.strptime(time_str, '%H:%M').time()
                    except ValueError:
                        self.app.notify("Invalid time format. Use HH:MM:SS or HH:MM", severity="error")
                        time_input.focus()
                        return

            # Check what changed
            date_changed = new_date != self.current_date
            time_changed = new_time != self.current_time

            if not date_changed and not time_changed:
                self.app.notify("No changes detected", severity="warning")
                self.dismiss(False)
                return

            # Update transaction date/time
            success = self.db.update_receipt_transaction_datetime(
                self.receipt_id,
                new_date,
                new_time,
                self.user_id
            )

            if success:
                date_display = new_date.strftime('%Y-%m-%d')
                time_display = new_time.strftime('%H:%M:%S') if new_time else "(cleared)"
                self.app.notify(
                    f"Receipt date/time updated: {date_display} {time_display}",
                    severity="information"
                )
                self.dismiss(True)
            else:
                self.app.notify("Failed to update receipt date/time", severity="error")
                self.dismiss(False)

        except ValueError as e:
            self.app.notify(f"Validation error: {str(e)}", severity="error")
        except Exception as e:
            logger.error(f"Error saving receipt date/time: {e}", exc_info=True)
            self.app.notify(f"Error: {str(e)}", severity="error")

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(False)
