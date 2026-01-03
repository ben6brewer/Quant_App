"""
Backfill status tracker for hybrid market data system.

Tracks which tickers have had their pre-5-year historical data
fetched from Yahoo Finance (one-time operation).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Status file location
_STATUS_FILE = Path.home() / ".quant_terminal" / "cache" / "backfill_status.json"

# Thread-safe cache
_cache: Optional[Dict[str, dict]] = None
_lock = threading.Lock()


class BackfillTracker:
    """
    Tracks backfill status for tickers.

    Stores status in JSON file at ~/.quant_terminal/cache/backfill_status.json

    Format:
    {
        "AAPL": {"backfilled": true, "timestamp": "2024-01-15T10:30:00"},
        "BTC-USD": {"backfilled": true, "timestamp": "2024-01-15T10:31:00"},
        ...
    }
    """

    @classmethod
    def is_backfilled(cls, ticker: str) -> bool:
        """
        Check if ticker has been backfilled with pre-5-year Yahoo data.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "BTC-USD")

        Returns:
            True if backfill has been performed, False otherwise
        """
        ticker = ticker.upper().strip()
        status = cls._load_status()
        entry = status.get(ticker, {})
        return entry.get("backfilled", False)

    @classmethod
    def mark_backfilled(cls, ticker: str) -> None:
        """
        Mark ticker as backfilled (Yahoo historical data fetched).

        Args:
            ticker: Ticker symbol
        """
        ticker = ticker.upper().strip()

        with _lock:
            status = cls._load_status()
            status[ticker] = {
                "backfilled": True,
                "timestamp": datetime.now().isoformat(),
            }
            cls._save_status(status)

    @classmethod
    def clear_status(cls, ticker: Optional[str] = None) -> None:
        """
        Clear backfill status for one or all tickers.

        Args:
            ticker: Ticker to clear, or None to clear all
        """
        global _cache

        with _lock:
            if ticker is None:
                # Clear all
                _cache = {}
                cls._save_status({})
            else:
                ticker = ticker.upper().strip()
                status = cls._load_status()
                if ticker in status:
                    del status[ticker]
                    cls._save_status(status)

    @classmethod
    def _load_status(cls) -> Dict[str, dict]:
        """
        Load status from disk (with in-memory caching).

        Returns:
            Dict mapping tickers to status entries
        """
        global _cache

        # Return cached if available
        if _cache is not None:
            return _cache

        # Load from disk
        if _STATUS_FILE.exists():
            try:
                with open(_STATUS_FILE, "r") as f:
                    _cache = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load backfill status: {e}")
                _cache = {}
        else:
            _cache = {}

        return _cache

    @classmethod
    def _save_status(cls, status: Dict[str, dict]) -> None:
        """
        Persist status to disk.

        Args:
            status: Status dict to save
        """
        global _cache

        # Ensure directory exists
        _STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(_STATUS_FILE, "w") as f:
                json.dump(status, f, indent=2)
            _cache = status
        except IOError as e:
            print(f"Warning: Could not save backfill status: {e}")

    @classmethod
    def get_all_backfilled(cls) -> list[str]:
        """
        Get list of all tickers that have been backfilled.

        Returns:
            List of ticker symbols
        """
        status = cls._load_status()
        return [
            ticker
            for ticker, entry in status.items()
            if entry.get("backfilled", False)
        ]
