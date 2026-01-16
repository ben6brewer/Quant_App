"""Ticker Name Cache Service - Persistent cache for ticker display names."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, Optional


class TickerNameCache:
    """
    Persistent cache for ticker short names.

    Stores ticker names (e.g., "Apple Inc." for "AAPL") to disk so they
    don't need to be re-fetched from Yahoo Finance on every app launch.

    Thread-safe for concurrent read/write operations.
    """

    _CACHE_FILE = Path.home() / ".quant_terminal" / "ticker_names.json"
    _lock = threading.Lock()
    _cache: Optional[Dict[str, str]] = None

    @classmethod
    def _ensure_dir(cls) -> None:
        """Create cache directory if it doesn't exist."""
        cls._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _load_cache(cls) -> Dict[str, str]:
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
                    print(f"Warning: Could not load ticker name cache: {e}")
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
                print(f"Warning: Could not save ticker name cache: {e}")

    @classmethod
    def load_names(cls) -> Dict[str, str]:
        """
        Load all cached ticker names from disk.

        Returns:
            Dict mapping ticker symbols to display names
        """
        return cls._load_cache().copy()

    @classmethod
    def get_name(cls, ticker: str) -> Optional[str]:
        """
        Get cached name for a single ticker.

        Args:
            ticker: Ticker symbol (e.g., "AAPL")

        Returns:
            Display name if cached, None otherwise
        """
        cache = cls._load_cache()
        return cache.get(ticker.upper())

    @classmethod
    def get_names(cls, tickers: list[str]) -> Dict[str, Optional[str]]:
        """
        Get cached names for multiple tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker to name (None if not cached)
        """
        cache = cls._load_cache()
        return {t.upper(): cache.get(t.upper()) for t in tickers}

    @classmethod
    def set_name(cls, ticker: str, name: str) -> None:
        """
        Set name for a single ticker and persist to disk.

        Args:
            ticker: Ticker symbol
            name: Display name
        """
        cache = cls._load_cache()
        cache[ticker.upper()] = name
        cls._save_cache()

    @classmethod
    def update_names(cls, names: Dict[str, str]) -> None:
        """
        Update cache with multiple names and persist to disk.

        Args:
            names: Dict mapping ticker symbols to display names
        """
        if not names:
            return

        cache = cls._load_cache()
        for ticker, name in names.items():
            if name:  # Only cache non-None names
                cache[ticker.upper()] = name
        cls._save_cache()

    @classmethod
    def get_missing_tickers(cls, tickers: list[str]) -> list[str]:
        """
        Get list of tickers not in cache.

        Args:
            tickers: List of ticker symbols to check

        Returns:
            List of ticker symbols not found in cache
        """
        cache = cls._load_cache()
        return [t for t in tickers if t.upper() not in cache]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached ticker names."""
        with cls._lock:
            cls._cache = {}
            if cls._CACHE_FILE.exists():
                cls._CACHE_FILE.unlink()
        print("[TickerNameCache] Cache cleared")
