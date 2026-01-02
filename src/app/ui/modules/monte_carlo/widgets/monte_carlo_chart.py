"""Monte Carlo Chart Widget - Probability cone visualization with statistics panel."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from app.ui.widgets.charting.axes import (
    DraggablePercentageAxisItem,
    DraggableTradingDayAxisItem,
)
from ..services.monte_carlo_service import SimulationResult
from ..services.simulation_worker import SimulationResultBundle


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
    portfolio paths over time, with interactive features like crosshair,
    draggable axes, and median/mouse position labels.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self._current_result: Optional[SimulationResult] = None
        self._current_benchmark_result: Optional[SimulationResult] = None

        # Chart settings (will be updated from settings manager)
        self._chart_settings: Dict[str, Any] = {
            "show_crosshair": True,
            "show_median_label": True,
            "show_gridlines": True,
            "chart_background": None,
            "portfolio_median_color": (255, 255, 255),
            "portfolio_median_line_style": Qt.SolidLine,
            "portfolio_median_line_width": 2,
            "show_portfolio_median": True,
            "benchmark_median_color": (255, 165, 0),
            "benchmark_median_line_style": Qt.SolidLine,
            "benchmark_median_line_width": 2,
            "show_benchmark_median": True,
        }

        # Crosshair lines
        self._crosshair_v: Optional[pg.InfiniteLine] = None
        self._crosshair_h: Optional[pg.InfiniteLine] = None

        # Median labels (QLabel overlays)
        self._portfolio_median_label: Optional[QLabel] = None
        self._benchmark_median_label: Optional[QLabel] = None

        # Timer for throttling label updates during pan/drag (max 20fps)
        self._label_update_timer = QTimer()
        self._label_update_timer.setSingleShot(True)
        self._label_update_timer.timeout.connect(self._update_median_labels)

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

        # Create custom draggable axes
        self._bottom_axis = DraggableTradingDayAxisItem(orientation='bottom')
        self._right_axis = DraggablePercentageAxisItem(orientation='right')
        self._bottom_axis.set_start_date(datetime.now())

        # Create plot item with custom axes
        self.plot_item = self.plot_widget.addPlot(
            axisItems={
                'bottom': self._bottom_axis,
                'right': self._right_axis,
            }
        )
        self.plot_item.showAxis("right")
        self.plot_item.hideAxis("left")
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel("bottom", "Trading Days")

        # Set fixed width for right axis
        self._right_axis.setWidth(70)

        # Get ViewBox reference
        self._view_box = self.plot_item.getViewBox()
        self._view_box.setMouseEnabled(x=True, y=True)

        # Connect view range changed signal for label updates
        self._view_box.sigRangeChanged.connect(self._on_view_range_changed)

        # Add legend in top-left
        self.legend = self.plot_item.addLegend(offset=(60, 5))
        self.legend.setParentItem(self.plot_item.graphicsItem())

        # Store plot items for clearing
        self._plot_items: List = []

        # Enable mouse tracking for crosshair
        self.setMouseTracking(True)
        self.plot_widget.setMouseTracking(True)

        # Connect to scene mouse moved signal for crosshair
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Placeholder
        self.placeholder = QLabel("Select a portfolio and run simulation")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size: 16px; color: #888888;")
        layout.addWidget(self.placeholder)
        self.placeholder.setVisible(True)
        self.plot_widget.setVisible(False)

        # Create overlay labels (hidden initially)
        self._create_overlay_labels()

    def _create_optimized_fill(
        self, x, y_lower, y_upper, brush_color, alpha: int
    ) -> pg.FillBetweenItem:
        """Create an optimized FillBetweenItem with viewport clipping.

        Args:
            x: X-axis data points
            y_lower: Lower bound y-values
            y_upper: Upper bound y-values
            brush_color: RGB tuple for fill color
            alpha: Alpha value (0-255)

        Returns:
            FillBetweenItem with clipping enabled on internal curves
        """
        # Create PlotDataItems with viewport clipping enabled
        lower_curve = pg.PlotDataItem(x, y_lower)
        upper_curve = pg.PlotDataItem(x, y_upper)
        lower_curve.setClipToView(True)
        upper_curve.setClipToView(True)

        fill = pg.FillBetweenItem(lower_curve, upper_curve, brush=(*brush_color, alpha))
        return fill

    def _create_optimized_line(
        self, x, y, pen, name: str = None
    ) -> pg.PlotDataItem:
        """Create an optimized line plot with viewport clipping and downsampling.

        Args:
            x: X-axis data points
            y: Y-axis data points
            pen: PyQtGraph pen for line styling
            name: Optional legend name

        Returns:
            PlotDataItem with optimizations enabled
        """
        if name:
            line = self.plot_item.plot(x, y, pen=pen, name=name)
        else:
            line = self.plot_item.plot(x, y, pen=pen)

        # Enable viewport clipping (skip rendering outside visible area)
        line.setClipToView(True)

        # Enable automatic downsampling for smoother pan/zoom
        # 'peak' method preserves peaks and valleys for accurate visual representation
        line.setDownsampling(auto=True, method='peak')

        return line

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
        self._current_benchmark_result = benchmark_result
        self._clear_plot()

        # Update chart settings from passed settings
        self._chart_settings.update(settings)

        # Show chart, hide placeholder
        self.placeholder.setVisible(False)
        self.plot_widget.setVisible(True)

        # Get x values (trading days)
        n_points = result.n_periods + 1
        x = np.arange(n_points)

        # Update axis with trading day count
        self._bottom_axis.set_n_periods(result.n_periods)

        theme = self.theme_manager.current_theme

        # Portfolio median color and line settings (from chart settings or defaults)
        portfolio_median_color = settings.get("portfolio_median_color", (255, 255, 255))
        portfolio_median_style = settings.get("portfolio_median_line_style", Qt.SolidLine)
        portfolio_median_width = settings.get("portfolio_median_line_width", 2)

        # Auto-derive band colors from median color (same hue, different opacity)
        portfolio_band_90_color = portfolio_median_color[:3]  # RGB only
        portfolio_band_50_color = portfolio_median_color[:3]

        # Benchmark median color and line settings
        benchmark_median_color = settings.get("benchmark_median_color", (255, 165, 0))
        benchmark_median_style = settings.get("benchmark_median_line_style", Qt.SolidLine)
        benchmark_median_width = settings.get("benchmark_median_line_width", 2)

        # Auto-derive benchmark band colors from median color
        benchmark_band_90_color = benchmark_median_color[:3]
        benchmark_band_50_color = benchmark_median_color[:3]

        # Helper to convert values to percentage return
        def to_pct(values, initial):
            return (values / initial - 1) * 100

        # Draw benchmark first (so portfolio draws on top)
        if benchmark_result is not None:
            bench_initial = benchmark_result.initial_value

            # Draw benchmark 90% confidence band (optimized with clipping)
            if settings.get("show_band_90", True):
                p5 = to_pct(benchmark_result.get_percentile(5), bench_initial)
                p95 = to_pct(benchmark_result.get_percentile(95), bench_initial)
                fill = self._create_optimized_fill(x, p5, p95, benchmark_band_90_color, 40)
                self.plot_item.addItem(fill)
                self._plot_items.append(fill)

            # Draw benchmark 50% confidence band (optimized with clipping)
            if settings.get("show_band_50", True):
                p25 = to_pct(benchmark_result.get_percentile(25), bench_initial)
                p75 = to_pct(benchmark_result.get_percentile(75), bench_initial)
                fill = self._create_optimized_fill(x, p25, p75, benchmark_band_50_color, 60)
                self.plot_item.addItem(fill)
                self._plot_items.append(fill)

            # Draw benchmark median line (optimized with clipping + downsampling)
            if settings.get("show_benchmark_median", True):
                median = to_pct(benchmark_result.median_path, bench_initial)
                pen = pg.mkPen(
                    color=benchmark_median_color,
                    width=benchmark_median_width,
                    style=benchmark_median_style
                )
                bench_label = benchmark_name if benchmark_name else "Benchmark"
                line = self._create_optimized_line(x, median, pen, name=bench_label)
                self._plot_items.append(line)

            # Draw benchmark mean line (optimized, no legend entry)
            if settings.get("show_mean", False):
                mean = to_pct(benchmark_result.mean_path, bench_initial)
                pen = pg.mkPen(color=(255, 180, 100), width=2, style=Qt.DashLine)
                line = self._create_optimized_line(x, mean, pen)
                self._plot_items.append(line)

        # Portfolio initial value for percentage conversion
        port_initial = result.initial_value

        # Draw portfolio 90% confidence band (optimized with clipping)
        if settings.get("show_band_90", True):
            p5 = to_pct(result.get_percentile(5), port_initial)
            p95 = to_pct(result.get_percentile(95), port_initial)
            fill = self._create_optimized_fill(x, p5, p95, portfolio_band_90_color, 50)
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

        # Draw portfolio 50% confidence band (optimized with clipping)
        if settings.get("show_band_50", True):
            p25 = to_pct(result.get_percentile(25), port_initial)
            p75 = to_pct(result.get_percentile(75), port_initial)
            fill = self._create_optimized_fill(x, p25, p75, portfolio_band_50_color, 80)
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

        # Draw portfolio median line (optimized with clipping + downsampling)
        if settings.get("show_portfolio_median", True):
            median = to_pct(result.median_path, port_initial)
            pen = pg.mkPen(
                color=portfolio_median_color,
                width=portfolio_median_width,
                style=portfolio_median_style
            )
            port_label = portfolio_name if portfolio_name else "Portfolio"
            line = self._create_optimized_line(x, median, pen, name=port_label)
            self._plot_items.append(line)

        # Draw portfolio mean line (optimized, no legend entry)
        if settings.get("show_mean", False):
            mean = to_pct(result.mean_path, port_initial)
            color = settings.get("mean_color", (255, 200, 0))
            pen = pg.mkPen(color=color, width=2, style=Qt.DashLine)
            line = self._create_optimized_line(x, mean, pen)
            self._plot_items.append(line)

        # Draw 0% baseline (optimized)
        pen = pg.mkPen(color=(100, 100, 100), width=1, style=Qt.DotLine)
        line = self._create_optimized_line(x, np.zeros(n_points), pen)
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

        # Update label styles with new colors from settings
        self._update_label_styles()

        # Update median labels after rendering (immediate + delayed for layout)
        self._update_median_labels()
        QTimer.singleShot(50, self._update_median_labels)

        # Apply gridlines setting
        show_grid = settings.get("show_gridlines", True)
        self.plot_item.showGrid(x=show_grid, y=show_grid, alpha=0.3)

    def set_simulation_result_with_stats(
        self,
        bundle: SimulationResultBundle,
        settings: Dict[str, Any],
        portfolio_name: str = "",
        benchmark_name: str = "",
    ):
        """Display simulation result with pre-computed statistics.

        This method accepts a SimulationResultBundle that includes all statistics
        computed in the background thread, avoiding redundant computation on the
        UI thread.

        Args:
            bundle: Complete simulation results with pre-computed statistics
            settings: Chart settings dictionary
            portfolio_name: Display name for portfolio
            benchmark_name: Display name for benchmark
        """
        result = bundle.portfolio_result
        benchmark_result = bundle.benchmark_result

        self._current_result = result
        self._current_benchmark_result = benchmark_result
        self._clear_plot()

        # Update chart settings from passed settings
        self._chart_settings.update(settings)

        # Show chart, hide placeholder
        self.placeholder.setVisible(False)
        self.plot_widget.setVisible(True)

        # Get x values (trading days)
        n_points = result.n_periods + 1
        x = np.arange(n_points)

        # Update axis with trading day count
        self._bottom_axis.set_n_periods(result.n_periods)

        theme = self.theme_manager.current_theme

        # Portfolio median color and line settings (from chart settings or defaults)
        portfolio_median_color = settings.get("portfolio_median_color", (255, 255, 255))
        portfolio_median_style = settings.get("portfolio_median_line_style", Qt.SolidLine)
        portfolio_median_width = settings.get("portfolio_median_line_width", 2)

        # Auto-derive band colors from median color (same hue, different opacity)
        portfolio_band_90_color = portfolio_median_color[:3]  # RGB only
        portfolio_band_50_color = portfolio_median_color[:3]

        # Benchmark median color and line settings
        benchmark_median_color = settings.get("benchmark_median_color", (255, 165, 0))
        benchmark_median_style = settings.get("benchmark_median_line_style", Qt.SolidLine)
        benchmark_median_width = settings.get("benchmark_median_line_width", 2)

        # Auto-derive benchmark band colors from median color
        benchmark_band_90_color = benchmark_median_color[:3]
        benchmark_band_50_color = benchmark_median_color[:3]

        # Helper to convert values to percentage return
        def to_pct(values, initial):
            return (values / initial - 1) * 100

        # Draw benchmark first (so portfolio draws on top)
        if benchmark_result is not None:
            bench_initial = benchmark_result.initial_value

            # Draw benchmark 90% confidence band (optimized with clipping)
            if settings.get("show_band_90", True):
                p5 = to_pct(benchmark_result.get_percentile(5), bench_initial)
                p95 = to_pct(benchmark_result.get_percentile(95), bench_initial)
                fill = self._create_optimized_fill(x, p5, p95, benchmark_band_90_color, 40)
                self.plot_item.addItem(fill)
                self._plot_items.append(fill)

            # Draw benchmark 50% confidence band (optimized with clipping)
            if settings.get("show_band_50", True):
                p25 = to_pct(benchmark_result.get_percentile(25), bench_initial)
                p75 = to_pct(benchmark_result.get_percentile(75), bench_initial)
                fill = self._create_optimized_fill(x, p25, p75, benchmark_band_50_color, 60)
                self.plot_item.addItem(fill)
                self._plot_items.append(fill)

            # Draw benchmark median line (optimized with clipping + downsampling)
            if settings.get("show_benchmark_median", True):
                median = to_pct(benchmark_result.median_path, bench_initial)
                pen = pg.mkPen(
                    color=benchmark_median_color,
                    width=benchmark_median_width,
                    style=benchmark_median_style
                )
                bench_label = benchmark_name if benchmark_name else "Benchmark"
                line = self._create_optimized_line(x, median, pen, name=bench_label)
                self._plot_items.append(line)

            # Draw benchmark mean line (optimized, no legend entry)
            if settings.get("show_mean", False):
                mean = to_pct(benchmark_result.mean_path, bench_initial)
                pen = pg.mkPen(color=(255, 180, 100), width=2, style=Qt.DashLine)
                line = self._create_optimized_line(x, mean, pen)
                self._plot_items.append(line)

        # Portfolio initial value for percentage conversion
        port_initial = result.initial_value

        # Draw portfolio 90% confidence band (optimized with clipping)
        if settings.get("show_band_90", True):
            p5 = to_pct(result.get_percentile(5), port_initial)
            p95 = to_pct(result.get_percentile(95), port_initial)
            fill = self._create_optimized_fill(x, p5, p95, portfolio_band_90_color, 50)
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

        # Draw portfolio 50% confidence band (optimized with clipping)
        if settings.get("show_band_50", True):
            p25 = to_pct(result.get_percentile(25), port_initial)
            p75 = to_pct(result.get_percentile(75), port_initial)
            fill = self._create_optimized_fill(x, p25, p75, portfolio_band_50_color, 80)
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

        # Draw portfolio median line (optimized with clipping + downsampling)
        if settings.get("show_portfolio_median", True):
            median = to_pct(result.median_path, port_initial)
            pen = pg.mkPen(
                color=portfolio_median_color,
                width=portfolio_median_width,
                style=portfolio_median_style
            )
            port_label = portfolio_name if portfolio_name else "Portfolio"
            line = self._create_optimized_line(x, median, pen, name=port_label)
            self._plot_items.append(line)

        # Draw portfolio mean line (optimized, no legend entry)
        if settings.get("show_mean", False):
            mean = to_pct(result.mean_path, port_initial)
            color = settings.get("mean_color", (255, 200, 0))
            pen = pg.mkPen(color=color, width=2, style=Qt.DashLine)
            line = self._create_optimized_line(x, mean, pen)
            self._plot_items.append(line)

        # Draw 0% baseline (optimized)
        pen = pg.mkPen(color=(100, 100, 100), width=1, style=Qt.DotLine)
        line = self._create_optimized_line(x, np.zeros(n_points), pen)
        self._plot_items.append(line)

        # Auto-range
        self.plot_item.autoRange()

        # Use pre-computed statistics from bundle (no recalculation needed)
        self.stats_panel.set_portfolio_name(portfolio_name)

        # Get pre-computed portfolio statistics
        portfolio_stats = bundle.portfolio_stats

        if benchmark_result is not None and bundle.benchmark_stats is not None:
            benchmark_stats = bundle.benchmark_stats
            outperformance = bundle.outperformance

            port_beats_bench = outperformance["portfolio_beats_benchmark"]
            bench_beats_port = outperformance["benchmark_beats_portfolio"]

            # Update portfolio stats with P(Beat) = P(Portfolio beats Benchmark)
            self.stats_panel.update_statistics(
                result,
                portfolio_stats.var_cvar,
                portfolio_stats.probabilities,
                portfolio_stats.ann_vol,
                portfolio_stats.max_dd,
                port_beats_bench
            )

            # Update benchmark stats with P(Beat) = P(Benchmark beats Portfolio)
            self.stats_panel.set_benchmark_visible(True, benchmark_name)
            self.stats_panel.update_benchmark_statistics(
                benchmark_result,
                benchmark_stats.var_cvar,
                benchmark_stats.probabilities,
                benchmark_stats.ann_vol,
                benchmark_stats.max_dd,
                bench_beats_port
            )
        else:
            # No benchmark - update portfolio without P(Beat)
            self.stats_panel.update_statistics(
                result,
                portfolio_stats.var_cvar,
                portfolio_stats.probabilities,
                portfolio_stats.ann_vol,
                portfolio_stats.max_dd
            )
            self.stats_panel.set_benchmark_visible(False)

        # Update label styles with new colors from settings
        self._update_label_styles()

        # Update median labels after rendering (immediate + delayed for layout)
        self._update_median_labels()
        QTimer.singleShot(50, self._update_median_labels)

        # Apply gridlines setting
        show_grid = settings.get("show_gridlines", True)
        self.plot_item.showGrid(x=show_grid, y=show_grid, alpha=0.3)

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

        # Update right axis styling (we use right axis, not left)
        self.plot_item.getAxis("right").setPen(axis_pen)
        self.plot_item.getAxis("right").setTextPen(text_color)

        # Update crosshair color if it exists
        self._update_crosshair_color()

        # Update label styles
        self._update_label_styles()

    # ========== Interactive Features ==========

    def _create_overlay_labels(self):
        """Create QLabel overlays for median labels."""
        # Portfolio median label
        self._portfolio_median_label = QLabel(self)
        self._portfolio_median_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._portfolio_median_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._portfolio_median_label.hide()

        # Benchmark median label
        self._benchmark_median_label = QLabel(self)
        self._benchmark_median_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._benchmark_median_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._benchmark_median_label.hide()

        self._update_label_styles()

    def _update_label_styles(self):
        """Update label styles based on median line colors from settings."""
        # Get median line colors from chart settings
        portfolio_color = self._chart_settings.get("portfolio_median_color", (255, 255, 255))
        benchmark_color = self._chart_settings.get("benchmark_median_color", (255, 165, 0))

        # Determine text color based on background brightness
        def get_text_color(bg_color):
            # Calculate luminance to determine if text should be black or white
            r, g, b = bg_color[:3]
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return "#000000" if luminance > 0.5 else "#ffffff"

        # Portfolio median label style
        if self._portfolio_median_label:
            port_hex = f"#{portfolio_color[0]:02x}{portfolio_color[1]:02x}{portfolio_color[2]:02x}"
            port_text = get_text_color(portfolio_color)
            portfolio_style = f"""
                background-color: {port_hex};
                color: {port_text};
                font-weight: bold;
                padding: 2px 0px 2px 0px;
                border-radius: 2px;
            """
            self._portfolio_median_label.setStyleSheet(portfolio_style)

        # Benchmark median label style
        if self._benchmark_median_label:
            bench_hex = f"#{benchmark_color[0]:02x}{benchmark_color[1]:02x}{benchmark_color[2]:02x}"
            bench_text = get_text_color(benchmark_color)
            benchmark_style = f"""
                background-color: {bench_hex};
                color: {bench_text};
                font-weight: bold;
                padding: 2px 0px 2px 0px;
                border-radius: 2px;
            """
            self._benchmark_median_label.setStyleSheet(benchmark_style)

        # Match axis font to median labels for consistent sizing
        if hasattr(self, '_right_axis') and self._right_axis:
            axis_font = self._right_axis.font()
            if self._portfolio_median_label:
                self._portfolio_median_label.setFont(axis_font)
            if self._benchmark_median_label:
                self._benchmark_median_label.setFont(axis_font)

    def _create_crosshair(self):
        """Create crosshair lines if not already created."""
        if self._crosshair_v is not None:
            return

        crosshair_color = self._get_crosshair_color()
        pen = pg.mkPen(color=crosshair_color, width=1, style=Qt.DashLine)

        self._crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pen)

        self._view_box.addItem(self._crosshair_v)
        self._view_box.addItem(self._crosshair_h)

        self._crosshair_v.hide()
        self._crosshair_h.hide()

    def _get_crosshair_color(self) -> Tuple[int, int, int]:
        """Get crosshair color based on theme."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return (100, 100, 100)
        elif theme == "bloomberg":
            return (100, 120, 140)
        else:
            return (150, 150, 150)

    def _update_crosshair_color(self):
        """Update crosshair pen color based on theme."""
        if self._crosshair_v is None:
            return

        color = self._get_crosshair_color()
        pen = pg.mkPen(color=color, width=1, style=Qt.DashLine)
        self._crosshair_v.setPen(pen)
        self._crosshair_h.setPen(pen)

    def _on_view_range_changed(self):
        """Handle view range change - update median labels (throttled)."""
        # Throttle label updates to max 20fps (50ms) during pan/drag
        # This prevents expensive label repositioning on every frame
        if not self._label_update_timer.isActive():
            self._label_update_timer.start(50)

    def resizeEvent(self, event):
        """Handle resize - update label positions."""
        super().resizeEvent(event)
        self._update_median_labels()

    def _on_mouse_moved(self, scene_pos):
        """Handle mouse move from scene signal - update crosshair and mouse labels."""
        if not self.plot_widget.isVisible():
            return

        # Check if mouse is within the ViewBox area
        vb_scene_rect = self._view_box.sceneBoundingRect()
        if not vb_scene_rect.contains(scene_pos):
            # Mouse is outside the plot area - hide crosshair
            self._hide_crosshair()
            return

        # Convert scene position to view coordinates
        view_pos = self._view_box.mapSceneToView(scene_pos)

        # Update crosshair
        if self._chart_settings.get("show_crosshair", True):
            self._create_crosshair()  # Ensure crosshair exists
            if self._crosshair_v and self._crosshair_h:
                self._crosshair_v.setPos(view_pos.x())
                self._crosshair_h.setPos(view_pos.y())
                self._crosshair_v.show()
                self._crosshair_h.show()

    def _hide_crosshair(self):
        """Hide crosshair lines."""
        if self._crosshair_v:
            self._crosshair_v.hide()
        if self._crosshair_h:
            self._crosshair_h.hide()

    def leaveEvent(self, event):
        """Hide crosshair when mouse leaves."""
        super().leaveEvent(event)
        self._hide_crosshair()

    def _update_median_labels(self):
        """Update median label positions and text."""
        if not self._chart_settings.get("show_median_label", True):
            if self._portfolio_median_label:
                self._portfolio_median_label.hide()
            if self._benchmark_median_label:
                self._benchmark_median_label.hide()
            return

        if self._current_result is None:
            if self._portfolio_median_label:
                self._portfolio_median_label.hide()
            if self._benchmark_median_label:
                self._benchmark_median_label.hide()
            return

        # Get visible X range
        (x0, x1), (y0, y1) = self._view_box.viewRange()
        rightmost_idx = int(min(max(0, x1), self._current_result.n_periods))

        if rightmost_idx < 0:
            return

        # Portfolio median label
        if self._portfolio_median_label and self._chart_settings.get("show_portfolio_median", True):
            initial = self._current_result.initial_value
            median_val = self._current_result.median_path[rightmost_idx]
            median_pct = (median_val / initial - 1) * 100

            self._portfolio_median_label.setText(f"{median_pct:+.1f}%")
            self._portfolio_median_label.adjustSize()

            # Position on right axis - only show if positioning succeeds
            if self._position_label_on_axis(self._portfolio_median_label, median_pct):
                self._portfolio_median_label.show()
        elif self._portfolio_median_label:
            self._portfolio_median_label.hide()

        # Benchmark median label
        if self._benchmark_median_label and self._current_benchmark_result is not None:
            if self._chart_settings.get("show_benchmark_median", True):
                bench_initial = self._current_benchmark_result.initial_value
                bench_rightmost = min(rightmost_idx, self._current_benchmark_result.n_periods)
                bench_median_val = self._current_benchmark_result.median_path[bench_rightmost]
                bench_median_pct = (bench_median_val / bench_initial - 1) * 100

                self._benchmark_median_label.setText(f"{bench_median_pct:+.1f}%")
                self._benchmark_median_label.adjustSize()

                # Position on right axis - only show if positioning succeeds
                if self._position_label_on_axis(
                    self._benchmark_median_label,
                    bench_median_pct,
                    offset_y=self._portfolio_median_label.height() + 4 if self._portfolio_median_label.isVisible() else 0
                ):
                    self._benchmark_median_label.show()
            else:
                self._benchmark_median_label.hide()
        elif self._benchmark_median_label:
            self._benchmark_median_label.hide()

    def _position_label_on_axis(self, label: QLabel, y_value: float, offset_y: int = 0) -> bool:
        """Position a label on the right axis at the given Y value.

        Returns True if positioning was successful, False otherwise.
        """
        axis_rect = self._get_right_axis_geometry()
        if not axis_rect or axis_rect.width() <= 0:
            # Axis geometry not ready - hide label and return False
            label.hide()
            return False

        # Validate that the right axis is actually on the right side of the chart.
        # During initialization, Qt may report valid geometry but with incorrect
        # positions (e.g., x=0), causing labels to flash across the screen.
        plot_width = self.plot_widget.width()
        if plot_width > 0 and axis_rect.left() < plot_width * 0.3:
            # Axis is positioned too far left - geometry not ready yet
            label.hide()
            return False

        # Map Y value to widget coordinates
        view_point = self._view_box.mapViewToScene(pg.Point(0, y_value))
        widget_point = self.plot_widget.mapFromScene(view_point)
        parent_point = self.plot_widget.mapToParent(widget_point)

        label_y = parent_point.y() - label.height() // 2 + offset_y

        # left_offset = 11 matches Chart module (accounts for column spacing + tick marks)
        left_offset = 11
        right_padding = 6

        # Set fixed width to span axis (matches Chart module pattern)
        label_width = axis_rect.width() - left_offset + right_padding
        label.setFixedWidth(max(int(label_width), 50))

        label.move(
            axis_rect.left() + left_offset,
            int(label_y)
        )
        return True

    def _get_right_axis_geometry(self):
        """Get the geometry of the right axis in widget coordinates."""
        axis = self.plot_item.getAxis("right")
        if axis is None:
            return None

        # Get axis bounding rect in scene coordinates
        scene_rect = axis.mapRectToScene(axis.boundingRect())
        # Map to widget coordinates
        top_left = self.plot_widget.mapFromScene(scene_rect.topLeft())
        bottom_right = self.plot_widget.mapFromScene(scene_rect.bottomRight())
        # Convert to parent widget coordinates
        top_left = self.plot_widget.mapToParent(top_left)
        bottom_right = self.plot_widget.mapToParent(bottom_right)

        from PySide6.QtCore import QRect
        return QRect(top_left, bottom_right)

    def update_chart_settings(self, settings: Dict[str, Any]):
        """Update chart settings and refresh display."""
        self._chart_settings.update(settings)

        # Update crosshair visibility
        if not settings.get("show_crosshair", True):
            if self._crosshair_v:
                self._crosshair_v.hide()
            if self._crosshair_h:
                self._crosshair_h.hide()

        # Update gridlines
        show_grid = settings.get("show_gridlines", True)
        self.plot_item.showGrid(x=show_grid, y=show_grid, alpha=0.3)

        # Update background color
        custom_bg = settings.get("chart_background")
        if custom_bg:
            self.plot_widget.setBackground(custom_bg)
            self.setStyleSheet(f"background-color: rgb{tuple(custom_bg)};")
        else:
            self._apply_theme()  # Use theme default

        # Update label styles (colors may have changed)
        self._update_label_styles()

        # Update median labels
        self._update_median_labels()

        # If we have a current result, redraw with new settings
        if self._current_result is not None:
            # Store current state
            result = self._current_result
            benchmark = self._current_benchmark_result

            # Merge new settings into a full settings dict for rendering
            full_settings = dict(self._chart_settings)
            full_settings.update(settings)

            # Re-render would require storing more state, so just update labels for now
            self._update_crosshair_color()
