"""Transaction Log Table Widget - Editable Transaction Table"""

from typing import Dict, List, Any, Optional, Tuple
from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView,
    QAbstractButton, QWidget, QHBoxLayout, QApplication, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal, QDate, QTimer, QEvent
from PySide6.QtGui import QBrush, QColor

from app.core.theme_manager import ThemeManager
from app.services.theme_stylesheet_service import ThemeStylesheetService
from app.ui.widgets.common import (
    CustomMessageBox,
    DateInputWidget,
    AutoSelectLineEdit,
    ValidatedNumericLineEdit,
    NoScrollComboBox,
    EditableTableBase,
)
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from ..services.portfolio_service import PortfolioService
from .mixins import FieldRevertMixin, SortingMixin


class TransactionLogTable(LazyThemeMixin, FieldRevertMixin, SortingMixin, EditableTableBase):
    """
    Editable transaction log table (left side).
    Inline editing with date picker and dropdown.
    """

    # Signals
    transaction_added = Signal(dict)           # Emitted when row added
    transaction_modified = Signal(str, dict)   # (transaction_id, updated_transaction)
    transaction_deleted = Signal(str)          # (transaction_id)
    _price_autofill_ready = Signal(int, float) # (row, price) - internal signal for thread-safe UI update
    _name_autofill_ready = Signal(int, str)    # (row, name) - internal signal for thread-safe name update
    _date_correction_needed = Signal(int, str, str)  # (row, first_available_date, ticker) - for date before history

    # Columns
    COLUMNS = [
        "Date",                # col 0 - DateInputWidget
        "Ticker",              # col 1 - AutoSelectLineEdit
        "Name",                # col 2 - Read-only (auto-populated from Yahoo Finance)
        "Quantity",            # col 3 - ValidatedNumericLineEdit
        "Execution Price",     # col 4 - ValidatedNumericLineEdit
        "Fees",                # col 5 - ValidatedNumericLineEdit
        "Type",                # col 6 - NoScrollComboBox (Buy/Sell)
        "Daily Closing Price", # col 7 - Read-only (historical close on tx date)
        "Live Price",          # col 8 - Read-only (last daily close)
        "Principal",           # col 9 - Read-only (calculated)
        "Market Value"         # col 10 - Read-only (calculated)
    ]

    # Editable columns (0-6, but 2 is read-only Name)
    EDITABLE_COLUMNS = [0, 1, 3, 4, 5, 6]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        # Initialize base class with theme_manager and columns
        super().__init__(theme_manager, self.COLUMNS, parent)

        # UUID-based transaction storage
        self._transactions_by_id: Dict[str, Dict[str, Any]] = {}  # Map transaction_id -> transaction_dict
        self._row_to_id: Dict[int, str] = {}  # Map row_index -> transaction_id

        # Legacy field for backwards compatibility (will be phased out)
        self._transactions = {}  # Map row_index -> transaction_dict

        self._current_prices: Dict[str, float] = {}  # Map ticker -> current_price
        self._historical_prices: Dict[str, Dict[str, float]] = {}  # Map ticker -> {date -> close_price}
        self._cached_names: Dict[str, str] = {}  # Map ticker -> short name from Yahoo Finance

        # Track original values for existing rows (for revert on invalid)
        # Map transaction_id -> {"ticker": str, "date": str}
        self._original_values: Dict[str, Dict[str, str]] = {}

        # Focus tracking for auto-delete
        self._current_editing_row: Optional[int] = None
        self._row_widgets_map: Dict[int, List[QWidget]] = {}
        self._skip_focus_validation: bool = False  # Prevent double validation dialogs
        self._validating: bool = False  # Prevent _on_cell_changed from corrupting sequences during validation

        # Debug flag for tracking _original_values changes (set to True to enable debugging)
        self._debug_original_values = False

        # Highlight editable fields setting (default True)
        self._highlight_editable = True

        # Hide FREE CASH summary row setting (default False - show it)
        self._hide_free_cash_summary = False

        # Custom sorting state (blank row always stays at top)
        self._current_sort_column: int = -1
        self._current_sort_order: Qt.SortOrder = Qt.AscendingOrder

        # FREE CASH summary row tracking (pinned at row 1, below blank row)
        self._free_cash_row_id = "FREE_CASH_SUMMARY"

        # Sequence counter for same-day transaction ordering (higher = newer)
        self._next_sequence: int = 0

        # Focus generation counter - increments on sort/successful edit to invalidate
        # any pending deferred focus callbacks that were queued before the operation
        self._focus_generation: int = 0

        # Track rows where user manually entered execution price (not auto-filled)
        # Set of row indices - if row is in this set, don't auto-fill the price
        self._user_entered_price_rows: set = set()

        # Batch loading mode - skip FREE CASH summary updates during bulk operations
        self._batch_loading: bool = False

        # For lazy theme application
        self._theme_dirty = False

        # Prevent duplicate date correction dialogs from multiple autofill threads
        self._date_correction_pending = False

        self._setup_table()
        self._apply_theme()

        # Connect theme changes (lazy - only apply when visible)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

        # Connect internal signals for thread-safe auto-fill
        self._price_autofill_ready.connect(self._apply_autofill_price)
        self._name_autofill_ready.connect(self._apply_autofill_name)
        self._date_correction_needed.connect(self._handle_date_correction)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def begin_batch_loading(self):
        """
        Begin batch loading mode.

        In this mode, FREE CASH summary updates are skipped during add_transaction_row()
        to avoid O(N²) performance when loading many transactions. Call end_batch_loading()
        when done to update the FREE CASH summary once.
        """
        self._batch_loading = True

    def end_batch_loading(self):
        """
        End batch loading mode and update FREE CASH summary.

        This updates the FREE CASH summary row once after all transactions have been added,
        reducing O(N²) to O(N) for batch loading operations.
        """
        self._batch_loading = False
        self._update_free_cash_summary_row()

    def _debug_set_original_values(self, tx_id: str, values: dict, caller: str):
        """Debug helper: log when _original_values is set."""
        if self._debug_original_values:
            ticker = values.get("ticker", "?")
            date = values.get("date", "?")
            old_values = self._original_values.get(tx_id, {})
            old_date = old_values.get("date", "NOT_SET")
            print(f"[ORIGINAL_VALUES] {caller}: tx_id={tx_id[:8]}... ticker={ticker} "
                  f"date: {old_date} -> {date}")
        self._original_values[tx_id] = values

    def _get_editable_columns(self) -> List[int]:
        """Return list of editable column indices (implements abstract method)."""
        return self.EDITABLE_COLUMNS

    def _setup_table(self):
        """Configure table structure."""
        # Call base class setup (handles column setup, row heights, selection, scrolling)
        self._setup_base_table()

        # Set column resize modes and widths (transaction-specific)
        self._reset_column_widths()

        # Connect header click for custom sorting
        header = self.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)

        # Set corner label
        self._set_corner_label("Transaction")

    def _reset_column_widths(self):
        """Reset column widths to fixed values. Called after table content changes."""
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # Date
        self.setColumnWidth(0, 150)
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Ticker
        self.setColumnWidth(1, 150)
        header.setSectionResizeMode(2, QHeaderView.Interactive)  # Name
        self.setColumnWidth(2, 300)
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Quantity
        self.setColumnWidth(3, 150)
        header.setSectionResizeMode(4, QHeaderView.Interactive)  # Execution Price
        self.setColumnWidth(4, 150)
        header.setSectionResizeMode(5, QHeaderView.Interactive)  # Fees
        self.setColumnWidth(5, 100)
        header.setSectionResizeMode(6, QHeaderView.Interactive)  # Type
        self.setColumnWidth(6, 100)
        header.setSectionResizeMode(7, QHeaderView.Interactive)  # Daily Closing Price
        self.setColumnWidth(7, 175)
        header.setSectionResizeMode(8, QHeaderView.Interactive)  # Live Price
        self.setColumnWidth(8, 150)
        header.setSectionResizeMode(9, QHeaderView.Stretch)  # Principal
        header.setSectionResizeMode(10, QHeaderView.Stretch)  # Market Value

    def _set_corner_label(self, text: str):
        """Set text for table corner button."""
        corner_button = self.findChild(QAbstractButton)
        if corner_button:
            corner_button.setText(text)
            corner_button.setEnabled(False)

    def _get_transaction_for_row(self, row: int) -> Optional[Dict[str, Any]]:
        """
        Get transaction dict for row index using ID mapping.

        Args:
            row: Row index

        Returns:
            Transaction dict or None if not found
        """
        tx_id = self._row_to_id.get(row)
        if tx_id:
            return self._transactions_by_id.get(tx_id)
        return None

    def _rebuild_transaction_map(self):
        """Rebuild row→id mapping after row operations."""
        new_row_to_id = {}
        for row in range(self.rowCount()):
            # Extract ID from widgets
            tx = self._extract_transaction_from_row(row)
            if tx and "id" in tx:
                new_row_to_id[row] = tx["id"]
        self._row_to_id = new_row_to_id

    def _get_next_sequence(self) -> int:
        """Get next sequence number and increment counter."""
        seq = self._next_sequence
        self._next_sequence += 1
        return seq

    def _initialize_sequence_counter(self, transactions: List[Dict[str, Any]]):
        """
        Initialize sequence counter from existing transactions.
        Sets counter to max(existing sequences) + 1.

        Args:
            transactions: List of transaction dicts
        """
        if not transactions:
            self._next_sequence = 0
            return

        max_seq = max(tx.get("sequence", 0) for tx in transactions)
        self._next_sequence = max_seq + 1

    def _ensure_blank_row(self):
        """Ensure blank row exists at top of table. Create if missing."""
        from datetime import datetime

        # Check if blank row already exists
        if self.rowCount() > 0:
            first_row_tx = self._get_transaction_for_row(0)
            if first_row_tx and first_row_tx.get("is_blank"):
                return  # Blank row already exists

        # Create blank transaction
        blank_transaction = {
            "id": "BLANK_ROW",
            "is_blank": True,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ticker": "",
            "transaction_type": "",  # Empty until user selects Buy/Sell
            "quantity": 0.0,
            "entry_price": 0.0,
            "fees": 0.0
        }

        # Shift existing row indices down (before inserting at row 0)
        # Build new mappings with shifted indices
        new_row_to_id = {}
        new_transactions = {}
        new_row_widgets_map = {}

        for old_row in range(self.rowCount()):
            new_row = old_row + 1  # Shift down by 1
            if old_row in self._row_to_id:
                new_row_to_id[new_row] = self._row_to_id[old_row]
            if old_row in self._transactions:
                new_transactions[new_row] = self._transactions[old_row]
            if old_row in self._row_widgets_map:
                new_row_widgets_map[new_row] = self._row_widgets_map[old_row]

        # Insert at top (row 0)
        self.setSortingEnabled(False)
        self.insertRow(0)
        self.setRowHeight(0, 48)  # Ensure consistent row height

        # Set blank vertical header for dummy row (excludes from row count display)
        blank_header = QTableWidgetItem("")
        self.setVerticalHeaderItem(0, blank_header)

        # Apply shifted mappings
        self._row_to_id = new_row_to_id
        self._transactions = new_transactions
        self._row_widgets_map = new_row_widgets_map

        # Store blank row at index 0
        self._transactions_by_id["BLANK_ROW"] = blank_transaction
        self._row_to_id[0] = "BLANK_ROW"
        self._transactions[0] = blank_transaction

        # Get current theme stylesheets
        widget_style = self._get_widget_stylesheet()
        combo_style = self._get_combo_stylesheet()

        # Create widgets for blank row
        # Date cell - column 0
        date_edit = DateInputWidget()
        date_edit.validation_error.connect(self._on_date_validation_error)
        date_edit.setDate(QDate.fromString(blank_transaction["date"], "yyyy-MM-dd"))
        date_edit.setStyleSheet(widget_style)
        date_edit.date_changed.connect(self._on_widget_changed)
        self._set_widget_position(date_edit, 0, 0)
        self._set_editable_cell_widget(0, 0, date_edit)

        # Ticker cell - column 1
        ticker_edit = AutoSelectLineEdit(blank_transaction["ticker"])
        ticker_edit.setPlaceholderText("Enter ticker...")
        ticker_edit.setStyleSheet(widget_style)
        ticker_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(ticker_edit, 0, 1)
        self._set_editable_cell_widget(0, 1, ticker_edit)

        # Name cell (read-only, styled like editable) - column 2
        name_edit = AutoSelectLineEdit("")
        name_edit.setReadOnly(True)
        name_edit.setStyleSheet(widget_style)
        self._set_widget_position(name_edit, 0, 2)
        self._set_editable_cell_widget(0, 2, name_edit)

        # Quantity cell - column 3
        qty_edit = ValidatedNumericLineEdit(min_value=0.0001, max_value=999999999, decimals=4, prefix="", show_dash_for_zero=True)
        qty_edit.setValue(blank_transaction["quantity"])
        qty_edit.setStyleSheet(widget_style)
        qty_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(qty_edit, 0, 3)
        self._set_editable_cell_widget(0, 3, qty_edit)

        # Execution Price cell - column 4
        price_edit = ValidatedNumericLineEdit(min_value=0, max_value=1000000, decimals=2, prefix="", show_dash_for_zero=True)
        price_edit.setValue(blank_transaction["entry_price"])
        price_edit.setStyleSheet(widget_style)
        price_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(price_edit, 0, 4)
        self._set_editable_cell_widget(0, 4, price_edit)

        # Fees cell - column 5
        fees_edit = ValidatedNumericLineEdit(min_value=0, max_value=10000, decimals=2, prefix="", show_dash_for_zero=True)
        fees_edit.setValue(blank_transaction["fees"])
        fees_edit.setStyleSheet(widget_style)
        fees_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(fees_edit, 0, 5)
        self._set_editable_cell_widget(0, 5, fees_edit)

        # Type cell - column 6
        type_combo = NoScrollComboBox()
        type_combo.addItems(["Buy", "Sell"])
        type_combo.setCurrentIndex(-1)  # No selection initially
        type_combo.setPlaceholderText("Buy/Sell")
        type_combo.currentTextChanged.connect(self._on_widget_changed)
        type_combo.setStyleSheet(combo_style)
        self._set_widget_position(type_combo, 0, 6)
        self._set_editable_cell_widget(0, 6, type_combo)

        # Daily Closing Price cell (read-only) - column 7
        daily_close_item = QTableWidgetItem("--")
        daily_close_item.setFlags(daily_close_item.flags() & ~Qt.ItemIsEditable)
        daily_close_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(0, 7, daily_close_item)

        # Live Price cell (read-only) - column 8
        live_price_item = QTableWidgetItem("--")
        live_price_item.setFlags(live_price_item.flags() & ~Qt.ItemIsEditable)
        live_price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(0, 8, live_price_item)

        # Principal cell (read-only) - column 9
        principal_item = QTableWidgetItem("--")
        principal_item.setFlags(principal_item.flags() & ~Qt.ItemIsEditable)
        principal_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(0, 9, principal_item)

        # Market Value cell (read-only) - column 10
        market_value_item = QTableWidgetItem("--")
        market_value_item.setFlags(market_value_item.flags() & ~Qt.ItemIsEditable)
        market_value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(0, 10, market_value_item)

        # Install focus watchers for auto-delete functionality
        self._install_focus_watcher(0)

        # Set up tab order for keyboard navigation
        self._setup_tab_order(0)

        # Update row positions for all shifted rows (rows 1+)
        self._update_row_positions(1)

        self.setSortingEnabled(False)  # Keep sorting disabled for manual control

        # Ensure FREE CASH summary row exists after blank row
        self._ensure_free_cash_summary_row()

    def _ensure_free_cash_summary_row(self):
        """
        Ensure FREE CASH summary row exists at index 1 (below blank row).
        Creates if missing, updates values if exists.
        """
        # First, scan the table to find any existing FREE CASH summary row
        actual_row = None
        for row in range(self.rowCount()):
            # Check if this row has "FREE CASH" as ticker in column 1 (QTableWidgetItem)
            ticker_item = self.item(row, 1)
            if ticker_item and ticker_item.text() == "FREE CASH":
                # Also verify it's the summary row by checking if column 0 has no widget
                if self.cellWidget(row, 0) is None:
                    actual_row = row
                    break

        # If summary row exists in table, update mappings and return
        if actual_row is not None:
            # Remove any stale mappings to FREE CASH row ID
            for r in list(self._row_to_id.keys()):
                if self._row_to_id[r] == self._free_cash_row_id:
                    del self._row_to_id[r]
                    if r in self._transactions:
                        del self._transactions[r]
                    break

            # Ensure entry exists in _transactions_by_id
            if self._free_cash_row_id not in self._transactions_by_id:
                self._transactions_by_id[self._free_cash_row_id] = {
                    "id": self._free_cash_row_id,
                    "is_free_cash_summary": True,
                    "date": "",
                    "ticker": "FREE CASH",
                    "transaction_type": "",
                    "quantity": 0.0,
                    "entry_price": 0.0,
                    "fees": 0.0
                }

            # Set correct mapping
            self._row_to_id[actual_row] = self._free_cash_row_id
            self._transactions[actual_row] = self._transactions_by_id[self._free_cash_row_id]

            # Update calculated values
            self._update_free_cash_summary_row()

            # Apply hidden state if setting is enabled
            self.setRowHidden(actual_row, self._hide_free_cash_summary)
            return

        # No summary row found in table - clean up any stale data and create new one
        if self._free_cash_row_id in self._transactions_by_id:
            del self._transactions_by_id[self._free_cash_row_id]
        for r in list(self._row_to_id.keys()):
            if self._row_to_id[r] == self._free_cash_row_id:
                del self._row_to_id[r]
                if r in self._transactions:
                    del self._transactions[r]
                break

        # Need to insert FREE CASH summary row at index 1
        # First shift all existing rows down (except blank row at 0)
        new_row_to_id = {0: self._row_to_id.get(0)}  # Keep blank row mapping
        new_transactions = {0: self._transactions.get(0)}  # Keep blank row data
        new_row_widgets_map = {0: self._row_widgets_map.get(0)} if 0 in self._row_widgets_map else {}

        for old_row in range(1, self.rowCount()):
            new_row = old_row + 1  # Shift down by 1
            if old_row in self._row_to_id:
                new_row_to_id[new_row] = self._row_to_id[old_row]
            if old_row in self._transactions:
                new_transactions[new_row] = self._transactions[old_row]
            if old_row in self._row_widgets_map:
                new_row_widgets_map[new_row] = self._row_widgets_map[old_row]

        # Insert row at index 1
        self.insertRow(1)
        self.setRowHeight(1, 48)

        # Set blank vertical header (no row number)
        blank_header = QTableWidgetItem("")
        self.setVerticalHeaderItem(1, blank_header)

        # Apply shifted mappings
        self._row_to_id = new_row_to_id
        self._transactions = new_transactions
        self._row_widgets_map = new_row_widgets_map

        # Create FREE CASH summary transaction entry
        free_cash_summary = {
            "id": self._free_cash_row_id,
            "is_free_cash_summary": True,
            "date": "",
            "ticker": "FREE CASH",
            "transaction_type": "",
            "quantity": 0.0,
            "entry_price": 0.0,
            "fees": 0.0
        }

        # Store FREE CASH summary
        self._transactions_by_id[self._free_cash_row_id] = free_cash_summary
        self._row_to_id[1] = self._free_cash_row_id
        self._transactions[1] = free_cash_summary

        # Create read-only cells (no editable widgets, no highlight)
        # Date cell (empty) - col 0
        date_item = QTableWidgetItem("")
        date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
        date_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 0, date_item)

        # Ticker cell ("FREE CASH") - col 1
        ticker_item = QTableWidgetItem("FREE CASH")
        ticker_item.setFlags(ticker_item.flags() & ~Qt.ItemIsEditable)
        ticker_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 1, ticker_item)

        # Name cell ("FREE CASH") - col 2
        name_item = QTableWidgetItem("FREE CASH")
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 2, name_item)

        # Quantity cell (calculated) - col 3
        qty_item = QTableWidgetItem("--")
        qty_item.setFlags(qty_item.flags() & ~Qt.ItemIsEditable)
        qty_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 3, qty_item)

        # Execution Price cell (empty) - col 4
        price_item = QTableWidgetItem("")
        price_item.setFlags(price_item.flags() & ~Qt.ItemIsEditable)
        price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 4, price_item)

        # Fees cell (empty) - col 5
        fees_item = QTableWidgetItem("")
        fees_item.setFlags(fees_item.flags() & ~Qt.ItemIsEditable)
        fees_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 5, fees_item)

        # Type cell (empty) - col 6
        type_item = QTableWidgetItem("")
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        type_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 6, type_item)

        # Daily Closing Price cell (empty) - col 7
        daily_item = QTableWidgetItem("")
        daily_item.setFlags(daily_item.flags() & ~Qt.ItemIsEditable)
        daily_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 7, daily_item)

        # Live Price cell (empty) - col 8
        live_item = QTableWidgetItem("")
        live_item.setFlags(live_item.flags() & ~Qt.ItemIsEditable)
        live_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 8, live_item)

        # Principal cell (calculated) - col 9
        principal_item = QTableWidgetItem("--")
        principal_item.setFlags(principal_item.flags() & ~Qt.ItemIsEditable)
        principal_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 9, principal_item)

        # Market Value cell (calculated) - col 10
        mv_item = QTableWidgetItem("--")
        mv_item.setFlags(mv_item.flags() & ~Qt.ItemIsEditable)
        mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 10, mv_item)

        # Update row positions for shifted rows (rows 2+)
        self._update_row_positions(2)

        # Update calculated values
        self._update_free_cash_summary_row()

        # Apply hidden state if setting is enabled
        self.setRowHidden(1, self._hide_free_cash_summary)

    def _update_free_cash_summary_row(self):
        """Update FREE CASH summary row with calculated values."""
        # Find the FREE CASH summary row by scanning the table
        # (don't rely on _row_to_id which can be stale after row operations)
        row = None
        for r in range(self.rowCount()):
            # Check if this row has "FREE CASH" as ticker in column 1 (QTableWidgetItem, not widget)
            ticker_item = self.item(r, 1)
            if ticker_item and ticker_item.text() == "FREE CASH":
                # Verify it's the summary row by checking if column 0 has no widget (date widget)
                if self.cellWidget(r, 0) is None:
                    row = r
                    break

        if row is None:
            return  # Summary row doesn't exist yet

        # Get all real transactions (excluding blank and summary rows)
        transactions = self.get_all_transactions()

        # Calculate summary values
        summary = PortfolioService.calculate_free_cash_summary(transactions)

        # Update Quantity (col 3)
        qty_item = self.item(row, 3)
        if qty_item:
            qty = summary["quantity"]
            if qty != 0:
                qty_item.setText(f"${qty:,.2f}")
            else:
                qty_item.setText("--")

        # Principal (col 9) - leave blank for FREE CASH summary
        principal_item = self.item(row, 9)
        if principal_item:
            principal_item.setText("")

        # Update Market Value (col 10)
        mv_item = self.item(row, 10)
        if mv_item:
            mv = summary["market_value"]
            if mv != 0:
                mv_item.setText(f"${mv:,.2f}")
            else:
                mv_item.setText("--")

    def _is_transaction_complete(self, transaction: Dict[str, Any]) -> bool:
        """
        Check if transaction has all required fields filled.

        Args:
            transaction: Transaction dict

        Returns:
            True if ticker, qty > 0, entry_price >= 0, and valid transaction_type
        """
        ticker = transaction.get("ticker", "").strip()
        quantity = transaction.get("quantity", 0.0)
        entry_price = transaction.get("entry_price", 0.0)
        transaction_type = transaction.get("transaction_type", "")

        return (
            ticker != "" and
            quantity > 0 and
            entry_price >= 0 and  # Allow 0 for gifts
            transaction_type in ("Buy", "Sell")  # Must select a valid type
        )

    def _transition_blank_to_real(self, row: int, transaction: Dict[str, Any]) -> bool:
        """
        Convert blank row to real transaction and create new blank.

        Args:
            row: Row index of blank row
            transaction: Updated transaction data

        Returns:
            True if transition succeeded, False if validation failed
        """
        import uuid

        # Normalize ticker before validation (but don't modify other fields yet)
        ticker_normalized = transaction["ticker"].upper().strip()

        # Create a temporary copy for validation (don't mutate original yet)
        temp_transaction = dict(transaction)
        temp_transaction["id"] = str(uuid.uuid4())
        temp_transaction["is_blank"] = False
        temp_transaction["ticker"] = ticker_normalized

        # For FREE CASH ticker, auto-set execution price to $1.00
        if ticker_normalized == PortfolioService.FREE_CASH_TICKER:
            temp_transaction["entry_price"] = 1.0

        # Validate transaction safeguards (cash balance, position)
        # Set _validating to prevent _on_cell_changed from corrupting sequences
        self._validating = True
        try:
            is_valid, error_msg = self._validate_transaction_safeguards(row, temp_transaction, is_new=True)
        finally:
            self._validating = False
        if not is_valid:
            # Set flag to prevent double dialog from focus loss
            self._skip_focus_validation = True
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Transaction Error",
                error_msg
            )
            # Set flag again after dialog (dialog may have triggered focus events that reset it)
            self._skip_focus_validation = True
            return False  # Don't transition - keep as blank row (original transaction unchanged)

        # Validation passed - now apply changes to original transaction
        transaction["id"] = temp_transaction["id"]
        transaction["is_blank"] = False
        transaction["ticker"] = ticker_normalized
        if ticker_normalized == PortfolioService.FREE_CASH_TICKER:
            transaction["entry_price"] = 1.0

        # Assign sequence number for same-day ordering (higher = newer)
        transaction["sequence"] = self._get_next_sequence()

        # Clear user-entered price tracking for this row (new blank row starts fresh)
        self._user_entered_price_rows.discard(row)

        # Remove old blank entry from storage
        if "BLANK_ROW" in self._transactions_by_id:
            del self._transactions_by_id["BLANK_ROW"]
        if row in self._row_to_id:
            del self._row_to_id[row]
        if row in self._transactions:
            del self._transactions[row]
        if row in self._row_widgets_map:
            del self._row_widgets_map[row]

        # Remove the blank row from the table
        self.removeRow(row)

        # Shift _transactions indices down for rows that moved after removeRow
        # This is necessary because _rebuild_transaction_map relies on _transactions
        new_transactions = {}
        for old_row, tx in self._transactions.items():
            if old_row > row:
                new_transactions[old_row - 1] = tx
            elif old_row < row:
                new_transactions[old_row] = tx
            # old_row == row was already deleted, skip it
        self._transactions = new_transactions

        # Also shift _row_to_id and _row_widgets_map
        new_row_to_id = {}
        for old_row, tx_id in self._row_to_id.items():
            if old_row > row:
                new_row_to_id[old_row - 1] = tx_id
            elif old_row < row:
                new_row_to_id[old_row] = tx_id
        self._row_to_id = new_row_to_id

        new_row_widgets_map = {}
        for old_row, widgets in self._row_widgets_map.items():
            if old_row > row:
                new_row_widgets_map[old_row - 1] = widgets
            elif old_row < row:
                new_row_widgets_map[old_row] = widgets
        self._row_widgets_map = new_row_widgets_map

        # Rebuild mappings after row removal
        self._rebuild_transaction_map()

        # Create new blank row at top (also ensures FREE CASH summary at row 1)
        self._ensure_blank_row()

        # Use binary insertion to add transaction at correct sorted position
        # This avoids full table rebuild - O(log n) search + O(1) widget creation
        insertion_pos = self._find_insertion_position(transaction)
        self._insert_transaction_at_position(transaction, insertion_pos)

        # Emit signal
        self.transaction_added.emit(transaction)

        # Update FREE CASH summary row
        self._update_free_cash_summary_row()

        # Increment focus generation to invalidate pending deferred callbacks
        # (same as sort_by_date_descending would do)
        self._focus_generation += 1

        return True  # Transition succeeded

    def add_transaction_row(self, transaction: Dict[str, Any]) -> int:
        """
        Add a new transaction row.

        Args:
            transaction: Transaction dict

        Returns:
            Row index
        """
        # Disable sorting while adding row
        self.setSortingEnabled(False)

        row = self.rowCount()
        self.insertRow(row)
        self.setRowHeight(row, 48)  # Ensure consistent row height

        # Set row label (row number excludes blank row at 0 and FREE CASH summary at 1)
        # Row 2 = label "1", Row 3 = label "2", etc.
        row_header = QTableWidgetItem(str(row - 1))
        self.setVerticalHeaderItem(row, row_header)

        # Store transaction in UUID-based storage
        tx_id = transaction["id"]
        self._transactions_by_id[tx_id] = transaction
        self._row_to_id[row] = tx_id

        # Also store in legacy dict for backwards compatibility
        self._transactions[row] = transaction

        # Store original values for revert on invalid edit
        # Only set if not already tracked - preserves values from successful edits
        # (sort_by_date_descending calls add_transaction_row but shouldn't overwrite
        # the _original_values that were just set after a successful edit)
        if tx_id not in self._original_values:
            self._debug_set_original_values(tx_id, {
                "ticker": transaction.get("ticker", ""),
                "date": transaction.get("date", ""),
                "quantity": transaction.get("quantity", 0.0),
                "entry_price": transaction.get("entry_price", 0.0),
                "fees": transaction.get("fees", 0.0),
                "transaction_type": transaction.get("transaction_type", "Buy"),
                "sequence": transaction.get("sequence", 0)
            }, "add_transaction_row")
        elif self._debug_original_values:
            print(f"[ORIGINAL_VALUES] add_transaction_row: SKIPPED tx_id={tx_id[:8]}... "
                  f"(already tracked with date={self._original_values[tx_id].get('date')})")

        # Create widgets using shared helper
        self._create_transaction_row_widgets(row, transaction)

        # Update FREE CASH summary - all transactions affect cash balance
        # (Buy costs cash, Sell adds cash, FREE CASH deposits/withdrawals)
        # Skip during batch loading to avoid O(N²) performance - will update once at end
        if not self._batch_loading:
            self._update_free_cash_summary_row()

        return row

    def _create_transaction_row_widgets(self, row: int, transaction: Dict[str, Any]):
        """
        Create all widgets for a transaction row.

        This is the widget creation logic extracted from add_transaction_row() for reuse
        by both add_transaction_row() and _insert_transaction_at_position().

        Args:
            row: Row index
            transaction: Transaction dict
        """
        # Get current theme stylesheets
        widget_style = self._get_widget_stylesheet()
        combo_style = self._get_combo_stylesheet()

        # Date cell - column 0
        date_edit = DateInputWidget()
        date_edit.validation_error.connect(self._on_date_validation_error)
        date_edit.setDate(QDate.fromString(transaction["date"], "yyyy-MM-dd"))
        date_edit.setStyleSheet(widget_style)
        date_edit.date_changed.connect(self._on_widget_changed)
        self._set_widget_position(date_edit, row, 0)
        self._set_editable_cell_widget(row, 0, date_edit)

        # Ticker cell - column 1
        ticker_edit = AutoSelectLineEdit(transaction["ticker"])
        ticker_edit.setStyleSheet(widget_style)
        ticker_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(ticker_edit, row, 1)
        self._set_editable_cell_widget(row, 1, ticker_edit)

        # Name cell (read-only, styled like editable) - column 2
        ticker = transaction["ticker"]
        if ticker.upper() == PortfolioService.FREE_CASH_TICKER:
            name = "FREE CASH"
        else:
            name = self._cached_names.get(ticker, "")
        name_edit = AutoSelectLineEdit(name)
        name_edit.setReadOnly(True)
        name_edit.setStyleSheet(widget_style)
        self._set_widget_position(name_edit, row, 2)
        self._set_editable_cell_widget(row, 2, name_edit)

        # Quantity cell - column 3
        qty_edit = ValidatedNumericLineEdit(min_value=0.0001, max_value=999999999, decimals=4, prefix="", show_dash_for_zero=True)
        qty_edit.setValue(transaction["quantity"])
        qty_edit.setStyleSheet(widget_style)
        qty_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(qty_edit, row, 3)
        self._set_editable_cell_widget(row, 3, qty_edit)

        # Execution Price cell - column 4
        price_edit = ValidatedNumericLineEdit(min_value=0, max_value=1000000, decimals=2, prefix="", show_dash_for_zero=True)
        price_edit.setValue(transaction["entry_price"])
        price_edit.setStyleSheet(widget_style)
        price_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(price_edit, row, 4)
        self._set_editable_cell_widget(row, 4, price_edit)

        # Fees cell - column 5
        fees_edit = ValidatedNumericLineEdit(min_value=0, max_value=10000, decimals=2, prefix="", show_dash_for_zero=True)
        fees_edit.setValue(transaction["fees"])
        fees_edit.setStyleSheet(widget_style)
        fees_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(fees_edit, row, 5)
        self._set_editable_cell_widget(row, 5, fees_edit)

        # Type cell - column 6
        type_combo = NoScrollComboBox()
        type_combo.addItems(["Buy", "Sell"])
        type_combo.setCurrentText(transaction["transaction_type"])
        type_combo.currentTextChanged.connect(self._on_widget_changed)
        type_combo.setStyleSheet(combo_style)
        self._set_widget_position(type_combo, row, 6)
        self._set_editable_cell_widget(row, 6, type_combo)

        # Daily Closing Price cell (read-only) - column 7
        daily_close_item = QTableWidgetItem("--")
        daily_close_item.setFlags(daily_close_item.flags() & ~Qt.ItemIsEditable)
        daily_close_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 7, daily_close_item)

        # Live Price cell (read-only) - column 8
        live_price_item = QTableWidgetItem("--")
        live_price_item.setFlags(live_price_item.flags() & ~Qt.ItemIsEditable)
        live_price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 8, live_price_item)

        # Principal cell (read-only) - column 9
        principal_item = QTableWidgetItem("--")
        principal_item.setFlags(principal_item.flags() & ~Qt.ItemIsEditable)
        principal_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 9, principal_item)

        # Market Value cell (read-only) - column 10
        market_value_item = QTableWidgetItem("--")
        market_value_item.setFlags(market_value_item.flags() & ~Qt.ItemIsEditable)
        market_value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 10, market_value_item)

        # Install focus watchers for auto-delete functionality
        self._install_focus_watcher(row)

        # Set up tab order for keyboard navigation
        self._setup_tab_order(row)

    def _insert_transaction_at_position(self, transaction: Dict[str, Any], pos: int) -> int:
        """
        Insert a transaction at a specific row position without rebuilding the table.

        This is O(n) for mapping shifts but O(1) for widget operations.

        Args:
            transaction: Transaction dict to insert
            pos: Row index to insert at

        Returns:
            The actual row index where transaction was inserted
        """
        tx_id = transaction["id"]

        # 1. Shift all mappings for rows >= pos BEFORE inserting
        # This must happen before insertRow() because Qt shifts visual rows automatically
        new_row_to_id = {}
        new_transactions = {}
        new_row_widgets_map = {}

        for old_row in sorted(self._row_to_id.keys(), reverse=True):
            if old_row >= pos:
                new_row_to_id[old_row + 1] = self._row_to_id[old_row]
            else:
                new_row_to_id[old_row] = self._row_to_id[old_row]

        for old_row in sorted(self._transactions.keys(), reverse=True):
            if old_row >= pos:
                new_transactions[old_row + 1] = self._transactions[old_row]
            else:
                new_transactions[old_row] = self._transactions[old_row]

        for old_row in sorted(self._row_widgets_map.keys(), reverse=True):
            if old_row >= pos:
                new_row_widgets_map[old_row + 1] = self._row_widgets_map[old_row]
            else:
                new_row_widgets_map[old_row] = self._row_widgets_map[old_row]

        self._row_to_id = new_row_to_id
        self._transactions = new_transactions
        self._row_widgets_map = new_row_widgets_map

        # 2. Insert the row in Qt table
        self.setSortingEnabled(False)
        self.insertRow(pos)
        self.setRowHeight(pos, 48)

        # 3. Set row header (row number excludes blank row at 0 and FREE CASH summary at 1)
        row_header = QTableWidgetItem(str(pos - 1))
        self.setVerticalHeaderItem(pos, row_header)

        # 4. Store transaction in mappings
        self._transactions_by_id[tx_id] = transaction
        self._row_to_id[pos] = tx_id
        self._transactions[pos] = transaction

        # 5. Store original values for revert on invalid edit
        if tx_id not in self._original_values:
            self._debug_set_original_values(tx_id, {
                "ticker": transaction.get("ticker", ""),
                "date": transaction.get("date", ""),
                "quantity": transaction.get("quantity", 0.0),
                "entry_price": transaction.get("entry_price", 0.0),
                "fees": transaction.get("fees", 0.0),
                "transaction_type": transaction.get("transaction_type", "Buy"),
                "sequence": transaction.get("sequence", 0)
            }, "_insert_transaction_at_position")

        # 6. Create widgets using shared helper
        self._create_transaction_row_widgets(pos, transaction)

        # 7. Update calculated cells for this row
        self._update_calculated_cells(pos)

        # 8. Update row headers for shifted rows (pos+1 onwards)
        for row in range(pos + 1, self.rowCount()):
            tx = self._get_transaction_for_row(row)
            if tx and not tx.get("is_blank") and not tx.get("is_free_cash_summary"):
                header_item = QTableWidgetItem(str(row - 1))
                self.setVerticalHeaderItem(row, header_item)

        return pos

    def _on_cell_changed(self, row: int, col: int):
        """Handle cell value change."""
        # Skip during validation to prevent sequence corruption from stale data
        if self._validating:
            return

        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        # Extract updated values
        updated = self._extract_transaction_from_row(row)
        if not updated:
            return


        # Check if this is the blank row
        if transaction.get("is_blank"):
            # Just update stored values without transitioning
            # Transition will happen on focus loss or Enter key to avoid lag while typing
            self._transactions_by_id["BLANK_ROW"].update(updated)
            self._transactions[row] = updated
            return

        # Normal transaction modification (not blank row)
        transaction_id = transaction["id"]

        # Always update stored transaction (even if invalid)
        # This allows focus loss detection to see empty tickers and delete the row
        self._transactions_by_id[transaction_id] = updated
        self._transactions[row] = updated

        # DON'T fetch prices here - that happens on focus loss only
        # This prevents lag when typing/deleting ticker symbols

    def _extract_transaction_from_row(self, row: int) -> Dict[str, Any]:
        """
        Extract transaction data from row widgets.

        Args:
            row: Row index

        Returns:
            Transaction dict or None if extraction fails
        """
        if row not in self._transactions:
            return None

        # Get existing transaction to preserve flags like is_blank
        existing_transaction = self._transactions[row]
        transaction_id = existing_transaction["id"]

        try:
            # Get inner widgets from cells (unwrap containers)
            date_edit = self._get_inner_widget(row, 0)
            ticker_edit = self._get_inner_widget(row, 1)
            # Column 2 is Name (read-only)
            qty_spin = self._get_inner_widget(row, 3)
            price_spin = self._get_inner_widget(row, 4)
            fees_spin = self._get_inner_widget(row, 5)
            type_combo = self._get_inner_widget(row, 6)
            # Columns 7-10 are read-only items, not widgets

            if not all([date_edit, ticker_edit, type_combo, qty_spin, price_spin, fees_spin]):
                return None

            extracted = {
                "id": transaction_id,
                "date": date_edit.date().toString("yyyy-MM-dd"),
                "ticker": ticker_edit.text().strip().upper(),
                "transaction_type": type_combo.currentText(),
                "quantity": qty_spin.value(),
                "entry_price": price_spin.value(),
                "fees": fees_spin.value()
            }

            # Preserve is_blank flag if it exists
            if "is_blank" in existing_transaction:
                extracted["is_blank"] = existing_transaction["is_blank"]

            # Preserve sequence for same-day ordering - use _transactions_by_id as source of truth
            if transaction_id in self._transactions_by_id:
                extracted["sequence"] = self._transactions_by_id[transaction_id].get("sequence", 0)
            elif "sequence" in existing_transaction:
                extracted["sequence"] = existing_transaction["sequence"]

            return extracted
        except Exception as e:
            print(f"Error extracting transaction from row {row}: {e}")
            return None

    def _update_calculated_cells(self, row: int):
        """
        Update calculated cells: Daily Closing Price, Live Price, Principal, Market Value.

        Args:
            row: Row index
        """
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        # Skip FREE CASH summary row (it's handled separately)
        if transaction.get("is_free_cash_summary"):
            return

        ticker = transaction.get("ticker", "")
        tx_date = transaction.get("date", "")
        quantity = transaction.get("quantity", 0.0)

        # Check if this is a FREE CASH transaction
        is_free_cash = ticker.upper() == PortfolioService.FREE_CASH_TICKER

        # --- Daily Closing Price (col 7) ---
        item_7 = self.item(row, 7)
        if item_7:
            if is_free_cash:
                # FREE CASH: show blank (price is always $1, redundant to display)
                item_7.setText("")
            elif ticker and tx_date and ticker in self._historical_prices:
                daily_close = self._historical_prices[ticker].get(tx_date)
                if daily_close is not None:
                    item_7.setText(f"${daily_close:,.2f}")
                else:
                    item_7.setText("--")
            else:
                item_7.setText("--")

        # --- Live Price (col 8) ---
        item_8 = self.item(row, 8)
        if item_8:
            if is_free_cash:
                # FREE CASH: show blank (price is always $1, redundant to display)
                item_8.setText("")
            else:
                live_price = self._current_prices.get(ticker)
                if live_price is not None:
                    item_8.setText(f"${live_price:,.2f}")
                else:
                    item_8.setText("--")

        # --- Principal (col 9) ---
        item_9 = self.item(row, 9)
        if item_9:
            if is_free_cash:
                # FREE CASH: leave principal blank (not applicable)
                item_9.setText("")
            else:
                principal = PortfolioService.calculate_principal(transaction)

                if principal != 0:
                    # Format with sign: negative for buys, positive for sells
                    if principal < 0:
                        item_9.setText(f"-${abs(principal):,.2f}")
                    else:
                        item_9.setText(f"${principal:,.2f}")
                else:
                    item_9.setText("--")

        # --- Market Value (col 10) ---
        item_10 = self.item(row, 10)
        if item_10:
            if is_free_cash:
                # FREE CASH: market value = quantity (since price is $1)
                if quantity > 0:
                    item_10.setText(f"${quantity:,.2f}")
                else:
                    item_10.setText("--")
            else:
                live_price = self._current_prices.get(ticker)
                if live_price is not None and quantity > 0:
                    market_value = live_price * quantity
                    item_10.setText(f"${market_value:,.2f}")
                else:
                    item_10.setText("--")

    def update_current_prices(self, prices: Dict[str, float]):
        """
        Update current prices and recalculate all rows.

        Args:
            prices: Dict mapping ticker -> price
        """
        self._current_prices = prices
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

    def update_historical_prices(self, historical_prices: Dict[str, Dict[str, float]]):
        """
        Update historical prices cache and recalculate all rows.

        Args:
            historical_prices: Dict mapping ticker -> {date -> close_price}
        """
        self._historical_prices = historical_prices
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

    def fetch_historical_prices_batch(self):
        """
        Fetch historical closing prices for all transactions in batch.
        Called on portfolio load and when transactions change.
        Only fetches prices for ticker/date pairs not already cached.
        """
        from typing import List, Tuple

        # Collect all ticker/date pairs that need fetching
        ticker_dates_to_fetch: List[Tuple[str, str]] = []
        for row in range(self.rowCount()):
            tx = self._get_transaction_for_row(row)
            if tx and not tx.get("is_blank"):
                ticker = tx.get("ticker", "")
                tx_date = tx.get("date", "")
                if ticker and tx_date:
                    # Only fetch if not already cached
                    if ticker not in self._historical_prices or tx_date not in self._historical_prices.get(ticker, {}):
                        ticker_dates_to_fetch.append((ticker, tx_date))

        # Fetch only new ticker/date pairs
        if ticker_dates_to_fetch:
            new_prices = PortfolioService.fetch_historical_closes_batch(ticker_dates_to_fetch)
            # Merge into existing cache
            for ticker, dates in new_prices.items():
                if ticker not in self._historical_prices:
                    self._historical_prices[ticker] = {}
                self._historical_prices[ticker].update(dates)

        # Update all calculated cells
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """
        Get all transactions from table (excluding blank row and FREE CASH summary).

        Returns:
            List of transaction dicts
        """
        transactions = []
        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            # Filter out blank row and FREE CASH summary row
            if tx and not tx.get("is_blank") and not tx.get("is_free_cash_summary"):
                transactions.append(tx)
        return transactions

    def clear_all_transactions(self):
        """Clear all transactions from table."""
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()  # Clear legacy storage too
        self._user_entered_price_rows.clear()  # Clear price tracking
        self._current_prices.clear()  # Clear current prices cache
        self._historical_prices.clear()  # Clear historical prices cache
        self._original_values.clear()  # Clear original values tracking
        self._reset_column_widths()  # Ensure consistent column widths

    def delete_selected_rows(self):
        """Delete selected rows and emit signals."""
        selected_rows = sorted(set(idx.row() for idx in self.selectedIndexes()), reverse=True)

        # Get all current transactions for validation
        all_transactions = self.get_all_transactions()
        deleted_any = False

        for row in selected_rows:
            # Get transaction using UUID-based lookup
            transaction = self._get_transaction_for_row(row)
            if transaction:
                # Skip blank rows and FREE CASH summary row
                if transaction.get("is_blank") or transaction.get("is_summary"):
                    continue

                transaction_id = transaction["id"]

                # Validate that deletion won't break the portfolio
                can_delete, error_msg = PortfolioService.validate_transaction_deletion(
                    all_transactions, transaction
                )
                if not can_delete:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Cannot Delete Transaction",
                        error_msg
                    )
                    continue  # Skip this deletion, try next selected row

                # Remove from UUID-based storage
                if transaction_id in self._transactions_by_id:
                    del self._transactions_by_id[transaction_id]

                # Remove from original values tracking
                if transaction_id in self._original_values:
                    del self._original_values[transaction_id]

                # Remove from row mapping
                if row in self._row_to_id:
                    del self._row_to_id[row]

                # Remove from legacy storage
                if row in self._transactions:
                    del self._transactions[row]

                # Remove from all_transactions for subsequent validation
                all_transactions = [tx for tx in all_transactions if tx.get("id") != transaction_id]

                # Remove row from table
                self.removeRow(row)

                # Emit signal
                self.transaction_deleted.emit(transaction_id)
                deleted_any = True

        if deleted_any:
            # Rebuild transaction map (row indices shifted after deletion)
            self._rebuild_transaction_map()

            # Also rebuild legacy map
            new_transactions = {}
            for row in range(self.rowCount()):
                tx = self._get_transaction_for_row(row)
                if tx:
                    new_transactions[row] = tx
            self._transactions = new_transactions

            # Update all stored row positions after deletion
            self._update_row_positions(0)

            # Update FREE CASH summary row
            self._update_free_cash_summary_row()

    def _update_row_positions(self, start_row: int):
        """
        Update stored row positions for all widgets from start_row onwards.
        Called after row insertion/deletion to keep positions in sync.

        Args:
            start_row: First row to update
        """
        for row in range(start_row, self.rowCount()):
            for col in range(7):  # Columns 0-6 have widgets
                # Update inner widget position (signals are connected to inner widgets)
                inner_widget = self._get_inner_widget(row, col)
                if inner_widget:
                    inner_widget.setProperty("_table_row", row)

    def _on_widget_changed(self):
        """
        Generic handler for widget value changes.
        Uses sender() to find which widget changed, then looks up its position.
        """
        widget = self.sender()
        if not widget:
            return

        row, col = self._find_cell_for_widget(widget)
        if row is not None and col is not None:
            # Track if user manually entered execution price (col 4)
            # This prevents auto-fill from overwriting user input
            if col == 4:
                transaction = self._get_transaction_for_row(row)
                if transaction and transaction.get("is_blank"):
                    self._user_entered_price_rows.add(row)

            self._on_cell_changed(row, col)

    def _on_date_validation_error(self, title: str, message: str):
        """Handle date validation errors from DateInputWidget."""
        CustomMessageBox.warning(
            self.theme_manager,
            self,
            title,
            message
        )

    def _install_focus_watcher(self, row: int):
        """
        Install event filters on all widgets in a row for focus tracking.

        Args:
            row: Row index to install watchers on
        """
        widgets = []

        # Install event filters on all editable columns (0-6)
        for col in range(7):
            container = self.cellWidget(row, col)
            if container:
                # Get the inner widget (the actual editable widget, not the container)
                inner_widget = container.property("_inner_widget")
                if inner_widget:
                    inner_widget.installEventFilter(self)
                    widgets.append(inner_widget)
                else:
                    # Fallback if no inner widget (shouldn't happen)
                    container.installEventFilter(self)
                    widgets.append(container)

        # Store widget references for this row
        self._row_widgets_map[row] = widgets

    def _setup_tab_order(self, row: int):
        """
        Set up tab order for widgets in a row.

        Args:
            row: Row index to set up tab order for
        """
        # Get inner widgets for columns 0-6 (editable fields)
        widgets = []
        for col in range(7):
            inner = self._get_inner_widget(row, col)
            if inner:
                widgets.append(inner)

        # Set up tab order: date -> ticker -> qty -> price -> fees -> type
        for i in range(len(widgets) - 1):
            self.setTabOrder(widgets[i], widgets[i + 1])

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """
        Handle focus and key events on row widgets.

        Args:
            obj: The widget that received the event
            event: The event

        Returns:
            False to allow normal event processing
        """
        event_type = event.type()

        if event_type == QEvent.FocusIn:
            # Focus entered a widget - find which row
            row = self._find_row_for_widget(obj)
            if row is not None:
                self._current_editing_row = row
                # Select this row visually (sync with table selection)
                self.selectRow(row)

        elif event_type == QEvent.FocusOut:
            # Check if ticker field (col 1) in blank row lost focus - trigger auto-fill
            row, col = self._find_cell_for_widget(obj)
            if row is not None and col == 1:  # Ticker column
                transaction = self._get_transaction_for_row(row)
                if transaction and transaction.get("is_blank"):
                    # Defer to allow focus to settle, then auto-fill price and name
                    QTimer.singleShot(0, lambda r=row: self._try_autofill_execution_price(r))
                    ticker_widget = self._get_inner_widget(row, 1)
                    if ticker_widget:
                        ticker = ticker_widget.text().strip()
                        if ticker:
                            QTimer.singleShot(0, lambda r=row, t=ticker: self._try_autofill_name(r, t))

            # Date column (col 0) lost focus - re-trigger auto-fill if ticker already filled
            elif row is not None and col == 0:  # Date column
                transaction = self._get_transaction_for_row(row)
                if transaction and transaction.get("is_blank"):
                    ticker = transaction.get("ticker", "").strip()
                    if ticker:  # Only if ticker already entered
                        QTimer.singleShot(0, lambda r=row: self._try_autofill_execution_price(r))

            # Focus left a widget - defer check to see if it left the row
            # Capture current generation so we can detect if a sort/edit invalidated this callback
            gen = self._focus_generation
            QTimer.singleShot(0, lambda g=gen: self._check_row_focus_loss(g))

        elif event_type == QEvent.KeyPress:
            # Handle keyboard navigation
            from PySide6.QtGui import QKeyEvent
            key_event = event
            if isinstance(key_event, QKeyEvent):
                key = key_event.key()
                modifiers = key_event.modifiers()

                # Handle Tab key for field navigation
                if key == Qt.Key_Tab or key == Qt.Key_Backtab:
                    row, col = self._find_cell_for_widget(obj)
                    if row is not None and col is not None:
                        # Determine direction: Tab = forward, Shift+Tab = backward
                        if key == Qt.Key_Backtab or (modifiers & Qt.ShiftModifier):
                            next_col = col - 1
                            # Skip Name column (col 2) - it's read-only
                            if next_col == 2:
                                next_col = 1
                        else:
                            next_col = col + 1
                            # Skip Name column (col 2) - it's read-only
                            if next_col == 2:
                                next_col = 3

                        # Stay within editable columns (0-1, 3-6)
                        if 0 <= next_col <= 6 and next_col != 2:
                            next_widget = self._get_inner_widget(row, next_col)
                            if next_widget:
                                next_widget.setFocus()
                                return True  # Consume event
                        # If out of range, let default tab behavior happen
                    return False

                # Check for Enter/Return key (but NOT Shift+Enter - let that through for newlines)
                if key in (Qt.Key_Return, Qt.Key_Enter) and not (modifiers & Qt.ShiftModifier):
                    # Find which row this widget belongs to
                    row = self._find_row_for_widget(obj)
                    if row is not None:
                        # Get transaction
                        transaction = self._get_transaction_for_row(row)

                        # Check if blank row and complete - validate and transition if so
                        if transaction and transaction.get("is_blank"):
                            if self._is_transaction_complete(transaction):
                                # Validate ticker before transitioning
                                ticker = transaction.get("ticker", "").strip().upper()
                                tx_date = transaction.get("date", "")

                                # Validate ticker exists in Yahoo Finance
                                is_valid_ticker, ticker_error = PortfolioService.is_valid_ticker(ticker)
                                if not is_valid_ticker:
                                    self._skip_focus_validation = True  # Prevent double dialog
                                    CustomMessageBox.warning(
                                        self.theme_manager,
                                        self,
                                        "Invalid Ticker",
                                        ticker_error
                                    )
                                    return True  # Consume event, don't transition

                                # Validate trading day for stocks (non-crypto)
                                is_valid_day, day_error = PortfolioService.is_valid_trading_day(ticker, tx_date)
                                if not is_valid_day:
                                    self._skip_focus_validation = True  # Prevent double dialog
                                    CustomMessageBox.warning(
                                        self.theme_manager,
                                        self,
                                        "Invalid Trading Day",
                                        day_error
                                    )
                                    return True  # Consume event, don't transition

                                # Set flag before transition (in case dialog shows during validation)
                                self._skip_focus_validation = True
                                success = self._transition_blank_to_real(row, transaction)
                                if success:
                                    # Move focus to new blank row's ticker field (row 0, col 1)
                                    new_blank_ticker = self.cellWidget(0, 1)
                                    if new_blank_ticker:
                                        new_blank_ticker.setFocus()
                                # Keep flag set to prevent any pending focus handlers
                                self._skip_focus_validation = True
                                return True  # Consume event

                        # Handle normal rows (not blank)
                        if transaction and not transaction.get("is_blank"):
                            # Prevent _on_row_focus_lost from double-processing after clearFocus()
                            self._skip_focus_validation = True

                            ticker = transaction.get("ticker", "").strip()
                            quantity = transaction.get("quantity", 0.0)
                            tx_date = transaction.get("date", "")
                            transaction_id = transaction.get("id")

                            if not ticker or quantity == 0.0:
                                # Empty ticker or zero quantity - validate before deleting
                                # Use original values to check if deletion would break portfolio
                                original = self._original_values.get(transaction_id, {})
                                if original:
                                    # Build original transaction for validation
                                    original_tx = {
                                        "id": transaction_id,
                                        "ticker": original.get("ticker", ""),
                                        "date": original.get("date", ""),
                                        "quantity": original.get("quantity", 0.0),
                                        "entry_price": original.get("entry_price", 0.0),
                                        "fees": original.get("fees", 0.0),
                                        "transaction_type": original.get("transaction_type", "Buy")
                                    }
                                    all_transactions = self.get_all_transactions()
                                    can_delete, error_msg = PortfolioService.validate_transaction_deletion(
                                        all_transactions, original_tx
                                    )
                                    if not can_delete:
                                        self._skip_focus_validation = True
                                        CustomMessageBox.warning(
                                            self.theme_manager,
                                            self,
                                            "Cannot Delete Transaction",
                                            error_msg
                                        )
                                        # Revert to original values
                                        self._revert_all_fields(row, original)
                                        return True  # Consume event

                                # Validation passed or no original - delete row
                                self._delete_empty_row(row)
                                return True  # Consume event
                            else:
                                # Validate ticker and trading day
                                original = self._original_values.get(transaction_id, {})
                                original_ticker = original.get("ticker", "")
                                original_date = original.get("date", "")
                                ticker_upper = ticker.upper()

                                # Read date from widget TEXT (not _current_date) to get what user typed
                                # This is important because _current_date only updates on focusOut,
                                # but Enter key fires before focusOut
                                date_edit = self._get_inner_widget(row, 0)
                                if date_edit:
                                    # Read text directly and parse it
                                    date_text = date_edit.text() if hasattr(date_edit, 'text') else ""
                                    parsed_date = QDate.fromString(date_text, "yyyy-MM-dd")
                                    if parsed_date.isValid():
                                        tx_date = parsed_date.toString("yyyy-MM-dd")
                                        # Also update the widget's internal _current_date so that
                                        # subsequent reads (e.g., during sort) get the correct date
                                        date_edit.setDate(parsed_date)
                                    else:
                                        # Fallback to stored date if text is invalid/incomplete
                                        tx_date = date_edit.date().toString("yyyy-MM-dd")
                                    # Update transaction dict with current date for validation
                                    transaction["date"] = tx_date
                                else:
                                    tx_date = transaction.get("date", "")

                                # Check if ticker changed
                                if ticker_upper != original_ticker.upper():
                                    is_valid_ticker, ticker_error = PortfolioService.is_valid_ticker(ticker_upper)
                                    if not is_valid_ticker:
                                        self._skip_focus_validation = True  # Prevent double dialog
                                        CustomMessageBox.warning(
                                            self.theme_manager,
                                            self,
                                            "Invalid Ticker",
                                            ticker_error
                                        )
                                        self._revert_ticker(row, original_ticker)
                                        return True  # Consume event

                                # Check if date or ticker changed
                                if tx_date != original_date or ticker_upper != original_ticker.upper():
                                    is_valid_day, day_error = PortfolioService.is_valid_trading_day(ticker_upper, tx_date)
                                    if not is_valid_day:
                                        self._skip_focus_validation = True  # Prevent double dialog
                                        CustomMessageBox.warning(
                                            self.theme_manager,
                                            self,
                                            "Invalid Trading Day",
                                            day_error
                                        )
                                        self._revert_date(row, original_date)
                                        return True  # Consume event

                                # If date changed OR type changed for FREE CASH, reassign sequence BEFORE validation
                                # FREE CASH Buy (deposit) goes first, FREE CASH Sell (withdrawal) goes last
                                old_sequence = transaction.get("sequence", 0)
                                is_free_cash = ticker_upper == PortfolioService.FREE_CASH_TICKER
                                tx_type = transaction.get("transaction_type", "Buy")
                                original_type = original.get("transaction_type", "Buy")
                                type_changed = tx_type != original_type

                                # Resequence if date changed OR if FREE CASH type changed
                                if tx_date != original_date or (is_free_cash and type_changed):
                                    all_transactions = self.get_all_transactions()
                                    other_txs = [t for t in all_transactions if t.get("id") != transaction_id]
                                    new_sequence = PortfolioService.get_sequence_for_date_edit(
                                        other_txs, tx_date, is_free_cash, tx_type
                                    )
                                    transaction["sequence"] = new_sequence
                                    if transaction_id in self._transactions_by_id:
                                        self._transactions_by_id[transaction_id]["sequence"] = new_sequence

                                # Valid data - validate and fetch prices
                                is_valid, error = PortfolioService.validate_transaction(transaction)
                                if is_valid:
                                    # For FREE CASH ticker, auto-set execution price to $1.00
                                    if ticker_upper == PortfolioService.FREE_CASH_TICKER:
                                        transaction["entry_price"] = 1.0
                                        price_widget = self.cellWidget(row, 4)
                                        if price_widget:
                                            inner_widget = price_widget.findChild(ValidatedNumericLineEdit)
                                            if inner_widget:
                                                inner_widget.setValue(1.0)

                                    # Validate transaction safeguards (cash balance, position, chain)
                                    # Set _validating to prevent _on_cell_changed from corrupting sequences
                                    self._validating = True
                                    try:
                                        safeguard_valid, safeguard_error = self._validate_transaction_safeguards(
                                            row, transaction, is_new=False, original_date=original_date
                                        )
                                    finally:
                                        self._validating = False
                                    if not safeguard_valid:
                                        self._skip_focus_validation = True
                                        CustomMessageBox.warning(
                                            self.theme_manager,
                                            self,
                                            "Transaction Error",
                                            safeguard_error
                                        )
                                        # Revert sequence if we changed it
                                        if tx_date != original_date:
                                            transaction["sequence"] = old_sequence
                                            if transaction_id in self._transactions_by_id:
                                                self._transactions_by_id[transaction_id]["sequence"] = old_sequence
                                        # Revert all fields to original values
                                        original = self._original_values.get(transaction_id, {})
                                        self._revert_all_fields(row, original)
                                        # Increment focus generation to invalidate any pending
                                        # deferred focus callbacks that were scheduled before this revert
                                        self._focus_generation += 1
                                        return True  # Consume event

                                    # Update original values
                                    if transaction_id:
                                        self._debug_set_original_values(transaction_id, {
                                            "ticker": ticker_upper,
                                            "date": tx_date,
                                            "quantity": transaction.get("quantity", 0.0),
                                            "entry_price": transaction.get("entry_price", 0.0),
                                            "fees": transaction.get("fees", 0.0),
                                            "transaction_type": transaction.get("transaction_type", "Buy"),
                                            "sequence": transaction.get("sequence", 0)
                                        }, "eventFilter_success")
                                        # Increment focus generation to invalidate any pending
                                        # deferred focus callbacks from before this successful edit
                                        self._focus_generation += 1
                                    self._update_calculated_cells(row)
                                    if transaction_id:
                                        self.transaction_modified.emit(transaction_id, transaction)
                                    # Update FREE CASH summary row
                                    self._update_free_cash_summary_row()

                                    # Re-sort if date was changed (sequence already reassigned)
                                    if tx_date != original_date:
                                        self.sort_by_date_descending()
                                        # Clear _current_editing_row to prevent deferred focus checks
                                        # from processing stale row data after the sort
                                        self._current_editing_row = None
                                else:
                                    # Basic validation failed - revert sequence if we changed it
                                    if tx_date != original_date:
                                        transaction["sequence"] = old_sequence
                                        if transaction_id in self._transactions_by_id:
                                            self._transactions_by_id[transaction_id]["sequence"] = old_sequence
                                    # Increment focus generation to invalidate pending deferred callbacks
                                    self._focus_generation += 1
                                # Clear selection and focus from the widget
                                self.clearSelection()
                                obj.clearFocus()  # Clear focus from the specific widget
                                return True  # Consume event

        return super().eventFilter(obj, event)

    def _check_row_focus_loss(self, expected_generation: int):
        """Check if focus has left the current editing row (deferred check).

        Args:
            expected_generation: The focus generation when this callback was queued.
                If it doesn't match current generation, a sort or successful edit
                happened and this callback should be ignored.
        """
        # Skip if generation changed (sort or successful edit invalidated this callback)
        if expected_generation != self._focus_generation:
            return

        # Skip if we're in the middle of validation/sorting
        if self._validating:
            return

        if self._current_editing_row is None:
            return

        # Get the currently focused widget
        focused_widget = QApplication.focusWidget()

        if not focused_widget:
            # Focus lost completely - trigger row focus lost
            if self._debug_original_values:
                print(f"[DEBUG] _check_row_focus_loss: calling _on_row_focus_lost({self._current_editing_row}) "
                      f"- no focused widget, skip_flag={self._skip_focus_validation}")
            self._on_row_focus_lost(self._current_editing_row)
            self._current_editing_row = None
            return

        # Check if focus is still in the same row
        new_row = self._find_row_for_widget(focused_widget)

        if new_row != self._current_editing_row:
            # Focus moved to different row - trigger row focus lost
            if self._debug_original_values:
                print(f"[DEBUG] _check_row_focus_loss: calling _on_row_focus_lost({self._current_editing_row}) "
                      f"- focus moved to row {new_row}, skip_flag={self._skip_focus_validation}")
            self._on_row_focus_lost(self._current_editing_row)
            self._current_editing_row = new_row

    def _on_row_focus_lost(self, row: int):
        """
        Handle when focus leaves a row.
        Auto-deletes empty rows (except blank row), or validates and fetches prices.
        Validates ticker existence and trading day for stocks.

        Args:
            row: Row index that lost focus
        """
        # Skip if we're in the middle of validation/sorting (prevents interference)
        if self._validating:
            return

        # Check if we should skip validation (already handled by Enter key)
        if self._skip_focus_validation:
            self._skip_focus_validation = False
            return

        # Get transaction for this row
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        # Check if this is blank row
        if transaction.get("is_blank"):
            # Try to auto-fill execution price and name when date and ticker are filled
            self._try_autofill_execution_price(row)
            ticker = transaction.get("ticker", "").strip()
            if ticker:
                self._try_autofill_name(row, ticker)

            # Check if it's complete, if so validate and transition to real
            if self._is_transaction_complete(transaction):
                # Validate ticker before transitioning
                ticker = transaction.get("ticker", "").strip().upper()
                tx_date = transaction.get("date", "")

                # Validate ticker exists in Yahoo Finance
                is_valid_ticker, ticker_error = PortfolioService.is_valid_ticker(ticker)
                if not is_valid_ticker:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Invalid Ticker",
                        ticker_error
                    )
                    # Don't transition - keep as blank row
                    return

                # Validate trading day for stocks (non-crypto)
                is_valid_day, day_error = PortfolioService.is_valid_trading_day(ticker, tx_date)
                if not is_valid_day:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Invalid Trading Day",
                        day_error
                    )
                    # Don't transition - keep as blank row
                    return

                # Transition will set skip flag if validation fails
                self._transition_blank_to_real(row, transaction)
            return

        # Existing row - check if row should be deleted (ticker empty OR quantity is 0/blank)
        ticker = transaction.get("ticker", "").strip()
        quantity = transaction.get("quantity", 0.0)
        transaction_id = transaction.get("id")

        # Read date from widget to get current value (stored data might be stale after sort)
        date_edit = self._get_inner_widget(row, 0)
        if date_edit:
            tx_date = date_edit.date().toString("yyyy-MM-dd")
            # Update transaction dict with current date
            transaction["date"] = tx_date
        else:
            tx_date = transaction.get("date", "")

        if not ticker or quantity == 0.0:
            # Empty ticker or zero quantity - validate before deleting
            # Use original values to check if deletion would break portfolio
            original = self._original_values.get(transaction_id, {})
            if original:
                # Build original transaction for validation
                original_tx = {
                    "id": transaction_id,
                    "ticker": original.get("ticker", ""),
                    "date": original.get("date", ""),
                    "quantity": original.get("quantity", 0.0),
                    "entry_price": original.get("entry_price", 0.0),
                    "fees": original.get("fees", 0.0),
                    "transaction_type": original.get("transaction_type", "Buy")
                }
                all_transactions = self.get_all_transactions()
                can_delete, error_msg = PortfolioService.validate_transaction_deletion(
                    all_transactions, original_tx
                )
                if not can_delete:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Cannot Delete Transaction",
                        error_msg
                    )
                    # Revert to original values
                    self._revert_all_fields(row, original)
                    return

            # Validation passed or no original - delete row
            self._delete_empty_row(row)
        else:
            # Has ticker and quantity - validate ticker and date, then fetch prices
            original = self._original_values.get(transaction_id, {})
            original_ticker = original.get("ticker", "")
            original_date = original.get("date", "")
            ticker_upper = ticker.upper()

            # Check if ticker changed
            if ticker_upper != original_ticker.upper():
                # Validate new ticker
                is_valid_ticker, ticker_error = PortfolioService.is_valid_ticker(ticker_upper)
                if not is_valid_ticker:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Invalid Ticker",
                        ticker_error
                    )
                    # Revert to original ticker
                    self._revert_ticker(row, original_ticker)
                    return

            # Check if date changed or ticker changed (need to revalidate trading day)
            if tx_date != original_date or ticker_upper != original_ticker.upper():
                # Validate trading day for stocks
                is_valid_day, day_error = PortfolioService.is_valid_trading_day(ticker_upper, tx_date)
                if not is_valid_day:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Invalid Trading Day",
                        day_error
                    )
                    # Revert to original date
                    self._revert_date(row, original_date)
                    return

            # If date changed OR type changed for FREE CASH, reassign sequence BEFORE validation
            # FREE CASH Buy (deposit) goes first, FREE CASH Sell (withdrawal) goes last
            old_sequence = transaction.get("sequence", 0)
            is_free_cash = ticker_upper == PortfolioService.FREE_CASH_TICKER
            tx_type = transaction.get("transaction_type", "Buy")
            original_type = original.get("transaction_type", "Buy")
            type_changed = tx_type != original_type
            needs_resequence = tx_date != original_date or (is_free_cash and type_changed)

            if needs_resequence:
                all_transactions = self.get_all_transactions()
                other_txs = [t for t in all_transactions if t.get("id") != transaction_id]
                new_sequence = PortfolioService.get_sequence_for_date_edit(
                    other_txs, tx_date, is_free_cash, tx_type
                )
                transaction["sequence"] = new_sequence
                if transaction_id in self._transactions_by_id:
                    self._transactions_by_id[transaction_id]["sequence"] = new_sequence

            # Validate transaction
            is_valid, error = PortfolioService.validate_transaction(transaction)
            if not is_valid:
                # Revert sequence if we changed it
                if needs_resequence:
                    transaction["sequence"] = old_sequence
                    if transaction_id in self._transactions_by_id:
                        self._transactions_by_id[transaction_id]["sequence"] = old_sequence
                return

            # Validate transaction safeguards (cash balance, position, chain)
            # Set _validating to prevent _on_cell_changed from corrupting sequences
            self._validating = True
            try:
                safeguard_valid, safeguard_error = self._validate_transaction_safeguards(
                    row, transaction, is_new=False, original_date=original_date
                )
            finally:
                self._validating = False
            if not safeguard_valid:
                CustomMessageBox.warning(
                    self.theme_manager,
                    self,
                    "Transaction Error",
                    safeguard_error
                )
                # Revert sequence if we changed it
                if tx_date != original_date:
                    transaction["sequence"] = old_sequence
                    if transaction_id in self._transactions_by_id:
                        self._transactions_by_id[transaction_id]["sequence"] = old_sequence
                # Revert all fields to original values
                original = self._original_values.get(transaction_id, {})
                self._revert_all_fields(row, original)
                return

            # Update original values since validation passed
            # BUT only if we're actually making a change - don't overwrite with stale data
            # (eventFilter may have already updated _original_values before sort)
            if transaction_id:
                current_original = self._original_values.get(transaction_id, {})
                # Only update if the widget date differs from current original
                # This prevents overwriting correct values with stale stored data
                if tx_date != current_original.get("date", ""):
                    self._debug_set_original_values(transaction_id, {
                        "ticker": ticker_upper,
                        "date": tx_date,
                        "quantity": transaction.get("quantity", 0.0),
                        "entry_price": transaction.get("entry_price", 0.0),
                        "fees": transaction.get("fees", 0.0),
                        "transaction_type": transaction.get("transaction_type", "Buy"),
                        "sequence": transaction.get("sequence", 0)
                    }, "_on_row_focus_lost")
                    # Increment focus generation to invalidate any pending callbacks
                    self._focus_generation += 1
                elif self._debug_original_values:
                    print(f"[DEBUG] _on_row_focus_lost: SKIPPED update for tx_id={transaction_id[:8]}... "
                          f"(widget date {tx_date} matches current original)")

            # Update calculated cells (fetch prices)
            self._update_calculated_cells(row)

            # Emit signal that transaction was modified
            if transaction_id:
                self.transaction_modified.emit(transaction_id, transaction)

            # Update FREE CASH summary row
            self._update_free_cash_summary_row()

            # Re-sort if date was changed to maintain chronological order
            # (sequence was already reassigned before validation)
            if tx_date != original_date:
                self.sort_by_date_descending()
                # Clear _current_editing_row to prevent deferred focus checks
                # from processing stale row data after the sort
                self._current_editing_row = None

    def _try_autofill_execution_price(self, row: int) -> None:
        """
        Auto-fill execution price for blank row when date and ticker are filled.
        Only fills if execution price was not manually entered by user.
        Fetches price in background thread to avoid UI lag.
        Also validates date is within ticker's available history.

        Args:
            row: Row index (should be 0 for blank row)
        """
        import threading
        from datetime import datetime

        transaction = self._get_transaction_for_row(row)
        if not transaction or not transaction.get("is_blank"):
            return

        # Track if user manually entered price (still validate date even if they did)
        user_entered_price = row in self._user_entered_price_rows

        # Get date and ticker values
        ticker = transaction.get("ticker", "").strip().upper()
        tx_date = transaction.get("date", "")

        # Only proceed if date AND ticker are filled
        if not ticker or not tx_date:
            return

        # FREE CASH is always $1.00 - no network call needed
        if ticker == PortfolioService.FREE_CASH_TICKER:
            if not user_entered_price:
                self._apply_autofill_price(row, 1.0)
            return

        # Determine if today or historical
        today_str = datetime.now().strftime("%Y-%m-%d")

        def fetch_and_apply():
            """Background thread: fetch price, then emit signal for main thread."""
            try:
                if tx_date == today_str:
                    prices = PortfolioService.fetch_current_prices([ticker])
                    price = prices.get(ticker)
                else:
                    results = PortfolioService.fetch_historical_closes_batch([(ticker, tx_date)])
                    price = results.get(ticker, {}).get(tx_date)

                if price is not None:
                    # Only auto-fill price if user didn't manually enter one
                    if not user_entered_price:
                        self._price_autofill_ready.emit(row, price)
                else:
                    # Price is None - check if date is before ticker history
                    first_date = PortfolioService.get_first_available_date(ticker)
                    if first_date and tx_date < first_date:
                        # Emit signal for main thread to show dialog and correct date
                        self._date_correction_needed.emit(row, first_date, ticker)
            except Exception:
                pass  # Silently fail

        # Start background thread for price fetch
        thread = threading.Thread(target=fetch_and_apply, daemon=True)
        thread.start()

    def _apply_autofill_price(self, row: int, price: float) -> None:
        """
        Apply auto-filled price to the execution price widget.
        Must be called from the main thread.

        Args:
            row: Row index
            price: Price to set
        """
        # Verify row is still the blank row (user might have submitted already)
        transaction = self._get_transaction_for_row(row)
        if not transaction or not transaction.get("is_blank"):
            return

        # Don't overwrite if user manually entered a price
        if row in self._user_entered_price_rows:
            return

        price_widget = self._get_inner_widget(row, 4)
        if price_widget and isinstance(price_widget, ValidatedNumericLineEdit):
            price_widget.blockSignals(True)
            price_widget.setValue(price)
            price_widget.blockSignals(False)
            price_widget.repaint()
            # Update stored transaction
            transaction["entry_price"] = price
            self._transactions_by_id["BLANK_ROW"]["entry_price"] = price
            if row in self._transactions:
                self._transactions[row]["entry_price"] = price

    def _apply_autofill_name(self, row: int, name: str) -> None:
        """
        Apply auto-filled name to the name widget.

        Called from signal handler (thread-safe).

        Args:
            row: Row index
            name: Name to set
        """
        # Verify row still exists
        if row >= self.rowCount():
            return

        name_widget = self._get_inner_widget(row, 2)
        if name_widget and isinstance(name_widget, QLineEdit):
            name_widget.blockSignals(True)
            name_widget.setText(name)
            name_widget.blockSignals(False)
            name_widget.repaint()

    def _handle_date_correction(self, row: int, first_date: str, ticker: str) -> None:
        """
        Handle date correction when entered date is before ticker history.
        Shows warning dialog and updates date to first available date.

        Args:
            row: Row index
            first_date: First available date in YYYY-MM-DD format
            ticker: Ticker symbol
        """
        # Prevent duplicate dialogs from multiple autofill threads
        if self._date_correction_pending:
            return
        self._date_correction_pending = True

        # Verify row is still the blank row
        transaction = self._get_transaction_for_row(row)
        if not transaction or not transaction.get("is_blank"):
            self._date_correction_pending = False
            return

        # Show warning dialog
        CustomMessageBox.warning(
            self.theme_manager,
            self,
            "Date Before Ticker History",
            f"The entered date is before the available price history for {ticker}.\n\n"
            f"First available date: {first_date}\n\n"
            f"The date has been automatically adjusted."
        )

        # Update date widget
        date_widget = self._get_inner_widget(row, 0)
        if date_widget and isinstance(date_widget, DateInputWidget):
            date_widget.blockSignals(True)
            date_widget.setDate(QDate.fromString(first_date, "yyyy-MM-dd"))
            date_widget.blockSignals(False)

            # Update stored transaction
            transaction["date"] = first_date
            self._transactions_by_id["BLANK_ROW"]["date"] = first_date
            if row in self._transactions:
                self._transactions[row]["date"] = first_date

        # Re-trigger auto-fill with corrected date
        QTimer.singleShot(0, lambda r=row: self._try_autofill_execution_price(r))

        # Reset flag after correction is complete
        self._date_correction_pending = False

    def _try_autofill_name(self, row: int, ticker: str) -> None:
        """
        Auto-fill name for a row when ticker is set.

        Fetches name in background thread to avoid UI lag.

        Args:
            row: Row index
            ticker: Ticker symbol
        """
        if not ticker:
            return

        ticker_upper = ticker.upper()

        # FREE CASH gets special name
        if ticker_upper == PortfolioService.FREE_CASH_TICKER:
            self._apply_autofill_name(row, "FREE CASH")
            return

        # Check cache first
        if ticker_upper in self._cached_names:
            self._apply_autofill_name(row, self._cached_names[ticker_upper])
            return

        # Fetch in background thread
        import threading

        def fetch_name():
            """Background thread: fetch name, then emit signal for main thread."""
            try:
                names = PortfolioService.fetch_ticker_names([ticker_upper])
                name = names.get(ticker_upper, "")
                if name:
                    # Cache the name
                    self._cached_names[ticker_upper] = name
                    # Emit signal to update UI from main thread
                    self._name_autofill_ready.emit(row, name)
            except Exception as e:
                print(f"Error fetching name for {ticker_upper}: {e}")

        thread = threading.Thread(target=fetch_name, daemon=True)
        thread.start()

    def update_ticker_names(self, names: Dict[str, str]):
        """
        Update cached ticker names from external source and refresh Name cells.

        Args:
            names: Dict mapping ticker -> name
        """
        self._cached_names.update(names)

        # Update Name cells for all existing rows
        for row in range(self.rowCount()):
            # Get ticker from column 1
            ticker_widget = self._get_inner_widget(row, 1)
            if ticker_widget and isinstance(ticker_widget, QLineEdit):
                ticker = ticker_widget.text().strip().upper()
                if ticker and ticker in self._cached_names:
                    name = self._cached_names[ticker]
                    name_widget = self._get_inner_widget(row, 2)
                    if name_widget and isinstance(name_widget, QLineEdit):
                        name_widget.setText(name)

    def _validate_transaction_safeguards(
        self,
        row: int,
        transaction: Dict[str, Any],
        is_new: bool = False,
        original_date: str = ""
    ) -> Tuple[bool, str]:
        """
        Validate transaction safeguards (cash balance, position, chain).

        Args:
            row: Row index
            transaction: Transaction to validate
            is_new: True if this is a new transaction (blank row transition)
            original_date: Original date before edit (for detecting date adjustments)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get all existing transactions
        all_transactions = self.get_all_transactions()

        # Validate using PortfolioService
        return PortfolioService.validate_transaction_safeguards(
            all_transactions, transaction, is_new, original_date
        )

    def _delete_empty_row(self, row: int):
        """
        Delete a single empty row.

        Args:
            row: Row index to delete
        """
        # Get transaction
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        transaction_id = transaction["id"]

        # Remove from UUID-based storage
        if transaction_id in self._transactions_by_id:
            del self._transactions_by_id[transaction_id]

        # Remove from original values tracking
        if transaction_id in self._original_values:
            del self._original_values[transaction_id]

        # Remove row from table first (this shifts all rows below up by 1)
        self.removeRow(row)

        # Rebuild all mappings to account for shifted row indices
        new_row_to_id = {}
        new_transactions = {}
        new_row_widgets_map = {}

        for old_row in sorted(self._row_to_id.keys()):
            if old_row < row:
                # Rows above deleted row keep same index
                new_row_to_id[old_row] = self._row_to_id[old_row]
                if old_row in self._transactions:
                    new_transactions[old_row] = self._transactions[old_row]
                if old_row in self._row_widgets_map:
                    new_row_widgets_map[old_row] = self._row_widgets_map[old_row]
            elif old_row > row:
                # Rows below deleted row shift up by 1
                new_index = old_row - 1
                new_row_to_id[new_index] = self._row_to_id[old_row]
                if old_row in self._transactions:
                    new_transactions[new_index] = self._transactions[old_row]
                if old_row in self._row_widgets_map:
                    new_row_widgets_map[new_index] = self._row_widgets_map[old_row]
            # old_row == row is the deleted row, skip it

        self._row_to_id = new_row_to_id
        self._transactions = new_transactions
        self._row_widgets_map = new_row_widgets_map

        # Update stored row positions for all widgets from deleted row onwards
        self._update_row_positions(row)

        # Emit signal
        self.transaction_deleted.emit(transaction_id)

        # Update FREE CASH summary row
        self._update_free_cash_summary_row()

    def _on_header_clicked(self, column: int):
        """
        Handle column header click for custom sorting.
        Keeps blank row and FREE CASH summary row pinned at top while sorting transactions.

        Args:
            column: Column index that was clicked
        """
        # Collect all sortable transactions (exclude blank and FREE CASH summary)
        sortable_transactions = []
        blank_transaction = None

        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            if tx:
                if tx.get("is_blank"):
                    blank_transaction = tx
                elif tx.get("is_free_cash_summary"):
                    # Skip FREE CASH summary - it will be recreated
                    pass
                else:
                    sortable_transactions.append(tx)

        if not sortable_transactions:
            return

        # Toggle sort order if same column, otherwise default to ascending
        if column == self._current_sort_column:
            if self._current_sort_order == Qt.AscendingOrder:
                self._current_sort_order = Qt.DescendingOrder
            else:
                self._current_sort_order = Qt.AscendingOrder
        else:
            self._current_sort_column = column
            self._current_sort_order = Qt.AscendingOrder

        # Define sort key functions based on column
        # Columns 0-6: Editable fields stored in transaction dict
        # Columns 7-10: Calculated/read-only fields
        def get_sort_key(tx: Dict[str, Any]):
            ticker = tx.get("ticker", "")
            tx_date = tx.get("date", "")

            if column == 0:  # Date - use priority then sequence for same-day transactions
                # Priority order: FREE CASH Buy (0), Regular Sell (1), Regular Buy (2), FREE CASH Sell (3)
                # Negate priority and sequence so lower values appear first when date is descending
                tx_type = tx.get("transaction_type", "Buy")
                priority = PortfolioService.get_transaction_priority(ticker, tx_type)
                sequence = tx.get("sequence", 0)
                return (tx_date, -priority, -sequence)
            elif column == 1:  # Ticker
                return ticker.lower()
            elif column == 2:  # Name (auto-populated, sort by cached name)
                return (self._cached_names.get(ticker) or "").lower()
            elif column == 3:  # Quantity
                return tx.get("quantity", 0.0)
            elif column == 4:  # Execution Price
                return tx.get("entry_price", 0.0)
            elif column == 5:  # Fees
                return tx.get("fees", 0.0)
            elif column == 6:  # Type
                return tx.get("transaction_type", "").lower()
            elif column == 7:  # Daily Closing Price
                if ticker and tx_date and ticker in self._historical_prices:
                    return self._historical_prices[ticker].get(tx_date, 0.0) or 0.0
                return 0.0
            elif column == 8:  # Live Price
                return self._current_prices.get(ticker, 0.0) or 0.0
            elif column == 9:  # Principal
                return PortfolioService.calculate_principal(tx)
            elif column == 10:  # Market Value
                live_price = self._current_prices.get(ticker, 0.0) or 0.0
                quantity = tx.get("quantity", 0.0)
                return live_price * quantity
            return 0

        reverse = self._current_sort_order == Qt.DescendingOrder

        # Sort the transactions
        sorted_transactions = sorted(sortable_transactions, key=get_sort_key, reverse=reverse)

        # Increment focus generation to invalidate any pending deferred focus callbacks
        self._focus_generation += 1

        # Rebuild table
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()
        self._row_widgets_map.clear()

        # Add blank row first if it exists (pinned at top)
        # Note: _ensure_blank_row() also creates FREE CASH summary row at index 1
        if blank_transaction:
            self._ensure_blank_row()

        # Add sorted transactions (starting at row 2, after blank and FREE CASH summary)
        for tx in sorted_transactions:
            self.add_transaction_row(tx)

        # Update calculated cells
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

        # Update FREE CASH summary row after all transactions are added
        # (must be done after transactions are added, not before)
        self._update_free_cash_summary_row()

        # Reset column widths after rebuilding table
        self._reset_column_widths()

        # Update header sort indicator
        header = self.horizontalHeader()
        header.setSortIndicator(column, self._current_sort_order)

    def _sort_transactions(self):
        """
        Sort transactions: blank row at top, FREE CASH summary at row 1,
        completed transactions by date below.
        """
        # Get all sortable transactions (exclude blank and FREE CASH summary)
        sortable_transactions = []
        blank_transaction = None

        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            if tx:
                if tx.get("is_blank"):
                    blank_transaction = tx
                elif tx.get("is_free_cash_summary"):
                    # Skip FREE CASH summary - it will be recreated
                    pass
                else:
                    sortable_transactions.append(tx)

        # Sort transactions by date (oldest first)
        sortable_transactions.sort(key=lambda t: t.get("date", ""))

        # Increment focus generation to invalidate any pending deferred focus callbacks
        self._focus_generation += 1

        # Rebuild table
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()
        self._row_widgets_map.clear()

        # Add blank row first if it exists (also creates FREE CASH summary at row 1)
        if blank_transaction:
            self._ensure_blank_row()

        # Add sorted transactions
        for tx in sortable_transactions:
            self.add_transaction_row(tx)

        # Update FREE CASH summary row after all transactions are added
        self._update_free_cash_summary_row()

        # Reset column widths after rebuilding table
        self._reset_column_widths()

    def sort_by_date_descending(self):
        """
        Sort transactions by date DESCENDING (most recent first).
        For same-day transactions, sort by sequence DESCENDING (newest first).

        This is the default sort applied on load and after adding transactions.
        Keeps blank row pinned at row 0 and FREE CASH summary at row 1.
        """
        # Increment focus generation BEFORE sort to invalidate any pending
        # deferred focus callbacks that were queued before this sort
        self._focus_generation += 1

        if self._debug_original_values:
            print(f"[DEBUG] sort_by_date_descending: START (gen={self._focus_generation})")
            for tx_id, vals in self._original_values.items():
                if tx_id != "BLANK_ROW" and not tx_id.startswith("FREE_CASH"):
                    print(f"  _original_values[{tx_id[:8]}...] = date={vals.get('date')}")
        # Set _validating to prevent _on_cell_changed from running during sort
        # (widget signals fire when recreating widgets, could corrupt sequences)
        self._validating = True
        try:
            self._sort_by_date_descending_impl()
        finally:
            self._validating = False
        if self._debug_original_values:
            print(f"[DEBUG] sort_by_date_descending: END")
            for tx_id, vals in self._original_values.items():
                if tx_id != "BLANK_ROW" and not tx_id.startswith("FREE_CASH"):
                    print(f"  _original_values[{tx_id[:8]}...] = date={vals.get('date')}")

    def _sort_by_date_descending_impl(self):
        """Internal implementation of sort_by_date_descending."""
        # Collect all sortable transactions (exclude blank and FREE CASH summary)
        sortable_transactions = []
        blank_transaction = None

        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            if tx:
                if tx.get("is_blank"):
                    blank_transaction = tx
                elif tx.get("is_free_cash_summary"):
                    # Skip FREE CASH summary - it will be recreated
                    pass
                else:
                    sortable_transactions.append(tx)

        if not sortable_transactions:
            return

        # Sort by date descending, then by priority ascending, then by sequence ascending
        # Priority order: FREE CASH Buy (0), Regular Sell (1), Regular Buy (2), FREE CASH Sell (3)
        def sort_key(tx: Dict[str, Any]):
            date = tx.get("date", "")
            ticker = tx.get("ticker", "")
            tx_type = tx.get("transaction_type", "Buy")
            priority = PortfolioService.get_transaction_priority(ticker, tx_type)
            sequence = tx.get("sequence", 0)
            # Negate priority and sequence to get ascending order while date is descending
            return (date, -priority, -sequence)

        # Reverse=True for descending order on date, but priority/sequence are negated for ascending
        sorted_transactions = sorted(sortable_transactions, key=sort_key, reverse=True)

        # Rebuild table
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()
        self._row_widgets_map.clear()

        # Add blank row first if it exists (also creates FREE CASH summary at row 1)
        if blank_transaction:
            self._ensure_blank_row()

        # Add sorted transactions using batch mode to avoid O(N²) FREE CASH updates
        self._batch_loading = True
        for tx in sorted_transactions:
            self.add_transaction_row(tx)
        self._batch_loading = False

        # Update calculated cells
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

        # Update FREE CASH summary row after all transactions are added
        self._update_free_cash_summary_row()

        # Reset column widths after rebuilding table
        self._reset_column_widths()

        # Update sort state to reflect date column, descending
        self._current_sort_column = 0  # Date column
        self._current_sort_order = Qt.DescendingOrder

        # Update header sort indicator
        header = self.horizontalHeader()
        header.setSortIndicator(0, Qt.DescendingOrder)

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        # Use centralized stylesheet service
        stylesheet = ThemeStylesheetService.get_table_stylesheet(theme)
        widget_stylesheet = ThemeStylesheetService.get_line_edit_stylesheet(
            theme, highlighted=self._highlight_editable
        )

        self.setStyleSheet(stylesheet)

        # Apply styling to all editable cell widgets
        self._apply_widget_theme(widget_stylesheet)

    def _apply_widget_theme(self, widget_stylesheet: str):
        """Apply theme styling to all editable cell widgets."""
        bg_color = self._get_cell_background_color()
        combo_style = self._get_combo_stylesheet()

        for row in range(self.rowCount()):
            # Columns 0-6 have container widgets with inner widgets
            for col in range(7):
                container = self.cellWidget(row, col)
                if container:
                    # Update container background
                    container.setStyleSheet(f"QWidget {{ background-color: {bg_color}; }}")

                    # Update cell item background
                    item = self.item(row, col)
                    if item:
                        if self._highlight_editable and bg_color != "transparent":
                            item.setBackground(QBrush(QColor(bg_color)))
                        else:
                            item.setBackground(QBrush())  # Reset to default

                    # Update inner widget style
                    inner = container.property("_inner_widget")
                    if inner:
                        if col == 6:  # Combo box (Type column)
                            inner.setStyleSheet(combo_style)
                        else:  # QLineEdit-based widgets
                            inner.setStyleSheet(widget_stylesheet)

    def set_highlight_editable(self, enabled: bool):
        """
        Enable or disable editable field highlighting.

        Args:
            enabled: True to show colored backgrounds on editable fields
        """
        if self._highlight_editable == enabled:
            return  # No change, skip expensive theme re-application
        self._highlight_editable = enabled
        # Re-apply theme to update all widget styles
        self._apply_theme()

    def set_hide_free_cash_summary(self, hidden: bool):
        """
        Show or hide the FREE CASH summary row.

        Args:
            hidden: True to hide the FREE CASH summary row, False to show it
        """
        if self._hide_free_cash_summary == hidden:
            return  # No change
        self._hide_free_cash_summary = hidden
        # Apply visibility to row 1 (FREE CASH summary row is always at index 1)
        if self.rowCount() > 1:
            self.setRowHidden(1, hidden)
