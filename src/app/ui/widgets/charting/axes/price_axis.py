"""Price Axis - Right axis with USD formatting and log scale support."""

import numpy as np
from .draggable_axis import DraggableAxisItem
from app.utils.formatters import format_price_usd


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
