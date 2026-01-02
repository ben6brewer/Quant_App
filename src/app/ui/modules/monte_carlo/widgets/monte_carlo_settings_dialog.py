"""Monte Carlo Settings Dialog - Settings dialog for Monte Carlo module."""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QSpinBox,
    QColorDialog,
    QGroupBox,
    QCheckBox,
    QWidget,
    QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import ThemedDialog, CustomMessageBox
from app.services.theme_stylesheet_service import ThemeStylesheetService


class MonteCarloSettingsDialog(ThemedDialog):
    """
    Dialog for customizing Monte Carlo chart settings.

    Provides controls for:
    - Chart settings (crosshair, labels, gridlines, background)
    - Line customization (portfolio/benchmark median color, style, width)
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

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: dict,
        parent=None,
        has_benchmark: bool = False,
    ):
        self.current_settings = current_settings
        self.has_benchmark = has_benchmark

        # Initialize color values from settings
        self._init_color_values()

        super().__init__(
            theme_manager,
            "Monte Carlo Settings",
            parent,
            min_width=700,
            min_height=480,
        )

    def _init_color_values(self):
        """Initialize color values from current settings."""
        self.chart_background_color = self.current_settings.get("chart_background", None)
        self.portfolio_median_color = self.current_settings.get(
            "portfolio_median_color", (255, 255, 255)
        )
        self.benchmark_median_color = self.current_settings.get(
            "benchmark_median_color", (255, 165, 0)
        )

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content - called by ThemedDialog."""
        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)

        # Chart Settings group
        chart_group = self._create_chart_settings_group()
        content_layout.addWidget(chart_group)

        # Line Customization group
        line_group = self._create_line_customization_group()
        content_layout.addWidget(line_group)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll, stretch=1)

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

        layout.addLayout(button_layout)

    def _create_chart_settings_group(self) -> QGroupBox:
        """Create chart settings group."""
        group = QGroupBox("Chart Settings")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Crosshair toggle
        self.crosshair_check = QCheckBox("Show crosshair")
        self.crosshair_check.setChecked(self.current_settings.get("show_crosshair", True))
        layout.addWidget(self.crosshair_check)

        # Median label toggle
        self.median_label_check = QCheckBox("Show median price label")
        self.median_label_check.setChecked(self.current_settings.get("show_median_label", True))
        layout.addWidget(self.median_label_check)

        # Gridlines toggle
        self.gridlines_check = QCheckBox("Show gridlines")
        self.gridlines_check.setChecked(self.current_settings.get("show_gridlines", True))
        layout.addWidget(self.gridlines_check)

        # Background color row
        bg_row = QHBoxLayout()
        bg_row.setSpacing(8)

        bg_label = QLabel("Chart Background:")
        bg_label.setMinimumWidth(160)
        bg_row.addWidget(bg_label)

        self.bg_color_btn = QPushButton("Color")
        self.bg_color_btn.setFixedWidth(75)
        self.bg_color_btn.clicked.connect(lambda: self._choose_color("chart_background"))
        bg_row.addWidget(self.bg_color_btn)

        self.bg_color_preview = QLabel("\u25a0")  # ■
        self.bg_color_preview.setFixedWidth(24)
        self._update_color_preview(self.bg_color_preview, self.chart_background_color, "chart_background")
        bg_row.addWidget(self.bg_color_preview)

        bg_row.addStretch()
        layout.addLayout(bg_row)

        group.setLayout(layout)
        return group

    def _create_line_customization_group(self) -> QGroupBox:
        """Create line customization group."""
        group = QGroupBox("Line Customization")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Portfolio median row
        portfolio_row = self._create_viz_row(
            "Portfolio Median",
            "portfolio_median",
            self.current_settings.get("show_portfolio_median", True),
            self.portfolio_median_color,
            self.current_settings.get("portfolio_median_line_style", Qt.SolidLine),
            self.current_settings.get("portfolio_median_line_width", 2),
        )
        layout.addLayout(portfolio_row)

        # Benchmark median row (always shown)
        benchmark_row = self._create_viz_row(
            "Benchmark Median",
            "benchmark_median",
            self.current_settings.get("show_benchmark_median", True),
            self.benchmark_median_color,
            self.current_settings.get("benchmark_median_line_style", Qt.SolidLine),
            self.current_settings.get("benchmark_median_line_width", 2),
        )
        layout.addLayout(benchmark_row)

        # Note about std dev clouds
        cloud_note = QLabel(
            "Note: Confidence band colors are auto-derived from median colors "
            "(same hue with different opacity levels)."
        )
        cloud_note.setWordWrap(True)
        cloud_note.setObjectName("noteLabel")
        layout.addWidget(cloud_note)

        group.setLayout(layout)
        return group

    def _create_viz_row(
        self,
        label: str,
        prefix: str,
        show: bool,
        color: Optional[Tuple[int, int, int]],
        style: Qt.PenStyle,
        width: int,
    ) -> QHBoxLayout:
        """Create a single-line visualization row with toggle, color, style, and width."""
        row = QHBoxLayout()
        row.setSpacing(8)

        # Toggle checkbox with fixed width label area
        toggle = QCheckBox(label)
        toggle.setChecked(show)
        toggle.setMinimumWidth(160)
        row.addWidget(toggle)
        setattr(self, f"{prefix}_toggle", toggle)

        # Color picker
        color_btn = QPushButton("Color")
        color_btn.setFixedWidth(75)
        color_btn.clicked.connect(lambda: self._choose_color(prefix))
        row.addWidget(color_btn)
        setattr(self, f"{prefix}_color_btn", color_btn)

        preview = QLabel("\u25cf")  # ●
        preview.setFixedWidth(24)
        self._update_color_preview(preview, color, prefix)
        row.addWidget(preview)
        setattr(self, f"{prefix}_color_preview", preview)

        # Spacer
        row.addSpacing(20)

        # Line style dropdown
        style_label = QLabel("Style:")
        row.addWidget(style_label)

        style_combo = QComboBox()
        style_combo.addItems(list(self.LINE_STYLES.keys()))
        style_name = self.LINE_STYLE_NAMES.get(style, "Solid")
        style_combo.setCurrentText(style_name)
        style_combo.setFixedWidth(90)
        row.addWidget(style_combo)
        setattr(self, f"{prefix}_style_combo", style_combo)

        # Width spinbox
        width_label = QLabel("Width:")
        row.addWidget(width_label)

        width_spin = QSpinBox()
        width_spin.setMinimum(1)
        width_spin.setMaximum(10)
        width_spin.setValue(width)
        width_spin.setSuffix(" px")
        width_spin.setFixedWidth(70)
        row.addWidget(width_spin)
        setattr(self, f"{prefix}_width_spin", width_spin)

        row.addStretch()
        return row

    def _update_color_preview(
        self,
        preview: QLabel,
        color: Optional[Tuple[int, int, int]],
        prefix: str = "",
    ) -> None:
        """Update color preview label. Shows theme default color when color is None."""
        if color:
            preview.setStyleSheet(
                f"font-size: 24px; color: rgb({color[0]}, {color[1]}, {color[2]});"
            )
        else:
            # Show the theme default color
            theme_color = self._get_theme_default_color(prefix)
            preview.setStyleSheet(
                f"font-size: 24px; color: rgb({theme_color[0]}, {theme_color[1]}, {theme_color[2]});"
            )

    def _get_theme_default_color(self, prefix: str) -> Tuple[int, int, int]:
        """Get the theme default color for a given setting prefix."""
        theme = self.theme_manager.current_theme
        c = ThemeStylesheetService.get_colors(theme)

        # Map prefixes to appropriate colors
        if prefix == "chart_background":
            # Parse the background color from theme
            bg = c["bg"]
            if bg.startswith("#"):
                r = int(bg[1:3], 16)
                g = int(bg[3:5], 16)
                b = int(bg[5:7], 16)
                return (r, g, b)
            return (30, 30, 30)  # fallback
        elif prefix == "portfolio_median":
            return (255, 255, 255)  # White
        elif prefix == "benchmark_median":
            return (255, 165, 0)  # Orange
        else:
            return (255, 255, 255)

    def _choose_color(self, color_type: str) -> None:
        """Open color picker for a specific color type."""
        # Get current color
        color_attr = f"{color_type}_color"
        current_color_value = getattr(self, color_attr, None)

        if current_color_value:
            current_color = QColor(*current_color_value)
        else:
            # Start with theme default color
            theme_default = self._get_theme_default_color(color_type)
            current_color = QColor(*theme_default)

        title = f"Select {color_type.replace('_', ' ').title()} Color"
        color = QColorDialog.getColor(current_color, self, title)

        if color.isValid():
            rgb = (color.red(), color.green(), color.blue())
            setattr(self, color_attr, rgb)

            # Update preview
            preview = getattr(self, f"{color_type}_color_preview", None)
            if preview:
                self._update_color_preview(preview, rgb, color_type)

    def _reset_to_defaults(self) -> None:
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
            # Reset chart settings
            self.crosshair_check.setChecked(True)
            self.median_label_check.setChecked(True)
            self.gridlines_check.setChecked(False)
            self.chart_background_color = None
            self._update_color_preview(self.bg_color_preview, None, "chart_background")

            # Reset portfolio median
            self.portfolio_median_toggle.setChecked(True)
            self.portfolio_median_color = (255, 255, 255)
            self._update_color_preview(
                self.portfolio_median_color_preview, self.portfolio_median_color, "portfolio_median"
            )
            self.portfolio_median_style_combo.setCurrentText("Solid")
            self.portfolio_median_width_spin.setValue(2)

            # Reset benchmark median
            self.benchmark_median_toggle.setChecked(True)
            self.benchmark_median_color = (255, 165, 0)
            self._update_color_preview(
                self.benchmark_median_color_preview, self.benchmark_median_color, "benchmark_median"
            )
            self.benchmark_median_style_combo.setCurrentText("Solid")
            self.benchmark_median_width_spin.setValue(2)

    def _save_settings(self) -> None:
        """Save the settings and close."""
        # Start with current settings to preserve values not shown in dialog
        self.result = dict(self.current_settings)

        # Save chart settings
        self.result["show_crosshair"] = self.crosshair_check.isChecked()
        self.result["show_median_label"] = self.median_label_check.isChecked()
        self.result["show_gridlines"] = self.gridlines_check.isChecked()
        self.result["chart_background"] = self.chart_background_color

        # Save portfolio median settings
        self.result["show_portfolio_median"] = self.portfolio_median_toggle.isChecked()
        self.result["portfolio_median_color"] = self.portfolio_median_color
        self.result["portfolio_median_line_style"] = self.LINE_STYLES[
            self.portfolio_median_style_combo.currentText()
        ]
        self.result["portfolio_median_line_width"] = self.portfolio_median_width_spin.value()

        # Save benchmark median settings
        self.result["show_benchmark_median"] = self.benchmark_median_toggle.isChecked()
        self.result["benchmark_median_color"] = self.benchmark_median_color
        self.result["benchmark_median_line_style"] = self.LINE_STYLES[
            self.benchmark_median_style_combo.currentText()
        ]
        self.result["benchmark_median_line_width"] = self.benchmark_median_width_spin.value()

        self.accept()

    def get_settings(self):
        """Get the configured settings."""
        return getattr(self, "result", None)
