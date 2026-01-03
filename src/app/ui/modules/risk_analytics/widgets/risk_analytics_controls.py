"""Risk Analytics Controls Widget - Top Control Bar."""

from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QAbstractItemView,
    QListView,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QWheelEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class SmoothScrollListView(QListView):
    """QListView with smoother, slower scrolling for combo box dropdowns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def wheelEvent(self, event: QWheelEvent):
        """Override wheel event to reduce scroll speed."""
        delta = event.angleDelta().y()
        pixels_to_scroll = int(delta / 4)
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - pixels_to_scroll)
        event.accept()


class RiskAnalyticsControls(LazyThemeMixin, QWidget):
    """
    Control bar at top of Risk Analytics module.

    Contains: Home button, Portfolio selector, Benchmark selector, Settings button.
    """

    # Signals
    home_clicked = Signal()
    portfolio_changed = Signal(str)  # Emits portfolio name
    benchmark_changed = Signal(str)  # Emits benchmark name/ticker or empty string
    analyze_clicked = Signal()  # Emits when Analyze button clicked
    settings_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        # Track last processed values to prevent duplicate signals
        self._last_portfolio_text: str = ""
        self._last_benchmark_text: str = ""

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

        # Portfolio selector (editable with read-only line edit for display control)
        self.portfolio_label = QLabel("Portfolio:")
        self.portfolio_label.setObjectName("control_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = QComboBox()
        self.portfolio_combo.setEditable(True)
        self.portfolio_combo.lineEdit().setReadOnly(True)
        self.portfolio_combo.setFixedWidth(250)
        self.portfolio_combo.setFixedHeight(40)
        smooth_view = SmoothScrollListView(self.portfolio_combo)
        smooth_view.setAlternatingRowColors(True)
        self.portfolio_combo.setView(smooth_view)
        self.portfolio_combo.currentIndexChanged.connect(self._on_portfolio_selected)
        layout.addWidget(self.portfolio_combo)

        layout.addSpacing(20)

        # Benchmark selector (editable combo box)
        self.benchmark_label = QLabel("Benchmark:")
        self.benchmark_label.setObjectName("control_label")
        layout.addWidget(self.benchmark_label)
        self.benchmark_combo = QComboBox()
        self.benchmark_combo.setEditable(True)
        self.benchmark_combo.setFixedWidth(250)
        self.benchmark_combo.setFixedHeight(40)
        self.benchmark_combo.lineEdit().setPlaceholderText("SPY")
        smooth_view_bmrk = SmoothScrollListView(self.benchmark_combo)
        smooth_view_bmrk.setAlternatingRowColors(True)
        self.benchmark_combo.setView(smooth_view_bmrk)
        # Connect editing finished (Enter or focus out) and dropdown selection
        self.benchmark_combo.lineEdit().editingFinished.connect(
            self._on_benchmark_entered
        )
        self.benchmark_combo.lineEdit().returnPressed.connect(self._on_benchmark_entered)
        self.benchmark_combo.currentIndexChanged.connect(self._on_benchmark_selected)
        layout.addWidget(self.benchmark_combo)

        layout.addSpacing(15)

        # Analyze button (primary action)
        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.setFixedSize(100, 40)
        self.analyze_btn.setObjectName("analyze_btn")
        self.analyze_btn.clicked.connect(self.analyze_clicked.emit)
        layout.addWidget(self.analyze_btn)

        # Add stretch to push settings button to right
        layout.addStretch(1)

        # Settings button (right-aligned)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedSize(100, 40)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def _on_portfolio_selected(self, index: int):
        """Handle dropdown selection in portfolio combo box."""
        if index >= 0:
            text = self.portfolio_combo.currentText()
            if text and text != self._last_portfolio_text:
                self._last_portfolio_text = text
                # Show name without prefix in the display
                if text.startswith("[Port] "):
                    self.portfolio_combo.lineEdit().setText(text[7:])
                self.portfolio_changed.emit(text)

    def _on_benchmark_entered(self):
        """Handle Enter key or focus out in benchmark combo box."""
        text = self.benchmark_combo.currentText().strip()

        # Treat "NONE" or empty as no benchmark
        if not text or text.upper() == "NONE":
            text = ""
        else:
            # Check if this matches a portfolio in the dropdown (case-insensitive)
            # Portfolios are listed as "[Port] Name"
            portfolio_match = None
            for i in range(self.benchmark_combo.count()):
                item = self.benchmark_combo.itemText(i)
                if item.lower() == text.lower():
                    portfolio_match = item
                    break

            if portfolio_match:
                text = portfolio_match  # Use exact portfolio name
            else:
                text = text.upper()  # Uppercase for ticker lookup

        # Always update display to show uppercase
        if text:
            self.benchmark_combo.blockSignals(True)
            self.benchmark_combo.lineEdit().blockSignals(True)
            self.benchmark_combo.lineEdit().setText(text)
            self.benchmark_combo.lineEdit().blockSignals(False)
            self.benchmark_combo.blockSignals(False)

        # Only emit signal if value actually changed
        if text != self._last_benchmark_text:
            self._last_benchmark_text = text
            if text:
                self.benchmark_changed.emit(text)
            else:
                # Clear to show placeholder
                self.benchmark_combo.blockSignals(True)
                self.benchmark_combo.lineEdit().clear()
                self.benchmark_combo.setCurrentIndex(-1)
                self.benchmark_combo.blockSignals(False)
                self.benchmark_changed.emit("")

    def _on_benchmark_selected(self, index: int):
        """Handle benchmark selected from dropdown."""
        if index >= 0:
            text = self.benchmark_combo.currentText()
            if text and text != self._last_benchmark_text:
                self._last_benchmark_text = text
                self.benchmark_changed.emit(text)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        """
        Update portfolio dropdown.

        Args:
            portfolios: List of portfolio names
            current: Currently selected portfolio name (None to keep current)
        """
        self.portfolio_combo.blockSignals(True)
        self.portfolio_combo.clear()
        for p in portfolios:
            self.portfolio_combo.addItem(f"[Port] {p}")
        if current and current in portfolios:
            self.portfolio_combo.setCurrentText(f"[Port] {current}")
            # Show name without prefix in the display
            self.portfolio_combo.lineEdit().setText(current)
        elif portfolios:
            self.portfolio_combo.setCurrentIndex(0)
            # Show first portfolio name without prefix
            self.portfolio_combo.lineEdit().setText(portfolios[0])
        self.portfolio_combo.blockSignals(False)

    def update_benchmark_list(self, portfolios: List[str]):
        """
        Update the benchmark dropdown with available portfolios.

        Args:
            portfolios: List of portfolio names
        """
        current = self.benchmark_combo.currentText()
        self.benchmark_combo.blockSignals(True)
        self.benchmark_combo.clear()
        # Add portfolios with prefix
        for p in portfolios:
            self.benchmark_combo.addItem(f"[Port] {p}")
        # Restore previous selection if still valid, otherwise show placeholder
        if current:
            self.benchmark_combo.setCurrentText(current)
        else:
            self.benchmark_combo.setCurrentIndex(-1)  # Show placeholder
        self.benchmark_combo.blockSignals(False)

    def get_current_portfolio(self) -> str:
        """Get currently selected portfolio name."""
        return self.portfolio_combo.currentText() or ""

    def get_current_benchmark(self) -> str:
        """
        Get currently selected benchmark.

        Returns:
            Benchmark ticker/portfolio name, or empty string if none selected.
        """
        return self.benchmark_combo.currentText() or ""

    def set_benchmark(self, benchmark: str):
        """
        Set the benchmark value.

        Args:
            benchmark: Benchmark ticker or portfolio name
        """
        self.benchmark_combo.blockSignals(True)
        self.benchmark_combo.lineEdit().setText(benchmark)
        self._last_benchmark_text = benchmark
        self.benchmark_combo.blockSignals(False)

    def reset_benchmark(self):
        """Reset the benchmark dropdown to show placeholder."""
        self.benchmark_combo.blockSignals(True)
        self.benchmark_combo.setCurrentIndex(-1)  # Show placeholder
        self.benchmark_combo.lineEdit().clear()
        self.benchmark_combo.blockSignals(False)

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
            QPushButton#analyze_btn {
                background-color: #00d4ff;
                color: #000000;
                border: none;
                font-weight: bold;
            }
            QPushButton#analyze_btn:hover {
                background-color: #00b8e6;
            }
            QPushButton#analyze_btn:pressed {
                background-color: #0099cc;
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
            QPushButton#analyze_btn {
                background-color: #0066cc;
                color: #ffffff;
                border: none;
                font-weight: bold;
            }
            QPushButton#analyze_btn:hover {
                background-color: #0052a3;
            }
            QPushButton#analyze_btn:pressed {
                background-color: #004080;
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
            QPushButton#analyze_btn {
                background-color: #FF8000;
                color: #000000;
                border: none;
                font-weight: bold;
            }
            QPushButton#analyze_btn:hover {
                background-color: #e67300;
            }
            QPushButton#analyze_btn:pressed {
                background-color: #cc6600;
            }
        """
