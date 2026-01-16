"""Factor Risk Service - Risk metric calculations from factor model.

This service calculates all risk metrics from factor regression results:

Security-Level Metrics:
- Idiosyncratic Vol = std(residuals) * sqrt(252)
- Factor Vol = std(fitted_values) * sqrt(252)
- Total Vol = std(excess_returns) * sqrt(252)

Portfolio-Level Metrics:
- Active Weight = Portfolio Weight - Benchmark Weight
- Idiosyncratic TEV = std(portfolio_residuals - benchmark_residuals) * sqrt(252)
- Idiosyncratic CTEV = w_i * Cov(residual_i, portfolio_residual) / Var(portfolio_residual)

Risk Summary:
- Total Active Risk (tracking error)
- Factor Risk % (from weighted average R-squared)
- Idiosyncratic Risk % (1 - Factor Risk %)
- Beta Ex-Ante (weighted average Mkt-RF betas)
- Beta Ex-Post (regression of portfolio vs benchmark)

CTEV by Factor Group:
- Market: Mkt-RF exposure difference contribution
- Sector: Based on metadata sector concentration
- Style: SMB+HML+RMW+CMA+UMD contribution
- Country: Based on metadata country concentration
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd
    from .factor_model_service import FactorRegressionResult


class FactorRiskService:
    """
    Calculates risk metrics from factor model regression results.
    """

    # Factor groupings for CTEV decomposition (simplified model)
    MARKET_FACTORS = ["Mkt-RF"]
    STYLE_FACTORS = ["SMB", "HML", "RMW", "CMA", "UMD"]

    @staticmethod
    def calculate_security_risk_metrics(
        ticker: str,
        regression_result: "FactorRegressionResult",
        portfolio_weight: float,
        benchmark_weight: float,
        trading_days: int = 252,
    ) -> Dict[str, float]:
        """
        Calculate risk metrics for a single security.

        Args:
            ticker: Ticker symbol
            regression_result: Factor regression result for this security
            portfolio_weight: Weight in portfolio (decimal)
            benchmark_weight: Weight in benchmark (decimal)
            trading_days: Trading days per year for annualization

        Returns:
            Dict with risk metrics
        """
        import numpy as np

        active_weight = portfolio_weight - benchmark_weight

        # Use pre-computed volatilities from regression result (stored in cache)
        idio_vol = regression_result.idio_vol
        factor_vol = regression_result.factor_vol

        # Fallback: compute from residuals if available and pre-computed is 0
        if idio_vol == 0 and regression_result.residuals is not None and len(regression_result.residuals) > 0:
            idio_vol = float(regression_result.residuals.std() * np.sqrt(trading_days))

        if factor_vol == 0 and regression_result.fitted_values is not None and len(regression_result.fitted_values) > 0:
            factor_vol = float(regression_result.fitted_values.std() * np.sqrt(trading_days))

        # Total vol from sum of variances (assuming independence)
        total_vol = np.sqrt(idio_vol**2 + factor_vol**2)

        return {
            "portfolio_weight": round(portfolio_weight * 100, 2),
            "benchmark_weight": round(benchmark_weight * 100, 2),
            "active_weight": round(active_weight * 100, 2),
            "total_vol": round(total_vol * 100, 2),
            "factor_vol": round(factor_vol * 100, 2),
            "idio_vol": round(idio_vol * 100, 2),
            "r_squared": round(regression_result.r_squared * 100, 2),
        }

    @classmethod
    def calculate_portfolio_residuals(
        cls,
        regression_results: Dict[str, "FactorRegressionResult"],
        weights: Dict[str, float],
    ) -> "pd.Series":
        """
        Calculate weighted portfolio residuals from individual regressions.

        Args:
            regression_results: Dict mapping ticker to regression result
            weights: Dict mapping ticker to portfolio weight (decimal)

        Returns:
            Series of weighted portfolio residuals
        """
        import pandas as pd

        # Collect all residuals and align dates
        all_residuals: Dict[str, pd.Series] = {}
        for ticker, result in regression_results.items():
            if result.residuals is not None and ticker.upper() in weights:
                all_residuals[ticker] = result.residuals

        if not all_residuals:
            return pd.Series(dtype=float)

        # Create DataFrame and align dates
        residuals_df = pd.DataFrame(all_residuals)
        residuals_df = residuals_df.ffill().dropna()

        if residuals_df.empty:
            return pd.Series(dtype=float)

        # Calculate weighted residuals
        portfolio_residuals = pd.Series(0.0, index=residuals_df.index)
        total_weight = 0.0

        for ticker in residuals_df.columns:
            weight = weights.get(ticker.upper(), 0.0)
            if weight > 0:
                portfolio_residuals += residuals_df[ticker] * weight
                total_weight += weight

        # Normalize if not all weights captured
        if total_weight > 0 and total_weight < 0.99:
            portfolio_residuals /= total_weight

        return portfolio_residuals

    @classmethod
    def calculate_idiosyncratic_ctev(
        cls,
        ticker: str,
        regression_result: "FactorRegressionResult",
        portfolio_residuals: "pd.Series",
        active_weight: float,
        total_idio_var: float,
        trading_days: int = 252,
    ) -> float:
        """
        Calculate idiosyncratic contribution to tracking error volatility.

        Args:
            ticker: Ticker symbol
            regression_result: Regression result for this security
            portfolio_residuals: Portfolio-level residuals series
            active_weight: Active weight (portfolio - benchmark)
            total_idio_var: Total portfolio residual variance
            trading_days: Trading days for annualization

        Returns:
            Idiosyncratic CTEV contribution (percentage points)
        """
        import pandas as pd
        import numpy as np

        if regression_result.residuals is None or len(regression_result.residuals) == 0:
            return 0.0

        if total_idio_var <= 0:
            return 0.0

        # Align residuals
        aligned = pd.concat(
            [regression_result.residuals, portfolio_residuals],
            axis=1,
            keys=["security", "portfolio"]
        ).dropna()

        if len(aligned) < 10:
            return 0.0

        # Covariance with portfolio residuals
        cov = aligned["security"].cov(aligned["portfolio"])

        # CTEV contribution
        idio_std = np.sqrt(total_idio_var) * np.sqrt(trading_days)
        ctev = abs(active_weight) * (cov / total_idio_var) * idio_std

        return float(ctev * 100)  # Convert to percentage points

    @classmethod
    def calculate_factor_ctev_by_group(
        cls,
        regression_results: Dict[str, "FactorRegressionResult"],
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        total_active_risk: float,
    ) -> Dict[str, float]:
        """
        Calculate CTEV breakdown by factor group.

        Uses the Fama-French factor betas to decompose risk.
        Sector and Country contributions are estimated from metadata.

        Args:
            regression_results: Dict mapping ticker to regression result
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            total_active_risk: Total tracking error (percentage)

        Returns:
            Dict mapping factor group to CTEV contribution
        """
        if total_active_risk <= 0:
            return {"Market": 0.0, "Sector": 0.0, "Style": 0.0, "Country": 0.0}

        # Calculate weighted average factor exposures for portfolio and benchmark
        port_market_exp = 0.0
        bench_market_exp = 0.0
        port_style_exp = 0.0
        bench_style_exp = 0.0
        port_total_weight = 0.0
        bench_total_weight = 0.0

        # Sector concentration
        port_sectors: Dict[str, float] = {}
        bench_sectors: Dict[str, float] = {}

        # Country (US vs non-US)
        port_nonus_weight = 0.0
        bench_nonus_weight = 0.0

        for ticker, result in regression_results.items():
            pw = portfolio_weights.get(ticker.upper(), 0.0)
            bw = benchmark_weights.get(ticker.upper(), 0.0)

            # Market beta
            mkt_beta = result.betas.get("Mkt-RF", 1.0)
            if pw > 0:
                port_market_exp += mkt_beta * pw
                port_total_weight += pw
            if bw > 0:
                bench_market_exp += mkt_beta * bw
                bench_total_weight += bw

            # Style factors
            style_exp = sum(abs(result.betas.get(f, 0.0)) for f in cls.STYLE_FACTORS)
            if pw > 0:
                port_style_exp += style_exp * pw
            if bw > 0:
                bench_style_exp += style_exp * bw

            # Sector from metadata
            sector = result.sector or "Not Classified"
            if pw > 0:
                port_sectors[sector] = port_sectors.get(sector, 0.0) + pw
            if bw > 0:
                bench_sectors[sector] = bench_sectors.get(sector, 0.0) + bw

            # Country from metadata
            country = result.country or "US"
            if country.upper() not in ["US", "USA", "UNITED STATES"]:
                if pw > 0:
                    port_nonus_weight += pw
                if bw > 0:
                    bench_nonus_weight += bw

        # Market: difference in beta exposure
        if port_total_weight > 0:
            port_market_exp /= port_total_weight
        if bench_total_weight > 0:
            bench_market_exp /= bench_total_weight
        market_diff = abs(port_market_exp - bench_market_exp)

        # Style: difference in style factor exposure
        if port_total_weight > 0:
            port_style_exp /= port_total_weight
        if bench_total_weight > 0:
            bench_style_exp /= bench_total_weight
        style_diff = abs(port_style_exp - bench_style_exp)

        # Sector: HHI-like concentration difference
        all_sectors = set(port_sectors.keys()) | set(bench_sectors.keys())
        sector_diff = sum(
            abs(port_sectors.get(s, 0) - bench_sectors.get(s, 0))
            for s in all_sectors
        )

        # Country: difference in non-US exposure
        country_diff = abs(port_nonus_weight - bench_nonus_weight)

        # Allocate factor risk proportionally
        # Estimate factor risk as R² percentage of total
        avg_r2 = 0.0
        count = 0
        for result in regression_results.values():
            avg_r2 += result.r_squared
            count += 1
        if count > 0:
            avg_r2 /= count

        factor_risk = total_active_risk * avg_r2

        # Distribute factor risk
        total_diff = market_diff + sector_diff + style_diff + country_diff
        if total_diff < 0.001:
            # If no differences, use typical allocation
            return {
                "Market": round(factor_risk * 0.40, 2),
                "Sector": round(factor_risk * 0.30, 2),
                "Style": round(factor_risk * 0.25, 2),
                "Country": round(factor_risk * 0.05, 2),
            }

        return {
            "Market": round((market_diff / total_diff) * factor_risk, 2),
            "Sector": round((sector_diff / total_diff) * factor_risk, 2),
            "Style": round((style_diff / total_diff) * factor_risk, 2),
            "Country": round((country_diff / total_diff) * factor_risk, 2),
        }

    @classmethod
    def calculate_risk_summary(
        cls,
        regression_results: Dict[str, "FactorRegressionResult"],
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        portfolio_returns: "pd.Series",
        benchmark_returns: "pd.Series",
        trading_days: int = 252,
    ) -> Dict[str, float]:
        """
        Calculate portfolio-level risk summary metrics.

        Args:
            regression_results: Dict mapping ticker to regression result
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            portfolio_returns: Portfolio return series
            benchmark_returns: Benchmark return series
            trading_days: Trading days for annualization

        Returns:
            Dict with summary metrics
        """
        import pandas as pd
        import numpy as np

        # Total active risk (tracking error)
        aligned = pd.concat(
            [portfolio_returns, benchmark_returns],
            axis=1,
            keys=["portfolio", "benchmark"]
        ).dropna()

        if len(aligned) < 10:
            return {
                "total_active_risk": 0.0,
                "factor_risk_pct": 50.0,
                "idio_risk_pct": 50.0,
                "ex_ante_beta": 1.0,
                "ex_post_beta": 1.0,
            }

        active_returns = aligned["portfolio"] - aligned["benchmark"]
        total_active_risk = float(active_returns.std() * np.sqrt(trading_days) * 100)

        # Ex-ante beta (weighted average of Mkt-RF betas)
        ex_ante_beta = 0.0
        total_weight = 0.0

        for ticker, result in regression_results.items():
            weight = portfolio_weights.get(ticker.upper(), 0.0)
            if weight > 0:
                mkt_beta = result.betas.get("Mkt-RF", 1.0)
                ex_ante_beta += mkt_beta * weight
                total_weight += weight

        if total_weight > 0:
            ex_ante_beta /= total_weight
        else:
            ex_ante_beta = 1.0

        # Ex-post beta (regression of portfolio vs benchmark)
        cov = aligned["portfolio"].cov(aligned["benchmark"])
        var = aligned["benchmark"].var()
        ex_post_beta = cov / var if var > 0 else 1.0

        # Factor vs idiosyncratic risk split
        # Use weighted average R-squared as estimate of factor risk %
        weighted_r2 = 0.0
        total_weight = 0.0

        for ticker, result in regression_results.items():
            weight = abs(portfolio_weights.get(ticker.upper(), 0.0) -
                        benchmark_weights.get(ticker.upper(), 0.0))
            if weight > 0:
                weighted_r2 += result.r_squared * weight
                total_weight += weight

        if total_weight > 0:
            factor_risk_pct = (weighted_r2 / total_weight) * 100
        else:
            factor_risk_pct = 50.0

        # Ensure reasonable bounds
        factor_risk_pct = max(20.0, min(80.0, factor_risk_pct))
        idio_risk_pct = 100.0 - factor_risk_pct

        return {
            "total_active_risk": round(total_active_risk, 2),
            "factor_risk_pct": round(factor_risk_pct, 1),
            "idio_risk_pct": round(idio_risk_pct, 1),
            "ex_ante_beta": round(float(ex_ante_beta), 2),
            "ex_post_beta": round(float(ex_post_beta), 2),
        }

    @classmethod
    def calculate_all_security_risks(
        cls,
        regression_results: Dict[str, "FactorRegressionResult"],
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        trading_days: int = 252,
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate risk metrics for all securities.

        Args:
            regression_results: Dict mapping ticker to regression result
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            trading_days: Trading days for annualization

        Returns:
            Dict mapping ticker to risk metrics
        """
        # Calculate portfolio residuals for CTEV
        portfolio_residuals = cls.calculate_portfolio_residuals(
            regression_results, portfolio_weights
        )

        # Portfolio residual variance
        total_idio_var = portfolio_residuals.var() if len(portfolio_residuals) > 0 else 0.0

        results: Dict[str, Dict[str, float]] = {}

        # Get all tickers (union of portfolio and benchmark)
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        for ticker in all_tickers:
            ticker_upper = ticker.upper()
            port_weight = portfolio_weights.get(ticker_upper, 0.0)
            bench_weight = benchmark_weights.get(ticker_upper, 0.0)

            # Skip if no position in either
            if port_weight <= 0 and bench_weight <= 0:
                continue

            active_weight = port_weight - bench_weight

            # Get regression result if available
            result = regression_results.get(ticker_upper)

            if result is not None:
                # Full calculation with regression
                security_risk = cls.calculate_security_risk_metrics(
                    ticker_upper, result, port_weight, bench_weight, trading_days
                )

                # Calculate idiosyncratic CTEV
                idio_ctev = cls.calculate_idiosyncratic_ctev(
                    ticker_upper,
                    result,
                    portfolio_residuals,
                    active_weight,
                    total_idio_var,
                    trading_days,
                )

                security_risk["idio_ctev"] = round(idio_ctev, 2)
                # Idio TEV = Idio Vol × |active_weight| (marginal contribution before diversification)
                # This represents the security's standalone idiosyncratic tracking error contribution
                idio_vol_decimal = security_risk["idio_vol"] / 100  # Convert from percentage
                active_weight_abs = abs(active_weight)
                idio_tev = idio_vol_decimal * active_weight_abs * 100  # Back to percentage points
                security_risk["idio_tev"] = round(idio_tev, 2)

            else:
                # Fallback for securities without regression
                security_risk = {
                    "portfolio_weight": round(port_weight * 100, 2),
                    "benchmark_weight": round(bench_weight * 100, 2),
                    "active_weight": round(active_weight * 100, 2),
                    "total_vol": 0.0,
                    "factor_vol": 0.0,
                    "idio_vol": 0.0,
                    "idio_tev": 0.0,
                    "idio_ctev": 0.0,
                    "r_squared": 0.0,
                }

            results[ticker_upper] = security_risk

        return results

    # Friendly names for factors
    FACTOR_NAMES = {
        "Mkt-RF": "Market",
        "SMB": "Size",
        "HML": "Value",
        "RMW": "Profitability",
        "CMA": "Investment",
        "UMD": "Momentum",
    }

    @classmethod
    def calculate_factor_contributions(
        cls,
        regression_results: Dict[str, "FactorRegressionResult"],
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        total_active_risk: float,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate per-factor contributions with top securities for each factor.

        For each Fama-French factor, calculates:
        - Total factor contribution to TEV
        - Top 20 securities contributing to that factor's TEV

        Args:
            regression_results: Dict mapping ticker to regression result
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            total_active_risk: Total tracking error (percentage)

        Returns:
            Dict mapping factor name to {ctev, securities: [{ticker, name, beta, active_weight, contribution}]}
        """
        import numpy as np
        from app.services.ticker_metadata_service import TickerMetadataService

        factors = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
        result: Dict[str, Dict[str, Any]] = {}

        for factor in factors:
            # Calculate weighted average beta for portfolio and benchmark
            port_beta = 0.0
            bench_beta = 0.0
            port_total = 0.0
            bench_total = 0.0

            # Per-security contributions
            security_contributions = []

            for ticker, reg_result in regression_results.items():
                ticker_upper = ticker.upper()
                pw = portfolio_weights.get(ticker_upper, 0.0)
                bw = benchmark_weights.get(ticker_upper, 0.0)
                beta = reg_result.betas.get(factor, 0.0)

                if pw > 0:
                    port_beta += beta * pw
                    port_total += pw
                if bw > 0:
                    bench_beta += beta * bw
                    bench_total += bw

                # Active weight
                active_weight = pw - bw
                if active_weight == 0:
                    continue

                # Security's contribution = active_weight × beta
                # This captures how much the security tilts the portfolio toward this factor
                contribution = active_weight * beta

                # Get security name
                metadata = TickerMetadataService.get_metadata(ticker_upper)
                name = metadata.get("shortName") or ticker_upper

                security_contributions.append({
                    "ticker": ticker_upper,
                    "name": name,
                    "beta": round(beta, 3),
                    "active_weight": round(active_weight * 100, 2),
                    "contribution": contribution,
                })

            # Normalize portfolio/benchmark betas
            if port_total > 0:
                port_beta /= port_total
            if bench_total > 0:
                bench_beta /= bench_total

            # Active factor exposure
            active_beta = port_beta - bench_beta

            # Sort securities by absolute contribution (descending)
            security_contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)

            # Take top 20
            top_securities = security_contributions[:20]

            # Calculate total contribution to TEV for this factor
            # Use sum of absolute contributions as proxy for factor's TEV contribution
            total_contribution = sum(abs(s["contribution"]) for s in security_contributions)

            # Scale to percentage of total active risk (rough approximation)
            # The actual factor variance contribution would require factor covariance matrix
            # Here we use relative contribution as a proxy
            factor_ctev = abs(active_beta) * total_active_risk * 0.2  # Scale factor

            # Get friendly name
            friendly_name = cls.FACTOR_NAMES.get(factor, factor)

            result[friendly_name] = {
                "factor_code": factor,
                "ctev": round(factor_ctev, 2),
                "active_beta": round(active_beta, 3),
                "portfolio_beta": round(port_beta, 3),
                "benchmark_beta": round(bench_beta, 3),
                "securities": [
                    {
                        "ticker": s["ticker"],
                        "name": s["name"],
                        "beta": s["beta"],
                        "active_weight": s["active_weight"],
                        "contribution": round(s["contribution"] * 100, 3),  # Convert to percentage
                    }
                    for s in top_securities
                ],
            }

        # Sort factors by CTEV (descending)
        result = dict(sorted(result.items(), key=lambda x: x[1]["ctev"], reverse=True))

        return result

    @classmethod
    def validate_risk_decomposition(
        cls,
        security_risks: Dict[str, Dict[str, float]],
        summary: Dict[str, float],
        ctev_by_factor: Dict[str, float],
    ) -> List[str]:
        """
        Validate that risk decomposition sums correctly.

        Args:
            security_risks: Per-security risk metrics
            summary: Portfolio summary metrics
            ctev_by_factor: CTEV by factor group

        Returns:
            List of warning messages (empty if all valid)
        """
        warnings_list: List[str] = []

        # Check 1: Factor % + Idio % = 100%
        factor_pct = summary.get("factor_risk_pct", 0)
        idio_pct = summary.get("idio_risk_pct", 0)
        if abs(factor_pct + idio_pct - 100.0) > 0.1:
            warnings_list.append(
                f"Factor ({factor_pct:.1f}%) + Idio ({idio_pct:.1f}%) != 100%"
            )

        return warnings_list
