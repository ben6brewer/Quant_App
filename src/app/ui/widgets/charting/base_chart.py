"""Base Chart - Reusable chart infrastructure for all chart modules."""

from typing import Tuple
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent


class BaseChart(pg.GraphicsLayoutWidget):
    """
    Base class for all chart widgets providing common infrastructure:
    - Theme-aware background and gridlines
    - Crosshair support
    - Mouse event handling hooks
    - ViewBox management utilities

    Subclasses should override:
    - _setup_plots() to create plot items and axes
    - _on_mouse_move() for custom mouse tracking
    - _on_mouse_leave() for custom leave behavior
    """

    # Signals
    theme_changed = Signal(str)  # Emitted when theme changes

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Theme state
        self._theme: str = "dark"

        # Subclasses should create their plot items in _setup_plots()
        self.plot_item = None  # Main plot item (to be set by subclass)
        self.view_box = None  # Main ViewBox (to be set by subclass)

        # Crosshair lines (optional, managed by subclass)
        self._crosshair_v = None
        self._crosshair_h = None

    def set_theme(self, theme: str) -> None:
        """Apply theme to chart (background, gridlines, crosshair)."""
        self._theme = theme
        self._apply_background()
        self._apply_gridlines()
        if self._crosshair_v is not None or self._crosshair_h is not None:
            self._update_crosshair_color()
        self.theme_changed.emit(theme)

    def _apply_background(self):
        """Apply theme-specific background color."""
        if self.plot_item is None:
            return

        bg_color = self._get_background_rgb()
        self.setBackground(bg_color)
        if hasattr(self.plot_item, 'setBackground'):
            self.plot_item.setBackground(bg_color)

    def _get_background_rgb(self) -> tuple[int, int, int]:
        """Get background color for current theme."""
        if self._theme == "dark":
            return (30, 30, 30)
        elif self._theme == "light":
            return (255, 255, 255)
        elif self._theme == "bloomberg":
            return (13, 20, 32)
        return (30, 30, 30)

    def _apply_gridlines(self):
        """Apply theme-specific gridlines."""
        if self.plot_item is None:
            return

        grid_color = self._get_contrasting_grid_color()
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.getAxis('bottom').setPen(color=grid_color, width=1)
        self.plot_item.getAxis('left').setPen(color=grid_color, width=1)
        if self.plot_item.getAxis('right'):
            self.plot_item.getAxis('right').setPen(color=grid_color, width=1)

    def _get_contrasting_grid_color(self) -> tuple[int, int, int]:
        """Get gridline color that contrasts with background."""
        bg_rgb = self._get_background_rgb()
        luminance = self._calculate_relative_luminance(bg_rgb)

        # Light background → dark grid, Dark background → light grid
        if luminance > 0.5:
            return (100, 100, 100)  # Dark gray for light backgrounds
        else:
            return (80, 80, 80)  # Light gray for dark backgrounds

    def _calculate_relative_luminance(self, rgb: tuple[int, int, int]) -> float:
        """Calculate relative luminance (0.0 = black, 1.0 = white)."""
        r, g, b = [x / 255.0 for x in rgb]

        # Apply gamma correction
        def gamma_correct(c):
            if c <= 0.03928:
                return c / 12.92
            else:
                return ((c + 0.055) / 1.055) ** 2.4

        r_linear = gamma_correct(r)
        g_linear = gamma_correct(g)
        b_linear = gamma_correct(b)

        # ITU-R BT.709 coefficients
        return 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear

    def _create_crosshair(self, plot_item, view_box):
        """Create crosshair lines for a plot."""
        color = self._get_crosshair_color()
        pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)

        crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pen)

        crosshair_v.setVisible(False)
        crosshair_h.setVisible(False)

        plot_item.addItem(crosshair_v, ignoreBounds=True)
        plot_item.addItem(crosshair_h, ignoreBounds=True)

        return crosshair_v, crosshair_h

    def _get_crosshair_color(self) -> tuple[int, int, int]:
        """Get crosshair color for current theme."""
        if self._theme == "dark":
            return (150, 150, 150)
        elif self._theme == "light":
            return (100, 100, 100)
        elif self._theme == "bloomberg":
            return (100, 120, 140)
        return (150, 150, 150)

    def _update_crosshair_color(self):
        """Update crosshair color when theme changes."""
        if self._crosshair_v is None and self._crosshair_h is None:
            return

        color = self._get_crosshair_color()
        pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)

        if self._crosshair_v is not None:
            self._crosshair_v.setPen(pen)
        if self._crosshair_h is not None:
            self._crosshair_h.setPen(pen)

    def _get_theme_accent_color(self) -> tuple[int, int, int]:
        """Get theme accent color for highlights."""
        if self._theme == "dark":
            return (0, 212, 255)  # Cyan
        elif self._theme == "light":
            return (0, 102, 204)  # Blue
        elif self._theme == "bloomberg":
            return (255, 128, 0)  # Orange
        return (0, 212, 255)

    def _get_label_text_color(self) -> tuple[int, int, int]:
        """Get appropriate text color for labels based on theme."""
        if self._theme == "light":
            return (0, 0, 0)  # Black text on light background
        else:
            return (255, 255, 255)  # White text on dark background

    # Event handlers (can be overridden by subclasses)

    def mouseMoveEvent(self, ev: QMouseEvent):
        """Handle mouse move - override in subclass for custom behavior."""
        self._on_mouse_move(ev)
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev):
        """Handle mouse leave - override in subclass for custom behavior."""
        self._on_mouse_leave(ev)
        super().leaveEvent(ev)

    def _on_mouse_move(self, ev: QMouseEvent):
        """Hook for subclass to implement custom mouse move behavior."""
        pass

    def _on_mouse_leave(self, ev):
        """Hook for subclass to implement custom mouse leave behavior."""
        pass

    # Utility methods

    def clear_plot(self):
        """Clear all items from the main plot."""
        if self.plot_item is not None:
            self.plot_item.clear()

    def add_item(self, item, ignoreBounds=False):
        """Add an item to the main plot."""
        if self.plot_item is not None:
            self.plot_item.addItem(item, ignoreBounds=ignoreBounds)

    def remove_item(self, item):
        """Remove an item from the main plot."""
        if self.plot_item is not None:
            self.plot_item.removeItem(item)
