"""General services - shared business logic across modules.

Uses PEP 562 lazy imports (__getattr__) for faster startup.
Services are imported only when first accessed.
"""
from __future__ import annotations

__all__ = [
    "fetch_price_history",
    "clear_cache",
    "PortfolioDataService",
    "PortfolioData",
    "Transaction",
    "Holding",
    "ReturnsDataService",
    "StatisticsService",
]


def __getattr__(name: str):
    """Lazy import services only when accessed."""
    if name in ("fetch_price_history", "clear_cache"):
        from app.services.market_data import fetch_price_history, clear_cache
        globals()["fetch_price_history"] = fetch_price_history
        globals()["clear_cache"] = clear_cache
        return globals()[name]

    if name in ("PortfolioDataService", "PortfolioData", "Transaction", "Holding"):
        from app.services.portfolio_data_service import (
            PortfolioDataService,
            PortfolioData,
            Transaction,
            Holding,
        )
        globals()["PortfolioDataService"] = PortfolioDataService
        globals()["PortfolioData"] = PortfolioData
        globals()["Transaction"] = Transaction
        globals()["Holding"] = Holding
        return globals()[name]

    if name == "ReturnsDataService":
        from app.services.returns_data_service import ReturnsDataService
        globals()["ReturnsDataService"] = ReturnsDataService
        return ReturnsDataService

    if name == "StatisticsService":
        from app.services.statistics_service import StatisticsService
        globals()["StatisticsService"] = StatisticsService
        return StatisticsService

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
