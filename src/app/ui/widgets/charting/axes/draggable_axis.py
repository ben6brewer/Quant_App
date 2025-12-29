"""Draggable Axis - Base axis with drag-to-zoom support."""

import math
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore


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
