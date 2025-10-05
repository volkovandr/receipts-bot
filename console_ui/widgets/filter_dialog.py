"""
Filter Dialog - Allows filtering receipts by various criteria.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Button, Input, Select, Label, Static
import logging

logger = logging.getLogger(__name__)


class FilterDialog(ModalScreen[dict | None]):
    """Modal dialog for filtering receipts."""

    DEFAULT_CSS = """
    FilterDialog {
        align: center middle;
    }

    #filter-dialog {
        width: 70;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #filter-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .filter-field {
        height: auto;
        margin-bottom: 1;
    }

    .filter-label {
        width: 20;
        padding-top: 1;
    }

    .filter-input {
        width: 1fr;
    }

    #filter-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
        margin-top: 1;
    }

    #filter-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, current_filters: dict):
        """
        Initialize filter dialog.

        Args:
            current_filters: Current filter values (merchant_name, status)
        """
        super().__init__()
        self.current_filters = current_filters or {}

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Container(id="filter-dialog"):
            yield Static("Filter Receipts", id="filter-title")

            # Merchant name filter
            with Horizontal(classes="filter-field"):
                yield Label("Merchant:", classes="filter-label")
                yield Input(
                    placeholder="Enter merchant name...",
                    value=self.current_filters.get("merchant_name", ""),
                    id="merchant-input",
                    classes="filter-input"
                )

            # Status filter
            with Horizontal(classes="filter-field"):
                yield Label("Status:", classes="filter-label")
                yield Select(
                    [
                        ("All statuses", ""),
                        ("Completed", "completed"),
                        ("Completed/Inconsistent", "completed/inconsistent"),
                        ("Processing", "processing"),
                        ("Pre-processed", "pre-processed"),
                        ("Created", "created"),
                        ("Failed", "failed"),
                    ],
                    value=self.current_filters.get("status", ""),
                    id="status-select",
                    classes="filter-input"
                )

            # Buttons
            with Horizontal(id="filter-buttons"):
                yield Button("Apply", variant="primary", id="apply-btn")
                yield Button("Clear All", id="clear-btn")
                yield Button("Cancel", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "apply-btn":
            # Get filter values
            merchant_input = self.query_one("#merchant-input", Input)
            status_select = self.query_one("#status-select", Select)

            filters = {}

            # Only include filters that have values
            merchant_name = merchant_input.value.strip()
            if merchant_name:
                filters["merchant_name"] = merchant_name

            status_value = status_select.value
            if status_value and status_value != "":
                filters["status"] = status_value

            # Return filters
            self.dismiss(filters)

        elif event.button.id == "clear-btn":
            # Clear all filters
            self.dismiss({})

        elif event.button.id == "cancel-btn":
            # Cancel - return None to indicate no changes
            self.dismiss(None)
