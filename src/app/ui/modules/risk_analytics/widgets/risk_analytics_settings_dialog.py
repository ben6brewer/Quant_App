"""Risk Analytics Settings Dialog - Configure module settings and sector overrides."""

from typing import Any, Dict, List, Optional
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

from .smooth_scroll_widgets import SmoothScrollListWidget
from app.ui.widgets.common import SmoothScrollListView
from PySide6.QtCore import Signal, Qt, QDate

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
        # Compute sectors present in the portfolio
        self.universe_sectors = self._compute_portfolio_sectors()
        # Custom date range storage
        self._custom_start_date: Optional[str] = current_settings.get("custom_start_date")
        self._custom_end_date: Optional[str] = current_settings.get("custom_end_date")
        super().__init__(
            theme_manager,
            "Risk Analytics Settings",
            parent,
            min_width=620,
            min_height=720,
        )

    def _compute_portfolio_sectors(self) -> List[str]:
        """
        Compute sectors present in the current portfolio.

        Returns only sectors that have at least one ticker in the portfolio.
        Falls back to all sectors (excluding Not Classified) if no portfolio loaded.
        """
        if not self.portfolio_tickers:
            # No portfolio - show all sectors except "Not Classified"
            return [s for s in SectorOverrideService.SECTORS if s != "Not Classified"]

        # Get unique sectors from portfolio tickers
        portfolio_sector_set = set()
        for ticker in self.portfolio_tickers:
            sector = SectorOverrideService.get_effective_sector(ticker)
            portfolio_sector_set.add(sector)

        # Return in standard SECTORS order (for consistent UI)
        return [s for s in SectorOverrideService.SECTORS if s in portfolio_sector_set]

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
            ["3 Months", "6 Months", "1 Year", "2 Years", "3 Years", "Custom Date Range..."]
        )
        self.lookback_combo.setFixedWidth(180)
        # Use activated signal so clicking the same item again still triggers
        self.lookback_combo.activated.connect(self._on_lookback_activated)
        lookback_row.addWidget(self.lookback_combo)
        lookback_row.addStretch()
        analysis_layout.addLayout(lookback_row)

        # Currency factor checkbox
        self.currency_check = QCheckBox("Include Currency Factor in decomposition")
        self.currency_check.setObjectName("settingsCheckbox")
        analysis_layout.addWidget(self.currency_check)

        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)

        # Universe Settings section
        universe_group = QGroupBox("Universe Settings")
        universe_layout = QHBoxLayout()

        # Portfolio Universe
        portfolio_universe_layout = QVBoxLayout()
        portfolio_universe_label = QLabel("Portfolio Universe:")
        portfolio_universe_label.setObjectName("settingsSubLabel")
        portfolio_universe_layout.addWidget(portfolio_universe_label)

        self.portfolio_universe_list = SmoothScrollListWidget()
        self.portfolio_universe_list.setFixedHeight(150)
        self.portfolio_universe_list.setSelectionMode(QListWidget.MultiSelection)
        self.portfolio_universe_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.portfolio_universe_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for sector in self.universe_sectors:
            item = QListWidgetItem(sector)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.portfolio_universe_list.addItem(item)
        portfolio_universe_layout.addWidget(self.portfolio_universe_list)

        # Select All / Clear buttons for portfolio
        portfolio_btn_row = QHBoxLayout()
        portfolio_btn_row.setContentsMargins(0, 20, 0, 0)
        self.portfolio_select_all_btn = QPushButton("Select All")
        self.portfolio_select_all_btn.setFixedWidth(80)
        self.portfolio_select_all_btn.clicked.connect(self._select_all_portfolio_sectors)
        portfolio_btn_row.addWidget(self.portfolio_select_all_btn)

        self.portfolio_clear_btn = QPushButton("Clear")
        self.portfolio_clear_btn.setFixedWidth(80)
        self.portfolio_clear_btn.clicked.connect(self._clear_portfolio_sectors)
        portfolio_btn_row.addWidget(self.portfolio_clear_btn)
        portfolio_btn_row.addStretch()
        portfolio_universe_layout.addLayout(portfolio_btn_row)

        universe_layout.addLayout(portfolio_universe_layout)

        # Benchmark Universe (disabled for now)
        benchmark_universe_layout = QVBoxLayout()
        benchmark_universe_label = QLabel("Benchmark Universe:")
        benchmark_universe_label.setObjectName("settingsSubLabel")
        benchmark_universe_layout.addWidget(benchmark_universe_label)

        self.benchmark_universe_list = SmoothScrollListWidget()
        self.benchmark_universe_list.setFixedHeight(150)
        self.benchmark_universe_list.setSelectionMode(QListWidget.MultiSelection)
        self.benchmark_universe_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.benchmark_universe_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.benchmark_universe_list.setEnabled(False)  # Disabled for now
        for sector in self.universe_sectors:
            item = QListWidgetItem(sector)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.benchmark_universe_list.addItem(item)
        benchmark_universe_layout.addWidget(self.benchmark_universe_list)

        # Select All / Clear buttons for benchmark (disabled)
        benchmark_btn_row = QHBoxLayout()
        benchmark_btn_row.setContentsMargins(0, 20, 0, 0)
        self.benchmark_select_all_btn = QPushButton("Select All")
        self.benchmark_select_all_btn.setFixedWidth(80)
        self.benchmark_select_all_btn.setEnabled(False)
        benchmark_btn_row.addWidget(self.benchmark_select_all_btn)

        self.benchmark_clear_btn = QPushButton("Clear")
        self.benchmark_clear_btn.setFixedWidth(80)
        self.benchmark_clear_btn.setEnabled(False)
        benchmark_btn_row.addWidget(self.benchmark_clear_btn)
        benchmark_btn_row.addStretch()
        benchmark_universe_layout.addLayout(benchmark_btn_row)

        universe_layout.addLayout(benchmark_universe_layout)

        universe_group.setLayout(universe_layout)
        layout.addWidget(universe_group)

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
        smooth_view = SmoothScrollListView(self.sector_combo)
        self.sector_combo.setView(smooth_view)
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

        self.overrides_list = SmoothScrollListWidget()
        self.overrides_list.setFixedHeight(210)
        self.overrides_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.overrides_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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

    def _select_all_portfolio_sectors(self):
        """Select all sectors in portfolio universe."""
        for i in range(self.portfolio_universe_list.count()):
            self.portfolio_universe_list.item(i).setCheckState(Qt.Checked)

    def _clear_portfolio_sectors(self):
        """Clear all sectors in portfolio universe."""
        for i in range(self.portfolio_universe_list.count()):
            self.portfolio_universe_list.item(i).setCheckState(Qt.Unchecked)

    def _get_checked_portfolio_sectors(self) -> List[str]:
        """Get list of checked sectors in portfolio universe."""
        checked = []
        for i in range(self.portfolio_universe_list.count()):
            item = self.portfolio_universe_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked

    def _set_checked_portfolio_sectors(self, sectors: List[str]):
        """Set checked state for portfolio universe sectors."""
        sector_set = set(sectors) if sectors else set(self.universe_sectors)
        for i in range(self.portfolio_universe_list.count()):
            item = self.portfolio_universe_list.item(i)
            if item.text() in sector_set:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _on_lookback_activated(self, index: int):
        """Handle lookback period dropdown selection (activated fires even for same item)."""
        text = self.lookback_combo.itemText(index)
        if text == "Custom Date Range...":
            self._show_date_range_dialog()

    def _show_date_range_dialog(self):
        """Show the custom date range dialog."""
        from app.ui.modules.return_distribution.widgets.date_range_dialog import DateRangeDialog

        dialog = DateRangeDialog(self.theme_manager, self)

        # Pre-populate with existing custom dates if available
        # Check both instance variables and current_settings as fallback
        start_date_str = self._custom_start_date or self.current_settings.get("custom_start_date")
        end_date_str = self._custom_end_date or self.current_settings.get("custom_end_date")

        if start_date_str:
            start_date = QDate.fromString(start_date_str, "yyyy-MM-dd")
            if start_date.isValid():
                dialog.start_date_input.setDate(start_date)

        if end_date_str:
            end_date = QDate.fromString(end_date_str, "yyyy-MM-dd")
            if end_date.isValid():
                dialog.end_date_input.setDate(end_date)

        from PySide6.QtWidgets import QDialog
        if dialog.exec() == QDialog.Accepted:
            start_date, end_date = dialog.get_date_range()
            if start_date and end_date:
                self._custom_start_date = start_date
                self._custom_end_date = end_date
                # Update dropdown to show "Custom"
                self._update_lookback_display_custom()
            else:
                # Dialog accepted but no valid dates - revert
                self._revert_lookback_selection()
        else:
            # User cancelled - revert to previous selection
            self._revert_lookback_selection()

    def _update_lookback_display_custom(self):
        """Update the lookback dropdown to show 'Custom Date Range...' as selected."""
        self.lookback_combo.blockSignals(True)
        # Just select "Custom Date Range..." - no need for a separate "Custom" item
        custom_index = self.lookback_combo.findText("Custom Date Range...")
        if custom_index >= 0:
            self.lookback_combo.setCurrentIndex(custom_index)
        self.lookback_combo.blockSignals(False)

    def _revert_lookback_selection(self):
        """Revert lookback dropdown to previous selection."""
        self.lookback_combo.blockSignals(True)
        # If we have custom dates, show "Custom", otherwise show based on lookback_days
        if self._custom_start_date and self._custom_end_date:
            self._update_lookback_display_custom()
        else:
            lookback_days = self.current_settings.get("lookback_days", 252)
            lookback_days_to_text = {
                63: "3 Months",
                126: "6 Months",
                252: "1 Year",
                504: "2 Years",
                756: "3 Years",
            }
            text = lookback_days_to_text.get(lookback_days or 252, "1 Year")
            index = self.lookback_combo.findText(text)
            if index >= 0:
                self.lookback_combo.setCurrentIndex(index)
        self.lookback_combo.blockSignals(False)

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
        self.lookback_combo.blockSignals(True)

        # Lookback period - check if custom date range is set
        lookback_days = self.current_settings.get("lookback_days")
        custom_start = self.current_settings.get("custom_start_date")
        custom_end = self.current_settings.get("custom_end_date")

        # Always load custom dates from settings if available (for pre-population)
        if custom_start:
            self._custom_start_date = custom_start
        if custom_end:
            self._custom_end_date = custom_end

        if lookback_days is None and custom_start and custom_end:
            # Custom date range is active - show "Custom" in dropdown
            self._update_lookback_display_custom()
        else:
            # Standard lookback period - use text-based lookup (more robust)
            lookback_days_to_text = {
                63: "3 Months",
                126: "6 Months",
                252: "1 Year",
                504: "2 Years",
                756: "3 Years",
            }
            text = lookback_days_to_text.get(lookback_days or 252, "1 Year")
            index = self.lookback_combo.findText(text)
            if index >= 0:
                self.lookback_combo.setCurrentIndex(index)

        self.lookback_combo.blockSignals(False)

        # Currency factor
        self.currency_check.setChecked(
            self.current_settings.get("show_currency_factor", True)
        )

        # Portfolio universe sectors (default to all sectors if not set)
        portfolio_sectors = self.current_settings.get("portfolio_universe_sectors")
        self._set_checked_portfolio_sectors(portfolio_sectors)

    def _save_settings(self):
        """Save settings and close dialog."""
        # Get checked portfolio universe sectors
        portfolio_sectors = self._get_checked_portfolio_sectors()

        # Check if custom date range is selected
        current_text = self.lookback_combo.currentText()
        if current_text == "Custom Date Range..." and self._custom_start_date and self._custom_end_date:
            # Custom date range
            settings = {
                "lookback_days": None,
                "custom_start_date": self._custom_start_date,
                "custom_end_date": self._custom_end_date,
                "show_currency_factor": self.currency_check.isChecked(),
                "portfolio_universe_sectors": portfolio_sectors,
            }
        else:
            # Standard lookback period - use text-based lookup (more robust than index)
            lookback_text_map = {
                "3 Months": 63,
                "6 Months": 126,
                "1 Year": 252,
                "2 Years": 504,
                "3 Years": 756,
            }
            lookback_days = lookback_text_map.get(current_text, 252)
            settings = {
                "lookback_days": lookback_days,
                "custom_start_date": None,
                "custom_end_date": None,
                "show_currency_factor": self.currency_check.isChecked(),
                "portfolio_universe_sectors": portfolio_sectors,
            }

        # Emit signal first, then close dialog
        self.settings_saved.emit(settings)
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        """Get the current dialog settings."""
        current_text = self.lookback_combo.currentText()

        if current_text == "Custom Date Range..." and self._custom_start_date and self._custom_end_date:
            return {
                "lookback_days": None,
                "custom_start_date": self._custom_start_date,
                "custom_end_date": self._custom_end_date,
                "show_currency_factor": self.currency_check.isChecked(),
            }
        else:
            lookback_map = {0: 63, 1: 126, 2: 252, 3: 504, 4: 756}
            lookback_days = lookback_map.get(self.lookback_combo.currentIndex(), 252)
            return {
                "lookback_days": lookback_days,
                "custom_start_date": None,
                "custom_end_date": None,
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
            QListWidget:disabled {{
                background-color: {colors['bg']};
                color: {colors['text_muted']};
            }}
            QListWidget::item {{
                padding: 4px 8px;
            }}
            QListWidget::item:selected {{
                background-color: {colors['accent']};
                color: {colors['bg']};
            }}
            QListWidget::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {colors['border']};
                border-radius: 2px;
                background-color: {colors['bg_alt']};
            }}
            QListWidget::indicator:checked {{
                background-color: {colors['accent']};
                border-color: {colors['accent']};
            }}
            QListWidget::indicator:disabled {{
                background-color: {colors['bg']};
                border-color: {colors['border']};
            }}
        """

        self.setStyleSheet(self.styleSheet() + additional_style)
