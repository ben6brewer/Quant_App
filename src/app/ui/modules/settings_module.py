from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QLabel,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager


class SettingsModule(QWidget):
    """Settings module with theme switching and other preferences."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()
        self._sync_theme_buttons()

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
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        # Header
        header = QLabel("Settings")
        header.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header)

        # Appearance settings
        appearance_group = self._create_appearance_group()
        layout.addWidget(appearance_group)

        # Future settings groups can go here
        # layout.addWidget(self._create_data_group())
        # layout.addWidget(self._create_api_group())

        layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_appearance_group(self) -> QGroupBox:
        """Create appearance settings group."""
        group = QGroupBox("Appearance")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
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
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Theme label
        theme_label = QLabel("Color Theme")
        theme_label.setStyleSheet("font-size: 14px; font-weight: normal; margin-left: 10px;")
        layout.addWidget(theme_label)

        # Radio buttons for theme selection
        self.theme_group = QButtonGroup(self)
        
        self.dark_radio = QRadioButton("Dark Mode")
        self.dark_radio.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.theme_group.addButton(self.dark_radio, 0)
        layout.addWidget(self.dark_radio)

        self.light_radio = QRadioButton("Light Mode")
        self.light_radio.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.theme_group.addButton(self.light_radio, 1)
        layout.addWidget(self.light_radio)

        self.bloomberg_radio = QRadioButton("Bloomberg Mode")
        self.bloomberg_radio.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                padding: 8px;
                margin-left: 20px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.theme_group.addButton(self.bloomberg_radio, 2)
        layout.addWidget(self.bloomberg_radio)

        # Connect theme change
        self.theme_group.buttonClicked.connect(self._on_theme_changed)

        group.setLayout(layout)
        return group

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
        self.theme_manager.set_theme(theme)
