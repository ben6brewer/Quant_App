"""Factor Model Service - OLS regression for factor decomposition.

This service runs factor regressions for each security to decompose returns
into systematic (factor) and idiosyncratic components.

Regression Specification (simplified for robustness):
R_i - RF = alpha + beta1(Mkt-RF) + beta2(SMB) + beta3(HML) + beta4(RMW) +
           beta5(CMA) + beta6(UMD) + epsilon

Note: Sector and country effects are captured through the metadata but not
included as dummy variables in the regression to avoid multicollinearity.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd


@dataclass
class FactorRegressionResult:
    """Result of a factor model regression for a single security."""

    ticker: str
    betas: Dict[str, float] = field(default_factory=dict)
    alpha: float = 0.0
    r_squared: float = 0.0
    adj_r_squared: float = 0.0
    residuals: Optional["pd.Series"] = None
    fitted_values: Optional["pd.Series"] = None
    t_stats: Dict[str, float] = field(default_factory=dict)
    p_values: Dict[str, float] = field(default_factory=dict)
    n_observations: int = 0
    regression_date: str = ""
    sector: str = ""
    country: str = ""
    # Pre-computed volatilities (stored in cache since residuals aren't serialized)
    idio_vol: float = 0.0  # Annualized idiosyncratic volatility
    factor_vol: float = 0.0  # Annualized factor volatility

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (excludes Series)."""
        return {
            "ticker": self.ticker,
            "betas": self.betas,
            "alpha": self.alpha,
            "r_squared": self.r_squared,
            "adj_r_squared": self.adj_r_squared,
            "t_stats": self.t_stats,
            "p_values": self.p_values,
            "n_observations": self.n_observations,
            "regression_date": self.regression_date,
            "sector": self.sector,
            "country": self.country,
            "idio_vol": self.idio_vol,
            "factor_vol": self.factor_vol,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FactorRegressionResult":
        """Create instance from dictionary."""
        return cls(
            ticker=data.get("ticker", ""),
            betas=data.get("betas", {}),
            alpha=data.get("alpha", 0.0),
            r_squared=data.get("r_squared", 0.0),
            adj_r_squared=data.get("adj_r_squared", 0.0),
            t_stats=data.get("t_stats", {}),
            p_values=data.get("p_values", {}),
            n_observations=data.get("n_observations", 0),
            regression_date=data.get("regression_date", ""),
            sector=data.get("sector", ""),
            country=data.get("country", ""),
            idio_vol=data.get("idio_vol", 0.0),
            factor_vol=data.get("factor_vol", 0.0),
        )


class FactorModelService:
    """
    Runs factor model regressions for securities.

    Uses OLS regression to decompose security returns into factor exposures
    and idiosyncratic returns. Results are cached to avoid recomputation.
    """

    _CACHE_DIR = Path.home() / ".quant_terminal" / "cache" / "regressions"
    _lock = threading.Lock()

    # Core Fama-French factors (no dummies to avoid multicollinearity)
    CORE_FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]

    # Minimum observations required for regression
    MIN_OBSERVATIONS = 126  # ~6 months of data

    @classmethod
    def _ensure_dir(cls) -> None:
        """Create cache directory if needed."""
        cls._CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _get_cache_path(cls, ticker: str) -> Path:
        """Get cache file path for a ticker."""
        return cls._CACHE_DIR / f"{ticker.upper()}_regression.json"

    @classmethod
    def _load_cached_result(cls, ticker: str) -> Optional[FactorRegressionResult]:
        """Load cached regression result if exists and not stale."""
        cache_path = cls._get_cache_path(ticker)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            return FactorRegressionResult.from_dict(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[FactorModel] Error loading cache for {ticker}: {e}")
            return None

    @classmethod
    def _save_cached_result(cls, result: FactorRegressionResult) -> None:
        """Save regression result to cache."""
        cls._ensure_dir()
        cache_path = cls._get_cache_path(result.ticker)
        try:
            with open(cache_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
        except IOError as e:
            print(f"[FactorModel] Error saving cache for {result.ticker}: {e}")

    @classmethod
    def run_factor_regression(
        cls,
        ticker: str,
        excess_returns: "pd.Series",
        ff_factors: "pd.DataFrame",
        sector: str = "Not Classified",
        country: str = "US",
        use_cache: bool = True,
    ) -> Optional[FactorRegressionResult]:
        """
        Run factor regression for a single security.

        Uses a simplified model with just FF5 + Momentum factors.

        Args:
            ticker: Ticker symbol
            excess_returns: Series of excess returns (R - RF)
            ff_factors: Fama-French factors DataFrame
            sector: GICS sector name (stored in result, not used in regression)
            country: Country name (stored in result, not used in regression)
            use_cache: Whether to use cached results

        Returns:
            FactorRegressionResult or None if insufficient data
        """
        import numpy as np
        import pandas as pd
        from scipy import stats

        ticker_upper = ticker.upper()

        # Check cache first
        if use_cache:
            cached = cls._load_cached_result(ticker_upper)
            if cached is not None:
                # Check if cache is recent (within 7 days)
                if cached.regression_date:
                    try:
                        cache_date = datetime.fromisoformat(cached.regression_date)
                        if (datetime.now() - cache_date).days < 7:
                            return cached
                    except ValueError:
                        pass

        # Clean the returns - drop NaN and infinite values
        excess_returns = excess_returns.replace([np.inf, -np.inf], np.nan).dropna()

        # Validate minimum observations
        if len(excess_returns) < cls.MIN_OBSERVATIONS:
            return None  # Silent skip for insufficient data

        # Align factors with returns dates
        common_dates = excess_returns.index.intersection(ff_factors.index)
        if len(common_dates) < cls.MIN_OBSERVATIONS:
            return None

        # Get aligned data
        y = excess_returns.loc[common_dates].values
        X_factors = ff_factors.loc[common_dates, cls.CORE_FACTORS].values

        # Check for NaN in factors
        if np.isnan(X_factors).any() or np.isnan(y).any():
            # Try to clean up
            valid_mask = ~(np.isnan(X_factors).any(axis=1) | np.isnan(y))
            if valid_mask.sum() < cls.MIN_OBSERVATIONS:
                return None
            y = y[valid_mask]
            X_factors = X_factors[valid_mask]
            common_dates = common_dates[valid_mask]

        # Add constant for intercept
        X = np.column_stack([np.ones(len(y)), X_factors])
        factor_names = ["const"] + cls.CORE_FACTORS

        n = len(y)
        k = X.shape[1]

        if n <= k:
            return None  # Not enough observations for regression

        try:
            # Use pseudo-inverse for numerical stability
            XtX = X.T @ X

            # Check condition number
            cond = np.linalg.cond(XtX)
            if cond > 1e10:
                # Matrix is ill-conditioned, use pseudo-inverse
                XtX_inv = np.linalg.pinv(XtX)
            else:
                XtX_inv = np.linalg.inv(XtX)

            Xty = X.T @ y
            betas = XtX_inv @ Xty

            # Fitted values and residuals
            fitted = X @ betas
            residuals = y - fitted

            # R-squared
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
            r_squared = max(0.0, min(1.0, r_squared))  # Clamp to [0, 1]

            # Adjusted R-squared
            if n > k + 1:
                adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k - 1)
                adj_r_squared = max(0.0, min(1.0, adj_r_squared))
            else:
                adj_r_squared = r_squared

            # Standard errors and t-statistics
            mse = ss_res / (n - k) if n > k else 1.0
            var_betas = np.diag(XtX_inv) * mse
            # Ensure non-negative variances
            var_betas = np.maximum(var_betas, 1e-10)
            se_betas = np.sqrt(var_betas)
            t_stats = betas / se_betas

            # P-values (two-tailed)
            df = max(n - k, 1)
            p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), df=df))

            # Build result
            betas_dict = {name: float(betas[i]) for i, name in enumerate(factor_names)}
            t_stats_dict = {name: float(t_stats[i]) for i, name in enumerate(factor_names)}
            p_values_dict = {name: float(p_values[i]) for i, name in enumerate(factor_names)}

            # Extract alpha (constant term)
            alpha = betas_dict.get("const", 0.0)

            # Compute annualized volatilities (stored in cache)
            idio_vol_ann = float(np.std(residuals) * np.sqrt(252))
            factor_vol_ann = float(np.std(fitted) * np.sqrt(252))

            result = FactorRegressionResult(
                ticker=ticker_upper,
                betas=betas_dict,
                alpha=alpha,
                r_squared=float(r_squared),
                adj_r_squared=float(adj_r_squared),
                residuals=pd.Series(residuals, index=common_dates),
                fitted_values=pd.Series(fitted, index=common_dates),
                t_stats=t_stats_dict,
                p_values=p_values_dict,
                n_observations=n,
                regression_date=datetime.now().isoformat(),
                sector=sector,
                country=country,
                idio_vol=idio_vol_ann,
                factor_vol=factor_vol_ann,
            )

            # Cache result
            if use_cache:
                cls._save_cached_result(result)

            return result

        except Exception as e:
            # Silent failure - don't spam console
            return None

    @classmethod
    def run_portfolio_regressions(
        cls,
        ticker_excess_returns: "pd.DataFrame",
        ff_factors: "pd.DataFrame",
        metadata: Dict[str, Dict[str, Any]],
        max_workers: int = 10,
        use_cache: bool = True,
    ) -> Dict[str, FactorRegressionResult]:
        """
        Run factor regressions for all securities in portfolio.

        Args:
            ticker_excess_returns: DataFrame with excess returns (columns = tickers)
            ff_factors: Fama-French factors DataFrame
            metadata: Dict mapping ticker to metadata (sector, country, etc.)
            max_workers: Max parallel workers for regression
            use_cache: Whether to use cached results

        Returns:
            Dict mapping ticker to FactorRegressionResult
        """
        results: Dict[str, FactorRegressionResult] = {}
        tickers = list(ticker_excess_returns.columns)

        print(f"[FactorModel] Running regressions for {len(tickers)} securities...")

        def run_single_regression(ticker: str) -> Tuple[str, Optional[FactorRegressionResult]]:
            """Run regression for a single ticker."""
            excess_returns = ticker_excess_returns[ticker]

            # Get metadata
            ticker_meta = metadata.get(ticker.upper(), {})
            sector = ticker_meta.get("sector", "Not Classified")
            country = ticker_meta.get("country", "US")

            result = cls.run_factor_regression(
                ticker=ticker,
                excess_returns=excess_returns,
                ff_factors=ff_factors,
                sector=sector,
                country=country,
                use_cache=use_cache,
            )

            return ticker, result

        # Run regressions in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_single_regression, ticker): ticker
                for ticker in tickers
            }

            completed = 0
            successful = 0
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    ticker, result = future.result()
                    if result is not None:
                        results[ticker.upper()] = result
                        successful += 1
                except Exception:
                    pass  # Silent failure

                completed += 1
                if completed % 500 == 0:
                    print(f"[FactorModel] Progress: {completed}/{len(tickers)} ({successful} successful)")

        print(f"[FactorModel] Completed {successful}/{len(tickers)} successful regressions")

        return results

    @classmethod
    def clear_cache(cls, ticker: Optional[str] = None) -> None:
        """
        Clear regression cache.

        Args:
            ticker: Specific ticker to clear, or None to clear all
        """
        with cls._lock:
            if ticker:
                cache_path = cls._get_cache_path(ticker)
                if cache_path.exists():
                    cache_path.unlink()
                    print(f"[FactorModel] Cleared cache for {ticker}")
            else:
                # Clear all caches
                if cls._CACHE_DIR.exists():
                    for cache_file in cls._CACHE_DIR.glob("*_regression.json"):
                        cache_file.unlink()
                    print("[FactorModel] Cleared all regression caches")
