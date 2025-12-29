"""Chart Controls Widget - Control bar for chart module."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QComboBox
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


class ChartControls(QWidget):
    """Control bar widget for chart configuration.

    Provides ticker input, interval/chart type/scale selectors,
    and buttons for indicators, depth, and settings.
    """

    # Signals
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
        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        """Create the control bar UI layout."""
        controls = QHBoxLayout(self)
        controls.setContentsMargins(125, 12, 15, 12)  # Space for home button
        controls.setSpacing(20)

        # Ticker input
        controls.addWidget(QLabel("TICKER"))
        self.ticker_input = QLineEdit()
        self.ticker_input.setText(DEFAULT_TICKER)
        self.ticker_input.setMaximumWidth(200)
        self.ticker_input.setPlaceholderText("Ticker or =equation...")
        controls.addWidget(self.ticker_input)

        # Separator
        controls.addSpacing(10)

        # Interval selector
        controls.addWidget(QLabel("INTERVAL"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(CHART_INTERVALS)
        self.interval_combo.setCurrentText(DEFAULT_INTERVAL)
        self.interval_combo.setMaximumWidth(100)
        controls.addWidget(self.interval_combo)

        # Chart type selector
        controls.addWidget(QLabel("CHART"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(CHART_TYPES)
        self.chart_type_combo.setCurrentText(DEFAULT_CHART_TYPE)
        self.chart_type_combo.setMaximumWidth(100)
        controls.addWidget(self.chart_type_combo)

        # Scale selector
        controls.addWidget(QLabel("SCALE"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(CHART_SCALES)
        self.scale_combo.setCurrentText(DEFAULT_SCALE)
        self.scale_combo.setMaximumWidth(120)
        controls.addWidget(self.scale_combo)

        # Separator
        controls.addSpacing(20)

        # Indicators button
        self.indicators_btn = self.theme_manager.create_styled_button("Indicators", checkable=True)
        self.indicators_btn.setMaximumWidth(120)
        controls.addWidget(self.indicators_btn)

        # Depth button
        self.depth_btn = self.theme_manager.create_styled_button("Depth", checkable=True)
        self.depth_btn.setMaximumWidth(120)
        self.depth_btn.setEnabled(False)  # Disabled by default, enabled for Binance tickers
        controls.addWidget(self.depth_btn)

        # Push settings button to the right
        controls.addStretch(1)

        # Chart settings button (right-aligned)
        self.chart_settings_btn = self.theme_manager.create_styled_button("Settings")
        self.chart_settings_btn.setMaximumWidth(120)
        controls.addWidget(self.chart_settings_btn)

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
        self.chart_settings_btn.clicked.connect(self.settings_clicked.emit)

        # Toggle buttons
        self.indicators_btn.clicked.connect(
            lambda: self.indicators_toggled.emit(self.indicators_btn.isChecked())
        )
        self.depth_btn.clicked.connect(
            lambda: self.depth_toggled.emit(self.depth_btn.isChecked())
        )

    def _apply_theme(self) -> None:
        """Apply theme-specific styling to the control bar."""
        stylesheet = self.theme_manager.get_controls_stylesheet()
        self.setStyleSheet(stylesheet)

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
