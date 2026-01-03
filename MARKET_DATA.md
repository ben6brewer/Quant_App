# Market Data Architecture

This document describes how market data is fetched, stored, updated, and refreshed across all modules in Quant Terminal.

---

## Data Sources

### Yahoo Finance (Primary - Chart Module)
- **Use Case**: All chart module data (historical + live polling)
- **Library**: `yfinance` Python package
- **Rate Limits**: Unofficial API, no documented limits (be reasonable)
- **Docs**: https://github.com/ranaroussi/yfinance

### Polygon.io (Future - Bulk Imports)
- **Use Case**: Bulk historical data imports, WebSocket live data for other modules
- **API Key**: Stored in `.env` as `POLYGON_API_KEY`
- **Plan**: Starter ($29/mo) - 5 years historical, 15-min delayed WebSocket

| Resource | URL |
|----------|-----|
| REST API Docs | https://polygon.io/docs/stocks |
| WebSocket Docs | https://polygon.io/docs/stocks/ws_getting-started |
| Python Client | https://github.com/polygon-io/client-python |
| API Reference | https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to |

#### Polygon API Endpoints Used

```
# Historical Aggregates (OHLCV)
GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}

# Previous Day Bar
GET /v2/aggs/ticker/{ticker}/prev

# WebSocket (Stocks)
wss://delayed.polygon.io/stocks  (Starter plan - 15min delay)
wss://socket.polygon.io/stocks   (Real-time - higher plans)

# WebSocket Subscribe Message
{"action": "subscribe", "params": "AM.AAPL"}  # Minute aggregates
{"action": "subscribe", "params": "A.AAPL"}   # Second aggregates
```

#### Polygon Starter Plan Limits
- **Historical**: 5 years maximum
- **WebSocket**: 15-minute delayed data
- **Crypto**: NOT supported on WebSocket (use Yahoo Finance instead)
- **Rate Limit**: 5 calls/minute (free), unlimited (paid)

---

## Storage Architecture

### Cache Directory Structure

```
~/.quant_terminal/
├── cache/
│   ├── AAPL.parquet          # Daily OHLCV data
│   ├── BTC-USD.parquet       # Crypto daily data
│   ├── MSFT.parquet
│   ├── backfill_status.json  # Tracks Yahoo historical backfill
│   └── .data_source_version  # Tracks data source changes
├── portfolios/               # Portfolio JSON files
├── favorites.json            # Favorited modules
└── *_settings.json           # Module settings
```

### Parquet File Format

Each ticker's parquet file contains:

| Column | Type | Description |
|--------|------|-------------|
| Index | DatetimeIndex | Trading date (timezone-naive) |
| Open | float64 | Opening price |
| High | float64 | High price |
| Low | float64 | Low price |
| Close | float64 | Closing price |
| Volume | int64 | Trading volume |

### Backfill Status Tracking

`backfill_status.json` tracks which tickers have been backfilled with Yahoo historical data:

```json
{
  "AAPL": true,
  "MSFT": true,
  "BTC-USD": true
}
```

This prevents redundant Yahoo Finance calls for pre-5-year data.

---

## Module Data Flows

### Chart Module (Yahoo Finance Only)

```
┌─────────────────────────────────────────────────────────────────┐
│                      load_ticker_max(ticker)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Memory Cache Hit?   │
                    └───────────────────────┘
                         │            │
                        yes           no
                         │            │
                         ▼            ▼
                    [Return]    ┌─────────────────┐
                                │ Parquet Exists? │
                                └─────────────────┘
                                     │        │
                                    yes       no
                                     │        │
                                     ▼        ▼
                         ┌──────────────┐  ┌─────────────────────┐
                         │ Load Parquet │  │ Fresh Yahoo Fetch   │
                         └──────────────┘  │ (fetch_full_history)│
                                │          └─────────────────────┘
                                ▼                    │
                    ┌───────────────────────┐        │
                    │ Backfilled? (Yahoo)   │        │
                    └───────────────────────┘        │
                         │            │              │
                        yes           no             │
                         │            │              │
                         │            ▼              │
                         │   ┌─────────────────┐     │
                         │   │ Backfill with   │     │
                         │   │ Yahoo Historical│     │
                         │   └─────────────────┘     │
                         │            │              │
                         ▼            ▼              │
                    ┌───────────────────────┐        │
                    │   Cache Current?      │        │
                    └───────────────────────┘        │
                         │            │              │
                        yes           no             │
                         │            │              │
                         │            ▼              │
                         │   ┌─────────────────┐     │
                         │   │ Incremental     │     │
                         │   │ Yahoo Update    │     │
                         │   └─────────────────┘     │
                         │            │              │
                         ▼            ▼              ▼
                    ┌─────────────────────────────────────┐
                    │         Save to Parquet             │
                    │         Update Memory Cache         │
                    └─────────────────────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │         Start Live Polling          │
                    └─────────────────────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │                     │
                       [Crypto]              [Stock]
                          │                     │
                          ▼                     ▼
                    ┌───────────┐    ┌─────────────────────┐
                    │ Poll 24/7 │    │ Market Open?        │
                    │ (60s)     │    │ (4am-8pm ET)        │
                    └───────────┘    └─────────────────────┘
                                          │           │
                                         yes          no
                                          │           │
                                          ▼           ▼
                                    ┌──────────┐  [No Timer]
                                    │ Poll 60s │
                                    └──────────┘
```

#### Chart Module Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `fetch_price_history_yahoo()` | `market_data.py:620` | Main entry point for Yahoo-only fetching |
| `_perform_yahoo_backfill()` | `market_data.py:710` | Add pre-5-year historical data |
| `_perform_yahoo_incremental_update()` | `market_data.py:762` | Fetch missing recent days |
| `YahooFinanceService.fetch_full_history()` | `yahoo_finance_service.py:190` | Fresh max history fetch |
| `YahooFinanceService.fetch_today_ohlcv()` | `yahoo_finance_service.py:91` | Live polling (today's bar) |

#### Chart Module Live Polling

| Asset Type | Timer | Interval | Condition |
|------------|-------|----------|-----------|
| Crypto (-USD, -USDT) | `_crypto_poll_timer` | 60 seconds | Always (24/7) |
| Stocks | `_stock_poll_timer` | 60 seconds | Only during extended hours |

**Extended Market Hours** (when stock polling runs):
- Pre-market: 4:00 AM - 9:30 AM ET
- Regular: 9:30 AM - 4:00 PM ET
- After-hours: 4:00 PM - 8:00 PM ET
- Excludes weekends and NYSE holidays

---

### Other Modules (Future - Polygon)

For modules requiring bulk data imports (backtesting, screening, etc.), Polygon will be used:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Bulk Import Module                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Parquet Exists?     │
                    └───────────────────────┘
                         │            │
                        yes           no
                         │            │
                         ▼            ▼
                    [Load Cache]  ┌─────────────────────┐
                         │        │ Polygon REST API    │
                         │        │ (5 years max)       │
                         │        └─────────────────────┘
                         │                  │
                         ▼                  ▼
                    ┌───────────────────────────────────┐
                    │         Check Backfill Flag       │
                    └───────────────────────────────────┘
                         │            │
                        yes           no
                         │            │
                         │            ▼
                         │   ┌─────────────────────────┐
                         │   │ Yahoo Historical        │
                         │   │ (pre-5-year backfill)   │
                         │   └─────────────────────────┘
                         │            │
                         ▼            ▼
                    ┌───────────────────────────────────┐
                    │       Incremental Update          │
                    │       (Polygon for stocks)        │
                    └───────────────────────────────────┘
                                     │
                                     ▼
                    ┌───────────────────────────────────┐
                    │    Optional: WebSocket Live       │
                    │    (15-min delayed on Starter)    │
                    └───────────────────────────────────┘
```

---

## Cache Freshness Logic

### Stock Cache Freshness

A stock's cache is considered **current** if:
1. Last cached date >= last expected trading date

**Last Expected Trading Date** calculation:
- If today is a trading day AND market has closed (after 4 PM ET) → today
- Otherwise → most recent past trading day

### Crypto Cache Freshness

Crypto trades 24/7, so cache is current if:
- Last cached date >= yesterday (crypto always has today's partial data available)

### NYSE Trading Calendar

The system accounts for:
- Weekends (Saturday, Sunday)
- NYSE holidays:
  - New Year's Day
  - MLK Day (3rd Monday of January)
  - Presidents' Day (3rd Monday of February)
  - Good Friday
  - Memorial Day (last Monday of May)
  - Juneteenth (June 19)
  - Independence Day (July 4)
  - Labor Day (1st Monday of September)
  - Thanksgiving (4th Thursday of November)
  - Christmas (December 25)

Holiday observance rules:
- Falls on Saturday → observed Friday
- Falls on Sunday → observed Monday

---

## Key Services

### BackfillTracker (`services/backfill_tracker.py`)

Tracks which tickers have been backfilled with Yahoo historical data.

```python
from app.services.backfill_tracker import BackfillTracker

# Check if ticker has been backfilled
BackfillTracker.is_backfilled("AAPL")  # Returns bool

# Mark ticker as backfilled
BackfillTracker.mark_backfilled("AAPL")

# Clear status (for testing)
BackfillTracker.clear_status("AAPL")  # Single ticker
BackfillTracker.clear_status()         # All tickers
```

### MarketDataCache (`services/market_data_cache.py`)

Handles parquet file storage and retrieval.

```python
from app.services.market_data_cache import MarketDataCache

cache = MarketDataCache()

# Check if cache exists
cache.has_cache("AAPL")  # Returns bool

# Get cached data
df = cache.get_cached_data("AAPL")  # Returns DataFrame or None

# Save to cache
cache.save_to_cache("AAPL", df)

# Check if cache is current
cache.is_cache_current("AAPL")  # Returns bool

# Clear all cache
cache.clear_cache()
```

### YahooFinanceService (`services/yahoo_finance_service.py`)

Yahoo Finance wrapper for all data fetching.

```python
from app.services.yahoo_finance_service import YahooFinanceService

# Fetch date range (for backfill)
df = YahooFinanceService.fetch_historical("AAPL", "1970-01-01", "2019-12-31")

# Fetch today's bar (for live polling)
df = YahooFinanceService.fetch_today_ohlcv("AAPL")

# Fetch full history (fresh load)
df = YahooFinanceService.fetch_full_history("AAPL")

# Validate ticker
is_valid = YahooFinanceService.is_valid_ticker("AAPL")
```

### PolygonDataService (`services/polygon_data.py`)

Polygon.io REST API wrapper (for future bulk imports).

```python
from app.services.polygon_data import PolygonDataService

# Fetch historical data (max 5 years)
df = PolygonDataService.fetch_historical("AAPL", period="max")

# Fetch specific date range
df = PolygonDataService.fetch_date_range("AAPL", "2024-01-01", "2024-12-31")

# Fetch live bar (today's partial)
df = PolygonDataService.fetch_live_bar("AAPL")
```

### Market Hours Utilities (`utils/market_hours.py`)

```python
from app.utils.market_hours import (
    is_crypto_ticker,
    is_nyse_trading_day,
    is_market_open_extended,
    get_last_expected_trading_date,
    is_stock_cache_current,
)

# Check if crypto
is_crypto_ticker("BTC-USD")   # True
is_crypto_ticker("ETH-USDT")  # True
is_crypto_ticker("AAPL")      # False

# Check trading day
is_nyse_trading_day(date(2024, 12, 25))  # False (Christmas)

# Check if market is open (including extended hours)
is_market_open_extended()  # True if 4am-8pm ET on trading day

# Get last expected date for cache freshness
get_last_expected_trading_date()  # Returns date
```

---

## Configuration

### Environment Variables (`.env`)

```bash
POLYGON_API_KEY=your_api_key_here
```

### Config Constants (`core/config.py`)

```python
# Polygon limits
POLYGON_MAX_HISTORY_YEARS = 5
POLYGON_MAX_HISTORY_DAYS = 1825

# Yahoo historical start (for backfill)
YAHOO_HISTORICAL_START = "1970-01-01"
```

---

## Testing & Debugging

### Clear All Cache

```python
# Via Python
from app.services.market_data_cache import MarketDataCache
from app.services.backfill_tracker import BackfillTracker

MarketDataCache().clear_cache()
BackfillTracker.clear_status()
```

Or delete the directory:
```bash
rm -rf ~/.quant_terminal/cache/
```

### Force Re-backfill

```python
from app.services.backfill_tracker import BackfillTracker
BackfillTracker.clear_status("AAPL")  # Clear specific ticker
```

### Check Cache Status

```python
from app.services.market_data_cache import MarketDataCache
from app.services.backfill_tracker import BackfillTracker

cache = MarketDataCache()
ticker = "AAPL"

print(f"Has cache: {cache.has_cache(ticker)}")
print(f"Is current: {cache.is_cache_current(ticker)}")
print(f"Is backfilled: {BackfillTracker.is_backfilled(ticker)}")

df = cache.get_cached_data(ticker)
if df is not None:
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print(f"Total bars: {len(df)}")
```

---

## Future Enhancements

### Planned Polygon Integration

1. **Bulk Import Module**
   - Import multiple tickers at once
   - Use Polygon REST API for 5-year history
   - Backfill with Yahoo for pre-5-year data

2. **WebSocket Live Data**
   - Real-time updates for portfolio modules
   - 15-minute delayed on Starter plan
   - Minute aggregates (AM.* subscription)

3. **Intraday Data**
   - 1-minute, 5-minute, 15-minute bars
   - Stored in separate parquet files per timeframe

### Potential Data Sources

| Source | Use Case | Status |
|--------|----------|--------|
| Yahoo Finance | Chart module, crypto | Active |
| Polygon.io | Bulk imports, WebSocket | API key ready |
| Alpha Vantage | Backup source | Not implemented |
| IEX Cloud | Fundamentals | Not implemented |

---

## Summary

| Module | Data Source | Storage | Live Updates |
|--------|-------------|---------|--------------|
| Chart | Yahoo Finance | Parquet | Polling (60s) |
| Portfolio | Yahoo Finance | Parquet | On-demand |
| Bulk Import | Polygon (future) | Parquet | N/A |
| Screener | Polygon (future) | Parquet | WebSocket |
