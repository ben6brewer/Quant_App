"""Constructed Factor Service - Calculates factors from price/volume data.

This service constructs additional risk factors that are not available
from the Fama-French dataset:
- Volatility: Rolling 60-day standard deviation of returns
- Liquidity: Rolling 30-day average dollar volume
- Reversal: Prior 21-day cumulative return (short-term reversal)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    import pandas as pd


class ConstructedFactorService:
    """
    Calculates constructed factors from price and volume data.

    These factors capture additional dimensions of risk not covered
    by the standard Fama-French factors.
    """

    @staticmethod
    def calculate_volatility_factor(
        returns: "pd.Series",
        window: int = 60,
    ) -> "pd.Series":
        """
        Calculate rolling volatility factor for a security.

        Higher volatility = higher factor exposure.

        Args:
            returns: Daily returns series
            window: Rolling window in trading days (default 60 = ~3 months)

        Returns:
            Series of rolling volatility values (annualized)
        """
        import numpy as np

        if returns is None or len(returns) < window:
            import pandas as pd
            return pd.Series(dtype=float)

        # Calculate rolling standard deviation, annualized
        rolling_vol = returns.rolling(window=window).std() * np.sqrt(252)

        return rolling_vol

    @staticmethod
    def calculate_liquidity_factor(
        price_data: "pd.DataFrame",
        window: int = 30,
    ) -> "pd.Series":
        """
        Calculate rolling liquidity factor from dollar volume.

        Higher liquidity (dollar volume) = lower factor exposure (inverse).
        We take log and invert so illiquid stocks have higher exposure.

        Args:
            price_data: DataFrame with 'Close' and 'Volume' columns
            window: Rolling window in trading days (default 30)

        Returns:
            Series of liquidity factor values (inverted, standardized)
        """
        import numpy as np
        import pandas as pd

        if price_data is None or len(price_data) < window:
            return pd.Series(dtype=float)

        if "Close" not in price_data.columns or "Volume" not in price_data.columns:
            return pd.Series(dtype=float)

        # Dollar volume = price * shares traded
        dollar_volume = price_data["Close"] * price_data["Volume"]

        # Rolling average dollar volume
        rolling_dollar_vol = dollar_volume.rolling(window=window).mean()

        # Take log to reduce skewness
        log_dollar_vol = np.log1p(rolling_dollar_vol)

        # Invert and standardize (higher = less liquid)
        # Negative because low liquidity = high risk
        liquidity_factor = -log_dollar_vol

        return liquidity_factor

    @staticmethod
    def calculate_reversal_factor(
        returns: "pd.Series",
        window: int = 21,
    ) -> "pd.Series":
        """
        Calculate short-term reversal factor.

        Cumulative return over prior 21 days (approx 1 month).
        Short-term reversal effect: losers tend to rebound, winners regress.

        Args:
            returns: Daily returns series
            window: Lookback window in trading days (default 21 = ~1 month)

        Returns:
            Series of prior period cumulative returns
        """
        import numpy as np

        if returns is None or len(returns) < window:
            import pandas as pd
            return pd.Series(dtype=float)

        # Rolling cumulative return over window
        # Using product of (1 + r) - 1
        rolling_cum_return = (
            (1 + returns)
            .rolling(window=window)
            .apply(lambda x: np.prod(x) - 1, raw=True)
        )

        return rolling_cum_return

    @staticmethod
    def get_security_factors(
        returns: "pd.Series",
        price_data: "pd.DataFrame",
        vol_window: int = 60,
        liq_window: int = 30,
        rev_window: int = 21,
    ) -> "pd.DataFrame":
        """
        Calculate all constructed factors for a single security.

        Args:
            returns: Daily returns series
            price_data: DataFrame with Close and Volume columns
            vol_window: Volatility rolling window
            liq_window: Liquidity rolling window
            rev_window: Reversal lookback window

        Returns:
            DataFrame with columns: Volatility, Liquidity, Reversal
        """
        import pandas as pd

        volatility = ConstructedFactorService.calculate_volatility_factor(
            returns, vol_window
        )
        liquidity = ConstructedFactorService.calculate_liquidity_factor(
            price_data, liq_window
        )
        reversal = ConstructedFactorService.calculate_reversal_factor(
            returns, rev_window
        )

        # Combine into DataFrame, aligning on common index
        factors = pd.DataFrame({
            "Volatility": volatility,
            "Liquidity": liquidity,
            "Reversal": reversal,
        })

        return factors

    @staticmethod
    def get_portfolio_factors(
        ticker_returns: "pd.DataFrame",
        ticker_price_data: Dict[str, "pd.DataFrame"],
        vol_window: int = 60,
        liq_window: int = 30,
        rev_window: int = 21,
    ) -> Dict[str, "pd.DataFrame"]:
        """
        Calculate constructed factors for all securities in portfolio.

        Args:
            ticker_returns: DataFrame with ticker returns (columns = tickers)
            ticker_price_data: Dict mapping ticker to price DataFrame
            vol_window: Volatility rolling window
            liq_window: Liquidity rolling window
            rev_window: Reversal lookback window

        Returns:
            Dict mapping ticker to factor DataFrame
        """
        result: Dict[str, "pd.DataFrame"] = {}

        for ticker in ticker_returns.columns:
            returns = ticker_returns[ticker]
            price_data = ticker_price_data.get(ticker)

            if price_data is None:
                continue

            factors = ConstructedFactorService.get_security_factors(
                returns, price_data, vol_window, liq_window, rev_window
            )

            if not factors.empty:
                result[ticker] = factors

        return result

    @staticmethod
    def standardize_factors(
        factor_series: "pd.Series",
        window: Optional[int] = None,
    ) -> "pd.Series":
        """
        Standardize factor values (z-score).

        Args:
            factor_series: Raw factor values
            window: Rolling window for standardization, or None for full sample

        Returns:
            Standardized factor values (mean=0, std=1)
        """
        import pandas as pd

        if factor_series is None or len(factor_series) == 0:
            return pd.Series(dtype=float)

        if window:
            # Rolling standardization
            rolling_mean = factor_series.rolling(window=window).mean()
            rolling_std = factor_series.rolling(window=window).std()
            standardized = (factor_series - rolling_mean) / rolling_std
        else:
            # Full sample standardization
            mean = factor_series.mean()
            std = factor_series.std()
            if std > 0:
                standardized = (factor_series - mean) / std
            else:
                standardized = factor_series - mean

        return standardized

    @staticmethod
    def create_cross_sectional_factors(
        all_ticker_factors: Dict[str, "pd.DataFrame"],
        date: str,
    ) -> Dict[str, float]:
        """
        Create cross-sectional factor exposures for a given date.

        Standardizes factors across all securities at a point in time,
        which is more appropriate for factor model regressions.

        Args:
            all_ticker_factors: Dict mapping ticker to factor DataFrame
            date: Date string (YYYY-MM-DD) to extract cross-section

        Returns:
            Dict mapping ticker to standardized factor exposures
        """
        import pandas as pd
        import numpy as np

        result: Dict[str, Dict[str, float]] = {}
        factor_names = ["Volatility", "Liquidity", "Reversal"]

        # Collect all values for each factor at this date
        factor_values: Dict[str, Dict[str, float]] = {f: {} for f in factor_names}

        date_ts = pd.Timestamp(date)

        for ticker, factors_df in all_ticker_factors.items():
            if date_ts not in factors_df.index:
                continue

            for factor_name in factor_names:
                if factor_name in factors_df.columns:
                    val = factors_df.loc[date_ts, factor_name]
                    if pd.notna(val) and np.isfinite(val):
                        factor_values[factor_name][ticker] = val

        # Standardize each factor across securities
        for factor_name in factor_names:
            values = factor_values[factor_name]
            if not values:
                continue

            vals_array = list(values.values())
            mean_val = np.mean(vals_array)
            std_val = np.std(vals_array)

            for ticker, raw_val in values.items():
                if ticker not in result:
                    result[ticker] = {}

                if std_val > 0:
                    result[ticker][factor_name] = (raw_val - mean_val) / std_val
                else:
                    result[ticker][factor_name] = 0.0

        return result
