"""
Backfill status tracker for hybrid market data system.

Tracks which tickers have had their full historical data
fetched from Yahoo Finance (one-time operation).

Schema v2: Renamed "backfilled" -> "yahoo_backfilled" for clarity.
Migration happens automatically on first load.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Status file location
_STATUS_FILE = Path.home() / ".quant_terminal" / "cache" / "backfill_status.json"

# Schema version for migration tracking
_SCHEMA_VERSION = 2

# Thread-safe cache
_cache: Optional[Dict[str, dict]] = None
_lock = threading.Lock()


class BackfillTracker:
    """
    Tracks Yahoo Finance backfill status for tickers.

    Stores status in JSON file at ~/.quant_terminal/cache/backfill_status.json

    Format (v2):
    {
        "schema_version": 2,
        "AAPL": {"yahoo_backfilled": true, "timestamp": "2024-01-15T10:30:00"},
        "BTC-USD": {"yahoo_backfilled": true, "timestamp": "2024-01-15T10:31:00"},
        ...
    }

    The yahoo_backfilled flag indicates the ticker has full Yahoo Finance
    historical data. If False or missing, the ticker only has Polygon data
    (5-year limit) and needs Yahoo backfill on next access.
    """

    @classmethod
    def is_yahoo_backfilled(cls, ticker: str) -> bool:
        """
        Check if ticker has full Yahoo Finance historical data.

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "BTC-USD")

        Returns:
            True if Yahoo backfill has been performed, False otherwise
        """
        ticker = ticker.upper().strip()
        status = cls._load_status()
        entry = status.get(ticker, {})
        # Support both old "backfilled" and new "yahoo_backfilled" keys
        return entry.get("yahoo_backfilled", entry.get("backfilled", False))

    @classmethod
    def mark_yahoo_backfilled(cls, ticker: str) -> None:
        """
        Mark ticker as having full Yahoo Finance historical data.

        Args:
            ticker: Ticker symbol
        """
        ticker = ticker.upper().strip()

        with _lock:
            status = cls._load_status()
            status[ticker] = {
                "yahoo_backfilled": True,
                "timestamp": datetime.now().isoformat(),
            }
            cls._save_status(status)

    # Legacy aliases for backward compatibility
    @classmethod
    def is_backfilled(cls, ticker: str) -> bool:
        """Legacy alias for is_yahoo_backfilled()."""
        return cls.is_yahoo_backfilled(ticker)

    @classmethod
    def mark_backfilled(cls, ticker: str) -> None:
        """Legacy alias for mark_yahoo_backfilled()."""
        cls.mark_yahoo_backfilled(ticker)

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

        Automatically migrates old schema (v1) to new schema (v2).

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

        # Migrate schema if needed
        _cache = cls._migrate_schema(_cache)

        return _cache

    @classmethod
    def _migrate_schema(cls, status: Dict[str, dict]) -> Dict[str, dict]:
        """
        Migrate old schema to new schema.

        v1 -> v2: Rename "backfilled" to "yahoo_backfilled"

        Args:
            status: Status dict to migrate

        Returns:
            Migrated status dict
        """
        # Check if already migrated
        if status.get("schema_version") == _SCHEMA_VERSION:
            return status

        # Migrate each ticker entry
        for key, entry in list(status.items()):
            if key == "schema_version":
                continue
            if isinstance(entry, dict) and "backfilled" in entry:
                entry["yahoo_backfilled"] = entry.pop("backfilled")

        # Mark as migrated
        status["schema_version"] = _SCHEMA_VERSION

        # Save migrated status
        cls._save_status(status)

        return status

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
        Get list of all tickers that have Yahoo Finance backfill.

        Returns:
            List of ticker symbols
        """
        status = cls._load_status()
        return [
            ticker
            for ticker, entry in status.items()
            if ticker != "schema_version"
            and isinstance(entry, dict)
            and entry.get("yahoo_backfilled", entry.get("backfilled", False))
        ]
