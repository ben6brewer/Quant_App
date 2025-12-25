from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import numpy as np


class IndicatorService:
    """
    Service for calculating technical indicators.
    Implements indicators manually using pandas and numpy (no external dependencies).
    All indicators are user-created and persisted to disk.
    """

    # Storage for user-created indicators (starts empty)
    OVERLAY_INDICATORS = {}
    OSCILLATOR_INDICATORS = {}
    ALL_INDICATORS = {}

    # Path to save/load custom indicators
    _SAVE_PATH = Path.home() / ".quant_terminal" / "custom_indicators.json"

    @classmethod
    def initialize(cls) -> None:
        """Initialize the service and load saved indicators."""
        cls.load_indicators()

    @classmethod
    def get_overlay_names(cls) -> List[str]:
        """Get list of overlay indicator names."""
        return sorted(list(cls.OVERLAY_INDICATORS.keys()))

    @classmethod
    def get_oscillator_names(cls) -> List[str]:
        """Get list of oscillator indicator names."""
        return sorted(list(cls.OSCILLATOR_INDICATORS.keys()))

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Get list of all indicator names."""
        return sorted(list(cls.ALL_INDICATORS.keys()))

    @classmethod
    def is_overlay(cls, indicator_name: str) -> bool:
        """Check if indicator is an overlay (plots on price chart)."""
        return indicator_name in cls.OVERLAY_INDICATORS

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
        """Remove a custom indicator."""
        cls.ALL_INDICATORS.pop(name, None)
        cls.OVERLAY_INDICATORS.pop(name, None)
        cls.OSCILLATOR_INDICATORS.pop(name, None)
        
        # Auto-save after removing
        cls.save_indicators()

    @classmethod
    def save_indicators(cls) -> None:
        """Save all custom indicators to disk."""
        try:
            # Create directory if it doesn't exist
            cls._SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data to save
            data = {
                "overlays": cls.OVERLAY_INDICATORS,
                "oscillators": cls.OSCILLATOR_INDICATORS,
            }
            
            # Write to JSON file
            with open(cls._SAVE_PATH, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"Saved {len(cls.ALL_INDICATORS)} indicators to {cls._SAVE_PATH}")
            
        except Exception as e:
            print(f"Error saving indicators: {e}")

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
            
            # Load overlays
            cls.OVERLAY_INDICATORS = data.get("overlays", {})
            
            # Load oscillators
            cls.OSCILLATOR_INDICATORS = data.get("oscillators", {})
            
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
        cls, df: pd.DataFrame, indicator_name: str
    ) -> Optional[pd.DataFrame]:
        """
        Calculate a specific indicator.

        Args:
            df: DataFrame with OHLCV data
            indicator_name: Name of the indicator to calculate

        Returns:
            DataFrame with indicator values, or None if calculation fails
        """
        if indicator_name not in cls.ALL_INDICATORS:
            return None

        config = cls.ALL_INDICATORS[indicator_name]
        kind = config["kind"]

        try:
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
            return None

        except Exception as e:
            print(f"Error calculating {indicator_name}: {e}")
            return None

    @classmethod
    def calculate_multiple(
        cls, df: pd.DataFrame, indicator_names: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """
        Calculate multiple indicators.

        Args:
            df: DataFrame with OHLCV data
            indicator_names: List of indicator names to calculate

        Returns:
            Dictionary mapping indicator names to their calculated DataFrames
        """
        results = {}
        for name in indicator_names:
            result = cls.calculate(df, name)
            if result is not None:
                results[name] = result
        return results

    # ========================
    # Indicator Implementations
    # ========================

    @staticmethod
    def _calculate_sma(df: pd.DataFrame, length: int) -> pd.DataFrame:
        """Calculate Simple Moving Average."""
        close = df["Close"]
        sma = close.rolling(window=length).mean()
        return pd.DataFrame({"SMA": sma}, index=df.index)

    @staticmethod
    def _calculate_ema(df: pd.DataFrame, length: int) -> pd.DataFrame:
        """Calculate Exponential Moving Average."""
        close = df["Close"]
        ema = close.ewm(span=length, adjust=False).mean()
        return pd.DataFrame({"EMA": ema}, index=df.index)

    @staticmethod
    def _calculate_bbands(df: pd.DataFrame, length: int, std: float) -> pd.DataFrame:
        """Calculate Bollinger Bands."""
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
    def _calculate_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
        """Calculate Relative Strength Index."""
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
        df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        """Calculate MACD (Moving Average Convergence Divergence)."""
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
        df: pd.DataFrame, k: int = 14, d: int = 3, smooth_k: int = 3
    ) -> pd.DataFrame:
        """Calculate Stochastic Oscillator."""
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
    def _calculate_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
        """Calculate Average True Range."""
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
    def _calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate On-Balance Volume."""
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
    def _calculate_vwap(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Volume Weighted Average Price."""
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