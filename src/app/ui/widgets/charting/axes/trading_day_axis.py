"""Trading Day Axis - Bottom axis for projected trading days."""

from datetime import datetime, timedelta
from typing import Optional

from .draggable_axis import DraggableAxisItem


class DraggableTradingDayAxisItem(DraggableAxisItem):
    """
    Bottom axis that displays projected dates based on trading day indices.

    Supports:
    - Mapping trading day index (0..N) to projected calendar date
    - Drag-to-zoom on X axis
    - Smart date formatting based on zoom level
    """

    def __init__(self, orientation: str = "bottom", *args, **kwargs):
        super().__init__(orientation=orientation, *args, **kwargs)
        self._start_date: datetime = datetime.now()
        self._n_periods: int = 252  # Default 1 year

    def set_start_date(self, start_date: datetime) -> None:
        """Set the simulation start date."""
        self._start_date = start_date

    def set_n_periods(self, n_periods: int) -> None:
        """Set the total number of trading periods for range calculation."""
        self._n_periods = n_periods

    def _trading_day_to_calendar(self, trading_day: int) -> Optional[datetime]:
        """Convert trading day index to approximate calendar date."""
        if trading_day < 0:
            return None
        # Approximately 252 trading days per year
        # Add ~1.4 calendar days per trading day (365/252)
        calendar_days = int(trading_day * 365 / 252)
        return self._start_date + timedelta(days=calendar_days)

    def tickStrings(self, values, scale, spacing):
        """Format tick values as projected dates in yyyy-mm-dd format."""
        out: list[str] = []

        for v in values:
            try:
                trading_day = int(round(v))
                date = self._trading_day_to_calendar(trading_day)
                if date is None:
                    out.append("")
                    continue

                # Consistent yyyy-mm-dd format
                out.append(date.strftime("%Y-%m-%d"))
            except (ValueError, OverflowError):
                out.append("")
        return out
