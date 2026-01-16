"""Ticker Metadata Service - Persistent cache for yfinance ticker info data."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class TickerMetadataService:
    """
    Persistent cache for ticker metadata from yfinance.

    Stores sector, industry, style factors, and other metadata to avoid
    repeated API calls. Cache entries expire after CACHE_EXPIRY_DAYS.

    Thread-safe for concurrent read/write operations.
    """

    _CACHE_FILE = Path.home() / ".quant_terminal" / "cache" / "ticker_metadata.json"
    _lock = threading.Lock()
    _cache: Optional[Dict[str, Dict[str, Any]]] = None
    _CACHE_EXPIRY_DAYS = 7

    # Fields to fetch from yfinance .info
    CORE_FIELDS = [
        "sector",
        "industry",
        "quoteType",
        "marketCap",
        "beta",
        "country",
        "currency",
    ]

    STYLE_FIELDS = [
        "trailingPE",
        "priceToBook",
        "returnOnEquity",
        "debtToEquity",
        "revenueGrowth",
        "earningsGrowth",
        "fiftyTwoWeekChange",
    ]

    ALL_FIELDS = CORE_FIELDS + STYLE_FIELDS

    # Standard GICS sectors
    SECTORS = [
        "Communication Services",
        "Consumer Cyclical",
        "Consumer Defensive",
        "Energy",
        "Financial Services",
        "Healthcare",
        "Industrials",
        "Technology",
        "Basic Materials",
        "Real Estate",
        "Utilities",
    ]

    @classmethod
    def _ensure_dir(cls) -> None:
        """Create cache directory if it doesn't exist."""
        cls._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _load_cache(cls) -> Dict[str, Dict[str, Any]]:
        """Load cache from disk (lazy loading, called once per session)."""
        if cls._cache is not None:
            return cls._cache

        with cls._lock:
            # Double-check after acquiring lock
            if cls._cache is not None:
                return cls._cache

            cls._ensure_dir()

            if cls._CACHE_FILE.exists():
                try:
                    with open(cls._CACHE_FILE, "r", encoding="utf-8") as f:
                        cls._cache = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Could not load ticker metadata cache: {e}")
                    cls._cache = {}
            else:
                cls._cache = {}

            return cls._cache

    @classmethod
    def _save_cache(cls) -> None:
        """Save cache to disk."""
        if cls._cache is None:
            return

        with cls._lock:
            cls._ensure_dir()
            try:
                with open(cls._CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cls._cache, f, indent=2)
            except IOError as e:
                print(f"Warning: Could not save ticker metadata cache: {e}")

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached ticker metadata."""
        with cls._lock:
            if cls._CACHE_FILE.exists():
                cls._CACHE_FILE.unlink()
            cls._cache = None
        print("[TickerMetadataService] Cache cleared")

    @classmethod
    def _is_cache_stale(cls, ticker: str) -> bool:
        """Check if cached metadata is older than CACHE_EXPIRY_DAYS."""
        cache = cls._load_cache()
        ticker_upper = ticker.upper()

        if ticker_upper not in cache:
            return True

        entry = cache[ticker_upper]
        last_updated = entry.get("last_updated")

        if not last_updated:
            return True

        try:
            updated_time = datetime.fromisoformat(last_updated)
            expiry_time = updated_time + timedelta(days=cls._CACHE_EXPIRY_DAYS)
            return datetime.now() > expiry_time
        except (ValueError, TypeError):
            return True

    @classmethod
    def _fetch_from_yfinance(cls, ticker: str) -> Dict[str, Any]:
        """
        Fetch ticker info from yfinance.

        Args:
            ticker: Ticker symbol

        Returns:
            Dict with requested fields (values may be None if unavailable)
        """
        import yfinance as yf

        result: Dict[str, Any] = {}

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Extract requested fields
            for field in cls.ALL_FIELDS:
                result[field] = info.get(field)

            # Also get shortName for display
            result["shortName"] = info.get("shortName")

        except Exception as e:
            print(f"Warning: Could not fetch metadata for {ticker}: {e}")
            # Return empty dict with None values
            for field in cls.ALL_FIELDS:
                result[field] = None

        result["last_updated"] = datetime.now().isoformat()
        return result

    @classmethod
    def get_metadata(cls, ticker: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get metadata for a single ticker.

        Args:
            ticker: Ticker symbol
            force_refresh: If True, always fetch fresh data from yfinance

        Returns:
            Dict with metadata fields
        """
        ticker_upper = ticker.upper()
        cache = cls._load_cache()

        # Return cached data if valid
        if not force_refresh and ticker_upper in cache and not cls._is_cache_stale(
            ticker_upper
        ):
            return cache[ticker_upper].copy()

        # Fetch fresh data
        metadata = cls._fetch_from_yfinance(ticker_upper)
        cache[ticker_upper] = metadata
        cls._save_cache()

        return metadata.copy()

    @classmethod
    def get_metadata_batch(
        cls, tickers: List[str], force_refresh: bool = False, max_workers: int = 10
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get metadata for multiple tickers (batch fetch missing/stale entries).

        Args:
            tickers: List of ticker symbols
            force_refresh: If True, always fetch fresh data
            max_workers: Max parallel fetch threads

        Returns:
            Dict mapping ticker to metadata
        """
        cache = cls._load_cache()
        result: Dict[str, Dict[str, Any]] = {}
        tickers_to_fetch: List[str] = []

        # Check which tickers need fetching
        for ticker in tickers:
            ticker_upper = ticker.upper()
            if (
                not force_refresh
                and ticker_upper in cache
                and not cls._is_cache_stale(ticker_upper)
            ):
                result[ticker_upper] = cache[ticker_upper].copy()
            else:
                tickers_to_fetch.append(ticker_upper)

        # Fetch missing tickers in parallel
        if tickers_to_fetch:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_ticker = {
                    executor.submit(cls._fetch_from_yfinance, t): t
                    for t in tickers_to_fetch
                }

                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        metadata = future.result()
                        cache[ticker] = metadata
                        result[ticker] = metadata.copy()
                    except Exception as e:
                        print(f"Warning: Failed to fetch metadata for {ticker}: {e}")
                        # Create empty entry
                        empty_entry = {field: None for field in cls.ALL_FIELDS}
                        empty_entry["last_updated"] = datetime.now().isoformat()
                        cache[ticker] = empty_entry
                        result[ticker] = empty_entry.copy()

            cls._save_cache()

        return result

    @classmethod
    def get_sector(cls, ticker: str) -> str:
        """
        Get sector for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Sector name or "Not Classified" if unavailable
        """
        metadata = cls.get_metadata(ticker)
        sector = metadata.get("sector")
        return sector if sector else "Not Classified"

    @classmethod
    def get_industry(cls, ticker: str) -> str:
        """
        Get industry for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Industry name or "Not Classified" if unavailable
        """
        metadata = cls.get_metadata(ticker)
        industry = metadata.get("industry")
        return industry if industry else "Not Classified"

    @classmethod
    def get_style_factors(cls, ticker: str) -> Dict[str, Optional[float]]:
        """
        Get style factor values for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Dict with style factor values (may be None if unavailable)
        """
        metadata = cls.get_metadata(ticker)
        return {field: metadata.get(field) for field in cls.STYLE_FIELDS}

    @classmethod
    def get_beta(cls, ticker: str) -> Optional[float]:
        """
        Get beta for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Beta value or None if unavailable
        """
        metadata = cls.get_metadata(ticker)
        return metadata.get("beta")

    @classmethod
    def get_currency(cls, ticker: str) -> str:
        """
        Get currency for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Currency code (e.g., "USD") or "USD" as default
        """
        metadata = cls.get_metadata(ticker)
        currency = metadata.get("currency")
        return currency if currency else "USD"

    @classmethod
    def get_market_cap(cls, ticker: str) -> Optional[float]:
        """
        Get market cap for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Market cap in currency units or None if unavailable
        """
        metadata = cls.get_metadata(ticker)
        return metadata.get("marketCap")

    @classmethod
    def refresh_metadata(cls, ticker: str) -> Dict[str, Any]:
        """
        Force refresh metadata for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Updated metadata dict
        """
        return cls.get_metadata(ticker, force_refresh=True)

    @classmethod
    def get_cached_tickers(cls) -> List[str]:
        """
        Get list of all cached tickers.

        Returns:
            List of ticker symbols in cache
        """
        cache = cls._load_cache()
        return list(cache.keys())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached metadata (useful for testing)."""
        with cls._lock:
            cls._cache = {}
            if cls._CACHE_FILE.exists():
                cls._CACHE_FILE.unlink()

    @classmethod
    def cache_from_etf_holdings(
        cls,
        holdings: Dict[str, Any],
        overwrite: bool = False,
    ) -> int:
        """
        Cache metadata for tickers from ETF holdings CSV (e.g., IWV).

        Imports sector, name, currency, and location from ETF constituent data.
        This avoids needing to fetch from yfinance for ~3000 benchmark tickers.

        Args:
            holdings: Dict mapping ticker -> ETFHolding object with:
                - sector: str (GICS-normalized)
                - name: str (company name)
                - currency: str
                - location: str (country)
            overwrite: If True, overwrite existing entries. Default False (skip existing).

        Returns:
            Number of tickers cached (new or updated)
        """
        if not holdings:
            return 0

        cache = cls._load_cache()
        cached_count = 0
        total = len(holdings)

        print(f"[Metadata] Caching metadata for {total} ETF holdings...")

        for ticker, holding in holdings.items():
            ticker_upper = ticker.upper()

            # Skip if already in cache and not overwriting
            if not overwrite and ticker_upper in cache and not cls._is_cache_stale(ticker_upper):
                continue

            # Extract fields from ETFHolding
            # ETFHolding has: ticker, name, sector, weight, currency, asset_class, location
            metadata: Dict[str, Any] = {
                "sector": getattr(holding, "sector", None),
                "shortName": getattr(holding, "name", None),
                "currency": getattr(holding, "currency", "USD"),
                "country": getattr(holding, "location", None),
                # Mark source as ETF for reference
                "source": "etf_holdings",
                "last_updated": datetime.now().isoformat(),
            }

            # Preserve existing fields if we have them (don't overwrite with None)
            if ticker_upper in cache:
                existing = cache[ticker_upper]
                for field in cls.ALL_FIELDS:
                    if field not in metadata or metadata.get(field) is None:
                        metadata[field] = existing.get(field)

            cache[ticker_upper] = metadata
            cached_count += 1

        # Save to disk
        cls._save_cache()

        existing_count = total - cached_count
        print(f"[Metadata] Cached {cached_count} tickers ({existing_count} already existed)")

        return cached_count
