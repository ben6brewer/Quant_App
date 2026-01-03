"""Candlestick Item - OHLC candlestick chart renderer."""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from app.core.config import CANDLE_BAR_WIDTH


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

    def update_last_candle(self, o: float, c: float, lo: float, hi: float) -> None:
        """
        Update only the last candle's OHLC values.

        This is used for incremental live updates to avoid full chart rebuild.
        The QPicture is regenerated, but this is still faster than recreating
        all chart objects via set_prices().

        Args:
            o: Open price
            c: Close price
            lo: Low price
            hi: High price
        """
        if self.data.size == 0:
            return
        last_idx = len(self.data) - 1
        x = self.data[last_idx, 0]
        self.data[last_idx] = [x, o, c, lo, hi]
        self._generate_picture()
        self.update()

    def append_candle(self, x: float, o: float, c: float, lo: float, hi: float) -> None:
        """
        Append a new candle to the data array.

        Used when a new trading day starts during live updates.

        Args:
            x: X-coordinate (index position)
            o: Open price
            c: Close price
            lo: Low price
            hi: High price
        """
        new_row = np.array([[x, o, c, lo, hi]], dtype=float)
        if self.data.size == 0:
            self.data = new_row
        else:
            self.data = np.vstack([self.data, new_row])
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
