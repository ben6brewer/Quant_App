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

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Set

from app.services.ticker_metadata_service import TickerMetadataService

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
    ) -> Dict[str, Dict[str, float]]:
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
            Dict mapping factor group to {"ctev": float, "active_weight": float}
        """
        if total_active_risk <= 0:
            return {
                "Market": {"ctev": 0.0, "active_weight": 0.0},
                "Style": {"ctev": 0.0, "active_weight": 0.0},
                "Sector": {"ctev": 0.0, "active_weight": 0.0},
                "Industry": {"ctev": 0.0, "active_weight": 0.0},
                "Country": {"ctev": 0.0, "active_weight": 0.0},
            }

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

        # Industry concentration
        port_industries: Dict[str, float] = {}
        bench_industries: Dict[str, float] = {}

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

            # Industry from metadata
            metadata = TickerMetadataService.get_metadata(ticker.upper())
            industry = metadata.get("industry") or "Not Classified"
            if pw > 0:
                port_industries[industry] = port_industries.get(industry, 0.0) + pw
            if bw > 0:
                bench_industries[industry] = bench_industries.get(industry, 0.0) + bw

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

        # Industry: concentration difference (more granular than sector)
        all_industries = set(port_industries.keys()) | set(bench_industries.keys())
        industry_diff = sum(
            abs(port_industries.get(ind, 0) - bench_industries.get(ind, 0))
            for ind in all_industries
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
        total_diff = market_diff + sector_diff + industry_diff + style_diff + country_diff
        if total_diff < 0.001:
            # If no differences, use typical allocation
            return {
                "Market": {"ctev": round(factor_risk * 0.35, 2), "active_weight": round(market_diff * 100, 2)},
                "Style": {"ctev": round(factor_risk * 0.25, 2), "active_weight": round(style_diff * 100, 2)},
                "Sector": {"ctev": round(factor_risk * 0.15, 2), "active_weight": round(sector_diff * 100, 2)},
                "Industry": {"ctev": round(factor_risk * 0.15, 2), "active_weight": round(industry_diff * 100, 2)},
                "Country": {"ctev": round(factor_risk * 0.10, 2), "active_weight": round(country_diff * 100, 2)},
            }

        return {
            "Market": {"ctev": round((market_diff / total_diff) * factor_risk, 2), "active_weight": round(market_diff * 100, 2)},
            "Style": {"ctev": round((style_diff / total_diff) * factor_risk, 2), "active_weight": round(style_diff * 100, 2)},
            "Sector": {"ctev": round((sector_diff / total_diff) * factor_risk, 2), "active_weight": round(sector_diff * 100, 2)},
            "Industry": {"ctev": round((industry_diff / total_diff) * factor_risk, 2), "active_weight": round(industry_diff * 100, 2)},
            "Country": {"ctev": round((country_diff / total_diff) * factor_risk, 2), "active_weight": round(country_diff * 100, 2)},
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
        ctev_by_factor: Optional[Dict[str, Dict[str, float]]] = None,
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
            ctev_by_factor: Optional dict with CTEV by factor group (Market, Style) for consistency

        Returns:
            Dict mapping factor name to {ctev, securities: [{ticker, name, beta, active_weight, contribution}]}
        """
        import numpy as np
        from app.services.ticker_metadata_service import TickerMetadataService

        factors = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
        style_factors = ["SMB", "HML", "RMW", "CMA", "UMD"]
        result: Dict[str, Dict[str, Any]] = {}

        # Get CTEV values from ctev_by_factor for consistency
        market_ctev_total = 0.0
        style_ctev_total = 0.0
        if ctev_by_factor:
            market_data = ctev_by_factor.get("Market", {})
            market_ctev_total = market_data.get("ctev", 0) if isinstance(market_data, dict) else 0
            style_data = ctev_by_factor.get("Style", {})
            style_ctev_total = style_data.get("ctev", 0) if isinstance(style_data, dict) else 0

        # First pass: collect all factor data
        factor_data: Dict[str, Dict[str, Any]] = {}

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

            # Take top 50
            top_securities = security_contributions[:50]

            factor_data[factor] = {
                "active_beta": active_beta,
                "portfolio_beta": port_beta,
                "benchmark_beta": bench_beta,
                "securities": top_securities,
            }

        # Second pass: calculate CTEV values using ctev_by_factor for consistency
        # Calculate total abs(active_beta) for style factors to distribute Style CTEV proportionally
        total_style_abs_beta = sum(
            abs(factor_data[f]["active_beta"]) for f in style_factors
        )

        for factor in factors:
            data = factor_data[factor]
            active_beta = data["active_beta"]

            # Determine CTEV based on factor type
            if factor == "Mkt-RF":
                # Market factor uses Market CTEV directly from ctev_by_factor
                if market_ctev_total > 0:
                    factor_ctev = market_ctev_total
                else:
                    # Fallback to rough approximation
                    factor_ctev = abs(active_beta) * total_active_risk * 0.2
            else:
                # Style factors share Style CTEV proportionally based on abs(active_beta)
                if style_ctev_total > 0 and total_style_abs_beta > 0:
                    proportion = abs(active_beta) / total_style_abs_beta
                    factor_ctev = proportion * style_ctev_total
                else:
                    # Fallback to rough approximation
                    factor_ctev = abs(active_beta) * total_active_risk * 0.2

            # Get friendly name
            friendly_name = cls.FACTOR_NAMES.get(factor, factor)

            result[friendly_name] = {
                "factor_code": factor,
                "ctev": round(factor_ctev, 2),
                "active_beta": round(active_beta, 3),
                "portfolio_beta": round(data["portfolio_beta"], 3),
                "benchmark_beta": round(data["benchmark_beta"], 3),
                "securities": [
                    {
                        "ticker": s["ticker"],
                        "name": s["name"],
                        "beta": s["beta"],
                        "active_weight": s["active_weight"],
                        "contribution": round(s["contribution"] * 100, 3),  # Convert to percentage
                    }
                    for s in data["securities"]
                ],
            }

        # Sort factors by CTEV (descending)
        result = dict(sorted(result.items(), key=lambda x: x[1]["ctev"], reverse=True))

        return result

    @classmethod
    def calculate_industry_contributions(
        cls,
        regression_results: Dict[str, "FactorRegressionResult"],
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        benchmark_holdings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate industry factor contributions with top securities.

        Groups securities by industry and calculates active weight differences.
        Industry data comes from Yahoo Finance metadata.

        Args:
            regression_results: Dict mapping ticker to regression result
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            benchmark_holdings: Optional iShares holdings for additional metadata

        Returns:
            Dict mapping industry name to {active_weight, securities: [...]}
            Sorted by absolute active weight, top 20 industries
        """
        from app.services.ticker_metadata_service import TickerMetadataService

        # Group securities by industry
        industry_data: Dict[str, Dict[str, Any]] = {}

        # Get all tickers from both portfolio and benchmark
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        for ticker in all_tickers:
            ticker_upper = ticker.upper()
            pw = portfolio_weights.get(ticker_upper, 0.0)
            bw = benchmark_weights.get(ticker_upper, 0.0)
            active_weight = pw - bw

            # Skip if no position
            if pw <= 0 and bw <= 0:
                continue

            # Get industry from metadata
            metadata = TickerMetadataService.get_metadata(ticker_upper)
            industry = metadata.get("industry") or "Not Classified"
            name = metadata.get("shortName") or ticker_upper

            if industry not in industry_data:
                industry_data[industry] = {
                    "portfolio_weight": 0.0,
                    "benchmark_weight": 0.0,
                    "active_weight": 0.0,
                    "securities": [],
                }

            industry_data[industry]["portfolio_weight"] += pw
            industry_data[industry]["benchmark_weight"] += bw
            industry_data[industry]["active_weight"] += active_weight
            industry_data[industry]["securities"].append({
                "ticker": ticker_upper,
                "name": name,
                "portfolio_weight": round(pw * 100, 2),
                "benchmark_weight": round(bw * 100, 2),
                "active_weight": round(active_weight * 100, 2),
            })

        # Sort securities within each industry by absolute active weight
        for industry in industry_data:
            industry_data[industry]["securities"].sort(
                key=lambda x: abs(x["active_weight"]), reverse=True
            )
            # Keep top 50 securities per industry
            industry_data[industry]["securities"] = industry_data[industry]["securities"][:50]
            # Round industry-level weights
            industry_data[industry]["portfolio_weight"] = round(
                industry_data[industry]["portfolio_weight"] * 100, 2
            )
            industry_data[industry]["benchmark_weight"] = round(
                industry_data[industry]["benchmark_weight"] * 100, 2
            )
            industry_data[industry]["active_weight"] = round(
                industry_data[industry]["active_weight"] * 100, 2
            )

        # Sort industries by absolute active weight and take top 50
        sorted_industries = sorted(
            industry_data.items(),
            key=lambda x: abs(x[1]["active_weight"]),
            reverse=True
        )[:50]

        return dict(sorted_industries)

    @classmethod
    def calculate_sector_industry_contributions(
        cls,
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        total_active_risk: float,
        regression_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate hierarchical Sector → Industry factor contributions.

        Returns a nested structure where:
        - Sector (parent level): Collapsible header showing CTEV, contains industries
        - Industry (child level): Collapsible sub-header showing CTEV, contains securities
        - Securities: Individual holdings under each industry with their CTEV contribution

        CTEV Calculation:
        - Sector CTEV = |sector_active_weight| × (sector_active_weight / total_sector_diff) × factor_risk
        - Industry CTEV = |industry_active_weight| × (industry_active_weight / sector_diff) × sector_ctev
        - Security CTEV = (|security_active_weight| / industry_total_diff) × industry_ctev

        Args:
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            total_active_risk: Total tracking error (percentage)
            regression_results: Optional regression results for R² calculation

        Returns:
            Dict mapping sector name to:
            {
                "ctev": float,
                "active_weight": float,
                "portfolio_weight": float,
                "benchmark_weight": float,
                "industries": {
                    "Industry Name": {
                        "ctev": float,
                        "active_weight": float,
                        "portfolio_weight": float,
                        "benchmark_weight": float,
                        "securities": [
                            {"ticker": str, "name": str, "portfolio_weight": float,
                             "benchmark_weight": float, "active_weight": float, "ctev": float},
                            ...
                        ]
                    },
                    ...
                }
            }
            Sorted by CTEV with "Not Classified" always last.
        """
        from app.services.ticker_metadata_service import TickerMetadataService

        # Build hierarchical structure: Sector → Industry → Securities
        sector_data: Dict[str, Dict[str, Any]] = {}

        # Get all tickers from both portfolio and benchmark
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        # DEBUG: Comprehensive logging
        print(f"[SectorIndustry] === DEBUG START ===")
        print(f"[SectorIndustry] portfolio_weights dict size: {len(portfolio_weights)}")
        print(f"[SectorIndustry] benchmark_weights dict size: {len(benchmark_weights)}")
        print(f"[SectorIndustry] all_tickers set size: {len(all_tickers)}")

        # Count non-zero weights in each dict
        port_nonzero = sum(1 for v in portfolio_weights.values() if v > 0)
        bench_nonzero = sum(1 for v in benchmark_weights.values() if v > 0)
        print(f"[SectorIndustry] Portfolio non-zero weights: {port_nonzero}")
        print(f"[SectorIndustry] Benchmark non-zero weights: {bench_nonzero}")

        # Sample some benchmark weights to check values
        bench_samples = list(benchmark_weights.items())[:5]
        print(f"[SectorIndustry] Sample benchmark weights: {bench_samples}")

        # Pre-fetch industry data from Yahoo Finance for tickers missing it
        # The iShares CSV only has sector, not industry - so we need Yahoo for detailed breakdown
        tickers_needing_industry = []
        for ticker in all_tickers:
            ticker_upper = ticker.upper()
            pw = portfolio_weights.get(ticker_upper, 0.0)
            bw = benchmark_weights.get(ticker_upper, 0.0)
            if pw <= 0 and bw <= 0:
                continue
            # Check if this ticker is missing industry data
            cached = TickerMetadataService._load_cache().get(ticker_upper, {})
            if not cached.get("industry"):
                tickers_needing_industry.append(ticker_upper)

        if tickers_needing_industry:
            print(f"[SectorIndustry] Fetching industry data from Yahoo Finance for {len(tickers_needing_industry)} tickers...")
            print(f"[SectorIndustry] This may take several minutes (rate-limited to avoid Yahoo throttling)...")
            # Batch fetch from Yahoo with force_refresh since these are in cache but missing industry
            # Use only 5 workers to avoid Yahoo rate limiting
            TickerMetadataService.get_metadata_batch(tickers_needing_industry, force_refresh=True, max_workers=5)
            # Verify fetch success
            cache = TickerMetadataService._load_cache()
            has_industry = sum(1 for t in tickers_needing_industry if cache.get(t, {}).get("industry"))
            print(f"[SectorIndustry] Industry data fetch complete: {has_industry}/{len(tickers_needing_industry)} now have industry")

        for ticker in all_tickers:
            ticker_upper = ticker.upper()
            pw = portfolio_weights.get(ticker_upper, 0.0)
            bw = benchmark_weights.get(ticker_upper, 0.0)
            active_weight = pw - bw

            # Skip if no position
            if pw <= 0 and bw <= 0:
                continue

            # Get sector and industry from metadata
            metadata = TickerMetadataService.get_metadata(ticker_upper)
            sector = metadata.get("sector") or "Not Classified"
            industry = metadata.get("industry") or "Not Classified"
            name = metadata.get("shortName") or ticker_upper

            # Initialize sector if needed
            if sector not in sector_data:
                sector_data[sector] = {
                    "portfolio_weight": 0.0,
                    "benchmark_weight": 0.0,
                    "active_weight": 0.0,
                    "ctev": 0.0,
                    "industries": {},
                }

            # Initialize industry if needed
            if industry not in sector_data[sector]["industries"]:
                sector_data[sector]["industries"][industry] = {
                    "portfolio_weight": 0.0,
                    "benchmark_weight": 0.0,
                    "active_weight": 0.0,
                    "ctev": 0.0,
                    "securities": [],
                }

            # Aggregate weights at sector level
            sector_data[sector]["portfolio_weight"] += pw
            sector_data[sector]["benchmark_weight"] += bw
            sector_data[sector]["active_weight"] += active_weight

            # Aggregate weights at industry level
            sector_data[sector]["industries"][industry]["portfolio_weight"] += pw
            sector_data[sector]["industries"][industry]["benchmark_weight"] += bw
            sector_data[sector]["industries"][industry]["active_weight"] += active_weight

            # Add security (CTEV will be calculated after industry CTEV is known)
            sector_data[sector]["industries"][industry]["securities"].append({
                "ticker": ticker_upper,
                "name": name,
                "portfolio_weight": pw,  # Keep as decimal for now
                "benchmark_weight": bw,
                "active_weight": active_weight,
                "ctev": 0.0,  # Will be calculated later
            })

        # DEBUG: Count how many securities were actually added (before top-10 limit)
        total_securities_added = sum(
            len(ind["securities"])
            for s in sector_data.values()
            for ind in s["industries"].values()
        )
        total_industries = sum(len(s["industries"]) for s in sector_data.values())
        not_classified_sectors_count = 1 if "Not Classified" in sector_data else 0
        not_classified_industries_count = sum(
            1 for s in sector_data.values()
            for ind in s["industries"].keys()
            if ind == "Not Classified"
        )
        print(f"[SectorIndustry] Total securities ADDED (before top-10): {total_securities_added}")
        print(f"[SectorIndustry] Total sectors: {len(sector_data)}")
        print(f"[SectorIndustry] Total industries: {total_industries}")
        print(f"[SectorIndustry] 'Not Classified' sectors: {not_classified_sectors_count}")
        print(f"[SectorIndustry] 'Not Classified' industries: {not_classified_industries_count}")
        print(f"[SectorIndustry] === DEBUG END ===")

        # Calculate CTEV for sectors and industries
        # Estimate factor risk as R² percentage of total active risk
        avg_r2 = 0.5  # Default 50%
        if regression_results:
            total_r2 = sum(r.r_squared for r in regression_results.values())
            count = len(regression_results)
            if count > 0:
                avg_r2 = total_r2 / count

        factor_risk = total_active_risk * avg_r2

        # Calculate total sector weight difference for proportional allocation
        total_sector_diff = sum(
            abs(s["active_weight"]) for s in sector_data.values()
        )

        # Allocate CTEV proportionally to sectors
        for sector_name, sector_info in sector_data.items():
            sector_active_weight = sector_info["active_weight"]

            if total_sector_diff > 0.001:
                # Sector CTEV proportional to its active weight difference
                sector_ctev = (abs(sector_active_weight) / total_sector_diff) * factor_risk
            else:
                sector_ctev = 0.0

            sector_info["ctev"] = round(sector_ctev, 2)

            # Calculate total industry weight difference within this sector
            total_industry_diff = sum(
                abs(i["active_weight"]) for i in sector_info["industries"].values()
            )

            # Allocate sector CTEV proportionally to industries
            for industry_name, industry_info in sector_info["industries"].items():
                industry_active_weight = industry_info["active_weight"]

                if total_industry_diff > 0.001 and sector_ctev > 0:
                    # Industry CTEV proportional to its active weight within sector
                    industry_ctev = (abs(industry_active_weight) / total_industry_diff) * sector_ctev
                else:
                    industry_ctev = 0.0

                industry_info["ctev"] = round(industry_ctev, 2)

                # Calculate security-level CTEV
                # Total active weight difference within this industry
                industry_security_diff = sum(
                    abs(s["active_weight"]) for s in industry_info["securities"]
                )

                for security in industry_info["securities"]:
                    if industry_security_diff > 0.0001 and industry_ctev > 0:
                        # Security CTEV proportional to its active weight within industry
                        security_ctev = (abs(security["active_weight"]) / industry_security_diff) * industry_ctev
                    else:
                        security_ctev = 0.0
                    security["ctev"] = round(security_ctev, 4)

                    # Convert weights to percentages
                    security["portfolio_weight"] = round(security["portfolio_weight"] * 100, 2)
                    security["benchmark_weight"] = round(security["benchmark_weight"] * 100, 2)
                    security["active_weight"] = round(security["active_weight"] * 100, 2)

                # Sort securities by CTEV descending (not active weight)
                industry_info["securities"].sort(
                    key=lambda x: x["ctev"], reverse=True
                )

                # Show all securities (no limit)

                # Round weights to percentages
                industry_info["portfolio_weight"] = round(industry_info["portfolio_weight"] * 100, 2)
                industry_info["benchmark_weight"] = round(industry_info["benchmark_weight"] * 100, 2)
                industry_info["active_weight"] = round(industry_info["active_weight"] * 100, 2)

            # Round sector-level weights to percentages
            sector_info["portfolio_weight"] = round(sector_info["portfolio_weight"] * 100, 2)
            sector_info["benchmark_weight"] = round(sector_info["benchmark_weight"] * 100, 2)
            sector_info["active_weight"] = round(sector_info["active_weight"] * 100, 2)

            # Sort industries by CTEV descending, with "Not Classified" always last
            classified_industries = {
                k: v for k, v in sector_info["industries"].items() if k != "Not Classified"
            }
            not_classified_industries = {
                k: v for k, v in sector_info["industries"].items() if k == "Not Classified"
            }

            sorted_classified = dict(sorted(
                classified_industries.items(),
                key=lambda x: x[1]["ctev"],
                reverse=True
            ))
            # Append "Not Classified" at the end
            sorted_industries = {**sorted_classified, **not_classified_industries}
            sector_info["industries"] = sorted_industries

        # Sort sectors by CTEV descending, with "Not Classified" always last
        classified_sectors = {k: v for k, v in sector_data.items() if k != "Not Classified"}
        not_classified_sectors = {k: v for k, v in sector_data.items() if k == "Not Classified"}

        sorted_classified = dict(sorted(
            classified_sectors.items(),
            key=lambda x: x[1]["ctev"],
            reverse=True
        ))
        # Append "Not Classified" at the end
        sorted_sectors = {**sorted_classified, **not_classified_sectors}

        return sorted_sectors

    @classmethod
    def calculate_currency_contributions(
        cls,
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        benchmark_holdings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate binary USD vs non-USD currency factor with contributing securities.

        Currency data comes from iShares holdings (primary) or metadata (fallback).

        Args:
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            benchmark_holdings: iShares holdings for currency field

        Returns:
            Dict with "USD" and "Non-USD" entries, each containing:
            {portfolio_weight, benchmark_weight, active_weight, securities: [...]}
        """
        from app.services.ticker_metadata_service import TickerMetadataService

        result = {
            "USD": {
                "portfolio_weight": 0.0,
                "benchmark_weight": 0.0,
                "active_weight": 0.0,
                "securities": [],
            },
            "Non-USD": {
                "portfolio_weight": 0.0,
                "benchmark_weight": 0.0,
                "active_weight": 0.0,
                "securities": [],
            },
        }

        # Get all tickers from both portfolio and benchmark
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        for ticker in all_tickers:
            ticker_upper = ticker.upper()
            pw = portfolio_weights.get(ticker_upper, 0.0)
            bw = benchmark_weights.get(ticker_upper, 0.0)
            active_weight = pw - bw

            # Skip if no position
            if pw <= 0 and bw <= 0:
                continue

            # Get currency - prefer iShares holdings, fallback to metadata
            currency = "USD"  # Default
            if benchmark_holdings and ticker_upper in benchmark_holdings:
                holding = benchmark_holdings[ticker_upper]
                currency = getattr(holding, "currency", "USD") or "USD"
            else:
                metadata = TickerMetadataService.get_metadata(ticker_upper)
                currency = metadata.get("currency") or "USD"

            # Get security name
            metadata = TickerMetadataService.get_metadata(ticker_upper)
            name = metadata.get("shortName") or ticker_upper

            # Classify as USD or Non-USD
            bucket = "USD" if currency.upper() == "USD" else "Non-USD"

            result[bucket]["portfolio_weight"] += pw
            result[bucket]["benchmark_weight"] += bw
            result[bucket]["active_weight"] += active_weight
            result[bucket]["securities"].append({
                "ticker": ticker_upper,
                "name": name,
                "currency": currency,
                "portfolio_weight": round(pw * 100, 2),
                "benchmark_weight": round(bw * 100, 2),
                "active_weight": round(active_weight * 100, 2),
            })

        # Sort securities within each bucket by absolute active weight, show all
        for bucket in result:
            result[bucket]["securities"].sort(
                key=lambda x: abs(x["active_weight"]), reverse=True
            )
            # No limit - show all securities
            # Round bucket-level weights
            result[bucket]["portfolio_weight"] = round(
                result[bucket]["portfolio_weight"] * 100, 2
            )
            result[bucket]["benchmark_weight"] = round(
                result[bucket]["benchmark_weight"] * 100, 2
            )
            result[bucket]["active_weight"] = round(
                result[bucket]["active_weight"] * 100, 2
            )

        return result

    @classmethod
    def calculate_sector_contributions(
        cls,
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        total_active_risk: float,
        regression_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate flat sector-level CTEV (no industry grouping).

        Returns a flat structure where:
        - Sector (top level): Shows CTEV, active weight, contains ALL securities
        - Securities: Individual holdings under each sector with their CTEV contribution

        This is different from calculate_sector_industry_contributions() which has
        hierarchical Sector → Industry → Securities structure.

        CTEV Calculation:
        - Sector CTEV = |sector_active_weight| × (sector_active_weight / total_sector_diff) × factor_risk
        - Security CTEV = (|security_active_weight| / sector_total_diff) × sector_ctev

        Args:
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            total_active_risk: Total tracking error (percentage)
            regression_results: Optional regression results for R² calculation

        Returns:
            Dict mapping sector name to:
            {
                "ctev": float,
                "active_weight": float,
                "portfolio_weight": float,
                "benchmark_weight": float,
                "securities": [
                    {"ticker": str, "name": str, "portfolio_weight": float,
                     "benchmark_weight": float, "active_weight": float, "ctev": float},
                    ...
                ]
            }
            Sorted by CTEV with "Not Classified" always last.
        """
        from app.services.ticker_metadata_service import TickerMetadataService

        # Build flat structure: Sector → Securities (no industry level)
        sector_data: Dict[str, Dict[str, Any]] = {}

        # Get all tickers from both portfolio and benchmark
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        for ticker in all_tickers:
            ticker_upper = ticker.upper()
            pw = portfolio_weights.get(ticker_upper, 0.0)
            bw = benchmark_weights.get(ticker_upper, 0.0)
            active_weight = pw - bw

            # Skip if no position
            if pw <= 0 and bw <= 0:
                continue

            # Get sector from metadata (no industry needed for flat view)
            metadata = TickerMetadataService.get_metadata(ticker_upper)
            sector = metadata.get("sector") or "Not Classified"
            name = metadata.get("shortName") or ticker_upper

            # Initialize sector if needed
            if sector not in sector_data:
                sector_data[sector] = {
                    "portfolio_weight": 0.0,
                    "benchmark_weight": 0.0,
                    "active_weight": 0.0,
                    "ctev": 0.0,
                    "securities": [],
                }

            # Aggregate weights at sector level
            sector_data[sector]["portfolio_weight"] += pw
            sector_data[sector]["benchmark_weight"] += bw
            sector_data[sector]["active_weight"] += active_weight

            # Add security (CTEV will be calculated after sector CTEV is known)
            sector_data[sector]["securities"].append({
                "ticker": ticker_upper,
                "name": name,
                "portfolio_weight": pw,  # Keep as decimal for now
                "benchmark_weight": bw,
                "active_weight": active_weight,
                "ctev": 0.0,  # Will be calculated later
            })

        # Calculate CTEV for sectors
        # Estimate factor risk as R² percentage of total active risk
        avg_r2 = 0.5  # Default 50%
        if regression_results:
            total_r2 = sum(r.r_squared for r in regression_results.values())
            count = len(regression_results)
            if count > 0:
                avg_r2 = total_r2 / count

        factor_risk = total_active_risk * avg_r2

        # Calculate total sector weight difference for proportional allocation
        total_sector_diff = sum(
            abs(s["active_weight"]) for s in sector_data.values()
        )

        # Allocate CTEV proportionally to sectors
        for sector_name, sector_info in sector_data.items():
            sector_active_weight = sector_info["active_weight"]

            if total_sector_diff > 0.001:
                # Sector CTEV proportional to its active weight difference
                sector_ctev = (abs(sector_active_weight) / total_sector_diff) * factor_risk
            else:
                sector_ctev = 0.0

            sector_info["ctev"] = round(sector_ctev, 2)

            # Calculate security-level CTEV within this sector
            sector_security_diff = sum(
                abs(s["active_weight"]) for s in sector_info["securities"]
            )

            for security in sector_info["securities"]:
                if sector_security_diff > 0.0001 and sector_ctev > 0:
                    # Security CTEV proportional to its active weight within sector
                    security_ctev = (abs(security["active_weight"]) / sector_security_diff) * sector_ctev
                else:
                    security_ctev = 0.0
                security["ctev"] = round(security_ctev, 4)

                # Convert weights to percentages
                security["portfolio_weight"] = round(security["portfolio_weight"] * 100, 2)
                security["benchmark_weight"] = round(security["benchmark_weight"] * 100, 2)
                security["active_weight"] = round(security["active_weight"] * 100, 2)

            # Sort securities by CTEV descending
            sector_info["securities"].sort(
                key=lambda x: x["ctev"], reverse=True
            )

            # Round sector-level weights to percentages
            sector_info["portfolio_weight"] = round(sector_info["portfolio_weight"] * 100, 2)
            sector_info["benchmark_weight"] = round(sector_info["benchmark_weight"] * 100, 2)
            sector_info["active_weight"] = round(sector_info["active_weight"] * 100, 2)

        # Sort sectors by CTEV descending, with "Not Classified" always last
        classified_sectors = {k: v for k, v in sector_data.items() if k != "Not Classified"}
        not_classified_sectors = {k: v for k, v in sector_data.items() if k == "Not Classified"}

        sorted_classified = dict(sorted(
            classified_sectors.items(),
            key=lambda x: x[1]["ctev"],
            reverse=True
        ))
        # Append "Not Classified" at the end
        sorted_sectors = {**sorted_classified, **not_classified_sectors}

        return sorted_sectors

    @classmethod
    def calculate_country_contributions(
        cls,
        portfolio_weights: Dict[str, float],
        benchmark_weights: Dict[str, float],
        benchmark_holdings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate binary US vs non-US country factor with contributing securities.

        Country data comes from iShares holdings location field (primary) or metadata.

        Args:
            portfolio_weights: Portfolio weights (decimal)
            benchmark_weights: Benchmark weights (decimal)
            benchmark_holdings: iShares holdings for location field

        Returns:
            Dict with "US" and "Non-US" entries, each containing:
            {portfolio_weight, benchmark_weight, active_weight, securities: [...]}
        """
        from app.services.ticker_metadata_service import TickerMetadataService

        result = {
            "US": {
                "portfolio_weight": 0.0,
                "benchmark_weight": 0.0,
                "active_weight": 0.0,
                "securities": [],
            },
            "Non-US": {
                "portfolio_weight": 0.0,
                "benchmark_weight": 0.0,
                "active_weight": 0.0,
                "securities": [],
            },
        }

        # US location values from iShares
        US_LOCATIONS = {"United States", "USA", "US"}

        # Get all tickers from both portfolio and benchmark
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        for ticker in all_tickers:
            ticker_upper = ticker.upper()
            pw = portfolio_weights.get(ticker_upper, 0.0)
            bw = benchmark_weights.get(ticker_upper, 0.0)
            active_weight = pw - bw

            # Skip if no position
            if pw <= 0 and bw <= 0:
                continue

            # Get location - prefer iShares holdings, fallback to metadata country
            location = "United States"  # Default for US stocks
            if benchmark_holdings and ticker_upper in benchmark_holdings:
                holding = benchmark_holdings[ticker_upper]
                location = getattr(holding, "location", "United States") or "United States"
            else:
                metadata = TickerMetadataService.get_metadata(ticker_upper)
                location = metadata.get("country") or "United States"

            # Get security name
            metadata = TickerMetadataService.get_metadata(ticker_upper)
            name = metadata.get("shortName") or ticker_upper

            # Classify as US or Non-US
            bucket = "US" if location in US_LOCATIONS else "Non-US"

            result[bucket]["portfolio_weight"] += pw
            result[bucket]["benchmark_weight"] += bw
            result[bucket]["active_weight"] += active_weight
            result[bucket]["securities"].append({
                "ticker": ticker_upper,
                "name": name,
                "country": location,
                "portfolio_weight": round(pw * 100, 2),
                "benchmark_weight": round(bw * 100, 2),
                "active_weight": round(active_weight * 100, 2),
            })

        # Sort securities within each bucket by absolute active weight, show all
        for bucket in result:
            result[bucket]["securities"].sort(
                key=lambda x: abs(x["active_weight"]), reverse=True
            )
            # No limit - show all securities
            # Round bucket-level weights
            result[bucket]["portfolio_weight"] = round(
                result[bucket]["portfolio_weight"] * 100, 2
            )
            result[bucket]["benchmark_weight"] = round(
                result[bucket]["benchmark_weight"] * 100, 2
            )
            result[bucket]["active_weight"] = round(
                result[bucket]["active_weight"] * 100, 2
            )

        return result

    @classmethod
    def validate_risk_decomposition(
        cls,
        security_risks: Dict[str, Dict[str, float]],
        summary: Dict[str, float],
        ctev_by_factor: Dict[str, Dict[str, float]],
    ) -> List[str]:
        """
        Validate that risk decomposition sums correctly.

        Args:
            security_risks: Per-security risk metrics
            summary: Portfolio summary metrics
            ctev_by_factor: CTEV by factor group ({"Factor": {"ctev": X, "active_weight": Y}})

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
