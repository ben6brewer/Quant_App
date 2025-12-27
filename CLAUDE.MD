# Quant Terminal - Project Guide

## Project Overview

**Quant Terminal** is a Bloomberg Terminal-inspired desktop application for investing, charting, and technical analysis. Built with Python and PySide6 (Qt), it provides professional-grade charting, custom indicators, and equation-based price analysis.

- **Version**: 0.1.0 (early stage)
- **Status**: Core charting complete, portfolio and other modules in development
- **Tech Stack**: Python 3.10+, PySide6, yfinance, pandas, numpy, pyqtgraph

## Architecture & Design Patterns

### UI Pattern: Hub-and-Spoke
- Main window (`HubWindow`) with sidebar navigation (200px fixed width)
- Stacked widget system for switching between modules
- Each module is a self-contained `QWidget`

### Separation of Concerns
```
src/app/
├── core/           # Configuration and cross-cutting concerns
│   ├── config.py           # Centralized app settings
│   └── theme_manager.py    # Dark/light theme switching
├── services/       # Business logic (stateless/singleton-like)
│   ├── market_data.py              # Yahoo Finance data fetching
│   ├── indicator_service.py        # Technical indicator calculations
│   └── ticker_equation_parser.py   # Parse math expressions with tickers
├── ui/             # User interface
│   ├── hub_window.py       # Main application window
│   ├── widgets/            # Reusable UI components
│   └── modules/            # Pluggable module sections
└── utils/          # Helper functions
```

### Data Flow
```
MarketDataService → IndicatorService → PriceChart
        ↓
TickerEquationParser (for expressions like =BTC-USD/SPX)
```

## Core Components

### HubWindow (`ui/hub_window.py`)
Main application window with sidebar navigation and module switching.
- Creates sidebar buttons for each module
- Manages stacked widget for module content
- Handles theme switching
- Default size: 1400x900px

### ChartModule (`ui/modules/chart/chart_module.py`)
Primary charting interface with:
- Ticker input (supports symbols and equations: `=BTC-USD/SPX`)
- Interval selector (daily, weekly, monthly, yearly)
- Chart type (Candles, Line)
- Scale selector (Regular, Logarithmic)
- Technical indicator panel with create/apply/delete
- Default ticker: BTC-USD

### IndicatorService (`services/indicator_service.py`)
Manages technical indicators without external TA libraries.
- **Overlays**: SMA, EMA, Bollinger Bands, VWAP
- **Oscillators**: RSI, MACD, ATR, Stochastic, OBV
- Custom user-created indicators
- Persistence: `~/.quant_terminal/custom_indicators.json`
- Multi-selection support

### TickerEquationParser (`services/ticker_equation_parser.py`)
Parses mathematical expressions combining tickers.
- Supported operations: `+`, `-`, `*`, `/`, `()`
- Examples:
  - `=BTC-USD*2` (multiply price by 2)
  - `=BTC-USD/SPX` (ratio of Bitcoin to S&P 500)
  - `=(BTC-USD+ETH-USD)/2` (average of two assets)
- Handles date alignment when combining multiple tickers
- Caches ticker data to avoid re-fetching

### MarketDataService (`services/market_data.py`)
Fetches historical OHLCV data via yfinance.
- Interval conversion: `daily→1d`, `weekly→1wk`, `monthly→1mo`, `yearly→1mo+resample`
- Supports periods: `"max"`, `"1y"`, `"6mo"`, etc.
- Handles MultiIndex columns and normalization

### ThemeManager (`core/theme_manager.py`)
Centralized theme management.
- **Dark theme** (default): `#1e1e1e` background, `#00d4ff` accent
- **Light theme**: `#ffffff` background, `#0066cc` accent
- Emits `theme_changed` signal for UI updates
- Provides stylesheets for all components

### PriceChart (`ui/widgets/price_chart.py`)
PyQtGraph-based charting widget.
- Renders candlestick and line charts
- Logarithmic and regular scaling
- Draggable axes for zoom
- Indicator overlay support
- Custom date/price axis formatting

## Key Features

### Ticker Equations
Use `=` prefix to write mathematical expressions with tickers:
```python
=BTC-USD              # Single ticker
=BTC-USD/SPX          # Ratio
=BTC-USD*2            # Scaled
=(BTC-USD+ETH-USD)/2  # Average
```

### Technical Indicators
- 9 built-in indicator types (SMA, EMA, RSI, MACD, etc.)
- Custom indicator creation with persistence
- Multiple indicators can be applied simultaneously
- Stored in: `~/.quant_terminal/custom_indicators.json`

### Charting
- Multiple timeframes: daily, weekly, monthly, yearly
- Chart types: Candlestick, Line
- Scaling: Regular, Logarithmic
- Interactive zoom via axis dragging
- Real-time data from Yahoo Finance

## Development Guidelines

### Code Style

**Type Hints** (gradually adopting):
```python
def fetch_data(ticker: str, interval: str) -> pd.DataFrame:
    """Fetch OHLCV data for ticker."""
    ...
```

**Minimal Documentation**:
- ✅ Add docstrings for: Business logic, complex algorithms, public APIs
- ❌ Skip docstrings for: Simple UI setup, getters/setters, obvious widgets
- One-line docstrings are fine

**Qt Conventions**:
```python
# Signals: snake_case
theme_changed = Signal(str)
ticker_updated = Signal(str)

# Slots: prefix with _on_
def _on_theme_changed(self, theme_name: str):
    ...

# Private widgets: prefix with _
self._chart_widget = PriceChart()
```

**File Organization**:
- One widget class per file in `ui/widgets/`
- One module per file in `ui/modules/`
- Services are stateless/singleton-like

### Testing Strategy

**Current**: Manual testing through UI

**Future** (pytest):
- ✅ Unit test: Services, parsers, calculators, data transformations
- ❌ Skip testing: Widget initialization, simple UI layouts
- Mock external dependencies (yfinance) in tests
- Use pytest-qt for Qt components

## Common Development Tasks

### Running the App
```bash
# From project root
python -m app.main
```

### Installing Dependencies
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

### Adding a New Module
1. Create module class in `ui/modules/` inheriting from `QWidget`
2. Implement the module UI and logic
3. Add to `HubWindow` initialization in `main.py`:
   ```python
   from app.ui.modules.new_module import NewModule

   # In HubWindow.__init__
   new_module = NewModule()
   self.stacked_widget.addWidget(new_module)
   ```
4. Add sidebar button in `HubWindow._setup_sidebar()`

### Adding a New Indicator
1. Add calculation method to `IndicatorService`:
   ```python
   def calculate_new_indicator(self, data: pd.DataFrame, param: int) -> pd.Series:
       """Calculate new indicator."""
       return data['Close'].rolling(window=param).mean()
   ```
2. Add to `INDICATOR_TYPES` dict in `IndicatorService`
3. Update `CreateIndicatorDialog` if new parameters needed

### Adding Config Settings
- Add to `core/config.py`
- Access via: `from app.core.config import CONFIG`

## Current Development Focus

### Near-Term Priorities
1. **Data Management & Persistence**: Improve caching, storage, and data handling
2. **Modularity**: Refactor architecture to make new module development easier
3. **Portfolio Module**: Next major feature to implement

### Placeholder Modules (Coming Soon)
- Portfolio (investment tracking)
- Watchlist (real-time monitoring)
- News (financial news aggregation)
- Screener (stock/crypto screening)
- Analysis (valuation tools)
- Settings (application preferences)

## Configuration

**Default Settings** (`core/config.py`):
- Window: 1400x900px
- Sidebar: 200px fixed width
- Default ticker: BTC-USD
- Default interval: daily
- Default theme: dark
- Default chart type: Candles
- Default scale: Logarithmic
- Chart period: Last 365 days

**User Data**:
- Indicators: `~/.quant_terminal/custom_indicators.json`

## Git Workflow

- **Main branch**: `main`
- **Active development**: `bb` branch
- **Recent work**: Indicators, interval bug fixes, refactoring

## Project Entry Point

**Main entry**: `src/app/main.py`
```python
# Creates QApplication
# Initializes ThemeManager
# Sets up HubWindow with modules
# Starts event loop
```

---

**Pro Tips**:
- The equation parser tokenizes and evaluates using RPN (Reverse Polish Notation)
- Indicators can be overlays (on price chart) or oscillators (separate pane)
- Theme switching is handled via `ThemeManager` signals, not direct stylesheet updates
- All market data flows through `MarketDataService` for consistency
