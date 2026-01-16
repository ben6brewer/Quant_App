"""iShares ETF Holdings Service - Fetches and parses ETF constituent data.

This service fetches holdings data from iShares CSV endpoints and provides
normalized constituent information for performance attribution.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    pass

# Cache location for IWV holdings
_CACHE_FILE = Path.home() / ".quant_terminal" / "cache" / "iwv_holdings.json"


@dataclass
class ETFHolding:
    """Represents a single holding in an ETF."""

    ticker: str
    name: str
    sector: str
    weight: float  # As decimal (0.0665 = 6.65%)
    currency: str
    asset_class: str
    location: str


class ISharesHoldingsService:
    """Fetches and parses ETF holdings from iShares CSV endpoints."""

    # ETF URLs - add more as needed
    ETF_URLS = {
        "IWV": "https://www.ishares.com/us/products/239714/ishares-russell-3000-etf/1467271812596.ajax?fileType=csv&dataType=fund",
    }

    # iShares sector names mapped to standard GICS sectors
    SECTOR_MAP = {
        "Information Technology": "Technology",
        "Consumer Discretionary": "Consumer Cyclical",
        "Consumer Staples": "Consumer Defensive",
        "Health Care": "Healthcare",
        "Financials": "Financial Services",
        "Communication Services": "Communication Services",
        "Communication": "Communication Services",
        "Industrials": "Industrials",
        "Energy": "Energy",
        "Materials": "Basic Materials",
        "Real Estate": "Real Estate",
        "Utilities": "Utilities",
    }

    # iShares ticker format -> Yahoo Finance format
    # Only some share classes need hyphen conversion - many use concatenated format on Yahoo too
    TICKER_MAP = {
        # Berkshire Hathaway (Yahoo uses hyphen)
        "BRKA": "BRK-A",
        "BRKB": "BRK-B",
        # Brown-Forman (Yahoo uses hyphen)
        "BFA": "BF-A",
        "BFB": "BF-B",
        # Lennar (Yahoo uses hyphen)
        "LENA": "LEN-A",
        "LENB": "LEN-B",
        # Greif (Yahoo uses hyphen)
        "GEFA": "GEF-A",
        "GEFB": "GEF-B",
        # Moog (Yahoo uses hyphen)
        "MOGA": "MOG-A",
        "MOGB": "MOG-B",
        # Clearway Energy (Yahoo uses hyphen)
        "CWENA": "CWEN-A",
        # Heico (Yahoo uses hyphen)
        "HEIA": "HEI-A",
        # Note: These tickers use concatenated format on Yahoo (NO hyphen needed):
        # FOXA, NWSA, NWSB, FWONA, FWONK, LSXMA, LSXMB, LSXMK, DISCA, DISCB, DISCK
    }

    # -------------------------------------------------------------------------
    # Cache methods
    # -------------------------------------------------------------------------

    @classmethod
    def _is_cache_current(cls) -> bool:
        """Check if cached IWV holdings are current (no new trading day data expected)."""
        if not _CACHE_FILE.exists():
            return False

        try:
            with open(_CACHE_FILE, "r") as f:
                cache_data = json.load(f)

            last_updated_str = cache_data.get("last_updated")
            if not last_updated_str:
                return False

            last_updated = date.fromisoformat(last_updated_str)

            # Use same staleness logic as stock cache
            from app.utils.market_hours import get_last_expected_trading_date

            expected_date = get_last_expected_trading_date()
            return last_updated >= expected_date

        except (json.JSONDecodeError, ValueError, KeyError):
            return False

    @classmethod
    def _load_from_cache(cls) -> Optional[Dict[str, ETFHolding]]:
        """Load IWV holdings from cache file."""
        if not _CACHE_FILE.exists():
            return None

        try:
            with open(_CACHE_FILE, "r") as f:
                cache_data = json.load(f)

            holdings_data = cache_data.get("holdings", {})
            holdings: Dict[str, ETFHolding] = {}

            for ticker, data in holdings_data.items():
                holdings[ticker] = ETFHolding(
                    ticker=data["ticker"],
                    name=data["name"],
                    sector=data["sector"],
                    weight=data["weight"],
                    currency=data["currency"],
                    asset_class=data["asset_class"],
                    location=data["location"],
                )

            return holdings

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"[ISharesHoldingsService] Failed to load cache: {e}")
            return None

    @classmethod
    def _save_to_cache(cls, holdings: Dict[str, ETFHolding]) -> None:
        """Save IWV holdings to cache file."""
        try:
            # Ensure cache directory exists
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Serialize holdings to JSON-compatible format
            holdings_data = {ticker: asdict(holding) for ticker, holding in holdings.items()}

            cache_data = {
                "last_updated": date.today().isoformat(),
                "holdings": holdings_data,
            }

            with open(_CACHE_FILE, "w") as f:
                json.dump(cache_data, f)

            print(f"[ISharesHoldingsService] Cached {len(holdings)} IWV holdings")

        except Exception as e:
            print(f"[ISharesHoldingsService] Failed to save cache: {e}")

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached IWV holdings."""
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
        print("[ISharesHoldingsService] Cache cleared")

    # -------------------------------------------------------------------------
    # Fetch methods
    # -------------------------------------------------------------------------

    @classmethod
    def fetch_holdings(cls, etf_symbol: str = "IWV") -> Dict[str, ETFHolding]:
        """
        Fetch current holdings for an iShares ETF.

        For IWV, uses trading-day-aware caching to avoid re-fetching on every call.
        Cache is refreshed when a new trading day's data is expected.

        Args:
            etf_symbol: ETF ticker symbol (default: IWV)

        Returns:
            Dict mapping ticker -> ETFHolding
            Empty dict if fetch fails
        """
        etf_upper = etf_symbol.upper()

        # Only IWV is cached
        if etf_upper == "IWV":
            # Check cache first
            if cls._is_cache_current():
                cached = cls._load_from_cache()
                if cached:
                    print(f"[ISharesHoldingsService] Using cached IWV holdings ({len(cached)} tickers)")
                    return cached

        # Fetch fresh data from iShares
        holdings = cls._fetch_from_ishares(etf_upper)

        # Cache if IWV and fetch succeeded
        if etf_upper == "IWV" and holdings:
            cls._save_to_cache(holdings)

        # If fetch failed but we have stale cache, use it
        if not holdings and etf_upper == "IWV":
            cached = cls._load_from_cache()
            if cached:
                print(f"[ISharesHoldingsService] Using stale cache ({len(cached)} tickers)")
                return cached

        return holdings

    @classmethod
    def _fetch_from_ishares(cls, etf_symbol: str) -> Dict[str, ETFHolding]:
        """Fetch holdings directly from iShares website."""
        import requests

        url = cls.ETF_URLS.get(etf_symbol)
        if not url:
            print(f"[ISharesHoldingsService] Unknown ETF: {etf_symbol}")
            return {}

        print(f"[ISharesHoldingsService] Fetching {etf_symbol} holdings from iShares...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            holdings = cls._parse_ishares_csv(response.text)
            print(f"[ISharesHoldingsService] Loaded {len(holdings)} holdings for {etf_symbol}")
            return holdings
        except requests.RequestException as e:
            print(f"[ISharesHoldingsService] Failed to fetch {etf_symbol}: {e}")
            return {}

    @classmethod
    def _parse_ishares_csv(cls, csv_content: str) -> Dict[str, ETFHolding]:
        """
        Parse messy iShares CSV format.

        The CSV has:
        - ~9 metadata rows at the top (fund info)
        - 1 header row with column names
        - Data rows until end or footer

        Args:
            csv_content: Raw CSV text

        Returns:
            Dict mapping ticker -> ETFHolding
        """
        import csv
        from io import StringIO

        holdings: Dict[str, ETFHolding] = {}
        lines = csv_content.strip().split("\n")

        # Find the header row (contains "Ticker" as first column)
        header_idx = None
        for i, line in enumerate(lines):
            if line.startswith("Ticker,") or line.startswith('"Ticker",'):
                header_idx = i
                break

        if header_idx is None:
            print("[ISharesHoldingsService] Could not find header row")
            return {}

        # Parse from header row onwards
        csv_data = "\n".join(lines[header_idx:])
        reader = csv.DictReader(StringIO(csv_data))

        for row in reader:
            try:
                holding = cls._parse_row(row)
                if holding:
                    holdings[holding.ticker] = holding
            except Exception as e:
                # Skip malformed rows
                ticker = row.get("Ticker", "unknown")
                print(f"[ISharesHoldingsService] Skipping row {ticker}: {e}")
                continue

        return holdings

    @classmethod
    def _parse_row(cls, row: Dict[str, str]) -> Optional[ETFHolding]:
        """
        Parse a single CSV row into an ETFHolding.

        Args:
            row: Dict from csv.DictReader

        Returns:
            ETFHolding or None if row should be skipped
        """
        ticker = row.get("Ticker", "").strip()
        asset_class = row.get("Asset Class", "").strip()

        # Skip non-equity holdings (cash, derivatives, etc.)
        if asset_class != "Equity":
            return None

        # Skip invalid tickers
        if not ticker or ticker == "-" or len(ticker) > 10:
            return None

        # Parse weight (remove % if present)
        weight_str = row.get("Weight (%)", "0").strip()
        weight_str = weight_str.replace("%", "").replace(",", "")
        try:
            weight = float(weight_str) / 100.0  # Convert to decimal
        except ValueError:
            weight = 0.0

        # Normalize sector
        raw_sector = row.get("Sector", "").strip()
        sector = cls._normalize_sector(raw_sector)

        # Normalize ticker (iShares format -> Yahoo format)
        normalized_ticker = cls._normalize_ticker(ticker)

        return ETFHolding(
            ticker=normalized_ticker,
            name=row.get("Name", "").strip(),
            sector=sector,
            weight=weight,
            currency=row.get("Currency", "USD").strip(),
            asset_class=asset_class,
            location=row.get("Location", "").strip(),
        )

    @classmethod
    def _normalize_sector(cls, ishares_sector: str) -> str:
        """
        Map iShares sector names to standard sector names.

        Args:
            ishares_sector: Sector name from iShares CSV

        Returns:
            Normalized sector name
        """
        return cls.SECTOR_MAP.get(ishares_sector, ishares_sector or "Not Classified")

    @classmethod
    def _normalize_ticker(cls, ishares_ticker: str) -> str:
        """
        Convert iShares ticker format to Yahoo Finance format.

        iShares concatenates share class letters (BRKB), Yahoo uses hyphen (BRK-B).

        Args:
            ishares_ticker: Ticker from iShares CSV

        Returns:
            Yahoo-compatible ticker
        """
        ticker = ishares_ticker.upper().strip()
        return cls.TICKER_MAP.get(ticker, ticker)

    @classmethod
    def get_available_etfs(cls) -> list[str]:
        """Return list of available ETF symbols."""
        return list(cls.ETF_URLS.keys())
