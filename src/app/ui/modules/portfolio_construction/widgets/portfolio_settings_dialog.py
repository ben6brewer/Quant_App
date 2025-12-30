"""Portfolio Settings Dialog - Settings dialog for Portfolio Construction module."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QWidget,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent

from app.core.theme_manager import ThemeManager


class PortfolioSettingsDialog(QDialog):
    """
    Dialog for customizing portfolio construction settings.
    """

    def __init__(self, theme_manager: ThemeManager, current_settings: dict, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(400)

        # Remove native title bar
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self.theme_manager = theme_manager
        self.current_settings = current_settings

        # For window dragging
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()
        self._load_current_settings()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Custom title bar
        self.title_bar = self._create_title_bar("Portfolio Settings")
        layout.addWidget(self.title_bar)

        # Content container
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        # Display settings group
        display_group = self._create_display_group()
        content_layout.addWidget(display_group)

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

        content_layout.addLayout(button_layout)

        # Add content to main layout
        layout.addWidget(content_widget)

    def _create_title_bar(self, title: str) -> QWidget:
        """Create custom title bar with window controls."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 0, 0)
        bar_layout.setSpacing(5)

        # Dialog title
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        bar_layout.addWidget(self.title_label)

        bar_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bar_layout.addWidget(close_btn)

        # Enable dragging from title bar
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press on title bar for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move on title bar for dragging."""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

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

        info_label = QLabel(
            "When enabled, editable cells in the transaction log\n"
            "will have a colored background matching the theme."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888888; font-style: italic; font-size: 11px;")
        layout.addWidget(info_label)

        group.setLayout(layout)
        return group

    def _load_current_settings(self):
        """Load current settings into the UI."""
        self.highlight_editable_check.setChecked(
            self.current_settings.get("highlight_editable_fields", True)
        )

    def _save_settings(self):
        """Save the settings and close."""
        self.result = {
            "highlight_editable_fields": self.highlight_editable_check.isChecked(),
        }
        self.accept()

    def get_settings(self):
        """Get the configured settings."""
        return getattr(self, "result", None)

    def _apply_theme(self):
        """Apply the current theme to the dialog."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Get dark theme stylesheet."""
        return """
            QDialog {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            #titleBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
            #titleLabel {
                background-color: transparent;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #ffffff;
                background-color: #2d2d2d;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QCheckBox {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
            }
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #00d4ff;
                background-color: #2d2d2d;
            }
            QPushButton:pressed {
                background-color: #00d4ff;
                color: #000000;
            }
            QPushButton#defaultButton {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
            QPushButton#defaultButton:hover {
                background-color: #00c4ef;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Get light theme stylesheet."""
        return """
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            #titleBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #cccccc;
            }
            #titleLabel {
                background-color: transparent;
                color: #000000;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(0, 0, 0, 0.08);
                color: #000000;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #000000;
                background-color: #f5f5f5;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QCheckBox {
                color: #333333;
                font-size: 13px;
                background-color: transparent;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #0066cc;
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                background-color: #0066cc;
                color: #ffffff;
            }
            QPushButton#defaultButton {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
            QPushButton#defaultButton:hover {
                background-color: #0052a3;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Get Bloomberg theme stylesheet."""
        return """
            QDialog {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            #titleBar {
                background-color: #0d1420;
                border-bottom: 1px solid #1a2332;
            }
            #titleLabel {
                background-color: transparent;
                color: #e8e8e8;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #e8e8e8;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #e8e8e8;
                background-color: #0d1420;
                border: 2px solid #1a2332;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QCheckBox {
                color: #b0b0b0;
                font-size: 13px;
                background-color: transparent;
            }
            QPushButton {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #FF8000;
                background-color: rgba(255, 128, 0, 0.1);
            }
            QPushButton:pressed {
                background-color: #FF8000;
                color: #000000;
            }
            QPushButton#defaultButton {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
            QPushButton#defaultButton:hover {
                background-color: #FF9520;
            }
        """
