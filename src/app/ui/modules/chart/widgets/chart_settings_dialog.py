from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QColorDialog,
    QGroupBox,
    QCheckBox,
    QWidget,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QMouseEvent

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox


class ChartSettingsDialog(QDialog):
    """
    Dialog for customizing chart appearance settings.
    """

    # Line style options
    LINE_STYLES = {
        "Solid": Qt.SolidLine,
        "Dashed": Qt.DashLine,
        "Dotted": Qt.DotLine,
        "Dash-Dot": Qt.DashDotLine,
    }

    def __init__(self, theme_manager: ThemeManager, current_settings: dict, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(500)

        # Remove native title bar
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self.theme_manager = theme_manager
        self.current_settings = current_settings

        # Color selections
        self.candle_up_color = current_settings.get("candle_up_color", (76, 153, 0))
        self.candle_down_color = current_settings.get("candle_down_color", (200, 50, 50))
        self.line_color = current_settings.get("line_color", None)
        self.chart_background = current_settings.get("chart_background", None)

        # For window dragging
        self._drag_pos = QPoint()

        self._setup_ui()
        self._apply_theme()
        self._load_current_settings()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Custom title bar
        self.title_bar = self._create_title_bar("Chart Settings")
        layout.addWidget(self.title_bar)

        # Content container
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        # Candlestick settings
        candle_group = self._create_candle_group()
        content_layout.addWidget(candle_group)

        # Line chart settings
        line_group = self._create_line_group()
        content_layout.addWidget(line_group)

        # Chart background settings
        background_group = self._create_background_group()
        content_layout.addWidget(background_group)

        # General settings
        general_group = self._create_general_group()
        content_layout.addWidget(general_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(self.reset_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setDefault(True)
        self.save_btn.setObjectName("defaultButton")
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)

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

    def _create_candle_group(self) -> QGroupBox:
        """Create candlestick settings group."""
        group = QGroupBox("Candlestick Settings")
        group.setObjectName("settingsGroup")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Up candle color
        up_color_layout = QHBoxLayout()
        self.up_color_btn = QPushButton("Choose Color")
        self.up_color_btn.clicked.connect(lambda: self._choose_color("up"))
        up_color_layout.addWidget(self.up_color_btn)
        
        self.up_color_preview = QLabel("●")
        self.up_color_preview.setStyleSheet(
            f"font-size: 24px; color: rgb({self.candle_up_color[0]}, "
            f"{self.candle_up_color[1]}, {self.candle_up_color[2]});"
        )
        up_color_layout.addWidget(self.up_color_preview)
        up_color_layout.addStretch()
        
        layout.addRow("Up Candle Color:", up_color_layout)

        # Down candle color
        down_color_layout = QHBoxLayout()
        self.down_color_btn = QPushButton("Choose Color")
        self.down_color_btn.clicked.connect(lambda: self._choose_color("down"))
        down_color_layout.addWidget(self.down_color_btn)
        
        self.down_color_preview = QLabel("●")
        self.down_color_preview.setStyleSheet(
            f"font-size: 24px; color: rgb({self.candle_down_color[0]}, "
            f"{self.candle_down_color[1]}, {self.candle_down_color[2]});"
        )
        down_color_layout.addWidget(self.down_color_preview)
        down_color_layout.addStretch()
        
        layout.addRow("Down Candle Color:", down_color_layout)

        # Candle width
        self.candle_width_spin = QDoubleSpinBox()
        self.candle_width_spin.setMinimum(0.1)
        self.candle_width_spin.setMaximum(1.0)
        self.candle_width_spin.setSingleStep(0.1)
        self.candle_width_spin.setValue(0.6)
        self.candle_width_spin.setDecimals(1)
        layout.addRow("Candle Width:", self.candle_width_spin)

        group.setLayout(layout)
        return group

    def _create_line_group(self) -> QGroupBox:
        """Create line chart settings group."""
        group = QGroupBox("Line Chart Settings")
        group.setObjectName("settingsGroup")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Line color with "Use Theme Default" checkbox
        line_color_layout = QVBoxLayout()
        
        self.line_use_theme_check = QCheckBox("Use Theme Default")
        self.line_use_theme_check.setChecked(self.line_color is None)
        self.line_use_theme_check.toggled.connect(self._on_line_theme_toggled)
        line_color_layout.addWidget(self.line_use_theme_check)
        
        line_color_picker_layout = QHBoxLayout()
        self.line_color_btn = QPushButton("Choose Color")
        self.line_color_btn.clicked.connect(lambda: self._choose_color("line"))
        self.line_color_btn.setEnabled(self.line_color is not None)
        line_color_picker_layout.addWidget(self.line_color_btn)
        
        self.line_color_preview = QLabel("●")
        if self.line_color:
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.line_color[0]}, "
                f"{self.line_color[1]}, {self.line_color[2]});"
            )
        else:
            # Show theme default
            theme_color = self.theme_manager.get_chart_line_color()
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({theme_color[0]}, "
                f"{theme_color[1]}, {theme_color[2]});"
            )
        line_color_picker_layout.addWidget(self.line_color_preview)
        line_color_picker_layout.addStretch()
        
        line_color_layout.addLayout(line_color_picker_layout)
        layout.addRow("Line Color:", line_color_layout)

        # Line width
        self.line_width_spin = QSpinBox()
        self.line_width_spin.setMinimum(1)
        self.line_width_spin.setMaximum(10)
        self.line_width_spin.setValue(2)
        self.line_width_spin.setSuffix(" px")
        layout.addRow("Line Width:", self.line_width_spin)

        # Line style
        self.line_style_combo = QComboBox()
        self.line_style_combo.addItems(list(self.LINE_STYLES.keys()))
        layout.addRow("Line Style:", self.line_style_combo)

        group.setLayout(layout)
        return group

    def _create_background_group(self) -> QGroupBox:
        """Create background settings group."""
        group = QGroupBox("Chart Background")
        group.setObjectName("settingsGroup")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Background color with "Use Theme Default" checkbox
        bg_layout = QVBoxLayout()
        
        self.bg_use_theme_check = QCheckBox("Use Theme Default")
        self.bg_use_theme_check.setChecked(self.chart_background is None)
        self.bg_use_theme_check.toggled.connect(self._on_bg_theme_toggled)
        bg_layout.addWidget(self.bg_use_theme_check)
        
        bg_color_picker_layout = QHBoxLayout()
        self.bg_color_btn = QPushButton("Choose Color")
        self.bg_color_btn.clicked.connect(lambda: self._choose_color("background"))
        self.bg_color_btn.setEnabled(self.chart_background is not None)
        bg_color_picker_layout.addWidget(self.bg_color_btn)
        
        self.bg_color_preview = QLabel("■")
        if self.chart_background:
            self.bg_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.chart_background[0]}, "
                f"{self.chart_background[1]}, {self.chart_background[2]});"
            )
        else:
            # Show theme default (simplified, just show a placeholder)
            self.bg_color_preview.setStyleSheet("font-size: 24px; color: #888888;")
        bg_color_picker_layout.addWidget(self.bg_color_preview)
        bg_color_picker_layout.addStretch()
        
        bg_layout.addLayout(bg_color_picker_layout)
        layout.addRow("Background Color:", bg_layout)

        group.setLayout(layout)
        return group

    def _create_general_group(self) -> QGroupBox:
        """Create general settings group."""
        group = QGroupBox("General")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Price label toggle
        self.show_price_label_check = QCheckBox("Show price label")
        self.show_price_label_check.setChecked(
            self.current_settings.get("show_price_label", True)
        )
        layout.addWidget(self.show_price_label_check)

        # Mouse price label toggle
        self.show_mouse_price_label_check = QCheckBox("Show price label at mouse position")
        self.show_mouse_price_label_check.setChecked(
            self.current_settings.get("show_mouse_price_label", True)
        )
        layout.addWidget(self.show_mouse_price_label_check)

        # Date label toggle
        self.show_date_label_check = QCheckBox("Show date label on bottom axis")
        self.show_date_label_check.setChecked(
            self.current_settings.get("show_date_label", True)
        )
        layout.addWidget(self.show_date_label_check)

        # Gridlines toggle
        self.show_gridlines_check = QCheckBox("Show gridlines")
        self.show_gridlines_check.setChecked(
            self.current_settings.get("show_gridlines", False)
        )
        layout.addWidget(self.show_gridlines_check)

        # Crosshair toggle
        self.show_crosshair_check = QCheckBox("Show crosshair lines")
        self.show_crosshair_check.setChecked(
            self.current_settings.get("show_crosshair", True)
        )
        layout.addWidget(self.show_crosshair_check)

        info_label = QLabel(
            "Custom settings will override theme defaults.\n"
            "Changing themes will not affect your custom colors."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888888; font-style: italic; font-size: 11px;")
        layout.addWidget(info_label)

        group.setLayout(layout)
        return group

    def _on_line_theme_toggled(self, checked: bool):
        """Handle line theme default checkbox toggle."""
        self.line_color_btn.setEnabled(not checked)
        if checked:
            # Show theme default color
            self.line_color = None
            theme_color = self.theme_manager.get_chart_line_color()
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({theme_color[0]}, "
                f"{theme_color[1]}, {theme_color[2]});"
            )

    def _on_bg_theme_toggled(self, checked: bool):
        """Handle background theme default checkbox toggle."""
        self.bg_color_btn.setEnabled(not checked)
        if checked:
            # Show theme default
            self.chart_background = None
            self.bg_color_preview.setStyleSheet("font-size: 24px; color: #888888;")

    def _choose_color(self, color_type: str):
        """Open color picker for a specific color type."""
        if color_type == "up":
            current_color = QColor(*self.candle_up_color)
            title = "Select Up Candle Color"
        elif color_type == "down":
            current_color = QColor(*self.candle_down_color)
            title = "Select Down Candle Color"
        elif color_type == "line":
            if self.line_color:
                current_color = QColor(*self.line_color)
            else:
                theme_color = self.theme_manager.get_chart_line_color()
                current_color = QColor(*theme_color)
            title = "Select Line Color"
        elif color_type == "background":
            if self.chart_background:
                current_color = QColor(*self.chart_background)
            else:
                current_color = QColor(30, 30, 30)  # Default dark
            title = "Select Background Color"
        else:
            return

        color = QColorDialog.getColor(current_color, self, title)
        
        if color.isValid():
            rgb = (color.red(), color.green(), color.blue())
            
            if color_type == "up":
                self.candle_up_color = rgb
                self.up_color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                )
            elif color_type == "down":
                self.candle_down_color = rgb
                self.down_color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                )
            elif color_type == "line":
                self.line_color = rgb
                self.line_color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                )
            elif color_type == "background":
                self.chart_background = rgb
                self.bg_color_preview.setStyleSheet(
                    f"font-size: 24px; color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]});"
                )

    def _load_current_settings(self):
        """Load current settings into the UI."""
        # Candle width
        self.candle_width_spin.setValue(
            self.current_settings.get("candle_width", 0.6)
        )
        
        # Line width
        self.line_width_spin.setValue(
            self.current_settings.get("line_width", 2)
        )
        
        # Line style
        line_style = self.current_settings.get("line_style", Qt.SolidLine)
        for style_name, style_value in self.LINE_STYLES.items():
            if style_value == line_style:
                index = self.line_style_combo.findText(style_name)
                if index >= 0:
                    self.line_style_combo.setCurrentIndex(index)
                break

    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Reset to Defaults",
            "Are you sure you want to reset all chart settings to defaults?",
            CustomMessageBox.Yes | CustomMessageBox.No,
            CustomMessageBox.No,
        )

        if reply == CustomMessageBox.Yes:
            # Reset to defaults
            self.candle_up_color = (76, 153, 0)
            self.candle_down_color = (200, 50, 50)
            self.line_color = None
            self.chart_background = None

            # Update UI
            self.up_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.candle_up_color[0]}, "
                f"{self.candle_up_color[1]}, {self.candle_up_color[2]});"
            )
            self.down_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.candle_down_color[0]}, "
                f"{self.candle_down_color[1]}, {self.candle_down_color[2]});"
            )

            self.line_use_theme_check.setChecked(True)
            self.bg_use_theme_check.setChecked(True)

            self.candle_width_spin.setValue(0.6)
            self.line_width_spin.setValue(2)
            self.line_style_combo.setCurrentIndex(0)  # Solid

            # Reset General settings checkboxes to defaults
            self.show_price_label_check.setChecked(True)
            self.show_mouse_price_label_check.setChecked(True)
            self.show_date_label_check.setChecked(True)
            self.show_gridlines_check.setChecked(False)
            self.show_crosshair_check.setChecked(True)

    def _save_settings(self):
        """Save the settings and close."""
        self.result = {
            "candle_up_color": self.candle_up_color,
            "candle_down_color": self.candle_down_color,
            "candle_width": self.candle_width_spin.value(),
            "line_color": self.line_color,
            "line_width": self.line_width_spin.value(),
            "line_style": self.LINE_STYLES[self.line_style_combo.currentText()],
            "chart_background": self.chart_background,
            "show_price_label": self.show_price_label_check.isChecked(),
            "show_mouse_price_label": self.show_mouse_price_label_check.isChecked(),
            "show_date_label": self.show_date_label_check.isChecked(),
            "show_gridlines": self.show_gridlines_check.isChecked(),
            "show_crosshair": self.show_crosshair_check.isChecked(),
        }
        self.accept()

    def get_settings(self):
        """Get the configured settings."""
        return getattr(self, "result", None)

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
            QSpinBox, QDoubleSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
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
            QSpinBox, QDoubleSpinBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
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
            QSpinBox, QDoubleSpinBox {
                background-color: transparent;
                color: #e8e8e8;
                border: 1px solid #1a2332;
                border-radius: 2px;
                padding: 8px;
                font-size: 13px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
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