"""Risk Analytics Settings Dialog - Configure module settings and sector overrides."""

from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
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
    - Analysis settings (lookback period, currency factor)
    - Sector classification overrides
    """

    settings_saved = Signal(dict)

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: Dict[str, Any],
        portfolio_tickers: List[str] = None,
        parent=None,
    ):
        """
        Initialize settings dialog.

        Args:
            theme_manager: Application theme manager
            current_settings: Current settings values
            portfolio_tickers: List of tickers in current portfolio (for validation)
            parent: Parent widget
        """
        self.current_settings = current_settings
        self.portfolio_tickers = set(t.upper() for t in (portfolio_tickers or []))
        super().__init__(
            theme_manager,
            "Risk Analytics Settings",
            parent,
            min_width=620,
            min_height=450,
        )

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
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
        self.ticker_input.textChanged.connect(self._on_ticker_text_changed)
        self.ticker_input.editingFinished.connect(self._on_ticker_editing_finished)
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
        self.add_override_btn.setFixedWidth(120)
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

        # Edit and Remove buttons
        action_row = QHBoxLayout()
        action_row.addStretch()

        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.setFixedWidth(130)
        self.edit_btn.clicked.connect(self._edit_override)
        self.edit_btn.setEnabled(False)
        action_row.addWidget(self.edit_btn)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setFixedWidth(130)
        self.remove_btn.clicked.connect(self._remove_override)
        self.remove_btn.setEnabled(False)
        action_row.addWidget(self.remove_btn)
        override_layout.addLayout(action_row)

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

    def _on_ticker_text_changed(self, text: str):
        """Enable/disable add button based on ticker input."""
        self.add_override_btn.setEnabled(len(text.strip()) > 0)

    def _on_ticker_editing_finished(self):
        """Validate ticker when user finishes editing (tab, enter, or click away)."""
        from app.ui.widgets.common.custom_message_box import CustomMessageBox

        ticker = self.ticker_input.text().strip().upper()

        # Only validate if there's text and we have portfolio tickers to check against
        if ticker and self.portfolio_tickers and ticker not in self.portfolio_tickers:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Ticker Not Found",
                f"'{ticker}' was not found in the current portfolio.\n\n"
                f"Make sure you're using the ticker symbol (e.g., 'AFRM') "
                f"not the company name (e.g., 'Affirm').",
            )

    def _on_override_selected(self):
        """Enable/disable edit and remove buttons based on list selection."""
        has_selection = len(self.overrides_list.selectedItems()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)

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

    def _edit_override(self):
        """Edit the selected override by loading it into the input fields."""
        selected = self.overrides_list.selectedItems()
        if not selected:
            return

        item = selected[0]
        ticker = item.data(Qt.UserRole)
        if not ticker:
            return

        # Get current sector for this ticker
        override = SectorOverrideService.get_override(ticker)
        if override:
            sector = override.get("sector", "")

            # Load into input fields
            self.ticker_input.setText(ticker)

            # Set the sector combo to the current sector
            index = self.sector_combo.findText(sector)
            if index >= 0:
                self.sector_combo.setCurrentIndex(index)

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

        self.edit_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)

    def _load_settings(self):
        """Load current settings into UI."""
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
            "lookback_days": lookback_days,
            "show_currency_factor": self.currency_check.isChecked(),
        }

    def _apply_theme(self):
        """Apply theme styling."""
        super()._apply_theme()

        theme = self.theme_manager.current_theme
        colors = ThemeStylesheetService.get_colors(theme)

        # Additional styling for group boxes, inputs, etc.
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
            QComboBox {{
                background-color: {colors['bg_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            QComboBox:focus {{
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
