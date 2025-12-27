from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from app.ui.widgets.price_chart import PriceChart
from app.ui.widgets.create_indicator_dialog import CreateIndicatorDialog
from app.ui.widgets.chart_settings_dialog import ChartSettingsDialog
from app.ui.widgets.depth_chart import OrderBookPanel
from app.services.market_data import fetch_price_history
from app.services.ticker_equation_parser import TickerEquationParser
from app.services.indicator_service import IndicatorService
from app.services.chart_settings_manager import ChartSettingsManager
from app.services.binance_data import BinanceOrderBook
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


class ChartModule(QWidget):
    """
    Charting module with indicator support and order book depth.
    Handles ticker data loading, chart display, and technical indicators.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.equation_parser = TickerEquationParser()
        self.indicator_service = IndicatorService()
        
        # Initialize chart settings manager
        self.chart_settings_manager = ChartSettingsManager()
        
        # Initialize indicator service to load saved indicators
        IndicatorService.initialize()
        
        self._setup_ui()
        self._setup_state()
        self._connect_signals()

        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

        # Auto-load initial ticker
        self.load_ticker_max(self.ticker_input.text())

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change signal."""
        self._apply_control_bar_theme()
        self._apply_indicator_panel_theme()
        self._apply_depth_panel_theme()
        self.chart.set_theme(theme)

    def _apply_control_bar_theme(self) -> None:
        """Apply theme-specific styling to the control bar."""
        stylesheet = self.theme_manager.get_controls_stylesheet()
        self.controls_widget.setStyleSheet(stylesheet)

    def _apply_indicator_panel_theme(self) -> None:
        """Apply theme-specific styling to the indicator panel."""
        if not hasattr(self, 'indicator_panel'):
            return
            
        theme = self.theme_manager.current_theme
        
        if theme == "light":
            stylesheet = self._get_light_indicator_panel_stylesheet()
        else:
            stylesheet = self._get_dark_indicator_panel_stylesheet()
        
        self.indicator_panel.setStyleSheet(stylesheet)

    def _apply_depth_panel_theme(self) -> None:
        """Apply theme-specific styling to the depth panel."""
        # The depth panel handles its own theming via theme_manager
        pass

    def _get_dark_indicator_panel_stylesheet(self) -> str:
        """Get dark theme stylesheet for indicator panel."""
        return """
            #indicatorPanel {
                background-color: #2d2d2d;
                border-left: 2px solid #3d3d3d;
            }
            QLabel {
                color: #cccccc;
            }
            QListWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #00d4ff;
                background-color: #2d2d2d;
            }
            QPushButton:pressed {
                background-color: #00d4ff;
                color: #000000;
            }
            QPushButton#createButton {
                background-color: #00d4ff;
                color: #000000;
                border: none;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#createButton:hover {
                background-color: #00c4ef;
            }
            QPushButton#createButton:pressed {
                background-color: #00b4df;
            }
        """

    def _get_light_indicator_panel_stylesheet(self) -> str:
        """Get light theme stylesheet for indicator panel."""
        return """
            #indicatorPanel {
                background-color: #f5f5f5;
                border-left: 2px solid #d0d0d0;
            }
            QLabel {
                color: #333333;
            }
            QListWidget {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #0066cc;
                background-color: #e8e8e8;
            }
            QPushButton:pressed {
                background-color: #0066cc;
                color: #ffffff;
            }
            QPushButton#createButton {
                background-color: #0066cc;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton#createButton:hover {
                background-color: #0052a3;
            }
            QPushButton#createButton:pressed {
                background-color: #003d7a;
            }
        """

    def _setup_ui(self) -> None:
        """Create the UI layout."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Controls bar
        self.controls_widget = QWidget()
        
        controls = QHBoxLayout(self.controls_widget)
        controls.setContentsMargins(125, 12, 15, 12)  # Space for home button
        controls.setSpacing(20)

        # Ticker input
        controls.addWidget(QLabel("TICKER"))
        self.ticker_input = QLineEdit()
        self.ticker_input.setText(DEFAULT_TICKER)
        self.ticker_input.setMaximumWidth(200)
        self.ticker_input.setPlaceholderText("Ticker or =equation...")
        controls.addWidget(self.ticker_input)

        # Separator
        controls.addSpacing(10)

        # Interval selector
        controls.addWidget(QLabel("INTERVAL"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(CHART_INTERVALS)
        self.interval_combo.setCurrentText(DEFAULT_INTERVAL)
        self.interval_combo.setMaximumWidth(100)
        controls.addWidget(self.interval_combo)

        # Chart type selector
        controls.addWidget(QLabel("CHART"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(CHART_TYPES)
        self.chart_type_combo.setCurrentText(DEFAULT_CHART_TYPE)
        self.chart_type_combo.setMaximumWidth(100)
        controls.addWidget(self.chart_type_combo)

        # Scale selector
        controls.addWidget(QLabel("SCALE"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(CHART_SCALES)
        self.scale_combo.setCurrentText(DEFAULT_SCALE)
        self.scale_combo.setMaximumWidth(120)
        controls.addWidget(self.scale_combo)

        # Separator
        controls.addSpacing(20)

        # Indicators button
        self.indicators_btn = QPushButton("📊 Indicators")
        self.indicators_btn.setCheckable(True)
        self.indicators_btn.setMaximumWidth(120)
        controls.addWidget(self.indicators_btn)
        self.indicators_btn.show()

        # Depth button
        self.depth_btn = QPushButton("📈 Depth")
        self.depth_btn.setCheckable(True)
        self.depth_btn.setMaximumWidth(120)
        self.depth_btn.setEnabled(False)  # Disabled by default, enabled for Binance tickers
        self.depth_btn.setToolTip("Load a Binance crypto pair (BTC-USD, ETH-USD, etc.) to enable")
        controls.addWidget(self.depth_btn)
        self.depth_btn.show()

        # Chart settings button
        self.chart_settings_btn = QPushButton("⚙️ Settings")
        self.chart_settings_btn.setMaximumWidth(120)
        self.chart_settings_btn.clicked.connect(self._open_chart_settings)
        controls.addWidget(self.chart_settings_btn)
        self.chart_settings_btn.show()

        controls.addStretch(1)
        root.addWidget(self.controls_widget)

        # Apply initial theme to control bar
        self._apply_control_bar_theme()

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
        self.indicator_panel = self._create_indicator_panel()
        self.indicator_panel.setVisible(False)
        content_layout.addWidget(self.indicator_panel)

        root.addLayout(content_layout, stretch=1)

    def _create_indicator_panel(self) -> QWidget:
        """Create the indicator selection panel."""
        panel = QWidget()
        panel.setFixedWidth(250)
        panel.setObjectName("indicatorPanel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header = QLabel("Technical Indicators")
        header.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        layout.addWidget(header)

        # Create New Indicator button
        create_btn = QPushButton("➕ Create New Indicator")
        create_btn.setObjectName("createButton")
        create_btn.clicked.connect(self._create_custom_indicator)
        layout.addWidget(create_btn)

        # Overlay indicators section
        overlay_label = QLabel("Overlays (plot on price):")
        overlay_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(overlay_label)

        self.overlay_list = QListWidget()
        self.overlay_list.setSelectionMode(QListWidget.MultiSelection)
        self.overlay_list.addItems(IndicatorService.get_overlay_names())
        self.overlay_list.setMaximumHeight(200)
        # Double-click to edit
        self.overlay_list.itemDoubleClicked.connect(self._edit_indicator_from_list)
        layout.addWidget(self.overlay_list)

        # Oscillator indicators section
        oscillator_label = QLabel("Oscillators (plot separately):")
        oscillator_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(oscillator_label)

        self.oscillator_list = QListWidget()
        self.oscillator_list.setSelectionMode(QListWidget.MultiSelection)
        self.oscillator_list.addItems(IndicatorService.get_oscillator_names())
        self.oscillator_list.setMaximumHeight(150)
        # Double-click to edit
        self.oscillator_list.itemDoubleClicked.connect(self._edit_indicator_from_list)
        layout.addWidget(self.oscillator_list)

        # Apply button
        apply_btn = QPushButton("Apply Indicators")
        apply_btn.clicked.connect(self._apply_indicators)
        layout.addWidget(apply_btn)

        # Clear button
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_indicators)
        layout.addWidget(clear_btn)

        # Edit button
        edit_btn = QPushButton("✏️ Edit Selected")
        edit_btn.clicked.connect(self._edit_selected_indicator)
        layout.addWidget(edit_btn)

        # Delete selected indicator button
        delete_btn = QPushButton("🗑 Delete Selected")
        delete_btn.clicked.connect(self._delete_custom_indicator)
        layout.addWidget(delete_btn)

        layout.addStretch(1)

        # Apply initial theme directly to panel
        theme = self.theme_manager.current_theme
        if theme == "light":
            stylesheet = self._get_light_indicator_panel_stylesheet()
        else:
            stylesheet = self._get_dark_indicator_panel_stylesheet()
        panel.setStyleSheet(stylesheet)

        return panel

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
        # Enter in ticker box -> download and render
        self.ticker_input.returnPressed.connect(
            lambda: self.load_ticker_max(self.ticker_input.text())
        )

        # Change chart type / scale -> re-render only (no refetch)
        self.chart_type_combo.currentTextChanged.connect(lambda _: self.render_from_cache())
        self.scale_combo.currentTextChanged.connect(lambda _: self.render_from_cache())

        # Change interval -> MUST refetch because bars change
        self.interval_combo.currentTextChanged.connect(
            lambda _: self.load_ticker_max(self.ticker_input.text())
        )

        # Toggle indicator panel
        self.indicators_btn.clicked.connect(self._toggle_indicator_panel)

        # Toggle depth panel
        self.depth_btn.clicked.connect(self._toggle_depth_panel)

    def _toggle_indicator_panel(self) -> None:
        """Toggle the indicator selection panel visibility."""
        is_visible = self.indicators_btn.isChecked()
        self.indicator_panel.setVisible(is_visible)
        
        # If showing indicators, hide depth
        if is_visible and self.depth_panel.isVisible():
            self.depth_btn.setChecked(False)
            self.depth_panel.setVisible(False)
            self.depth_panel.stop_updates()

    def _toggle_depth_panel(self) -> None:
        """Toggle the depth panel visibility."""
        is_visible = self.depth_btn.isChecked()
        self.depth_panel.setVisible(is_visible)
        
        # If showing depth, hide indicators
        if is_visible:
            if self.indicator_panel.isVisible():
                self.indicators_btn.setChecked(False)
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
        overlay_items = self.overlay_list.selectedItems()
        oscillator_items = self.oscillator_list.selectedItems()
        
        selected = [item.text() for item in overlay_items + oscillator_items]
        
        # Store in state
        self.state["indicators"] = selected
        
        # Re-render with indicators
        self.render_from_cache()

    def _clear_indicators(self) -> None:
        """Clear all indicators from the chart."""
        # Deselect all items
        self.overlay_list.clearSelection()
        self.oscillator_list.clearSelection()
        
        # Clear state
        self.state["indicators"] = []
        
        # Re-render without indicators
        self.render_from_cache()

    def _edit_indicator_from_list(self, item) -> None:
        """Edit an indicator that was double-clicked in the sidebar list."""
        indicator_name = item.text()
        self._edit_indicator(indicator_name)

    def _edit_selected_indicator(self) -> None:
        """Edit the currently selected indicator from the sidebar."""
        # Get selected item from either list
        selected_overlay = self.overlay_list.selectedItems()
        selected_oscillator = self.oscillator_list.selectedItems()
        
        selected = selected_overlay + selected_oscillator
        
        if len(selected) == 0:
            QMessageBox.information(
                self,
                "No Indicator Selected",
                "Please select an indicator to edit.",
            )
            return
        
        if len(selected) > 1:
            QMessageBox.information(
                self,
                "Multiple Indicators Selected",
                "Please select only one indicator to edit.",
            )
            return
        
        indicator_name = selected[0].text()
        self._edit_indicator(indicator_name)

    def _edit_indicator(self, indicator_name: str) -> None:
        """Open the edit dialog for an indicator."""
        # Get the indicator config
        if indicator_name not in IndicatorService.ALL_INDICATORS:
            QMessageBox.warning(
                self,
                "Indicator Not Found",
                f"Indicator '{indicator_name}' not found.",
            )
            return
        
        config = IndicatorService.ALL_INDICATORS[indicator_name]
        
        # Check if this is a plugin-based indicator
        if config.get("kind") == "plugin":
            QMessageBox.information(
                self,
                "Cannot Edit Plugin",
                f"'{indicator_name}' is a plugin-based indicator and cannot be edited through the UI.\n\n"
                "To modify it, edit the plugin file directly.",
            )
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
        
        # Extract parameters (exclude 'kind' and 'appearance')
        params = {k: v for k, v in config.items() if k not in ["kind", "appearance"]}
        
        # Get appearance settings
        appearance = config.get("appearance", {})
        
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
            "appearance": appearance,
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
                
                QMessageBox.information(
                    self,
                    "Indicator Updated",
                    f"Successfully updated indicator.",
                )

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
        appearance = config.get("appearance", {})
        
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
            "appearance": appearance,
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
                    QMessageBox.information(
                        self,
                        "Already Exists",
                        f"The indicator '{name}' already exists in the list.",
                    )
                    return
                
                # Add indicator
                self._add_indicator_from_config(config)
                
                # Refresh the lists
                self._refresh_indicator_lists()
                
                QMessageBox.information(
                    self,
                    "Indicator Created",
                    f"Created custom indicator: {name}",
                )

    def _delete_custom_indicator(self) -> None:
        """Delete indicators from the list."""
        # Get all selected items from both lists
        selected = []
        for item in self.overlay_list.selectedItems():
            selected.append(item.text())
        for item in self.oscillator_list.selectedItems():
            selected.append(item.text())
        
        if not selected:
            QMessageBox.information(
                self,
                "No Indicator Selected",
                "Please select an indicator to delete.",
            )
            return
        
        # Confirm deletion
        indicator_list = "\n".join(selected)
        reply = QMessageBox.question(
            self,
            "Delete Indicators",
            f"Are you sure you want to delete these indicators?\n\n{indicator_list}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        
        if reply == QMessageBox.Yes:
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
            
            QMessageBox.information(
                self,
                "Indicators Deleted",
                f"Deleted {len(selected)} indicator(s).",
            )

    def _refresh_indicator_lists(self) -> None:
        """Refresh the indicator lists to show newly added custom indicators."""
        # Store current selections
        overlay_selected = [item.text() for item in self.overlay_list.selectedItems()]
        oscillator_selected = [item.text() for item in self.oscillator_list.selectedItems()]
        
        # Clear and repopulate lists
        self.overlay_list.clear()
        self.overlay_list.addItems(sorted(IndicatorService.get_overlay_names()))
        
        self.oscillator_list.clear()
        self.oscillator_list.addItems(sorted(IndicatorService.get_oscillator_names()))
        
        # Restore selections
        for i in range(self.overlay_list.count()):
            item = self.overlay_list.item(i)
            if item.text() in overlay_selected:
                item.setSelected(True)
        
        for i in range(self.oscillator_list.count()):
            item = self.oscillator_list.item(i)
            if item.text() in oscillator_selected:
                item.setSelected(True)

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
        return self.chart_type_combo.currentText()

    def current_interval(self) -> str:
        return self.interval_combo.currentText()

    def current_scale(self) -> str:
        return self.scale_combo.currentText()

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
            QMessageBox.critical(self, "Render Error", str(e))

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
            self.depth_btn.setEnabled(is_binance)
            self.depth_btn.setVisible(is_binance)

            if is_binance:
                self.depth_btn.setText("📈 Depth ✓")
                self.depth_btn.setToolTip(
                    f"✓ Order book depth available for {display_name}\n\n"
                    f"Click to show live Binance order book with:\n"
                    f"• Real-time bid/ask levels\n"
                    f"• Cumulative volume visualization\n"
                    f"• Spread analysis"
                )
                
                # If depth panel is already visible, update it
                if self.depth_panel.isVisible():
                    self.depth_panel.set_ticker(display_name)
            else:
                self.depth_btn.setText("📈 Depth")
                self.depth_btn.setToolTip(
                    f"✗ {display_name} is not available on Binance\n\n"
                    f"Order book depth is only available for crypto pairs.\n\n"
                    f"Supported tickers include:\n"
                    f"BTC-USD, ETH-USD, SOL-USD, DOGE-USD, ADA-USD,\n"
                    f"MATIC-USD, AVAX-USD, DOT-USD, LINK-USD, and more."
                )
                
                # Hide depth panel if it was visible
                if self.depth_panel.isVisible():
                    self.depth_btn.setChecked(False)
                    self.depth_panel.setVisible(False)
                    self.depth_panel.stop_updates()

            self.render_from_cache()

        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            # Clear the equation parser cache on error
            self.equation_parser.clear_cache()