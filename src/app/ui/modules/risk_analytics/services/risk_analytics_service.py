"""Risk Analytics Service - Core risk calculation engine.

Implements a simplified factor model for risk decomposition:
- Total Active Risk = Tracking Error (annualized std of return differences)
- Factor Risk = Risk explained by factor exposures (beta, sector, style, currency)
- Idiosyncratic Risk = sqrt(Total^2 - Factor^2)
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

    Provides methods for:
    - Total active risk (tracking error volatility)
    - Factor risk decomposition (Market, Sector, Style, Currency)
    - Idiosyncratic risk calculation
    - CTEV (Contribution to Tracking Error Volatility) by security/sector/factor
    """

    FACTOR_GROUPS = ["Market", "Sector", "Style", "Currency"]

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
    def calculate_factor_exposures(
        tickers: List[str],
        weights: Dict[str, float],
        benchmark_beta: float = 1.0,
    ) -> Dict[str, float]:
        """
        Calculate portfolio's active exposure to each factor group.

        Args:
            tickers: List of ticker symbols
            weights: Dict mapping ticker to portfolio weight (decimal)
            benchmark_beta: Benchmark beta (typically 1.0 for market index)

        Returns:
            Dict with active exposures: {"Market": 0.15, "Sector": 0.08, ...}
        """
        import math

        exposures: Dict[str, float] = {}

        # Market exposure = portfolio beta - benchmark beta
        portfolio_beta = RiskAnalyticsService.calculate_ex_ante_beta(tickers, weights)
        exposures["Market"] = abs(portfolio_beta - benchmark_beta)

        # Sector exposure = concentration deviation from benchmark
        # Simplified: measure sector concentration (HHI-like)
        sector_weights: Dict[str, float] = {}
        for ticker in tickers:
            weight = weights.get(ticker.upper(), 0.0)
            if weight is None or weight <= 0:
                continue
            sector = SectorOverrideService.get_effective_sector(ticker)
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

        # Calculate sector concentration (deviation from equal-weight benchmark)
        n_sectors = max(len(sector_weights), 1)
        equal_weight = 1.0 / n_sectors if n_sectors > 0 else 0.0
        sector_deviation = sum(
            abs(w - equal_weight) for w in sector_weights.values()
        ) / max(n_sectors, 1)
        exposures["Sector"] = sector_deviation

        # Style exposure = weighted average of style factor tilts
        style_exposure = RiskAnalyticsService._calculate_style_exposure(tickers, weights)
        exposures["Style"] = style_exposure

        # Currency exposure = non-USD weight
        currency_exposure = 0.0
        for ticker in tickers:
            weight = weights.get(ticker.upper(), 0.0)
            if weight is None or weight <= 0:
                continue
            currency = TickerMetadataService.get_currency(ticker)
            if currency != "USD":
                currency_exposure += weight
        exposures["Currency"] = currency_exposure

        return exposures

    @staticmethod
    def _calculate_style_exposure(
        tickers: List[str],
        weights: Dict[str, float],
    ) -> float:
        """
        Calculate aggregate style factor exposure.

        Considers: Size, Value, Momentum, Growth, Quality
        """
        import math

        style_scores: List[float] = []

        for ticker in tickers:
            weight = weights.get(ticker.upper(), 0.0)
            if weight is None or weight <= 0:
                continue

            factors = TickerMetadataService.get_style_factors(ticker)

            # Size factor: log(marketCap) deviation from median
            market_cap = TickerMetadataService.get_market_cap(ticker)
            if market_cap and market_cap > 0:
                # Large cap = low size factor, small cap = high size factor
                log_cap = math.log10(market_cap)
                # Normalize: 9 = ~$1B (small), 12 = ~$1T (mega)
                size_score = (12 - log_cap) / 3  # Higher for smaller caps
                style_scores.append(abs(size_score) * weight)

            # Value factor: inverse PE
            pe = factors.get("trailingPE")
            if pe and pe > 0:
                value_score = min(30 / pe, 2.0)  # Higher for lower PE
                style_scores.append(abs(value_score - 1.0) * weight * 0.3)

            # Momentum factor: 52-week change
            momentum = factors.get("fiftyTwoWeekChange")
            if momentum is not None:
                style_scores.append(abs(momentum) * weight * 0.5)

        return sum(style_scores) / max(len(tickers), 1) if style_scores else 0.0

    @staticmethod
    def calculate_factor_risk(
        total_active_risk: float,
        factor_exposures: Dict[str, float],
    ) -> Tuple[float, float]:
        """
        Calculate factor risk and idiosyncratic risk.

        Uses a simplified model where factor risk is proportional to exposures.
        Typical active portfolios have 40-70% factor risk, 30-60% idiosyncratic.

        Args:
            total_active_risk: Total tracking error (percentage)
            factor_exposures: Dict with factor exposures

        Returns:
            Tuple of (factor_risk_pct, idio_risk_pct) as percentages of total
        """
        import math

        if total_active_risk <= 0:
            return 50.0, 50.0  # Default split

        # Calculate weighted exposure contribution
        # Scale each factor type appropriately
        market_exp = factor_exposures.get("Market", 0) * 3.0  # Market beta diff is important
        sector_exp = factor_exposures.get("Sector", 0) * 2.0  # Sector concentration matters
        style_exp = factor_exposures.get("Style", 0) * 1.5    # Style tilts
        currency_exp = factor_exposures.get("Currency", 0) * 1.0  # FX exposure

        # Combined factor score (0-1 range typically)
        factor_score = market_exp + sector_exp + style_exp + currency_exp

        # Base factor risk proportion (even low-exposure portfolios have some factor risk)
        # Most actively managed portfolios have 40-70% factor risk
        base_factor_pct = 35.0
        variable_factor_pct = min(factor_score * 50, 50.0)  # Up to 50% additional

        factor_risk_pct = min(base_factor_pct + variable_factor_pct, 95.0)
        idio_risk_pct = 100 - factor_risk_pct

        return round(factor_risk_pct, 1), round(idio_risk_pct, 1)

    @staticmethod
    def calculate_ctev_by_security(
        ticker_returns: "pd.DataFrame",
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        weights: Dict[str, float],
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate per-security risk metrics.

        CTEV_i = w_i * cov(R_i - R_b, R_p - R_b) / var(R_p - R_b) * TE

        Args:
            ticker_returns: DataFrame with ticker returns (columns = tickers)
            portfolio_returns: Series of portfolio returns
            benchmark_returns: Series of benchmark returns
            weights: Dict mapping ticker to weight

        Returns:
            Dict mapping ticker to risk metrics:
            {
                "AAPL": {
                    "net_weight": 5.2,
                    "factor_tev": 1.2,
                    "idio_tev": 0.8,
                    "idio_ctev": 0.15,
                },
                ...
            }
        """
        import numpy as np
        import pandas as pd

        result: Dict[str, Dict[str, float]] = {}

        # Calculate active returns
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"],
        ).dropna()

        if len(aligned) < 10:
            return result

        active_returns = aligned["portfolio"] - aligned["benchmark"]
        active_var = active_returns.var()

        if active_var <= 0:
            return result

        total_te = active_returns.std() * np.sqrt(252) * 100

        for ticker in ticker_returns.columns:
            ticker_upper = ticker.upper()
            weight = weights.get(ticker_upper, 0.0)

            if weight is None or weight <= 0:
                continue

            # Align ticker returns with active returns
            ticker_ret = ticker_returns[ticker]
            combined = pd.concat(
                [ticker_ret, aligned["benchmark"], active_returns],
                axis=1,
                keys=["ticker", "benchmark", "active"],
            ).dropna()

            if len(combined) < 10:
                continue

            ticker_active = combined["ticker"] - combined["benchmark"]

            # Calculate CTEV contribution
            cov_with_active = ticker_active.cov(combined["active"])
            ctev_contribution = (weight * cov_with_active / active_var) * total_te

            # Estimate factor vs idio split based on beta
            beta = TickerMetadataService.get_beta(ticker)
            if beta is None:
                beta = 1.0

            # Higher beta = more factor risk
            factor_proportion = min(abs(beta) / 2, 0.8)

            ticker_vol = ticker_active.std() * np.sqrt(252) * 100
            factor_tev = ticker_vol * factor_proportion
            idio_tev = ticker_vol * (1 - factor_proportion)

            result[ticker_upper] = {
                "net_weight": weight * 100,
                "factor_tev": round(factor_tev, 2),
                "idio_tev": round(idio_tev, 2),
                "idio_ctev": round(abs(ctev_contribution) * (1 - factor_proportion), 2),
            }

        return result

    @staticmethod
    def calculate_ctev_by_sector(
        security_risks: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """
        Calculate CTEV by sector classification.

        Args:
            security_risks: Output from calculate_ctev_by_security

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
    def calculate_ctev_by_factor_group(
        total_active_risk: float,
        factor_exposures: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Calculate CTEV by factor group.

        Args:
            total_active_risk: Total tracking error (percentage)
            factor_exposures: Dict with factor exposures

        Returns:
            Dict mapping factor group to CTEV contribution
        """
        if total_active_risk <= 0:
            return {f: 0.0 for f in RiskAnalyticsService.FACTOR_GROUPS}

        # Get factor risk proportion
        factor_risk_pct, _ = RiskAnalyticsService.calculate_factor_risk(
            total_active_risk, factor_exposures
        )
        factor_risk = total_active_risk * (factor_risk_pct / 100)

        # Scale exposures with same weights used in calculate_factor_risk
        scaled_exposures = {
            "Market": factor_exposures.get("Market", 0) * 3.0,
            "Sector": factor_exposures.get("Sector", 0) * 2.0,
            "Style": factor_exposures.get("Style", 0) * 1.5,
            "Currency": factor_exposures.get("Currency", 0) * 1.0,
        }

        # Add minimum exposure so we always show some factor contribution
        for factor in scaled_exposures:
            if scaled_exposures[factor] < 0.01:
                scaled_exposures[factor] = 0.01

        total_scaled = sum(scaled_exposures.values())
        if total_scaled <= 0:
            total_scaled = 1.0

        # Allocate factor risk proportionally to scaled exposures
        result: Dict[str, float] = {}
        for factor in RiskAnalyticsService.FACTOR_GROUPS:
            scaled_exp = scaled_exposures.get(factor, 0.01)
            result[factor] = round((scaled_exp / total_scaled) * factor_risk, 2)

        return result

    @staticmethod
    def get_summary_metrics(
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        tickers: List[str],
        weights: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Calculate all summary panel metrics.

        Args:
            portfolio_returns: Series of portfolio returns
            benchmark_returns: Series of benchmark returns
            tickers: List of ticker symbols
            weights: Dict mapping ticker to weight

        Returns:
            Dict with all summary metrics:
            {
                "total_active_risk": 5.2,
                "factor_risk_pct": 65.0,
                "idio_risk_pct": 35.0,
                "ex_ante_beta": 1.15,
                "ex_post_beta": 1.10,
            }
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

        # Factor exposures and risk decomposition
        factor_exposures = RiskAnalyticsService.calculate_factor_exposures(
            tickers, weights
        )
        factor_risk_pct, idio_risk_pct = RiskAnalyticsService.calculate_factor_risk(
            total_active_risk, factor_exposures
        )

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
    ) -> Dict[str, Any]:
        """
        Run complete risk analysis and return all results.

        Args:
            portfolio_returns: Series of portfolio returns
            benchmark_returns: Series of benchmark returns
            ticker_returns: DataFrame with individual ticker returns
            tickers: List of ticker symbols
            weights: Dict mapping ticker to weight

        Returns:
            Dict with all analysis results
        """
        # Summary metrics
        summary = RiskAnalyticsService.get_summary_metrics(
            portfolio_returns, benchmark_returns, tickers, weights
        )

        # Factor exposures
        factor_exposures = RiskAnalyticsService.calculate_factor_exposures(
            tickers, weights
        )

        # CTEV by factor group
        ctev_by_factor = RiskAnalyticsService.calculate_ctev_by_factor_group(
            summary["total_active_risk"], factor_exposures
        )

        # CTEV by security
        security_risks = RiskAnalyticsService.calculate_ctev_by_security(
            ticker_returns, portfolio_returns, benchmark_returns, weights
        )

        # CTEV by sector
        ctev_by_sector = RiskAnalyticsService.calculate_ctev_by_sector(security_risks)

        # Top securities by CTEV
        top_securities = dict(
            sorted(
                security_risks.items(),
                key=lambda x: x[1].get("idio_ctev", 0),
                reverse=True,
            )[:15]
        )

        return {
            "summary": summary,
            "factor_exposures": factor_exposures,
            "ctev_by_factor": ctev_by_factor,
            "ctev_by_sector": ctev_by_sector,
            "security_risks": security_risks,
            "top_securities": top_securities,
        }
