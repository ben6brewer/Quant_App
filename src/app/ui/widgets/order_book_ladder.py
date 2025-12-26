from __future__ import annotations

from typing import List, Tuple, Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QFont, QColor, QPalette, QPainter


class UnifiedOrderBookTable(QTableWidget):
    """
    Unified order book table with asks on top, bids on bottom, and one central price column.
    Volume bars extend from the center price column outward.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ask_volume_data = {}  # {row: bar_width_percent}
        self._bid_volume_data = {}  # {row: bar_width_percent}
        self._theme = "dark"
        self._num_levels = 11  # Number of levels to show on each side
    
    def set_theme(self, theme: str):
        """Set the theme."""
        self._theme = theme
        self.viewport().update()
    
    def set_volume_data(self, ask_volume_data: dict, bid_volume_data: dict):
        """Set volume data for bar rendering."""
        self._ask_volume_data = ask_volume_data
        self._bid_volume_data = bid_volume_data
        self.viewport().update()
    
    def paintEvent(self, event):
        """Paint volume bars in background, then paint cells on top."""
        # First paint the volume bars
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Paint ask bars (rows 0 to spread_row-1)
        ask_bar_color = QColor(59, 29, 34, 120) if self._theme == "dark" else QColor(255, 200, 200, 80)
        
        for row, bar_width_percent in self._ask_volume_data.items():
            if bar_width_percent > 0 and row < self.rowCount():
                self._paint_bar(painter, row, bar_width_percent, ask_bar_color, "ask")
        
        # Paint bid bars (rows spread_row+1 to end)
        bid_bar_color = QColor(25, 54, 38, 120) if self._theme == "dark" else QColor(200, 255, 200, 80)
        
        for row, bar_width_percent in self._bid_volume_data.items():
            if bar_width_percent > 0 and row < self.rowCount():
                self._paint_bar(painter, row, bar_width_percent, bid_bar_color, "bid")
        
        painter.end()
        
        # Now paint the normal table content on top
        super().paintEvent(event)
    
    def _paint_bar(self, painter, row, bar_width_percent, color, side):
        """Paint a volume bar for a specific row extending from center of price column."""
        # Get row position
        row_y = self.rowViewportPosition(row)
        row_height = self.rowHeight(row)
        
        # Calculate positions of columns
        # Columns: 0=Bid Total, 1=Bid Qty, 2=Price, 3=Ask Qty, 4=Ask Total
        bid_total_w = self.columnWidth(0)
        bid_qty_w = self.columnWidth(1)
        price_x = bid_total_w + bid_qty_w
        price_w = self.columnWidth(2)
        ask_qty_w = self.columnWidth(3)
        ask_total_w = self.columnWidth(4)
        
        # Calculate the CENTER of the price column
        price_center_x = price_x + (price_w // 2)
        
        # Calculate bar width based on the relevant side's columns
        if side == "bid":
            # Bid bars: extend from center of price column to the LEFT
            # Maximum width = bid_total + bid_qty columns + half of price column
            max_width = bid_total_w + bid_qty_w + (price_w // 2)
            bar_width = int(max_width * bar_width_percent / 100.0)
            
            # Bar starts at center of price column and extends left
            bar_rect = QRect(
                price_center_x - bar_width,
                row_y,
                bar_width,
                row_height
            )
        else:
            # Ask bars: extend from center of price column to the RIGHT
            # Maximum width = ask_qty + ask_total columns + half of price column
            max_width = ask_qty_w + ask_total_w + (price_w // 2)
            bar_width = int(max_width * bar_width_percent / 100.0)
            
            # Bar starts at center of price column and extends right
            bar_rect = QRect(
                price_center_x,
                row_y,
                bar_width,
                row_height
            )
        
        painter.fillRect(bar_rect, color)


class OrderBookLadderWidget(QWidget):
    """
    Traditional order book ladder display with asks on top, bids on bottom.
    Shows one central price column with volume bars extending outward.
    """
    
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent)
        self._theme = theme
        self._max_bid_volume = 0
        self._max_ask_volume = 0
        self._num_levels = 11  # Show 10 levels on each side
        
        self._setup_ui()
        self._apply_theme()
    
    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Spread header
        self.spread_header = QWidget()
        self.spread_header.setObjectName("spreadHeader")
        spread_layout = QHBoxLayout(self.spread_header)
        spread_layout.setContentsMargins(10, 8, 10, 8)
        
        self.spread_label = QLabel("Spread: --")
        self.spread_label.setObjectName("spreadLabel")
        spread_font = QFont()
        spread_font.setPointSize(11)
        spread_font.setBold(True)
        self.spread_label.setFont(spread_font)
        spread_layout.addWidget(self.spread_label, alignment=Qt.AlignCenter)
        
        layout.addWidget(self.spread_header)
        
        # Unified order book table
        self.order_table = UnifiedOrderBookTable(self)
        self.order_table.setObjectName("orderTable")
        self._configure_table()
        layout.addWidget(self.order_table)
    
    def _configure_table(self):
        """Configure the unified order book table."""
        table = self.order_table
        
        # 5 columns: Bid Total, Bid Qty, Price, Ask Qty, Ask Total
        table.setColumnCount(5)
        
        # Rows: num_levels (asks) + num_levels (bids) - NO spread row
        total_rows = self._num_levels * 2
        table.setRowCount(total_rows)
        
        # Set headers
        table.setHorizontalHeaderLabels(["Total", "Quantity", "Price", "Quantity", "Total"])
        
        # Configure header
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        
        # Set column widths
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Bid Total
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Bid Qty
        header.setSectionResizeMode(2, QHeaderView.Fixed)    # Price (fixed, narrower)
        table.setColumnWidth(2, 120)  # Narrower price column
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Ask Qty
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # Ask Total
        
        # Table properties
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFocusPolicy(Qt.NoFocus)
        table.setShowGrid(False)
        
        # Row heights - all same now (no spread row)
        for i in range(table.rowCount()):
            table.setRowHeight(i, 28)
        
        # Style
        table.setStyleSheet("""
            QTableWidget::item {
                padding: 4px 8px;
                border: none;
            }
        """)
    
    def set_theme(self, theme: str):
        """Set the theme."""
        self._theme = theme
        self.order_table.set_theme(theme)
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme styling."""
        if self._theme == "light":
            stylesheet = self._get_light_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()
        
        self.setStyleSheet(stylesheet)
    
    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet matching the screenshot."""
        return """
            QWidget {
                background-color: #1a1d2e;
                color: #ffffff;
            }
            #spreadHeader {
                background-color: #232739;
                border-bottom: 1px solid #2a2f45;
            }
            #spreadLabel {
                color: #8b92ab;
            }
            QTableWidget {
                background-color: #1a1d2e;
                border: none;
                gridline-color: transparent;
            }
            QTableWidget::item {
                border: none;
                padding: 4px 8px;
            }
            QHeaderView::section {
                background-color: #232739;
                color: #8b92ab;
                border: none;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            #orderTable {
                background-color: #1a1d2e;
            }
        """
    
    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            #spreadHeader {
                background-color: #f5f5f5;
                border-bottom: 1px solid #e0e0e0;
            }
            #spreadLabel {
                color: #666666;
            }
            QTableWidget {
                background-color: #ffffff;
                border: none;
                gridline-color: transparent;
            }
            QTableWidget::item {
                border: none;
                padding: 4px 8px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #666666;
                border: none;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            #orderTable {
                background-color: #ffffff;
            }
        """
    
    def update_order_book(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        spread: float,
        spread_pct: float,
    ):
        """
        Update the order book display.
        
        Args:
            bids: List of (price, quantity) tuples, sorted descending
            asks: List of (price, quantity) tuples, sorted ascending
            spread: Absolute spread value
            spread_pct: Spread percentage
        """
        # Update spread
        self.spread_label.setText(f"Spread: {spread:.2f} ({spread_pct:.3f}%)")
        
        # Calculate cumulative totals
        ask_totals = self._calculate_cumulative(asks)
        bid_totals = self._calculate_cumulative(bids)
        
        # IMPORTANT: Only consider the levels we're DISPLAYING for the maximum
        # Otherwise bars are scaled to off-screen data!
        displayed_ask_totals = ask_totals[:self._num_levels] if ask_totals else []
        displayed_bid_totals = bid_totals[:self._num_levels] if bid_totals else []
        
        # Find the UNIFIED maximum across displayed levels only
        max_ask = max(displayed_ask_totals) if displayed_ask_totals else 0
        max_bid = max(displayed_bid_totals) if displayed_bid_totals else 0
        unified_max_volume = max(max_ask, max_bid)
        
        # Store for reference
        self._max_ask_volume = max_ask
        self._max_bid_volume = max_bid
        
        # Calculate volume bar widths using UNIFIED maximum
        # The largest displayed bar will now take 100% of space!
        ask_volume_data = {}
        bid_volume_data = {}
        
        for i in range(min(len(asks), self._num_levels)):
            bar_percent = int((ask_totals[i] / unified_max_volume * 100)) if unified_max_volume > 0 else 0
            ask_volume_data[i] = bar_percent
        
        for i in range(min(len(bids), self._num_levels)):
            row_index = self._num_levels + i  # No spread row, so bids start at row 10
            bar_percent = int((bid_totals[i] / unified_max_volume * 100)) if unified_max_volume > 0 else 0
            bid_volume_data[row_index] = bar_percent
        
        # Update table with volume data
        self.order_table.set_volume_data(ask_volume_data, bid_volume_data)
        
        # Populate asks (top section, reversed so best ask is at bottom)
        # Asks are sorted ascending, so we want to reverse them for display
        asks_display = list(reversed(asks[:self._num_levels]))
        for i in range(len(asks_display)):
            price, qty = asks_display[i]
            total = ask_totals[len(asks_display) - 1 - i]
            
            row = i
            
            # Bid side (left): empty for ask rows
            empty_total = QTableWidgetItem("")
            empty_qty = QTableWidgetItem("")
            
            # Price (center)
            price_item = self._create_price_item(f"{price:,.2f}", is_ask=True)
            
            # Ask side (right): Quantity, Total
            qty_item = self._create_ask_item(f"{qty:.4f}")
            total_item = self._create_ask_item(f"{total:.4f}")
            
            self.order_table.setItem(row, 0, empty_total)
            self.order_table.setItem(row, 1, empty_qty)
            self.order_table.setItem(row, 2, price_item)
            self.order_table.setItem(row, 3, qty_item)
            self.order_table.setItem(row, 4, total_item)
        
        # Populate bids (bottom section - no spread row)
        for i in range(min(len(bids), self._num_levels)):
            price, qty = bids[i]
            total = bid_totals[i]
            
            row = self._num_levels + i
            
            # Bid side (left): Total, Quantity
            total_item = self._create_bid_item(f"{total:.4f}")
            qty_item = self._create_bid_item(f"{qty:.4f}")
            
            # Price (center)
            price_item = self._create_price_item(f"{price:,.2f}", is_ask=False)
            
            # Ask side (right): empty for bid rows
            empty_qty = QTableWidgetItem("")
            empty_total = QTableWidgetItem("")
            
            self.order_table.setItem(row, 0, total_item)
            self.order_table.setItem(row, 1, qty_item)
            self.order_table.setItem(row, 2, price_item)
            self.order_table.setItem(row, 3, empty_qty)
            self.order_table.setItem(row, 4, empty_total)
        
        # Clear remaining rows
        for i in range(len(asks_display), self._num_levels):
            for j in range(5):
                self.order_table.setItem(i, j, QTableWidgetItem(""))
        
        for i in range(len(bids), self._num_levels):
            row = self._num_levels + i
            for j in range(5):
                self.order_table.setItem(row, j, QTableWidgetItem(""))
    
    def _calculate_cumulative(self, orders: List[Tuple[float, float]]) -> List[float]:
        """Calculate cumulative totals."""
        cumulative = []
        total = 0
        for _, qty in orders:
            total += qty
            cumulative.append(total)
        return cumulative
    
    def _create_ask_item(self, text: str) -> QTableWidgetItem:
        """Create a table item for ask side with neutral text (now on right)."""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Left align (right side of table)
        
        font = QFont()
        font.setPointSize(10)
        item.setFont(font)
        
        if self._theme == "dark":
            item.setForeground(QColor(171, 178, 191))
        else:
            item.setForeground(QColor(80, 80, 80))
        
        return item
    
    def _create_bid_item(self, text: str) -> QTableWidgetItem:
        """Create a table item for bid side with neutral text (now on left)."""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # Right align (left side of table)
        
        font = QFont()
        font.setPointSize(10)
        item.setFont(font)
        
        if self._theme == "dark":
            item.setForeground(QColor(171, 178, 191))
        else:
            item.setForeground(QColor(80, 80, 80))
        
        return item
    
    def _create_price_item(self, text: str, is_ask: bool) -> QTableWidgetItem:
        """Create a price item (center column) with appropriate color."""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        item.setFont(font)
        
        if self._theme == "dark":
            if is_ask:
                item.setForeground(QColor(241, 108, 119))  # Red for asks
            else:
                item.setForeground(QColor(106, 188, 127))  # Green for bids
        else:
            if is_ask:
                item.setForeground(QColor(200, 0, 0))
            else:
                item.setForeground(QColor(0, 128, 0))
        
        return item
    
    def clear_order_book(self):
        """Clear the order book display."""
        self.spread_label.setText("Spread: --")
        
        # Clear volume data
        self.order_table.set_volume_data({}, {})
        
        # Clear all cells
        for i in range(self.order_table.rowCount()):
            for j in range(self.order_table.columnCount()):
                self.order_table.setItem(i, j, QTableWidgetItem(""))