"""Performance Metrics Module - Bloomberg-style performance statistics table."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QApplication
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.services.returns_data_service import ReturnsDataService
from app.ui.widgets.common.custom_message_box import CustomMessageBox
from app.ui.widgets.common.loading_overlay import LoadingOverlay
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

from .services.performance_metrics_service import PerformanceMetricsService
from .services.performance_metrics_settings_manager import PerformanceMetricsSettingsManager
from .widgets.performance_metrics_controls import PerformanceMetricsControls
from .widgets.performance_metrics_table import PerformanceMetricsTable
from .widgets.performance_metrics_settings_dialog import PerformanceMetricsSettingsDialog

if TYPE_CHECKING:
    import pandas as pd


class PerformanceMetricsModule(LazyThemeMixin, QWidget):
    """
    Performance Metrics module.

    Displays comprehensive portfolio statistics across multiple time periods
    with optional benchmark comparison, in a Bloomberg terminal style.
    """

    # Signal emitted when user clicks home button
    home_clicked = Signal()

    # Time period definitions: (name, trading_days or None for YTD)
    TIME_PERIODS = [
        ("3 Months", 63),
        ("6 Months", 126),
        ("12 Months", 252),
        ("YTD", None),
    ]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        # Settings manager
        self.settings_manager = PerformanceMetricsSettingsManager()

        # Current state
        self._current_portfolio: str = ""
        self._is_ticker_mode: bool = False
        self._current_benchmark: str = ""
        self._is_benchmark_portfolio: bool = False
        self._portfolio_list: list = []

        # Loading overlay
        self._loading_overlay = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Apply saved column visibility settings
        settings = self.settings_manager.get_all_settings()
        self.table.set_visible_periods(
            settings.get("show_3_months", True),
            settings.get("show_6_months", True),
            settings.get("show_12_months", True),
            settings.get("show_ytd", True),
        )

        # Load portfolio list
        self._refresh_portfolio_list()

    def _setup_ui(self):
        """Setup the module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = PerformanceMetricsControls(self.theme_manager)
        layout.addWidget(self.controls)

        # Container for centering the table horizontally
        self.table_container = QWidget()
        table_layout = QHBoxLayout(self.table_container)
        table_layout.setContentsMargins(20, 20, 20, 20)

        # Add stretch on left to center
        table_layout.addStretch(1)

        # Metrics table
        self.table = PerformanceMetricsTable(self.theme_manager)
        table_layout.addWidget(self.table)

        # Add stretch on right to center
        table_layout.addStretch(1)

        layout.addWidget(self.table_container, stretch=1)

    def _connect_signals(self):
        """Connect signals to slots."""
        # Controls signals
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.benchmark_changed.connect(self._on_benchmark_changed)
        self.controls.settings_clicked.connect(self._show_settings_dialog)

        # Theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def _refresh_portfolio_list(self):
        """Refresh the portfolio dropdown and benchmark dropdown."""
        self._portfolio_list = PortfolioDataService.list_portfolios_by_recent()
        self.controls.update_portfolio_list(self._portfolio_list, self._current_portfolio)
        self.controls.update_benchmark_list(self._portfolio_list)

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio/ticker selection change."""
        # Strip "[Port] " prefix if present
        if name.startswith("[Port] "):
            name = name[7:]

        if name == self._current_portfolio:
            return

        self._current_portfolio = name
        # Check if this is a portfolio or a ticker
        self._is_ticker_mode = name not in self._portfolio_list
        self._update_metrics()

    def _on_benchmark_changed(self, benchmark: str):
        """Handle benchmark selection change."""
        if benchmark == self._current_benchmark:
            return

        self._current_benchmark = benchmark

        # Determine if benchmark is a portfolio
        if benchmark:
            self._is_benchmark_portfolio = benchmark.startswith("[Port] ")
        else:
            self._is_benchmark_portfolio = False

        # Update table structure
        self.table.set_has_benchmark(bool(benchmark))
        self._update_metrics()

    def _show_settings_dialog(self):
        """Show the settings dialog."""
        current_settings = self.settings_manager.get_all_settings()
        dialog = PerformanceMetricsSettingsDialog(
            self.theme_manager, current_settings, self
        )
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, settings: Dict[str, Any]):
        """Handle settings saved from dialog."""
        self.settings_manager.update_settings(settings)
        # Apply column visibility settings
        self.table.set_visible_periods(
            settings.get("show_3_months", True),
            settings.get("show_6_months", True),
            settings.get("show_12_months", True),
            settings.get("show_ytd", True),
        )
        # Only recalculate if a portfolio is selected
        if self._current_portfolio:
            self._update_metrics()

    def _update_metrics(self):
        """Update the metrics table with current settings."""
        if not self._current_portfolio:
            self.table.show_placeholder("Select a portfolio or enter a ticker")
            return

        # Show loading overlay
        self._show_loading_overlay("Calculating metrics...")

        try:
            # Get risk-free rate from settings
            settings = self.settings_manager.get_all_settings()
            if settings.get("risk_free_source") == "manual":
                risk_free_rate = settings.get("manual_risk_free_rate", 0.05)
            else:
                risk_free_rate = PerformanceMetricsService.get_risk_free_rate()

            # Pre-calculate all date ranges to find the earliest start date
            date_ranges: Dict[str, Tuple[str, str]] = {}
            for period_name, trading_days in self.TIME_PERIODS:
                date_ranges[period_name] = self._get_date_range(trading_days)

            # Find the earliest start date across all periods
            earliest_start = min(dr[0] for dr in date_ranges.values())
            end_date = datetime.now().strftime("%Y-%m-%d")

            # Fetch portfolio returns ONCE for the full range
            full_portfolio_returns = self._get_returns(
                self._current_portfolio,
                self._is_ticker_mode,
                earliest_start,
                end_date,
            )

            if full_portfolio_returns is None or full_portfolio_returns.empty:
                self.table.show_placeholder("No data available for selected portfolio")
                return

            # Fetch benchmark returns ONCE for the full range (if selected)
            full_benchmark_returns = None
            benchmark_failed = False
            if self._current_benchmark:
                benchmark_name = self._current_benchmark
                is_portfolio = self._is_benchmark_portfolio

                if is_portfolio:
                    # Remove "[Port] " prefix
                    benchmark_name = benchmark_name.replace("[Port] ", "")

                full_benchmark_returns = self._get_returns(
                    benchmark_name,
                    not is_portfolio,  # is_ticker = not is_portfolio
                    earliest_start,
                    end_date,
                )

                # Check if benchmark data was loaded successfully
                if full_benchmark_returns is None or full_benchmark_returns.empty:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Benchmark Not Found",
                        f"Could not load data for benchmark '{self._current_benchmark}'. "
                        "Please check the ticker symbol.",
                    )
                    self._current_benchmark = ""
                    self.controls.reset_benchmark()
                    self.table.set_has_benchmark(False)
                    full_benchmark_returns = None
                    benchmark_failed = True

            # Calculate metrics for each time period by filtering pre-fetched data
            metrics_by_period: Dict[str, Dict[str, Any]] = {}

            for period_name, trading_days in self.TIME_PERIODS:
                start_date, period_end = date_ranges[period_name]

                # Filter portfolio returns by date range
                portfolio_returns = self._filter_returns_by_date(
                    full_portfolio_returns, start_date, period_end
                )

                if portfolio_returns is None or portfolio_returns.empty:
                    # Skip this period if no data
                    metrics_by_period[period_name] = {}
                    continue

                # Filter benchmark returns by date range
                benchmark_returns = None
                if full_benchmark_returns is not None:
                    benchmark_returns = self._filter_returns_by_date(
                        full_benchmark_returns, start_date, period_end
                    )

                # Calculate all metrics for this period
                metrics = PerformanceMetricsService.calculate_all_metrics(
                    portfolio_returns,
                    benchmark_returns,
                    risk_free_rate,
                )

                metrics_by_period[period_name] = metrics

            # Update table
            self.table.update_metrics(metrics_by_period)

        except Exception as e:
            print(f"Error calculating metrics: {e}")
            import traceback
            traceback.print_exc()
            self.table.show_placeholder(f"Error loading data: {str(e)}")

        finally:
            self._hide_loading_overlay()

    def _filter_returns_by_date(
        self,
        returns: "pd.Series",
        start_date: str,
        end_date: str,
    ) -> "pd.Series":
        """
        Filter a returns series by date range.

        Args:
            returns: Series of returns with DatetimeIndex
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Filtered returns series
        """
        import pandas as pd

        if returns is None or returns.empty:
            return returns

        # Ensure datetime index
        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)

        # Filter by date range
        mask = (returns.index >= start_date) & (returns.index <= end_date)
        return returns[mask]

    def _get_date_range(self, trading_days: Optional[int]) -> Tuple[str, str]:
        """
        Get start and end date for a time period.

        Args:
            trading_days: Number of trading days, or None for YTD

        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        end_date = datetime.now().strftime("%Y-%m-%d")

        if trading_days is None:
            # YTD: From January 1 of current year
            start_date = f"{datetime.now().year}-01-01"
        else:
            # Approximate calendar days from trading days
            # (252 trading days ≈ 365 calendar days)
            calendar_days = int(trading_days * 365 / 252)
            start = datetime.now() - timedelta(days=calendar_days)
            start_date = start.strftime("%Y-%m-%d")

        return start_date, end_date

    def _get_returns(
        self,
        name: str,
        is_ticker: bool,
        start_date: str,
        end_date: str,
    ) -> "pd.Series":
        """
        Get returns for a portfolio or ticker.

        Automatically appends today's live return if within market hours
        (for stocks) or anytime (for crypto).

        Args:
            name: Portfolio name or ticker symbol
            is_ticker: True if name is a ticker, False if portfolio
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Series of daily returns (with today's live return appended if eligible)
        """
        if is_ticker:
            returns = ReturnsDataService.get_ticker_returns(
                name,
                start_date=start_date,
                end_date=end_date,
                interval="daily",
            )
            # Append today's live return if eligible
            returns = ReturnsDataService.append_live_return(returns, name)
        else:
            returns = ReturnsDataService.get_time_varying_portfolio_returns(
                name,
                start_date=start_date,
                end_date=end_date,
                include_cash=False,
                interval="daily",
            )
            # Append today's live portfolio return if eligible
            returns = ReturnsDataService.append_live_portfolio_return(
                returns, name, include_cash=False
            )

        return returns

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
        elif theme == "bloomberg":
            bg_color = "#000814"
        else:
            bg_color = "#1e1e1e"

        self.setStyleSheet(f"""
            PerformanceMetricsModule {{ background-color: {bg_color}; }}
            QWidget {{ background-color: {bg_color}; }}
        """)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _show_loading_overlay(self, message: str = "Loading..."):
        """Show loading overlay over the entire module."""
        # Hide table container to prevent painting over overlay
        self.table_container.hide()

        if self._loading_overlay is None:
            self._loading_overlay = LoadingOverlay(self, self.theme_manager, message)
        else:
            self._loading_overlay.set_message(message)

        # Cover the entire module
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.show()
        self._loading_overlay.raise_()
        self._loading_overlay.repaint()
        QApplication.processEvents()

    def _hide_loading_overlay(self):
        """Hide and cleanup loading overlay."""
        if self._loading_overlay is not None:
            self._loading_overlay.hide()
            self._loading_overlay.deleteLater()
            self._loading_overlay = None

        # Show table container again
        self.table_container.show()

    def refresh(self):
        """Refresh the module (called when navigating back)."""
        self._refresh_portfolio_list()
        if self._current_portfolio:
            self._update_metrics()
