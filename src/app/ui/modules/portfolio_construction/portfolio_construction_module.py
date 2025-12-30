"""Portfolio Construction Module - Main Orchestrator"""

from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox

from .services import PortfolioService, PortfolioPersistence
from .widgets import (
    PortfolioControls,
    TransactionLogTable,
    AggregatePortfolioTable,
    NewPortfolioDialog,
    LoadPortfolioDialog,
    RenamePortfolioDialog,
    ViewTabBar
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

        # Price cache - only fetch when tickers change
        self._cached_prices = {}  # ticker -> price
        self._cached_tickers = set()  # Set of tickers we've fetched prices for

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Initialize portfolio list without loading data
        self._initialize_portfolio_list()

        # Set initial view mode (Transaction Log by default)
        self.controls.set_view_mode(is_transaction_view=True)

        # Connect theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self):
        """Setup main UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar at top
        self.controls = PortfolioControls(self.theme_manager)
        layout.addWidget(self.controls)

        # View tab bar
        self.view_tab_bar = ViewTabBar(self.theme_manager)
        layout.addWidget(self.view_tab_bar)

        # Stacked widget for switching between tables
        self.table_stack = QStackedWidget()

        # Index 0: Transaction Log (full screen, no label)
        self.transaction_table = TransactionLogTable(self.theme_manager)
        self.table_stack.addWidget(self.transaction_table)

        # Index 1: Portfolio Holdings (full screen, no label)
        self.aggregate_table = AggregatePortfolioTable(self.theme_manager)
        self.table_stack.addWidget(self.aggregate_table)

        # Default to Transaction Log
        self.table_stack.setCurrentIndex(0)

        layout.addWidget(self.table_stack)

    def _connect_signals(self):
        """Connect all signals."""
        # Controls
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.save_clicked.connect(self._save_portfolio)
        self.controls.new_portfolio_clicked.connect(self._new_portfolio_dialog)
        self.controls.rename_portfolio_clicked.connect(self._rename_portfolio_dialog)
        self.controls.delete_portfolio_clicked.connect(self._delete_portfolio_dialog)
        self.controls.home_clicked.connect(self._on_home_clicked)

        # Transaction table
        self.transaction_table.transaction_added.connect(self._on_transaction_changed)
        self.transaction_table.transaction_modified.connect(self._on_transaction_changed)
        self.transaction_table.transaction_deleted.connect(self._on_transaction_changed)

        # View tab bar
        self.view_tab_bar.view_changed.connect(self._on_view_changed)

    def _on_view_changed(self, index: int):
        """Handle view tab change."""
        self.table_stack.setCurrentIndex(index)
        # Show editing buttons only on Transaction Log view (index 0)
        self.controls.set_view_mode(is_transaction_view=(index == 0))

    def _initialize_portfolio_list(self):
        """Initialize portfolio dropdown without loading data."""
        portfolios = PortfolioPersistence.list_portfolios()

        if not portfolios:
            # Create empty Default portfolio if none exist
            self.current_portfolio = PortfolioPersistence.create_new_portfolio("Default")
            PortfolioPersistence.save_portfolio(self.current_portfolio)
            portfolios = ["Default"]

        # Populate dropdown only (no data fetching)
        self.controls.update_portfolio_list(portfolios, portfolios[0])

        # Show empty state
        self._show_empty_state()

        # Ensure blank row exists for immediate editing
        self.transaction_table._ensure_blank_row()

    def _populate_transaction_table(self):
        """Populate transaction table from current portfolio."""
        self.transaction_table.clear_all_transactions()

        if not self.current_portfolio:
            return

        for transaction in self.current_portfolio.get("transactions", []):
            self.transaction_table.add_transaction_row(transaction)

        # Ensure blank row exists for adding new transactions
        self.transaction_table._ensure_blank_row()

        # Sort to maintain blank at top, transactions by date
        self.transaction_table._sort_transactions()

        self.unsaved_changes = False

    def _on_transaction_changed(self, *args):
        """Handle transaction add/modify/delete."""
        self.unsaved_changes = True
        self._update_aggregate_table()

    def _show_empty_state(self):
        """Display empty state when no portfolio loaded."""
        self.current_portfolio = None
        self.transaction_table.clear_all_transactions()
        self.aggregate_table.setRowCount(0)
        self.unsaved_changes = False
        # Clear price cache
        self._cached_prices.clear()
        self._cached_tickers.clear()

    def _update_aggregate_table(self, force_fetch: bool = False):
        """
        Recalculate and update aggregate table.

        Args:
            force_fetch: If True, fetch prices for all tickers (used on portfolio load)
        """
        transactions = self.transaction_table.get_all_transactions()

        if not transactions:
            self.aggregate_table.setRowCount(0)
            return

        # Get unique tickers
        tickers = set(t["ticker"] for t in transactions if t["ticker"])

        if not tickers:
            self.aggregate_table.setRowCount(0)
            return

        # Determine which tickers need price fetching
        if force_fetch:
            # Full refresh - fetch all tickers
            tickers_to_fetch = list(tickers)
        else:
            # Only fetch prices for NEW tickers (not already cached)
            tickers_to_fetch = [t for t in tickers if t not in self._cached_tickers]

        # Fetch prices only for tickers that need it
        if tickers_to_fetch:
            new_prices = PortfolioService.fetch_current_prices(tickers_to_fetch)
            # Update cache
            self._cached_prices.update(new_prices)
            self._cached_tickers.update(tickers_to_fetch)

        # Remove cached tickers that are no longer in use
        removed_tickers = self._cached_tickers - tickers
        for ticker in removed_tickers:
            self._cached_tickers.discard(ticker)
            self._cached_prices.pop(ticker, None)

        # Use cached prices for calculations
        current_prices = {t: self._cached_prices.get(t) for t in tickers}

        # Update transaction table with prices
        self.transaction_table.update_current_prices(current_prices)

        # Calculate holdings
        holdings = PortfolioService.calculate_aggregate_holdings(transactions, current_prices)

        # Update aggregate table
        self.aggregate_table.update_holdings(holdings)

    def _refresh_prices(self):
        """Manually refresh current prices."""
        # Clear cache and force fetch all prices
        self._cached_prices.clear()
        self._cached_tickers.clear()
        self._update_aggregate_table(force_fetch=True)
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

        # Clear price cache when loading new portfolio
        self._cached_prices.clear()
        self._cached_tickers.clear()

        self.current_portfolio = portfolio
        self._populate_transaction_table()
        # Force fetch all prices on portfolio load
        self._update_aggregate_table(force_fetch=True)

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

            # Clear tables and price cache
            self.transaction_table.clear_all_transactions()
            self.aggregate_table.setRowCount(0)
            self._cached_prices.clear()
            self._cached_tickers.clear()

            # Update controls
            portfolios = PortfolioPersistence.list_portfolios()
            self.controls.update_portfolio_list(portfolios, name)

            self.unsaved_changes = False

    def _rename_portfolio_dialog(self):
        """Open rename portfolio dialog."""
        if not self.current_portfolio:
            return

        current_name = self.current_portfolio.get("name", "")
        existing = PortfolioPersistence.list_portfolios()
        dialog = RenamePortfolioDialog(self.theme_manager, current_name, existing, self)

        if dialog.exec():
            new_name = dialog.get_name()
            if new_name and new_name != current_name:
                success = PortfolioPersistence.rename_portfolio(current_name, new_name)
                if success:
                    # Update current portfolio name
                    self.current_portfolio["name"] = new_name
                    # Refresh dropdown
                    portfolios = PortfolioPersistence.list_portfolios()
                    self.controls.update_portfolio_list(portfolios, new_name)
                else:
                    CustomMessageBox.critical(
                        self.theme_manager,
                        self,
                        "Rename Error",
                        f"Failed to rename portfolio to '{new_name}'."
                    )

    def _delete_portfolio_dialog(self):
        """Show confirmation dialog and delete current portfolio."""
        if not self.current_portfolio:
            return

        portfolio_name = self.current_portfolio.get("name", "")

        # Confirm deletion
        reply = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Delete Portfolio",
            f"Are you sure you want to delete '{portfolio_name}'?\n\nThis action cannot be undone.",
            CustomMessageBox.Yes | CustomMessageBox.No,
            CustomMessageBox.No
        )

        if reply != CustomMessageBox.Yes:
            return

        # Delete portfolio
        success = PortfolioPersistence.delete_portfolio(portfolio_name)

        if success:
            # Get remaining portfolios
            portfolios = PortfolioPersistence.list_portfolios()

            if not portfolios:
                # Create new Default portfolio if none left
                self.current_portfolio = PortfolioPersistence.create_new_portfolio("Default")
                PortfolioPersistence.save_portfolio(self.current_portfolio)
                portfolios = ["Default"]

            # Load first available portfolio
            self.controls.update_portfolio_list(portfolios, portfolios[0])
            self._load_portfolio(portfolios[0])
        else:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Delete Error",
                f"Failed to delete portfolio '{portfolio_name}'."
            )

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio selection change in dropdown."""
        if not name:
            return

        # Track if this is first load
        is_first_load = self.current_portfolio is None

        # Skip same-portfolio check on first load
        if not is_first_load and self.current_portfolio and name == self.current_portfolio.get("name"):
            return

        # Check for unsaved changes (skip on first load)
        if not is_first_load and self.unsaved_changes:
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

    def _on_home_clicked(self):
        """Handle home button click."""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'show_home'):
                parent.show_home()
                break
            parent = parent.parent()

    def _apply_theme(self):
        """Apply theme to module."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
        elif theme == "bloomberg":
            bg_color = "#000814"
        else:
            bg_color = "#1e1e1e"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
            }}
        """)
