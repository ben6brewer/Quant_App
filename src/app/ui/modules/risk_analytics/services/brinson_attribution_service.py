"""Brinson Attribution Service - Performance attribution using Brinson-Fachler methodology.

Implements Brinson-Fachler (1985) attribution analysis to decompose portfolio
excess returns into allocation, selection, and interaction effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd

from app.services.ishares_holdings_service import ETFHolding


@dataclass
class AttributionResult:
    """Attribution results for a single holding or sector."""

    ticker: str  # Ticker symbol or sector name for aggregated results
    name: str
    sector: str
    industry: str
    portfolio_weight: float  # w_p (decimal)
    benchmark_weight: float  # w_b (decimal)
    portfolio_return: float  # r_p (decimal)
    benchmark_return: float  # r_b (decimal)
    allocation_effect: float  # (w_p - w_b) * (r_b_sector - r_b_total)
    selection_effect: float  # w_b * (r_p - r_b)
    interaction_effect: float  # (w_p - w_b) * (r_p - r_b)
    total_effect: float  # allocation + selection + interaction


@dataclass
class BrinsonAnalysis:
    """Complete Brinson-Fachler analysis results."""

    period_start: str
    period_end: str
    total_portfolio_return: float  # Cumulative return for period
    total_benchmark_return: float
    total_excess_return: float
    total_allocation_effect: float
    total_selection_effect: float
    total_interaction_effect: float

    by_security: Dict[str, AttributionResult] = field(default_factory=dict)
    by_sector: Dict[str, AttributionResult] = field(default_factory=dict)


class BrinsonAttributionService:
    """
    Brinson-Fachler (1985) performance attribution.

    Decomposes portfolio excess return into:
    - Allocation Effect: Return from over/underweighting sectors
    - Selection Effect: Return from security selection within sectors
    - Interaction Effect: Combined effect of allocation and selection decisions
    """

    @classmethod
    def calculate_attribution(
        cls,
        portfolio_weights: Dict[str, float],
        benchmark_holdings: Dict[str, ETFHolding],
        portfolio_returns: "pd.DataFrame",
        benchmark_returns: "pd.DataFrame",
        period_start: str,
        period_end: str,
        daily_weights: "pd.DataFrame" = None,
    ) -> BrinsonAnalysis:
        """
        Calculate Brinson-Fachler attribution.

        Args:
            portfolio_weights: Dict mapping ticker -> weight (decimal)
            benchmark_holdings: Dict mapping ticker -> ETFHolding from iShares
            portfolio_returns: DataFrame with tickers as columns, daily returns
            benchmark_returns: DataFrame with benchmark constituent returns
            period_start: Start date (YYYY-MM-DD)
            period_end: End date (YYYY-MM-DD)
            daily_weights: Optional DataFrame with daily portfolio weights.
                          If provided, returns are calculated only for days
                          when each ticker was actually held.

        Returns:
            BrinsonAnalysis with complete attribution breakdown
        """
        import numpy as np

        # Calculate cumulative returns for the period
        # For portfolio: use daily_weights to only count returns when held
        port_cum_returns = cls._calculate_period_returns(
            portfolio_returns, period_start, period_end, weights_df=daily_weights
        )
        # For benchmark: use full period (benchmark weights are static)
        bench_cum_returns = cls._calculate_period_returns(
            benchmark_returns, period_start, period_end
        )

        # Get benchmark weights from holdings
        benchmark_weights = {
            ticker: holding.weight for ticker, holding in benchmark_holdings.items()
        }

        # Calculate total benchmark return (weighted)
        total_benchmark_return = sum(
            benchmark_weights.get(ticker, 0) * bench_cum_returns.get(ticker, 0)
            for ticker in benchmark_weights
        )

        # Calculate sector-level benchmark returns
        sector_bench_returns = cls._calculate_sector_returns(
            benchmark_holdings, bench_cum_returns
        )

        # Calculate attribution for each security
        security_results: Dict[str, AttributionResult] = {}
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_holdings.keys())

        for ticker in all_tickers:
            port_weight = portfolio_weights.get(ticker, 0)
            bench_weight = benchmark_weights.get(ticker, 0)

            # Portfolio return: use actual return if in portfolio, else 0
            port_return = port_cum_returns.get(ticker, 0) if port_weight > 0 else 0

            # Benchmark return: use actual return ONLY if in benchmark, else 0
            # (Don't use portfolio ticker returns for benchmark calculation)
            bench_return = bench_cum_returns.get(ticker, 0) if bench_weight > 0 else 0

            result = cls._calculate_security_attribution(
                ticker=ticker,
                portfolio_weight=port_weight,
                benchmark_weight=bench_weight,
                portfolio_return=port_return,
                benchmark_return=bench_return,
                benchmark_holdings=benchmark_holdings,
                sector_bench_returns=sector_bench_returns,
                total_benchmark_return=total_benchmark_return,
            )
            if result:
                security_results[ticker] = result

        # Aggregate by sector
        sector_results = cls._aggregate_by_sector(security_results)

        # Calculate totals
        total_allocation = sum(r.allocation_effect for r in security_results.values())
        total_selection = sum(r.selection_effect for r in security_results.values())
        total_interaction = sum(
            r.interaction_effect for r in security_results.values()
        )

        # Calculate total portfolio return
        total_portfolio_return = sum(
            portfolio_weights.get(ticker, 0) * port_cum_returns.get(ticker, 0)
            for ticker in portfolio_weights
        )

        return BrinsonAnalysis(
            period_start=period_start,
            period_end=period_end,
            total_portfolio_return=total_portfolio_return,
            total_benchmark_return=total_benchmark_return,
            total_excess_return=total_portfolio_return - total_benchmark_return,
            total_allocation_effect=total_allocation,
            total_selection_effect=total_selection,
            total_interaction_effect=total_interaction,
            by_security=security_results,
            by_sector=sector_results,
        )

    @classmethod
    def _calculate_period_returns(
        cls,
        returns_df: "pd.DataFrame",
        start_date: str,
        end_date: str,
        weights_df: "pd.DataFrame" = None,
    ) -> Dict[str, float]:
        """
        Calculate cumulative returns for each ticker over the period.

        If weights_df is provided, only calculates returns for days when the
        ticker was actually held (weight > 0). This gives accurate holding-period
        returns for securities that were bought/sold during the period.

        Args:
            returns_df: DataFrame with daily returns (tickers as columns)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            weights_df: Optional DataFrame with daily weights (tickers as columns)

        Returns:
            Dict mapping ticker -> cumulative return (decimal)
        """
        import pandas as pd

        if returns_df is None or returns_df.empty:
            return {}

        # Filter to date range
        mask = (returns_df.index >= pd.Timestamp(start_date)) & (
            returns_df.index <= pd.Timestamp(end_date)
        )
        period_returns = returns_df.loc[mask]

        if period_returns.empty:
            return {}

        # Also filter weights if provided (using its own date range, not the returns mask)
        period_weights = None
        if weights_df is not None and not weights_df.empty:
            weights_mask = (weights_df.index >= pd.Timestamp(start_date)) & (
                weights_df.index <= pd.Timestamp(end_date)
            )
            period_weights = weights_df.loc[weights_mask] if weights_mask.any() else None

        # Calculate cumulative return: (1 + r1) * (1 + r2) * ... - 1
        # If weights provided, only include days when ticker was held (weight > 0)
        cum_returns = {}
        for ticker in period_returns.columns:
            series = period_returns[ticker].dropna()

            # If we have weights, filter to only days when ticker was held
            if period_weights is not None and ticker in period_weights.columns:
                ticker_weights = period_weights[ticker]
                # Only include days where weight > 0 (ticker was held)
                held_dates = ticker_weights[ticker_weights > 0].index
                series = series[series.index.isin(held_dates)]

            if len(series) > 0:
                cum_return = (1 + series).prod() - 1
                cum_returns[ticker] = cum_return

        return cum_returns

    @classmethod
    def _calculate_sector_returns(
        cls,
        benchmark_holdings: Dict[str, ETFHolding],
        benchmark_returns: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Calculate weighted sector-level benchmark returns.

        Args:
            benchmark_holdings: Dict of ETF holdings
            benchmark_returns: Dict of ticker -> cumulative return

        Returns:
            Dict mapping sector -> weighted return
        """
        sector_weights: Dict[str, float] = {}
        sector_returns: Dict[str, float] = {}

        for ticker, holding in benchmark_holdings.items():
            sector = holding.sector
            weight = holding.weight
            ret = benchmark_returns.get(ticker, 0)

            if sector not in sector_weights:
                sector_weights[sector] = 0
                sector_returns[sector] = 0

            sector_weights[sector] += weight
            sector_returns[sector] += weight * ret

        # Normalize by sector weight
        for sector in sector_returns:
            if sector_weights[sector] > 0:
                sector_returns[sector] /= sector_weights[sector]

        return sector_returns

    @classmethod
    def _calculate_security_attribution(
        cls,
        ticker: str,
        portfolio_weight: float,
        benchmark_weight: float,
        portfolio_return: float,
        benchmark_return: float,
        benchmark_holdings: Dict[str, ETFHolding],
        sector_bench_returns: Dict[str, float],
        total_benchmark_return: float,
    ) -> Optional[AttributionResult]:
        """
        Calculate Brinson attribution for a single security.

        Brinson-Fachler (1985) formulas:
        - Allocation = (w_p - w_b) * (r_b_sector - r_b_total)
        - Selection = w_b * (r_p - r_b)
        - Interaction = (w_p - w_b) * (r_p - r_b)
        """
        from app.services.ticker_metadata_service import TickerMetadataService

        # Skip if no exposure
        if portfolio_weight == 0 and benchmark_weight == 0:
            return None

        # Get sector and industry
        if ticker in benchmark_holdings:
            holding = benchmark_holdings[ticker]
            sector = holding.sector
            name = holding.name
            industry = ""  # iShares doesn't provide industry
        else:
            # Non-benchmark holding - use Yahoo metadata
            metadata = TickerMetadataService.get_metadata(ticker)
            sector = metadata.get("sector", "Not Classified")
            name = metadata.get("shortName", ticker)
            industry = metadata.get("industry", "")

        # Get sector benchmark return
        sector_bench_return = sector_bench_returns.get(sector, total_benchmark_return)

        # Brinson-Fachler formulas
        active_weight = portfolio_weight - benchmark_weight
        allocation_effect = active_weight * (sector_bench_return - total_benchmark_return)
        selection_effect = benchmark_weight * (portfolio_return - benchmark_return)
        interaction_effect = active_weight * (portfolio_return - benchmark_return)
        total_effect = allocation_effect + selection_effect + interaction_effect

        return AttributionResult(
            ticker=ticker,
            name=name,
            sector=sector,
            industry=industry,
            portfolio_weight=portfolio_weight,
            benchmark_weight=benchmark_weight,
            portfolio_return=portfolio_return,
            benchmark_return=benchmark_return,
            allocation_effect=allocation_effect,
            selection_effect=selection_effect,
            interaction_effect=interaction_effect,
            total_effect=total_effect,
        )

    @classmethod
    def _aggregate_by_sector(
        cls,
        security_results: Dict[str, AttributionResult],
    ) -> Dict[str, AttributionResult]:
        """
        Aggregate security-level attribution to sector level.

        Args:
            security_results: Dict of ticker -> AttributionResult

        Returns:
            Dict of sector -> aggregated AttributionResult
        """
        sector_data: Dict[str, Dict] = {}

        for ticker, result in security_results.items():
            sector = result.sector

            if sector not in sector_data:
                sector_data[sector] = {
                    "portfolio_weight": 0,
                    "benchmark_weight": 0,
                    "portfolio_return_weighted": 0,
                    "benchmark_return_weighted": 0,
                    "allocation_effect": 0,
                    "selection_effect": 0,
                    "interaction_effect": 0,
                    "count": 0,
                }

            data = sector_data[sector]
            data["portfolio_weight"] += result.portfolio_weight
            data["benchmark_weight"] += result.benchmark_weight
            data["portfolio_return_weighted"] += (
                result.portfolio_weight * result.portfolio_return
            )
            data["benchmark_return_weighted"] += (
                result.benchmark_weight * result.benchmark_return
            )
            data["allocation_effect"] += result.allocation_effect
            data["selection_effect"] += result.selection_effect
            data["interaction_effect"] += result.interaction_effect
            data["count"] += 1

        # Create aggregated results
        sector_results: Dict[str, AttributionResult] = {}

        for sector, data in sector_data.items():
            # Calculate weighted average returns
            port_ret = (
                data["portfolio_return_weighted"] / data["portfolio_weight"]
                if data["portfolio_weight"] > 0
                else 0
            )
            bench_ret = (
                data["benchmark_return_weighted"] / data["benchmark_weight"]
                if data["benchmark_weight"] > 0
                else 0
            )

            total_effect = (
                data["allocation_effect"]
                + data["selection_effect"]
                + data["interaction_effect"]
            )

            sector_results[sector] = AttributionResult(
                ticker=sector,  # Use sector name as "ticker" for display
                name=f"{sector} ({data['count']} holdings)",
                sector=sector,
                industry="",
                portfolio_weight=data["portfolio_weight"],
                benchmark_weight=data["benchmark_weight"],
                portfolio_return=port_ret,
                benchmark_return=bench_ret,
                allocation_effect=data["allocation_effect"],
                selection_effect=data["selection_effect"],
                interaction_effect=data["interaction_effect"],
                total_effect=total_effect,
            )

        return sector_results
