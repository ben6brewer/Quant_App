"""Portfolio Dialogs - New/Load Portfolio Dialogs"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QWidget
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox
from ..services.portfolio_persistence import PortfolioPersistence


class NewPortfolioDialog(QDialog):
    """Dialog to create a new portfolio."""

    def __init__(self, theme_manager: ThemeManager, existing_names: List[str], parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.theme_manager = theme_manager
        self.existing_names = existing_names
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = self._create_title_bar("New Portfolio")
        layout.addWidget(title_bar)

        # Content
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        content_layout.addWidget(QLabel("Portfolio Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter portfolio name...")
        self.name_edit.returnPressed.connect(self._validate_and_accept)
        content_layout.addWidget(self.name_edit)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        create_btn = QPushButton("Create")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(create_btn)

        content_layout.addLayout(button_layout)

        layout.addWidget(content)

    def _create_title_bar(self, title: str) -> QWidget:
        """Create custom title bar with close button."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 0, 0)
        bar_layout.setSpacing(5)

        # Dialog title
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        bar_layout.addWidget(title_label)

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

    def _validate_and_accept(self):
        """Validate name and accept."""
        name = self.name_edit.text().strip()

        if not name:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Invalid Name",
                "Please enter a portfolio name."
            )
            return

        if name in self.existing_names:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Name Exists",
                f"A portfolio named '{name}' already exists."
            )
            return

        self.accept()

    def get_name(self) -> str:
        """Get entered portfolio name."""
        return self.name_edit.text().strip()

    def _apply_theme(self):
        """Apply theme styling."""
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
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QWidget#titleBar {
                background-color: #2d2d2d;
            }
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }
            QPushButton#titleBarCloseButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 16px;
            }
            QPushButton#titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #00d4ff;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #00d4ff;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            QWidget#titleBar {
                background-color: #f5f5f5;
            }
            QLabel#titleLabel {
                color: #000000;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }
            QPushButton#titleBarCloseButton {
                background-color: transparent;
                color: #000000;
                border: none;
                font-size: 16px;
            }
            QPushButton#titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0066cc;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QDialog {
                background-color: #000814;
                color: #e8e8e8;
            }
            QWidget#titleBar {
                background-color: #0d1420;
            }
            QLabel#titleLabel {
                color: #e8e8e8;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }
            QPushButton#titleBarCloseButton {
                background-color: transparent;
                color: #e8e8e8;
                border: none;
                font-size: 16px;
            }
            QPushButton#titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #a8a8a8;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #FF8000;
            }
            QPushButton {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1a2838;
                border-color: #FF8000;
            }
            QPushButton:pressed {
                background-color: #060a10;
            }
        """


class LoadPortfolioDialog(QDialog):
    """Dialog to load an existing portfolio."""

    def __init__(self, theme_manager: ThemeManager, portfolios: List[str], parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.theme_manager = theme_manager
        self.portfolios = portfolios
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = self._create_title_bar("Load Portfolio")
        layout.addWidget(title_bar)

        # Content
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        content_layout.addWidget(QLabel("Select Portfolio:"))
        self.portfolio_list = QListWidget()
        self.portfolio_list.addItems(self.portfolios)
        self.portfolio_list.itemDoubleClicked.connect(self.accept)
        content_layout.addWidget(self.portfolio_list)

        # Buttons
        button_layout = QHBoxLayout()

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        button_layout.addWidget(delete_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        load_btn = QPushButton("Load")
        load_btn.setDefault(True)
        load_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(load_btn)

        content_layout.addLayout(button_layout)

        layout.addWidget(content)

    def _create_title_bar(self, title: str) -> QWidget:
        """Create custom title bar with close button."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 0, 0)
        bar_layout.setSpacing(5)

        # Dialog title
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        bar_layout.addWidget(title_label)

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

    def _validate_and_accept(self):
        """Validate selection and accept."""
        if not self.portfolio_list.currentItem():
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Selection",
                "Please select a portfolio to load."
            )
            return
        self.accept()

    def _delete_selected(self):
        """Delete selected portfolio."""
        current_item = self.portfolio_list.currentItem()
        if not current_item:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Selection",
                "Please select a portfolio to delete."
            )
            return

        name = current_item.text()

        if name == "Default":
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Cannot Delete",
                "Cannot delete the Default portfolio."
            )
            return

        reply = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Delete Portfolio",
            f"Are you sure you want to delete '{name}'?",
            CustomMessageBox.Yes | CustomMessageBox.No,
            CustomMessageBox.No
        )

        if reply == CustomMessageBox.Yes:
            if PortfolioPersistence.delete_portfolio(name):
                row = self.portfolio_list.row(current_item)
                self.portfolio_list.takeItem(row)
                CustomMessageBox.information(
                    self.theme_manager,
                    self,
                    "Deleted",
                    f"Portfolio '{name}' deleted successfully."
                )
            else:
                CustomMessageBox.critical(
                    self.theme_manager,
                    self,
                    "Delete Error",
                    f"Failed to delete portfolio '{name}'."
                )

    def get_selected_name(self) -> Optional[str]:
        """Get selected portfolio name."""
        current_item = self.portfolio_list.currentItem()
        return current_item.text() if current_item else None

    def _apply_theme(self):
        """Apply theme styling."""
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
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QWidget#titleBar {
                background-color: #2d2d2d;
            }
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }
            QPushButton#titleBarCloseButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 16px;
            }
            QPushButton#titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
            }
            QListWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #00d4ff;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            QWidget#titleBar {
                background-color: #f5f5f5;
            }
            QLabel#titleLabel {
                color: #000000;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }
            QPushButton#titleBarCloseButton {
                background-color: transparent;
                color: #000000;
                border: none;
                font-size: 16px;
            }
            QPushButton#titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
            }
            QListWidget {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #e8e8e8;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QDialog {
                background-color: #000814;
                color: #e8e8e8;
            }
            QWidget#titleBar {
                background-color: #0d1420;
            }
            QLabel#titleLabel {
                color: #e8e8e8;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }
            QPushButton#titleBarCloseButton {
                background-color: transparent;
                color: #e8e8e8;
                border: none;
                font-size: 16px;
            }
            QPushButton#titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #a8a8a8;
                font-size: 13px;
            }
            QListWidget {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background-color: #FF8000;
                color: #000000;
            }
            QListWidget::item:hover {
                background-color: #1a2838;
            }
            QPushButton {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1a2838;
                border-color: #FF8000;
            }
            QPushButton:pressed {
                background-color: #060a10;
            }
        """
