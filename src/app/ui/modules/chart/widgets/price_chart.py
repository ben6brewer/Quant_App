from __future__ import annotations

import math
from typing import Dict, Tuple, Any

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QColor

from app.utils.formatters import format_price_usd, format_date
from app.core.config import CANDLE_BAR_WIDTH, DEFAULT_VIEW_PERIOD_DAYS, VIEW_PADDING_PERCENT
from .oscillator_pane import OscillatorPane
from app.ui.widgets.charting.overlays import ResizeHandle
from app.ui.widgets.charting.axes import (
    DraggableAxisItem,
    DraggablePriceAxisItem,
    DraggableIndexDateAxisItem,
    VolumeAxisItem,
)
from app.ui.widgets.charting.renderers import CandlestickItem


# -----------------------------
# Chart (with oscillator support)
# -----------------------------
class PriceChart(pg.GraphicsLayoutWidget):
    # Indicator color palette
    INDICATOR_COLORS = [
        (0, 150, 255),    # Blue
        (255, 150, 0),    # Orange
        (150, 0, 255),    # Purple
        (255, 200, 0),    # Yellow
        (0, 255, 150),    # Cyan
        (255, 0, 150),    # Magenta
    ]

    def __init__(self, parent=None, chart_settings=None):
        super().__init__(parent=parent)

        # Create price plot (row 0, column 0)
        self.price_plot = self.addPlot(
            row=0, col=0,
            axisItems={
                'bottom': DraggableIndexDateAxisItem(orientation='bottom'),
                'right': DraggablePriceAxisItem(orientation='right')
            }
        )
        self.price_plot.showAxis("right")
        self.price_plot.hideAxis("left")

        # Store axis references
        self.bottom_axis = self.price_plot.getAxis('bottom')
        self.right_axis = self.price_plot.getAxis('right')
        self.price_vb = self.price_plot.getViewBox()
        self.price_vb.setMouseEnabled(x=True, y=True)

        # Store original bottom axis pen for restoration
        self._original_bottom_axis_pen = self.bottom_axis.pen()

        # Set fixed width for price axis to ensure alignment with oscillator axis
        self.right_axis.setWidth(95)

        # Add padding to right of price axis
        self.price_plot.layout.setColumnSpacing(2, 5)

        # Create oscillator plot (row 1, column 0) - initially hidden
        # Uses VolumeAxisItem for proper formatting of large volume numbers
        self.oscillator_plot = self.addPlot(
            row=1, col=0,
            axisItems={
                'bottom': DraggableIndexDateAxisItem(orientation='bottom'),
                'right': VolumeAxisItem(orientation='right')
            }
        )
        # No label on oscillator axis (leave blank)
        self.oscillator_plot.hideAxis("right")  # Start hidden, show only when oscillators are applied
        self.oscillator_plot.hideAxis("left")
        self.oscillator_plot.hideAxis('bottom')  # Share X-axis with price

        # Store oscillator references
        self.oscillator_axis = self.oscillator_plot.getAxis('right')
        self.oscillator_bottom_axis = self.oscillator_plot.getAxis('bottom')
        self.oscillator_vb = self.oscillator_plot.getViewBox()
        self.oscillator_vb.setMouseEnabled(x=True, y=True)

        # Set fixed width for oscillator axis to match price axis (ensures vertical alignment)
        self.oscillator_axis.setWidth(95)

        # Add padding to right of oscillator axis (match price plot spacing)
        self.oscillator_plot.layout.setColumnSpacing(2, 5)

        # Link X-axes for synchronized pan/zoom
        self.oscillator_plot.setXLink(self.price_plot)

        # Set initial heights (oscillator hidden = 0, price takes full space)
        self.ci.layout.setRowPreferredHeight(0, 100)  # Price plot
        self.ci.layout.setRowPreferredHeight(1, 0)    # Oscillator hidden
        self.ci.layout.setRowStretchFactor(0, 3)      # Price 3x stretch
        self.ci.layout.setRowStretchFactor(1, 1)      # Oscillator 1x stretch

        # Track visibility (start as True so first call to _set_oscillator_visibility(False) actually executes)
        self._oscillator_visible = True

        self._candles = None
        self._line = None
        self._price_indicator_lines = []  # Overlay indicators on price chart
        self._oscillator_indicator_lines = []  # Oscillator indicators on separate axis

        # Oscillator pane management (new multi-pane system)
        self._oscillator_panes = {}  # Dict[indicator_name, OscillatorPane]
        self._next_pane_id = 0

        # Price label (rightmost visible price)
        self._price_label = None  # Will be created when enabled
        self.data = None  # Store original DataFrame for price lookup
        self._price_label_positioned = False  # Track if initial positioning is done

        # Mouse price label (follows mouse Y position)
        self._mouse_price_label = None  # Will be created when enabled (price chart)
        self._mouse_osc_label = None  # Will be created when enabled (oscillator chart)

        # Date label (crosshair)
        self._date_label = None  # Will be created when enabled
        self._date_label_positioned = False  # Track if initial positioning is done

        # Crosshair lines
        self._crosshair_v = None  # Vertical line (price chart)
        self._crosshair_h = None  # Horizontal line (price chart)
        self._crosshair_v_osc = None  # Vertical line (oscillator chart)
        self._crosshair_h_osc = None  # Horizontal line (oscillator chart)

        self.candle_width = CANDLE_BAR_WIDTH
        self._has_initialized_view = False

        self._scale_mode: str = "regular"
        self._theme: str = "dark"

        # Store chart settings
        self.chart_settings = chart_settings or {}

        # Add legend (top-left, fixed position)
        self.legend = pg.LegendItem(offset=(10, 10))
        self.legend.setParentItem(self.price_vb)
        self.legend.anchor(itemPos=(0, 0), parentPos=(0, 0))  # Top-left anchor

        # Add oscillator legend (top-left, fixed position)
        self.oscillator_legend = pg.LegendItem(offset=(10, 10))
        self.oscillator_legend.setParentItem(self.oscillator_vb)
        self.oscillator_legend.anchor(itemPos=(0, 0), parentPos=(0, 0))  # Top-left anchor

        # Apply initial background (which also applies gridlines)
        self._apply_background()

        # Apply initial crosshair
        self._apply_crosshair()

        # Update price label when view range changes
        self.price_vb.sigRangeChanged.connect(self._update_price_label)

        # Enable mouse tracking for cursor changes
        self.setMouseTracking(True)

        # Ensure oscillator is properly hidden from the start (using setRowFixedHeight, not just setRowPreferredHeight)
        self._set_oscillator_visibility(False)

        # Create resize handle (initially hidden)
        self.resize_handle = ResizeHandle(self)
        self.resize_handle.height_changed.connect(self._on_resize_handle_drag)
        self.resize_handle.drag_started.connect(self._on_resize_drag_started)
        self.resize_handle.drag_ended.connect(self._on_resize_drag_ended)
        self.resize_handle.hide()

        # Track resize handle drag state
        self._resize_handle_dragging = False

    def mousePressEvent(self, ev):
        """Handle mouse press events."""
        # Use default behavior (no oscillator dragging)
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        """Handle mouse move events for labels and crosshair."""
        # Update date label position based on mouse position
        if self._date_label and self.chart_settings.get('show_date_label', True):
            self._update_date_label(ev.pos())

        # Update mouse price label position based on mouse position
        self._update_mouse_price_label(ev.pos())

        # Update mouse oscillator label position based on mouse position
        if self._oscillator_visible:
            self._update_mouse_osc_label(ev.pos())

        # Update crosshair position if enabled
        if self._crosshair_v is not None and self._crosshair_h is not None:
            if self.chart_settings.get('show_crosshair', True):
                # Map mouse position to view coordinates
                mouse_point = self.price_vb.mapSceneToView(self.mapToScene(ev.pos()))

                # Update price chart crosshair positions
                self._crosshair_v.setPos(mouse_point.x())
                self._crosshair_h.setPos(mouse_point.y())

                # Show price chart crosshair
                self._crosshair_v.show()
                self._crosshair_h.show()

                # Update oscillator crosshair if visible
                if self._oscillator_visible and self._crosshair_v_osc is not None and self._crosshair_h_osc is not None:
                    osc_mouse_point = self.oscillator_vb.mapSceneToView(self.mapToScene(ev.pos()))
                    self._crosshair_v_osc.setPos(osc_mouse_point.x())
                    self._crosshair_h_osc.setPos(osc_mouse_point.y())
                    self._crosshair_v_osc.show()
                    self._crosshair_h_osc.show()

        # Use default behavior
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        """Handle mouse release events."""
        # Use default behavior (no oscillator dragging)
        super().mouseReleaseEvent(ev)

    def leaveEvent(self, ev):
        """Override to hide labels and crosshair when mouse leaves the chart."""
        # Hide date label when mouse leaves
        if self._date_label:
            self._date_label.hide()

        # Hide mouse price label when mouse leaves
        if self._mouse_price_label:
            self._mouse_price_label.hide()
        if self._mouse_osc_label:
            self._mouse_osc_label.hide()

        # Hide crosshair when mouse leaves
        if self._crosshair_v is not None:
            self._crosshair_v.hide()
        if self._crosshair_h is not None:
            self._crosshair_h.hide()
        if self._crosshair_v_osc is not None:
            self._crosshair_v_osc.hide()
        if self._crosshair_h_osc is not None:
            self._crosshair_h_osc.hide()

        super().leaveEvent(ev)

    def resizeEvent(self, ev):
        """Override to update price label position on resize."""
        super().resizeEvent(ev)
        # Update price label position after resize (if it exists)
        if hasattr(self, '_price_label') and self._price_label and self._price_label.isVisible():
            self._update_price_label()

        # Update resize handle position
        if hasattr(self, 'resize_handle') and self.resize_handle:
            QTimer.singleShot(0, self._position_resize_handle)

    def showEvent(self, ev):
        """Override to update price label position when widget is shown."""
        super().showEvent(ev)
        # Trigger initial label positioning after widget is fully shown
        if (hasattr(self, '_price_label') and self._price_label and
            not self._price_label_positioned and
            self.chart_settings.get('show_price_label', True)):
            # Use a small delay to ensure layout is complete
            QTimer.singleShot(100, self._initial_price_label_position)

    def _initial_price_label_position(self):
        """Perform initial price label positioning (called once after first show)."""
        if not self._price_label_positioned:
            self._update_price_label()
            self._price_label_positioned = True

    def _clear_chart(self):
        """Custom clear method to properly clean up both price and oscillator ViewBoxes."""
        # Clear legend items (but don't destroy the legend itself)
        if hasattr(self, 'legend') and self.legend is not None:
            self.legend.clear()

        # Clear oscillator legend items
        if hasattr(self, 'oscillator_legend') and self.oscillator_legend is not None:
            self.oscillator_legend.clear()

        # Remove oscillator indicators - use slice copy to avoid modification during iteration
        for item in self._oscillator_indicator_lines[:]:
            try:
                self.oscillator_vb.removeItem(item)
                if item.scene() is not None:
                    item.scene().removeItem(item)
            except:
                pass
        self._oscillator_indicator_lines.clear()

        # Remove price indicators - use slice copy
        for item in self._price_indicator_lines[:]:
            try:
                self.price_vb.removeItem(item)
                if item.scene() is not None:
                    item.scene().removeItem(item)
            except:
                pass
        self._price_indicator_lines.clear()

        # Remove candles manually
        if self._candles is not None:
            try:
                self.price_vb.removeItem(self._candles)
                if self._candles.scene() is not None:
                    self._candles.scene().removeItem(self._candles)
            except:
                pass
            self._candles = None

        # Remove line manually
        if self._line is not None:
            try:
                self.price_vb.removeItem(self._line)
                if self._line.scene() is not None:
                    self._line.scene().removeItem(self._line)
            except:
                pass
            self._line = None

        # Hide price label if it exists
        if self._price_label is not None:
            self._price_label.hide()

        # Hide mouse price label if it exists
        if self._mouse_price_label is not None:
            self._mouse_price_label.hide()
        if self._mouse_osc_label is not None:
            self._mouse_osc_label.hide()

        # Hide date label if it exists
        if self._date_label is not None:
            self._date_label.hide()

        # Hide crosshair if it exists
        if self._crosshair_v is not None:
            self._crosshair_v.hide()
        if self._crosshair_h is not None:
            self._crosshair_h.hide()
        if self._crosshair_v_osc is not None:
            self._crosshair_v_osc.hide()
        if self._crosshair_h_osc is not None:
            self._crosshair_h_osc.hide()

        # Hide oscillator subplot when cleared
        self._set_oscillator_visibility(False)

    def _set_oscillator_visibility(self, visible: bool) -> None:
        """Show or hide the oscillator subplot."""
        if visible == self._oscillator_visible:
            return

        self._oscillator_visible = visible

        if visible:
            # Expand oscillator row to 150px
            self.ci.layout.setRowFixedHeight(1, 150)
            self.oscillator_plot.showAxis('right')
            # Move date axis to bottom: keep price bottom axis for gridlines but hide labels and axis line, show oscillator bottom axis
            self.price_plot.showAxis('bottom')
            self.bottom_axis.setStyle(showValues=False)  # Hide tick labels but keep gridlines
            self.bottom_axis.setPen(None)  # Hide axis line but keep gridlines
            self.oscillator_plot.showAxis('bottom')
        else:
            # Collapse oscillator row to 0
            self.ci.layout.setRowFixedHeight(1, 0)
            self.oscillator_plot.hideAxis('right')
            # Move date axis back to price chart: show price bottom axis with labels, hide oscillator bottom axis
            self.price_plot.showAxis('bottom')
            self.bottom_axis.setStyle(showValues=True)  # Show tick labels again
            self.bottom_axis.setPen(self._original_bottom_axis_pen)  # Restore axis line
            self.oscillator_plot.hideAxis('bottom')

        # Update resize handle visibility
        if hasattr(self, 'resize_handle') and self.resize_handle:
            QTimer.singleShot(50, self._position_resize_handle)

    def _on_resize_handle_drag(self, delta_y: int):
        """
        Handle resize handle drag events.

        Args:
            delta_y: Vertical mouse delta (negative = drag up, positive = drag down)
        """
        if not self._oscillator_visible:
            return

        # Get current oscillator height
        current_height = self.oscillator_plot.sceneBoundingRect().height()

        # Calculate new height (inverted: drag up increases height)
        new_height = current_height - delta_y

        # Clamp to reasonable bounds
        total_height = self.height()
        max_height = int(total_height * 0.8)  # Max 80% of total
        min_height = 50  # Min 50px
        new_height = max(min_height, min(new_height, max_height))

        # Apply new height
        self.ci.layout.setRowFixedHeight(1, int(new_height))

        # Labels are hidden during drag and redrawn on drag end

    def _position_resize_handle(self):
        """Position the resize handle at the boundary between price and oscillator."""
        # Skip if actively dragging - user controls position
        if self._resize_handle_dragging:
            return

        if not self._oscillator_visible or not self.resize_handle:
            self.resize_handle.hide()
            return

        # Get oscillator plot top edge in widget coordinates
        osc_scene_rect = self.oscillator_plot.sceneBoundingRect()
        osc_top_left_widget = self.mapFromScene(osc_scene_rect.topLeft())

        # Position handle centered on boundary (4px above, 4px below)
        handle_y = int(osc_top_left_widget.y() - 4)

        # Handle spans full width
        self.resize_handle.setGeometry(0, handle_y, self.width(), 8)
        self.resize_handle.show()

    def _on_resize_drag_started(self):
        """Mark drag as active and hide custom overlay labels during drag."""
        self._resize_handle_dragging = True

        # Hide only custom overlay labels (not axis tick labels)
        if self._price_label:
            self._price_label.hide()
        if self._mouse_price_label:
            self._mouse_price_label.hide()
        if self._date_label:
            self._date_label.hide()

    def _on_resize_drag_ended(self):
        """Mark drag as ended, show custom labels, and reposition handle."""
        self._resize_handle_dragging = False

        # Reposition handle once after drag ends to sync with final position
        QTimer.singleShot(0, self._position_resize_handle)

        # Update custom labels (they will show if enabled in settings)
        QTimer.singleShot(10, self._update_price_label)

    def _apply_background(self):
        """Apply background color from settings or theme."""
        custom_bg = self.chart_settings.get('chart_background')
        if custom_bg:
            # Convert RGB tuple to hex color
            bg_hex = f"#{custom_bg[0]:02x}{custom_bg[1]:02x}{custom_bg[2]:02x}"
            self.setBackground(bg_hex)
        else:
            # Use theme default
            bg_color = 'w' if self._theme == "light" else '#1e1e1e'
            self.setBackground(bg_color)

        # Update gridlines after background changes
        self._apply_gridlines()

        # Update crosshair color after background changes
        self._update_crosshair_color()

    def _get_background_rgb(self) -> tuple[int, int, int]:
        """Get the current background color as RGB tuple."""
        custom_bg = self.chart_settings.get('chart_background')
        if custom_bg:
            return custom_bg
        else:
            # Return theme default colors
            if self._theme == "light":
                return (255, 255, 255)  # White
            elif self._theme == "bloomberg":
                return (13, 20, 32)  # Bloomberg dark blue
            else:
                return (30, 30, 30)  # Dark grey

    def _calculate_relative_luminance(self, rgb: tuple[int, int, int]) -> float:
        """
        Calculate relative luminance of an RGB color.

        Args:
            rgb: RGB color tuple (0-255 range)

        Returns:
            Relative luminance (0.0 to 1.0)
        """
        # Normalize to 0-1 range
        r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0

        # Apply gamma correction
        def gamma_correct(channel):
            if channel <= 0.03928:
                return channel / 12.92
            else:
                return ((channel + 0.055) / 1.055) ** 2.4

        r = gamma_correct(r)
        g = gamma_correct(g)
        b = gamma_correct(b)

        # Calculate relative luminance
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _get_contrasting_grid_color(self) -> tuple[int, int, int]:
        """
        Calculate a subtle contrasting grid color based on the current background.

        Returns:
            RGB tuple for grid color
        """
        bg_rgb = self._get_background_rgb()
        luminance = self._calculate_relative_luminance(bg_rgb)

        # Create very subtle gridlines by slightly adjusting the background color
        # Only 8-10 units difference for minimal distraction
        if luminance > 0.5:
            # Light background - make gridlines slightly darker
            # Subtract a small amount from each channel
            r = max(0, bg_rgb[0] - 8)
            g = max(0, bg_rgb[1] - 8)
            b = max(0, bg_rgb[2] - 8)
        else:
            # Dark background - make gridlines slightly lighter
            # Add a small amount to each channel
            r = min(255, bg_rgb[0] + 8)
            g = min(255, bg_rgb[1] + 8)
            b = min(255, bg_rgb[2] + 8)

        return (r, g, b)

    def _apply_gridlines(self):
        """Apply gridlines with contrasting color based on background."""
        show_gridlines = self.chart_settings.get('show_gridlines', False)

        # Apply gridlines to both price and oscillator plots
        for plot_item in [self.price_plot, self.oscillator_plot]:
            if show_gridlines:
                # Get contrasting color
                grid_color = self._get_contrasting_grid_color()

                # Create grid pen with contrasting color
                # Using solid line with extremely low alpha for minimal distraction
                grid_pen = pg.mkPen(color=grid_color, width=1, alpha=0.08)

                # Set grid pen for each axis
                for axis_name in ['bottom', 'left', 'right']:
                    axis = plot_item.getAxis(axis_name)
                    if axis is not None:
                        axis.setGrid(255)  # Enable grid with full opacity (alpha is in pen)
            else:
                # Disable grid on all axes
                for axis_name in ['bottom', 'left', 'right']:
                    axis = plot_item.getAxis(axis_name)
                    if axis is not None:
                        axis.setGrid(False)

    # -----------------------------
    # Crosshair
    # -----------------------------
    def _create_crosshair(self):
        """Create crosshair lines for both price and oscillator charts."""
        if self._crosshair_v is not None or self._crosshair_h is not None:
            return  # Already exists

        # Get crosshair color
        crosshair_color = self._get_crosshair_color()

        # Create vertical line for price chart (follows X/time)
        self._crosshair_v = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(color=crosshair_color, width=1, style=QtCore.Qt.DashLine)
        )
        self.price_vb.addItem(self._crosshair_v)
        self._crosshair_v.hide()

        # Create horizontal line for price chart (follows Y/price)
        self._crosshair_h = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(color=crosshair_color, width=1, style=QtCore.Qt.DashLine)
        )
        self.price_vb.addItem(self._crosshair_h)
        self._crosshair_h.hide()

        # Create vertical line for oscillator chart (follows X/time)
        self._crosshair_v_osc = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(color=crosshair_color, width=1, style=QtCore.Qt.DashLine)
        )
        self.oscillator_vb.addItem(self._crosshair_v_osc)
        self._crosshair_v_osc.hide()

        # Create horizontal line for oscillator chart (follows Y/oscillator value)
        self._crosshair_h_osc = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(color=crosshair_color, width=1, style=QtCore.Qt.DashLine)
        )
        self.oscillator_vb.addItem(self._crosshair_h_osc)
        self._crosshair_h_osc.hide()

    def _get_crosshair_color(self) -> tuple[int, int, int]:
        """
        Get crosshair color based on background.

        Returns:
            RGB tuple for crosshair color
        """
        bg_rgb = self._get_background_rgb()
        luminance = self._calculate_relative_luminance(bg_rgb)

        # Use a more visible color than gridlines
        if luminance > 0.5:
            # Light background - use medium grey
            return (100, 100, 100)
        else:
            # Dark background - use light grey
            return (150, 150, 150)

    def _update_crosshair_color(self):
        """Update crosshair line colors when background changes."""
        if self._crosshair_v is None or self._crosshair_h is None:
            return

        crosshair_color = self._get_crosshair_color()
        pen = pg.mkPen(color=crosshair_color, width=1, style=QtCore.Qt.DashLine)

        self._crosshair_v.setPen(pen)
        self._crosshair_h.setPen(pen)

        # Update oscillator crosshair colors if they exist
        if self._crosshair_v_osc is not None:
            self._crosshair_v_osc.setPen(pen)
        if self._crosshair_h_osc is not None:
            self._crosshair_h_osc.setPen(pen)

    def _apply_crosshair(self):
        """Apply crosshair settings."""
        show_crosshair = self.chart_settings.get('show_crosshair', True)

        if show_crosshair:
            if self._crosshair_v is None or self._crosshair_h is None:
                self._create_crosshair()
            # Crosshair visibility is handled by mouseMoveEvent/leaveEvent
        else:
            # Hide and remove price chart crosshair
            if self._crosshair_v is not None:
                self._crosshair_v.hide()
                self.price_vb.removeItem(self._crosshair_v)
                self._crosshair_v = None
            if self._crosshair_h is not None:
                self._crosshair_h.hide()
                self.price_vb.removeItem(self._crosshair_h)
                self._crosshair_h = None

            # Hide and remove oscillator crosshair
            if self._crosshair_v_osc is not None:
                self._crosshair_v_osc.hide()
                self.oscillator_vb.removeItem(self._crosshair_v_osc)
                self._crosshair_v_osc = None
            if self._crosshair_h_osc is not None:
                self._crosshair_h_osc.hide()
                self.oscillator_vb.removeItem(self._crosshair_h_osc)
                self._crosshair_h_osc = None

    # -----------------------------
    # Price Label
    # -----------------------------
    def _get_theme_accent_color(self) -> tuple[int, int, int]:
        """Get accent color based on current theme."""
        if self._theme == "light":
            return (0, 102, 204)  # Blue
        elif self._theme == "bloomberg":
            return (255, 128, 0)  # Orange
        else:
            return (0, 212, 255)  # Cyan

    def _get_label_text_color(self) -> tuple[int, int, int]:
        """Get text color for optimal contrast on accent background."""
        if self._theme == "light":
            return (255, 255, 255)  # White on blue
        else:
            return (0, 0, 0)  # Black on cyan/orange

    def _get_rightmost_visible_price(self) -> float | None:
        """
        Get the price of the rightmost visible candlestick in the current view.

        Returns:
            Rightmost visible close price or None if no data
        """
        if self.data is None or self.data.empty:
            return None

        # Get visible X range
        (x0, x1), _ = self.price_vb.viewRange()

        # Clamp to data bounds
        max_idx = len(self.data) - 1
        rightmost_idx = int(min(x1, max_idx))

        if rightmost_idx < 0 or rightmost_idx > max_idx:
            return None

        # Get close price at rightmost visible index
        close_price = self.data.iloc[rightmost_idx]['Close']

        return close_price

    def _create_price_label(self):
        """Create the price label as a QLabel widget overlay."""
        if self._price_label is not None:
            return  # Already exists

        self._price_label = QLabel(self)
        self._price_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._price_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # Don't block mouse events
        self._update_price_label_style()
        self._price_label.show()

    def _update_price_label_style(self):
        """Update price label stylesheet based on theme."""
        if not self._price_label:
            return

        accent_color = self._get_theme_accent_color()
        text_color = self._get_label_text_color()

        bg_color = f"rgb({accent_color[0]}, {accent_color[1]}, {accent_color[2]})"
        fg_color = f"rgb({text_color[0]}, {text_color[1]}, {text_color[2]})"

        self._price_label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {fg_color};
                border: none;
                padding: 2px 0px 2px 0px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)

    def _update_price_label(self):
        """Update price label position and text."""
        if not self._price_label or not self.chart_settings.get('show_price_label', True):
            if self._price_label:
                self._price_label.hide()
            return

        rightmost_price = self._get_rightmost_visible_price()
        if rightmost_price is None:
            self._price_label.hide()
            return

        # Format and set text
        label_text = format_price_usd(rightmost_price)
        self._price_label.setText(label_text)

        # Adjust size to fit content
        self._price_label.adjustSize()

        # Calculate y-position in view coordinates
        if self._scale_mode == "log":
            y_view = np.log10(rightmost_price)
        else:
            y_view = rightmost_price

        # Map view coordinates to widget pixel coordinates
        view_point = self.price_vb.mapViewToScene(pg.Point(0, y_view))
        widget_point = self.mapFromScene(view_point)

        # Get axis geometry to position label on the axis
        axis_rect = self.price_plot.getAxis('right').geometry()

        # Position label on the y-axis at the price level (fixed-width, left-aligned)
        # Use fixed width spanning entire axis for consistent positioning
        # Account for column spacing + tick marks extending into plot area
        left_offset = 11  # Column spacing + tick mark length
        right_padding = 0  # No extra padding needed with left alignment
        axis_width = axis_rect.width() - left_offset + right_padding
        label_height = self._price_label.height()

        # Set fixed width (axis width plus extra right padding to shift center left)
        self._price_label.setFixedWidth(axis_width)

        # Position left edge flush with axis background (after ticks)
        x_pos = int(axis_rect.left() + left_offset)
        y_pos = int(widget_point.y() - label_height / 2)

        self._price_label.move(x_pos, y_pos)
        self._price_label.show()

    # -----------------------------
    # Mouse Price Label (follows mouse Y)
    # -----------------------------
    def _create_mouse_price_label(self):
        """Create the mouse price label as a QLabel widget overlay."""
        if self._mouse_price_label is not None:
            return  # Already exists

        self._mouse_price_label = QLabel(self)
        self._mouse_price_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._mouse_price_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # Don't block mouse events
        self._update_mouse_price_label_style()
        self._mouse_price_label.hide()  # Start hidden, show on mouse move

    def _update_mouse_price_label_style(self):
        """Update mouse price label stylesheet based on theme."""
        if not self._mouse_price_label:
            return

        accent_color = self._get_theme_accent_color()
        bg_rgb = self._get_background_rgb()

        # Use dark background with colored border for mouse-following label
        bg_color = f"rgb({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]})"
        border_color = f"rgb({accent_color[0]}, {accent_color[1]}, {accent_color[2]})"

        # Text color based on theme
        if self._theme == "light":
            text_color = "rgb(0, 0, 0)"  # Black text on light background
        else:
            text_color = "rgb(255, 255, 255)"  # White text on dark background

        stylesheet = f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                padding: 2px 0px 2px 0px;
                font-size: 11px;
                font-weight: bold;
            }}
        """

        self._mouse_price_label.setStyleSheet(stylesheet)

        # Apply same style to oscillator label if it exists
        if self._mouse_osc_label:
            self._mouse_osc_label.setStyleSheet(stylesheet)

    def _update_mouse_price_label(self, mouse_pos: QtCore.QPoint):
        """Update mouse price label position and text based on mouse position.

        Args:
            mouse_pos: Mouse position in widget pixels
        """
        # Check if mouse price label is enabled
        if not self.chart_settings.get('show_mouse_price_label', True):
            if self._mouse_price_label:
                self._mouse_price_label.hide()
            return

        if not self._mouse_price_label:
            self._create_mouse_price_label()

        # Check if mouse is over the y-axis background (not just the tick marks)
        # The axis background starts 11 pixels to the right of the ViewBox edge
        # (accounting for column spacing + tick mark length)
        axis_rect = self.price_plot.getAxis('right').geometry()
        left_offset = 11  # Column spacing + tick mark length
        axis_background_start = axis_rect.left() + left_offset

        # If mouse X is in the axis background area, hide the label
        if mouse_pos.x() > axis_background_start:
            self._mouse_price_label.hide()
            return

        # Extract y-coordinate for rest of the method
        mouse_y = mouse_pos.y()

        # Check if mouse is within the price ViewBox area (not below in axis/oscillator area)
        price_vb_scene_rect = self.price_vb.sceneBoundingRect()
        price_vb_widget_top_left = self.mapFromScene(price_vb_scene_rect.topLeft())
        price_vb_widget_bottom = price_vb_widget_top_left.y() + price_vb_scene_rect.height()

        # If mouse is below the price chart ViewBox (in X-axis or oscillator area), hide the label
        if mouse_y > price_vb_widget_bottom:
            self._mouse_price_label.hide()
            return

        # Map mouse widget coordinates to view coordinates
        view_pos = self.price_vb.mapSceneToView(self.mapToScene(0, mouse_y))
        y_view = view_pos.y()

        # Convert from view coordinates to actual price
        if self._scale_mode == "log":
            try:
                price = 10 ** float(y_view)
            except (OverflowError, ValueError):
                self._mouse_price_label.hide()
                return
        else:
            price = float(y_view)

        # Format and set text
        label_text = format_price_usd(price)
        self._mouse_price_label.setText(label_text)

        # Get axis geometry to position label on the axis
        axis_rect = self.price_plot.getAxis('right').geometry()

        # Position label on the y-axis at the mouse y-position (fixed-width, left-aligned)
        # Use fixed width spanning entire axis for consistent positioning
        # Account for column spacing + tick marks extending into plot area
        left_offset = 11  # Column spacing + tick mark length
        right_padding = 0  # No extra padding needed with left alignment
        axis_width = axis_rect.width() - left_offset + right_padding
        label_size = self._mouse_price_label.sizeHint()
        label_height = label_size.height()

        # Set fixed width (axis width plus extra right padding to shift center left)
        self._mouse_price_label.setFixedWidth(axis_width)

        # Position left edge flush with axis background (after ticks)
        x_pos = int(axis_rect.left() + left_offset)
        y_pos = int(mouse_y - label_height / 2)

        self._mouse_price_label.move(x_pos, y_pos)
        self._mouse_price_label.show()

    def _update_mouse_osc_label(self, mouse_pos: QtCore.QPoint):
        """Update mouse oscillator label position and text based on mouse position.

        Args:
            mouse_pos: Mouse position in widget pixels
        """
        # Check if mouse price label is enabled
        if not self.chart_settings.get('show_mouse_price_label', True):
            if self._mouse_osc_label:
                self._mouse_osc_label.hide()
            return

        if not self._mouse_osc_label:
            self._create_mouse_osc_label()

        # Check if mouse is over the y-axis background (not just the tick marks)
        # The axis background starts 11 pixels to the right of the ViewBox edge
        # (accounting for column spacing + tick mark length)
        axis_rect = self.oscillator_plot.getAxis('right').geometry()
        left_offset = 11  # Column spacing + tick mark length
        axis_background_start = axis_rect.left() + left_offset

        # If mouse X is in the axis background area, hide the label
        if mouse_pos.x() > axis_background_start:
            self._mouse_osc_label.hide()
            return

        # Extract y-coordinate
        mouse_y = mouse_pos.y()

        # Check if mouse is within the oscillator ViewBox area
        osc_vb_scene_rect = self.oscillator_vb.sceneBoundingRect()
        osc_vb_widget_top_left = self.mapFromScene(osc_vb_scene_rect.topLeft())
        osc_vb_widget_top = osc_vb_widget_top_left.y()
        osc_vb_widget_bottom = osc_vb_widget_top + osc_vb_scene_rect.height()

        # If mouse is not within oscillator area, hide the label
        if mouse_y < osc_vb_widget_top or mouse_y > osc_vb_widget_bottom:
            self._mouse_osc_label.hide()
            return

        # Map mouse widget coordinates to oscillator view coordinates
        view_pos = self.oscillator_vb.mapSceneToView(self.mapToScene(0, mouse_y))
        y_view = view_pos.y()

        # Format the oscillator value (no log transform needed for oscillators)
        value = float(y_view)

        # Format with 2 decimal places
        label_text = f"{value:.2f}"
        self._mouse_osc_label.setText(label_text)

        # Get oscillator axis geometry to position label on the axis
        axis_rect = self.oscillator_plot.getAxis('right').geometry()

        # Position label on the y-axis at the mouse y-position (fixed-width, left-aligned)
        left_offset = 11  # Column spacing + tick mark length
        right_padding = 0
        axis_width = axis_rect.width() - left_offset + right_padding
        label_size = self._mouse_osc_label.sizeHint()
        label_height = label_size.height()

        # Set fixed width
        self._mouse_osc_label.setFixedWidth(axis_width)

        # Position left edge flush with axis background (after ticks)
        x_pos = int(axis_rect.left() + left_offset)
        y_pos = int(mouse_y - label_height / 2)

        self._mouse_osc_label.move(x_pos, y_pos)
        self._mouse_osc_label.show()

    def _create_mouse_osc_label(self):
        """Create the mouse oscillator label as a QLabel widget overlay."""
        if self._mouse_osc_label is not None:
            return  # Already exists

        self._mouse_osc_label = QLabel(self)
        self._mouse_osc_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._mouse_osc_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # Don't block mouse events
        self._update_mouse_price_label_style()  # Uses same style as price label
        self._mouse_osc_label.hide()  # Start hidden, show on mouse move

    # -----------------------------
    # Date label (crosshair)
    # -----------------------------
    def _create_date_label(self):
        """Create the date label as a QLabel widget overlay."""
        if self._date_label is not None:
            return

        self._date_label = QLabel(self)
        self._date_label.setAlignment(Qt.AlignCenter)
        self._date_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._update_date_label_style()
        self._date_label.hide()  # Start hidden, show on mouse move

    def _update_date_label_style(self):
        """Update date label stylesheet based on theme."""
        if not self._date_label:
            return

        accent_color = self._get_theme_accent_color()
        bg_rgb = self._get_background_rgb()

        # Use dark background with colored border for mouse-following label
        bg_color = f"rgb({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]})"
        border_color = f"rgb({accent_color[0]}, {accent_color[1]}, {accent_color[2]})"

        # Text color based on theme
        if self._theme == "light":
            text_color = "rgb(0, 0, 0)"  # Black text on light background
        else:
            text_color = "rgb(255, 255, 255)"  # White text on dark background

        self._date_label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                padding: 2px 4px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)

    def _update_date_label(self, mouse_pos: QtCore.QPoint):
        """Update date label position and text based on mouse position.

        Args:
            mouse_pos: Mouse position in widget pixels
        """
        if not self._date_label or not self.chart_settings.get('show_date_label', True):
            if self._date_label:
                self._date_label.hide()
            return

        if self.data is None or self.data.empty:
            self._date_label.hide()
            return

        # Extract mouse coordinates
        mouse_x = mouse_pos.x()
        mouse_y = mouse_pos.y()

        # Check if mouse is over the Y-axis area (too far right)
        # Use price plot's right axis as the reference
        right_axis_rect = self.price_plot.getAxis('right').geometry()
        if mouse_x >= right_axis_rect.left():
            self._date_label.hide()
            return

        # Map mouse widget coordinates to view coordinates
        view_pos = self.price_vb.mapSceneToView(self.mapToScene(mouse_x, 0))
        x_view = view_pos.x()

        # Clamp to data bounds
        x_index = int(round(x_view))
        if x_index < 0 or x_index >= len(self.data):
            self._date_label.hide()
            return

        # Get the date at this index
        date_value = self.data.index[x_index]

        # Format the date
        if isinstance(date_value, pd.Timestamp):
            label_text = date_value.strftime("%Y-%m-%d")
        else:
            label_text = str(date_value)

        self._date_label.setText(label_text)
        self._date_label.adjustSize()

        # Get bottom axis geometry to position label on the axis
        # Use oscillator axis if visible, otherwise use price axis
        if self._oscillator_visible:
            target_plot = self.oscillator_plot
            axis_item = self.oscillator_plot.getAxis('bottom')
        else:
            target_plot = self.price_plot
            axis_item = self.price_plot.getAxis('bottom')

        # Get axis geometry and map to widget coordinates
        axis_rect = axis_item.geometry()

        # Get the plot's scene bounding rect and map to widget
        plot_scene_rect = target_plot.sceneBoundingRect()
        plot_widget_top_left = self.mapFromScene(plot_scene_rect.topLeft())

        # Calculate axis top position in widget coordinates (the x-axis line itself)
        axis_top_y = plot_widget_top_left.y() + axis_rect.top()

        # If mouse is below the x-axis line, hide the label
        if mouse_y > axis_top_y:
            self._date_label.hide()
            return

        # Position label on the bottom axis at the mouse x-position (centered on axis)
        label_width = self._date_label.width()
        label_height = self._date_label.height()
        x_pos = int(mouse_x - label_width / 2)

        # Map axis position to widget coordinates and center label vertically on axis
        # The axis rect is in the plot's coordinate system, so add the plot's widget position
        axis_center_y = axis_rect.top() + (axis_rect.height() - label_height) / 2
        y_pos = int(plot_widget_top_left.y() + axis_center_y) + 2  # Add 2px offset to move down

        self._date_label.move(x_pos, y_pos)
        self._date_label.show()

    # -----------------------------
    # Scale transform (plot-space only)
    # -----------------------------
    @staticmethod
    def _to_log10_prices(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        eps = 1e-12
        for col in ("Open", "High", "Low", "Close"):
            if col in out.columns:
                out[col] = np.log10(out[col].astype(float).clip(lower=eps))
        return out

    @staticmethod
    def _to_log10_series(series: pd.Series) -> pd.Series:
        """Convert a series to log10 values."""
        eps = 1e-12
        return np.log10(series.astype(float).clip(lower=eps))

    # -----------------------------
    # Theme
    # -----------------------------
    def set_theme(self, theme: str) -> None:
        """Set the chart theme (affects line color and background)."""
        self._theme = theme
        # Apply background (respects custom settings)
        self._apply_background()

        # Update price label style if it exists
        if self._price_label:
            self._update_price_label_style()

        # Update mouse price label style if it exists
        if self._mouse_price_label:
            self._update_mouse_price_label_style()

        # Update mouse oscillator label style if it exists
        if self._mouse_osc_label:
            self._update_mouse_price_label_style()  # Uses same style

        # Update date label style if it exists
        if self._date_label:
            self._update_date_label_style()

        # Update resize handle theme
        if hasattr(self, 'resize_handle') and self.resize_handle:
            self.resize_handle.set_theme(theme)

    def get_line_color(self) -> tuple[int, int, int]:
        """Get line color from settings or theme."""
        custom_color = self.chart_settings.get('line_color')
        if custom_color:
            return custom_color
        return (0, 0, 0) if self._theme == "light" else (76, 175, 80)

    def get_line_settings(self) -> dict:
        """Get line settings from custom settings or theme default."""
        # Check for custom line color
        custom_color = self.chart_settings.get('line_color')
        if custom_color:
            color = custom_color
        else:
            # Use theme default
            color = (0, 0, 0) if self._theme == "light" else (76, 175, 80)
        
        width = self.chart_settings.get('line_width', 2)
        style = self.chart_settings.get('line_style', QtCore.Qt.SolidLine)
        
        return {'color': color, 'width': width, 'style': style}

    def update_chart_settings(self, settings):
        """Update chart settings and refresh display."""
        self.chart_settings = settings or {}

        # Update background (which also updates gridlines)
        self._apply_background()

        # Update candle colors if candles exist
        if self._candles:
            up_color = settings.get('candle_up_color', (76, 153, 0))
            down_color = settings.get('candle_down_color', (200, 50, 50))
            self._candles.setColors(up_color, down_color)

        # Update line if exists
        if self._line:
            line_settings = self.get_line_settings()
            pen = pg.mkPen(color=line_settings['color'], width=line_settings['width'], style=line_settings['style'])
            self._line.setPen(pen)

        # Handle price label toggle
        show_label = settings.get('show_price_label', True)
        if show_label:
            if not self._price_label:
                self._create_price_label()
            self._update_price_label()
        elif self._price_label:
            self._price_label.hide()

        # Handle date label toggle
        show_date_label = settings.get('show_date_label', True)
        if show_date_label:
            if not self._date_label:
                self._create_date_label()
            # Date label will show on next mouse move
        elif self._date_label:
            self._date_label.hide()

        # Handle crosshair toggle
        self._apply_crosshair()

    # -----------------------------
    # View helpers
    # -----------------------------
    def _get_visible_date_window(self) -> Tuple[pd.Timestamp | None, pd.Timestamp | None]:
        if not self.bottom_axis._index_to_dt:
            return None, None

        (x0, x1), _ = self.price_vb.viewRange()
        n = len(self.bottom_axis._index_to_dt)

        i0 = int(np.clip(round(x0), 0, n - 1))
        i1 = int(np.clip(round(x1), 0, n - 1))

        return self.bottom_axis._index_to_dt[i0], self.bottom_axis._index_to_dt[i1]

    @staticmethod
    def _date_to_index(df: pd.DataFrame, dt: pd.Timestamp) -> int:
        dt = pd.Timestamp(dt)
        return int(df.index.get_indexer([dt], method="nearest")[0])

    def _safe_set_yrange(self, y_min: float, y_max: float) -> None:
        if y_max <= y_min:
            y_max = y_min + 1e-6

        pad = (y_max - y_min) * VIEW_PADDING_PERCENT if y_max != y_min else max(1e-6, abs(y_max) * 0.001)
        self.price_vb.setYRange(y_min - pad, y_max + pad, padding=0)

    def _apply_date_window(self, df_plot: pd.DataFrame, left_dt: pd.Timestamp, right_dt: pd.Timestamp) -> None:
        i0 = self._date_to_index(df_plot, left_dt)
        i1 = self._date_to_index(df_plot, right_dt)
        if i0 > i1:
            i0, i1 = i1, i0

        self.price_vb.setXRange(i0, i1, padding=0)

        df_vis = df_plot.iloc[max(0, i0) : min(len(df_plot), i1 + 1)]
        if df_vis.empty:
            return

        if {"Low", "High"}.issubset(df_vis.columns):
            y_min = float(df_vis["Low"].min())
            y_max = float(df_vis["High"].max())
        elif "Close" in df_vis.columns:
            y_min = float(df_vis["Close"].min())
            y_max = float(df_vis["Close"].max())
        else:
            return

        self._safe_set_yrange(y_min, y_max)

    def _set_view_last_year(self, df_plot: pd.DataFrame) -> None:
        if df_plot is None or df_plot.empty:
            return

        end = df_plot.index.max()
        start = end - pd.Timedelta(days=DEFAULT_VIEW_PERIOD_DAYS)
        df_1y = df_plot.loc[df_plot.index >= start]
        if df_1y.empty:
            return

        self._apply_date_window(df_plot, df_1y.index.min(), df_1y.index.max())

    # -----------------------------
    # Public API
    # -----------------------------
    def set_prices(
        self,
        df: pd.DataFrame,
        ticker: str,
        chart_type: str = "Candles",
        scale: str = "Regular",
        indicators: Dict[str, Dict[str, Any]] = None,
    ) -> None:
        if df is None or df.empty:
            self._clear_chart()
            return

        # Store original data for price label
        self.data = df.copy() if df is not None else None

        prev_left_dt, prev_right_dt = self._get_visible_date_window()

        scale_key = (scale or "Regular").strip().lower()
        self._scale_mode = "log" if scale_key.startswith("log") else "regular"

        df_plot = self._to_log10_prices(df) if self._scale_mode == "log" else df

        # USD tick formatting for BOTH regular + log
        self.right_axis.set_scale_mode(self._scale_mode)

        # Clear chart
        self._clear_chart()
        self._candles = None
        self._line = None
        self._price_indicator_lines = []
        self._oscillator_indicator_lines = []

        # Set index for both bottom axes (price and oscillator)
        self.bottom_axis.set_index(df_plot.index)
        self.oscillator_bottom_axis.set_index(df_plot.index)
        x = np.arange(len(df_plot), dtype=float)

        chart_type = (chart_type or "Candles").strip()

        if chart_type == "Line":
            if "Close" not in df_plot.columns:
                raise ValueError(f"Missing 'Close' column. Columns: {list(df_plot.columns)}")

            y = df_plot["Close"].astype(float).to_numpy()
            
            # Get line settings (color, width, style)
            line_settings = self.get_line_settings()
            pen = pg.mkPen(color=line_settings['color'], width=line_settings['width'], style=line_settings['style'])
            self._line = self.price_plot.plot(x, y, pen=pen, name=f"{ticker}")
        else:
            required = {"Open", "High", "Low", "Close"}
            missing = required - set(df_plot.columns)
            if missing:
                raise ValueError(f"Missing OHLC columns: {sorted(missing)}. Columns: {list(df_plot.columns)}")

            o = df_plot["Open"].astype(float).to_numpy()
            h = df_plot["High"].astype(float).to_numpy()
            l = df_plot["Low"].astype(float).to_numpy()
            c = df_plot["Close"].astype(float).to_numpy()

            data = np.column_stack([x, o, c, l, h])
            
            # Get candle colors and width from settings
            up_color = self.chart_settings.get('candle_up_color', (76, 153, 0))
            down_color = self.chart_settings.get('candle_down_color', (200, 50, 50))
            candle_width = self.chart_settings.get('candle_width', self.candle_width)
            
            self._candles = CandlestickItem(data, bar_width=candle_width, up_color=up_color, down_color=down_color)
            self.price_vb.addItem(self._candles)

        # Plot indicators (always call to ensure oscillator visibility is updated)
        self._plot_indicators(x, df, indicators or {})

        # restore window or init view
        if prev_left_dt is not None and prev_right_dt is not None:
            self._apply_date_window(df_plot, prev_left_dt, prev_right_dt)
        elif not self._has_initialized_view:
            self._set_view_last_year(df_plot)
            self._has_initialized_view = True

        # Create price label if enabled (positioning handled by showEvent and sigRangeChanged)
        if self.chart_settings.get('show_price_label', True):
            if not self._price_label:
                self._create_price_label()
            # Reset positioning flag so showEvent will trigger initial positioning
            self._price_label_positioned = False

        # Create date label if enabled (positioning handled by mouseMoveEvent)
        if self.chart_settings.get('show_date_label', True):
            if not self._date_label:
                self._create_date_label()
            # Reset positioning flag
            self._date_label_positioned = False

    # -------------------------
    # Oscillator Pane Management
    # -------------------------

    def _create_oscillator_pane(self, indicator_name: str):
        """
        Create a new oscillator pane for the given indicator.

        Args:
            indicator_name: Name of the indicator (e.g., "RSI(14)")

        Returns:
            OscillatorPane instance
        """
        pane = OscillatorPane(
            indicator_name=indicator_name,
            pane_id=self._next_pane_id,
            theme_manager=None,  # Will be set when applying theme
            parent=None
        )
        self._next_pane_id += 1

        # Set pane width to match chart
        chart_width = self.price_vb.sceneBoundingRect().width()
        pane.update_width(chart_width)

        # Link X-axis to price chart
        pane.set_x_link(self.price_vb)

        # Apply current theme
        pane.apply_theme(self._theme)

        # Add to scene
        self.scene().addItem(pane)

        # Position pane
        self._position_pane(pane)

        return pane

    def _position_pane(self, pane) -> None:
        """
        Position pane based on existing panes (stack from bottom-right).

        Args:
            pane: OscillatorPane to position
        """
        # Get price chart bounds in scene coordinates
        price_rect = self.price_vb.sceneBoundingRect()

        # Calculate base position (bottom-right of chart)
        margin = 20
        base_x = price_rect.right() - pane.pane_width - margin
        base_y = price_rect.bottom() - pane.pane_height - margin

        # Adjust for existing panes (stack upward)
        pane_count = len(self._oscillator_panes)
        gap = 10

        y_offset = pane_count * (pane.pane_height + gap)

        pane.setPos(base_x, base_y - y_offset)

    def _remove_oscillator_pane(self, indicator_name: str) -> None:
        """
        Remove an oscillator pane.

        Args:
            indicator_name: Name of the indicator to remove
        """
        if indicator_name in self._oscillator_panes:
            pane = self._oscillator_panes[indicator_name]
            self.scene().removeItem(pane)
            del self._oscillator_panes[indicator_name]

    def _clear_all_oscillator_panes(self) -> None:
        """Clear all oscillator panes."""
        for pane in list(self._oscillator_panes.values()):
            self.scene().removeItem(pane)
        self._oscillator_panes.clear()

    def _plot_indicators(
        self, x: np.ndarray, df: pd.DataFrame, indicators: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Plot indicators on appropriate ViewBox (price or oscillator).

        Args:
            x: Array of x-coordinates (indices)
            df: Original price DataFrame
            indicators: Dict mapping indicator names to dicts containing:
                - "data": DataFrame with indicator values
                - "appearance": Appearance settings (or None for defaults)
                - "per_line_appearance": Per-line appearance settings (or None)
        """
        from ..services import IndicatorService

        # Early exit for empty indicators - ensure oscillator is hidden
        if not indicators:
            self._set_oscillator_visibility(False)
            return

        # Clear legends before plotting (if they exist)
        if hasattr(self, 'legend') and self.legend is not None:
            self.legend.clear()
        if hasattr(self, 'oscillator_legend') and self.oscillator_legend is not None:
            self.oscillator_legend.clear()

        color_idx = 0
        has_oscillators = False

        for indicator_name, indicator_info in indicators.items():
            # Extract data and per-line appearance
            indicator_df = indicator_info.get("data")
            per_line_appearance = indicator_info.get("per_line_appearance", {}) or {}  # Safety: never None

            if indicator_df is None or indicator_df.empty:
                continue

            # Determine if this is an oscillator or overlay
            is_oscillator = IndicatorService.is_overlay(indicator_name) == False

            if is_oscillator:
                has_oscillators = True

            # Select the appropriate PlotItem and ViewBox
            target_plot = self.oscillator_plot if is_oscillator else self.price_plot
            target_vb = target_plot.getViewBox()

            # Special handling for Volume indicator histogram
            config = IndicatorService.ALL_INDICATORS.get(indicator_name, {})
            if config.get("kind") == "volume":
                display_type = config.get("display_type", "histogram")
                if display_type == "histogram" and "Volume" in indicator_df.columns:
                    # Render as histogram with direction-based coloring
                    volume_data = indicator_df["Volume"].to_numpy()
                    direction_data = indicator_df.get(
                        "Volume_Direction", pd.Series([0] * len(volume_data))
                    ).to_numpy()

                    # Get colors from config
                    up_color = config.get("up_color", (76, 153, 0))
                    down_color = config.get("down_color", (200, 50, 50))
                    neutral_color = (100, 100, 100)

                    # Create per-bar brushes based on direction
                    brushes = []
                    for direction in direction_data:
                        if direction > 0:
                            brushes.append(pg.mkBrush(*up_color, 180))
                        elif direction < 0:
                            brushes.append(pg.mkBrush(*down_color, 180))
                        else:
                            brushes.append(pg.mkBrush(*neutral_color, 180))

                    # Create BarGraphItem for histogram
                    bar_width = 0.8
                    bar_graph = pg.BarGraphItem(
                        x=x,
                        height=volume_data,
                        width=bar_width,
                        brushes=brushes,
                        pen=pg.mkPen(None),
                    )
                    target_vb.addItem(bar_graph)
                    self._oscillator_indicator_lines.append(bar_graph)

                    continue  # Skip normal column rendering for Volume histogram

            # Plot each column in the indicator dataframe
            for col in indicator_df.columns:
                # Skip internal/metadata columns
                if col == "Volume_Direction":
                    continue

                # Get per-line settings
                line_settings = per_line_appearance.get(col, {})

                # Check visibility
                if not line_settings.get("visible", True):
                    continue  # Skip hidden lines

                # Get custom label for legend
                label = line_settings.get("label", col)
                if not label.strip():
                    label = None  # Don't add to legend if empty

                # Get appearance FROM PER-LINE ONLY (no fallback to global)
                custom_color = line_settings.get("color")
                if not custom_color:
                    # Use auto-color if no per-line color specified
                    custom_color = self.INDICATOR_COLORS[color_idx % len(self.INDICATOR_COLORS)]

                line_width = line_settings.get("line_width", 2)
                line_style = line_settings.get("line_style", QtCore.Qt.SolidLine)
                marker_shape = line_settings.get("marker_shape", "o")
                marker_size = line_settings.get("marker_size", 10)
                marker_offset = line_settings.get("marker_offset", 0)
                y_series = indicator_df[col]

                # Check if this is a sparse signal column
                non_nan_count = y_series.notna().sum()
                total_count = len(y_series)
                is_sparse = non_nan_count < (total_count * 0.1)

                if is_sparse and non_nan_count > 0:
                    # Render as scatter plot (for crossover signals, etc.)
                    mask = y_series.notna()
                    x_points = x[mask]
                    y_points = y_series[mask].to_numpy()

                    # Apply log transform only for price overlays in log mode
                    if self._scale_mode == "log" and not is_oscillator:
                        y_points = self._to_log10_series(pd.Series(y_points)).to_numpy()

                    # Apply marker offset (convert pixels to data units)
                    if marker_offset != 0:
                        view_range = target_vb.viewRange()
                        y_min, y_max = view_range[1]
                        vb_height = target_vb.height()
                        if vb_height > 0:
                            data_per_pixel = (y_max - y_min) / vb_height
                            offset_in_data_units = marker_offset * data_per_pixel
                            y_points = y_points + offset_in_data_units
                    
                    # Determine marker color and style
                    if "Golden" in col or "Bull" in col or "Buy" in col:
                        # Bullish signals - green
                        symbol = marker_shape if custom_color else 'o'
                        color = custom_color if custom_color else (76, 175, 80)
                        size = marker_size
                    elif "Death" in col or "Bear" in col or "Sell" in col:
                        # Bearish signals - red
                        symbol = marker_shape if custom_color else 'x'
                        color = custom_color if custom_color else (244, 67, 54)
                        size = marker_size
                    else:
                        # Default signal marker
                        symbol = marker_shape
                        color = custom_color if custom_color else self.INDICATOR_COLORS[color_idx % len(self.INDICATOR_COLORS)]
                        size = marker_size
                    
                    # Create scatter plot
                    scatter = pg.ScatterPlotItem(
                        x=x_points,
                        y=y_points,
                        pen=pg.mkPen(None),
                        brush=pg.mkBrush(color),
                        symbol=symbol,
                        size=size,
                        name=label or col,
                    )
                    target_vb.addItem(scatter)

                    # Add to appropriate legend
                    if label:
                        if is_oscillator and hasattr(self, 'oscillator_legend') and self.oscillator_legend is not None:
                            self.oscillator_legend.addItem(scatter, label)
                        elif not is_oscillator and hasattr(self, 'legend') and self.legend is not None:
                            self.legend.addItem(scatter, label)

                    if is_oscillator:
                        self._oscillator_indicator_lines.append(scatter)
                    else:
                        self._price_indicator_lines.append(scatter)
                    
                else:
                    # Render as line plot (for continuous indicators)
                    y = y_series.to_numpy()
                    
                    # Apply log transform only for price overlays in log mode
                    if self._scale_mode == "log" and not is_oscillator:
                        y = self._to_log10_series(y_series).to_numpy()
                    
                    # Get color for this indicator line
                    if custom_color:
                        color = custom_color
                    else:
                        color = self.INDICATOR_COLORS[color_idx % len(self.INDICATOR_COLORS)]
                    
                    # Determine line style if not provided
                    if not custom_color:
                        if "BB" in col or "Band" in col:
                            line_style = QtCore.Qt.DashLine
                        elif "Middle" in col or "SMA" in col or "EMA" in col:
                            line_style = QtCore.Qt.SolidLine
                    
                    pen = pg.mkPen(color=color, width=line_width, style=line_style)

                    # Plot the indicator
                    line = pg.PlotCurveItem(x=x, y=y, pen=pen, name=label or col)
                    target_vb.addItem(line)

                    # Add to appropriate legend
                    if label:
                        if is_oscillator and hasattr(self, 'oscillator_legend') and self.oscillator_legend is not None:
                            self.oscillator_legend.addItem(line, label)
                        elif not is_oscillator and hasattr(self, 'legend') and self.legend is not None:
                            self.legend.addItem(line, label)

                    if is_oscillator:
                        self._oscillator_indicator_lines.append(line)
                    else:
                        self._price_indicator_lines.append(line)
                
                color_idx += 1
        
        # Show/hide oscillator subplot based on whether we have oscillators
        self._set_oscillator_visibility(has_oscillators)
        if has_oscillators:
            # Auto-fit oscillator range
            self._auto_fit_oscillator_range()

        # Update price label after oscillator visibility changes (with small delay to let layout settle)
        QTimer.singleShot(50, self._update_price_label)

    def _auto_fit_oscillator_range(self):
        """Auto-fit the oscillator Y-range to show all oscillator data."""
        if not self._oscillator_indicator_lines:
            return

        # Collect all Y values from oscillator indicators
        all_y_values = []
        for item in self._oscillator_indicator_lines:
            if isinstance(item, pg.ScatterPlotItem):
                points = item.getData()
                if points and len(points) > 1:
                    all_y_values.extend(points[1])
            elif isinstance(item, pg.PlotCurveItem):
                y_data = item.getData()[1]
                if y_data is not None:
                    all_y_values.extend(y_data[np.isfinite(y_data)])
            elif isinstance(item, pg.BarGraphItem):
                # Handle BarGraphItem (e.g., Volume histogram)
                height = item.opts.get("height")
                if height is not None:
                    all_y_values.extend(height[np.isfinite(height)])

        if all_y_values:
            y_min = np.min(all_y_values)
            y_max = np.max(all_y_values)

            # Add some padding
            padding = (y_max - y_min) * 0.1
            self.oscillator_vb.setYRange(y_min - padding, y_max + padding, padding=0)