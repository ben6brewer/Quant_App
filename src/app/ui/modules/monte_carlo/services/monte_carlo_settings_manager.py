"""Monte Carlo Settings Manager - Persistent settings for Monte Carlo module."""

from typing import Any, Dict

from app.services.base_settings_manager import BaseSettingsManager


class MonteCarloSettingsManager(BaseSettingsManager):
    """
    Settings manager for Monte Carlo simulation module.

    Persists user preferences for simulation parameters, visualization options,
    and benchmark configuration.
    """

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
            "show_gridlines": True,
            "show_terminal_histogram": True,
            "show_var_cvar": True,
            "var_confidence_level": 0.95,
        }

    @property
    def settings_filename(self) -> str:
        """Settings file name."""
        return "monte_carlo_settings.json"

    def _serialize_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Convert RGB tuples to lists for JSON serialization."""
        result = settings.copy()
        for key in ["band_90_color", "band_50_color", "median_color", "mean_color"]:
            if key in result and isinstance(result[key], tuple):
                result[key] = list(result[key])
        return result

    def _deserialize_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert lists back to RGB tuples."""
        result = data.copy()
        for key in ["band_90_color", "band_50_color", "median_color", "mean_color"]:
            if key in result and isinstance(result[key], list):
                result[key] = tuple(result[key])
        return result
