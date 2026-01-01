"""Chart Controls Widget - Control bar for chart module."""

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.core.config import (
    DEFAULT_TICKER,
    DEFAULT_INTERVAL,
    DEFAULT_CHART_TYPE,
    DEFAULT_SCALE,
    CHART_INTERVALS,
    CHART_TYPES,
    CHART_SCALES,
)
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class ChartControls(LazyThemeMixin, QWidget):
    """Control bar widget for chart configuration.

    Provides home button, ticker input, interval/chart type/scale selectors,
    and buttons for indicators, depth, and settings.
    """

    # Signals
    home_clicked = Signal()  # Emitted when home button is clicked
    ticker_changed = Signal(str)  # Emitted when ticker input is submitted (Enter pressed)
    interval_changed = Signal(str)  # Emitted when interval selection changes
    chart_type_changed = Signal(str)  # Emitted when chart type changes
    scale_changed = Signal(str)  # Emitted when scale changes
    settings_clicked = Signal()  # Emitted when settings button is clicked
    indicators_toggled = Signal(bool)  # Emitted when indicators button is toggled
    depth_toggled = Signal(bool)  # Emitted when depth button is toggled

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Connect to theme changes (lazy - only apply when visible)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self) -> None:
        """Create the control bar UI layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Home button (leftmost)
        self.home_btn = QPushButton("Home")
        self.home_btn.setFixedSize(100, 40)
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        # Add stretch to push controls toward center
        layout.addStretch(1)

        # Ticker input
        self.ticker_label = QLabel("Ticker:")
        self.ticker_label.setObjectName("control_label")
        layout.addWidget(self.ticker_label)
        self.ticker_input = QLineEdit()
        self.ticker_input.setText(DEFAULT_TICKER)
        self.ticker_input.setFixedWidth(200)
        self.ticker_input.setFixedHeight(40)
        self.ticker_input.setPlaceholderText("Ticker or =equation...")
        self.ticker_input.textEdited.connect(self._on_ticker_text_edited)
        layout.addWidget(self.ticker_input)

        layout.addSpacing(20)

        # Interval selector
        self.interval_label = QLabel("Interval:")
        self.interval_label.setObjectName("control_label")
        layout.addWidget(self.interval_label)
        self.interval_combo = QComboBox()
        self.interval_combo.setFixedWidth(120)
        self.interval_combo.setFixedHeight(40)
        self.interval_combo.addItems(CHART_INTERVALS)
        self.interval_combo.setCurrentText(DEFAULT_INTERVAL)
        layout.addWidget(self.interval_combo)

        layout.addSpacing(20)

        # Chart type selector
        self.chart_type_label = QLabel("Chart:")
        self.chart_type_label.setObjectName("control_label")
        layout.addWidget(self.chart_type_label)
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.setFixedWidth(120)
        self.chart_type_combo.setFixedHeight(40)
        self.chart_type_combo.addItems(CHART_TYPES)
        self.chart_type_combo.setCurrentText(DEFAULT_CHART_TYPE)
        layout.addWidget(self.chart_type_combo)

        layout.addSpacing(20)

        # Scale selector
        self.scale_label = QLabel("Scale:")
        self.scale_label.setObjectName("control_label")
        layout.addWidget(self.scale_label)
        self.scale_combo = QComboBox()
        self.scale_combo.setFixedWidth(130)
        self.scale_combo.setFixedHeight(40)
        self.scale_combo.addItems(CHART_SCALES)
        self.scale_combo.setCurrentText(DEFAULT_SCALE)
        layout.addWidget(self.scale_combo)

        layout.addSpacing(20)

        # Indicators button
        self.indicators_btn = QPushButton("Indicators")
        self.indicators_btn.setFixedSize(100, 40)
        self.indicators_btn.setCheckable(True)
        layout.addWidget(self.indicators_btn)

        # Depth button
        self.depth_btn = QPushButton("Depth")
        self.depth_btn.setFixedSize(100, 40)
        self.depth_btn.setCheckable(True)
        self.depth_btn.setEnabled(False)  # Disabled by default
        layout.addWidget(self.depth_btn)

        # Push settings button to the right
        layout.addStretch(1)

        # Settings button (right-aligned)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedSize(100, 40)
        layout.addWidget(self.settings_btn)

    def _connect_signals(self) -> None:
        """Connect internal widget signals to external signals."""
        # Ticker input (only on Enter press)
        self.ticker_input.returnPressed.connect(
            lambda: self.ticker_changed.emit(self.ticker_input.text())
        )

        # Interval changes (requires data refetch)
        self.interval_combo.currentTextChanged.connect(self.interval_changed.emit)

        # Chart type changes (no refetch needed)
        self.chart_type_combo.currentTextChanged.connect(self.chart_type_changed.emit)

        # Scale changes (no refetch needed)
        self.scale_combo.currentTextChanged.connect(self.scale_changed.emit)

        # Settings button
        self.settings_btn.clicked.connect(self.settings_clicked.emit)

        # Toggle buttons
        self.indicators_btn.clicked.connect(
            lambda: self.indicators_toggled.emit(self.indicators_btn.isChecked())
        )
        self.depth_btn.clicked.connect(
            lambda: self.depth_toggled.emit(self.depth_btn.isChecked())
        )

    def _on_ticker_text_edited(self, text: str):
        """Convert ticker input to uppercase as user types."""
        cursor_pos = self.ticker_input.cursorPosition()
        self.ticker_input.setText(text.upper())
        self.ticker_input.setCursorPosition(cursor_pos)

    def _apply_theme(self) -> None:
        """Apply theme-specific styling to the control bar."""
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
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #00d4ff;
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
            QPushButton:checked {
                background-color: #00d4ff;
                color: #000000;
                border-color: #00d4ff;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #666666;
                border-color: #2d2d2d;
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
            QLineEdit {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #0066cc;
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
            QPushButton:checked {
                background-color: #0066cc;
                color: #ffffff;
                border-color: #0066cc;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #999999;
                border-color: #cccccc;
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
            QLineEdit {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #FF8000;
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
            QPushButton:checked {
                background-color: #FF8000;
                color: #000000;
                border-color: #FF8000;
            }
            QPushButton:disabled {
                background-color: #060a10;
                color: #555555;
                border-color: #1a2838;
            }
        """

    # Public getters
    def get_ticker(self) -> str:
        """Get current ticker text."""
        return self.ticker_input.text()

    def get_interval(self) -> str:
        """Get current interval selection."""
        return self.interval_combo.currentText()

    def get_chart_type(self) -> str:
        """Get current chart type selection."""
        return self.chart_type_combo.currentText()

    def get_scale(self) -> str:
        """Get current scale selection."""
        return self.scale_combo.currentText()

    def set_depth_enabled(self, enabled: bool) -> None:
        """Enable or disable the depth button."""
        self.depth_btn.setEnabled(enabled)

    def set_depth_visible(self, visible: bool) -> None:
        """Show or hide the depth button."""
        self.depth_btn.setVisible(visible)

    def set_depth_text(self, text: str) -> None:
        """Set the depth button text."""
        self.depth_btn.setText(text)

    def set_indicators_checked(self, checked: bool) -> None:
        """Set the checked state of the indicators button."""
        self.indicators_btn.setChecked(checked)

    def set_depth_checked(self, checked: bool) -> None:
        """Set the checked state of the depth button."""
        self.depth_btn.setChecked(checked)
