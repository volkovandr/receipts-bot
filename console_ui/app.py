#!/usr/bin/env python3
"""
Receipts Bot - Console UI
A terminal-based user interface for managing receipts.
"""

import sys
import os

# Add parent directory to path to import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from textual.app import App
from console_ui.screens.receipt_list import ReceiptListScreen
from database import Database
from config import Config


class ReceiptsApp(App):
    """A Textual app for managing receipts."""

    CSS = """
    DataTable {
        height: 1fr;
    }

    #receipt-count {
        padding: 0 1;
        background: $panel;
        color: $text-muted;
        text-style: italic;
    }

    #receipt_header {
        padding: 1;
        background: $panel;
        border: solid $primary;
        margin-bottom: 1;
    }

    #detail_container {
        height: 1fr;
    }

    /* Discrepancy status styling */
    #detail_container.discrepancy {
        background: $error 10%;
    }

    #detail_container.no-discrepancy {
        background: $success 10%;
    }

    #items_table {
        height: 1fr;
    }

    /* Modal editor styling */
    #editor_dialog {
        align: center middle;
        width: 80;
        height: auto;
        background: $surface;
        border: thick $primary;
    }

    #editor_content {
        width: 100%;
        height: auto;
        padding: 2;
    }

    #modal_title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    #button_row {
        align: center middle;
        width: 100%;
        height: auto;
        padding-top: 1;
    }

    #button_row Button {
        margin: 0 1;
    }

    #name_input, #amount_input {
        width: 100%;
    }

    #category_select {
        width: 100%;
    }
    """

    def __init__(self, db: Database, user_id: int):
        """
        Initialize the app.

        Args:
            db: Database instance
            user_id: User ID to display receipts for
        """
        super().__init__()
        self.db = db
        self.user_id = user_id

    def on_mount(self) -> None:
        """Push the receipt list screen when app starts."""
        self.push_screen(ReceiptListScreen(self.db, self.user_id))


def main():
    """Run the application."""
    # Load configuration
    config = Config()

    # Get user_id from command line argument or use first allowed user
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
        except ValueError:
            print(f"Error: Invalid user_id '{sys.argv[1]}'. Must be an integer.")
            sys.exit(1)
    else:
        # Use first allowed user from config
        if not config.allowed_user_ids:
            print("Error: No user_id provided and no allowed_user_ids in config.ini")
            print("Usage: python console_ui/app.py <user_id>")
            sys.exit(1)
        user_id = list(config.allowed_user_ids)[0]
        print(f"Using user_id: {user_id} (from config.ini)")

    # Initialize database
    db = Database(
        config.db_host,
        config.db_port,
        config.db_name,
        config.db_user,
        config.db_password
    )
    db.connect()

    try:
        # Run the app
        app = ReceiptsApp(db, user_id)
        app.run()
    finally:
        # Close database connection
        db.close()


if __name__ == "__main__":
    main()
