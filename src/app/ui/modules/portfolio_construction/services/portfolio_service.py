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

    # Special ticker for cash holdings (bypasses Yahoo Finance validation)
    FREE_CASH_TICKER = "FREE CASH"

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

        # Check entry price (0 is allowed for gifts)
        try:
            entry_price = float(transaction.get("entry_price", 0))
            if entry_price < 0:
                return False, "Entry price cannot be negative"
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

        # Group transactions by ticker (excluding FREE CASH - handled separately)
        ticker_transactions = defaultdict(list)
        for tx in transactions:
            ticker = tx["ticker"]
            if ticker.upper() == PortfolioService.FREE_CASH_TICKER:
                continue  # Skip FREE CASH - handled separately in calculate_free_cash_summary
            ticker_transactions[ticker].append(tx)

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

        Uses period="max" to leverage parquet caching for efficiency.
        Cache stored at ~/.quant_terminal/cache/{TICKER}.parquet
        FREE CASH ticker always returns $1.00 (no Yahoo fetch).

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> price (or None if fetch failed)
        """
        prices = {}

        for ticker in tickers:
            if not ticker:
                continue

            # FREE CASH is always $1.00 per unit
            if ticker == PortfolioService.FREE_CASH_TICKER:
                prices[ticker] = 1.0
                continue

            try:
                # Fetch full history (uses cache if current)
                df = fetch_price_history(ticker, period="max", interval="1d")

                if df is not None and not df.empty:
                    # Get last close price
                    prices[ticker] = float(df["Close"].iloc[-1])
                else:
                    prices[ticker] = None
            except Exception as e:
                print(f"Error fetching price for {ticker}: {e}")
                prices[ticker] = None

        return prices

    @staticmethod
    def is_valid_ticker(ticker: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a ticker is valid by attempting to fetch data from Yahoo Finance.
        FREE CASH ticker is always valid (bypasses Yahoo Finance).

        Args:
            ticker: Ticker symbol to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not ticker or not ticker.strip():
            return False, "Ticker cannot be empty"

        ticker = ticker.strip().upper()

        # FREE CASH is always valid (special cash ticker)
        if ticker == PortfolioService.FREE_CASH_TICKER:
            return True, None

        try:
            df = fetch_price_history(ticker, period="max", interval="1d")

            if df is None or df.empty:
                return False, f"No data found for ticker '{ticker}'"

            return True, None

        except Exception as e:
            return False, f"Failed to fetch data for '{ticker}': {str(e)}"

    @staticmethod
    def is_valid_trading_day(ticker: str, date_str: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a date is a valid trading day for a stock ticker.
        Crypto tickers (ending in -USD) and FREE CASH are exempt from this check.

        Args:
            ticker: Ticker symbol
            date_str: Date in ISO format (YYYY-MM-DD)

        Returns:
            Tuple of (is_valid, error_message)
        """
        import pandas as pd
        from datetime import datetime

        if not ticker or not date_str:
            return True, None  # Skip validation if missing data

        ticker = ticker.strip().upper()

        # FREE CASH can be transacted any day
        if ticker == PortfolioService.FREE_CASH_TICKER:
            return True, None

        # Crypto tickers (ending in -USD) trade 24/7, skip validation
        if ticker.endswith("-USD"):
            return True, None

        try:
            target_date = pd.to_datetime(date_str)

            # Check if it's a weekend
            if target_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                day_name = "Saturday" if target_date.weekday() == 5 else "Sunday"
                return False, f"{date_str} is a {day_name}. Stock markets are closed on weekends."

            # Fetch historical data to check if it's a trading day
            df = fetch_price_history(ticker, period="max", interval="1d")

            if df is None or df.empty:
                # Can't validate without data, allow it
                return True, None

            # Check if the exact date exists in the data (meaning it was a trading day)
            # Only check for dates that should have data (not future dates)
            today = pd.Timestamp.now().normalize()
            if target_date > today:
                return False, f"{date_str} is in the future."

            # Check if this date exists in the trading data
            if target_date in df.index:
                return True, None

            # Date not found - could be a holiday
            # Check if there are trading days before and after this date
            prior_dates = df.index[df.index < target_date]
            future_dates = df.index[df.index > target_date]

            if len(prior_dates) > 0 and len(future_dates) > 0:
                # There's data before and after, so this was likely a holiday
                return False, f"{date_str} appears to be a market holiday. Please select a valid trading day."

            # If date is before the first available data point
            if len(prior_dates) == 0 and len(future_dates) > 0:
                first_date = df.index.min().strftime("%Y-%m-%d")
                return False, f"No trading data available before {first_date} for '{ticker}'."

            return True, None

        except Exception as e:
            # On error, allow the date (don't block user due to technical issues)
            print(f"Error validating trading day: {e}")
            return True, None

    @staticmethod
    def fetch_historical_close_price(ticker: str, date_str: str) -> Optional[float]:
        """
        Fetch the closing price for a ticker on a specific date.
        FREE CASH ticker always returns $1.00.

        Args:
            ticker: Ticker symbol
            date_str: Date in ISO format (YYYY-MM-DD)

        Returns:
            Closing price on that date, or None if not available
        """
        import pandas as pd

        if not ticker or not date_str:
            return None

        # FREE CASH is always $1.00 per unit
        if ticker.upper() == PortfolioService.FREE_CASH_TICKER:
            return 1.0

        try:
            # Fetch full history (uses cache if current)
            df = fetch_price_history(ticker, period="max", interval="1d")

            if df is None or df.empty:
                return None

            # Convert date string to datetime for lookup
            target_date = pd.to_datetime(date_str)

            # Find the exact date or the closest previous trading day
            if target_date in df.index:
                return float(df.loc[target_date, "Close"])

            # If exact date not found, find closest previous date
            prior_dates = df.index[df.index <= target_date]
            if len(prior_dates) > 0:
                closest_date = prior_dates.max()
                return float(df.loc[closest_date, "Close"])

            return None

        except Exception as e:
            print(f"Error fetching historical price for {ticker} on {date_str}: {e}")
            return None

    @staticmethod
    def fetch_historical_closes_batch(
        ticker_dates: List[Tuple[str, str]]
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Batch fetch historical closing prices for multiple ticker/date pairs.
        FREE CASH ticker always returns $1.00 for any date.

        Args:
            ticker_dates: List of (ticker, date_str) tuples

        Returns:
            Dict of ticker -> {date -> close_price}
        """
        import pandas as pd

        results: Dict[str, Dict[str, Optional[float]]] = {}

        # Group by ticker to minimize fetches
        ticker_groups: Dict[str, List[str]] = {}
        for ticker, date_str in ticker_dates:
            if ticker not in ticker_groups:
                ticker_groups[ticker] = []
            if date_str not in ticker_groups[ticker]:
                ticker_groups[ticker].append(date_str)

        # Fetch each ticker once and extract all needed dates
        for ticker, dates in ticker_groups.items():
            if ticker not in results:
                results[ticker] = {}

            # FREE CASH is always $1.00 per unit
            if ticker.upper() == PortfolioService.FREE_CASH_TICKER:
                for date_str in dates:
                    results[ticker][date_str] = 1.0
                continue

            try:
                df = fetch_price_history(ticker, period="max", interval="1d")

                if df is None or df.empty:
                    for date_str in dates:
                        results[ticker][date_str] = None
                    continue

                for date_str in dates:
                    target_date = pd.to_datetime(date_str)

                    if target_date in df.index:
                        results[ticker][date_str] = float(df.loc[target_date, "Close"])
                    else:
                        prior_dates = df.index[df.index <= target_date]
                        if len(prior_dates) > 0:
                            closest_date = prior_dates.max()
                            results[ticker][date_str] = float(df.loc[closest_date, "Close"])
                        else:
                            results[ticker][date_str] = None

            except Exception as e:
                print(f"Error fetching historical prices for {ticker}: {e}")
                for date_str in dates:
                    results[ticker][date_str] = None

        return results

    @staticmethod
    def calculate_principal(transaction: Dict[str, Any]) -> float:
        """
        Calculate principal for a transaction.

        Principal = quantity * execution_price, signed by transaction type:
        - Buy: (quantity * execution_price + fees) [money spent, positive]
        - Sell: -(quantity * execution_price - fees) [money received, negative]

        Args:
            transaction: Transaction dict with quantity, entry_price, fees, transaction_type

        Returns:
            Principal value (positive for Buy, negative for Sell)
        """
        quantity = float(transaction.get("quantity", 0))
        execution_price = float(transaction.get("entry_price", 0))
        fees = float(transaction.get("fees", 0))
        transaction_type = transaction.get("transaction_type", "Buy")

        if transaction_type == "Buy":
            # Money spent (positive)
            return (quantity * execution_price + fees)
        else:
            # Money received (negative)
            return -(quantity * execution_price - fees)

    # Import functionality

    @staticmethod
    def generate_imported_transactions(
        transactions: List[Dict[str, Any]],
        include_fees: bool
    ) -> List[Dict[str, Any]]:
        """
        Clone transactions with new UUIDs for full history import.

        Args:
            transactions: Source portfolio transactions
            include_fees: Whether to include original fees

        Returns:
            List of cloned transactions with new UUIDs
        """
        result = []
        for tx in transactions:
            new_tx = {
                "id": str(uuid.uuid4()),
                "date": tx.get("date", ""),
                "ticker": tx.get("ticker", "").strip().upper(),
                "transaction_type": tx.get("transaction_type", "Buy"),
                "quantity": float(tx.get("quantity", 0)),
                "entry_price": float(tx.get("entry_price", 0)),
                "fees": float(tx.get("fees", 0)) if include_fees else 0.0
            }
            result.append(new_tx)
        return result

    @staticmethod
    def process_flat_import(
        transactions: List[Dict[str, Any]],
        include_fees: bool,
        skip_zero_positions: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Consolidate transactions into flat positions with average cost basis.

        Args:
            transactions: Source portfolio transactions
            include_fees: Whether to sum fees for each ticker
            skip_zero_positions: Whether to skip tickers with net zero quantity

        Returns:
            List of consolidated transactions (one per ticker)
        """
        from datetime import datetime

        # Group transactions by ticker
        by_ticker: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for tx in transactions:
            ticker = tx.get("ticker", "").strip().upper()
            if ticker:
                by_ticker[ticker].append(tx)

        result = []
        today = datetime.now().strftime("%Y-%m-%d")

        for ticker, txs in by_ticker.items():
            # Calculate net quantity
            buy_qty = sum(
                float(tx.get("quantity", 0))
                for tx in txs
                if tx.get("transaction_type") == "Buy"
            )
            sell_qty = sum(
                float(tx.get("quantity", 0))
                for tx in txs
                if tx.get("transaction_type") == "Sell"
            )
            net_qty = buy_qty - sell_qty

            # Skip zero positions if flag is set
            if skip_zero_positions and abs(net_qty) < 0.0001:
                continue

            # Calculate average cost basis (BUY prices only, weighted)
            buy_txs = [tx for tx in txs if tx.get("transaction_type") == "Buy"]
            if buy_txs:
                total_cost = sum(
                    float(tx.get("quantity", 0)) * float(tx.get("entry_price", 0))
                    for tx in buy_txs
                )
                total_buy_qty = sum(float(tx.get("quantity", 0)) for tx in buy_txs)
                avg_cost = total_cost / total_buy_qty if total_buy_qty > 0 else 0
            else:
                avg_cost = 0

            # Sum fees if requested
            total_fees = (
                sum(float(tx.get("fees", 0)) for tx in txs)
                if include_fees
                else 0
            )

            result.append({
                "id": str(uuid.uuid4()),
                "date": today,
                "ticker": ticker,
                "transaction_type": "Buy" if net_qty > 0 else "Sell",
                "quantity": abs(net_qty),
                "entry_price": avg_cost,
                "fees": total_fees
            })

        return result

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

    @staticmethod
    def calculate_free_cash_summary(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate FREE CASH summary values for the summary row.

        Only tracks FREE CASH transaction money flow:
        - Buy (deposit): adds (qty - fees) to cash position
        - Sell (withdrawal): removes (qty + fees) from cash position

        Principal = Market Value = Quantity (all same for cash at $1/unit)

        Args:
            transactions: List of all transactions

        Returns:
            Dict with ticker, quantity, principal, market_value
        """
        free_cash_balance = 0.0  # Net FREE CASH position

        for tx in transactions:
            ticker = tx.get("ticker", "").upper()
            tx_type = tx.get("transaction_type", "")
            qty = float(tx.get("quantity", 0))
            fees = float(tx.get("fees", 0))

            if ticker == PortfolioService.FREE_CASH_TICKER:
                if tx_type == "Buy":  # Deposit
                    # Deposit: add qty, subtract fees paid
                    free_cash_balance += qty - fees
                else:  # Sell = Withdrawal
                    # Withdrawal: subtract qty, subtract fees paid
                    free_cash_balance -= (qty + fees)

        return {
            "ticker": PortfolioService.FREE_CASH_TICKER,
            "quantity": free_cash_balance,  # Cash = $1 per unit
            "principal": free_cash_balance,
            "market_value": free_cash_balance
        }
