"""Risk Summary Panel Widget - Mixed layout with large metric, table, and text."""

from typing import Dict, Optional

from collections import OrderedDict

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QFrame,
)
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from .risk_decomposition_panel import CTEVTable


class RiskSummaryPanel(LazyThemeMixin, QFrame):
    """
    Summary panel with mixed layout:
    - Large Total Active Risk display
    - Small table for Factor/Idiosyncratic with bars
    - Text labels for Beta values
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self.setObjectName("risk_summary_panel")
        self._setup_ui()
        self._apply_theme()

        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup panel UI with mixed layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Panel title
        self.title_label = QLabel("Risk Summary")
        self.title_label.setObjectName("panel_title")
        self.title_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.title_label)

        # Total Active Risk section (large display) - hidden until data loaded
        self.risk_container = QWidget()
        self.risk_container.setObjectName("risk_container")
        risk_layout = QVBoxLayout(self.risk_container)
        risk_layout.setContentsMargins(0, 4, 0, 4)
        risk_layout.setSpacing(2)

        self.risk_title_label = QLabel("Total Active Risk")
        self.risk_title_label.setObjectName("risk_title")
        self.risk_title_label.setAlignment(Qt.AlignCenter)
        risk_layout.addWidget(self.risk_title_label)

        self.risk_value_label = QLabel("--")
        self.risk_value_label.setObjectName("risk_value")
        self.risk_value_label.setAlignment(Qt.AlignCenter)
        risk_layout.addWidget(self.risk_value_label)

        self.risk_container.hide()  # Hidden until data loaded
        layout.addWidget(self.risk_container)

        # Factor/Idiosyncratic table (using CTEVTable for consistent row heights)
        self.table = CTEVTable("", ["Label", "Value"])

        # Customize column widths for Risk Summary layout
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 100)  # Label column (fits "Idiosyncratic")
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 55)  # Value column
        # Column 2 (bar) remains stretch from CTEVTable defaults

        layout.addWidget(self.table)

        # Stretch to push betas to bottom
        layout.addStretch()

        # Beta values section (text labels) - hidden until data loaded
        self.beta_container = QWidget()
        self.beta_container.setObjectName("beta_container")
        beta_layout = QVBoxLayout(self.beta_container)
        beta_layout.setContentsMargins(0, 0, 0, 0)
        beta_layout.setSpacing(2)

        # Ex-Ante Beta row
        ante_row = QHBoxLayout()
        ante_row.setSpacing(4)
        ante_label = QLabel("Beta (Ex-Ante):")
        ante_label.setObjectName("beta_label")
        ante_row.addWidget(ante_label)
        self.beta_ante_value = QLabel("--")
        self.beta_ante_value.setObjectName("beta_value")
        self.beta_ante_value.setAlignment(Qt.AlignRight)
        ante_row.addWidget(self.beta_ante_value)
        beta_layout.addLayout(ante_row)

        # Ex-Post Beta row
        post_row = QHBoxLayout()
        post_row.setSpacing(4)
        post_label = QLabel("Beta (Ex-Post):")
        post_label.setObjectName("beta_label")
        post_row.addWidget(post_label)
        self.beta_post_value = QLabel("--")
        self.beta_post_value.setObjectName("beta_value")
        self.beta_post_value.setAlignment(Qt.AlignRight)
        post_row.addWidget(self.beta_post_value)
        beta_layout.addLayout(post_row)

        self.beta_container.hide()  # Hidden until data loaded
        layout.addWidget(self.beta_container)

    def set_bar_color(self, color: str):
        """Set the bar color for the visualization."""
        self.table.set_bar_color(color)

    def update_metrics(self, metrics: Optional[Dict[str, float]]):
        """Update displayed metric values."""
        if metrics is None:
            self.clear_metrics()
            return

        # Show containers
        self.risk_container.show()
        self.beta_container.show()

        # Total Active Risk (large display)
        total_risk = metrics.get("total_active_risk", 0)
        self.risk_value_label.setText(f"{total_risk:.2f}%")

        # Populate table with Factor and Idiosyncratic rows
        factor_risk = metrics.get("factor_risk_pct", 0)
        idio_risk = metrics.get("idio_risk_pct", 0)

        # Use OrderedDict to preserve row order
        data = OrderedDict([
            ("Factor", factor_risk),
            ("Idiosyncratic", idio_risk),
        ])

        # CTEVTable.set_data() handles row creation, bar scaling, and resizeRowsToContents()
        self.table.set_data(data)

        # Force row heights to 37px to match decomposition panels
        # (resizeRowsToContents() calculates 31px here due to stylesheet differences)
        for i in range(self.table.rowCount()):
            self.table.setRowHeight(i, 37)

        # Beta values (text labels)
        beta_ante = metrics.get("ex_ante_beta", 1.0)
        self.beta_ante_value.setText(f"{beta_ante:.2f}")

        beta_post = metrics.get("ex_post_beta", 1.0)
        self.beta_post_value.setText(f"{beta_post:.2f}")

    def clear_metrics(self):
        """Clear all displayed values and hide data containers."""
        self.risk_container.hide()
        self.beta_container.hide()
        self.table.clear_data()

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
            bar_color = "#0066cc"
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
            bar_color = "#FF8000"
        else:
            stylesheet = self._get_dark_stylesheet()
            bar_color = "#00d4ff"

        self.setStyleSheet(stylesheet)
        self.set_bar_color(bar_color)

    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet."""
        return """
            QFrame#risk_summary_panel {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
            QLabel#panel_title {
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px;
            }
            QWidget#risk_container {
                background: transparent;
            }
            QLabel#risk_title {
                color: #a0a0a0;
                font-size: 13px;
                background: transparent;
            }
            QLabel#risk_value {
                color: #00d4ff;
                font-size: 28px;
                font-weight: bold;
                background: transparent;
            }
            QTableWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: none;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #3d3d3d;
            }
            QTableWidget::item:alternate {
                background-color: #252525;
            }
            QWidget#beta_container {
                background: transparent;
            }
            QLabel#beta_label {
                color: #a0a0a0;
                font-size: 13px;
                background: transparent;
            }
            QLabel#beta_value {
                color: #00d4ff;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QFrame#risk_summary_panel {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 6px;
            }
            QLabel#panel_title {
                color: #000000;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px;
            }
            QWidget#risk_container {
                background: transparent;
            }
            QLabel#risk_title {
                color: #666666;
                font-size: 13px;
                background: transparent;
            }
            QLabel#risk_value {
                color: #0066cc;
                font-size: 28px;
                font-weight: bold;
                background: transparent;
            }
            QTableWidget {
                background-color: #f5f5f5;
                color: #000000;
                border: none;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #e0e0e0;
            }
            QTableWidget::item:alternate {
                background-color: #e8e8e8;
            }
            QWidget#beta_container {
                background: transparent;
            }
            QLabel#beta_label {
                color: #666666;
                font-size: 13px;
                background: transparent;
            }
            QLabel#beta_value {
                color: #0066cc;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QFrame#risk_summary_panel {
                background-color: #0d1420;
                border: 1px solid #1a2838;
                border-radius: 6px;
            }
            QLabel#panel_title {
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px;
            }
            QWidget#risk_container {
                background: transparent;
            }
            QLabel#risk_title {
                color: #808080;
                font-size: 13px;
                background: transparent;
            }
            QLabel#risk_value {
                color: #FF8000;
                font-size: 28px;
                font-weight: bold;
                background: transparent;
            }
            QTableWidget {
                background-color: #0d1420;
                color: #e8e8e8;
                border: none;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #1a2838;
            }
            QTableWidget::item:alternate {
                background-color: #0a1018;
            }
            QWidget#beta_container {
                background: transparent;
            }
            QLabel#beta_label {
                color: #808080;
                font-size: 13px;
                background: transparent;
            }
            QLabel#beta_value {
                color: #FF8000;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """
