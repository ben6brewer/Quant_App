from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from app.core.config import (
    INTERVAL_MAP,
    DEFAULT_PERIOD,
    DATA_FETCH_THREADS,
    POLYGON_BATCH_CONCURRENCY,
    SHOW_DOWNLOAD_PROGRESS,
    ERROR_EMPTY_TICKER,
    ERROR_NO_DATA,
    YAHOO_HISTORICAL_START,
)

if TYPE_CHECKING:
    import pandas as pd


# ============================================================================
# Batch Processing Types
# ============================================================================


class TickerGroup(Enum):
    """Classification groups for batch ticker processing."""

    CACHE_CURRENT = "cache_current"  # Cache is up-to-date, just read
    NEED_YAHOO_BACKFILL = "need_yahoo_backfill"  # Need Yahoo full history
    NEED_POLYGON_UPDATE = "need_polygon_update"  # Need Polygon incremental


@dataclass
class TickerClassification:
    """Classification result for a single ticker."""

    group: TickerGroup
    ticker: str
    cached_df: Optional["pd.DataFrame"] = None
    update_from_date: Optional[str] = None
    update_to_date: Optional[str] = None

# Import the cache manager
from app.services.market_data_cache import MarketDataCache

# Import Polygon.io data service (primary data source)
from app.services.polygon_data import PolygonDataService

# Import Yahoo Finance service (for historical backfill and crypto live prices)
from app.services.yahoo_finance_service import YahooFinanceService

# Import backfill tracker (prevents repeat Yahoo calls)
from app.services.backfill_tracker import BackfillTracker

# Import crypto detection utility
from app.utils.market_hours import is_crypto_ticker

# Create a global cache instance (disk-based parquet cache)
_cache = MarketDataCache()

# Data source version tracking - increment this when switching data sources
# to automatically clear cache and avoid mixing data from different providers
_DATA_SOURCE_VERSION = "polygon_v1"
_VERSION_FILE = Path.home() / ".quant_terminal" / "cache" / ".data_source_version"


def _check_data_source_version() -> None:
    """
    Check if data source has changed and clear cache if needed.

    This ensures we don't mix data from different providers (e.g., Yahoo vs Polygon)
    which could have different adjusted prices or date ranges.
    """
    _VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    if _VERSION_FILE.exists():
        current = _VERSION_FILE.read_text().strip()
        if current == _DATA_SOURCE_VERSION:
            return

    print(f"Data source changed to {_DATA_SOURCE_VERSION}, clearing cache...")
    _cache.clear_cache()
    _VERSION_FILE.write_text(_DATA_SOURCE_VERSION)

# In-memory session cache to avoid repeated parquet reads
# Key: ticker (uppercase), Value: DataFrame
_memory_cache: Dict[str, Any] = {}
_memory_cache_lock = threading.Lock()

# Live bar cache for today's partial data (stocks only)
# Key: ticker, Value: {"df": DataFrame, "timestamp": float}
_live_bar_cache: Dict[str, Any] = {}
_live_bar_cache_lock = threading.Lock()
_LIVE_BAR_REFRESH_SECONDS = 900  # 15 minutes


def _get_from_memory_cache(ticker: str) -> Optional["pd.DataFrame"]:
    """Get DataFrame from memory cache (thread-safe)."""
    with _memory_cache_lock:
        return _memory_cache.get(ticker)


def _set_memory_cache(ticker: str, df: "pd.DataFrame") -> None:
    """Set DataFrame in memory cache (thread-safe)."""
    with _memory_cache_lock:
        _memory_cache[ticker] = df


def _get_live_bar(ticker: str) -> Optional["pd.DataFrame"]:
    """
    Get today's partial (live) bar for a stock ticker.

    Uses a 15-minute cache to avoid excessive API calls.
    Only works for stocks on Polygon Starter plan.

    Args:
        ticker: Ticker symbol

    Returns:
        DataFrame with today's partial bar, or None if unavailable
    """
    import time

    ticker = ticker.upper()

    # Check cache first
    with _live_bar_cache_lock:
        cached = _live_bar_cache.get(ticker)
        if cached:
            elapsed = time.time() - cached["timestamp"]
            if elapsed < _LIVE_BAR_REFRESH_SECONDS:
                return cached["df"]

    # Fetch fresh live bar
    live_bar = PolygonDataService.fetch_live_bar(ticker)

    # Cache the result (even if None)
    with _live_bar_cache_lock:
        _live_bar_cache[ticker] = {
            "df": live_bar,
            "timestamp": time.time(),
        }

    return live_bar


def _append_live_bar(df: "pd.DataFrame", ticker: str) -> "pd.DataFrame":
    """
    Append live bar to daily data if available.

    Only appends if:
    - Live bar is available (stocks only on Starter plan)
    - The live bar's date is not already in the DataFrame

    Args:
        df: DataFrame with daily OHLCV data
        ticker: Ticker symbol

    Returns:
        DataFrame with live bar appended (if applicable)
    """
    import pandas as pd

    live_bar = _get_live_bar(ticker)
    if live_bar is None or live_bar.empty:
        return df

    # Get the date of the live bar
    live_bar_date = live_bar.index[0].date()
    last_cached_date = df.index.max().date()

    # Only append if live bar date is newer than cached data
    if live_bar_date <= last_cached_date:
        return df

    # Append live bar
    combined = pd.concat([df, live_bar])
    combined.sort_index(inplace=True)

    return combined


def _perform_historical_backfill(ticker: str, polygon_df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Perform one-time historical backfill from Yahoo Finance.

    Only fetches data OLDER than what Polygon provides (pre-5-year data).
    This is a one-time operation tracked by BackfillTracker.

    Args:
        ticker: Ticker symbol
        polygon_df: DataFrame from Polygon (up to 5 years)

    Returns:
        Combined DataFrame with Yahoo historical + Polygon data
    """
    import pandas as pd
    from datetime import timedelta

    # Check if already backfilled
    if BackfillTracker.is_backfilled(ticker):
        return polygon_df

    # Get Polygon's earliest date
    polygon_earliest = polygon_df.index.min()

    # Calculate end date for Yahoo fetch (day before Polygon's earliest)
    yahoo_end = (polygon_earliest - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"Checking Yahoo Finance for {ticker} historical data before {yahoo_end}...")

    # Fetch from Yahoo Finance (pre-5-year data)
    try:
        yahoo_df = YahooFinanceService.fetch_historical(
            ticker, YAHOO_HISTORICAL_START, yahoo_end
        )
    except Exception as e:
        # Fail silently - just use Polygon data
        print(f"Yahoo backfill unavailable for {ticker}: {e}")
        BackfillTracker.mark_backfilled(ticker)
        return polygon_df

    # If Yahoo has no older data, mark as backfilled and return Polygon data
    if yahoo_df is None or yahoo_df.empty:
        print(f"No pre-5-year Yahoo data available for {ticker}")
        BackfillTracker.mark_backfilled(ticker)
        return polygon_df

    # Check for gap at boundary (> 5 trading days)
    yahoo_latest = yahoo_df.index.max()
    gap_days = (polygon_earliest - yahoo_latest).days
    if gap_days > 7:  # More than a week gap (accounting for weekends)
        print(f"Warning: {gap_days} day gap at boundary for {ticker} "
              f"(Yahoo ends: {yahoo_latest.date()}, Polygon starts: {polygon_earliest.date()})")
        # Try to fill the gap with Yahoo data
        gap_start = (yahoo_latest + timedelta(days=1)).strftime("%Y-%m-%d")
        gap_end = (polygon_earliest - timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            gap_df = YahooFinanceService.fetch_historical(ticker, gap_start, gap_end)
            if gap_df is not None and not gap_df.empty:
                yahoo_df = pd.concat([yahoo_df, gap_df])
                yahoo_df.sort_index(inplace=True)
                print(f"Filled {len(gap_df)} bars in gap from Yahoo")
        except Exception:
            pass  # Continue without gap fill

    # Merge: Yahoo first, then Polygon (Polygon takes priority for overlaps)
    combined = pd.concat([yahoo_df, polygon_df])
    combined = combined[~combined.index.duplicated(keep='last')]  # Polygon wins
    combined.sort_index(inplace=True)

    print(f"Backfilled {ticker} with {len(yahoo_df)} historical bars from Yahoo Finance")

    # Mark as backfilled
    BackfillTracker.mark_backfilled(ticker)

    return combined


def _perform_incremental_update(ticker: str, cached_df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Fetch only missing days from Polygon and append to cached data.

    Args:
        ticker: Ticker symbol
        cached_df: Existing cached DataFrame

    Returns:
        Updated DataFrame with new data appended
    """
    import pandas as pd
    from datetime import datetime, timedelta

    # Get last cached date
    last_date = cached_df.index.max().date()

    # Calculate date range for update
    start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    # If start > end, no update needed
    if start_date >= end_date:
        return cached_df

    print(f"Incremental update for {ticker}: {start_date} to {end_date}")

    # Fetch missing days from Polygon
    try:
        new_df = PolygonDataService.fetch_date_range(ticker, start_date, end_date)
    except Exception as e:
        print(f"Incremental update failed for {ticker}: {e}")
        return cached_df

    # If no new data, return cached
    if new_df is None or new_df.empty:
        return cached_df

    # Append and deduplicate (keep new data for any overlaps)
    combined = pd.concat([cached_df, new_df])
    combined = combined[~combined.index.duplicated(keep='last')]
    combined.sort_index(inplace=True)

    return combined


def _append_crypto_today(df: "pd.DataFrame", ticker: str) -> "pd.DataFrame":
    """
    Append today's bar for crypto tickers from Yahoo Finance.

    Polygon WebSocket doesn't support crypto on Starter plan,
    so we fetch today's OHLCV from Yahoo Finance instead.

    Args:
        df: Existing DataFrame
        ticker: Crypto ticker (e.g., "BTC-USD")

    Returns:
        DataFrame with today's bar appended if not already present
    """
    import pandas as pd
    from datetime import datetime

    # Only for crypto tickers
    if not is_crypto_ticker(ticker):
        return df

    # Check if today is already in the data
    today = datetime.now().date()
    if df.index.max().date() >= today:
        return df

    print(f"Fetching today's price for crypto {ticker} from Yahoo Finance...")

    # Fetch today's bar from Yahoo
    try:
        today_bar = YahooFinanceService.fetch_today_ohlcv(ticker)
        if today_bar is not None and not today_bar.empty:
            # Only append if the bar date is newer
            bar_date = today_bar.index[0].date()
            if bar_date > df.index.max().date():
                combined = pd.concat([df, today_bar])
                combined = combined[~combined.index.duplicated(keep='last')]
                combined.sort_index(inplace=True)
                print(f"Added today's bar for {ticker} from Yahoo")
                return combined
    except Exception as e:
        print(f"Failed to fetch today's crypto bar for {ticker}: {e}")

    return df


def _load_btc_historical_csv() -> "pd.DataFrame":
    """Load historical BTC data from CSV for pre-Yahoo-Finance dates."""
    import pandas as pd
    from pathlib import Path

    csv_path = Path(__file__).parent / "bitcoin_historical_prices.csv"
    if not csv_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
    # Capitalize column names to match yfinance format
    df.columns = [c.capitalize() for c in df.columns]
    df.index.name = None
    df.sort_index(inplace=True)
    return df


def _prepend_btc_historical(yf_df: "pd.DataFrame") -> "pd.DataFrame":
    """Prepend historical CSV data to BTC-USD Yahoo Finance data."""
    import pandas as pd

    csv_df = _load_btc_historical_csv()
    if csv_df.empty:
        return yf_df

    # Get first date from Yahoo Finance data
    first_yf_date = yf_df.index.min()

    # Filter CSV to dates BEFORE Yahoo Finance starts
    csv_before = csv_df[csv_df.index < first_yf_date]

    if csv_before.empty:
        return yf_df

    # Concatenate: CSV first, then Yahoo Finance
    combined = pd.concat([csv_before, yf_df])
    combined.sort_index(inplace=True)
    return combined


def _perform_yahoo_full_fetch_and_merge(
    ticker: str, existing_df: "pd.DataFrame"
) -> "pd.DataFrame":
    """
    Fetch full Yahoo Finance history and merge with existing data.

    Used when parquet exists but doesn't have Yahoo backfill.
    Fetches full Yahoo history and merges, prioritizing Yahoo data.

    Args:
        ticker: Ticker symbol
        existing_df: Existing DataFrame from parquet (may be Polygon-only)

    Returns:
        Merged DataFrame with Yahoo historical data
    """
    import pandas as pd

    print(f"Fetching full Yahoo history for {ticker} to merge with existing data...")

    # Try to fetch full Yahoo history
    yahoo_df, was_rate_limited = YahooFinanceService.fetch_full_history_safe(ticker)

    if was_rate_limited or yahoo_df is None or yahoo_df.empty:
        # Yahoo failed/rate-limited - keep existing data, don't set flag
        print(f"Yahoo fetch failed for {ticker}, keeping existing Polygon data")
        return existing_df

    # Ensure proper datetime index
    yahoo_df.index = pd.to_datetime(yahoo_df.index)
    yahoo_df.sort_index(inplace=True)

    # Merge: Yahoo data takes priority for overlaps
    # This gives us Yahoo's full history + any recent Polygon data
    combined = pd.concat([yahoo_df, existing_df])
    combined = combined[~combined.index.duplicated(keep='first')]  # Yahoo wins
    combined.sort_index(inplace=True)

    print(f"Merged Yahoo history ({len(yahoo_df)} bars) with existing data for {ticker}")

    # Mark as yahoo_backfilled
    BackfillTracker.mark_yahoo_backfilled(ticker)

    return combined


# ============================================================================
# Batch Processing Functions
# ============================================================================


def classify_tickers(
    tickers: List[str],
) -> Dict[TickerGroup, List[TickerClassification]]:
    """
    Classify tickers into processing groups based on cache state.

    Groups:
    - CACHE_CURRENT: yahoo_backfilled=True AND cache is current
    - NEED_YAHOO_BACKFILL: yahoo_backfilled=False OR no cache
    - NEED_POLYGON_UPDATE: yahoo_backfilled=True AND cache outdated

    Args:
        tickers: List of ticker symbols

    Returns:
        Dict mapping TickerGroup -> list of TickerClassification
    """
    from datetime import datetime, timedelta

    groups: Dict[TickerGroup, List[TickerClassification]] = {
        TickerGroup.CACHE_CURRENT: [],
        TickerGroup.NEED_YAHOO_BACKFILL: [],
        TickerGroup.NEED_POLYGON_UPDATE: [],
    }

    for ticker in tickers:
        ticker = ticker.strip().upper()

        # Check memory cache first
        df = _get_from_memory_cache(ticker)
        if df is not None and not df.empty and _cache.is_cache_current(ticker):
            groups[TickerGroup.CACHE_CURRENT].append(
                TickerClassification(TickerGroup.CACHE_CURRENT, ticker, df)
            )
            continue

        # Check disk cache
        has_parquet = _cache.has_cache(ticker)
        is_yahoo_backfilled = BackfillTracker.is_yahoo_backfilled(ticker)

        if not has_parquet or not is_yahoo_backfilled:
            # Need full Yahoo backfill
            cached_df = _cache.get_cached_data(ticker) if has_parquet else None
            groups[TickerGroup.NEED_YAHOO_BACKFILL].append(
                TickerClassification(
                    TickerGroup.NEED_YAHOO_BACKFILL, ticker, cached_df
                )
            )
        else:
            # Has parquet and yahoo_backfilled - check if current
            cached_df = _cache.get_cached_data(ticker)
            if cached_df is not None and not cached_df.empty:
                if _cache.is_cache_current(ticker):
                    groups[TickerGroup.CACHE_CURRENT].append(
                        TickerClassification(
                            TickerGroup.CACHE_CURRENT, ticker, cached_df
                        )
                    )
                else:
                    # Need Polygon incremental update
                    last_date = cached_df.index.max().date()
                    from_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
                    to_date = datetime.now().strftime("%Y-%m-%d")
                    groups[TickerGroup.NEED_POLYGON_UPDATE].append(
                        TickerClassification(
                            TickerGroup.NEED_POLYGON_UPDATE,
                            ticker,
                            cached_df,
                            from_date,
                            to_date,
                        )
                    )
            else:
                # Empty cached data - need Yahoo backfill
                groups[TickerGroup.NEED_YAHOO_BACKFILL].append(
                    TickerClassification(
                        TickerGroup.NEED_YAHOO_BACKFILL, ticker, None
                    )
                )

    return groups


def fetch_price_history_batch(
    tickers: List[str],
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
) -> Dict[str, "pd.DataFrame"]:
    """
    Fetch price history for multiple tickers with batch optimization.

    Classifies tickers into groups and processes each group optimally:
    - Group A (Cache Current): Direct parquet reads
    - Group B (Need Yahoo Backfill): Single batch yf.download()
    - Group C (Need Polygon Update): Parallel Polygon incremental fetches

    Args:
        tickers: List of ticker symbols
        progress_callback: Optional callback(completed, total, ticker, phase)
                          phase is one of: "classifying", "cache", "yahoo", "polygon"

    Returns:
        Dict mapping ticker -> DataFrame with OHLCV data
    """
    import pandas as pd

    if not tickers:
        return {}

    # Ensure unique, uppercase tickers
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers))
    total = len(tickers)

    print(f"\n=== Batch fetching {total} tickers ===")

    results: Dict[str, pd.DataFrame] = {}

    # Phase 1: Classification
    if progress_callback:
        progress_callback(0, total, "", "classifying")

    groups = classify_tickers(tickers)

    group_a = groups[TickerGroup.CACHE_CURRENT]
    group_b = groups[TickerGroup.NEED_YAHOO_BACKFILL]
    group_c = groups[TickerGroup.NEED_POLYGON_UPDATE]

    print(f"  Group A (cache current): {len(group_a)} tickers")
    print(f"  Group B (need Yahoo): {len(group_b)} tickers")
    print(f"  Group C (need Polygon update): {len(group_c)} tickers")

    # Phase 2: Process Group A (Cache Current) - just return cached data
    if group_a:
        print(f"\nReading {len(group_a)} tickers from cache...")
        for i, classification in enumerate(group_a):
            results[classification.ticker] = classification.cached_df
            _set_memory_cache(classification.ticker, classification.cached_df)
            if progress_callback:
                progress_callback(i + 1, len(group_a), classification.ticker, "cache")

    # Phase 3: Process Group B (Need Yahoo Backfill) - batch download
    if group_b:
        batch_tickers = [c.ticker for c in group_b]

        def yahoo_progress(completed: int, yahoo_total: int, ticker: str) -> None:
            if progress_callback:
                progress_callback(completed, yahoo_total, ticker, "yahoo")

        yahoo_results, failed = YahooFinanceService.fetch_batch_full_history(
            batch_tickers, yahoo_progress
        )

        # Process successful Yahoo results
        for classification in group_b:
            ticker = classification.ticker
            if ticker in yahoo_results:
                df = yahoo_results[ticker]

                # Legacy: Prepend BTC historical CSV if needed
                if ticker == "BTC-USD":
                    df = _prepend_btc_historical(df)

                # Mark as yahoo_backfilled
                BackfillTracker.mark_yahoo_backfilled(ticker)

                # Save to caches
                _cache.save_to_cache(ticker, df)
                _set_memory_cache(ticker, df)

                results[ticker] = df
            elif ticker in failed:
                # Yahoo failed - try Polygon fallback for this ticker
                print(f"  {ticker}: Yahoo failed, trying Polygon fallback...")
                try:
                    df = PolygonDataService.fetch(ticker, period="max", interval="1d")
                    if df is not None and not df.empty:
                        df.index = pd.to_datetime(df.index)
                        df.sort_index(inplace=True)

                        if ticker == "BTC-USD":
                            df = _prepend_btc_historical(df)

                        # Save but DON'T mark yahoo_backfilled
                        _cache.save_to_cache(ticker, df)
                        _set_memory_cache(ticker, df)
                        results[ticker] = df
                        print(f"  {ticker}: Polygon fallback succeeded")
                except Exception as e:
                    print(f"  {ticker}: Both Yahoo and Polygon failed: {e}")

    # Phase 4: Process Group C (Need Polygon Update) - batch incremental
    if group_c:
        print(f"\nBatch updating {len(group_c)} tickers from Polygon...")
        date_ranges = {
            c.ticker: (c.update_from_date, c.update_to_date) for c in group_c
        }

        def polygon_progress(completed: int, poly_total: int, ticker: str) -> None:
            if progress_callback:
                progress_callback(completed, poly_total, ticker, "polygon")

        polygon_results = PolygonDataService.fetch_batch_date_range(
            [c.ticker for c in group_c],
            date_ranges,
            polygon_progress,
        )

        # Merge incremental updates with cached data
        for classification in group_c:
            ticker = classification.ticker
            cached_df = classification.cached_df

            if ticker in polygon_results:
                new_df = polygon_results[ticker]
                combined = pd.concat([cached_df, new_df])
                combined = combined[~combined.index.duplicated(keep="last")]
                combined.sort_index(inplace=True)

                # Save updated data
                _cache.save_to_cache(ticker, combined)
                _set_memory_cache(ticker, combined)
                results[ticker] = combined
            else:
                # No new data from Polygon - use cached
                results[ticker] = cached_df
                _set_memory_cache(ticker, cached_df)

    print(f"\n=== Batch complete: {len(results)}/{total} tickers loaded ===\n")
    return results


def fetch_price_history_batch_polygon_first(
    tickers: List[str],
    max_workers: int = POLYGON_BATCH_CONCURRENCY,
) -> Dict[str, "pd.DataFrame"]:
    """
    Fetch price history for multiple tickers using Polygon as primary source.

    Optimized for Risk Analytics Attribution with ~3000 IWV tickers.
    Uses high concurrency (100 workers) for fast batch fetching.

    Strategy:
    1. Check cache first - return cached data if current
    2. Fetch from Polygon (100 concurrent) for uncached/stale tickers
    3. Yahoo fallback for Polygon failures only
    4. Save all fetched data to cache

    Args:
        tickers: List of ticker symbols
        max_workers: Polygon concurrent workers (default from config)

    Returns:
        Dict mapping ticker -> DataFrame with OHLCV data
    """
    import pandas as pd

    if not tickers:
        return {}

    # Ensure unique, uppercase tickers
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers))
    total = len(tickers)

    print(f"\n=== Polygon-First Batch: {total} tickers ===")

    results: Dict[str, pd.DataFrame] = {}

    # Phase 1: Check cache for all tickers (optimized with parallel reads)
    cached_tickers: List[str] = []
    need_fetch: List[str] = []
    need_disk_check: List[str] = []

    print(f"[Cache] Checking {total} tickers...")

    # First pass: check memory cache (fast)
    for ticker in tickers:
        df = _get_from_memory_cache(ticker)
        if df is not None and not df.empty and _cache.is_cache_current(ticker, df):
            results[ticker] = df
            cached_tickers.append(ticker)
        elif _cache.has_cache(ticker):
            need_disk_check.append(ticker)
        else:
            need_fetch.append(ticker)

    # Second pass: parallel disk cache reads
    if need_disk_check:
        def _check_disk_cache(ticker: str):
            df = _cache.get_cached_data(ticker)
            if df is not None and not df.empty and _cache.is_cache_current(ticker, df):
                return ticker, df, True  # cached and current
            return ticker, df, False  # needs fetch (even if df exists but stale)

        with ThreadPoolExecutor(max_workers=20) as executor:
            disk_results = list(executor.map(_check_disk_cache, need_disk_check))

        for ticker, df, is_current in disk_results:
            if is_current and df is not None:
                _set_memory_cache(ticker, df)
                results[ticker] = df
                cached_tickers.append(ticker)
            else:
                need_fetch.append(ticker)

    print(f"[Cache] {len(cached_tickers)} current, {len(need_fetch)} need fetch")

    if not need_fetch:
        print(f"=== Batch Complete: {len(results)}/{total} tickers loaded (all from cache) ===\n")
        return results

    # Phase 2: Fetch from Polygon (primary source)
    polygon_results, failed_tickers = PolygonDataService.fetch_batch_full_history(
        need_fetch, max_workers=max_workers
    )

    # Process successful Polygon results (parallel cache writes)
    def _save_polygon_ticker(item):
        ticker, df = item
        if df is not None and not df.empty:
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            _cache.save_to_cache(ticker, df)
            return ticker, df
        return ticker, None

    with ThreadPoolExecutor(max_workers=20) as executor:
        saved_items = list(executor.map(_save_polygon_ticker, polygon_results.items()))

    for ticker, df in saved_items:
        if df is not None:
            _set_memory_cache(ticker, df)
            results[ticker] = df

    # Phase 3: Yahoo fallback for failed tickers
    if failed_tickers:
        print(f"[Yahoo Fallback] Fetching {len(failed_tickers)} failed tickers...")

        def yahoo_progress(completed: int, yahoo_total: int, ticker: str) -> None:
            pass  # Silent progress for fallback

        yahoo_results, yahoo_failed = YahooFinanceService.fetch_batch_full_history(
            failed_tickers, yahoo_progress
        )

        # Parallel cache writes for Yahoo results
        def _save_yahoo_ticker(item):
            ticker, df = item
            if df is not None and not df.empty:
                df.index = pd.to_datetime(df.index)
                df.sort_index(inplace=True)
                BackfillTracker.mark_yahoo_backfilled(ticker)
                _cache.save_to_cache(ticker, df)
                return ticker, df
            return ticker, None

        with ThreadPoolExecutor(max_workers=20) as executor:
            yahoo_saved = list(executor.map(_save_yahoo_ticker, yahoo_results.items()))

        for ticker, df in yahoo_saved:
            if df is not None:
                _set_memory_cache(ticker, df)
                results[ticker] = df

        yahoo_succeeded = len(yahoo_results)
        yahoo_failed_count = len(yahoo_failed)
        print(f"[Yahoo Fallback] Complete: {yahoo_succeeded} succeeded, {yahoo_failed_count} failed")

    print(f"=== Batch Complete: {len(results)}/{total} tickers loaded ===\n")
    return results


def fetch_price_history(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = "1d",
    skip_live_bar: bool = False,
) -> "pd.DataFrame":
    """
    Fetch historical price data for a ticker with two-level caching.

    NEW DATA FLOW (Yahoo-first with Polygon fallback):
    1. Check memory cache -> if current, return
    2. Check parquet cache:
       a. If exists AND yahoo_backfilled AND up-to-date -> return cached
       b. If exists but NOT yahoo_backfilled -> Pull Yahoo full history, set flag
       c. If exists AND yahoo_backfilled but OUTDATED -> Polygon incremental update
    3. If NO parquet:
       a. Try Yahoo Finance for full history
       b. If Yahoo rate-limited -> Polygon fallback (5-year), DON'T set flag

    Args:
        ticker: Ticker symbol (e.g., "BTC-USD", "AAPL")
        period: Time period (e.g., "max", "1y", "6mo")
        interval: Data interval (e.g., "1d", "daily", "weekly")
        skip_live_bar: If True, skip fetching today's live bar from Polygon.
            Use this for portfolio operations that don't need intraday precision.

    Returns:
        DataFrame with OHLCV data

    Raises:
        ValueError: If ticker is empty or no data is available
    """
    import pandas as pd

    # Check if data source has changed (auto-clears cache if switching providers)
    _check_data_source_version()

    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError(ERROR_EMPTY_TICKER)

    interval_key = (interval or "1d").strip().lower()
    yf_interval = INTERVAL_MAP.get(interval_key, "1d")

    # Check if we need daily data based on ORIGINAL interval_key (before modification)
    needs_daily = interval_key in ["daily", "1d"]

    # Special handling for yearly interval
    if yf_interval == "1y":
        yf_interval = "1d"  # We'll resample from daily data

    # Helper to append live data (crypto vs stock)
    def _append_live_data(data: "pd.DataFrame") -> "pd.DataFrame":
        """Append today's data: Yahoo for crypto, Polygon snapshot for stocks."""
        if skip_live_bar:
            return data  # Skip live bar fetching for portfolio operations
        if is_crypto_ticker(ticker):
            return _append_crypto_today(data, ticker)
        return _append_live_bar(data, ticker)

    # Helper to return data with appropriate resampling
    def _return_data(data: "pd.DataFrame") -> "pd.DataFrame":
        """Return data with live append and resampling if needed."""
        df_with_live = _append_live_data(data)
        if needs_daily:
            return df_with_live
        return _resample_data(df_with_live, interval_key)

    # LEVEL 1: Check memory cache first (instant, no disk I/O)
    df = _get_from_memory_cache(ticker)
    if df is not None and not df.empty:
        # Memory cache hit - check if still current
        if _cache.is_cache_current(ticker):
            return _return_data(df)

        # Memory cache exists but outdated
        # Check if yahoo_backfilled - determines update strategy
        if BackfillTracker.is_yahoo_backfilled(ticker):
            # Yahoo backfilled - use Polygon for incremental update
            print(f"Memory cache outdated for {ticker}, Polygon incremental update...")
            df = _perform_incremental_update(ticker, df)
        else:
            # Not backfilled - try Yahoo full history
            print(f"Memory cache outdated for {ticker}, trying Yahoo backfill...")
            df = _perform_yahoo_full_fetch_and_merge(ticker, df)

        # Update both caches
        _cache.save_to_cache(ticker, df)
        _set_memory_cache(ticker, df)
        return _return_data(df)

    # LEVEL 2: Check disk cache (parquet)
    if _cache.has_cache(ticker):
        df = _cache.get_cached_data(ticker)
        if df is not None and not df.empty:
            last_date = df.index.max().strftime("%Y-%m-%d")

            # Check if yahoo_backfilled flag is set
            if not BackfillTracker.is_yahoo_backfilled(ticker):
                # Need to backfill with Yahoo full history
                print(f"Parquet exists for {ticker} but not Yahoo backfilled, fetching full Yahoo history...")
                df = _perform_yahoo_full_fetch_and_merge(ticker, df)
                _cache.save_to_cache(ticker, df)

            # Check if cache is current
            if _cache.is_cache_current(ticker):
                print(f"Using cached data for {ticker} (last date: {last_date})")
                _set_memory_cache(ticker, df)
                return _return_data(df)
            else:
                # Cache outdated - use Polygon incremental (since yahoo_backfilled)
                print(f"Cache outdated for {ticker} (last date: {last_date}), Polygon incremental update...")
                df = _perform_incremental_update(ticker, df)
                _cache.save_to_cache(ticker, df)
                _set_memory_cache(ticker, df)
                return _return_data(df)

    # LEVEL 3: No parquet exists - fresh fetch
    # Try Yahoo Finance first (primary source for new data)
    print(f"No cache for {ticker}, trying Yahoo Finance...")
    df, was_rate_limited = YahooFinanceService.fetch_full_history_safe(ticker)

    if not was_rate_limited and df is not None and not df.empty:
        # Yahoo succeeded - mark as backfilled
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        # Legacy: Prepend historical CSV data for BTC-USD
        if ticker == "BTC-USD":
            df = _prepend_btc_historical(df)

        # Mark as yahoo_backfilled and save
        BackfillTracker.mark_yahoo_backfilled(ticker)
        _cache.save_to_cache(ticker, df)
        _set_memory_cache(ticker, df)

        print(f"Fetched {len(df)} bars for {ticker} from Yahoo Finance")
        return _return_data(df)

    # Yahoo rate-limited or failed - Polygon fallback (5-year limit)
    print(f"Yahoo rate-limited for {ticker}, using Polygon fallback (5-year limit)...")
    try:
        df = PolygonDataService.fetch(
            ticker=ticker,
            period="max",
            interval="1d",
        )

        if df is None or df.empty:
            raise ValueError(ERROR_NO_DATA.format(ticker=ticker))

        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        # Legacy: Prepend historical CSV data for BTC-USD
        if ticker == "BTC-USD":
            df = _prepend_btc_historical(df)

        # Save to cache but DON'T set yahoo_backfilled flag
        # (Next access will try Yahoo again for full history)
        _cache.save_to_cache(ticker, df)
        _set_memory_cache(ticker, df)

        print(f"Fetched {len(df)} bars for {ticker} from Polygon (5-year limit)")
        return _return_data(df)

    except Exception as e:
        print(f"Polygon fallback failed for {ticker}: {e}")

        # Last resort: use any cached data (even if outdated)
        if _cache.has_cache(ticker):
            df = _cache.get_cached_data(ticker)
            if df is not None and not df.empty:
                last_date = df.index.max().strftime("%Y-%m-%d")
                print(f"Using outdated cached data for {ticker} (last date: {last_date})")
                _set_memory_cache(ticker, df)
                return _return_data(df)

        # No data available
        raise ValueError(ERROR_NO_DATA.format(ticker=ticker))


def _resample_data(df: "pd.DataFrame", interval_key: str) -> "pd.DataFrame":
    """
    Resample daily data to the requested interval.

    Args:
        df: DataFrame with daily OHLCV data
        interval_key: Interval key (e.g., "weekly", "monthly", "yearly")

    Returns:
        Resampled DataFrame
    """
    if interval_key in ["1d", "daily"]:
        return df
    
    # Define resampling rules
    resample_rules = {
        "weekly": "W",
        "1wk": "W",
        "monthly": "ME",
        "1mo": "ME",
        "yearly": "YE",
        "1y": "YE",
    }
    
    resample_freq = resample_rules.get(interval_key)
    
    if resample_freq is None:
        # Unknown interval, return daily data
        return df
    
    # OHLCV aggregation
    ohlc = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
    }
    if "Volume" in df.columns:
        ohlc["Volume"] = "sum"
    
    # Resample
    df_resampled = df.resample(resample_freq).agg(ohlc).dropna(how="any")
    
    return df_resampled


def clear_cache(ticker: str | None = None) -> None:
    """
    Clear cache for a specific ticker or all tickers.

    Clears memory cache, disk cache, and backfill status.

    Args:
        ticker: Ticker symbol to clear, or None to clear all
    """
    # Clear memory cache
    with _memory_cache_lock:
        if ticker:
            _memory_cache.pop(ticker.upper(), None)
        else:
            _memory_cache.clear()

    # Clear disk cache
    _cache.clear_cache(ticker)

    # Clear backfill status (so next fetch will re-do backfill)
    BackfillTracker.clear_status(ticker)


def fetch_price_history_yahoo(
    ticker: str,
    period: str = "max",
    interval: str = "1d",
) -> "pd.DataFrame":
    """
    Fetch price history using Yahoo Finance exclusively.

    Used by chart module. Checks parquet first, backfills if needed.

    Flow:
    1. Check if parquet exists
    2. If exists but not backfilled -> backfill with Yahoo historical
    3. If most recent date < today -> fetch missing days from Yahoo
    4. If no parquet -> fresh fetch from Yahoo
    5. Save/update parquet

    Args:
        ticker: Ticker symbol (e.g., "BTC-USD", "AAPL")
        period: Time period (e.g., "max", "1y", "6mo") - only "max" fully supported
        interval: Data interval (e.g., "1d", "daily", "weekly")

    Returns:
        DataFrame with OHLCV data

    Raises:
        ValueError: If ticker is empty or no data is available
    """
    import pandas as pd
    from datetime import datetime, timedelta

    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError(ERROR_EMPTY_TICKER)

    interval_key = (interval or "1d").strip().lower()
    needs_daily = interval_key in ["daily", "1d"]

    # LEVEL 1: Check memory cache first
    df = _get_from_memory_cache(ticker)
    if df is not None and not df.empty:
        if _cache.is_cache_current(ticker):
            if needs_daily:
                return df
            return _resample_data(df, interval_key)

    # LEVEL 2: Check if parquet exists
    if _cache.has_cache(ticker):
        df = _cache.get_cached_data(ticker)
        if df is not None and not df.empty:
            last_date = df.index.max().strftime("%Y-%m-%d")
            print(f"Found cached data for {ticker} (last date: {last_date})")

            # Check if backfill needed (Yahoo historical data)
            if not BackfillTracker.is_backfilled(ticker):
                print(f"Backfilling {ticker} with Yahoo historical data...")
                df = _perform_yahoo_backfill(ticker, df)
                _cache.save_to_cache(ticker, df)

            # Check if incremental update needed
            if not _cache.is_cache_current(ticker):
                print(f"Updating {ticker} with recent Yahoo data...")
                df = _perform_yahoo_incremental_update(ticker, df)
                _cache.save_to_cache(ticker, df)

            _set_memory_cache(ticker, df)

            if needs_daily:
                return df
            return _resample_data(df, interval_key)

    # LEVEL 3: Fresh fetch from Yahoo Finance (no parquet exists)
    print(f"Fresh fetch for {ticker} from Yahoo Finance...")
    df = YahooFinanceService.fetch_full_history(ticker)

    if df is None or df.empty:
        raise ValueError(ERROR_NO_DATA.format(ticker=ticker))

    # Mark as backfilled (since we got full history from Yahoo)
    BackfillTracker.mark_backfilled(ticker)

    # Save to cache
    _cache.save_to_cache(ticker, df)
    _set_memory_cache(ticker, df)

    if needs_daily:
        return df
    return _resample_data(df, interval_key)


def _perform_yahoo_backfill(ticker: str, existing_df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Backfill existing parquet with older Yahoo Finance data.

    Used when parquet exists (possibly from Polygon in another module)
    but hasn't been backfilled with Yahoo historical data yet.

    Args:
        ticker: Ticker symbol
        existing_df: Existing DataFrame from parquet

    Returns:
        Combined DataFrame with Yahoo historical + existing data
    """
    import pandas as pd
    from datetime import timedelta

    # Get the earliest date in existing data
    earliest_date = existing_df.index.min()
    yahoo_end = (earliest_date - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"Fetching Yahoo historical data for {ticker} before {yahoo_end}...")

    # Fetch older data from Yahoo
    try:
        yahoo_df = YahooFinanceService.fetch_historical(
            ticker, YAHOO_HISTORICAL_START, yahoo_end
        )
    except Exception as e:
        print(f"Yahoo backfill failed for {ticker}: {e}")
        BackfillTracker.mark_backfilled(ticker)
        return existing_df

    # If no older data, mark as backfilled and return existing
    if yahoo_df is None or yahoo_df.empty:
        print(f"No older Yahoo data available for {ticker}")
        BackfillTracker.mark_backfilled(ticker)
        return existing_df

    # Merge: Yahoo first, existing takes priority for overlaps
    combined = pd.concat([yahoo_df, existing_df])
    combined = combined[~combined.index.duplicated(keep='last')]
    combined.sort_index(inplace=True)

    print(f"Backfilled {ticker} with {len(yahoo_df)} historical bars from Yahoo")

    # Mark as backfilled
    BackfillTracker.mark_backfilled(ticker)

    return combined


def _perform_yahoo_incremental_update(ticker: str, cached_df: "pd.DataFrame") -> "pd.DataFrame":
    """
    Fetch missing recent days from Yahoo Finance.

    Args:
        ticker: Ticker symbol
        cached_df: Existing cached DataFrame

    Returns:
        Updated DataFrame with new data appended
    """
    import pandas as pd
    from datetime import datetime, timedelta

    # Get last cached date
    last_date = cached_df.index.max().date()

    # Calculate date range for update
    start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    # If start > end, no update needed
    if start_date >= end_date:
        return cached_df

    print(f"Fetching Yahoo data for {ticker}: {start_date} to {end_date}")

    # Fetch missing days from Yahoo
    try:
        new_df = YahooFinanceService.fetch_historical(ticker, start_date, end_date)
    except Exception as e:
        print(f"Yahoo incremental update failed for {ticker}: {e}")
        return cached_df

    # If no new data, return cached
    if new_df is None or new_df.empty:
        print(f"No new Yahoo data for {ticker}")
        return cached_df

    # Append and deduplicate
    combined = pd.concat([cached_df, new_df])
    combined = combined[~combined.index.duplicated(keep='last')]
    combined.sort_index(inplace=True)

    print(f"Updated {ticker} with {len(new_df)} new bars from Yahoo")
    return combined