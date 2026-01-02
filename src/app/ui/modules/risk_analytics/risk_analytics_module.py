"""Risk Analytics Module - Bloomberg TEV-style risk decomposition analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QApplication,
)
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.services.returns_data_service import ReturnsDataService
from app.ui.widgets.common.custom_message_box import CustomMessageBox
from app.ui.widgets.common.loading_overlay import LoadingOverlay
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

from .services.risk_analytics_service import RiskAnalyticsService
from .services.risk_analytics_settings_manager import RiskAnalyticsSettingsManager
from .services.ticker_metadata_service import TickerMetadataService
from .widgets.risk_analytics_controls import RiskAnalyticsControls
from .widgets.risk_summary_panel import RiskSummaryPanel
from .widgets.risk_decomposition_panel import RiskDecompositionPanel
from .widgets.security_risk_table import SecurityRiskTable
from .widgets.risk_analytics_settings_dialog import RiskAnalyticsSettingsDialog

if TYPE_CHECKING:
    import pandas as pd


class RiskAnalyticsModule(LazyThemeMixin, QWidget):
    """
    Risk Analytics module - Bloomberg TEV-style risk decomposition.

    Provides tracking error volatility analysis including:
    - Total active risk (tracking error)
    - Factor vs idiosyncratic risk decomposition
    - CTEV breakdown by factor group, sector, and security
    - Collapsible security-level risk table
    """

    # Signal emitted when user clicks home button
    home_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        # Settings manager
        self.settings_manager = RiskAnalyticsSettingsManager()

        # Current state
        self._current_portfolio: str = ""
        self._current_benchmark: str = ""
        self._is_benchmark_portfolio: bool = False
        self._portfolio_list: List[str] = []

        # Loading overlay
        self._loading_overlay: Optional[LoadingOverlay] = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Load portfolio list
        self._refresh_portfolio_list()

        # Set default benchmark from settings
        default_benchmark = self.settings_manager.get_setting("default_benchmark")
        if default_benchmark:
            self.controls.set_benchmark(default_benchmark)
            self._current_benchmark = default_benchmark

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup the module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = RiskAnalyticsControls(self.theme_manager)
        layout.addWidget(self.controls)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        # Top row: Risk Summary + 3 CTEV panels (4 equal columns)
        # Fixed height to show 6 rows (title + header + 6 data rows)
        top_row = QWidget()
        top_row.setFixedHeight(280)
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(20)

        # Summary panel (vertical layout with main metric + sub-rows)
        self.summary_panel = RiskSummaryPanel(self.theme_manager)
        top_row_layout.addWidget(self.summary_panel, stretch=1)

        # Risk decomposition panels (3 columns - gets 3/4 of the width)
        self.decomposition_panel = RiskDecompositionPanel(self.theme_manager)
        top_row_layout.addWidget(self.decomposition_panel, stretch=3)

        content_layout.addWidget(top_row)

        # Security risk table (collapsible by sector)
        self.security_table = SecurityRiskTable(self.theme_manager)
        content_layout.addWidget(self.security_table, stretch=1)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

    def _connect_signals(self):
        """Connect signals to slots."""
        # Controls signals
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.benchmark_changed.connect(self._on_benchmark_changed)
        self.controls.analyze_clicked.connect(self._update_risk_analysis)
        self.controls.settings_clicked.connect(self._show_settings_dialog)

        # Theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _refresh_portfolio_list(self):
        """Refresh the portfolio dropdown and benchmark dropdown."""
        self._portfolio_list = PortfolioDataService.list_portfolios_by_recent()
        self.controls.update_portfolio_list(self._portfolio_list, self._current_portfolio)
        self.controls.update_benchmark_list(self._portfolio_list)

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio selection change (just update state, don't analyze)."""
        if name == self._current_portfolio:
            return

        self._current_portfolio = name

    def _on_benchmark_changed(self, benchmark: str):
        """Handle benchmark selection change (just update state, don't analyze)."""
        if benchmark == self._current_benchmark:
            return

        self._current_benchmark = benchmark

        # Determine if benchmark is a portfolio
        if benchmark:
            self._is_benchmark_portfolio = benchmark.startswith("[Portfolio] ")
        else:
            self._is_benchmark_portfolio = False

    def _show_settings_dialog(self):
        """Show the settings dialog."""
        current_settings = self.settings_manager.get_all_settings()
        dialog = RiskAnalyticsSettingsDialog(
            self.theme_manager, current_settings, self
        )
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, settings: Dict[str, Any]):
        """Handle settings saved from dialog."""
        self.settings_manager.update_settings(settings)
        # Settings saved - user can click Analyze to apply new settings

    def _update_risk_analysis(self):
        """Run risk analysis and update all displays."""
        # Get current selections from controls (user might not have triggered change signals)
        self._current_portfolio = self.controls.get_current_portfolio()
        benchmark_text = self.controls.get_current_benchmark().strip()

        # Normalize benchmark text
        if benchmark_text and benchmark_text.upper() != "NONE":
            if benchmark_text.startswith("[Portfolio]"):
                self._current_benchmark = benchmark_text
                self._is_benchmark_portfolio = True
            else:
                self._current_benchmark = benchmark_text.upper()
                self._is_benchmark_portfolio = False
        else:
            self._current_benchmark = ""
            self._is_benchmark_portfolio = False

        if not self._current_portfolio:
            self._clear_displays()
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Portfolio",
                "Please select a portfolio to analyze.",
            )
            return

        if not self._current_benchmark:
            self._clear_displays()
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Benchmark",
                "Please enter a benchmark ticker (e.g., SPY) to compare against.",
            )
            return

        # Show loading overlay
        self._show_loading_overlay("Analyzing risk...")

        try:
            # Get portfolio tickers first to fetch current prices
            tickers_list = PortfolioDataService.get_tickers(self._current_portfolio)
            if not tickers_list:
                self._hide_loading_overlay()
                self._clear_displays()
                CustomMessageBox.warning(
                    self.theme_manager,
                    self,
                    "No Holdings",
                    f"Portfolio '{self._current_portfolio}' has no holdings.",
                )
                return

            # Fetch current prices for weight calculation
            from app.services.market_data import fetch_price_history

            current_prices = {}
            for ticker in tickers_list:
                try:
                    df = fetch_price_history(ticker, period="5d", interval="1d")
                    if df is not None and not df.empty:
                        current_prices[ticker] = df["Close"].iloc[-1]
                except Exception:
                    pass

            # Get portfolio data with current prices
            holdings = PortfolioDataService.get_holdings(self._current_portfolio, current_prices)
            if not holdings:
                self._hide_loading_overlay()
                self._clear_displays()
                CustomMessageBox.warning(
                    self.theme_manager,
                    self,
                    "No Holdings",
                    f"Portfolio '{self._current_portfolio}' has no holdings.",
                )
                return

            # Extract tickers and weights (normalize to uppercase for consistent lookups)
            tickers = [h.ticker.upper() for h in holdings if h.ticker != "FREE CASH"]
            weights = {h.ticker.upper(): h.weight for h in holdings if h.ticker != "FREE CASH"}

            if not tickers:
                self._hide_loading_overlay()
                self._clear_displays()
                return

            # Prefetch metadata for all tickers (parallel fetch)
            TickerMetadataService.get_metadata_batch(tickers)

            # Get lookback days from settings
            lookback_days = self.settings_manager.get_setting("lookback_days")

            # Get portfolio returns
            portfolio_returns = ReturnsDataService.get_portfolio_returns(
                self._current_portfolio
            )

            if portfolio_returns is None or portfolio_returns.empty:
                self._hide_loading_overlay()
                self._clear_displays()
                CustomMessageBox.warning(
                    self.theme_manager,
                    self,
                    "No Returns Data",
                    f"Could not calculate returns for '{self._current_portfolio}'.",
                )
                return

            # Trim to lookback period
            if len(portfolio_returns) > lookback_days:
                portfolio_returns = portfolio_returns.iloc[-lookback_days:]

            # Get benchmark returns
            benchmark_returns = self._get_benchmark_returns(lookback_days)

            if benchmark_returns is None or benchmark_returns.empty:
                self._hide_loading_overlay()
                self._clear_displays()
                CustomMessageBox.warning(
                    self.theme_manager,
                    self,
                    "No Benchmark Data",
                    f"Could not fetch returns for benchmark '{self._current_benchmark}'.",
                )
                return

            # Get individual ticker returns for CTEV calculation
            ticker_returns = self._get_ticker_returns(tickers, lookback_days)

            # Run full analysis
            analysis = RiskAnalyticsService.get_full_analysis(
                portfolio_returns,
                benchmark_returns,
                ticker_returns,
                tickers,
                weights,
            )

            # Update displays
            self._update_displays(analysis)

        except Exception as e:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Analysis Error",
                f"Error running risk analysis: {str(e)}",
            )
        finally:
            self._hide_loading_overlay()

    def _get_benchmark_returns(self, lookback_days: int) -> Optional["pd.Series"]:
        """Get benchmark returns (portfolio or ticker)."""
        import pandas as pd

        benchmark = self._current_benchmark

        if not benchmark:
            return None

        if self._is_benchmark_portfolio:
            # Extract portfolio name from "[Portfolio] Name"
            portfolio_name = benchmark.replace("[Portfolio] ", "")
            returns = ReturnsDataService.get_portfolio_returns(portfolio_name)
        else:
            # It's a ticker - fetch from market data
            from app.services.market_data import fetch_price_history

            df = fetch_price_history(benchmark, period="max", interval="1d")
            if df is None or df.empty:
                return None
            returns = df["Close"].pct_change().dropna()

        if returns is None or returns.empty:
            return None

        # Trim to lookback period
        if len(returns) > lookback_days:
            returns = returns.iloc[-lookback_days:]

        return returns

    def _get_ticker_returns(
        self, tickers: List[str], lookback_days: int
    ) -> "pd.DataFrame":
        """Get returns for individual tickers."""
        import pandas as pd
        from app.services.market_data import fetch_price_history

        returns_dict = {}

        for ticker in tickers:
            try:
                df = fetch_price_history(ticker, period="max", interval="1d")
                if df is not None and not df.empty:
                    returns = df["Close"].pct_change().dropna()
                    if len(returns) > lookback_days:
                        returns = returns.iloc[-lookback_days:]
                    returns_dict[ticker] = returns
            except Exception:
                continue

        if not returns_dict:
            return pd.DataFrame()

        # Combine into DataFrame, aligning by date
        # Use dropna(how='all') to only remove rows where ALL values are NaN
        # This preserves more data when tickers have different trading histories
        df = pd.DataFrame(returns_dict)
        df = df.dropna(how='all')  # Remove rows with all NaN
        df = df.ffill().bfill()    # Forward/backward fill remaining NaN
        return df

    def _update_displays(self, analysis: Dict[str, Any]):
        """Update all display widgets with analysis results."""
        # Summary panel
        self.summary_panel.update_metrics(analysis.get("summary"))

        # Decomposition panels
        self.decomposition_panel.update_factor_ctev(analysis.get("ctev_by_factor"))
        self.decomposition_panel.update_sector_ctev(analysis.get("ctev_by_sector"))
        self.decomposition_panel.update_security_ctev(analysis.get("top_securities"))

        # Security table
        self.security_table.set_data(analysis.get("security_risks", {}))

    def _clear_displays(self):
        """Clear all display widgets."""
        self.summary_panel.clear_metrics()
        self.decomposition_panel.clear_all()
        self.security_table.clear_data()

    def _show_loading_overlay(self, message: str = "Loading..."):
        """Show loading overlay."""
        if self._loading_overlay is None:
            self._loading_overlay = LoadingOverlay(self, self.theme_manager, message)
        else:
            self._loading_overlay.set_message(message)
        self._loading_overlay.show()
        QApplication.processEvents()

    def _hide_loading_overlay(self):
        """Hide loading overlay."""
        if self._loading_overlay:
            self._loading_overlay.hide()

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
        elif theme == "bloomberg":
            bg_color = "#000814"
        else:  # dark
            bg_color = "#1e1e1e"

        self.setStyleSheet(f"""
            RiskAnalyticsModule {{
                background-color: {bg_color};
            }}
            QScrollArea {{
                background-color: {bg_color};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {bg_color};
            }}
        """)
