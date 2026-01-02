"""Risk Analytics Settings Dialog - Configure module settings and sector overrides."""

from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QDoubleSpinBox,
    QGroupBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QWidget,
)
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.themed_dialog import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService
from ..services.sector_override_service import SectorOverrideService


class RiskAnalyticsSettingsDialog(ThemedDialog):
    """
    Settings dialog for Risk Analytics module.

    Allows configuration of:
    - Risk-free rate source (3-month T-bill or manual)
    - Analysis settings (lookback period, currency factor)
    - Sector classification overrides
    """

    settings_saved = Signal(dict)

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: Dict[str, Any],
        parent=None,
    ):
        """
        Initialize settings dialog.

        Args:
            theme_manager: Application theme manager
            current_settings: Current settings values
            parent: Parent widget
        """
        self.current_settings = current_settings
        self._current_irx_rate = self._fetch_irx_rate()
        super().__init__(
            theme_manager,
            "Risk Analytics Settings",
            parent,
            min_width=550,
            min_height=500,
        )

    def _fetch_irx_rate(self) -> float:
        """Fetch current ^IRX rate."""
        try:
            from app.services import StatisticsService
            return StatisticsService.get_risk_free_rate()
        except Exception:
            return 0.05

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        # Risk-Free Rate section
        rf_group = QGroupBox("Risk-Free Rate")
        rf_layout = QVBoxLayout()

        # Radio button group
        self.rf_button_group = QButtonGroup(self)

        # Option 1: Use ^IRX (3-month T-bill)
        irx_rate_pct = self._current_irx_rate * 100
        self.irx_radio = QRadioButton(
            f"Use 3-Month Treasury Bill (^IRX: {irx_rate_pct:.2f}%)"
        )
        self.irx_radio.setObjectName("settingsRadio")
        self.rf_button_group.addButton(self.irx_radio)
        rf_layout.addWidget(self.irx_radio)

        # Option 2: Manual rate
        manual_row = QHBoxLayout()
        self.manual_radio = QRadioButton("Manual Rate:")
        self.manual_radio.setObjectName("settingsRadio")
        self.rf_button_group.addButton(self.manual_radio)
        manual_row.addWidget(self.manual_radio)

        self.manual_rate_spin = QDoubleSpinBox()
        self.manual_rate_spin.setRange(0.0, 20.0)
        self.manual_rate_spin.setDecimals(2)
        self.manual_rate_spin.setSuffix("%")
        self.manual_rate_spin.setSingleStep(0.25)
        self.manual_rate_spin.setFixedWidth(100)
        manual_row.addWidget(self.manual_rate_spin)
        manual_row.addStretch()
        rf_layout.addLayout(manual_row)

        rf_group.setLayout(rf_layout)
        layout.addWidget(rf_group)

        # Analysis Settings section
        analysis_group = QGroupBox("Analysis Settings")
        analysis_layout = QVBoxLayout()

        # Lookback period
        lookback_row = QHBoxLayout()
        lookback_label = QLabel("Lookback Period:")
        lookback_row.addWidget(lookback_label)

        self.lookback_combo = QComboBox()
        self.lookback_combo.addItems(
            ["3 Months (63 days)", "6 Months (126 days)", "1 Year (252 days)",
             "2 Years (504 days)", "3 Years (756 days)"]
        )
        self.lookback_combo.setFixedWidth(180)
        lookback_row.addWidget(self.lookback_combo)
        lookback_row.addStretch()
        analysis_layout.addLayout(lookback_row)

        # Currency factor checkbox
        self.currency_check = QCheckBox("Include Currency Factor in decomposition")
        self.currency_check.setObjectName("settingsCheckbox")
        analysis_layout.addWidget(self.currency_check)

        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)

        # Sector Overrides section
        override_group = QGroupBox("Sector Classification Overrides")
        override_layout = QVBoxLayout()

        # Description
        override_desc = QLabel(
            "Override the sector classification for specific tickers that "
            "may be incorrectly classified by yfinance."
        )
        override_desc.setWordWrap(True)
        override_desc.setObjectName("settingsDescription")
        override_layout.addWidget(override_desc)

        # Add override controls
        add_row = QHBoxLayout()

        # Ticker input
        ticker_label = QLabel("Ticker:")
        add_row.addWidget(ticker_label)
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("e.g., COIN")
        self.ticker_input.setFixedWidth(100)
        self.ticker_input.textChanged.connect(self._on_ticker_input_changed)
        add_row.addWidget(self.ticker_input)

        # Sector dropdown
        sector_label = QLabel("Sector:")
        add_row.addWidget(sector_label)
        self.sector_combo = QComboBox()
        self.sector_combo.addItems(SectorOverrideService.SECTORS)
        self.sector_combo.setFixedWidth(180)
        add_row.addWidget(self.sector_combo)

        # Add button
        self.add_override_btn = QPushButton("Add Override")
        self.add_override_btn.setFixedWidth(100)
        self.add_override_btn.clicked.connect(self._add_override)
        self.add_override_btn.setEnabled(False)
        add_row.addWidget(self.add_override_btn)

        add_row.addStretch()
        override_layout.addLayout(add_row)

        # Current overrides list
        list_label = QLabel("Current Overrides:")
        list_label.setObjectName("settingsSubLabel")
        override_layout.addWidget(list_label)

        self.overrides_list = QListWidget()
        self.overrides_list.setMaximumHeight(120)
        override_layout.addWidget(self.overrides_list)

        # Remove button
        remove_row = QHBoxLayout()
        remove_row.addStretch()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setFixedWidth(120)
        self.remove_btn.clicked.connect(self._remove_override)
        self.remove_btn.setEnabled(False)
        remove_row.addWidget(self.remove_btn)
        override_layout.addLayout(remove_row)

        # Connect list selection
        self.overrides_list.itemSelectionChanged.connect(self._on_override_selected)

        override_group.setLayout(override_layout)
        layout.addWidget(override_group)

        # Load current settings
        self._load_settings()
        self._load_overrides()

        # Add stretch
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(100, 36)
        save_btn.setObjectName("defaultButton")
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _on_ticker_input_changed(self, text: str):
        """Enable/disable add button based on ticker input."""
        self.add_override_btn.setEnabled(len(text.strip()) > 0)

    def _on_override_selected(self):
        """Enable/disable remove button based on list selection."""
        self.remove_btn.setEnabled(len(self.overrides_list.selectedItems()) > 0)

    def _add_override(self):
        """Add a new sector override."""
        ticker = self.ticker_input.text().strip().upper()
        sector = self.sector_combo.currentText()

        if not ticker:
            return

        # Save to service
        SectorOverrideService.set_override(ticker, sector)

        # Update list
        self._load_overrides()

        # Clear input
        self.ticker_input.clear()

    def _remove_override(self):
        """Remove selected override."""
        selected = self.overrides_list.selectedItems()
        if not selected:
            return

        for item in selected:
            ticker = item.data(Qt.UserRole)
            if ticker:
                SectorOverrideService.remove_override(ticker)

        # Update list
        self._load_overrides()

    def _load_overrides(self):
        """Load current overrides into list."""
        self.overrides_list.clear()

        overrides = SectorOverrideService.list_overrides()
        for ticker, data in sorted(overrides.items()):
            sector = data.get("sector", "Unknown")
            item = QListWidgetItem(f"{ticker}: {sector}")
            item.setData(Qt.UserRole, ticker)
            self.overrides_list.addItem(item)

        self.remove_btn.setEnabled(False)

    def _load_settings(self):
        """Load current settings into UI."""
        # Risk-free rate source
        if self.current_settings.get("risk_free_source") == "manual":
            self.manual_radio.setChecked(True)
            manual_rate = self.current_settings.get("manual_risk_free_rate", 0.05)
            self.manual_rate_spin.setValue(manual_rate * 100)
        else:
            self.irx_radio.setChecked(True)
            self.manual_rate_spin.setValue(self._current_irx_rate * 100)

        # Lookback period
        lookback_days = self.current_settings.get("lookback_days", 252)
        lookback_map = {63: 0, 126: 1, 252: 2, 504: 3, 756: 4}
        self.lookback_combo.setCurrentIndex(lookback_map.get(lookback_days, 2))

        # Currency factor
        self.currency_check.setChecked(
            self.current_settings.get("show_currency_factor", True)
        )

    def _save_settings(self):
        """Save settings and close dialog."""
        # Map lookback combo index to days
        lookback_map = {0: 63, 1: 126, 2: 252, 3: 504, 4: 756}
        lookback_days = lookback_map.get(self.lookback_combo.currentIndex(), 252)

        settings = {
            "risk_free_source": "manual" if self.manual_radio.isChecked() else "irx",
            "manual_risk_free_rate": self.manual_rate_spin.value() / 100,
            "lookback_days": lookback_days,
            "show_currency_factor": self.currency_check.isChecked(),
        }

        # Close dialog first, then emit signal
        self.accept()
        self.settings_saved.emit(settings)

    def get_settings(self) -> Dict[str, Any]:
        """Get the current dialog settings."""
        lookback_map = {0: 63, 1: 126, 2: 252, 3: 504, 4: 756}
        lookback_days = lookback_map.get(self.lookback_combo.currentIndex(), 252)

        return {
            "risk_free_source": "manual" if self.manual_radio.isChecked() else "irx",
            "manual_risk_free_rate": self.manual_rate_spin.value() / 100,
            "lookback_days": lookback_days,
            "show_currency_factor": self.currency_check.isChecked(),
        }

    def _apply_theme(self):
        """Apply theme styling."""
        super()._apply_theme()

        theme = self.theme_manager.current_theme
        colors = ThemeStylesheetService.get_colors(theme)

        # Additional styling for group boxes, radio buttons, etc.
        additional_style = f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {colors['border']};
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: {colors['text']};
            }}
            QRadioButton {{
                color: {colors['text']};
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
            }}
            QDoubleSpinBox, QComboBox {{
                background-color: {colors['bg_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            QDoubleSpinBox:focus, QComboBox:focus {{
                border-color: {colors['accent']};
            }}
            QLineEdit {{
                background-color: {colors['bg_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border-color: {colors['accent']};
            }}
            QLabel#settingsDescription {{
                color: {colors['text_muted']};
                font-size: 12px;
                margin-bottom: 8px;
            }}
            QLabel#settingsSubLabel {{
                color: {colors['text_muted']};
                font-size: 12px;
                margin-top: 8px;
            }}
            QCheckBox {{
                color: {colors['text']};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QListWidget {{
                background-color: {colors['bg_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
            }}
            QListWidget::item {{
                padding: 4px 8px;
            }}
            QListWidget::item:selected {{
                background-color: {colors['accent']};
                color: {colors['bg']};
            }}
        """

        self.setStyleSheet(self.styleSheet() + additional_style)
