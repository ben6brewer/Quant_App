"""Volume Axis - Axis with human-readable volume formatting."""

from .draggable_axis import DraggableAxisItem


class VolumeAxisItem(DraggableAxisItem):
    """
    Axis that formats large volume numbers with K/M/B suffixes.

    Examples:
        1,500,000,000 -> "1.5B"
        250,000,000 -> "250M"
        10,000 -> "10K"
        500 -> "500"
    """

    def __init__(self, orientation: str, *args, **kwargs):
        super().__init__(orientation=orientation, *args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        """Format tick values with K/M/B suffixes for readability."""
        strings = []
        for v in values:
            if v is None or v != v:  # Check for NaN
                strings.append("")
                continue

            abs_v = abs(v)

            if abs_v >= 1_000_000_000:
                # Billions
                formatted = f"{v / 1_000_000_000:.1f}B"
            elif abs_v >= 1_000_000:
                # Millions
                formatted = f"{v / 1_000_000:.1f}M"
            elif abs_v >= 1_000:
                # Thousands
                formatted = f"{v / 1_000:.1f}K"
            else:
                # Small numbers - show as-is
                formatted = f"{v:.0f}"

            # Clean up trailing .0 (e.g., "1.0B" -> "1B")
            if ".0" in formatted:
                formatted = formatted.replace(".0", "")

            strings.append(formatted)

        return strings
