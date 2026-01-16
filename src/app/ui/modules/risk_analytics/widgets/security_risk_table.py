"""Security Risk Table Widget - Collapsible grouped table by sector."""

from typing import Dict, List, Optional, Set

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
)

from .smooth_scroll_widgets import SmoothScrollTableWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from ..services.sector_override_service import SectorOverrideService
from app.services.ticker_metadata_service import TickerMetadataService


class SecurityRiskTable(LazyThemeMixin, QWidget):
    """
    Collapsible security risk table with sector groupings.

    Displays security-level risk metrics grouped by sector with
    clickable headers to expand/collapse groups.

    Columns match Bloomberg PORT Risk screen:
    - Name: Security name
    - Ticker: Ticker symbol
    - Port Wt: Portfolio weight %
    - Bench Wt: Benchmark weight %
    - Active Wt: Active weight (Port - Bench)
    - Idio Vol: Idiosyncratic volatility
    - Idio TEV: Idiosyncratic tracking error variance
    - Idio CTEV: Idiosyncratic contribution to TEV
    """

    COLUMNS = ["Name", "Ticker", "Port Wt", "Bench Wt", "Active Wt", "Idio Vol", "Idio TEV", "Idio CTEV"]
    COL_WIDTHS = [200, 80, 70, 70, 70, 70, 70, 70]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._collapsed_sectors: Set[str] = set()
        self._security_data: Dict[str, Dict[str, float]] = {}
        self._benchmark_weights: Dict[str, float] = {}
        self._sector_rows: Dict[str, int] = {}  # Maps sector to header row index

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
        self.title_label = QLabel("Risk Analysis")
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
        self.table.setAlternatingRowColors(False)  # We handle row colors manually

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

    def set_data(
        self,
        security_risks: Dict[str, Dict[str, float]],
        benchmark_weights: Optional[Dict[str, float]] = None,
    ):
        """
        Set security risk data and rebuild table.

        Args:
            security_risks: Dict mapping ticker to risk metrics:
                {
                    "AAPL": {
                        "portfolio_weight": 5.2,
                        "benchmark_weight": 3.1,
                        "active_weight": 2.1,
                        "idio_vol": 25.5,
                        "idio_tev": 0.8,
                        "idio_ctev": 0.15,
                    },
                    ...
                }
            benchmark_weights: Optional dict mapping ticker to benchmark weight %
                (used as fallback if not included in security_risks)
        """
        self._security_data = security_risks
        self._benchmark_weights = benchmark_weights or {}
        self._rebuild_table()

    def _rebuild_table(self):
        """Rebuild the table with current data and collapse states."""
        self.table.setRowCount(0)
        self._sector_rows.clear()

        if not self._security_data:
            return

        # Group securities by sector and calculate sector aggregates
        sector_groups: Dict[str, List[tuple]] = {}
        sector_aggregates: Dict[str, Dict[str, float]] = {}

        for ticker, metrics in self._security_data.items():
            sector = SectorOverrideService.get_effective_sector(ticker)
            if sector not in sector_groups:
                sector_groups[sector] = []
                sector_aggregates[sector] = {
                    "portfolio_weight": 0.0,
                    "benchmark_weight": 0.0,
                    "active_weight": 0.0,
                    "idio_vol": None,  # Not additive - can't sum volatilities
                    "idio_tev": 0.0,
                    "idio_ctev": 0.0,
                }

            # Get display name from cache
            metadata = TickerMetadataService.get_metadata(ticker)
            name = metadata.get("shortName") or ticker

            sector_groups[sector].append((ticker, name, metrics))

            # Aggregate metrics for sector (only additive metrics)
            for key in ["portfolio_weight", "benchmark_weight", "active_weight", "idio_tev", "idio_ctev"]:
                sector_aggregates[sector][key] += metrics.get(key, 0.0)

        # Calculate grand totals (only additive metrics)
        grand_totals = {
            "portfolio_weight": 0.0,
            "benchmark_weight": 0.0,
            "active_weight": 0.0,
            "idio_vol": None,  # Not additive - can't sum volatilities
            "idio_tev": 0.0,
            "idio_ctev": 0.0,
        }
        for sector_agg in sector_aggregates.values():
            for key in ["portfolio_weight", "benchmark_weight", "active_weight", "idio_tev", "idio_ctev"]:
                grand_totals[key] += sector_agg[key]

        # Sort sectors by total CTEV descending
        sorted_sectors = sorted(
            sector_groups.keys(),
            key=lambda s: sector_aggregates[s]["idio_ctev"],
            reverse=True,
        )

        # Build table rows
        current_row = 0

        # Add Total row at the very top
        self._add_total_row(len(self._security_data), grand_totals)
        current_row += 1

        for sector in sorted_sectors:
            securities = sector_groups[sector]
            # Sort securities by CTEV descending (metrics is at index 2)
            securities.sort(key=lambda x: x[2].get("idio_ctev", 0), reverse=True)

            is_collapsed = sector in self._collapsed_sectors

            # Add sector header row with aggregated metrics
            header_row = self._add_sector_header(
                sector, len(securities), sector_aggregates[sector], is_collapsed
            )
            self._sector_rows[sector] = header_row
            current_row += 1

            # Add security rows if not collapsed
            if not is_collapsed:
                for ticker, name, metrics in securities:
                    self._add_security_row(ticker, name, metrics)
                    current_row += 1

        self.table.resizeRowsToContents()

    def _add_total_row(self, count: int, totals: Dict[str, float]) -> int:
        """
        Add the grand total row at the top of the table.

        Returns:
            Row index of the total row
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        # Column 0: Total label
        total_item = QTableWidgetItem(f"TOTAL ({count} securities)")
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        total_item.setFont(font)
        total_item.setData(Qt.UserRole, "total_header")
        self.table.setItem(row, 0, total_item)

        # Column 1: Empty (Ticker column)
        empty_item = QTableWidgetItem("")
        empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
        empty_item.setData(Qt.UserRole, "total_header")
        self.table.setItem(row, 1, empty_item)

        # Column 2: Portfolio Weight
        port_wt_item = QTableWidgetItem(f"{totals.get('portfolio_weight', 0):.2f}")
        port_wt_item.setFlags(port_wt_item.flags() & ~Qt.ItemIsEditable)
        port_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        port_wt_item.setFont(font)
        port_wt_item.setData(Qt.UserRole, "total_header")
        self.table.setItem(row, 2, port_wt_item)

        # Column 3: Benchmark Weight
        bench_wt_item = QTableWidgetItem(f"{totals.get('benchmark_weight', 0):.2f}")
        bench_wt_item.setFlags(bench_wt_item.flags() & ~Qt.ItemIsEditable)
        bench_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bench_wt_item.setFont(font)
        bench_wt_item.setData(Qt.UserRole, "total_header")
        self.table.setItem(row, 3, bench_wt_item)

        # Column 4: Active Weight
        active_wt_item = QTableWidgetItem(f"{totals.get('active_weight', 0):.2f}")
        active_wt_item.setFlags(active_wt_item.flags() & ~Qt.ItemIsEditable)
        active_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        active_wt_item.setFont(font)
        active_wt_item.setData(Qt.UserRole, "total_header")
        self.table.setItem(row, 4, active_wt_item)

        # Column 5: Idio Vol (not additive - show "--")
        idio_vol_item = QTableWidgetItem("--")
        idio_vol_item.setFlags(idio_vol_item.flags() & ~Qt.ItemIsEditable)
        idio_vol_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        idio_vol_item.setFont(font)
        idio_vol_item.setData(Qt.UserRole, "total_header")
        self.table.setItem(row, 5, idio_vol_item)

        # Column 6: Idio TEV (sum of individual Idio TEV contributions)
        idio_tev_item = QTableWidgetItem(f"{totals.get('idio_tev', 0):.2f}")
        idio_tev_item.setFlags(idio_tev_item.flags() & ~Qt.ItemIsEditable)
        idio_tev_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        idio_tev_item.setFont(font)
        idio_tev_item.setData(Qt.UserRole, "total_header")
        self.table.setItem(row, 6, idio_tev_item)

        # Column 7: Idio CTEV (sum of individual CTEV contributions)
        ctev_item = QTableWidgetItem(f"{totals.get('idio_ctev', 0):.2f}")
        ctev_item.setFlags(ctev_item.flags() & ~Qt.ItemIsEditable)
        ctev_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ctev_item.setFont(font)
        ctev_item.setData(Qt.UserRole, "total_header")
        self.table.setItem(row, 7, ctev_item)

        # Apply total row styling
        self._style_total_row(row)

        return row

    def _add_sector_header(
        self, sector: str, count: int, aggregates: Dict[str, float], is_collapsed: bool
    ) -> int:
        """
        Add a sector header row with aggregated metrics.

        Returns:
            Row index of the header
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        # Column 0: Sector name with collapse indicator
        arrow = "▶" if is_collapsed else "▼"
        header_text = f"{arrow} {sector} ({count})"
        header_item = QTableWidgetItem(header_text)
        header_item.setFlags(header_item.flags() & ~Qt.ItemIsEditable)
        header_item.setFont(font)
        header_item.setData(Qt.UserRole, "sector_header")
        header_item.setData(Qt.UserRole + 1, sector)
        self.table.setItem(row, 0, header_item)

        # Column 1: Empty (Ticker column)
        empty_item = QTableWidgetItem("")
        empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
        empty_item.setData(Qt.UserRole, "sector_header")
        empty_item.setData(Qt.UserRole + 1, sector)
        self.table.setItem(row, 1, empty_item)

        # Column 2: Portfolio Weight
        port_wt_item = QTableWidgetItem(f"{aggregates.get('portfolio_weight', 0):.2f}")
        port_wt_item.setFlags(port_wt_item.flags() & ~Qt.ItemIsEditable)
        port_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        port_wt_item.setFont(font)
        port_wt_item.setData(Qt.UserRole, "sector_header")
        port_wt_item.setData(Qt.UserRole + 1, sector)
        self.table.setItem(row, 2, port_wt_item)

        # Column 3: Benchmark Weight
        bench_wt_item = QTableWidgetItem(f"{aggregates.get('benchmark_weight', 0):.2f}")
        bench_wt_item.setFlags(bench_wt_item.flags() & ~Qt.ItemIsEditable)
        bench_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bench_wt_item.setFont(font)
        bench_wt_item.setData(Qt.UserRole, "sector_header")
        bench_wt_item.setData(Qt.UserRole + 1, sector)
        self.table.setItem(row, 3, bench_wt_item)

        # Column 4: Active Weight
        active_wt_item = QTableWidgetItem(f"{aggregates.get('active_weight', 0):.2f}")
        active_wt_item.setFlags(active_wt_item.flags() & ~Qt.ItemIsEditable)
        active_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        active_wt_item.setFont(font)
        active_wt_item.setData(Qt.UserRole, "sector_header")
        active_wt_item.setData(Qt.UserRole + 1, sector)
        self.table.setItem(row, 4, active_wt_item)

        # Column 5: Idio Vol (not additive - show "--")
        idio_vol_item = QTableWidgetItem("--")
        idio_vol_item.setFlags(idio_vol_item.flags() & ~Qt.ItemIsEditable)
        idio_vol_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        idio_vol_item.setFont(font)
        idio_vol_item.setData(Qt.UserRole, "sector_header")
        idio_vol_item.setData(Qt.UserRole + 1, sector)
        self.table.setItem(row, 5, idio_vol_item)

        # Column 6: Idio TEV (sum of individual contributions)
        idio_tev_item = QTableWidgetItem(f"{aggregates.get('idio_tev', 0):.2f}")
        idio_tev_item.setFlags(idio_tev_item.flags() & ~Qt.ItemIsEditable)
        idio_tev_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        idio_tev_item.setFont(font)
        idio_tev_item.setData(Qt.UserRole, "sector_header")
        idio_tev_item.setData(Qt.UserRole + 1, sector)
        self.table.setItem(row, 6, idio_tev_item)

        # Column 7: Idio CTEV
        ctev_item = QTableWidgetItem(f"{aggregates.get('idio_ctev', 0):.2f}")
        ctev_item.setFlags(ctev_item.flags() & ~Qt.ItemIsEditable)
        ctev_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ctev_item.setFont(font)
        ctev_item.setData(Qt.UserRole, "sector_header")
        ctev_item.setData(Qt.UserRole + 1, sector)
        self.table.setItem(row, 7, ctev_item)

        # Apply header styling
        self._style_header_row(row)

        return row

    def _add_security_row(
        self, ticker: str, name: str, metrics: Dict[str, float]
    ):
        """Add a security data row with all columns."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Column 0: Name (indented)
        name_item = QTableWidgetItem(f"    {name}")
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, name_item)

        # Column 1: Ticker
        ticker_item = QTableWidgetItem(ticker)
        ticker_item.setFlags(ticker_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, ticker_item)

        # Column 2: Portfolio Weight
        port_wt = metrics.get("portfolio_weight", 0)
        port_wt_item = QTableWidgetItem(f"{port_wt:.2f}")
        port_wt_item.setFlags(port_wt_item.flags() & ~Qt.ItemIsEditable)
        port_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 2, port_wt_item)

        # Column 3: Benchmark Weight
        bench_wt = metrics.get("benchmark_weight", 0)
        bench_wt_item = QTableWidgetItem(f"{bench_wt:.2f}")
        bench_wt_item.setFlags(bench_wt_item.flags() & ~Qt.ItemIsEditable)
        bench_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 3, bench_wt_item)

        # Column 4: Active Weight (Port - Bench)
        active_wt = metrics.get("active_weight", port_wt - bench_wt)
        active_wt_item = QTableWidgetItem(f"{active_wt:.2f}")
        active_wt_item.setFlags(active_wt_item.flags() & ~Qt.ItemIsEditable)
        active_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 4, active_wt_item)

        # Column 5: Idio Vol (idiosyncratic volatility)
        idio_vol = metrics.get("idio_vol", 0)
        idio_vol_item = QTableWidgetItem(f"{idio_vol:.2f}")
        idio_vol_item.setFlags(idio_vol_item.flags() & ~Qt.ItemIsEditable)
        idio_vol_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 5, idio_vol_item)

        # Column 6: Idio TEV
        idio_tev = metrics.get("idio_tev", 0)
        idio_tev_item = QTableWidgetItem(f"{idio_tev:.2f}")
        idio_tev_item.setFlags(idio_tev_item.flags() & ~Qt.ItemIsEditable)
        idio_tev_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 6, idio_tev_item)

        # Column 7: Idio CTEV
        idio_ctev = metrics.get("idio_ctev", 0)
        ctev_item = QTableWidgetItem(f"{idio_ctev:.2f}")
        ctev_item.setFlags(ctev_item.flags() & ~Qt.ItemIsEditable)
        ctev_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 7, ctev_item)

        # Apply data row styling
        self._style_data_row(row)

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

    def _style_total_row(self, row: int):
        """Apply styling to the total row (more prominent than sector headers)."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = QColor("#c0c0c0")
            fg_color = QColor("#000000")
        elif theme == "bloomberg":
            bg_color = QColor("#0d1830")
            fg_color = QColor("#FFa000")
        else:  # dark
            bg_color = QColor("#2a2a2a")
            fg_color = QColor("#00e4ff")

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
        self._security_data.clear()
        self._benchmark_weights.clear()
        self._sector_rows.clear()
        self.table.setRowCount(0)

    def set_collapsed_sectors(self, sectors: List[str]):
        """Set which sectors should start collapsed."""
        self._collapsed_sectors = set(sectors)
        if self._security_data:
            self._rebuild_table()

    def get_collapsed_sectors(self) -> List[str]:
        """Get list of currently collapsed sectors."""
        return list(self._collapsed_sectors)

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
        if self._security_data:
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
