"""Performance Metrics Service - Calculate comprehensive portfolio performance statistics.

This service orchestrates performance metric calculations for the Performance Metrics
module. It delegates to StatisticsService for all statistical calculations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd


class PerformanceMetricsService:
    """
    Service for calculating comprehensive performance metrics.

    This service orchestrates the calculation of all metrics for the
    Performance Metrics module. Individual calculations are delegated
    to StatisticsService for consistency and reuse.
    """

    # =========================================================================
    # Delegated Methods (for backward compatibility)
    # =========================================================================

    @staticmethod
    def get_total_return(returns: "pd.Series") -> float:
        """Calculate total cumulative return. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_total_return(returns)

    @staticmethod
    def get_max_return(returns: "pd.Series") -> float:
        """Get maximum single-period return. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_max_return(returns)

    @staticmethod
    def get_min_return(returns: "pd.Series") -> float:
        """Get minimum single-period return. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_min_return(returns)

    @staticmethod
    def get_annualized_mean_return(returns: "pd.Series") -> float:
        """Calculate annualized mean return. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_annualized_return(returns)

    @staticmethod
    def get_mean_excess_return(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """Calculate annualized mean excess return. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_mean_excess_return(portfolio_returns, benchmark_returns)

    @staticmethod
    def get_annualized_std(returns: "pd.Series") -> float:
        """Calculate annualized volatility. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_annualized_volatility(returns)

    @staticmethod
    def get_downside_risk(returns: "pd.Series", target: float = 0.0) -> float:
        """Calculate annualized downside deviation. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_downside_risk(returns, target)

    @staticmethod
    def get_skewness(returns: "pd.Series") -> float:
        """Calculate skewness. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_skewness(returns)

    @staticmethod
    def get_var_95(returns: "pd.Series") -> float:
        """Calculate 95% VaR. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_var(returns, confidence=0.95)

    @staticmethod
    def get_treynor_measure(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        risk_free_rate: float = 0.0,
    ) -> float:
        """Calculate Treynor ratio. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_treynor_ratio(
            portfolio_returns, benchmark_returns, risk_free_rate
        )

    @staticmethod
    def get_capture_ratio(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> Tuple[float, float]:
        """Calculate capture ratios. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_capture_ratio(portfolio_returns, benchmark_returns)

    @staticmethod
    def get_capture_ratio_display(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate capture ratio as Up Capture / Down Capture.

        Values > 1 indicate portfolio captures more upside than downside.
        """
        import numpy as np
        from app.services import StatisticsService

        up_cap, down_cap = StatisticsService.get_capture_ratio(
            portfolio_returns, benchmark_returns
        )

        if np.isnan(up_cap) or np.isnan(down_cap) or down_cap == 0:
            return float("nan")

        return up_cap / down_cap

    @staticmethod
    def get_risk_free_rate() -> float:
        """Fetch current risk-free rate. Delegates to StatisticsService."""
        from app.services import StatisticsService
        return StatisticsService.get_risk_free_rate()

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
        from app.services import StatisticsService

        metrics: Dict[str, Any] = {}

        # Return Section - Portfolio
        metrics["total_return"] = StatisticsService.get_total_return(portfolio_returns)
        metrics["max_return"] = StatisticsService.get_max_return(portfolio_returns)
        metrics["min_return"] = StatisticsService.get_min_return(portfolio_returns)
        metrics["mean_return_annualized"] = StatisticsService.get_annualized_return(
            portfolio_returns
        )

        # Risk Section - Portfolio
        metrics["std_annualized"] = StatisticsService.get_annualized_volatility(
            portfolio_returns
        )
        metrics["downside_risk"] = StatisticsService.get_downside_risk(portfolio_returns)
        metrics["skewness"] = StatisticsService.get_skewness(portfolio_returns)
        metrics["var_95"] = StatisticsService.get_var(portfolio_returns, confidence=0.95)

        # Risk/Return Section - Portfolio
        metrics["sharpe_ratio"] = StatisticsService.get_sharpe_ratio(
            portfolio_returns, risk_free_rate
        )
        metrics["sortino_ratio"] = StatisticsService.get_sortino_ratio(
            portfolio_returns, risk_free_rate
        )

        # Benchmark-relative metrics
        if benchmark_returns is not None and not benchmark_returns.empty:
            # Return section - Benchmark
            metrics["bmrk_total_return"] = StatisticsService.get_total_return(
                benchmark_returns
            )
            metrics["bmrk_max_return"] = StatisticsService.get_max_return(
                benchmark_returns
            )
            metrics["bmrk_min_return"] = StatisticsService.get_min_return(
                benchmark_returns
            )
            metrics["bmrk_mean_return_annualized"] = StatisticsService.get_annualized_return(
                benchmark_returns
            )

            # Mean excess return (portfolio only)
            metrics["mean_excess_return"] = StatisticsService.get_mean_excess_return(
                portfolio_returns, benchmark_returns
            )

            # Risk section - Benchmark
            metrics["bmrk_std_annualized"] = StatisticsService.get_annualized_volatility(
                benchmark_returns
            )
            metrics["bmrk_downside_risk"] = StatisticsService.get_downside_risk(
                benchmark_returns
            )
            metrics["bmrk_skewness"] = StatisticsService.get_skewness(benchmark_returns)
            metrics["bmrk_var_95"] = StatisticsService.get_var(
                benchmark_returns, confidence=0.95
            )

            # Tracking error (portfolio only)
            metrics["tracking_error"] = StatisticsService.get_tracking_error(
                portfolio_returns, benchmark_returns
            )

            # Risk/Return section - Benchmark
            metrics["bmrk_sharpe_ratio"] = StatisticsService.get_sharpe_ratio(
                benchmark_returns, risk_free_rate
            )
            metrics["bmrk_sortino_ratio"] = StatisticsService.get_sortino_ratio(
                benchmark_returns, risk_free_rate
            )

            # Portfolio vs benchmark metrics (portfolio only)
            metrics["jensen_alpha"] = StatisticsService.get_alpha(
                portfolio_returns, benchmark_returns, risk_free_rate
            )
            metrics["information_ratio"] = StatisticsService.get_information_ratio(
                portfolio_returns, benchmark_returns
            )
            metrics["treynor_measure"] = StatisticsService.get_treynor_ratio(
                portfolio_returns, benchmark_returns, risk_free_rate
            )
            metrics["beta"] = StatisticsService.get_beta(
                portfolio_returns, benchmark_returns
            )
            metrics["correlation"] = StatisticsService.get_correlation(
                portfolio_returns, benchmark_returns
            )
            metrics["capture_ratio"] = StatisticsService.get_capture_ratio(
                portfolio_returns, benchmark_returns
            )

        return metrics
