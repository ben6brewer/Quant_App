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
from app.utils.market_hours import is_crypto_ticker

from .services.risk_analytics_service import RiskAnalyticsService
from .services.risk_analytics_settings_manager import RiskAnalyticsSettingsManager
from app.services.ticker_metadata_service import TickerMetadataService
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
        self._current_benchmark: str = "IWV"
        self._current_etf_benchmark: str = "IWV"
        self._portfolio_list: List[str] = []
        self._current_weights: Dict[str, float] = {}
        self._current_ticker_returns: Optional["pd.DataFrame"] = None
        self._benchmark_holdings: Optional[Dict] = None  # Cached ETF holdings
        self._benchmark_weights_normalized: Dict[str, float] = {}  # Renormalized benchmark weights
        self._period_start: str = ""
        self._period_end: str = ""

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
            self.controls.set_etf_benchmark(default_benchmark)
            self._current_benchmark = default_benchmark

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup the module UI.

        New layout (Bloomberg-style):
        ┌─────────────────────────────────────┐
        │ Controls (Portfolio, Benchmark)     │
        ├─────────────────────────────────────┤
        │ Risk Summary │ Top CTEV panels (3)  │  ← ALWAYS VISIBLE
        ├─────────────────────────────────────┤
        │ Idiosyncratic Risk Table            │  ← SECURITY TABLE
        └─────────────────────────────────────┘
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = RiskAnalyticsControls(self.theme_manager)
        layout.addWidget(self.controls)

        # Scroll area for main content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        # Top section: Risk Summary + 3 CTEV panels (always visible)
        top_row = QWidget()
        top_row.setFixedHeight(280)
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(20)

        self.summary_panel = RiskSummaryPanel(self.theme_manager)
        top_row_layout.addWidget(self.summary_panel, stretch=1)

        self.decomposition_panel = RiskDecompositionPanel(self.theme_manager)
        top_row_layout.addWidget(self.decomposition_panel, stretch=3)

        content_layout.addWidget(top_row)

        # Bottom section: Idiosyncratic Risk Table
        self.security_table = SecurityRiskTable(self.theme_manager)
        content_layout.addWidget(self.security_table, stretch=1)

        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

    def _connect_signals(self):
        """Connect signals to slots."""
        # Controls signals
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.etf_benchmark_changed.connect(self._on_etf_benchmark_changed)
        self.controls.analyze_clicked.connect(self._update_risk_analysis)
        self.controls.settings_clicked.connect(self._show_settings_dialog)

        # Theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _on_etf_benchmark_changed(self, etf_symbol: str):
        """Handle ETF benchmark selection change."""
        self._current_etf_benchmark = etf_symbol

    def _refresh_portfolio_list(self):
        """Refresh the portfolio dropdown."""
        self._portfolio_list = PortfolioDataService.list_portfolios_by_recent()
        self.controls.update_portfolio_list(self._portfolio_list, self._current_portfolio)

    def _get_crypto_tickers_in_portfolio(self, portfolio_name: str) -> List[str]:
        """
        Check if a portfolio contains any cryptocurrency tickers.

        Args:
            portfolio_name: Name of the portfolio to check

        Returns:
            List of crypto ticker symbols found in the portfolio (empty if none)
        """
        tickers = PortfolioDataService.get_tickers(portfolio_name)
        if not tickers:
            return []

        crypto_tickers = []
        for ticker in tickers:
            if ticker and is_crypto_ticker(ticker):
                crypto_tickers.append(ticker)

        return crypto_tickers

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio selection change (just update state, don't analyze)."""
        # Strip "[Port] " prefix if present
        if name.startswith("[Port] "):
            name = name[7:]

        if name == self._current_portfolio:
            return

        # Check if portfolio contains crypto tickers
        crypto_tickers = self._get_crypto_tickers_in_portfolio(name)
        if crypto_tickers:
            # Block signals before showing dialog to prevent re-trigger
            self.controls.portfolio_combo.blockSignals(True)
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Crypto Not Supported",
                f"Risk Analytics does not support cryptocurrency tickers.\n\n"
                f"Portfolio '{name}' contains: {', '.join(crypto_tickers[:5])}"
                f"{'...' if len(crypto_tickers) > 5 else ''}\n\n"
                f"Please select a portfolio without crypto holdings.",
            )
            # Reset the dropdown to previous value
            self.controls.update_portfolio_list(self._portfolio_list, self._current_portfolio)
            self.controls.portfolio_combo.blockSignals(False)
            return

        self._current_portfolio = name

        # Reset universe sectors to include all sectors from new portfolio
        self.settings_manager.update_settings({"portfolio_universe_sectors": None})

    def _show_settings_dialog(self):
        """Show the settings dialog."""
        current_settings = self.settings_manager.get_all_settings()

        # Get current portfolio tickers for validation
        portfolio_tickers = []
        if self._current_portfolio:
            portfolio_tickers = [
                t.upper() for t in PortfolioDataService.get_tickers(self._current_portfolio)
            ]

        dialog = RiskAnalyticsSettingsDialog(
            self.theme_manager, current_settings, portfolio_tickers, self
        )
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, settings: Dict[str, Any]):
        """Handle settings saved from dialog."""
        self.settings_manager.update_settings(settings)
        # Auto-reanalyze if we have already run analysis
        if self._current_portfolio:
            self._update_risk_analysis()

    def _update_risk_analysis(self):
        """Run risk analysis and update all displays."""
        # Get current selections from controls (user might not have triggered change signals)
        portfolio_value = self.controls.get_current_portfolio()

        # Strip "[Port] " prefix if present
        if portfolio_value.startswith("[Port] "):
            self._current_portfolio = portfolio_value[7:]
        else:
            self._current_portfolio = portfolio_value

        # Get ETF benchmark for attribution
        self._current_etf_benchmark = self.controls.get_current_etf_benchmark()
        self._current_benchmark = self._current_etf_benchmark  # Use ETF as benchmark

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
                "Please select a benchmark ETF.",
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

            # Batch fetch current prices for weight calculation (Polygon-first for speed)
            from app.services.market_data import fetch_price_history_batch_polygon_first

            batch_data = fetch_price_history_batch_polygon_first(tickers_list)
            current_prices = {}
            for ticker in tickers_list:
                if ticker in batch_data:
                    df = batch_data[ticker]
                    if df is not None and not df.empty:
                        current_prices[ticker] = df["Close"].iloc[-1]

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

            # Filter by portfolio universe sectors if specified
            from .services.sector_override_service import SectorOverrideService

            universe_sectors = self.settings_manager.get_setting("portfolio_universe_sectors")
            if universe_sectors:
                # Filter tickers to only those in allowed sectors
                allowed_sectors = set(universe_sectors)
                filtered_tickers = []
                filtered_weights = {}

                for ticker in tickers:
                    sector = SectorOverrideService.get_effective_sector(ticker)
                    if sector in allowed_sectors:
                        filtered_tickers.append(ticker)
                        filtered_weights[ticker] = weights[ticker]

                if not filtered_tickers:
                    self._hide_loading_overlay()
                    self._clear_displays()
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "No Holdings in Universe",
                        f"No holdings in '{self._current_portfolio}' match the selected "
                        f"portfolio universe sectors.",
                    )
                    return

                # Renormalize weights to sum to 1.0
                total_weight = sum(filtered_weights.values())
                if total_weight > 0:
                    filtered_weights = {
                        t: w / total_weight for t, w in filtered_weights.items()
                    }

                tickers = filtered_tickers
                weights = filtered_weights

            # Get lookback settings (either lookback_days or custom date range)
            lookback_days = self.settings_manager.get_setting("lookback_days")
            custom_start_date = self.settings_manager.get_setting("custom_start_date")
            custom_end_date = self.settings_manager.get_setting("custom_end_date")

            # Get portfolio returns using TIME-VARYING weights from transaction history
            # This correctly accounts for when each holding was actually purchased/sold
            portfolio_returns = ReturnsDataService.get_time_varying_portfolio_returns(
                self._current_portfolio, include_cash=False
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

            # Apply date filtering
            portfolio_returns = self._filter_returns_by_period(
                portfolio_returns, lookback_days, custom_start_date, custom_end_date
            )

            # Clip any extreme portfolio returns (>50% daily is extreme)
            extreme_port = (portfolio_returns.abs() > 0.5).sum()
            if extreme_port > 0:
                print(f"[RiskAnalysis] Clipping {extreme_port} extreme portfolio return days")
                portfolio_returns = portfolio_returns.clip(lower=-0.5, upper=0.5)

            # Get benchmark returns
            benchmark_returns = self._get_benchmark_returns(
                lookback_days, custom_start_date, custom_end_date
            )

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

            # Normalize indices to date-only (remove time component) to ensure alignment
            # This fixes timezone mismatches between portfolio and benchmark data sources
            portfolio_returns.index = portfolio_returns.index.normalize()
            benchmark_returns.index = benchmark_returns.index.normalize()

            # Remove any duplicate indices created by normalization (keep last value)
            if portfolio_returns.index.duplicated().any():
                portfolio_returns = portfolio_returns[~portfolio_returns.index.duplicated(keep="last")]
            if benchmark_returns.index.duplicated().any():
                benchmark_returns = benchmark_returns[~benchmark_returns.index.duplicated(keep="last")]

            # DEBUG: Print return statistics to diagnose tracking error issues
            print(f"[DEBUG] Portfolio returns: len={len(portfolio_returns)}, mean={portfolio_returns.mean():.6f}, std={portfolio_returns.std():.6f}")
            print(f"[DEBUG] Portfolio date range: {portfolio_returns.index.min()} to {portfolio_returns.index.max()}")
            print(f"[DEBUG] Benchmark returns: len={len(benchmark_returns)}, mean={benchmark_returns.mean():.6f}, std={benchmark_returns.std():.6f}")
            print(f"[DEBUG] Benchmark date range: {benchmark_returns.index.min()} to {benchmark_returns.index.max()}")
            # Check overlap
            common_dates = portfolio_returns.index.intersection(benchmark_returns.index)
            print(f"[DEBUG] Common dates: {len(common_dates)}")

            # Get individual ticker returns for CTEV calculation
            ticker_returns = self._get_ticker_returns(
                tickers, lookback_days, custom_start_date, custom_end_date
            )

            # Also fetch returns for ALL benchmark tickers NOT in portfolio
            # These are needed to show underweight positions (negative active weight)
            if self._benchmark_holdings:
                import pandas as pd

                # Get all benchmark tickers not in portfolio
                portfolio_set = set(t.upper() for t in tickers)
                benchmark_only_tickers = [
                    ticker
                    for ticker in self._benchmark_holdings.keys()
                    if ticker.upper() not in portfolio_set
                ]

                if benchmark_only_tickers:
                    print(f"[RiskAnalysis] Fetching returns for {len(benchmark_only_tickers)} benchmark-only tickers")
                    benchmark_ticker_returns = self._get_ticker_returns(
                        benchmark_only_tickers, lookback_days, custom_start_date, custom_end_date
                    )

                    # Merge with portfolio ticker returns
                    if not benchmark_ticker_returns.empty:
                        # Ensure indices are aligned
                        if not ticker_returns.empty:
                            ticker_returns = pd.concat(
                                [ticker_returns, benchmark_ticker_returns], axis=1
                            )
                            # Remove any duplicate columns
                            ticker_returns = ticker_returns.loc[:, ~ticker_returns.columns.duplicated()]
                        else:
                            ticker_returns = benchmark_ticker_returns

            # If universe filtering is active, recalculate portfolio returns from filtered tickers
            if universe_sectors and not ticker_returns.empty:
                import pandas as pd

                # Calculate weighted portfolio returns from filtered ticker returns
                filtered_portfolio_returns = pd.Series(0.0, index=ticker_returns.index)
                for ticker in tickers:
                    if ticker in ticker_returns.columns:
                        weight = weights.get(ticker, 0.0)
                        filtered_portfolio_returns += ticker_returns[ticker] * weight

                # Use filtered returns instead of full portfolio returns
                portfolio_returns = filtered_portfolio_returns.dropna()

                if portfolio_returns.empty:
                    self._hide_loading_overlay()
                    self._clear_displays()
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "No Returns Data",
                        "Could not calculate returns for the filtered portfolio universe.",
                    )
                    return

            # Store data for attribution analysis
            self._current_weights = weights
            self._current_ticker_returns = ticker_returns
            # Use portfolio_returns for period dates (it's filtered to lookback period)
            if not portfolio_returns.empty:
                self._period_start = portfolio_returns.index.min().strftime("%Y-%m-%d")
                self._period_end = portfolio_returns.index.max().strftime("%Y-%m-%d")
            print(f"[RiskAnalysis] Stored {len(weights)} weights and returns with shape {ticker_returns.shape}")
            print(f"[RiskAnalysis] Attribution period: {self._period_start} to {self._period_end}")

            # Use renormalized benchmark weights (calculated in _get_benchmark_returns)
            # These are already normalized to sum to 1.0 for the filtered universe
            benchmark_weights = getattr(self, '_benchmark_weights_normalized', {})
            if not benchmark_weights and self._benchmark_holdings:
                # Fallback: calculate from holdings if not already computed
                total_weight = sum(h.weight for h in self._benchmark_holdings.values())
                if total_weight > 0:
                    benchmark_weights = {
                        ticker.upper(): holding.weight / total_weight
                        for ticker, holding in self._benchmark_holdings.items()
                    }

            # Build ticker price data dict for constructed factors
            # Combine portfolio and benchmark price data
            ticker_price_data = {}
            for ticker in ticker_returns.columns:
                ticker_upper = ticker.upper()
                if ticker in batch_data and batch_data[ticker] is not None:
                    ticker_price_data[ticker_upper] = batch_data[ticker]
                elif ticker_upper in batch_data and batch_data[ticker_upper] is not None:
                    ticker_price_data[ticker_upper] = batch_data[ticker_upper]

            # Run full analysis (pass benchmark weights and price data for factor model)
            analysis = RiskAnalyticsService.get_full_analysis(
                portfolio_returns,
                benchmark_returns,
                ticker_returns,
                tickers,
                weights,
                benchmark_weights,
                ticker_price_data,
            )

            # Update displays (pass benchmark weights to table)
            self._update_displays(analysis, benchmark_weights)

        except Exception as e:
            CustomMessageBox.critical(
                self.theme_manager,
                self,
                "Analysis Error",
                f"Error running risk analysis: {str(e)}",
            )
        finally:
            self._hide_loading_overlay()

    def _filter_returns_by_period(
        self,
        returns: "pd.Series",
        lookback_days: Optional[int],
        custom_start_date: Optional[str],
        custom_end_date: Optional[str],
    ) -> "pd.Series":
        """
        Filter returns by either lookback period or custom date range.

        Args:
            returns: Series of returns with DatetimeIndex
            lookback_days: Number of trading days to look back (or None for custom)
            custom_start_date: Start date string (YYYY-MM-DD) for custom range
            custom_end_date: End date string (YYYY-MM-DD) for custom range

        Returns:
            Filtered returns series
        """
        if returns is None or returns.empty:
            return returns

        if lookback_days is None and custom_start_date and custom_end_date:
            # Custom date range - filter by dates
            import pandas as pd

            start = pd.Timestamp(custom_start_date)
            end = pd.Timestamp(custom_end_date)
            return returns[(returns.index >= start) & (returns.index <= end)]
        elif lookback_days is not None:
            # Standard lookback period - take last N days
            if len(returns) > lookback_days:
                return returns.iloc[-lookback_days:]
        return returns

    def _get_benchmark_returns(
        self,
        lookback_days: Optional[int],
        custom_start_date: Optional[str] = None,
        custom_end_date: Optional[str] = None,
    ) -> Optional["pd.Series"]:
        """
        Get benchmark returns calculated from constituent-weighted returns.

        Instead of fetching the ETF ticker, this fetches all constituent
        holdings and calculates weighted daily returns for accuracy.
        """
        import pandas as pd
        from app.services.ishares_holdings_service import ISharesHoldingsService
        from app.services.market_data import fetch_price_history_batch_polygon_first
        from app.services.ticker_metadata_service import TickerMetadataService

        benchmark = self._current_benchmark

        if not benchmark:
            return None

        # Fetch ETF holdings (e.g., IWV has ~3000 constituents)
        print(f"[Benchmark] Fetching {benchmark} holdings for constituent-weighted returns...")
        holdings = ISharesHoldingsService.fetch_holdings(benchmark)
        if not holdings:
            print(f"[Benchmark] Could not fetch holdings for {benchmark}")
            return None

        print(f"[Benchmark] Got {len(holdings)} constituents")

        # Cache metadata from ETF holdings (sector, name, etc.)
        TickerMetadataService.cache_from_etf_holdings(holdings)

        # Apply benchmark universe sector filter if set
        benchmark_universe_sectors = self.settings_manager.get_setting("benchmark_universe_sectors")
        if benchmark_universe_sectors:
            sector_set = set(benchmark_universe_sectors)
            filtered_holdings = {
                ticker: holding
                for ticker, holding in holdings.items()
                if holding.sector in sector_set
            }
            if not filtered_holdings:
                print(f"[Benchmark] No holdings match selected benchmark universe sectors")
                return None
            print(f"[Benchmark] Filtered to {len(filtered_holdings)} constituents in selected sectors")
            holdings = filtered_holdings

        # Store holdings for later use (filtered if applicable)
        self._benchmark_holdings = holdings

        # Calculate and store renormalized benchmark weights (sum to 1.0)
        total_benchmark_weight = sum(h.weight for h in holdings.values())
        if total_benchmark_weight > 0:
            self._benchmark_weights_normalized = {
                ticker.upper(): holding.weight / total_benchmark_weight
                for ticker, holding in holdings.items()
            }
        else:
            self._benchmark_weights_normalized = {}

        # Get all constituent tickers
        constituent_tickers = list(holdings.keys())

        # Fetch price data for all constituents (Polygon-first)
        print(f"[Benchmark] Fetching price data for {len(constituent_tickers)} constituents...")
        batch_data = fetch_price_history_batch_polygon_first(constituent_tickers)

        # Calculate individual returns for each constituent
        # Filter out extreme returns (>100% or <-100%) which are likely data errors
        constituent_returns = {}
        outlier_count = 0
        for ticker, holding in holdings.items():
            if ticker in batch_data and batch_data[ticker] is not None:
                df = batch_data[ticker]
                if not df.empty:
                    returns = df["Close"].pct_change().dropna()
                    if not returns.empty:
                        # Clip extreme returns - daily moves >100% are almost certainly data errors
                        extreme_mask = (returns > 1.0) | (returns < -1.0)
                        if extreme_mask.any():
                            outlier_count += extreme_mask.sum()
                            returns = returns.clip(lower=-1.0, upper=1.0)
                        constituent_returns[ticker] = returns

        if outlier_count > 0:
            print(f"[Benchmark] Clipped {outlier_count} extreme return values (>100% daily)")

        if not constituent_returns:
            print(f"[Benchmark] No valid returns data for constituents")
            return None

        print(f"[Benchmark] Got returns for {len(constituent_returns)} constituents")

        # Create DataFrame of constituent returns
        returns_df = pd.DataFrame(constituent_returns)

        # Normalize index to date-only and remove duplicates
        returns_df.index = returns_df.index.normalize()
        if returns_df.index.duplicated().any():
            returns_df = returns_df[~returns_df.index.duplicated(keep="last")]

        # Calculate weighted benchmark returns
        # Weight = holding.weight (already as decimal, e.g., 0.05 = 5%)
        weights = {ticker: holdings[ticker].weight for ticker in returns_df.columns}

        # Normalize weights to sum to 1.0 (in case some constituents are missing)
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {t: w / total_weight for t, w in weights.items()}

        # Calculate weighted daily returns
        benchmark_returns = pd.Series(0.0, index=returns_df.index)
        for ticker in returns_df.columns:
            weight = weights.get(ticker, 0.0)
            benchmark_returns += returns_df[ticker].fillna(0) * weight

        benchmark_returns = benchmark_returns.dropna()

        if benchmark_returns.empty:
            print(f"[Benchmark] Weighted returns calculation produced empty result")
            return None

        # Final sanity check - clip any remaining extreme values in weighted returns
        extreme_weighted = (benchmark_returns.abs() > 0.5).sum()  # >50% daily is extreme for an index
        if extreme_weighted > 0:
            print(f"[Benchmark] Warning: {extreme_weighted} days with >50% weighted return, clipping")
            benchmark_returns = benchmark_returns.clip(lower=-0.5, upper=0.5)

        print(f"[Benchmark] Calculated constituent-weighted returns: {len(benchmark_returns)} days")

        # Apply date filtering
        return self._filter_returns_by_period(
            benchmark_returns, lookback_days, custom_start_date, custom_end_date
        )

    def _get_ticker_returns(
        self,
        tickers: List[str],
        lookback_days: Optional[int],
        custom_start_date: Optional[str] = None,
        custom_end_date: Optional[str] = None,
    ) -> "pd.DataFrame":
        """Get returns for individual tickers."""
        import pandas as pd
        from app.services.market_data import fetch_price_history_batch_polygon_first

        # Batch fetch all tickers at once (Polygon-first for speed)
        batch_data = fetch_price_history_batch_polygon_first(tickers)

        returns_dict = {}
        outlier_count = 0
        for ticker in tickers:
            if ticker not in batch_data:
                continue
            df = batch_data[ticker]
            if df is not None and not df.empty:
                returns = df["Close"].pct_change().dropna()
                # Clip extreme returns (>100% daily is likely data error)
                extreme_mask = (returns > 1.0) | (returns < -1.0)
                if extreme_mask.any():
                    outlier_count += extreme_mask.sum()
                    returns = returns.clip(lower=-1.0, upper=1.0)
                # Apply date filtering
                returns = self._filter_returns_by_period(
                    returns, lookback_days, custom_start_date, custom_end_date
                )
                if returns is not None and not returns.empty:
                    returns_dict[ticker] = returns

        if outlier_count > 0:
            print(f"[RiskAnalysis] Clipped {outlier_count} extreme ticker return values")

        if not returns_dict:
            return pd.DataFrame()

        # Combine into DataFrame, aligning by date
        # Use dropna(how='all') to only remove rows where ALL values are NaN
        # This preserves more data when tickers have different trading histories
        df = pd.DataFrame(returns_dict)

        # Normalize index to date-only and remove duplicates
        df.index = df.index.normalize()
        if df.index.duplicated().any():
            df = df[~df.index.duplicated(keep="last")]

        df = df.dropna(how='all')  # Remove rows with all NaN
        df = df.ffill().bfill()    # Forward/backward fill remaining NaN
        return df

    def _update_displays(
        self,
        analysis: Dict[str, Any],
        benchmark_weights: Optional[Dict[str, float]] = None,
    ):
        """Update all display widgets with analysis results."""
        # Summary panel
        self.summary_panel.update_metrics(analysis.get("summary"))

        # Decomposition panels
        # Filter out Currency factor if setting is disabled
        ctev_by_factor = analysis.get("ctev_by_factor", {})
        show_currency = self.settings_manager.get_setting("show_currency_factor")
        if not show_currency and "Currency" in ctev_by_factor:
            ctev_by_factor = {k: v for k, v in ctev_by_factor.items() if k != "Currency"}

        self.decomposition_panel.update_factor_ctev(ctev_by_factor)
        self.decomposition_panel.update_sector_ctev(analysis.get("ctev_by_sector"))
        self.decomposition_panel.update_security_ctev(analysis.get("top_securities"))

        # Security table (pass benchmark weights, regression results, and factor contributions)
        self.security_table.set_data(
            analysis.get("security_risks", {}),
            benchmark_weights,
            analysis.get("regression_results"),
            analysis.get("factor_contributions"),
        )

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
