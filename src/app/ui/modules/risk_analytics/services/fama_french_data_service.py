"""Fama-French Factor Data Service - Downloads and caches FF5+Momentum factors.

This service fetches daily factor returns from Kenneth French's data library:
- Mkt-RF: Market excess return
- SMB: Small minus Big (size factor)
- HML: High minus Low (value factor)
- RMW: Robust minus Weak (profitability factor)
- CMA: Conservative minus Aggressive (investment factor)
- UMD: Up minus Down (momentum factor)
- RF: Risk-free rate
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import pandas as pd


class FamaFrenchDataService:
    """
    Downloads and caches Fama-French factor data.

    Data is fetched from Kenneth French's data library and cached locally
    in parquet format for fast loading. Cache is refreshed if >30 days stale.
    """

    _CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "factors"
    _CACHE_FILE = _CACHE_DIR / "fama_french.parquet"
    _TIMESTAMP_FILE = _CACHE_DIR / "fama_french_last_update.txt"
    _STALE_DAYS = 30

    _lock = threading.Lock()
    _cached_data: Optional["pd.DataFrame"] = None

    # Factor datasets from Kenneth French Data Library
    # FF5 daily: "F-F_Research_Data_5_Factors_2x3_daily"
    # Momentum daily: "F-F_Momentum_Factor_daily"

    @classmethod
    def _ensure_dir(cls) -> None:
        """Create cache directory if it doesn't exist."""
        cls._CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def is_data_current(cls) -> bool:
        """
        Check if cached data is current (less than 30 days old).

        Returns:
            True if cache is current, False if stale or missing
        """
        if not cls._TIMESTAMP_FILE.exists():
            return False

        try:
            with open(cls._TIMESTAMP_FILE, "r") as f:
                timestamp_str = f.read().strip()
            last_update = datetime.fromisoformat(timestamp_str)
            age = datetime.now() - last_update
            return age.days < cls._STALE_DAYS
        except (ValueError, IOError):
            return False

    @classmethod
    def _save_timestamp(cls) -> None:
        """Save current timestamp to file."""
        cls._ensure_dir()
        with open(cls._TIMESTAMP_FILE, "w") as f:
            f.write(datetime.now().isoformat())

    @classmethod
    def _fetch_from_web(cls) -> "pd.DataFrame":
        """
        Fetch factor data from Kenneth French Data Library.

        Returns:
            DataFrame with columns: Mkt-RF, SMB, HML, RMW, CMA, UMD, RF
            Index: DatetimeIndex (daily dates)
        """
        import pandas as pd
        import pandas_datareader.data as pdr

        print("[FamaFrench] Fetching Fama-French 5 factors from web...")

        # Fetch FF5 factors (daily)
        ff5 = pdr.DataReader(
            "F-F_Research_Data_5_Factors_2x3_daily",
            "famafrench",
            start="1990-01-01"
        )[0]  # [0] gets the daily data table

        print("[FamaFrench] Fetching Momentum factor from web...")

        # Fetch Momentum factor (daily)
        mom = pdr.DataReader(
            "F-F_Momentum_Factor_daily",
            "famafrench",
            start="1990-01-01"
        )[0]

        # Rename momentum column to UMD
        mom = mom.rename(columns={"Mom   ": "UMD", "Mom": "UMD"})
        if "UMD" not in mom.columns:
            # Handle variations in column naming
            for col in mom.columns:
                if "mom" in col.lower():
                    mom = mom.rename(columns={col: "UMD"})
                    break

        # Keep only UMD column
        if "UMD" in mom.columns:
            mom = mom[["UMD"]]
        else:
            # Create empty UMD if not found
            mom = pd.DataFrame(index=mom.index)
            mom["UMD"] = 0.0

        # Merge FF5 and Momentum on date index
        factors = ff5.join(mom, how="inner")

        # Convert from percentage to decimal (FF data is in percentage form)
        for col in factors.columns:
            factors[col] = factors[col] / 100.0

        # Ensure we have all expected columns
        expected_cols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "UMD"]
        for col in expected_cols:
            if col not in factors.columns:
                print(f"[FamaFrench] Warning: Missing column {col}, filling with 0")
                factors[col] = 0.0

        # Ensure index is DatetimeIndex
        if not isinstance(factors.index, pd.DatetimeIndex):
            factors.index = pd.to_datetime(factors.index.astype(str))

        print(f"[FamaFrench] Fetched {len(factors)} days of factor data")
        print(f"[FamaFrench] Date range: {factors.index.min()} to {factors.index.max()}")

        return factors[expected_cols]

    @classmethod
    def _load_from_cache(cls) -> Optional["pd.DataFrame"]:
        """
        Load factor data from parquet cache.

        Returns:
            DataFrame if cache exists, None otherwise
        """
        import pandas as pd

        if not cls._CACHE_FILE.exists():
            return None

        try:
            df = pd.read_parquet(cls._CACHE_FILE)
            print(f"[FamaFrench] Loaded {len(df)} days from cache")
            return df
        except Exception as e:
            print(f"[FamaFrench] Error loading cache: {e}")
            return None

    @classmethod
    def _save_to_cache(cls, df: "pd.DataFrame") -> None:
        """Save factor data to parquet cache."""
        cls._ensure_dir()
        try:
            df.to_parquet(cls._CACHE_FILE)
            cls._save_timestamp()
            print(f"[FamaFrench] Saved {len(df)} days to cache")
        except Exception as e:
            print(f"[FamaFrench] Error saving cache: {e}")

    @classmethod
    def refresh_data(cls) -> "pd.DataFrame":
        """
        Force refresh factor data from web.

        Returns:
            DataFrame with factor returns
        """
        with cls._lock:
            df = cls._fetch_from_web()
            cls._save_to_cache(df)
            cls._cached_data = df
            return df

    @classmethod
    def get_factor_returns(
        cls,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.DataFrame":
        """
        Get daily factor returns (Mkt-RF, SMB, HML, RMW, CMA, UMD).

        Automatically fetches from web if cache is stale or missing.

        Args:
            start_date: Start date (YYYY-MM-DD) or None for full history
            end_date: End date (YYYY-MM-DD) or None for full history

        Returns:
            DataFrame with columns: Mkt-RF, SMB, HML, RMW, CMA, UMD
            Index: DatetimeIndex (daily dates)
            Values: Daily factor returns as decimals (e.g., 0.01 = 1%)
        """
        import pandas as pd

        with cls._lock:
            # Return cached data if available and current
            if cls._cached_data is not None and cls.is_data_current():
                df = cls._cached_data
            else:
                # Try loading from disk cache
                if cls.is_data_current():
                    df = cls._load_from_cache()
                    if df is not None:
                        cls._cached_data = df
                    else:
                        # Cache file missing, fetch from web
                        df = cls._fetch_from_web()
                        cls._save_to_cache(df)
                        cls._cached_data = df
                else:
                    # Cache is stale, refresh from web
                    df = cls._fetch_from_web()
                    cls._save_to_cache(df)
                    cls._cached_data = df

        # Filter by date range if specified
        if start_date:
            start = pd.Timestamp(start_date)
            df = df[df.index >= start]
        if end_date:
            end = pd.Timestamp(end_date)
            df = df[df.index <= end]

        # Return only factor columns (not RF)
        factor_cols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
        return df[factor_cols].copy()

    @classmethod
    def get_risk_free_rate(
        cls,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> "pd.Series":
        """
        Get daily risk-free rate from Fama-French data.

        Args:
            start_date: Start date (YYYY-MM-DD) or None for full history
            end_date: End date (YYYY-MM-DD) or None for full history

        Returns:
            Series with daily risk-free rate as decimal
        """
        import pandas as pd

        with cls._lock:
            # Same loading logic as get_factor_returns
            if cls._cached_data is not None and cls.is_data_current():
                df = cls._cached_data
            else:
                if cls.is_data_current():
                    df = cls._load_from_cache()
                    if df is not None:
                        cls._cached_data = df
                    else:
                        df = cls._fetch_from_web()
                        cls._save_to_cache(df)
                        cls._cached_data = df
                else:
                    df = cls._fetch_from_web()
                    cls._save_to_cache(df)
                    cls._cached_data = df

        # Filter by date range
        rf = df["RF"].copy()
        if start_date:
            start = pd.Timestamp(start_date)
            rf = rf[rf.index >= start]
        if end_date:
            end = pd.Timestamp(end_date)
            rf = rf[rf.index <= end]

        return rf

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached factor data."""
        with cls._lock:
            cls._cached_data = None
            if cls._CACHE_FILE.exists():
                cls._CACHE_FILE.unlink()
            if cls._TIMESTAMP_FILE.exists():
                cls._TIMESTAMP_FILE.unlink()
            print("[FamaFrench] Cache cleared")
