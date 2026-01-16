"""Returns Data Service - Cached Daily Returns for Portfolio Analysis.

This service computes and caches daily returns for portfolios, optimized
for analysis modules like Risk Analysis, Monte Carlo, and Return Distributions.
"""

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
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
    _memory_cache: Dict[str, Any] = {}
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
    ) -> "pd.DataFrame":
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
        import pandas as pd

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
    def _compute_returns(cls, portfolio_name: str) -> "pd.DataFrame":
        """
        Compute daily returns for all tickers in a portfolio.

        Uses batch fetching for optimal performance with large portfolios.

        Returns:
            DataFrame with daily returns for each ticker
        """
        import pandas as pd
        from app.services.market_data import fetch_price_history_batch

        tickers = PortfolioDataService.get_tickers(portfolio_name)
        if not tickers:
            return pd.DataFrame()

        # Batch fetch all ticker data at once (much faster than sequential)
        price_data = fetch_price_history_batch(tickers)

        returns_dict: Dict[str, Any] = {}

        for ticker in tickers:
            try:
                if ticker not in price_data:
                    continue

                df = price_data[ticker]
                if df is None or df.empty:
                    continue

                # Calculate daily returns from Close prices
                close = df["Close"]
                daily_returns = close.pct_change().dropna()

                returns_dict[ticker] = daily_returns

            except Exception as e:
                print(f"Warning: Could not compute returns for {ticker}: {e}")
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
        df: "pd.DataFrame",
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> "pd.DataFrame":
        """Filter DataFrame to date range."""
        import pandas as pd

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
    ) -> "pd.Series":
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
        import pandas as pd

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
    ) -> "pd.DataFrame":
        """
        Get cumulative returns for all tickers.

        Args:
            portfolio_name: Name of the portfolio
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with cumulative returns (1.0 = 100% gain)
        """
        import pandas as pd

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
    def clear_cache(cls) -> None:
        """Clear all cached portfolio returns."""
        cls.invalidate_all_caches()
        print("[ReturnsDataService] Cache cleared")

    @classmethod
    def get_correlation_matrix(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.DataFrame":
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
        import pandas as pd

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
    ) -> "pd.DataFrame":
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
        import numpy as np
        import pandas as pd

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
    ) -> "pd.DataFrame":
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
        import pandas as pd

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
    ) -> "pd.DataFrame":
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
        import numpy as np
        import pandas as pd

        # Get position quantities over time
        positions = cls.get_position_history(
            portfolio_name, start_date, end_date, include_cash
        )
        if positions.empty:
            return pd.DataFrame()

        tickers = positions.columns.tolist()

        # Batch fetch daily close prices for all tickers (except FREE CASH)
        from app.services.market_data import fetch_price_history_batch

        tickers_to_fetch = [t for t in tickers if t.upper() != "FREE CASH"]
        batch_data = fetch_price_history_batch(tickers_to_fetch)

        # Extract close prices from batch results
        price_data: Dict[str, Any] = {}
        for ticker in tickers_to_fetch:
            if ticker in batch_data:
                df = batch_data[ticker]
                if df is not None and not df.empty:
                    close = df["Close"]
                    close.index = pd.to_datetime(close.index)
                    price_data[ticker] = close

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
    ) -> "pd.Series":
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
        import pandas as pd

        # Get time-varying weights
        weights = cls.get_daily_weights(
            portfolio_name, start_date, end_date, include_cash
        )
        if weights.empty:
            print(f"[DEBUG] get_time_varying_portfolio_returns: weights empty for '{portfolio_name}'")
            return pd.Series(dtype=float)

        print(f"[DEBUG] Weights shape: {weights.shape}, date range: {weights.index.min()} to {weights.index.max()}")

        # Get daily returns for all tickers (excluding FREE CASH - it has 0% return)
        tickers = [t for t in weights.columns if t.upper() != "FREE CASH"]

        if not tickers:
            # Only cash in portfolio - return zeros
            print(f"[DEBUG] Only cash in portfolio, returning zeros")
            return pd.Series(0.0, index=weights.index, name="portfolio_return")

        # Get daily returns
        returns = cls.get_daily_returns(portfolio_name, start_date, end_date)
        print(f"[DEBUG] Returns shape: {returns.shape if not returns.empty else 'empty'}")

        # Normalize both indices to date-only (remove time component and timezone)
        # This fixes mismatches like 2026-01-15 00:00:00 vs 2026-01-15 05:00:00
        weights_idx = pd.to_datetime(weights.index).normalize()
        returns_idx = pd.to_datetime(returns.index).normalize()
        # Remove timezone if present
        if weights_idx.tz is not None:
            weights_idx = weights_idx.tz_localize(None)
        if returns_idx.tz is not None:
            returns_idx = returns_idx.tz_localize(None)
        weights.index = weights_idx
        returns.index = returns_idx

        # Ensure same index
        common_dates = weights.index.intersection(returns.index)
        if common_dates.empty:
            print(f"[DEBUG] No common dates between weights and returns!")
            if not returns.empty:
                print(f"[DEBUG] Returns date range: {returns.index.min()} to {returns.index.max()}")
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
    def _resample_returns(cls, returns: "pd.Series", interval: str) -> "pd.Series":
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
    def get_distribution_statistics(cls, returns: "pd.Series") -> Dict[str, float]:
        """
        Calculate distribution statistics for a returns series.

        This method computes standard statistical measures used in distribution
        analysis, suitable for histograms, risk reports, and performance summaries.

        Args:
            returns: Series of returns (as decimals, e.g., 0.05 = 5%)

        Returns:
            Dict with keys:
            - mean: Average return
            - std: Standard deviation (sample, ddof=1)
            - skew: Skewness (third moment, asymmetry)
            - kurtosis: Excess kurtosis (fourth moment, tail risk)
            - min: Minimum return
            - max: Maximum return
            - count: Number of observations
        """
        if returns is None or returns.empty:
            return {
                "mean": float("nan"),
                "std": float("nan"),
                "skew": float("nan"),
                "kurtosis": float("nan"),
                "min": float("nan"),
                "max": float("nan"),
                "count": 0,
            }

        clean_returns = returns.dropna()
        if clean_returns.empty:
            return {
                "mean": float("nan"),
                "std": float("nan"),
                "skew": float("nan"),
                "kurtosis": float("nan"),
                "min": float("nan"),
                "max": float("nan"),
                "count": 0,
            }

        return {
            "mean": clean_returns.mean(),
            "std": clean_returns.std(ddof=1),
            "skew": clean_returns.skew(),
            "kurtosis": clean_returns.kurtosis(),
            "min": clean_returns.min(),
            "max": clean_returns.max(),
            "count": len(clean_returns),
        }

    @classmethod
    def get_portfolio_volatility(
        cls,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = False,
        interval: str = "daily",
    ) -> "pd.Series":
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
        import numpy as np
        import pandas as pd

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
    ) -> "pd.Series":
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
        import numpy as np
        import pandas as pd

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
    ) -> "pd.Series":
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
        import pandas as pd

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
    ) -> "pd.Series":
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
        import pandas as pd

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
    ) -> "pd.Series":
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
        import pandas as pd

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
    ) -> "pd.Series":
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
        import pandas as pd

        # skip_live_bar=True - returns calculations use daily closes, not intraday
        df = fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)
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
    ) -> "pd.Series":
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
        import numpy as np
        import pandas as pd

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
    ) -> "pd.Series":
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
        import numpy as np
        import pandas as pd

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
    ) -> "pd.Series":
        """
        Calculate drawdown series for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Series of drawdown values (as negative decimals, e.g., -0.15 = -15%)
        """
        import pandas as pd

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
    ) -> "pd.Series":
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
        import pandas as pd

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
    ) -> "pd.Series":
        """
        Calculate time under water for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "SPY", "BTC-USD")
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            Series of days under water (integer values)
        """
        import pandas as pd

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

    # =========================================================================
    # Risk-Adjusted Performance Metrics
    # =========================================================================

    @classmethod
    def get_sharpe_ratio(
        cls,
        returns: "pd.Series",
        risk_free_rate: float = 0.0,
    ) -> float:
        """
        Calculate the Sharpe ratio for a returns series.

        Sharpe ratio measures risk-adjusted return: (mean return - risk-free rate) / volatility.
        Higher values indicate better risk-adjusted performance.

        Args:
            returns: Series of returns (as decimals, e.g., 0.05 = 5%)
            risk_free_rate: Annualized risk-free rate (as decimal, e.g., 0.05 = 5%)

        Returns:
            Annualized Sharpe ratio, or NaN if insufficient data
        """
        import numpy as np

        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 2:
            return float("nan")

        # Convert annualized risk-free rate to daily
        daily_rf = risk_free_rate / 252

        # Calculate excess returns
        excess_returns = clean_returns - daily_rf

        # Calculate Sharpe ratio
        std = excess_returns.std(ddof=1)
        if std == 0 or np.isnan(std):
            return float("nan")

        # Annualize: multiply by sqrt(252)
        return (excess_returns.mean() / std) * np.sqrt(252)

    @classmethod
    def get_sortino_ratio(
        cls,
        returns: "pd.Series",
        risk_free_rate: float = 0.0,
        target_return: float = 0.0,
    ) -> float:
        """
        Calculate the Sortino ratio for a returns series.

        Sortino ratio is similar to Sharpe but only penalizes downside volatility,
        making it more appropriate for asymmetric return distributions.

        Args:
            returns: Series of returns (as decimals, e.g., 0.05 = 5%)
            risk_free_rate: Annualized risk-free rate (as decimal, e.g., 0.05 = 5%)
            target_return: Annualized target/minimum acceptable return (default: 0)

        Returns:
            Annualized Sortino ratio, or NaN if insufficient data
        """
        import numpy as np

        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 2:
            return float("nan")

        # Convert annualized rates to daily
        daily_rf = risk_free_rate / 252
        daily_target = target_return / 252

        # Calculate excess returns over target
        excess_returns = clean_returns - daily_rf

        # Calculate downside deviation (only negative returns below target)
        downside_returns = clean_returns[clean_returns < daily_target] - daily_target
        if len(downside_returns) == 0:
            # No downside - infinite Sortino (return a large number or NaN)
            return float("nan")

        downside_std = np.sqrt((downside_returns ** 2).mean())
        if downside_std == 0 or np.isnan(downside_std):
            return float("nan")

        # Annualize: multiply by sqrt(252)
        return (excess_returns.mean() / downside_std) * np.sqrt(252)

    # =========================================================================
    # Benchmark-Relative Metrics
    # =========================================================================

    @classmethod
    def get_beta(
        cls,
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate portfolio beta relative to a benchmark.

        Beta measures the portfolio's sensitivity to benchmark movements.
        Beta > 1 means more volatile than benchmark, Beta < 1 means less volatile.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

        Returns:
            Beta coefficient, or NaN if insufficient data
        """
        import numpy as np
        import pandas as pd

        if portfolio_returns is None or benchmark_returns is None:
            return float("nan")

        # Align the two series to common dates
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns], axis=1, keys=["portfolio", "benchmark"]
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        # Beta = Cov(Rp, Rb) / Var(Rb)
        covariance = aligned["portfolio"].cov(aligned["benchmark"])
        benchmark_variance = aligned["benchmark"].var()

        if benchmark_variance == 0 or np.isnan(benchmark_variance):
            return float("nan")

        return covariance / benchmark_variance

    @classmethod
    def get_alpha(
        cls,
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        risk_free_rate: float = 0.0,
    ) -> float:
        """
        Calculate Jensen's alpha (annualized).

        Alpha measures excess return not explained by beta exposure to benchmark.
        Positive alpha indicates outperformance, negative indicates underperformance.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)
            risk_free_rate: Annualized risk-free rate (as decimal, e.g., 0.05 = 5%)

        Returns:
            Annualized alpha, or NaN if insufficient data
        """
        import numpy as np
        import pandas as pd

        beta = cls.get_beta(portfolio_returns, benchmark_returns)
        if np.isnan(beta):
            return float("nan")

        # Align returns
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns], axis=1, keys=["portfolio", "benchmark"]
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        # Annualize mean returns
        portfolio_annual = aligned["portfolio"].mean() * 252
        benchmark_annual = aligned["benchmark"].mean() * 252

        # Jensen's Alpha = Rp - [Rf + beta * (Rb - Rf)]
        alpha = portfolio_annual - (risk_free_rate + beta * (benchmark_annual - risk_free_rate))

        return alpha

    @classmethod
    def get_tracking_error(
        cls,
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate annualized tracking error.

        Tracking error measures the volatility of the difference between
        portfolio and benchmark returns. Lower values indicate closer tracking.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

        Returns:
            Annualized tracking error, or NaN if insufficient data
        """
        import numpy as np
        import pandas as pd

        if portfolio_returns is None or benchmark_returns is None:
            return float("nan")

        # Align the two series
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns], axis=1, keys=["portfolio", "benchmark"]
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        # Tracking error = std(portfolio - benchmark) * sqrt(252)
        excess_returns = aligned["portfolio"] - aligned["benchmark"]
        tracking_error = excess_returns.std(ddof=1) * np.sqrt(252)

        return tracking_error

    @classmethod
    def get_information_ratio(
        cls,
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate the information ratio.

        Information ratio measures active return per unit of active risk.
        Higher values indicate better risk-adjusted active performance.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

        Returns:
            Information ratio, or NaN if insufficient data
        """
        import numpy as np
        import pandas as pd

        tracking_error = cls.get_tracking_error(portfolio_returns, benchmark_returns)
        if np.isnan(tracking_error) or tracking_error == 0:
            return float("nan")

        # Align returns
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns], axis=1, keys=["portfolio", "benchmark"]
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        # Annualized excess return
        excess_returns = aligned["portfolio"] - aligned["benchmark"]
        annualized_excess = excess_returns.mean() * 252

        # Information ratio = annualized excess return / tracking error
        return annualized_excess / tracking_error

    @classmethod
    def get_correlation(
        cls,
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate correlation between portfolio and benchmark returns.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

        Returns:
            Correlation coefficient (-1 to 1), or NaN if insufficient data
        """
        import pandas as pd

        if portfolio_returns is None or benchmark_returns is None:
            return float("nan")

        # Align the two series
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns], axis=1, keys=["portfolio", "benchmark"]
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        return aligned["portfolio"].corr(aligned["benchmark"])

    @classmethod
    def get_r_squared(
        cls,
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate R-squared (coefficient of determination).

        R-squared measures what percentage of portfolio variance is explained
        by the benchmark. Higher values indicate closer relationship.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

        Returns:
            R-squared (0 to 1), or NaN if insufficient data
        """
        import numpy as np

        correlation = cls.get_correlation(portfolio_returns, benchmark_returns)
        if np.isnan(correlation):
            return float("nan")

        return correlation ** 2

    @classmethod
    def get_benchmark_returns(
        cls,
        benchmark: str,
        is_portfolio: bool,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = False,
        interval: str = "daily",
    ) -> "pd.Series":
        """
        Get returns for a benchmark (ticker or portfolio).

        This is a unified helper method that retrieves returns for either
        a ticker symbol or another portfolio, making benchmark comparisons
        seamless across the application.

        Args:
            benchmark: Ticker symbol (e.g., "SPY") or portfolio name
            is_portfolio: True if benchmark is a portfolio name, False for ticker
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: Include cash in portfolio benchmark (ignored for tickers)
            interval: Return interval - "daily", "weekly", "monthly", "yearly"

        Returns:
            Series of benchmark returns (as decimals)
        """
        if is_portfolio:
            return cls.get_time_varying_portfolio_returns(
                benchmark, start_date, end_date, include_cash, interval
            )
        else:
            return cls.get_ticker_returns(benchmark, start_date, end_date, interval)

    @classmethod
    def append_live_return(
        cls,
        returns: "pd.Series",
        ticker: str,
    ) -> "pd.Series":
        """
        Append today's live return to a returns series if eligible.

        Only appends if:
        - Today is a trading day (stocks) or any day (crypto)
        - Current time is within extended market hours (stocks) or any time (crypto)
        - Returns series doesn't already include today

        Args:
            returns: Existing returns series with DatetimeIndex
            ticker: Ticker symbol to fetch live price for

        Returns:
            Returns series with today's live return appended (if applicable),
            or original series if not eligible for update
        """
        import pandas as pd
        from app.utils.market_hours import is_crypto_ticker, is_market_open_extended

        if returns is None or returns.empty:
            return returns

        # Check if ticker is eligible for live update
        is_crypto = is_crypto_ticker(ticker)
        if not is_crypto and not is_market_open_extended():
            return returns  # Stocks outside market hours

        # Check if returns already includes today
        today = pd.Timestamp.now().normalize()
        if returns.index.max() >= today:
            return returns  # Already have today's data

        # Get yesterday's close (last value in the price series)
        # We need to fetch the actual close price, not the return
        from app.services.market_data import fetch_price_history

        df = fetch_price_history(ticker, period="5d", interval="1d", skip_live_bar=True)
        if df is None or df.empty or len(df) < 2:
            return returns

        yesterday_close = df["Close"].iloc[-1]

        # Fetch live price
        from app.services.yahoo_finance_service import YahooFinanceService

        live_prices = YahooFinanceService.fetch_batch_current_prices([ticker])
        if not live_prices or ticker not in live_prices:
            return returns

        live_price = live_prices[ticker]

        # Calculate today's return
        todays_return = (live_price / yesterday_close) - 1

        # Append to returns series
        new_entry = pd.Series([todays_return], index=[today], name=returns.name)
        updated_returns = pd.concat([returns, new_entry])

        print(f"[Live Return] {ticker}: yesterday=${yesterday_close:.2f}, live=${live_price:.2f}, return={todays_return:.4f}")

        return updated_returns

    @classmethod
    def append_live_portfolio_return(
        cls,
        returns: "pd.Series",
        portfolio_name: str,
        include_cash: bool = False,
    ) -> "pd.Series":
        """
        Append today's live portfolio return based on current holdings.

        Fetches live prices for all eligible tickers and calculates
        the weighted portfolio return for today.

        Args:
            returns: Existing portfolio returns series
            portfolio_name: Name of the portfolio
            include_cash: Whether to include cash in weight calculation

        Returns:
            Returns series with today's live return appended (if applicable)
        """
        import pandas as pd
        from app.utils.market_hours import is_crypto_ticker, is_market_open_extended
        from app.services.yahoo_finance_service import YahooFinanceService
        from app.services.market_data import fetch_price_history

        if returns is None or returns.empty:
            return returns

        # Check if returns already includes today
        today = pd.Timestamp.now().normalize()
        if returns.index.max() >= today:
            return returns

        # Get current positions and weights from latest date
        weights = cls.get_daily_weights(portfolio_name, include_cash=include_cash)
        if weights.empty:
            return returns

        # Get latest weights (last row)
        latest_weights = weights.iloc[-1]
        tickers = [t for t in latest_weights.index if t.upper() != "FREE CASH" and latest_weights[t] > 0]

        if not tickers:
            return returns

        # Determine which tickers are eligible for live update
        is_extended_hours = is_market_open_extended()
        eligible_tickers = []
        for ticker in tickers:
            if is_crypto_ticker(ticker) or is_extended_hours:
                eligible_tickers.append(ticker)

        if not eligible_tickers:
            return returns

        # Fetch live prices in batch
        live_prices = YahooFinanceService.fetch_batch_current_prices(eligible_tickers)
        if not live_prices:
            return returns

        # Get yesterday's closes for eligible tickers
        yesterday_closes = {}
        for ticker in eligible_tickers:
            df = fetch_price_history(ticker, period="5d", interval="1d", skip_live_bar=True)
            if df is not None and not df.empty:
                yesterday_closes[ticker] = df["Close"].iloc[-1]

        # Calculate weighted portfolio return for today
        portfolio_return = 0.0
        total_weight = 0.0

        for ticker in eligible_tickers:
            if ticker in live_prices and ticker in yesterday_closes:
                weight = latest_weights[ticker]
                yesterday = yesterday_closes[ticker]
                live = live_prices[ticker]
                ticker_return = (live / yesterday) - 1
                portfolio_return += weight * ticker_return
                total_weight += weight

        if total_weight == 0:
            return returns

        # Note: Non-eligible tickers contribute 0 return but keep their weight
        # This is a simplification - ideally we'd use yesterday's return for them

        # Append to returns series
        new_entry = pd.Series([portfolio_return], index=[today], name=returns.name)
        updated_returns = pd.concat([returns, new_entry])

        print(f"[Live Return] Portfolio {portfolio_name}: {len(eligible_tickers)} tickers updated, return={portfolio_return:.4f}")

        return updated_returns

    @classmethod
    def get_risk_metrics(
        cls,
        portfolio_name: str,
        benchmark: str,
        is_benchmark_portfolio: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_cash: bool = False,
        risk_free_rate: float = 0.0,
    ) -> Dict[str, float]:
        """
        Calculate comprehensive risk metrics for a portfolio vs benchmark.

        This is a convenience method that calculates all common risk and
        performance metrics in a single call, avoiding redundant data fetching.

        Args:
            portfolio_name: Name of the portfolio
            benchmark: Benchmark ticker (e.g., "SPY") or portfolio name
            is_benchmark_portfolio: True if benchmark is a portfolio name
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            include_cash: Include cash in portfolio calculations
            risk_free_rate: Annualized risk-free rate (as decimal, e.g., 0.05 = 5%)

        Returns:
            Dict with keys:
            - beta: Portfolio beta vs benchmark
            - alpha: Jensen's alpha (annualized)
            - tracking_error: Annualized tracking error
            - information_ratio: Information ratio
            - sharpe_ratio: Portfolio Sharpe ratio
            - sortino_ratio: Portfolio Sortino ratio
            - benchmark_sharpe: Benchmark Sharpe ratio
            - correlation: Correlation with benchmark
            - r_squared: R-squared of regression
            - portfolio_volatility: Annualized portfolio volatility
            - benchmark_volatility: Annualized benchmark volatility
        """
        import numpy as np

        # Get portfolio returns
        portfolio_returns = cls.get_time_varying_portfolio_returns(
            portfolio_name, start_date, end_date, include_cash, interval="daily"
        )

        # Get benchmark returns
        benchmark_returns = cls.get_benchmark_returns(
            benchmark, is_benchmark_portfolio, start_date, end_date, include_cash, "daily"
        )

        # Handle empty returns
        if portfolio_returns.empty or benchmark_returns.empty:
            return {
                "beta": float("nan"),
                "alpha": float("nan"),
                "tracking_error": float("nan"),
                "information_ratio": float("nan"),
                "sharpe_ratio": float("nan"),
                "sortino_ratio": float("nan"),
                "benchmark_sharpe": float("nan"),
                "correlation": float("nan"),
                "r_squared": float("nan"),
                "portfolio_volatility": float("nan"),
                "benchmark_volatility": float("nan"),
            }

        # Calculate all metrics
        return {
            "beta": cls.get_beta(portfolio_returns, benchmark_returns),
            "alpha": cls.get_alpha(portfolio_returns, benchmark_returns, risk_free_rate),
            "tracking_error": cls.get_tracking_error(portfolio_returns, benchmark_returns),
            "information_ratio": cls.get_information_ratio(portfolio_returns, benchmark_returns),
            "sharpe_ratio": cls.get_sharpe_ratio(portfolio_returns, risk_free_rate),
            "sortino_ratio": cls.get_sortino_ratio(portfolio_returns, risk_free_rate),
            "benchmark_sharpe": cls.get_sharpe_ratio(benchmark_returns, risk_free_rate),
            "correlation": cls.get_correlation(portfolio_returns, benchmark_returns),
            "r_squared": cls.get_r_squared(portfolio_returns, benchmark_returns),
            "portfolio_volatility": portfolio_returns.std() * np.sqrt(252),
            "benchmark_volatility": benchmark_returns.std() * np.sqrt(252),
        }
