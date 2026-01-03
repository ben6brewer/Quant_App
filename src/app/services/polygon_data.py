"""
Polygon.io market data service.

Fetches OHLCV data from Polygon.io API with rate limiting and error handling.
"""

from __future__ import annotations

import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import pandas as pd

from app.core.config import (
    POLYGON_BASE_URL,
    POLYGON_RATE_LIMIT_CALLS,
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

        # Stocks: unchanged
        return ticker

    @classmethod
    def _wait_for_rate_limit(cls) -> None:
        """Implement rate limiting for Polygon API."""
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
        import requests

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
        for attempt in range(max_retries):
            try:
                print(f"Fetching {ticker} from Polygon.io (attempt {attempt + 1})...")
                response = requests.get(url, params=params, timeout=30)
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
        import requests

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
        for attempt in range(max_retries):
            try:
                print(f"Fetching {ticker} ({from_date} to {to_date}) from Polygon.io...")
                response = requests.get(url, params=params, timeout=30)
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
        import requests
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
            response = requests.get(url, params=params, timeout=15)
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
