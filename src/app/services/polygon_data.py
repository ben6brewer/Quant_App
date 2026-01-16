"""
Polygon.io market data service.

Fetches OHLCV data from Polygon.io API with rate limiting and error handling.
"""

from __future__ import annotations

import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    import pandas as pd

from app.core.config import (
    POLYGON_BASE_URL,
    POLYGON_BATCH_CONCURRENCY,
    POLYGON_RATE_LIMIT_CALLS,
    POLYGON_RATE_LIMIT_ENABLED,
    POLYGON_RATE_LIMIT_PERIOD,
    POLYGON_TIMESPAN_MAP,
)

# Rate limiting state (thread-safe)
_rate_limit_lock = threading.Lock()
_request_timestamps: list[float] = []


class PolygonDataService:
    """
    Service for fetching market data from Polygon.io API.

    Features:
    - Rate limiting (respects Starter plan limits)
    - Ticker format conversion (Yahoo format -> Polygon format)
    - Retry logic with exponential backoff
    - Returns DataFrame compatible with existing interface
    """

    _api_key: Optional[str] = None
    _session: Optional["requests.Session"] = None
    _session_lock = threading.Lock()

    @classmethod
    def _get_session(cls) -> "requests.Session":
        """Get or create a shared requests Session for connection pooling."""
        if cls._session is None:
            with cls._session_lock:
                if cls._session is None:
                    import requests
                    from requests.adapters import HTTPAdapter
                    from urllib3.util.retry import Retry

                    session = requests.Session()

                    # Configure connection pooling (100 connections matches worker count)
                    retry_strategy = Retry(
                        total=3,
                        backoff_factor=0.5,
                        status_forcelist=[429, 500, 502, 503, 504],
                    )
                    adapter = HTTPAdapter(
                        pool_connections=100,
                        pool_maxsize=100,
                        max_retries=retry_strategy,
                    )
                    session.mount("https://", adapter)
                    session.mount("http://", adapter)

                    cls._session = session

        return cls._session

    @classmethod
    def _load_api_key(cls) -> Optional[str]:
        """Load API key from environment or .env file."""
        if cls._api_key is not None:
            return cls._api_key

        # Lazy import to avoid startup cost
        from dotenv import load_dotenv

        # Load from project root .env file
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        load_dotenv(env_path)

        cls._api_key = os.getenv("POLYGON_API_KEY")
        return cls._api_key

    @classmethod
    def _convert_ticker(cls, yahoo_ticker: str) -> str:
        """
        Convert Yahoo Finance ticker format to Polygon format.

        Conversions:
        - BTC-USD -> X:BTCUSD (crypto)
        - ETH-USD -> X:ETHUSD (crypto)
        - BRK-B -> BRK.B (share classes: hyphen to dot)
        - AAPL -> AAPL (stocks unchanged)
        - ^IRX -> I:IRX (indices)
        - ^SPX -> I:SPX (indices)
        """
        ticker = yahoo_ticker.upper().strip()

        # Crypto: BTC-USD -> X:BTCUSD
        if ticker.endswith("-USD"):
            base = ticker.replace("-USD", "")
            return f"X:{base}USD"

        # Indices: ^IRX -> I:IRX
        if ticker.startswith("^"):
            return f"I:{ticker[1:]}"

        # Share classes: BRK-B -> BRK.B (Yahoo uses hyphen, Polygon uses dot)
        if "-" in ticker:
            return ticker.replace("-", ".")

        # Stocks: unchanged
        return ticker

    @classmethod
    def _wait_for_rate_limit(cls) -> None:
        """Implement rate limiting for Polygon API (only if enabled)."""
        # Skip rate limiting for unlimited tier
        if not POLYGON_RATE_LIMIT_ENABLED:
            return

        global _request_timestamps

        with _rate_limit_lock:
            now = time.time()
            # Remove timestamps older than rate limit period
            _request_timestamps = [
                ts
                for ts in _request_timestamps
                if now - ts < POLYGON_RATE_LIMIT_PERIOD
            ]

            # If at limit, wait
            if len(_request_timestamps) >= POLYGON_RATE_LIMIT_CALLS:
                wait_time = POLYGON_RATE_LIMIT_PERIOD - (now - _request_timestamps[0])
                if wait_time > 0:
                    print(f"Rate limit reached, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time + 0.1)

            # Record this request
            _request_timestamps.append(time.time())

    @classmethod
    def _calculate_date_range(cls, period: str) -> tuple[str, str]:
        """
        Convert period string to from/to dates.

        Args:
            period: "max", "1y", "6mo", "1mo", "5d", etc.

        Returns:
            (from_date, to_date) in YYYY-MM-DD format
        """
        today = datetime.now()
        to_date = today.strftime("%Y-%m-%d")

        # Polygon Starter plan only provides 5 years of historical data
        # Yahoo Finance backfill handles anything older
        period_map = {
            "1d": 1,
            "5d": 5,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825,
            "10y": 1825,  # Capped at 5 years (Polygon Starter limit)
            "max": 1825,  # Capped at 5 years (Polygon Starter limit)
        }

        days = period_map.get(period.lower(), 1825)  # Default to 5 years
        from_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

        return from_date, to_date

    @classmethod
    def fetch(
        cls,
        ticker: str,
        period: str = "max",
        interval: str = "1d",
    ) -> "pd.DataFrame":
        """
        Fetch OHLCV data from Polygon.io API.

        Args:
            ticker: Yahoo Finance format ticker (e.g., "BTC-USD", "AAPL")
            period: Time period (e.g., "max", "1y", "6mo")
            interval: Data interval (e.g., "1d", "daily")

        Returns:
            DataFrame with OHLCV columns and DatetimeIndex

        Raises:
            ValueError: If API key not configured or no data returned
            RuntimeError: If API request fails after retries
        """
        import pandas as pd
        import requests  # For exception types

        # Get API key
        api_key = cls._load_api_key()
        if not api_key or api_key == "your_api_key_here":
            raise ValueError(
                "POLYGON_API_KEY not found or not configured. "
                "Please create a .env file with POLYGON_API_KEY=your_key"
            )

        # Convert ticker format
        polygon_ticker = cls._convert_ticker(ticker)

        # Warn about index tickers (require higher tier Polygon plan)
        if polygon_ticker.startswith("I:"):
            raise ValueError(
                f"Index ticker '{ticker}' requires Polygon Developer plan or higher. "
                f"Consider using an ETF equivalent (e.g., SPY instead of ^SPX, "
                f"or use Yahoo Finance for indices)."
            )

        # Convert interval to Polygon timespan
        interval_key = interval.lower().replace("1", "").replace("d", "daily")
        if interval_key == "aily":  # Fix for "1d" -> "daily" -> "aily"
            interval_key = "daily"
        timespan = POLYGON_TIMESPAN_MAP.get(interval.lower(), "day")

        # Calculate date range
        from_date, to_date = cls._calculate_date_range(period)

        # Build URL
        url = (
            f"{POLYGON_BASE_URL}/v2/aggs/ticker/{polygon_ticker}"
            f"/range/1/{timespan}/{from_date}/{to_date}"
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": api_key,
        }

        # Rate limiting
        cls._wait_for_rate_limit()

        # Make request with retry logic
        max_retries = 3
        last_error = None
        session = cls._get_session()
        for attempt in range(max_retries):
            try:
                print(f"Fetching {ticker} from Polygon.io (attempt {attempt + 1})...")
                response = session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Check for API errors
                if data.get("status") == "ERROR":
                    error_msg = data.get("error", "Unknown API error")
                    raise ValueError(f"Polygon API error: {error_msg}")

                break
            except requests.RequestException as e:
                last_error = e
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Polygon API request failed after {max_retries} attempts: {e}"
                    )
                wait = 2**attempt
                print(f"Polygon request failed, retrying in {wait}s... ({e})")
                time.sleep(wait)

        # Check for results
        results = data.get("results", [])
        if not results:
            raise ValueError(f"No data returned for ticker '{ticker}' from Polygon.io")

        # Convert to DataFrame
        df = pd.DataFrame(results)

        # Rename columns to match Yahoo Finance format
        column_map = {
            "o": "Open",
            "h": "High",
            "l": "Low",
            "c": "Close",
            "v": "Volume",
            "t": "timestamp",
        }
        df = df.rename(columns=column_map)

        # Convert timestamp (ms) to DatetimeIndex
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("Date", inplace=True)

        # Drop extra columns (vw=volume-weighted avg, n=num transactions, otc=otc flag)
        cols_to_drop = ["timestamp", "vw", "n", "otc"]
        df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)

        # Ensure standard column order and only keep OHLCV
        standard_cols = ["Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in standard_cols if c in df.columns]]
        df.sort_index(inplace=True)

        print(f"Fetched {len(df)} bars for {ticker} from Polygon.io")
        return df

    @classmethod
    def fetch_date_range(
        cls,
        ticker: str,
        from_date: str,
        to_date: str,
    ) -> "pd.DataFrame":
        """
        Fetch OHLCV data for a specific date range.

        Used for incremental updates (only fetching missing days).

        Args:
            ticker: Yahoo Finance format ticker (e.g., "BTC-USD", "AAPL")
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV for the date range

        Raises:
            ValueError: If API key not configured or no data returned
            RuntimeError: If API request fails after retries
        """
        import pandas as pd
        import requests  # For exception types

        # Get API key
        api_key = cls._load_api_key()
        if not api_key or api_key == "your_api_key_here":
            raise ValueError(
                "POLYGON_API_KEY not found or not configured. "
                "Please create a .env file with POLYGON_API_KEY=your_key"
            )

        # Convert ticker format
        polygon_ticker = cls._convert_ticker(ticker)

        # Warn about index tickers (require higher tier Polygon plan)
        if polygon_ticker.startswith("I:"):
            raise ValueError(
                f"Index ticker '{ticker}' requires Polygon Developer plan or higher."
            )

        # Build URL for daily data
        url = (
            f"{POLYGON_BASE_URL}/v2/aggs/ticker/{polygon_ticker}"
            f"/range/1/day/{from_date}/{to_date}"
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": api_key,
        }

        # Rate limiting
        cls._wait_for_rate_limit()

        # Make request with retry logic
        max_retries = 3
        session = cls._get_session()
        for attempt in range(max_retries):
            try:
                print(f"Fetching {ticker} ({from_date} to {to_date}) from Polygon.io...")
                response = session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Check for API errors
                if data.get("status") == "ERROR":
                    error_msg = data.get("error", "Unknown API error")
                    raise ValueError(f"Polygon API error: {error_msg}")

                break
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Polygon API request failed after {max_retries} attempts: {e}"
                    )
                wait = 2**attempt
                print(f"Polygon request failed, retrying in {wait}s... ({e})")
                time.sleep(wait)

        # Check for results
        results = data.get("results", [])
        if not results:
            # No data for this range - return empty DataFrame
            print(f"No new data for {ticker} from {from_date} to {to_date}")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(results)

        # Rename columns to match Yahoo Finance format
        column_map = {
            "o": "Open",
            "h": "High",
            "l": "Low",
            "c": "Close",
            "v": "Volume",
            "t": "timestamp",
        }
        df = df.rename(columns=column_map)

        # Convert timestamp (ms) to DatetimeIndex
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("Date", inplace=True)

        # Drop extra columns
        cols_to_drop = ["timestamp", "vw", "n", "otc"]
        df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)

        # Ensure standard column order and only keep OHLCV
        standard_cols = ["Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in standard_cols if c in df.columns]]
        df.sort_index(inplace=True)

        print(f"Fetched {len(df)} bars for {ticker} (incremental update)")
        return df

    @classmethod
    def fetch_batch_date_range(
        cls,
        tickers: list[str],
        date_ranges: dict[str, tuple[str, str]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, "pd.DataFrame"]:
        """
        Fetch incremental updates for multiple tickers in parallel.

        Uses high concurrency (100 workers) for fast batch fetching.
        Rate limiting only applies if POLYGON_RATE_LIMIT_ENABLED=True.

        Args:
            tickers: List of ticker symbols
            date_ranges: Dict mapping ticker -> (from_date, to_date)
            progress_callback: Optional callback(completed, total, current_ticker)

        Returns:
            Dict mapping ticker -> DataFrame with new data
        """
        import pandas as pd

        if not tickers:
            return {}

        total = len(tickers)
        print(f"Batch fetching {total} tickers from Polygon (incremental updates)...")

        results: dict[str, pd.DataFrame] = {}

        def fetch_one(ticker: str) -> tuple[str, Optional[pd.DataFrame]]:
            """Fetch a single ticker's date range."""
            from_date, to_date = date_ranges.get(ticker, ("", ""))
            if not from_date or not to_date:
                return ticker, None
            try:
                df = cls.fetch_date_range(ticker, from_date, to_date)
                return ticker, df
            except Exception as e:
                print(f"  {ticker}: FAILED ({e})")
                return ticker, None

        # Parallel fetch with ThreadPoolExecutor (100 workers for unlimited tier)
        with ThreadPoolExecutor(max_workers=POLYGON_BATCH_CONCURRENCY) as executor:
            futures = {executor.submit(fetch_one, t): t for t in tickers}
            completed_count = 0

            for future in as_completed(futures):
                ticker, df = future.result()
                completed_count += 1

                if df is not None and not df.empty:
                    results[ticker] = df
                    print(f"  {ticker}: {len(df)} new bars")
                elif df is not None:
                    print(f"  {ticker}: no new data")

                if progress_callback:
                    progress_callback(completed_count, total, ticker)

        print(
            f"Polygon batch complete: {len(results)} tickers with updates"
        )
        return results

    @classmethod
    def fetch_batch_full_history(
        cls,
        tickers: list[str],
        max_workers: int = POLYGON_BATCH_CONCURRENCY,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> tuple[dict[str, "pd.DataFrame"], list[str]]:
        """
        Fetch full 5-year history for multiple tickers with async I/O.

        Uses aiohttp for true async HTTP requests with connection pooling.
        Designed for maximum throughput with Polygon API.

        Args:
            tickers: List of ticker symbols (Yahoo format)
            max_workers: Number of concurrent requests (default from config)
            progress_callback: Optional callback(completed, total, current_ticker)

        Returns:
            Tuple of:
            - Dict mapping ticker -> DataFrame with OHLCV data
            - List of failed tickers (for Yahoo fallback)
        """
        import asyncio

        if not tickers:
            return {}, []

        # Get API key upfront
        api_key = cls._load_api_key()
        if not api_key or api_key == "your_api_key_here":
            print("[Polygon Batch] ERROR: API key not configured")
            return {}, list(tickers)

        # Run the async fetch
        return asyncio.run(
            cls._fetch_batch_full_history_async(
                tickers, api_key, max_workers, progress_callback
            )
        )

    @classmethod
    async def _fetch_batch_full_history_async(
        cls,
        tickers: list[str],
        api_key: str,
        max_concurrent: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> tuple[dict[str, "pd.DataFrame"], list[str]]:
        """Async implementation of batch fetch using aiohttp."""
        import asyncio
        import aiohttp
        import pandas as pd

        total = len(tickers)
        print(f"[Polygon Batch] Starting async fetch for {total} tickers ({max_concurrent} concurrent)...")

        # Calculate date range for 5-year history
        from_date, to_date = cls._calculate_date_range("max")

        results: dict[str, pd.DataFrame] = {}
        failed: list[str] = []
        completed_count = 0

        # Semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_one(
            session: aiohttp.ClientSession,
            ticker: str,
        ) -> tuple[str, Optional[pd.DataFrame], Optional[str]]:
            """Fetch a single ticker's full history."""
            nonlocal completed_count

            polygon_ticker = cls._convert_ticker(ticker)

            # Skip indices (require higher tier)
            if polygon_ticker.startswith("I:"):
                return ticker, None, "index requires Developer plan"

            # Build URL for daily data
            url = (
                f"{POLYGON_BASE_URL}/v2/aggs/ticker/{polygon_ticker}"
                f"/range/1/day/{from_date}/{to_date}"
            )
            params = {
                "adjusted": "true",
                "sort": "asc",
                "limit": "50000",
                "apiKey": api_key,
            }

            # Make request with retry logic
            max_retries = 3
            async with semaphore:
                for attempt in range(max_retries):
                    try:
                        async with session.get(
                            url, params=params, timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status != 200:
                                if attempt == max_retries - 1:
                                    return ticker, None, f"HTTP {response.status}"
                                await asyncio.sleep(2**attempt)
                                continue

                            data = await response.json()

                            if data.get("status") == "ERROR":
                                return ticker, None, data.get("error", "API error")

                            results_data = data.get("results", [])
                            if not results_data:
                                return ticker, None, "no data"

                            # Convert to DataFrame
                            df = pd.DataFrame(results_data)
                            column_map = {
                                "o": "Open",
                                "h": "High",
                                "l": "Low",
                                "c": "Close",
                                "v": "Volume",
                                "t": "timestamp",
                            }
                            df = df.rename(columns=column_map)
                            df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
                            df.set_index("Date", inplace=True)

                            cols_to_drop = ["timestamp", "vw", "n", "otc"]
                            df.drop(
                                columns=[c for c in cols_to_drop if c in df.columns],
                                inplace=True,
                            )

                            standard_cols = ["Open", "High", "Low", "Close", "Volume"]
                            df = df[[c for c in standard_cols if c in df.columns]]
                            df.sort_index(inplace=True)

                            return ticker, df, None

                    except asyncio.TimeoutError:
                        if attempt == max_retries - 1:
                            return ticker, None, "timeout"
                        await asyncio.sleep(2**attempt)
                    except aiohttp.ClientError as e:
                        if attempt == max_retries - 1:
                            return ticker, None, str(e)
                        await asyncio.sleep(2**attempt)

            return ticker, None, "max retries exceeded"

        # Create aiohttp session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=max_concurrent,  # Connection pool size
            limit_per_host=max_concurrent,  # Per-host limit
            ttl_dns_cache=300,  # DNS cache TTL
            enable_cleanup_closed=True,
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            # Create all fetch tasks
            tasks = [fetch_one(session, ticker) for ticker in tickers]

            # Process results as they complete
            for coro in asyncio.as_completed(tasks):
                ticker, df, error = await coro
                completed_count += 1

                if df is not None and not df.empty:
                    results[ticker] = df
                    # Progress logging every 50 tickers or at milestones
                    if completed_count % 50 == 0 or completed_count == total:
                        pct = (completed_count / total) * 100
                        print(
                            f"[Polygon Batch] Progress: {completed_count}/{total} "
                            f"({pct:.1f}%) - {ticker}: {len(df)} bars"
                        )
                else:
                    failed.append(ticker)
                    if error and error != "no data":
                        print(f"  {ticker}: FAILED ({error})")

                if progress_callback:
                    progress_callback(completed_count, total, ticker)

        succeeded = len(results)
        failed_count = len(failed)
        print(f"[Polygon Batch] Complete: {succeeded} succeeded, {failed_count} failed")

        return results, failed

    @classmethod
    def fetch_live_bar(cls, ticker: str) -> "pd.DataFrame | None":
        """
        Fetch today's partial (live) bar for a stock ticker.

        Uses the Polygon snapshot endpoint which provides current day's OHLCV.
        Only works for stocks - crypto requires Polygon upgrade.

        Args:
            ticker: Yahoo Finance format ticker (e.g., "AAPL")

        Returns:
            DataFrame with single row containing today's partial OHLCV, or None if unavailable
        """
        import pandas as pd
        from datetime import datetime

        # Get API key
        api_key = cls._load_api_key()
        if not api_key or api_key == "your_api_key_here":
            return None

        # Convert ticker format
        polygon_ticker = cls._convert_ticker(ticker)

        # Skip crypto and indices - snapshot not available on Starter plan
        if polygon_ticker.startswith("X:") or polygon_ticker.startswith("I:"):
            return None

        # Rate limiting
        cls._wait_for_rate_limit()

        # Fetch stock snapshot
        url = f"{POLYGON_BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{polygon_ticker}"
        params = {"apiKey": api_key}

        try:
            response = cls._get_session().get(url, params=params, timeout=15)
            if response.status_code != 200:
                return None

            data = response.json()
            ticker_data = data.get("ticker", {})
            day_data = ticker_data.get("day", {})

            if not day_data or "o" not in day_data:
                return None

            # Get the actual date from the updated timestamp
            # The "updated" field is in nanoseconds
            updated_ns = ticker_data.get("updated", 0)
            if updated_ns:
                bar_date = datetime.fromtimestamp(updated_ns / 1_000_000_000).date()
            else:
                bar_date = datetime.now().date()

            # Build the bar with the correct date
            df = pd.DataFrame(
                [{
                    "Open": day_data.get("o"),
                    "High": day_data.get("h"),
                    "Low": day_data.get("l"),
                    "Close": day_data.get("c"),
                    "Volume": day_data.get("v", 0),
                }],
                index=pd.DatetimeIndex([bar_date], name="Date"),
            )

            return df

        except Exception as e:
            print(f"Failed to fetch live bar for {ticker}: {e}")
            return None
