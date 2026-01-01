from __future__ import annotations

from typing import Callable
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QPushButton


class ThemeManager(QObject):
    """
    Centralized theme management for the application.
    Provides consistent theming across all modules and widgets.
    Automatically saves theme preferences to disk.
    """

    theme_changed = Signal(str)  # Emits the new theme name

    def __init__(self):
        super().__init__()
        self._current_theme = "bloomberg"  # Default if not loaded from preferences
        self._theme_listeners = []
        self._styled_buttons = []  # Track buttons for theme updates

    @property
    def current_theme(self) -> str:
        """Get the current active theme."""
        return self._current_theme

    def set_theme(self, theme: str, save_preference: bool = True) -> None:
        """
        Set the application theme.

        Args:
            theme: Either "dark", "light", or "bloomberg"
            save_preference: Whether to save the theme preference to disk (default: True)
        """
        if theme not in ("dark", "light", "bloomberg"):
            raise ValueError(f"Unknown theme: {theme}. Must be 'dark', 'light', or 'bloomberg'.")

        if theme == self._current_theme:
            return

        self._current_theme = theme

        # Emit signal immediately so UI can respond
        self.theme_changed.emit(theme)

        # Defer button updates to avoid blocking the UI thread
        QTimer.singleShot(0, self._update_styled_buttons)

        # Save preference to disk
        if save_preference:
            from app.services.preferences_service import PreferencesService
            PreferencesService.set_theme(theme)

    def _update_styled_buttons(self) -> None:
        """Apply current theme styling to all tracked buttons (deferred)."""
        universal_style = self._get_universal_button_style()
        # Filter out destroyed buttons and update valid ones
        valid_buttons = []
        for button in self._styled_buttons:
            try:
                # Try to access the button - will raise if deleted
                if button and button.isVisible is not None:
                    button.setStyleSheet(universal_style)
                    valid_buttons.append(button)
            except RuntimeError:
                # Button was deleted, skip it
                pass
        self._styled_buttons = valid_buttons

    def register_listener(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback to be notified of theme changes.
        
        Args:
            callback: Function that takes theme name as argument
        """
        self._theme_listeners.append(callback)
        self.theme_changed.connect(callback)

    def unregister_listener(self, callback: Callable[[str], None]) -> None:
        """Unregister a theme change callback."""
        if callback in self._theme_listeners:
            self._theme_listeners.remove(callback)
            self.theme_changed.disconnect(callback)

    # Dark theme stylesheets
    @staticmethod
    def get_dark_sidebar_style() -> str:
        """Get dark theme stylesheet for sidebar."""
        return """
            #sidebar {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            
            #sidebarHeader {
                background-color: #1a1a1a;
                color: #00d4ff;
                font-size: 14px;
                font-weight: bold;
                padding: 20px 10px;
                border-bottom: 2px solid #00d4ff;
            }
            
            #sidebarFooter {
                color: #666666;
                font-size: 10px;
                padding: 10px;
            }
            
            #navButton {
                text-align: left;
                padding: 15px 20px;
                border: none;
                background-color: transparent;
                color: #cccccc;
                font-size: 13px;
                font-weight: 500;
            }
            
            #navButton:hover {
                background-color: #3d3d3d;
                color: #ffffff;
            }
            
            #navButton:checked {
                background-color: #00d4ff;
                color: #000000;
                font-weight: bold;
            }
        """

    @staticmethod
    def get_dark_content_style() -> str:
        """Get dark theme stylesheet for content area."""
        return """
            QStackedWidget {
                background-color: #1e1e1e;
            }
            
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            
            QGroupBox {
                color: #ffffff;
                background-color: #2d2d2d;
            }
            
            QLabel {
                color: #cccccc;
            }
            
            QRadioButton {
                color: #cccccc;
            }
            
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """

    @staticmethod
    def get_dark_controls_style() -> str:
        """Get dark theme stylesheet for chart controls."""
        return """
            QWidget {
                background-color: #2d2d2d;
                border-bottom: 2px solid #00d4ff;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 12px;
                font-weight: bold;
                font-family: "Segoe UI", "Arial", sans-serif;
                letter-spacing: 0.5px;
                padding: 0px 5px;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 7px 10px;
                font-size: 13px;
                font-weight: 600;
                selection-background-color: #00d4ff;
                selection-color: #000000;
            }
            QLineEdit:hover {
                border: 1px solid #00d4ff;
                background-color: #252525;
            }
            QLineEdit:focus {
                border: 1px solid #00d4ff;
                background-color: #252525;
            }
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                padding: 7px 10px;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox:hover {
                border: 1px solid #00d4ff;
                background-color: #252525;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #cccccc;
                margin-right: 5px;
            }
            QComboBox::down-arrow:hover {
                border-top-color: #00d4ff;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
                border: 1px solid #00d4ff;
            }
        """

    # Light theme stylesheets
    @staticmethod
    def get_light_sidebar_style() -> str:
        """Get light theme stylesheet for sidebar."""
        return """
            #sidebar {
                background-color: #f5f5f5;
                color: #000000;
            }
            
            #sidebarHeader {
                background-color: #e0e0e0;
                color: #0066cc;
                font-size: 14px;
                font-weight: bold;
                padding: 20px 10px;
                border-bottom: 2px solid #0066cc;
            }
            
            #sidebarFooter {
                color: #999999;
                font-size: 10px;
                padding: 10px;
            }
            
            #navButton {
                text-align: left;
                padding: 15px 20px;
                border: none;
                background-color: transparent;
                color: #333333;
                font-size: 13px;
                font-weight: 500;
            }
            
            #navButton:hover {
                background-color: #e8e8e8;
                color: #000000;
            }
            
            #navButton:checked {
                background-color: #0066cc;
                color: #ffffff;
                font-weight: bold;
            }
        """

    @staticmethod
    def get_light_content_style() -> str:
        """Get light theme stylesheet for content area."""
        return """
            QStackedWidget {
                background-color: #ffffff;
            }
            
            QScrollArea {
                background-color: #ffffff;
                border: none;
            }
            
            QGroupBox {
                color: #000000;
                background-color: #f5f5f5;
                border: 2px solid #d0d0d0;
            }
            
            QLabel {
                color: #333333;
            }
            
            QRadioButton {
                color: #333333;
            }
            
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
        """

    @staticmethod
    def get_light_controls_style() -> str:
        """Get light theme stylesheet for chart controls."""
        return """
            QWidget {
                background-color: #f5f5f5;
                border-bottom: 2px solid #0066cc;
            }
            QLabel {
                color: #555555;
                font-size: 12px;
                font-weight: bold;
                font-family: "Segoe UI", "Arial", sans-serif;
                letter-spacing: 0.5px;
                padding: 0px 5px;
            }
            QLineEdit {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 2px;
                padding: 7px 10px;
                font-size: 13px;
                font-weight: 600;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
            }
            QLineEdit:hover {
                border: 1px solid #0066cc;
                background-color: #f9f9f9;
            }
            QLineEdit:focus {
                border: 1px solid #0066cc;
                background-color: #ffffff;
            }
            QComboBox {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 2px;
                padding: 7px 10px;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox:hover {
                border: 1px solid #0066cc;
                background-color: #f9f9f9;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #555555;
                margin-right: 5px;
            }
            QComboBox::down-arrow:hover {
                border-top-color: #0066cc;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
                border: 1px solid #0066cc;
            }
        """

    def get_controls_stylesheet(self) -> str:
        """Get controls stylesheet for current theme."""
        if self._current_theme == "light":
            return self.get_light_controls_style()
        elif self._current_theme == "bloomberg":
            return self.get_bloomberg_controls_style()
        return self.get_dark_controls_style()

    def get_chart_background_color(self) -> str:
        """Get chart background color for current theme."""
        if self._current_theme == "light":
            return 'w'
        elif self._current_theme == "bloomberg":
            return '#000814'
        return '#1e1e1e'

    def get_chart_line_color(self) -> tuple[int, int, int]:
        """Get chart line color for current theme."""
        if self._current_theme == "light":
            return (0, 0, 0)
        elif self._current_theme == "bloomberg":
            return (0, 212, 255)  # Bloomberg cyan
        return (76, 175, 80)

    @staticmethod
    def get_dark_home_button_style() -> str:
        """Get dark theme stylesheet for home button."""
        return """
            #homeButton, #chartSettingsButton, #settingsButton {
                background-color: transparent;
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
            }
            #settingsButton {
                margin: 5px 10px;
            }
            #homeButton:hover, #chartSettingsButton:hover, #settingsButton:hover {
                background-color: rgba(0, 212, 255, 0.15);
                border: 1px solid #00d4ff;
            }
            #homeButton:pressed, #chartSettingsButton:pressed, #settingsButton:pressed {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
        """

    @staticmethod
    def get_light_home_button_style() -> str:
        """Get light theme stylesheet for home button."""
        return """
            #homeButton, #chartSettingsButton, #settingsButton {
                background-color: transparent;
                color: #000000;
                border: 1px solid transparent;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
            }
            #settingsButton {
                margin: 5px 10px;
            }
            #homeButton:hover, #chartSettingsButton:hover, #settingsButton:hover {
                background-color: rgba(0, 102, 204, 0.15);
                border: 1px solid #0066cc;
            }
            #homeButton:pressed, #chartSettingsButton:pressed, #settingsButton:pressed {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
        """

    # Bloomberg theme stylesheets
    @staticmethod
    def get_bloomberg_sidebar_style() -> str:
        """Get Bloomberg theme stylesheet for sidebar."""
        return """
            #sidebar {
                background-color: #0d1420;
                color: #e8e8e8;
            }

            #sidebarHeader {
                background-color: #000814;
                color: #FF8000;
                font-size: 14px;
                font-weight: bold;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                padding: 20px 10px;
                border-bottom: 2px solid #FF8000;
            }

            #sidebarFooter {
                color: #666666;
                font-size: 10px;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                padding: 10px;
            }

            #navButton {
                text-align: left;
                padding: 15px 20px;
                border: none;
                background-color: transparent;
                color: #b0b0b0;
                font-size: 13px;
                font-weight: 500;
            }

            #navButton:hover {
                background-color: #162030;
                color: #e8e8e8;
                border-left: 3px solid #FF8000;
            }

            #navButton:checked {
                background-color: #FF8000;
                color: #000000;
                font-weight: bold;
            }
        """

    @staticmethod
    def get_bloomberg_content_style() -> str:
        """Get Bloomberg theme stylesheet for content area."""
        return """
            QStackedWidget {
                background-color: #000814;
            }

            QScrollArea {
                background-color: #000814;
                border: none;
            }

            QGroupBox {
                color: #e8e8e8;
                background-color: #0a1018;
                border: 1px solid #1a2332;
                font-family: "Segoe UI", "Arial", sans-serif;
            }

            QLabel {
                color: #b0b0b0;
            }

            QRadioButton {
                color: #b0b0b0;
            }

            QWidget {
                background-color: #000814;
                color: #e8e8e8;
            }
        """

    @staticmethod
    def get_bloomberg_controls_style() -> str:
        """Get Bloomberg theme stylesheet for chart controls."""
        return """
            QWidget {
                background-color: #0d1420;
                border-bottom: 2px solid #FF8000;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 11px;
                font-weight: bold;
                font-family: "Segoe UI", "Arial", sans-serif;
                letter-spacing: 0.5px;
                padding: 0px 5px;
            }
            QLineEdit {
                background-color: #0a1018;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: 600;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                selection-background-color: #FF8000;
                selection-color: #000000;
            }
            QLineEdit:hover {
                border: 1px solid #FF8000;
                background-color: #0d1420;
            }
            QLineEdit:focus {
                border: 1px solid #FF8000;
                background-color: #0d1420;
            }
            QComboBox {
                background-color: #0a1018;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox:hover {
                border: 1px solid #FF8000;
                background-color: #0d1420;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #b0b0b0;
                margin-right: 5px;
            }
            QComboBox::down-arrow:hover {
                border-top-color: #FF8000;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1420;
                color: #e8e8e8;
                selection-background-color: #FF8000;
                selection-color: #000000;
                border: 1px solid #FF8000;
            }
        """

    @staticmethod
    def get_bloomberg_home_button_style() -> str:
        """Get Bloomberg theme stylesheet for home button."""
        return """
            #homeButton, #chartSettingsButton, #settingsButton {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid transparent;
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                font-family: "Segoe UI", "Arial", sans-serif;
            }
            #settingsButton {
                margin: 5px 10px;
            }
            #homeButton:hover, #chartSettingsButton:hover, #settingsButton:hover {
                background-color: rgba(255, 128, 0, 0.15);
                border: 1px solid #FF8000;
            }
            #homeButton:pressed, #chartSettingsButton:pressed, #settingsButton:pressed {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
        """

    def get_home_button_style(self) -> str:
        """Get home button stylesheet for current theme."""
        if self._current_theme == "light":
            return self.get_light_home_button_style()
        elif self._current_theme == "bloomberg":
            return self.get_bloomberg_home_button_style()
        return self.get_dark_home_button_style()

    def create_styled_button(self, text: str, checkable: bool = False) -> QPushButton:
        """
        Create a button with universal styling applied.

        Args:
            text: Button text
            checkable: If True, button is checkable (toggle button)

        Returns:
            QPushButton with styling applied and tracked for theme updates
        """
        button = QPushButton(text)
        button.setCheckable(checkable)
        stylesheet = self._get_universal_button_style()
        button.setStyleSheet(stylesheet)

        # Track for theme updates
        self._styled_buttons.append(button)

        return button

    def _get_universal_button_style(self) -> str:
        """Get universal button stylesheet for current theme."""
        if self._current_theme == "light":
            return self._get_light_button_style()
        elif self._current_theme == "bloomberg":
            return self._get_bloomberg_button_style()
        return self._get_dark_button_style()

    @staticmethod
    def _get_dark_button_style() -> str:
        """Universal button style for dark theme."""
        return """
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(0, 212, 255, 0.15);
                border: 1px solid #00d4ff;
            }
            QPushButton:pressed {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
            QPushButton:checked {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
            QPushButton:disabled {
                opacity: 0.4;
            }
        """

    @staticmethod
    def _get_light_button_style() -> str:
        """Universal button style for light theme."""
        return """
            QPushButton {
                background-color: transparent;
                color: #000000;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(0, 102, 204, 0.15);
                border: 1px solid #0066cc;
            }
            QPushButton:pressed {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
            QPushButton:checked {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
            QPushButton:disabled {
                opacity: 0.4;
            }
        """

    @staticmethod
    def _get_bloomberg_button_style() -> str:
        """Universal button style for Bloomberg theme."""
        return """
            QPushButton {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 128, 0, 0.15);
                border: 1px solid #FF8000;
            }
            QPushButton:pressed {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
            QPushButton:checked {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
            QPushButton:disabled {
                opacity: 0.4;
            }
        """
