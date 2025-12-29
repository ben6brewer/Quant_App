"""Aggregate Portfolio Table Widget - Read-Only Holdings Display"""

from typing import List, Dict, Any
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
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
        "Total P&L",
        "Weight %"
    ]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

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

        # Read-only
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Enable sorting
        self.setSortingEnabled(True)

    def update_holdings(self, holdings: List[Dict[str, Any]]):
        """
        Update table with aggregate holdings.

        Args:
            holdings: List of holding dicts from PortfolioService
        """
        # Disable sorting while updating
        self.setSortingEnabled(False)

        # Clear existing
        self.setRowCount(0)

        if not holdings:
            self.setSortingEnabled(True)
            return

        # Holdings are already sorted by weight descending from PortfolioService

        for holding in holdings:
            row = self.rowCount()
            self.insertRow(row)

            # Ticker
            ticker_item = QTableWidgetItem(holding["ticker"])
            ticker_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 0, ticker_item)

            # Total Quantity
            qty_item = QTableWidgetItem(f"{holding['total_quantity']:.4f}")
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 1, qty_item)

            # Avg Cost Basis
            cost_item = QTableWidgetItem(f"${holding['avg_cost_basis']:.2f}")
            cost_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 2, cost_item)

            # Current Price
            price = holding.get("current_price")
            if price is not None:
                price_item = QTableWidgetItem(f"${price:.2f}")
            else:
                price_item = QTableWidgetItem("N/A")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 3, price_item)

            # Market Value
            market_value = holding.get("market_value")
            if market_value is not None:
                mv_item = QTableWidgetItem(f"${market_value:,.2f}")
            else:
                mv_item = QTableWidgetItem("N/A")
            mv_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 4, mv_item)

            # Total P&L
            pnl = holding.get("total_pnl")
            if pnl is not None:
                pnl_item = QTableWidgetItem(f"${pnl:+,.2f}")
                # Color coding
                if pnl > 0:
                    pnl_item.setForeground(QColor(76, 153, 0))  # Green
                elif pnl < 0:
                    pnl_item.setForeground(QColor(200, 50, 50))  # Red
            else:
                pnl_item = QTableWidgetItem("N/A")
            pnl_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 5, pnl_item)

            # Weight %
            weight_item = QTableWidgetItem(f"{holding['weight_pct']:.2f}%")
            weight_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 6, weight_item)

        # Add totals row (last row, bold)
        self._add_totals_row(holdings)

        # Re-enable sorting
        self.setSortingEnabled(True)

    def _add_totals_row(self, holdings: List[Dict[str, Any]]):
        """
        Add a totals row at the bottom.

        Args:
            holdings: List of holdings to calculate totals from
        """
        if not holdings:
            return

        totals = PortfolioService.calculate_portfolio_totals(holdings)

        row = self.rowCount()
        self.insertRow(row)

        # "TOTAL" label
        total_label = QTableWidgetItem("TOTAL")
        total_label.setTextAlignment(Qt.AlignCenter)
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
        mv_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        mv_item.setFont(font)
        self.setItem(row, 4, mv_item)

        # Total P&L
        pnl_item = QTableWidgetItem(f"${totals['total_pnl']:+,.2f}")
        pnl_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        pnl_item.setFont(font)
        # Color coding
        if totals['total_pnl'] > 0:
            pnl_item.setForeground(QColor(76, 153, 0))  # Green
        elif totals['total_pnl'] < 0:
            pnl_item.setForeground(QColor(200, 50, 50))  # Red
        self.setItem(row, 5, pnl_item)

        # Weight is always 100%
        weight_item = QTableWidgetItem("100.00%")
        weight_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        weight_item.setFont(font)
        self.setItem(row, 6, weight_item)

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
