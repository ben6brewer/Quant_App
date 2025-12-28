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
    QApplication,
)
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QMouseEvent, QRegion

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
    Transparent overlay widget that only "exists" where the Home button is.
    Uses a mask to make the overlay transparent everywhere except the Home button area.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Ensure overlay fills container
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        
        # Transparent background
        self.setStyleSheet("TransparentOverlay { background: transparent; }")
        
        # We'll update the mask when the home button is added
        self._home_button = None
    
    def set_home_button(self, button):
        """Set the home button and update mask."""
        self._home_button = button
        # Update mask whenever the button moves/resizes
        button.installEventFilter(self)
        self._update_mask()
    
    def _update_mask(self):
        """Update the mask to only include the home button area."""
        if not self._home_button:
            return
        
        # Create a region that only includes the home button's geometry
        button_rect = self._home_button.geometry()
        region = QRegion(button_rect)
        self.setMask(region)
    
    def eventFilter(self, obj, event):
        """Update mask when home button is moved or resized."""
        if obj == self._home_button:
            event_type = event.type()
            # 13 = Move, 14 = Resize
            if event_type in (13, 14):
                self._update_mask()
        return super().eventFilter(obj, event)
    
    def resizeEvent(self, event):
        """Update mask when overlay is resized."""
        super().resizeEvent(event)
        self._update_mask()


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

        # For tracking window geometry before maximize
        self._normal_geometry = None
        self._is_maximized = False  # Manual state tracking for frameless windows

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
        title_bar.mouseDoubleClickEvent = self._title_bar_mouse_double_click

        return title_bar

    def _toggle_maximize(self) -> None:
        """Toggle between maximized and normal state."""
        if self._is_maximized:
            # Restore to normal size
            if self._normal_geometry:
                # Restore saved geometry
                self.setGeometry(self._normal_geometry)
            else:
                # No saved geometry (started maximized), use default size centered on screen
                screen = QApplication.primaryScreen().availableGeometry()
                width = DEFAULT_WINDOW_WIDTH
                height = DEFAULT_WINDOW_HEIGHT
                x = screen.x() + (screen.width() - width) // 2
                y = screen.y() + (screen.height() - height) // 2
                self.setGeometry(x, y, width, height)
            self._is_maximized = False
            self.max_btn.setText("□")
        else:
            # Save current geometry before maximizing
            self._normal_geometry = self.geometry()
            # Manually maximize by setting geometry to screen bounds
            # DO NOT use showMaximized() - it causes Windows to lock geometry on frameless windows
            screen = QApplication.primaryScreen().availableGeometry()
            self.setGeometry(screen)
            self._is_maximized = True
            self.max_btn.setText("❐")

    def showEvent(self, event):
        """Handle show event to update maximize button state."""
        super().showEvent(event)
        # Update button state based on current maximized flag
        if self._is_maximized:
            self.max_btn.setText("❐")
        else:
            self.max_btn.setText("□")

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press on title bar for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move on title bar for dragging."""
        if event.buttons() == Qt.LeftButton:
            if self._is_maximized:
                # Auto-restore when dragging from maximized state
                # Calculate where to position the window so cursor stays on title bar
                mouse_global = event.globalPosition().toPoint()

                # Restore to normal size
                if self._normal_geometry:
                    width = self._normal_geometry.width()
                    height = self._normal_geometry.height()
                else:
                    width = DEFAULT_WINDOW_WIDTH
                    height = DEFAULT_WINDOW_HEIGHT

                # Position window so cursor is at proportional position on title bar
                # Cursor should be at same percentage across title bar width
                title_bar_click_ratio = self._drag_pos.x() / self.width()
                new_x = mouse_global.x() - int(width * title_bar_click_ratio)
                new_y = mouse_global.y() - self._drag_pos.y()

                # Set new geometry
                self.setGeometry(new_x, new_y, width, height)
                self._is_maximized = False
                self.max_btn.setText("□")

                # Update drag position for continued dragging
                self._drag_pos = QPoint(int(width * title_bar_click_ratio), self._drag_pos.y())
            else:
                # Normal dragging when not maximized
                self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _title_bar_mouse_double_click(self, event: QMouseEvent) -> None:
        """Handle double-click on title bar to toggle maximize."""
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()
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

        # Ensure overlay is on top
        overlay.raise_()

        return container

    def _create_home_button_overlay(self) -> QWidget:
        """Create transparent overlay with home button in top-left corner."""
        overlay = TransparentOverlay()

        # Force overlay to expand and fill container
        overlay.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        # Set minimum size to ensure it's never collapsed
        overlay.setMinimumSize(100, 40)

        # Ensure overlay doesn't interfere with focus
        overlay.setFocusPolicy(Qt.NoFocus)

        # Layout for positioning home button
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(10, 10, 0, 0)

        # Home button
        home_btn = self.theme_manager.create_styled_button("Home")
        home_btn.setFixedSize(100, 40)
        home_btn.setCursor(Qt.PointingHandCursor)
        home_btn.clicked.connect(self.show_home)

        # Add button with alignment to position it top-left within the expanding layout
        layout.addWidget(home_btn, alignment=Qt.AlignTop | Qt.AlignLeft)
        layout.addStretch(1)
        
        # Set up the mask so overlay only exists where Home button is
        overlay.set_home_button(home_btn)

        return overlay

    def open_module(self, module_id: str) -> None:
        """Open a module in full screen."""
        if module_id not in self.module_containers:
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

    def maximize_on_startup(self) -> None:
        """
        Maximize window on startup without using showMaximized().

        Critical for frameless windows on Windows: showMaximized() causes Qt/Windows
        to set internal geometry constraints that prevent manual resizing later.
        Instead, we manually set geometry to fill the screen.
        """
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen)
        self._is_maximized = True
        self.max_btn.setText("❐")

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
            self._get_dark_title_bar_style()
        )

    def _get_light_stylesheet(self) -> str:
        """Get complete light theme stylesheet."""
        return (
            self.theme_manager.get_light_content_style() +
            self._get_light_title_bar_style()
        )

    def _get_bloomberg_stylesheet(self) -> str:
        """Get complete Bloomberg theme stylesheet."""
        return (
            self.theme_manager.get_bloomberg_content_style() +
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