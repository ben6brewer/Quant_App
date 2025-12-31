# Portfolio Section - Module Guide

## Overview

The Portfolio section provides investment portfolio management, analysis, and tracking tools. All portfolio modules share a common data model via the Portfolio Construction module's export API.

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
    ├── portfolio_controls.py          # Top control bar
    ├── portfolio_dialogs.py           # Uses ThemedDialog base class
    └── view_tab_bar.py                # Transaction/Holdings toggle
```

## Portfolio Construction Module

**Purpose**: Transaction tracking and portfolio data entry
- Side-by-side view: Transaction Log + Aggregate Holdings
- Multiple portfolio support with save/load
- Real-time P&L calculations using yfinance prices
- Export API for other modules

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

### Data Structures

**Holdings:**
```python
{"ticker": str, "total_quantity": float, "avg_cost_basis": float,
 "current_price": float, "market_value": float, "total_pnl": float, "weight_pct": float}
```

**Transactions:**
```python
{"id": str, "date": str, "ticker": str, "transaction_type": str,
 "quantity": float, "entry_price": float, "fees": float, "notes": str}
```

---

## FREE CASH Special Ticker

- Ticker "FREE CASH" tracks cash deposits/withdrawals
- Bypasses Yahoo Finance validation, always $1.00/unit
- Buy = Deposit (adds cash), Sell = Withdrawal (removes cash)
- Included in portfolio weight calculations
- Regular transactions affect cash: Buys decrease, Sells increase

---

## Transaction Safeguards

PortfolioService validates transactions won't create invalid states:
- Can't sell more shares than owned at that date
- Can't withdraw more cash than available
- Validates entire transaction chain on edits/deletes

---

## Import Modes

- **Full History**: Clone transactions with original dates (maintains audit trail)
- **Flat**: Consolidate to net positions dated today (clean slate)

---

## Building a New Portfolio Module

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout
from app.core.theme_manager import ThemeManager
from app.ui.modules.portfolio_construction.services import PortfolioService

class PortfolioRiskModule(QWidget):
    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()

    def load_portfolio(self, portfolio_name: str = "Default"):
        holdings = PortfolioService.get_current_holdings_snapshot(portfolio_name)
        for holding in holdings:
            # Calculate risk metrics per holding
            pass
```

---

## Module Integration Checklist

- [ ] Register in `config.py` under `MODULE_SECTIONS["Portfolio"]`
- [ ] Add to `main.py` with `hub.add_module(id, module)`
- [ ] Pass `theme_manager` to constructor
- [ ] Implement `_apply_theme()` method
- [ ] Use PortfolioService API to access data
- [ ] Use `ThemedDialog` for any dialogs
- [ ] Keep services in `modules/{name}/services/`

---

## Planned Modules

- **Portfolio Risk Analysis**: VaR, Sharpe ratio, correlation matrix
- **Tax Reporting**: Capital gains, cost basis tracking
- **Performance Attribution**: Sector/security contribution
- **Rebalancing Tools**: Target vs actual allocation
- **Monte Carlo Simulation**: Portfolio outcome projections

---

## Data Persistence

Portfolios stored in `~/.quant_terminal/portfolios/`:
- Format: JSON with transaction list
- Auto-saves on transaction changes
- Other modules: read-only via PortfolioService API

---

## Best Practices

1. **Read-only access**: Don't modify portfolio data directly
2. **Price caching**: Use PortfolioService for consistency
3. **Error handling**: Portfolio may not exist, handle None
4. **Theme-aware**: Respond to theme_changed signal
5. **Use ThemedDialog**: For dialogs (frameless, themed)

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
volatility = df["Close"].pct_change().std() * (252 ** 0.5)
```

---

## Architecture Notes

- **Composition over inheritance**: Portfolio modules are QWidgets
- **Service-based**: Business logic in services, widgets for UI
- **Signal-based**: Use Qt signals for widget communication
- **Stateless services**: PortfolioService uses static methods
- **ThemedDialog**: Use for all dialogs (inherits title bar, theming)
- **ThemeStylesheetService**: Use for consistent widget styling
