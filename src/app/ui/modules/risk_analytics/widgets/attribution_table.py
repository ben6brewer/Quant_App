"""Attribution Table Widget - Displays Brinson-Fachler attribution results."""

from typing import Dict, List, Optional, Set, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from .smooth_scroll_widgets import SmoothScrollTableWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

if TYPE_CHECKING:
    from ..services.brinson_attribution_service import BrinsonAnalysis, AttributionResult


class AttributionTable(LazyThemeMixin, QWidget):
    """
    Collapsible attribution table with sector groupings.

    Displays Brinson-Fachler attribution results grouped by sector
    with clickable headers to expand/collapse groups.

    Columns:
    - Name: Company name or sector name
    - Ticker: Ticker symbol
    - Port Wt (%): Portfolio weight
    - Bench Wt (%): Benchmark weight
    - Port Ret (%): Portfolio return
    - Bench Ret (%): Benchmark return
    - Allocation: Allocation effect
    - Selection: Selection effect
    - Interaction: Interaction effect
    - Total: Total effect
    """

    COLUMNS = [
        "Name",
        "Ticker",
        "Port Wt",
        "Bench Wt",
        "Port Ret",
        "Bench Ret",
        "Allocation",
        "Selection",
        "Interaction",
        "Total",
    ]
    COL_WIDTHS = [180, 70, 70, 70, 70, 70, 80, 80, 80, 80]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._collapsed_sectors: Set[str] = set()
        self._analysis: Optional["BrinsonAnalysis"] = None
        self._sector_rows: Dict[str, int] = {}

        self._setup_ui()
        self._apply_theme()

        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup table UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title
        self.title_label = QLabel("Performance Attribution")
        self.title_label.setObjectName("section_title")
        layout.addWidget(self.title_label)

        # Table
        self.table = SmoothScrollTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)

        # Hide scrollbars but keep scroll functionality
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Column sizing
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for i, width in enumerate(self.COL_WIDTHS):
            self.table.setColumnWidth(i, width)
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name column stretches

        # Connect click handler for collapsible headers
        self.table.cellClicked.connect(self._on_cell_clicked)

        layout.addWidget(self.table, stretch=1)

    def set_data(self, analysis: "BrinsonAnalysis"):
        """
        Set attribution analysis data and rebuild table.

        Args:
            analysis: BrinsonAnalysis with attribution results
        """
        self._analysis = analysis
        self._rebuild_table()

    def _rebuild_table(self):
        """Rebuild the table with current data and collapse states."""
        self.table.setRowCount(0)
        self._sector_rows.clear()

        if not self._analysis:
            return

        # Add totals row first
        self._add_totals_row()

        # Group by sector
        sector_groups: Dict[str, List["AttributionResult"]] = {}
        for ticker, result in self._analysis.by_security.items():
            sector = result.sector
            if sector not in sector_groups:
                sector_groups[sector] = []
            sector_groups[sector].append(result)

        # Sort sectors by total effect descending
        sector_totals = {
            sector: sum(r.total_effect for r in results)
            for sector, results in sector_groups.items()
        }
        sorted_sectors = sorted(
            sector_groups.keys(),
            key=lambda s: abs(sector_totals.get(s, 0)),
            reverse=True,
        )

        # Build table rows
        for sector in sorted_sectors:
            securities = sector_groups[sector]
            # Sort securities by total effect descending
            securities.sort(key=lambda x: abs(x.total_effect), reverse=True)

            is_collapsed = sector in self._collapsed_sectors

            # Add sector header row
            sector_result = self._analysis.by_sector.get(sector)
            header_row = self._add_sector_header(sector, sector_result, is_collapsed)
            self._sector_rows[sector] = header_row

            # Add security rows if not collapsed
            if not is_collapsed:
                for result in securities:
                    self._add_security_row(result)

        self.table.resizeRowsToContents()

    def _add_totals_row(self):
        """Add the totals summary row at the top."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        analysis = self._analysis

        # Name column
        name_item = QTableWidgetItem("TOTAL")
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        font = QFont()
        font.setBold(True)
        name_item.setFont(font)
        self.table.setItem(row, 0, name_item)

        # Empty ticker
        self.table.setItem(row, 1, self._create_item(""))

        # Portfolio weight (100%)
        self.table.setItem(row, 2, self._create_item("100.00", bold=True))

        # Benchmark weight (100%)
        self.table.setItem(row, 3, self._create_item("100.00", bold=True))

        # Portfolio return
        port_ret = analysis.total_portfolio_return * 100
        self.table.setItem(row, 4, self._create_item(f"{port_ret:.2f}", bold=True))

        # Benchmark return
        bench_ret = analysis.total_benchmark_return * 100
        self.table.setItem(row, 5, self._create_item(f"{bench_ret:.2f}", bold=True))

        # Allocation effect
        alloc = analysis.total_allocation_effect * 100
        self.table.setItem(row, 6, self._create_item(f"{alloc:.2f}", bold=True))

        # Selection effect
        sel = analysis.total_selection_effect * 100
        self.table.setItem(row, 7, self._create_item(f"{sel:.2f}", bold=True))

        # Interaction effect
        inter = analysis.total_interaction_effect * 100
        self.table.setItem(row, 8, self._create_item(f"{inter:.2f}", bold=True))

        # Total effect (excess return)
        total = analysis.total_excess_return * 100
        self.table.setItem(row, 9, self._create_item(f"{total:.2f}", bold=True))

        self._style_totals_row(row)

    def _add_sector_header(
        self,
        sector: str,
        sector_result: Optional["AttributionResult"],
        is_collapsed: bool,
    ) -> int:
        """Add a sector header row."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Collapse indicator
        arrow = ">" if is_collapsed else "v"

        if sector_result:
            count = sector_result.name.split("(")[-1].rstrip(") holdings") if "(" in sector_result.name else "?"
        else:
            count = "0"

        header_text = f"{arrow} {sector} ({count} holdings)"

        # Name column
        header_item = QTableWidgetItem(header_text)
        header_item.setFlags(header_item.flags() & ~Qt.ItemIsEditable)
        header_item.setData(Qt.UserRole, "sector_header")
        header_item.setData(Qt.UserRole + 1, sector)
        font = QFont()
        font.setBold(True)
        header_item.setFont(font)
        self.table.setItem(row, 0, header_item)

        # Fill other columns
        if sector_result:
            # Empty ticker for sector
            self._set_header_item(row, 1, "", sector)

            # Portfolio weight
            self._set_header_item(
                row, 2, f"{sector_result.portfolio_weight * 100:.2f}", sector
            )

            # Benchmark weight
            self._set_header_item(
                row, 3, f"{sector_result.benchmark_weight * 100:.2f}", sector
            )

            # Portfolio return
            self._set_header_item(
                row, 4, f"{sector_result.portfolio_return * 100:.2f}", sector
            )

            # Benchmark return
            self._set_header_item(
                row, 5, f"{sector_result.benchmark_return * 100:.2f}", sector
            )

            # Allocation effect
            self._set_header_item(
                row, 6, f"{sector_result.allocation_effect * 100:.2f}", sector
            )

            # Selection effect
            self._set_header_item(
                row, 7, f"{sector_result.selection_effect * 100:.2f}", sector
            )

            # Interaction effect
            self._set_header_item(
                row, 8, f"{sector_result.interaction_effect * 100:.2f}", sector
            )

            # Total effect
            self._set_header_item(
                row, 9, f"{sector_result.total_effect * 100:.2f}", sector
            )
        else:
            for col in range(1, 10):
                self._set_header_item(row, col, "", sector)

        self._style_header_row(row)
        return row

    def _set_header_item(self, row: int, col: int, text: str, sector: str):
        """Set a header row item with proper styling."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if col >= 2:  # Numeric columns
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item.setData(Qt.UserRole, "sector_header")
        item.setData(Qt.UserRole + 1, sector)
        font = QFont()
        font.setBold(True)
        item.setFont(font)
        self.table.setItem(row, col, item)

    def _add_security_row(self, result: "AttributionResult"):
        """Add a security data row."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Name column (indented)
        name_item = QTableWidgetItem(f"    {result.name[:30]}")
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, name_item)

        # Ticker
        self.table.setItem(row, 1, self._create_item(result.ticker))

        # Portfolio weight
        self.table.setItem(
            row, 2, self._create_item(f"{result.portfolio_weight * 100:.2f}")
        )

        # Benchmark weight
        self.table.setItem(
            row, 3, self._create_item(f"{result.benchmark_weight * 100:.2f}")
        )

        # Portfolio return
        self.table.setItem(
            row, 4, self._create_item(f"{result.portfolio_return * 100:.2f}")
        )

        # Benchmark return
        self.table.setItem(
            row, 5, self._create_item(f"{result.benchmark_return * 100:.2f}")
        )

        # Allocation effect
        self.table.setItem(
            row, 6, self._create_item(f"{result.allocation_effect * 100:.2f}")
        )

        # Selection effect
        self.table.setItem(
            row, 7, self._create_item(f"{result.selection_effect * 100:.2f}")
        )

        # Interaction effect
        self.table.setItem(
            row, 8, self._create_item(f"{result.interaction_effect * 100:.2f}")
        )

        # Total effect
        self.table.setItem(
            row, 9, self._create_item(f"{result.total_effect * 100:.2f}")
        )

        self._style_data_row(row)

    def _create_item(self, text: str, bold: bool = False) -> QTableWidgetItem:
        """Create a table item."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if bold:
            font = QFont()
            font.setBold(True)
            item.setFont(font)
        return item

    def _on_cell_clicked(self, row: int, col: int):
        """Handle cell click - toggle sector collapse if header clicked."""
        item = self.table.item(row, 0)
        if item and item.data(Qt.UserRole) == "sector_header":
            sector = item.data(Qt.UserRole + 1)
            self._toggle_sector(sector)

    def _toggle_sector(self, sector: str):
        """Toggle collapsed state for a sector."""
        if sector in self._collapsed_sectors:
            self._collapsed_sectors.remove(sector)
        else:
            self._collapsed_sectors.add(sector)
        self._rebuild_table()

    def _style_totals_row(self, row: int):
        """Apply styling to the totals row."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = QColor("#d0d0ff")
            fg_color = QColor("#000000")
        elif theme == "bloomberg":
            bg_color = QColor("#1a2838")
            fg_color = QColor("#00ff00")
        else:  # dark
            bg_color = QColor("#2a3a4a")
            fg_color = QColor("#00ff00")

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(fg_color)

    def _style_header_row(self, row: int):
        """Apply styling to a sector header row."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = QColor("#e0e0e0")
            fg_color = QColor("#000000")
        elif theme == "bloomberg":
            bg_color = QColor("#1a2838")
            fg_color = QColor("#FF8000")
        else:  # dark
            bg_color = QColor("#3d3d3d")
            fg_color = QColor("#00d4ff")

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(fg_color)

    def _style_data_row(self, row: int):
        """Apply styling to a data row."""
        theme = self.theme_manager.current_theme

        # Alternate row colors
        if row % 2 == 0:
            if theme == "light":
                bg_color = QColor("#ffffff")
            elif theme == "bloomberg":
                bg_color = QColor("#0d1420")
            else:
                bg_color = QColor("#2d2d2d")
        else:
            if theme == "light":
                bg_color = QColor("#f5f5f5")
            elif theme == "bloomberg":
                bg_color = QColor("#0a1018")
            else:
                bg_color = QColor("#252525")

        if theme == "light":
            fg_color = QColor("#000000")
        else:
            fg_color = QColor("#e8e8e8")

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(fg_color)

    def clear_data(self):
        """Clear all table data."""
        self._analysis = None
        self._sector_rows.clear()
        self.table.setRowCount(0)

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

        # Re-apply row styling if data exists
        if self._analysis:
            self._rebuild_table()

    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QLabel#section_title {
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px 0;
            }
            QTableWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #a0a0a0;
                border: none;
                border-bottom: 1px solid #3d3d3d;
                border-right: 1px solid #3d3d3d;
                padding: 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QHeaderView::section:last {
                border-right: none;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QLabel#section_title {
                color: #000000;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px 0;
            }
            QTableWidget {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 4px;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #666666;
                border: none;
                border-bottom: 1px solid #cccccc;
                border-right: 1px solid #cccccc;
                padding: 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QHeaderView::section:last {
                border-right: none;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QLabel#section_title {
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                padding: 4px 0;
            }
            QTableWidget {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 4px;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px 8px;
            }
            QHeaderView::section {
                background-color: #000814;
                color: #808080;
                border: none;
                border-bottom: 1px solid #1a2838;
                border-right: 1px solid #1a2838;
                padding: 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QHeaderView::section:last {
                border-right: none;
            }
        """
