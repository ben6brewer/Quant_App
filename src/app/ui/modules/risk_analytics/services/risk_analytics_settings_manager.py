"""Risk Analytics Settings Manager - Persistent settings storage."""

from __future__ import annotations

from typing import Any, Dict

from app.services.base_settings_manager import BaseSettingsManager


class RiskAnalyticsSettingsManager(BaseSettingsManager):
    """
    Settings manager for Risk Analytics module.

    Settings are persisted to ~/.quant_terminal/risk_analytics_settings.json

    Session-only settings (not persisted, reset on module reopen):
    - lookback_days, custom_start_date, custom_end_date (lookback period)
    - portfolio_universe_sectors (universe filter)
    """

    # Keys that are session-only (not saved to disk)
    SESSION_ONLY_KEYS = frozenset([
        "lookback_days",
        "custom_start_date",
        "custom_end_date",
        "portfolio_universe_sectors",
    ])

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            # Benchmark settings
            "default_benchmark": "SPY",
            # Analysis settings
            "lookback_days": 252,  # 1 year default (trading days), None if custom date range
            "custom_start_date": None,  # Custom start date (YYYY-MM-DD), only used when lookback_days is None
            "custom_end_date": None,  # Custom end date (YYYY-MM-DD), only used when lookback_days is None
            "show_currency_factor": True,  # Show currency in factor decomposition
            # Universe settings (None = all sectors, list = filter to these sectors)
            "portfolio_universe_sectors": None,  # Filter portfolio to these sectors
            "benchmark_universe_sectors": None,  # Filter benchmark to these sectors (not yet implemented)
            # Display settings
            "decimal_places": 2,  # Decimal places for percentages
            # Table settings
            "collapsed_sectors": [],  # List of sector names to start collapsed
        }

    @property
    def settings_filename(self) -> str:
        return "risk_analytics_settings.json"

    def _serialize_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert settings to JSON-serializable format.

        Session-only settings (lookback period, universe sectors) are excluded
        from persistence - they reset to defaults each time the module is opened.
        """
        return {
            key: value
            for key, value in settings.items()
            if key not in self.SESSION_ONLY_KEYS
        }
