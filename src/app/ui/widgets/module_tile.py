from __future__ import annotations

from typing import Optional
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap, QMouseEvent

from app.core.theme_manager import ThemeManager
from app.services.favorites_service import FavoritesService
from app.utils.screenshot_manager import ScreenshotManager


class ModuleTile(QFrame):
    """
    Individual tile widget for a module with screenshot preview and favorite star.
    """

    clicked = Signal(str)  # Emits module_id when tile is clicked
    favorite_toggled = Signal(str, bool)  # Emits (module_id, is_favorite)

    def __init__(
        self,
        module_id: str,
        label: str,
        emoji: str,
        section: str,
        theme_manager: ThemeManager,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.module_id = module_id
        self.label = label
        self.emoji = emoji
        self.section = section
        self.theme_manager = theme_manager

        self._is_favorite = FavoritesService.is_favorite(module_id)

        self._setup_ui()
        self._apply_theme()

        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self) -> None:
        """Setup the tile UI."""
        # Set fixed size
        self.setFixedSize(453, 285)  # Accommodate 453×255 screenshot (16:9 ratio) + label
        self.setCursor(Qt.PointingHandCursor)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top row: Screenshot area + star button
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # Screenshot
        self.screenshot_label = QLabel()
        self.screenshot_label.setFixedSize(453, 255)  # 16:9 aspect ratio
        self.screenshot_label.setScaledContents(True)
        self._load_screenshot()

        # Star button (positioned absolutely in top-right)
        self.star_button = QPushButton()
        self.star_button.setObjectName("starButton")
        self.star_button.setFixedSize(32, 32)
        self.star_button.setCursor(Qt.PointingHandCursor)
        self.star_button.clicked.connect(self._on_star_clicked)
        self._update_star_icon()

        # Add to top layout
        top_layout.addWidget(self.screenshot_label)
        top_layout.addWidget(self.star_button, alignment=Qt.AlignTop | Qt.AlignRight)

        layout.addWidget(top_widget)

        # Label
        self.label_widget = QLabel(self.label)  # Text only, no emoji
        self.label_widget.setObjectName("tileLabel")
        self.label_widget.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label_widget)

    def _load_screenshot(self) -> None:
        """Load screenshot from ScreenshotManager."""
        pixmap = ScreenshotManager.load_or_generate(
            self.module_id,
            self.label,
            self.emoji,
            self.section
        )
        self.screenshot_label.setPixmap(pixmap)

    def _update_star_icon(self) -> None:
        """Update star button icon based on favorite status."""
        if self._is_favorite:
            self.star_button.setText("⭐")
        else:
            self.star_button.setText("☆")

    def _on_star_clicked(self) -> None:
        """Handle star button click."""
        # Stop event propagation to prevent tile click
        self._is_favorite = FavoritesService.toggle_favorite(self.module_id)
        self._update_star_icon()
        self.favorite_toggled.emit(self.module_id, self._is_favorite)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press on tile."""
        # Check if click was on star button
        if self.star_button.geometry().contains(event.pos()):
            # Let star button handle it
            super().mousePressEvent(event)
            return

        # Emit clicked signal for tile
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.module_id)

        super().mousePressEvent(event)

    def set_favorite(self, is_favorite: bool) -> None:
        """Update favorite status (external update)."""
        self._is_favorite = is_favorite
        self._update_star_icon()

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "dark":
            self.setStyleSheet("""
                ModuleTile {
                    background-color: #2d2d2d;
                    border: 2px solid #3d3d3d;
                    border-radius: 8px;
                }
                ModuleTile:hover {
                    border: 2px solid #00d4ff;
                }
                #tileLabel {
                    color: #ffffff;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 8px 0px;
                }
                #starButton {
                    background-color: transparent;
                    border: none;
                    font-size: 20px;
                    padding: 0px;
                }
                #starButton:hover {
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 16px;
                }
            """)
        elif theme == "bloomberg":
            self.setStyleSheet(self._get_bloomberg_stylesheet())
        else:  # light theme
            self.setStyleSheet("""
                ModuleTile {
                    background-color: #ffffff;
                    border: 2px solid #d0d0d0;
                    border-radius: 8px;
                }
                ModuleTile:hover {
                    border: 2px solid #0066cc;
                }
                #tileLabel {
                    color: #000000;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 8px 0px;
                }
                #starButton {
                    background-color: transparent;
                    border: none;
                    font-size: 20px;
                    padding: 0px;
                }
                #starButton:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                    border-radius: 16px;
                }
            """)

    def _get_bloomberg_stylesheet(self) -> str:
        """Get Bloomberg theme stylesheet."""
        return """
            ModuleTile {
                background-color: #0a1018;
                border: 1px solid #1a2332;
                border-radius: 4px;
            }
            ModuleTile:hover {
                border: 2px solid #FF8000;
            }
            #tileLabel {
                color: #e8e8e8;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 0px;
            }
            #starButton {
                background-color: transparent;
                border: none;
                font-size: 20px;
                padding: 0px;
            }
            #starButton:hover {
                background-color: rgba(255, 128, 0, 0.2);
                border-radius: 16px;
            }
        """
