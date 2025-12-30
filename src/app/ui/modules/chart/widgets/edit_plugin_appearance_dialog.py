from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QWidget, QLineEdit, QSpinBox, QComboBox,
    QColorDialog, QCheckBox,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QMouseEvent

from app.core.theme_manager import ThemeManager
from ..services import IndicatorService


class EditPluginAppearanceDialog(QDialog):
    """
    Dialog for editing appearance settings of plugin indicators.
    Parameters cannot be edited (plugin code defines those).
    """

    # Line style options (same as CreateIndicatorDialog)
    LINE_STYLES = {
        "Solid": Qt.SolidLine,
        "Dashed": Qt.DashLine,
        "Dotted": Qt.DotLine,
        "Dash-Dot": Qt.DashDotLine,
    }

    # Marker shapes (same as CreateIndicatorDialog)
    MARKER_SHAPES = {
        "Circle": "o",
        "Square": "s",
        "Triangle": "t",
        "Diamond": "d",
        "Plus": "+",
        "Cross": "x",
        "Star": "star",
    }

    def __init__(
        self,
        theme_manager: ThemeManager,
        plugin_name: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self.theme_manager = theme_manager
        self.plugin_name = plugin_name
        self.line_widgets = {}
        self._drag_pos = QPoint()

        # Get current appearance overrides (if any)
        self.current_appearance = IndicatorService.get_plugin_appearance(plugin_name)

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Custom title bar
        self.title_bar = self._create_title_bar(f"Edit Appearance: {self.plugin_name}")
        layout.addWidget(self.title_bar)

        # Content container
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)

        # Appearance settings group
        appearance_group = self._create_appearance_group()
        content_layout.addWidget(appearance_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.update_btn = QPushButton("Update Indicator")
        self.update_btn.setDefault(True)
        self.update_btn.setObjectName("defaultButton")
        self.update_btn.clicked.connect(self._save_appearance)
        button_layout.addWidget(self.update_btn)

        content_layout.addLayout(button_layout)
        layout.addWidget(content_widget)

    def _create_title_bar(self, title: str) -> QWidget:
        """Create custom title bar."""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(32)

        bar_layout = QHBoxLayout(title_bar)
        bar_layout.setContentsMargins(10, 0, 0, 0)
        bar_layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        bar_layout.addWidget(title_label)
        bar_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("titleBarCloseButton")
        close_btn.setFixedSize(40, 32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        bar_layout.addWidget(close_btn)

        # Enable dragging
        title_bar.mousePressEvent = self._title_bar_mouse_press
        title_bar.mouseMoveEvent = self._title_bar_mouse_move

        return title_bar

    def _title_bar_mouse_press(self, event: QMouseEvent) -> None:
        """Handle mouse press for dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_mouse_move(self, event: QMouseEvent) -> None:
        """Handle mouse move for dragging."""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _create_appearance_group(self) -> QGroupBox:
        """Create the appearance settings group."""
        group = QGroupBox("Appearance Settings")
        group.setObjectName("appearanceGroup")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.setSpacing(10)

        # Container for line widgets
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(5, 0, 0, 5)
        container_layout.setSpacing(5)

        # Get plugin columns by preview calculation
        columns = IndicatorService.preview_indicator_columns(self.plugin_name)

        if not columns:
            error_label = QLabel("Error: Could not determine plugin columns.")
            error_label.setStyleSheet("color: #ff5555;")
            container_layout.addWidget(error_label)
            layout.addWidget(container)
            return group

        # Generate default colors (cycling through preset colors)
        default_colors = [
            (0, 150, 255),    # Blue
            (255, 150, 0),    # Orange
            (150, 0, 255),    # Purple
            (0, 255, 150),    # Cyan
            (255, 0, 150),    # Magenta
            (255, 200, 0),    # Yellow
            (76, 175, 80),    # Green
            (244, 67, 54),    # Red
        ]

        # Create widgets for each column
        for idx, column_name in enumerate(columns):
            # Get existing appearance or use defaults
            if column_name in self.current_appearance:
                metadata = self.current_appearance[column_name]
            else:
                # Default appearance
                metadata = {
                    "label": column_name,
                    "visible": True,
                    "color": default_colors[idx % len(default_colors)],
                    "line_width": 2,
                    "line_style": Qt.SolidLine,
                    "marker_shape": "o",
                    "marker_size": 10,
                    "marker_offset": 0,
                }

            # Detect markers per-column (not per-plugin)
            uses_markers = "cross" in column_name.lower() or "marker" in column_name.lower()

            line_widget = self._create_line_widget(column_name, metadata, uses_markers)
            container_layout.addWidget(line_widget)

        layout.addWidget(container)
        return group

    def _create_line_widget(self, column_name: str, metadata: dict, uses_markers: bool) -> QWidget:
        """Create a widget for customizing a single line."""
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 0, 5)
        layout.setSpacing(8)

        # Visibility checkbox
        visible_check = QCheckBox()
        visible_check.setChecked(metadata.get("visible", True))
        visible_check.setToolTip("Show/hide this line")
        layout.addWidget(visible_check)

        # Label input
        label_input = QLineEdit(metadata.get("label", column_name))
        label_input.setPlaceholderText("Display label")
        label_input.setFixedWidth(150)
        label_input.setToolTip("Custom label for legend")
        layout.addWidget(label_input)

        # Color button
        color = metadata.get("color", (0, 150, 255))
        color_btn = QPushButton()
        color_btn.setFixedSize(30, 30)
        color_btn.setStyleSheet(
            f"background-color: rgb({color[0]}, {color[1]}, {color[2]}); "
            f"border: 1px solid #555;"
        )
        color_btn.setToolTip("Click to change color")
        color_btn.setCursor(Qt.PointingHandCursor)
        color_btn.clicked.connect(lambda: self._pick_color(column_name))
        layout.addWidget(color_btn)

        # Line width
        width_spin = QSpinBox()
        width_spin.setMinimum(1)
        width_spin.setMaximum(10)
        width_spin.setValue(metadata.get("line_width", 2))
        width_spin.setPrefix("W: ")
        width_spin.setMaximumWidth(70)
        width_spin.setToolTip("Line width in pixels")
        layout.addWidget(width_spin)

        # Line style
        style_combo = QComboBox()
        style_combo.addItems(list(self.LINE_STYLES.keys()))
        style_combo.setMaximumWidth(120)
        style_combo.setToolTip("Line style")
        line_style = metadata.get("line_style", Qt.SolidLine)
        for style_name, style_val in self.LINE_STYLES.items():
            if style_val == line_style:
                style_combo.setCurrentText(style_name)
                break
        layout.addWidget(style_combo)

        # Marker controls (conditional)
        marker_shape_combo = None
        marker_size_spin = None
        marker_offset_spin = None

        if uses_markers:
            marker_shape_combo = QComboBox()
            marker_shape_combo.addItems(list(self.MARKER_SHAPES.keys()))
            marker_shape_combo.setMaximumWidth(100)
            marker_shape_combo.setToolTip("Marker shape")
            marker_shape = metadata.get("marker_shape", "o")
            for shape_name, shape_val in self.MARKER_SHAPES.items():
                if shape_val == marker_shape:
                    marker_shape_combo.setCurrentText(shape_name)
                    break
            layout.addWidget(marker_shape_combo)

            marker_size_spin = QSpinBox()
            marker_size_spin.setMinimum(1)
            marker_size_spin.setMaximum(50)
            marker_size_spin.setValue(metadata.get("marker_size", 10))
            marker_size_spin.setPrefix("M: ")
            marker_size_spin.setMaximumWidth(70)
            marker_size_spin.setToolTip("Marker size")
            layout.addWidget(marker_size_spin)

            marker_offset_spin = QSpinBox()
            marker_offset_spin.setMinimum(-1000)
            marker_offset_spin.setMaximum(1000)
            marker_offset_spin.setValue(metadata.get("marker_offset", 0))
            marker_offset_spin.setPrefix("Y: ")
            marker_offset_spin.setMaximumWidth(80)
            marker_offset_spin.setToolTip("Vertical offset in pixels (positive = up, negative = down)")
            layout.addWidget(marker_offset_spin)

        # Add stretch to keep widgets aligned on the left
        layout.addStretch()

        # Store widget references
        self.line_widgets[column_name] = {
            "widget": widget,
            "visible": visible_check,
            "label": label_input,
            "color": color,
            "color_btn": color_btn,
            "width": width_spin,
            "style": style_combo,
            "marker_shape": marker_shape_combo,
            "marker_size": marker_size_spin,
            "marker_offset": marker_offset_spin,
        }

        return widget

    def _pick_color(self, column_name: str):
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

    def _save_appearance(self):
        """Save the appearance settings."""
        # Collect per-line appearance
        per_line_appearance = {}
        for col_name, widgets in self.line_widgets.items():
            line_config = {
                "label": widgets["label"].text().strip(),
                "visible": widgets["visible"].isChecked(),
                "color": widgets["color"],
                "line_width": widgets["width"].value(),
                "line_style": self.LINE_STYLES[widgets["style"].currentText()],
            }

            # Include marker settings if widgets exist
            if widgets["marker_shape"] is not None:
                line_config["marker_shape"] = self.MARKER_SHAPES[widgets["marker_shape"].currentText()]
            if widgets["marker_size"] is not None:
                line_config["marker_size"] = widgets["marker_size"].value()
            if widgets["marker_offset"] is not None:
                line_config["marker_offset"] = widgets["marker_offset"].value()

            per_line_appearance[col_name] = line_config

        # Save to service
        IndicatorService.set_plugin_appearance(self.plugin_name, per_line_appearance)

        self.accept()

    def _apply_theme(self):
        """Apply the current theme."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
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
                subcontrol-position: top left;
                padding: 5px 10px;
                color: #ffffff;
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
            QLineEdit, QSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #00d4ff;
            }
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
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
        return """
            QDialog {
                background-color: #ffffff;
                color: #000000;
            }
            #titleBar {
                background-color: #ffffff;
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
                background-color: #ffffff;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
                color: #000000;
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
            QLineEdit, QSpinBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #0066cc;
            }
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
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
        return """
            QDialog {
                background-color: #0d1420;
                color: #ffffff;
            }
            #titleBar {
                background-color: #0d1420;
                border-bottom: 1px solid #1a2332;
            }
            #titleLabel {
                background-color: transparent;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
            #titleBarCloseButton {
                background-color: rgba(255, 255, 255, 0.08);
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
                color: #b8bcc2;
                font-size: 13px;
                background-color: transparent;
            }
            QGroupBox {
                color: #ffffff;
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
                subcontrol-position: top left;
                padding: 5px 10px;
                color: #ffffff;
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
            QLineEdit, QSpinBox {
                background-color: #1a2332;
                color: #ffffff;
                border: 1px solid #2a3442;
                border-radius: 4px;
                padding: 8px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #FF8000;
            }
            QComboBox {
                background-color: #1a2332;
                color: #ffffff;
                border: 1px solid #2a3442;
                border-radius: 4px;
                padding: 8px;
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
