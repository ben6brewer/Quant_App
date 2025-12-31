"""Themed Dialog Base Class - Frameless dialog with custom title bar and theming."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent

from app.core.theme_manager import ThemeManager
from app.services.theme_stylesheet_service import ThemeStylesheetService


class ThemedDialog(QDialog):
    """
    Base class for themed dialogs with custom title bar.

    Provides:
    - Frameless window with custom title bar
    - Drag-to-move functionality
    - Theme-aware styling via ThemeStylesheetService
    - Consistent close button behavior

    Subclasses should:
    1. Call super().__init__() with theme_manager and title
    2. Override _setup_content() to add dialog-specific content
    3. Optionally override _apply_theme() to add custom styling
    """

    def __init__(
        self,
        theme_manager: ThemeManager,
        title: str,
        parent=None,
        min_width: int = 400,
        min_height: int = None
    ):
        """
        Initialize themed dialog.

        Args:
            theme_manager: Application theme manager
            title: Dialog title shown in title bar
            parent: Parent widget
            min_width: Minimum dialog width (default 400)
            min_height: Minimum dialog height (optional)
        """
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._dialog_title = title
        self._drag_pos = QPoint()

        # Window setup
        self.setModal(True)
        self.setMinimumWidth(min_width)
        if min_height:
            self.setMinimumHeight(min_height)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        # Build UI
        self._build_layout()
        self._apply_theme()

    def _build_layout(self):
        """Build the dialog layout with title bar and content area."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = self._create_title_bar(self._dialog_title)
        layout.addWidget(title_bar)

        # Content area
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        # Let subclass populate content
        self._setup_content(content_layout)

        layout.addWidget(content)

    def _create_title_bar(self, title: str) -> QWidget:
        """
        Create custom title bar with close button.

        Args:
            title: Title text to display

        Returns:
            QWidget containing the title bar
        """
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 0, 0)
        bar_layout.setSpacing(5)

        # Title label
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

    def _setup_content(self, layout: QVBoxLayout):
        """
        Setup dialog content. Override in subclass.

        Args:
            layout: The content area layout to populate
        """
        pass

    def _apply_theme(self):
        """Apply theme styling using ThemeStylesheetService."""
        theme = self.theme_manager.current_theme
        stylesheet = ThemeStylesheetService.get_dialog_stylesheet(theme)
        self.setStyleSheet(stylesheet)
