"""Portfolio Data Service - Read-Only Access to Portfolio Data.

This service provides a clean API for analysis modules to access portfolio
data without modifying it. It wraps PortfolioPersistence and PortfolioService
to provide computed properties like holdings.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.ui.modules.portfolio_construction.services.portfolio_persistence import (
    PortfolioPersistence,
)
from app.ui.modules.portfolio_construction.services.portfolio_service import (
    PortfolioService,
)


@dataclass
class Transaction:
    """Immutable transaction record."""

    id: str
    date: str
    ticker: str
    transaction_type: str  # "Buy" or "Sell"
    quantity: float
    entry_price: float
    fees: float
    sequence: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        """Create Transaction from dict."""
        return cls(
            id=data.get("id", ""),
            date=data.get("date", ""),
            ticker=data.get("ticker", ""),
            transaction_type=data.get("transaction_type", "Buy"),
            quantity=float(data.get("quantity", 0)),
            entry_price=float(data.get("entry_price", 0)),
            fees=float(data.get("fees", 0)),
            sequence=int(data.get("sequence", 0)),
        )


@dataclass
class Holding:
    """Computed holding position."""

    ticker: str
    quantity: float
    avg_cost_basis: float
    total_cost: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    pnl: Optional[float] = None
    weight: Optional[float] = None


@dataclass
class PortfolioData:
    """Complete portfolio data structure."""

    name: str
    created_date: str
    last_modified: str
    transactions: List[Transaction]

    @property
    def tickers(self) -> List[str]:
        """Get unique tickers in this portfolio (excluding FREE CASH)."""
        seen = set()
        result = []
        for tx in self.transactions:
            ticker = tx.ticker.upper()
            if ticker != "FREE CASH" and ticker not in seen:
                seen.add(ticker)
                result.append(ticker)
        return result

    @property
    def transaction_count(self) -> int:
        """Get number of transactions."""
        return len(self.transactions)


class PortfolioDataService:
    """
    Read-only service for accessing portfolio data.

    This service is designed for analysis modules that need to read
    portfolio holdings and transactions without modifying them.
    All methods return immutable dataclasses.
    """

    # Portfolios directory (same as PortfolioPersistence)
    _PORTFOLIOS_DIR = Path.home() / ".quant_terminal" / "portfolios"

    @classmethod
    def list_portfolios(cls) -> List[str]:
        """
        List all available portfolio names.

        Returns:
            List of portfolio names sorted alphabetically
        """
        return sorted(PortfolioPersistence.list_portfolios())

    @classmethod
    def list_portfolios_by_recent(cls) -> List[str]:
        """
        List portfolios sorted by most recently accessed.

        Returns:
            List of portfolio names, most recently accessed first
        """
        return PortfolioPersistence.list_portfolios_by_recent()

    @classmethod
    def get_portfolio(cls, name: str) -> Optional[PortfolioData]:
        """
        Load portfolio by name.

        Args:
            name: Portfolio name (without .json extension)

        Returns:
            PortfolioData or None if not found
        """
        raw = PortfolioPersistence.load_portfolio(name)
        if raw is None:
            return None

        transactions = [
            Transaction.from_dict(tx) for tx in raw.get("transactions", [])
        ]

        return PortfolioData(
            name=raw.get("name", name),
            created_date=raw.get("created_date", ""),
            last_modified=raw.get("last_modified", ""),
            transactions=transactions,
        )

    @classmethod
    def get_transactions(cls, name: str) -> List[Transaction]:
        """
        Get all transactions for a portfolio.

        Args:
            name: Portfolio name

        Returns:
            List of Transaction objects, or empty list if portfolio not found
        """
        portfolio = cls.get_portfolio(name)
        return portfolio.transactions if portfolio else []

    @classmethod
    def get_holdings(
        cls,
        name: str,
        current_prices: Optional[Dict[str, float]] = None,
    ) -> List[Holding]:
        """
        Get computed holdings for a portfolio.

        Args:
            name: Portfolio name
            current_prices: Optional dict of ticker -> current price.
                           If not provided, market values won't be computed.

        Returns:
            List of Holding objects with computed values
        """
        raw = PortfolioPersistence.load_portfolio(name)
        if raw is None:
            return []

        transactions = raw.get("transactions", [])
        if not transactions:
            return []

        # Use PortfolioService to calculate aggregate holdings
        prices = current_prices or {}
        raw_holdings = PortfolioService.calculate_aggregate_holdings(
            transactions, prices
        )

        # Convert to Holding dataclasses
        holdings = []
        for h in raw_holdings:
            # calculate_aggregate_holdings uses "weight_pct" (0-100) and "total_quantity"
            # Convert to decimal weight (0-1) for calculations
            weight_pct = h.get("weight_pct", 0)
            weight_decimal = weight_pct / 100.0 if weight_pct else None

            holdings.append(
                Holding(
                    ticker=h.get("ticker", ""),
                    quantity=h.get("total_quantity", h.get("quantity", 0)),
                    avg_cost_basis=h.get("avg_cost_basis", 0),
                    total_cost=h.get("total_cost", 0),
                    current_price=h.get("current_price"),
                    market_value=h.get("market_value"),
                    pnl=h.get("total_pnl", h.get("pnl")),
                    weight=weight_decimal,
                )
            )

        return holdings

    @classmethod
    def get_tickers(cls, name: str) -> List[str]:
        """
        Get unique tickers in a portfolio (excluding FREE CASH).

        Args:
            name: Portfolio name

        Returns:
            List of unique ticker symbols
        """
        portfolio = cls.get_portfolio(name)
        return portfolio.tickers if portfolio else []

    @classmethod
    def portfolio_exists(cls, name: str) -> bool:
        """
        Check if a portfolio exists.

        Args:
            name: Portfolio name

        Returns:
            True if portfolio exists
        """
        return PortfolioPersistence.portfolio_exists(name)

    @classmethod
    def get_portfolio_modified_time(cls, name: str) -> Optional[datetime]:
        """
        Get the last modified timestamp for a portfolio.

        Useful for cache invalidation.

        Args:
            name: Portfolio name

        Returns:
            datetime of last modification, or None if not found
        """
        path = cls._PORTFOLIOS_DIR / f"{name}.json"
        if not path.exists():
            return None

        try:
            return datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            return None
