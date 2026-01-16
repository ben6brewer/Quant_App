"""Aggregate Portfolio Table Widget - Read-Only Holdings Display"""

from typing import List, Dict, Any
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.core.theme_manager import ThemeManager
from app.services.theme_stylesheet_service import ThemeStylesheetService
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from ..services.portfolio_service import PortfolioService


class AggregatePortfolioTable(LazyThemeMixin, QTableWidget):
    """
    Read-only aggregate portfolio table (right side).
    Shows holdings grouped by ticker with totals.
    """

    # Columns
    COLUMNS = [
        "Ticker",
        "Name",
        "Quantity",
        "Avg Cost Basis",
        "Current Price",
        "Market Value",
        "P&L",
        "Weight"
    ]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self._holdings_data: List[Dict[str, Any]] = []
        self._free_cash_summary: Dict[str, Any] = None  # FREE CASH summary data
        self._ticker_names: Dict[str, str] = {}  # ticker -> short name
        self._current_sort_column: int = -1
        self._current_sort_order: Qt.SortOrder = Qt.DescendingOrder

        self._setup_table()
        self._apply_theme()

        # Lazy theme - only apply when visible
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_table(self):
        """Configure table structure."""
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # Column sizing: Ticker narrow, Name wide, others stretch equally
        header = self.horizontalHeader()
        # Ticker - fixed narrow width
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 100)
        # Name - stretch with higher weight (takes extra space)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(1, 300)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.setColumnWidth(2, 100)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.setColumnWidth(3, 175)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.setColumnWidth(4, 175)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Stretch)
        # Other columns stretch equally

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

        # Enable smooth pixel-based scrolling instead of item-based
        self.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

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

    def update_holdings(self, holdings: List[Dict[str, Any]], free_cash_summary: Dict[str, Any] = None, ticker_names: Dict[str, str] = None):
        """
        Update table with aggregate holdings.

        Args:
            holdings: List of holding dicts from PortfolioService
            free_cash_summary: Optional FREE CASH summary dict with quantity, principal, market_value
            ticker_names: Optional dict mapping ticker -> short name
        """
        # Store holdings data for sorting
        self._holdings_data = holdings.copy() if holdings else []
        self._free_cash_summary = free_cash_summary
        self._ticker_names = ticker_names or {}

        # Calculate total market value including FREE CASH
        holdings_market_value = sum(
            h.get("market_value", 0) or 0 for h in self._holdings_data
        )
        free_cash_value = free_cash_summary.get("market_value", 0) or 0 if free_cash_summary else 0
        total_market_value = holdings_market_value + free_cash_value

        # Recalculate weight percentages to include FREE CASH in total
        if total_market_value > 0:
            for holding in self._holdings_data:
                if holding.get("market_value") is not None:
                    holding["weight_pct"] = (
                        holding["market_value"] / total_market_value
                    ) * 100

        # Add FREE CASH as a regular holding so it sorts with other assets
        if free_cash_summary and free_cash_value != 0:
            free_cash_weight = (free_cash_value / total_market_value * 100) if total_market_value > 0 else 0
            free_cash_holding = {
                "ticker": "FREE CASH",
                "total_quantity": free_cash_value,  # For cash, quantity = market value
                "avg_cost_basis": 1.0,  # Cash is always $1/unit
                "current_price": 1.0,  # Cash is always $1/unit
                "market_value": free_cash_value,
                "total_pnl": 0.0,  # Cash has no P&L
                "weight_pct": free_cash_weight,
                "_is_free_cash": True  # Internal flag to identify FREE CASH row
            }
            self._holdings_data.append(free_cash_holding)

        # Clear existing
        self.setRowCount(0)

        # Add totals row first (row 0, pinned at top) - includes FREE CASH in total
        self._add_totals_row(holdings, free_cash_summary)

        # Add all holdings (including FREE CASH) starting after TOTAL
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

            is_free_cash = holding.get("_is_free_cash", False)
            ticker = holding["ticker"]

            # Ticker
            ticker_item = QTableWidgetItem(ticker)
            ticker_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 0, ticker_item)

            # Name
            name = self._ticker_names.get(ticker, "") or ""
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 1, name_item)

            # Quantity - format as dollar amount for FREE CASH, otherwise 2 decimals without trailing zeroes
            if is_free_cash:
                qty = holding['total_quantity']
                if qty != 0:
                    qty_item = QTableWidgetItem(f"${qty:,.2f}")
                else:
                    qty_item = QTableWidgetItem("--")
            else:
                # Format to 2 decimals, strip trailing zeroes and trailing decimal point
                qty_str = f"{holding['total_quantity']:.2f}".rstrip('0').rstrip('.')
                qty_item = QTableWidgetItem(qty_str)
            qty_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 2, qty_item)

            # Avg Cost Basis
            cost_item = QTableWidgetItem(f"${holding['avg_cost_basis']:.2f}")
            cost_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 3, cost_item)

            # Current Price
            price = holding.get("current_price")
            if price is not None:
                price_item = QTableWidgetItem(f"${price:.2f}")
            else:
                price_item = QTableWidgetItem("N/A")
            price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 4, price_item)

            # Market Value
            market_value = holding.get("market_value")
            if market_value is not None:
                mv_item = QTableWidgetItem(f"${market_value:,.2f}")
            else:
                mv_item = QTableWidgetItem("N/A")
            mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 5, mv_item)

            # P&L - FREE CASH always shows "--"
            if is_free_cash:
                pnl_item = QTableWidgetItem("--")
            else:
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
            self.setItem(row, 6, pnl_item)

            # Weight %
            weight_item = QTableWidgetItem(f"{holding['weight_pct']:.2f}%")
            weight_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 7, weight_item)

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

        # Empty cells for name, qty, avg cost, current price
        for col in [1, 2, 3, 4]:
            empty_item = QTableWidgetItem("")
            self.setItem(row, col, empty_item)

        # Total Market Value (including FREE CASH)
        mv_item = QTableWidgetItem(f"${total_market_value:,.2f}")
        mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        mv_item.setFont(font)
        self.setItem(row, 5, mv_item)

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
        self.setItem(row, 6, pnl_item)

        # Weight is always 100%
        weight_item = QTableWidgetItem("100.00%")
        weight_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        weight_item.setFont(font)
        self.setItem(row, 7, weight_item)

    def _on_header_clicked(self, column: int):
        """
        Handle column header click for custom sorting.
        Keeps TOTAL row pinned at top while sorting all holdings (including FREE CASH).

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
            1: lambda h: (self._ticker_names.get(h["ticker"]) or "").lower(),
            2: lambda h: h["total_quantity"],
            3: lambda h: h["avg_cost_basis"],
            4: lambda h: h.get("current_price") or 0,
            5: lambda h: h.get("market_value") or 0,
            6: lambda h: h.get("total_pnl") or 0,
            7: lambda h: h["weight_pct"],
        }

        key_func = sort_keys.get(column, lambda h: 0)
        reverse = self._current_sort_order == Qt.DescendingOrder

        # Sort all holdings data (including FREE CASH)
        sorted_holdings = sorted(self._holdings_data, key=key_func, reverse=reverse)

        # Clear and repopulate (keeping TOTAL row pinned)
        self.setRowCount(0)

        # Get holdings without FREE CASH for totals calculation
        regular_holdings = [h for h in self._holdings_data if not h.get("_is_free_cash")]
        self._add_totals_row(regular_holdings, self._free_cash_summary)

        # Populate sorted holdings (including FREE CASH)
        self._populate_holdings(sorted_holdings)

        # Update header sort indicator
        header = self.horizontalHeader()
        header.setSortIndicator(column, self._current_sort_order)

    def update_live_prices(self, prices: Dict[str, float]) -> None:
        """
        Update current prices in-place without full table refresh.

        Updates Current Price, Market Value, P&L, and Weight columns
        for tickers that have new prices. Also updates the TOTAL row.

        Args:
            prices: Dict mapping ticker -> current price
        """
        if not prices or not self._holdings_data:
            return

        # Track if any holding was updated
        holdings_updated = False

        # First, update holdings data and collect updated values
        for holding in self._holdings_data:
            ticker = holding["ticker"]

            # Skip FREE CASH - price is always $1
            if holding.get("_is_free_cash"):
                continue

            if ticker in prices:
                new_price = prices[ticker]
                old_price = holding.get("current_price")

                # Skip if price unchanged
                if old_price == new_price:
                    continue

                # Update holding data
                holding["current_price"] = new_price
                quantity = holding["total_quantity"]
                cost_basis = holding["avg_cost_basis"]

                # Recalculate derived values
                holding["market_value"] = quantity * new_price
                holding["total_pnl"] = (new_price - cost_basis) * quantity

                holdings_updated = True

        if not holdings_updated:
            return

        # Recalculate weights based on new total market value
        holdings_market_value = sum(
            h.get("market_value", 0) or 0
            for h in self._holdings_data
            if not h.get("_is_free_cash")
        )
        free_cash_value = 0
        for h in self._holdings_data:
            if h.get("_is_free_cash"):
                free_cash_value = h.get("market_value", 0) or 0
                break

        total_market_value = holdings_market_value + free_cash_value

        if total_market_value > 0:
            for holding in self._holdings_data:
                mv = holding.get("market_value", 0) or 0
                holding["weight_pct"] = (mv / total_market_value) * 100

        # Now update the displayed cells
        # Row 0 is TOTAL row, holdings start at row 1
        for row in range(1, self.rowCount()):
            ticker_item = self.item(row, 0)  # Ticker column
            if not ticker_item:
                continue
            ticker = ticker_item.text()

            # Find corresponding holding
            holding = None
            for h in self._holdings_data:
                if h["ticker"] == ticker:
                    holding = h
                    break

            if not holding or ticker not in prices:
                continue

            # Skip FREE CASH
            if holding.get("_is_free_cash"):
                continue

            # Update Current Price (column 4)
            price = holding["current_price"]
            price_item = QTableWidgetItem(f"${price:.2f}")
            price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 4, price_item)

            # Update Market Value (column 5)
            market_value = holding.get("market_value")
            if market_value is not None:
                mv_item = QTableWidgetItem(f"${market_value:,.2f}")
            else:
                mv_item = QTableWidgetItem("N/A")
            mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 5, mv_item)

            # Update P&L (column 6)
            pnl = holding.get("total_pnl")
            if pnl is not None:
                if pnl == 0:
                    pnl_item = QTableWidgetItem("--")
                else:
                    pnl_item = QTableWidgetItem(f"${abs(pnl):,.2f}")
                    if pnl > 0:
                        pnl_item.setForeground(QColor(76, 153, 0))  # Green
                    elif pnl < 0:
                        pnl_item.setForeground(QColor(200, 50, 50))  # Red
            else:
                pnl_item = QTableWidgetItem("N/A")
            pnl_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 6, pnl_item)

            # Update Weight (column 7)
            weight_item = QTableWidgetItem(f"{holding['weight_pct']:.2f}%")
            weight_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.setItem(row, 7, weight_item)

        # Update TOTAL row (row 0)
        self._update_totals_row()

    def _update_totals_row(self) -> None:
        """Update the TOTAL row with current totals from holdings data."""
        if self.rowCount() == 0:
            return

        # Calculate totals from holdings (excluding FREE CASH for P&L)
        total_market_value = 0.0
        total_pnl = 0.0

        for holding in self._holdings_data:
            market_value = holding.get("market_value", 0) or 0
            total_market_value += market_value

            # FREE CASH has no P&L
            if not holding.get("_is_free_cash"):
                pnl = holding.get("total_pnl", 0) or 0
                total_pnl += pnl

        # Update Market Value cell (column 5, row 0)
        mv_item = QTableWidgetItem(f"${total_market_value:,.2f}")
        mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        mv_item.setFont(font)
        self.setItem(0, 5, mv_item)

        # Update P&L cell (column 6, row 0)
        if total_pnl == 0:
            pnl_item = QTableWidgetItem("--")
        else:
            pnl_item = QTableWidgetItem(f"${abs(total_pnl):,.2f}")
            if total_pnl > 0:
                pnl_item.setForeground(QColor(76, 153, 0))
            elif total_pnl < 0:
                pnl_item.setForeground(QColor(200, 50, 50))
        pnl_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = QFont()
        font.setBold(True)
        pnl_item.setFont(font)
        self.setItem(0, 6, pnl_item)

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme
        stylesheet = ThemeStylesheetService.get_table_stylesheet(theme)
        self.setStyleSheet(stylesheet)
