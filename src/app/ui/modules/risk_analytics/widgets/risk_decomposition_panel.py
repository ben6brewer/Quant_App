"""Risk Decomposition Panel Widget - 3-column CTEV breakdown display with bar charts."""

from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
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
        self._bar_color = QColor("#00d4ff")  # Default cyan
        self._max_value = 1.0

    def set_bar_color(self, color: str):
        """Set the bar color."""
        self._bar_color = QColor(color)

    def set_max_value(self, max_val: float):
        """Set the maximum value for scaling bars."""
        self._max_value = max(max_val, 0.01)  # Avoid division by zero

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Paint the bar in the cell."""
        # Get the value from the model
        value = index.data(Qt.UserRole)
        if value is None:
            return

        painter.save()

        # Calculate bar width as proportion of cell width
        cell_rect = option.rect
        bar_width = int((value / self._max_value) * (cell_rect.width() - 4))
        bar_width = max(bar_width, 0)

        # Draw the bar
        bar_rect = QRect(
            cell_rect.left() + 2,
            cell_rect.top() + 4,
            bar_width,
            cell_rect.height() - 8
        )

        painter.fillRect(bar_rect, self._bar_color)
        painter.restore()


class CTEVTable(QTableWidget):
    """Table widget for displaying CTEV breakdown with bar visualization."""

    def __init__(self, title: str, columns: List[str], parent=None):
        super().__init__(parent)
        self._title = title
        self._columns = columns + [""]  # Add empty column for bar
        self._bar_delegate = BarDelegate(self)
        self._setup_table()

    def _setup_table(self):
        """Setup table configuration."""
        self.setColumnCount(len(self._columns))
        self.setHorizontalHeaderLabels(self._columns)
        self.horizontalHeader().setVisible(False)  # Hide column headers
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)

        # Hide scrollbars but keep scroll functionality
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Set default row height for consistency
        self.verticalHeader().setDefaultSectionSize(28)

        # Column sizing
        header = self.horizontalHeader()
        # Name column stretches
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        # Value column fixed width
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(1, 45)  # Slightly narrower for CTEV values
        # Bar column stretches
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        # Set delegate for bar column
        self.setItemDelegateForColumn(2, self._bar_delegate)

    def set_bar_color(self, color: str):
        """Set the bar color for the visualization."""
        self._bar_delegate.set_bar_color(color)

    def set_data(self, data: Dict[str, float]):
        """
        Set table data from dict.

        Args:
            data: Dict mapping name to value
        """
        self.setRowCount(len(data))

        # Find max value for scaling
        max_value = max(data.values()) if data else 1.0
        self._bar_delegate.set_max_value(max_value)

        for row, (name, value) in enumerate(data.items()):
            # Name column
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.setItem(row, 0, name_item)

            # Value column
            if isinstance(value, (int, float)):
                value_str = f"{value:.2f}"
            else:
                value_str = str(value)
            value_item = QTableWidgetItem(value_str)
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 1, value_item)

            # Bar column - store value for delegate to use
            bar_item = QTableWidgetItem()
            bar_item.setFlags(bar_item.flags() & ~Qt.ItemIsEditable)
            bar_item.setData(Qt.UserRole, value if isinstance(value, (int, float)) else 0)
            self.setItem(row, 2, bar_item)

        self.resizeRowsToContents()

    def clear_data(self):
        """Clear all table data."""
        self.setRowCount(0)


class CTEVPanel(QFrame):
    """Panel containing a title and CTEV table."""

    def __init__(self, title: str, columns: List[str], parent=None):
        super().__init__(parent)
        self._title = title
        self._columns = columns
        self._setup_ui()
        self.setObjectName("ctev_panel")

    def _setup_ui(self):
        """Setup panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title
        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("panel_title")
        self.title_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.title_label)

        # Table
        self.table = CTEVTable(self._title, self._columns)
        layout.addWidget(self.table, stretch=1)

    def set_bar_color(self, color: str):
        """Set the bar color for the table."""
        self.table.set_bar_color(color)

    def set_data(self, data: Dict[str, float]):
        """Set table data."""
        self.table.set_data(data)

    def clear_data(self):
        """Clear table data."""
        self.table.clear_data()


class RiskDecompositionPanel(LazyThemeMixin, QWidget):
    """
    Risk decomposition panel showing 3 CTEV breakdowns.

    Displays: CTEV by Factor Group, CTEV by Sector, Top CTEV Securities
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self._setup_ui()
        self._apply_theme()

        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup panel with 3 columns."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # CTEV by Factor Group
        self.factor_panel = CTEVPanel(
            "Top CTEV by Factor Group",
            ["Factor", "CTEV"]
        )
        layout.addWidget(self.factor_panel, stretch=1)

        # CTEV by Sector
        self.sector_panel = CTEVPanel(
            "Top CTEV by Classification",
            ["Sector", "CTEV"]
        )
        layout.addWidget(self.sector_panel, stretch=1)

        # Top CTEV by Security
        self.security_panel = CTEVPanel(
            "Top CTEV by Security",
            ["Ticker", "CTEV"]
        )
        layout.addWidget(self.security_panel, stretch=1)

    def update_factor_ctev(self, data: Optional[Dict[str, float]]):
        """Update CTEV by factor group."""
        if data:
            self.factor_panel.set_data(data)
        else:
            self.factor_panel.clear_data()

    def update_sector_ctev(self, data: Optional[Dict[str, float]]):
        """Update CTEV by sector."""
        if data:
            # Limit to top 10
            sorted_data = dict(
                sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
            )
            self.sector_panel.set_data(sorted_data)
        else:
            self.sector_panel.clear_data()

    def update_security_ctev(self, data: Optional[Dict[str, Dict[str, float]]]):
        """
        Update CTEV by security.

        Args:
            data: Dict mapping ticker to metrics dict with 'idio_ctev' key
        """
        if data:
            # Extract just the CTEV values and limit to top 10
            ctev_data = {
                ticker: metrics.get("idio_ctev", 0)
                for ticker, metrics in data.items()
            }
            sorted_data = dict(
                sorted(ctev_data.items(), key=lambda x: x[1], reverse=True)[:10]
            )
            self.security_panel.set_data(sorted_data)
        else:
            self.security_panel.clear_data()

    def clear_all(self):
        """Clear all panels."""
        self.factor_panel.clear_data()
        self.sector_panel.clear_data()
        self.security_panel.clear_data()

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

        # Update bar colors for all panels
        self.factor_panel.set_bar_color(bar_color)
        self.sector_panel.set_bar_color(bar_color)
        self.security_panel.set_bar_color(bar_color)

    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QFrame#ctev_panel {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 10px;
            }
            QLabel#panel_title {
                color: #00d4ff;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px;
            }
            QTableWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: none;
                gridline-color: #3d3d3d;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #3d3d3d;
            }
            QTableWidget::item:alternate {
                background-color: #252525;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #a0a0a0;
                border: none;
                border-bottom: 1px solid #3d3d3d;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QFrame#ctev_panel {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 10px;
            }
            QLabel#panel_title {
                color: #0066cc;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px;
            }
            QTableWidget {
                background-color: #f5f5f5;
                color: #000000;
                border: none;
                gridline-color: #cccccc;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #e0e0e0;
            }
            QTableWidget::item:alternate {
                background-color: #e8e8e8;
            }
            QHeaderView::section {
                background-color: #ffffff;
                color: #666666;
                border: none;
                border-bottom: 1px solid #cccccc;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QFrame#ctev_panel {
                background-color: #0d1420;
                border: 1px solid #1a2838;
                border-radius: 6px;
                padding: 10px;
            }
            QLabel#panel_title {
                color: #FF8000;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px;
            }
            QTableWidget {
                background-color: #0d1420;
                color: #e8e8e8;
                border: none;
                gridline-color: #1a2838;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #1a2838;
            }
            QTableWidget::item:alternate {
                background-color: #0a1018;
            }
            QHeaderView::section {
                background-color: #000814;
                color: #808080;
                border: none;
                border-bottom: 1px solid #1a2838;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """
