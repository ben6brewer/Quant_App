# Portfolio Construction Module

## Overview

Transaction-based portfolio management with real-time calculations, validation safeguards, and data services for analysis modules.

## Architecture

```
portfolio_construction/
├── portfolio_construction_module.py  # Main orchestrator
├── services/
│   ├── portfolio_service.py          # Business logic, validation
│   ├── portfolio_persistence.py      # JSON save/load
│   ├── portfolio_settings_manager.py # User preferences
│   ├── row_index_mapper.py           # Row-to-ID mapping (available)
│   ├── autofill_service.py           # Background price fetch (available)
│   └── focus_manager.py              # Focus tracking (available)
└── widgets/
    ├── transaction_log_table.py      # Main editable table (~2650 lines)
    ├── aggregate_portfolio_table.py  # Holdings summary
    ├── portfolio_controls.py         # Toolbar buttons
    ├── portfolio_dialogs.py          # New/Load/Import dialogs
    ├── pinned_row_manager.py         # Blank row + FREE CASH (available)
    └── mixins/
        ├── field_revert_mixin.py     # Generic field revert
        └── sorting_mixin.py          # Binary search insertion
```

## Data Flow

```
User Input → TransactionLogTable → PortfolioService (validate)
                                 → PortfolioPersistence (save JSON)
                                 → ReturnsDataService (invalidate cache)

Analysis Modules → PortfolioDataService (read-only)
                 → ReturnsDataService (cached parquet)
```

## Key Classes

### TransactionLogTable
Inherits: `FieldRevertMixin`, `SortingMixin`, `EditableTableBase`

- 11 columns: Date, Ticker, Name, Qty, Price, Fees, Type, Daily Close, Live Price, Principal, Market Value
- Pinned rows: Blank entry (row 0), FREE CASH summary (row 1)
- Real-time validation with safeguards (cash balance, position limits)

### PortfolioService (Static Methods)
- `validate_transaction_safeguards()` - Check cash/position constraints
- `calculate_free_cash_summary()` - Aggregate FREE CASH transactions
- `get_transaction_priority()` - Sort order for same-day transactions
- `is_valid_ticker()` - Yahoo Finance validation

### Shared Data Services (in `app/services/`)

```python
from app.services.portfolio_data_service import PortfolioDataService
from app.services.returns_data_service import ReturnsDataService

# Read-only access for analysis modules
portfolio = PortfolioDataService.get_portfolio("name")
holdings = PortfolioDataService.get_holdings("name")
transactions = PortfolioDataService.get_transactions("name")

# Cached daily returns (parquet files)
returns_df = ReturnsDataService.get_daily_returns("name")  # ticker columns
portfolio_returns = ReturnsDataService.get_portfolio_returns("name")  # weighted
```

## Mixins (Reusable)

### FieldRevertMixin
Generic field revert with column config:
```python
REVERT_FIELD_CONFIG = {
    0: ("date", DateInputWidget, "setDate"),
    1: ("ticker", QLineEdit, "setText"),
    # ...
}
self._revert_field(row, col, value)
```

### SortingMixin
Binary search for sorted insertion:
```python
pos = self._find_insertion_position(transaction)  # O(log n)
self._get_transaction_sort_key(tx)  # (date, -priority, -sequence)
```

## Transaction Types

| Type | Priority | Effect |
|------|----------|--------|
| FREE CASH (Buy) | 0 | Add cash to portfolio |
| FREE CASH (Sell) | 1 | Withdraw cash |
| Regular Buy | 2 | Purchase security |
| Regular Sell | 3 | Sell security |

## Validation Safeguards

1. **Cash Balance**: Cannot sell more FREE CASH than available
2. **Position Check**: Cannot sell more shares than owned
3. **Chain Validation**: Edits checked against full transaction history
4. **Ticker Validation**: Yahoo Finance lookup before save

## Storage

- **Portfolios**: `~/.quant_terminal/portfolios/{name}.json`
- **Returns Cache**: `~/.quant_terminal/cache/returns/{name}.parquet`
- **Settings**: `~/.quant_terminal/portfolio_settings.json`

## Live Price Updates

Holdings tab polls Yahoo Finance every 60 seconds for live price updates.

**Trigger:** Portfolio load → `_start_live_updates()`

**Logic:**
- Crypto tickers (-USD, -USDT): Poll 24/7
- Stock tickers: Poll only during extended hours (4am-8pm ET on trading days)
- Pause when module hidden (`hideEvent`)
- Resume when module shown (`showEvent`)

**Flow:**
```
QTimer (60s) → _on_live_poll_tick() → fetch_batch_current_prices()
            → _live_prices_received signal → _apply_live_prices()
            → aggregate_table.update_live_prices(prices)
```

**Updated Columns:** Current Price, Market Value, P&L, Weight

## Future Integration

Services ready but not yet integrated (for further line reduction):
- `RowIndexMapper`: Replace 40+ manual mapping operations
- `FocusManager`: Replace 326-line eventFilter
- `PinnedRowManager`: Replace 338 lines of blank/FREE CASH code
