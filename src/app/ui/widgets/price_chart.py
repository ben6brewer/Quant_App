from __future__ import annotations

import math
from typing import Dict, Tuple, Any

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QTimer

from app.utils.formatters import format_price_usd, format_date
from app.core.config import CANDLE_BAR_WIDTH, DEFAULT_VIEW_PERIOD_DAYS, VIEW_PADDING_PERCENT


# -----------------------------
# Axes (keeping existing code)
# -----------------------------
class DraggableAxisItem(pg.AxisItem):
    """
    Numeric axis + axis-drag zoom.

    Left-drag:
      - bottom/top axis: drag left/right to zoom X
      - left/right axis: drag up/down to zoom Y

    Custom behavior:
      - For Y axes ("left"/"right"), dragging UP zooms IN.
    """

    def __init__(self, orientation: str, *args, **kwargs):
        super().__init__(orientation=orientation, *args, **kwargs)
        self._ori = orientation
        self._drag_active = False

    def mouseDragEvent(self, ev):
        vb = self.linkedView()
        if vb is None:
            ev.ignore()
            return

        if ev.button() != QtCore.Qt.LeftButton:
            ev.ignore()
            return

        ev.accept()

        if ev.isStart():
            self._drag_active = True
            return

        if not self._drag_active:
            return

        dp = ev.pos() - ev.lastPos()

        is_x_axis = self._ori in ("bottom", "top")
        delta = dp.x() if is_x_axis else dp.y()

        sensitivity = 0.005

        # X axis: keep feel; Y axis: invert so drag UP (negative y) => zoom IN
        if is_x_axis:
            factor = math.exp(-float(delta) * sensitivity)
        else:
            factor = math.exp(+float(delta) * sensitivity)

        (x0, x1), (y0, y1) = vb.viewRange()

        if x1 == x0 or y1 == y0:
            if ev.isFinish():
                self._drag_active = False
            return

        if is_x_axis:
            cx = 0.5 * (x0 + x1)
            half = 0.5 * (x1 - x0) * factor
            vb.setXRange(cx - half, cx + half, padding=0)
        else:
            cy = 0.5 * (y0 + y1)
            half = 0.5 * (y1 - y0) * factor
            vb.setYRange(cy - half, cy + half, padding=0)

        if ev.isFinish():
            self._drag_active = False


class DraggablePriceAxisItem(DraggableAxisItem):
    """
    Right price axis that ALWAYS displays USD labels.

    If scale_mode == "log":
        plotted values are log10(price) and we render ticks as 10**tick in USD.
    If scale_mode == "regular":
        plotted values are price and we render ticks directly in USD.
    """

    def __init__(self, orientation: str, *args, **kwargs):
        super().__init__(orientation=orientation, *args, **kwargs)
        self.scale_mode: str = "regular"

    def set_scale_mode(self, mode: str) -> None:
        self.scale_mode = (mode or "regular").strip().lower()
        self.update()

    def tickStrings(self, values, scale, spacing):
        out: list[str] = []

        is_log = self.scale_mode.startswith("log")
        for v in values:
            if not np.isfinite(v):
                out.append("")
                continue

            if is_log:
                # v is log10(price)
                try:
                    price = 10 ** float(v)
                except OverflowError:
                    out.append("")
                    continue
                out.append(format_price_usd(price))
            else:
                # v is already price
                out.append(format_price_usd(float(v)))

        return out


class DraggableIndexDateAxisItem(pg.AxisItem):
    """
    Bottom axis that:
      1) Displays dates even though X values are integer indices (0..N-1)
      2) Supports axis-drag zoom on X (left drag)

    This keeps candle spacing uniform across intervals AND gives you the X-axis dragging behavior.
    """

    def __init__(self, orientation: str = "bottom", *args, **kwargs):
        super().__init__(orientation=orientation, *args, **kwargs)
        self._index_to_dt: list[pd.Timestamp] = []
        self._drag_active = False

    def set_index(self, dt_index: pd.DatetimeIndex) -> None:
        self._index_to_dt = [pd.Timestamp(x) for x in dt_index.to_pydatetime()]

    def tickStrings(self, values, scale, spacing):
        out: list[str] = []
        n = len(self._index_to_dt)
        for v in values:
            i = int(round(v))
            if 0 <= i < n:
                dt = self._index_to_dt[i]
                out.append(format_date(dt))
            else:
                out.append("")
        return out

    def mouseDragEvent(self, ev):
        vb = self.linkedView()
        if vb is None:
            ev.ignore()
            return

        if ev.button() != QtCore.Qt.LeftButton:
            ev.ignore()
            return

        ev.accept()

        if ev.isStart():
            self._drag_active = True
            return

        if not self._drag_active:
            return

        dp = ev.pos() - ev.lastPos()
        delta = dp.x()

        sensitivity = 0.005
        factor = math.exp(-float(delta) * sensitivity)

        (x0, x1), _ = vb.viewRange()
        if x1 == x0:
            if ev.isFinish():
                self._drag_active = False
            return

        cx = 0.5 * (x0 + x1)
        half = 0.5 * (x1 - x0) * factor

        vb.setXRange(cx - half, cx + half, padding=0)

        if ev.isFinish():
            self._drag_active = False


# -----------------------------
# Candles (with color support)
# -----------------------------
class CandlestickItem(pg.GraphicsObject):
    """
    data rows: [x, open, close, low, high]
    x is an integer index (0..N-1) for uniform spacing
    """

    def __init__(self, data, bar_width: float = CANDLE_BAR_WIDTH, up_color=None, down_color=None):
        super().__init__()
        self.data = np.array(data, dtype=float)
        self.bar_width = float(bar_width)
        self.up_color = up_color or (76, 153, 0)
        self.down_color = down_color or (200, 50, 50)
        self._picture = None
        self._generate_picture()

    def setData(self, data):
        self.data = np.array(data, dtype=float)
        self._generate_picture()
        self.update()

    def setColors(self, up_color, down_color):
        """Update candle colors and regenerate picture."""
        self.up_color = up_color
        self.down_color = down_color
        self._generate_picture()
        self.update()

    def _generate_picture(self):
        picture = QtGui.QPicture()
        p = QtGui.QPainter(picture)

        if self.data.size == 0:
            p.end()
            self._picture = picture
            return

        up_color = self.up_color
        down_color = self.down_color
        up_pen = pg.mkPen(color=up_color, width=1)
        down_pen = pg.mkPen(color=down_color, width=1)
        up_brush = pg.mkBrush(up_color)
        down_brush = pg.mkBrush(down_color)

        w = self.bar_width  # in "index units"

        for x, o, c, lo, hi in self.data:
            if not np.isfinite([x, o, c, lo, hi]).all():
                continue

            is_up = c >= o
            p.setPen(up_pen if is_up else down_pen)
            p.setBrush(up_brush if is_up else down_brush)

            # wick
            p.drawLine(QtCore.QPointF(x, lo), QtCore.QPointF(x, hi))

            # body
            top = max(o, c)
            bot = min(o, c)

            if top == bot:
                p.drawLine(QtCore.QPointF(x - w / 2, top), QtCore.QPointF(x + w / 2, top))
            else:
                rect = QtCore.QRectF(x - w / 2, bot, w, top - bot)
                p.drawRect(rect)

        p.end()
        self._picture = picture

    def paint(self, painter, *args):
        if self._picture is not None:
            painter.drawPicture(0, 0, self._picture)

    def boundingRect(self):
        if self.data.size == 0:
            return QtCore.QRectF()

        x = self.data[:, 0]
        lo = self.data[:, 3]
        hi = self.data[:, 4]

        return QtCore.QRectF(
            float(x.min()),
            float(lo.min()),
            float(x.max() - x.min()),
            float(hi.max() - lo.min()),
        )


# -----------------------------
# Draggable ViewBox for Oscillators
# -----------------------------
class DraggableViewBox(pg.ViewBox):
    """
    ViewBox for oscillators with independent Y-axis positioning.
    Dragging is handled at the PlotWidget level for better event routing.
    """
    
    sigVerticalOffsetChanged = QtCore.Signal(float)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vertical_offset = 0
    
    def get_vertical_offset(self):
        """Get the current vertical offset."""
        return self._vertical_offset
    
    def set_vertical_offset(self, offset):
        """Set the vertical offset."""
        self._vertical_offset = offset
        self.sigVerticalOffsetChanged.emit(offset)


# -----------------------------
# Chart (with oscillator support)
# -----------------------------
class PriceChart(pg.PlotWidget):
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

        self.showGrid(x=True, y=True)
        self.setLabel("bottom", "Time")

        # Main price ViewBox and axes
        self.bottom_axis = DraggableIndexDateAxisItem(orientation="bottom")
        self.right_axis = DraggablePriceAxisItem(orientation="right")

        self.setAxisItems({"bottom": self.bottom_axis, "right": self.right_axis})
        self.showAxis("right")
        self.hideAxis("left")

        # Add 10px padding to the right of the right axis
        self.plotItem.layout.setColumnSpacing(2, 10)  # Column 2 is right axis

        self.price_vb = self.getViewBox()
        self.price_vb.setMouseEnabled(x=True, y=True)

        # Create second ViewBox for oscillators with independent Y-axis
        self.oscillator_vb = DraggableViewBox()
        self.oscillator_vb.setMouseEnabled(x=True, y=True)
        
        # Create second right axis for oscillators
        self.oscillator_axis = DraggableAxisItem(orientation="right")
        self.oscillator_axis.setLabel("Oscillator")
        
        # Add the oscillator ViewBox to the plot
        self.plotItem.scene().addItem(self.oscillator_vb)
        self.oscillator_axis.linkToView(self.oscillator_vb)
        
        # Link X-axes so they pan/zoom together
        self.oscillator_vb.setXLink(self.price_vb)
        
        # Position the oscillator axis to the right of the price axis
        self.plotItem.layout.addItem(self.oscillator_axis, 2, 3)
        
        # Connect signal to update geometry when offset changes
        self.oscillator_vb.sigVerticalOffsetChanged.connect(self._update_oscillator_geometry)
        
        # Initially hide oscillator axis
        self.oscillator_axis.hide()

        self._candles = None
        self._line = None
        self._price_indicator_lines = []  # Overlay indicators on price chart
        self._oscillator_indicator_lines = []  # Oscillator indicators on separate axis

        # Track if we're dragging the oscillator
        self._oscillator_drag_active = False
        self._cursor_over_oscillator = False

        # Price label
        self._price_label = None  # Will be created when enabled
        self.data = None  # Store original DataFrame for price lookup
        self._price_label_positioned = False  # Track if initial positioning is done

        # Date label (crosshair)
        self._date_label = None  # Will be created when enabled
        self._date_label_positioned = False  # Track if initial positioning is done

        self.candle_width = CANDLE_BAR_WIDTH
        self._has_initialized_view = False

        self._scale_mode: str = "regular"
        self._theme: str = "dark"

        # Store chart settings
        self.chart_settings = chart_settings or {}

        # Add legend
        self.legend = self.addLegend(offset=(10, 10))

        # Apply initial background
        self._apply_background()
        
        # Update oscillator ViewBox geometry when price ViewBox changes
        self.price_vb.sigRangeChanged.connect(self._update_oscillator_geometry)

        # Update price label when view range changes
        self.price_vb.sigRangeChanged.connect(self._update_price_label)

        # Initialize oscillator geometry
        self._update_oscillator_geometry()

        # Enable mouse tracking for cursor changes
        self.setMouseTracking(True)

    def _is_mouse_over_oscillator(self, scene_pos):
        """Check if mouse position is over any oscillator items."""
        if not self._oscillator_indicator_lines:
            return False
        
        # Map scene position to oscillator view coordinates
        view_pos = self.oscillator_vb.mapSceneToView(scene_pos)
        
        # Get current view range for threshold calculations
        x_range = self.oscillator_vb.viewRange()[0]
        y_range = self.oscillator_vb.viewRange()[1]
        
        # Use more generous thresholds for easier grabbing
        x_threshold = (x_range[1] - x_range[0]) * 0.05  # 5% of X range
        y_threshold = (y_range[1] - y_range[0]) * 0.15  # 15% of Y range
        
        # Check each oscillator item
        for item in self._oscillator_indicator_lines:
            if isinstance(item, pg.PlotCurveItem):
                # For line items, check if mouse is near the line
                data = item.getData()
                if data and len(data) >= 2:
                    x_data, y_data = data[0], data[1]
                    if x_data is not None and y_data is not None:
                        # Find the closest point on the line
                        for i in range(len(x_data)):
                            if np.isfinite([x_data[i], y_data[i]]).all():
                                dx = abs(view_pos.x() - x_data[i])
                                dy = abs(view_pos.y() - y_data[i])
                                
                                if dx < x_threshold and dy < y_threshold:
                                    return True
                                    
            elif isinstance(item, pg.ScatterPlotItem):
                # For scatter items, check proximity to any point
                data = item.getData()
                if data and len(data) >= 2:
                    x_data, y_data = data[0], data[1]
                    if x_data is not None and y_data is not None:
                        for x, y in zip(x_data, y_data):
                            if np.isfinite([x, y]).all():
                                dx = abs(view_pos.x() - x)
                                dy = abs(view_pos.y() - y)
                                
                                if dx < x_threshold and dy < y_threshold:
                                    return True
        
        return False

    def mousePressEvent(self, ev):
        """Override to detect clicks on oscillator."""
        # Map widget position to scene coordinates
        scene_pos = self.plotItem.vb.mapToScene(ev.pos())
        
        # Check if clicking on oscillator (pass scene position)
        if self._is_mouse_over_oscillator(scene_pos):
            self._oscillator_drag_active = True
            self._drag_start_pos = ev.pos()
            ev.accept()
            return
        
        # Otherwise use default behavior
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        """Override to handle oscillator dragging and cursor changes."""
        if self._oscillator_drag_active and hasattr(self, '_drag_start_pos'):
            # Calculate drag delta
            delta = ev.pos() - self._drag_start_pos
            self._drag_start_pos = ev.pos()
            
            # Update oscillator vertical offset
            current_offset = self.oscillator_vb.get_vertical_offset()
            new_offset = current_offset + delta.y()
            self.oscillator_vb.set_vertical_offset(new_offset)
            
            ev.accept()
            return
        
        # Check if cursor is over oscillator to change cursor
        if self._oscillator_indicator_lines:
            scene_pos = self.plotItem.vb.mapToScene(ev.pos())
            is_over = self._is_mouse_over_oscillator(scene_pos)
            
            if is_over and not self._cursor_over_oscillator:
                # Change cursor to indicate draggable
                self.setCursor(QtCore.Qt.SizeVerCursor)  # Vertical resize cursor
                self._cursor_over_oscillator = True
            elif not is_over and self._cursor_over_oscillator:
                # Restore default cursor
                self.setCursor(QtCore.Qt.ArrowCursor)
                self._cursor_over_oscillator = False

        # Update date label position based on mouse x-coordinate
        if self._date_label and self.chart_settings.get('show_date_label', True):
            self._update_date_label(ev.pos().x())

        # Otherwise use default behavior
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        """Override to end oscillator dragging."""
        if self._oscillator_drag_active:
            self._oscillator_drag_active = False
            if hasattr(self, '_drag_start_pos'):
                delattr(self, '_drag_start_pos')

            # Reset cursor if not still over oscillator
            scene_pos = self.plotItem.vb.mapToScene(ev.pos())
            if not self._is_mouse_over_oscillator(scene_pos):
                self.setCursor(QtCore.Qt.ArrowCursor)
                self._cursor_over_oscillator = False

            ev.accept()
            return

        # Otherwise use default behavior
        super().mouseReleaseEvent(ev)

    def leaveEvent(self, ev):
        """Override to hide date label when mouse leaves the chart."""
        # Hide date label when mouse leaves
        if self._date_label:
            self._date_label.hide()

        super().leaveEvent(ev)

    def resizeEvent(self, ev):
        """Override to update price label position on resize."""
        super().resizeEvent(ev)
        # Update price label position after resize (if it exists)
        if hasattr(self, '_price_label') and self._price_label and self._price_label.isVisible():
            self._update_price_label()

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
        # Remove old legend first
        if hasattr(self, 'legend') and self.legend is not None:
            try:
                self.legend.scene().removeItem(self.legend)
            except:
                pass
            self.legend = None

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

        # Hide date label if it exists
        if self._date_label is not None:
            self._date_label.hide()

        # Hide oscillator axis when cleared
        self.oscillator_axis.hide()

        # Reset oscillator position
        self.oscillator_vb.set_vertical_offset(0)

        # Reset cursor state
        self._cursor_over_oscillator = False
        self.setCursor(QtCore.Qt.ArrowCursor)

        # Re-add legend after clear
        self.legend = self.addLegend(offset=(10, 10))

    def _update_oscillator_geometry(self, *args):
        """Update the oscillator ViewBox to match price ViewBox geometry with offset."""
        # Get the price ViewBox geometry
        price_rect = self.price_vb.sceneBoundingRect()
        
        # Get vertical offset (in scene coordinates)
        offset = self.oscillator_vb.get_vertical_offset()
        
        # Position oscillator ViewBox with the same dimensions but offset vertically
        # The offset allows the oscillator to be positioned anywhere over the price chart
        self.oscillator_vb.setGeometry(price_rect.translated(0, offset))

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
        self._price_label.setAlignment(Qt.AlignCenter)
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
                padding: 2px 4px;
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
        axis_rect = self.getAxis('right').geometry()

        # Position label on the y-axis at the price level
        label_height = self._price_label.height()
        x_pos = int(axis_rect.left())
        y_pos = int(widget_point.y() - label_height / 2)

        self._price_label.move(x_pos, y_pos)
        self._price_label.show()

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
        text_color = self._get_label_text_color()

        bg_color = f"rgb({accent_color[0]}, {accent_color[1]}, {accent_color[2]})"
        fg_color = f"rgb({text_color[0]}, {text_color[1]}, {text_color[2]})"

        self._date_label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {fg_color};
                border: none;
                padding: 2px 4px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)

    def _update_date_label(self, mouse_x: int):
        """Update date label position and text based on mouse x-coordinate.

        Args:
            mouse_x: Mouse x-coordinate in widget pixels
        """
        if not self._date_label or not self.chart_settings.get('show_date_label', True):
            if self._date_label:
                self._date_label.hide()
            return

        if self.data is None or self.data.empty:
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
        axis_rect = self.getAxis('bottom').geometry()

        # Position label on the bottom axis at the mouse x-position
        label_width = self._date_label.width()
        x_pos = int(mouse_x - label_width / 2)
        y_pos = int(axis_rect.top())

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

        # Update date label style if it exists
        if self._date_label:
            self._update_date_label_style()

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

        # Update background
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

        self.bottom_axis.set_index(df_plot.index)
        x = np.arange(len(df_plot), dtype=float)

        chart_type = (chart_type or "Candles").strip()

        if chart_type == "Line":
            if "Close" not in df_plot.columns:
                raise ValueError(f"Missing 'Close' column. Columns: {list(df_plot.columns)}")

            y = df_plot["Close"].astype(float).to_numpy()
            
            # Get line settings (color, width, style)
            line_settings = self.get_line_settings()
            pen = pg.mkPen(color=line_settings['color'], width=line_settings['width'], style=line_settings['style'])
            self._line = self.plot(x, y, pen=pen, name=f"{ticker}")
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

        # Plot indicators
        if indicators:
            self._plot_indicators(x, df, indicators)

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
        """
        from app.services.indicator_service import IndicatorService
        
        color_idx = 0
        has_oscillators = False
        
        for indicator_name, indicator_info in indicators.items():
            # Extract data and appearance
            indicator_df = indicator_info.get("data")
            appearance = indicator_info.get("appearance", {})
            
            if indicator_df is None or indicator_df.empty:
                continue
            
            # Determine if this is an oscillator or overlay
            is_oscillator = IndicatorService.is_overlay(indicator_name) == False
            
            if is_oscillator:
                has_oscillators = True
            
            # Get appearance settings with defaults
            custom_color = appearance.get("color", None)
            line_width = appearance.get("line_width", 2)
            line_style = appearance.get("line_style", QtCore.Qt.SolidLine)
            marker_shape = appearance.get("marker_shape", "o")
            marker_size = appearance.get("marker_size", 10)
            
            # Select the appropriate ViewBox
            target_vb = self.oscillator_vb if is_oscillator else self.price_vb
            
            # Plot each column in the indicator dataframe
            for col in indicator_df.columns:
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
                        name=col,
                    )
                    target_vb.addItem(scatter)
                    
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
                    line = pg.PlotCurveItem(x=x, y=y, pen=pen, name=col)
                    target_vb.addItem(line)
                    
                    if is_oscillator:
                        self._oscillator_indicator_lines.append(line)
                    else:
                        self._price_indicator_lines.append(line)
                
                color_idx += 1
        
        # Show/hide oscillator axis based on whether we have oscillators
        if has_oscillators:
            self.oscillator_axis.show()
            # Auto-fit oscillator range
            self._auto_fit_oscillator_range()
        else:
            self.oscillator_axis.hide()

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
        
        if all_y_values:
            y_min = np.min(all_y_values)
            y_max = np.max(all_y_values)
            
            # Add some padding
            padding = (y_max - y_min) * 0.1
            self.oscillator_vb.setYRange(y_min - padding, y_max + padding, padding=0)