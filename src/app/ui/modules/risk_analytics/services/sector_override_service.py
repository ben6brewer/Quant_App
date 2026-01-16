"""Sector Override Service - Manual sector classification overrides for tickers."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.ticker_metadata_service import TickerMetadataService


class SectorOverrideService:
    """
    Service for managing manual sector/industry classification overrides.

    Allows users to override the yfinance sector/industry for specific tickers
    that may be incorrectly classified or not classified at all.

    Thread-safe for concurrent read/write operations.
    """

    _OVERRIDE_FILE = Path.home() / ".quant_terminal" / "sector_overrides.json"
    _lock = threading.Lock()
    _overrides: Optional[Dict[str, Dict[str, str]]] = None

    # Standard GICS sectors for dropdown
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
        "Not Classified",
    ]

    @classmethod
    def _ensure_dir(cls) -> None:
        """Create directory if it doesn't exist."""
        cls._OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _load_overrides(cls) -> Dict[str, Dict[str, str]]:
        """Load overrides from disk (lazy loading)."""
        if cls._overrides is not None:
            return cls._overrides

        with cls._lock:
            # Double-check after acquiring lock
            if cls._overrides is not None:
                return cls._overrides

            cls._ensure_dir()

            if cls._OVERRIDE_FILE.exists():
                try:
                    with open(cls._OVERRIDE_FILE, "r", encoding="utf-8") as f:
                        cls._overrides = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Could not load sector overrides: {e}")
                    cls._overrides = {}
            else:
                cls._overrides = {}

            return cls._overrides

    @classmethod
    def _save_overrides(cls) -> None:
        """Save overrides to disk."""
        if cls._overrides is None:
            return

        with cls._lock:
            cls._ensure_dir()
            try:
                with open(cls._OVERRIDE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cls._overrides, f, indent=2)
            except IOError as e:
                print(f"Warning: Could not save sector overrides: {e}")

    @classmethod
    def get_override(cls, ticker: str) -> Optional[Dict[str, str]]:
        """
        Get sector/industry override for a ticker if it exists.

        Args:
            ticker: Ticker symbol

        Returns:
            Dict with 'sector' and optionally 'industry', or None if no override
        """
        overrides = cls._load_overrides()
        return overrides.get(ticker.upper())

    @classmethod
    def set_override(
        cls, ticker: str, sector: str, industry: Optional[str] = None
    ) -> None:
        """
        Set sector override for a ticker.

        Args:
            ticker: Ticker symbol
            sector: Sector classification
            industry: Optional industry classification
        """
        overrides = cls._load_overrides()
        ticker_upper = ticker.upper()

        override_data: Dict[str, str] = {"sector": sector}
        if industry:
            override_data["industry"] = industry

        overrides[ticker_upper] = override_data
        cls._save_overrides()

    @classmethod
    def remove_override(cls, ticker: str) -> bool:
        """
        Remove override for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            True if override was removed, False if it didn't exist
        """
        overrides = cls._load_overrides()
        ticker_upper = ticker.upper()

        if ticker_upper in overrides:
            del overrides[ticker_upper]
            cls._save_overrides()
            return True
        return False

    @classmethod
    def get_effective_sector(cls, ticker: str) -> str:
        """
        Get the effective sector for a ticker.

        Priority: Override > yfinance metadata > "Not Classified"

        Args:
            ticker: Ticker symbol

        Returns:
            Sector name
        """
        # Check for override first
        override = cls.get_override(ticker)
        if override and override.get("sector"):
            return override["sector"]

        # Fall back to yfinance metadata
        return TickerMetadataService.get_sector(ticker)

    @classmethod
    def get_effective_industry(cls, ticker: str) -> str:
        """
        Get the effective industry for a ticker.

        Priority: Override > yfinance metadata > "Not Classified"

        Args:
            ticker: Ticker symbol

        Returns:
            Industry name
        """
        # Check for override first
        override = cls.get_override(ticker)
        if override and override.get("industry"):
            return override["industry"]

        # Fall back to yfinance metadata
        return TickerMetadataService.get_industry(ticker)

    @classmethod
    def list_overrides(cls) -> Dict[str, Dict[str, str]]:
        """
        Get all current overrides.

        Returns:
            Dict mapping ticker to override data
        """
        overrides = cls._load_overrides()
        return overrides.copy()

    @classmethod
    def get_overridden_tickers(cls) -> List[str]:
        """
        Get list of tickers that have overrides.

        Returns:
            List of ticker symbols
        """
        overrides = cls._load_overrides()
        return list(overrides.keys())

    @classmethod
    def has_override(cls, ticker: str) -> bool:
        """
        Check if a ticker has an override.

        Args:
            ticker: Ticker symbol

        Returns:
            True if override exists
        """
        overrides = cls._load_overrides()
        return ticker.upper() in overrides

    @classmethod
    def clear_all_overrides(cls) -> None:
        """Clear all overrides (useful for testing)."""
        with cls._lock:
            cls._overrides = {}
            if cls._OVERRIDE_FILE.exists():
                cls._OVERRIDE_FILE.unlink()

    @classmethod
    def get_sectors_with_counts(
        cls, tickers: List[str]
    ) -> Dict[str, List[str]]:
        """
        Group tickers by their effective sector.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping sector name to list of tickers
        """
        result: Dict[str, List[str]] = {}

        for ticker in tickers:
            sector = cls.get_effective_sector(ticker)
            if sector not in result:
                result[sector] = []
            result[sector].append(ticker.upper())

        return result
