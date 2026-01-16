from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox


class SettingsModule(QWidget):
    """Settings module with theme switching and other preferences."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._is_changing_theme = False  # Flag to prevent redundant updates
        self._setup_ui()
        self._sync_theme_buttons()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_external_theme_change)

    def _setup_ui(self) -> None:
        """Create the settings UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scrollable area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 70, 40, 40)  # Extra top margin to avoid home button
        layout.setSpacing(30)

        # Header
        self.header = QLabel("Settings")
        self.header.setObjectName("headerLabel")
        layout.addWidget(self.header)

        # Appearance settings
        appearance_group = self._create_appearance_group()
        layout.addWidget(appearance_group)

        # Memory Manager settings
        memory_group = self._create_memory_group()
        layout.addWidget(memory_group)

        # Future settings groups can go here
        # layout.addWidget(self._create_api_group())

        layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_appearance_group(self) -> QGroupBox:
        """Create appearance settings group."""
        group = QGroupBox("Appearance")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Theme label
        theme_label = QLabel("Color Theme")
        theme_label.setObjectName("themeLabel")
        layout.addWidget(theme_label)

        # Radio buttons for theme selection
        self.theme_group = QButtonGroup(self)

        self.dark_radio = QRadioButton("Dark Mode")
        self.theme_group.addButton(self.dark_radio, 0)
        layout.addWidget(self.dark_radio)

        self.light_radio = QRadioButton("Light Mode")
        self.theme_group.addButton(self.light_radio, 1)
        layout.addWidget(self.light_radio)

        self.bloomberg_radio = QRadioButton("Bloomberg Mode")
        self.theme_group.addButton(self.bloomberg_radio, 2)
        layout.addWidget(self.bloomberg_radio)

        # Connect theme change
        self.theme_group.buttonClicked.connect(self._on_theme_changed)

        group.setLayout(layout)
        return group

    def _create_memory_group(self) -> QGroupBox:
        """Create memory manager settings group."""
        group = QGroupBox("Memory Manager")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Description label
        desc_label = QLabel(
            "Clear cached data stored on your local system. "
            "Data will be re-fetched from APIs on next use."
        )
        desc_label.setObjectName("descLabel")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Grid of cache buttons (2 columns)
        grid = QGridLayout()
        grid.setSpacing(10)

        # Define buttons: (label, handler)
        cache_buttons = [
            ("Clear Market Data", self._on_clear_market_data),
            ("Clear Ticker Metadata", self._on_clear_ticker_metadata),
            ("Clear Ticker Names", self._on_clear_ticker_names),
            ("Clear Portfolio Returns", self._on_clear_portfolio_returns),
            ("Clear Benchmark Returns", self._on_clear_benchmark_returns),
            ("Clear IWV Holdings", self._on_clear_iwv_holdings),
        ]

        for i, (label, handler) in enumerate(cache_buttons):
            btn = QPushButton(label)
            btn.setObjectName("cacheButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(handler)
            row = i // 2
            col = i % 2
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        # Clear All button (full width, more prominent)
        self.clear_all_btn = QPushButton("Clear All Cache")
        self.clear_all_btn.setObjectName("clearAllButton")
        self.clear_all_btn.setCursor(Qt.PointingHandCursor)
        self.clear_all_btn.clicked.connect(self._on_clear_all_cache)
        layout.addWidget(self.clear_all_btn)

        group.setLayout(layout)
        return group

    # -------------------------------------------------------------------------
    # Cache clear handlers
    # -------------------------------------------------------------------------

    def _on_clear_market_data(self) -> None:
        """Clear market data cache (parquet files + backfill status)."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Market Data",
            "This will delete all cached price data (parquet files) and backfill status.\n\n"
            "Data will be re-fetched from APIs on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.market_data import clear_cache
            try:
                clear_cache()
            except Exception as e:
                self._show_error("Failed to clear market data cache", e)

    def _on_clear_ticker_metadata(self) -> None:
        """Clear ticker metadata cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Ticker Metadata",
            "This will delete cached ticker information (sector, industry, beta, etc.).\n\n"
            "Metadata will be re-fetched from Yahoo Finance on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.ticker_metadata_service import TickerMetadataService
            try:
                TickerMetadataService.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear ticker metadata cache", e)

    def _on_clear_ticker_names(self) -> None:
        """Clear ticker names cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Ticker Names",
            "This will delete cached ticker display names (e.g., 'Apple Inc.').\n\n"
            "Names will be re-fetched from Yahoo Finance on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.ticker_name_cache import TickerNameCache
            try:
                TickerNameCache.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear ticker names cache", e)

    def _on_clear_portfolio_returns(self) -> None:
        """Clear portfolio returns cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Portfolio Returns",
            "This will delete all cached portfolio return calculations.\n\n"
            "Returns will be recalculated on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.returns_data_service import ReturnsDataService
            try:
                ReturnsDataService.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear portfolio returns cache", e)

    def _on_clear_benchmark_returns(self) -> None:
        """Clear benchmark returns cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Benchmark Returns",
            "This will delete all cached benchmark constituent returns.\n\n"
            "Returns will be re-fetched on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.benchmark_returns_service import BenchmarkReturnsService
            try:
                BenchmarkReturnsService.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear benchmark returns cache", e)

    def _on_clear_iwv_holdings(self) -> None:
        """Clear IWV holdings cache."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear IWV Holdings",
            "This will delete cached iShares Russell 3000 ETF holdings.\n\n"
            "Holdings will be re-fetched from iShares on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            from app.services.ishares_holdings_service import ISharesHoldingsService
            try:
                ISharesHoldingsService.clear_cache()
            except Exception as e:
                self._show_error("Failed to clear IWV holdings cache", e)

    def _on_clear_all_cache(self) -> None:
        """Clear all caches."""
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear All Cache",
            "This will delete ALL cached data:\n\n"
            "• Market data (price history)\n"
            "• Ticker metadata (sector, industry, beta)\n"
            "• Ticker names\n"
            "• Portfolio returns\n"
            "• Benchmark returns\n"
            "• IWV holdings\n\n"
            "All data will be re-fetched on next use.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )
        if result == CustomMessageBox.Ok:
            errors = []

            # Clear all caches
            try:
                from app.services.market_data import clear_cache
                clear_cache()
            except Exception as e:
                errors.append(f"Market data: {e}")

            try:
                from app.services.ticker_metadata_service import TickerMetadataService
                TickerMetadataService.clear_cache()
            except Exception as e:
                errors.append(f"Ticker metadata: {e}")

            try:
                from app.services.ticker_name_cache import TickerNameCache
                TickerNameCache.clear_cache()
            except Exception as e:
                errors.append(f"Ticker names: {e}")

            try:
                from app.services.returns_data_service import ReturnsDataService
                ReturnsDataService.clear_cache()
            except Exception as e:
                errors.append(f"Portfolio returns: {e}")

            try:
                from app.services.benchmark_returns_service import BenchmarkReturnsService
                BenchmarkReturnsService.clear_cache()
            except Exception as e:
                errors.append(f"Benchmark returns: {e}")

            try:
                from app.services.ishares_holdings_service import ISharesHoldingsService
                ISharesHoldingsService.clear_cache()
            except Exception as e:
                errors.append(f"IWV holdings: {e}")

            if errors:
                CustomMessageBox.critical(
                    self.theme_manager,
                    self,
                    "Partial Error",
                    "Some caches failed to clear:\n\n" + "\n".join(errors),
                )

    def _show_error(self, message: str, error: Exception) -> None:
        """Show error dialog."""
        CustomMessageBox.critical(
            self.theme_manager,
            self,
            "Error",
            f"{message}:\n\n{str(error)}",
        )

    def _sync_theme_buttons(self) -> None:
        """Synchronize radio buttons with current theme."""
        current_theme = self.theme_manager.current_theme
        if current_theme == "dark":
            self.dark_radio.setChecked(True)
        elif current_theme == "bloomberg":
            self.bloomberg_radio.setChecked(True)
        else:
            self.light_radio.setChecked(True)

    def _on_theme_changed(self) -> None:
        """Handle theme change from radio buttons."""
        if self.dark_radio.isChecked():
            theme = "dark"
        elif self.bloomberg_radio.isChecked():
            theme = "bloomberg"
        else:
            theme = "light"

        # Set flag to skip redundant _apply_theme call from signal
        self._is_changing_theme = True
        self.theme_manager.set_theme(theme)
        # Defer _apply_theme to avoid blocking the UI thread
        QTimer.singleShot(0, self._apply_theme)
        # Defer flag reset so external handlers still skip correctly
        QTimer.singleShot(0, lambda: setattr(self, '_is_changing_theme', False))

    def _on_external_theme_change(self) -> None:
        """Handle theme changes from external sources (not our radio buttons)."""
        if self._is_changing_theme:
            return  # Skip if we triggered the change
        self._sync_theme_buttons()
        self._apply_theme()

    def _apply_theme(self) -> None:
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
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QLabel#headerLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 10px;
            }
            QLabel#themeLabel {
                font-size: 14px;
                font-weight: normal;
                color: #cccccc;
                margin-left: 10px;
            }
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QRadioButton {
                color: #ffffff;
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #3d3d3d;
                background-color: #2d2d2d;
            }
            QRadioButton::indicator:checked {
                border-color: #00d4ff;
                background-color: #00d4ff;
            }
            QRadioButton::indicator:hover {
                border-color: #00d4ff;
            }
            QLabel#descLabel {
                font-size: 13px;
                color: #999999;
                margin-left: 10px;
                margin-right: 10px;
            }
            QPushButton#cacheButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#cacheButton:hover {
                border-color: #ff6b6b;
                background-color: #3d3d3d;
            }
            QPushButton#cacheButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
            QPushButton#clearAllButton {
                background-color: #3d2020;
                color: #ffffff;
                border: 1px solid #ff6b6b;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton#clearAllButton:hover {
                border-color: #ff8888;
                background-color: #4d2525;
            }
            QPushButton#clearAllButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QScrollArea {
                background-color: #ffffff;
                border: none;
            }
            QLabel#headerLabel {
                font-size: 24px;
                font-weight: bold;
                color: #000000;
                margin-bottom: 10px;
            }
            QLabel#themeLabel {
                font-size: 14px;
                font-weight: normal;
                color: #333333;
                margin-left: 10px;
            }
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #000000;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QRadioButton {
                color: #000000;
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #cccccc;
                background-color: #f5f5f5;
            }
            QRadioButton::indicator:checked {
                border-color: #0066cc;
                background-color: #0066cc;
            }
            QRadioButton::indicator:hover {
                border-color: #0066cc;
            }
            QLabel#descLabel {
                font-size: 13px;
                color: #666666;
                margin-left: 10px;
                margin-right: 10px;
            }
            QPushButton#cacheButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#cacheButton:hover {
                border-color: #e53935;
                background-color: #e8e8e8;
            }
            QPushButton#cacheButton:pressed {
                background-color: #e53935;
                color: #ffffff;
            }
            QPushButton#clearAllButton {
                background-color: #ffebee;
                color: #c62828;
                border: 1px solid #e53935;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton#clearAllButton:hover {
                border-color: #c62828;
                background-color: #ffcdd2;
            }
            QPushButton#clearAllButton:pressed {
                background-color: #e53935;
                color: #ffffff;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: #000814;
                color: #e8e8e8;
            }
            QScrollArea {
                background-color: #000814;
                border: none;
            }
            QLabel#headerLabel {
                font-size: 24px;
                font-weight: bold;
                color: #e8e8e8;
                margin-bottom: 10px;
            }
            QLabel#themeLabel {
                font-size: 14px;
                font-weight: normal;
                color: #a8a8a8;
                margin-left: 10px;
            }
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #e8e8e8;
                border: 2px solid #1a2838;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QRadioButton {
                color: #e8e8e8;
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #1a2838;
                background-color: #0d1420;
            }
            QRadioButton::indicator:checked {
                border-color: #FF8000;
                background-color: #FF8000;
            }
            QRadioButton::indicator:hover {
                border-color: #FF8000;
            }
            QLabel#descLabel {
                font-size: 13px;
                color: #808080;
                margin-left: 10px;
                margin-right: 10px;
            }
            QPushButton#cacheButton {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#cacheButton:hover {
                border-color: #ff6b6b;
                background-color: #1a2838;
            }
            QPushButton#cacheButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
            QPushButton#clearAllButton {
                background-color: #2a1515;
                color: #ff6b6b;
                border: 1px solid #ff6b6b;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton#clearAllButton:hover {
                border-color: #ff8888;
                background-color: #3a2020;
            }
            QPushButton#clearAllButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
        """
