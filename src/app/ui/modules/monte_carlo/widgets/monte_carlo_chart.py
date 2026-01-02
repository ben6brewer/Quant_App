"""Monte Carlo Chart Widget - Probability cone visualization with statistics panel."""

from typing import Any, Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QGridLayout,
)
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from ..services.monte_carlo_service import SimulationResult


class StatisticsPanel(QFrame):
    """Panel displaying Monte Carlo simulation statistics with portfolio and benchmark rows."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()

    def _setup_ui(self):
        """Setup statistics panel layout with two rows."""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setMaximumHeight(120)

        layout = QGridLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(12)

        # Column headers (row 0)
        # P(Beat) header will be shown/hidden with benchmark
        headers = ["", "Median", "Mean", "CAGR", "Cum. Ret", "Ann. Vol", "Max DD", "P(Gain)", "P(Loss>10%)", "VaR 95%", "CVaR 95%", "P(Beat)"]
        self._header_labels = []
        for col, header in enumerate(headers):
            label = QLabel(header)
            label.setObjectName("stat_header")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, 0, col)
            self._header_labels.append(label)

        # Row 1: Portfolio
        self.portfolio_name_label = QLabel("Portfolio")
        self.portfolio_name_label.setObjectName("stat_row_name")
        self.portfolio_name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.portfolio_name_label, 1, 0)

        self.portfolio_labels = {}
        stat_keys = ["median", "mean", "cagr", "cum_ret", "ann_vol", "max_dd", "prob_positive", "prob_loss_10", "var_95", "cvar_95", "prob_beat"]
        for col, key in enumerate(stat_keys, start=1):
            label = QLabel("--")
            label.setObjectName("stat_value")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, 1, col)
            self.portfolio_labels[key] = label

        # Row 2: Benchmark (hidden by default)
        self.benchmark_name_label = QLabel("Benchmark")
        self.benchmark_name_label.setObjectName("stat_row_name")
        self.benchmark_name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.benchmark_name_label, 2, 0)

        self.benchmark_labels = {}
        for col, key in enumerate(stat_keys, start=1):
            label = QLabel("--")
            label.setObjectName("stat_value")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, 2, col)
            self.benchmark_labels[key] = label

        # Store benchmark widgets for visibility toggling
        self._benchmark_widgets = [self.benchmark_name_label] + list(self.benchmark_labels.values())

        # P(Beat) column - header and both row values (hidden when no benchmark)
        self._pbeat_header = self._header_labels[-1]  # Last header is P(Beat)
        self._pbeat_widgets = [
            self._pbeat_header,
            self.portfolio_labels["prob_beat"],
            self.benchmark_labels["prob_beat"],
        ]

        # Hide benchmark row and P(Beat) column by default
        self.set_benchmark_visible(False)

    def set_portfolio_name(self, name: str):
        """Set the portfolio row name."""
        self.portfolio_name_label.setText(name if name else "Portfolio")

    def set_benchmark_visible(self, visible: bool, name: str = ""):
        """Show or hide the benchmark statistics row and P(Beat) column."""
        if name:
            self.benchmark_name_label.setText(name)
        else:
            self.benchmark_name_label.setText("Benchmark")

        # Show/hide benchmark row
        for widget in self._benchmark_widgets:
            widget.setVisible(visible)

        # Show/hide P(Beat) column (only relevant when benchmark is visible)
        for widget in self._pbeat_widgets:
            widget.setVisible(visible)

    def update_statistics(
        self,
        result: SimulationResult,
        var_cvar: Dict[str, Dict[str, float]],
        probabilities: Dict[str, float],
        ann_vol: float = 0.0,
        max_dd: Dict[str, float] = None,
        prob_beat: Optional[float] = None,
    ):
        """Update portfolio statistics from simulation result."""
        self._update_row(self.portfolio_labels, result, var_cvar, probabilities, ann_vol, max_dd, prob_beat)

    def update_benchmark_statistics(
        self,
        result: SimulationResult,
        var_cvar: Dict[str, Dict[str, float]],
        probabilities: Dict[str, float],
        ann_vol: float = 0.0,
        max_dd: Dict[str, float] = None,
        prob_beat: Optional[float] = None,
    ):
        """Update benchmark statistics from simulation result."""
        self._update_row(self.benchmark_labels, result, var_cvar, probabilities, ann_vol, max_dd, prob_beat)

    def _update_row(
        self,
        labels: Dict[str, QLabel],
        result: SimulationResult,
        var_cvar: Dict[str, Dict[str, float]],
        probabilities: Dict[str, float],
        ann_vol: float = 0.0,
        max_dd: Dict[str, float] = None,
        prob_beat: Optional[float] = None,
    ):
        """Update a row of statistics."""
        # Terminal values as percentage change from initial
        median_pct = (result.median_terminal / result.initial_value - 1) * 100
        mean_pct = (result.mean_terminal / result.initial_value - 1) * 100
        labels["median"].setText(f"{median_pct:+.1f}%")
        labels["mean"].setText(f"{mean_pct:+.1f}%")

        # CAGR
        cagr = result.terminal_cagr
        if not np.isnan(cagr):
            labels["cagr"].setText(f"{cagr * 100:+.1f}%")
        else:
            labels["cagr"].setText("--")

        # Cumulative Return (median terminal return)
        cum_ret = (result.median_terminal / result.initial_value - 1) * 100
        labels["cum_ret"].setText(f"{cum_ret:+.1f}%")

        # Annualized Volatility
        labels["ann_vol"].setText(f"{ann_vol * 100:.1f}%")

        # Max Drawdown (median)
        if max_dd:
            mdd = max_dd.get("median_mdd", 0)
            labels["max_dd"].setText(f"{mdd:.1f}%")
        else:
            labels["max_dd"].setText("--")

        # Probabilities
        prob_pos = probabilities.get("prob_positive", 0)
        labels["prob_positive"].setText(f"{prob_pos * 100:.1f}%")

        prob_loss = probabilities.get("prob_loss_10pct", 0)
        labels["prob_loss_10"].setText(f"{prob_loss * 100:.1f}%")

        # VaR and CVaR
        if "0.95" in var_cvar:
            var_95 = var_cvar["0.95"]["var_pct"]
            cvar_95 = var_cvar["0.95"]["cvar_pct"]
            labels["var_95"].setText(f"{var_95:+.1f}%")
            labels["cvar_95"].setText(f"{cvar_95:+.1f}%")
        else:
            labels["var_95"].setText("--")
            labels["cvar_95"].setText("--")

        # P(Beat) - probability of beating the other
        if prob_beat is not None:
            labels["prob_beat"].setText(f"{prob_beat * 100:.1f}%")
        else:
            labels["prob_beat"].setText("--")

    def clear(self):
        """Clear all statistics."""
        for label in self.portfolio_labels.values():
            label.setText("--")
        for label in self.benchmark_labels.values():
            label.setText("--")
        self.set_benchmark_visible(False)

    def apply_theme(self, theme: str):
        """Apply theme styling."""
        if theme == "dark":
            bg = "#252525"
            text = "#ffffff"
            header = "#888888"
            border = "#444444"
        elif theme == "light":
            bg = "#f8f8f8"
            text = "#000000"
            header = "#666666"
            border = "#cccccc"
        else:  # bloomberg
            bg = "#0a1018"
            text = "#e8e8e8"
            header = "#888888"
            border = "#3a4654"

        self.setStyleSheet(f"""
            StatisticsPanel {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QLabel#stat_header {{
                color: {header};
                font-size: 11px;
                background: transparent;
            }}
            QLabel#stat_row_name {{
                color: {text};
                font-size: 12px;
                font-weight: bold;
                background: transparent;
            }}
            QLabel#stat_value {{
                color: {text};
                font-size: 13px;
                background: transparent;
            }}
        """)


class MonteCarloChart(LazyThemeMixin, QWidget):
    """
    Monte Carlo simulation visualization chart.

    Displays probability cones showing percentile bands of simulated
    portfolio paths over time.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self._current_result: Optional[SimulationResult] = None

        self._setup_ui()
        self._apply_theme()

        # Lazy theme - only apply when visible
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup chart UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Statistics panel at top
        self.stats_panel = StatisticsPanel(self.theme_manager)
        layout.addWidget(self.stats_panel)

        # Chart widget
        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget, stretch=1)

        # Create plot item
        self.plot_item = self.plot_widget.addPlot()
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel("left", "Return (%)")
        self.plot_item.setLabel("bottom", "Trading Days")

        # Add legend in top-left
        self.legend = self.plot_item.addLegend(offset=(60, 5))
        self.legend.setParentItem(self.plot_item.graphicsItem())

        # Store plot items for clearing
        self._plot_items: List = []

        # Placeholder
        self.placeholder = QLabel("Select a portfolio and run simulation")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size: 16px; color: #888888;")
        layout.addWidget(self.placeholder)
        self.placeholder.setVisible(True)
        self.plot_widget.setVisible(False)

    def set_simulation_result(
        self,
        result: SimulationResult,
        settings: Dict[str, Any],
        benchmark_result: Optional[SimulationResult] = None,
        portfolio_name: str = "",
        benchmark_name: str = "",
    ):
        """Display simulation result on chart, optionally with benchmark comparison."""
        self._current_result = result
        self._clear_plot()

        # Show chart, hide placeholder
        self.placeholder.setVisible(False)
        self.plot_widget.setVisible(True)

        # Get x values (trading days)
        n_points = result.n_periods + 1
        x = np.arange(n_points)

        theme = self.theme_manager.current_theme

        # Portfolio colors (blue tones)
        portfolio_band_90_color = settings.get("band_90_color", (100, 100, 255))
        portfolio_band_50_color = settings.get("band_50_color", (50, 50, 200))
        portfolio_median_color = settings.get("median_color", (255, 255, 255))

        # Benchmark colors (orange/red tones for contrast)
        benchmark_band_90_color = (255, 140, 100)
        benchmark_band_50_color = (200, 100, 50)
        benchmark_median_color = (255, 165, 0)  # Orange

        # Helper to convert values to percentage return
        def to_pct(values, initial):
            return (values / initial - 1) * 100

        # Draw benchmark first (so portfolio draws on top)
        if benchmark_result is not None:
            bench_initial = benchmark_result.initial_value

            # Draw benchmark 90% confidence band
            if settings.get("show_band_90", True):
                p5 = to_pct(benchmark_result.get_percentile(5), bench_initial)
                p95 = to_pct(benchmark_result.get_percentile(95), bench_initial)
                fill = pg.FillBetweenItem(
                    pg.PlotDataItem(x, p5),
                    pg.PlotDataItem(x, p95),
                    brush=(*benchmark_band_90_color, 40),
                )
                self.plot_item.addItem(fill)
                self._plot_items.append(fill)

            # Draw benchmark 50% confidence band
            if settings.get("show_band_50", True):
                p25 = to_pct(benchmark_result.get_percentile(25), bench_initial)
                p75 = to_pct(benchmark_result.get_percentile(75), bench_initial)
                fill = pg.FillBetweenItem(
                    pg.PlotDataItem(x, p25),
                    pg.PlotDataItem(x, p75),
                    brush=(*benchmark_band_50_color, 60),
                )
                self.plot_item.addItem(fill)
                self._plot_items.append(fill)

            # Draw benchmark median line (add to legend with benchmark name)
            if settings.get("show_median", True):
                median = to_pct(benchmark_result.median_path, bench_initial)
                pen = pg.mkPen(color=benchmark_median_color, width=2, style=Qt.SolidLine)
                bench_label = benchmark_name if benchmark_name else "Benchmark"
                line = self.plot_item.plot(x, median, pen=pen, name=bench_label)
                self._plot_items.append(line)

            # Draw benchmark mean line (no legend entry)
            if settings.get("show_mean", False):
                mean = to_pct(benchmark_result.mean_path, bench_initial)
                pen = pg.mkPen(color=(255, 180, 100), width=2, style=Qt.DashLine)
                line = self.plot_item.plot(x, mean, pen=pen)
                self._plot_items.append(line)

        # Portfolio initial value for percentage conversion
        port_initial = result.initial_value

        # Draw portfolio 90% confidence band (5th - 95th percentile)
        if settings.get("show_band_90", True):
            p5 = to_pct(result.get_percentile(5), port_initial)
            p95 = to_pct(result.get_percentile(95), port_initial)
            fill = pg.FillBetweenItem(
                pg.PlotDataItem(x, p5),
                pg.PlotDataItem(x, p95),
                brush=(*portfolio_band_90_color, 50),
            )
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

        # Draw portfolio 50% confidence band (25th - 75th percentile)
        if settings.get("show_band_50", True):
            p25 = to_pct(result.get_percentile(25), port_initial)
            p75 = to_pct(result.get_percentile(75), port_initial)
            fill = pg.FillBetweenItem(
                pg.PlotDataItem(x, p25),
                pg.PlotDataItem(x, p75),
                brush=(*portfolio_band_50_color, 80),
            )
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

        # Draw portfolio median line (add to legend with portfolio name)
        if settings.get("show_median", True):
            median = to_pct(result.median_path, port_initial)
            pen = pg.mkPen(color=portfolio_median_color, width=2, style=Qt.SolidLine)
            port_label = portfolio_name if portfolio_name else "Portfolio"
            line = self.plot_item.plot(x, median, pen=pen, name=port_label)
            self._plot_items.append(line)

        # Draw portfolio mean line (no legend entry)
        if settings.get("show_mean", False):
            mean = to_pct(result.mean_path, port_initial)
            color = settings.get("mean_color", (255, 200, 0))
            pen = pg.mkPen(color=color, width=2, style=Qt.DashLine)
            line = self.plot_item.plot(x, mean, pen=pen)
            self._plot_items.append(line)

        # Draw 0% baseline
        pen = pg.mkPen(color=(100, 100, 100), width=1, style=Qt.DotLine)
        line = self.plot_item.plot(x, np.zeros(n_points), pen=pen)
        self._plot_items.append(line)

        # Auto-range
        self.plot_item.autoRange()

        # Calculate and update statistics
        from ..services.monte_carlo_service import MonteCarloService

        # Portfolio statistics
        self.stats_panel.set_portfolio_name(portfolio_name)
        var_cvar = MonteCarloService.calculate_var_cvar(
            result.terminal_values, result.initial_value
        )
        probabilities = MonteCarloService.calculate_probability_metrics(
            result.terminal_values, result.initial_value
        )
        ann_vol = MonteCarloService.calculate_annualized_volatility(result.paths)
        max_dd = MonteCarloService.calculate_max_drawdown(result.paths)

        # Benchmark statistics and outperformance probabilities
        if benchmark_result is not None:
            bench_var_cvar = MonteCarloService.calculate_var_cvar(
                benchmark_result.terminal_values, benchmark_result.initial_value
            )
            bench_probabilities = MonteCarloService.calculate_probability_metrics(
                benchmark_result.terminal_values, benchmark_result.initial_value
            )
            bench_ann_vol = MonteCarloService.calculate_annualized_volatility(benchmark_result.paths)
            bench_max_dd = MonteCarloService.calculate_max_drawdown(benchmark_result.paths)

            # Calculate outperformance probabilities
            outperformance = MonteCarloService.calculate_outperformance_probability(
                result.terminal_values, benchmark_result.terminal_values
            )
            port_beats_bench = outperformance["portfolio_beats_benchmark"]
            bench_beats_port = outperformance["benchmark_beats_portfolio"]

            # Update portfolio stats with P(Beat) = P(Portfolio beats Benchmark)
            self.stats_panel.update_statistics(
                result, var_cvar, probabilities, ann_vol, max_dd, port_beats_bench
            )

            # Update benchmark stats with P(Beat) = P(Benchmark beats Portfolio)
            self.stats_panel.set_benchmark_visible(True, benchmark_name)
            self.stats_panel.update_benchmark_statistics(
                benchmark_result, bench_var_cvar, bench_probabilities,
                bench_ann_vol, bench_max_dd, bench_beats_port
            )
        else:
            # No benchmark - update portfolio without P(Beat)
            self.stats_panel.update_statistics(result, var_cvar, probabilities, ann_vol, max_dd)
            self.stats_panel.set_benchmark_visible(False)

    def _clear_plot(self):
        """Clear all plot items and legend."""
        for item in self._plot_items:
            self.plot_item.removeItem(item)
        self._plot_items.clear()

        # Clear legend
        self.legend.clear()

    def show_placeholder(self, message: str):
        """Show placeholder message."""
        self._clear_plot()
        self._current_result = None
        self.placeholder.setText(message)
        self.placeholder.setVisible(True)
        self.plot_widget.setVisible(False)
        self.stats_panel.clear()

    def clear(self):
        """Clear the chart."""
        self.show_placeholder("Select a portfolio and run simulation")

    def _apply_theme(self):
        """Apply theme styling."""
        theme = self.theme_manager.current_theme

        # Background colors
        if theme == "dark":
            bg_rgb = (30, 30, 30)
            text_color = "#ffffff"
            grid_color = (80, 80, 80)
        elif theme == "light":
            bg_rgb = (255, 255, 255)
            text_color = "#000000"
            grid_color = (200, 200, 200)
        else:  # bloomberg
            bg_rgb = (13, 20, 32)
            text_color = "#e8e8e8"
            grid_color = (50, 60, 80)

        # Apply to plot widget
        self.plot_widget.setBackground(bg_rgb)

        # Apply to axes
        axis_pen = pg.mkPen(color=grid_color, width=1)
        self.plot_item.getAxis("bottom").setPen(axis_pen)
        self.plot_item.getAxis("left").setPen(axis_pen)
        self.plot_item.getAxis("bottom").setTextPen(text_color)
        self.plot_item.getAxis("left").setTextPen(text_color)

        # Apply gridlines
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        # Apply to legend (transparent background, no border)
        self.legend.setLabelTextColor(text_color)
        self.legend.setBrush(pg.mkBrush(None))  # Transparent background
        self.legend.setPen(pg.mkPen(None))  # No border

        # Apply to statistics panel
        self.stats_panel.apply_theme(theme)

        # Apply to placeholder
        self.placeholder.setStyleSheet(f"font-size: 16px; color: #888888; background: transparent;")

        # Container background
        self.setStyleSheet(f"background-color: rgb{bg_rgb};")
