"""Distribution Chart Widget - Histogram visualization with statistics panel."""

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import pyqtgraph as pg
from scipy import stats as scipy_stats
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
from app.services.returns_data_service import ReturnsDataService
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


# Qt PenStyle mapping
LINE_STYLES = {
    Qt.SolidLine: Qt.SolidLine,
    Qt.DashLine: Qt.DashLine,
    Qt.DotLine: Qt.DotLine,
    Qt.DashDotLine: Qt.DashDotLine,
}


class StatisticsPanel(LazyThemeMixin, QWidget):
    """Panel displaying return distribution statistics in horizontal layout."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self._current_metric = "Returns"
        self._setup_ui()
        self._apply_theme()
        # Lazy theme - only apply when visible
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup the statistics panel UI with horizontal layout (metrics as columns)."""
        # Use HBoxLayout to center the grid
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Add stretch to center the content
        outer_layout.addStretch(1)

        # Container widget for the grid
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setHorizontalSpacing(25)
        layout.setVerticalSpacing(6)

        # Column headers (row 0): Name, Mean, Std Dev, Skew, Kurtosis, Min, Max, Count, Cash Drag
        headers = ["", "Mean", "Std Dev", "Skew", "Kurtosis", "Min", "Max", "Count", "Cash Drag"]
        for col, header in enumerate(headers):
            label = self._create_header_label(header)
            layout.addWidget(label, 0, col)
            if col == 0:
                layout.setColumnMinimumWidth(col, 140)  # Name column wider
            else:
                layout.setColumnMinimumWidth(col, 85)

        # Row 1: Portfolio row
        self.portfolio_name_label = self._create_row_label("Portfolio")
        self.mean_value = self._create_value_label("--")
        self.std_value = self._create_value_label("--")
        self.skew_value = self._create_value_label("--")
        self.kurtosis_value = self._create_value_label("--")
        self.min_value = self._create_value_label("--")
        self.max_value = self._create_value_label("--")
        self.count_value = self._create_value_label("--")
        self.cash_drag_value = self._create_value_label("--")

        layout.addWidget(self.portfolio_name_label, 1, 0)
        layout.addWidget(self.mean_value, 1, 1)
        layout.addWidget(self.std_value, 1, 2)
        layout.addWidget(self.skew_value, 1, 3)
        layout.addWidget(self.kurtosis_value, 1, 4)
        layout.addWidget(self.min_value, 1, 5)
        layout.addWidget(self.max_value, 1, 6)
        layout.addWidget(self.count_value, 1, 7)
        layout.addWidget(self.cash_drag_value, 1, 8)

        # Row 2: Benchmark row (initially hidden)
        self.benchmark_name_label = self._create_row_label("Benchmark")
        self.benchmark_mean_value = self._create_value_label("--")
        self.benchmark_std_value = self._create_value_label("--")
        self.benchmark_skew_value = self._create_value_label("--")
        self.benchmark_kurtosis_value = self._create_value_label("--")
        self.benchmark_min_value = self._create_value_label("--")
        self.benchmark_max_value = self._create_value_label("--")
        self.benchmark_count_value = self._create_value_label("--")
        self.benchmark_cash_drag_value = self._create_value_label("--")

        layout.addWidget(self.benchmark_name_label, 2, 0)
        layout.addWidget(self.benchmark_mean_value, 2, 1)
        layout.addWidget(self.benchmark_std_value, 2, 2)
        layout.addWidget(self.benchmark_skew_value, 2, 3)
        layout.addWidget(self.benchmark_kurtosis_value, 2, 4)
        layout.addWidget(self.benchmark_min_value, 2, 5)
        layout.addWidget(self.benchmark_max_value, 2, 6)
        layout.addWidget(self.benchmark_count_value, 2, 7)
        layout.addWidget(self.benchmark_cash_drag_value, 2, 8)

        # Store benchmark widgets for visibility toggling
        self._benchmark_widgets = [
            self.benchmark_name_label,
            self.benchmark_mean_value,
            self.benchmark_std_value,
            self.benchmark_skew_value,
            self.benchmark_kurtosis_value,
            self.benchmark_min_value,
            self.benchmark_max_value,
            self.benchmark_count_value,
            self.benchmark_cash_drag_value,
        ]

        # Hide benchmark row by default
        self.set_benchmark_visible(False)

        # Add container to outer layout with stretch on both sides to center
        outer_layout.addWidget(container)
        outer_layout.addStretch(1)

    def _create_header_label(self, text: str) -> QLabel:
        """Create a column header label."""
        label = QLabel(text)
        label.setObjectName("headerLabel")
        label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        return label

    def _create_row_label(self, text: str) -> QLabel:
        """Create a row name label (portfolio/benchmark name)."""
        label = QLabel(text)
        label.setObjectName("rowLabel")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return label

    def _create_value_label(self, text: str) -> QLabel:
        """Create a statistic value label."""
        label = QLabel(text)
        label.setObjectName("statValue")
        label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        return label

    def set_portfolio_name(self, name: str):
        """Set the portfolio row name."""
        if name:
            self.portfolio_name_label.setText(name)
        else:
            self.portfolio_name_label.setText("Portfolio")

    def set_benchmark_visible(self, visible: bool, name: str = ""):
        """Show or hide the benchmark statistics row."""
        if name:
            self.benchmark_name_label.setText(name)
        else:
            self.benchmark_name_label.setText("Benchmark")

        for widget in self._benchmark_widgets:
            widget.setVisible(visible)

    def update_benchmark_statistics(self, stats: Dict[str, float]):
        """Update the benchmark statistics display."""
        is_time_under_water = self._current_metric == "Time Under Water"

        def fmt_value(val, decimals=2):
            if val is None or np.isnan(val):
                return "N/A"
            if is_time_under_water:
                return f"{val:.0f}"
            else:
                return f"{val * 100:.{decimals}f}%"

        def fmt_num(val, decimals=2):
            if val is None or np.isnan(val):
                return "N/A"
            return f"{val:.{decimals}f}"

        self.benchmark_mean_value.setText(fmt_value(stats.get("mean")))
        self.benchmark_std_value.setText(fmt_value(stats.get("std")))
        self.benchmark_skew_value.setText(fmt_num(stats.get("skew")))
        self.benchmark_kurtosis_value.setText(fmt_num(stats.get("kurtosis")))
        self.benchmark_min_value.setText(fmt_value(stats.get("min")))
        self.benchmark_max_value.setText(fmt_value(stats.get("max")))
        self.benchmark_count_value.setText(str(stats.get("count", 0)))

    def clear_benchmark(self):
        """Clear benchmark statistics and hide row."""
        self.benchmark_mean_value.setText("--")
        self.benchmark_std_value.setText("--")
        self.benchmark_skew_value.setText("--")
        self.benchmark_kurtosis_value.setText("--")
        self.benchmark_min_value.setText("--")
        self.benchmark_max_value.setText("--")
        self.benchmark_count_value.setText("--")
        self.benchmark_cash_drag_value.setText("--")
        self.set_benchmark_visible(False)

    def set_metric(self, metric: str):
        """Set the current metric for formatting purposes."""
        self._current_metric = metric

    def update_statistics(
        self,
        stats: Dict[str, float],
        cash_drag: Optional[Dict[str, float]] = None,
        show_cash_drag: bool = True,
        is_ticker_mode: bool = False,
    ):
        """Update the statistics display.

        Args:
            stats: Dictionary of statistics (mean, std, skew, kurtosis, min, max, count)
            cash_drag: Cash drag data from ReturnsDataService.calculate_cash_drag()
            show_cash_drag: If False (exclude_cash is True), show "--" for cash drag
            is_ticker_mode: If True, this is a ticker not a portfolio, show "--" for cash drag
        """
        is_time_under_water = self._current_metric == "Time Under Water"

        def fmt_value(val, decimals=2):
            if val is None or np.isnan(val):
                return "N/A"
            if is_time_under_water:
                return f"{val:.0f}"
            else:
                return f"{val * 100:.{decimals}f}%"

        def fmt_num(val, decimals=2):
            if val is None or np.isnan(val):
                return "N/A"
            return f"{val:.{decimals}f}"

        self.mean_value.setText(fmt_value(stats.get("mean")))
        self.std_value.setText(fmt_value(stats.get("std")))
        self.skew_value.setText(fmt_num(stats.get("skew")))
        self.kurtosis_value.setText(fmt_num(stats.get("kurtosis")))
        self.min_value.setText(fmt_value(stats.get("min")))
        self.max_value.setText(fmt_value(stats.get("max")))
        self.count_value.setText(str(stats.get("count", 0)))

        # Cash drag logic:
        # Show "--" if: exclude_cash setting is on, or it's a ticker, or cash_drag is None/0
        if not show_cash_drag or is_ticker_mode:
            self.cash_drag_value.setText("--")
        elif cash_drag is None:
            self.cash_drag_value.setText("--")
        else:
            drag_value = cash_drag.get("cash_drag_annualized", 0)
            if drag_value is None or drag_value == 0:
                self.cash_drag_value.setText("--")
            else:
                # Cash drag is already a decimal, convert to percentage
                self.cash_drag_value.setText(f"{drag_value * 100:.2f}%")

    def clear(self):
        """Clear all statistics."""
        self.mean_value.setText("--")
        self.std_value.setText("--")
        self.skew_value.setText("--")
        self.kurtosis_value.setText("--")
        self.min_value.setText("--")
        self.max_value.setText("--")
        self.count_value.setText("--")
        self.cash_drag_value.setText("--")

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#f5f5f5"
            text_color = "#000000"
            label_color = "#555555"
            border_color = "#cccccc"
        elif theme == "bloomberg":
            bg_color = "#0d1420"
            text_color = "#e8e8e8"
            label_color = "#888888"
            border_color = "#1a2332"
        else:  # dark
            bg_color = "#2d2d2d"
            text_color = "#ffffff"
            label_color = "#888888"
            border_color = "#3d3d3d"

        self.setStyleSheet(f"""
            StatisticsPanel {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QLabel#headerLabel {{
                color: {label_color};
                font-size: 16px;
                background-color: transparent;
            }}
            QLabel#rowLabel {{
                color: {text_color};
                font-size: 18px;
                background-color: transparent;
            }}
            QLabel#statValue {{
                color: {text_color};
                font-size: 18px;
                background-color: transparent;
            }}
        """)


class DistributionChart(LazyThemeMixin, QWidget):
    """
    Histogram visualization of portfolio returns with statistics panel.
    """

    # X-axis labels for each metric
    X_AXIS_LABELS = {
        "Returns": "Return (%)",
        "Volatility": "Annualized Volatility (%)",
        "Rolling Volatility": "Rolling Volatility (%)",
        "Drawdown": "Drawdown (%)",
        "Rolling Return": "Rolling Return (%)",
        "Time Under Water": "Days Under Water",
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application

        # Store current returns for redraws
        self._current_returns: Optional[pd.Series] = None
        self._current_settings: Dict = {}
        self._current_metric: str = "Returns"

        # Benchmark data
        self._benchmark_returns: Optional[pd.Series] = None
        self._benchmark_name: str = ""

        # Overlay items
        self.bar_graph = None
        self.benchmark_bar_graph = None
        self.kde_curve = None
        self.benchmark_kde_curve = None
        self.normal_curve = None
        self.mean_line = None
        self.median_line = None
        self.benchmark_mean_line = None
        self.benchmark_median_line = None
        self.cdf_curve = None
        self.benchmark_cdf_curve = None
        self.legend = None

        # Benchmark mode flag
        self._has_benchmark = False

        self._setup_ui()
        self._apply_theme()

        # Lazy theme - only apply when visible
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup the chart UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Histogram using PyQtGraph
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("bottom", "Return (%)")
        self.plot_widget.setLabel("left", "Frequency")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        layout.addWidget(self.plot_widget, stretch=1)

        # Placeholder message (shown when no data)
        self.placeholder = QLabel("Select a portfolio to view return distribution")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setObjectName("placeholder")
        self.placeholder.setVisible(False)
        layout.addWidget(self.placeholder)

        # Statistics panel at bottom
        self.stats_panel = StatisticsPanel(self.theme_manager)
        self.stats_panel.setFixedHeight(95)  # Compact horizontal layout with larger text
        layout.addWidget(self.stats_panel)

    def set_metric(self, metric: str):
        """
        Set the current metric and update axis labels.

        Args:
            metric: The metric name (e.g., "Returns", "Volatility", "Time Under Water")
        """
        self._current_metric = metric
        x_label = self.X_AXIS_LABELS.get(metric, "Value (%)")
        self.plot_widget.setLabel("bottom", x_label)
        self.stats_panel.set_metric(metric)

    def set_returns(
        self,
        returns: pd.Series,
        settings: Dict[str, Any],
        cash_drag: Optional[Dict[str, float]] = None,
        show_cash_drag: bool = True,
        num_bins: int = 30,
        benchmark_returns: Optional[pd.Series] = None,
        benchmark_name: str = "",
        portfolio_name: str = "",
        is_ticker_mode: bool = False,
    ):
        """
        Update the histogram with new return data.

        Args:
            returns: Series of portfolio returns (as decimals, e.g., 0.05 = 5%)
            settings: Full settings dict from DistributionSettingsManager
            cash_drag: Cash drag statistics
            show_cash_drag: Whether to show cash drag statistic
            num_bins: Number of histogram bins
            benchmark_returns: Optional benchmark returns for comparison overlay
            benchmark_name: Name of the benchmark (ticker or portfolio name)
            portfolio_name: Name of the portfolio or ticker being displayed
            is_ticker_mode: If True, portfolio is a ticker not a portfolio
        """
        # Clear existing plot and overlays
        self._clear_overlays()

        # Store for potential redraws
        self._current_returns = returns
        self._benchmark_returns = benchmark_returns
        self._benchmark_name = benchmark_name
        self._portfolio_name = portfolio_name
        self._current_settings = settings

        # Determine if we're in benchmark mode
        has_benchmark = benchmark_returns is not None and not benchmark_returns.empty
        self._has_benchmark = has_benchmark

        # Extract visualization settings based on mode
        if has_benchmark:
            show_portfolio_kde = settings.get("benchmark_show_portfolio_kde", True)
            show_benchmark_kde = settings.get("benchmark_show_benchmark_kde", True)
            show_kde_curve = show_portfolio_kde or show_benchmark_kde
            show_normal_distribution = settings.get("benchmark_show_normal_distribution", True)
            show_cdf_view = settings.get("benchmark_show_cdf_view", False)
            # Mean/median controlled per-line in benchmark mode
            show_mean_median_lines = (
                settings.get("benchmark_show_portfolio_mean", True) or
                settings.get("benchmark_show_portfolio_median", True) or
                settings.get("benchmark_show_benchmark_mean", True) or
                settings.get("benchmark_show_benchmark_median", True)
            )
        else:
            show_kde_curve = settings.get("show_kde_curve", True)
            show_normal_distribution = settings.get("show_normal_distribution", True)
            show_cdf_view = settings.get("show_cdf_view", False)
            show_mean_median_lines = (
                settings.get("show_mean_line", True) or
                settings.get("show_median_line", True)
            )

        # Apply gridlines setting
        show_gridlines = settings.get("show_gridlines", True)
        self.plot_widget.showGrid(x=show_gridlines, y=show_gridlines, alpha=0.3)

        # Apply background color setting
        self._apply_background_color(settings)

        if returns is None or returns.empty:
            self.show_placeholder("No return data available")
            self.stats_panel.clear()
            return

        # Hide placeholder
        self.placeholder.setVisible(False)
        self.plot_widget.setVisible(True)

        # Drop NaN values
        returns = returns.dropna()

        if len(returns) < 2:
            self.show_placeholder("Insufficient data for distribution")
            self.stats_panel.clear()
            return

        # Convert to display format based on metric type
        if self._current_metric == "Time Under Water":
            # Time Under Water is already in days, no conversion needed
            values_display = returns.copy()
        else:
            # All other metrics: convert from decimal to percentage
            values_display = returns * 100

        # Process benchmark returns if provided
        benchmark_values_display = None
        if benchmark_returns is not None and not benchmark_returns.empty:
            benchmark_clean = benchmark_returns.dropna()
            if len(benchmark_clean) >= 2:
                if self._current_metric == "Time Under Water":
                    benchmark_values_display = benchmark_clean.copy()
                else:
                    benchmark_values_display = benchmark_clean * 100

        if show_cdf_view:
            # Draw CDF instead of histogram
            self._draw_cdf(values_display, is_portfolio=True)
            # Draw benchmark CDF if available
            if benchmark_values_display is not None:
                self._draw_cdf(benchmark_values_display, is_portfolio=False)
            self.plot_widget.setLabel("left", "Cumulative Probability")
        else:
            # Draw histogram
            self._draw_histogram(values_display, num_bins)
            self.plot_widget.setLabel("left", "Frequency")

            # Draw benchmark histogram if provided (behind portfolio)
            if benchmark_values_display is not None:
                self._draw_benchmark_histogram(benchmark_values_display, num_bins)

            # Draw overlays on histogram
            if show_kde_curve:
                # In benchmark mode, check individual toggles
                if has_benchmark:
                    if settings.get("benchmark_show_portfolio_kde", True):
                        self._draw_kde_curve(values_display, num_bins, is_portfolio=True)
                    if benchmark_values_display is not None and settings.get("benchmark_show_benchmark_kde", True):
                        self._draw_kde_curve(
                            benchmark_values_display, num_bins, is_portfolio=False
                        )
                else:
                    self._draw_kde_curve(values_display, num_bins, is_portfolio=True)

            if show_normal_distribution:
                self._draw_normal_distribution(values_display, num_bins)

        # Mean/median lines apply to both views
        if show_mean_median_lines:
            self._draw_mean_median_lines(values_display, benchmark_values_display)

        # Add legend if any overlays are enabled
        self._update_legend(
            values_display,
            show_kde_curve=show_kde_curve,
            show_normal_distribution=show_normal_distribution,
            show_mean_median_lines=show_mean_median_lines,
            show_cdf_view=show_cdf_view,
            has_benchmark=benchmark_values_display is not None,
            benchmark_values_display=benchmark_values_display,
        )

        # Auto-range
        self.plot_widget.autoRange()

        # Calculate and display statistics
        stats = self._calculate_statistics(returns)
        self.stats_panel.update_statistics(stats, cash_drag, show_cash_drag, is_ticker_mode)

        # Update stats panel portfolio header
        self.stats_panel.set_portfolio_name(portfolio_name)

        # Handle benchmark statistics
        if benchmark_values_display is not None and benchmark_returns is not None:
            benchmark_stats = self._calculate_statistics(benchmark_returns.dropna())
            self.stats_panel.set_benchmark_visible(True, benchmark_name)
            self.stats_panel.update_benchmark_statistics(benchmark_stats)
        else:
            self.stats_panel.set_benchmark_visible(False)

    def _clear_overlays(self):
        """Clear all overlay items."""
        # Remove legend from ViewBox before clearing (it's parented to vb, not PlotItem)
        if self.legend is not None:
            self.legend.scene().removeItem(self.legend)
            self.legend = None

        self.plot_widget.clear()
        self.bar_graph = None
        self.benchmark_bar_graph = None
        self.kde_curve = None
        self.benchmark_kde_curve = None
        self.normal_curve = None
        self.mean_line = None
        self.median_line = None
        self.benchmark_mean_line = None
        self.benchmark_median_line = None
        self.cdf_curve = None
        self.benchmark_cdf_curve = None

    def _draw_histogram(self, returns_pct: pd.Series, num_bins: int):
        """Draw histogram bars."""
        counts, bin_edges = np.histogram(returns_pct, bins=num_bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_width = bin_edges[1] - bin_edges[0]

        self.bar_graph = pg.BarGraphItem(
            x=bin_centers,
            height=counts,
            width=bin_width * 0.9,
            brush=self._get_bar_color(),
            pen=self._get_bar_pen(),
        )
        self.plot_widget.addItem(self.bar_graph)

    def _draw_benchmark_histogram(self, benchmark_pct: pd.Series, num_bins: int):
        """Draw semi-transparent benchmark histogram overlay."""
        counts, bin_edges = np.histogram(benchmark_pct, bins=num_bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_width = bin_edges[1] - bin_edges[0]

        self.benchmark_bar_graph = pg.BarGraphItem(
            x=bin_centers,
            height=counts,
            width=bin_width * 0.8,  # Slightly narrower than portfolio bars
            brush=self._get_benchmark_bar_color(),
            pen=self._get_benchmark_bar_pen(),
        )
        self.plot_widget.addItem(self.benchmark_bar_graph)

    def _draw_kde_curve(
        self, returns_pct: pd.Series, num_bins: int, is_portfolio: bool = True
    ):
        """Draw KDE (Kernel Density Estimation) curve overlay."""
        if len(returns_pct) < 3:
            return

        try:
            # Calculate KDE
            kde = scipy_stats.gaussian_kde(returns_pct.values)

            # Generate x values for smooth curve
            x_min, x_max = returns_pct.min(), returns_pct.max()
            x_range = x_max - x_min
            x = np.linspace(x_min - x_range * 0.1, x_max + x_range * 0.1, 200)
            y = kde(x)

            # Scale KDE to match histogram height
            counts, bin_edges = np.histogram(returns_pct, bins=num_bins)
            bin_width = bin_edges[1] - bin_edges[0]
            y_scaled = y * len(returns_pct) * bin_width

            # Draw curve with appropriate pen
            pen = self._get_kde_pen(is_portfolio=is_portfolio)
            curve = self.plot_widget.plot(x, y_scaled, pen=pen)

            # Store in appropriate attribute
            if is_portfolio:
                self.kde_curve = curve
            else:
                self.benchmark_kde_curve = curve

        except Exception as e:
            print(f"Error drawing KDE curve: {e}")

    def _draw_normal_distribution(self, returns_pct: pd.Series, num_bins: int):
        """Draw normal distribution overlay (dashed line)."""
        if len(returns_pct) < 3:
            return

        try:
            mean = returns_pct.mean()
            std = returns_pct.std()

            # Generate x values
            x_min, x_max = returns_pct.min(), returns_pct.max()
            x_range = x_max - x_min
            x = np.linspace(x_min - x_range * 0.1, x_max + x_range * 0.1, 200)

            # Calculate normal PDF
            y = scipy_stats.norm.pdf(x, mean, std)

            # Scale to match histogram height
            counts, bin_edges = np.histogram(returns_pct, bins=num_bins)
            bin_width = bin_edges[1] - bin_edges[0]
            y_scaled = y * len(returns_pct) * bin_width

            # Draw dashed curve
            pen = self._get_normal_pen()
            self.normal_curve = self.plot_widget.plot(x, y_scaled, pen=pen)

        except Exception as e:
            print(f"Error drawing normal distribution: {e}")

    def _draw_mean_median_lines(self, returns_pct: pd.Series, benchmark_pct: Optional[pd.Series] = None):
        """Draw vertical lines for mean and median."""
        settings = self._current_settings
        has_benchmark = self._has_benchmark and benchmark_pct is not None

        if has_benchmark:
            # Benchmark mode: separate toggles for each line
            # Portfolio mean
            if settings.get("benchmark_show_portfolio_mean", True):
                mean_val = returns_pct.mean()
                mean_pen = self._get_mean_pen(is_portfolio=True)
                self.mean_line = pg.InfiniteLine(pos=mean_val, angle=90, pen=mean_pen)
                self.plot_widget.addItem(self.mean_line)

            # Portfolio median
            if settings.get("benchmark_show_portfolio_median", True):
                median_val = returns_pct.median()
                median_pen = self._get_median_pen(is_portfolio=True)
                self.median_line = pg.InfiniteLine(pos=median_val, angle=90, pen=median_pen)
                self.plot_widget.addItem(self.median_line)

            # Benchmark mean
            if settings.get("benchmark_show_benchmark_mean", True):
                benchmark_mean_val = benchmark_pct.mean()
                benchmark_mean_pen = self._get_mean_pen(is_portfolio=False)
                self.benchmark_mean_line = pg.InfiniteLine(
                    pos=benchmark_mean_val, angle=90, pen=benchmark_mean_pen
                )
                self.plot_widget.addItem(self.benchmark_mean_line)

            # Benchmark median
            if settings.get("benchmark_show_benchmark_median", True):
                benchmark_median_val = benchmark_pct.median()
                benchmark_median_pen = self._get_median_pen(is_portfolio=False)
                self.benchmark_median_line = pg.InfiniteLine(
                    pos=benchmark_median_val, angle=90, pen=benchmark_median_pen
                )
                self.plot_widget.addItem(self.benchmark_median_line)
        else:
            # Portfolio mode: show_mean_line and show_median_line
            if settings.get("show_mean_line", True):
                mean_val = returns_pct.mean()
                mean_pen = self._get_mean_pen(is_portfolio=True)
                self.mean_line = pg.InfiniteLine(pos=mean_val, angle=90, pen=mean_pen)
                self.plot_widget.addItem(self.mean_line)

            if settings.get("show_median_line", True):
                median_val = returns_pct.median()
                median_pen = self._get_median_pen(is_portfolio=True)
                self.median_line = pg.InfiniteLine(pos=median_val, angle=90, pen=median_pen)
                self.plot_widget.addItem(self.median_line)

    def _draw_cdf(self, returns_pct: pd.Series, is_portfolio: bool = True):
        """Draw cumulative distribution function."""
        # Sort values for CDF
        sorted_returns = np.sort(returns_pct.values)
        cdf_y = np.arange(1, len(sorted_returns) + 1) / len(sorted_returns)

        # Draw CDF curve with appropriate pen
        pen = self._get_cdf_pen(is_portfolio=is_portfolio)
        curve = self.plot_widget.plot(sorted_returns, cdf_y, pen=pen)

        if is_portfolio:
            self.cdf_curve = curve
        else:
            self.benchmark_cdf_curve = curve

    def _update_legend(
        self,
        values_display: pd.Series,
        show_kde_curve: bool,
        show_normal_distribution: bool,
        show_mean_median_lines: bool,
        show_cdf_view: bool,
        has_benchmark: bool = False,
        benchmark_values_display: Optional[pd.Series] = None,
    ):
        """Add legend to top-left of plot."""
        # Create legend anchored to top-left inside the plot area
        self.legend = pg.LegendItem(offset=(10, 1), labelTextSize="11pt")
        self.legend.setParentItem(self.plot_widget.getPlotItem().vb)

        settings = self._current_settings
        portfolio_name = self._portfolio_name if self._portfolio_name else "Portfolio"
        benchmark_name = self._benchmark_name if self._benchmark_name else "Benchmark"

        # Always add portfolio entry in histogram mode
        if not show_cdf_view:
            # Portfolio bar entry - use actual portfolio/ticker name (pen=None removes border line)
            self.legend.addItem(
                pg.BarGraphItem(x=[0], height=[0], width=0.5, brush=self._get_bar_color(), pen=None),
                portfolio_name
            )
            # Benchmark bar entry (only when benchmark is present)
            if has_benchmark:
                self.legend.addItem(
                    pg.BarGraphItem(x=[0], height=[0], width=0.5, brush=self._get_benchmark_bar_color(), pen=None),
                    benchmark_name
                )

        # Add items based on what's enabled
        if show_cdf_view:
            # CDF view - show portfolio and benchmark with CDF line styles
            cdf_pen = self._get_cdf_pen(is_portfolio=True)
            self.legend.addItem(
                pg.PlotDataItem(pen=cdf_pen),
                portfolio_name
            )
            # Add benchmark CDF entry if benchmark is present
            if has_benchmark:
                benchmark_cdf_pen = self._get_cdf_pen(is_portfolio=False)
                self.legend.addItem(
                    pg.PlotDataItem(pen=benchmark_cdf_pen),
                    benchmark_name
                )
        else:
            # Histogram mode overlays
            if show_kde_curve:
                if has_benchmark:
                    # Show separate KDE entries for portfolio and benchmark
                    if self.kde_curve and settings.get("benchmark_show_portfolio_kde", True):
                        kde_pen = self._get_kde_pen(is_portfolio=True)
                        self.legend.addItem(
                            pg.PlotDataItem(pen=kde_pen),
                            f"{portfolio_name} KDE"
                        )
                    if self.benchmark_kde_curve and settings.get("benchmark_show_benchmark_kde", True):
                        benchmark_kde_pen = self._get_kde_pen(is_portfolio=False)
                        self.legend.addItem(
                            pg.PlotDataItem(pen=benchmark_kde_pen),
                            f"{benchmark_name} KDE"
                        )
                elif self.kde_curve:
                    kde_pen = self._get_kde_pen()
                    self.legend.addItem(
                        pg.PlotDataItem(pen=kde_pen),
                        "KDE Curve"
                    )

            if show_normal_distribution and self.normal_curve:
                normal_pen = self._get_normal_pen()
                self.legend.addItem(
                    pg.PlotDataItem(pen=normal_pen),
                    "Normal Dist."
                )

        # Mean/median lines apply to both views
        if show_mean_median_lines:
            if has_benchmark:
                # Show separate mean/median entries for portfolio and benchmark
                if self._current_metric == "Time Under Water":
                    fmt = lambda v: f"{v:.0f} days"
                else:
                    fmt = lambda v: f"{v:.2f}%"

                # Portfolio mean
                if settings.get("benchmark_show_portfolio_mean", True) and self.mean_line:
                    mean_val = values_display.mean()
                    mean_pen = self._get_mean_pen(is_portfolio=True)
                    self.legend.addItem(
                        pg.PlotDataItem(pen=mean_pen),
                        f"{portfolio_name} Mean ({fmt(mean_val)})"
                    )

                # Portfolio median
                if settings.get("benchmark_show_portfolio_median", True) and self.median_line:
                    median_val = values_display.median()
                    median_pen = self._get_median_pen(is_portfolio=True)
                    self.legend.addItem(
                        pg.PlotDataItem(pen=median_pen),
                        f"{portfolio_name} Median ({fmt(median_val)})"
                    )

                # Benchmark mean
                if settings.get("benchmark_show_benchmark_mean", True) and self.benchmark_mean_line and benchmark_values_display is not None:
                    benchmark_mean_val = benchmark_values_display.mean()
                    benchmark_mean_pen = self._get_mean_pen(is_portfolio=False)
                    self.legend.addItem(
                        pg.PlotDataItem(pen=benchmark_mean_pen),
                        f"{benchmark_name} Mean ({fmt(benchmark_mean_val)})"
                    )

                # Benchmark median
                if settings.get("benchmark_show_benchmark_median", True) and self.benchmark_median_line and benchmark_values_display is not None:
                    benchmark_median_val = benchmark_values_display.median()
                    benchmark_median_pen = self._get_median_pen(is_portfolio=False)
                    self.legend.addItem(
                        pg.PlotDataItem(pen=benchmark_median_pen),
                        f"{benchmark_name} Median ({fmt(benchmark_median_val)})"
                    )
            else:
                # Single portfolio mode
                mean_val = values_display.mean()
                median_val = values_display.median()

                # Format based on metric type
                if self._current_metric == "Time Under Water":
                    mean_label = f"Mean ({mean_val:.0f} days)"
                    median_label = f"Median ({median_val:.0f} days)"
                else:
                    mean_label = f"Mean ({mean_val:.2f}%)"
                    median_label = f"Median ({median_val:.2f}%)"

                if settings.get("show_mean_line", True) and self.mean_line:
                    mean_pen = self._get_mean_pen()
                    self.legend.addItem(
                        pg.PlotDataItem(pen=mean_pen),
                        mean_label
                    )

                if settings.get("show_median_line", True) and self.median_line:
                    median_pen = self._get_median_pen()
                    self.legend.addItem(
                        pg.PlotDataItem(pen=median_pen),
                        median_label
                    )

    def _calculate_statistics(self, returns: pd.Series) -> Dict[str, float]:
        """Calculate distribution statistics using centralized service."""
        return ReturnsDataService.get_distribution_statistics(returns)

    def show_placeholder(self, message: str):
        """Show placeholder message."""
        self._clear_overlays()
        self.placeholder.setText(message)
        self.placeholder.setVisible(True)

    def apply_general_settings(self, settings: Dict[str, Any]):
        """
        Apply general chart settings (background color and gridlines).

        This can be called even when no data is displayed to show the user
        their settings are being applied.

        Args:
            settings: Full settings dict from DistributionSettingsManager
        """
        # Apply gridlines setting
        show_gridlines = settings.get("show_gridlines", False)
        self.plot_widget.showGrid(x=show_gridlines, y=show_gridlines, alpha=0.3)

        # Apply background color setting
        self._apply_background_color(settings)

    def clear(self):
        """Clear the chart and statistics."""
        self._clear_overlays()
        self._current_returns = None
        self._current_settings = {}
        self.stats_panel.clear()
        self.show_placeholder("Select a portfolio to view return distribution")

    def _apply_background_color(self, settings: Dict[str, Any]):
        """Apply background color from settings."""
        bg_color = settings.get("background_color")
        if bg_color is None:
            # Use theme default
            theme = self.theme_manager.current_theme
            if theme == "light":
                self.plot_widget.setBackground("#ffffff")
            elif theme == "bloomberg":
                self.plot_widget.setBackground("#000814")
            else:
                self.plot_widget.setBackground("#1e1e1e")
        else:
            self.plot_widget.setBackground(
                f"rgb({bg_color[0]},{bg_color[1]},{bg_color[2]})"
            )

    def _get_theme_default_color(self, color_type: str) -> Tuple[int, int, int]:
        """Get default color for a color type based on theme."""
        theme = self.theme_manager.current_theme
        defaults = {
            "histogram": {
                "dark": (0, 212, 255),
                "light": (0, 102, 204),
                "bloomberg": (255, 128, 0),
            },
            "kde": {
                "dark": (255, 100, 100),
                "light": (220, 50, 50),
                "bloomberg": (0, 200, 255),
            },
            "normal": {
                "dark": (180, 100, 255),
                "light": (150, 0, 150),
                "bloomberg": (200, 100, 255),
            },
            "mean": {
                "dark": (255, 100, 100),
                "light": (200, 50, 50),
                "bloomberg": (255, 80, 80),
            },
            "median": {
                "dark": (0, 200, 0),
                "light": (0, 150, 0),
                "bloomberg": (0, 200, 100),
            },
            "benchmark_kde": {
                "dark": (255, 140, 0),
                "light": (255, 100, 0),
                "bloomberg": (0, 180, 255),
            },
            "benchmark_portfolio_histogram": {
                "dark": (0, 212, 255),
                "light": (0, 102, 204),
                "bloomberg": (255, 128, 0),
            },
            "benchmark_benchmark_histogram": {
                "dark": (255, 140, 0),
                "light": (255, 100, 0),
                "bloomberg": (0, 180, 255),
            },
        }
        color_defaults = defaults.get(color_type, defaults["histogram"])
        return color_defaults.get(theme, color_defaults["dark"])

    def _get_bar_color(self):
        """Get bar color based on settings and theme."""
        settings = self._current_settings
        has_benchmark = self._has_benchmark

        if has_benchmark:
            color = settings.get("benchmark_portfolio_histogram_color")
            if color is None:
                color = self._get_theme_default_color("benchmark_portfolio_histogram")
        else:
            color = settings.get("histogram_color")
            if color is None:
                color = self._get_theme_default_color("histogram")

        return pg.mkBrush(color[0], color[1], color[2], 180)

    def _get_bar_pen(self):
        """Get bar border pen based on settings and theme."""
        settings = self._current_settings
        has_benchmark = self._has_benchmark

        if has_benchmark:
            color = settings.get("benchmark_portfolio_histogram_color")
            if color is None:
                color = self._get_theme_default_color("benchmark_portfolio_histogram")
        else:
            color = settings.get("histogram_color")
            if color is None:
                color = self._get_theme_default_color("histogram")

        # Darken for border
        border_color = (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40))
        return pg.mkPen(border_color[0], border_color[1], border_color[2], 255, width=1)

    def _get_benchmark_bar_color(self):
        """Get benchmark bar color (semi-transparent)."""
        settings = self._current_settings
        color = settings.get("benchmark_benchmark_histogram_color")

        if color is None:
            color = self._get_theme_default_color("benchmark_benchmark_histogram")

        # Semi-transparent brush
        return pg.mkBrush(color[0], color[1], color[2], 120)

    def _get_benchmark_bar_pen(self):
        """Get benchmark bar border pen."""
        settings = self._current_settings
        color = settings.get("benchmark_benchmark_histogram_color")

        if color is None:
            color = self._get_theme_default_color("benchmark_benchmark_histogram")

        # Darken for border
        border_color = (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40))
        return pg.mkPen(border_color[0], border_color[1], border_color[2], 180, width=1)

    def _get_kde_pen(self, is_portfolio: bool = True):
        """Get pen for KDE curve based on settings."""
        settings = self._current_settings
        has_benchmark = self._has_benchmark

        if has_benchmark:
            if is_portfolio:
                color = settings.get("benchmark_portfolio_kde_color")
                style = settings.get("benchmark_portfolio_kde_line_style", Qt.SolidLine)
                width = settings.get("benchmark_portfolio_kde_line_width", 2)
            else:
                color = settings.get("benchmark_kde_color")
                style = settings.get("benchmark_kde_line_style", Qt.SolidLine)
                width = settings.get("benchmark_kde_line_width", 2)
        else:
            color = settings.get("kde_color")
            style = settings.get("kde_line_style", Qt.SolidLine)
            width = settings.get("kde_line_width", 2)

        if color is None:
            color_type = "benchmark_kde" if has_benchmark and not is_portfolio else "kde"
            color = self._get_theme_default_color(color_type)

        return pg.mkPen(color=color, width=width, style=style)

    def _get_normal_pen(self):
        """Get pen for normal distribution curve based on settings."""
        settings = self._current_settings
        has_benchmark = self._has_benchmark

        if has_benchmark:
            color = settings.get("benchmark_normal_color")
            style = settings.get("benchmark_normal_line_style", Qt.DashLine)
            width = settings.get("benchmark_normal_line_width", 2)
        else:
            color = settings.get("normal_color")
            style = settings.get("normal_line_style", Qt.DashLine)
            width = settings.get("normal_line_width", 2)

        if color is None:
            color = self._get_theme_default_color("normal")

        return pg.mkPen(color=color, width=width, style=style)

    def _get_mean_pen(self, is_portfolio: bool = True):
        """Get pen for mean vertical line based on settings."""
        settings = self._current_settings
        has_benchmark = self._has_benchmark

        if has_benchmark:
            if is_portfolio:
                color = settings.get("benchmark_portfolio_mean_color")
                style = settings.get("benchmark_portfolio_mean_line_style", Qt.SolidLine)
                width = settings.get("benchmark_portfolio_mean_line_width", 2)
            else:
                color = settings.get("benchmark_benchmark_mean_color")
                style = settings.get("benchmark_benchmark_mean_line_style", Qt.DashLine)
                width = settings.get("benchmark_benchmark_mean_line_width", 2)
        else:
            color = settings.get("mean_color")
            style = settings.get("mean_line_style", Qt.SolidLine)
            width = settings.get("mean_line_width", 2)

        if color is None:
            color = self._get_theme_default_color("mean")

        return pg.mkPen(color=color, width=width, style=style)

    def _get_median_pen(self, is_portfolio: bool = True):
        """Get pen for median vertical line based on settings."""
        settings = self._current_settings
        has_benchmark = self._has_benchmark

        if has_benchmark:
            if is_portfolio:
                color = settings.get("benchmark_portfolio_median_color")
                style = settings.get("benchmark_portfolio_median_line_style", Qt.SolidLine)
                width = settings.get("benchmark_portfolio_median_line_width", 2)
            else:
                color = settings.get("benchmark_benchmark_median_color")
                style = settings.get("benchmark_benchmark_median_line_style", Qt.DashLine)
                width = settings.get("benchmark_benchmark_median_line_width", 2)
        else:
            color = settings.get("median_color")
            style = settings.get("median_line_style", Qt.SolidLine)
            width = settings.get("median_line_width", 2)

        if color is None:
            color = self._get_theme_default_color("median")

        return pg.mkPen(color=color, width=width, style=style)

    def _get_cdf_pen(self, is_portfolio: bool = True):
        """Get pen for CDF curve based on portfolio or benchmark."""
        theme = self.theme_manager.current_theme

        if is_portfolio:
            # Portfolio CDF - solid line
            if theme == "light":
                return pg.mkPen(0, 102, 204, 255, width=2, style=Qt.SolidLine)  # Blue
            elif theme == "bloomberg":
                return pg.mkPen(255, 128, 0, 255, width=2, style=Qt.SolidLine)  # Orange
            else:
                return pg.mkPen(0, 212, 255, 255, width=2, style=Qt.SolidLine)  # Cyan
        else:
            # Benchmark CDF - dashed line with different color
            if theme == "light":
                return pg.mkPen(255, 100, 0, 255, width=2, style=Qt.DashLine)  # Orange
            elif theme == "bloomberg":
                return pg.mkPen(0, 180, 255, 255, width=2, style=Qt.DashLine)  # Cyan
            else:
                return pg.mkPen(255, 140, 0, 255, width=2, style=Qt.DashLine)  # Orange

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
            text_color = "#000000"
            grid_color = "#cccccc"
            placeholder_color = "#666666"
        elif theme == "bloomberg":
            bg_color = "#000814"
            text_color = "#e8e8e8"
            grid_color = "#1a2332"
            placeholder_color = "#888888"
        else:  # dark
            bg_color = "#1e1e1e"
            text_color = "#ffffff"
            grid_color = "#3d3d3d"
            placeholder_color = "#888888"

        # Update plot widget
        self.plot_widget.setBackground(bg_color)

        # Update axis colors
        axis_pen = pg.mkPen(text_color, width=1)
        self.plot_widget.getAxis("bottom").setPen(axis_pen)
        self.plot_widget.getAxis("bottom").setTextPen(axis_pen)
        self.plot_widget.getAxis("left").setPen(axis_pen)
        self.plot_widget.getAxis("left").setTextPen(axis_pen)

        # Update bar colors if they exist
        if self.bar_graph:
            self.bar_graph.setOpts(
                brush=self._get_bar_color(),
                pen=self._get_bar_pen(),
            )

        # Update placeholder
        self.placeholder.setStyleSheet(f"""
            QLabel#placeholder {{
                color: {placeholder_color};
                font-size: 16px;
                background-color: {bg_color};
            }}
        """)

        # Main widget background
        self.setStyleSheet(f"DistributionChart {{ background-color: {bg_color}; }}")
