"""Return Distribution Module - Histogram visualization of portfolio returns."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.services.portfolio_data_service import PortfolioDataService
from app.services.returns_data_service import ReturnsDataService
from app.ui.widgets.common.custom_message_box import CustomMessageBox
from app.ui.widgets.common.loading_overlay import LoadingOverlay
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin

from .services.distribution_settings_manager import DistributionSettingsManager
from .widgets.distribution_controls import DistributionControls
from .widgets.distribution_chart import DistributionChart
from .widgets.distribution_settings_dialog import DistributionSettingsDialog
from .widgets.date_range_dialog import DateRangeDialog


class ReturnDistributionModule(LazyThemeMixin, QWidget):
    """
    Portfolio Return Distribution module.

    Displays a histogram of portfolio returns with statistical analysis.
    Supports time-varying weights based on transaction history.
    """

    # Signal emitted when user clicks home button
    home_clicked = Signal()

    # Window name to trading days mapping
    WINDOW_TO_DAYS = {
        "1 Month": 21,
        "3 Months": 63,
        "6 Months": 126,
        "1 Year": 252,
        "3 Years": 756,
        "5 Years": 1260,
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application

        # Settings manager
        self.settings_manager = DistributionSettingsManager()

        # Current state
        self._current_portfolio: str = ""  # Can be portfolio name or ticker
        self._is_ticker_mode: bool = False  # True if viewing a single ticker
        self._current_interval: str = "Daily"
        self._current_start_date: str = ""
        self._current_end_date: str = ""
        self._current_metric: str = "Returns"
        self._current_window: str = ""
        self._current_benchmark: str = ""
        self._portfolio_list: list = []  # Cache of available portfolios

        # Loading overlay (created on demand)
        self._loading_overlay = None

        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Apply initial chart settings (background, gridlines) before any data
        self._apply_initial_chart_settings()

        # Load portfolio list
        self._refresh_portfolio_list()

    def _setup_ui(self):
        """Setup the module UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Controls bar
        self.controls = DistributionControls(self.theme_manager)
        layout.addWidget(self.controls)

        # Distribution chart (histogram + stats)
        self.chart = DistributionChart(self.theme_manager)
        layout.addWidget(self.chart, stretch=1)

    def _connect_signals(self):
        """Connect signals to slots."""
        # Controls signals
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.portfolio_changed.connect(self._on_portfolio_changed)
        self.controls.metric_changed.connect(self._on_metric_changed)
        self.controls.window_changed.connect(self._on_window_changed)
        self.controls.interval_changed.connect(self._on_interval_changed)
        self.controls.date_range_changed.connect(self._on_date_range_changed)
        self.controls.custom_date_range_requested.connect(self._show_date_range_dialog)
        self.controls.settings_clicked.connect(self._show_settings_dialog)
        self.controls.benchmark_changed.connect(self._on_benchmark_changed)

        # Theme changes (lazy - only apply when visible)
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
        self._update_distribution()

    def _on_metric_changed(self, metric: str):
        """Handle metric selection change."""
        if metric == self._current_metric:
            return

        self._current_metric = metric
        # Update chart labels before updating data
        self.chart.set_metric(metric)
        self._update_distribution()

    def _on_window_changed(self, window: str):
        """Handle window selection change for rolling metrics."""
        if window == self._current_window:
            return

        self._current_window = window
        self._update_distribution()

    def _on_interval_changed(self, interval: str):
        """Handle interval selection change."""
        if interval == self._current_interval:
            return

        self._current_interval = interval
        self._update_distribution()

    def _on_date_range_changed(self, start_date: str, end_date: str):
        """Handle date range change."""
        self._current_start_date = start_date
        self._current_end_date = end_date
        self._update_distribution()

    def _on_benchmark_changed(self, benchmark: str):
        """Handle benchmark selection change."""
        self._current_benchmark = benchmark
        self._update_distribution()

    def _show_date_range_dialog(self):
        """Show the custom date range dialog."""
        dialog = DateRangeDialog(self.theme_manager, self)
        if dialog.exec():
            start_date, end_date = dialog.get_date_range()
            if start_date and end_date:
                self.controls.set_custom_date_range(start_date, end_date)

    def _show_settings_dialog(self):
        """Show the settings dialog."""
        current_settings = self.settings_manager.get_all_settings()
        has_benchmark = bool(self._current_benchmark)
        dialog = DistributionSettingsDialog(
            self.theme_manager, current_settings, self, has_benchmark=has_benchmark
        )
        if dialog.exec():
            new_settings = dialog.get_settings()
            if new_settings:
                self.settings_manager.update_settings(new_settings)
                self._update_distribution()

    def _update_distribution(self):
        """Update the distribution chart with current settings."""
        # Get all settings first - we need them for both placeholder and data display
        all_settings = self.settings_manager.get_all_settings()

        if not self._current_portfolio:
            # Apply general settings even when showing placeholder
            self.chart.apply_general_settings(all_settings)
            self.chart.show_placeholder("Type a ticker or select a portfolio")
            return

        # Show loading overlay
        self._show_loading_overlay("Loading Distribution...")

        # Get exclude_cash for data fetching
        exclude_cash = all_settings.get("exclude_cash", True)
        include_cash = not exclude_cash

        # Get date range
        start_date = self._current_start_date if self._current_start_date else None
        end_date = self._current_end_date if self._current_end_date else None

        try:
            # Get data based on selected metric and mode (ticker vs portfolio)
            data = self._get_metric_data(start_date, end_date, include_cash)

            if data is None or data.empty:
                if self._is_ticker_mode:
                    # Show error for invalid ticker and reset
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Ticker Not Found",
                        f"Ticker '{self._current_portfolio}' not found or has insufficient data. Please check the symbol and try again."
                    )
                    self._current_portfolio = ""
                    self.controls.portfolio_combo.setCurrentIndex(-1)
                    self.chart.show_placeholder("Type a ticker or select a portfolio")
                else:
                    self.chart.show_placeholder(f"No {self._current_metric.lower()} data available")
                return

            # Get cash drag for portfolios (always calculate, display logic in stats panel)
            cash_drag = None
            if self._current_metric == "Returns" and not self._is_ticker_mode:
                cash_drag = ReturnsDataService.calculate_cash_drag(
                    self._current_portfolio,
                    start_date=start_date,
                    end_date=end_date,
                )

            # Get benchmark data if specified (works for all metrics)
            benchmark_returns = None
            benchmark_name = ""
            if self._current_benchmark:
                benchmark_returns, benchmark_name, error_msg = self._get_benchmark_data(
                    start_date, end_date, include_cash
                )
                # If benchmark couldn't be loaded, show error and reset to None
                if error_msg:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Benchmark Not Found",
                        error_msg
                    )
                    # Reset benchmark to None
                    self._current_benchmark = ""
                    self.controls.reset_benchmark()
                    benchmark_returns = None
                    benchmark_name = ""

            # Align portfolio and benchmark to same number of periods (trailing)
            if benchmark_returns is not None and not benchmark_returns.empty:
                min_periods = min(len(data), len(benchmark_returns))
                # Take trailing periods from both series
                data = data.iloc[-min_periods:]
                benchmark_returns = benchmark_returns.iloc[-min_periods:]

            # Update chart with all settings
            self.chart.set_returns(
                data,
                settings=all_settings,
                cash_drag=cash_drag,
                show_cash_drag=(self._current_metric == "Returns" and include_cash),
                benchmark_returns=benchmark_returns,
                benchmark_name=benchmark_name,
                portfolio_name=self._current_portfolio,
                is_ticker_mode=self._is_ticker_mode,
            )

        except Exception as e:
            print(f"Error updating distribution: {e}")
            import traceback
            traceback.print_exc()
            self.chart.show_placeholder(f"Error loading data: {str(e)}")

        finally:
            # Always hide loading overlay
            self._hide_loading_overlay()

    def _get_metric_data(self, start_date, end_date, include_cash):
        """
        Get data for the selected metric.

        Args:
            start_date: Start date for data range
            end_date: End date for data range
            include_cash: Whether to include cash in calculations

        Returns:
            pd.Series of metric values
        """
        metric = self._current_metric
        is_ticker = self._is_ticker_mode
        name = self._current_portfolio

        if metric == "Returns":
            if is_ticker:
                return ReturnsDataService.get_ticker_returns(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                    interval=self._current_interval,
                )
            else:
                return ReturnsDataService.get_time_varying_portfolio_returns(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                    interval=self._current_interval,
                )

        elif metric == "Volatility":
            if is_ticker:
                return ReturnsDataService.get_ticker_volatility(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                return ReturnsDataService.get_portfolio_volatility(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )

        elif metric == "Rolling Volatility":
            window_days = self.WINDOW_TO_DAYS.get(self._current_window, 21)
            if is_ticker:
                return ReturnsDataService.get_ticker_rolling_volatility(
                    name,
                    window_days=window_days,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                return ReturnsDataService.get_rolling_volatility(
                    name,
                    window_days=window_days,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )

        elif metric == "Drawdown":
            if is_ticker:
                return ReturnsDataService.get_ticker_drawdowns(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                return ReturnsDataService.get_drawdowns(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )

        elif metric == "Rolling Return":
            window_days = self.WINDOW_TO_DAYS.get(self._current_window, 252)
            if is_ticker:
                return ReturnsDataService.get_ticker_rolling_returns(
                    name,
                    window_days=window_days,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                return ReturnsDataService.get_rolling_returns(
                    name,
                    window_days=window_days,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )

        elif metric == "Time Under Water":
            if is_ticker:
                return ReturnsDataService.get_ticker_time_under_water(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                return ReturnsDataService.get_time_under_water(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )

        else:
            # Default to returns
            if is_ticker:
                return ReturnsDataService.get_ticker_returns(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                    interval=self._current_interval,
                )
            else:
                return ReturnsDataService.get_time_varying_portfolio_returns(
                    name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                    interval=self._current_interval,
                )

    def _get_benchmark_data(self, start_date, end_date, include_cash):
        """
        Get benchmark data for the current metric.

        Args:
            start_date: Start date for data range
            end_date: End date for data range
            include_cash: Whether to include cash in portfolio benchmark calculations

        Returns:
            Tuple of (pd.Series of metric data, benchmark name string, error message or None)
        """
        import pandas as pd

        benchmark = self._current_benchmark
        metric = self._current_metric
        is_portfolio = benchmark.startswith("[Port] ")

        if is_portfolio:
            benchmark_name = benchmark.replace("[Port] ", "")
        else:
            benchmark_name = benchmark

        try:
            data = self._get_benchmark_metric_data(
                benchmark_name, is_portfolio, start_date, end_date, include_cash
            )

            if data is None or data.empty:
                if is_portfolio:
                    return pd.Series(dtype=float), "", f"Portfolio '{benchmark_name}' has no {metric.lower()} data available."
                else:
                    return pd.Series(dtype=float), "", f"Ticker '{benchmark_name}' not found. Please check the symbol and try again."

            return data, benchmark_name, None

        except Exception as e:
            print(f"Error loading benchmark {benchmark_name}: {e}")
            if is_portfolio:
                return pd.Series(dtype=float), "", f"Could not load portfolio '{benchmark_name}'."
            else:
                return pd.Series(dtype=float), "", f"Could not load ticker '{benchmark_name}'. Please check the symbol and try again."

    def _get_benchmark_metric_data(
        self, benchmark_name: str, is_portfolio: bool, start_date, end_date, include_cash
    ):
        """
        Get metric data for benchmark (portfolio or ticker).

        Args:
            benchmark_name: Name of portfolio or ticker symbol
            is_portfolio: True if benchmark is a portfolio, False if ticker
            start_date: Start date for data range
            end_date: End date for data range
            include_cash: Whether to include cash in portfolio calculations

        Returns:
            pd.Series of metric values
        """
        metric = self._current_metric

        if metric == "Returns":
            if is_portfolio:
                return ReturnsDataService.get_time_varying_portfolio_returns(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                    interval=self._current_interval,
                )
            else:
                return ReturnsDataService.get_ticker_returns(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                    interval=self._current_interval,
                )

        elif metric == "Volatility":
            if is_portfolio:
                return ReturnsDataService.get_portfolio_volatility(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )
            else:
                return ReturnsDataService.get_ticker_volatility(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                )

        elif metric == "Rolling Volatility":
            window_days = self.WINDOW_TO_DAYS.get(self._current_window, 21)
            if is_portfolio:
                return ReturnsDataService.get_rolling_volatility(
                    benchmark_name,
                    window_days=window_days,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )
            else:
                return ReturnsDataService.get_ticker_rolling_volatility(
                    benchmark_name,
                    window_days=window_days,
                    start_date=start_date,
                    end_date=end_date,
                )

        elif metric == "Drawdown":
            if is_portfolio:
                return ReturnsDataService.get_drawdowns(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )
            else:
                return ReturnsDataService.get_ticker_drawdowns(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                )

        elif metric == "Rolling Return":
            window_days = self.WINDOW_TO_DAYS.get(self._current_window, 252)
            if is_portfolio:
                return ReturnsDataService.get_rolling_returns(
                    benchmark_name,
                    window_days=window_days,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )
            else:
                return ReturnsDataService.get_ticker_rolling_returns(
                    benchmark_name,
                    window_days=window_days,
                    start_date=start_date,
                    end_date=end_date,
                )

        elif metric == "Time Under Water":
            if is_portfolio:
                return ReturnsDataService.get_time_under_water(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                )
            else:
                return ReturnsDataService.get_ticker_time_under_water(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                )

        else:
            # Default to returns
            if is_portfolio:
                return ReturnsDataService.get_time_varying_portfolio_returns(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                    include_cash=include_cash,
                    interval=self._current_interval,
                )
            else:
                return ReturnsDataService.get_ticker_returns(
                    benchmark_name,
                    start_date=start_date,
                    end_date=end_date,
                    interval=self._current_interval,
                )

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            bg_color = "#ffffff"
        elif theme == "bloomberg":
            bg_color = "#000814"
        else:
            bg_color = "#1e1e1e"

        self.setStyleSheet(f"ReturnDistributionModule {{ background-color: {bg_color}; }}")

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _apply_initial_chart_settings(self):
        """Apply chart settings (background, gridlines) on initialization."""
        all_settings = self.settings_manager.get_all_settings()
        self.chart.apply_general_settings(all_settings)

    def _show_loading_overlay(self, message: str = "Loading Distribution..."):
        """Show loading overlay over the entire module."""
        # Hide chart to prevent PyQtGraph from painting over the overlay
        self.chart.hide()

        if self._loading_overlay is None:
            self._loading_overlay = LoadingOverlay(self, self.theme_manager, message)
        else:
            # Update message if overlay already exists
            self._loading_overlay.set_message(message)

        # Cover the entire module
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.show()
        self._loading_overlay.raise_()
        # Force immediate repaint to ensure overlay is visible before heavy work
        self._loading_overlay.repaint()
        QApplication.processEvents()

    def _hide_loading_overlay(self):
        """Hide and cleanup loading overlay."""
        if self._loading_overlay is not None:
            self._loading_overlay.hide()
            self._loading_overlay.deleteLater()
            self._loading_overlay = None

        # Show chart again
        self.chart.show()

    def refresh(self):
        """Refresh the module (called when navigating back)."""
        self._refresh_portfolio_list()
        if self._current_portfolio:
            self._update_distribution()
