"""Chart Settings Dialog - Settings dialog using ThemedDialog base class."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QDoubleSpinBox,
    QSpinBox,
    QColorDialog,
    QGroupBox,
    QCheckBox,
    QGridLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox, ThemedDialog
from app.services.theme_stylesheet_service import ThemeStylesheetService


class ChartSettingsDialog(ThemedDialog):
    """
    Dialog for customizing chart appearance settings.

    Inherits from ThemedDialog for consistent styling and title bar.
    """

    # Line style options
    LINE_STYLES = {
        "Solid": Qt.SolidLine,
        "Dashed": Qt.DashLine,
        "Dotted": Qt.DotLine,
        "Dash-Dot": Qt.DashDotLine,
    }

    # Reverse mapping for display
    LINE_STYLE_NAMES = {v: k for k, v in LINE_STYLES.items()}

    def __init__(self, theme_manager: ThemeManager, current_settings: dict, parent=None):
        # Initialize color values before super().__init__
        self.current_settings = current_settings
        self.candle_up_color = current_settings.get("candle_up_color", (76, 153, 0))
        self.candle_down_color = current_settings.get("candle_down_color", (200, 50, 50))
        self.line_color = current_settings.get("line_color", None)
        self.chart_background = current_settings.get("chart_background", None)

        super().__init__(theme_manager, "Chart Settings", parent, min_width=520)
        self._load_current_settings()

    def _setup_content(self, layout: QVBoxLayout):
        """Set up dialog content (called by ThemedDialog)."""
        # Candlestick settings
        candle_group = self._create_candle_group()
        layout.addWidget(candle_group)

        # Line chart settings
        line_group = self._create_line_group()
        layout.addWidget(line_group)

        # Chart background settings
        background_group = self._create_background_group()
        layout.addWidget(background_group)

        # Display options
        display_group = self._create_display_group()
        layout.addWidget(display_group)

        # Add stretch
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(self.reset_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(100, 36)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedSize(100, 36)
        self.save_btn.setDefault(True)
        self.save_btn.setObjectName("defaultButton")
        self.save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

    def _create_candle_group(self) -> QGroupBox:
        """Create candlestick settings group."""
        group = QGroupBox("Candlestick Settings")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Single row with all candlestick settings
        candle_row = QHBoxLayout()
        candle_row.setSpacing(8)

        # Up candle color
        up_label = QLabel("Up:")
        candle_row.addWidget(up_label)

        self.up_color_btn = QPushButton("Color")
        self.up_color_btn.setFixedWidth(65)
        self.up_color_btn.clicked.connect(lambda: self._choose_color("up"))
        candle_row.addWidget(self.up_color_btn)

        self.up_color_preview = QLabel("\u25cf")  # ●
        self.up_color_preview.setFixedWidth(24)
        self.up_color_preview.setStyleSheet(
            f"font-size: 24px; color: rgb({self.candle_up_color[0]}, "
            f"{self.candle_up_color[1]}, {self.candle_up_color[2]});"
        )
        candle_row.addWidget(self.up_color_preview)

        candle_row.addSpacing(20)

        # Down candle color
        down_label = QLabel("Down:")
        candle_row.addWidget(down_label)

        self.down_color_btn = QPushButton("Color")
        self.down_color_btn.setFixedWidth(65)
        self.down_color_btn.clicked.connect(lambda: self._choose_color("down"))
        candle_row.addWidget(self.down_color_btn)

        self.down_color_preview = QLabel("\u25cf")  # ●
        self.down_color_preview.setFixedWidth(24)
        self.down_color_preview.setStyleSheet(
            f"font-size: 24px; color: rgb({self.candle_down_color[0]}, "
            f"{self.candle_down_color[1]}, {self.candle_down_color[2]});"
        )
        candle_row.addWidget(self.down_color_preview)

        candle_row.addSpacing(20)

        # Candle width
        width_label = QLabel("Width:")
        candle_row.addWidget(width_label)

        self.candle_width_spin = QDoubleSpinBox()
        self.candle_width_spin.setMinimum(0.1)
        self.candle_width_spin.setMaximum(1.0)
        self.candle_width_spin.setSingleStep(0.1)
        self.candle_width_spin.setValue(0.6)
        self.candle_width_spin.setDecimals(1)
        self.candle_width_spin.setFixedWidth(70)
        candle_row.addWidget(self.candle_width_spin)

        candle_row.addStretch()
        layout.addLayout(candle_row)

        group.setLayout(layout)
        return group

    def _create_line_group(self) -> QGroupBox:
        """Create line chart settings group."""
        group = QGroupBox("Line Chart Settings")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Single row with all line settings
        line_row = QHBoxLayout()
        line_row.setSpacing(8)

        self.line_use_theme_check = QCheckBox("Theme Default")
        self.line_use_theme_check.setChecked(self.line_color is None)
        self.line_use_theme_check.toggled.connect(self._on_line_theme_toggled)
        line_row.addWidget(self.line_use_theme_check)

        line_row.addSpacing(12)

        color_label = QLabel("Color:")
        line_row.addWidget(color_label)

        self.line_color_btn = QPushButton("Color")
        self.line_color_btn.setFixedWidth(65)
        self.line_color_btn.clicked.connect(self._on_line_color_clicked)
        line_row.addWidget(self.line_color_btn)

        self.line_color_preview = QLabel("\u25cf")  # ●
        self.line_color_preview.setFixedWidth(24)
        if self.line_color:
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.line_color[0]}, "
                f"{self.line_color[1]}, {self.line_color[2]});"
            )
        else:
            theme_color = self.theme_manager.get_chart_line_color()
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({theme_color[0]}, "
                f"{theme_color[1]}, {theme_color[2]});"
            )
        line_row.addWidget(self.line_color_preview)

        line_row.addSpacing(20)

        width_label = QLabel("Width:")
        line_row.addWidget(width_label)

        self.line_width_spin = QSpinBox()
        self.line_width_spin.setMinimum(1)
        self.line_width_spin.setMaximum(10)
        self.line_width_spin.setValue(2)
        self.line_width_spin.setSuffix(" px")
        self.line_width_spin.setFixedWidth(70)
        line_row.addWidget(self.line_width_spin)

        line_row.addSpacing(20)

        style_label = QLabel("Style:")
        line_row.addWidget(style_label)

        self.line_style_combo = QComboBox()
        self.line_style_combo.addItems(list(self.LINE_STYLES.keys()))
        self.line_style_combo.setFixedWidth(100)
        line_row.addWidget(self.line_style_combo)

        line_row.addStretch()
        layout.addLayout(line_row)

        group.setLayout(layout)
        return group

    def _create_background_group(self) -> QGroupBox:
        """Create background settings group."""
        group = QGroupBox("Chart Background")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Single row with theme checkbox and color picker
        bg_row = QHBoxLayout()
        bg_row.setSpacing(8)

        self.bg_use_theme_check = QCheckBox("Theme Default")
        self.bg_use_theme_check.setChecked(self.chart_background is None)
        self.bg_use_theme_check.toggled.connect(self._on_bg_theme_toggled)
        bg_row.addWidget(self.bg_use_theme_check)

        bg_row.addSpacing(12)

        bg_label = QLabel("Color:")
        bg_row.addWidget(bg_label)

        self.bg_color_btn = QPushButton("Color")
        self.bg_color_btn.setFixedWidth(65)
        self.bg_color_btn.clicked.connect(self._on_bg_color_clicked)
        bg_row.addWidget(self.bg_color_btn)

        self.bg_color_preview = QLabel("\u25a0")  # ■
        self.bg_color_preview.setFixedWidth(24)
        if self.chart_background:
            self.bg_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.chart_background[0]}, "
                f"{self.chart_background[1]}, {self.chart_background[2]});"
            )
        else:
            self.bg_color_preview.setStyleSheet("font-size: 24px; color: #888888;")
        bg_row.addWidget(self.bg_color_preview)

        bg_row.addStretch()
        layout.addLayout(bg_row)

        group.setLayout(layout)
        return group

    def _create_display_group(self) -> QGroupBox:
        """Create display options group."""
        group = QGroupBox("Display Options")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Two-column grid for checkboxes
        checkbox_grid = QGridLayout()
        checkbox_grid.setSpacing(8)

        # Left column
        self.show_price_label_check = QCheckBox("Show price label")
        self.show_price_label_check.setChecked(
            self.current_settings.get("show_price_label", True)
        )
        checkbox_grid.addWidget(self.show_price_label_check, 0, 0)

        self.show_mouse_price_label_check = QCheckBox("Show mouse price label")
        self.show_mouse_price_label_check.setChecked(
            self.current_settings.get("show_mouse_price_label", True)
        )
        checkbox_grid.addWidget(self.show_mouse_price_label_check, 1, 0)

        self.show_crosshair_check = QCheckBox("Show crosshair")
        self.show_crosshair_check.setChecked(
            self.current_settings.get("show_crosshair", True)
        )
        checkbox_grid.addWidget(self.show_crosshair_check, 2, 0)

        # Right column
        self.show_date_label_check = QCheckBox("Show date label")
        self.show_date_label_check.setChecked(
            self.current_settings.get("show_date_label", True)
        )
        checkbox_grid.addWidget(self.show_date_label_check, 0, 1)

        self.show_gridlines_check = QCheckBox("Show gridlines")
        self.show_gridlines_check.setChecked(
            self.current_settings.get("show_gridlines", False)
        )
        checkbox_grid.addWidget(self.show_gridlines_check, 1, 1)

        layout.addLayout(checkbox_grid)

        # Info label
        info_label = QLabel(
            "Custom colors override theme defaults and persist across theme changes."
        )
        info_label.setWordWrap(True)
        info_label.setObjectName("settingsDescription")
        layout.addWidget(info_label)

        group.setLayout(layout)
        return group

    def _on_line_theme_toggled(self, checked: bool):
        """Handle line theme default checkbox toggle."""
        if checked:
            self.line_color = None
            theme_color = self.theme_manager.get_chart_line_color()
            self.line_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({theme_color[0]}, "
                f"{theme_color[1]}, {theme_color[2]});"
            )

    def _on_bg_theme_toggled(self, checked: bool):
        """Handle background theme default checkbox toggle."""
        if checked:
            self.chart_background = None
            self.bg_color_preview.setStyleSheet("font-size: 24px; color: #888888;")

    def _on_line_color_clicked(self):
        """Handle line color button click - disable theme default and open picker."""
        self.line_use_theme_check.setChecked(False)
        self._choose_color("line")

    def _on_bg_color_clicked(self):
        """Handle background color button click - disable theme default and open picker."""
        self.bg_use_theme_check.setChecked(False)
        self._choose_color("background")

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
                current_color = QColor(30, 30, 30)
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
        style_name = self.LINE_STYLE_NAMES.get(line_style, "Solid")
        index = self.line_style_combo.findText(style_name)
        if index >= 0:
            self.line_style_combo.setCurrentIndex(index)

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
            # Reset colors
            self.candle_up_color = (76, 153, 0)
            self.candle_down_color = (200, 50, 50)
            self.line_color = None
            self.chart_background = None

            # Update color previews
            self.up_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.candle_up_color[0]}, "
                f"{self.candle_up_color[1]}, {self.candle_up_color[2]});"
            )
            self.down_color_preview.setStyleSheet(
                f"font-size: 24px; color: rgb({self.candle_down_color[0]}, "
                f"{self.candle_down_color[1]}, {self.candle_down_color[2]});"
            )

            # Reset theme checkboxes
            self.line_use_theme_check.setChecked(True)
            self.bg_use_theme_check.setChecked(True)

            # Reset spinboxes and combos
            self.candle_width_spin.setValue(0.6)
            self.line_width_spin.setValue(2)
            self.line_style_combo.setCurrentIndex(0)

            # Reset display options to defaults
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
        """Apply theme styling."""
        super()._apply_theme()

        theme = self.theme_manager.current_theme
        colors = ThemeStylesheetService.get_colors(theme)

        # Additional styling for group boxes and inputs
        additional_style = f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {colors['border']};
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: {colors['text']};
            }}
            QComboBox {{
                background-color: {colors['bg_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            QComboBox:focus {{
                border-color: {colors['accent']};
            }}
            QSpinBox, QDoubleSpinBox {{
                background-color: {colors['bg_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 3px;
                padding: 4px 8px;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {colors['accent']};
            }}
            QCheckBox {{
                color: {colors['text']};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QLabel#settingsDescription {{
                color: {colors['text_muted']};
                font-size: 12px;
                margin-top: 8px;
            }}
        """

        self.setStyleSheet(self.styleSheet() + additional_style)
