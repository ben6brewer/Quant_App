from __future__ import annotations

import requests
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class BinanceOrderBook:
    """
    Service for fetching order book depth data from Binance.
    
    Free API with no authentication required.
    Rate limit: 1200 requests per minute (20/second)
    
    Supports both Binance.com (international) and Binance.US (US users).
    Will automatically try Binance.US if Binance.com is blocked (451 error).
    """
    
    BASE_URL_INTL = "https://api.binance.com"
    BASE_URL_US = "https://api.binance.us"
    
    # Mapping from yfinance ticker format to Binance symbol format
    TICKER_MAP = {
        "BTC-USD": "BTCUSDT",
        "ETH-USD": "ETHUSDT",
        "BNB-USD": "BNBUSDT",
        "XRP-USD": "XRPUSDT",
        "ADA-USD": "ADAUSDT",
        "DOGE-USD": "DOGEUSDT",
        "SOL-USD": "SOLUSDT",
        "DOT-USD": "DOTUSDT",
        "MATIC-USD": "MATICUSDT",
        "LTC-USD": "LTCUSDT",
        "AVAX-USD": "AVAXUSDT",
        "LINK-USD": "LINKUSDT",
        "UNI-USD": "UNIUSDT",
        "ATOM-USD": "ATOMUSDT",
        "XLM-USD": "XLMUSDT",
        "ALGO-USD": "ALGOUSDT",
        "VET-USD": "VETUSDT",
        "ICP-USD": "ICPUSDT",
        "FIL-USD": "FILUSDT",
        "TRX-USD": "TRXUSDT",
    }
    
    def __init__(self, prefer_us_api: bool = True):
        """
        Initialize the Binance order book service.
        
        Args:
            prefer_us_api: If True (default), try Binance.US first, then fallback to Binance.com.
                          If False, try Binance.com first, then fallback to Binance.US.
        """
        self._cache = {}
        self._cache_duration = timedelta(seconds=5)  # Cache for 5 seconds
        self.prefer_us_api = prefer_us_api
        
        # Track which API is currently working
        self._working_base_url = None
    
    def _get_base_url(self) -> str:
        """Get the base URL to use, with automatic fallback."""
        if self._working_base_url:
            return self._working_base_url
        
        # Default based on preference
        return self.BASE_URL_US if self.prefer_us_api else self.BASE_URL_INTL
    
    def _try_fallback_url(self, primary_url: str) -> str:
        """Get the fallback URL if primary fails."""
        if primary_url == self.BASE_URL_US:
            return self.BASE_URL_INTL
        else:
            return self.BASE_URL_US
    
    @classmethod
    def is_binance_ticker(cls, ticker: str) -> bool:
        """Check if a ticker is supported by Binance."""
        ticker = ticker.strip().upper()
        return ticker in cls.TICKER_MAP
    
    @classmethod
    def get_binance_symbol(cls, ticker: str) -> Optional[str]:
        """Convert yfinance ticker to Binance symbol."""
        ticker = ticker.strip().upper()
        return cls.TICKER_MAP.get(ticker)
    
    def fetch_order_book(
        self, ticker: str, limit: int = 100
    ) -> Optional[Dict[str, List[Tuple[float, float]]]]:
        """
        Fetch order book depth data from Binance.
        
        Automatically handles geo-blocking by trying both Binance.com and Binance.US.
        
        Args:
            ticker: yfinance format ticker (e.g., "BTC-USD")
            limit: Number of price levels (5, 10, 20, 50, 100, 500, 1000, 5000)
        
        Returns:
            Dict with 'bids' and 'asks' as lists of (price, quantity) tuples,
            or None if fetch fails
        """
        # Check cache first
        cache_key = f"{ticker}_{limit}"
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if datetime.now() - cached_time < self._cache_duration:
                return cached_data
        
        # Get Binance symbol
        symbol = self.get_binance_symbol(ticker)
        if not symbol:
            return None
        
        # Validate limit
        valid_limits = [5, 10, 20, 50, 100, 500, 1000, 5000]
        if limit not in valid_limits:
            limit = 100  # Default
        
        # Try primary URL first
        primary_url = self._get_base_url()
        result = self._fetch_from_url(primary_url, symbol, limit)
        
        if result is not None:
            # Success! Remember this URL works
            self._working_base_url = primary_url
            
            # Cache the result
            self._cache[cache_key] = (result, datetime.now())
            return result
        
        # Primary failed - try fallback if we haven't locked to a working URL
        if self._working_base_url is None:
            fallback_url = self._try_fallback_url(primary_url)
            print(f"Primary Binance API failed, trying fallback: {fallback_url}")
            
            result = self._fetch_from_url(fallback_url, symbol, limit)
            
            if result is not None:
                # Fallback worked! Remember it
                self._working_base_url = fallback_url
                print(f"Successfully connected using {fallback_url}")
                
                # Cache the result
                self._cache[cache_key] = (result, datetime.now())
                return result
        
        # Both failed
        return None
    
    def _fetch_from_url(
        self, base_url: str, symbol: str, limit: int
    ) -> Optional[Dict[str, List[Tuple[float, float]]]]:
        """
        Fetch order book from a specific Binance API URL.
        
        Returns None if fetch fails (including geo-blocking).
        """
        try:
            url = f"{base_url}/api/v3/depth"
            params = {"symbol": symbol, "limit": limit}
            
            response = requests.get(url, params=params, timeout=5)
            
            # Check for geo-blocking (451 error)
            if response.status_code == 451:
                api_name = "Binance.US" if "binance.us" in base_url else "Binance.com"
                print(f"{api_name} is geo-blocked in your region (HTTP 451)")
                return None
            
            response.raise_for_status()
            
            data = response.json()
            
            # Parse bids and asks
            # Format: [["price", "quantity"], ...]
            bids = [(float(price), float(qty)) for price, qty in data.get("bids", [])]
            asks = [(float(price), float(qty)) for price, qty in data.get("asks", [])]
            
            return {
                "bids": bids,  # Sorted descending by price
                "asks": asks,  # Sorted ascending by price
                "timestamp": datetime.now(),
                "source": base_url,  # Track which API we used
            }
            
        except requests.exceptions.RequestException as e:
            # Don't print error here - let caller handle fallback
            return None
        except (KeyError, ValueError) as e:
            print(f"Error parsing Binance order book data: {e}")
            return None
    
    def get_depth_summary(
        self, ticker: str, levels: int = 10
    ) -> Optional[Dict[str, any]]:
        """
        Get a summary of order book depth.
        
        Args:
            ticker: yfinance format ticker
            levels: Number of levels to include in summary
        
        Returns:
            Dict with summary statistics
        """
        data = self.fetch_order_book(ticker, limit=levels)
        if not data:
            return None
        
        bids = data["bids"][:levels]
        asks = data["asks"][:levels]
        
        # Calculate total volume at each side
        bid_volume = sum(qty for _, qty in bids)
        ask_volume = sum(qty for _, qty in asks)
        
        # Calculate weighted average prices
        bid_weighted_price = (
            sum(price * qty for price, qty in bids) / bid_volume if bid_volume > 0 else 0
        )
        ask_weighted_price = (
            sum(price * qty for price, qty in asks) / ask_volume if ask_volume > 0 else 0
        )
        
        # Get best bid/ask
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        
        # Calculate spread
        spread = best_ask - best_bid if best_bid and best_ask else 0
        spread_pct = (spread / best_bid * 100) if best_bid else 0
        
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "spread_pct": spread_pct,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
            "bid_weighted_price": bid_weighted_price,
            "ask_weighted_price": ask_weighted_price,
            "bids": bids,
            "asks": asks,
            "timestamp": data["timestamp"],
            "source": data.get("source", "unknown"),  # Which API was used
        }
    
    def get_api_status(self) -> Dict[str, any]:
        """
        Get information about which Binance API is currently working.
        
        Returns:
            Dict with API status information
        """
        return {
            "working_url": self._working_base_url,
            "prefer_us": self.prefer_us_api,
            "is_us_api": self._working_base_url == self.BASE_URL_US if self._working_base_url else None,
        }
    
    def clear_cache(self):
        """Clear the order book cache."""
        self._cache.clear()
    
    def reset_api_selection(self):
        """Reset the API selection to allow re-trying both endpoints."""
        self._working_base_url = None
        print("Reset Binance API selection - will try both endpoints again")