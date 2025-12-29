"""Portfolio Service - Business Logic and Calculations"""

import uuid
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict

from app.services.market_data import fetch_price_history


class PortfolioService:
    """
    Stateless service for portfolio calculations and business logic.
    All methods are static and operate on data passed in.
    """

    @staticmethod
    def create_transaction(
        date: str,
        ticker: str,
        transaction_type: str,
        quantity: float,
        entry_price: float,
        fees: float = 0.0,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Create a new transaction with generated UUID.

        Args:
            date: Transaction date in ISO format (YYYY-MM-DD)
            ticker: Ticker symbol
            transaction_type: "Buy" or "Sell"
            quantity: Number of shares/coins
            entry_price: Price per share
            fees: Transaction fees
            notes: Optional user notes

        Returns:
            Transaction dict
        """
        return {
            "id": str(uuid.uuid4()),
            "date": date,
            "ticker": ticker.strip().upper(),
            "transaction_type": transaction_type,
            "quantity": float(quantity),
            "entry_price": float(entry_price),
            "fees": float(fees),
            "notes": notes.strip()
        }

    @staticmethod
    def validate_transaction(transaction: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate transaction data.

        Args:
            transaction: Transaction dict to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check date format
        if not transaction.get("date"):
            return False, "Date is required"

        # Check ticker
        ticker = transaction.get("ticker", "").strip()
        if not ticker:
            return False, "Ticker is required"

        # Check transaction type
        transaction_type = transaction.get("transaction_type", "")
        if transaction_type not in ["Buy", "Sell"]:
            return False, "Transaction type must be 'Buy' or 'Sell'"

        # Check quantity
        try:
            quantity = float(transaction.get("quantity", 0))
            if quantity <= 0:
                return False, "Quantity must be greater than 0"
        except (ValueError, TypeError):
            return False, "Invalid quantity"

        # Check entry price
        try:
            entry_price = float(transaction.get("entry_price", 0))
            if entry_price <= 0:
                return False, "Entry price must be greater than 0"
        except (ValueError, TypeError):
            return False, "Invalid entry price"

        # Check fees
        try:
            fees = float(transaction.get("fees", 0))
            if fees < 0:
                return False, "Fees cannot be negative"
        except (ValueError, TypeError):
            return False, "Invalid fees"

        return True, ""

    @staticmethod
    def calculate_cost_basis(transaction: Dict[str, Any]) -> float:
        """
        Calculate cost basis for a transaction.

        Args:
            transaction: Transaction dict

        Returns:
            Cost basis (positive for buys, negative for sells)
        """
        quantity = transaction["quantity"]
        entry_price = transaction["entry_price"]
        fees = transaction["fees"]

        if transaction["transaction_type"] == "Buy":
            # For buys: cost = (quantity * price) + fees
            return (quantity * entry_price) + fees
        else:
            # For sells: proceeds = (quantity * price) - fees (returned as negative cost)
            return -((quantity * entry_price) - fees)

    @staticmethod
    def calculate_aggregate_holdings(
        transactions: List[Dict[str, Any]],
        current_prices: Dict[str, Optional[float]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate aggregate holdings from transaction log.

        Args:
            transactions: List of all transactions
            current_prices: Dict mapping ticker -> current price (or None if unavailable)

        Returns:
            List of aggregate holdings dicts, sorted by weight descending
        """
        if not transactions:
            return []

        # Group transactions by ticker
        ticker_transactions = defaultdict(list)
        for tx in transactions:
            ticker_transactions[tx["ticker"]].append(tx)

        holdings = []
        total_market_value = 0.0

        # Calculate holdings for each ticker
        for ticker, txs in ticker_transactions.items():
            # Calculate net quantity and weighted average cost
            total_quantity = 0.0
            total_cost = 0.0

            for tx in txs:
                qty = tx["quantity"]
                price = tx["entry_price"]
                fees = tx["fees"]

                if tx["transaction_type"] == "Buy":
                    total_quantity += qty
                    total_cost += (qty * price) + fees
                else:  # Sell
                    total_quantity -= qty
                    # For sells, reduce the cost basis proportionally
                    total_cost -= (qty * price) - fees

            # Skip if position is fully closed (net quantity is 0 or negative)
            if total_quantity <= 0.0001:  # Use small epsilon for floating point comparison
                continue

            # Calculate weighted average cost basis
            avg_cost_basis = total_cost / total_quantity if total_quantity > 0 else 0

            # Get current price
            current_price = current_prices.get(ticker)

            # Calculate market value and P&L
            if current_price is not None:
                market_value = current_price * total_quantity
                total_pnl = market_value - total_cost
                total_market_value += market_value
            else:
                market_value = None
                total_pnl = None

            holdings.append({
                "ticker": ticker,
                "total_quantity": total_quantity,
                "avg_cost_basis": avg_cost_basis,
                "current_price": current_price,
                "market_value": market_value,
                "total_pnl": total_pnl,
                "weight_pct": 0.0  # Will be calculated after total is known
            })

        # Calculate weight percentages
        if total_market_value > 0:
            for holding in holdings:
                if holding["market_value"] is not None:
                    holding["weight_pct"] = (holding["market_value"] / total_market_value) * 100
                else:
                    holding["weight_pct"] = 0.0

        # Sort by weight descending
        holdings.sort(key=lambda h: h["weight_pct"], reverse=True)

        return holdings

    @staticmethod
    def calculate_portfolio_totals(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate portfolio-level totals.

        Args:
            holdings: List of holding dicts from calculate_aggregate_holdings

        Returns:
            Dict with total_market_value, total_cost_basis, total_pnl, total_pnl_pct
        """
        if not holdings:
            return {
                "total_market_value": 0.0,
                "total_cost_basis": 0.0,
                "total_pnl": 0.0,
                "total_pnl_pct": 0.0
            }

        total_market_value = 0.0
        total_cost_basis = 0.0
        total_pnl = 0.0

        for holding in holdings:
            if holding["market_value"] is not None:
                total_market_value += holding["market_value"]

            # Calculate cost basis from avg_cost_basis * quantity
            total_cost_basis += holding["avg_cost_basis"] * holding["total_quantity"]

            if holding["total_pnl"] is not None:
                total_pnl += holding["total_pnl"]

        # Calculate total P&L percentage
        if total_cost_basis > 0:
            total_pnl_pct = (total_pnl / total_cost_basis) * 100
        else:
            total_pnl_pct = 0.0

        return {
            "total_market_value": total_market_value,
            "total_cost_basis": total_cost_basis,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct
        }

    @staticmethod
    def fetch_current_prices(tickers: List[str]) -> Dict[str, Optional[float]]:
        """
        Fetch current prices for tickers using MarketDataService.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> price (or None if fetch failed)
        """
        prices = {}

        for ticker in tickers:
            if not ticker:
                continue

            try:
                # Fetch last 5 days of data to get latest close
                df = fetch_price_history(ticker, period="5d", interval="1d")

                if df is not None and not df.empty:
                    # Get last close price
                    prices[ticker] = float(df["Close"].iloc[-1])
                else:
                    prices[ticker] = None
            except Exception as e:
                print(f"Error fetching price for {ticker}: {e}")
                prices[ticker] = None

        return prices

    # Export API for other modules

    @staticmethod
    def get_current_holdings_snapshot(portfolio_name: str = "Default") -> List[Dict[str, Any]]:
        """
        Get current holdings for a portfolio (for other modules).

        Args:
            portfolio_name: Name of portfolio to load

        Returns:
            List of holding dicts with ticker, quantity, cost, price, value
        """
        from .portfolio_persistence import PortfolioPersistence

        portfolio = PortfolioPersistence.load_portfolio(portfolio_name)
        if not portfolio:
            return []

        transactions = portfolio.get("transactions", [])
        if not transactions:
            return []

        # Get unique tickers
        tickers = list(set(t["ticker"] for t in transactions if t.get("ticker")))

        # Fetch current prices
        current_prices = PortfolioService.fetch_current_prices(tickers)

        # Calculate holdings
        holdings = PortfolioService.calculate_aggregate_holdings(transactions, current_prices)

        return holdings

    @staticmethod
    def get_transaction_history(portfolio_name: str = "Default") -> List[Dict[str, Any]]:
        """
        Get full transaction history for a portfolio.

        Args:
            portfolio_name: Name of portfolio to load

        Returns:
            List of transaction dicts
        """
        from .portfolio_persistence import PortfolioPersistence

        portfolio = PortfolioPersistence.load_portfolio(portfolio_name)
        if not portfolio:
            return []

        return portfolio.get("transactions", [])

    @staticmethod
    def get_portfolio_value(portfolio_name: str = "Default") -> float:
        """
        Get total portfolio value.

        Args:
            portfolio_name: Name of portfolio to load

        Returns:
            Total market value (float)
        """
        holdings = PortfolioService.get_current_holdings_snapshot(portfolio_name)
        if not holdings:
            return 0.0

        totals = PortfolioService.calculate_portfolio_totals(holdings)
        return totals.get("total_market_value", 0.0)
