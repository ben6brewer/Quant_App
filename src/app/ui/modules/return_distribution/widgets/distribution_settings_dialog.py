"""Distribution Settings Dialog - Settings dialog using ThemedDialog base class."""

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
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox, ThemedDialog


class DistributionSettingsDialog(ThemedDialog):
    """
    Dialog for customizing return distribution settings.

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

    def __init__(
        self,
        theme_manager: ThemeManager,
        current_settings: dict,
        parent=None,
        has_benchmark: bool = False,
    ):
        # Store settings before super().__init__
        self.current_settings = current_settings
        self.has_benchmark = has_benchmark

        # Initialize color values from settings
        self._init_color_values()

        super().__init__(
            theme_manager,
            "Distribution Settings",
            parent,
            min_width=750,
            min_height=520,
        )

    def _init_color_values(self):
        """Initialize color values from current settings."""
        # General
        self.background_color = self.current_settings.get("background_color", None)

        # Portfolio Visualization
        self.histogram_color = self.current_settings.get("histogram_color", None)
        self.kde_color = self.current_settings.get("kde_color", None)
        self.normal_color = self.current_settings.get("normal_color", None)
        self.median_color = self.current_settings.get("median_color", None)
        self.mean_color = self.current_settings.get("mean_color", None)

        # Portfolio vs Benchmark
        self.benchmark_portfolio_histogram_color = self.current_settings.get(
            "benchmark_portfolio_histogram_color", None
        )
        self.benchmark_benchmark_histogram_color = self.current_settings.get(
            "benchmark_benchmark_histogram_color", None
        )
        self.benchmark_portfolio_kde_color = self.current_settings.get(
            "benchmark_portfolio_kde_color", None
        )
        self.benchmark_kde_color = self.current_settings.get("benchmark_kde_color", None)
        self.benchmark_normal_color = self.current_settings.get("benchmark_normal_color", None)
        self.benchmark_portfolio_median_color = self.current_settings.get(
            "benchmark_portfolio_median_color", None
        )
        self.benchmark_portfolio_mean_color = self.current_settings.get(
            "benchmark_portfolio_mean_color", None
        )
        self.benchmark_benchmark_median_color = self.current_settings.get(
            "benchmark_benchmark_median_color", None
        )
        self.benchmark_benchmark_mean_color = self.current_settings.get(
            "benchmark_benchmark_mean_color", None
        )

    def _setup_content(self, layout: QVBoxLayout):
        """Set up dialog content (called by ThemedDialog)."""
        # Content container
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 15, 20, 10)
        content_layout.setSpacing(12)

        # General settings group
        general_group = self._create_general_group()
        content_layout.addWidget(general_group)

        # Cash settings group
        cash_group = self._create_cash_group()
        content_layout.addWidget(cash_group)

        # Show either Portfolio Visualization OR Portfolio vs Benchmark based on context
        if self.has_benchmark:
            benchmark_viz_group = self._create_benchmark_viz_group()
            content_layout.addWidget(benchmark_viz_group)
        else:
            portfolio_viz_group = self._create_portfolio_viz_group()
            content_layout.addWidget(portfolio_viz_group)

        content_layout.addStretch()
        layout.addWidget(content_widget, stretch=1)

        # Buttons
        button_container = QWidget()
        button_container.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(20, 10, 20, 15)
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

        layout.addWidget(button_container)

    def _create_general_group(self) -> QGroupBox:
        """Create general settings group."""
        group = QGroupBox("General")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Gridlines toggle row
        gridlines_row = QHBoxLayout()
        self.gridlines_check = QCheckBox("Enable gridlines")
        self.gridlines_check.setChecked(self.current_settings.get("show_gridlines", True))
        gridlines_row.addWidget(self.gridlines_check)
        gridlines_row.addStretch()
        layout.addLayout(gridlines_row)

        # Background color row
        bg_row = QHBoxLayout()
        bg_row.setSpacing(8)

        bg_label = QLabel("Background:")
        bg_label.setMinimumWidth(160)
        bg_row.addWidget(bg_label)

        self.bg_color_btn = QPushButton("Color")
        self.bg_color_btn.setFixedWidth(75)
        self.bg_color_btn.clicked.connect(lambda: self._choose_color("background"))
        bg_row.addWidget(self.bg_color_btn)

        self.bg_color_preview = QLabel("\u25a0")  # ■
        self.bg_color_preview.setFixedWidth(24)
        self._update_color_preview(self.bg_color_preview, self.background_color, "background")
        bg_row.addWidget(self.bg_color_preview)

        bg_row.addStretch()
        layout.addLayout(bg_row)

        group.setLayout(layout)
        return group

    def _create_cash_group(self) -> QGroupBox:
        """Create cash settings group."""
        group = QGroupBox("Cash Handling")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Exclude cash checkbox
        self.exclude_cash_check = QCheckBox("Exclude cash from return distribution")
        self.exclude_cash_check.setChecked(self.current_settings.get("exclude_cash", True))
        layout.addWidget(self.exclude_cash_check)

        exclude_info = QLabel(
            "When enabled, FREE CASH positions are excluded from\n"
            "return calculations and the cash drag statistic is hidden."
        )
        exclude_info.setWordWrap(True)
        exclude_info.setStyleSheet("color: #888888; font-style: italic; font-size: 11px;")
        layout.addWidget(exclude_info)

        group.setLayout(layout)
        return group

    def _create_portfolio_viz_group(self) -> QGroupBox:
        """Create portfolio visualization settings group."""
        group = QGroupBox("Portfolio Visualization")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(12)

        info_label = QLabel("Settings applied when no benchmark is selected")
        info_label.setStyleSheet("color: #888888; font-style: italic; font-size: 11px;")
        layout.addWidget(info_label)

        # Histogram color
        hist_row = self._create_color_only_row(
            "Histogram Color:",
            "histogram",
            self.histogram_color,
            preview_symbol="\u25a0",
        )
        layout.addLayout(hist_row)

        # KDE Curve
        kde_row = self._create_viz_row(
            "KDE Curve",
            "kde",
            self.current_settings.get("show_kde_curve", True),
            self.kde_color,
            self.current_settings.get("kde_line_style", Qt.SolidLine),
            self.current_settings.get("kde_line_width", 2),
        )
        layout.addLayout(kde_row)

        # Normal Distribution
        normal_row = self._create_viz_row(
            "Normal Distribution",
            "normal",
            self.current_settings.get("show_normal_distribution", True),
            self.normal_color,
            self.current_settings.get("normal_line_style", Qt.DashLine),
            self.current_settings.get("normal_line_width", 2),
        )
        layout.addLayout(normal_row)

        # Median Line
        median_row = self._create_viz_row(
            "Median Line",
            "median",
            self.current_settings.get("show_median_line", True),
            self.median_color,
            self.current_settings.get("median_line_style", Qt.SolidLine),
            self.current_settings.get("median_line_width", 2),
        )
        layout.addLayout(median_row)

        # Mean Line
        mean_row = self._create_viz_row(
            "Mean Line",
            "mean",
            self.current_settings.get("show_mean_line", True),
            self.mean_color,
            self.current_settings.get("mean_line_style", Qt.SolidLine),
            self.current_settings.get("mean_line_width", 2),
        )
        layout.addLayout(mean_row)

        # CDF view toggle
        self.cdf_view_check = QCheckBox("Show cumulative distribution (CDF) view")
        self.cdf_view_check.setChecked(self.current_settings.get("show_cdf_view", False))
        layout.addWidget(self.cdf_view_check)

        group.setLayout(layout)
        return group

    def _create_benchmark_viz_group(self) -> QGroupBox:
        """Create portfolio vs benchmark visualization settings group."""
        group = QGroupBox("Portfolio vs Benchmark Visualization")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout()
        layout.setSpacing(12)

        info_label = QLabel("Settings applied when a benchmark is selected")
        info_label.setStyleSheet("color: #888888; font-style: italic; font-size: 11px;")
        layout.addWidget(info_label)

        # Portfolio Histogram color
        portfolio_hist_row = self._create_color_only_row(
            "Portfolio Histogram:",
            "benchmark_portfolio_histogram",
            self.benchmark_portfolio_histogram_color,
            preview_symbol="\u25a0",
        )
        layout.addLayout(portfolio_hist_row)

        # Benchmark Histogram color
        benchmark_hist_row = self._create_color_only_row(
            "Benchmark Histogram:",
            "benchmark_benchmark_histogram",
            self.benchmark_benchmark_histogram_color,
            preview_symbol="\u25a0",
        )
        layout.addLayout(benchmark_hist_row)

        # Portfolio KDE
        portfolio_kde_row = self._create_viz_row(
            "Portfolio KDE",
            "benchmark_portfolio_kde",
            self.current_settings.get("benchmark_show_portfolio_kde", True),
            self.benchmark_portfolio_kde_color,
            self.current_settings.get("benchmark_portfolio_kde_line_style", Qt.SolidLine),
            self.current_settings.get("benchmark_portfolio_kde_line_width", 2),
        )
        layout.addLayout(portfolio_kde_row)

        # Benchmark KDE
        benchmark_kde_row = self._create_viz_row(
            "Benchmark KDE",
            "benchmark_kde",
            self.current_settings.get("benchmark_show_benchmark_kde", True),
            self.benchmark_kde_color,
            self.current_settings.get("benchmark_kde_line_style", Qt.SolidLine),
            self.current_settings.get("benchmark_kde_line_width", 2),
        )
        layout.addLayout(benchmark_kde_row)

        # Normal Distribution
        normal_row = self._create_viz_row(
            "Normal Distribution",
            "benchmark_normal",
            self.current_settings.get("benchmark_show_normal_distribution", True),
            self.benchmark_normal_color,
            self.current_settings.get("benchmark_normal_line_style", Qt.DashLine),
            self.current_settings.get("benchmark_normal_line_width", 2),
        )
        layout.addLayout(normal_row)

        # Portfolio Median
        portfolio_median_row = self._create_viz_row(
            "Portfolio Median",
            "benchmark_portfolio_median",
            self.current_settings.get("benchmark_show_portfolio_median", True),
            self.benchmark_portfolio_median_color,
            self.current_settings.get("benchmark_portfolio_median_line_style", Qt.SolidLine),
            self.current_settings.get("benchmark_portfolio_median_line_width", 2),
        )
        layout.addLayout(portfolio_median_row)

        # Portfolio Mean
        portfolio_mean_row = self._create_viz_row(
            "Portfolio Mean",
            "benchmark_portfolio_mean",
            self.current_settings.get("benchmark_show_portfolio_mean", True),
            self.benchmark_portfolio_mean_color,
            self.current_settings.get("benchmark_portfolio_mean_line_style", Qt.SolidLine),
            self.current_settings.get("benchmark_portfolio_mean_line_width", 2),
        )
        layout.addLayout(portfolio_mean_row)

        # Benchmark Median
        benchmark_median_row = self._create_viz_row(
            "Benchmark Median",
            "benchmark_benchmark_median",
            self.current_settings.get("benchmark_show_benchmark_median", True),
            self.benchmark_benchmark_median_color,
            self.current_settings.get("benchmark_benchmark_median_line_style", Qt.DashLine),
            self.current_settings.get("benchmark_benchmark_median_line_width", 2),
        )
        layout.addLayout(benchmark_median_row)

        # Benchmark Mean
        benchmark_mean_row = self._create_viz_row(
            "Benchmark Mean",
            "benchmark_benchmark_mean",
            self.current_settings.get("benchmark_show_benchmark_mean", True),
            self.benchmark_benchmark_mean_color,
            self.current_settings.get("benchmark_benchmark_mean_line_style", Qt.DashLine),
            self.current_settings.get("benchmark_benchmark_mean_line_width", 2),
        )
        layout.addLayout(benchmark_mean_row)

        # CDF view toggle
        self.benchmark_cdf_view_check = QCheckBox("Show cumulative distribution (CDF) view")
        self.benchmark_cdf_view_check.setChecked(
            self.current_settings.get("benchmark_show_cdf_view", False)
        )
        layout.addWidget(self.benchmark_cdf_view_check)

        group.setLayout(layout)
        return group

    def _create_color_only_row(
        self,
        label: str,
        prefix: str,
        color: Optional[Tuple[int, int, int]],
        preview_symbol: str = "\u25cf",
    ) -> QHBoxLayout:
        """Create a single-line row with just a color picker."""
        row = QHBoxLayout()
        row.setSpacing(8)

        row_label = QLabel(label)
        row_label.setMinimumWidth(160)
        row.addWidget(row_label)

        # Color picker
        color_btn = QPushButton("Color")
        color_btn.setFixedWidth(75)
        color_btn.clicked.connect(lambda: self._choose_color(prefix))
        row.addWidget(color_btn)
        setattr(self, f"{prefix}_color_btn", color_btn)

        preview = QLabel(preview_symbol)
        preview.setFixedWidth(24)
        self._update_color_preview(preview, color, prefix)
        row.addWidget(preview)
        setattr(self, f"{prefix}_color_preview", preview)

        row.addStretch()
        return row

    def _create_viz_row(
        self,
        label: str,
        prefix: str,
        show: bool,
        color: Optional[Tuple[int, int, int]],
        style: Qt.PenStyle,
        width: int,
    ) -> QHBoxLayout:
        """Create a visualization row with toggle, color, style, and width."""
        row = QHBoxLayout()
        row.setSpacing(8)

        # Toggle checkbox with fixed width label area
        toggle = QCheckBox(label)
        toggle.setChecked(show)
        toggle.setMinimumWidth(160)
        toggle.toggled.connect(lambda checked: self._on_viz_toggled(prefix, checked))
        row.addWidget(toggle)
        setattr(self, f"{prefix}_toggle", toggle)

        # Color picker
        color_btn = QPushButton("Color")
        color_btn.setFixedWidth(75)
        color_btn.clicked.connect(lambda: self._choose_color(prefix))
        row.addWidget(color_btn)
        setattr(self, f"{prefix}_color_btn", color_btn)

        preview = QLabel("\u25cf")
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

        # Define theme colors
        if theme == "light":
            accent = (0, 102, 204)  # Blue
            secondary = (100, 100, 100)
            background = (255, 255, 255)
        elif theme == "bloomberg":
            accent = (255, 128, 0)  # Orange
            secondary = (200, 200, 200)
            background = (13, 20, 32)
        else:  # dark
            accent = (0, 212, 255)  # Cyan
            secondary = (150, 150, 150)
            background = (30, 30, 30)

        # Map prefixes to appropriate colors
        if prefix == "background":
            return background
        elif prefix in ("histogram", "benchmark_portfolio_histogram"):
            return accent
        elif prefix == "benchmark_benchmark_histogram":
            return secondary
        elif prefix in ("kde", "benchmark_portfolio_kde"):
            return accent
        elif prefix == "benchmark_kde":
            return secondary
        elif prefix in ("normal", "benchmark_normal"):
            return secondary
        elif prefix in ("median", "benchmark_portfolio_median"):
            return accent
        elif prefix in ("mean", "benchmark_portfolio_mean"):
            return accent
        elif prefix in ("benchmark_benchmark_median", "benchmark_benchmark_mean"):
            return secondary
        else:
            return accent

    def _on_viz_toggled(self, prefix: str, checked: bool) -> None:
        """Handle visualization toggle."""
        pass

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
            "Are you sure you want to reset all distribution settings to defaults?",
            CustomMessageBox.Yes | CustomMessageBox.No,
            CustomMessageBox.No,
        )

        if reply == CustomMessageBox.Yes:
            # Reset General
            self.gridlines_check.setChecked(False)
            self.background_color = None
            self._update_color_preview(self.bg_color_preview, None, "background")

            # Reset Cash
            self.exclude_cash_check.setChecked(True)

            if self.has_benchmark:
                # Reset Benchmark Visualization
                self._reset_color_setting("benchmark_portfolio_histogram", None)
                self._reset_color_setting("benchmark_benchmark_histogram", None)
                self._reset_viz_setting("benchmark_portfolio_kde", True, None, "Solid", 2)
                self._reset_viz_setting("benchmark_kde", True, None, "Solid", 2)
                self._reset_viz_setting("benchmark_normal", True, None, "Dashed", 2)
                self._reset_viz_setting("benchmark_portfolio_median", False, None, "Solid", 2)
                self._reset_viz_setting("benchmark_portfolio_mean", False, None, "Solid", 2)
                self._reset_viz_setting("benchmark_benchmark_median", False, None, "Dashed", 2)
                self._reset_viz_setting("benchmark_benchmark_mean", False, None, "Dashed", 2)
                self.benchmark_cdf_view_check.setChecked(False)
            else:
                # Reset Portfolio Visualization
                self._reset_color_setting("histogram", None)
                self._reset_viz_setting("kde", True, None, "Solid", 2)
                self._reset_viz_setting("normal", True, None, "Dashed", 2)
                self._reset_viz_setting("median", True, None, "Solid", 2)
                self._reset_viz_setting("mean", True, None, "Solid", 2)
                self.cdf_view_check.setChecked(False)

    def _reset_color_setting(
        self, prefix: str, color: Optional[Tuple[int, int, int]]
    ) -> None:
        """Reset a color-only setting."""
        setattr(self, f"{prefix}_color", color)
        preview = getattr(self, f"{prefix}_color_preview", None)
        if preview:
            self._update_color_preview(preview, color, prefix)

    def _reset_viz_setting(
        self,
        prefix: str,
        show: bool,
        color: Optional[Tuple[int, int, int]],
        style: str,
        width: int,
    ) -> None:
        """Reset a visualization setting."""
        toggle = getattr(self, f"{prefix}_toggle", None)
        if toggle:
            toggle.setChecked(show)

        self._reset_color_setting(prefix, color)

        style_combo = getattr(self, f"{prefix}_style_combo", None)
        if style_combo:
            style_combo.setCurrentText(style)

        width_spin = getattr(self, f"{prefix}_width_spin", None)
        if width_spin:
            width_spin.setValue(width)

    def _save_settings(self) -> None:
        """Save the settings and close."""
        # Start with current settings to preserve hidden section values
        self.result = dict(self.current_settings)

        # Always save General settings
        self.result["show_gridlines"] = self.gridlines_check.isChecked()
        self.result["background_color"] = self.background_color

        # Always save Cash settings
        self.result["exclude_cash"] = self.exclude_cash_check.isChecked()

        if self.has_benchmark:
            # Save Benchmark Visualization settings
            self.result["benchmark_portfolio_histogram_color"] = (
                self.benchmark_portfolio_histogram_color
            )
            self.result["benchmark_benchmark_histogram_color"] = (
                self.benchmark_benchmark_histogram_color
            )
            self.result["benchmark_show_portfolio_kde"] = (
                self.benchmark_portfolio_kde_toggle.isChecked()
            )
            self.result["benchmark_portfolio_kde_color"] = self.benchmark_portfolio_kde_color
            self.result["benchmark_portfolio_kde_line_style"] = self.LINE_STYLES[
                self.benchmark_portfolio_kde_style_combo.currentText()
            ]
            self.result["benchmark_portfolio_kde_line_width"] = (
                self.benchmark_portfolio_kde_width_spin.value()
            )
            self.result["benchmark_show_benchmark_kde"] = (
                self.benchmark_kde_toggle.isChecked()
            )
            self.result["benchmark_kde_color"] = self.benchmark_kde_color
            self.result["benchmark_kde_line_style"] = self.LINE_STYLES[
                self.benchmark_kde_style_combo.currentText()
            ]
            self.result["benchmark_kde_line_width"] = self.benchmark_kde_width_spin.value()
            self.result["benchmark_show_normal_distribution"] = (
                self.benchmark_normal_toggle.isChecked()
            )
            self.result["benchmark_normal_color"] = self.benchmark_normal_color
            self.result["benchmark_normal_line_style"] = self.LINE_STYLES[
                self.benchmark_normal_style_combo.currentText()
            ]
            self.result["benchmark_normal_line_width"] = self.benchmark_normal_width_spin.value()
            self.result["benchmark_show_portfolio_median"] = (
                self.benchmark_portfolio_median_toggle.isChecked()
            )
            self.result["benchmark_portfolio_median_color"] = self.benchmark_portfolio_median_color
            self.result["benchmark_portfolio_median_line_style"] = self.LINE_STYLES[
                self.benchmark_portfolio_median_style_combo.currentText()
            ]
            self.result["benchmark_portfolio_median_line_width"] = (
                self.benchmark_portfolio_median_width_spin.value()
            )
            self.result["benchmark_show_portfolio_mean"] = (
                self.benchmark_portfolio_mean_toggle.isChecked()
            )
            self.result["benchmark_portfolio_mean_color"] = self.benchmark_portfolio_mean_color
            self.result["benchmark_portfolio_mean_line_style"] = self.LINE_STYLES[
                self.benchmark_portfolio_mean_style_combo.currentText()
            ]
            self.result["benchmark_portfolio_mean_line_width"] = (
                self.benchmark_portfolio_mean_width_spin.value()
            )
            self.result["benchmark_show_benchmark_median"] = (
                self.benchmark_benchmark_median_toggle.isChecked()
            )
            self.result["benchmark_benchmark_median_color"] = self.benchmark_benchmark_median_color
            self.result["benchmark_benchmark_median_line_style"] = self.LINE_STYLES[
                self.benchmark_benchmark_median_style_combo.currentText()
            ]
            self.result["benchmark_benchmark_median_line_width"] = (
                self.benchmark_benchmark_median_width_spin.value()
            )
            self.result["benchmark_show_benchmark_mean"] = (
                self.benchmark_benchmark_mean_toggle.isChecked()
            )
            self.result["benchmark_benchmark_mean_color"] = self.benchmark_benchmark_mean_color
            self.result["benchmark_benchmark_mean_line_style"] = self.LINE_STYLES[
                self.benchmark_benchmark_mean_style_combo.currentText()
            ]
            self.result["benchmark_benchmark_mean_line_width"] = (
                self.benchmark_benchmark_mean_width_spin.value()
            )
            self.result["benchmark_show_cdf_view"] = self.benchmark_cdf_view_check.isChecked()
        else:
            # Save Portfolio Visualization settings
            self.result["histogram_color"] = self.histogram_color
            self.result["show_kde_curve"] = self.kde_toggle.isChecked()
            self.result["kde_color"] = self.kde_color
            self.result["kde_line_style"] = self.LINE_STYLES[self.kde_style_combo.currentText()]
            self.result["kde_line_width"] = self.kde_width_spin.value()
            self.result["show_normal_distribution"] = self.normal_toggle.isChecked()
            self.result["normal_color"] = self.normal_color
            self.result["normal_line_style"] = self.LINE_STYLES[
                self.normal_style_combo.currentText()
            ]
            self.result["normal_line_width"] = self.normal_width_spin.value()
            self.result["show_median_line"] = self.median_toggle.isChecked()
            self.result["median_color"] = self.median_color
            self.result["median_line_style"] = self.LINE_STYLES[
                self.median_style_combo.currentText()
            ]
            self.result["median_line_width"] = self.median_width_spin.value()
            self.result["show_mean_line"] = self.mean_toggle.isChecked()
            self.result["mean_color"] = self.mean_color
            self.result["mean_line_style"] = self.LINE_STYLES[self.mean_style_combo.currentText()]
            self.result["mean_line_width"] = self.mean_width_spin.value()
            self.result["show_cdf_view"] = self.cdf_view_check.isChecked()

        self.accept()

    def get_settings(self):
        """Get the configured settings."""
        return getattr(self, "result", None)
