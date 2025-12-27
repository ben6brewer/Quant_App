from __future__ import annotations

from typing import Callable
from PySide6.QtCore import QObject, Signal


class ThemeManager(QObject):
    """
    Centralized theme management for the application.
    Provides consistent theming across all modules and widgets.
    """

    theme_changed = Signal(str)  # Emits the new theme name

    def __init__(self):
        super().__init__()
        self._current_theme = "dark"
        self._theme_listeners = []

    @property
    def current_theme(self) -> str:
        """Get the current active theme."""
        return self._current_theme

    def set_theme(self, theme: str) -> None:
        """
        Set the application theme.
        
        Args:
            theme: Either "dark" or "light"
        """
        if theme not in ("dark", "light"):
            raise ValueError(f"Unknown theme: {theme}. Must be 'dark' or 'light'.")

        if theme == self._current_theme:
            return

        self._current_theme = theme
        self.theme_changed.emit(theme)

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
                color: #cccccc;
                font-size: 12px;
                font-weight: bold;
                padding: 0px 5px;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 1px solid #00d4ff;
            }
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #00d4ff;
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
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
                border: 1px solid #3d3d3d;
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
                color: #333333;
                font-size: 12px;
                font-weight: bold;
                padding: 0px 5px;
            }
            QLineEdit {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 1px solid #0066cc;
            }
            QComboBox {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #0066cc;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #333333;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """

    def get_controls_stylesheet(self) -> str:
        """Get controls stylesheet for current theme."""
        if self._current_theme == "light":
            return self.get_light_controls_style()
        return self.get_dark_controls_style()

    def get_chart_background_color(self) -> str:
        """Get chart background color for current theme."""
        return 'w' if self._current_theme == "light" else '#1e1e1e'

    def get_chart_line_color(self) -> tuple[int, int, int]:
        """Get chart line color for current theme."""
        return (0, 0, 0) if self._current_theme == "light" else (76, 175, 80)

    @staticmethod
    def get_dark_home_button_style() -> str:
        """Get dark theme stylesheet for home button."""
        return """
            #homeButton {
                background-color: #00d4ff;
                color: #000000;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            #homeButton:hover {
                background-color: #00c4ef;
            }
            #homeButton:pressed {
                background-color: #00b4df;
            }
            #settingsButton {
                background-color: #00d4ff;
                color: #000000;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                margin: 5px 10px;
            }
            #settingsButton:hover {
                background-color: #00c4ef;
            }
            #settingsButton:pressed {
                background-color: #00b4df;
            }
        """

    @staticmethod
    def get_light_home_button_style() -> str:
        """Get light theme stylesheet for home button."""
        return """
            #homeButton {
                background-color: #0066cc;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            #homeButton:hover {
                background-color: #0056b3;
            }
            #homeButton:pressed {
                background-color: #004999;
            }
            #settingsButton {
                background-color: #0066cc;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                margin: 5px 10px;
            }
            #settingsButton:hover {
                background-color: #0056b3;
            }
            #settingsButton:pressed {
                background-color: #004999;
            }
        """
