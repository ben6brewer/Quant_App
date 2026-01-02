"""Performance Metrics Service - Calculate comprehensive portfolio performance statistics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd


class PerformanceMetricsService:
    """
    Service for calculating comprehensive performance metrics.

    All methods are static and do not maintain state.
    Heavy imports (numpy, pandas) are done inside methods for lazy loading.
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
    def get_annualized_mean_return(returns: "pd.Series") -> float:
        """
        Calculate annualized mean return.

        Assumes daily returns (252 trading days per year).

        Args:
            returns: Series of daily returns (as decimals)

        Returns:
            Annualized mean return as decimal
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) == 0:
            return float("nan")

        return clean_returns.mean() * 252

    @staticmethod
    def get_mean_excess_return(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate annualized mean excess return (portfolio - benchmark).

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

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
        return excess_returns.mean() * 252

    # =========================================================================
    # Risk Metrics
    # =========================================================================

    @staticmethod
    def get_annualized_std(returns: "pd.Series") -> float:
        """
        Calculate annualized standard deviation (volatility).

        Args:
            returns: Series of daily returns (as decimals)

        Returns:
            Annualized standard deviation as decimal
        """
        import numpy as np

        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 2:
            return float("nan")

        return clean_returns.std(ddof=1) * np.sqrt(252)

    @staticmethod
    def get_downside_risk(returns: "pd.Series", target: float = 0.0) -> float:
        """
        Calculate annualized downside deviation (downside risk).

        Only considers returns below the target threshold.

        Args:
            returns: Series of daily returns (as decimals)
            target: Daily target return (default 0)

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
        return downside_dev * np.sqrt(252)

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
    def get_var_95(returns: "pd.Series") -> float:
        """
        Calculate historical Value at Risk at 95% confidence level.

        This is the 5th percentile of returns (ex-post/historical VaR).

        Args:
            returns: Series of returns (as decimals)

        Returns:
            VaR at 95% confidence (negative value expected)
        """
        if returns is None or returns.empty:
            return float("nan")

        clean_returns = returns.dropna()
        if len(clean_returns) < 20:  # Need sufficient data for VaR
            return float("nan")

        return clean_returns.quantile(0.05)

    # =========================================================================
    # Risk/Return Metrics
    # =========================================================================

    @staticmethod
    def get_treynor_measure(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        risk_free_rate: float = 0.0,
    ) -> float:
        """
        Calculate the Treynor measure (Treynor ratio).

        Treynor = (Portfolio Return - Risk-Free Rate) / Beta

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)
            risk_free_rate: Annualized risk-free rate (as decimal)

        Returns:
            Treynor measure
        """
        import numpy as np

        from app.services import ReturnsDataService

        beta = ReturnsDataService.get_beta(portfolio_returns, benchmark_returns)
        if np.isnan(beta) or beta == 0:
            return float("nan")

        # Annualized portfolio return
        if portfolio_returns is None or portfolio_returns.empty:
            return float("nan")

        clean_returns = portfolio_returns.dropna()
        if len(clean_returns) < 2:
            return float("nan")

        annualized_return = clean_returns.mean() * 252
        excess_return = annualized_return - risk_free_rate

        return excess_return / beta

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

    @staticmethod
    def get_capture_ratio_display(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate capture ratio as Up Capture / Down Capture.

        Values > 1 indicate portfolio captures more upside than downside.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (as decimals)

        Returns:
            Up capture / Down capture ratio
        """
        import numpy as np

        up_cap, down_cap = PerformanceMetricsService.get_capture_ratio(
            portfolio_returns, benchmark_returns
        )

        if np.isnan(up_cap) or np.isnan(down_cap) or down_cap == 0:
            return float("nan")

        return up_cap / down_cap

    # =========================================================================
    # Risk-Free Rate
    # =========================================================================

    @staticmethod
    def get_risk_free_rate() -> float:
        """
        Fetch current risk-free rate from ^IRX (3-month Treasury Bill).

        ^IRX is quoted as a percentage (e.g., 5.25 means 5.25%).

        Returns:
            Annualized risk-free rate as decimal (e.g., 0.0525 for 5.25%)
        """
        from app.services.market_data import fetch_price_history

        try:
            df = fetch_price_history("^IRX", period="5d", interval="1d")
            if df is not None and not df.empty:
                # ^IRX is quoted as percentage
                return df["Close"].iloc[-1] / 100
        except Exception as e:
            print(f"Error fetching risk-free rate: {e}")

        # Default fallback
        return 0.05  # 5%

    # =========================================================================
    # Comprehensive Metrics Calculation
    # =========================================================================

    @classmethod
    def calculate_all_metrics(
        cls,
        portfolio_returns: "pd.Series",
        benchmark_returns: Optional["pd.Series"],
        risk_free_rate: float,
    ) -> Dict[str, Any]:
        """
        Calculate all performance metrics for a single time period.

        Args:
            portfolio_returns: Series of portfolio returns (as decimals)
            benchmark_returns: Series of benchmark returns (optional)
            risk_free_rate: Annualized risk-free rate (as decimal)

        Returns:
            Dictionary with all metric values
        """
        from app.services import ReturnsDataService

        metrics: Dict[str, Any] = {}

        # Return Section - Portfolio
        metrics["total_return"] = cls.get_total_return(portfolio_returns)
        metrics["max_return"] = cls.get_max_return(portfolio_returns)
        metrics["min_return"] = cls.get_min_return(portfolio_returns)
        metrics["mean_return_annualized"] = cls.get_annualized_mean_return(
            portfolio_returns
        )

        # Risk Section - Portfolio
        metrics["std_annualized"] = cls.get_annualized_std(portfolio_returns)
        metrics["downside_risk"] = cls.get_downside_risk(portfolio_returns)
        metrics["skewness"] = cls.get_skewness(portfolio_returns)
        metrics["var_95"] = cls.get_var_95(portfolio_returns)

        # Risk/Return Section - Portfolio
        metrics["sharpe_ratio"] = ReturnsDataService.get_sharpe_ratio(
            portfolio_returns, risk_free_rate
        )
        metrics["sortino_ratio"] = ReturnsDataService.get_sortino_ratio(
            portfolio_returns, risk_free_rate
        )

        # Benchmark-relative metrics
        if benchmark_returns is not None and not benchmark_returns.empty:
            # Return section - Benchmark
            metrics["bmrk_total_return"] = cls.get_total_return(benchmark_returns)
            metrics["bmrk_max_return"] = cls.get_max_return(benchmark_returns)
            metrics["bmrk_min_return"] = cls.get_min_return(benchmark_returns)
            metrics["bmrk_mean_return_annualized"] = cls.get_annualized_mean_return(
                benchmark_returns
            )

            # Mean excess return (portfolio only)
            metrics["mean_excess_return"] = cls.get_mean_excess_return(
                portfolio_returns, benchmark_returns
            )

            # Risk section - Benchmark
            metrics["bmrk_std_annualized"] = cls.get_annualized_std(benchmark_returns)
            metrics["bmrk_downside_risk"] = cls.get_downside_risk(benchmark_returns)
            metrics["bmrk_skewness"] = cls.get_skewness(benchmark_returns)
            metrics["bmrk_var_95"] = cls.get_var_95(benchmark_returns)

            # Tracking error (portfolio only)
            metrics["tracking_error"] = ReturnsDataService.get_tracking_error(
                portfolio_returns, benchmark_returns
            )

            # Risk/Return section - Benchmark
            metrics["bmrk_sharpe_ratio"] = ReturnsDataService.get_sharpe_ratio(
                benchmark_returns, risk_free_rate
            )
            metrics["bmrk_sortino_ratio"] = ReturnsDataService.get_sortino_ratio(
                benchmark_returns, risk_free_rate
            )

            # Portfolio vs benchmark metrics (portfolio only)
            metrics["jensen_alpha"] = ReturnsDataService.get_alpha(
                portfolio_returns, benchmark_returns, risk_free_rate
            )
            metrics["information_ratio"] = ReturnsDataService.get_information_ratio(
                portfolio_returns, benchmark_returns
            )
            metrics["treynor_measure"] = cls.get_treynor_measure(
                portfolio_returns, benchmark_returns, risk_free_rate
            )
            metrics["beta"] = ReturnsDataService.get_beta(
                portfolio_returns, benchmark_returns
            )
            metrics["correlation"] = ReturnsDataService.get_correlation(
                portfolio_returns, benchmark_returns
            )
            metrics["capture_ratio"] = cls.get_capture_ratio(
                portfolio_returns, benchmark_returns
            )

        return metrics
