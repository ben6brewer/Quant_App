"""Monte Carlo Controls Widget - Top Control Bar for Monte Carlo module."""

from datetime import date
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QAbstractItemView,
    QListView,
    QSpinBox,
    QMessageBox,
)
from PySide6.QtCore import Signal, QDate, Qt
from PySide6.QtGui import QWheelEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import LazyThemeMixin, ThemedDialog, DateInputWidget, NoScrollComboBox
from app.services.theme_stylesheet_service import ThemeStylesheetService


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


class HorizonComboBox(NoScrollComboBox):
    """ComboBox for horizon selection with custom value display.

    Shows 'x.xx Years' when custom is selected, but reverts to 'Custom'
    in the dropdown so user can click to edit.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_years_text: Optional[str] = None  # e.g., "1.38 Years"
        self._custom_label = "Custom"

    def set_custom_years(self, years: float):
        """Set the custom years value to display."""
        self._custom_years_text = f"{years:.2f} Years"
        # Update the item text to show years
        last_idx = self.count() - 1
        self.setItemText(last_idx, self._custom_years_text)

    def clear_custom_years(self):
        """Clear the custom years display, revert to 'Custom'."""
        self._custom_years_text = None
        last_idx = self.count() - 1
        self.setItemText(last_idx, self._custom_label)

    def showPopup(self):
        """Before showing popup, temporarily show 'Custom' text."""
        if self._custom_years_text:
            last_idx = self.count() - 1
            self.setItemText(last_idx, self._custom_label)
        super().showPopup()

    def hidePopup(self):
        """After hiding popup, restore the years text if custom is selected."""
        super().hidePopup()
        if self._custom_years_text and self.currentData() == -1:
            last_idx = self.count() - 1
            self.setItemText(last_idx, self._custom_years_text)


class NoScrollSpinBox(QSpinBox):
    """SpinBox that ignores scroll wheel events."""

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class FutureDateInputWidget(DateInputWidget):
    """DateInputWidget that allows future dates (for Monte Carlo horizon)."""

    def _trigger_validation(self) -> bool:
        """Override to allow future dates and require date > today."""
        current = self.text()

        # Empty field is allowed (no error)
        if not current:
            self._current_date = None
            return True

        # Extract digits
        digits = current.replace("-", "")

        # Incomplete date (less than 8 digits)
        if len(digits) < 8:
            self.validation_error.emit(
                "Incomplete Date",
                f"Please enter a complete date in YYYY-MM-DD format.\nCurrent input: {current}"
            )
            self.setFocus()
            self.selectAll()
            return False

        # Parse as QDate
        parsed_date = QDate.fromString(current, "yyyy-MM-dd")

        if not parsed_date.isValid():
            self.validation_error.emit(
                "Invalid Date",
                f"The date '{current}' is not valid.\nPlease check the month and day values."
            )
            self.setFocus()
            self.selectAll()
            return False

        # Check date is AFTER today (opposite of transaction date validation)
        if parsed_date <= QDate.currentDate():
            self.validation_error.emit(
                "Date Must Be In Future",
                f"End date must be after today ({QDate.currentDate().toString('yyyy-MM-dd')})."
            )
            self.setFocus()
            self.selectAll()
            return False

        # Valid date - store and emit signal
        self._current_date = parsed_date
        self.date_changed.emit(parsed_date)
        return True


class CustomHorizonDialog(ThemedDialog):
    """Dialog for selecting a custom end date for Monte Carlo simulation horizon."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        self._end_date: Optional[QDate] = None
        super().__init__(theme_manager, "Custom Horizon", parent, min_width=350)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        # Description
        desc_label = QLabel("Enter the end date for the simulation horizon:")
        desc_label.setWordWrap(True)
        desc_label.setObjectName("description_label")
        layout.addWidget(desc_label)

        # Date input row
        date_row = QHBoxLayout()
        date_row.setSpacing(10)

        date_label = QLabel("End Date:")
        date_label.setObjectName("field_label")
        date_row.addWidget(date_label)

        self.date_input = FutureDateInputWidget()
        self.date_input.setFixedWidth(150)
        self.date_input.setFixedHeight(36)
        self.date_input.validation_error.connect(self._show_validation_error)
        date_row.addWidget(self.date_input)

        date_row.addStretch()
        layout.addLayout(date_row)

        # Info label
        info_label = QLabel("Date must be after today. Trading days will be calculated automatically.")
        info_label.setObjectName("noteLabel")
        layout.addWidget(info_label)

        layout.addStretch()

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(100, 36)
        ok_btn.setObjectName("defaultButton")
        ok_btn.clicked.connect(self._on_ok_clicked)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _show_validation_error(self, title: str, message: str):
        """Show validation error from DateInputWidget."""
        QMessageBox.warning(self, title, message)

    def _on_ok_clicked(self):
        """Handle OK button click with validation."""
        date_text = self.date_input.text().strip()

        if not date_text:
            QMessageBox.warning(self, "Date Required", "Please enter an end date.")
            self.date_input.setFocus()
            return

        # Parse the date
        parsed_date = QDate.fromString(date_text, "yyyy-MM-dd")
        if not parsed_date.isValid():
            QMessageBox.warning(
                self, "Invalid Date",
                f"The date '{date_text}' is not valid.\nPlease use YYYY-MM-DD format."
            )
            self.date_input.setFocus()
            self.date_input.selectAll()
            return

        # Check that date is after today
        today = QDate.currentDate()
        if parsed_date <= today:
            QMessageBox.warning(
                self, "Invalid Date",
                f"End date must be after today ({today.toString('yyyy-MM-dd')})."
            )
            self.date_input.setFocus()
            self.date_input.selectAll()
            return

        self._end_date = parsed_date
        self.accept()

    def get_end_date(self) -> Optional[QDate]:
        """Get the selected end date."""
        return self._end_date


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
    horizon_changed = Signal(int)  # Trading days (or years * 252 for presets)
    simulations_changed = Signal(int)
    benchmark_changed = Signal(str)
    run_simulation = Signal()
    settings_clicked = Signal()

    # Custom horizon marker
    CUSTOM_HORIZON_TEXT = "Custom"

    # Simulation methods
    METHOD_OPTIONS = ["Bootstrap", "Parametric"]
    METHOD_MAP = {"Bootstrap": "bootstrap", "Parametric": "parametric"}
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
        self.portfolio_combo.setFixedWidth(250)
        self.portfolio_combo.setFixedHeight(40)
        self.portfolio_combo.lineEdit().setPlaceholderText("Type ticker or select...")
        smooth_view = SmoothScrollListView(self.portfolio_combo)
        smooth_view.setAlternatingRowColors(True)
        self.portfolio_combo.setView(smooth_view)
        self.portfolio_combo.lineEdit().editingFinished.connect(self._on_portfolio_entered)
        self.portfolio_combo.lineEdit().returnPressed.connect(self._on_portfolio_entered)
        self.portfolio_combo.currentIndexChanged.connect(self._on_portfolio_selected)
        layout.addWidget(self.portfolio_combo)

        layout.addSpacing(20)

        # Benchmark selector (optional) - right after Portfolio
        self.benchmark_label = QLabel("Benchmark:")
        self.benchmark_label.setObjectName("control_label")
        layout.addWidget(self.benchmark_label)
        self.benchmark_combo = QComboBox()
        self.benchmark_combo.setEditable(True)
        self.benchmark_combo.setFixedWidth(250)
        self.benchmark_combo.setFixedHeight(40)
        self.benchmark_combo.lineEdit().setPlaceholderText("None")
        smooth_view_bench = SmoothScrollListView(self.benchmark_combo)
        smooth_view_bench.setAlternatingRowColors(True)
        self.benchmark_combo.setView(smooth_view_bench)
        self.benchmark_combo.lineEdit().editingFinished.connect(self._on_benchmark_entered)
        self.benchmark_combo.lineEdit().returnPressed.connect(self._on_benchmark_entered)
        self.benchmark_combo.currentIndexChanged.connect(self._on_benchmark_selected)
        layout.addWidget(self.benchmark_combo)

        layout.addSpacing(20)

        # Simulation method selector
        self.method_label = QLabel("Method:")
        self.method_label.setObjectName("control_label")
        layout.addWidget(self.method_label)
        self.method_combo = NoScrollComboBox()
        self.method_combo.setFixedWidth(120)
        self.method_combo.setFixedHeight(40)
        self.method_combo.addItems(self.METHOD_OPTIONS)
        self.method_combo.currentTextChanged.connect(self._on_method_changed)
        layout.addWidget(self.method_combo)

        layout.addSpacing(15)

        # Time horizon selector
        self.horizon_label = QLabel("Horizon:")
        self.horizon_label.setObjectName("control_label")
        layout.addWidget(self.horizon_label)
        self.horizon_combo = HorizonComboBox()
        self.horizon_combo.setFixedWidth(125)
        self.horizon_combo.setFixedHeight(40)
        for years in self.HORIZON_OPTIONS:
            self.horizon_combo.addItem(f"{years} Year{'s' if years > 1 else ''}", years)
        self.horizon_combo.addItem(self.CUSTOM_HORIZON_TEXT, -1)  # -1 indicates custom
        self.horizon_combo.currentIndexChanged.connect(self._on_horizon_changed)
        layout.addWidget(self.horizon_combo)
        self._custom_horizon_days: Optional[int] = None  # Store custom horizon in trading days

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
            # Check if this matches a portfolio name (case-insensitive)
            portfolio_match = None
            for i in range(self.portfolio_combo.count()):
                item = self.portfolio_combo.itemText(i)
                # Strip [Port] prefix for comparison
                item_name = item[7:] if item.startswith("[Port] ") else item
                if item_name.lower() == current_text.lower():
                    portfolio_match = item
                    break

            if portfolio_match:
                current_text = portfolio_match  # Use exact portfolio name with prefix
            else:
                current_text = current_text.upper()  # Uppercase for ticker lookup
                self.portfolio_combo.lineEdit().setText(current_text)
            self.portfolio_changed.emit(current_text)

    def _on_portfolio_selected(self, index: int):
        """Handle portfolio selection from dropdown."""
        if index >= 0:
            text = self.portfolio_combo.currentText()
            if text and text != self._last_portfolio_text:
                self._last_portfolio_text = text
                # Show name without prefix in the display
                if text.startswith("[Port] "):
                    self.portfolio_combo.lineEdit().setText(text[7:])
                self.portfolio_changed.emit(text)

    def _on_method_changed(self, text: str):
        """Handle simulation method change."""
        method = self.METHOD_MAP.get(text, "bootstrap")
        self.method_changed.emit(method)

    def _on_horizon_changed(self, index: int):
        """Handle time horizon change."""
        data = self.horizon_combo.currentData()

        if data == -1:  # Custom selected
            self._show_custom_horizon_dialog()
        elif data:
            # Preset years - convert to trading days
            trading_days = data * 252
            # Clear custom years display
            self.horizon_combo.clear_custom_years()
            self.horizon_changed.emit(trading_days)

    def _show_custom_horizon_dialog(self):
        """Show dialog for custom horizon date selection."""
        dialog = CustomHorizonDialog(self.theme_manager, self)
        if dialog.exec():
            end_date = dialog.get_end_date()
            if end_date:
                # Calculate trading days from today to end date
                today = QDate.currentDate()
                calendar_days = today.daysTo(end_date)

                # Approximate trading days (roughly 252 per year, ~21 per month)
                # More accurate: assume ~70% of calendar days are trading days
                trading_days = int(calendar_days * 252 / 365)
                trading_days = max(1, trading_days)  # Ensure at least 1 day

                self._custom_horizon_days = trading_days

                # Update the combo box to show the custom years value
                years = trading_days / 252
                self.horizon_combo.set_custom_years(years)

                self.horizon_changed.emit(trading_days)
        else:
            # User cancelled - revert to first option and clear custom display
            self.horizon_combo.clear_custom_years()
            self.horizon_combo.blockSignals(True)
            self.horizon_combo.setCurrentIndex(0)
            self.horizon_combo.blockSignals(False)

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
                current_text.startswith(prefix) for prefix in ["[Port]"]
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
        self.portfolio_combo.blockSignals(True)
        self.portfolio_combo.clear()
        for portfolio in portfolios:
            self.portfolio_combo.addItem(f"[Port] {portfolio}")
        if current:
            self.portfolio_combo.setCurrentText(current)
            # Show name without prefix in the display
            if current.startswith("[Port] "):
                self.portfolio_combo.lineEdit().setText(current[7:])
        else:
            self.portfolio_combo.setCurrentIndex(-1)  # Show placeholder
        self.portfolio_combo.blockSignals(False)

    def set_benchmark_list(self, portfolios: List[str]):
        """Set the list of available portfolios for benchmark."""
        current = self.benchmark_combo.currentText()
        self.benchmark_combo.blockSignals(True)
        self.benchmark_combo.clear()
        for portfolio in portfolios:
            self.benchmark_combo.addItem(f"[Port] {portfolio}")
        if current:
            self.benchmark_combo.setCurrentText(current)
        else:
            self.benchmark_combo.setCurrentIndex(-1)  # Show placeholder
        self.benchmark_combo.blockSignals(False)

    def set_method(self, method: str):
        """Set the current simulation method."""
        display = self.METHOD_REVERSE.get(method, "Bootstrap")
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
        """Apply theme-specific styling using centralized colors."""
        c = ThemeStylesheetService.get_colors(self.theme_manager.current_theme)

        # Compute hover colors based on theme
        if self.theme_manager.current_theme == "dark":
            bg_hover = "#3d3d3d"
            run_hover = "#00bfe6"
            run_pressed = "#00a6c7"
        elif self.theme_manager.current_theme == "light":
            bg_hover = "#e8e8e8"
            run_hover = "#0055aa"
            run_pressed = "#004488"
        else:  # bloomberg
            bg_hover = "#1a2838"
            run_hover = "#e67300"
            run_pressed = "#cc6600"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QLabel {{
                color: {c['text_muted']};
                font-size: 13px;
            }}
            QLabel#control_label {{
                color: {c['text']};
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }}
            QComboBox {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QComboBox:hover {{
                border-color: {c['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid {c['text']};
                margin-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['bg_header']};
                color: {c['text']};
                selection-background-color: {c['accent']};
                selection-color: {c['text_on_accent']};
                font-size: 14px;
                padding: 4px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:alternate {{
                background-color: {c['bg_alt']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
            }}
            QPushButton {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                border-color: {c['accent']};
            }}
            QPushButton:pressed {{
                background-color: {c['bg']};
            }}
            QPushButton#run_btn {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                font-weight: bold;
                border: 1px solid {c['accent']};
            }}
            QPushButton#run_btn:hover {{
                background-color: {run_hover};
                border-color: {run_hover};
            }}
            QPushButton#run_btn:pressed {{
                background-color: {run_pressed};
            }}
        """)
