"""Benchmark Returns Service - Caches daily returns for ETF constituents.

This service manages cached returns data for ETF constituents used in
performance attribution calculations.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd


class BenchmarkReturnsService:
    """
    Manages cached returns data for ETF constituents.

    Cache structure:
        ~/.quant_terminal/cache/benchmark/{ETF}/{TICKER}.parquet

    Features:
    - Memory cache for session-persistent data
    - Disk cache with parquet format
    - Incremental updates via Polygon API
    - Thread-safe access
    """

    _CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "benchmark"
    _memory_cache: Dict[str, "pd.DataFrame"] = {}
    _cache_lock = threading.Lock()

    @classmethod
    def get_constituent_returns(
        cls,
        etf_symbol: str,
        tickers: List[str],
        lookback_years: int = 5,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> "pd.DataFrame":
        """
        Get daily returns for ETF constituent tickers.

        Args:
            etf_symbol: ETF ticker (e.g., "IWV")
            tickers: List of constituent tickers to fetch
            lookback_years: Years of history (default 5, matches Polygon limit)
            progress_callback: Optional callback(completed, total, ticker)

        Returns:
            DataFrame with tickers as columns, dates as index, returns as values
        """
        import pandas as pd

        if not tickers:
            return pd.DataFrame()

        etf_dir = cls._get_etf_cache_dir(etf_symbol)
        results: Dict[str, pd.Series] = {}

        # Classify tickers into cache status
        need_fetch: List[str] = []
        need_update: Dict[str, str] = {}  # ticker -> from_date

        for ticker in tickers:
            cache_path = cls._get_ticker_cache_path(etf_symbol, ticker)

            # Check memory cache first
            cache_key = f"{etf_symbol}:{ticker}"
            with cls._cache_lock:
                if cache_key in cls._memory_cache:
                    cached = cls._memory_cache[cache_key]
                    if cls._is_cache_current(cached):
                        results[ticker] = cached["return"]
                        continue

            # Check disk cache
            if cache_path.exists():
                try:
                    cached_df = pd.read_parquet(cache_path)
                    if not cached_df.empty:
                        last_date = cached_df.index.max()
                        if cls._is_cache_current(cached_df):
                            # Cache is current, use it
                            results[ticker] = cached_df["return"]
                            # Store in memory cache
                            with cls._cache_lock:
                                cls._memory_cache[cache_key] = cached_df
                            continue
                        else:
                            # Cache exists but needs update
                            from_date = (last_date + timedelta(days=1)).strftime(
                                "%Y-%m-%d"
                            )
                            need_update[ticker] = from_date
                            continue
                except Exception as e:
                    print(f"[BenchmarkReturns] Error reading cache for {ticker}: {e}")

            # No cache, need full fetch
            need_fetch.append(ticker)

        # Fetch missing data
        if need_fetch or need_update:
            cls._fetch_and_cache(
                etf_symbol,
                need_fetch,
                need_update,
                lookback_years,
                progress_callback,
            )

            # Re-read cached data
            for ticker in need_fetch + list(need_update.keys()):
                cache_path = cls._get_ticker_cache_path(etf_symbol, ticker)
                if cache_path.exists():
                    try:
                        cached_df = pd.read_parquet(cache_path)
                        if not cached_df.empty:
                            results[ticker] = cached_df["return"]
                            cache_key = f"{etf_symbol}:{ticker}"
                            with cls._cache_lock:
                                cls._memory_cache[cache_key] = cached_df
                    except Exception as e:
                        print(f"[BenchmarkReturns] Error reading {ticker}: {e}")

        # Combine into single DataFrame
        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df.sort_index(inplace=True)
        return df

    @classmethod
    def _fetch_and_cache(
        cls,
        etf_symbol: str,
        need_fetch: List[str],
        need_update: Dict[str, str],
        lookback_years: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> None:
        """
        Fetch missing/outdated data and cache it.

        Args:
            etf_symbol: ETF ticker
            need_fetch: Tickers needing full history
            need_update: Tickers needing incremental update (ticker -> from_date)
            lookback_years: Years of history to fetch
            progress_callback: Optional progress callback
        """
        import pandas as pd

        from app.services.polygon_data import PolygonDataService

        today = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_years * 365)).strftime(
            "%Y-%m-%d"
        )

        # Prepare date ranges for batch fetch
        all_tickers = need_fetch + list(need_update.keys())
        date_ranges: Dict[str, tuple] = {}

        for ticker in need_fetch:
            date_ranges[ticker] = (start_date, today)

        for ticker, from_date in need_update.items():
            date_ranges[ticker] = (from_date, today)

        if not date_ranges:
            return

        total = len(date_ranges)
        print(f"[BenchmarkReturns] Fetching {total} tickers...")

        # Fetch in batches using Polygon
        try:
            price_data = PolygonDataService.fetch_batch_date_range(
                list(date_ranges.keys()),
                date_ranges,
                progress_callback,
            )
        except Exception as e:
            print(f"[BenchmarkReturns] Batch fetch error: {e}")
            price_data = {}

        # Process and cache each ticker
        etf_dir = cls._get_etf_cache_dir(etf_symbol)
        etf_dir.mkdir(parents=True, exist_ok=True)

        for ticker, prices_df in price_data.items():
            if prices_df is None or prices_df.empty:
                continue

            cache_path = cls._get_ticker_cache_path(etf_symbol, ticker)

            try:
                # Calculate returns
                returns = prices_df["Close"].pct_change().dropna()

                if returns.empty:
                    continue

                # Create returns DataFrame
                returns_df = pd.DataFrame({"return": returns})

                # If updating, merge with existing cache
                if ticker in need_update and cache_path.exists():
                    try:
                        existing = pd.read_parquet(cache_path)
                        # Combine, preferring new data for overlaps
                        combined = pd.concat([existing, returns_df])
                        combined = combined[~combined.index.duplicated(keep="last")]
                        combined.sort_index(inplace=True)
                        returns_df = combined
                    except Exception:
                        pass  # Use new data only

                # Save to cache
                returns_df.to_parquet(cache_path)
                print(f"  Cached {ticker}: {len(returns_df)} returns")

            except Exception as e:
                print(f"[BenchmarkReturns] Error caching {ticker}: {e}")

    @classmethod
    def _get_etf_cache_dir(cls, etf_symbol: str) -> Path:
        """Get cache directory for an ETF."""
        safe_etf = etf_symbol.upper().replace("/", "_").replace("\\", "_")
        return cls._CACHE_DIR / safe_etf

    @classmethod
    def _get_ticker_cache_path(cls, etf_symbol: str, ticker: str) -> Path:
        """Get cache file path for a ticker within an ETF."""
        etf_dir = cls._get_etf_cache_dir(etf_symbol)
        safe_ticker = ticker.upper().replace("/", "_").replace("\\", "_")
        return etf_dir / f"{safe_ticker}.parquet"

    @classmethod
    def _is_cache_current(cls, df: "pd.DataFrame") -> bool:
        """
        Check if cached data is current.

        Cache is current if last date >= last trading day.
        """
        from app.utils.market_hours import is_stock_cache_current

        if df is None or df.empty:
            return False

        last_date = df.index.max().date()
        return is_stock_cache_current(last_date)

    @classmethod
    def clear_cache(cls, etf_symbol: Optional[str] = None) -> None:
        """
        Clear cached returns data.

        Args:
            etf_symbol: ETF to clear, or None to clear all
        """
        with cls._cache_lock:
            if etf_symbol:
                # Clear specific ETF
                etf_dir = cls._get_etf_cache_dir(etf_symbol)
                if etf_dir.exists():
                    for cache_file in etf_dir.glob("*.parquet"):
                        cache_file.unlink()
                    print(f"Cleared benchmark cache for {etf_symbol}")

                # Clear memory cache for this ETF
                keys_to_remove = [
                    k for k in cls._memory_cache.keys() if k.startswith(f"{etf_symbol}:")
                ]
                for key in keys_to_remove:
                    del cls._memory_cache[key]
            else:
                # Clear all
                if cls._CACHE_DIR.exists():
                    for etf_dir in cls._CACHE_DIR.iterdir():
                        if etf_dir.is_dir():
                            for cache_file in etf_dir.glob("*.parquet"):
                                cache_file.unlink()
                    print("Cleared all benchmark caches")

                cls._memory_cache.clear()

    @classmethod
    def get_cache_info(cls, etf_symbol: str) -> Dict:
        """
        Get information about cached data for an ETF.

        Returns:
            Dict with cache statistics
        """
        etf_dir = cls._get_etf_cache_dir(etf_symbol)

        if not etf_dir.exists():
            return {"exists": False, "num_tickers": 0, "total_size_mb": 0}

        cache_files = list(etf_dir.glob("*.parquet"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "exists": True,
            "num_tickers": len(cache_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
