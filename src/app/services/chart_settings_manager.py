from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PySide6.QtCore import Qt


class ChartSettingsManager:
    """
    Manages chart appearance settings with persistent storage.
    Settings are saved to disk and loaded on startup.
    """

    # Default settings (used when no custom settings are set)
    DEFAULT_SETTINGS = {
        # Candle colors (RGB tuples)
        "candle_up_color": (76, 153, 0),
        "candle_down_color": (200, 50, 50),

        # Chart background (None means use theme default)
        "chart_background": None,

        # Candle width
        "candle_width": 0.6,

        # Line chart settings
        "line_color": None,  # None means use theme default
        "line_width": 2,
        "line_style": Qt.SolidLine,

        # Price label
        "show_price_label": True,  # ON by default

        # Date label (crosshair)
        "show_date_label": True,  # ON by default
    }

    # Path to save/load settings
    _SAVE_PATH = Path.home() / ".quant_terminal" / "chart_settings.json"

    # Qt PenStyle mapping for JSON serialization
    _PENSTYLE_TO_STR = {
        Qt.SolidLine: "solid",
        Qt.DashLine: "dash",
        Qt.DotLine: "dot",
        Qt.DashDotLine: "dashdot",
    }
    
    _STR_TO_PENSTYLE = {
        "solid": Qt.SolidLine,
        "dash": Qt.DashLine,
        "dot": Qt.DotLine,
        "dashdot": Qt.DashDotLine,
    }

    def __init__(self):
        self._settings = self.DEFAULT_SETTINGS.copy()
        self.load_settings()

    def get_setting(self, key: str) -> Any:
        """Get a specific setting value."""
        return self._settings.get(key)

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
            
            # Serialize settings
            serialized = self._serialize_settings(self._settings)
            
            # Write to JSON file
            with open(self._SAVE_PATH, 'w') as f:
                json.dump(serialized, f, indent=2)
                
            print(f"Saved chart settings to {self._SAVE_PATH}")
            
        except Exception as e:
            print(f"Error saving chart settings: {e}")

    def load_settings(self) -> None:
        """Load settings from disk."""
        try:
            if not self._SAVE_PATH.exists():
                print(f"No saved chart settings found at {self._SAVE_PATH}")
                return
            
            # Read from JSON file
            with open(self._SAVE_PATH, 'r') as f:
                data = json.load(f)
            
            # Deserialize settings
            deserialized = self._deserialize_settings(data)
            
            # Update settings
            self._settings.update(deserialized)
            
            print(f"Loaded chart settings from {self._SAVE_PATH}")
            
        except Exception as e:
            print(f"Error loading chart settings: {e}")
            # Use defaults on error
            self._settings = self.DEFAULT_SETTINGS.copy()

    def _serialize_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Convert settings to JSON-serializable format."""
        serialized = {}
        
        for key, value in settings.items():
            if isinstance(value, Qt.PenStyle):
                # Convert Qt.PenStyle to string
                serialized[key] = self._PENSTYLE_TO_STR.get(value, "solid")
            elif isinstance(value, tuple):
                # Convert tuples to lists for JSON
                serialized[key] = list(value)
            else:
                serialized[key] = value
        
        return serialized

    def _deserialize_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert settings from JSON format to runtime format."""
        deserialized = {}
        
        for key, value in data.items():
            if key == "line_style" and isinstance(value, str):
                # Convert string to Qt.PenStyle
                deserialized[key] = self._STR_TO_PENSTYLE.get(value, Qt.SolidLine)
            elif key in ["candle_up_color", "candle_down_color", "line_color"] and isinstance(value, list):
                # Convert lists to tuples for colors
                deserialized[key] = tuple(value) if value else None
            else:
                deserialized[key] = value
        
        return deserialized

    def has_custom_setting(self, key: str) -> bool:
        """Check if a setting has been customized (differs from default)."""
        return self._settings.get(key) != self.DEFAULT_SETTINGS.get(key)

    def get_candle_colors(self) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Get candle up and down colors."""
        up = self._settings.get("candle_up_color", self.DEFAULT_SETTINGS["candle_up_color"])
        down = self._settings.get("candle_down_color", self.DEFAULT_SETTINGS["candle_down_color"])
        return up, down

    def get_line_settings(self) -> Dict[str, Any]:
        """Get line chart settings."""
        return {
            "color": self._settings.get("line_color"),
            "width": self._settings.get("line_width", 2),
            "style": self._settings.get("line_style", Qt.SolidLine),
        }