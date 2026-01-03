"""
Live bar aggregator for WebSocket minute bars.

Aggregates incoming minute bars into a single daily OHLCV bar
for display on daily interval charts.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    import pandas as pd


class LiveBarAggregator:
    """
    Aggregates minute bars into a daily OHLCV bar.

    When receiving minute bars from WebSocket, this class maintains
    a running aggregation for "today's" bar:
    - Open: First bar's open price
    - High: Maximum high across all bars
    - Low: Minimum low across all bars
    - Close: Most recent bar's close price
    - Volume: Sum of all bar volumes

    Usage:
        aggregator = LiveBarAggregator()
        daily_bar = aggregator.add_minute_bar(minute_bar_data)
        # daily_bar is a dict with OHLCV for today
    """

    def __init__(self):
        self._current_date: Optional[date] = None
        self._today_bar: Optional[Dict[str, Any]] = None
        self._bar_count: int = 0

    def add_minute_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a minute bar and return the updated daily aggregation.

        Args:
            bar: Dict with keys: open, high, low, close, volume, start_ts

        Returns:
            Dict with aggregated daily OHLCV: Open, High, Low, Close, Volume, Date
        """
        # Extract timestamp and determine date
        start_ts = bar.get("start_ts", 0)
        if start_ts:
            bar_date = datetime.fromtimestamp(start_ts / 1000).date()
        else:
            bar_date = datetime.now().date()

        # Check if we need to reset for a new day
        if self._current_date != bar_date:
            self._reset_aggregation(bar_date)

        # Update aggregation
        o = bar.get("open")
        h = bar.get("high")
        l = bar.get("low")
        c = bar.get("close")
        v = bar.get("volume", 0)

        if self._today_bar is None:
            # First bar of the day
            self._today_bar = {
                "Open": o,
                "High": h,
                "Low": l,
                "Close": c,
                "Volume": v,
                "Date": bar_date,
            }
        else:
            # Update existing aggregation
            # Open stays as first bar's open
            self._today_bar["High"] = max(self._today_bar["High"], h) if h else self._today_bar["High"]
            self._today_bar["Low"] = min(self._today_bar["Low"], l) if l else self._today_bar["Low"]
            self._today_bar["Close"] = c if c else self._today_bar["Close"]
            self._today_bar["Volume"] = self._today_bar["Volume"] + (v or 0)

        self._bar_count += 1

        return self._today_bar.copy()

    def _reset_aggregation(self, new_date: date) -> None:
        """Reset aggregation for a new day."""
        self._current_date = new_date
        self._today_bar = None
        self._bar_count = 0

    def get_current_bar(self) -> Optional[Dict[str, Any]]:
        """Get the current aggregated bar without adding new data."""
        return self._today_bar.copy() if self._today_bar else None

    def get_bar_count(self) -> int:
        """Get the number of minute bars aggregated today."""
        return self._bar_count

    def reset(self) -> None:
        """Reset the aggregator completely."""
        self._current_date = None
        self._today_bar = None
        self._bar_count = 0

    def to_series(self) -> "pd.Series":
        """
        Convert current aggregated bar to a pandas Series.

        Returns:
            pd.Series with OHLCV data, or empty Series if no data
        """
        import pandas as pd

        if self._today_bar is None:
            return pd.Series(dtype=float)

        return pd.Series({
            "Open": self._today_bar["Open"],
            "High": self._today_bar["High"],
            "Low": self._today_bar["Low"],
            "Close": self._today_bar["Close"],
            "Volume": self._today_bar["Volume"],
        }, name=pd.Timestamp(self._today_bar["Date"]))
