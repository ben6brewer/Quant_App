"""Statistics Service - Centralized financial statistics calculations.

This service provides all statistical calculations for portfolio analysis,
risk metrics, and performance measurement. All methods are static with
lazy imports to maintain fast startup times.

Used by:
- Performance Metrics module
- Monte Carlo module
- Return Distribution module
- Tracking Error Volatility module (upcoming)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd


class StatisticsService:
    """
    Centralized service for financial statistics calculations.

    All methods are static and stateless. Heavy imports (numpy, pandas)
    are done inside methods for lazy loading to keep startup fast.

    Usage:
        from app.services import StatisticsService

        sharpe = StatisticsService.get_sharpe_ratio(returns, risk_free_rate=0.05)
        beta = StatisticsService.get_beta(portfolio_returns, benchmark_returns)
    """

    # =========================================================================
    # Return Metrics
    # =========================================================================

    @staticmethod
    def get_total_return(returns: "pd.Series") -> float:
        """
        Calculate total cumulative return over the period.

        Args:
            returns: Series of returns (as decimals, e.g., 0.05 = 5%)

        Returns:
            Total cumulative return as decimal (e.g., 0.15 = 15%)
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) == 0:
            return float("nan")

        return (1 + clean_returns).prod() - 1

    @staticmethod
    def get_annualized_return(
        returns: "pd.Series",
        trading_days: int = 252,
    ) -> float:
        """
        Calculate annualized mean return.

        Args:
            returns: Series of daily returns (as decimals)
            trading_days: Number of trading days per year (default 252)

        Returns:
            Annualized mean return as decimal
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) == 0:
            return float("nan")

        return clean_returns.mean() * trading_days

    @staticmethod
    def get_max_return(returns: "pd.Series") -> float:
        """
        Get maximum single-period return.

        Args:
            returns: Series of returns (as decimals)

        Returns:
            Maximum return as decimal
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) == 0:
            return float("nan")

        return clean_returns.max()

    @staticmethod
    def get_min_return(returns: "pd.Series") -> float:
        """
        Get minimum single-period return.

        Args:
            returns: Series of returns (as decimals)

        Returns:
            Minimum return as decimal
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) == 0:
            return float("nan")

        return clean_returns.min()

    @staticmethod
    def get_mean_excess_return(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        trading_days: int = 252,
    ) -> float:
        """
        Calculate annualized mean excess return (portfolio - benchmark).

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)
            trading_days: Number of trading days per year (default 252)

        Returns:
            Annualized mean excess return as decimal
        """
        import pandas as pd

        if portfolio_returns is None or benchmark_returns is None:
            return float("nan")

        # Align the two series
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        excess_returns = aligned["portfolio"] - aligned["benchmark"]
        return excess_returns.mean() * trading_days

    # =========================================================================
    # Risk Metrics
    # =========================================================================

    @staticmethod
    def get_annualized_volatility(
        returns: "pd.Series",
        trading_days: int = 252,
    ) -> float:
        """
        Calculate annualized standard deviation (volatility).

        Args:
            returns: Series of daily returns (as decimals)
            trading_days: Number of trading days per year (default 252)

        Returns:
            Annualized standard deviation as decimal
        """
        import numpy as np

        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 2:
            return float("nan")

        return clean_returns.std(ddof=1) * np.sqrt(trading_days)

    @staticmethod
    def get_downside_risk(
        returns: "pd.Series",
        target: float = 0.0,
        trading_days: int = 252,
    ) -> float:
        """
        Calculate annualized downside deviation (downside risk).

        Only considers returns below the target threshold.

        Args:
            returns: Series of daily returns (as decimals)
            target: Daily target return (default 0)
            trading_days: Number of trading days per year (default 252)

        Returns:
            Annualized downside deviation as decimal
        """
        import numpy as np

        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 2:
            return float("nan")

        # Only consider returns below target
        downside_returns = clean_returns[clean_returns < target]
        if len(downside_returns) == 0:
            return 0.0  # No downside

        # Calculate downside deviation: sqrt(mean(min(r-target, 0)^2))
        squared_downside = (downside_returns - target) ** 2
        downside_dev = np.sqrt(squared_downside.mean())

        # Annualize
        return downside_dev * np.sqrt(trading_days)

    @staticmethod
    def get_skewness(returns: "pd.Series") -> float:
        """
        Calculate skewness of returns distribution.

        Positive skew = longer right tail (more extreme gains)
        Negative skew = longer left tail (more extreme losses)

        Args:
            returns: Series of returns (as decimals)

        Returns:
            Skewness value
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 3:
            return float("nan")

        return clean_returns.skew()

    @staticmethod
    def get_kurtosis(returns: "pd.Series") -> float:
        """
        Calculate excess kurtosis of returns distribution.

        Positive kurtosis = heavier tails (more extreme events)
        Negative kurtosis = lighter tails (fewer extreme events)

        Args:
            returns: Series of returns (as decimals)

        Returns:
            Excess kurtosis value
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 4:
            return float("nan")

        return clean_returns.kurtosis()

    @staticmethod
    def get_var(
        returns: "pd.Series",
        confidence: float = 0.95,
    ) -> float:
        """
        Calculate historical Value at Risk.

        This is the percentile of returns (ex-post/historical VaR).

        Args:
            returns: Series of returns (as decimals)
            confidence: Confidence level (default 0.95 for 95% VaR)

        Returns:
            VaR at specified confidence (negative value expected)
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 20:  # Need sufficient data for VaR
            return float("nan")

        # VaR at 95% is the 5th percentile
        return clean_returns.quantile(1 - confidence)

    @staticmethod
    def get_cvar(
        returns: "pd.Series",
        confidence: float = 0.95,
    ) -> float:
        """
        Calculate Conditional Value at Risk (Expected Shortfall).

        CVaR is the expected loss given that losses exceed VaR.
        Also known as Expected Shortfall (ES).

        Args:
            returns: Series of returns (as decimals)
            confidence: Confidence level (default 0.95)

        Returns:
            CVaR at specified confidence (negative value expected)
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 20:
            return float("nan")

        var = clean_returns.quantile(1 - confidence)
        # CVaR = mean of returns below VaR
        tail_returns = clean_returns[clean_returns <= var]

        if len(tail_returns) == 0:
            return var

        return tail_returns.mean()

    @staticmethod
    def get_max_drawdown(returns: "pd.Series") -> float:
        """
        Calculate maximum drawdown from returns series.

        Args:
            returns: Series of returns (as decimals)

        Returns:
            Maximum drawdown as negative decimal (e.g., -0.20 = -20%)
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 2:
            return float("nan")

        # Calculate cumulative returns (wealth index)
        cumulative = (1 + clean_returns).cumprod()

        # Calculate running maximum
        running_max = cumulative.cummax()

        # Drawdown = current / peak - 1
        drawdowns = cumulative / running_max - 1

        return drawdowns.min()

    # =========================================================================
    # Risk-Adjusted Metrics
    # =========================================================================

    @staticmethod
    def get_sharpe_ratio(
        returns: "pd.Series",
        risk_free_rate: float = 0.0,
        trading_days: int = 252,
    ) -> float:
        """
        Calculate the Sharpe ratio.

        Sharpe ratio measures risk-adjusted return:
        (mean return - risk-free rate) / volatility

        Args:
            returns: Series of returns (as decimals)
            risk_free_rate: Annualized risk-free rate (as decimal)
            trading_days: Number of trading days per year (default 252)

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
        daily_rf = risk_free_rate / trading_days

        # Calculate excess returns
        excess_returns = clean_returns - daily_rf

        # Calculate Sharpe ratio
        std = excess_returns.std(ddof=1)
        if std == 0 or np.isnan(std):
            return float("nan")

        # Annualize: multiply by sqrt(trading_days)
        return (excess_returns.mean() / std) * np.sqrt(trading_days)

    @staticmethod
    def get_sortino_ratio(
        returns: "pd.Series",
        risk_free_rate: float = 0.0,
        target_return: float = 0.0,
        trading_days: int = 252,
    ) -> float:
        """
        Calculate the Sortino ratio.

        Sortino ratio is similar to Sharpe but only penalizes downside volatility,
        making it more appropriate for asymmetric return distributions.

        Args:
            returns: Series of returns (as decimals)
            risk_free_rate: Annualized risk-free rate (as decimal)
            target_return: Annualized target/minimum acceptable return (default 0)
            trading_days: Number of trading days per year (default 252)

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
        daily_rf = risk_free_rate / trading_days
        daily_target = target_return / trading_days

        # Calculate excess returns over risk-free rate
        excess_returns = clean_returns - daily_rf

        # Calculate downside deviation (only negative returns below target)
        downside_returns = clean_returns[clean_returns < daily_target] - daily_target
        if len(downside_returns) == 0:
            return float("nan")

        downside_std = np.sqrt((downside_returns ** 2).mean())
        if downside_std == 0 or np.isnan(downside_std):
            return float("nan")

        # Annualize
        return (excess_returns.mean() / downside_std) * np.sqrt(trading_days)

    @staticmethod
    def get_treynor_ratio(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        risk_free_rate: float = 0.0,
        trading_days: int = 252,
    ) -> float:
        """
        Calculate the Treynor ratio.

        Treynor = (Portfolio Return - Risk-Free Rate) / Beta

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)
            risk_free_rate: Annualized risk-free rate (as decimal)
            trading_days: Number of trading days per year (default 252)

        Returns:
            Treynor ratio, or NaN if insufficient data
        """
        import numpy as np

        beta = StatisticsService.get_beta(portfolio_returns, benchmark_returns)
        if np.isnan(beta) or beta == 0:
            return float("nan")

        if portfolio_returns is None or portfolio_returns.empty:
            return float("nan")

        clean_returns = portfolio_returns.dropna()
        if len(clean_returns) < 2:
            return float("nan")

        annualized_return = clean_returns.mean() * trading_days
        excess_return = annualized_return - risk_free_rate

        return excess_return / beta

    # =========================================================================
    # Benchmark-Relative Metrics
    # =========================================================================

    @staticmethod
    def get_beta(
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
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        # Beta = Cov(Rp, Rb) / Var(Rb)
        covariance = aligned["portfolio"].cov(aligned["benchmark"])
        benchmark_variance = aligned["benchmark"].var()

        if benchmark_variance == 0 or np.isnan(benchmark_variance):
            return float("nan")

        return covariance / benchmark_variance

    @staticmethod
    def get_alpha(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        risk_free_rate: float = 0.0,
        trading_days: int = 252,
    ) -> float:
        """
        Calculate Jensen's alpha (annualized).

        Alpha measures excess return not explained by beta exposure to benchmark.
        Positive alpha indicates outperformance.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)
            risk_free_rate: Annualized risk-free rate (as decimal)
            trading_days: Number of trading days per year (default 252)

        Returns:
            Annualized alpha, or NaN if insufficient data
        """
        import numpy as np
        import pandas as pd

        beta = StatisticsService.get_beta(portfolio_returns, benchmark_returns)
        if np.isnan(beta):
            return float("nan")

        # Align returns
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        # Annualize mean returns
        portfolio_annual = aligned["portfolio"].mean() * trading_days
        benchmark_annual = aligned["benchmark"].mean() * trading_days

        # Jensen's Alpha = Rp - [Rf + beta * (Rb - Rf)]
        alpha = portfolio_annual - (
            risk_free_rate + beta * (benchmark_annual - risk_free_rate)
        )

        return alpha

    @staticmethod
    def get_tracking_error(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        trading_days: int = 252,
    ) -> float:
        """
        Calculate annualized tracking error.

        Tracking error measures the volatility of the difference between
        portfolio and benchmark returns. Lower values indicate closer tracking.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)
            trading_days: Number of trading days per year (default 252)

        Returns:
            Annualized tracking error, or NaN if insufficient data
        """
        import numpy as np
        import pandas as pd

        if portfolio_returns is None or benchmark_returns is None:
            return float("nan")

        # Align the two series
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        # Tracking error = std(portfolio - benchmark) * sqrt(trading_days)
        excess_returns = aligned["portfolio"] - aligned["benchmark"]
        tracking_error = excess_returns.std(ddof=1) * np.sqrt(trading_days)

        return tracking_error

    @staticmethod
    def get_information_ratio(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        trading_days: int = 252,
    ) -> float:
        """
        Calculate the information ratio.

        Information ratio measures active return per unit of active risk.
        Higher values indicate better risk-adjusted active performance.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)
            trading_days: Number of trading days per year (default 252)

        Returns:
            Information ratio, or NaN if insufficient data
        """
        import numpy as np
        import pandas as pd

        tracking_error = StatisticsService.get_tracking_error(
            portfolio_returns, benchmark_returns, trading_days
        )
        if np.isnan(tracking_error) or tracking_error == 0:
            return float("nan")

        # Align returns
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        # Annualized excess return
        excess_returns = aligned["portfolio"] - aligned["benchmark"]
        annualized_excess = excess_returns.mean() * trading_days

        # Information ratio = annualized excess return / tracking error
        return annualized_excess / tracking_error

    @staticmethod
    def get_correlation(
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
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 2:
            return float("nan")

        return aligned["portfolio"].corr(aligned["benchmark"])

    @staticmethod
    def get_r_squared(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate R-squared (coefficient of determination).

        R-squared measures what percentage of portfolio variance is explained
        by the benchmark.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

        Returns:
            R-squared (0 to 1), or NaN if insufficient data
        """
        import numpy as np

        correlation = StatisticsService.get_correlation(
            portfolio_returns, benchmark_returns
        )
        if np.isnan(correlation):
            return float("nan")

        return correlation ** 2

    @staticmethod
    def get_capture_ratio(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> Tuple[float, float]:
        """
        Calculate upside and downside capture ratios.

        Up Capture = mean(portfolio | benchmark > 0) / mean(benchmark | benchmark > 0) * 100
        Down Capture = mean(portfolio | benchmark < 0) / mean(benchmark | benchmark < 0) * 100

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

        Returns:
            Tuple of (up_capture, down_capture) as percentages
        """
        import numpy as np
        import pandas as pd

        if portfolio_returns is None or benchmark_returns is None:
            return (float("nan"), float("nan"))

        # Align the two series
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 10:  # Need sufficient data
            return (float("nan"), float("nan"))

        # Up capture: when benchmark is positive
        up_mask = aligned["benchmark"] > 0
        if up_mask.sum() == 0:
            up_capture = float("nan")
        else:
            up_port_mean = aligned.loc[up_mask, "portfolio"].mean()
            up_bmrk_mean = aligned.loc[up_mask, "benchmark"].mean()
            if up_bmrk_mean == 0:
                up_capture = float("nan")
            else:
                up_capture = (up_port_mean / up_bmrk_mean) * 100

        # Down capture: when benchmark is negative
        down_mask = aligned["benchmark"] < 0
        if down_mask.sum() == 0:
            down_capture = float("nan")
        else:
            down_port_mean = aligned.loc[down_mask, "portfolio"].mean()
            down_bmrk_mean = aligned.loc[down_mask, "benchmark"].mean()
            if down_bmrk_mean == 0:
                down_capture = float("nan")
            else:
                down_capture = (down_port_mean / down_bmrk_mean) * 100

        return (up_capture, down_capture)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def get_risk_free_rate() -> float:
        """
        Fetch current risk-free rate from ^IRX (3-month Treasury Bill).

        ^IRX is quoted as a percentage (e.g., 5.25 means 5.25%).

        Returns:
            Annualized risk-free rate as decimal (e.g., 0.0525 for 5.25%)
        """
        # Use Yahoo Finance directly for ^IRX (index tickers not supported by Polygon Starter)
        import yfinance as yf

        try:
            df = yf.download("^IRX", period="5d", interval="1d", progress=False)
            if df is not None and not df.empty:
                # Handle MultiIndex columns if present
                if hasattr(df.columns, 'levels'):
                    close = df["Close"].iloc[:, 0] if df["Close"].ndim > 1 else df["Close"]
                else:
                    close = df["Close"]
                # ^IRX is quoted as percentage
                return float(close.iloc[-1]) / 100
        except Exception as e:
            print(f"Error fetching risk-free rate: {e}")

        # Default fallback
        return 0.05  # 5%

    @staticmethod
    def get_distribution_statistics(returns: "pd.Series") -> Dict[str, float]:
        """
        Calculate distribution statistics for a returns series.

        This is a convenience method that computes standard statistical measures
        used in distribution analysis.

        Args:
            returns: Series of returns (as decimals)

        Returns:
            Dict with keys: mean, std, skew, kurtosis, min, max, count
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

    @staticmethod
    def align_returns(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> "pd.DataFrame":
        """
        Align portfolio and benchmark returns to common dates.

        Args:
            portfolio_returns: Series of portfolio returns
            benchmark_returns: Series of benchmark returns

        Returns:
            DataFrame with 'portfolio' and 'benchmark' columns, NaN rows dropped
        """
        import pandas as pd

        if portfolio_returns is None or benchmark_returns is None:
            return pd.DataFrame()

        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        return aligned
