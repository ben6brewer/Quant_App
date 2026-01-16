# Market Data Architecture

This document describes how market data is fetched, stored, updated, and refreshed across all modules in Quant Terminal.

---

## Data Sources

### Yahoo Finance (Primary)
- **Use Case**: Full historical data, portfolio batch loading, chart module
- **Library**: `yfinance` Python package
- **Rate Limits**: Unofficial API, no documented limits (be reasonable)
- **Docs**: https://github.com/ranaroussi/yfinance

### Polygon.io (Fallback + Incremental Updates)
- **Use Case**: Fallback when Yahoo rate-limited, incremental daily updates
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

`backfill_status.json` tracks which tickers have full Yahoo Finance historical data (schema v2):

```json
{
  "schema_version": 2,
  "AAPL": {"yahoo_backfilled": true, "timestamp": "2024-01-15T10:30:00"},
  "MSFT": {"yahoo_backfilled": true, "timestamp": "2024-01-15T10:31:00"},
  "BTC-USD": {"yahoo_backfilled": true, "timestamp": "2024-01-15T10:32:00"}
}
```

- **`yahoo_backfilled: true`** = Full Yahoo history fetched, use Polygon for incremental updates
- **`yahoo_backfilled: false` or missing** = Only has Polygon data (5-year limit), retry Yahoo on next access

---

## Module Data Flows

### Batch Processing (Portfolio/Analysis Modules)

For loading multiple tickers (portfolios, risk analysis, etc.), the system uses optimized batch processing:

```
┌─────────────────────────────────────────────────────────────────┐
│              fetch_price_history_batch(tickers)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   classify_tickers()   │
                    │   (Pre-sort by state) │
                    └───────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │   Group A:    │   │   Group B:    │   │   Group C:    │
    │ Cache Current │   │ Need Yahoo    │   │ Need Polygon  │
    │ (just read)   │   │ Backfill      │   │ Update        │
    └───────────────┘   └───────────────┘   └───────────────┘
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │ Read parquet  │   │ Single batch  │   │ Parallel      │
    │ (instant)     │   │ yf.download() │   │ Polygon calls │
    └───────────────┘   └───────────────┘   └───────────────┘
            │                   │                   │
            └───────────────────┴───────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Dict[ticker, DataFrame] │
                    └───────────────────────┘
```

**Classification Groups:**

| Group | Condition | Action |
|-------|-----------|--------|
| **A: Cache Current** | `yahoo_backfilled=True` AND cache up-to-date | Read from parquet |
| **B: Need Yahoo** | `yahoo_backfilled=False` OR no parquet | Batch `yf.download()` |
| **C: Need Update** | `yahoo_backfilled=True` AND cache outdated | Parallel Polygon incremental |

**Performance Improvement:**

| Scenario | Sequential | Batch | Speedup |
|----------|-----------|-------|---------|
| 100 tickers, all cached | ~10s | ~2s | 5x |
| 100 tickers, need Yahoo | ~200s | ~15s | 13x |
| 100 tickers, need Polygon | ~120s | ~10s | 12x |

---

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

### Portfolio Construction (Live Price Updates)

Holdings tab polls Yahoo Finance every 60 seconds for live price updates during market hours.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Portfolio Load                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Start Live Polling   │
                    │  (_start_live_updates)│
                    └───────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                 [Crypto]                [Stock]
                    │                       │
                    ▼                       ▼
            ┌───────────────┐    ┌─────────────────────┐
            │ Always poll   │    │ Market Open?        │
            │ (24/7)        │    │ (4am-8pm ET)        │
            └───────────────┘    └─────────────────────┘
                    │                 │           │
                    │                yes          no
                    │                 │           │
                    ▼                 ▼           ▼
            ┌─────────────────────────────┐  [Skip ticker]
            │  fetch_batch_current_prices │
            │  (single yf.download call)  │
            └─────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Update Holdings Tab  │
                    │  (Price, MV, P&L, %)  │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Wait 60 seconds      │
                    │  (QTimer)             │
                    └───────────────────────┘
```

**Behavior:**
- Polling starts when portfolio is loaded
- Pauses when module is hidden (hideEvent)
- Resumes when module is shown (showEvent)
- Crypto tickers (-USD, -USDT): update 24/7
- Stock tickers: only during extended hours (4am-8pm ET on trading days)

---

### Performance Metrics (Live Returns on Load)

Performance Metrics appends today's live return to historical returns when calculating metrics.

```python
# Automatic live return injection in _get_returns():
returns = ReturnsDataService.get_ticker_returns(ticker, start_date, end_date)
returns = ReturnsDataService.append_live_return(returns, ticker)  # Adds today

# For portfolios:
returns = ReturnsDataService.get_time_varying_portfolio_returns(portfolio_name, ...)
returns = ReturnsDataService.append_live_portfolio_return(returns, portfolio_name)
```

**Behavior:**
- Live return appended once on module load (not polling)
- Crypto: always eligible for live return
- Stocks: only during extended market hours
- If today's data already in cache: no additional fetch

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

Tracks which tickers have full Yahoo Finance historical data.

```python
from app.services.backfill_tracker import BackfillTracker

# Check if ticker has Yahoo backfill (full history)
BackfillTracker.is_yahoo_backfilled("AAPL")  # Returns bool

# Mark ticker as having Yahoo backfill
BackfillTracker.mark_yahoo_backfilled("AAPL")

# Get all backfilled tickers
tickers = BackfillTracker.get_all_backfilled()  # Returns list[str]

# Clear status (for testing/re-fetch)
BackfillTracker.clear_status("AAPL")  # Single ticker
BackfillTracker.clear_status()         # All tickers

# Legacy aliases (still work)
BackfillTracker.is_backfilled("AAPL")    # Same as is_yahoo_backfilled
BackfillTracker.mark_backfilled("AAPL")  # Same as mark_yahoo_backfilled
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

# Fetch full history with rate limit detection
df, was_rate_limited = YahooFinanceService.fetch_full_history_safe("AAPL")

# BATCH: Fetch multiple tickers in single yf.download() call
results, failed = YahooFinanceService.fetch_batch_full_history(
    ["AAPL", "MSFT", "GOOGL"],
    progress_callback=lambda completed, total, ticker: print(f"{completed}/{total}")
)
# results = {"AAPL": DataFrame, "MSFT": DataFrame, ...}
# failed = ["INVALID_TICKER", ...]  # Tickers that failed

# BATCH: Fetch current live prices for multiple tickers (for live updates)
prices = YahooFinanceService.fetch_batch_current_prices(["AAPL", "MSFT", "BTC-USD"])
# prices = {"AAPL": 175.50, "MSFT": 380.25, "BTC-USD": 98234.56}

# Validate ticker
is_valid = YahooFinanceService.is_valid_ticker("AAPL")
```

### PolygonDataService (`services/polygon_data.py`)

Polygon.io REST API wrapper for fallback and incremental updates.

```python
from app.services.polygon_data import PolygonDataService

# Fetch historical data (max 5 years)
df = PolygonDataService.fetch("AAPL", period="max", interval="1d")

# Fetch specific date range (for incremental updates)
df = PolygonDataService.fetch_date_range("AAPL", "2024-01-01", "2024-12-31")

# BATCH: Parallel incremental updates for multiple tickers
results = PolygonDataService.fetch_batch_date_range(
    ["AAPL", "MSFT", "GOOGL"],
    date_ranges={
        "AAPL": ("2024-12-01", "2024-12-31"),
        "MSFT": ("2024-12-15", "2024-12-31"),
        "GOOGL": ("2024-12-20", "2024-12-31"),
    },
    progress_callback=lambda completed, total, ticker: print(f"{completed}/{total}")
)
# results = {"AAPL": DataFrame, "MSFT": DataFrame, ...}

# Fetch live bar (today's partial - stocks only)
df = PolygonDataService.fetch_live_bar("AAPL")
```

### Market Data Entry Points (`services/market_data.py`)

Main entry points for fetching market data.

```python
from app.services.market_data import (
    fetch_price_history,
    fetch_price_history_batch,
    fetch_price_history_yahoo,
    clear_cache,
)

# Single ticker (Yahoo-first with Polygon fallback)
df = fetch_price_history("AAPL", period="max", interval="1d")

# BATCH: Multiple tickers with optimized grouping
results = fetch_price_history_batch(
    ["AAPL", "MSFT", "GOOGL", "AMZN"],
    progress_callback=lambda completed, total, ticker, phase: print(f"[{phase}] {ticker}")
)
# results = {"AAPL": DataFrame, "MSFT": DataFrame, ...}
# phase = "classifying" | "cache" | "yahoo" | "polygon"

# Chart module only (Yahoo-only, no Polygon)
df = fetch_price_history_yahoo("AAPL", period="max", interval="1d")

# Clear cache (for testing/re-fetch)
clear_cache("AAPL")  # Single ticker
clear_cache()         # All tickers
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

# Check if crypto (strips whitespace, case-insensitive)
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

### ReturnsDataService (`services/returns_data_service.py`)

Cached daily returns with live return injection.

```python
from app.services.returns_data_service import ReturnsDataService

# Get cached daily returns for portfolio
returns_df = ReturnsDataService.get_daily_returns("portfolio_name")  # DataFrame

# Get weighted portfolio returns (time-varying weights)
returns = ReturnsDataService.get_time_varying_portfolio_returns(
    "portfolio_name",
    start_date="2024-01-01",
    end_date="2024-12-31",
    include_cash=False,
)

# Get single ticker returns
returns = ReturnsDataService.get_ticker_returns("AAPL", start_date="2024-01-01")

# LIVE: Append today's live return to a ticker's returns series
# Only appends if: crypto (24/7) OR stock during market hours
# AND today's data not already in series
updated = ReturnsDataService.append_live_return(returns, "AAPL")

# LIVE: Append today's live portfolio return (weighted across holdings)
updated = ReturnsDataService.append_live_portfolio_return(returns, "portfolio_name")

# Invalidate cache when portfolio changes
ReturnsDataService.invalidate_cache("portfolio_name")
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

### Data Flow Strategy

| Operation | Primary Source | Fallback | Notes |
|-----------|----------------|----------|-------|
| Fresh fetch (no cache) | Yahoo Finance | Polygon (5yr limit) | Don't set `yahoo_backfilled` on Polygon fallback |
| Incremental update | Polygon | - | Only if `yahoo_backfilled=True` |
| Batch fetch | Yahoo batch | Polygon parallel | 10-15x faster than sequential |

### Module Data Sources

| Module | Entry Point | Storage | Live Updates |
|--------|-------------|---------|--------------|
| Chart | `fetch_price_history_yahoo()` | Parquet | Polling (60s) |
| Portfolio Construction | `fetch_price_history_batch()` | Parquet | Polling (60s) - Holdings tab |
| Performance Metrics | `ReturnsDataService` | Parquet | On-load (once) |
| Risk Analytics | `fetch_price_history_batch()` | Parquet | On-demand |
| Distribution | `fetch_price_history_batch()` | Parquet | On-demand |
