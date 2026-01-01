"""Portfolio Settings Manager - Manages portfolio construction settings with persistence."""

from __future__ import annotations

from typing import Dict, Any

from app.services.base_settings_manager import BaseSettingsManager


class PortfolioSettingsManager(BaseSettingsManager):
    """
    Manages portfolio construction settings with persistent storage.

    Simple implementation using base class defaults - no special serialization needed.
    """

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        """Default portfolio settings."""
        return {
            "highlight_editable_fields": True,
            "hide_free_cash_summary": False,
        }

    @property
    def settings_filename(self) -> str:
        """Settings file name."""
        return "portfolio_settings.json"
