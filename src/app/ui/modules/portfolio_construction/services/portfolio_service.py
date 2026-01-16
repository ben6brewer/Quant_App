"""Portfolio Service - Business Logic and Calculations"""

import uuid
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        notes: str = "",
        sequence: int = 0
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
            sequence: Ordering number for same-day transactions (higher = newer)

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
            "notes": notes.strip(),
            "sequence": sequence
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
        Fetch current prices for tickers using MarketDataService with parallel fetching.

        Uses period="max" to leverage parquet caching for efficiency.
        Cache stored at ~/.quant_terminal/cache/{TICKER}.parquet
        FREE CASH ticker always returns $1.00 (no Yahoo fetch).
        Fetches multiple tickers in parallel using ThreadPoolExecutor.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> price (or None if fetch failed)
        """
        if not tickers:
            return {}

        prices = {}

        # Filter out empty tickers and handle FREE CASH separately
        real_tickers = []
        for ticker in tickers:
            if not ticker:
                continue
            if ticker.upper() == PortfolioService.FREE_CASH_TICKER:
                prices[ticker] = 1.0
            else:
                real_tickers.append(ticker)

        if not real_tickers:
            return prices

        def fetch_single_price(ticker: str) -> Tuple[str, Optional[float]]:
            try:
                # skip_live_bar=True to avoid Polygon rate limiting for portfolio ops
                df = fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)
                if df is not None and not df.empty:
                    return ticker, float(df["Close"].iloc[-1])
            except Exception as e:
                print(f"Error fetching price for {ticker}: {e}")
            return ticker, None

        # Parallel fetch using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_single_price, t) for t in real_tickers]
            for future in as_completed(futures):
                ticker, price = future.result()
                prices[ticker] = price

        return prices

    @staticmethod
    def fetch_ticker_names(tickers: List[str]) -> Dict[str, Optional[str]]:
        """
        Fetch short names for tickers using TickerMetadataService cache.

        Uses the shared metadata cache populated during Yahoo backfill.
        If not cached, fetches from yfinance and caches for future use.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> short name (or None if fetch failed)
        """
        from app.services.ticker_metadata_service import TickerMetadataService

        if not tickers:
            return {}

        result: Dict[str, Optional[str]] = {}

        # Separate FREE CASH (special case) from real tickers
        real_tickers = []
        for t in tickers:
            if not t:
                continue
            if t.upper() == PortfolioService.FREE_CASH_TICKER:
                result[t] = None
            else:
                real_tickers.append(t)

        if not real_tickers:
            return result

        # Get metadata for all tickers (uses cache, fetches if missing)
        metadata_batch = TickerMetadataService.get_metadata_batch(real_tickers)

        # Extract shortName from metadata
        for ticker in real_tickers:
            ticker_upper = ticker.upper()
            if ticker_upper in metadata_batch:
                result[ticker] = metadata_batch[ticker_upper].get("shortName")
            else:
                result[ticker] = None

        return result

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

        # Reject tickers with spaces (except FREE CASH which is already handled above)
        # Spaces cause yfinance to interpret as multiple tickers
        if " " in ticker:
            return False, f"Invalid ticker '{ticker}'. Ticker symbols cannot contain spaces."

        try:
            # skip_live_bar=True to avoid Polygon rate limiting for portfolio ops
            df = fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)

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
            # skip_live_bar=True to avoid Polygon rate limiting for portfolio ops
            df = fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)

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
            # skip_live_bar=True to avoid Polygon rate limiting for portfolio ops
            df = fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)

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
        Fetches multiple tickers in parallel using ThreadPoolExecutor.

        Args:
            ticker_dates: List of (ticker, date_str) tuples

        Returns:
            Dict of ticker -> {date -> close_price}
        """
        import pandas as pd

        if not ticker_dates:
            return {}

        results: Dict[str, Dict[str, Optional[float]]] = {}

        # Group by ticker to minimize fetches
        ticker_groups: Dict[str, List[str]] = {}
        for ticker, date_str in ticker_dates:
            if ticker not in ticker_groups:
                ticker_groups[ticker] = []
            if date_str not in ticker_groups[ticker]:
                ticker_groups[ticker].append(date_str)

        # Handle FREE CASH separately (no API call needed)
        real_ticker_groups: Dict[str, List[str]] = {}
        for ticker, dates in ticker_groups.items():
            if ticker.upper() == PortfolioService.FREE_CASH_TICKER:
                results[ticker] = {d: 1.0 for d in dates}
            else:
                real_ticker_groups[ticker] = dates

        if not real_ticker_groups:
            return results

        def fetch_ticker_dates(
            ticker: str, dates: List[str]
        ) -> Tuple[str, Dict[str, Optional[float]]]:
            """Fetch all needed dates for a single ticker."""
            date_prices: Dict[str, Optional[float]] = {}
            try:
                # skip_live_bar=True to avoid Polygon rate limiting for portfolio ops
                df = fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)

                if df is None or df.empty:
                    return ticker, {d: None for d in dates}

                for date_str in dates:
                    target_date = pd.to_datetime(date_str)

                    if target_date in df.index:
                        date_prices[date_str] = float(df.loc[target_date, "Close"])
                    else:
                        prior_dates = df.index[df.index <= target_date]
                        if len(prior_dates) > 0:
                            closest_date = prior_dates.max()
                            date_prices[date_str] = float(df.loc[closest_date, "Close"])
                        else:
                            date_prices[date_str] = None

            except Exception as e:
                print(f"Error fetching historical prices for {ticker}: {e}")
                return ticker, {d: None for d in dates}

            return ticker, date_prices

        # Parallel fetch using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(fetch_ticker_dates, ticker, dates)
                for ticker, dates in real_ticker_groups.items()
            ]
            for future in as_completed(futures):
                ticker, date_prices = future.result()
                results[ticker] = date_prices

        return results

    @staticmethod
    def get_first_available_date(ticker: str) -> Optional[str]:
        """
        Get the first available date for a ticker's price history.

        Args:
            ticker: Ticker symbol

        Returns:
            Date string in YYYY-MM-DD format, or None if no data available
        """
        try:
            # skip_live_bar=True to avoid Polygon rate limiting for portfolio ops
            df = fetch_price_history(ticker, period="max", interval="1d", skip_live_bar=True)
            if df is None or df.empty:
                return None
            return df.index.min().strftime("%Y-%m-%d")
        except Exception:
            return None

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

        Tracks all transaction money flow to show true cash position:

        FREE CASH transactions:
        - Buy (deposit): adds (qty - fees) to cash
        - Sell (withdrawal): removes (qty + fees) from cash

        Regular security transactions:
        - Buy: subtracts (qty * price + fees) from cash
        - Sell: adds (qty * price - fees) to cash

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
            price = float(tx.get("entry_price", 0))
            fees = float(tx.get("fees", 0))

            if ticker == PortfolioService.FREE_CASH_TICKER:
                # FREE CASH transactions (price is always $1)
                if tx_type == "Buy":  # Deposit
                    free_cash_balance += qty - fees
                else:  # Sell = Withdrawal
                    free_cash_balance -= (qty + fees)
            else:
                # Regular security transactions affect cash position
                if tx_type == "Buy":
                    # Buying securities costs cash
                    free_cash_balance -= (qty * price + fees)
                else:  # Sell
                    # Selling securities adds cash
                    free_cash_balance += (qty * price - fees)

        return {
            "ticker": PortfolioService.FREE_CASH_TICKER,
            "quantity": free_cash_balance,  # Cash = $1 per unit
            "principal": free_cash_balance,
            "market_value": free_cash_balance
        }

    @staticmethod
    def calculate_free_cash_at_date(
        transactions: List[Dict[str, Any]],
        target_date: str,
        exclude_transaction_id: Optional[str] = None
    ) -> float:
        """
        Calculate FREE CASH balance at a specific date.

        Args:
            transactions: List of all transactions
            target_date: Date string (YYYY-MM-DD) - include transactions on/before this date
            exclude_transaction_id: Optional transaction ID to exclude (for edit validation)

        Returns:
            FREE CASH balance as float (can be negative)
        """
        free_cash_balance = 0.0

        # Sort by date then sequence to ensure correct processing order
        sorted_txs = sorted(
            transactions,
            key=lambda t: (t.get("date", ""), t.get("sequence", 0))
        )


        for tx in sorted_txs:
            # Skip excluded transaction
            if exclude_transaction_id and tx.get("id") == exclude_transaction_id:
                continue

            # Only include transactions on or before target date
            tx_date = tx.get("date", "")
            if tx_date > target_date:
                continue

            ticker = tx.get("ticker", "").upper()
            tx_type = tx.get("transaction_type", "")
            qty = float(tx.get("quantity", 0))
            price = float(tx.get("entry_price", 0))
            fees = float(tx.get("fees", 0))

            if ticker == PortfolioService.FREE_CASH_TICKER:
                if tx_type == "Buy":  # Deposit
                    free_cash_balance += qty - fees
                else:  # Sell = Withdrawal
                    free_cash_balance -= (qty + fees)
            else:
                if tx_type == "Buy":
                    free_cash_balance -= (qty * price + fees)
                else:  # Sell
                    free_cash_balance += (qty * price - fees)

        return free_cash_balance

    @staticmethod
    def calculate_position_at_date(
        transactions: List[Dict[str, Any]],
        ticker: str,
        target_date: str,
        exclude_transaction_id: Optional[str] = None
    ) -> float:
        """
        Calculate share position for a ticker at a specific date.

        Args:
            transactions: List of all transactions
            ticker: Ticker symbol to calculate position for
            target_date: Date string (YYYY-MM-DD) - include transactions on/before this date
            exclude_transaction_id: Optional transaction ID to exclude (for edit validation)

        Returns:
            Net share position (can be negative for validation)
        """
        position = 0.0
        ticker_upper = ticker.upper()

        # Sort by date then sequence to ensure correct processing order
        sorted_txs = sorted(
            transactions,
            key=lambda t: (t.get("date", ""), t.get("sequence", 0))
        )

        for tx in sorted_txs:
            # Skip excluded transaction
            if exclude_transaction_id and tx.get("id") == exclude_transaction_id:
                continue

            # Only include transactions for this ticker
            if tx.get("ticker", "").upper() != ticker_upper:
                continue

            # Only include transactions on or before target date
            tx_date = tx.get("date", "")
            if tx_date > target_date:
                continue

            qty = float(tx.get("quantity", 0))
            tx_type = tx.get("transaction_type", "")

            if tx_type == "Buy":
                position += qty
            else:  # Sell
                position -= qty

        return position

    @staticmethod
    def get_transaction_priority(ticker: str, transaction_type: str) -> int:
        """
        Get processing priority for a transaction.

        Priority order (lower = processed first):
        0: FREE CASH Buy (deposit) - happens at start of day
        1: Regular Sell - sell first to free up cash
        2: Regular Buy - buy with available cash
        3: FREE CASH Sell (withdrawal) - happens at end of day

        Args:
            ticker: Transaction ticker
            transaction_type: "Buy" or "Sell"

        Returns:
            Priority value 0-3
        """
        is_free_cash = ticker.upper() == PortfolioService.FREE_CASH_TICKER
        if is_free_cash:
            return 0 if transaction_type == "Buy" else 3
        else:
            return 1 if transaction_type == "Sell" else 2

    @staticmethod
    def resequence_same_day_transactions(
        transactions: List[Dict[str, Any]],
        target_date: str
    ) -> Dict[str, int]:
        """
        Calculate new sequences for all transactions on a given date based on priority.

        Priority order:
        1. FREE CASH Buy (deposit)
        2. Regular Sells
        3. Regular Buys
        4. FREE CASH Sell (withdrawal)

        Within same priority, original sequence order is preserved.

        Args:
            transactions: All transactions to consider
            target_date: Date to resequence

        Returns:
            Dict mapping transaction_id -> new_sequence
        """
        same_day_txs = [t for t in transactions if t.get("date") == target_date]
        if not same_day_txs:
            return {}

        # Sort by (priority, original_sequence) to maintain order within priority
        def sort_key(tx):
            ticker = tx.get("ticker", "")
            tx_type = tx.get("transaction_type", "Buy")
            priority = PortfolioService.get_transaction_priority(ticker, tx_type)
            sequence = tx.get("sequence", 0)
            return (priority, sequence)

        sorted_txs = sorted(same_day_txs, key=sort_key)

        # Assign new sequences 0, 1, 2, ...
        return {tx.get("id"): idx for idx, tx in enumerate(sorted_txs)}

    @staticmethod
    def get_sequence_for_date_edit(
        transactions: List[Dict[str, Any]],
        target_date: str,
        is_free_cash: bool,
        transaction_type: str = "Buy"
    ) -> int:
        """
        Get appropriate sequence for a transaction whose date was edited.

        Sequences are assigned based on transaction priority:
        - FREE CASH Buy (deposit): Priority 0 (first)
        - Regular Sell: Priority 1 (second)
        - Regular Buy: Priority 2 (third)
        - FREE CASH Sell (withdrawal): Priority 3 (last)

        Args:
            transactions: All transactions (excluding the one being edited)
            target_date: The new date being set
            is_free_cash: Whether this is a FREE CASH transaction
            transaction_type: "Buy" or "Sell"

        Returns:
            Sequence number for the transaction
        """
        same_day_txs = [t for t in transactions if t.get("date") == target_date]
        if not same_day_txs:
            return 0

        # Get this transaction's priority
        ticker = PortfolioService.FREE_CASH_TICKER if is_free_cash else "OTHER"
        my_priority = PortfolioService.get_transaction_priority(ticker, transaction_type)

        # Find sequences grouped by priority
        priority_sequences = {0: [], 1: [], 2: [], 3: []}
        for tx in same_day_txs:
            tx_ticker = tx.get("ticker", "")
            tx_type = tx.get("transaction_type", "Buy")
            tx_priority = PortfolioService.get_transaction_priority(tx_ticker, tx_type)
            priority_sequences[tx_priority].append(tx.get("sequence", 0))

        # Determine sequence based on priority
        # We want to slot in after all transactions with lower priority
        # and before all transactions with higher priority
        if my_priority == 0:
            # FREE CASH Buy: before everything
            all_seqs = [s for seqs in priority_sequences.values() for s in seqs]
            return min(all_seqs) - 1 if all_seqs else 0
        elif my_priority == 3:
            # FREE CASH Sell: after everything
            all_seqs = [s for seqs in priority_sequences.values() for s in seqs]
            return max(all_seqs) + 1 if all_seqs else 0
        else:
            # Regular Sell (1) or Regular Buy (2)
            # Find max sequence of same or lower priority
            lower_or_same = []
            for p in range(my_priority + 1):
                lower_or_same.extend(priority_sequences[p])

            if lower_or_same:
                return max(lower_or_same) + 1
            else:
                # No lower priority transactions, go before higher priority
                higher = []
                for p in range(my_priority + 1, 4):
                    higher.extend(priority_sequences[p])
                if higher:
                    return min(higher) - 1
                return 0

    @staticmethod
    def validate_transaction_safeguards(
        transactions: List[Dict[str, Any]],
        transaction: Dict[str, Any],
        is_new: bool = False,
        original_date: str = ""
    ) -> Tuple[bool, str]:
        """
        Validate transaction safeguards (cash balance, position, chain).

        Args:
            transactions: List of all existing transactions
            transaction: Transaction to validate (new or edited)
            is_new: True if this is a new transaction
            original_date: Original date before edit (for detecting date adjustments)

        Returns:
            Tuple of (is_valid, error_message)
        """
        tx_id = transaction.get("id")
        tx_date = transaction.get("date", "")
        ticker = transaction.get("ticker", "").upper()
        tx_type = transaction.get("transaction_type", "")
        qty = float(transaction.get("quantity", 0))
        price = float(transaction.get("entry_price", 0))
        fees = float(transaction.get("fees", 0))

        # Build transaction list for validation
        # Exclude current transaction if editing, we'll add the new version
        if is_new:
            test_transactions = list(transactions)
        else:
            test_transactions = [tx for tx in transactions if tx.get("id") != tx_id]

        # Calculate cash before this transaction
        cash_before = PortfolioService.calculate_free_cash_at_date(
            test_transactions, tx_date
        )

        # Validate based on transaction type
        if ticker == PortfolioService.FREE_CASH_TICKER:
            if tx_type == "Sell":  # Withdrawal
                withdrawal_amount = qty + fees
                if cash_before < withdrawal_amount:
                    return (
                        False,
                        f"Cannot withdraw ${qty:,.2f}. "
                        f"Only ${max(0, cash_before):,.2f} is available on {tx_date}."
                    )
        else:
            # Regular security transaction
            if tx_type == "Sell":
                # Check position before this transaction
                position_before = PortfolioService.calculate_position_at_date(
                    test_transactions, ticker, tx_date
                )
                if position_before < qty:
                    return (
                        False,
                        f"Cannot sell {qty:,.4f} shares of {ticker}. "
                        f"You only have {max(0, position_before):,.4f} shares available on {tx_date}."
                    )
                # Also check that the sale proceeds minus fees don't cause issues
                # (the cash impact is positive for sells, so usually not an issue)

            elif tx_type == "Buy":
                # Check if we have enough cash to buy
                cost = qty * price + fees
                if cash_before < cost:
                    return (
                        False,
                        f"Cannot complete this purchase. "
                        f"You would need ${cost:,.2f} but only have ${max(0, cash_before):,.2f} available on {tx_date}."
                    )

        # If editing an existing transaction, validate the chain
        if not is_new:
            # Detect FREE CASH deposit date adjustment (moving date backwards)
            # This is a special case where user is adjusting when cash was deposited
            # Moving a deposit date backwards should always be allowed as it only
            # makes cash available earlier (helps subsequent transactions)
            is_free_cash_deposit_moving_back = (
                ticker == PortfolioService.FREE_CASH_TICKER
                and tx_type == "Buy"
                and original_date
                and tx_date <= original_date
            )

            # Detect FREE CASH deposit moving forward - need to validate from original date
            # to catch any transactions that would now be before the deposit
            is_free_cash_deposit_moving_forward = (
                ticker == PortfolioService.FREE_CASH_TICKER
                and tx_type == "Buy"
                and original_date
                and tx_date > original_date
            )

            # Pass original_date when moving forward so validation starts from there
            validation_start_date = original_date if is_free_cash_deposit_moving_forward else ""

            chain_valid, chain_error = PortfolioService.validate_transaction_chain(
                transactions, transaction, is_free_cash_deposit_moving_back, validation_start_date
            )
            if not chain_valid:
                return (False, chain_error)

        return (True, "")

    @staticmethod
    def validate_transaction_chain(
        transactions: List[Dict[str, Any]],
        edited_transaction: Dict[str, Any],
        skip_validation: bool = False,
        validation_start_date: str = ""
    ) -> Tuple[bool, str]:
        """
        Validate that editing a transaction doesn't break subsequent transactions.

        Args:
            transactions: List of all transactions (with edited transaction already updated)
            edited_transaction: The transaction that was edited
            skip_validation: True to skip chain validation entirely (e.g., FREE CASH deposit
                moving to an earlier date)
            validation_start_date: Override date to start validation from. Used when a
                FREE CASH deposit moves forward - validation must start from the original
                date to catch transactions that would now be before the deposit.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # When adjusting a FREE CASH deposit date backwards, skip chain validation
        # Moving a deposit earlier only makes cash available sooner, which can only
        # help (not break) subsequent transactions
        if skip_validation:
            return (True, "")

        edit_date = edited_transaction.get("date", "")
        edit_id = edited_transaction.get("id")

        # Use validation_start_date if provided (for FREE CASH deposit moving forward)
        # This ensures we validate transactions between old and new dates
        check_from_date = validation_start_date if validation_start_date else edit_date

        # Build list: remove old version, add edited version
        # This ensures the edited transaction is at its NEW date, not OLD date
        filtered_transactions = [tx for tx in transactions if tx.get("id") != edit_id]
        all_transactions = filtered_transactions + [edited_transaction]

        # Sort by date, then sequence for same-day ordering
        sorted_txs = sorted(all_transactions, key=lambda x: (x.get("date", ""), x.get("sequence", 0)))

        # Track running balances
        cash_balance = 0.0
        positions: Dict[str, float] = {}  # ticker -> position

        for tx in sorted_txs:
            tx_date = tx.get("date", "")
            ticker = tx.get("ticker", "").upper()
            tx_type = tx.get("transaction_type", "")
            qty = float(tx.get("quantity", 0))
            price = float(tx.get("entry_price", 0))
            fees = float(tx.get("fees", 0))

            if ticker == PortfolioService.FREE_CASH_TICKER:
                if tx_type == "Buy":  # Deposit
                    cash_balance += qty - fees
                else:  # Sell = Withdrawal
                    # Validate before applying
                    withdrawal = qty + fees
                    if cash_balance < withdrawal and tx_date >= check_from_date:
                        return (
                            False,
                            f"This change would cause insufficient cash for withdrawal on {tx_date}.\n"
                            f"Available: ${max(0, cash_balance):,.2f}, Needed: ${withdrawal:,.2f}"
                        )
                    cash_balance -= withdrawal
            else:
                if ticker not in positions:
                    positions[ticker] = 0.0

                if tx_type == "Buy":
                    cost = qty * price + fees
                    # Validate cash before applying
                    if cash_balance < cost and tx_date >= check_from_date:
                        return (
                            False,
                            f"This change would cause insufficient cash for {ticker} purchase on {tx_date}.\n"
                            f"Available: ${max(0, cash_balance):,.2f}, Needed: ${cost:,.2f}"
                        )
                    cash_balance -= cost
                    positions[ticker] += qty
                else:  # Sell
                    # Validate position before applying
                    if positions[ticker] < qty and tx_date >= check_from_date:
                        return (
                            False,
                            f"This change would cause insufficient shares for {ticker} sale on {tx_date}.\n"
                            f"Available: {max(0, positions[ticker]):,.4f}, Needed: {qty:,.4f}"
                        )
                    positions[ticker] -= qty
                    proceeds = qty * price - fees
                    cash_balance += proceeds

        return (True, "")

    @staticmethod
    def validate_transaction_deletion(
        transactions: List[Dict[str, Any]],
        transaction_to_delete: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate that deleting a transaction won't break the portfolio.

        This is especially important for FREE CASH deposits - deleting one
        could leave subsequent transactions without sufficient funds.

        Args:
            transactions: List of all current transactions
            transaction_to_delete: The transaction being deleted

        Returns:
            Tuple of (can_delete, error_message)
        """
        delete_id = transaction_to_delete.get("id")
        delete_ticker = transaction_to_delete.get("ticker", "").upper()
        delete_type = transaction_to_delete.get("transaction_type", "")
        delete_date = transaction_to_delete.get("date", "")

        # Build list without the transaction to delete
        remaining_transactions = [
            tx for tx in transactions if tx.get("id") != delete_id
        ]

        # If no remaining transactions, deletion is always valid
        if not remaining_transactions:
            return (True, "")

        # Sort by date
        sorted_txs = sorted(remaining_transactions, key=lambda x: x.get("date", ""))

        # Track running balances
        cash_balance = 0.0
        positions: Dict[str, float] = {}

        # Find first problem after the deletion date
        for tx in sorted_txs:
            tx_date = tx.get("date", "")
            ticker = tx.get("ticker", "").upper()
            tx_type = tx.get("transaction_type", "")
            qty = float(tx.get("quantity", 0))
            price = float(tx.get("entry_price", 0))
            fees = float(tx.get("fees", 0))

            if ticker == PortfolioService.FREE_CASH_TICKER:
                if tx_type == "Buy":  # Deposit
                    cash_balance += qty - fees
                else:  # Sell = Withdrawal
                    withdrawal = qty + fees
                    if cash_balance < withdrawal and tx_date >= delete_date:
                        return (
                            False,
                            f"Cannot delete this deposit. It would cause insufficient cash "
                            f"for withdrawal on {tx_date}.\n\n"
                            f"Available: ${max(0, cash_balance):,.2f}, Needed: ${withdrawal:,.2f}\n\n"
                            f"Please delete or modify transactions that depend on this cash first."
                        )
                    cash_balance -= withdrawal
            else:
                if ticker not in positions:
                    positions[ticker] = 0.0

                if tx_type == "Buy":
                    cost = qty * price + fees
                    if cash_balance < cost and tx_date >= delete_date:
                        return (
                            False,
                            f"Cannot delete this deposit. It would cause insufficient cash "
                            f"for {ticker} purchase on {tx_date}.\n\n"
                            f"Available: ${max(0, cash_balance):,.2f}, Needed: ${cost:,.2f}\n\n"
                            f"Please delete or modify transactions that depend on this cash first."
                        )
                    cash_balance -= cost
                    positions[ticker] += qty
                else:  # Sell
                    if positions[ticker] < qty and tx_date >= delete_date:
                        return (
                            False,
                            f"Cannot delete this transaction. It would cause insufficient shares "
                            f"for {ticker} sale on {tx_date}.\n\n"
                            f"Available: {max(0, positions[ticker]):,.4f}, Needed: {qty:,.4f}\n\n"
                            f"Please delete or modify transactions that depend on this position first."
                        )
                    positions[ticker] -= qty
                    proceeds = qty * price - fees
                    cash_balance += proceeds

        return (True, "")
