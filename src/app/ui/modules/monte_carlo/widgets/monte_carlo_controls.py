"""Monte Carlo Controls Widget - Top Control Bar for Monte Carlo module."""

from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QAbstractItemView,
    QListView,
    QSpinBox,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QWheelEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class SmoothScrollListView(QListView):
    """QListView with smoother, slower scrolling for combo box dropdowns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    def wheelEvent(self, event: QWheelEvent):
        """Override wheel event to reduce scroll speed."""
        delta = event.angleDelta().y()
        pixels_to_scroll = int(delta / 4)
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - pixels_to_scroll)
        event.accept()


class NoScrollComboBox(QComboBox):
    """ComboBox that ignores scroll wheel events."""

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class NoScrollSpinBox(QSpinBox):
    """SpinBox that ignores scroll wheel events."""

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class MonteCarloControls(LazyThemeMixin, QWidget):
    """
    Control bar at top of Monte Carlo module.

    Contains: Home button, Portfolio selector, Simulation method, Time horizon,
    Number of simulations, Benchmark selector, Settings button.
    """

    # Signals
    home_clicked = Signal()
    portfolio_changed = Signal(str)
    method_changed = Signal(str)  # "bootstrap" or "parametric"
    horizon_changed = Signal(int)  # Years
    simulations_changed = Signal(int)
    benchmark_changed = Signal(str)
    run_simulation = Signal()
    settings_clicked = Signal()

    # Simulation methods
    METHOD_OPTIONS = ["Historical Bootstrap", "Parametric (Normal)"]
    METHOD_MAP = {"Historical Bootstrap": "bootstrap", "Parametric (Normal)": "parametric"}
    METHOD_REVERSE = {v: k for k, v in METHOD_MAP.items()}

    # Time horizon options (in years)
    HORIZON_OPTIONS = [1, 2, 3, 5, 10]

    # Simulation count options
    SIMULATION_OPTIONS = [100, 500, 1000, 5000, 10000]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
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

        layout.addStretch(1)

        # Portfolio selector (editable - can type ticker or select portfolio)
        self.portfolio_label = QLabel("Portfolio:")
        self.portfolio_label.setObjectName("control_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = QComboBox()
        self.portfolio_combo.setEditable(True)
        self.portfolio_combo.setFixedWidth(200)
        self.portfolio_combo.setFixedHeight(40)
        self.portfolio_combo.lineEdit().setPlaceholderText("Type ticker or select...")
        smooth_view = SmoothScrollListView(self.portfolio_combo)
        smooth_view.setAlternatingRowColors(True)
        self.portfolio_combo.setView(smooth_view)
        self.portfolio_combo.lineEdit().editingFinished.connect(self._on_portfolio_entered)
        self.portfolio_combo.lineEdit().returnPressed.connect(self._on_portfolio_entered)
        self.portfolio_combo.currentIndexChanged.connect(self._on_portfolio_selected)
        layout.addWidget(self.portfolio_combo)

        layout.addSpacing(15)

        # Simulation method selector
        self.method_label = QLabel("Method:")
        self.method_label.setObjectName("control_label")
        layout.addWidget(self.method_label)
        self.method_combo = NoScrollComboBox()
        self.method_combo.setFixedWidth(180)
        self.method_combo.setFixedHeight(40)
        self.method_combo.addItems(self.METHOD_OPTIONS)
        self.method_combo.currentTextChanged.connect(self._on_method_changed)
        layout.addWidget(self.method_combo)

        layout.addSpacing(15)

        # Time horizon selector
        self.horizon_label = QLabel("Horizon:")
        self.horizon_label.setObjectName("control_label")
        layout.addWidget(self.horizon_label)
        self.horizon_combo = NoScrollComboBox()
        self.horizon_combo.setFixedWidth(100)
        self.horizon_combo.setFixedHeight(40)
        for years in self.HORIZON_OPTIONS:
            self.horizon_combo.addItem(f"{years} Year{'s' if years > 1 else ''}", years)
        self.horizon_combo.currentIndexChanged.connect(self._on_horizon_changed)
        layout.addWidget(self.horizon_combo)

        layout.addSpacing(15)

        # Number of simulations
        self.sims_label = QLabel("Simulations:")
        self.sims_label.setObjectName("control_label")
        layout.addWidget(self.sims_label)
        self.sims_combo = NoScrollComboBox()
        self.sims_combo.setFixedWidth(100)
        self.sims_combo.setFixedHeight(40)
        for count in self.SIMULATION_OPTIONS:
            self.sims_combo.addItem(f"{count:,}", count)
        self.sims_combo.setCurrentIndex(2)  # Default 1000
        self.sims_combo.currentIndexChanged.connect(self._on_sims_changed)
        layout.addWidget(self.sims_combo)

        layout.addSpacing(15)

        # Benchmark selector (optional)
        self.benchmark_label = QLabel("Benchmark:")
        self.benchmark_label.setObjectName("control_label")
        layout.addWidget(self.benchmark_label)
        self.benchmark_combo = QComboBox()
        self.benchmark_combo.setEditable(True)
        self.benchmark_combo.setFixedWidth(150)
        self.benchmark_combo.setFixedHeight(40)
        self.benchmark_combo.lineEdit().setPlaceholderText("None")
        self.benchmark_combo.lineEdit().editingFinished.connect(self._on_benchmark_entered)
        self.benchmark_combo.lineEdit().returnPressed.connect(self._on_benchmark_entered)
        self.benchmark_combo.currentIndexChanged.connect(self._on_benchmark_selected)
        layout.addWidget(self.benchmark_combo)

        layout.addSpacing(15)

        # Run simulation button
        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.setFixedSize(140, 40)
        self.run_btn.setObjectName("run_btn")
        self.run_btn.clicked.connect(self.run_simulation.emit)
        layout.addWidget(self.run_btn)

        layout.addStretch(1)

        # Settings button (right-aligned)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedSize(100, 40)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def _on_portfolio_entered(self):
        """Handle Enter key or focus out in portfolio combo box."""
        current_text = self.portfolio_combo.lineEdit().text().strip()
        if current_text and current_text != self._last_portfolio_text:
            self._last_portfolio_text = current_text
            # Auto-uppercase if it looks like a ticker
            if not any(current_text.startswith(prefix) for prefix in ["[Portfolio]"]):
                current_text = current_text.upper()
                self.portfolio_combo.lineEdit().setText(current_text)
            self.portfolio_changed.emit(current_text)

    def _on_portfolio_selected(self, index: int):
        """Handle portfolio selection from dropdown."""
        if index >= 0:
            text = self.portfolio_combo.currentText()
            if text and text != self._last_portfolio_text:
                self._last_portfolio_text = text
                self.portfolio_changed.emit(text)

    def _on_method_changed(self, text: str):
        """Handle simulation method change."""
        method = self.METHOD_MAP.get(text, "bootstrap")
        self.method_changed.emit(method)

    def _on_horizon_changed(self, index: int):
        """Handle time horizon change."""
        years = self.horizon_combo.currentData()
        if years:
            self.horizon_changed.emit(years)

    def _on_sims_changed(self, index: int):
        """Handle simulation count change."""
        count = self.sims_combo.currentData()
        if count:
            self.simulations_changed.emit(count)

    def _on_benchmark_entered(self):
        """Handle Enter key or focus out in benchmark combo box."""
        current_text = self.benchmark_combo.lineEdit().text().strip()
        if current_text != self._last_benchmark_text:
            self._last_benchmark_text = current_text
            if current_text and not any(
                current_text.startswith(prefix) for prefix in ["[Portfolio]"]
            ):
                current_text = current_text.upper()
                self.benchmark_combo.lineEdit().setText(current_text)
            self.benchmark_changed.emit(current_text)

    def _on_benchmark_selected(self, index: int):
        """Handle benchmark selection from dropdown."""
        if index >= 0:
            text = self.benchmark_combo.currentText()
            if text != self._last_benchmark_text:
                self._last_benchmark_text = text
                self.benchmark_changed.emit(text)

    def set_portfolio_list(self, portfolios: List[str]):
        """Set the list of available portfolios."""
        current = self.portfolio_combo.currentText()
        self.portfolio_combo.clear()
        for portfolio in portfolios:
            self.portfolio_combo.addItem(f"[Portfolio] {portfolio}")
        if current:
            self.portfolio_combo.setCurrentText(current)

    def set_benchmark_list(self, portfolios: List[str]):
        """Set the list of available portfolios for benchmark."""
        current = self.benchmark_combo.currentText()
        self.benchmark_combo.clear()
        for portfolio in portfolios:
            self.benchmark_combo.addItem(f"[Portfolio] {portfolio}")
        if current:
            self.benchmark_combo.setCurrentText(current)

    def set_method(self, method: str):
        """Set the current simulation method."""
        display = self.METHOD_REVERSE.get(method, "Historical Bootstrap")
        self.method_combo.setCurrentText(display)

    def set_horizon(self, years: int):
        """Set the current time horizon."""
        for i in range(self.horizon_combo.count()):
            if self.horizon_combo.itemData(i) == years:
                self.horizon_combo.setCurrentIndex(i)
                break

    def set_simulations(self, count: int):
        """Set the current simulation count."""
        for i in range(self.sims_combo.count()):
            if self.sims_combo.itemData(i) == count:
                self.sims_combo.setCurrentIndex(i)
                break

    def get_current_portfolio(self) -> str:
        """Get the current portfolio/ticker selection."""
        return self.portfolio_combo.currentText().strip()

    def get_current_benchmark(self) -> str:
        """Get the current benchmark selection."""
        return self.benchmark_combo.currentText().strip()

    def get_current_method(self) -> str:
        """Get the current simulation method."""
        return self.METHOD_MAP.get(self.method_combo.currentText(), "bootstrap")

    def get_current_horizon(self) -> int:
        """Get the current time horizon in years."""
        return self.horizon_combo.currentData() or 1

    def get_current_simulations(self) -> int:
        """Get the current number of simulations."""
        return self.sims_combo.currentData() or 1000

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "dark":
            bg_color = "#1e1e1e"
            text_color = "#ffffff"
            border_color = "#444444"
            hover_bg = "#333333"
            accent_color = "#00d4ff"
        elif theme == "light":
            bg_color = "#f5f5f5"
            text_color = "#000000"
            border_color = "#cccccc"
            hover_bg = "#e0e0e0"
            accent_color = "#0066cc"
        else:  # bloomberg
            bg_color = "#0d1420"
            text_color = "#e8e8e8"
            border_color = "#3a4654"
            hover_bg = "#1a2836"
            accent_color = "#FF8000"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QLabel#control_label {{
                font-size: 14px;
                font-weight: bold;
                background: transparent;
            }}
            QPushButton {{
                background-color: {border_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 5px 15px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                border: 1px solid {accent_color};
            }}
            QPushButton#run_btn {{
                background-color: {accent_color};
                color: #000000;
                font-weight: bold;
            }}
            QPushButton#run_btn:hover {{
                background-color: {accent_color};
                opacity: 0.8;
            }}
            QComboBox {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 14px;
            }}
            QComboBox:hover {{
                border: 1px solid {accent_color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg_color};
                color: {text_color};
                selection-background-color: {hover_bg};
                border: 1px solid {border_color};
            }}
            QLineEdit {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 5px;
            }}
        """)
