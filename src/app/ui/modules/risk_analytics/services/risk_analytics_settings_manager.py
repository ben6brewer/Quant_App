"""Risk Analytics Settings Manager - Persistent settings storage."""

from __future__ import annotations

from typing import Any, Dict

from app.services.base_settings_manager import BaseSettingsManager


class RiskAnalyticsSettingsManager(BaseSettingsManager):
    """
    Settings manager for Risk Analytics module.

    Settings are persisted to ~/.quant_terminal/risk_analytics_settings.json
    """

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            # Benchmark settings
            "default_benchmark": "SPY",
            # Risk-free rate settings
            "risk_free_source": "irx",  # "irx" (^IRX 3-month T-bill) or "manual"
            "manual_risk_free_rate": 0.05,  # 5% default manual rate
            # Analysis settings
            "lookback_days": 252,  # 1 year default (trading days)
            "show_currency_factor": True,  # Show currency in factor decomposition
            # Display settings
            "decimal_places": 2,  # Decimal places for percentages
            # Table settings
            "collapsed_sectors": [],  # List of sector names to start collapsed
        }

    @property
    def settings_filename(self) -> str:
        return "risk_analytics_settings.json"
