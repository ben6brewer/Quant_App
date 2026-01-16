"""
Yahoo Finance service for historical backfill and crypto live prices.

Used for:
1. One-time backfill of data older than 5 years (beyond Polygon's limit)
2. Fetching today's OHLCV for crypto tickers (since Polygon WebSocket doesn't support crypto)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional

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

            # Also cache metadata (name, sector, etc.) for this ticker
            try:
                from app.services.ticker_metadata_service import TickerMetadataService

                TickerMetadataService.get_metadata(ticker)
            except Exception as meta_err:
                # Don't fail the fetch if metadata caching fails
                print(f"Warning: Could not cache metadata for {ticker}: {meta_err}")

            return df

        except Exception as e:
            print(f"Yahoo Finance full history fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    @classmethod
    def fetch_full_history_safe(
        cls, ticker: str
    ) -> tuple["pd.DataFrame", bool]:
        """
        Fetch full history with rate limit detection.

        This method wraps fetch_full_history() and detects rate limiting
        by checking for empty responses or exceptions.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "BTC-USD")

        Returns:
            Tuple of (DataFrame, was_rate_limited):
            - If successful: (DataFrame with data, False)
            - If rate limited: (empty DataFrame, True)
        """
        import pandas as pd

        try:
            df = cls.fetch_full_history(ticker)

            # Empty DataFrame indicates rate limiting or invalid ticker
            if df is None or df.empty:
                return (pd.DataFrame(), True)

            return (df, False)

        except Exception as e:
            # Any exception is treated as rate limiting
            print(f"Yahoo Finance rate limited or failed for {ticker}: {e}")
            return (pd.DataFrame(), True)

    @classmethod
    def fetch_batch_full_history(
        cls,
        tickers: list[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> tuple[dict[str, "pd.DataFrame"], list[str]]:
        """
        Fetch full history for multiple tickers in a single yf.download call.

        This is much faster than sequential single-ticker fetches for portfolios.
        Uses yfinance's native multi-ticker support.

        Args:
            tickers: List of ticker symbols
            progress_callback: Optional callback(completed, total, current_ticker)

        Returns:
            Tuple of:
            - Dict mapping ticker -> DataFrame with OHLCV data
            - List of failed tickers (for retry or fallback)
        """
        import pandas as pd
        import yfinance as yf

        if not tickers:
            return {}, []

        # Normalize tickers
        tickers = [t.strip().upper() for t in tickers]
        total = len(tickers)

        print(f"Batch fetching {total} tickers from Yahoo Finance...")

        try:
            # Single batch download - use space-separated string for multiple tickers
            # group_by="ticker" gives us MultiIndex columns grouped by ticker
            df = yf.download(
                tickers=" ".join(tickers) if len(tickers) > 1 else tickers[0],
                period="max",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,  # Enable yfinance internal threading for batch
                group_by="ticker" if len(tickers) > 1 else "column",
            )

            if df is None or df.empty:
                print("Yahoo Finance batch download returned empty data")
                return {}, tickers

            results: dict[str, pd.DataFrame] = {}
            failed: list[str] = []

            # Handle single vs multiple ticker response structure
            if len(tickers) == 1:
                # Single ticker: flat columns (Open, High, Low, Close, Volume)
                ticker = tickers[0]
                try:
                    # Handle potential MultiIndex from single ticker
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [c[0] for c in df.columns]

                    ticker_df = cls._normalize_columns(df.copy())
                    ticker_df.index = pd.to_datetime(ticker_df.index)
                    ticker_df.sort_index(inplace=True)
                    ticker_df.dropna(how="all", inplace=True)

                    if not ticker_df.empty:
                        results[ticker] = ticker_df
                        print(f"  {ticker}: {len(ticker_df)} bars")
                    else:
                        failed.append(ticker)
                        print(f"  {ticker}: FAILED (empty data)")
                except Exception as e:
                    print(f"  {ticker}: FAILED ({e})")
                    failed.append(ticker)

                if progress_callback:
                    progress_callback(1, 1, ticker)
            else:
                # Multiple tickers: MultiIndex columns (ticker, field)
                # Access individual ticker data via df[ticker]
                for i, ticker in enumerate(tickers):
                    try:
                        # Check if ticker exists in the response
                        if ticker in df.columns.get_level_values(0):
                            ticker_df = df[ticker].copy()

                            # Normalize columns (should already be standard OHLCV)
                            ticker_df = cls._normalize_columns(ticker_df)
                            ticker_df.index = pd.to_datetime(ticker_df.index)
                            ticker_df.sort_index(inplace=True)
                            ticker_df.dropna(how="all", inplace=True)

                            if not ticker_df.empty:
                                results[ticker] = ticker_df
                                print(f"  {ticker}: {len(ticker_df)} bars")
                            else:
                                failed.append(ticker)
                                print(f"  {ticker}: FAILED (empty after dropna)")
                        else:
                            failed.append(ticker)
                            print(f"  {ticker}: FAILED (not in response)")
                    except Exception as e:
                        print(f"  {ticker}: FAILED ({e})")
                        failed.append(ticker)

                    if progress_callback:
                        progress_callback(i + 1, total, ticker)

            print(
                f"Yahoo batch complete: {len(results)} succeeded, {len(failed)} failed"
            )

            # Also cache metadata (name, sector, etc.) for successful tickers
            if results:
                try:
                    from app.services.ticker_metadata_service import TickerMetadataService

                    successful_tickers = list(results.keys())
                    TickerMetadataService.get_metadata_batch(successful_tickers)
                    print(f"Cached metadata for {len(successful_tickers)} tickers")
                except Exception as meta_err:
                    # Don't fail the fetch if metadata caching fails
                    print(f"Warning: Could not cache metadata: {meta_err}")

            return results, failed

        except Exception as e:
            print(f"Yahoo Finance batch download failed: {e}")
            return {}, tickers

    @classmethod
    def fetch_batch_current_prices(cls, tickers: list[str]) -> dict[str, float]:
        """
        Fetch current prices for multiple tickers in a single API call.

        Used for live price updates in Portfolio Construction module.
        Returns the most recent close price for each ticker.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> latest close price
        """
        import pandas as pd
        import yfinance as yf

        if not tickers:
            return {}

        # Normalize tickers
        tickers = [t.strip().upper() for t in tickers]

        try:
            # Single batch download - fetch 5 days for redundancy
            df = yf.download(
                tickers=" ".join(tickers) if len(tickers) > 1 else tickers[0],
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="ticker" if len(tickers) > 1 else "column",
            )

            if df is None or df.empty:
                return {}

            prices: dict[str, float] = {}

            if len(tickers) == 1:
                # Single ticker - flat columns
                ticker = tickers[0]
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0] for c in df.columns]
                if "Close" in df.columns:
                    close_series = df["Close"].dropna()
                    if not close_series.empty:
                        prices[ticker] = float(close_series.iloc[-1])
            else:
                # Multiple tickers - MultiIndex columns
                for ticker in tickers:
                    try:
                        if ticker in df.columns.get_level_values(0):
                            ticker_close = df[ticker]["Close"].dropna()
                            if not ticker_close.empty:
                                prices[ticker] = float(ticker_close.iloc[-1])
                    except Exception:
                        pass  # Skip failed tickers silently

            return prices

        except Exception as e:
            print(f"Yahoo Finance batch current prices failed: {e}")
            return {}

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
