"""Loading Overlay Widget - Semi-transparent overlay with loading indicator."""

from typing import Optional

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import QWidget

from app.services.theme_stylesheet_service import ThemeStylesheetService


class LoadingOverlay(QWidget):
    """
    Semi-transparent overlay with 'Loading Portfolio...' text.

    Covers parent widget during long operations. Theme-aware with
    a pulsing opacity animation for visual feedback.
    """

    def __init__(self, parent: QWidget, theme_manager, message: str = "Loading Portfolio..."):
        """
        Initialize the loading overlay.

        Args:
            parent: Parent widget to overlay
            theme_manager: ThemeManager instance for theme awareness
            message: Loading message to display
        """
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._message = message
        self._opacity = 1.0
        self._dot_count = 0

        # Setup animation for pulsing effect
        self._pulse_animation: Optional[QPropertyAnimation] = None
        self._dot_timer: Optional[QTimer] = None

        # Connect to theme changes
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

        # Setup widget - ensure it stacks above other widgets including QGraphicsView
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)

        # Cover parent completely
        self._update_geometry()

        # Start animations
        self._setup_animations()

    def _get_opacity(self) -> float:
        """Get current opacity for animation."""
        return self._opacity

    def _set_opacity(self, value: float) -> None:
        """Set opacity and trigger repaint."""
        self._opacity = value
        self.update()

    # Property for QPropertyAnimation
    opacity = Property(float, _get_opacity, _set_opacity)

    def _setup_animations(self) -> None:
        """Setup pulsing opacity animation."""
        # Pulse animation
        self._pulse_animation = QPropertyAnimation(self, b"opacity")
        self._pulse_animation.setDuration(800)
        self._pulse_animation.setStartValue(0.7)
        self._pulse_animation.setEndValue(1.0)
        self._pulse_animation.setEasingCurve(QEasingCurve.InOutSine)
        self._pulse_animation.setLoopCount(-1)  # Infinite loop
        self._pulse_animation.start()

        # Dot animation timer
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._update_dots)
        self._dot_timer.start(400)

    def _update_dots(self) -> None:
        """Update loading dots animation."""
        self._dot_count = (self._dot_count + 1) % 4
        self.update()

    def _update_geometry(self) -> None:
        """Update overlay to cover parent widget."""
        if self.parent():
            self.setGeometry(self.parent().rect())

    def _on_theme_changed(self) -> None:
        """Handle theme changes."""
        self.update()

    def resizeEvent(self, event) -> None:
        """Handle parent resize."""
        super().resizeEvent(event)
        self._update_geometry()

    def showEvent(self, event) -> None:
        """Handle show event."""
        super().showEvent(event)
        self._update_geometry()
        self.raise_()  # Bring to front
        self.activateWindow()  # Ensure we have focus
        # Force all siblings to stack under us
        if self.parent():
            for sibling in self.parent().children():
                if sibling is not self and hasattr(sibling, 'stackUnder'):
                    sibling.stackUnder(self)

    def paintEvent(self, event) -> None:
        """Paint the overlay with loading message."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Get theme colors
        theme = self._theme_manager.current_theme
        colors = ThemeStylesheetService.get_colors(theme)

        # Draw semi-transparent background
        bg_color = QColor(colors["bg"])
        bg_color.setAlphaF(0.85)
        painter.fillRect(self.rect(), bg_color)

        # Calculate text position (centered)
        rect = self.rect()

        # Build message with animated dots
        dots = "." * self._dot_count
        display_message = f"{self._message}{dots}"

        # Setup font
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)

        # Draw text with pulsing opacity
        text_color = QColor(colors["text"])
        text_color.setAlphaF(self._opacity)
        painter.setPen(text_color)

        painter.drawText(rect, Qt.AlignCenter, display_message)

        # Draw subtle accent line below text
        accent_color = QColor(colors["accent"])
        accent_color.setAlphaF(self._opacity * 0.5)
        painter.setPen(accent_color)

        # Get text metrics for line positioning
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(display_message)
        text_height = fm.height()

        center_x = rect.center().x()
        center_y = rect.center().y()

        line_y = center_y + text_height // 2 + 8
        line_half_width = text_width // 2 + 20

        painter.drawLine(
            int(center_x - line_half_width), line_y,
            int(center_x + line_half_width), line_y
        )

    def set_message(self, message: str) -> None:
        """Update the loading message."""
        self._message = message
        self.update()

    def stop(self) -> None:
        """Stop animations and cleanup."""
        if self._pulse_animation:
            self._pulse_animation.stop()
        if self._dot_timer:
            self._dot_timer.stop()

    def hideEvent(self, event) -> None:
        """Cleanup when hidden."""
        self.stop()
        super().hideEvent(event)

    def deleteLater(self) -> None:
        """Cleanup before deletion."""
        self.stop()
        super().deleteLater()
