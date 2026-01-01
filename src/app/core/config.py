from __future__ import annotations

from pathlib import Path

"""
Central configuration for the Quant Terminal application.
All application-wide constants and settings should be defined here.
"""

# Application metadata
APP_NAME = "Quant Terminal"
APP_VERSION = "0.2.0"
APP_ORGANIZATION = "QuantApp"

# Window settings
DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 900

# Chart settings
DEFAULT_TICKER = "BTC-USD"
DEFAULT_INTERVAL = "Daily"
DEFAULT_CHART_TYPE = "Candles"
DEFAULT_SCALE = "Logarithmic"
CANDLE_BAR_WIDTH = 0.6

# Data fetching
DEFAULT_PERIOD = "max"
DATA_FETCH_THREADS = True
SHOW_DOWNLOAD_PROGRESS = False

# Interval mappings for yfinance (case-insensitive lookup)
INTERVAL_MAP = {
    "daily": "1d",
    "weekly": "1wk",
    "monthly": "1mo",
    "yearly": "1y",
    "Daily": "1d",
    "Weekly": "1wk",
    "Monthly": "1mo",
    "Yearly": "1y",
}

# Chart intervals (display names)
CHART_INTERVALS = ["Daily", "Weekly", "Monthly", "Yearly"]
CHART_TYPES = ["Candles", "Line"]
CHART_SCALES = ["Regular", "Logarithmic"]

# Theme settings
DEFAULT_THEME = "bloomberg"
AVAILABLE_THEMES = ["dark", "light", "bloomberg"]

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

# UI Colors - Bloomberg Theme
BLOOMBERG_PRIMARY_COLOR = "#FF8000"           # Bloomberg signature orange
BLOOMBERG_BACKGROUND_COLOR = "#000814"        # Deep navy-black
BLOOMBERG_PANEL_COLOR = "#0a1018"            # Slightly lighter panels
BLOOMBERG_SIDEBAR_COLOR = "#0d1420"          # Sidebar background
BLOOMBERG_TEXT_COLOR = "#e8e8e8"             # Primary text
BLOOMBERG_SECONDARY_TEXT_COLOR = "#b0b0b0"   # Secondary text
BLOOMBERG_ACCENT_YELLOW = "#FFD700"          # Amber/gold highlights
BLOOMBERG_BORDER_COLOR = "#1a2332"           # Subtle borders
BLOOMBERG_HOVER_COLOR = "#162030"            # Hover states
BLOOMBERG_GRID_COLOR = "#151f2e"             # Chart grid
BLOOMBERG_CANDLE_UP = "#00FF00"              # Green candles
BLOOMBERG_CANDLE_DOWN = "#FF0000"            # Red candles
BLOOMBERG_CHART_LINE = "#00D4FF"             # Cyan line charts

# Module sections and navigation
MODULE_SECTIONS = {
    "Charting": [
        {"id": "charts", "label": "Charts"}
    ],
    "Crypto": [
        {"id": "crypto_dashboard", "label": "Crypto Dashboard"},
        {"id": "defi", "label": "DeFi"},
        {"id": "nft", "label": "NFT Tracker"}
    ],
    "Portfolio": [
        {"id": "portfolio", "label": "Portfolio"},
        {"id": "portfolio_construction", "label": "Portfolio Construction"},
        {"id": "distribution_metrics", "label": "Distribution Metrics"},
        {"id": "monte_carlo", "label": "Monte Carlo"},
        {"id": "watchlist", "label": "Watchlist"}
    ],
    "Market Data": [
        {"id": "news", "label": "News"},
        {"id": "screener", "label": "Screener"}
    ],
    "Analysis": [
        {"id": "analysis", "label": "Analysis"}
    ]
}

# Flatten all modules for backward compatibility
ALL_MODULES = [module for section_modules in MODULE_SECTIONS.values() for module in section_modules]

# Tile settings
TILE_SCREENSHOT_DIR = Path.home() / ".quant_terminal" / "screenshots"
TILE_WIDTH = 453           # 3-column layout (16:9 aspect ratio, ~70% of original)
TILE_HEIGHT = 285          # 16:9 preview (453×255) + 30px label
TILE_COLS = 3              # 3-column grid
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
