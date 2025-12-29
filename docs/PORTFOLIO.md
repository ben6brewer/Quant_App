# Portfolio Section - Module Guide

## Overview

The Portfolio section provides investment portfolio management, analysis, and tracking tools. All portfolio modules share a common data model via the Portfolio Construction module's export API.

## Module Structure

```
src/app/ui/modules/
└── portfolio_construction/        # Core portfolio data module
    ├── services/
    │   ├── portfolio_service.py       # Business logic & export API
    │   └── portfolio_persistence.py   # JSON save/load
    └── widgets/
        ├── transaction_log_table.py
        ├── aggregate_portfolio_table.py
        ├── portfolio_controls.py
        └── portfolio_dialogs.py
```

## Modules

### Portfolio Construction (Portfolio Builder)
**Purpose**: Transaction tracking and portfolio data entry
- Side-by-side view: Transaction Log + Aggregate Holdings
- Multiple portfolio support with save/load
- Real-time P&L calculations using yfinance prices
- Export API for other modules

**Use Cases**:
- Log buy/sell transactions with fees
- Track cost basis and realized gains
- View portfolio allocation by ticker
- Export data for risk analysis, tax reporting, etc.

## Shared Data API

Portfolio Construction provides an export API for other modules to access portfolio data:

### Getting Holdings

```python
from app.ui.modules.portfolio_construction.services import PortfolioService

# Get current holdings snapshot
holdings = PortfolioService.get_current_holdings_snapshot("My Portfolio")
# Returns: [{"ticker": "AAPL", "total_quantity": 100, "avg_cost_basis": 150.00, ...}]

# Get transaction history
transactions = PortfolioService.get_transaction_history("My Portfolio")
# Returns: [{"id": "...", "date": "2024-01-15", "ticker": "AAPL", ...}]

# Get total portfolio value
total_value = PortfolioService.get_portfolio_value("My Portfolio")
# Returns: float (e.g., 45000.00)
```

### Holdings Data Structure

```python
{
    "ticker": str,              # Ticker symbol
    "total_quantity": float,    # Net shares (buys - sells)
    "avg_cost_basis": float,    # Weighted average cost per share
    "current_price": float,     # Latest price from yfinance
    "market_value": float,      # current_price * total_quantity
    "total_pnl": float,         # Profit/loss in dollars
    "weight_pct": float         # Percentage of total portfolio
}
```

### Transaction Data Structure

```python
{
    "id": str,                  # UUID
    "date": str,                # ISO format (YYYY-MM-DD)
    "ticker": str,              # Ticker symbol
    "transaction_type": str,    # "Buy" or "Sell"
    "quantity": float,          # Number of shares
    "entry_price": float,       # Price per share
    "fees": float,              # Transaction fees
    "notes": str                # User notes
}
```

## Building a New Portfolio Module

### Example: Portfolio Risk Analysis Module

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout
from app.core.theme_manager import ThemeManager
from app.ui.modules.portfolio_construction.services import PortfolioService

class PortfolioRiskModule(QWidget):
    """Portfolio risk metrics and analysis."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # Add widgets for risk metrics (VaR, Sharpe, Beta, etc.)

    def load_portfolio(self, portfolio_name: str = "Default"):
        """Load portfolio and calculate risk metrics."""
        # Get holdings from Portfolio Construction
        holdings = PortfolioService.get_current_holdings_snapshot(portfolio_name)

        # Calculate metrics
        for holding in holdings:
            ticker = holding["ticker"]
            quantity = holding["total_quantity"]
            # Fetch historical prices, calculate volatility, etc.
```

## Module Integration Checklist

When creating a new Portfolio module:

- [ ] Register in `config.py` under `MODULE_SECTIONS["Portfolio"]`
- [ ] Add to `main.py` with `hub.add_module(id, module)`
- [ ] Pass `theme_manager` to constructor
- [ ] Implement `_apply_theme()` method with theme switching support
- [ ] Use PortfolioService API to access portfolio data
- [ ] Follow naming: `{name}_module.py` for main widget
- [ ] Use module-scoped services in `modules/{name}/services/`
- [ ] Document any new shared APIs

## Planned Modules

Future modules will integrate with Portfolio Construction:

- **Portfolio Risk Analysis**: VaR, Sharpe ratio, correlation matrix
- **Tax Reporting**: Capital gains, cost basis tracking, tax-loss harvesting
- **Performance Attribution**: Sector/security contribution analysis
- **Rebalancing Tools**: Target allocation vs actual, rebalancing suggestions
- **Monte Carlo Simulation**: Portfolio outcome projections
- **Dividend Tracker**: Income tracking and forecasting

## Data Persistence

Portfolios are stored in `~/.quant_terminal/portfolios/`:
- Format: JSON
- File naming: `{portfolio_name}.json`
- Auto-saves on transaction changes (Portfolio Construction module)
- Other modules read-only access via PortfolioService API

## Best Practices

1. **Read-only access**: Other modules should NOT modify portfolio data directly
2. **Price caching**: Use PortfolioService.fetch_current_prices() for consistency
3. **Error handling**: Portfolio may not exist, handle None returns gracefully
4. **Theme-aware**: All modules must respond to theme_changed signal
5. **Module-scoped services**: Keep services in `modules/{name}/services/` not global

## Common Patterns

### Loading Portfolio on Module Open

```python
def showEvent(self, event):
    """Load default portfolio when module is shown."""
    super().showEvent(event)
    if not self._loaded:
        self.load_portfolio("Default")
        self._loaded = True
```

### Refreshing on Portfolio Changes

Portfolio Construction emits no signals for changes. Other modules should:
- Provide manual "Refresh" button
- Auto-refresh when module is shown (via `showEvent`)
- Watch for file system changes (advanced, not required)

### Using Market Data

```python
from app.services.market_data import fetch_price_history

# Fetch historical data for risk calculations
df = fetch_price_history("AAPL", period="1y", interval="1d")
returns = df["Close"].pct_change()
volatility = returns.std() * (252 ** 0.5)  # Annualized
```

## Architecture Notes

- **Composition over inheritance**: Portfolio modules are QWidgets, not subclasses of PortfolioConstructionModule
- **Service-based**: Business logic in services, widgets for UI only
- **Signal-based**: Use Qt signals for widget communication
- **Stateless services**: PortfolioService has no instance state, all static methods
- **Theme-driven**: All styling via theme manager, avoid hardcoded colors
