# Quant Terminal - AI Assistant Guide

**Bloomberg Terminal-inspired desktop app for investing and technical analysis**

## Quick Facts

- **Tech Stack**: Python 3.10+, PySide6 (Qt6), PyQtGraph, pandas, yfinance
- **Status**: Early stage (v0.1.0), tile-based navigation, 5 production modules
- **Architecture**: Modular, composition-based, signal-driven, theme-aware
- **Planned Scale**: 25+ specialized finance modules

---

## Core Architecture

### 1. Module-Scoped Services Pattern

**Critical**: Services go in module directories, NOT global `services/` (prevents clutter at scale)

```
services/                    # ONLY truly shared services
├── market_data.py          # Yahoo Finance fetching
├── statistics_service.py   # Financial calculations (25+ methods)
├── returns_data_service.py # Cached returns data
└── base_settings_manager.py

modules/chart/services/     # Chart-specific only
├── indicator_service.py
└── ticker_equation_parser.py
```

### 2. Widget Organization

```
ui/widgets/
├── charting/          # Reusable chart infrastructure (BaseChart, axes, renderers)
├── navigation/        # Tiles, tabs, search
└── common/            # ThemedDialog, EditableTableBase, input widgets

modules/{name}/widgets/  # Module-specific only
```

**Rule**: Used by 3+ modules? → `ui/widgets/`. Otherwise → module directory.

### 3. Key Patterns

- **Services**: Stateless business logic, never import widgets
- **Widgets**: Presentation, reusable UI components
- **Modules**: Integration/orchestration, use factory functions in main.py
- **Signals**: Qt signal/slot for all widget communication

### 4. Lazy Loading (Critical for Fast Startup)

Heavy libraries (numpy, pandas, scipy) must be imported inside functions:

```python
class StatisticsService:
    @staticmethod
    def get_sharpe_ratio(returns: "pd.Series") -> float:
        import numpy as np  # Lazy import inside method
        # ... calculation
```

---

## Directory Structure

```
src/app/
├── core/
│   ├── config.py              # MODULE_SECTIONS registry
│   └── theme_manager.py       # Dark/Light/Bloomberg themes
│
├── services/                  # SHARED ONLY
│   ├── statistics_service.py       # 25+ financial calculations
│   ├── market_data.py              # Yahoo Finance fetching
│   ├── returns_data_service.py     # Cached daily returns
│   ├── portfolio_data_service.py   # Read-only portfolio access
│   ├── theme_stylesheet_service.py # Centralized theme colors
│   └── base_settings_manager.py    # Settings persistence base
│
├── ui/
│   ├── hub_window.py          # Main window, navigation
│   ├── widgets/
│   │   ├── charting/          # BaseChart, axes, renderers
│   │   ├── navigation/        # HomeScreen, tiles, tabs
│   │   └── common/            # ThemedDialog, inputs, tables
│   └── modules/               # One folder per module
│
└── utils/
    ├── formatters.py          # Price, number, metric formatting
    └── screenshot_manager.py
```

---

## Creating a New Module

### Structure

```
modules/{name}/
├── {name}_module.py     # Main widget (inherits QWidget)
├── services/            # Business logic (optional)
└── widgets/             # UI components (optional)
```

### Minimal Example

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout
from app.ui.widgets.common import LazyThemeMixin

class MyModule(LazyThemeMixin, QWidget):
    def __init__(self, theme_manager, parent=None):
        self._theme_dirty = False
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)
        self._apply_theme()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # Add widgets...

    def _apply_theme(self):
        theme = self.theme_manager.current_theme
        # Apply theme stylesheet...
```

### Registration

**config.py**: Add to `MODULE_SECTIONS`
**main.py**: `hub.add_module("id", lambda: MyModule(theme_manager))`

---

## Shared Services Reference

### StatisticsService (`services/statistics_service.py`)

Centralized financial calculations. All methods are static with lazy imports.

```python
from app.services import StatisticsService

# Return metrics
StatisticsService.get_total_return(returns)
StatisticsService.get_annualized_return(returns)
StatisticsService.get_max_return(returns)
StatisticsService.get_min_return(returns)

# Risk metrics
StatisticsService.get_annualized_volatility(returns)
StatisticsService.get_downside_risk(returns, target=0.0)
StatisticsService.get_var(returns, confidence=0.95)
StatisticsService.get_cvar(returns, confidence=0.95)
StatisticsService.get_max_drawdown(returns)
StatisticsService.get_skewness(returns)
StatisticsService.get_kurtosis(returns)

# Risk-adjusted metrics
StatisticsService.get_sharpe_ratio(returns, risk_free_rate)
StatisticsService.get_sortino_ratio(returns, risk_free_rate)
StatisticsService.get_treynor_ratio(portfolio, benchmark, risk_free_rate)

# Benchmark-relative metrics
StatisticsService.get_beta(portfolio, benchmark)
StatisticsService.get_alpha(portfolio, benchmark, risk_free_rate)
StatisticsService.get_tracking_error(portfolio, benchmark)
StatisticsService.get_information_ratio(portfolio, benchmark)
StatisticsService.get_correlation(portfolio, benchmark)
StatisticsService.get_capture_ratio(portfolio, benchmark)

# Utility
StatisticsService.get_risk_free_rate()  # Fetches ^IRX
StatisticsService.get_distribution_statistics(returns)
StatisticsService.align_returns(portfolio, benchmark)
```

### Other Shared Services

**ThemeStylesheetService** - Centralized theme colors and stylesheets
- `get_colors(theme)`, `get_dialog_stylesheet(theme)`, `get_table_stylesheet(theme)`

**BaseSettingsManager** - Settings persistence base class
- Subclass with `DEFAULT_SETTINGS` and `settings_filename` properties

**MarketDataService** - Yahoo Finance with caching
- `fetch_price_history(ticker, period, interval)`

**ReturnsDataService** - Cached portfolio returns
- `get_daily_returns(portfolio_name)`, `get_portfolio_returns()`

---

## Common Widgets Reference

### ThemedDialog (`common/themed_dialog.py`)

Base class for all dialogs. Provides frameless window, custom title bar, drag-to-move.

```python
from app.ui.widgets.common import ThemedDialog

class MyDialog(ThemedDialog):
    def __init__(self, theme_manager, parent=None):
        super().__init__(theme_manager, "Dialog Title", parent, min_width=500)

    def _setup_content(self, layout):
        # Add widgets to layout (title bar handled by base class)
        layout.addWidget(QLabel("Content"))
```

### Portfolio/Benchmark Dropdowns (`common/portfolio_ticker_combo.py`)

Reusable dropdowns for portfolio/ticker selection. Used by 5+ modules.

```python
from app.ui.widgets.common import PortfolioTickerComboBox, BenchmarkComboBox, PortfolioComboBox

# Editable - allows typing tickers OR selecting portfolios
self.portfolio_combo = PortfolioTickerComboBox()
self.portfolio_combo.set_portfolios(["Portfolio A", "Portfolio B"], current="Portfolio A")
self.portfolio_combo.value_changed.connect(self._on_portfolio_changed)  # Emits with [Port] prefix

# Benchmark - same as above but treats "NONE"/empty as clearing
self.benchmark_combo = BenchmarkComboBox()  # Default placeholder: "None"
self.benchmark_combo = BenchmarkComboBox(placeholder="SPY")  # Custom placeholder

# Read-only - dropdown only, no typing (for portfolio-only selection)
self.portfolio_combo = PortfolioComboBox()
```

**Key Features**:
- Portfolios stored internally with `[Port] ` prefix, displayed without
- `value_changed` signal emits full value (with prefix for portfolios, UPPERCASE for tickers)
- `SmoothScrollListView` for slow, smooth dropdown scrolling
- Methods: `set_portfolios()`, `get_value()`, `get_display_value()`, `reset()`

### Other Common Widgets

- **EditableTableBase**: Themed editable tables with cell highlighting
- **DateInputWidget**: Date input with live formatting (YYYY-MM-DD)
- **ValidatedNumericLineEdit**: Numeric input with validation
- **AutoSelectLineEdit**: Auto-select on focus, auto-capitalize
- **NoScrollComboBox**: ComboBox ignoring wheel events
- **SmoothScrollListView**: Slow-scroll list view for combo dropdowns
- **CustomMessageBox**: Themed message dialogs
- **LoadingOverlay**: Semi-transparent loading indicator
- **LazyThemeMixin**: Defer theme application when widget hidden

---

## Charting Components

### BaseChart (`charting/base_chart.py`, ~600 lines)

Foundation for all chart modules. Provides theme, gridlines, crosshair, mouse events.

```python
from app.ui.widgets.charting import BaseChart

class MyChart(BaseChart):
    def __init__(self, theme_manager, parent=None):
        super().__init__(theme_manager, parent)
        # BaseChart handles setup, just add plotting logic
```

### Axes

- **DraggableAxisItem**: Click-and-drag to zoom/pan
- **PriceAxisItem**: USD formatting ($1,234.56)
- **DateIndexAxisItem**: Smart date formatting for integer indices

### Renderers & Overlays

- **CandlestickItem**: OHLC candlestick rendering
- **ResizeHandle**: Draggable handle for split panes

---

## Utilities

### formatters.py

```python
from app.utils.formatters import format_metric_value

# Format types: "percent", "ratio", "decimal", "decimal4", "capture"
format_metric_value(0.15, "percent")    # → "15.00"
format_metric_value(1.234, "ratio")     # → "1.23"
format_metric_value(None, "percent")    # → "" (blank for missing)
format_metric_value(0, "percent")       # → "--" (dash for zero)
```

---

## Code Conventions

### Imports

**Within module**: Relative imports (`from ..services import MyService`)
**Cross-module**: Absolute imports (`from app.services import StatisticsService`)

### Naming

- **Classes**: PascalCase (`PortfolioModule`, `StatisticsService`)
- **Functions**: snake_case (`get_sharpe_ratio`, `_apply_theme`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_TICKER`)
- **Private**: Prefix `_` (`_setup_ui`, `_chart_widget`)

### Qt Signals/Slots

```python
# Signals (snake_case)
theme_changed = Signal(str)

# Slots (prefix _on_)
def _on_theme_changed(self, theme: str):
    self._apply_theme()
```

---

## Critical Technical Details

### Theme Colors

| Theme | Background | Accent |
|-------|------------|--------|
| Dark | #1e1e1e | #00d4ff (cyan) |
| Light | #ffffff | #0066cc (blue) |
| Bloomberg | #0d1420 | #FF8000 (orange) |

### Module Lifecycle

Modules are **destroyed on navigate, recreated on open**:
- Use factory functions: `lambda: Module(theme_manager)`
- Don't store state in module (use services for persistence)
- Theme applied fresh on each creation

### Event API Differences

```python
# QMouseEvent
pos = event.pos()

# QWheelEvent (different!)
pos = event.position().toPoint()
```

### PyQtGraph Notes

- Use numeric x-values, not DatetimeIndex
- DateIndexAxisItem maps indices to date strings

---

## Configuration & Persistence

### config.py

```python
MODULE_SECTIONS = {
    "Charting": [{"id": "charts", "label": "Charts", "emoji": "📈"}],
    "Portfolio": [{"id": "portfolio", "label": "Portfolio", "emoji": "💼"}],
}
```

### User Data (`~/.quant_terminal/`)

- `favorites.json` - Favorited modules
- `portfolios/` - Portfolio JSON files
- `*_settings.json` - Module settings
- `cache/` - Market data cache

---

## Testing Checklist

**After UI Changes**:
- [ ] Theme switching (Dark ↔ Light ↔ Bloomberg)
- [ ] Button clicks, hover effects
- [ ] Mouse wheel, dragging
- [ ] Dialog title bar dragging

**Navigation**:
- [ ] Tiles open modules
- [ ] Home button returns home
- [ ] Favorites persist

---

## Quick Reference

### New Chart Module
1. Inherit `BaseChart`
2. Add plotting methods
3. Result: ~50 lines vs 600+

### New Settings Dialog
1. Inherit `ThemedDialog`
2. Override `_setup_content(layout)`
3. Title bar, theming handled by base

### Using Statistics
```python
from app.services import StatisticsService
sharpe = StatisticsService.get_sharpe_ratio(returns, risk_free_rate)
```

### Common Gotchas
- Use factory functions for `add_module()` (lambda required)
- Services in module directories, not global `services/`
- QWheelEvent uses `.position().toPoint()` not `.pos()`
- Title bar labels need `background: transparent`

---

## Summary

**Architecture**: Module-scoped services, composition over inheritance, signal-based

**Key Services**: StatisticsService (25+ financial calcs), ThemeStylesheetService, BaseSettingsManager

**Key Widgets**: ThemedDialog (dialogs), BaseChart (charts), EditableTableBase (tables), PortfolioTickerComboBox/BenchmarkComboBox (dropdowns)

**Scalability**: Designed for 25+ modules with tile navigation and reusable components
