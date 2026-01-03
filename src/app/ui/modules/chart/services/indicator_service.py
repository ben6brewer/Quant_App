from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Type, Any
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    import pandas as pd
    import numpy as np


class IndicatorService:
    """
    Service for calculating technical indicators.
    Implements indicators manually using pandas and numpy (no external dependencies).
    All indicators are user-created and persisted to disk.
    
    Now supports loading custom indicator plugins from Python files.
    """

    # Storage for user-created indicators (starts empty)
    OVERLAY_INDICATORS = {}
    OSCILLATOR_INDICATORS = {}
    ALL_INDICATORS = {}
    
    # Storage for custom indicator classes loaded from files
    CUSTOM_INDICATOR_CLASSES = {}

    # Path to save/load custom indicators
    _SAVE_PATH = Path.home() / ".quant_terminal" / "custom_indicators.json"
    
    # Path to custom indicator plugin files
    _PLUGIN_PATH = Path(__file__).parent.parent / "custom_indicators"

    # Path to save/load plugin indicator appearance overrides
    _PLUGIN_APPEARANCE_PATH = Path.home() / ".quant_terminal" / "plugin_indicator_appearance.json"

    # Storage for plugin appearance overrides (keyed by plugin NAME)
    PLUGIN_APPEARANCE_OVERRIDES = {}

    # Lazy initialization flag
    _initialized = False

    # Column metadata for multi-line indicators (for per-line customization)
    INDICATOR_COLUMN_METADATA = {
        "bbands": [
            {"column": "BB_Upper", "label": "Upper Band", "default_color": (255, 100, 100), "default_style": Qt.DashLine},
            {"column": "BB_Middle", "label": "Middle Band", "default_color": (255, 255, 100), "default_style": Qt.SolidLine},
            {"column": "BB_Lower", "label": "Lower Band", "default_color": (100, 255, 100), "default_style": Qt.DashLine}
        ],
        "macd": [
            {"column": "MACD", "label": "MACD Line", "default_color": (0, 150, 255), "default_style": Qt.SolidLine},
            {"column": "MACDs", "label": "Signal Line", "default_color": (255, 150, 0), "default_style": Qt.SolidLine},
            {"column": "MACDh", "label": "Histogram", "default_color": (150, 150, 150), "default_style": Qt.SolidLine}
        ],
        "stochastic": [
            {"column": "STOCHk", "label": "%K Line", "default_color": (0, 150, 255), "default_style": Qt.SolidLine},
            {"column": "STOCHd", "label": "%D Line", "default_color": (255, 150, 0), "default_style": Qt.SolidLine}
        ],
        "sma": [
            {"column": "SMA", "label": "SMA", "default_color": (0, 150, 255), "default_style": Qt.SolidLine}
        ],
        "ema": [
            {"column": "EMA", "label": "EMA", "default_color": (255, 150, 0), "default_style": Qt.SolidLine}
        ],
        "rsi": [
            {"column": "RSI", "label": "RSI", "default_color": (150, 0, 255), "default_style": Qt.SolidLine}
        ],
        "atr": [
            {"column": "ATR", "label": "ATR", "default_color": (255, 200, 0), "default_style": Qt.SolidLine}
        ],
        "obv": [
            {"column": "OBV", "label": "OBV", "default_color": (0, 255, 150), "default_style": Qt.SolidLine}
        ],
        "vwap": [
            {"column": "VWAP", "label": "VWAP", "default_color": (255, 0, 150), "default_style": Qt.SolidLine}
        ],
        "volume": [
            {"column": "Volume", "label": "Volume", "default_color": (100, 100, 100), "default_style": Qt.SolidLine}
        ]
    }

    # Path to save Volume indicator settings
    _VOLUME_SETTINGS_PATH = Path.home() / ".quant_terminal" / "volume_settings.json"

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

    @classmethod
    def _serialize_appearance(cls, appearance: Dict[str, Any]) -> Dict[str, Any]:
        """Convert appearance dict to JSON-serializable format (handles nested dicts)."""
        if not appearance:
            return appearance

        serialized = {}

        for key, value in appearance.items():
            # Recursively serialize nested dicts (for per_line_appearance)
            if isinstance(value, dict):
                serialized[key] = cls._serialize_appearance(value)
            # Convert Qt.PenStyle to string
            elif key == "line_style" and isinstance(value, Qt.PenStyle):
                serialized[key] = cls._PENSTYLE_TO_STR.get(value, "solid")
            else:
                serialized[key] = value

        return serialized
    
    @classmethod
    def _deserialize_appearance(cls, appearance: Dict[str, Any]) -> Dict[str, Any]:
        """Convert appearance dict from JSON format to runtime format (handles nested dicts)."""
        if not appearance:
            return appearance

        deserialized = {}

        for key, value in appearance.items():
            # Recursively deserialize nested dicts (for per_line_appearance)
            if isinstance(value, dict):
                deserialized[key] = cls._deserialize_appearance(value)
            # Convert string to Qt.PenStyle
            elif key == "line_style" and isinstance(value, str):
                deserialized[key] = cls._STR_TO_PENSTYLE.get(value, Qt.SolidLine)
            else:
                deserialized[key] = value

        return deserialized

    @classmethod
    def _migrate_to_per_line_appearance(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate old indicator config to per_line_appearance format.

        Creates per_line_appearance from metadata defaults for built-in indicators.
        For indicators without metadata, returns empty dict.
        """
        kind = config.get("kind")
        metadata_list = cls.INDICATOR_COLUMN_METADATA.get(kind, [])

        if not metadata_list:
            # No metadata available (plugin or unknown indicator)
            return {}

        per_line_appearance = {}
        for meta in metadata_list:
            column = meta["column"]
            per_line_appearance[column] = {
                "label": meta["label"],
                "visible": True,
                "color": meta["default_color"],
                "line_width": 2,
                "line_style": meta["default_style"],
                "marker_shape": "o",
                "marker_size": 10
            }

        return per_line_appearance

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Lazy initialization - called automatically when needed."""
        if not cls._initialized:
            cls.initialize()

    @classmethod
    def initialize(cls) -> None:
        """Initialize the service and load saved indicators and plugins."""
        if cls._initialized:
            return
        cls._initialized = True  # Set early to prevent recursive calls
        cls.load_indicators()
        cls.load_custom_indicator_plugins()
        cls.load_plugin_appearance_overrides()
        cls._register_builtin_volume()
        cls.load_volume_settings()

    @classmethod
    def _register_builtin_volume(cls) -> None:
        """Register the built-in Volume indicator."""
        volume_config = {
            "kind": "volume",
            "builtin": True,  # Mark as built-in (cannot be deleted)
            "display_type": "histogram",  # Default display mode
            "up_color": (76, 153, 0),  # Green for up bars
            "down_color": (200, 50, 50),  # Red for down bars
            "line_color": (100, 100, 100),  # Used when display_type is "line"
            "line_width": 2,
        }
        cls.ALL_INDICATORS["Volume"] = volume_config
        cls.OSCILLATOR_INDICATORS["Volume"] = volume_config  # Volume is an oscillator

    @classmethod
    def save_volume_settings(cls) -> None:
        """Save Volume indicator settings."""
        if "Volume" not in cls.ALL_INDICATORS:
            return
        try:
            cls._VOLUME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            config = cls.ALL_INDICATORS["Volume"]
            settings = {
                "display_type": config.get("display_type", "histogram"),
                "up_color": list(config.get("up_color", (76, 153, 0))),
                "down_color": list(config.get("down_color", (200, 50, 50))),
                "line_color": list(config.get("line_color", (100, 100, 100))),
                "line_width": config.get("line_width", 2),
            }
            with open(cls._VOLUME_SETTINGS_PATH, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Error saving volume settings: {e}")

    @classmethod
    def load_volume_settings(cls) -> None:
        """Load Volume indicator settings."""
        if not cls._VOLUME_SETTINGS_PATH.exists():
            return
        try:
            with open(cls._VOLUME_SETTINGS_PATH, "r") as f:
                settings = json.load(f)
            if "Volume" in cls.ALL_INDICATORS:
                # Convert color lists back to tuples
                if "up_color" in settings:
                    settings["up_color"] = tuple(settings["up_color"])
                if "down_color" in settings:
                    settings["down_color"] = tuple(settings["down_color"])
                if "line_color" in settings:
                    settings["line_color"] = tuple(settings["line_color"])
                cls.ALL_INDICATORS["Volume"].update(settings)
                cls.OSCILLATOR_INDICATORS["Volume"].update(settings)
        except Exception as e:
            print(f"Error loading volume settings: {e}")

    @classmethod
    def load_custom_indicator_plugins(cls) -> None:
        """
        Load custom indicator plugins from the custom_indicators directory.
        
        Each plugin should be a Python file containing a class that inherits
        from BaseIndicator.
        """
        if not cls._PLUGIN_PATH.exists():
            cls._PLUGIN_PATH.mkdir(parents=True, exist_ok=True)
            print(f"Created custom indicators directory: {cls._PLUGIN_PATH}")
            return
        
        # Find all Python files in the plugin directory
        plugin_files = list(cls._PLUGIN_PATH.glob("*.py"))
        
        if not plugin_files:
            print(f"No custom indicator plugins found in {cls._PLUGIN_PATH}")
            return
        
        print(f"Loading custom indicator plugins from {cls._PLUGIN_PATH}")
        
        # CRITICAL FIX: Add the plugin directory to sys.path FIRST
        # This allows imports between plugin files to work (e.g., from base_indicator import BaseIndicator)
        plugin_path_str = str(cls._PLUGIN_PATH)
        if plugin_path_str not in sys.path:
            sys.path.insert(0, plugin_path_str)
        
        for plugin_file in plugin_files:
            try:
                # Skip __init__.py and base_indicator.py
                if plugin_file.name.startswith("__") or plugin_file.name == "base_indicator.py":
                    continue
                
                # Load the module
                module_name = plugin_file.stem
                spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                if spec is None or spec.loader is None:
                    print(f"  Failed to load spec for {plugin_file.name}")
                    continue
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Find classes that inherit from BaseIndicator
                # We need to import BaseIndicator or check for the right methods
                indicator_classes = []
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, 'calculate') and 
                        hasattr(attr, 'NAME') and
                        attr_name != 'BaseIndicator'):
                        indicator_classes.append(attr)
                
                # Register each indicator class
                for indicator_class in indicator_classes:
                    cls._register_custom_indicator_class(indicator_class)
                    print(f"  Loaded: {indicator_class.NAME} from {plugin_file.name}")
                
            except Exception as e:
                print(f"  Error loading plugin {plugin_file.name}: {e}")
                import traceback
                traceback.print_exc()

    @classmethod
    def _register_custom_indicator_class(cls, indicator_class: Type[Any]) -> None:
        """Register a custom indicator class."""
        name = indicator_class.NAME
        is_overlay = indicator_class.IS_OVERLAY
        
        # Store the class
        cls.CUSTOM_INDICATOR_CLASSES[name] = indicator_class
        
        # Add to appropriate category
        # For plugin-based indicators, we use a special config that includes the class
        config = {"kind": "plugin", "class": name}
        
        cls.ALL_INDICATORS[name] = config
        
        if is_overlay:
            cls.OVERLAY_INDICATORS[name] = config
        else:
            cls.OSCILLATOR_INDICATORS[name] = config

    @classmethod
    def get_overlay_names(cls) -> List[str]:
        """Get list of overlay indicator names."""
        cls._ensure_initialized()
        return sorted(list(cls.OVERLAY_INDICATORS.keys()))

    @classmethod
    def get_oscillator_names(cls) -> List[str]:
        """Get list of oscillator indicator names."""
        cls._ensure_initialized()
        return sorted(list(cls.OSCILLATOR_INDICATORS.keys()))

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Get list of all indicator names."""
        cls._ensure_initialized()
        return sorted(list(cls.ALL_INDICATORS.keys()))

    @classmethod
    def is_overlay(cls, indicator_name: str) -> bool:
        """Check if indicator is an overlay (plots on price chart)."""
        cls._ensure_initialized()
        return indicator_name in cls.OVERLAY_INDICATORS

    @classmethod
    def get_column_metadata(cls, indicator_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get column metadata for an indicator (for per-line customization).

        Returns list of dicts with keys: column, label, default_color, default_style
        For plugin indicators, returns None (requires preview calculation).

        Args:
            indicator_name: Name of the indicator

        Returns:
            List of column metadata dicts, or None for plugin indicators
        """
        cls._ensure_initialized()
        if indicator_name not in cls.ALL_INDICATORS:
            return []

        config = cls.ALL_INDICATORS[indicator_name]
        kind = config.get("kind")

        # Plugin indicators need preview calculation
        if kind == "plugin":
            return None

        # Return metadata for built-in indicators
        return cls.INDICATOR_COLUMN_METADATA.get(kind, [])

    @classmethod
    def preview_indicator_columns(cls, indicator_name: str) -> List[str]:
        """
        Preview which columns an indicator will produce.
        For plugins, calculates on sample data. For built-ins, uses metadata.

        Args:
            indicator_name: Name of the indicator

        Returns:
            List of column names
        """
        metadata = cls.get_column_metadata(indicator_name)

        # If we have metadata, extract column names
        if metadata is not None:
            return [m["column"] for m in metadata]

        # Plugin indicator - need to calculate preview
        try:
            from app.services.market_data import fetch_price_history

            # Fetch minimal sample data (BTC-USD, last 365 days)
            df = fetch_price_history("BTC-USD", period="1y", interval="1d")
            if df is None or df.empty:
                return []

            # Calculate indicator
            result_df = cls.calculate(df, indicator_name)
            if result_df is None or result_df.empty:
                return []

            return list(result_df.columns)

        except Exception as e:
            print(f"Error previewing indicator columns: {e}")
            return []

    @classmethod
    def add_custom_indicator(cls, name: str, config: dict, is_overlay: bool = True) -> None:
        """
        Add a custom indicator to the available indicators.
        
        Args:
            name: Display name for the indicator (e.g., "SMA(365)")
            config: Configuration dict with 'kind' and parameters
            is_overlay: True if overlay, False if oscillator
        """
        cls.ALL_INDICATORS[name] = config
        
        if is_overlay:
            cls.OVERLAY_INDICATORS[name] = config
        else:
            cls.OSCILLATOR_INDICATORS[name] = config
        
        # Auto-save after adding
        cls.save_indicators()

    @classmethod
    def remove_custom_indicator(cls, name: str) -> None:
        """
        Remove a custom indicator.
        Note: Cannot remove plugin-based indicators (they're loaded from files).
        Note: Cannot remove built-in indicators (like Volume).
        """
        # Check if this is a built-in indicator
        config = cls.ALL_INDICATORS.get(name, {})
        if config.get("builtin", False):
            print(f"Cannot remove built-in indicator '{name}'.")
            return

        # Check if this is a plugin-based indicator
        if name in cls.CUSTOM_INDICATOR_CLASSES:
            print(f"Cannot remove plugin-based indicator '{name}'. Delete the plugin file instead.")
            return

        cls.ALL_INDICATORS.pop(name, None)
        cls.OVERLAY_INDICATORS.pop(name, None)
        cls.OSCILLATOR_INDICATORS.pop(name, None)
        
        # Auto-save after removing
        cls.save_indicators()

    @classmethod
    def save_indicators(cls) -> None:
        """
        Save all custom indicators to disk.
        Note: Plugin-based indicators are not saved here (they're in plugin files).
        """
        try:
            # Create directory if it doesn't exist
            cls._SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Filter out plugin-based indicators and serialize appearance
            overlays_to_save = {}
            for k, v in cls.OVERLAY_INDICATORS.items():
                if v.get("kind") != "plugin":
                    config = v.copy()
                    if "appearance" in config:
                        config["appearance"] = cls._serialize_appearance(config["appearance"])
                    if "per_line_appearance" in config:
                        config["per_line_appearance"] = cls._serialize_appearance(config["per_line_appearance"])
                    overlays_to_save[k] = config

            oscillators_to_save = {}
            for k, v in cls.OSCILLATOR_INDICATORS.items():
                if v.get("kind") != "plugin":
                    config = v.copy()
                    if "appearance" in config:
                        config["appearance"] = cls._serialize_appearance(config["appearance"])
                    if "per_line_appearance" in config:
                        config["per_line_appearance"] = cls._serialize_appearance(config["per_line_appearance"])
                    oscillators_to_save[k] = config
            
            # Prepare data to save
            data = {
                "overlays": overlays_to_save,
                "oscillators": oscillators_to_save,
            }
            
            # Write to JSON file
            with open(cls._SAVE_PATH, 'w') as f:
                json.dump(data, f, indent=2)
                
            saved_count = len(overlays_to_save) + len(oscillators_to_save)
            print(f"Saved {saved_count} indicators to {cls._SAVE_PATH}")
            
        except Exception as e:
            print(f"Error saving indicators: {e}")

    @classmethod
    def save_plugin_appearance_overrides(cls) -> None:
        """Save plugin indicator appearance overrides to disk."""
        try:
            cls._PLUGIN_APPEARANCE_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Serialize appearance overrides
            serialized_overrides = {}
            for plugin_name, per_line_appearance in cls.PLUGIN_APPEARANCE_OVERRIDES.items():
                serialized_overrides[plugin_name] = cls._serialize_appearance(per_line_appearance)

            # Write to JSON
            with open(cls._PLUGIN_APPEARANCE_PATH, 'w') as f:
                json.dump(serialized_overrides, f, indent=2)

            print(f"Saved appearance overrides for {len(serialized_overrides)} plugins")
        except Exception as e:
            print(f"Error saving plugin appearance overrides: {e}")

    @classmethod
    def load_plugin_appearance_overrides(cls) -> None:
        """Load plugin appearance overrides from disk. Called AFTER plugins are loaded."""
        try:
            if not cls._PLUGIN_APPEARANCE_PATH.exists():
                print(f"No plugin appearance overrides found")
                return

            with open(cls._PLUGIN_APPEARANCE_PATH, 'r') as f:
                data = json.load(f)

            cls.PLUGIN_APPEARANCE_OVERRIDES = {}
            for plugin_name, per_line_appearance in data.items():
                # Skip if plugin no longer exists
                if plugin_name not in cls.CUSTOM_INDICATOR_CLASSES:
                    print(f"  Skipping overrides for removed plugin: {plugin_name}")
                    continue

                # Get current columns from plugin
                current_columns = set(cls.preview_indicator_columns(plugin_name))
                if not current_columns:
                    print(f"  Could not determine columns for: {plugin_name}")
                    continue

                # Filter to only matching columns
                deserialized = cls._deserialize_appearance(per_line_appearance)
                filtered = {
                    col: settings
                    for col, settings in deserialized.items()
                    if col in current_columns
                }

                if filtered:
                    cls.PLUGIN_APPEARANCE_OVERRIDES[plugin_name] = filtered
                    print(f"  Loaded overrides for '{plugin_name}' ({len(filtered)} columns)")

            print(f"Loaded appearance overrides for {len(cls.PLUGIN_APPEARANCE_OVERRIDES)} plugins")
        except Exception as e:
            print(f"Error loading plugin appearance overrides: {e}")
            import traceback
            traceback.print_exc()
            cls.PLUGIN_APPEARANCE_OVERRIDES = {}

    @classmethod
    def get_plugin_appearance(cls, plugin_name: str) -> Dict[str, Any]:
        """Get appearance overrides for a plugin (empty dict if none)."""
        return cls.PLUGIN_APPEARANCE_OVERRIDES.get(plugin_name, {})

    @classmethod
    def set_plugin_appearance(cls, plugin_name: str, per_line_appearance: Dict[str, Any]) -> None:
        """Set appearance overrides for a plugin and auto-save."""
        if plugin_name not in cls.CUSTOM_INDICATOR_CLASSES:
            print(f"Warning: Unknown plugin: {plugin_name}")
            return

        # Validate columns
        current_columns = set(cls.preview_indicator_columns(plugin_name))
        filtered = {
            col: settings
            for col, settings in per_line_appearance.items()
            if col in current_columns
        }

        if filtered:
            cls.PLUGIN_APPEARANCE_OVERRIDES[plugin_name] = filtered
            cls.save_plugin_appearance_overrides()

            # Update config in ALL_INDICATORS
            if plugin_name in cls.ALL_INDICATORS:
                cls.ALL_INDICATORS[plugin_name]["per_line_appearance"] = filtered
        else:
            cls.PLUGIN_APPEARANCE_OVERRIDES.pop(plugin_name, None)
            cls.save_plugin_appearance_overrides()

    @classmethod
    def load_indicators(cls) -> None:
        """Load custom indicators from disk."""
        try:
            if not cls._SAVE_PATH.exists():
                print(f"No saved indicators found at {cls._SAVE_PATH}")
                return
            
            # Read from JSON file
            with open(cls._SAVE_PATH, 'r') as f:
                data = json.load(f)
            
            # Load overlays and deserialize appearance
            cls.OVERLAY_INDICATORS = {}
            for k, v in data.get("overlays", {}).items():
                config = v.copy()
                if "appearance" in config:
                    config["appearance"] = cls._deserialize_appearance(config["appearance"])
                if "per_line_appearance" in config:
                    config["per_line_appearance"] = cls._deserialize_appearance(config["per_line_appearance"])
                else:
                    # MIGRATION: Auto-populate per_line_appearance from metadata if missing
                    config["per_line_appearance"] = cls._migrate_to_per_line_appearance(config)
                cls.OVERLAY_INDICATORS[k] = config

            # Load oscillators and deserialize appearance
            cls.OSCILLATOR_INDICATORS = {}
            for k, v in data.get("oscillators", {}).items():
                config = v.copy()
                if "appearance" in config:
                    config["appearance"] = cls._deserialize_appearance(config["appearance"])
                if "per_line_appearance" in config:
                    config["per_line_appearance"] = cls._deserialize_appearance(config["per_line_appearance"])
                else:
                    # MIGRATION: Auto-populate per_line_appearance from metadata if missing
                    config["per_line_appearance"] = cls._migrate_to_per_line_appearance(config)
                cls.OSCILLATOR_INDICATORS[k] = config
            
            # Rebuild ALL_INDICATORS
            cls.ALL_INDICATORS = {**cls.OVERLAY_INDICATORS, **cls.OSCILLATOR_INDICATORS}
            
            print(f"Loaded {len(cls.ALL_INDICATORS)} indicators from {cls._SAVE_PATH}")
            
        except Exception as e:
            print(f"Error loading indicators: {e}")
            # Initialize with empty dicts on error
            cls.OVERLAY_INDICATORS = {}
            cls.OSCILLATOR_INDICATORS = {}
            cls.ALL_INDICATORS = {}

    @classmethod
    def calculate(
        cls, df: "pd.DataFrame", indicator_name: str
    ) -> Optional["pd.DataFrame"]:
        """
        Calculate a specific indicator.

        Args:
            df: DataFrame with OHLCV data
            indicator_name: Name of the indicator to calculate

        Returns:
            DataFrame with indicator values, or None if calculation fails
        """
        cls._ensure_initialized()
        if indicator_name not in cls.ALL_INDICATORS:
            return None

        config = cls.ALL_INDICATORS[indicator_name]
        kind = config["kind"]

        try:
            # Check if this is a plugin-based indicator
            if kind == "plugin":
                return cls._calculate_plugin_indicator(df, indicator_name)
            
            # Built-in indicators
            if kind == "sma":
                return cls._calculate_sma(df, config["length"])
            elif kind == "ema":
                return cls._calculate_ema(df, config["length"])
            elif kind == "bbands":
                return cls._calculate_bbands(df, config["length"], config["std"])
            elif kind == "rsi":
                return cls._calculate_rsi(df, config["length"])
            elif kind == "macd":
                return cls._calculate_macd(df, config["fast"], config["slow"], config["signal"])
            elif kind == "atr":
                return cls._calculate_atr(df, config["length"])
            elif kind == "stochastic":
                return cls._calculate_stochastic(df, config["k"], config["d"], config["smooth_k"])
            elif kind == "obv":
                return cls._calculate_obv(df)
            elif kind == "vwap":
                return cls._calculate_vwap(df)
            elif kind == "volume":
                return cls._calculate_volume(df)
            return None

        except Exception as e:
            print(f"Error calculating {indicator_name}: {e}")
            return None

    @classmethod
    def _calculate_plugin_indicator(cls, df: "pd.DataFrame", indicator_name: str) -> Optional["pd.DataFrame"]:
        """Calculate a plugin-based custom indicator."""
        if indicator_name not in cls.CUSTOM_INDICATOR_CLASSES:
            print(f"Plugin class not found for {indicator_name}")
            return None
        
        try:
            # Get the indicator class
            indicator_class = cls.CUSTOM_INDICATOR_CLASSES[indicator_name]
            
            # Create an instance and calculate
            indicator_instance = indicator_class()
            result = indicator_instance.calculate(df)
            
            return result
            
        except Exception as e:
            print(f"Error calculating plugin indicator {indicator_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    @classmethod
    def calculate_multiple(
        cls, df: "pd.DataFrame", indicator_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate multiple indicators.

        Args:
            df: DataFrame with OHLCV data
            indicator_names: List of indicator names to calculate

        Returns:
            Dictionary mapping indicator names to dicts containing:
                - "data": DataFrame with indicator values
                - "per_line_appearance": Per-line appearance settings dict (or empty dict if none)
        """
        results = {}
        for name in indicator_names:
            result_df = cls.calculate(df, name)
            if result_df is not None:
                # Get appearance settings from config if available
                config = cls.ALL_INDICATORS.get(name, {})
                per_line_appearance = config.get("per_line_appearance", {})

                # For plugin indicators, use overrides
                if config.get("kind") == "plugin":
                    per_line_appearance = cls.get_plugin_appearance(name)

                results[name] = {
                    "data": result_df,
                    "per_line_appearance": per_line_appearance,  # Only this field
                }
        return results

    # ========================
    # Indicator Implementations
    # ========================

    @staticmethod
    def _calculate_sma(df: "pd.DataFrame", length: int) -> "pd.DataFrame":
        """Calculate Simple Moving Average."""
        import pandas as pd
        close = df["Close"]
        sma = close.rolling(window=length).mean()
        return pd.DataFrame({"SMA": sma}, index=df.index)

    @staticmethod
    def _calculate_ema(df: "pd.DataFrame", length: int) -> "pd.DataFrame":
        """Calculate Exponential Moving Average."""
        import pandas as pd
        close = df["Close"]
        ema = close.ewm(span=length, adjust=False).mean()
        return pd.DataFrame({"EMA": ema}, index=df.index)

    @staticmethod
    def _calculate_bbands(df: "pd.DataFrame", length: int, std: float) -> "pd.DataFrame":
        """Calculate Bollinger Bands."""
        import pandas as pd
        close = df["Close"]

        # Middle band is SMA
        middle = close.rolling(window=length).mean()

        # Standard deviation
        rolling_std = close.rolling(window=length).std()

        # Upper and lower bands
        upper = middle + (rolling_std * std)
        lower = middle - (rolling_std * std)

        return pd.DataFrame({
            "BB_Upper": upper,
            "BB_Middle": middle,
            "BB_Lower": lower,
        }, index=df.index)

    @staticmethod
    def _calculate_rsi(df: "pd.DataFrame", length: int = 14) -> "pd.DataFrame":
        """Calculate Relative Strength Index."""
        import pandas as pd
        close = df["Close"]

        # Calculate price changes
        delta = close.diff()

        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)

        # Calculate average gains and losses using EMA
        avg_gains = gains.ewm(span=length, adjust=False).mean()
        avg_losses = losses.ewm(span=length, adjust=False).mean()

        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        return pd.DataFrame({"RSI": rsi}, index=df.index)

    @staticmethod
    def _calculate_macd(
        df: "pd.DataFrame", fast: int = 12, slow: int = 26, signal: int = 9
    ) -> "pd.DataFrame":
        """Calculate MACD (Moving Average Convergence Divergence)."""
        import pandas as pd
        close = df["Close"]

        # Calculate fast and slow EMAs
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line (EMA of MACD)
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()

        # Histogram
        histogram = macd_line - signal_line

        return pd.DataFrame({
            "MACD": macd_line,
            "MACDs": signal_line,
            "MACDh": histogram,
        }, index=df.index)

    @staticmethod
    def _calculate_stochastic(
        df: "pd.DataFrame", k: int = 14, d: int = 3, smooth_k: int = 3
    ) -> "pd.DataFrame":
        """Calculate Stochastic Oscillator."""
        import pandas as pd
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        # Lowest low and highest high over k periods
        lowest_low = low.rolling(window=k).min()
        highest_high = high.rolling(window=k).max()

        # %K (fast stochastic)
        k_fast = 100 * (close - lowest_low) / (highest_high - lowest_low)

        # Smooth %K
        k_slow = k_fast.rolling(window=smooth_k).mean()

        # %D (signal line)
        d_line = k_slow.rolling(window=d).mean()

        return pd.DataFrame({
            "STOCHk": k_slow,
            "STOCHd": d_line,
        }, index=df.index)

    @staticmethod
    def _calculate_atr(df: "pd.DataFrame", length: int = 14) -> "pd.DataFrame":
        """Calculate Average True Range."""
        import pandas as pd
        high = df["High"]
        low = df["Low"]
        close = df["Close"]

        # True Range calculation
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR is EMA of TR
        atr = tr.ewm(span=length, adjust=False).mean()

        return pd.DataFrame({"ATR": atr}, index=df.index)

    @staticmethod
    def _calculate_obv(df: "pd.DataFrame") -> "pd.DataFrame":
        """Calculate On-Balance Volume."""
        import numpy as np
        import pandas as pd
        if "Volume" not in df.columns:
            return None

        close = df["Close"]
        volume = df["Volume"]

        # Price direction
        price_change = close.diff()

        # OBV calculation
        obv = (np.sign(price_change) * volume).fillna(0).cumsum()

        return pd.DataFrame({"OBV": obv}, index=df.index)

    @staticmethod
    def _calculate_vwap(df: "pd.DataFrame") -> "pd.DataFrame":
        """Calculate Volume Weighted Average Price."""
        import pandas as pd
        if "Volume" not in df.columns:
            return None

        high = df["High"]
        low = df["Low"]
        close = df["Close"]
        volume = df["Volume"]

        # Typical price
        typical_price = (high + low + close) / 3

        # VWAP calculation (cumulative)
        vwap = (typical_price * volume).cumsum() / volume.cumsum()

        return pd.DataFrame({"VWAP": vwap}, index=df.index)

    @staticmethod
    def _calculate_volume(df: "pd.DataFrame") -> "pd.DataFrame":
        """Return Volume data with candle direction for coloring."""
        import pandas as pd

        if "Volume" not in df.columns:
            return None

        volume = df["Volume"].copy()

        # Calculate direction: 1 for up (close > open), -1 for down (close < open), 0 for unchanged
        direction = (df["Close"] > df["Open"]).astype(int) - (
            df["Close"] < df["Open"]
        ).astype(int)

        return pd.DataFrame(
            {"Volume": volume, "Volume_Direction": direction}, index=df.index
        )