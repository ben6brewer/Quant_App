"""Risk Analytics Service - Core risk calculation engine using factor model.

Implements proper factor-based risk decomposition:
- Total Active Risk = Tracking Error (annualized std of return differences)
- Factor Risk = Risk explained by factor exposures (from R² of regressions)
- Idiosyncratic Risk = Risk from residuals (1 - Factor Risk)

Uses OLS regression with Fama-French 5 factors + Momentum + constructed factors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd

from .sector_override_service import SectorOverrideService
from app.services.ticker_metadata_service import TickerMetadataService


class RiskAnalyticsService:
    """
    Risk analytics calculations for portfolio vs benchmark.

    Uses a regression-based factor model for proper risk decomposition:
    - Factor model regression per security
    - Risk metrics derived from regression residuals and fitted values
    - CTEV contributions based on actual factor exposures
    """

    FACTOR_GROUPS = ["Market", "Sector", "Style", "Country"]

    @staticmethod
    def calculate_total_active_risk(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        trading_days: int = 252,
    ) -> float:
        """
        Calculate total tracking error volatility (annualized).

        Args:
            portfolio_returns: Series of portfolio daily returns
            benchmark_returns: Series of benchmark daily returns
            trading_days: Trading days per year for annualization

        Returns:
            Annualized tracking error as percentage (e.g., 5.2 for 5.2%)
        """
        from app.services import StatisticsService

        te = StatisticsService.get_tracking_error(
            portfolio_returns, benchmark_returns, trading_days
        )

        import math

        if math.isnan(te):
            return 0.0

        # Convert to percentage
        return te * 100

    @staticmethod
    def calculate_ex_ante_beta(
        tickers: List[str],
        weights: Dict[str, float],
    ) -> float:
        """
        Calculate portfolio ex-ante beta using individual ticker betas.

        Ex-ante beta = sum(weight_i * beta_i)

        Args:
            tickers: List of ticker symbols
            weights: Dict mapping ticker to portfolio weight (decimal)

        Returns:
            Portfolio beta (weighted average of individual betas)
        """
        total_beta = 0.0
        total_weight = 0.0

        for ticker in tickers:
            weight = weights.get(ticker.upper(), 0.0)
            if weight is None or weight <= 0:
                continue

            beta = TickerMetadataService.get_beta(ticker)
            if beta is not None:
                total_beta += weight * beta
                total_weight += weight

        if total_weight > 0:
            # Normalize if we don't have betas for all holdings
            return total_beta / total_weight if total_weight < 0.99 else total_beta

        return 1.0  # Default to market beta

    @staticmethod
    def calculate_ex_post_beta(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
    ) -> float:
        """
        Calculate portfolio ex-post beta from historical returns.

        Ex-post beta = cov(portfolio, benchmark) / var(benchmark)

        Args:
            portfolio_returns: Series of portfolio daily returns
            benchmark_returns: Series of benchmark daily returns

        Returns:
            Historical beta based on actual returns
        """
        import pandas as pd

        # Align the returns
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 10:
            return 1.0  # Default to market beta if insufficient data

        cov = aligned["portfolio"].cov(aligned["benchmark"])
        var = aligned["benchmark"].var()

        if var <= 0:
            return 1.0

        return cov / var

    @staticmethod
    def get_summary_metrics(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        tickers: List[str],
        weights: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Calculate all summary panel metrics using simple method.

        This is a fallback when factor model hasn't been run yet.

        Args:
            portfolio_returns: Series of portfolio returns
            benchmark_returns: Series of benchmark returns
            tickers: List of ticker symbols
            weights: Dict mapping ticker to weight

        Returns:
            Dict with all summary metrics
        """
        # Total active risk
        total_active_risk = RiskAnalyticsService.calculate_total_active_risk(
            portfolio_returns, benchmark_returns
        )

        # Ex-ante beta (from individual ticker betas)
        ex_ante_beta = RiskAnalyticsService.calculate_ex_ante_beta(tickers, weights)

        # Ex-post beta (from historical returns)
        ex_post_beta = RiskAnalyticsService.calculate_ex_post_beta(
            portfolio_returns, benchmark_returns
        )

        # Default factor/idio split (will be updated by factor model)
        factor_risk_pct = 50.0
        idio_risk_pct = 50.0

        return {
            "total_active_risk": round(total_active_risk, 2),
            "factor_risk_pct": round(factor_risk_pct, 1),
            "idio_risk_pct": round(idio_risk_pct, 1),
            "ex_ante_beta": round(ex_ante_beta, 2),
            "ex_post_beta": round(ex_post_beta, 2),
        }

    @staticmethod
    def get_full_analysis(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        ticker_returns: "pd.DataFrame",
        tickers: List[str],
        weights: Dict[str, float],
        benchmark_weights: Optional[Dict[str, float]] = None,
        ticker_price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
    ) -> Dict[str, Any]:
        """
        Run complete risk analysis using factor model.

        Args:
            portfolio_returns: Series of portfolio returns
            benchmark_returns: Series of benchmark returns
            ticker_returns: DataFrame with individual ticker returns
            tickers: List of ticker symbols
            weights: Dict mapping ticker to portfolio weight (decimal)
            benchmark_weights: Dict mapping ticker to benchmark weight (decimal)
            ticker_price_data: Dict mapping ticker to price DataFrame (for constructed factors)

        Returns:
            Dict with all analysis results
        """
        import numpy as np
        import pandas as pd

        from .fama_french_data_service import FamaFrenchDataService
        from .factor_model_service import FactorModelService
        from .factor_risk_service import FactorRiskService

        benchmark_weights = benchmark_weights or {}

        # Get date range from returns
        start_date = ticker_returns.index.min().strftime("%Y-%m-%d")
        end_date = ticker_returns.index.max().strftime("%Y-%m-%d")

        print(f"[RiskAnalytics] Running factor model analysis for {len(tickers)} tickers")
        print(f"[RiskAnalytics] Date range: {start_date} to {end_date}")

        # Step 1: Fetch Fama-French factors
        try:
            ff_factors = FamaFrenchDataService.get_factor_returns(start_date, end_date)
            rf_rate = FamaFrenchDataService.get_risk_free_rate(start_date, end_date)
            print(f"[RiskAnalytics] Loaded {len(ff_factors)} days of Fama-French data")
        except Exception as e:
            print(f"[RiskAnalytics] Error loading Fama-French data: {e}")
            # Fall back to simple analysis
            return RiskAnalyticsService._get_fallback_analysis(
                portfolio_returns, benchmark_returns, ticker_returns,
                tickers, weights, benchmark_weights
            )

        # Step 2: Calculate excess returns (R - RF)
        # Normalize ticker_returns index to match FF data (timezone-naive dates)
        ticker_returns_clean = ticker_returns.copy()
        ticker_returns_clean.index = pd.to_datetime(ticker_returns_clean.index).normalize()

        # Normalize FF factors index too
        ff_factors.index = pd.to_datetime(ff_factors.index).normalize()
        rf_rate.index = pd.to_datetime(rf_rate.index).normalize()

        # Align risk-free rate with ticker returns
        rf_aligned = rf_rate.reindex(ticker_returns_clean.index).ffill().fillna(0)
        ticker_excess_returns = ticker_returns_clean.sub(rf_aligned, axis=0)

        print(f"[RiskAnalytics] Ticker returns shape: {ticker_excess_returns.shape}")
        print(f"[RiskAnalytics] FF factors shape: {ff_factors.shape}")
        print(f"[RiskAnalytics] Date overlap: {len(ticker_excess_returns.index.intersection(ff_factors.index))} days")

        # Step 3: Get metadata for all tickers
        all_tickers = list(set(tickers) | set(benchmark_weights.keys()))
        metadata = TickerMetadataService.get_metadata_batch(all_tickers)

        # Step 4: Run factor regressions (simplified model - FF5+Momentum only)
        # Note: use_cache=False because CTEV calculations need actual residuals
        # which aren't stored in the cache
        print("[RiskAnalytics] Running factor regressions...")
        regression_results = FactorModelService.run_portfolio_regressions(
            ticker_excess_returns,
            ff_factors,
            metadata,
            max_workers=10,
            use_cache=False,
        )
        print(f"[RiskAnalytics] Completed {len(regression_results)} regressions")

        # Step 6: Calculate risk metrics
        if len(regression_results) > 0:
            # Calculate summary using factor model
            summary = FactorRiskService.calculate_risk_summary(
                regression_results,
                weights,
                benchmark_weights,
                portfolio_returns,
                benchmark_returns,
            )

            # Calculate CTEV by factor group
            ctev_by_factor = FactorRiskService.calculate_factor_ctev_by_group(
                regression_results,
                weights,
                benchmark_weights,
                summary["total_active_risk"],
            )

            # Calculate per-factor contributions with top securities
            factor_contributions = FactorRiskService.calculate_factor_contributions(
                regression_results,
                weights,
                benchmark_weights,
                summary["total_active_risk"],
            )

            # Calculate per-security risks
            security_risks = FactorRiskService.calculate_all_security_risks(
                regression_results,
                weights,
                benchmark_weights,
            )
        else:
            # Fall back if no regressions succeeded
            return RiskAnalyticsService._get_fallback_analysis(
                portfolio_returns, benchmark_returns, ticker_returns,
                tickers, weights, benchmark_weights
            )

        # Step 7: Calculate CTEV by sector
        ctev_by_sector = RiskAnalyticsService._calculate_ctev_by_sector(security_risks)

        # Step 8: Get top securities by CTEV
        top_securities = dict(
            sorted(
                security_risks.items(),
                key=lambda x: abs(x[1].get("idio_ctev", 0)),
                reverse=True,
            )[:15]
        )

        # Step 9: Validate risk decomposition
        warnings = FactorRiskService.validate_risk_decomposition(
            security_risks, summary, ctev_by_factor
        )
        if warnings:
            for warning in warnings:
                print(f"[RiskAnalytics] Validation warning: {warning}")

        return {
            "summary": summary,
            "factor_exposures": {},  # Not needed with new model
            "ctev_by_factor": ctev_by_factor,
            "ctev_by_sector": ctev_by_sector,
            "security_risks": security_risks,
            "top_securities": top_securities,
            "regression_results": regression_results,  # Include for debugging
            "factor_contributions": factor_contributions,  # Per-factor breakdown with top securities
        }

    @staticmethod
    def _calculate_ctev_by_sector(
        security_risks: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """
        Calculate CTEV by sector classification.

        Args:
            security_risks: Output from calculate_all_security_risks

        Returns:
            Dict mapping sector to total CTEV contribution
        """
        sector_ctev: Dict[str, float] = {}

        for ticker, risks in security_risks.items():
            sector = SectorOverrideService.get_effective_sector(ticker)
            ctev = risks.get("idio_ctev", 0.0)
            sector_ctev[sector] = sector_ctev.get(sector, 0.0) + ctev

        # Sort by CTEV descending
        return dict(sorted(sector_ctev.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def _get_fallback_analysis(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        ticker_returns: "pd.DataFrame",
        tickers: List[str],
        weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Fallback analysis when factor model fails.

        Uses simpler heuristic-based calculations.
        """
        import numpy as np
        import pandas as pd

        print("[RiskAnalytics] Using fallback heuristic analysis")

        # Summary metrics
        summary = RiskAnalyticsService.get_summary_metrics(
            portfolio_returns, benchmark_returns, tickers, weights
        )

        # Simple CTEV by factor (heuristic)
        total_active_risk = summary["total_active_risk"]
        ctev_by_factor = {
            "Market": round(total_active_risk * 0.35, 2),
            "Sector": round(total_active_risk * 0.25, 2),
            "Style": round(total_active_risk * 0.25, 2),
            "Country": round(total_active_risk * 0.15, 2),
        }

        # Security-level risks (simplified)
        security_risks: Dict[str, Dict[str, float]] = {}
        benchmark_weights = benchmark_weights or {}

        # Align returns
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 10:
            return {
                "summary": summary,
                "factor_exposures": {},
                "ctev_by_factor": ctev_by_factor,
                "ctev_by_sector": {},
                "security_risks": {},
                "top_securities": {},
            }

        active_returns = aligned["portfolio"] - aligned["benchmark"]
        active_var = active_returns.var()
        total_te = float(active_returns.std() * np.sqrt(252) * 100)

        for ticker in ticker_returns.columns:
            ticker_upper = ticker.upper()
            port_weight = weights.get(ticker_upper, 0.0)
            bench_weight = benchmark_weights.get(ticker_upper, 0.0)

            if (port_weight is None or port_weight <= 0) and bench_weight <= 0:
                continue

            port_weight = port_weight if port_weight else 0.0
            active_weight = port_weight - bench_weight

            # Align ticker returns
            ticker_ret = ticker_returns[ticker]
            combined = pd.concat(
                [ticker_ret, aligned["benchmark"], active_returns],
                axis=1,
                keys=["ticker", "benchmark", "active"],
            ).dropna()

            if len(combined) < 10:
                continue

            ticker_active = combined["ticker"] - combined["benchmark"]
            ticker_vol = float(ticker_active.std() * np.sqrt(252) * 100)

            # Estimate idiosyncratic portion (rough)
            idio_vol = ticker_vol * 0.5

            # CTEV contribution
            if active_var > 0:
                cov_with_active = ticker_active.cov(combined["active"])
                ctev = abs(active_weight) * (cov_with_active / active_var) * total_te
            else:
                ctev = 0.0

            security_risks[ticker_upper] = {
                "portfolio_weight": round(port_weight * 100, 2),
                "benchmark_weight": round(bench_weight * 100, 2),
                "active_weight": round(active_weight * 100, 2),
                "idio_vol": round(idio_vol, 2),
                "idio_tev": round(idio_vol, 2),
                "idio_ctev": round(abs(ctev) * 0.5, 2),
            }

        # CTEV by sector
        ctev_by_sector = RiskAnalyticsService._calculate_ctev_by_sector(security_risks)

        # Top securities
        top_securities = dict(
            sorted(
                security_risks.items(),
                key=lambda x: abs(x[1].get("idio_ctev", 0)),
                reverse=True,
            )[:15]
        )

        return {
            "summary": summary,
            "factor_exposures": {},
            "ctev_by_factor": ctev_by_factor,
            "ctev_by_sector": ctev_by_sector,
            "security_risks": security_risks,
            "top_securities": top_securities,
        }
