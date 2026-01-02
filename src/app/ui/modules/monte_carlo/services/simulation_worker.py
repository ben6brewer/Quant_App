"""Background worker for Monte Carlo simulations.

Runs simulations in a background thread to keep the UI responsive.
Supports parallel execution of portfolio and benchmark simulations.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from PySide6.QtCore import QThread, Signal

if TYPE_CHECKING:
    import pandas as pd

from .monte_carlo_service import MonteCarloService, SimulationResult


@dataclass
class SimulationParams:
    """Parameters for running a Monte Carlo simulation."""

    n_simulations: int = 1000
    n_periods: int = 252
    initial_value: float = 100.0
    block_size: int = 21
    method: str = "bootstrap"


@dataclass
class SimulationStats:
    """Pre-computed statistics for a simulation result."""

    var_cvar: Dict[str, Dict[str, float]] = field(default_factory=dict)
    probabilities: Dict[str, float] = field(default_factory=dict)
    ann_vol: float = 0.0
    max_dd: Dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationResultBundle:
    """Complete simulation results with pre-computed statistics.

    Bundles both portfolio and benchmark results along with all
    statistics computed in the background thread.
    """

    portfolio_result: SimulationResult
    portfolio_stats: SimulationStats
    benchmark_result: Optional[SimulationResult] = None
    benchmark_stats: Optional[SimulationStats] = None
    outperformance: Optional[Dict[str, float]] = None


class SimulationWorker(QThread):
    """Background worker for running Monte Carlo simulations.

    Runs simulations in a separate thread to keep the UI responsive.
    Supports parallel execution of portfolio and benchmark simulations
    using ThreadPoolExecutor.

    Signals:
        simulation_complete: Emitted with SimulationResultBundle on success
        simulation_error: Emitted with error message on failure
    """

    simulation_complete = Signal(object)  # SimulationResultBundle
    simulation_error = Signal(str)

    def __init__(
        self,
        portfolio_returns: "pd.Series",
        params: SimulationParams,
        benchmark_returns: Optional["pd.Series"] = None,
        parent=None,
    ):
        """Initialize the simulation worker.

        Args:
            portfolio_returns: Historical daily returns for portfolio
            params: Simulation parameters
            benchmark_returns: Optional historical daily returns for benchmark
            parent: Parent QObject
        """
        super().__init__(parent)
        self._portfolio_returns = portfolio_returns
        self._benchmark_returns = benchmark_returns
        self._params = params
        self._cancelled = False

    def request_cancellation(self):
        """Request graceful cancellation of the simulation."""
        self._cancelled = True

    def run(self):
        """Execute simulations in background thread."""
        try:
            results = {}

            # Use ThreadPoolExecutor for parallel simulation
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}

                # Submit portfolio simulation
                futures[
                    executor.submit(
                        self._run_single_simulation,
                        self._portfolio_returns,
                        "portfolio",
                    )
                ] = "portfolio"

                # Submit benchmark simulation if present
                if self._benchmark_returns is not None:
                    futures[
                        executor.submit(
                            self._run_single_simulation,
                            self._benchmark_returns,
                            "benchmark",
                        )
                    ] = "benchmark"

                # Collect results as they complete
                for future in as_completed(futures):
                    if self._cancelled:
                        return

                    name = futures[future]
                    try:
                        results[name] = future.result()
                    except Exception as e:
                        self.simulation_error.emit(f"Error in {name} simulation: {e}")
                        return

            # Check cancellation
            if self._cancelled:
                return

            # Build result bundle with pre-computed statistics
            bundle = self._build_result_bundle(
                results["portfolio"], results.get("benchmark")
            )

            self.simulation_complete.emit(bundle)

        except Exception as e:
            self.simulation_error.emit(str(e))

    def _run_single_simulation(
        self, returns: "pd.Series", name: str
    ) -> SimulationResult:
        """Run a single simulation (portfolio or benchmark).

        Args:
            returns: Historical daily returns
            name: Identifier for logging/debugging

        Returns:
            SimulationResult with simulated paths
        """
        if self._params.method == "bootstrap":
            return MonteCarloService.simulate_historical_bootstrap(
                returns=returns,
                n_simulations=self._params.n_simulations,
                n_periods=self._params.n_periods,
                initial_value=self._params.initial_value,
                block_size=self._params.block_size,
            )
        else:  # parametric
            mean = returns.mean()
            std = returns.std()
            return MonteCarloService.simulate_parametric(
                mean=mean,
                std=std,
                n_simulations=self._params.n_simulations,
                n_periods=self._params.n_periods,
                initial_value=self._params.initial_value,
            )

    def _compute_stats(self, result: SimulationResult) -> SimulationStats:
        """Compute all statistics for a simulation result.

        Args:
            result: Simulation result with paths and terminal values

        Returns:
            SimulationStats with all pre-computed statistics
        """
        var_cvar = MonteCarloService.calculate_var_cvar(
            result.terminal_values, result.initial_value
        )
        probabilities = MonteCarloService.calculate_probability_metrics(
            result.terminal_values, result.initial_value
        )
        ann_vol = MonteCarloService.calculate_annualized_volatility(result.paths)
        max_dd = MonteCarloService.calculate_max_drawdown(result.paths)

        return SimulationStats(
            var_cvar=var_cvar,
            probabilities=probabilities,
            ann_vol=ann_vol,
            max_dd=max_dd,
        )

    def _build_result_bundle(
        self,
        portfolio_result: SimulationResult,
        benchmark_result: Optional[SimulationResult],
    ) -> SimulationResultBundle:
        """Build complete result bundle with all statistics.

        Args:
            portfolio_result: Simulation result for portfolio
            benchmark_result: Optional simulation result for benchmark

        Returns:
            SimulationResultBundle with all pre-computed statistics
        """
        # Compute portfolio statistics
        portfolio_stats = self._compute_stats(portfolio_result)

        # Compute benchmark statistics if present
        benchmark_stats = None
        outperformance = None

        if benchmark_result is not None:
            benchmark_stats = self._compute_stats(benchmark_result)

            # Compute outperformance probability
            outperformance = MonteCarloService.calculate_outperformance_probability(
                portfolio_result.terminal_values, benchmark_result.terminal_values
            )

        return SimulationResultBundle(
            portfolio_result=portfolio_result,
            portfolio_stats=portfolio_stats,
            benchmark_result=benchmark_result,
            benchmark_stats=benchmark_stats,
            outperformance=outperformance,
        )
