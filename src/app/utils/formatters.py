from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.config import (
    PRICE_FORMAT_BILLION,
    PRICE_FORMAT_THOUSAND,
    PRICE_FORMAT_ONE,
)


def format_price_usd(value: float) -> str:
    """
    Format a price value as USD string.
    
    Args:
        value: Price value to format
        
    Returns:
        Formatted price string (e.g., "$1,234.56")
    """
    if not np.isfinite(value):
        return ""
    
    if value >= PRICE_FORMAT_BILLION:
        return f"${value:,.0f}"
    if value >= PRICE_FORMAT_THOUSAND:
        return f"${value:,.2f}"
    if value >= PRICE_FORMAT_ONE:
        return f"${value:,.2f}"
    return f"${value:.6f}"


def format_date(dt: pd.Timestamp, format_str: str = "%Y-%m-%d") -> str:
    """
    Format a pandas Timestamp as a date string.
    
    Args:
        dt: Timestamp to format
        format_str: strftime format string
        
    Returns:
        Formatted date string
    """
    if dt is None or pd.isna(dt):
        return ""
    return dt.strftime(format_str)


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format a value as a percentage.
    
    Args:
        value: Value to format (e.g., 0.05 for 5%)
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string (e.g., "5.00%")
    """
    if not np.isfinite(value):
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def format_number(value: float, decimals: int = 2) -> str:
    """
    Format a number with thousands separators.
    
    Args:
        value: Number to format
        decimals: Number of decimal places
        
    Returns:
        Formatted number string
    """
    if not np.isfinite(value):
        return "N/A"
    return f"{value:,.{decimals}f}"


def format_large_number(value: float) -> str:
    """
    Format large numbers with abbreviations (K, M, B, T).
    
    Args:
        value: Number to format
        
    Returns:
        Formatted string (e.g., "1.5M", "2.3B")
    """
    if not np.isfinite(value):
        return "N/A"
    
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    
    if abs_value >= 1e12:
        return f"{sign}{abs_value/1e12:.2f}T"
    elif abs_value >= 1e9:
        return f"{sign}{abs_value/1e9:.2f}B"
    elif abs_value >= 1e6:
        return f"{sign}{abs_value/1e6:.2f}M"
    elif abs_value >= 1e3:
        return f"{sign}{abs_value/1e3:.2f}K"
    else:
        return f"{sign}{abs_value:.2f}"


def format_metric_value(value, format_type: str, decimals: int = 2) -> str:
    """
    Format a financial metric value for display in tables.

    Used by Performance Metrics, Tracking Error Volatility, and other modules
    that display financial statistics in tabular form.

    Args:
        value: The value to format (float, tuple, or None)
        format_type: One of:
            - "percent": Multiply by 100, show as percentage (e.g., 0.15 → "15.00")
            - "ratio": Show as ratio (e.g., 1.234 → "1.23")
            - "decimal": Show as decimal (e.g., 0.567 → "0.57")
            - "decimal4": Show with 4 decimal places (e.g., 0.5678 → "0.5678")
            - "capture": Handle tuple (up_capture, down_capture) → ratio
        decimals: Number of decimal places (default 2, ignored for decimal4)

    Returns:
        Formatted string:
        - Empty string "" for None/NaN (missing data)
        - "--" for zero values (indicates zero, not missing)
        - Formatted number otherwise
    """
    # Return blank for None (missing data)
    if value is None:
        return ""

    # Handle tuple for capture ratio
    if format_type == "capture" and isinstance(value, tuple):
        return _format_capture_ratio(value, decimals)

    # Handle NaN (missing data) - show blank
    if isinstance(value, float) and np.isnan(value):
        return ""

    # Handle actual zero - show "--"
    if value == 0:
        return "--"

    # Format by type
    if format_type == "percent":
        return f"{value * 100:.{decimals}f}"
    elif format_type == "ratio":
        return f"{value:.{decimals}f}"
    elif format_type == "decimal":
        return f"{value:.{decimals}f}"
    elif format_type == "decimal4":
        return f"{value:.4f}"
    else:
        return str(value)


def _format_capture_ratio(value: tuple, decimals: int = 2) -> str:
    """
    Format capture ratio tuple (up_capture, down_capture) as a ratio.

    Values > 1 indicate portfolio captures more upside than downside.

    Args:
        value: Tuple of (up_capture, down_capture) as percentages
        decimals: Number of decimal places

    Returns:
        Formatted ratio string, or blank/-- for invalid data
    """
    if not isinstance(value, tuple) or len(value) != 2:
        return ""

    up, down = value

    # Check for NaN
    if (isinstance(up, float) and np.isnan(up)) or (
        isinstance(down, float) and np.isnan(down)
    ):
        return ""

    # Check for zero denominator
    if down == 0:
        return "--"

    return f"{up / down:.{decimals}f}"
