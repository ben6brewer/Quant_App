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
    """Panel displaying Monte Carlo simulation statistics."""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()

    def _setup_ui(self):
        """Setup statistics panel layout."""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setMaximumHeight(100)

        layout = QGridLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(20)

        # Create labels for statistics
        self.labels = {}
        stats = [
            ("initial", "Initial Value"),
            ("median_terminal", "Median Terminal"),
            ("mean_terminal", "Mean Terminal"),
            ("cagr", "Implied CAGR"),
            ("prob_positive", "P(Gain)"),
            ("prob_loss_10", "P(Loss > 10%)"),
            ("var_95", "VaR (95%)"),
            ("cvar_95", "CVaR (95%)"),
        ]

        for col, (key, label) in enumerate(stats):
            header = QLabel(label)
            header.setObjectName("stat_header")
            header.setAlignment(Qt.AlignCenter)
            layout.addWidget(header, 0, col)

            value = QLabel("--")
            value.setObjectName("stat_value")
            value.setAlignment(Qt.AlignCenter)
            layout.addWidget(value, 1, col)
            self.labels[key] = value

    def update_statistics(
        self,
        result: SimulationResult,
        var_cvar: Dict[str, Dict[str, float]],
        probabilities: Dict[str, float],
    ):
        """Update displayed statistics from simulation result."""
        # Initial value
        self.labels["initial"].setText(f"${result.initial_value:,.0f}")

        # Terminal values
        self.labels["median_terminal"].setText(f"${result.median_terminal:,.0f}")
        self.labels["mean_terminal"].setText(f"${result.mean_terminal:,.0f}")

        # CAGR
        cagr = result.terminal_cagr
        if not np.isnan(cagr):
            self.labels["cagr"].setText(f"{cagr * 100:+.1f}%")
        else:
            self.labels["cagr"].setText("--")

        # Probabilities
        prob_pos = probabilities.get("prob_positive", 0)
        self.labels["prob_positive"].setText(f"{prob_pos * 100:.1f}%")

        prob_loss = probabilities.get("prob_loss_10pct", 0)
        self.labels["prob_loss_10"].setText(f"{prob_loss * 100:.1f}%")

        # VaR and CVaR
        if "0.95" in var_cvar:
            var_95 = var_cvar["0.95"]["var_pct"]
            cvar_95 = var_cvar["0.95"]["cvar_pct"]
            self.labels["var_95"].setText(f"{var_95:+.1f}%")
            self.labels["cvar_95"].setText(f"{cvar_95:+.1f}%")
        else:
            self.labels["var_95"].setText("--")
            self.labels["cvar_95"].setText("--")

    def clear(self):
        """Clear all statistics."""
        for label in self.labels.values():
            label.setText("--")

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
            QLabel#stat_value {{
                color: {text};
                font-size: 14px;
                font-weight: bold;
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
        self.plot_item.setLabel("left", "Portfolio Value ($)")
        self.plot_item.setLabel("bottom", "Trading Days")

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
    ):
        """Display simulation result on chart."""
        self._current_result = result
        self._clear_plot()

        # Show chart, hide placeholder
        self.placeholder.setVisible(False)
        self.plot_widget.setVisible(True)

        # Get x values (trading days)
        n_points = result.n_periods + 1
        x = np.arange(n_points)

        theme = self.theme_manager.current_theme

        # Draw 90% confidence band (5th - 95th percentile)
        if settings.get("show_band_90", True):
            p5 = result.get_percentile(5)
            p95 = result.get_percentile(95)
            color = settings.get("band_90_color", (100, 100, 255))
            fill = pg.FillBetweenItem(
                pg.PlotDataItem(x, p5),
                pg.PlotDataItem(x, p95),
                brush=(*color, 50),  # Semi-transparent
            )
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

        # Draw 50% confidence band (25th - 75th percentile)
        if settings.get("show_band_50", True):
            p25 = result.get_percentile(25)
            p75 = result.get_percentile(75)
            color = settings.get("band_50_color", (50, 50, 200))
            fill = pg.FillBetweenItem(
                pg.PlotDataItem(x, p25),
                pg.PlotDataItem(x, p75),
                brush=(*color, 80),
            )
            self.plot_item.addItem(fill)
            self._plot_items.append(fill)

        # Draw median line
        if settings.get("show_median", True):
            median = result.median_path
            color = settings.get("median_color", (255, 255, 255))
            pen = pg.mkPen(color=color, width=2, style=Qt.SolidLine)
            line = self.plot_item.plot(x, median, pen=pen, name="Median")
            self._plot_items.append(line)

        # Draw mean line
        if settings.get("show_mean", False):
            mean = result.mean_path
            color = settings.get("mean_color", (255, 200, 0))
            pen = pg.mkPen(color=color, width=2, style=Qt.DashLine)
            line = self.plot_item.plot(x, mean, pen=pen, name="Mean")
            self._plot_items.append(line)

        # Draw initial value line
        pen = pg.mkPen(color=(100, 100, 100), width=1, style=Qt.DotLine)
        line = self.plot_item.plot(
            x, np.full(n_points, result.initial_value), pen=pen
        )
        self._plot_items.append(line)

        # Auto-range
        self.plot_item.autoRange()

        # Calculate and update statistics
        from ..services.monte_carlo_service import MonteCarloService

        var_cvar = MonteCarloService.calculate_var_cvar(
            result.terminal_values, result.initial_value
        )
        probabilities = MonteCarloService.calculate_probability_metrics(
            result.terminal_values, result.initial_value
        )
        self.stats_panel.update_statistics(result, var_cvar, probabilities)

    def _clear_plot(self):
        """Clear all plot items."""
        for item in self._plot_items:
            self.plot_item.removeItem(item)
        self._plot_items.clear()

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

        # Apply to statistics panel
        self.stats_panel.apply_theme(theme)

        # Apply to placeholder
        self.placeholder.setStyleSheet(f"font-size: 16px; color: #888888; background: transparent;")

        # Container background
        self.setStyleSheet(f"background-color: rgb{bg_rgb};")
