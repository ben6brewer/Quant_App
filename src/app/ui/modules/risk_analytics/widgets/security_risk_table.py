"""Security Risk Table Widget - Tabbed view with Idiosyncratic and Factor breakdowns."""

from typing import Any, Dict, List, Optional, Set

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
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
    Tabbed security risk table with sector/factor groupings.

    Two tabs:
    - Idiosyncratic: Shows idiosyncratic risk metrics grouped by sector
      (Vol, TEV, CTEV)
    - Factor: Shows Fama-French factor contributions as collapsible rows
      (Market, Size, Value, Profitability, Investment, Momentum)
      Each factor expands to show top 20 securities contributing to that factor
    """

    # Column definitions for each tab
    IDIO_COLUMNS = ["Name", "Ticker", "Port Wt", "Bench Wt", "Active Wt", "Idio Vol", "Idio TEV", "Idio CTEV"]
    IDIO_COL_WIDTHS = [200, 80, 70, 70, 70, 70, 70, 70]

    # Factor tab: shows factors as collapsible rows with top securities
    FACTOR_COLUMNS = ["Name", "Ticker", "Active Wt", "Beta", "Contribution"]
    FACTOR_COL_WIDTHS = [280, 80, 80, 80, 100]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False
        self._collapsed_sectors: Set[str] = set()  # For idiosyncratic tab
        self._collapsed_factors: Set[str] = set()  # For factor tab (start collapsed)
        self._collapsed_industries: Set[str] = set()  # For industry section (flat)
        self._collapsed_currencies: Set[str] = set()  # For currency section
        self._collapsed_countries: Set[str] = set()  # For country section
        self._collapsed_factor_sectors: Set[str] = set()  # For hierarchical sector section in Factor tab (Industry display)
        self._collapsed_factor_industries: Set[str] = set()  # For hierarchical industry (key: "Sector|Industry")
        self._collapsed_sector_section: bool = True  # Top-level SECTOR section collapsed (flat)
        self._collapsed_industry_section: bool = True  # Top-level INDUSTRY section collapsed (hierarchical)
        self._collapsed_flat_sectors: Set[str] = set()  # For flat sector section (individual sectors)
        self._collapsed_country_section: bool = True  # Top-level COUNTRY section collapsed
        self._security_data: Dict[str, Dict[str, float]] = {}
        self._regression_results: Dict[str, Any] = {}  # FactorRegressionResult objects
        self._factor_contributions: Dict[str, Any] = {}  # Per-factor breakdown
        self._industry_contributions: Dict[str, Any] = {}  # Industry breakdown (flat)
        self._sector_industry_contributions: Dict[str, Any] = {}  # Hierarchical sector→industry (for "Industry" display)
        self._sector_contributions: Dict[str, Any] = {}  # Flat sector contributions (for "Sector" display)
        self._currency_contributions: Dict[str, Any] = {}  # Currency breakdown
        self._country_contributions: Dict[str, Any] = {}  # Country breakdown
        self._ctev_by_factor: Dict[str, Any] = {}  # CTEV by factor group (for consistent top-level headers)
        self._benchmark_weights: Dict[str, float] = {}
        self._sector_rows: Dict[str, int] = {}
        self._factor_rows: Dict[str, int] = {}  # Track factor header rows
        self._industry_rows: Dict[str, int] = {}  # Track industry header rows (flat)
        self._factor_sector_rows: Dict[str, int] = {}  # Track hierarchical sector rows
        self._factor_industry_rows: Dict[str, int] = {}  # Track hierarchical industry rows
        self._currency_rows: Dict[str, int] = {}  # Track currency header rows
        self._country_rows: Dict[str, int] = {}  # Track country header rows
        self._flat_sector_rows: Dict[str, int] = {}  # Track flat sector header rows
        self._sector_section_row: Optional[int] = None  # Track top-level SECTOR row (flat)
        self._industry_section_row: Optional[int] = None  # Track top-level INDUSTRY row (hierarchical)
        self._country_section_row: Optional[int] = None  # Track top-level COUNTRY row
        self._current_tab = "idiosyncratic"  # "idiosyncratic" or "factor"

        self._setup_ui()
        self._apply_theme()

        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup table UI with tabs."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header row with title and tabs
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        # Title
        self.title_label = QLabel("Risk Analysis")
        self.title_label.setObjectName("section_title")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Tab buttons
        self.idio_tab_btn = QPushButton("Idiosyncratic")
        self.idio_tab_btn.setObjectName("tab_button_active")
        self.idio_tab_btn.setCursor(Qt.PointingHandCursor)
        self.idio_tab_btn.clicked.connect(lambda: self._switch_tab("idiosyncratic"))
        header_layout.addWidget(self.idio_tab_btn)

        self.factor_tab_btn = QPushButton("Factor")
        self.factor_tab_btn.setObjectName("tab_button")
        self.factor_tab_btn.setCursor(Qt.PointingHandCursor)
        self.factor_tab_btn.clicked.connect(lambda: self._switch_tab("factor"))
        header_layout.addWidget(self.factor_tab_btn)

        layout.addLayout(header_layout)

        # Table
        self.table = SmoothScrollTableWidget()
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)

        # Hide scrollbars but keep scroll functionality
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Connect click handler for collapsible headers
        self.table.cellClicked.connect(self._on_cell_clicked)

        layout.addWidget(self.table, stretch=1)

        # Initialize with idiosyncratic columns
        self._setup_table_columns("idiosyncratic")

    def _setup_table_columns(self, tab: str):
        """Setup table columns for the specified tab."""
        if tab == "idiosyncratic":
            columns = self.IDIO_COLUMNS
            widths = self.IDIO_COL_WIDTHS
        else:
            columns = self.FACTOR_COLUMNS
            widths = self.FACTOR_COL_WIDTHS

        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for i, width in enumerate(widths):
            self.table.setColumnWidth(i, width)
        header.setSectionResizeMode(0, QHeaderView.Stretch)

    def _switch_tab(self, tab: str):
        """Switch between idiosyncratic and factor tabs."""
        if tab == self._current_tab:
            return

        self._current_tab = tab

        # Update button styles
        if tab == "idiosyncratic":
            self.idio_tab_btn.setObjectName("tab_button_active")
            self.factor_tab_btn.setObjectName("tab_button")
        else:
            self.idio_tab_btn.setObjectName("tab_button")
            self.factor_tab_btn.setObjectName("tab_button_active")

        # Force style refresh
        self.idio_tab_btn.style().unpolish(self.idio_tab_btn)
        self.idio_tab_btn.style().polish(self.idio_tab_btn)
        self.factor_tab_btn.style().unpolish(self.factor_tab_btn)
        self.factor_tab_btn.style().polish(self.factor_tab_btn)

        # Setup new columns and rebuild table
        self._setup_table_columns(tab)
        self._rebuild_table()

    def set_data(
        self,
        security_risks: Dict[str, Dict[str, float]],
        benchmark_weights: Optional[Dict[str, float]] = None,
        regression_results: Optional[Dict[str, Any]] = None,
        factor_contributions: Optional[Dict[str, Any]] = None,
        industry_contributions: Optional[Dict[str, Any]] = None,
        currency_contributions: Optional[Dict[str, Any]] = None,
        country_contributions: Optional[Dict[str, Any]] = None,
        sector_industry_contributions: Optional[Dict[str, Any]] = None,
        sector_contributions: Optional[Dict[str, Any]] = None,
        ctev_by_factor: Optional[Dict[str, Any]] = None,
    ):
        """
        Set security risk data and rebuild table.

        Args:
            security_risks: Dict mapping ticker to risk metrics
            benchmark_weights: Optional dict mapping ticker to benchmark weight %
            regression_results: Optional dict mapping ticker to FactorRegressionResult
            factor_contributions: Optional dict with per-factor breakdown and top securities
            industry_contributions: Optional dict with industry breakdown (flat)
            currency_contributions: Optional dict with USD vs Non-USD breakdown
            country_contributions: Optional dict with US vs Non-US breakdown
            sector_industry_contributions: Optional dict with hierarchical sector→industry breakdown (for "Industry" display)
            sector_contributions: Optional dict with flat sector breakdown (for "Sector" display)
            ctev_by_factor: Optional dict with CTEV by factor group (Market, Style, Sector, Industry, Country)
        """
        self._security_data = security_risks
        self._benchmark_weights = benchmark_weights or {}
        self._regression_results = regression_results or {}
        self._factor_contributions = factor_contributions or {}
        self._industry_contributions = industry_contributions or {}
        self._sector_industry_contributions = sector_industry_contributions or {}
        self._sector_contributions = sector_contributions or {}
        self._currency_contributions = currency_contributions or {}
        self._country_contributions = country_contributions or {}
        self._ctev_by_factor = ctev_by_factor or {}

        # Initialize all sections as collapsed by default
        self._collapsed_factors = set(self._factor_contributions.keys())
        self._collapsed_flat_sectors = set(self._sector_contributions.keys())  # Flat sectors
        self._collapsed_factor_sectors = set(self._sector_industry_contributions.keys())  # Hierarchical sectors
        # Collapse all industries within sectors
        self._collapsed_factor_industries = set()
        for sector_name, sector_data in self._sector_industry_contributions.items():
            for industry_name in sector_data.get("industries", {}).keys():
                self._collapsed_factor_industries.add(f"{sector_name}|{industry_name}")
        self._collapsed_countries = set(self._country_contributions.keys())
        # Idiosyncratic sectors also collapsed
        if security_risks:
            sectors = set()
            for ticker in security_risks:
                sectors.add(SectorOverrideService.get_effective_sector(ticker))
            self._collapsed_sectors = sectors

        self._rebuild_table()

    def _rebuild_table(self):
        """Rebuild the table with current data and collapse states."""
        self.table.setRowCount(0)
        self._sector_rows.clear()
        self._factor_rows.clear()
        self._industry_rows.clear()
        self._factor_sector_rows.clear()
        self._factor_industry_rows.clear()
        self._currency_rows.clear()
        self._country_rows.clear()
        self._flat_sector_rows.clear()
        self._sector_section_row = None
        self._industry_section_row = None
        self._country_section_row = None

        if self._current_tab == "idiosyncratic":
            if not self._security_data:
                return
            self._rebuild_idiosyncratic_table()
        else:
            if not self._factor_contributions:
                return
            self._rebuild_factor_table()

        self.table.resizeRowsToContents()

    def _rebuild_idiosyncratic_table(self):
        """Rebuild table with idiosyncratic risk data."""
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
                    "idio_vol": None,
                    "idio_tev": 0.0,
                    "idio_ctev": 0.0,
                }

            metadata = TickerMetadataService.get_metadata(ticker)
            name = metadata.get("shortName") or ticker
            sector_groups[sector].append((ticker, name, metrics))

            for key in ["portfolio_weight", "benchmark_weight", "active_weight", "idio_tev", "idio_ctev"]:
                sector_aggregates[sector][key] += metrics.get(key, 0.0)

        # Calculate grand totals
        grand_totals = {
            "portfolio_weight": 0.0,
            "benchmark_weight": 0.0,
            "active_weight": 0.0,
            "idio_vol": None,
            "idio_tev": 0.0,
            "idio_ctev": 0.0,
        }
        for sector_agg in sector_aggregates.values():
            for key in ["portfolio_weight", "benchmark_weight", "active_weight", "idio_tev", "idio_ctev"]:
                grand_totals[key] += sector_agg[key]

        sorted_sectors = sorted(
            sector_groups.keys(),
            key=lambda s: sector_aggregates[s]["idio_ctev"],
            reverse=True,
        )

        # Add Total row
        self._add_idio_total_row(len(self._security_data), grand_totals)

        for sector in sorted_sectors:
            securities = sector_groups[sector]
            securities.sort(key=lambda x: x[2].get("idio_ctev", 0), reverse=True)
            is_collapsed = sector in self._collapsed_sectors

            header_row = self._add_idio_sector_header(
                sector, len(securities), sector_aggregates[sector], is_collapsed
            )
            self._sector_rows[sector] = header_row

            if not is_collapsed:
                for ticker, name, metrics in securities:
                    self._add_idio_security_row(ticker, name, metrics)

    def _rebuild_factor_table(self):
        """Rebuild table with factor breakdown - factors as collapsible rows."""
        if not self._factor_contributions:
            return

        # Section 1: Fama-French Factors (already sorted by CTEV in the service)
        for factor_name, factor_data in self._factor_contributions.items():
            is_collapsed = factor_name in self._collapsed_factors
            securities = factor_data.get("securities", [])

            # Add factor header row
            header_row = self._add_factor_header_row(
                factor_name,
                factor_data,
                len(securities),
                is_collapsed,
            )
            self._factor_rows[factor_name] = header_row

            # Add security rows if expanded
            if not is_collapsed:
                for security in securities:
                    self._add_factor_security_row(security, factor_data.get("factor_code", ""))

        # Section 2: Sector (flat, no industry grouping)
        if self._sector_contributions:
            # Calculate totals for top-level SECTOR header (flat)
            total_flat_sector_securities = sum(
                len(s.get("securities", [])) for s in self._sector_contributions.values()
            )
            # Use CTEV from ctev_by_factor for consistency with "Top CTEV by Factor Group" panel
            sector_factor_data = self._ctev_by_factor.get("Sector", {})
            total_flat_sector_ctev = sector_factor_data.get("ctev", 0) if isinstance(sector_factor_data, dict) else 0

            # Add top-level SECTOR header (collapsible like factors)
            self._sector_section_row = self._add_top_level_section_header(
                "Sector",
                total_flat_sector_securities,
                total_flat_sector_ctev,
                self._collapsed_sector_section,
            )

            # Only show sectors if top-level is expanded
            if not self._collapsed_sector_section:
                for sector_name, sector_data in self._sector_contributions.items():
                    is_sector_collapsed = sector_name in self._collapsed_flat_sectors
                    securities = sector_data.get("securities", [])

                    # Add flat sector header row
                    header_row = self._add_flat_sector_header_row(
                        sector_name,
                        sector_data,
                        len(securities),
                        is_sector_collapsed,
                    )
                    self._flat_sector_rows[sector_name] = header_row

                    # If sector is expanded, show securities (no industry level)
                    if not is_sector_collapsed:
                        for security in securities:
                            self._add_flat_sector_security_row(security)

        # Section 3: Industry (hierarchical: sector → industry → securities)
        if self._sector_industry_contributions:
            # Calculate totals for top-level INDUSTRY header
            total_industry_securities = sum(
                sum(len(ind.get("securities", [])) for ind in s.get("industries", {}).values())
                for s in self._sector_industry_contributions.values()
            )
            # Use CTEV from ctev_by_factor for consistency with "Top CTEV by Factor Group" panel
            industry_factor_data = self._ctev_by_factor.get("Industry", {})
            total_industry_ctev = industry_factor_data.get("ctev", 0) if isinstance(industry_factor_data, dict) else 0

            # Add top-level INDUSTRY header (collapsible like factors)
            self._industry_section_row = self._add_top_level_section_header(
                "Industry",
                total_industry_securities,
                total_industry_ctev,
                self._collapsed_industry_section,
            )

            # Only show sectors if top-level is expanded
            if not self._collapsed_industry_section:
                for sector_name, sector_data in self._sector_industry_contributions.items():
                    is_sector_collapsed = sector_name in self._collapsed_factor_sectors
                    industries = sector_data.get("industries", {})
                    total_securities = sum(
                        len(ind.get("securities", [])) for ind in industries.values()
                    )

                    # Add sector header row (parent level, indented)
                    header_row = self._add_factor_sector_header_row(
                        sector_name,
                        sector_data,
                        total_securities,
                        is_sector_collapsed,
                    )
                    self._factor_sector_rows[sector_name] = header_row

                    # If sector is expanded, show industries
                    if not is_sector_collapsed:
                        for industry_name, industry_data in industries.items():
                            industry_key = f"{sector_name}|{industry_name}"
                            is_industry_collapsed = industry_key in self._collapsed_factor_industries
                            securities = industry_data.get("securities", [])

                            # Add industry header row (child level, indented)
                            industry_row = self._add_factor_industry_header_row(
                                industry_name,
                                industry_data,
                                len(securities),
                                is_industry_collapsed,
                                sector_name,
                            )
                            self._factor_industry_rows[industry_key] = industry_row

                            # If industry is expanded, show securities
                            if not is_industry_collapsed:
                                for security in securities:
                                    self._add_sector_industry_security_row(security)

        # Section 4: Country (top-level collapsible) - Currency section removed (all USD)
        if self._country_contributions:
            # Calculate totals for top-level COUNTRY header
            total_country_securities = sum(
                len(c.get("securities", [])) for c in self._country_contributions.values()
            )
            # Use CTEV from ctev_by_factor for consistency with "Top CTEV by Factor Group" panel
            country_factor_data = self._ctev_by_factor.get("Country", {})
            total_country_ctev = country_factor_data.get("ctev", 0) if isinstance(country_factor_data, dict) else 0

            # Add top-level COUNTRY header (collapsible like factors)
            self._country_section_row = self._add_top_level_section_header(
                "Country",
                total_country_securities,
                total_country_ctev if total_country_ctev > 0 else None,
                self._collapsed_country_section,
            )

            # Only show countries if top-level is expanded
            if not self._collapsed_country_section:
                for country_name, country_data in self._country_contributions.items():
                    is_collapsed = country_name in self._collapsed_countries
                    securities = country_data.get("securities", [])

                    header_row = self._add_country_header_row(
                        country_name,
                        country_data,
                        len(securities),
                        is_collapsed,
                    )
                    self._country_rows[country_name] = header_row

                    if not is_collapsed:
                        for security in securities:
                            self._add_country_security_row(security)

    def _add_idio_total_row(self, count: int, totals: Dict[str, float]) -> int:
        """Add total row for idiosyncratic tab."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        items = [
            (f"TOTAL ({count} securities)", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{totals.get('portfolio_weight', 0):.2f}", Qt.AlignRight),
            (f"{totals.get('benchmark_weight', 0):.2f}", Qt.AlignRight),
            (f"{totals.get('active_weight', 0):.2f}", Qt.AlignRight),
            ("--", Qt.AlignRight),  # Idio Vol not additive
            (f"{totals.get('idio_tev', 0):.2f}", Qt.AlignRight),
            (f"{totals.get('idio_ctev', 0):.2f}", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "total_header")
            self.table.setItem(row, col, item)

        self._style_total_row(row)
        return row

    def _add_factor_header_row(
        self, factor_name: str, factor_data: Dict[str, Any], count: int, is_collapsed: bool
    ) -> int:
        """Add factor header row (collapsible)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"
        active_beta = factor_data.get("active_beta", 0)
        ctev = factor_data.get("ctev", 0)

        # Show Active Weight (active_beta * 100) and CTEV
        active_weight = active_beta * 100  # Convert to percentage

        items = [
            (f"{arrow} {factor_name} ({count} securities)", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{active_weight:.2f}", Qt.AlignRight),  # Active weight %
            ("", Qt.AlignRight),  # Empty
            (f"{ctev:.2f}", Qt.AlignRight),  # CTEV in contribution column
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "factor_header")
            item.setData(Qt.UserRole + 1, factor_name)
            self.table.setItem(row, col, item)

        self._style_factor_header_row(row)
        return row

    def _add_top_level_section_header(
        self, section_name: str, count: int, ctev: Optional[float], is_collapsed: bool
    ) -> int:
        """Add top-level section header (Sector, Country) - collapsible like factors."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"

        # Format with CTEV if available
        if ctev is not None:
            items = [
                (f"{arrow} {section_name} ({count} securities)", Qt.AlignLeft),
                ("", Qt.AlignLeft),
                ("", Qt.AlignRight),
                ("", Qt.AlignRight),
                (f"{ctev:.2f}", Qt.AlignRight),  # CTEV in contribution column
            ]
        else:
            items = [
                (f"{arrow} {section_name} ({count} securities)", Qt.AlignLeft),
                ("", Qt.AlignLeft),
                ("", Qt.AlignRight),
                ("", Qt.AlignRight),
                ("", Qt.AlignRight),
            ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "section_header")
            item.setData(Qt.UserRole + 1, section_name)
            self.table.setItem(row, col, item)

        self._style_factor_header_row(row)
        return row

    def _add_idio_sector_header(
        self, sector: str, count: int, aggregates: Dict[str, float], is_collapsed: bool
    ) -> int:
        """Add sector header for idiosyncratic tab."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"
        items = [
            (f"{arrow} {sector} ({count})", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{aggregates.get('portfolio_weight', 0):.2f}", Qt.AlignRight),
            (f"{aggregates.get('benchmark_weight', 0):.2f}", Qt.AlignRight),
            (f"{aggregates.get('active_weight', 0):.2f}", Qt.AlignRight),
            ("--", Qt.AlignRight),
            (f"{aggregates.get('idio_tev', 0):.2f}", Qt.AlignRight),
            (f"{aggregates.get('idio_ctev', 0):.2f}", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "sector_header")
            item.setData(Qt.UserRole + 1, sector)
            self.table.setItem(row, col, item)

        self._style_header_row(row)
        return row

    def _add_idio_security_row(self, ticker: str, name: str, metrics: Dict[str, float]):
        """Add security row for idiosyncratic tab."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        items = [
            (f"    {name}", Qt.AlignLeft),
            (ticker, Qt.AlignLeft),
            (f"{metrics.get('portfolio_weight', 0):.2f}", Qt.AlignRight),
            (f"{metrics.get('benchmark_weight', 0):.2f}", Qt.AlignRight),
            (f"{metrics.get('active_weight', 0):.2f}", Qt.AlignRight),
            (f"{metrics.get('idio_vol', 0):.2f}", Qt.AlignRight),
            (f"{metrics.get('idio_tev', 0):.2f}", Qt.AlignRight),
            (f"{metrics.get('idio_ctev', 0):.2f}", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            self.table.setItem(row, col, item)

        self._style_data_row(row)

    def _add_factor_security_row(self, security: Dict[str, Any], factor_code: str):
        """Add security row under a factor header."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        name = security.get("name", "")
        ticker = security.get("ticker", "")
        active_weight = security.get("active_weight", 0)
        beta = security.get("beta", 0)
        contribution = security.get("contribution", 0)

        items = [
            (f"    {name}", Qt.AlignLeft),
            (ticker, Qt.AlignLeft),
            (f"{active_weight:+.2f}", Qt.AlignRight),
            (f"{beta:.3f}", Qt.AlignRight),
            (f"{contribution:.3f}", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            self.table.setItem(row, col, item)

        self._style_data_row(row)

    def _add_industry_header_row(
        self, industry_name: str, industry_data: Dict[str, Any], count: int, is_collapsed: bool
    ) -> int:
        """Add industry header row (collapsible)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"
        active_weight = industry_data.get("active_weight", 0)
        port_weight = industry_data.get("portfolio_weight", 0)
        bench_weight = industry_data.get("benchmark_weight", 0)

        items = [
            (f"{arrow} {industry_name} ({count})", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{active_weight:+.2f}", Qt.AlignRight),
            (f"Port: {port_weight:.1f}%", Qt.AlignRight),
            (f"Bench: {bench_weight:.1f}%", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "industry_header")
            item.setData(Qt.UserRole + 1, industry_name)
            self.table.setItem(row, col, item)

        self._style_factor_header_row(row)
        return row

    def _add_industry_security_row(self, security: Dict[str, Any]):
        """Add security row under an industry header."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        name = security.get("name", "")
        ticker = security.get("ticker", "")
        active_weight = security.get("active_weight", 0)
        port_weight = security.get("portfolio_weight", 0)
        bench_weight = security.get("benchmark_weight", 0)

        items = [
            (f"    {name}", Qt.AlignLeft),
            (ticker, Qt.AlignLeft),
            (f"{active_weight:+.2f}", Qt.AlignRight),
            (f"{port_weight:.2f}", Qt.AlignRight),
            (f"{bench_weight:.2f}", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            self.table.setItem(row, col, item)

        self._style_data_row(row)

    def _add_factor_sector_header_row(
        self, sector_name: str, sector_data: Dict[str, Any], count: int, is_collapsed: bool
    ) -> int:
        """Add sector header row for hierarchical sector→industry section (parent level)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"
        ctev = sector_data.get("ctev", 0)
        active_weight = sector_data.get("active_weight", 0)
        port_weight = sector_data.get("portfolio_weight", 0)

        items = [
            (f"{arrow} {sector_name} ({count})", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{active_weight:.2f}", Qt.AlignRight),
            (f"{port_weight:.2f}", Qt.AlignRight),
            (f"{ctev:.2f}", Qt.AlignRight),  # CTEV in contribution column
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "factor_sector_header")
            item.setData(Qt.UserRole + 1, sector_name)
            self.table.setItem(row, col, item)

        self._style_sector_header_row(row)
        return row

    def _add_factor_industry_header_row(
        self, industry_name: str, industry_data: Dict[str, Any], count: int,
        is_collapsed: bool, sector_name: str
    ) -> int:
        """Add industry header row for hierarchical sector→industry section (child level, indented)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"
        ctev = industry_data.get("ctev", 0)
        active_weight = industry_data.get("active_weight", 0)
        port_weight = industry_data.get("portfolio_weight", 0)

        # Indented (4 spaces) to show it's under a sector
        items = [
            (f"    {arrow} {industry_name} ({count})", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{active_weight:.2f}", Qt.AlignRight),
            (f"{port_weight:.2f}", Qt.AlignRight),
            (f"{ctev:.2f}", Qt.AlignRight),  # CTEV in contribution column
        ]

        industry_key = f"{sector_name}|{industry_name}"

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "factor_industry_header")
            item.setData(Qt.UserRole + 1, industry_key)
            self.table.setItem(row, col, item)

        self._style_industry_header_row(row)
        return row

    def _add_sector_industry_security_row(self, security: Dict[str, Any]):
        """Add security row under an industry in the hierarchical sector→industry section (double-indented)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        name = security.get("name", "")
        ticker = security.get("ticker", "")
        active_weight = security.get("active_weight", 0)
        port_weight = security.get("portfolio_weight", 0)
        ctev = security.get("ctev", 0)

        # Double-indented (8 spaces) to show it's under an industry
        # Columns: Name, Ticker, Active Wt, (Port Wt), CTEV
        items = [
            (f"        {name}", Qt.AlignLeft),
            (ticker, Qt.AlignLeft),
            (f"{active_weight:.2f}", Qt.AlignRight),
            (f"{port_weight:.2f}", Qt.AlignRight),
            (f"{ctev:.4f}", Qt.AlignRight),  # CTEV without prefix
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            self.table.setItem(row, col, item)

        self._style_data_row(row)

    def _add_flat_sector_header_row(
        self, sector_name: str, sector_data: Dict[str, Any], count: int, is_collapsed: bool
    ) -> int:
        """Add sector header row for flat sector section (no industry grouping)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"
        ctev = sector_data.get("ctev", 0)
        active_weight = sector_data.get("active_weight", 0)
        port_weight = sector_data.get("portfolio_weight", 0)

        items = [
            (f"    {arrow} {sector_name} ({count})", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{active_weight:.2f}", Qt.AlignRight),
            (f"{port_weight:.2f}", Qt.AlignRight),
            (f"{ctev:.2f}", Qt.AlignRight),  # CTEV in contribution column
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "flat_sector_header")
            item.setData(Qt.UserRole + 1, sector_name)
            self.table.setItem(row, col, item)

        self._style_sector_header_row(row)
        return row

    def _add_flat_sector_security_row(self, security: Dict[str, Any]):
        """Add security row under a flat sector (single indent)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        name = security.get("name", "")
        ticker = security.get("ticker", "")
        active_weight = security.get("active_weight", 0)
        port_weight = security.get("portfolio_weight", 0)
        ctev = security.get("ctev", 0)

        # Single-indented (8 spaces) to show it's under a sector
        # Columns: Name, Ticker, Active Wt, (Port Wt), CTEV
        items = [
            (f"        {name}", Qt.AlignLeft),
            (ticker, Qt.AlignLeft),
            (f"{active_weight:.2f}", Qt.AlignRight),
            (f"{port_weight:.2f}", Qt.AlignRight),
            (f"{ctev:.4f}", Qt.AlignRight),  # CTEV without prefix
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            self.table.setItem(row, col, item)

        self._style_data_row(row)

    def _add_currency_header_row(
        self, currency_name: str, currency_data: Dict[str, Any], count: int, is_collapsed: bool
    ) -> int:
        """Add currency header row (collapsible)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"
        active_weight = currency_data.get("active_weight", 0)
        port_weight = currency_data.get("portfolio_weight", 0)
        bench_weight = currency_data.get("benchmark_weight", 0)

        items = [
            (f"{arrow} {currency_name} ({count})", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{active_weight:+.2f}", Qt.AlignRight),
            (f"Port: {port_weight:.1f}%", Qt.AlignRight),
            (f"Bench: {bench_weight:.1f}%", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "currency_header")
            item.setData(Qt.UserRole + 1, currency_name)
            self.table.setItem(row, col, item)

        self._style_factor_header_row(row)
        return row

    def _add_currency_security_row(self, security: Dict[str, Any]):
        """Add security row under a currency header."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        name = security.get("name", "")
        ticker = security.get("ticker", "")
        active_weight = security.get("active_weight", 0)
        currency = security.get("currency", "USD")
        bench_weight = security.get("benchmark_weight", 0)

        items = [
            (f"    {name}", Qt.AlignLeft),
            (ticker, Qt.AlignLeft),
            (f"{active_weight:+.2f}", Qt.AlignRight),
            (currency, Qt.AlignRight),
            (f"{bench_weight:.2f}", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            self.table.setItem(row, col, item)

        self._style_data_row(row)

    def _add_country_header_row(
        self, country_name: str, country_data: Dict[str, Any], count: int, is_collapsed: bool
    ) -> int:
        """Add country header row (collapsible)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        font = QFont()
        font.setBold(True)

        arrow = "▶" if is_collapsed else "▼"
        active_weight = country_data.get("active_weight", 0)
        port_weight = country_data.get("portfolio_weight", 0)
        bench_weight = country_data.get("benchmark_weight", 0)

        items = [
            (f"{arrow} {country_name} ({count})", Qt.AlignLeft),
            ("", Qt.AlignLeft),
            (f"{active_weight:+.2f}", Qt.AlignRight),
            (f"Port: {port_weight:.1f}%", Qt.AlignRight),
            (f"Bench: {bench_weight:.1f}%", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            item.setFont(font)
            item.setData(Qt.UserRole, "country_header")
            item.setData(Qt.UserRole + 1, country_name)
            self.table.setItem(row, col, item)

        self._style_factor_header_row(row)
        return row

    def _add_country_security_row(self, security: Dict[str, Any]):
        """Add security row under a country header."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        name = security.get("name", "")
        ticker = security.get("ticker", "")
        active_weight = security.get("active_weight", 0)
        country = security.get("country", "United States")
        bench_weight = security.get("benchmark_weight", 0)

        items = [
            (f"    {name}", Qt.AlignLeft),
            (ticker, Qt.AlignLeft),
            (f"{active_weight:+.2f}", Qt.AlignRight),
            (country, Qt.AlignRight),
            (f"{bench_weight:.2f}", Qt.AlignRight),
        ]

        for col, (text, align) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setTextAlignment(align | Qt.AlignVCenter)
            self.table.setItem(row, col, item)

        self._style_data_row(row)

    def _on_cell_clicked(self, row: int, col: int):
        """Handle cell click - toggle collapse if header clicked."""
        item = self.table.item(row, 0)
        if not item:
            return

        item_type = item.data(Qt.UserRole)
        item_name = item.data(Qt.UserRole + 1)

        if item_type == "sector_header":
            self._toggle_sector(item_name)
        elif item_type == "factor_header":
            self._toggle_factor(item_name)
        elif item_type == "industry_header":
            self._toggle_industry(item_name)
        elif item_type == "factor_sector_header":
            self._toggle_factor_sector(item_name)
        elif item_type == "factor_industry_header":
            self._toggle_factor_industry(item_name)
        elif item_type == "flat_sector_header":
            self._toggle_flat_sector(item_name)
        elif item_type == "currency_header":
            self._toggle_currency(item_name)
        elif item_type == "country_header":
            self._toggle_country(item_name)
        elif item_type == "section_header":
            self._toggle_section(item_name)

    def _toggle_sector(self, sector: str):
        """Toggle collapsed state for a sector."""
        if sector in self._collapsed_sectors:
            self._collapsed_sectors.remove(sector)
        else:
            self._collapsed_sectors.add(sector)
        self._rebuild_table()

    def _toggle_factor(self, factor: str):
        """Toggle collapsed state for a factor."""
        if factor in self._collapsed_factors:
            self._collapsed_factors.remove(factor)
        else:
            self._collapsed_factors.add(factor)
        self._rebuild_table()

    def _toggle_industry(self, industry: str):
        """Toggle collapsed state for an industry."""
        if industry in self._collapsed_industries:
            self._collapsed_industries.remove(industry)
        else:
            self._collapsed_industries.add(industry)
        self._rebuild_table()

    def _toggle_factor_sector(self, sector: str):
        """Toggle collapsed state for a sector in the hierarchical factor tab."""
        if sector in self._collapsed_factor_sectors:
            self._collapsed_factor_sectors.remove(sector)
        else:
            self._collapsed_factor_sectors.add(sector)
        self._rebuild_table()

    def _toggle_factor_industry(self, industry_key: str):
        """Toggle collapsed state for an industry in the hierarchical factor tab.

        Args:
            industry_key: Key in format "Sector|Industry"
        """
        if industry_key in self._collapsed_factor_industries:
            self._collapsed_factor_industries.remove(industry_key)
        else:
            self._collapsed_factor_industries.add(industry_key)
        self._rebuild_table()

    def _toggle_flat_sector(self, sector: str):
        """Toggle collapsed state for a sector in the flat sector section."""
        if sector in self._collapsed_flat_sectors:
            self._collapsed_flat_sectors.remove(sector)
        else:
            self._collapsed_flat_sectors.add(sector)
        self._rebuild_table()

    def _toggle_currency(self, currency: str):
        """Toggle collapsed state for a currency bucket."""
        if currency in self._collapsed_currencies:
            self._collapsed_currencies.remove(currency)
        else:
            self._collapsed_currencies.add(currency)
        self._rebuild_table()

    def _toggle_country(self, country: str):
        """Toggle collapsed state for a country bucket."""
        if country in self._collapsed_countries:
            self._collapsed_countries.remove(country)
        else:
            self._collapsed_countries.add(country)
        self._rebuild_table()

    def _toggle_section(self, section_name: str):
        """Toggle collapsed state for a top-level section (Sector, Industry, Country)."""
        if section_name == "Sector":
            self._collapsed_sector_section = not self._collapsed_sector_section
        elif section_name == "Industry":
            self._collapsed_industry_section = not self._collapsed_industry_section
        elif section_name == "Country":
            self._collapsed_country_section = not self._collapsed_country_section
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
        else:
            bg_color = QColor("#3d3d3d")
            fg_color = QColor("#00d4ff")

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(fg_color)

    def _style_factor_header_row(self, row: int):
        """Apply styling to a factor header row."""
        theme = self.theme_manager.current_theme

        # Factor headers use a slightly different color to distinguish from sectors
        if theme == "light":
            bg_color = QColor("#d0d8e0")
            fg_color = QColor("#0055aa")
        elif theme == "bloomberg":
            bg_color = QColor("#162030")
            fg_color = QColor("#FFa500")
        else:
            bg_color = QColor("#2a3540")
            fg_color = QColor("#00c8ff")

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(fg_color)

    def _style_sector_header_row(self, row: int):
        """Apply styling to a sector header row in hierarchical view (parent level)."""
        theme = self.theme_manager.current_theme

        # Sector headers: bold accent color, darker background
        if theme == "light":
            bg_color = QColor("#d0d8e0")
            fg_color = QColor("#0055aa")
        elif theme == "bloomberg":
            bg_color = QColor("#162030")
            fg_color = QColor("#FFa500")
        else:
            bg_color = QColor("#2a3540")
            fg_color = QColor("#00c8ff")

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(fg_color)

    def _style_industry_header_row(self, row: int):
        """Apply styling to an industry header row in hierarchical view (child level)."""
        theme = self.theme_manager.current_theme

        # Industry headers: slightly dimmer than sector headers
        if theme == "light":
            bg_color = QColor("#e0e8f0")
            fg_color = QColor("#3366aa")
        elif theme == "bloomberg":
            bg_color = QColor("#1a2838")
            fg_color = QColor("#cc8800")
        else:
            bg_color = QColor("#323a45")
            fg_color = QColor("#00b0e0")

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(bg_color)
                item.setForeground(fg_color)

    def _style_total_row(self, row: int):
        """Apply styling to the total row."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = QColor("#c0c0c0")
            fg_color = QColor("#000000")
        elif theme == "bloomberg":
            bg_color = QColor("#0d1830")
            fg_color = QColor("#FFa000")
        else:
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
        self._regression_results.clear()
        self._factor_contributions.clear()
        self._industry_contributions.clear()
        self._sector_industry_contributions.clear()
        self._sector_contributions.clear()
        self._currency_contributions.clear()
        self._country_contributions.clear()
        self._ctev_by_factor.clear()
        self._sector_rows.clear()
        self._factor_rows.clear()
        self._industry_rows.clear()
        self._factor_sector_rows.clear()
        self._factor_industry_rows.clear()
        self._flat_sector_rows.clear()
        self._currency_rows.clear()
        self._country_rows.clear()
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
            QPushButton#tab_button {
                background-color: transparent;
                color: #808080;
                border: none;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: normal;
            }
            QPushButton#tab_button:hover {
                color: #00d4ff;
            }
            QPushButton#tab_button_active {
                background-color: transparent;
                color: #00d4ff;
                border: none;
                border-bottom: 2px solid #00d4ff;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: bold;
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
            QPushButton#tab_button {
                background-color: transparent;
                color: #808080;
                border: none;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: normal;
            }
            QPushButton#tab_button:hover {
                color: #0066cc;
            }
            QPushButton#tab_button_active {
                background-color: transparent;
                color: #0066cc;
                border: none;
                border-bottom: 2px solid #0066cc;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: bold;
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
            QPushButton#tab_button {
                background-color: transparent;
                color: #808080;
                border: none;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: normal;
            }
            QPushButton#tab_button:hover {
                color: #FF8000;
            }
            QPushButton#tab_button_active {
                background-color: transparent;
                color: #FF8000;
                border: none;
                border-bottom: 2px solid #FF8000;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: bold;
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
