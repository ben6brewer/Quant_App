"""Performance Metrics Settings Dialog - Configure module settings."""

from typing import Dict, Any

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
)
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.themed_dialog import ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService
from ..services.performance_metrics_service import PerformanceMetricsService


class PerformanceMetricsSettingsDialog(ThemedDialog):
    """
    Settings dialog for Performance Metrics module.

    Allows configuration of:
    - Risk-free rate source (3-month T-bill or manual)
    - Manual risk-free rate value
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
        # Fetch current ^IRX rate for display
        self._current_irx_rate = PerformanceMetricsService.get_risk_free_rate()
        super().__init__(
            theme_manager,
            "Performance Metrics Settings",
            parent,
            min_width=450,
        )

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        # Risk-Free Rate section
        rf_group = QGroupBox("Risk-Free Rate")
        rf_layout = QVBoxLayout()

        # Radio button group
        self.rf_button_group = QButtonGroup(self)

        # Option 1: Use ^IRX (3-month T-bill) - show current rate
        irx_rate_pct = self._current_irx_rate * 100
        self.irx_radio = QRadioButton(f"Use 3-Month Treasury Bill (^IRX of {irx_rate_pct:.2f}%)")
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

        # Description
        rf_desc = QLabel(
            "The risk-free rate is used to calculate Sharpe ratio, Sortino ratio, "
            "Jensen's alpha, and Treynor measure."
        )
        rf_desc.setWordWrap(True)
        rf_desc.setObjectName("settingsDescription")
        rf_layout.addWidget(rf_desc)

        rf_group.setLayout(rf_layout)
        layout.addWidget(rf_group)

        # Visualization section
        viz_group = QGroupBox("Visualization")
        viz_layout = QVBoxLayout()

        # Column visibility checkboxes
        self.show_3m_check = QCheckBox("Show 3 Months")
        self.show_3m_check.setObjectName("settingsCheckbox")
        viz_layout.addWidget(self.show_3m_check)

        self.show_6m_check = QCheckBox("Show 6 Months")
        self.show_6m_check.setObjectName("settingsCheckbox")
        viz_layout.addWidget(self.show_6m_check)

        self.show_12m_check = QCheckBox("Show 12 Months")
        self.show_12m_check.setObjectName("settingsCheckbox")
        viz_layout.addWidget(self.show_12m_check)

        self.show_ytd_check = QCheckBox("Show YTD")
        self.show_ytd_check.setObjectName("settingsCheckbox")
        viz_layout.addWidget(self.show_ytd_check)

        viz_group.setLayout(viz_layout)
        layout.addWidget(viz_group)

        # Load current settings
        self._load_settings()

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

    def _load_settings(self):
        """Load current settings into UI."""
        # Risk-free rate source
        if self.current_settings.get("risk_free_source") == "manual":
            self.manual_radio.setChecked(True)
            # Use saved manual rate
            manual_rate = self.current_settings.get("manual_risk_free_rate", 0.05)
            self.manual_rate_spin.setValue(manual_rate * 100)
        else:
            self.irx_radio.setChecked(True)
            # Auto-populate manual field with current IRX rate for visual reference
            self.manual_rate_spin.setValue(self._current_irx_rate * 100)

        # Column visibility
        self.show_3m_check.setChecked(self.current_settings.get("show_3_months", True))
        self.show_6m_check.setChecked(self.current_settings.get("show_6_months", True))
        self.show_12m_check.setChecked(self.current_settings.get("show_12_months", True))
        self.show_ytd_check.setChecked(self.current_settings.get("show_ytd", True))

    def _save_settings(self):
        """Save settings and close dialog."""
        settings = {
            "risk_free_source": "manual" if self.manual_radio.isChecked() else "irx",
            "manual_risk_free_rate": self.manual_rate_spin.value() / 100,
            "show_3_months": self.show_3m_check.isChecked(),
            "show_6_months": self.show_6m_check.isChecked(),
            "show_12_months": self.show_12m_check.isChecked(),
            "show_ytd": self.show_ytd_check.isChecked(),
        }

        # Close dialog first, then emit signal (so loading overlay shows properly)
        self.accept()
        self.settings_saved.emit(settings)

    def get_settings(self) -> Dict[str, Any]:
        """Get the current dialog settings."""
        return {
            "risk_free_source": "manual" if self.manual_radio.isChecked() else "irx",
            "manual_risk_free_rate": self.manual_rate_spin.value() / 100,
            "show_3_months": self.show_3m_check.isChecked(),
            "show_6_months": self.show_6m_check.isChecked(),
            "show_12_months": self.show_12m_check.isChecked(),
            "show_ytd": self.show_ytd_check.isChecked(),
        }

    def _apply_theme(self):
        """Apply theme styling."""
        super()._apply_theme()

        theme = self.theme_manager.current_theme
        colors = ThemeStylesheetService.get_colors(theme)

        # Additional styling for group boxes and radio buttons
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
            QDoubleSpinBox {{
                background-color: {colors['bg_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            QDoubleSpinBox:focus {{
                border-color: {colors['accent']};
            }}
            QLabel#settingsDescription {{
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
        """

        self.setStyleSheet(self.styleSheet() + additional_style)
