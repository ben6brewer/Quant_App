"""Risk Summary Panel Widget - Mixed layout with large metric, table, and text."""

from typing import Dict, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class BarDelegate(QStyledItemDelegate):
    """Custom delegate to draw horizontal bars in table cells."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bar_color = QColor("#00d4ff")
        self._max_value = 100.0

    def set_bar_color(self, color: str):
        """Set the bar color."""
        self._bar_color = QColor(color)

    def set_max_value(self, max_val: float):
        """Set the maximum value for scaling bars."""
        self._max_value = max(max_val, 0.01)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint the bar in the cell."""
        value = index.data(Qt.UserRole)
        if value is None or value == 0:
            return

        painter.save()

        cell_rect = option.rect
        bar_width = int((value / self._max_value) * (cell_rect.width() - 4))
        bar_width = max(bar_width, 0)

        bar_rect = QRect(
            cell_rect.left() + 2,
            cell_rect.top() + 4,
            bar_width,
            cell_rect.height() - 8
        )

        painter.fillRect(bar_rect, self._bar_color)
        painter.restore()


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
        self._bar_delegate = BarDelegate(self)
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

        # Total Active Risk section (large display)
        risk_container = QWidget()
        risk_container.setObjectName("risk_container")
        risk_layout = QVBoxLayout(risk_container)
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

        layout.addWidget(risk_container)

        # Factor/Idiosyncratic table (2 rows with bars)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["", "", ""])
        self.table.horizontalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(26)

        # Hide scrollbars but keep scroll functionality
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Column sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 75)  # Label column
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 55)  # Value column
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Bar column

        self.table.setItemDelegateForColumn(2, self._bar_delegate)
        self.table.setRowCount(2)
        self._init_table_rows()
        self.table.setFixedHeight(56)  # 2 rows * 26px + small margin

        layout.addWidget(self.table)

        # Stretch to push betas to bottom
        layout.addStretch()

        # Beta values section (text labels) - at the very bottom
        beta_container = QWidget()
        beta_container.setObjectName("beta_container")
        beta_layout = QVBoxLayout(beta_container)
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

        layout.addWidget(beta_container)

    def _init_table_rows(self):
        """Initialize the Factor/Idiosyncratic table rows."""
        rows = ["Factor", "Idiosyncratic"]

        for row, label in enumerate(rows):
            # Label column
            label_item = QTableWidgetItem(label)
            label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, label_item)

            # Value column
            value_item = QTableWidgetItem("--")
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, value_item)

            # Bar column
            bar_item = QTableWidgetItem()
            bar_item.setFlags(bar_item.flags() & ~Qt.ItemIsEditable)
            bar_item.setData(Qt.UserRole, 0)
            self.table.setItem(row, 2, bar_item)

    def set_bar_color(self, color: str):
        """Set the bar color for the visualization."""
        self._bar_delegate.set_bar_color(color)

    def update_metrics(self, metrics: Optional[Dict[str, float]]):
        """Update displayed metric values."""
        if metrics is None:
            self.risk_value_label.setText("--")
            self.table.item(0, 1).setText("--")
            self.table.item(0, 2).setData(Qt.UserRole, 0)
            self.table.item(1, 1).setText("--")
            self.table.item(1, 2).setData(Qt.UserRole, 0)
            self.beta_ante_value.setText("--")
            self.beta_post_value.setText("--")
            return

        # Total Active Risk (large display)
        total_risk = metrics.get("total_active_risk", 0)
        self.risk_value_label.setText(f"{total_risk:.2f}%")

        # Factor risk (table row 0)
        factor_risk = metrics.get("factor_risk_pct", 0)
        self.table.item(0, 1).setText(f"{factor_risk:.1f}%")
        self.table.item(0, 2).setData(Qt.UserRole, factor_risk)

        # Idiosyncratic risk (table row 1)
        idio_risk = metrics.get("idio_risk_pct", 0)
        self.table.item(1, 1).setText(f"{idio_risk:.1f}%")
        self.table.item(1, 2).setData(Qt.UserRole, idio_risk)

        self._bar_delegate.set_max_value(100.0)

        # Beta values (text labels)
        beta_ante = metrics.get("ex_ante_beta", 1.0)
        self.beta_ante_value.setText(f"{beta_ante:.2f}")

        beta_post = metrics.get("ex_post_beta", 1.0)
        self.beta_post_value.setText(f"{beta_post:.2f}")

        self.table.viewport().update()

    def clear_metrics(self):
        """Clear all displayed values to placeholder."""
        self.update_metrics(None)

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
                color: #00d4ff;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
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
                padding: 4px 6px;
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
                color: #0066cc;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
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
                padding: 4px 6px;
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
                color: #FF8000;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
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
                padding: 4px 6px;
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
