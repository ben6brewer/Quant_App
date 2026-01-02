"""Monte Carlo Simulation Service.

Provides simulation engines for portfolio projection and risk analysis.
Supports both historical bootstrap and parametric simulation methods.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd


@dataclass
class SimulationResult:
    """Result container for Monte Carlo simulation.

    Attributes:
        paths: Simulated portfolio value paths, shape (n_simulations, n_periods + 1)
        terminal_values: Final portfolio values for each simulation
        dates: Projected dates for the simulation horizon
        percentiles: Pre-computed percentile paths for visualization
        method: Simulation method used ("bootstrap" or "parametric")
        initial_value: Starting portfolio value
        n_simulations: Number of simulation paths
        n_periods: Number of time periods simulated
    """

    paths: Any  # np.ndarray
    terminal_values: Any  # np.ndarray
    dates: Any  # pd.DatetimeIndex
    percentiles: Dict[int, Any] = field(default_factory=dict)
    method: str = "bootstrap"
    initial_value: float = 100.0
    n_simulations: int = 1000
    n_periods: int = 252

    @property
    def mean_path(self) -> Any:
        """Average portfolio value path across all simulations."""
        return self.paths.mean(axis=0)

    @property
    def median_path(self) -> Any:
        """Median portfolio value path across all simulations."""
        import numpy as np
        return np.median(self.paths, axis=0)

    @property
    def median_terminal(self) -> float:
        """Median final portfolio value."""
        import numpy as np
        return float(np.median(self.terminal_values))

    @property
    def mean_terminal(self) -> float:
        """Mean final portfolio value."""
        import numpy as np
        return float(np.mean(self.terminal_values))

    @property
    def terminal_cagr(self) -> float:
        """Compound annual growth rate implied by median terminal value."""
        years = self.n_periods / 252
        if years <= 0 or self.initial_value <= 0:
            return float("nan")
        return (self.median_terminal / self.initial_value) ** (1 / years) - 1

    def get_percentile(self, p: int) -> Any:
        """Get or compute a percentile path.

        Args:
            p: Percentile (0-100)

        Returns:
            Array of portfolio values at the given percentile for each time step
        """
        import numpy as np
        if p not in self.percentiles:
            self.percentiles[p] = np.percentile(self.paths, p, axis=0)
        return self.percentiles[p]


class MonteCarloService:
    """Monte Carlo simulation service for portfolio projections.

    Provides two simulation methods:
    1. Historical Bootstrap: Resamples actual historical returns
    2. Parametric: Simulates from fitted normal distribution

    Both methods support block resampling to preserve autocorrelation.
    """

    @staticmethod
    def simulate_historical_bootstrap(
        returns: "pd.Series",
        n_simulations: int = 1000,
        n_periods: int = 252,
        initial_value: float = 100.0,
        block_size: int = 21,
        percentiles: Optional[List[int]] = None,
        seed: Optional[int] = None,
    ) -> SimulationResult:
        """
        Run Monte Carlo simulation using historical bootstrap.

        Resamples historical returns with replacement to generate future
        scenarios. Uses block bootstrap to preserve short-term autocorrelation
        and momentum effects in the data.

        Args:
            returns: Historical daily returns series (as decimals)
            n_simulations: Number of simulation paths to generate
            n_periods: Number of trading days to simulate (252 = 1 year)
            initial_value: Starting portfolio value
            block_size: Size of blocks for block bootstrap (21 = ~1 month)
            percentiles: List of percentiles to pre-compute (e.g., [5, 25, 50, 75, 95])
            seed: Random seed for reproducibility

        Returns:
            SimulationResult with simulated paths and statistics
        """
        import numpy as np
        import pandas as pd

        if percentiles is None:
            percentiles = [5, 10, 25, 50, 75, 90, 95]

        if seed is not None:
            np.random.seed(seed)

        # Clean returns
        clean_returns = returns.dropna().values
        if len(clean_returns) < block_size:
            # Not enough data - fall back to simple bootstrap
            block_size = max(1, len(clean_returns) // 2)

        n_returns = len(clean_returns)
        if n_returns == 0:
            # Return empty result
            return SimulationResult(
                paths=np.full((n_simulations, n_periods + 1), initial_value),
                terminal_values=np.full(n_simulations, initial_value),
                dates=pd.date_range(start=pd.Timestamp.now(), periods=n_periods + 1, freq="B"),
                method="bootstrap",
                initial_value=initial_value,
                n_simulations=n_simulations,
                n_periods=n_periods,
            )

        # Generate simulated returns using vectorized block bootstrap
        n_blocks = (n_periods + block_size - 1) // block_size

        # Vectorized block bootstrap:
        # Generate all block starting points at once
        all_block_starts = np.random.randint(
            0, n_returns - block_size + 1, size=(n_simulations, n_blocks)
        )

        # Create offset array for block indices [0, 1, 2, ..., block_size-1]
        offsets = np.arange(block_size)

        # Build all indices using broadcasting
        # Shape: (n_simulations, n_blocks, block_size)
        block_indices = all_block_starts[:, :, np.newaxis] + offsets

        # Flatten blocks and slice to n_periods
        # Shape: (n_simulations, n_blocks * block_size) -> (n_simulations, n_periods)
        block_indices = block_indices.reshape(n_simulations, -1)[:, :n_periods]

        # Extract all returns at once using advanced indexing
        simulated_returns = clean_returns[block_indices]

        # Convert returns to portfolio values using vectorized cumprod
        # paths[i, j] = portfolio value at time j for simulation i
        cumulative_returns = np.cumprod(1 + simulated_returns, axis=1)
        paths = np.zeros((n_simulations, n_periods + 1))
        paths[:, 0] = initial_value
        paths[:, 1:] = initial_value * cumulative_returns

        # Extract terminal values
        terminal_values = paths[:, -1]

        # Generate projected dates
        dates = pd.date_range(start=pd.Timestamp.now(), periods=n_periods + 1, freq="B")

        # Pre-compute percentiles
        percentile_paths = {}
        for p in percentiles:
            percentile_paths[p] = np.percentile(paths, p, axis=0)

        return SimulationResult(
            paths=paths,
            terminal_values=terminal_values,
            dates=dates,
            percentiles=percentile_paths,
            method="bootstrap",
            initial_value=initial_value,
            n_simulations=n_simulations,
            n_periods=n_periods,
        )

    @staticmethod
    def simulate_parametric(
        mean: float,
        std: float,
        n_simulations: int = 1000,
        n_periods: int = 252,
        initial_value: float = 100.0,
        percentiles: Optional[List[int]] = None,
        seed: Optional[int] = None,
    ) -> SimulationResult:
        """
        Run Monte Carlo simulation using parametric assumptions.

        Generates random returns from a normal distribution with specified
        mean and standard deviation. Faster than bootstrap and works even
        with limited historical data.

        Args:
            mean: Mean daily return (as decimal, e.g., 0.0004 = 0.04%)
            std: Daily standard deviation (as decimal, e.g., 0.01 = 1%)
            n_simulations: Number of simulation paths to generate
            n_periods: Number of trading days to simulate (252 = 1 year)
            initial_value: Starting portfolio value
            percentiles: List of percentiles to pre-compute
            seed: Random seed for reproducibility

        Returns:
            SimulationResult with simulated paths and statistics
        """
        import numpy as np
        import pandas as pd

        if percentiles is None:
            percentiles = [5, 10, 25, 50, 75, 90, 95]

        if seed is not None:
            np.random.seed(seed)

        # Generate random returns from normal distribution
        simulated_returns = np.random.normal(mean, std, (n_simulations, n_periods))

        # Convert returns to portfolio values using vectorized cumprod
        cumulative_returns = np.cumprod(1 + simulated_returns, axis=1)
        paths = np.zeros((n_simulations, n_periods + 1))
        paths[:, 0] = initial_value
        paths[:, 1:] = initial_value * cumulative_returns

        # Extract terminal values
        terminal_values = paths[:, -1]

        # Generate projected dates
        dates = pd.date_range(start=pd.Timestamp.now(), periods=n_periods + 1, freq="B")

        # Pre-compute percentiles
        percentile_paths = {}
        for p in percentiles:
            percentile_paths[p] = np.percentile(paths, p, axis=0)

        return SimulationResult(
            paths=paths,
            terminal_values=terminal_values,
            dates=dates,
            percentiles=percentile_paths,
            method="parametric",
            initial_value=initial_value,
            n_simulations=n_simulations,
            n_periods=n_periods,
        )

    @staticmethod
    def calculate_var_cvar(
        terminal_values: Any,  # np.ndarray
        initial_value: float = 100.0,
        confidence_levels: Optional[List[float]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate Value at Risk (VaR) and Conditional VaR (CVaR/Expected Shortfall).

        VaR represents the maximum loss at a given confidence level.
        CVaR represents the expected loss given that loss exceeds VaR.

        Args:
            terminal_values: Array of terminal portfolio values from simulation
            initial_value: Starting portfolio value
            confidence_levels: List of confidence levels (e.g., [0.95, 0.99])

        Returns:
            Dict with VaR and CVaR for each confidence level:
            {
                "0.95": {"var_pct": -10.5, "var_abs": -10500, "cvar_pct": -15.2, "cvar_abs": -15200},
                "0.99": {...}
            }
        """
        import numpy as np

        if confidence_levels is None:
            confidence_levels = [0.90, 0.95, 0.99]

        # Calculate returns from initial to terminal
        returns = (terminal_values - initial_value) / initial_value

        results = {}
        for level in confidence_levels:
            # VaR is the (1 - level) percentile of returns
            # E.g., 95% VaR is the 5th percentile
            var_pct = np.percentile(returns, (1 - level) * 100)
            var_abs = var_pct * initial_value

            # CVaR is the mean of returns below VaR
            cvar_returns = returns[returns <= var_pct]
            if len(cvar_returns) > 0:
                cvar_pct = cvar_returns.mean()
            else:
                cvar_pct = var_pct
            cvar_abs = cvar_pct * initial_value

            results[f"{level:.2f}"] = {
                "var_pct": float(var_pct * 100),  # Convert to percentage
                "var_abs": float(var_abs),
                "cvar_pct": float(cvar_pct * 100),
                "cvar_abs": float(cvar_abs),
            }

        return results

    @staticmethod
    def calculate_probability_metrics(
        terminal_values: Any,  # np.ndarray
        initial_value: float = 100.0,
        thresholds: Optional[List[float]] = None,
    ) -> Dict[str, float]:
        """
        Calculate probability-based metrics from simulation results.

        Args:
            terminal_values: Array of terminal portfolio values
            initial_value: Starting portfolio value
            thresholds: Return thresholds to evaluate (as decimals, e.g., [0, 0.1, 0.2])

        Returns:
            Dict with probability metrics:
            - prob_positive: Probability of positive return
            - prob_loss_10pct: Probability of losing more than 10%
            - prob_gain_20pct: Probability of gaining more than 20%
            - etc.
        """
        if thresholds is None:
            thresholds = [-0.20, -0.10, 0, 0.10, 0.20, 0.50, 1.0]

        returns = (terminal_values - initial_value) / initial_value
        n_sims = len(terminal_values)

        results = {
            "prob_positive": float((returns > 0).sum() / n_sims),
            "prob_negative": float((returns < 0).sum() / n_sims),
        }

        for threshold in thresholds:
            if threshold < 0:
                # Probability of loss exceeding threshold (e.g., losing more than 10%)
                key = f"prob_loss_{abs(int(threshold * 100))}pct"
                results[key] = float((returns < threshold).sum() / n_sims)
            elif threshold > 0:
                # Probability of gain exceeding threshold
                key = f"prob_gain_{int(threshold * 100)}pct"
                results[key] = float((returns > threshold).sum() / n_sims)

        return results

    @staticmethod
    def calculate_annualized_volatility(
        paths: Any,  # np.ndarray
    ) -> float:
        """
        Calculate annualized volatility from simulation paths.

        Args:
            paths: Simulated portfolio value paths, shape (n_simulations, n_periods + 1)

        Returns:
            Annualized volatility as a decimal (e.g., 0.20 = 20%)
        """
        import numpy as np

        # Calculate daily returns for each path
        daily_returns = paths[:, 1:] / paths[:, :-1] - 1

        # Calculate mean daily volatility across all simulations
        daily_vol = np.std(daily_returns)

        # Annualize (assuming 252 trading days)
        annualized_vol = daily_vol * np.sqrt(252)

        return float(annualized_vol)

    @staticmethod
    def calculate_max_drawdown(
        paths: Any,  # np.ndarray
    ) -> Dict[str, float]:
        """
        Calculate max drawdown statistics from simulation paths.

        Args:
            paths: Simulated portfolio value paths, shape (n_simulations, n_periods + 1)

        Returns:
            Dict with median and mean max drawdown as percentages
        """
        import numpy as np

        # Vectorized max drawdown calculation across all simulations
        # Compute running maximum along each path (axis=1)
        running_max = np.maximum.accumulate(paths, axis=1)

        # Compute drawdown at each point (negative values indicate drawdown)
        drawdown = (paths - running_max) / running_max

        # Get max drawdown (most negative value) for each simulation
        max_drawdowns = drawdown.min(axis=1)

        return {
            "median_mdd": float(np.median(max_drawdowns) * 100),
            "mean_mdd": float(np.mean(max_drawdowns) * 100),
        }

    @staticmethod
    def calculate_outperformance_probability(
        portfolio_terminal: Any,  # np.ndarray
        benchmark_terminal: Any,  # np.ndarray
    ) -> Dict[str, float]:
        """
        Calculate probability of portfolio outperforming benchmark.

        Args:
            portfolio_terminal: Terminal values from portfolio simulation
            benchmark_terminal: Terminal values from benchmark simulation

        Returns:
            Dict with probabilities for both directions
        """
        import numpy as np

        n_sims = len(portfolio_terminal)
        port_beats_bench = (portfolio_terminal > benchmark_terminal).sum()

        prob_port_beats = float(port_beats_bench / n_sims)
        prob_bench_beats = 1.0 - prob_port_beats

        return {
            "portfolio_beats_benchmark": prob_port_beats,
            "benchmark_beats_portfolio": prob_bench_beats,
        }
