"""
Yahoo Finance service for historical backfill and crypto live prices.

Used for:
1. One-time backfill of data older than 5 years (beyond Polygon's limit)
2. Fetching today's OHLCV for crypto tickers (since Polygon WebSocket doesn't support crypto)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import pandas as pd


class YahooFinanceService:
    """
    Service for fetching market data from Yahoo Finance.

    This is a supplementary data source used for:
    - Historical data backfill (pre-5-year data)
    - Crypto today's price (Polygon doesn't support crypto WebSocket on Starter plan)

    All methods use lazy imports for startup performance.
    """

    @classmethod
    def fetch_historical(
        cls,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> "pd.DataFrame":
        """
        Fetch historical OHLCV data from Yahoo Finance.

        Args:
            ticker: Ticker symbol (Yahoo format, e.g., "AAPL", "BTC-USD")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            DataFrame with OHLCV columns and DatetimeIndex.
            Returns empty DataFrame if no data available.

        Note:
            This method fails silently if Yahoo doesn't have data for the
            requested range. It returns an empty DataFrame in that case.
        """
        import pandas as pd
        import yfinance as yf

        ticker = ticker.strip().upper()

        try:
            # Fetch data from Yahoo Finance
            df = yf.download(
                tickers=ticker,
                start=start_date,
                end=end_date,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=1,
            )

            if df is None or df.empty:
                return pd.DataFrame()

            # Handle MultiIndex columns (yfinance sometimes returns these)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            # Ensure standard column names
            df = cls._normalize_columns(df)

            # Ensure DatetimeIndex
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)

            return df

        except Exception as e:
            # Fail silently - return empty DataFrame
            print(f"Yahoo Finance fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    @classmethod
    def fetch_today_ohlcv(cls, ticker: str) -> Optional["pd.DataFrame"]:
        """
        Fetch today's OHLCV bar for a ticker.

        Used primarily for crypto tickers where Polygon WebSocket
        is not available on Starter plan.

        Args:
            ticker: Ticker symbol (e.g., "BTC-USD")

        Returns:
            DataFrame with single row for today, or None if unavailable
        """
        import pandas as pd
        import yfinance as yf

        ticker = ticker.strip().upper()

        try:
            # Fetch last 5 days to ensure we get today's data
            # (sometimes Yahoo has a lag, so we fetch a few days)
            df = yf.download(
                tickers=ticker,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=1,
            )

            if df is None or df.empty:
                return None

            # Handle MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            # Normalize columns
            df = cls._normalize_columns(df)

            # Ensure DatetimeIndex
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)

            # Get the most recent bar (should be today or most recent trading day)
            if not df.empty:
                # Return only the last row
                last_bar = df.iloc[[-1]].copy()
                return last_bar

            return None

        except Exception as e:
            print(f"Yahoo Finance today fetch failed for {ticker}: {e}")
            return None

    @classmethod
    def _normalize_columns(cls, df: "pd.DataFrame") -> "pd.DataFrame":
        """
        Normalize DataFrame columns to standard OHLCV format.

        Ensures columns are: Open, High, Low, Close, Volume
        (capitalized to match Polygon format)

        Args:
            df: DataFrame with various column name formats

        Returns:
            DataFrame with normalized column names
        """
        # Map of possible column names to standard names
        column_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "adj close": "Adj Close",
            "adj_close": "Adj Close",
        }

        # Rename columns (case-insensitive)
        new_columns = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in column_map:
                new_columns[col] = column_map[col_lower]

        if new_columns:
            df = df.rename(columns=new_columns)

        # Keep only OHLCV columns
        standard_cols = ["Open", "High", "Low", "Close", "Volume"]
        available_cols = [c for c in standard_cols if c in df.columns]
        df = df[available_cols]

        return df

    @classmethod
    def fetch_full_history(cls, ticker: str) -> "pd.DataFrame":
        """
        Fetch maximum available history from Yahoo Finance.

        Used for fresh ticker loads in chart module when no parquet exists.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "BTC-USD")

        Returns:
            DataFrame with OHLCV columns and DatetimeIndex.
            Returns empty DataFrame if no data available.
        """
        import pandas as pd
        import yfinance as yf

        ticker = ticker.strip().upper()

        try:
            print(f"Fetching full history for {ticker} from Yahoo Finance...")

            # Fetch maximum history
            df = yf.download(
                tickers=ticker,
                period="max",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=1,
            )

            if df is None or df.empty:
                print(f"No data returned from Yahoo Finance for {ticker}")
                return pd.DataFrame()

            # Handle MultiIndex columns (yfinance sometimes returns these)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            # Ensure standard column names
            df = cls._normalize_columns(df)

            # Ensure DatetimeIndex
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)

            print(f"Fetched {len(df)} bars for {ticker} from Yahoo Finance")
            return df

        except Exception as e:
            print(f"Yahoo Finance full history fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    @classmethod
    def is_valid_ticker(cls, ticker: str) -> bool:
        """
        Check if a ticker exists on Yahoo Finance.

        Args:
            ticker: Ticker symbol

        Returns:
            True if valid, False otherwise
        """
        import yfinance as yf

        ticker = ticker.strip().upper()

        try:
            info = yf.Ticker(ticker).info
            # Check if we got valid data
            return info is not None and info.get("regularMarketPrice") is not None
        except Exception:
            return False
