from __future__ import annotations

from pathlib import Path

"""
Central configuration for the Quant Terminal application.
All application-wide constants and settings should be defined here.
"""

# Application metadata
APP_NAME = "Quant Terminal"
APP_VERSION = "0.1.0"
APP_ORGANIZATION = "QuantApp"

# Window settings
DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 900

# Chart settings
DEFAULT_TICKER = "BTC-USD"
DEFAULT_INTERVAL = "daily"
DEFAULT_CHART_TYPE = "Candles"
DEFAULT_SCALE = "Logarithmic"
CANDLE_BAR_WIDTH = 0.6

# Data fetching
DEFAULT_PERIOD = "max"
DATA_FETCH_THREADS = True
SHOW_DOWNLOAD_PROGRESS = False

# Interval mappings for yfinance
INTERVAL_MAP = {
    "daily": "1d",
    "weekly": "1wk",
    "monthly": "1mo",
    "yearly": "1y",
}

# Chart intervals
CHART_INTERVALS = ["daily", "weekly", "monthly", "yearly"]
CHART_TYPES = ["Candles", "Line"]
CHART_SCALES = ["Regular", "Logarithmic"]

# Theme settings
DEFAULT_THEME = "dark"
AVAILABLE_THEMES = ["dark", "light"]

# UI Colors - Dark Theme
DARK_PRIMARY_COLOR = "#00d4ff"
DARK_BACKGROUND_COLOR = "#1e1e1e"
DARK_SIDEBAR_COLOR = "#2d2d2d"
DARK_TEXT_COLOR = "#ffffff"
DARK_SECONDARY_TEXT_COLOR = "#cccccc"

# UI Colors - Light Theme
LIGHT_PRIMARY_COLOR = "#0066cc"
LIGHT_BACKGROUND_COLOR = "#ffffff"
LIGHT_SIDEBAR_COLOR = "#f5f5f5"
LIGHT_TEXT_COLOR = "#000000"
LIGHT_SECONDARY_TEXT_COLOR = "#333333"

# Module sections and navigation
MODULE_SECTIONS = {
    "Charting": [
        {"id": "charts", "label": "Charts", "emoji": "📊"}
    ],
    "Portfolio": [
        {"id": "portfolio", "label": "Portfolio", "emoji": "💼"},
        {"id": "watchlist", "label": "Watchlist", "emoji": "👁"}
    ],
    "Market Data": [
        {"id": "news", "label": "News", "emoji": "📰"},
        {"id": "screener", "label": "Screener", "emoji": "🔍"}
    ],
    "Analysis": [
        {"id": "analysis", "label": "Analysis", "emoji": "📈"}
    ]
}

# Flatten all modules for backward compatibility
ALL_MODULES = [module for section_modules in MODULE_SECTIONS.values() for module in section_modules]

# Tile settings
TILE_SCREENSHOT_DIR = Path.home() / ".quant_terminal" / "screenshots"
TILE_WIDTH = 280
TILE_HEIGHT = 200
TILE_COLS = 4
TILE_SPACING = 20

# Chart view settings
DEFAULT_VIEW_PERIOD_DAYS = 365  # Show last year by default
VIEW_PADDING_PERCENT = 0.05  # 5% padding on Y-axis

# Price formatting thresholds
PRICE_FORMAT_BILLION = 1e9
PRICE_FORMAT_THOUSAND = 1e3
PRICE_FORMAT_ONE = 1

# Equation parser settings
EQUATION_OPERATORS = {"+", "-", "*", "/"}
EQUATION_PREFIX = "="

# Error messages
ERROR_EMPTY_TICKER = "Ticker is empty."
ERROR_NO_DATA = "No data returned for ticker '{ticker}'."
ERROR_INVALID_EXPRESSION = "Invalid expression"
ERROR_NO_OVERLAPPING_DATES = "No overlapping dates found between tickers"

# Logging (for future implementation)
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
