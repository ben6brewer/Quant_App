"""Aggregate Portfolio Table Widget - Read-Only Holdings Display"""

from typing import List, Dict, Any
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.core.theme_manager import ThemeManager
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

    def update_holdings(self, holdings: List[Dict[str, Any]]):
        """
        Update table with aggregate holdings.

        Args:
            holdings: List of holding dicts from PortfolioService
        """
        # Store holdings data for sorting
        self._holdings_data = holdings.copy() if holdings else []

        # Clear existing
        self.setRowCount(0)

        if not holdings:
            return

        # Add totals row first (row 0, pinned at top)
        self._add_totals_row(holdings)

        # Add holdings starting from row 1
        self._populate_holdings(holdings)

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

    def _add_totals_row(self, holdings: List[Dict[str, Any]]):
        """
        Add a totals row at the top (row 0, pinned).

        Args:
            holdings: List of holdings to calculate totals from
        """
        if not holdings:
            return

        totals = PortfolioService.calculate_portfolio_totals(holdings)

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

        # Total Market Value
        mv_item = QTableWidgetItem(f"${totals['total_market_value']:,.2f}")
        mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        mv_item.setFont(font)
        self.setItem(row, 4, mv_item)

        # Total P&L
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

    def _on_header_clicked(self, column: int):
        """
        Handle column header click for custom sorting.
        Keeps TOTAL row pinned at top while sorting holdings.

        Args:
            column: Column index that was clicked
        """
        if not self._holdings_data:
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
        sorted_holdings = sorted(self._holdings_data, key=key_func, reverse=reverse)

        # Clear and repopulate (keeping TOTAL row)
        self.setRowCount(0)
        self._add_totals_row(self._holdings_data)  # Use original data for totals
        self._populate_holdings(sorted_holdings)

        # Update header sort indicator
        header = self.horizontalHeader()
        header.setSortIndicator(column, self._current_sort_order)

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
                alternate-background-color: #232323;
                color: #ffffff;
                gridline-color: #3d3d3d;
                border: 1px solid #3d3d3d;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 0px;
            }
            QTableWidget::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 8px;
                border: 1px solid #3d3d3d;
                font-weight: bold;
                font-size: 14px;
                text-align: left;
            }
            QTableCornerButton::section {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #3d3d3d;
                font-weight: bold;
                font-size: 11px;
                padding: 8px;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f5f5f5;
                color: #000000;
                gridline-color: #cccccc;
                border: 1px solid #cccccc;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 0px;
            }
            QTableWidget::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #333333;
                padding: 8px;
                border: 1px solid #cccccc;
                font-weight: bold;
                font-size: 14px;
                text-align: left;
            }
            QTableCornerButton::section {
                background-color: #f5f5f5;
                color: #333333;
                border: 1px solid #cccccc;
                font-weight: bold;
                font-size: 11px;
                padding: 8px;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QTableWidget {
                background-color: #000814;
                alternate-background-color: #0a0f1c;
                color: #e8e8e8;
                gridline-color: #1a2838;
                border: 1px solid #1a2838;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 0px;
            }
            QTableWidget::item:selected {
                background-color: #FF8000;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #0d1420;
                color: #a8a8a8;
                padding: 8px;
                border: 1px solid #1a2838;
                font-weight: bold;
                font-size: 14px;
                text-align: left;
            }
            QTableCornerButton::section {
                background-color: #0d1420;
                color: #a8a8a8;
                border: 1px solid #1a2838;
                font-weight: bold;
                font-size: 11px;
                padding: 8px;
            }
        """
