# Portfolio Section - Module Guide

## Overview

Portfolio section provides investment management, analysis, and tracking. All modules share data via PortfolioService API and use StatisticsService for calculations.

## Module Structure

```
src/app/ui/modules/portfolio_construction/
├── portfolio_construction_module.py
├── services/
│   ├── portfolio_service.py           # Business logic & export API
│   ├── portfolio_persistence.py       # JSON save/load
│   └── portfolio_settings_manager.py  # Extends BaseSettingsManager
└── widgets/
    ├── transaction_log_table.py       # Editable transactions
    ├── aggregate_portfolio_table.py   # Read-only holdings
    └── portfolio_dialogs.py           # Uses ThemedDialog base class
```

---

## Shared Data API

### Getting Holdings

```python
from app.ui.modules.portfolio_construction.services import PortfolioService

holdings = PortfolioService.get_current_holdings_snapshot("My Portfolio")
# Returns: [{"ticker": "AAPL", "total_quantity": 100, "avg_cost_basis": 150.00, ...}]

transactions = PortfolioService.get_transaction_history("My Portfolio")
total_value = PortfolioService.get_portfolio_value("My Portfolio")
```

### Using Statistics

```python
from app.services import StatisticsService

# Get portfolio returns then calculate metrics
sharpe = StatisticsService.get_sharpe_ratio(returns, risk_free_rate)
vol = StatisticsService.get_annualized_volatility(returns)
beta = StatisticsService.get_beta(portfolio_returns, benchmark_returns)
tracking_error = StatisticsService.get_tracking_error(portfolio, benchmark)
```

---

## FREE CASH Special Ticker

- Ticker "FREE CASH" tracks cash deposits/withdrawals
- Bypasses Yahoo Finance validation, always $1.00/unit
- Buy = Deposit, Sell = Withdrawal
- Regular transactions affect cash automatically

---

## Building a New Portfolio Module

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout
from app.core.theme_manager import ThemeManager
from app.services import StatisticsService
from app.ui.widgets.common import PortfolioTickerComboBox, BenchmarkComboBox

class PortfolioRiskModule(QWidget):
    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()

    def _setup_ui(self):
        # Use reusable dropdowns for portfolio/benchmark selection
        self.portfolio_combo = PortfolioTickerComboBox()  # Editable (ticker + portfolio)
        self.benchmark_combo = BenchmarkComboBox()        # With "None" handling
        self.portfolio_combo.value_changed.connect(self._on_portfolio_changed)
```

---

## Reusable Dropdown Components

```python
from app.ui.widgets.common import PortfolioTickerComboBox, BenchmarkComboBox, PortfolioComboBox

# PortfolioTickerComboBox - Editable, allows typing tickers OR selecting portfolios
combo.set_portfolios(["Portfolio A", "Portfolio B"], current="Portfolio A")
combo.value_changed.connect(handler)  # Emits "[Port] Name" or "TICKER"
combo.get_value()  # Full value with [Port] prefix
combo.get_display_value()  # Display text without prefix

# BenchmarkComboBox - Same as above but treats "NONE"/empty as clearing
benchmark = BenchmarkComboBox(placeholder="SPY")  # Custom placeholder

# PortfolioComboBox - Read-only dropdown (no typing, portfolio selection only)
```

---

## Module Integration Checklist

- [ ] Register in `config.py` under `MODULE_SECTIONS["Portfolio"]`
- [ ] Add to `main.py` with factory function
- [ ] Use `PortfolioTickerComboBox`/`BenchmarkComboBox` for dropdowns
- [ ] Use `StatisticsService` for financial calculations
- [ ] Use `ThemedDialog` for dialogs
- [ ] Keep module-specific services in `modules/{name}/services/`
- [ ] Implement `_apply_theme()` method

---

## Data Persistence

Portfolios stored in `~/.quant_terminal/portfolios/`:
- Format: JSON with transaction list
- Auto-saves on transaction changes
- Other modules: read-only via PortfolioService API

---

## Best Practices

1. **Read-only access**: Don't modify portfolio data directly
2. **Use StatisticsService**: For all financial calculations
3. **Error handling**: Portfolio may not exist, handle None
4. **Theme-aware**: Respond to theme_changed signal
5. **Use ThemedDialog**: For all dialogs (frameless, themed)

---

## Common Patterns

### Loading on Module Open
```python
def showEvent(self, event):
    super().showEvent(event)
    if not self._loaded:
        self.load_portfolio("Default")
        self._loaded = True
```

### Using Market Data
```python
from app.services.market_data import fetch_price_history
df = fetch_price_history("AAPL", period="1y", interval="1d")
```

### Live Price Updates
```python
from app.services.yahoo_finance_service import YahooFinanceService
from app.services.returns_data_service import ReturnsDataService

# Batch fetch current prices (for live polling)
prices = YahooFinanceService.fetch_batch_current_prices(["AAPL", "MSFT", "BTC-USD"])
# Returns: {"AAPL": 175.50, "MSFT": 380.25, "BTC-USD": 98234.56}

# Append today's live return to a returns series
returns = ReturnsDataService.get_ticker_returns("AAPL")
returns = ReturnsDataService.append_live_return(returns, "AAPL")

# Append today's live portfolio return (weighted)
returns = ReturnsDataService.get_time_varying_portfolio_returns("My Portfolio")
returns = ReturnsDataService.append_live_portfolio_return(returns, "My Portfolio")
```

---

## Architecture Notes

- **Composition over inheritance**: Portfolio modules are QWidgets
- **StatisticsService**: 25+ financial calculations (Sharpe, VaR, beta, etc.)
- **ThemedDialog**: Base class for all dialogs
- **Signal-based**: Use Qt signals for widget communication
