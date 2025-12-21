from __future__ import annotations

import math
from typing import Tuple

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui


# -----------------------------
# Axes
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

    @staticmethod
    def _format_usd(value: float) -> str:
        if not np.isfinite(value):
            return ""
        if value >= 1e9:
            return f"${value:,.0f}"
        if value >= 1e3:
            return f"${value:,.2f}"
        if value >= 1:
            return f"${value:,.2f}"
        return f"${value:.6f}"

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
                out.append(self._format_usd(price))
            else:
                # v is already price
                out.append(self._format_usd(float(v)))

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
                out.append(dt.strftime("%Y-%m-%d"))
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
# Candles
# -----------------------------
class CandlestickItem(pg.GraphicsObject):
    """
    data rows: [x, open, close, low, high]
    x is an integer index (0..N-1) for uniform spacing
    """

    def __init__(self, data, bar_width: float = 0.6):
        super().__init__()
        self.data = np.array(data, dtype=float)
        self.bar_width = float(bar_width)
        self._picture = None
        self._generate_picture()

    def setData(self, data):
        self.data = np.array(data, dtype=float)
        self._generate_picture()
        self.update()

    def _generate_picture(self):
        picture = QtGui.QPicture()
        p = QtGui.QPainter(picture)

        if self.data.size == 0:
            p.end()
            self._picture = picture
            return

        up_color = (76, 153, 0)
        down_color = (200, 50, 50)
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
# Chart
# -----------------------------
class PriceChart(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.showGrid(x=True, y=True)
        self.setLabel("bottom", "Time")

        # bottom axis is now draggable + date formatted
        self.bottom_axis = DraggableIndexDateAxisItem(orientation="bottom")
        self.right_axis = DraggablePriceAxisItem(orientation="right")

        self.setAxisItems({"bottom": self.bottom_axis, "right": self.right_axis})
        self.showAxis("right")
        self.hideAxis("left")

        self.setLabel("right", "Price (USD)")

        vb = self.getViewBox()
        vb.setMouseEnabled(x=True, y=True)

        self._candles = None
        self._line = None

        self.candle_width = 0.6
        self._has_initialized_view = False

        self._scale_mode: str = "regular"

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

    # -----------------------------
    # View helpers
    # -----------------------------
    def _get_visible_date_window(self) -> Tuple[pd.Timestamp | None, pd.Timestamp | None]:
        if not self.bottom_axis._index_to_dt:
            return None, None

        (x0, x1), _ = self.getViewBox().viewRange()
        n = len(self.bottom_axis._index_to_dt)

        i0 = int(np.clip(round(x0), 0, n - 1))
        i1 = int(np.clip(round(x1), 0, n - 1))

        return self.bottom_axis._index_to_dt[i0], self.bottom_axis._index_to_dt[i1]

    @staticmethod
    def _date_to_index(df: pd.DataFrame, dt: pd.Timestamp) -> int:
        dt = pd.Timestamp(dt)
        return int(df.index.get_indexer([dt], method="nearest")[0])

    def _safe_set_yrange(self, y_min: float, y_max: float) -> None:
        vb = self.getViewBox()
        if y_max <= y_min:
            y_max = y_min + 1e-6

        pad = (y_max - y_min) * 0.05 if y_max != y_min else max(1e-6, abs(y_max) * 0.001)
        vb.setYRange(y_min - pad, y_max + pad, padding=0)

    def _apply_date_window(self, df_plot: pd.DataFrame, left_dt: pd.Timestamp, right_dt: pd.Timestamp) -> None:
        i0 = self._date_to_index(df_plot, left_dt)
        i1 = self._date_to_index(df_plot, right_dt)
        if i0 > i1:
            i0, i1 = i1, i0

        vb = self.getViewBox()
        vb.setXRange(i0, i1, padding=0)

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
        start = end - pd.Timedelta(days=365)
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
    ) -> None:
        if df is None or df.empty:
            self.clear()
            return

        prev_left_dt, prev_right_dt = self._get_visible_date_window()

        scale_key = (scale or "Regular").strip().lower()
        self._scale_mode = "log" if scale_key.startswith("log") else "regular"

        df_plot = self._to_log10_prices(df) if self._scale_mode == "log" else df

        # USD tick formatting for BOTH regular + log
        self.right_axis.set_scale_mode(self._scale_mode)

        self.setLabel("right", "Price (USD)" if self._scale_mode == "regular" else "Price (USD, log scale)")

        self.clear()
        self._candles = None
        self._line = None

        self.bottom_axis.set_index(df_plot.index)
        x = np.arange(len(df_plot), dtype=float)

        chart_type = (chart_type or "Candles").strip()

        if chart_type == "Line":
            if "Close" not in df_plot.columns:
                raise ValueError(f"Missing 'Close' column. Columns: {list(df_plot.columns)}")

            y = df_plot["Close"].astype(float).to_numpy()
            self._line = self.plot(x, y, name=f"{ticker} Close")
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
            self._candles = CandlestickItem(data, bar_width=self.candle_width)
            self.addItem(self._candles)

        # restore window or init view
        if prev_left_dt is not None and prev_right_dt is not None:
            self._apply_date_window(df_plot, prev_left_dt, prev_right_dt)
        elif not self._has_initialized_view:
            self._set_view_last_year(df_plot)
            self._has_initialized_view = True
