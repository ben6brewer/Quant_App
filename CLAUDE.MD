# Quant Terminal - AI Assistant Guide

**Bloomberg Terminal-inspired desktop app for investing and technical analysis**

## Quick Facts

- **Tech Stack**: Python 3.10+, PySide6 (Qt6), PyQtGraph, pandas, yfinance
- **Status**: Early stage (v0.1.0), tile-based navigation complete, 1 production module (Charts), 8 placeholders
- **Architecture**: Modular, composition-based, signal-driven, theme-aware
- **Planned Scale**: 25+ specialized finance modules

---

## Core Architecture

### 1. Module-Scoped Services Pattern

**Critical**: Services go in module directories, NOT global `services/` (prevents clutter at scale)

```
services/                    # ONLY truly shared services
├── market_data.py          # Used by all modules
├── favorites_service.py    # Navigation system
└── preferences_service.py  # Settings

modules/chart/services/     # Chart-specific only
├── indicator_service.py
├── ticker_equation_parser.py
└── chart_theme_service.py
```

**Rationale**: With 25+ modules planned, flat `services/` becomes unmaintainable.

### 2. Widget Organization by Reusability

```
ui/widgets/
├── charting/          # Reusable for ALL chart modules (Portfolio, Risk, etc.)
│   ├── base_chart.py  # 600-line foundation
│   ├── axes/          # Price, date, draggable axes
│   └── renderers/     # Candlestick, line renderers
│
├── navigation/        # Tiles, tabs, search
└── common/            # Used by 3+ modules

modules/{name}/widgets/  # Module-specific only
```

**Decision Tree**: Used by 3+ modules? → `ui/widgets/`. Chart infrastructure? → `charting/`. Otherwise → module directory.

### 3. Separation of Concerns

```
MarketDataService (global) → Module Services → Widgets → UI
```

- **Services**: Business logic, calculations, data (stateless/singleton)
- **Widgets**: Presentation, interaction (reusable UI)
- **Modules**: Integration, orchestration
- **Rule**: Services never import widgets

### 4. Composition Over Inheritance

**Prefer**:
```python
class PortfolioChart(BaseChart):  # Only inherit infrastructure
    def __init__(self, theme_manager):
        super().__init__(theme_manager)
        # Compose reusable components
        self.price_axis = PriceAxisItem(orientation='right')
        self.resize_handle = ResizeHandle()
```

**Avoid**: Deep inheritance chains (hard to maintain)

### 5. Signal-Based Architecture

```python
# Publisher
class ThemeManager(QObject):
    theme_changed = Signal(str)

# Subscriber
class Widget(QWidget):
    def __init__(self, theme_manager):
        theme_manager.theme_changed.connect(self._on_theme_changed)
```

---

## Directory Structure (Simplified)

```
src/app/
├── core/
│   ├── config.py              # MODULE_SECTIONS registry, defaults
│   └── theme_manager.py       # Dark/Light/Bloomberg themes
│
├── services/                  # SHARED ONLY
│   ├── market_data.py              # Yahoo Finance fetching
│   ├── favorites_service.py        # Favorites persistence
│   ├── theme_stylesheet_service.py # Centralized theme colors/styles
│   └── base_settings_manager.py    # Abstract settings persistence
│
├── ui/
│   ├── hub_window.py          # Main window, title bar, navigation
│   │
│   ├── widgets/
│   │   ├── charting/          # Reusable chart infrastructure
│   │   │   ├── base_chart.py  # 600-line foundation
│   │   │   ├── axes/          # draggable_axis.py, price_axis.py, date_index_axis.py
│   │   │   ├── renderers/     # candlestick.py
│   │   │   └── overlays/      # resize_handle.py
│   │   │
│   │   ├── navigation/        # home_screen.py, module_tile.py, etc.
│   │   └── common/            # Shared widgets (ThemedDialog, DateInputWidget, etc.)
│   │
│   └── modules/
│       └── chart/             # Example module structure
│           ├── chart_module.py
│           ├── services/      # indicator_service.py, ticker_equation_parser.py
│           └── widgets/       # price_chart.py, chart_controls.py
│
└── utils/
    ├── formatters.py
    └── screenshot_manager.py
```

---

## Creating a New Module (Quick Guide)

### Step 1: Plan Structure

```
modules/{name}/
├── {name}_module.py     # Main orchestrator (inherits QWidget)
├── services/            # Business logic
│   ├── __init__.py
│   └── {name}_service.py
└── widgets/             # UI components
    ├── __init__.py
    └── {name}_widget.py
```

### Step 2: Create Service (if needed)

```python
# modules/portfolio/services/portfolio_service.py
class PortfolioService:
    @staticmethod
    def calculate_returns(holdings: List[Dict], prices: pd.DataFrame) -> pd.Series:
        """Calculate portfolio returns."""
        # Business logic here
        return returns
```

### Step 3: Create Chart Widget (if chart module)

```python
# modules/portfolio/widgets/portfolio_chart.py
from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.charting.axes import PriceAxisItem

class PortfolioChart(BaseChart):
    """Inherits 600 lines from BaseChart - just add portfolio-specific logic."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(theme_manager, parent)

        # Customize axes
        pct_axis = PriceAxisItem(orientation='right')
        pct_axis.setLabel('Return', units='%')
        self.set_y_axis(pct_axis)

    def plot_returns(self, returns: pd.Series):
        """Portfolio-specific plotting."""
        cumulative = (1 + returns).cumprod() - 1
        self.plot_line(range(len(cumulative)), cumulative.values * 100, pen='g')
        self.autoRange()
```

**Efficiency**: Write ~50 lines instead of 650+ (12x reduction)

### Step 4: Create Main Module

```python
# modules/portfolio/portfolio_module.py
from PySide6.QtWidgets import QWidget, QVBoxLayout
from .widgets import PortfolioChart
from .services import PortfolioService

class PortfolioModule(QWidget):
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        self._setup_ui()
        self.theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.chart = PortfolioChart(self.theme_manager)
        layout.addWidget(self.chart)

    def _apply_theme(self):
        theme = self.theme_manager.current_theme
        # Apply theme-specific stylesheet
        self.setStyleSheet(f"background-color: {self._get_bg_color(theme)};")
```

### Step 5: Register Module

**In `core/config.py`**:
```python
MODULE_SECTIONS = {
    "Portfolio": [
        {"id": "portfolio", "label": "Portfolio", "emoji": "💼"}  # ← Add here
    ]
}
```

**In `main.py`**:
```python
from app.ui.modules.portfolio.portfolio_module import PortfolioModule

hub.add_module("portfolio", PortfolioModule(theme_manager))
```

### Development Checklist

- [ ] Plan structure (services, widgets)
- [ ] Create services with business logic
- [ ] Create widgets (inherit BaseChart if chart module)
- [ ] Create main module widget
- [ ] Implement `_apply_theme()` method
- [ ] Register in `core/config.py`
- [ ] Register in `main.py`
- [ ] Test theme switching
- [ ] Generate screenshot (auto on first load)

---

## Code Conventions

### Import Patterns

**Within module** (use relative imports):
```python
# modules/chart/widgets/price_chart.py
from ..services import IndicatorService
from .oscillator_pane import OscillatorPane
```

**Cross-module** (use absolute imports):
```python
from app.services.market_data import fetch_price_history
from app.ui.widgets.charting.base_chart import BaseChart
from app.ui.widgets.navigation import HomeScreen
```

### Type Hints (Required)

```python
from typing import List, Dict, Optional
import pandas as pd

def fetch_data(ticker: str, interval: str = "daily") -> pd.DataFrame:
    """Fetch price data."""
    ...

def calculate_metric(values: pd.Series, period: int) -> Optional[float]:
    """Calculate metric, returns None if insufficient data."""
    ...
```

### Qt Conventions

**Signals** (snake_case):
```python
theme_changed = Signal(str)
ticker_updated = Signal(str)
data_loaded = Signal()
```

**Slots** (prefix `_on_`):
```python
def _on_theme_changed(self, theme: str):
    self._apply_theme()

def _on_button_clicked(self):
    self._process_action()
```

**Private attributes** (prefix `_`):
```python
self._chart_widget = PriceChart(theme_manager)
self._current_ticker = "BTC-USD"
```

### Naming

- **Classes**: PascalCase (`PortfolioModule`, `PriceAxisItem`)
- **Functions/Methods**: snake_case (`calculate_returns`, `_apply_theme`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_TICKER`, `TILE_WIDTH`)
- **Private**: Prefix with `_` (`_setup_ui`, `_chart_widget`)

### File Naming

- Modules: `{name}_module.py` (chart_module.py)
- Widgets: `{name}.py` (price_chart.py)
- Services: `{name}.py` (indicator_service.py)
- Dialogs: `{name}_dialog.py` (settings_dialog.py)
- **One class per file** (with rare exceptions)

---

## Critical Technical Details

### 1. Custom Title Bar Pattern

All dialogs use `ThemedDialog` base class for frameless design:

```python
from app.ui.widgets.common import ThemedDialog

class MyDialog(ThemedDialog):
    def __init__(self, theme_manager, parent=None):
        super().__init__(theme_manager, "Dialog Title", parent)

    def _setup_content(self, layout):
        # Add dialog-specific widgets to layout
        layout.addWidget(QLabel("Content"))
```

**ThemedDialog provides**: Custom title bar, drag-to-move, theme styling, close button.

**For main windows**: Implement title bar manually with minimize/maximize buttons.

### 2. Widget Masking for Overlays

**Why masking?** Qt's `:hover` is based on z-order, not event routing. Event forwarding doesn't activate `:hover`.

```python
class TransparentOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._home_button = None

    def set_home_button(self, button):
        self._home_button = button
        button.installEventFilter(self)  # Watch for move/resize
        self._update_mask()

    def _update_mask(self):
        """Make overlay transparent except button area."""
        if not self._home_button:
            return
        button_rect = self._home_button.geometry()
        self.setMask(QRegion(button_rect))  # Only "exists" in button area

    def eventFilter(self, obj, event):
        if obj == self._home_button and event.type() in (QEvent.Move, QEvent.Resize):
            self._update_mask()
        return super().eventFilter(obj, event)
```

**Use case**: Home button overlay on modules (preserves hover state)

### 3. Event API Differences

**QMouseEvent**:
```python
def mouseMoveEvent(self, event: QMouseEvent):
    pos = event.pos()  # QPoint
```

**QWheelEvent** (different!):
```python
def wheelEvent(self, event: QWheelEvent):
    pos = event.position().toPoint()  # NOT .pos()
    delta = event.angleDelta().y()
```

### 4. Theme Application Pattern

```python
class MyWidget(QWidget):
    def __init__(self, theme_manager):
        super().__init__()
        self.theme_manager = theme_manager
        self.theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme()

    def _apply_theme(self):
        theme = self.theme_manager.current_theme
        stylesheets = {
            "dark": "background: #1e1e1e; color: #ffffff;",
            "light": "background: #ffffff; color: #000000;",
            "bloomberg": "background: #0d1420; color: #e8e8e8;"
        }
        self.setStyleSheet(stylesheets.get(theme, stylesheets["dark"]))
```

**Theme accent colors**:
- Dark: Cyan `#00d4ff`
- Light: Blue `#0066cc`
- Bloomberg: Orange `#FF8000`

### 5. PyQtGraph Integration

BaseChart uses `GraphicsLayoutWidget` (not `PlotWidget`) for flexibility:

```python
# BaseChart provides
self.plot_item = self.getPlotItem()
self.view_box = self.plot_item.getViewBox()

# Inherit and customize
class MyChart(BaseChart):
    def __init__(self, theme_manager):
        super().__init__(theme_manager)
        # BaseChart handles PlotItem setup, theme, events, helpers
        # Just add your specific plotting logic
```

### 6. Date Axis Handling

PyQtGraph expects numeric x-values. Convert DatetimeIndex to integers:

```python
# Don't use dates directly
x = df.index  # ❌ DatetimeIndex not supported

# Use numeric indices
x = range(len(df))  # ✅ Works
```

Custom axis formatter maps numeric → date strings (see `DateIndexAxisItem`)

---

## Reusable Components Reference

### Shared Base Classes & Services

**ThemedDialog** (`common/themed_dialog.py`, ~130 lines):
- Base class for frameless dialogs with custom title bar
- Drag-to-move, theme-aware styling via ThemeStylesheetService
- Subclasses override `_setup_content(layout)` to add widgets

**ThemeStylesheetService** (`services/theme_stylesheet_service.py`):
- Centralized theme colors (dark/light/bloomberg)
- Methods: `get_colors()`, `get_table_stylesheet()`, `get_dialog_stylesheet()`, `get_line_edit_stylesheet()`, `get_combobox_stylesheet()`
- All theme colors defined in `COLORS` dict for easy maintenance

**BaseSettingsManager** (`services/base_settings_manager.py`):
- Abstract base for module settings persistence
- Subclasses define `DEFAULT_SETTINGS` property and `settings_filename`
- Provides: `get_setting()`, `update_settings()`, `save_settings()`, `load_settings()`

### Common Widgets (`ui/widgets/common/`)

- **DateInputWidget**: Date input with live dash formatting, validation
- **AutoSelectLineEdit**: Auto-select on focus, auto-capitalize
- **ValidatedNumericLineEdit**: Numeric input with min/max validation
- **NoScrollComboBox**: ComboBox that ignores scroll wheel
- **CustomMessageBox**: Themed message dialogs

---

### BaseChart (~600 lines)

**Location**: `ui/widgets/charting/base_chart.py`

**Provides**:
- PlotItem and ViewBox setup
- Theme-aware background, gridlines, crosshair
- Mouse events (move, leave, resize)
- View helpers (`_get_visible_date_window`, `_safe_set_yrange`, `autoRange`)

**Interface**:
```python
set_theme(theme: str)
set_x_axis(axis_item)
set_y_axis(axis_item, position='right')
plot_line(x, y, **kwargs) → PlotDataItem
clear()
```

**Usage**: Inherit for any chart module (Portfolio, Risk, Monte Carlo, etc.)

### Axes

**DraggableAxisItem** (`axes/draggable_axis.py`, ~90 lines):
- Click-and-drag to zoom/pan
- Base class for price, date, custom axes

**PriceAxisItem** (`axes/price_axis.py`, ~40 lines):
- Formats ticks as `$1,234.56`
- Inherits draggable functionality

**DateIndexAxisItem** (`axes/date_index_axis.py`, ~67 lines):
- Smart date formatting (2024, Q1 2024, Jan 2024, Jan 15)
- Maps DatetimeIndex to numeric x-coordinates

### Renderers

**CandlestickItem** (`renderers/candlestick.py`, ~88 lines):
- OHLC bar rendering
- Custom `paint()` method
- Configurable colors and width

### Overlays

**ResizeHandle** (`overlays/resize_handle.py`, ~100 lines):
- Draggable resize handle for split panes
- Emits `resize_requested(delta)` signal
- Theme-aware styling

### Navigation Components

**HomeScreen** (`navigation/home_screen.py`):
- Section tabs + search bar + tile grid
- Emits `module_selected(module_id)`
- Special: Charting tab auto-opens Charts module

**ModuleTile** (`navigation/module_tile.py`):
- 453×285px (453×255 screenshot + 30px label)
- Star button, hover effects
- Emits `tile_clicked(module_id)`

**ModuleTileGrid** (`navigation/module_tile_grid.py`):
- 3-column layout, 20px spacing
- Section filtering, search filtering
- Favorites-first sorting: `(not is_favorite, label.lower())`

**SectionTabBar** (`navigation/section_tab_bar.py`):
- Horizontal tabs (Home, Charting, Crypto, Portfolio, etc.)
- Emits `section_changed(section_name)`
- Auto-return to Home when clicking active tab

---

## Configuration & Persistence

### Config (`core/config.py`)

```python
MODULE_SECTIONS = {
    "Charting": [{"id": "charts", "label": "Charts", "emoji": "📈"}],
    "Portfolio": [{"id": "portfolio", "label": "Portfolio", "emoji": "💼"}],
    # ... other sections
}

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
DEFAULT_TICKER = "BTC-USD"
TILE_COLS = 3
```

### User Data (`~/.quant_terminal/`)

- `favorites.json`: Favorited module IDs (managed by FavoritesService)
- `custom_indicators.json`: Custom indicators (managed by IndicatorService)
- `chart_settings.json`: Chart preferences (managed by ChartSettingsManager)
- `screenshots/`: Module preview images (managed by ScreenshotManager)

### Persistence Services

**FavoritesService** (singleton):
```python
FavoritesService.initialize()
FavoritesService.toggle_favorite(module_id)
FavoritesService.is_favorite(module_id) → bool
```

**IndicatorService** (singleton):
```python
IndicatorService.save_custom_indicator(indicator)
IndicatorService.load_custom_indicators() → List[Dict]
```

---

## Key Features

### Ticker Equations

Parse math expressions combining tickers (prefix with `=`):

```
=BTC-USD              # Single ticker
=BTC-USD/SPX          # Ratio
=(BTC-USD+ETH-USD)/2  # Average
```

**Implementation**: `TickerEquationParser` (tokenize → Shunting Yard → RPN evaluation → date alignment)

### Technical Indicators

**9 Built-in**: SMA, EMA, Bollinger, VWAP, RSI, MACD, ATR, Stochastic, OBV

**Custom Creation**: Dialog → save to `custom_indicators.json` → plugin system

### Market Data

**Source**: Yahoo Finance (yfinance)

**Intervals**: Daily (1d), Weekly (1wk), Monthly (1mo), Yearly (1mo resampled)

**Caching**: 5-minute TTL in-memory cache

---

## Testing Checklist

**After UI Changes**:
- [ ] Button clicks, hover effects work
- [ ] Text input, dropdowns work
- [ ] Mouse wheel, dragging work
- [ ] Theme switching (Dark ↔ Light ↔ Bloomberg)
- [ ] Title bar, tiles, search update correctly

**Navigation**:
- [ ] Tiles open modules
- [ ] Home button returns to home
- [ ] Favorites persist across sessions

---

## Entry Point

**`main.py`**:
```python
def main():
    app = QApplication(sys.argv)
    FavoritesService.initialize()

    theme_manager = ThemeManager()
    theme_manager.set_theme("bloomberg")

    hub = HubWindow(theme_manager, FavoritesService)
    hub.add_module("charts", ChartModule(theme_manager))
    # Add other modules...

    hub.showMaximized()
    sys.exit(app.exec())
```

---

## Quick Reference

### Creating a Chart Module

1. Inherit from `BaseChart`
2. Customize axes (optional)
3. Implement plotting methods
4. Result: ~50 lines instead of 650+

### Creating a Non-Chart Module

1. Inherit from `QWidget`
2. Compose services + widgets
3. Implement `_apply_theme()`
4. Connect to `theme_changed` signal

### Adding to Navigation

1. Add to `MODULE_SECTIONS` in `config.py`
2. Call `hub.add_module(id, widget)` in `main.py`
3. Screenshot auto-generated on first load

### Common Gotchas

- Title bar labels need `background: transparent`
- QWheelEvent uses `.position().toPoint()` not `.pos()`
- Widget masking > event forwarding for `:hover`
- Services in module directories, not global `services/`
- PyQtGraph needs numeric x-values, not dates

---

## Summary

**Architecture**: Module-scoped services, composition over inheritance, signal-based communication

**Efficiency**: BaseChart provides 600 lines of infrastructure → write ~50 lines per chart module (12x reduction)

**Scalability**: Designed for 25+ modules with tile-based navigation and reusable components

**When building**: Follow the checklist, inherit from BaseChart for charts, use relative imports within modules, test theme switching
