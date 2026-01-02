"""Performance Metrics Settings Manager - Persistent settings storage."""

from __future__ import annotations

from typing import Dict, Any

from app.services.base_settings_manager import BaseSettingsManager


class PerformanceMetricsSettingsManager(BaseSettingsManager):
    """
    Settings manager for Performance Metrics module.

    Settings are persisted to ~/.quant_terminal/performance_metrics_settings.json
    """

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        return {
            "risk_free_source": "irx",  # "irx" (^IRX 3-month T-bill) or "manual"
            "manual_risk_free_rate": 0.05,  # 5% default manual rate
            "decimal_places": 2,  # Decimal places for display
            # Column visibility settings
            "show_3_months": True,
            "show_6_months": True,
            "show_12_months": True,
            "show_ytd": True,
        }

    @property
    def settings_filename(self) -> str:
        return "performance_metrics_settings.json"
