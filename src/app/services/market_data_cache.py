from __future__ import annotations

import pandas as pd
from pathlib import Path
from datetime import datetime


class MarketDataCache:
    """
    Cache manager for market data using parquet format.
    Stores daily OHLCV data to speed up subsequent requests and enable offline usage.
    """
    
    # Cache directory
    _CACHE_DIR = Path.home() / ".quant_terminal" / "cache"
    
    def __init__(self):
        """Initialize the cache manager and create cache directory if needed."""
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        self._CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, ticker: str) -> Path:
        """
        Get the cache file path for a ticker.
        
        Args:
            ticker: Ticker symbol (e.g., "BTC-USD")
        
        Returns:
            Path to the cache file
        """
        # Sanitize ticker for filename (replace problematic characters)
        safe_ticker = ticker.replace("/", "_").replace("\\", "_")
        return self._CACHE_DIR / f"{safe_ticker}.parquet"
    
    def has_cache(self, ticker: str) -> bool:
        """
        Check if a cache file exists for this ticker.
        
        Args:
            ticker: Ticker symbol
        
        Returns:
            True if cache exists, False otherwise
        """
        return self._get_cache_path(ticker).exists()
    
    def get_cached_data(self, ticker: str) -> pd.DataFrame | None:
        """
        Load cached data for a ticker.
        
        Args:
            ticker: Ticker symbol
        
        Returns:
            DataFrame with cached OHLCV data, or None if not found
        """
        cache_path = self._get_cache_path(ticker)
        
        if not cache_path.exists():
            return None
        
        try:
            df = pd.read_parquet(cache_path)
            # Ensure index is DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            print(f"Error reading cache for {ticker}: {e}")
            return None
    
    def is_cache_current(self, ticker: str) -> bool:
        """
        Check if cached data is current (last date >= today).
        
        Args:
            ticker: Ticker symbol
        
        Returns:
            True if cache is current, False otherwise
        """
        df = self.get_cached_data(ticker)
        
        if df is None or df.empty:
            return False
        
        # Get the last date in cache
        last_date = df.index.max()
        
        # Get today's date (without time component)
        today = pd.Timestamp(datetime.now().date())
        
        # Cache is current if last date is today or later
        return last_date >= today
    
    def get_last_cached_date(self, ticker: str) -> pd.Timestamp | None:
        """
        Get the last date in cached data.
        
        Args:
            ticker: Ticker symbol
        
        Returns:
            Last cached date, or None if no cache
        """
        df = self.get_cached_data(ticker)
        
        if df is None or df.empty:
            return None
        
        return df.index.max()
    
    def save_to_cache(self, ticker: str, df: pd.DataFrame) -> None:
        """
        Save data to cache.
        
        Args:
            ticker: Ticker symbol
            df: DataFrame with OHLCV data (must have DatetimeIndex)
        """
        if df is None or df.empty:
            print(f"Warning: Attempted to cache empty data for {ticker}")
            return
        
        cache_path = self._get_cache_path(ticker)
        
        try:
            # Ensure index is DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            # Sort by date
            df = df.sort_index()
            
            # Save to parquet
            df.to_parquet(cache_path)
            
            last_date = df.index.max().strftime("%Y-%m-%d")
            print(f"Cached {ticker} data (last date: {last_date})")
            
        except Exception as e:
            print(f"Error saving cache for {ticker}: {e}")
    
    def clear_cache(self, ticker: str | None = None) -> None:
        """
        Clear cache for a specific ticker or all tickers.
        
        Args:
            ticker: Ticker symbol to clear, or None to clear all
        """
        if ticker:
            cache_path = self._get_cache_path(ticker)
            if cache_path.exists():
                cache_path.unlink()
                print(f"Cleared cache for {ticker}")
        else:
            # Clear all cache files
            for cache_file in self._CACHE_DIR.glob("*.parquet"):
                cache_file.unlink()
            print("Cleared all cache files")
    
    def get_cache_info(self, ticker: str) -> dict:
        """
        Get information about cached data.
        
        Args:
            ticker: Ticker symbol
        
        Returns:
            Dict with cache info (exists, last_date, is_current, num_records)
        """
        exists = self.has_cache(ticker)
        
        if not exists:
            return {
                "exists": False,
                "last_date": None,
                "is_current": False,
                "num_records": 0,
            }
        
        df = self.get_cached_data(ticker)
        last_date = df.index.max() if df is not None and not df.empty else None
        is_current = self.is_cache_current(ticker)
        num_records = len(df) if df is not None else 0
        
        return {
            "exists": exists,
            "last_date": last_date,
            "is_current": is_current,
            "num_records": num_records,
        }