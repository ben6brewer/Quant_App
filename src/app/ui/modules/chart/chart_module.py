from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal

from app.ui.modules.chart.widgets import (
    PriceChart,
    ChartControls,
    IndicatorPanel,
    CreateIndicatorDialog,
    ChartSettingsDialog,
)
from app.ui.modules.chart.widgets.depth_chart import OrderBookPanel
from app.ui.modules.chart.widgets import EditPluginAppearanceDialog
from app.ui.widgets.common import CustomMessageBox
from app.services.market_data import fetch_price_history
from .services import (
    TickerEquationParser,
    IndicatorService,
    ChartSettingsManager,
    ChartThemeService,
    BinanceOrderBook
)
from app.core.theme_manager import ThemeManager
from app.core.config import (
    DEFAULT_TICKER,
    DEFAULT_INTERVAL,
    DEFAULT_CHART_TYPE,
    DEFAULT_SCALE,
    CHART_INTERVALS,
    CHART_TYPES,
    CHART_SCALES,
)
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class ChartModule(LazyThemeMixin, QWidget):
    """
    Charting module with indicator support and order book depth.
    Handles ticker data loading, chart display, and technical indicators.
    """

    # Signal emitted when user clicks home button
    home_clicked = Signal()

    # Flag indicating this module has its own home button
    has_own_home_button = True

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self.equation_parser = TickerEquationParser()
        self.indicator_service = IndicatorService()

        # Initialize chart settings manager
        self.chart_settings_manager = ChartSettingsManager()

        # Initialize indicator service to load saved indicators
        IndicatorService.initialize()

        self._setup_ui()
        self._setup_state()
        self._connect_signals()

        # Connect to theme changes (lazy - only apply when visible)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy_chart)

        # Auto-load initial ticker
        self.load_ticker_max(self.controls.get_ticker())

    def _on_theme_changed_lazy_chart(self, theme: str) -> None:
        """Handle theme change with visibility check."""
        if self.isVisible():
            self._apply_theme()
        else:
            self._theme_dirty = True

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _apply_theme(self) -> None:
        """Apply theme to chart and depth panel."""
        theme = self.theme_manager.current_theme
        self._apply_depth_panel_theme()
        self.chart.set_theme(theme)

    def _apply_depth_panel_theme(self) -> None:
        """Apply theme-specific styling to the depth panel."""
        # The depth panel handles its own theming via theme_manager
        pass

    def _setup_ui(self) -> None:
        """Create the UI layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Controls bar
        self.controls = ChartControls(self.theme_manager)
        root.addWidget(self.controls)

        # Horizontal layout for chart + panels
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Chart with settings
        self.chart = PriceChart(chart_settings=self.chart_settings_manager.get_all_settings())
        content_layout.addWidget(self.chart, stretch=1)
        
        # Apply initial theme to chart
        self.chart.set_theme(self.theme_manager.current_theme)

        # Depth panel (hidden by default)
        self.depth_panel = OrderBookPanel(self.theme_manager)
        self.depth_panel.setFixedWidth(400)
        self.depth_panel.setVisible(False)
        content_layout.addWidget(self.depth_panel)

        # Indicator selection panel (hidden by default)
        self.indicator_panel = IndicatorPanel(self.theme_manager)
        self.indicator_panel.setVisible(False)
        content_layout.addWidget(self.indicator_panel)

        root.addLayout(content_layout, stretch=1)

    def _setup_state(self) -> None:
        """Initialize state management."""
        self.state = {
            "df": None,
            "ticker": None,
            "interval": None,
            "indicators": [],
        }

    def _connect_signals(self) -> None:
        """Connect all signals."""
        # Control bar signals
        self.controls.home_clicked.connect(self.home_clicked.emit)
        self.controls.ticker_changed.connect(self.load_ticker_max)
        self.controls.interval_changed.connect(lambda _: self.load_ticker_max(self.controls.get_ticker()))
        self.controls.chart_type_changed.connect(lambda _: self.render_from_cache())
        self.controls.scale_changed.connect(lambda _: self.render_from_cache())
        self.controls.settings_clicked.connect(self._open_chart_settings)
        self.controls.indicators_toggled.connect(self._on_indicators_toggled)
        self.controls.depth_toggled.connect(self._on_depth_toggled)

        # Indicator panel signals
        self.indicator_panel.create_clicked.connect(self._create_custom_indicator)
        self.indicator_panel.apply_clicked.connect(self._apply_indicators)
        self.indicator_panel.clear_clicked.connect(self._clear_indicators)
        self.indicator_panel.clear_all_clicked.connect(self._clear_all_indicators)
        self.indicator_panel.edit_clicked.connect(self._edit_selected_indicator)
        self.indicator_panel.delete_clicked.connect(self._delete_custom_indicator)
        self.indicator_panel.indicator_double_clicked.connect(self._edit_indicator_from_list)

    def _on_indicators_toggled(self, is_checked: bool) -> None:
        """Handle indicators button toggle."""
        self.indicator_panel.setVisible(is_checked)

        # If showing indicators, hide depth
        if is_checked and self.depth_panel.isVisible():
            self.controls.set_depth_checked(False)
            self.depth_panel.setVisible(False)
            self.depth_panel.stop_updates()

    def _on_depth_toggled(self, is_checked: bool) -> None:
        """Handle depth button toggle."""
        self.depth_panel.setVisible(is_checked)

        # If showing depth, hide indicators
        if is_checked:
            if self.indicator_panel.isVisible():
                self.controls.set_indicators_checked(False)
                self.indicator_panel.setVisible(False)

            # Update depth with current ticker
            if self.state["ticker"]:
                self.depth_panel.set_ticker(self.state["ticker"])
        else:
            # Stop updates when hiding
            self.depth_panel.stop_updates()

    def _apply_indicators(self) -> None:
        """Apply selected indicators to the chart."""
        # Get selected indicators
        overlays, oscillators = self.indicator_panel.get_all_selected()
        selected = overlays + oscillators

        # Store in state
        self.state["indicators"] = selected

        # Re-render with indicators
        self.render_from_cache()

    def _clear_indicators(self) -> None:
        """Clear selected indicators from the chart."""
        # Get selected items
        overlays, oscillators = self.indicator_panel.get_all_selected()
        selected = overlays + oscillators

        if not selected:
            return

        # Deselect the items
        self.indicator_panel.clear_selections()

        # Remove from state
        for indicator in selected:
            if indicator in self.state["indicators"]:
                self.state["indicators"].remove(indicator)

        # Re-render without the cleared indicators
        self.render_from_cache()

    def _clear_all_indicators(self) -> None:
        """Clear all indicators from the chart."""
        # Deselect all items
        self.indicator_panel.clear_selections()

        # Clear state
        self.state["indicators"] = []

        # Re-render without indicators
        self.render_from_cache()

    def _edit_indicator_from_list(self, indicator_name: str) -> None:
        """Edit an indicator that was double-clicked in the sidebar list."""
        self._edit_indicator(indicator_name)

    def _edit_selected_indicator(self) -> None:
        """Edit the currently selected indicator from the sidebar."""
        # Get selected items from both lists
        overlays, oscillators = self.indicator_panel.get_all_selected()
        selected = overlays + oscillators

        if len(selected) == 0:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Indicator Selected",
                "Please select an indicator to edit.",
            )
            return

        if len(selected) > 1:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "Multiple Indicators Selected",
                "Please select only one indicator to edit.",
            )
            return

        indicator_name = selected[0]
        self._edit_indicator(indicator_name)

    def _edit_indicator(self, indicator_name: str) -> None:
        """Open the edit dialog for an indicator."""
        # Get the indicator config
        if indicator_name not in IndicatorService.ALL_INDICATORS:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Indicator Not Found",
                f"Indicator '{indicator_name}' not found.",
            )
            return
        
        config = IndicatorService.ALL_INDICATORS[indicator_name]
        
        # Check if this is a plugin-based indicator
        if config.get("kind") == "plugin":
            # For plugins, only allow appearance editing
            dialog = EditPluginAppearanceDialog(
                self.theme_manager,
                indicator_name,
                self,
            )

            if dialog.exec():
                # Appearance saved - re-render
                self.render_from_cache()

            return
        
        # Build indicator config for the dialog
        indicator_type_map = {
            "sma": "SMA",
            "ema": "EMA",
            "bbands": "Bollinger Bands",
            "rsi": "RSI",
            "macd": "MACD",
            "atr": "ATR",
            "stochastic": "Stochastic",
            "obv": "OBV",
            "vwap": "VWAP",
        }
        
        kind = config.get("kind")
        indicator_type = indicator_type_map.get(kind, kind)
        
        # Extract parameters (exclude 'kind', 'appearance', and 'per_line_appearance')
        params = {k: v for k, v in config.items() if k not in ["kind", "appearance", "per_line_appearance"]}

        # Get per-line appearance settings
        per_line_appearance = config.get("per_line_appearance", {})

        # Try to extract custom name from the indicator_name
        # If it matches the auto-generated pattern, don't set custom_name
        custom_name = None
        auto_name = self._generate_auto_name(indicator_type, params)
        if indicator_name != auto_name:
            custom_name = indicator_name

        edit_config = {
            "type": indicator_type,
            "params": params,
            "custom_name": custom_name,
            "per_line_appearance": per_line_appearance,  # Only this field
        }
        
        # Open edit dialog
        dialog = CreateIndicatorDialog(
            self.theme_manager,
            self,
            edit_mode=True,
            indicator_config=edit_config,
        )
        
        if dialog.exec():
            new_config = dialog.get_indicator_config()
            if new_config:
                # Remove old indicator
                old_name = indicator_name
                IndicatorService.remove_custom_indicator(old_name)
                
                # Add updated indicator
                self._add_indicator_from_config(new_config)
                
                # Update selection if this indicator was active
                if old_name in self.state["indicators"]:
                    self.state["indicators"].remove(old_name)
                    # Add new name
                    new_name = new_config.get("custom_name") or self._generate_auto_name(
                        new_config["type"], new_config["params"]
                    )
                    self.state["indicators"].append(new_name)
                
                # Refresh lists and re-render
                self._refresh_indicator_lists()
                self.render_from_cache()

    def _generate_auto_name(self, indicator_type: str, params: dict) -> str:
        """Generate auto name for an indicator based on type and params."""
        if not params:
            return indicator_type
        elif indicator_type == "SMA":
            return f"SMA({params.get('length', '')})"
        elif indicator_type == "EMA":
            return f"EMA({params.get('length', '')})"
        elif indicator_type == "Bollinger Bands":
            return f"BB({params.get('length', '')},{params.get('std', '')})"
        elif indicator_type == "RSI":
            return f"RSI({params.get('length', '')})"
        elif indicator_type == "MACD":
            return f"MACD({params.get('fast', '')},{params.get('slow', '')},{params.get('signal', '')})"
        elif indicator_type == "ATR":
            return f"ATR({params.get('length', '')})"
        elif indicator_type == "Stochastic":
            return f"Stochastic({params.get('k', '')},{params.get('d', '')},{params.get('smooth_k', '')})"
        else:
            return indicator_type

    def _add_indicator_from_config(self, config: dict) -> None:
        """Add an indicator from a config dict."""
        indicator_type = config["type"]
        params = config["params"]
        custom_name = config.get("custom_name")
        per_line_appearance = config.get("per_line_appearance", {})  # Required now

        # Use custom name if provided, otherwise auto-generate
        if custom_name:
            name = custom_name
        else:
            name = self._generate_auto_name(indicator_type, params)

        # Build config for IndicatorService
        kind_map = {
            "SMA": "sma",
            "EMA": "ema",
            "Bollinger Bands": "bbands",
            "RSI": "rsi",
            "MACD": "macd",
            "ATR": "atr",
            "Stochastic": "stochastic",
            "OBV": "obv",
            "VWAP": "vwap",
        }

        indicator_config = {
            "kind": kind_map[indicator_type],
            **params,
            "per_line_appearance": per_line_appearance,  # Only this field
        }

        # Determine if overlay or oscillator
        is_overlay = indicator_type in ["SMA", "EMA", "Bollinger Bands", "VWAP"]

        # Add to IndicatorService
        IndicatorService.add_custom_indicator(name, indicator_config, is_overlay)

    def _create_custom_indicator(self) -> None:
        """Open dialog to create a custom indicator."""
        dialog = CreateIndicatorDialog(self.theme_manager, self)
        
        if dialog.exec():
            config = dialog.get_indicator_config()
            if config:
                # Generate name
                custom_name = config.get("custom_name")
                if custom_name:
                    name = custom_name
                else:
                    name = self._generate_auto_name(config["type"], config["params"])
                
                # Check if already exists
                if name in IndicatorService.ALL_INDICATORS:
                    CustomMessageBox.information(
                        self.theme_manager,
                        self,
                        "Already Exists",
                        f"The indicator '{name}' already exists in the list.",
                    )
                    return
                
                # Add indicator
                self._add_indicator_from_config(config)

                # Refresh the lists
                self._refresh_indicator_lists()

    def _delete_custom_indicator(self) -> None:
        """Delete indicators from the list."""
        # Get all selected items from both lists
        overlays, oscillators = self.indicator_panel.get_all_selected()
        selected = overlays + oscillators

        if not selected:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Indicator Selected",
                "Please select an indicator to delete.",
            )
            return

        # Confirm deletion
        indicator_list = "\n".join(selected)
        reply = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Delete Indicators",
            f"Are you sure you want to delete these indicators?\n\n{indicator_list}",
            CustomMessageBox.Yes | CustomMessageBox.No,
            CustomMessageBox.No,
        )

        if reply == CustomMessageBox.Yes:
            # Remove from IndicatorService
            for name in selected:
                IndicatorService.remove_custom_indicator(name)

            # Refresh the lists
            self._refresh_indicator_lists()

            # Clear from active indicators if present
            for name in selected:
                if name in self.state["indicators"]:
                    self.state["indicators"].remove(name)

            # Re-render
            self.render_from_cache()

    def _refresh_indicator_lists(self) -> None:
        """Refresh the indicator lists to show newly added custom indicators."""
        self.indicator_panel.refresh_indicators(preserve_selection=True)

    def _open_chart_settings(self) -> None:
        """Open the chart settings dialog."""
        dialog = ChartSettingsDialog(
            self.theme_manager,
            self.chart_settings_manager.get_all_settings(),
            self
        )
        
        if dialog.exec():
            settings = dialog.get_settings()
            if settings:
                # Update settings manager
                self.chart_settings_manager.update_settings(settings)
                
                # Update chart
                self.chart.update_chart_settings(settings)
                
                # Re-render to apply settings
                self.render_from_cache()

    def current_chart_type(self) -> str:
        return self.controls.get_chart_type()

    def current_interval(self) -> str:
        return self.controls.get_interval()

    def current_scale(self) -> str:
        return self.controls.get_scale()

    def render_from_cache(self) -> None:
        """Re-render chart from cached data with indicators."""
        if self.state["df"] is None or self.state["ticker"] is None:
            return
        
        try:
            # Calculate indicators if any are selected
            indicators = {}
            if self.state["indicators"]:
                indicators = IndicatorService.calculate_multiple(
                    self.state["df"], self.state["indicators"]
                )
            
            # Render chart with indicators
            self.chart.set_prices(
                self.state["df"],
                ticker=self.state["ticker"],
                chart_type=self.current_chart_type(),
                scale=self.current_scale(),
                indicators=indicators,
            )
        except Exception as e:
            CustomMessageBox.critical(self.theme_manager, self, "Render Error", str(e))

    def load_ticker_max(self, ticker: str) -> None:
        """Load max history for a ticker or evaluate an equation."""
        ticker = (ticker or "").strip()
        if not ticker:
            return

        interval = self.current_interval()

        try:
            # Check if this is an equation
            if self.equation_parser.is_equation(ticker):
                # Parse and evaluate equation
                df, description = self.equation_parser.parse_and_evaluate(
                    ticker, period="max", interval=interval
                )
                display_name = description
            else:
                # Regular ticker
                ticker = ticker.upper()
                df = fetch_price_history(ticker, period="max", interval=interval)
                display_name = ticker

            self.state["df"] = df
            self.state["ticker"] = display_name
            self.state["interval"] = interval

            # Check if this ticker is supported on Binance
            is_binance = BinanceOrderBook.is_binance_ticker(display_name)

            # Enable/disable the depth button
            self.controls.set_depth_enabled(is_binance)
            self.controls.set_depth_visible(is_binance)

            if is_binance:
                self.controls.set_depth_text("Depth")

                # If depth panel is already visible, update it
                if self.depth_panel.isVisible():
                    self.depth_panel.set_ticker(display_name)
            else:
                self.controls.set_depth_text("Depth")

                # Hide depth panel if it was visible
                if self.depth_panel.isVisible():
                    self.controls.set_depth_checked(False)
                    self.depth_panel.setVisible(False)
                    self.depth_panel.stop_updates()

            self.render_from_cache()

        except Exception as e:
            CustomMessageBox.critical(self.theme_manager, self, "Load Error", str(e))
            # Clear the equation parser cache on error
            self.equation_parser.clear_cache()