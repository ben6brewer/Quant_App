from __future__ import annotations

from typing import List, Tuple, Optional
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from ..services import BinanceOrderBook
from .order_book_ladder import OrderBookLadderWidget

class DepthChartWidget(pg.PlotWidget):
    """
    Order book depth chart visualization.
    Shows bids and asks with cumulative volume.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setLabel("left", "Cumulative Volume")
        self.setLabel("bottom", "Price (USD)")
        self.showGrid(x=True, y=True, alpha=0.3)

        # Disable mouse dragging/panning - keep auto-scaling behavior
        self.setMouseEnabled(x=False, y=False)

        # Hide legend initially
        self.legend = None

        # Plot items
        self.bid_area = None
        self.ask_area = None
        self.bid_line = None
        self.ask_line = None

        # Theme colors
        self._theme = "dark"
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme colors."""
        if self._theme == "light":
            self.setBackground('w')
        elif self._theme == "bloomberg":
            self.setBackground('#0d1420')
        else:
            self.setBackground('#1e1e1e')
    
    def set_theme(self, theme: str):
        """Set the chart theme."""
        self._theme = theme
        self._apply_theme()
    
    def clear_depth(self):
        """Clear the depth chart."""
        if self.bid_area:
            self.removeItem(self.bid_area)
            self.bid_area = None
        if self.ask_area:
            self.removeItem(self.ask_area)
            self.ask_area = None
        if self.bid_line:
            self.removeItem(self.bid_line)
            self.bid_line = None
        if self.ask_line:
            self.removeItem(self.ask_line)
            self.ask_line = None
        if self.legend:
            try:
                self.legend.scene().removeItem(self.legend)
            except:
                pass
            self.legend = None
    
    def plot_depth(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
    ):
        """
        Plot order book depth.
        
        Args:
            bids: List of (price, quantity) tuples, sorted descending
            asks: List of (price, quantity) tuples, sorted ascending
        """
        self.clear_depth()
        
        if not bids and not asks:
            return
        
        # Calculate cumulative volumes
        bid_prices = [price for price, _ in bids]
        bid_volumes = [qty for _, qty in bids]
        bid_cumulative = np.cumsum(bid_volumes[::-1])[::-1]  # Cumulative from best bid down
        
        ask_prices = [price for price, _ in asks]
        ask_volumes = [qty for _, qty in asks]
        ask_cumulative = np.cumsum(ask_volumes)  # Cumulative from best ask up
        
        # Colors (green for bids, red for asks)
        bid_color = (76, 175, 80, 150)  # Green with transparency
        ask_color = (244, 67, 54, 150)  # Red with transparency
        bid_line_color = (76, 175, 80, 255)
        ask_line_color = (244, 67, 54, 255)
        
        # Plot bid area (filled)
        if bid_prices and bid_cumulative.size > 0:
            # Create step plot for bids
            bid_x = []
            bid_y = []
            for i in range(len(bid_prices)):
                bid_x.append(bid_prices[i])
                bid_y.append(bid_cumulative[i])
                if i < len(bid_prices) - 1:
                    bid_x.append(bid_prices[i+1])
                    bid_y.append(bid_cumulative[i])
            
            # Add area fill
            self.bid_area = pg.FillBetweenItem(
                pg.PlotCurveItem(bid_x, bid_y),
                pg.PlotCurveItem(bid_x, [0] * len(bid_x)),
                brush=pg.mkBrush(bid_color)
            )
            self.addItem(self.bid_area)
            
            # Add line
            self.bid_line = self.plot(
                bid_x, bid_y,
                pen=pg.mkPen(color=bid_line_color, width=2),
                name="Bids"
            )
        
        # Plot ask area (filled)
        if ask_prices and ask_cumulative.size > 0:
            # Create step plot for asks
            ask_x = []
            ask_y = []
            for i in range(len(ask_prices)):
                ask_x.append(ask_prices[i])
                ask_y.append(ask_cumulative[i])
                if i < len(ask_prices) - 1:
                    ask_x.append(ask_prices[i+1])
                    ask_y.append(ask_cumulative[i])
            
            # Add area fill
            self.ask_area = pg.FillBetweenItem(
                pg.PlotCurveItem(ask_x, ask_y),
                pg.PlotCurveItem(ask_x, [0] * len(ask_x)),
                brush=pg.mkBrush(ask_color)
            )
            self.addItem(self.ask_area)
            
            # Add line
            self.ask_line = self.plot(
                ask_x, ask_y,
                pen=pg.mkPen(color=ask_line_color, width=2),
                name="Asks"
            )
        
        # Add legend
        self.legend = self.addLegend(offset=(10, 10))
        
        # Auto-range to fit data
        self.autoRange()


class OrderBookPanel(LazyThemeMixin, QWidget):
    """
    Panel showing order book in ladder format (default) with optional depth chart.
    """

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self.binance_api = BinanceOrderBook()
        self.current_ticker = None

        # Update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._refresh_data)

        self._setup_ui()
        self._apply_theme()

        # Connect to theme changes (lazy - only apply when visible)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy_panel)

    def _on_theme_changed_lazy_panel(self) -> None:
        """Handle theme change with visibility check."""
        if self.isVisible():
            self._apply_theme()
        else:
            self._theme_dirty = True

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()
    
    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with view toggle
        self.header = QWidget()
        self.header.setObjectName("depthHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.setSpacing(10)
        
        # Title
        title = QLabel("Order Book")
        title.setObjectName("depthTitle")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # View toggle buttons
        self.ladder_btn = QPushButton("Ladder")
        self.ladder_btn.setCheckable(True)
        self.ladder_btn.setChecked(True)
        self.ladder_btn.setMaximumWidth(80)
        self.ladder_btn.clicked.connect(lambda: self._switch_view("ladder"))
        header_layout.addWidget(self.ladder_btn)
        
        self.chart_btn = QPushButton("Chart")
        self.chart_btn.setCheckable(True)
        self.chart_btn.setMaximumWidth(80)
        self.chart_btn.clicked.connect(lambda: self._switch_view("chart"))
        header_layout.addWidget(self.chart_btn)
        
        layout.addWidget(self.header)
        
        # Stacked widget for views
        self.view_stack = QStackedWidget()
        
        # Order book ladder (default view)
        self.ladder_widget = OrderBookLadderWidget(theme=self.theme_manager.current_theme)
        self.view_stack.addWidget(self.ladder_widget)
        
        # Depth chart
        self.depth_chart = DepthChartWidget()
        self.view_stack.addWidget(self.depth_chart)
        
        layout.addWidget(self.view_stack, stretch=1)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
    
    def _switch_view(self, view: str):
        """Switch between ladder and chart views."""
        if view == "ladder":
            self.view_stack.setCurrentIndex(0)
            self.ladder_btn.setChecked(True)
            self.chart_btn.setChecked(False)
        else:
            self.view_stack.setCurrentIndex(1)
            self.ladder_btn.setChecked(False)
            self.chart_btn.setChecked(True)
    
    def _apply_theme(self):
        """Apply theme styling to panel and child widgets."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)
        # Also update child widgets
        self.depth_chart.set_theme(theme)
        self.ladder_widget.set_theme(theme)
    
    def _get_dark_stylesheet(self) -> str:
        """Get dark theme stylesheet."""
        return """
            QWidget {
                background-color: #1a1d2e;
                color: #ffffff;
            }
            #depthHeader {
                background-color: #232739;
                border-bottom: 1px solid #2a2f45;
            }
            #depthTitle {
                color: #ffffff;
                background-color: transparent;
            }
            #statusLabel {
                color: #8b92ab;
                background-color: transparent;
                font-size: 10px;
                font-style: italic;
                padding: 5px;
            }
            QPushButton {
                background-color: #2a2f45;
                color: #8b92ab;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #343a52;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #00d4ff;
                color: #1a1d2e;
            }
        """
    
    def _get_light_stylesheet(self) -> str:
        """Get light theme stylesheet."""
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            #depthHeader {
                background-color: #f5f5f5;
                border-bottom: 2px solid #0066cc;
            }
            #depthTitle {
                color: #0066cc;
                background-color: transparent;
            }
            #statusLabel {
                color: #666666;
                background-color: transparent;
                font-size: 10px;
                font-style: italic;
                padding: 5px;
            }
            QPushButton {
                background-color: #e8e8e8;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d8d8d8;
                color: #000000;
            }
            QPushButton:checked {
                background-color: #0066cc;
                color: #ffffff;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Get Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            #depthHeader {
                background-color: #0a1018;
                border-bottom: 2px solid #FF8000;
            }
            #depthTitle {
                color: #FF8000;
                background-color: transparent;
            }
            #statusLabel {
                color: #b0b0b0;
                background-color: transparent;
                font-size: 10px;
                font-style: italic;
                padding: 5px;
            }
            QPushButton {
                background-color: #0a1018;
                color: #b0b0b0;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #FF8000;
            }
            QPushButton:checked {
                background-color: #FF8000;
                color: #000000;
            }
        """

    def set_ticker(self, ticker: str):
        """Set the ticker to display depth for."""
        self.current_ticker = ticker
        
        if not BinanceOrderBook.is_binance_ticker(ticker):
            self.clear_depth()
            self.status_label.setText(f"{ticker} is not available on Binance")
            self.stop_updates()
            return
        
        self.status_label.setText("Loading...")
        self._refresh_data()
        self.start_updates()
    
    def _refresh_data(self):
        """Refresh order book data."""
        if not self.current_ticker:
            return
        
        if not BinanceOrderBook.is_binance_ticker(self.current_ticker):
            return
        
        # Fetch order book with more levels for ladder view
        summary = self.binance_api.get_depth_summary(self.current_ticker, levels=500)
        
        if not summary:
            self.status_label.setText("Failed to fetch depth data")
            return
        
        # Update ladder widget
        self.ladder_widget.update_order_book(
            summary["bids"],
            summary["asks"],
            summary["spread"],
            summary["spread_pct"],
        )
        
        # Update depth chart
        self.depth_chart.plot_depth(summary["bids"], summary["asks"])
        
        # Update status
        timestamp = summary["timestamp"].strftime("%H:%M:%S")
        source = "Binance.US" if "binance.us" in summary.get("source", "") else "Binance"
        self.status_label.setText(f"Updated: {timestamp} • {source}")
    
    def start_updates(self, interval_ms: int = 500):
        """Start automatic updates (500 ms for ladder view)."""
        self.update_timer.start(interval_ms)
    
    def stop_updates(self):
        """Stop automatic updates."""
        self.update_timer.stop()
    
    def clear_depth(self):
        """Clear the depth chart and ladder."""
        self.depth_chart.clear_depth()
        self.ladder_widget.clear_order_book()
        self.status_label.setText("")
    
    def closeEvent(self, event):
        """Stop updates when widget is closed."""
        self.stop_updates()
        super().closeEvent(event)