"""Date Index Axis - Bottom axis showing dates for integer indices."""

import math
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore
from app.utils.formatters import format_date


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
