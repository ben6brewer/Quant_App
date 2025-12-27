from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStackedLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
)
from PySide6.QtCore import Qt, QCoreApplication, QPoint
from PySide6.QtGui import QMouseEvent, QWheelEvent, QCursor

from app.core.theme_manager import ThemeManager
from app.core.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
)
from app.ui.widgets.home_screen import HomeScreen


class TransparentOverlay(QWidget):
    """
    Transparent overlay widget that passes mouse events through except for its children.
    Handles complete event forwarding to enable full interaction with module widgets below.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def _forward_event_to_module(self, event) -> None:
        """Forward event to the module widget below in the stacked layout."""
        container = self.parent()
        if not container:
            event.ignore()
            return

        layout = container.layout()
        if not isinstance(layout, QStackedLayout):
            event.ignore()
            return

        # Module is at index 0, overlay at index 1
        if layout.count() >= 1:
            module_widget = layout.widget(0)
            if module_widget:
                # Map event position to module coordinates
                # QMouseEvent uses pos(), QWheelEvent uses position()
                if isinstance(event, QWheelEvent):
                    event_pos = event.position().toPoint()
                elif hasattr(event, 'pos'):
                    event_pos = event.pos()
                else:
                    event_pos = None

                if event_pos is not None:
                    global_pos = self.mapToGlobal(event_pos)
                    module_pos = module_widget.mapFromGlobal(global_pos)

                    # Find the actual child widget at this position
                    target_widget = module_widget.childAt(module_pos)
                    if target_widget:
                        # Send event to the specific child widget
                        child_pos = target_widget.mapFromGlobal(global_pos)

                        if isinstance(event, QMouseEvent):
                            new_event = QMouseEvent(
                                event.type(),
                                child_pos,
                                global_pos,
                                event.button(),
                                event.buttons(),
                                event.modifiers()
                            )
                        elif isinstance(event, QWheelEvent):
                            new_event = QWheelEvent(
                                child_pos,
                                global_pos,
                                event.pixelDelta(),
                                event.angleDelta(),
                                event.buttons(),
                                event.modifiers(),
                                event.phase(),
                                event.inverted()
                            )
                        else:
                            event.ignore()
                            return

                        QCoreApplication.sendEvent(target_widget, new_event)
                    else:
                        # No specific child widget, send to module itself
                        if isinstance(event, QMouseEvent):
                            new_event = QMouseEvent(
                                event.type(),
                                module_pos,
                                global_pos,
                                event.button(),
                                event.buttons(),
                                event.modifiers()
                            )
                        elif isinstance(event, QWheelEvent):
                            new_event = QWheelEvent(
                                module_pos,
                                global_pos,
                                event.pixelDelta(),
                                event.angleDelta(),
                                event.buttons(),
                                event.modifiers(),
                                event.phase(),
                                event.inverted()
                            )
                        else:
                            event.ignore()
                            return

                        QCoreApplication.sendEvent(module_widget, new_event)

                    event.accept()
                else:
                    # Events without position (like leaveEvent)
                    QCoreApplication.sendEvent(module_widget, event)
                    event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        """Pass mouse press events through unless clicking on home button."""
        if self.childAt(event.pos()):
            super().mousePressEvent(event)
        else:
            self._forward_event_to_module(event)

    def mouseReleaseEvent(self, event):
        """Pass mouse release events through unless on home button."""
        if self.childAt(event.pos()):
            super().mouseReleaseEvent(event)
        else:
            self._forward_event_to_module(event)

    def mouseMoveEvent(self, event):
        """Pass mouse move events through unless on home button."""
        if self.childAt(event.pos()):
            super().mouseMoveEvent(event)
        else:
            self._forward_event_to_module(event)

    def mouseDoubleClickEvent(self, event):
        """Pass double-click events through unless on home button."""
        if self.childAt(event.pos()):
            super().mouseDoubleClickEvent(event)
        else:
            self._forward_event_to_module(event)

    def wheelEvent(self, event):
        """Pass wheel events through unless on home button."""
        # QWheelEvent uses position() which returns QPointF, convert to QPoint
        pos = event.position().toPoint()
        if self.childAt(pos):
            super().wheelEvent(event)
        else:
            self._forward_event_to_module(event)

    def enterEvent(self, event):
        """Pass enter events through unless entering home button."""
        pos = self.mapFromGlobal(QCursor.pos())
        if self.childAt(pos):
            super().enterEvent(event)
        else:
            self._forward_event_to_module(event)

    def leaveEvent(self, event):
        """Pass leave events through to widgets below."""
        self._forward_event_to_module(event)

    def contextMenuEvent(self, event):
        """Pass context menu events through unless on home button."""
        if self.childAt(event.pos()):
            super().contextMenuEvent(event)
        else:
            self._forward_event_to_module(event)


class HubWindow(QMainWindow):
    """
    Main hub window with home screen and module navigation.
    Bloomberg terminal-inspired design with tile-based navigation.
    """

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Remove native title bar
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Theme manager
        self.theme_manager = theme_manager
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

        # Module storage
        self.modules = {}
        self.module_containers = {}

        # For window dragging
        self._drag_pos = QPoint()

        # Setup UI
        self._setup_ui()

        # Apply initial theme
        self._apply_theme()

    def _setup_ui(self) -> None:
        """Setup the main UI with custom title bar."""
        # Main container
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar
        self.title_bar = self._create_title_bar()
        main_layout.addWidget(self.title_bar)

        # Navigation area
        self._setup_navigation()
        main_layout.addWidget(self.main_stack)

        self.setCentralWidget(container)

    def _create_title_bar(self) -> QWidget:
        """Create custom title bar with window controls."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(5)

        # App title
        self.title_label = QLabel(f"{APP_NAME} v{APP_VERSION}")
        self.title_label.setObjectName("titleLabel")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Minimize button
        min_btn = QPushButton("−")
        min_btn.setObjectName("titleBarButton")
        min_btn.setFixedSize(40, 32)
        min_btn.setCursor(Qt.PointingHandCursor)
        min_btn.clicked.connect(self.showMinimized)
        layout.addWidget(min_btn)

        # Maximize/Restore button
        self.max_btn = QPushButton("□")
        self.max_btn.setObjectName("titleBarButton")
        self.max_btn.setFixedSize(40, 32)
        self.max_btn.setCursor(Qt.PointingHandCursor)
        self.max_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.max_btn)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        # Enable dragging from title bar
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _toggle_maximize(self) -> None:
        """Toggle between maximized and normal state."""
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("□")
        else:
            self.showMaximized()
            self.max_btn.setText("❐")

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press on title bar for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move on title bar for dragging."""
        if event.buttons() == Qt.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _setup_navigation(self) -> None:
        """Setup dual-mode navigation (home screen + module views)."""
        # Main stack: home screen + module containers
        self.main_stack = QStackedWidget()

        # Home screen (index 0)
        self.home_screen = HomeScreen(self.theme_manager)
        self.main_stack.addWidget(self.home_screen)

        # Connect home screen signals
        self.home_screen.module_selected.connect(self.open_module)
        self.home_screen.settings_requested.connect(self._open_settings)

    def add_module(self, module_id: str, widget: QWidget) -> None:
        """Add a module widget wrapped in container with home button."""
        # Create container with home button overlay
        container = self._create_module_container(widget)

        # Store references
        self.modules[module_id] = widget
        self.module_containers[module_id] = container

        # Add to stack
        self.main_stack.addWidget(container)

    def _create_module_container(self, module_widget: QWidget) -> QWidget:
        """Create container with home button overlay for module."""
        container = QWidget()
        layout = QStackedLayout(container)
        layout.setStackingMode(QStackedLayout.StackAll)
        layout.setContentsMargins(0, 0, 0, 0)

        # Layer 0: Module widget (full screen)
        layout.addWidget(module_widget)

        # Layer 1: Transparent overlay with home button (top-left)
        overlay = self._create_home_button_overlay()
        layout.addWidget(overlay)

        # CRITICAL FIX 3: Ensure overlay is on top
        overlay.raise_()

        return container

    def _create_home_button_overlay(self) -> QWidget:
        """Create transparent overlay with home button in top-left corner."""
        overlay = TransparentOverlay()

        # CRITICAL FIX 1: Force overlay to expand and fill container
        overlay.setSizePolicy(
            QSizePolicy.Expanding,  # Horizontal
            QSizePolicy.Expanding   # Vertical
        )

        # Set minimum size to ensure it's never collapsed
        overlay.setMinimumSize(100, 40)

        # Transparent background - overlay is invisible but passes events through
        # Only make the overlay transparent, not its children (home button)
        overlay.setStyleSheet("TransparentOverlay { background: transparent; }")

        # Ensure overlay doesn't interfere with focus
        overlay.setFocusPolicy(Qt.NoFocus)

        # CRITICAL FIX 2: Don't align the layout, align the widget within it
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(10, 10, 0, 0)
        # REMOVED: layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # This caused shrinking!

        # Home button
        home_btn = QPushButton("🏠 Home")
        home_btn.setObjectName("homeButton")
        home_btn.setFixedSize(100, 40)
        home_btn.setCursor(Qt.PointingHandCursor)
        home_btn.clicked.connect(self.show_home)

        # Add button with alignment to position it top-left within the expanding layout
        layout.addWidget(home_btn, alignment=Qt.AlignTop | Qt.AlignLeft)
        layout.addStretch(1)

        return overlay

    def open_module(self, module_id: str) -> None:
        """Open a module in full screen."""
        if module_id not in self.module_containers:
            print(f"Warning: Module '{module_id}' not found")
            return

        container = self.module_containers[module_id]
        self.main_stack.setCurrentWidget(container)

    def show_home(self) -> None:
        """Return to home screen."""
        self.main_stack.setCurrentWidget(self.home_screen)
        self.home_screen.refresh()  # Reload favorites

    def show_initial_screen(self) -> None:
        """Show home screen on startup."""
        self.show_home()

    def _open_settings(self) -> None:
        """Open Settings module from home screen button."""
        self.open_module("settings")

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change signal."""
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply the current theme to the window."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Get complete dark theme stylesheet."""
        return (
            self.theme_manager.get_dark_content_style() +
            self.theme_manager.get_dark_home_button_style() +
            self._get_dark_title_bar_style()
        )

    def _get_light_stylesheet(self) -> str:
        """Get complete light theme stylesheet."""
        return (
            self.theme_manager.get_light_content_style() +
            self.theme_manager.get_light_home_button_style() +
            self._get_light_title_bar_style()
        )

    def _get_bloomberg_stylesheet(self) -> str:
        """Get complete Bloomberg theme stylesheet."""
        return (
            self.theme_manager.get_bloomberg_content_style() +
            self.theme_manager.get_bloomberg_home_button_style() +
            self._get_bloomberg_title_bar_style()
        )

    def _get_dark_title_bar_style(self) -> str:
        """Get dark theme title bar stylesheet."""
        return """
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
            #titleBarButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            #titleBarButton:hover {
                background-color: #3d3d3d;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #ffffff;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
            }
        """

    def _get_light_title_bar_style(self) -> str:
        """Get light theme title bar stylesheet."""
        return """
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
            #titleBarButton {
                background-color: transparent;
                color: #000000;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            #titleBarButton:hover {
                background-color: #e0e0e0;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #000000;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
        """

    def _get_bloomberg_title_bar_style(self) -> str:
        """Get Bloomberg theme title bar stylesheet."""
        return """
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
            #titleBarButton {
                background-color: transparent;
                color: #e8e8e8;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            #titleBarButton:hover {
                background-color: #162030;
            }
            #titleBarCloseButton {
                background-color: transparent;
                color: #e8e8e8;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
        """
