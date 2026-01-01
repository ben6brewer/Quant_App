"""Returns Data Service - Cached Daily Returns for Portfolio Analysis.

This service computes and caches daily returns for portfolios, optimized
for analysis modules like Risk Analysis, Monte Carlo, and Return Distributions.
"""

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.services.market_data import fetch_price_history
from app.services.portfolio_data_service import PortfolioDataService


class ReturnsDataService:
    """
    Service for computing and caching portfolio daily returns.

    Features:
    - Lazy computation: returns calculated on first access
    - Parquet caching: fast load times for 100+ securities
    - Auto-invalidation: cache invalidated when portfolio modified
    - Thread-safe: multiple modules can access concurrently
    """

    _CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "returns"
    _cache_lock = threading.Lock()

    # In-memory cache for session performance
    _memory_cache: Dict[str, pd.DataFrame] = {}
    _memory_cache_timestamps: Dict[str, datetime] = {}

    @classmethod
    def _ensure_cache_dir(cls) -> None:
        """Create cache directory if it doesn't exist."""
        cls._CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _get_cache_path(cls, portfolio_name: str) -> Path:
        """Get parquet cache path for a portfolio."""
        # Sanitize name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in portfolio_name)
        return cls._CACHE_DIR / f"{safe_name}_returns.parquet"

    @classmethod
    def _is_cache_valid(cls, portfolio_name: str) -> bool:
        """
        Check if cached returns are still valid.

        Cache is invalid if:
        - Cache file doesn't exist
        - Portfolio was modified after cache creation
        """
        cache_path = cls._get_cache_path(portfolio_name)
        if not cache_path.exists():
            return False

        # Get portfolio modification time
        portfolio_mtime = PortfolioDataService.get_portfolio_modified_time(portfolio_name)
        if portfolio_mtime is None:
            return False

        # Get cache modification time
        try:
            cache_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        except OSError:
            return False

        # Cache valid if created after portfolio was last modified
        return cache_mtime > portfolio_mtime

    @classmethod
    def get_daily_returns(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get daily returns for all tickers in a portfolio.

        Returns a DataFrame with:
        - Index: dates (DatetimeIndex)
        - Columns: ticker symbols
        - Values: daily returns (percentage as decimal, e.g., 0.05 = 5%)

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            DataFrame of daily returns, or empty DataFrame if portfolio not found
        """
        with cls._cache_lock:
            # Check memory cache first
            if portfolio_name in cls._memory_cache:
                if cls._is_cache_valid(portfolio_name):
                    df = cls._memory_cache[portfolio_name]
                    return cls._filter_date_range(df, start_date, end_date)

            # Check disk cache
            if cls._is_cache_valid(portfolio_name):
                cache_path = cls._get_cache_path(portfolio_name)
                try:
                    df = pd.read_parquet(cache_path)
                    cls._memory_cache[portfolio_name] = df
                    return cls._filter_date_range(df, start_date, end_date)
                except Exception:
                    pass  # Cache corrupted, will recompute

            # Compute fresh returns
            df = cls._compute_returns(portfolio_name)
            if df.empty:
                return df

            # Cache to disk
            cls._ensure_cache_dir()
            try:
                df.to_parquet(cls._get_cache_path(portfolio_name))
            except Exception as e:
                print(f"Warning: Could not cache returns for {portfolio_name}: {e}")

            # Cache in memory
            cls._memory_cache[portfolio_name] = df

            return cls._filter_date_range(df, start_date, end_date)

    @classmethod
    def _compute_returns(cls, portfolio_name: str) -> pd.DataFrame:
        """
        Compute daily returns for all tickers in a portfolio.

        Returns:
            DataFrame with daily returns for each ticker
        """
        tickers = PortfolioDataService.get_tickers(portfolio_name)
        if not tickers:
            return pd.DataFrame()

        returns_dict: Dict[str, pd.Series] = {}

        for ticker in tickers:
            try:
                # Fetch price history (uses existing cache)
                df = fetch_price_history(ticker, period="max", interval="1d")
                if df.empty:
                    continue

                # Calculate daily returns from Close prices
                close = df["Close"]
                daily_returns = close.pct_change().dropna()

                returns_dict[ticker] = daily_returns

            except Exception as e:
                print(f"Warning: Could not fetch returns for {ticker}: {e}")
                continue

        if not returns_dict:
            return pd.DataFrame()

        # Combine all returns into a single DataFrame
        # Use outer join to preserve all dates (NaN for missing)
        df = pd.DataFrame(returns_dict)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        return df

    @classmethod
    def _filter_date_range(
        cls,
        df: pd.DataFrame,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> pd.DataFrame:
        """Filter DataFrame to date range."""
        if df.empty:
            return df

        result = df.copy()

        if start_date:
            result = result[result.index >= pd.to_datetime(start_date)]

        if end_date:
            result = result[result.index <= pd.to_datetime(end_date)]

        return result

    @classmethod
    def get_portfolio_returns(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> pd.Series:
        """
        Get weighted portfolio daily returns.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter
            end_date: Optional end date filter
            weights: Optional dict of ticker -> weight.
                    If not provided, uses equal weights.

        Returns:
            Series of daily portfolio returns
        """
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if returns.empty:
            return pd.Series(dtype=float)

        tickers = returns.columns.tolist()

        if weights is None:
            # Equal weight
            w = {t: 1.0 / len(tickers) for t in tickers}
        else:
            # Normalize weights to sum to 1
            total = sum(weights.get(t, 0) for t in tickers)
            if total == 0:
                return pd.Series(dtype=float)
            w = {t: weights.get(t, 0) / total for t in tickers}

        # Calculate weighted returns
        # Fill NaN with 0 for days where ticker didn't trade
        portfolio_returns = pd.Series(0.0, index=returns.index)
        for ticker in tickers:
            if ticker in w and w[ticker] > 0:
                ticker_returns = returns[ticker].fillna(0)
                portfolio_returns += ticker_returns * w[ticker]

        return portfolio_returns

    @classmethod
    def get_cumulative_returns(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get cumulative returns for all tickers.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with cumulative returns (1.0 = 100% gain)
        """
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if returns.empty:
            return pd.DataFrame()

        # Calculate cumulative returns: (1 + r1) * (1 + r2) * ... - 1
        cumulative = (1 + returns).cumprod() - 1
        return cumulative

    @classmethod
    def invalidate_cache(cls, portfolio_name: str) -> None:
        """
        Invalidate cache for a portfolio.

        Call this when a portfolio is modified.

        Args:
            portfolio_name: Name of the portfolio
        """
        with cls._cache_lock:
            # Clear memory cache
            cls._memory_cache.pop(portfolio_name, None)

            # Delete disk cache
            cache_path = cls._get_cache_path(portfolio_name)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                except OSError:
                    pass

    @classmethod
    def invalidate_all_caches(cls) -> None:
        """Clear all cached returns."""
        with cls._cache_lock:
            cls._memory_cache.clear()

            if cls._CACHE_DIR.exists():
                for cache_file in cls._CACHE_DIR.glob("*_returns.parquet"):
                    try:
                        cache_file.unlink()
                    except OSError:
                        pass

    @classmethod
    def get_correlation_matrix(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get correlation matrix of daily returns.

        Useful for risk analysis and diversification assessment.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Correlation matrix DataFrame
        """
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if returns.empty:
            return pd.DataFrame()

        return returns.corr()

    @classmethod
    def get_volatility(
        cls,
        portfolio_name: str,
        window: int = 252,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get annualized rolling volatility for each ticker.

        Args:
            portfolio_name: Name of the portfolio
            window: Rolling window in days (default 252 = 1 year)
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with rolling annualized volatility
        """
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if returns.empty:
            return pd.DataFrame()

        # Annualized volatility = daily_std * sqrt(252)
        volatility = returns.rolling(window=window).std() * np.sqrt(252)
        return volatility.dropna()

    # =========================================================================
    # Time-Varying Position and Weight Methods (for accurate portfolio returns)
    # =========================================================================

    @classmethod
    def get_position_history(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = True,
    ) -> pd.DataFrame:
        """
        Reconstruct position quantities for each date from transaction history.

        This method processes the transaction log to determine how many shares/units
        were held of each ticker on each trading day.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH positions

        Returns:
            DataFrame with:
            - Index: dates (DatetimeIndex)
            - Columns: ticker symbols
            - Values: position quantities (shares/units held at end of each day)
        """
        transactions = PortfolioDataService.get_transactions(portfolio_name)
        if not transactions:
            return pd.DataFrame()

        # Filter transactions by ticker inclusion
        if not include_cash:
            transactions = [t for t in transactions if t.ticker.upper() != "FREE CASH"]

        if not transactions:
            return pd.DataFrame()

        # Sort transactions by date and sequence
        transactions = sorted(transactions, key=lambda t: (t.date, t.sequence))

        # Get all unique tickers
        tickers = list(set(t.ticker for t in transactions))

        # Build position changes by date
        # Dict of date -> Dict of ticker -> quantity change
        position_changes: Dict[str, Dict[str, float]] = {}

        for tx in transactions:
            date = tx.date
            ticker = tx.ticker

            if date not in position_changes:
                position_changes[date] = {}

            if ticker not in position_changes[date]:
                position_changes[date][ticker] = 0.0

            # Buy increases position, Sell decreases
            if tx.transaction_type == "Buy":
                position_changes[date][ticker] += tx.quantity
            else:  # Sell
                position_changes[date][ticker] -= tx.quantity

        # Get date range
        transaction_dates = sorted(position_changes.keys())
        if not transaction_dates:
            return pd.DataFrame()

        first_tx_date = pd.to_datetime(transaction_dates[0])

        # Determine end date for position history
        if end_date:
            last_date = pd.to_datetime(end_date)
        else:
            last_date = pd.Timestamp.now().normalize()

        # Create date range (trading days approximation - all calendar days for simplicity)
        all_dates = pd.date_range(start=first_tx_date, end=last_date, freq="D")

        # Build cumulative positions
        positions = pd.DataFrame(0.0, index=all_dates, columns=tickers)

        current_position = {ticker: 0.0 for ticker in tickers}

        for date in all_dates:
            date_str = date.strftime("%Y-%m-%d")

            # Apply any position changes for this date
            if date_str in position_changes:
                for ticker, change in position_changes[date_str].items():
                    current_position[ticker] += change

            # Record position for this date
            for ticker in tickers:
                positions.loc[date, ticker] = current_position[ticker]

        # Apply start_date filter
        if start_date:
            positions = positions[positions.index >= pd.to_datetime(start_date)]

        return positions

    @classmethod
    def get_daily_weights(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = True,
    ) -> pd.DataFrame:
        """
        Calculate portfolio weights for each date based on market values.

        Uses position history and daily prices to compute the weight of each
        position in the portfolio on each day.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH with weight contribution

        Returns:
            DataFrame with:
            - Index: dates (DatetimeIndex)
            - Columns: ticker symbols
            - Values: weights (0.0 to 1.0, summing to ~1.0 per row)
        """
        # Get position quantities over time
        positions = cls.get_position_history(
            portfolio_name, start_date, end_date, include_cash
        )
        if positions.empty:
            return pd.DataFrame()

        tickers = positions.columns.tolist()

        # Fetch daily close prices for all tickers (except FREE CASH)
        price_data: Dict[str, pd.Series] = {}

        for ticker in tickers:
            if ticker.upper() == "FREE CASH":
                # FREE CASH: quantity IS the dollar value (price = $1)
                continue

            try:
                df = fetch_price_history(ticker, period="max", interval="1d")
                if not df.empty:
                    close = df["Close"]
                    close.index = pd.to_datetime(close.index)
                    price_data[ticker] = close
            except Exception as e:
                print(f"Warning: Could not fetch prices for {ticker}: {e}")

        # Calculate market values for each position on each day
        market_values = pd.DataFrame(index=positions.index, columns=tickers, dtype=float)

        for ticker in tickers:
            if ticker.upper() == "FREE CASH":
                # FREE CASH: market value = quantity (price is always $1)
                market_values[ticker] = positions[ticker]
            elif ticker in price_data:
                # Regular ticker: market value = quantity * price
                prices = price_data[ticker].reindex(positions.index, method="ffill")
                market_values[ticker] = positions[ticker] * prices
            else:
                # No price data - use 0 market value
                market_values[ticker] = 0.0

        # Fill any remaining NaN with 0
        market_values = market_values.fillna(0)

        # Calculate total portfolio value per day
        total_values = market_values.sum(axis=1)

        # Calculate weights (avoid division by zero)
        weights = market_values.copy()
        for col in weights.columns:
            weights[col] = np.where(
                total_values > 0,
                market_values[col] / total_values,
                0.0
            )

        return weights

    @classmethod
    def get_time_varying_portfolio_returns(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = True,
        interval: str = "daily",
    ) -> pd.Series:
        """
        Calculate portfolio returns using time-varying weights from transactions.

        This is the main method for calculating accurate portfolio returns that
        account for changing position sizes due to buys and sells.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH with 0% return
            interval: Return interval - "daily", "weekly", "monthly", or "yearly"

        Returns:
            Series of portfolio returns at the specified interval
        """
        # Get time-varying weights
        weights = cls.get_daily_weights(
            portfolio_name, start_date, end_date, include_cash
        )
        if weights.empty:
            return pd.Series(dtype=float)

        # Get daily returns for all tickers (excluding FREE CASH - it has 0% return)
        tickers = [t for t in weights.columns if t.upper() != "FREE CASH"]

        if not tickers:
            # Only cash in portfolio - return zeros
            return pd.Series(0.0, index=weights.index, name="portfolio_return")

        # Get daily returns
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)

        # Ensure same index
        common_dates = weights.index.intersection(returns.index)
        if common_dates.empty:
            return pd.Series(dtype=float)

        weights = weights.loc[common_dates]
        returns = returns.loc[common_dates]

        # Calculate weighted portfolio returns for each day
        # portfolio_return = sum(weight_i * return_i)
        # FREE CASH contributes weight * 0 = 0
        portfolio_returns = pd.Series(0.0, index=common_dates, name="portfolio_return")

        for ticker in weights.columns:
            if ticker.upper() == "FREE CASH":
                # Cash has 0% return, contributes nothing
                continue

            if ticker in returns.columns:
                ticker_returns = returns[ticker].fillna(0)
                ticker_weights = weights[ticker]
                portfolio_returns += ticker_weights * ticker_returns

        # Resample if needed
        if interval.lower() != "daily":
            portfolio_returns = cls._resample_returns(portfolio_returns, interval)

        return portfolio_returns

    @classmethod
    def _resample_returns(cls, returns: pd.Series, interval: str) -> pd.Series:
        """
        Resample daily returns to a different interval using geometric linking.

        Args:
            returns: Daily returns series
            interval: Target interval - "weekly", "monthly", or "yearly"

        Returns:
            Resampled returns series
        """
        if returns.empty:
            return returns

        # Map interval to pandas resample rule (case-insensitive)
        resample_map = {
            "weekly": "W",
            "monthly": "ME",
            "yearly": "YE",
        }

        rule = resample_map.get(interval.lower())
        if not rule:
            return returns

        # Geometric linking: (1 + r1) * (1 + r2) * ... - 1
        def compound_returns(r):
            return (1 + r).prod() - 1

        return returns.resample(rule).apply(compound_returns)

    @classmethod
    def calculate_cash_drag(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Calculate cash drag statistics for a portfolio.

        Cash drag represents the opportunity cost of holding cash instead of
        investing it in the market.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Dict with:
            - avg_cash_weight: Average cash allocation (0.0 to 1.0)
            - cash_drag_bps: Estimated return reduction in basis points
            - period_days: Number of days analyzed
        """
        # Get weights including cash
        weights = cls.get_daily_weights(
            portfolio_name, start_date, end_date, include_cash=True
        )

        if weights.empty:
            return {
                "avg_cash_weight": 0.0,
                "cash_drag_bps": 0.0,
                "period_days": 0,
            }

        # Find the FREE CASH column (case-insensitive)
        cash_col = None
        for col in weights.columns:
            if col.upper() == "FREE CASH":
                cash_col = col
                break

        if cash_col is None:
            return {
                "avg_cash_weight": 0.0,
                "cash_drag_bps": 0.0,
                "period_days": len(weights),
            }

        # Calculate average cash weight
        cash_weights = weights[cash_col]
        avg_cash_weight = cash_weights.mean()

        # Calculate average daily market return (non-cash positions)
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        if not returns.empty:
            avg_daily_return = returns.mean().mean()  # Mean across all tickers
            # Annualize: (1 + daily)^252 - 1, approximated as daily * 252
            annualized_market_return = avg_daily_return * 252
            # Cash drag in basis points (cash weight * missed return * 10000)
            cash_drag_bps = avg_cash_weight * annualized_market_return * 10000
        else:
            cash_drag_bps = 0.0

        return {
            "avg_cash_weight": avg_cash_weight,
            "cash_drag_bps": cash_drag_bps,
            "cash_drag_annualized": cash_drag_bps / 10000,  # Decimal form for display
            "period_days": len(weights),
        }

    # =========================================================================
    # Distribution Metric Calculations
    # =========================================================================

    @classmethod
    def get_portfolio_volatility(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = False,
        interval: str = "daily",
    ) -> pd.Series:
        """
        Calculate annualized volatility series for the portfolio.

        Returns a series of rolling 21-day volatility values (annualized).

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH (typically False for vol)
            interval: Return interval for underlying returns

        Returns:
            Series of annualized volatility values (as decimals, e.g., 0.20 = 20%)
        """
        # Get daily portfolio returns
        returns = cls.get_time_varying_portfolio_returns(
            portfolio_name, start_date, end_date, include_cash, interval="daily"
        )

        if returns.empty or len(returns) < 21:
            return pd.Series(dtype=float)

        # Calculate rolling 21-day volatility, annualized
        rolling_vol = returns.rolling(window=21).std() * np.sqrt(252)

        return rolling_vol.dropna()

    @classmethod
    def get_rolling_volatility(
        cls,
        portfolio_name: str,
        window_days: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = False,
    ) -> pd.Series:
        """
        Calculate rolling volatility with specified window.

        Args:
            portfolio_name: Name of the portfolio
            window_days: Rolling window in trading days (21=1m, 63=3m, 126=6m, 252=1y)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH

        Returns:
            Series of annualized volatility values (as decimals)
        """
        # Get daily portfolio returns
        returns = cls.get_time_varying_portfolio_returns(
            portfolio_name, start_date, end_date, include_cash, interval="daily"
        )

        if returns.empty or len(returns) < window_days:
            return pd.Series(dtype=float)

        # Calculate rolling volatility, annualized
        rolling_vol = returns.rolling(window=window_days).std() * np.sqrt(252)

        return rolling_vol.dropna()

    @classmethod
    def get_drawdowns(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = False,
    ) -> pd.Series:
        """
        Calculate drawdown series (distance from all-time high).

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH

        Returns:
            Series of drawdown values (as negative decimals, e.g., -0.15 = -15%)
        """
        # Get daily portfolio returns
        returns = cls.get_time_varying_portfolio_returns(
            portfolio_name, start_date, end_date, include_cash, interval="daily"
        )

        if returns.empty:
            return pd.Series(dtype=float)

        # Calculate cumulative returns (wealth index)
        cumulative = (1 + returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.cummax()

        # Drawdown = current / peak - 1
        drawdowns = cumulative / running_max - 1

        return drawdowns

    @classmethod
    def get_rolling_returns(
        cls,
        portfolio_name: str,
        window_days: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = False,
    ) -> pd.Series:
        """
        Calculate rolling returns with specified window.

        Args:
            portfolio_name: Name of the portfolio
            window_days: Rolling window in trading days (21=1m, 63=3m, 252=1y, 756=3y, 1260=5y)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH

        Returns:
            Series of rolling return values (as decimals, e.g., 0.10 = 10%)
        """
        # Get daily portfolio returns
        returns = cls.get_time_varying_portfolio_returns(
            portfolio_name, start_date, end_date, include_cash, interval="daily"
        )

        if returns.empty or len(returns) < window_days:
            return pd.Series(dtype=float)

        # Calculate rolling compounded returns
        # (1 + r1) * (1 + r2) * ... * (1 + rn) - 1
        def compound_return(window):
            return (1 + window).prod() - 1

        rolling_returns = returns.rolling(window=window_days).apply(
            compound_return, raw=False
        )

        return rolling_returns.dropna()

    @classmethod
    def get_time_under_water(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = False,
    ) -> pd.Series:
        """
        Calculate time under water (days since last all-time high).

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: If True, includes FREE CASH

        Returns:
            Series of days under water (integer values)
        """
        # Get daily portfolio returns
        returns = cls.get_time_varying_portfolio_returns(
            portfolio_name, start_date, end_date, include_cash, interval="daily"
        )

        if returns.empty:
            return pd.Series(dtype=float)

        # Calculate cumulative returns (wealth index)
        cumulative = (1 + returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.cummax()

        # Track days under water
        days_under_water = pd.Series(0, index=cumulative.index, dtype=int)

        current_underwater_days = 0
        for i, (cum, peak) in enumerate(zip(cumulative, running_max)):
            if cum < peak:
                current_underwater_days += 1
            else:
                current_underwater_days = 0
            days_under_water.iloc[i] = current_underwater_days

        return days_under_water

    # =========================================================================
    # Single Ticker Returns (for benchmark comparisons)
    # =========================================================================

    @classmethod
    def get_ticker_returns(
        cls,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = "daily",
    ) -> pd.Series:
        """
        Get returns for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            interval: Return interval - "daily", "weekly", "monthly", "yearly"

        Returns:
            Series of returns (as decimals, e.g., 0.05 = 5%)
        """
        df = fetch_price_history(ticker, period="max", interval="1d")
        if df.empty:
            return pd.Series(dtype=float)

        # Calculate daily returns
        returns = df["Close"].pct_change().dropna()
        returns.name = ticker

        # Filter date range
        if start_date or end_date:
            returns_df = returns.to_frame()
            returns_df = cls._filter_date_range(returns_df, start_date, end_date)
            returns = returns_df[ticker] if ticker in returns_df.columns else returns_df.iloc[:, 0]

        # Resample if needed
        if interval.lower() != "daily":
            returns = cls._resample_returns(returns, interval)

        return returns

    @classmethod
    def get_ticker_volatility(
        cls,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.Series:
        """
        Calculate annualized volatility series for a single ticker.

        Returns a series of rolling 21-day volatility values (annualized).

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Series of annualized volatility values (as decimals, e.g., 0.20 = 20%)
        """
        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty or len(returns) < 21:
            return pd.Series(dtype=float)

        # Calculate rolling 21-day volatility, annualized
        rolling_vol = returns.rolling(window=21).std() * np.sqrt(252)

        return rolling_vol.dropna()

    @classmethod
    def get_ticker_rolling_volatility(
        cls,
        ticker: str,
        window_days: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.Series:
        """
        Calculate rolling volatility with specified window for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            window_days: Rolling window in trading days (21=1m, 63=3m, 126=6m, 252=1y)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Series of annualized volatility values (as decimals)
        """
        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty or len(returns) < window_days:
            return pd.Series(dtype=float)

        # Calculate rolling volatility, annualized
        rolling_vol = returns.rolling(window=window_days).std() * np.sqrt(252)

        return rolling_vol.dropna()

    @classmethod
    def get_ticker_drawdowns(
        cls,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.Series:
        """
        Calculate drawdown series for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Series of drawdown values (as negative decimals, e.g., -0.15 = -15%)
        """
        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty:
            return pd.Series(dtype=float)

        # Calculate cumulative returns (wealth index)
        cumulative = (1 + returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.cummax()

        # Drawdown = current / peak - 1
        drawdowns = cumulative / running_max - 1

        return drawdowns

    @classmethod
    def get_ticker_rolling_returns(
        cls,
        ticker: str,
        window_days: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.Series:
        """
        Calculate rolling returns with specified window for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            window_days: Rolling window in trading days (21=1m, 63=3m, 252=1y, etc.)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Series of rolling return values (as decimals, e.g., 0.10 = 10%)
        """
        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty or len(returns) < window_days:
            return pd.Series(dtype=float)

        # Calculate rolling compounded returns
        def compound_return(window):
            return (1 + window).prod() - 1

        rolling_returns = returns.rolling(window=window_days).apply(
            compound_return, raw=False
        )

        return rolling_returns.dropna()

    @classmethod
    def get_ticker_time_under_water(
        cls,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.Series:
        """
        Calculate time under water for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Series of days under water (integer values)
        """
        returns = cls.get_ticker_returns(ticker, start_date, end_date, interval="daily")

        if returns.empty:
            return pd.Series(dtype=float)

        # Calculate cumulative returns (wealth index)
        cumulative = (1 + returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.cummax()

        # Track days under water
        days_under_water = pd.Series(0, index=cumulative.index, dtype=int)

        current_underwater_days = 0
        for i, (cum, peak) in enumerate(zip(cumulative, running_max)):
            if cum < peak:
                current_underwater_days += 1
            else:
                current_underwater_days = 0
            days_under_water.iloc[i] = current_underwater_days

        return days_under_water
