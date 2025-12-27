from __future__ import annotations

from pathlib import Path
from typing import Optional
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QRect


class ScreenshotManager:
    """
    Manages module screenshots for tile display.
    Generates placeholder images if screenshots don't exist.
    """

    # Project assets directory (not user directory)
    _PROJECT_ROOT = Path(__file__).parent.parent
    _SCREENSHOT_DIR = _PROJECT_ROOT / "assets" / "screenshots"

    @staticmethod
    def get_screenshot_path(module_id: str) -> Path:
        """Get the path to a module's screenshot."""
        return ScreenshotManager._SCREENSHOT_DIR / f"{module_id}.png"

    @staticmethod
    def has_screenshot(module_id: str) -> bool:
        """Check if a screenshot exists for the module."""
        return ScreenshotManager.get_screenshot_path(module_id).exists()

    @staticmethod
    def get_default_screenshot() -> QPixmap:
        """Get a generic default screenshot placeholder."""
        # Try to load coming_soon.png from assets
        coming_soon_path = ScreenshotManager._SCREENSHOT_DIR / "coming_soon.png"
        if coming_soon_path.exists():
            return QPixmap(str(coming_soon_path))

        # Fallback: generate simple placeholder if file missing
        pixmap = QPixmap(264, 264)
        pixmap.fill(QColor("#2d2d2d"))

        painter = QPainter(pixmap)
        painter.setPen(QColor("#cccccc"))
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "Coming Soon")
        painter.end()

        return pixmap

    @staticmethod
    def generate_placeholder(module_id: str, label: str, emoji: str, section: str = "Settings") -> QPixmap:
        """
        Generate a placeholder image (delegates to default).

        Args:
            module_id: The module's unique ID
            label: Display label (unused, kept for compatibility)
            emoji: Emoji icon (unused, kept for compatibility)
            section: Section name (unused, kept for compatibility)

        Returns:
            QPixmap with generated placeholder
        """
        return ScreenshotManager.get_default_screenshot()

    @staticmethod
    def load_or_generate(module_id: str, label: str, emoji: str, section: str = "Settings") -> QPixmap:
        """
        Load screenshot from project assets or use coming_soon placeholder.

        Args:
            module_id: The module's unique ID
            label: Display label (unused, kept for compatibility)
            emoji: Emoji icon (unused, kept for compatibility)
            section: Section name (unused, kept for compatibility)

        Returns:
            QPixmap with screenshot or placeholder
        """
        if ScreenshotManager.has_screenshot(module_id):
            # Load module-specific screenshot
            path = ScreenshotManager.get_screenshot_path(module_id)
            pixmap = QPixmap(str(path))

            # Ensure correct size (264×264)
            if pixmap.width() != 264 or pixmap.height() != 264:
                pixmap = pixmap.scaled(264, 264, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

            return pixmap
        else:
            # Use coming_soon placeholder
            return ScreenshotManager.get_default_screenshot()

    @staticmethod
    def save_screenshot(module_id: str, pixmap: QPixmap) -> bool:
        """
        Save a screenshot to disk (for future use when capturing real screenshots).

        Args:
            module_id: The module's unique ID
            pixmap: The screenshot image

        Returns:
            True if saved successfully, False otherwise
        """
        # Ensure directory exists
        ScreenshotManager._SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Save pixmap
        path = ScreenshotManager.get_screenshot_path(module_id)
        return pixmap.save(str(path), "PNG")
