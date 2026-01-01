from __future__ import annotations

import threading
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

from app.core.config import (
    INTERVAL_MAP,
    DEFAULT_PERIOD,
    DATA_FETCH_THREADS,
    SHOW_DOWNLOAD_PROGRESS,
    ERROR_EMPTY_TICKER,
    ERROR_NO_DATA,
)

# Import the cache manager
from app.services.market_data_cache import MarketDataCache

# Create a global cache instance (disk-based parquet cache)
_cache = MarketDataCache()

# In-memory session cache to avoid repeated parquet reads
# Key: ticker (uppercase), Value: DataFrame
_memory_cache: Dict[str, pd.DataFrame] = {}
_memory_cache_lock = threading.Lock()


def _get_from_memory_cache(ticker: str) -> Optional[pd.DataFrame]:
    """Get DataFrame from memory cache (thread-safe)."""
    with _memory_cache_lock:
        return _memory_cache.get(ticker)


def _set_memory_cache(ticker: str, df: pd.DataFrame) -> None:
    """Set DataFrame in memory cache (thread-safe)."""
    with _memory_cache_lock:
        _memory_cache[ticker] = df


def fetch_price_history(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Fetch historical price data for a ticker with two-level caching.

    Caching strategy (two levels for performance):
    1. Memory cache: In-session cache to avoid repeated parquet reads
    2. Disk cache: Parquet files for persistence across sessions

    - Check memory cache first (instant)
    - If not in memory, check disk cache
    - If disk cache current, load to memory and return
    - If outdated or missing, fetch from Yahoo Finance
    - If fetch fails (offline), return cached data if available
    - Resample cached daily data as needed for other intervals

    Args:
        ticker: Ticker symbol (e.g., "BTC-USD", "AAPL")
        period: Time period (e.g., "max", "1y", "6mo")
        interval: Data interval (e.g., "1d", "daily", "weekly")

    Returns:
        DataFrame with OHLCV data

    Raises:
        ValueError: If ticker is empty or no data is available
    """
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

    # LEVEL 1: Check memory cache first (instant, no disk I/O)
    df = _get_from_memory_cache(ticker)
    if df is not None and not df.empty:
        # Memory cache hit - check if still current
        if _cache.is_cache_current(ticker):
            if needs_daily:
                return df
            else:
                return _resample_data(df, interval_key)
        # Memory cache exists but outdated - will try to refresh below

    # LEVEL 2: Check disk cache (parquet)
    if needs_daily:
        if _cache.is_cache_current(ticker):
            df = _cache.get_cached_data(ticker)
            if df is not None and not df.empty:
                last_date = df.index.max().strftime("%Y-%m-%d")
                print(f"Using cached data for {ticker} (last date: {last_date})")
                # Store in memory cache for subsequent reads
                _set_memory_cache(ticker, df)
                return df
    else:
        # For non-daily intervals, check if we have cached daily data to resample
        if _cache.has_cache(ticker):
            df = _cache.get_cached_data(ticker)
            if df is not None and not df.empty:
                last_date = df.index.max().strftime("%Y-%m-%d")
                is_current = _cache.is_cache_current(ticker)
                status = "current" if is_current else "outdated"
                print(f"Using cached daily data for {ticker} ({status}, last date: {last_date})")
                # Store in memory cache for subsequent reads
                _set_memory_cache(ticker, df)
                # Resample to requested interval
                return _resample_data(df, interval_key)

    # Try to fetch fresh data from Yahoo Finance
    try:
        print(f"Fetching fresh data for {ticker} from Yahoo Finance...")

        # Always fetch daily data for max period (for caching)
        df = yf.download(
            tickers=ticker,
            period="max",
            interval="1d",
            auto_adjust=False,
            progress=SHOW_DOWNLOAD_PROGRESS,
            threads=DATA_FETCH_THREADS,
        )

        if df is None or df.empty:
            raise ValueError(ERROR_NO_DATA.format(ticker=ticker))

        # Sometimes yfinance returns MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        # Cache the daily data (both disk and memory)
        _cache.save_to_cache(ticker, df)
        _set_memory_cache(ticker, df)

        # If user needs non-daily interval, resample
        if not needs_daily:
            return _resample_data(df, interval_key)

        return df

    except Exception as e:
        # Fetch failed - try to use cached data as fallback (even if outdated)
        print(f"Failed to fetch {ticker} from Yahoo Finance: {e}")

        if _cache.has_cache(ticker):
            df = _cache.get_cached_data(ticker)
            if df is not None and not df.empty:
                last_date = df.index.max().strftime("%Y-%m-%d")
                print(f"Using outdated cached data for {ticker} (last date: {last_date})")
                # Store in memory cache
                _set_memory_cache(ticker, df)

                # Resample if needed
                if not needs_daily:
                    return _resample_data(df, interval_key)

                return df

        # No cache available, re-raise the error
        raise ValueError(ERROR_NO_DATA.format(ticker=ticker))


def _resample_data(df: pd.DataFrame, interval_key: str) -> pd.DataFrame:
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

    Clears both memory cache and disk cache.

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