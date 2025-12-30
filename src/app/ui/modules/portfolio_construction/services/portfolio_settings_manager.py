"""Portfolio Settings Manager - Manages persistent settings for Portfolio Construction module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


class PortfolioSettingsManager:
    """
    Manages portfolio construction settings with persistent storage.
    Settings are saved to disk and loaded on startup.
    """

    # Default settings
    DEFAULT_SETTINGS = {
        "highlight_editable_fields": True,
    }

    # Path to save/load settings
    _SAVE_PATH = Path.home() / ".quant_terminal" / "portfolio_settings.json"

    def __init__(self):
        self._settings = self.DEFAULT_SETTINGS.copy()
        self.load_settings()

    def get_setting(self, key: str) -> Any:
        """Get a specific setting value."""
        return self._settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy()

    def update_settings(self, settings: Dict[str, Any]) -> None:
        """Update settings and save to disk."""
        self._settings.update(settings)
        self.save_settings()

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = self.DEFAULT_SETTINGS.copy()
        self.save_settings()

    def save_settings(self) -> None:
        """Save settings to disk."""
        try:
            # Create directory if it doesn't exist
            self._SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Write to JSON file
            with open(self._SAVE_PATH, 'w') as f:
                json.dump(self._settings, f, indent=2)

        except Exception as e:
            print(f"Error saving portfolio settings: {e}")

    def load_settings(self) -> None:
        """Load settings from disk."""
        try:
            if not self._SAVE_PATH.exists():
                return

            # Read from JSON file
            with open(self._SAVE_PATH, 'r') as f:
                data = json.load(f)

            # Update settings with loaded data
            self._settings.update(data)

        except Exception as e:
            print(f"Error loading portfolio settings: {e}")
            # Use defaults on error
            self._settings = self.DEFAULT_SETTINGS.copy()

    def has_custom_setting(self, key: str) -> bool:
        """Check if a setting has been customized (differs from default)."""
        return self._settings.get(key) != self.DEFAULT_SETTINGS.get(key)
