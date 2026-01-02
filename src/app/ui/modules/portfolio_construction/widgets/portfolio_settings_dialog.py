"""Portfolio Settings Dialog - Settings dialog for Portfolio Construction module."""

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QCheckBox,
)

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import ThemedDialog


class PortfolioSettingsDialog(ThemedDialog):
    """
    Dialog for customizing portfolio construction settings.
    """

    def __init__(self, theme_manager: ThemeManager, current_settings: dict, parent=None):
        self.current_settings = current_settings
        super().__init__(theme_manager, "Portfolio Settings", parent, min_width=400)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content - called by ThemedDialog."""
        # Display settings group
        display_group = self._create_display_group()
        layout.addWidget(display_group)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setDefault(True)
        self.save_btn.setObjectName("defaultButton")
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

    def _create_display_group(self) -> QGroupBox:
        """Create display settings group."""
        group = QGroupBox("Display")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Highlight editable fields checkbox
        self.highlight_editable_check = QCheckBox("Highlight editable fields")
        self.highlight_editable_check.setChecked(
            self.current_settings.get("highlight_editable_fields", True)
        )
        layout.addWidget(self.highlight_editable_check)

        highlight_info = QLabel(
            "When enabled, editable cells in the transaction log\n"
            "will have a colored background matching the theme."
        )
        highlight_info.setWordWrap(True)
        highlight_info.setObjectName("noteLabel")
        layout.addWidget(highlight_info)

        layout.addSpacing(10)

        # Hide FREE CASH summary checkbox
        self.hide_free_cash_check = QCheckBox("Hide FREE CASH summary")
        self.hide_free_cash_check.setChecked(
            self.current_settings.get("hide_free_cash_summary", False)
        )
        layout.addWidget(self.hide_free_cash_check)

        free_cash_info = QLabel(
            "When enabled, the FREE CASH summary row in the\n"
            "transaction log will be hidden from view."
        )
        free_cash_info.setWordWrap(True)
        free_cash_info.setObjectName("noteLabel")
        layout.addWidget(free_cash_info)

        group.setLayout(layout)
        return group

    def _save_settings(self):
        """Save the settings and close."""
        self.result = {
            "highlight_editable_fields": self.highlight_editable_check.isChecked(),
            "hide_free_cash_summary": self.hide_free_cash_check.isChecked(),
        }
        self.accept()

    def get_settings(self):
        """Get the configured settings."""
        return getattr(self, "result", None)
