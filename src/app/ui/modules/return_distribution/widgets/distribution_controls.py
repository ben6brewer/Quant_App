"""Distribution Controls Widget - Top Control Bar for Return Distribution module."""

from typing import List, Optional, Tuple
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.core.config import CHART_INTERVALS
from app.ui.widgets.common import (
    LazyThemeMixin,
    PortfolioTickerComboBox,
    BenchmarkComboBox,
)


class DistributionControls(LazyThemeMixin, QWidget):
    """
    Control bar at top of return distribution module.
    Contains: Home button, Portfolio selector, Metric selector, Interval selector, Date Range selector, Settings button.
    """

    # Signals
    home_clicked = Signal()
    portfolio_changed = Signal(str)
    metric_changed = Signal(str)
    window_changed = Signal(str)
    interval_changed = Signal(str)
    benchmark_changed = Signal(str)  # Emits ticker/portfolio name or empty string
    date_range_changed = Signal(str, str)  # start_date, end_date (empty for "All")
    custom_date_range_requested = Signal()  # Open date range dialog
    settings_clicked = Signal()

    # Metric options
    METRIC_OPTIONS = [
        "Returns",
        "Volatility",
        "Rolling Volatility",
        "Drawdown",
        "Rolling Return",
        "Time Under Water",
    ]

    # Window options for rolling metrics
    ROLLING_VOL_WINDOWS = ["1 Month", "3 Months", "6 Months", "1 Year"]
    ROLLING_RETURN_WINDOWS = ["1 Month", "3 Months", "1 Year", "3 Years", "5 Years"]

    # Date range presets
    DATE_RANGE_OPTIONS = ["All", "1Y", "3Y", "5Y", "Custom Date Range..."]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self._custom_start_date: Optional[str] = None
        self._custom_end_date: Optional[str] = None

        self._setup_ui()
        self._apply_theme()

        # Lazy theme - only apply when visible
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup control bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Home button (leftmost)
        self.home_btn = QPushButton("Home")
        self.home_btn.setFixedSize(100, 40)
        self.home_btn.setObjectName("home_btn")
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        # Add stretch to push controls toward center
        layout.addStretch(1)

        # Portfolio selector (editable - can type ticker or select portfolio)
        self.portfolio_label = QLabel("Portfolio:")
        self.portfolio_label.setObjectName("control_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = PortfolioTickerComboBox()
        self.portfolio_combo.setFixedWidth(250)
        self.portfolio_combo.setFixedHeight(40)
        self.portfolio_combo.value_changed.connect(self.portfolio_changed.emit)
        layout.addWidget(self.portfolio_combo)

        layout.addSpacing(20)

        # Benchmark selector (editable combo box) - right after Portfolio
        self.benchmark_label = QLabel("Benchmark:")
        self.benchmark_label.setObjectName("control_label")
        layout.addWidget(self.benchmark_label)
        self.benchmark_combo = BenchmarkComboBox()
        self.benchmark_combo.setFixedWidth(250)
        self.benchmark_combo.setFixedHeight(40)
        self.benchmark_combo.value_changed.connect(self.benchmark_changed.emit)
        layout.addWidget(self.benchmark_combo)

        layout.addSpacing(20)

        # Metric selector
        self.metric_label = QLabel("Metric:")
        self.metric_label.setObjectName("control_label")
        layout.addWidget(self.metric_label)
        self.metric_combo = QComboBox()
        self.metric_combo.setFixedWidth(160)
        self.metric_combo.setFixedHeight(40)
        self.metric_combo.addItems(self.METRIC_OPTIONS)
        self.metric_combo.setCurrentText("Returns")
        self.metric_combo.currentTextChanged.connect(self._on_metric_changed)
        layout.addWidget(self.metric_combo)

        # Window selector (for rolling metrics - hidden by default)
        self.window_label = QLabel("Window:")
        self.window_label.setObjectName("control_label")
        self.window_label.setVisible(False)
        layout.addWidget(self.window_label)
        self.window_combo = QComboBox()
        self.window_combo.setFixedWidth(120)
        self.window_combo.setFixedHeight(40)
        self.window_combo.setVisible(False)
        self.window_combo.currentTextChanged.connect(self._on_window_changed)
        layout.addWidget(self.window_combo)

        layout.addSpacing(20)

        # Interval selector (only shown for Returns metric)
        self.interval_label = QLabel("Interval:")
        self.interval_label.setObjectName("control_label")
        layout.addWidget(self.interval_label)
        self.interval_combo = QComboBox()
        self.interval_combo.setFixedWidth(120)
        self.interval_combo.setFixedHeight(40)
        self.interval_combo.addItems(CHART_INTERVALS)
        self.interval_combo.setCurrentText("Daily")
        self.interval_combo.currentTextChanged.connect(self.interval_changed.emit)
        layout.addWidget(self.interval_combo)

        layout.addSpacing(20)

        # Date range selector
        self.date_range_label = QLabel("Date Range:")
        self.date_range_label.setObjectName("control_label")
        layout.addWidget(self.date_range_label)
        self.date_range_combo = QComboBox()
        self.date_range_combo.setFixedWidth(180)
        self.date_range_combo.setFixedHeight(40)
        self.date_range_combo.addItems(self.DATE_RANGE_OPTIONS)
        self.date_range_combo.setCurrentText("All")
        self.date_range_combo.currentTextChanged.connect(self._on_date_range_changed)
        layout.addWidget(self.date_range_combo)

        # Add stretch to push settings button to the right
        layout.addStretch(1)

        # Settings button (right-aligned)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedSize(100, 40)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def _on_metric_changed(self, metric: str):
        """Handle metric dropdown selection."""
        # Show/hide window dropdown based on metric
        if metric == "Rolling Volatility":
            self.window_combo.blockSignals(True)
            self.window_combo.clear()
            self.window_combo.addItems(self.ROLLING_VOL_WINDOWS)
            self.window_combo.setCurrentText("1 Month")
            self.window_combo.blockSignals(False)
            self.window_label.setVisible(True)
            self.window_combo.setVisible(True)
        elif metric == "Rolling Return":
            self.window_combo.blockSignals(True)
            self.window_combo.clear()
            self.window_combo.addItems(self.ROLLING_RETURN_WINDOWS)
            self.window_combo.setCurrentText("1 Year")
            self.window_combo.blockSignals(False)
            self.window_label.setVisible(True)
            self.window_combo.setVisible(True)
        else:
            self.window_label.setVisible(False)
            self.window_combo.setVisible(False)

        # Show/hide interval dropdown (only for Returns)
        show_interval = metric == "Returns"
        self.interval_label.setVisible(show_interval)
        self.interval_combo.setVisible(show_interval)

        # Benchmark dropdown is always visible (works for all metrics)

        # Emit metric change signal
        self.metric_changed.emit(metric)

    def _on_window_changed(self, window: str):
        """Handle window dropdown selection."""
        if window:
            self.window_changed.emit(window)

    def _on_date_range_changed(self, option: str):
        """Handle date range dropdown selection."""
        from datetime import datetime, timedelta

        if option == "Custom Date Range...":
            # Request custom date range dialog
            self.custom_date_range_requested.emit()
            return

        # Calculate date range based on preset
        end_date = datetime.now().strftime("%Y-%m-%d")

        if option == "All":
            # Empty dates mean "all available data"
            self.date_range_changed.emit("", "")
        elif option == "1Y":
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            self.date_range_changed.emit(start_date, end_date)
        elif option == "3Y":
            start_date = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
            self.date_range_changed.emit(start_date, end_date)
        elif option == "5Y":
            start_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
            self.date_range_changed.emit(start_date, end_date)

    def update_benchmark_list(self, portfolios: List[str]):
        """
        Update the benchmark dropdown with available portfolios.

        Args:
            portfolios: List of portfolio names
        """
        self.benchmark_combo.set_portfolios(portfolios)

    def set_custom_date_range(self, start_date: str, end_date: str):
        """
        Set a custom date range (called after user confirms dialog).

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        """
        self._custom_start_date = start_date
        self._custom_end_date = end_date

        # Update dropdown text to show custom range
        self.date_range_combo.blockSignals(True)
        # Add or update custom item
        custom_text = f"{start_date} to {end_date}"
        custom_index = self.date_range_combo.findText(custom_text)
        if custom_index == -1:
            # Remove any previous custom range
            for i in range(self.date_range_combo.count()):
                item_text = self.date_range_combo.itemText(i)
                if " to " in item_text and item_text != "Custom Date Range...":
                    self.date_range_combo.removeItem(i)
                    break
            # Insert before "Custom Date Range..."
            insert_index = self.date_range_combo.count() - 1
            self.date_range_combo.insertItem(insert_index, custom_text)
            custom_index = insert_index

        self.date_range_combo.setCurrentIndex(custom_index)
        self.date_range_combo.blockSignals(False)

        # Emit the date range
        self.date_range_changed.emit(start_date, end_date)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        """
        Update portfolio dropdown.

        Args:
            portfolios: List of portfolio names
            current: Currently selected portfolio name (None to show placeholder)
        """
        self.portfolio_combo.set_portfolios(portfolios, current)

    def get_current_portfolio(self) -> str:
        """Get currently selected portfolio name (with [Port] prefix if portfolio)."""
        return self.portfolio_combo.get_value()

    def get_current_interval(self) -> str:
        """Get currently selected interval."""
        return self.interval_combo.currentText() or "Daily"

    def get_current_metric(self) -> str:
        """Get currently selected metric."""
        return self.metric_combo.currentText() or "Returns"

    def get_current_window(self) -> str:
        """Get currently selected window for rolling metrics."""
        return self.window_combo.currentText() or ""

    def get_current_benchmark(self) -> str:
        """
        Get currently selected benchmark.

        Returns:
            Benchmark ticker/portfolio name, or empty string if none selected.
        """
        return self.benchmark_combo.get_value()

    def reset_benchmark(self):
        """Reset the benchmark dropdown to show placeholder."""
        self.benchmark_combo.reset()

    def get_current_date_range(self) -> Tuple[str, str]:
        """
        Get currently selected date range.

        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format.
            Empty strings mean "all available data".
        """
        option = self.date_range_combo.currentText()

        if option == "All":
            return ("", "")
        elif " to " in option:
            # Custom range displayed
            parts = option.split(" to ")
            return (parts[0], parts[1])
        else:
            # Calculate from preset
            from datetime import datetime, timedelta

            end_date = datetime.now().strftime("%Y-%m-%d")

            if option == "1Y":
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            elif option == "3Y":
                start_date = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
            elif option == "5Y":
                start_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
            else:
                return ("", "")

            return (start_date, end_date)

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
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
            }
            QLabel#control_label {
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #00d4ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #ffffff;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
                font-size: 14px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #252525;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #00d4ff;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
            }
            QLabel#control_label {
                color: #000000;
                font-size: 14px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #0066cc;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #000000;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #f5f5f5;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
                font-size: 14px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #e8e8e8;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: #000814;
                color: #e8e8e8;
            }
            QLabel {
                color: #a8a8a8;
                font-size: 13px;
            }
            QLabel#control_label {
                color: #e8e8e8;
                font-size: 14px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #FF8000;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #e8e8e8;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1420;
                color: #e8e8e8;
                selection-background-color: #FF8000;
                selection-color: #000000;
                font-size: 14px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #0a1018;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #FF8000;
                color: #000000;
            }
            QPushButton {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1a2838;
                border-color: #FF8000;
            }
            QPushButton:pressed {
                background-color: #060a10;
            }
        """
