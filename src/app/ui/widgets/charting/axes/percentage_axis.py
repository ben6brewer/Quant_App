"""Percentage Axis - Right axis with percentage formatting for return charts."""

from .draggable_axis import DraggableAxisItem


class DraggablePercentageAxisItem(DraggableAxisItem):
    """
    Right axis that displays percentage labels (+25.3%, -10.5%, etc.).

    Inherits drag-to-zoom from DraggableAxisItem.
    """

    def __init__(self, orientation: str = "right", *args, **kwargs):
        super().__init__(orientation=orientation, *args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        """Format tick values as percentages with sign."""
        out: list[str] = []
        for v in values:
            if not isinstance(v, (int, float)):
                out.append("")
                continue
            # Format with sign and 1 decimal place
            out.append(f"{v:+.1f}%")
        return out
