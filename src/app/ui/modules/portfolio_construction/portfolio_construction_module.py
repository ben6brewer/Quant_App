"""Portfolio Construction Module - Main Orchestrator"""

from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplitter
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox

from .services import PortfolioService, PortfolioPersistence
from .widgets import (
    PortfolioControls,
    TransactionLogTable,
    AggregatePortfolioTable,
    NewPortfolioDialog,
    LoadPortfolioDialog
)


class PortfolioConstructionModule(QWidget):
    """
    Main portfolio construction module.
    Orchestrates all widgets and services for portfolio management.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        # Initialize services
        PortfolioPersistence.initialize()

        # State
        self.current_portfolio = None  # Current portfolio dict
        self.unsaved_changes = False

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Load default portfolio on startup
        self._load_initial_portfolio()

        # Connect theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self):
        """Setup main UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = PortfolioControls(self.theme_manager)
        layout.addWidget(self.controls)

        # Splitter for side-by-side tables
        self.splitter = QSplitter(Qt.Horizontal)

        # Left: Transaction log
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.addWidget(QLabel("Transaction Log"))
        self.transaction_table = TransactionLogTable(self.theme_manager)
        left_layout.addWidget(self.transaction_table)

        # Right: Aggregate portfolio
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.addWidget(QLabel("Portfolio Holdings"))
        self.aggregate_table = AggregatePortfolioTable(self.theme_manager)
        right_layout.addWidget(self.aggregate_table)

        self.splitter.addWidget(left_container)
        self.splitter.addWidget(right_container)
        self.splitter.setSizes([600, 400])  # 60/40 split

        layout.addWidget(self.splitter)

    def _connect_signals(self):
        """Connect all signals."""
        # Controls
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.add_transaction_clicked.connect(self._add_transaction_row)
        self.controls.delete_transactions_clicked.connect(self._delete_selected_transactions)
        self.controls.save_clicked.connect(self._save_portfolio)
        self.controls.load_clicked.connect(self._load_portfolio_dialog)
        self.controls.new_portfolio_clicked.connect(self._new_portfolio_dialog)
        self.controls.refresh_prices_clicked.connect(self._refresh_prices)

        # Transaction table
        self.transaction_table.transaction_added.connect(self._on_transaction_changed)
        self.transaction_table.transaction_modified.connect(self._on_transaction_changed)
        self.transaction_table.transaction_deleted.connect(self._on_transaction_changed)

    def _load_initial_portfolio(self):
        """Load Default portfolio on startup."""
        # Check if Default exists
        if not PortfolioPersistence.portfolio_exists("Default"):
            # Create empty Default portfolio
            self.current_portfolio = PortfolioPersistence.create_new_portfolio("Default")
            PortfolioPersistence.save_portfolio(self.current_portfolio)
        else:
            # Load Default
            self.current_portfolio = PortfolioPersistence.load_portfolio("Default")

        # Populate controls
        portfolios = PortfolioPersistence.list_portfolios()
        if not portfolios:
            portfolios = ["Default"]
        self.controls.update_portfolio_list(portfolios, "Default")

        # Populate transaction table
        self._populate_transaction_table()

        # Fetch prices and update aggregate (don't show message on startup)
        self._update_aggregate_table()

    def _populate_transaction_table(self):
        """Populate transaction table from current portfolio."""
        self.transaction_table.clear_all_transactions()

        if not self.current_portfolio:
            return

        for transaction in self.current_portfolio.get("transactions", []):
            self.transaction_table.add_transaction_row(transaction)

        self.unsaved_changes = False

    def _add_transaction_row(self):
        """Add a new empty transaction row."""
        # Create empty transaction
        new_transaction = PortfolioService.create_transaction(
            date=datetime.now().strftime("%Y-%m-%d"),
            ticker="",
            transaction_type="Buy",
            quantity=0.0,
            entry_price=0.0,
            fees=0.0,
            notes=""
        )

        self.transaction_table.add_transaction_row(new_transaction)
        self.unsaved_changes = True

    def _delete_selected_transactions(self):
        """Delete selected transactions from table."""
        selected_count = len(set(idx.row() for idx in self.transaction_table.selectedIndexes()))

        if selected_count == 0:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Selection",
                "Please select transactions to delete."
            )
            return

        reply = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Delete Transactions",
            f"Delete {selected_count} selected transaction(s)?",
            CustomMessageBox.Yes | CustomMessageBox.No,
            CustomMessageBox.No
        )

        if reply == CustomMessageBox.Yes:
            self.transaction_table.delete_selected_rows()
            self.unsaved_changes = True
            self._update_aggregate_table()

    def _on_transaction_changed(self, *args):
        """Handle transaction add/modify/delete."""
        self.unsaved_changes = True
        self._update_aggregate_table()

    def _update_aggregate_table(self):
        """Recalculate and update aggregate table."""
        transactions = self.transaction_table.get_all_transactions()

        if not transactions:
            self.aggregate_table.setRowCount(0)
            return

        # Get unique tickers
        tickers = list(set(t["ticker"] for t in transactions if t["ticker"]))

        if not tickers:
            self.aggregate_table.setRowCount(0)
            return

        # Fetch current prices
        current_prices = PortfolioService.fetch_current_prices(tickers)

        # Update transaction table with prices
        self.transaction_table.update_current_prices(current_prices)

        # Calculate holdings
        holdings = PortfolioService.calculate_aggregate_holdings(transactions, current_prices)

        # Update aggregate table
        self.aggregate_table.update_holdings(holdings)

    def _refresh_prices(self):
        """Manually refresh current prices."""
        self._update_aggregate_table()
        CustomMessageBox.information(
            self.theme_manager,
            self,
            "Prices Refreshed",
            "Current prices updated successfully."
        )

    def _save_portfolio(self):
        """Save current portfolio to disk."""
        if not self.current_portfolio:
            return

        # Update transactions in portfolio
        self.current_portfolio["transactions"] = self.transaction_table.get_all_transactions()

        # Save
        success = PortfolioPersistence.save_portfolio(self.current_portfolio)

        if success:
            self.unsaved_changes = False
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "Saved",
                f"Portfolio '{self.current_portfolio['name']}' saved successfully."
            )
        else:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Save Error",
                "Failed to save portfolio."
            )

    def _load_portfolio_dialog(self):
        """Open load portfolio dialog."""
        # Check for unsaved changes
        if self.unsaved_changes:
            reply = CustomMessageBox.question(
                self.theme_manager,
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before loading?",
                CustomMessageBox.Yes | CustomMessageBox.No | CustomMessageBox.Cancel,
                CustomMessageBox.Cancel
            )

            if reply == CustomMessageBox.Yes:
                self._save_portfolio()
            elif reply == CustomMessageBox.Cancel:
                return

        # Open dialog
        portfolios = PortfolioPersistence.list_portfolios()
        if not portfolios:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Portfolios",
                "No portfolios found. Create a new one first."
            )
            return

        dialog = LoadPortfolioDialog(self.theme_manager, portfolios, self)

        if dialog.exec():
            name = dialog.get_selected_name()
            if name:
                self._load_portfolio(name)

    def _load_portfolio(self, name: str):
        """Load portfolio by name."""
        portfolio = PortfolioPersistence.load_portfolio(name)

        if not portfolio:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Load Error",
                f"Failed to load portfolio '{name}'."
            )
            return

        self.current_portfolio = portfolio
        self._populate_transaction_table()
        self._update_aggregate_table()

        # Update controls
        portfolios = PortfolioPersistence.list_portfolios()
        self.controls.update_portfolio_list(portfolios, name)

    def _new_portfolio_dialog(self):
        """Open new portfolio dialog."""
        # Check for unsaved changes
        if self.unsaved_changes:
            reply = CustomMessageBox.question(
                self.theme_manager,
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before creating a new portfolio?",
                CustomMessageBox.Yes | CustomMessageBox.No | CustomMessageBox.Cancel,
                CustomMessageBox.Cancel
            )

            if reply == CustomMessageBox.Yes:
                self._save_portfolio()
            elif reply == CustomMessageBox.Cancel:
                return

        # Open dialog
        existing = PortfolioPersistence.list_portfolios()
        dialog = NewPortfolioDialog(self.theme_manager, existing, self)

        if dialog.exec():
            name = dialog.get_name()
            # Create new portfolio
            self.current_portfolio = PortfolioPersistence.create_new_portfolio(name)
            PortfolioPersistence.save_portfolio(self.current_portfolio)

            # Clear tables
            self.transaction_table.clear_all_transactions()
            self.aggregate_table.setRowCount(0)

            # Update controls
            portfolios = PortfolioPersistence.list_portfolios()
            self.controls.update_portfolio_list(portfolios, name)

            self.unsaved_changes = False

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio selection change in dropdown."""
        if not name or (self.current_portfolio and name == self.current_portfolio.get("name")):
            return

        # Check for unsaved changes
        if self.unsaved_changes:
            reply = CustomMessageBox.question(
                self.theme_manager,
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before switching?",
                CustomMessageBox.Yes | CustomMessageBox.No | CustomMessageBox.Cancel,
                CustomMessageBox.Cancel
            )

            if reply == CustomMessageBox.Yes:
                self._save_portfolio()
            elif reply == CustomMessageBox.Cancel:
                # Revert dropdown
                current_name = self.current_portfolio.get("name") if self.current_portfolio else "Default"
                self.controls.update_portfolio_list(
                    PortfolioPersistence.list_portfolios(),
                    current_name
                )
                return

        self._load_portfolio(name)

    def _apply_theme(self):
        """Apply theme to module."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
            label_color = "#333333"
        elif theme == "bloomberg":
            bg_color = "#000814"
            label_color = "#a8a8a8"
        else:
            bg_color = "#1e1e1e"
            label_color = "#cccccc"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {label_color};
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
            }}
        """)
