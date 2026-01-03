from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QSpinBox,
    QColorDialog,
    QGroupBox,
    QWidget,
    QScrollArea,
    QCheckBox,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QMouseEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox


class CreateIndicatorDialog(QDialog):
    """
    Dialog for creating/editing custom indicators with user-specified parameters
    and appearance settings.
    """

    # Define indicator types and their parameters
    INDICATOR_TYPES = {
        "SMA": {
            "name": "Simple Moving Average",
            "params": [
                {"name": "length", "label": "Period", "default": "20", "type": "int"},
            ],
            "uses_markers": False,  # Only uses lines
        },
        "EMA": {
            "name": "Exponential Moving Average",
            "params": [
                {"name": "length", "label": "Period", "default": "12", "type": "int"},
            ],
            "uses_markers": False,
        },
        "Bollinger Bands": {
            "name": "Bollinger Bands",
            "params": [
                {"name": "length", "label": "Period", "default": "20", "type": "int"},
                {"name": "std", "label": "Std Dev", "default": "2", "type": "float"},
            ],
            "uses_markers": False,
        },
        "RSI": {
            "name": "Relative Strength Index",
            "params": [
                {"name": "length", "label": "Period", "default": "14", "type": "int"},
            ],
            "uses_markers": False,
        },
        "MACD": {
            "name": "MACD",
            "params": [
                {"name": "fast", "label": "Fast Period", "default": "12", "type": "int"},
                {"name": "slow", "label": "Slow Period", "default": "26", "type": "int"},
                {"name": "signal", "label": "Signal Period", "default": "9", "type": "int"},
            ],
            "uses_markers": False,
        },
        "ATR": {
            "name": "Average True Range",
            "params": [
                {"name": "length", "label": "Period", "default": "14", "type": "int"},
            ],
            "uses_markers": False,
        },
        "Stochastic": {
            "name": "Stochastic Oscillator",
            "params": [
                {"name": "k", "label": "K Period", "default": "14", "type": "int"},
                {"name": "d", "label": "D Period", "default": "3", "type": "int"},
                {"name": "smooth_k", "label": "Smooth K", "default": "3", "type": "int"},
            ],
            "uses_markers": False,
        },
        "OBV": {
            "name": "On-Balance Volume",
            "params": [],
            "uses_markers": False,
        },
        "VWAP": {
            "name": "Volume Weighted Average Price",
            "params": [],
            "uses_markers": False,
        },
        "Volume": {
            "name": "Volume",
            "params": [],
            "uses_markers": False,
            "is_builtin": True,
            "display_type_options": ["Histogram", "Line"],
        },
    }

    # Line style options
    LINE_STYLES = {
        "Solid": Qt.SolidLine,
        "Dashed": Qt.DashLine,
        "Dotted": Qt.DotLine,
        "Dash-Dot": Qt.DashDotLine,
    }

    # Marker/shape options
    MARKER_SHAPES = {
        "Circle": "o",
        "Square": "s",
        "Triangle": "t",
        "Diamond": "d",
        "Plus": "+",
        "Cross": "x",
        "Star": "star",
    }

    # Preset colors
    PRESET_COLORS = [
        ("Blue", (0, 150, 255)),
        ("Orange", (255, 150, 0)),
        ("Purple", (150, 0, 255)),
        ("Yellow", (255, 200, 0)),
        ("Cyan", (0, 255, 150)),
        ("Magenta", (255, 0, 150)),
        ("Green", (76, 175, 80)),
        ("Red", (244, 67, 54)),
        ("White", (255, 255, 255)),
        ("Custom...", None),
    ]

    def __init__(self, theme_manager: ThemeManager, parent=None, edit_mode=False, indicator_config=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(500)

        # Remove native title bar
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self.theme_manager = theme_manager
        self.edit_mode = edit_mode
        self.indicator_config = indicator_config or {}
        self.param_inputs = {}
        self.selected_color = (0, 150, 255)  # Default blue

        # For window dragging
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()

        # If in edit mode, populate fields
        if self.edit_mode and self.indicator_config:
            self._populate_from_config()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Custom title bar
        title_text = "Edit Indicator" if self.edit_mode else "Create Custom Indicator"
        self.title_bar = self._create_title_bar(title_text)
        layout.addWidget(self.title_bar)

        # Content container
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        # Indicator type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Indicator Type:"))

        self.type_combo = QComboBox()
        self.type_combo.addItems(list(self.INDICATOR_TYPES.keys()))
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        # Disable type combo in edit mode
        if self.edit_mode:
            self.type_combo.setEnabled(False)

        type_layout.addWidget(self.type_combo, stretch=1)

        content_layout.addLayout(type_layout)

        # Custom name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Custom Name (optional):"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Leave empty for auto-generated name")
        name_layout.addWidget(self.name_input, stretch=1)
        content_layout.addLayout(name_layout)

        # Parameter form
        param_group = QGroupBox("Indicator Parameters")
        param_group.setObjectName("paramGroup")
        param_layout = QVBoxLayout(param_group)

        self.param_form = QFormLayout()
        self.param_form.setSpacing(10)
        param_layout.addLayout(self.param_form)

        content_layout.addWidget(param_group)

        # Per-line settings group (always visible) with Appearance Settings title
        self.per_line_group = self._create_per_line_settings_group()
        content_layout.addWidget(self.per_line_group)

        # Initialize with first indicator type
        self._on_type_changed(self.type_combo.currentText())

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        button_text = "Update Indicator" if self.edit_mode else "Create Indicator"
        self.create_btn = QPushButton(button_text)
        self.create_btn.setDefault(True)
        self.create_btn.setObjectName("defaultButton")
        self.create_btn.clicked.connect(self._create_indicator)
        button_layout.addWidget(self.create_btn)

        content_layout.addLayout(button_layout)

        # Add content to main layout
        layout.addWidget(content_widget)

    def _create_title_bar(self, title: str) -> QWidget:
        """Create custom title bar with window controls."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 0, 0)
        bar_layout.setSpacing(5)

        # Dialog title
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        bar_layout.addWidget(self.title_label)

        bar_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bar_layout.addWidget(close_btn)

        # Enable dragging from title bar
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press on title bar for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move on title bar for dragging."""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _populate_from_config(self):
        """Populate dialog fields from existing indicator config."""
        config = self.indicator_config

        # Block signals while populating to prevent triggering dialogs
        self.type_combo.blockSignals(True)
        self.name_input.blockSignals(True)

        # Set indicator type
        indicator_type = config.get("type")
        if indicator_type:
            index = self.type_combo.findText(indicator_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

        # Re-enable type combo signal and manually trigger type changed to recreate param form
        self.type_combo.blockSignals(False)
        if indicator_type:
            self._on_type_changed(indicator_type)

        # Re-block to continue populating
        self.type_combo.blockSignals(True)

        # Set custom name
        custom_name = config.get("custom_name", "")
        if custom_name:
            self.name_input.setText(custom_name)

        # Set parameters (now that correct param form exists)
        params = config.get("params", {})
        for param_name, value in params.items():
            if param_name in self.param_inputs:
                self.param_inputs[param_name]["widget"].setText(str(value))

        # Set per-line appearance (now the only appearance config)
        per_line_appearance = config.get("per_line_appearance", {})
        if per_line_appearance and self.line_widgets:

            # Populate each line's settings
            for col_name, line_settings in per_line_appearance.items():
                if col_name in self.line_widgets:
                    widgets = self.line_widgets[col_name]

                    # Block signals for line widgets
                    widgets["visible"].blockSignals(True)
                    widgets["label"].blockSignals(True)
                    widgets["width"].blockSignals(True)
                    widgets["style"].blockSignals(True)
                    # Only block marker widget signals if they exist
                    if widgets["marker_shape"] is not None:
                        widgets["marker_shape"].blockSignals(True)
                    if widgets["marker_size"] is not None:
                        widgets["marker_size"].blockSignals(True)

                    # Set values
                    widgets["visible"].setChecked(line_settings.get("visible", True))
                    widgets["label"].setText(line_settings.get("label", col_name))
                    widgets["width"].setValue(line_settings.get("line_width", 2))

                    # Only set marker size if widget exists
                    if widgets["marker_size"] is not None:
                        widgets["marker_size"].setValue(line_settings.get("marker_size", 10))

                    # Set color
                    color = line_settings.get("color", (0, 150, 255))
                    widgets["color"] = color
                    widgets["color_btn"].setStyleSheet(
                        f"background-color: rgb({color[0]}, {color[1]}, {color[2]}); "
                        f"border: 1px solid #555;"
                    )

                    # Set line style
                    line_style = line_settings.get("line_style", Qt.SolidLine)
                    for style_name, style_val in self.LINE_STYLES.items():
                        if style_val == line_style:
                            widgets["style"].setCurrentText(style_name)
                            break

                    # Only set marker shape if widget exists
                    if widgets["marker_shape"] is not None:
                        marker_shape = line_settings.get("marker_shape", "o")
                        for shape_name, shape_val in self.MARKER_SHAPES.items():
                            if shape_val == marker_shape:
                                widgets["marker_shape"].setCurrentText(shape_name)
                                break

                    # Re-enable signals for line widgets
                    widgets["visible"].blockSignals(False)
                    widgets["label"].blockSignals(False)
                    widgets["width"].blockSignals(False)
                    widgets["style"].blockSignals(False)
                    # Only unblock marker widget signals if they exist
                    if widgets["marker_shape"] is not None:
                        widgets["marker_shape"].blockSignals(False)
                    if widgets["marker_size"] is not None:
                        widgets["marker_size"].blockSignals(False)

        # Re-enable signals
        self.type_combo.blockSignals(False)
        self.name_input.blockSignals(False)

        # Note: Per-line settings are already populated by _on_type_changed() at line 297
        # and then loaded with saved values above. No need to call _populate_per_line_settings() again.

    def _create_per_line_settings_group(self) -> QGroupBox:
        """Create the per-line appearance settings group."""
        group = QGroupBox("Appearance Settings")  # Renamed from "Per-Line Customization"
        group.setObjectName("perLineGroup")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 5, 10, 10)  # Reduced top margin from 10 to 5
        layout.setSpacing(10)

        # Container for line widgets (no scroll area - dialog auto-sizes)
        self.per_line_container = QWidget()
        self.per_line_container.setStyleSheet("background: transparent;")  # Match group box background
        self.per_line_layout = QVBoxLayout(self.per_line_container)
        self.per_line_layout.setContentsMargins(5, 0, 0, 5)  # No right margin for full width
        self.per_line_layout.setSpacing(5)

        layout.addWidget(self.per_line_container)

        # Storage for line widgets
        self.line_widgets = {}  # column_name -> widget dict

        return group

    def _create_line_widget(self, column_name: str, metadata: dict, uses_markers: bool) -> QWidget:
        """
        Create a widget for customizing a single line.

        Args:
            column_name: Technical column name (e.g., "BB_Upper")
            metadata: Dict with keys: label, default_color, default_style
            uses_markers: If True, include marker shape/size controls; if False, hide them
        """
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")  # Match group box background
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 0, 5)  # No right margin for full width
        layout.setSpacing(8)

        # Visibility checkbox
        visible_check = QCheckBox()
        visible_check.setChecked(True)
        visible_check.setToolTip("Show/hide this line")
        layout.addWidget(visible_check)

        # Label input (editable) - wider since no marker widgets
        label_input = QLineEdit(metadata.get("label", column_name))
        label_input.setPlaceholderText("Display label")
        label_input.setMinimumWidth(150)
        label_input.setMaximumWidth(200)
        label_input.setToolTip("Custom label for legend (leave empty to hide from legend)")
        layout.addWidget(label_input)

        # Color button
        color = metadata.get("default_color", (0, 150, 255))
        color_btn = QPushButton()
        color_btn.setFixedSize(30, 30)
        color_btn.setStyleSheet(
            f"background-color: rgb({color[0]}, {color[1]}, {color[2]}); "
            f"border: 1px solid #555;"
        )
        color_btn.setToolTip("Click to change color")
        color_btn.setCursor(Qt.PointingHandCursor)
        color_btn.clicked.connect(lambda: self._pick_line_color(column_name))
        layout.addWidget(color_btn)

        # Line width spinner
        width_spin = QSpinBox()
        width_spin.setMinimum(1)
        width_spin.setMaximum(10)
        width_spin.setValue(2)
        width_spin.setPrefix("W: ")
        width_spin.setMaximumWidth(70)
        width_spin.setToolTip("Line width in pixels")
        layout.addWidget(width_spin)

        # Line style combo - wider since no marker widgets
        style_combo = QComboBox()
        style_combo.addItems(list(self.LINE_STYLES.keys()))
        style_combo.setMaximumWidth(120)
        style_combo.setToolTip("Line style")
        # Set default from metadata
        default_style = metadata.get("default_style", Qt.SolidLine)
        for style_name, style_val in self.LINE_STYLES.items():
            if style_val == default_style:
                style_combo.setCurrentText(style_name)
                break
        layout.addWidget(style_combo)

        # Marker shape combo (only for marker-based indicators)
        if uses_markers:
            marker_shape_combo = QComboBox()
            marker_shape_combo.addItems(list(self.MARKER_SHAPES.keys()))
            marker_shape_combo.setMaximumWidth(100)
            marker_shape_combo.setToolTip("Marker shape for scatter plots")
            layout.addWidget(marker_shape_combo)
        else:
            marker_shape_combo = None

        # Marker size spinner (only for marker-based indicators)
        if uses_markers:
            marker_size_spin = QSpinBox()
            marker_size_spin.setMinimum(5)
            marker_size_spin.setMaximum(30)
            marker_size_spin.setValue(10)
            marker_size_spin.setPrefix("M: ")
            marker_size_spin.setMaximumWidth(70)
            marker_size_spin.setToolTip("Marker size for scatter plots")
            layout.addWidget(marker_size_spin)
        else:
            marker_size_spin = None

        # Store references
        self.line_widgets[column_name] = {
            "widget": widget,
            "visible": visible_check,
            "label": label_input,
            "color_btn": color_btn,
            "color": color,
            "width": width_spin,
            "style": style_combo,
            "marker_shape": marker_shape_combo,
            "marker_size": marker_size_spin
        }

        return widget

    def _populate_per_line_settings(self, indicator_type: str):
        """Populate per-line settings based on indicator type."""
        # Show per-line group (may have been hidden for Volume)
        if hasattr(self, "per_line_group") and self.per_line_group:
            self.per_line_group.show()

        # Clear existing widgets
        for col_name, widgets in self.line_widgets.items():
            widgets["widget"].setParent(None)
            widgets["widget"].deleteLater()
        self.line_widgets.clear()

        # Get indicator kind
        kind_map = {
            "SMA": "sma", "EMA": "ema", "Bollinger Bands": "bbands",
            "RSI": "rsi", "MACD": "macd", "ATR": "atr",
            "Stochastic": "stochastic", "OBV": "obv", "VWAP": "vwap",
            "Volume": "volume"
        }
        kind = kind_map.get(indicator_type, indicator_type.lower())

        # Get uses_markers flag from indicator type definition
        indicator_info = self.INDICATOR_TYPES.get(indicator_type, {})
        uses_markers = indicator_info.get("uses_markers", False)

        # Get column metadata
        from ..services import IndicatorService
        metadata_list = IndicatorService.INDICATOR_COLUMN_METADATA.get(kind, [])

        if not metadata_list:
            # No metadata available (shouldn't happen for built-ins)
            return

        # Create widgets for each line, passing uses_markers flag
        for metadata in metadata_list:
            column_name = metadata["column"]
            line_widget = self._create_line_widget(column_name, metadata, uses_markers)
            self.per_line_layout.addWidget(line_widget)

    def _pick_line_color(self, column_name: str):
        """Open color picker for a specific line."""
        if column_name not in self.line_widgets:
            return

        widgets = self.line_widgets[column_name]
        current_color = QColor(*widgets["color"])
        color = QColorDialog.getColor(current_color, self, f"Select Color for {column_name}")

        if color.isValid():
            widgets["color"] = (color.red(), color.green(), color.blue())
            widgets["color_btn"].setStyleSheet(
                f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); "
                f"border: 1px solid #555;"
            )

    def _apply_theme(self):
        """Apply the current theme to the dialog."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Get dark theme stylesheet."""
        return """
            QDialog {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            #titleBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
            #titleLabel {
                background-color: transparent;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #ffffff;
                background-color: #2d2d2d;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QCheckBox {
                color: #cccccc;
                font-size: 13px;
                background-color: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #3d3d3d;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                border-color: #00d4ff;
                background-color: #00d4ff;
            }
            QCheckBox::indicator:hover {
                border-color: #00d4ff;
            }
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #00d4ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #ffffff;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
                padding: 4px;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #00d4ff;
            }
            QSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover {
                border: 1px solid #00d4ff;
            }
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
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
            QPushButton#defaultButton {
                background-color: #00d4ff;
                color: #000000;
                border: 1px solid #00d4ff;
            }
            QPushButton#defaultButton:hover {
                background-color: #00c4ef;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Get light theme stylesheet."""
        return """
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            #titleBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #cccccc;
            }
            #titleLabel {
                background-color: transparent;
                color: #000000;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(0, 0, 0, 0.08);
                color: #000000;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #000000;
                background-color: #f5f5f5;
                border: 2px solid #d0d0d0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QCheckBox {
                color: #333333;
                font-size: 13px;
                background-color: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #cccccc;
                background-color: #f5f5f5;
            }
            QCheckBox::indicator:checked {
                border-color: #0066cc;
                background-color: #0066cc;
            }
            QCheckBox::indicator:hover {
                border-color: #0066cc;
            }
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #0066cc;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #000000;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
                padding: 4px;
            }
            QLineEdit {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #0066cc;
            }
            QSpinBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover {
                border: 1px solid #0066cc;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
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
            QPushButton#defaultButton {
                background-color: #0066cc;
                color: #ffffff;
                border: 1px solid #0066cc;
            }
            QPushButton#defaultButton:hover {
                background-color: #0052a3;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Get Bloomberg theme stylesheet."""
        return """
            QDialog {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            #titleBar {
                background-color: #0d1420;
                border-bottom: 1px solid #1a2332;
            }
            #titleLabel {
                background-color: transparent;
                color: #e8e8e8;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #e8e8e8;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            #titleBarCloseButton:hover {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #e8e8e8;
                background-color: #0d1420;
                border: 2px solid #1a2332;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QCheckBox {
                color: #b0b0b0;
                font-size: 13px;
                background-color: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #1a2838;
                background-color: #0d1420;
            }
            QCheckBox::indicator:checked {
                border-color: #FF8000;
                background-color: #FF8000;
            }
            QCheckBox::indicator:hover {
                border-color: #FF8000;
            }
            QComboBox {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 8px;
                font-size: 13px;
            }
            QComboBox:hover {
                border: 1px solid #FF8000;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #e8e8e8;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1420;
                color: #e8e8e8;
                selection-background-color: #FF8000;
                selection-color: #000000;
                padding: 4px;
            }
            QLineEdit {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #FF8000;
            }
            QSpinBox {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover {
                border: 1px solid #FF8000;
            }
            QPushButton {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                border: 1px solid #FF8000;
                background-color: rgba(255, 128, 0, 0.1);
            }
            QPushButton:pressed {
                background-color: #FF8000;
                color: #000000;
            }
            QPushButton#defaultButton {
                background-color: #FF8000;
                color: #000000;
                border: 1px solid #FF8000;
            }
            QPushButton#defaultButton:hover {
                background-color: #FF9520;
            }
        """

    def _on_type_changed(self, indicator_type: str):
        """Update parameter form when indicator type changes."""
        # Clear existing parameter inputs
        while self.param_form.rowCount() > 0:
            self.param_form.removeRow(0)
        self.param_inputs.clear()

        # Get parameter definitions for this indicator type
        indicator_info = self.INDICATOR_TYPES.get(indicator_type, {})
        params = indicator_info.get("params", [])

        # Special handling for Volume indicator
        if indicator_type == "Volume":
            self._setup_volume_settings()
            return

        # Add parameter inputs
        for param in params:
            label = QLabel(f"{param['label']}:")
            input_field = QLineEdit()
            input_field.setText(param["default"])
            input_field.setPlaceholderText(f"Enter {param['label'].lower()}")

            self.param_form.addRow(label, input_field)
            self.param_inputs[param["name"]] = {
                "widget": input_field,
                "type": param["type"],
            }

        # If no parameters, show a message
        if not params:
            no_params_label = QLabel("This indicator has no configurable parameters.")
            no_params_label.setStyleSheet("font-style: italic; color: #888888;")
            self.param_form.addRow(no_params_label)

        # Update per-line settings
        self._populate_per_line_settings(indicator_type)

    def _setup_volume_settings(self):
        """Setup special settings form for Volume indicator."""
        from ..services import IndicatorService

        # Get current Volume config
        config = IndicatorService.ALL_INDICATORS.get("Volume", {})
        current_display_type = config.get("display_type", "histogram")
        current_up_color = config.get("up_color", (76, 153, 0))
        current_down_color = config.get("down_color", (200, 50, 50))

        # Store colors for later access
        self._volume_up_color = current_up_color
        self._volume_down_color = current_down_color

        # Display type selector
        display_label = QLabel("Display Type:")
        self.volume_display_combo = QComboBox()
        self.volume_display_combo.addItems(["Histogram", "Line"])
        self.volume_display_combo.setCurrentText(
            "Histogram" if current_display_type == "histogram" else "Line"
        )
        self.param_form.addRow(display_label, self.volume_display_combo)

        # Up bar color (green for up candles)
        up_color_label = QLabel("Up Bar Color:")
        up_color_layout = QHBoxLayout()
        self.volume_up_color_btn = QPushButton()
        self.volume_up_color_btn.setFixedSize(60, 25)
        self._update_color_button(self.volume_up_color_btn, current_up_color)
        self.volume_up_color_btn.clicked.connect(self._pick_volume_up_color)
        up_color_layout.addWidget(self.volume_up_color_btn)
        up_color_layout.addStretch()
        up_color_widget = QWidget()
        up_color_widget.setLayout(up_color_layout)
        self.param_form.addRow(up_color_label, up_color_widget)

        # Down bar color (red for down candles)
        down_color_label = QLabel("Down Bar Color:")
        down_color_layout = QHBoxLayout()
        self.volume_down_color_btn = QPushButton()
        self.volume_down_color_btn.setFixedSize(60, 25)
        self._update_color_button(self.volume_down_color_btn, current_down_color)
        self.volume_down_color_btn.clicked.connect(self._pick_volume_down_color)
        down_color_layout.addWidget(self.volume_down_color_btn)
        down_color_layout.addStretch()
        down_color_widget = QWidget()
        down_color_widget.setLayout(down_color_layout)
        self.param_form.addRow(down_color_label, down_color_widget)

        # Note about built-in indicator
        note_label = QLabel("Volume is a built-in indicator and cannot be deleted.")
        note_label.setStyleSheet("font-style: italic; color: #888888;")
        self.param_form.addRow(note_label)

        # Hide per-line settings for Volume (it has its own settings)
        if hasattr(self, "per_line_group"):
            self.per_line_group.hide()

    def _update_color_button(self, button: QPushButton, color: tuple):
        """Update a color button's background to show the selected color."""
        r, g, b = color[:3]
        button.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); border: 1px solid #555;"
        )

    def _pick_volume_up_color(self):
        """Open color picker for Volume up bar color."""
        current = QColor(*self._volume_up_color)
        color = QColorDialog.getColor(current, self, "Select Up Bar Color")
        if color.isValid():
            self._volume_up_color = (color.red(), color.green(), color.blue())
            self._update_color_button(self.volume_up_color_btn, self._volume_up_color)

    def _pick_volume_down_color(self):
        """Open color picker for Volume down bar color."""
        current = QColor(*self._volume_down_color)
        color = QColorDialog.getColor(current, self, "Select Down Bar Color")
        if color.isValid():
            self._volume_down_color = (color.red(), color.green(), color.blue())
            self._update_color_button(self.volume_down_color_btn, self._volume_down_color)

    def _create_indicator(self):
        """Validate inputs and create/update the indicator."""
        from ..services import IndicatorService

        indicator_type = self.type_combo.currentText()

        # Special handling for Volume indicator (built-in)
        if indicator_type == "Volume":
            # Update Volume settings in IndicatorService
            display_type = self.volume_display_combo.currentText().lower()
            IndicatorService.ALL_INDICATORS["Volume"]["display_type"] = display_type
            IndicatorService.ALL_INDICATORS["Volume"]["up_color"] = self._volume_up_color
            IndicatorService.ALL_INDICATORS["Volume"]["down_color"] = self._volume_down_color
            IndicatorService.OSCILLATOR_INDICATORS["Volume"]["display_type"] = display_type
            IndicatorService.OSCILLATOR_INDICATORS["Volume"]["up_color"] = self._volume_up_color
            IndicatorService.OSCILLATOR_INDICATORS["Volume"]["down_color"] = self._volume_down_color

            # Save settings to disk
            IndicatorService.save_volume_settings()

            # Store result for dialog
            self.result = {
                "type": "Volume",
                "params": {},
                "custom_name": None,
                "per_line_appearance": {},
                "is_builtin": True,
            }
            self.accept()
            return

        # Collect and validate parameters
        params = {}
        for param_name, param_info in self.param_inputs.items():
            value_str = param_info["widget"].text().strip()
            param_type = param_info["type"]
            
            try:
                if param_type == "int":
                    value = int(value_str)
                    if value <= 0:
                        raise ValueError("Must be positive")
                elif param_type == "float":
                    value = float(value_str)
                    if value <= 0:
                        raise ValueError("Must be positive")
                else:
                    value = value_str
                
                params[param_name] = value
                
            except ValueError as e:
                CustomMessageBox.warning(
                    self.theme_manager,
                    self,
                    "Invalid Input",
                    f"Invalid value for {param_name}: {value_str}\n{str(e)}",
                )
                return

        # Get custom name if provided
        custom_name = self.name_input.text().strip()

        # Collect per-line appearance settings (REQUIRED - now the only appearance config)
        per_line_appearance = {}
        if self.line_widgets:
            for col_name, widgets in self.line_widgets.items():
                line_config = {
                    "label": widgets["label"].text().strip(),
                    "visible": widgets["visible"].isChecked(),
                    "color": widgets["color"],
                    "line_width": widgets["width"].value(),
                    "line_style": self.LINE_STYLES[widgets["style"].currentText()],
                }

                # Only include marker settings if widgets exist
                if widgets["marker_shape"] is not None:
                    line_config["marker_shape"] = self.MARKER_SHAPES[widgets["marker_shape"].currentText()]
                if widgets["marker_size"] is not None:
                    line_config["marker_size"] = widgets["marker_size"].value()

                per_line_appearance[col_name] = line_config

        # Store the result (NO global appearance dict)
        self.result = {
            "type": indicator_type,
            "params": params,
            "custom_name": custom_name or None,
            "per_line_appearance": per_line_appearance,  # Only this now
        }

        self.accept()

    def get_indicator_config(self):
        """Get the created/edited indicator configuration."""
        return getattr(self, "result", None)