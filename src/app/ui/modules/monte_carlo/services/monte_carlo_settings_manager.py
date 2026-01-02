"""Monte Carlo Settings Manager - Persistent settings for Monte Carlo module."""

from typing import Any, Dict

from PySide6.QtCore import Qt

from app.services.base_settings_manager import BaseSettingsManager


class MonteCarloSettingsManager(BaseSettingsManager):
    """
    Settings manager for Monte Carlo simulation module.

    Persists user preferences for simulation parameters, visualization options,
    and benchmark configuration.
    """

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

    @property
    def DEFAULT_SETTINGS(self) -> Dict[str, Any]:
        """Default settings for Monte Carlo module."""
        return {
            # Simulation parameters
            "simulation_method": "bootstrap",  # "bootstrap" or "parametric"
            "n_simulations": 1000,
            "n_years": 1,  # Simulation horizon in years
            "block_size": 21,  # Block size for bootstrap (trading days)
            "initial_value": 100.0,
            # Percentile bands to display
            "show_band_90": True,  # 5th-95th percentile
            "show_band_50": True,  # 25th-75th percentile
            "show_median": True,
            "show_mean": False,
            # Colors (RGB tuples)
            "band_90_color": (100, 100, 255),  # Light blue
            "band_50_color": (50, 50, 200),  # Darker blue
            "median_color": (255, 255, 255),  # White
            "mean_color": (255, 200, 0),  # Yellow
            # Benchmark settings
            "benchmark": "",  # Empty = no benchmark
            "benchmark_is_portfolio": False,
            # Display options
            "show_gridlines": False,
            "show_terminal_histogram": True,
            "show_var_cvar": True,
            "var_confidence_level": 0.95,
            # Chart Settings
            "show_crosshair": True,
            "show_median_label": True,
            "chart_background": None,  # None = use theme default
            # Portfolio median line customization
            "portfolio_median_color": (255, 255, 255),  # White
            "portfolio_median_line_style": Qt.SolidLine,
            "portfolio_median_line_width": 2,
            "show_portfolio_median": True,
            # Benchmark median line customization
            "benchmark_median_color": (255, 165, 0),  # Orange
            "benchmark_median_line_style": Qt.SolidLine,
            "benchmark_median_line_width": 2,
            "show_benchmark_median": True,
        }

    @property
    def settings_filename(self) -> str:
        """Settings file name."""
        return "monte_carlo_settings.json"

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
            if key.endswith("_line_style") and isinstance(value, str):
                # Convert string to Qt.PenStyle
                deserialized[key] = self._STR_TO_PENSTYLE.get(value, Qt.SolidLine)
            elif key.endswith("_color") and isinstance(value, list):
                # Convert lists to tuples for colors
                deserialized[key] = tuple(value) if value else None
            else:
                deserialized[key] = value

        return deserialized
