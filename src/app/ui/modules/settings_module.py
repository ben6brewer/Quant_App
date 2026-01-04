from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
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
            "Clear cached market data stored on your local system. "
            "This includes parquet files and backfill status tracking."
        )
        desc_label.setObjectName("descLabel")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Clear cache button
        self.clear_cache_btn = QPushButton("Clear Local Cache")
        self.clear_cache_btn.setObjectName("clearCacheButton")
        self.clear_cache_btn.setCursor(Qt.PointingHandCursor)
        self.clear_cache_btn.clicked.connect(self._on_clear_cache_clicked)
        layout.addWidget(self.clear_cache_btn)

        group.setLayout(layout)
        return group

    def _on_clear_cache_clicked(self) -> None:
        """Handle clear cache button click."""
        # Show confirmation dialog
        result = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Clear Local Cache",
            "This will permanently delete all cached market data from your system.\n\n"
            "• All parquet files (~/.quant_terminal/cache/)\n"
            "• Backfill status tracking\n"
            "• In-memory cache\n\n"
            "The next time you load data, it will be re-fetched from Yahoo Finance.\n\n"
            "Are you sure you want to continue?",
            CustomMessageBox.Ok | CustomMessageBox.Cancel,
        )

        if result == CustomMessageBox.Ok:
            self._clear_cache()

    def _clear_cache(self) -> None:
        """Clear all cached market data."""
        from app.services.market_data import clear_cache

        try:
            clear_cache()
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "Cache Cleared",
                "Local cache has been successfully cleared.\n\n"
                "Market data will be re-fetched on next access.",
            )
        except Exception as e:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Error",
                f"Failed to clear cache:\n\n{str(e)}",
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
            QPushButton#clearCacheButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-left: 10px;
                margin-right: 10px;
                max-width: 200px;
            }
            QPushButton#clearCacheButton:hover {
                border-color: #ff6b6b;
                background-color: #3d3d3d;
            }
            QPushButton#clearCacheButton:pressed {
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
            QPushButton#clearCacheButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-left: 10px;
                margin-right: 10px;
                max-width: 200px;
            }
            QPushButton#clearCacheButton:hover {
                border-color: #e53935;
                background-color: #e8e8e8;
            }
            QPushButton#clearCacheButton:pressed {
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
            QPushButton#clearCacheButton {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                margin-left: 10px;
                margin-right: 10px;
                max-width: 200px;
            }
            QPushButton#clearCacheButton:hover {
                border-color: #ff6b6b;
                background-color: #1a2838;
            }
            QPushButton#clearCacheButton:pressed {
                background-color: #ff6b6b;
                color: #ffffff;
            }
        """
