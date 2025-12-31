# Chart Architecture - Reusable Components Guide

## Overview

Modular, reusable chart architecture for building 25+ Bloomberg-scale chart modules. All charting components are in `src/app/ui/widgets/charting/`.

## Component Hierarchy

```
src/app/ui/widgets/charting/
├── base_chart.py              # Base class (~210 lines)
├── axes/
│   ├── draggable_axis.py      # Drag-to-zoom (~75 lines)
│   ├── price_axis.py          # USD formatting (~47 lines)
│   └── date_index_axis.py     # Date display (~79 lines)
├── renderers/
│   └── candlestick.py         # OHLC renderer (~96 lines)
└── overlays/
    └── resize_handle.py       # Draggable resize (~100 lines)
```

---

## Building a New Chart Module

```python
from app.ui.widgets.charting import BaseChart
from app.ui.widgets.charting.axes import DraggableAxisItem
import pyqtgraph as pg

class PortfolioPerformanceChart(BaseChart):
    """Portfolio cumulative returns chart."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent=parent)
        self.theme_manager = theme_manager

        # Create plot with custom axes
        self.plot_item = self.addPlot(
            axisItems={
                'bottom': pg.DateAxisItem(orientation='bottom'),
                'left': DraggableAxisItem(orientation='left')
            }
        )
        self.view_box = self.plot_item.getViewBox()

        # Apply theme
        self.set_theme(theme_manager.current_theme)
        theme_manager.theme_changed.connect(self.set_theme)

    def plot_returns(self, returns_df):
        """Plot cumulative returns data."""
        self.clear_plot()
        cumulative = (1 + returns_df['returns']).cumprod() - 1
        self.plot_item.plot(
            returns_df.index.to_pydatetime(),
            cumulative.values * 100,
            pen=pg.mkPen(color=self._get_theme_accent_color(), width=2)
        )
```

**What BaseChart provides (~210 lines):**
- Theme management (dark/light/bloomberg)
- Background and gridline styling
- Crosshair creation and color management
- Mouse event hooks
- Utility methods (clear_plot, add_item)

---

## Reusable Axes

**DraggableAxisItem** - Base axis with drag-to-zoom
```python
y_axis = DraggableAxisItem(orientation='left')
```

**DraggablePriceAxisItem** - USD formatting ($1,234.56), log scale support
```python
price_axis = DraggablePriceAxisItem(orientation='right')
price_axis.set_scale_mode('log')
```

**DraggableIndexDateAxisItem** - Date display for integer-indexed data
```python
date_axis = DraggableIndexDateAxisItem(orientation='bottom')
date_axis.set_index(df.index)  # Pass DatetimeIndex
```

---

## Reusable Renderers

**CandlestickItem** - OHLC candlestick chart
```python
from app.ui.widgets.charting.renderers import CandlestickItem
import numpy as np

# Data: [[x, open, close, low, high], ...]
candle_data = np.array([[0, 100, 105, 98, 107], ...])
candles = CandlestickItem(data=candle_data, bar_width=0.6)
plot_item.addItem(candles)
```

---

## Reusable Overlays

**ResizeHandle** - Draggable handle for resizing subplots
```python
from app.ui.widgets.charting.overlays import ResizeHandle

handle = ResizeHandle(parent=self)
handle.height_changed.connect(self._on_resize)
```

---

## Service Layer

**ChartThemeService** - Centralized chart component stylesheets
```python
from app.services.chart_theme_service import ChartThemeService

stylesheet = ChartThemeService.get_indicator_panel_stylesheet('bloomberg')
```

---

## Design Principles

1. **Composition Over Inheritance** - Components designed to be composed
2. **Single Responsibility** - Each component has one clear purpose
3. **Theme Awareness** - All components support dark/light/bloomberg
4. **Reusability First** - Components designed for multiple chart types
5. **Event-Driven** - Communication via Qt signals/slots

---

## Quick Start Checklist

1. Inherit from `BaseChart`
2. Set up plot and ViewBox: `self.plot_item = self.addPlot(...)`
3. Apply theme: `self.set_theme(theme_manager.current_theme)`
4. Connect theme signal: `theme_manager.theme_changed.connect(self.set_theme)`
5. Add optional crosshair: `self._create_crosshair(self.plot_item, self.view_box)`
6. Implement plotting methods

**Result:** Fully functional, theme-aware chart in ~50-100 lines!

---

## Line Count Summary

| Component | Lines | Purpose |
|-----------|-------|---------|
| base_chart.py | 210 | Base infrastructure |
| axes/ | 201 | Draggable, price, date axes |
| renderers/ | 96 | Candlestick renderer |
| overlays/ | 100 | Resize handle |
| **Reusable total** | **607** | Available for all modules |

**Benefits:**
- No file exceeds 1,400 lines
- Clear separation of concerns
- Future modules need ~50-100 lines each
- Easy to find and extend code
