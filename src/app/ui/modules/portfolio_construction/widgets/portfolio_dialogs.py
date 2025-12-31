"""Portfolio Dialogs - New/Load Portfolio Dialogs"""

from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QWidget, QComboBox, QRadioButton,
    QCheckBox, QButtonGroup
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


class RenamePortfolioDialog(QDialog):
    """Dialog to rename a portfolio."""

    def __init__(self, theme_manager: ThemeManager, current_name: str, existing_names: List[str], parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.theme_manager = theme_manager
        self.current_name = current_name
        self.existing_names = [n for n in existing_names if n != current_name]  # Exclude current name
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = self._create_title_bar("Rename Portfolio")
        layout.addWidget(title_bar)

        # Content
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        content_layout.addWidget(QLabel("New Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.current_name)
        self.name_edit.selectAll()
        self.name_edit.returnPressed.connect(self._validate_and_accept)
        content_layout.addWidget(self.name_edit)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(ok_btn)

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

        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        bar_layout.addWidget(title_label)

        bar_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bar_layout.addWidget(close_btn)

        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
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
        return """
            QDialog { background-color: #1e1e1e; color: #ffffff; }
            QWidget#titleBar { background-color: #2d2d2d; }
            QLabel#titleLabel { color: #ffffff; font-size: 14px; font-weight: bold; background-color: transparent; }
            QPushButton#titleBarCloseButton { background-color: transparent; color: #ffffff; border: none; font-size: 16px; }
            QPushButton#titleBarCloseButton:hover { background-color: #d32f2f; color: #ffffff; }
            QLabel { color: #cccccc; font-size: 13px; }
            QLineEdit { background-color: #2d2d2d; color: #ffffff; border: 1px solid #3d3d3d; border-radius: 3px; padding: 5px; font-size: 13px; }
            QLineEdit:focus { border-color: #00d4ff; }
            QPushButton { background-color: #2d2d2d; color: #ffffff; border: 1px solid #3d3d3d; border-radius: 3px; padding: 6px 12px; font-size: 13px; }
            QPushButton:hover { background-color: #3d3d3d; border-color: #00d4ff; }
            QPushButton:pressed { background-color: #1a1a1a; }
        """

    def _get_light_stylesheet(self) -> str:
        return """
            QDialog { background-color: #ffffff; color: #000000; }
            QWidget#titleBar { background-color: #f5f5f5; }
            QLabel#titleLabel { color: #000000; font-size: 14px; font-weight: bold; background-color: transparent; }
            QPushButton#titleBarCloseButton { background-color: transparent; color: #000000; border: none; font-size: 16px; }
            QPushButton#titleBarCloseButton:hover { background-color: #d32f2f; color: #ffffff; }
            QLabel { color: #333333; font-size: 13px; }
            QLineEdit { background-color: #f5f5f5; color: #000000; border: 1px solid #cccccc; border-radius: 3px; padding: 5px; font-size: 13px; }
            QLineEdit:focus { border-color: #0066cc; }
            QPushButton { background-color: #f5f5f5; color: #000000; border: 1px solid #cccccc; border-radius: 3px; padding: 6px 12px; font-size: 13px; }
            QPushButton:hover { background-color: #e8e8e8; border-color: #0066cc; }
            QPushButton:pressed { background-color: #d0d0d0; }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        return """
            QDialog { background-color: #000814; color: #e8e8e8; }
            QWidget#titleBar { background-color: #0d1420; }
            QLabel#titleLabel { color: #e8e8e8; font-size: 14px; font-weight: bold; background-color: transparent; }
            QPushButton#titleBarCloseButton { background-color: transparent; color: #e8e8e8; border: none; font-size: 16px; }
            QPushButton#titleBarCloseButton:hover { background-color: #d32f2f; color: #ffffff; }
            QLabel { color: #a8a8a8; font-size: 13px; }
            QLineEdit { background-color: #0d1420; color: #e8e8e8; border: 1px solid #1a2838; border-radius: 3px; padding: 5px; font-size: 13px; }
            QLineEdit:focus { border-color: #FF8000; }
            QPushButton { background-color: #0d1420; color: #e8e8e8; border: 1px solid #1a2838; border-radius: 3px; padding: 6px 12px; font-size: 13px; }
            QPushButton:hover { background-color: #1a2838; border-color: #FF8000; }
            QPushButton:pressed { background-color: #060a10; }
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


class ImportPortfolioDialog(QDialog):
    """Dialog to import transactions from another portfolio."""

    def __init__(self, theme_manager: ThemeManager, available_portfolios: List[str], parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.theme_manager = theme_manager
        self.available_portfolios = available_portfolios
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = self._create_title_bar("Import Transactions")
        layout.addWidget(title_bar)

        # Content
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        # Source portfolio dropdown
        content_layout.addWidget(QLabel("Source Portfolio:"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("Select a portfolio...")
        self.source_combo.addItems(self.available_portfolios)
        content_layout.addWidget(self.source_combo)

        content_layout.addSpacing(10)

        # Import mode radio buttons
        mode_label = QLabel("Import Mode:")
        content_layout.addWidget(mode_label)

        self.mode_group = QButtonGroup(self)

        # Full history option
        self.full_history_radio = QRadioButton("Import with transaction dates")
        self.full_history_radio.setChecked(True)
        self.full_history_radio.toggled.connect(self._on_mode_changed)
        self.mode_group.addButton(self.full_history_radio)
        content_layout.addWidget(self.full_history_radio)

        full_history_desc = QLabel("Keep full history with original dates")
        full_history_desc.setObjectName("descriptionLabel")
        full_history_desc.setContentsMargins(20, 0, 0, 0)
        content_layout.addWidget(full_history_desc)

        content_layout.addSpacing(5)

        # Flat import option
        self.flat_radio = QRadioButton("Import flat (all dates set to today)")
        self.flat_radio.toggled.connect(self._on_mode_changed)
        self.mode_group.addButton(self.flat_radio)
        content_layout.addWidget(self.flat_radio)

        flat_desc = QLabel("Consolidate to net positions with average cost basis")
        flat_desc.setObjectName("descriptionLabel")
        flat_desc.setContentsMargins(20, 0, 0, 0)
        content_layout.addWidget(flat_desc)

        content_layout.addSpacing(15)

        # Options section
        options_label = QLabel("Options:")
        content_layout.addWidget(options_label)

        self.include_fees_checkbox = QCheckBox("Include fees")
        self.include_fees_checkbox.setChecked(True)
        content_layout.addWidget(self.include_fees_checkbox)

        self.skip_zero_checkbox = QCheckBox("Skip net zero positions")
        self.skip_zero_checkbox.setChecked(False)
        self.skip_zero_checkbox.setEnabled(False)  # Disabled by default (full history mode)
        content_layout.addWidget(self.skip_zero_checkbox)

        content_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        import_btn = QPushButton("Import")
        import_btn.setDefault(True)
        import_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(import_btn)

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

        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        bar_layout.addWidget(title_label)

        bar_layout.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bar_layout.addWidget(close_btn)

        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _on_mode_changed(self):
        """Handle import mode radio button change."""
        is_flat_mode = self.flat_radio.isChecked()
        self.skip_zero_checkbox.setEnabled(is_flat_mode)
        if not is_flat_mode:
            self.skip_zero_checkbox.setChecked(False)

    def _validate_and_accept(self):
        """Validate selection and accept."""
        if self.source_combo.currentIndex() == 0:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Selection",
                "Please select a source portfolio to import from."
            )
            return
        self.accept()

    def get_import_config(self) -> Optional[Dict[str, Any]]:
        """
        Get import configuration.

        Returns:
            Dict with import settings or None if cancelled.
        """
        if self.result() != QDialog.Accepted:
            return None

        return {
            "source_portfolio": self.source_combo.currentText(),
            "import_mode": "flat" if self.flat_radio.isChecked() else "full_history",
            "include_fees": self.include_fees_checkbox.isChecked(),
            "skip_zero_positions": self.skip_zero_checkbox.isChecked()
        }

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
            QLabel#descriptionLabel {
                color: #888888;
                font-size: 12px;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #00d4ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #ffffff;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
                font-size: 13px;
                padding: 4px;
            }
            QRadioButton {
                color: #ffffff;
                font-size: 13px;
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
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #3d3d3d;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                border-color: #00d4ff;
                background-color: #00d4ff;
            }
            QCheckBox::indicator:hover {
                border-color: #00d4ff;
            }
            QCheckBox:disabled {
                color: #666666;
            }
            QCheckBox::indicator:disabled {
                border-color: #2d2d2d;
                background-color: #1a1a1a;
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
            QLabel#descriptionLabel {
                color: #666666;
                font-size: 12px;
            }
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #0066cc;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #000000;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #f5f5f5;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
                font-size: 13px;
                padding: 4px;
            }
            QRadioButton {
                color: #000000;
                font-size: 13px;
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
            QCheckBox {
                color: #000000;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #cccccc;
                background-color: #f5f5f5;
            }
            QCheckBox::indicator:checked {
                border-color: #0066cc;
                background-color: #0066cc;
            }
            QCheckBox::indicator:hover {
                border-color: #0066cc;
            }
            QCheckBox:disabled {
                color: #999999;
            }
            QCheckBox::indicator:disabled {
                border-color: #cccccc;
                background-color: #e0e0e0;
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
            QLabel#descriptionLabel {
                color: #666666;
                font-size: 12px;
            }
            QComboBox {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #FF8000;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #e8e8e8;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1420;
                color: #e8e8e8;
                selection-background-color: #FF8000;
                selection-color: #000000;
                font-size: 13px;
                padding: 4px;
            }
            QRadioButton {
                color: #e8e8e8;
                font-size: 13px;
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
            QCheckBox {
                color: #e8e8e8;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #1a2838;
                background-color: #0d1420;
            }
            QCheckBox::indicator:checked {
                border-color: #FF8000;
                background-color: #FF8000;
            }
            QCheckBox::indicator:hover {
                border-color: #FF8000;
            }
            QCheckBox:disabled {
                color: #555555;
            }
            QCheckBox::indicator:disabled {
                border-color: #1a2838;
                background-color: #060a10;
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
