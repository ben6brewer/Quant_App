"""Performance Metrics Table Widget - Bloomberg-style metrics display."""

from __future__ import annotations

from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QBrush

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class PerformanceMetricsTable(LazyThemeMixin, QTableWidget):
    """
    Bloomberg-style performance metrics table.

    Displays portfolio statistics across multiple time periods with optional
    benchmark comparison.
    """

    # Time period definitions: (display_name, trading_days or None for YTD)
    TIME_PERIODS = [
        ("3 Months", 63),
        ("6 Months", 126),
        ("12 Months", 252),
        ("YTD", None),
    ]

    # Metric definitions: (display_label, metric_key, has_benchmark_value, format_type)
    # format_type: "percent", "ratio", "decimal", "capture"
    RETURN_METRICS = [
        ("Total Return", "total_return", True, "percent"),
        ("Maximum Return", "max_return", True, "percent"),
        ("Minimum Return", "min_return", True, "percent"),
        ("Mean Return (Annualized)", "mean_return_annualized", True, "percent"),
        ("Mean Excess Return (Ann.)", "mean_excess_return", False, "percent"),
    ]

    RISK_METRICS = [
        ("Standard Deviation (Ann.)", "std_annualized", True, "percent"),
        ("Downside Risk (Ann.)", "downside_risk", True, "percent"),
        ("Skewness", "skewness", True, "decimal"),
        ("VaR 95% (ex-post)", "var_95", True, "percent"),
        ("Tracking Error (Ann.)", "tracking_error", False, "percent"),
    ]

    RISK_RETURN_METRICS = [
        ("Sharpe Ratio", "sharpe_ratio", True, "ratio"),
        ("Sortino Ratio", "sortino_ratio", True, "ratio"),
        ("Jensen Alpha", "jensen_alpha", False, "percent"),
        ("Information Ratio", "information_ratio", False, "ratio"),
        ("Treynor Measure", "treynor_measure", False, "ratio"),
        ("Beta (ex-post)", "beta", False, "decimal"),
        ("Correlation", "correlation", False, "decimal4"),
        ("Capture Ratio (Up/Down)", "capture_ratio", False, "capture"),
    ]

    # Metrics that require a benchmark (has_benchmark_value = False means benchmark-only)
    BENCHMARK_ONLY_METRICS = {
        "mean_excess_return",
        "tracking_error",
        "jensen_alpha",
        "information_ratio",
        "treynor_measure",
        "beta",
        "correlation",
        "capture_ratio",
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._has_benchmark = False
        self._metrics_by_period: Dict[str, Dict[str, Any]] = {}
        self._visible_periods = list(self.TIME_PERIODS)  # Default: all visible

        self._setup_table()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_table(self):
        """Setup initial table structure."""
        self.setAlternatingRowColors(False)
        self.setShowGrid(True)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Hide both headers - we'll use table rows for headers
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)

        # Disable scrollbars to prevent extra space
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Enable row height stretching
        self.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Build initial structure without benchmark
        self._rebuild_table()

    def set_has_benchmark(self, has_benchmark: bool):
        """Update table structure based on benchmark presence."""
        if self._has_benchmark != has_benchmark:
            self._has_benchmark = has_benchmark
            self._rebuild_table()

    def set_visible_periods(self, show_3m: bool, show_6m: bool, show_12m: bool, show_ytd: bool):
        """Set which time periods are visible."""
        new_visible = []
        for period_name, trading_days in self.TIME_PERIODS:
            if period_name == "3 Months" and show_3m:
                new_visible.append((period_name, trading_days))
            elif period_name == "6 Months" and show_6m:
                new_visible.append((period_name, trading_days))
            elif period_name == "12 Months" and show_12m:
                new_visible.append((period_name, trading_days))
            elif period_name == "YTD" and show_ytd:
                new_visible.append((period_name, trading_days))

        if new_visible != self._visible_periods:
            self._visible_periods = new_visible
            self._rebuild_table()

    def _get_filtered_metrics(self, metrics_list):
        """Filter metrics based on benchmark presence."""
        if self._has_benchmark:
            return metrics_list
        # Hide benchmark-only metrics when no benchmark
        return [m for m in metrics_list if m[1] not in self.BENCHMARK_ONLY_METRICS]

    def _rebuild_table(self):
        """Rebuild table structure based on benchmark mode."""
        self.clear()
        self.clearSpans()

        num_periods = len(self._visible_periods)
        if self._has_benchmark:
            # 1 label column + N periods * 2 sub-columns
            self.setColumnCount(1 + num_periods * 2)
        else:
            # 1 label column + N periods
            self.setColumnCount(1 + num_periods)

        # Get filtered metrics for current mode
        return_metrics = self._get_filtered_metrics(self.RETURN_METRICS)
        risk_metrics = self._get_filtered_metrics(self.RISK_METRICS)
        risk_return_metrics = self._get_filtered_metrics(self.RISK_RETURN_METRICS)

        # Calculate row count:
        # - Row 0: Period headers (3 Months, 6 Months, etc.)
        # - Row 1: Port/Bmrk sub-headers (only in benchmark mode)
        # - Then: 3 section headers + filtered metrics
        header_rows = 2 if self._has_benchmark else 1
        total_metrics = len(return_metrics) + len(risk_metrics) + len(risk_return_metrics)
        row_count = header_rows + 3 + total_metrics  # headers + 3 sections + metrics

        self.setRowCount(row_count)

        # Set column widths (75% larger than original)
        label_width = 350
        data_col_width = 96 if self._has_benchmark else 140

        self.setColumnWidth(0, label_width)
        for i in range(1, self.columnCount()):
            self.setColumnWidth(i, data_col_width)

        # Calculate and set fixed width to show all columns (no extra space)
        total_width = label_width + (self.columnCount() - 1) * data_col_width + 2  # +2 for border
        self.setFixedWidth(total_width)

        # Populate structure
        self._populate_structure()

        # Apply theme colors to structure (even before data is loaded)
        self._apply_value_colors()

    def _populate_structure(self):
        """Populate table with headers, section headers and metric labels."""
        row = 0

        # Row 0: Period headers
        # First cell: "Portfolio Statistics"
        header_item = QTableWidgetItem("Portfolio Statistics")
        header_item.setFlags(Qt.ItemIsEnabled)
        font = header_item.font()
        font.setBold(True)
        header_item.setFont(font)
        self.setItem(row, 0, header_item)

        if self._has_benchmark:
            # Period headers span 2 columns each (Port + Bmrk)
            for i, (period_name, _) in enumerate(self._visible_periods):
                col = 1 + i * 2
                period_item = QTableWidgetItem(period_name)
                period_item.setFlags(Qt.ItemIsEnabled)
                period_item.setTextAlignment(Qt.AlignCenter)
                font = period_item.font()
                font.setBold(True)
                period_item.setFont(font)
                self.setItem(row, col, period_item)
                # Span 2 columns (Port + Bmrk)
                self.setSpan(row, col, 1, 2)
        else:
            # Period headers in single columns
            for i, (period_name, _) in enumerate(self._visible_periods):
                col = 1 + i
                period_item = QTableWidgetItem(period_name)
                period_item.setFlags(Qt.ItemIsEnabled)
                period_item.setTextAlignment(Qt.AlignCenter)
                font = period_item.font()
                font.setBold(True)
                period_item.setFont(font)
                self.setItem(row, col, period_item)

        row += 1

        # Row 1: Port/Bmrk sub-headers (only in benchmark mode)
        if self._has_benchmark:
            # Empty first cell
            empty_item = QTableWidgetItem("")
            empty_item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, 0, empty_item)

            for i in range(len(self._visible_periods)):
                port_col = 1 + i * 2
                bmrk_col = 2 + i * 2

                port_item = QTableWidgetItem("Port")
                port_item.setFlags(Qt.ItemIsEnabled)
                port_item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, port_col, port_item)

                bmrk_item = QTableWidgetItem("Bmrk")
                bmrk_item.setFlags(Qt.ItemIsEnabled)
                bmrk_item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, bmrk_col, bmrk_item)

            row += 1

        # Get filtered metrics for current mode
        return_metrics = self._get_filtered_metrics(self.RETURN_METRICS)
        risk_metrics = self._get_filtered_metrics(self.RISK_METRICS)
        risk_return_metrics = self._get_filtered_metrics(self.RISK_RETURN_METRICS)

        # Return section
        row = self._add_section("Return", row)
        for label, key, has_bmrk, fmt in return_metrics:
            self._add_metric_row(label, row)
            row += 1

        # Risk section
        row = self._add_section("Risk", row)
        for label, key, has_bmrk, fmt in risk_metrics:
            self._add_metric_row(label, row)
            row += 1

        # Risk/Return section
        row = self._add_section("Risk/Return", row)
        for label, key, has_bmrk, fmt in risk_return_metrics:
            self._add_metric_row(label, row)
            row += 1

    def _add_section(self, section_name: str, row: int) -> int:
        """Add a section header row."""
        item = QTableWidgetItem(section_name)
        item.setFlags(Qt.ItemIsEnabled)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        self.setItem(row, 0, item)

        # Span all columns
        self.setSpan(row, 0, 1, self.columnCount())

        return row + 1

    def _add_metric_row(self, label: str, row: int):
        """Add a metric label row."""
        item = QTableWidgetItem(label)
        item.setFlags(Qt.ItemIsEnabled)
        self.setItem(row, 0, item)

    def update_metrics(self, metrics_by_period: Dict[str, Dict[str, Any]]):
        """
        Update table with calculated metrics.

        Args:
            metrics_by_period: Dict mapping period name to metrics dict
                              e.g., {"3 Months": {...}, "6 Months": {...}, ...}
        """
        self._metrics_by_period = metrics_by_period
        self._populate_values()

    def _populate_values(self):
        """Populate metric values into the table."""
        # Get filtered metrics for current mode
        return_metrics = self._get_filtered_metrics(self.RETURN_METRICS)
        risk_metrics = self._get_filtered_metrics(self.RISK_METRICS)
        risk_return_metrics = self._get_filtered_metrics(self.RISK_RETURN_METRICS)

        # Start row (after header rows)
        header_rows = 2 if self._has_benchmark else 1
        row = header_rows

        # Return section (skip section header)
        row += 1
        for label, key, has_bmrk, fmt in return_metrics:
            self._set_metric_values(row, key, has_bmrk, fmt)
            row += 1

        # Risk section (skip section header)
        row += 1
        for label, key, has_bmrk, fmt in risk_metrics:
            self._set_metric_values(row, key, has_bmrk, fmt)
            row += 1

        # Risk/Return section (skip section header)
        row += 1
        for label, key, has_bmrk, fmt in risk_return_metrics:
            self._set_metric_values(row, key, has_bmrk, fmt)
            row += 1

        # Apply theme colors to values
        self._apply_value_colors()

    def _set_metric_values(
        self, row: int, key: str, has_bmrk: bool, fmt: str
    ):
        """Set metric values for all visible time periods."""
        for i, (period_name, _) in enumerate(self._visible_periods):
            metrics = self._metrics_by_period.get(period_name, {})

            if self._has_benchmark:
                port_col = 1 + i * 2
                bmrk_col = 2 + i * 2

                # Portfolio value
                value = metrics.get(key)
                formatted = self._format_value(value, fmt)
                port_item = QTableWidgetItem(formatted)
                port_item.setFlags(Qt.ItemIsEnabled)
                port_item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, port_col, port_item)

                # Benchmark value (if this metric has benchmark equivalent)
                if has_bmrk:
                    bmrk_key = f"bmrk_{key}"
                    bmrk_value = metrics.get(bmrk_key)
                    bmrk_formatted = self._format_value(bmrk_value, fmt)
                else:
                    bmrk_formatted = ""  # No benchmark value for this metric

                bmrk_item = QTableWidgetItem(bmrk_formatted)
                bmrk_item.setFlags(Qt.ItemIsEnabled)
                bmrk_item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, bmrk_col, bmrk_item)
            else:
                # No benchmark mode - single value column per period
                # (benchmark-only metrics are hidden, so no special handling needed)
                col = 1 + i
                value = metrics.get(key)
                formatted = self._format_value(value, fmt)

                item = QTableWidgetItem(formatted)
                item.setFlags(Qt.ItemIsEnabled)
                item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row, col, item)

    def _format_value(self, value: Any, fmt: str) -> str:
        """Format a metric value for display."""
        import numpy as np

        # Return blank for None (missing data)
        if value is None:
            return ""

        # Handle tuple for capture ratio
        if fmt == "capture" and isinstance(value, tuple):
            up, down = value
            if (isinstance(up, float) and np.isnan(up)) or (
                isinstance(down, float) and np.isnan(down)
            ):
                return ""
            # Display as up/down ratio
            if down == 0:
                return "--"  # Division by zero
            ratio = up / down
            return f"{ratio:.2f}"

        # Handle NaN (missing data) - show blank
        if isinstance(value, float) and np.isnan(value):
            return ""

        # Handle actual zero - show "--"
        if value == 0:
            return "--"

        if fmt == "percent":
            return f"{value * 100:.2f}"
        elif fmt == "ratio":
            return f"{value:.2f}"
        elif fmt == "decimal":
            return f"{value:.2f}"
        elif fmt == "decimal4":
            return f"{value:.4f}"

        return str(value)

    def _apply_value_colors(self):
        """Apply theme-appropriate colors to value cells."""
        theme = self.theme_manager.current_theme
        colors = self._get_theme_colors(theme)

        header_rows = 2 if self._has_benchmark else 1

        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    text = item.text()

                    # Row 0: Period headers
                    if row == 0:
                        item.setBackground(QBrush(QColor(colors["header_bg"])))
                        item.setForeground(QBrush(QColor(colors["header_text"])))
                    # Row 1: Port/Bmrk sub-headers (benchmark mode)
                    elif row == 1 and self._has_benchmark:
                        item.setBackground(QBrush(QColor(colors["header_bg"])))
                        item.setForeground(QBrush(QColor(colors["subheader_text"])))
                    # Section headers (Return, Risk, Risk/Return)
                    elif col == 0 and text in ["Return", "Risk", "Risk/Return"]:
                        item.setBackground(QBrush(QColor(colors["section_bg"])))
                        item.setForeground(QBrush(QColor(colors["section_text"])))
                    # Label column (metric names)
                    elif col == 0:
                        item.setForeground(QBrush(QColor(colors["label_text"])))
                    # Value cells
                    else:
                        item.setForeground(QBrush(QColor(colors["value_text"])))

    def _get_theme_colors(self, theme: str) -> Dict[str, str]:
        """Get theme-specific colors."""
        if theme == "bloomberg":
            return {
                "bg": "#000814",
                "section_bg": "#0a1018",
                "section_text": "#ffffff",  # White for section headers
                "header_bg": "#0d1420",
                "header_text": "#b0b0b0",
                "subheader_text": "#808080",
                "label_text": "#FF8000",
                "value_text": "#FF8000",
                "grid": "#1a2838",
            }
        elif theme == "light":
            return {
                "bg": "#ffffff",
                "section_bg": "#f0f0f0",
                "section_text": "#000000",  # Black for section headers
                "header_bg": "#e8e8e8",
                "header_text": "#333333",
                "subheader_text": "#666666",
                "label_text": "#000000",
                "value_text": "#0066cc",
                "grid": "#cccccc",
            }
        else:  # dark
            return {
                "bg": "#1e1e1e",
                "section_bg": "#252525",
                "section_text": "#ffffff",  # White for section headers
                "header_bg": "#2d2d2d",
                "header_text": "#cccccc",
                "subheader_text": "#999999",
                "label_text": "#ffffff",
                "value_text": "#00d4ff",
                "grid": "#3d3d3d",
            }

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme
        colors = self._get_theme_colors(theme)

        stylesheet = f"""
            QTableWidget {{
                background-color: {colors['bg']};
                gridline-color: {colors['grid']};
                border: 1px solid {colors['grid']};
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
        """

        self.setStyleSheet(stylesheet)

        # Always apply value colors (for both empty table and with data)
        self._apply_value_colors()

    def show_placeholder(self, message: str):
        """Show a placeholder message when no data is available."""
        self.clear()
        self.clearSpans()
        self.setRowCount(1)
        self.setColumnCount(1)

        item = QTableWidgetItem(message)
        item.setFlags(Qt.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignCenter)
        self.setItem(0, 0, item)

        theme = self.theme_manager.current_theme
        colors = self._get_theme_colors(theme)
        item.setForeground(QBrush(QColor(colors["label_text"])))
