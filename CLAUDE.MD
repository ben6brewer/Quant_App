# Quant Terminal - Project Guide

## Project Overview

**Quant Terminal** is a Bloomberg Terminal-inspired desktop application for investing, charting, and technical analysis. Built with Python and PySide6 (Qt), it provides professional-grade charting, custom indicators, and equation-based price analysis within a modular, tile-based navigation system designed to scale to 10-20+ specialized finance modules.

- **Version**: 0.1.0 (early stage)
- **Status**: Tile-based navigation complete, core charting complete, expanding module ecosystem
- **Tech Stack**: Python 3.10+, PySide6, yfinance, pandas, numpy, pyqtgraph

## Architecture & Design Patterns

### Tile-Based Navigation
The application uses a modern tile-based home screen for module discovery and navigation:
- **HomeScreen** serves as the central hub with module tiles displayed in a 3-column grid
- **Section Tabs** organize modules by category: Home (all modules), Charting, Crypto, Portfolio, Market Data, Analysis
- **Search Bar** enables real-time filtering across all modules (centered, 926px width = 2 tiles)
- **Favorites System** allows users to star modules, which are then sorted to the top of the grid
- **Module Tiles** (453×285px) display screenshot previews with emoji placeholders and star buttons
- Each tile click opens the module in full-screen mode with a "Home" button overlay to return to the hub

### Custom Title Bar Pattern
The application uses a frameless window with a custom title bar for complete theme control:
- **Frameless Window**: Uses `Qt.FramelessWindowHint` to remove OS-controlled title bar
- **Custom Title Bar**: 32px height bar with app title (left) and window controls (right)
- **Window Controls**: Minimize, Maximize/Restore, Close buttons with theme-aware styling
- **Title Label**: Transparent background to blend with title bar theme colors
- **Draggable**: Click and drag title bar to move window
- **Why**: Allows full theme customization (background, text, borders) vs OS-controlled title bar

### Separation of Concerns
```
src/app/
├── core/           # Configuration and cross-cutting concerns
│   ├── config.py           # Centralized app settings, MODULE_SECTIONS
│   └── theme_manager.py    # Theme switching (dark, light, bloomberg)
├── services/       # Business logic (stateless/singleton-like)
│   ├── market_data.py              # Yahoo Finance data fetching
│   ├── indicator_service.py        # Technical indicator calculations
│   ├── ticker_equation_parser.py   # Parse math expressions with tickers
│   └── favorites_service.py        # Favorites persistence
├── ui/             # User interface
│   ├── hub_window.py       # Main application window with custom title bar
│   ├── widgets/            # Reusable UI components
│   │   ├── home_screen.py          # Central navigation hub
│   │   ├── module_tile.py          # Individual module tiles
│   │   ├── module_tile_grid.py     # 3-column tile layout
│   │   ├── section_tab_bar.py      # Section tabs with Home
│   │   └── price_chart.py          # PyQtGraph charting
│   └── modules/            # Pluggable module sections
└── utils/          # Helper functions
    └── screenshot_manager.py       # Module preview image generation
```

### Data Flow
```
MarketDataService → IndicatorService → PriceChart
        ↓
TickerEquationParser (for expressions like =BTC-USD/SPX)
```

## Core Components

### HubWindow (`ui/hub_window.py`)
Main application window with custom title bar and tile-based navigation.
- **Frameless Window**: Custom title bar with minimize, maximize, close controls
- **Title Bar Dragging**: Click and drag to move window
- **Manages Stacked Widget**: Switches between HomeScreen and module containers
- **Theme Switching**: Applies theme-aware styling to title bar and all components
- **Module Containers**: Wraps each module with transparent overlay for "Home" button
- **Default Behavior**: Launches maximized

### HomeScreen (`ui/widgets/home_screen.py`)
Central navigation hub combining section tabs, search, and module tiles.
- **Section Tabs**: Home (default), Charting, Crypto, Portfolio, Market Data, Analysis
- **Centered Search Bar**: 926px width (2 tiles), real-time filtering
- **Module Tile Grid**: 3-column layout with favorites sorted to top
- **Settings Button**: Top-right corner to open Settings module
- **Special Behavior**: Clicking "Charting" tab auto-opens Charts module (single-module section)

### ModuleTile (`ui/widgets/module_tile.py`)
Individual tile widget for a module with screenshot preview and favorite star.
- **Fixed Size**: 453×285px (16:9 screenshot 453×255px + 30px label)
- **Screenshot Preview**: Loads from ScreenshotManager (emoji placeholders)
- **Star Button**: Top-right corner, toggles favorite status
- **Click Behavior**: Opens module in full-screen
- **Theme-Aware**: Border hover effects match theme accent color

### ModuleTileGrid (`ui/widgets/module_tile_grid.py`)
Grid layout for module tiles with filtering and sorting.
- **3-Column Layout**: Fixed at 3 columns (TILE_COLS=3)
- **20px Spacing**: Between tiles (TILE_SPACING=20)
- **Section Filtering**: Shows only modules from selected section
- **Search Filtering**: Case-insensitive match against module labels
- **Favorites-First Sorting**: Starred modules always at top, then alphabetical
- **Centered Grid**: Horizontal alignment centers the grid

### SectionTabBar (`ui/widgets/section_tab_bar.py`)
Horizontal tab bar for filtering modules by section.
- **Tabs**: Home, Charting, Crypto, Portfolio, Market Data, Analysis
- **Home Tab**: Default selected, shows all modules (unfiltered view)
- **Exclusive Selection**: Only one tab active at a time
- **Auto-Return to Home**: Clicking active tab again returns to Home view
- **Centered Layout**: Tabs centered with stretch on both sides

### FavoritesService (`services/favorites_service.py`)
Service for managing favorite modules with cross-session persistence.
- **Persistence**: Saves to `~/.quant_terminal/favorites.json`
- **Toggle Favorite**: Click star to add/remove from favorites
- **Auto-Save**: Writes to disk on every toggle
- **Singleton Pattern**: Class-level storage and methods
- **Initialization**: Called from `main.py` on app startup

### ScreenshotManager (`utils/screenshot_manager.py`)
Generates and loads module preview images.
- **Colored Placeholders**: Section-based color coding with emoji
- **Storage**: `~/.quant_terminal/screenshots/`
- **Auto-Generation**: Creates screenshot if not found
- **16:9 Aspect Ratio**: 453×255px images
- **Lazy Loading**: Only generates when tile is displayed

### ChartModule (`ui/modules/chart/chart_module.py`)
Primary charting interface with professional-grade features.
- **Ticker Input**: Supports symbols and equations (e.g., `=BTC-USD/SPX`)
- **Interval Selector**: Daily, weekly, monthly, yearly
- **Chart Type**: Candles, Line
- **Scale Selector**: Regular, Logarithmic
- **Technical Indicator Panel**: Create, apply, delete custom indicators
- **Default Ticker**: BTC-USD

### IndicatorService (`services/indicator_service.py`)
Manages technical indicators without external TA libraries.
- **Overlays**: SMA, EMA, Bollinger Bands, VWAP
- **Oscillators**: RSI, MACD, ATR, Stochastic, OBV
- **Custom Indicators**: User-created with persistence
- **Persistence**: `~/.quant_terminal/custom_indicators.json`
- **Multi-Selection**: Apply multiple indicators simultaneously

### TickerEquationParser (`services/ticker_equation_parser.py`)
Parses mathematical expressions combining tickers.
- **Supported Operations**: `+`, `-`, `*`, `/`, `()`
- **Examples**:
  - `=BTC-USD*2` (multiply price by 2)
  - `=BTC-USD/SPX` (ratio of Bitcoin to S&P 500)
  - `=(BTC-USD+ETH-USD)/2` (average of two assets)
- **Date Alignment**: Handles date alignment when combining multiple tickers
- **Caching**: Caches ticker data to avoid re-fetching
- **RPN Evaluation**: Tokenizes and evaluates using Reverse Polish Notation

### MarketDataService (`services/market_data.py`)
Fetches historical OHLCV data via yfinance.
- **Interval Conversion**: `daily→1d`, `weekly→1wk`, `monthly→1mo`, `yearly→1mo+resample`
- **Periods**: Supports `"max"`, `"1y"`, `"6mo"`, etc.
- **MultiIndex Handling**: Normalizes yfinance column formats
- **Thread Support**: Optional threaded fetching for responsiveness

### ThemeManager (`core/theme_manager.py`)
Centralized theme management.
- **Default Theme**: Bloomberg (`#0d1420` background, `#FF8000` orange accent)
- **Available Themes**: Dark (`#1e1e1e` background, `#00d4ff` cyan accent), Light (`#ffffff` background, `#0066cc` blue accent), Bloomberg
- **Signal-Based**: Emits `theme_changed` signal for UI updates
- **Provides Stylesheets**: For title bar, home button, content areas
- **All Components Theme-Aware**: Title bar, tiles, search bar, tabs, modules

### PriceChart (`ui/widgets/price_chart.py`)
PyQtGraph-based charting widget.
- **Candlestick Charts**: OHLC bars with customizable width
- **Line Charts**: Close price line
- **Logarithmic Scaling**: Regular and log scale support
- **Draggable Axes**: Click and drag to zoom/pan
- **Indicator Overlays**: Support for multiple indicator plots
- **Custom Formatting**: Date and price axis labels

## UI/UX Design Guidelines

### Custom Title Bar Pattern
**All new windows should use frameless design with custom title bars:**
- Set `self.setWindowFlags(Qt.FramelessWindowHint)` in window constructor
- Create 32px title bar with app title (left) and window controls (right)
- Add minimize, maximize/restore, close buttons with theme-aware styling
- Title label must have `background-color: transparent` in all themes
- Implement title bar dragging via `mousePressEvent` and `mouseMoveEvent`
- Close button should turn red (`#d32f2f`) on hover across all themes

### Transparent Overlays & Event Forwarding
**For overlaying UI elements on modules (e.g., Home button):**
- Use `TransparentOverlay` widget with `QStackedLayout.StackAll` mode
- Overlay must have `QSizePolicy.Expanding` to fill container
- Set `background: transparent` stylesheet on overlay itself (not children)
- **Critical**: Forward events to module below using `childAt(pos)` to find target widget
- Send events to specific child widget, not container (Qt doesn't auto-propagate)
- `QMouseEvent` uses `.pos()`, `QWheelEvent` uses `.position().toPoint()`
- `QStackedLayout` widgets are siblings, not parent-child (event.ignore() doesn't propagate)

### Theme Awareness
**All UI components must respond to theme changes:**
- Connect to `ThemeManager.theme_changed` signal in component constructor
- Implement `_apply_theme()` method with separate stylesheets for each theme
- Use `self.theme_manager.current_theme` to get active theme
- Title bars, buttons, borders, and backgrounds must match theme colors
- Hover states should use theme accent colors (cyan, blue, or orange)

### Tile-Based Navigation
**Module tiles follow consistent sizing and behavior:**
- **Tile Size**: 453×285px (453×255 screenshot + 30px label)
- **Grid Layout**: 3 columns, 20px spacing, horizontally centered
- **Screenshot**: 16:9 aspect ratio preview image from ScreenshotManager
- **Star Button**: Top-right corner, 32×32px, transparent background
- **Hover Effect**: Border changes to theme accent color
- **Click Behavior**: Opens module full-screen

### Favorites-First Sorting
**Tiles always display favorites at the top:**
- Sort key: `(not is_favorite, label.lower())` - False < True puts favorites first
- Favorites persist across sessions via FavoritesService
- Grid refreshes automatically when favorite is toggled
- Starred modules appear first in all views (Home, filtered sections, search results)

### Section Organization
**Modules are grouped under logical sections:**
- **Charting**: Chart analysis tools (currently: Charts)
- **Crypto**: Cryptocurrency-specific modules (currently: Crypto Dashboard, DeFi, NFT Tracker)
- **Portfolio**: Investment tracking (currently: Portfolio, Watchlist)
- **Market Data**: News and screening tools (currently: News, Screener)
- **Analysis**: Valuation and analysis tools (currently: Analysis)
- All sections defined in `core/config.py` under `MODULE_SECTIONS`

### Search Behavior
**Real-time search filtering:**
- Search bar is centered, 926px width (2 tiles)
- Case-insensitive matching against module label
- Search filters on top of section filtering (if active)
- Empty search shows all modules (respects section filter)
- Clear button (X) to reset search

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

## Technical Implementation Details

### Overlay Widgets and Event Propagation
**Critical for home button overlays on modules:**
- Qt doesn't auto-propagate manually-sent events to child widgets
- When forwarding events, use `widget.childAt(pos)` to find the actual target widget
- Send events to the specific child widget, not its container
- `QStackedLayout` widgets are siblings, not parent-child (event.ignore() doesn't propagate between them)
- **Pattern**:
  ```python
  target_widget = module_widget.childAt(module_pos)
  if target_widget:
      child_pos = target_widget.mapFromGlobal(global_pos)
      new_event = QMouseEvent(...)
      QCoreApplication.sendEvent(target_widget, new_event)
  ```

### Event API Differences
- `QMouseEvent` uses `.pos()` for position
- `QWheelEvent` uses `.position().toPoint()` for position
- Always check event type when accessing position data

### Testing UI Changes
When modifying navigation/overlay systems, test:
- All button clicks and hover effects
- Text input focus and interaction
- Dropdown menus
- Mouse wheel scrolling/zooming
- Chart/widget dragging and panning

## Code Style

### Type Hints (gradually adopting)
```python
def fetch_data(ticker: str, interval: str) -> pd.DataFrame:
    """Fetch OHLCV data for ticker."""
    ...
```

### Minimal Documentation
- ✅ Add docstrings for: Business logic, complex algorithms, public APIs
- ❌ Skip docstrings for: Simple UI setup, getters/setters, obvious widgets
- One-line docstrings are fine

### Qt Conventions
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

### File Organization
- One widget class per file in `ui/widgets/`
- One module per file in `ui/modules/`
- Services are stateless/singleton-like

## Module Development

### Adding a New Module
1. **Create Module**: Inherit from `QWidget`, implement module UI and logic
2. **Add to CONFIG**: Add entry to `MODULE_SECTIONS` in `core/config.py`:
   ```python
   "Section Name": [
       {"id": "module_id", "label": "Module Label", "emoji": "📊"}
   ]
   ```
3. **Register in main.py**: Import and add to HubWindow:
   ```python
   hub.add_module("module_id", MyModule(theme_manager))
   ```
4. **Screenshot**: ScreenshotManager will auto-generate preview on first load
5. **Home Button**: Automatically added via `_create_module_container`

### Key Patterns for Modules
- All modules are self-contained `QWidget` instances
- Each module gets wrapped in container with transparent home button overlay
- Modules appear in `MODULE_SECTIONS` config for tile display
- Screenshot previews generated automatically from emoji and section
- Theme changes propagate via `ThemeManager.theme_changed` signal
- Modules should connect to theme_changed and implement `_apply_theme()`

## Configuration

**Default Settings** (`core/config.py`):
- **Window**: 1400x900px, launches maximized
- **Default Ticker**: BTC-USD
- **Default Interval**: daily
- **Default Theme**: bloomberg
- **Default Chart Type**: Candles
- **Default Scale**: Logarithmic
- **Chart Period**: Last 365 days (max for fetch)
- **Tile Layout**: 3 columns, 453×285px tiles, 20px spacing

**User Data Directories**:
- Custom Indicators: `~/.quant_terminal/custom_indicators.json`
- Favorites: `~/.quant_terminal/favorites.json`
- Screenshots: `~/.quant_terminal/screenshots/`

**Current Module Sections** (from config.py):
- **Charting**: Charts
- **Crypto**: Crypto Dashboard, DeFi, NFT Tracker
- **Portfolio**: Portfolio, Watchlist
- **Market Data**: News, Screener
- **Analysis**: Analysis

*Note: Module ecosystem designed to scale to 10-20+ specialized finance modules*

## Git Workflow

- **Main branch**: `main`
- **Active development**: `bb` branch
- **Recent work**: Tile-based navigation, custom title bar, favorites system

## Project Entry Point

**Main entry**: `src/app/main.py`
```python
# Creates QApplication
# Initializes FavoritesService
# Initializes ThemeManager (Bloomberg theme)
# Sets up HubWindow with custom title bar
# Adds all modules with home button overlays
# Starts event loop
```

---

**Pro Tips**:
- The equation parser tokenizes and evaluates using RPN (Reverse Polish Notation)
- Indicators can be overlays (on price chart) or oscillators (separate pane)
- Theme switching is handled via `ThemeManager` signals, not direct stylesheet updates
- All market data flows through `MarketDataService` for consistency
- Custom title bar allows seamless theme integration (OS title bars can't be styled)
- Event forwarding in overlays must target specific child widgets, not containers
