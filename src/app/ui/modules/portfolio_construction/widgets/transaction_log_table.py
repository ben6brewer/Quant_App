"""Transaction Log Table Widget - Editable Transaction Table"""

from typing import Dict, List, Any
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
    QLineEdit, QComboBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QColor

from app.core.theme_manager import ThemeManager
from ..services.portfolio_service import PortfolioService


class TransactionLogTable(QTableWidget):
    """
    Editable transaction log table (left side).
    Inline editing with date picker and dropdown.
    """

    # Signals
    transaction_added = Signal(dict)           # Emitted when row added
    transaction_modified = Signal(str, dict)   # (transaction_id, updated_transaction)
    transaction_deleted = Signal(str)          # (transaction_id)

    # Columns
    COLUMNS = [
        "Date",           # QDateEdit
        "Ticker",         # QLineEdit
        "Type",           # QComboBox (Buy/Sell)
        "Quantity",       # QDoubleSpinBox
        "Entry Price",    # QDoubleSpinBox
        "Fees",           # QDoubleSpinBox
        "Notes",          # QLineEdit
        "Market Value",   # Read-only label (calculated)
        "P&L"             # Read-only label (calculated)
    ]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._transactions = {}  # Map row_index -> transaction_dict
        self._current_prices = {}  # Map ticker -> current_price

        self._setup_table()
        self._apply_theme()

        # Connect theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_table(self):
        """Configure table structure."""
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # Column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Date
        self.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Ticker
        self.setColumnWidth(1, 100)
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Type
        self.setColumnWidth(2, 80)
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Quantity
        self.setColumnWidth(3, 100)
        header.setSectionResizeMode(4, QHeaderView.Interactive)  # Entry Price
        self.setColumnWidth(4, 110)
        header.setSectionResizeMode(5, QHeaderView.Interactive)  # Fees
        self.setColumnWidth(5, 90)
        header.setSectionResizeMode(6, QHeaderView.Stretch)  # Notes
        header.setSectionResizeMode(7, QHeaderView.Interactive)  # Market Value
        self.setColumnWidth(7, 120)
        header.setSectionResizeMode(8, QHeaderView.Interactive)  # P&L
        self.setColumnWidth(8, 120)

        # Table properties
        self.verticalHeader().setVisible(True)  # Show row numbers
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Enable sorting
        self.setSortingEnabled(True)

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

        # Store transaction
        self._transactions[row] = transaction

        # Date cell: QDateEdit widget
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setDate(QDate.fromString(transaction["date"], "yyyy-MM-dd"))
        date_edit.dateChanged.connect(lambda: self._on_cell_changed(row, 0))
        self.setCellWidget(row, 0, date_edit)

        # Ticker cell: QLineEdit
        ticker_edit = QLineEdit(transaction["ticker"])
        ticker_edit.textChanged.connect(lambda: self._on_cell_changed(row, 1))
        self.setCellWidget(row, 1, ticker_edit)

        # Type cell: QComboBox
        type_combo = QComboBox()
        type_combo.addItems(["Buy", "Sell"])
        type_combo.setCurrentText(transaction["transaction_type"])
        type_combo.currentTextChanged.connect(lambda: self._on_cell_changed(row, 2))
        self.setCellWidget(row, 2, type_combo)

        # Quantity cell: QDoubleSpinBox
        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0.0001, 1000000)
        qty_spin.setDecimals(4)
        qty_spin.setValue(transaction["quantity"])
        qty_spin.valueChanged.connect(lambda: self._on_cell_changed(row, 3))
        self.setCellWidget(row, 3, qty_spin)

        # Entry Price cell: QDoubleSpinBox
        price_spin = QDoubleSpinBox()
        price_spin.setRange(0.01, 1000000)
        price_spin.setDecimals(2)
        price_spin.setPrefix("$")
        price_spin.setValue(transaction["entry_price"])
        price_spin.valueChanged.connect(lambda: self._on_cell_changed(row, 4))
        self.setCellWidget(row, 4, price_spin)

        # Fees cell: QDoubleSpinBox
        fees_spin = QDoubleSpinBox()
        fees_spin.setRange(0, 10000)
        fees_spin.setDecimals(2)
        fees_spin.setPrefix("$")
        fees_spin.setValue(transaction["fees"])
        fees_spin.valueChanged.connect(lambda: self._on_cell_changed(row, 5))
        self.setCellWidget(row, 5, fees_spin)

        # Notes cell: QLineEdit
        notes_edit = QLineEdit(transaction.get("notes", ""))
        notes_edit.textChanged.connect(lambda: self._on_cell_changed(row, 6))
        self.setCellWidget(row, 6, notes_edit)

        # Market Value cell: Read-only QTableWidgetItem
        market_value_item = QTableWidgetItem("--")
        market_value_item.setFlags(market_value_item.flags() & ~Qt.ItemIsEditable)
        market_value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(row, 7, market_value_item)

        # P&L cell: Read-only QTableWidgetItem
        pnl_item = QTableWidgetItem("--")
        pnl_item.setFlags(pnl_item.flags() & ~Qt.ItemIsEditable)
        pnl_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(row, 8, pnl_item)

        # Re-enable sorting
        self.setSortingEnabled(True)

        return row

    def _on_cell_changed(self, row: int, col: int):
        """Handle cell value change."""
        if row not in self._transactions:
            return

        transaction = self._transactions[row]
        transaction_id = transaction["id"]

        # Extract updated values
        updated = self._extract_transaction_from_row(row)
        if not updated:
            return

        # Validate
        is_valid, error = PortfolioService.validate_transaction(updated)
        if not is_valid:
            # TODO: Show validation error in status bar or tooltip
            print(f"Validation error: {error}")
            return

        # Update stored transaction
        self._transactions[row] = updated

        # Update calculated cells
        self._update_calculated_cells(row)

        # Emit signal
        self.transaction_modified.emit(transaction_id, updated)

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

        transaction_id = self._transactions[row]["id"]

        try:
            date_edit = self.cellWidget(row, 0)
            ticker_edit = self.cellWidget(row, 1)
            type_combo = self.cellWidget(row, 2)
            qty_spin = self.cellWidget(row, 3)
            price_spin = self.cellWidget(row, 4)
            fees_spin = self.cellWidget(row, 5)
            notes_edit = self.cellWidget(row, 6)

            if not all([date_edit, ticker_edit, type_combo, qty_spin, price_spin, fees_spin, notes_edit]):
                return None

            return {
                "id": transaction_id,
                "date": date_edit.date().toString("yyyy-MM-dd"),
                "ticker": ticker_edit.text().strip().upper(),
                "transaction_type": type_combo.currentText(),
                "quantity": qty_spin.value(),
                "entry_price": price_spin.value(),
                "fees": fees_spin.value(),
                "notes": notes_edit.text().strip()
            }
        except Exception as e:
            print(f"Error extracting transaction from row {row}: {e}")
            return None

    def _update_calculated_cells(self, row: int):
        """
        Update Market Value and P&L cells.

        Args:
            row: Row index
        """
        if row not in self._transactions:
            return

        transaction = self._transactions[row]
        ticker = transaction["ticker"]

        # Get current price
        current_price = self._current_prices.get(ticker)

        if current_price is None:
            self.item(row, 7).setText("--")
            self.item(row, 8).setText("--")
            return

        # Calculate market value
        market_value = current_price * transaction["quantity"]

        # Calculate P&L
        cost_basis = PortfolioService.calculate_cost_basis(transaction)
        if transaction["transaction_type"] == "Buy":
            pnl = market_value - cost_basis
        else:  # Sell
            pnl = -cost_basis - market_value  # Proceeds - current value

        # Update cells
        self.item(row, 7).setText(f"${market_value:,.2f}")

        pnl_item = self.item(row, 8)
        pnl_item.setText(f"${pnl:+,.2f}")
        # Color coding
        if pnl > 0:
            pnl_item.setForeground(QColor(76, 153, 0))  # Green
        elif pnl < 0:
            pnl_item.setForeground(QColor(200, 50, 50))  # Red
        else:
            pnl_item.setForeground(QColor(128, 128, 128))  # Gray

    def update_current_prices(self, prices: Dict[str, float]):
        """
        Update current prices and recalculate all rows.

        Args:
            prices: Dict mapping ticker -> price
        """
        self._current_prices = prices
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """
        Get all transactions from table.

        Returns:
            List of transaction dicts
        """
        transactions = []
        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            if tx:
                transactions.append(tx)
        return transactions

    def clear_all_transactions(self):
        """Clear all transactions from table."""
        self.setRowCount(0)
        self._transactions.clear()

    def delete_selected_rows(self):
        """Delete selected rows and emit signals."""
        selected_rows = sorted(set(idx.row() for idx in self.selectedIndexes()), reverse=True)

        for row in selected_rows:
            if row in self._transactions:
                transaction_id = self._transactions[row]["id"]
                del self._transactions[row]
                self.removeRow(row)
                self.transaction_deleted.emit(transaction_id)

        # Rebuild transaction map (row indices shifted)
        new_transactions = {}
        for row in range(self.rowCount()):
            # Re-extract from widgets
            tx = self._extract_transaction_from_row(row)
            if tx:
                # Keep the original transaction from _transactions if possible
                old_tx = next((t for t in self._transactions.values() if t["id"] == tx["id"]), None)
                new_transactions[row] = old_tx if old_tx else tx
            else:
                # If extraction failed, try to keep old transaction
                for old_row, old_tx in self._transactions.items():
                    if old_row == row:
                        new_transactions[row] = old_tx
                        break

        self._transactions = new_transactions

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet."""
        return """
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                gridline-color: #3d3d3d;
                border: 1px solid #3d3d3d;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 5px;
                border: 1px solid #3d3d3d;
                font-weight: bold;
                font-size: 12px;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QTableWidget {
                background-color: #ffffff;
                color: #000000;
                gridline-color: #cccccc;
                border: 1px solid #cccccc;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #333333;
                padding: 5px;
                border: 1px solid #cccccc;
                font-weight: bold;
                font-size: 12px;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QTableWidget {
                background-color: #000814;
                color: #e8e8e8;
                gridline-color: #1a2838;
                border: 1px solid #1a2838;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #FF8000;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #0d1420;
                color: #a8a8a8;
                padding: 5px;
                border: 1px solid #1a2838;
                font-weight: bold;
                font-size: 12px;
            }
        """
