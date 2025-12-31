"""Aggregate Portfolio Table Widget - Read-Only Holdings Display"""

from typing import List, Dict, Any
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.core.theme_manager import ThemeManager
from app.services.theme_stylesheet_service import ThemeStylesheetService
from ..services.portfolio_service import PortfolioService


class AggregatePortfolioTable(QTableWidget):
    """
    Read-only aggregate portfolio table (right side).
    Shows holdings grouped by ticker with totals.
    """

    # Columns
    COLUMNS = [
        "Ticker",
        "Total Quantity",
        "Avg Cost Basis",
        "Current Price",
        "Market Value",
        "P&L",
        "Weight %"
    ]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._holdings_data: List[Dict[str, Any]] = []
        self._free_cash_summary: Dict[str, Any] = None  # FREE CASH summary data
        self._current_sort_column: int = -1
        self._current_sort_order: Qt.SortOrder = Qt.DescendingOrder

        self._setup_table()
        self._apply_theme()

        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_table(self):
        """Configure table structure."""
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # All columns stretch
        header = self.horizontalHeader()
        for i in range(len(self.COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.Stretch)

        # Left-align column headers
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Fixed row height (matching Transaction Log)
        v_header = self.verticalHeader()
        v_header.setDefaultSectionSize(48)

        # Read-only
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Disable built-in sorting - we handle it manually to keep TOTAL row pinned
        self.setSortingEnabled(False)

        # Connect header click for custom sorting
        header = self.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)

        # Set corner label
        self._set_corner_label("Position")

    def _set_corner_label(self, text: str):
        """Set text for table corner button."""
        corner_button = self.findChild(QAbstractButton)
        if corner_button:
            corner_button.setText(text)
            corner_button.setEnabled(False)

    def update_holdings(self, holdings: List[Dict[str, Any]], free_cash_summary: Dict[str, Any] = None):
        """
        Update table with aggregate holdings.

        Args:
            holdings: List of holding dicts from PortfolioService
            free_cash_summary: Optional FREE CASH summary dict with quantity, principal, market_value
        """
        # Store holdings data for sorting
        self._holdings_data = holdings.copy() if holdings else []
        self._free_cash_summary = free_cash_summary

        # Recalculate weight percentages to include FREE CASH in total
        # This fixes the bug where holdings sum to 100% even when FREE CASH is present
        if self._holdings_data and free_cash_summary:
            free_cash_value = free_cash_summary.get("market_value", 0) or 0
            if free_cash_value != 0:
                holdings_market_value = sum(
                    h.get("market_value", 0) or 0 for h in self._holdings_data
                )
                total_market_value = holdings_market_value + free_cash_value
                if total_market_value > 0:
                    for holding in self._holdings_data:
                        if holding.get("market_value") is not None:
                            holding["weight_pct"] = (
                                holding["market_value"] / total_market_value
                            ) * 100

        # Clear existing
        self.setRowCount(0)

        # Add totals row first (row 0, pinned at top) - includes FREE CASH in total
        self._add_totals_row(holdings, free_cash_summary)

        # Add FREE CASH row if present and has value
        if free_cash_summary and free_cash_summary.get("market_value", 0) != 0:
            self._add_free_cash_row(free_cash_summary, holdings)

        # Add holdings starting after TOTAL (and FREE CASH if present)
        self._populate_holdings(self._holdings_data)

    def _populate_holdings(self, holdings: List[Dict[str, Any]]):
        """
        Populate holdings rows (after the TOTAL row).

        Args:
            holdings: List of holding dicts to display
        """
        for idx, holding in enumerate(holdings):
            row = self.rowCount()
            self.insertRow(row)

            # Set row label (1-based, excluding TOTAL row)
            row_header = QTableWidgetItem(str(idx + 1))
            self.setVerticalHeaderItem(row, row_header)

            # Ticker
            ticker_item = QTableWidgetItem(holding["ticker"])
            ticker_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 0, ticker_item)

            # Total Quantity
            qty_item = QTableWidgetItem(f"{holding['total_quantity']:.4f}")
            qty_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 1, qty_item)

            # Avg Cost Basis
            cost_item = QTableWidgetItem(f"${holding['avg_cost_basis']:.2f}")
            cost_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 2, cost_item)

            # Current Price
            price = holding.get("current_price")
            if price is not None:
                price_item = QTableWidgetItem(f"${price:.2f}")
            else:
                price_item = QTableWidgetItem("N/A")
            price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 3, price_item)

            # Market Value
            market_value = holding.get("market_value")
            if market_value is not None:
                mv_item = QTableWidgetItem(f"${market_value:,.2f}")
            else:
                mv_item = QTableWidgetItem("N/A")
            mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 4, mv_item)

            # P&L
            pnl = holding.get("total_pnl")
            if pnl is not None:
                if pnl == 0:
                    pnl_item = QTableWidgetItem("--")
                else:
                    pnl_item = QTableWidgetItem(f"${abs(pnl):,.2f}")
                    # Color coding
                    if pnl > 0:
                        pnl_item.setForeground(QColor(76, 153, 0))  # Green
                    elif pnl < 0:
                        pnl_item.setForeground(QColor(200, 50, 50))  # Red
            else:
                pnl_item = QTableWidgetItem("N/A")
            pnl_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 5, pnl_item)

            # Weight %
            weight_item = QTableWidgetItem(f"{holding['weight_pct']:.2f}%")
            weight_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 6, weight_item)

    def _add_totals_row(self, holdings: List[Dict[str, Any]], free_cash_summary: Dict[str, Any] = None):
        """
        Add a totals row at the top (row 0, pinned).
        Includes FREE CASH in total market value.

        Args:
            holdings: List of holdings to calculate totals from
            free_cash_summary: Optional FREE CASH summary to include in totals
        """
        # Calculate totals from holdings
        if holdings:
            totals = PortfolioService.calculate_portfolio_totals(holdings)
        else:
            totals = {
                "total_market_value": 0.0,
                "total_cost_basis": 0.0,
                "total_pnl": 0.0,
                "total_pnl_pct": 0.0
            }

        # Add FREE CASH to total market value
        total_market_value = totals.get("total_market_value", 0)
        if free_cash_summary:
            free_cash_value = free_cash_summary.get("market_value", 0) or 0
            total_market_value += free_cash_value

        # Insert at row 0
        self.insertRow(0)
        row = 0

        # Set vertical header label to blank for TOTAL row
        blank_header = QTableWidgetItem("")
        self.setVerticalHeaderItem(0, blank_header)

        # "TOTAL" label
        total_label = QTableWidgetItem("TOTAL")
        total_label.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        total_label.setFont(font)
        self.setItem(row, 0, total_label)

        # Empty cells for qty, avg cost, current price
        for col in [1, 2, 3]:
            empty_item = QTableWidgetItem("")
            self.setItem(row, col, empty_item)

        # Total Market Value (including FREE CASH)
        mv_item = QTableWidgetItem(f"${total_market_value:,.2f}")
        mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        mv_item.setFont(font)
        self.setItem(row, 4, mv_item)

        # Total P&L (FREE CASH has no P&L, so just use holdings P&L)
        total_pnl = totals['total_pnl']
        if total_pnl == 0:
            pnl_item = QTableWidgetItem("--")
        else:
            pnl_item = QTableWidgetItem(f"${abs(total_pnl):,.2f}")
            # Color coding
            if total_pnl > 0:
                pnl_item.setForeground(QColor(76, 153, 0))  # Green
            elif total_pnl < 0:
                pnl_item.setForeground(QColor(200, 50, 50))  # Red
        pnl_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        pnl_item.setFont(font)
        self.setItem(row, 5, pnl_item)

        # Weight is always 100%
        weight_item = QTableWidgetItem("100.00%")
        weight_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        weight_item.setFont(font)
        self.setItem(row, 6, weight_item)

    def _add_free_cash_row(self, free_cash_summary: Dict[str, Any], holdings: List[Dict[str, Any]]):
        """
        Add FREE CASH row after TOTAL row.

        Args:
            free_cash_summary: Dict with quantity, principal, market_value
            holdings: Holdings list for calculating total market value
        """
        row = self.rowCount()
        self.insertRow(row)

        # Set blank vertical header (no row number for FREE CASH)
        blank_header = QTableWidgetItem("")
        self.setVerticalHeaderItem(row, blank_header)

        # Calculate total market value including FREE CASH for weight calculation
        holdings_market_value = sum(h.get("market_value", 0) or 0 for h in holdings) if holdings else 0
        free_cash_value = free_cash_summary.get("market_value", 0) or 0
        total_market_value = holdings_market_value + free_cash_value

        # Calculate weight
        weight_pct = (free_cash_value / total_market_value * 100) if total_market_value > 0 else 0

        # Ticker
        ticker_item = QTableWidgetItem("FREE CASH")
        ticker_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 0, ticker_item)

        # Total Quantity (same as market value for cash since $1/unit)
        qty = free_cash_summary.get("quantity", 0)
        if qty != 0:
            qty_item = QTableWidgetItem(f"${qty:,.2f}")
        else:
            qty_item = QTableWidgetItem("--")
        qty_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 1, qty_item)

        # Avg Cost Basis ($1.00 for cash)
        cost_item = QTableWidgetItem("$1.00")
        cost_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 2, cost_item)

        # Current Price ($1.00 for cash)
        price_item = QTableWidgetItem("$1.00")
        price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 3, price_item)

        # Market Value
        if free_cash_value != 0:
            mv_item = QTableWidgetItem(f"${free_cash_value:,.2f}")
        else:
            mv_item = QTableWidgetItem("--")
        mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 4, mv_item)

        # P&L (always $0 for cash, show as "--")
        pnl_item = QTableWidgetItem("--")
        pnl_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 5, pnl_item)

        # Weight %
        weight_item = QTableWidgetItem(f"{weight_pct:.2f}%")
        weight_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 6, weight_item)

    def _on_header_clicked(self, column: int):
        """
        Handle column header click for custom sorting.
        Keeps TOTAL row pinned at top while sorting holdings.
        FREE CASH row sorts with regular holdings.

        Args:
            column: Column index that was clicked
        """
        if not self._holdings_data and not self._free_cash_summary:
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

        # Define sort key based on column
        sort_keys = {
            0: lambda h: h["ticker"].lower(),
            1: lambda h: h["total_quantity"],
            2: lambda h: h["avg_cost_basis"],
            3: lambda h: h.get("current_price") or 0,
            4: lambda h: h.get("market_value") or 0,
            5: lambda h: h.get("total_pnl") or 0,
            6: lambda h: h["weight_pct"],
        }

        key_func = sort_keys.get(column, lambda h: 0)
        reverse = self._current_sort_order == Qt.DescendingOrder

        # Sort the holdings data
        sorted_holdings = sorted(self._holdings_data, key=key_func, reverse=reverse) if self._holdings_data else []

        # Clear and repopulate (keeping TOTAL row pinned, FREE CASH row sorts with holdings)
        self.setRowCount(0)
        self._add_totals_row(self._holdings_data, self._free_cash_summary)

        # Add FREE CASH row if present
        if self._free_cash_summary and self._free_cash_summary.get("market_value", 0) != 0:
            self._add_free_cash_row(self._free_cash_summary, self._holdings_data)

        self._populate_holdings(sorted_holdings)

        # Update header sort indicator
        header = self.horizontalHeader()
        header.setSortIndicator(column, self._current_sort_order)

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme
        stylesheet = ThemeStylesheetService.get_table_stylesheet(theme)
        self.setStyleSheet(stylesheet)
