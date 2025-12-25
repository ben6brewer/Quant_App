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
    QMessageBox,
)
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager


class CreateIndicatorDialog(QDialog):
    """
    Dialog for creating custom indicators with user-specified parameters.
    """

    # Define indicator types and their parameters
    INDICATOR_TYPES = {
        "SMA": {
            "name": "Simple Moving Average",
            "params": [
                {"name": "length", "label": "Period", "default": "20", "type": "int"},
            ],
        },
        "EMA": {
            "name": "Exponential Moving Average",
            "params": [
                {"name": "length", "label": "Period", "default": "12", "type": "int"},
            ],
        },
        "Bollinger Bands": {
            "name": "Bollinger Bands",
            "params": [
                {"name": "length", "label": "Period", "default": "20", "type": "int"},
                {"name": "std", "label": "Std Dev", "default": "2", "type": "float"},
            ],
        },
        "RSI": {
            "name": "Relative Strength Index",
            "params": [
                {"name": "length", "label": "Period", "default": "14", "type": "int"},
            ],
        },
        "MACD": {
            "name": "MACD",
            "params": [
                {"name": "fast", "label": "Fast Period", "default": "12", "type": "int"},
                {"name": "slow", "label": "Slow Period", "default": "26", "type": "int"},
                {"name": "signal", "label": "Signal Period", "default": "9", "type": "int"},
            ],
        },
        "ATR": {
            "name": "Average True Range",
            "params": [
                {"name": "length", "label": "Period", "default": "14", "type": "int"},
            ],
        },
        "Stochastic": {
            "name": "Stochastic Oscillator",
            "params": [
                {"name": "k", "label": "K Period", "default": "14", "type": "int"},
                {"name": "d", "label": "D Period", "default": "3", "type": "int"},
                {"name": "smooth_k", "label": "Smooth K", "default": "3", "type": "int"},
            ],
        },
        "OBV": {
            "name": "On-Balance Volume",
            "params": [],  # No parameters
        },
        "VWAP": {
            "name": "Volume Weighted Average Price",
            "params": [],  # No parameters
        },
    }

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Custom Indicator")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self.theme_manager = theme_manager
        self.param_inputs = {}
        
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Header
        self.header = QLabel("Create Custom Indicator")
        self.header.setObjectName("dialogHeader")
        layout.addWidget(self.header)

        # Indicator type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Indicator Type:"))
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(self.INDICATOR_TYPES.keys()))
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo, stretch=1)
        
        layout.addLayout(type_layout)

        # Parameter form
        self.param_form = QFormLayout()
        self.param_form.setSpacing(10)
        layout.addLayout(self.param_form)

        # Initialize with first indicator type
        self._on_type_changed(self.type_combo.currentText())

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.create_btn = QPushButton("Create Indicator")
        self.create_btn.setDefault(True)
        self.create_btn.setObjectName("defaultButton")
        self.create_btn.clicked.connect(self._create_indicator)
        button_layout.addWidget(self.create_btn)
        
        layout.addLayout(button_layout)

    def _apply_theme(self):
        """Apply the current theme to the dialog."""
        theme = self.theme_manager.current_theme
        
        if theme == "light":
            stylesheet = self._get_light_stylesheet()
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
            #dialogHeader {
                color: #00d4ff;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
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
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
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
            #dialogHeader {
                color: #0066cc;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
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
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
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

    def _on_type_changed(self, indicator_type: str):
        """Update parameter form when indicator type changes."""
        # Clear existing parameter inputs
        while self.param_form.rowCount() > 0:
            self.param_form.removeRow(0)
        self.param_inputs.clear()

        # Get parameter definitions for this indicator type
        indicator_info = self.INDICATOR_TYPES.get(indicator_type, {})
        params = indicator_info.get("params", [])

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

    def _create_indicator(self):
        """Validate inputs and create the indicator."""
        indicator_type = self.type_combo.currentText()
        
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
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Invalid value for {param_name}: {value_str}\n{str(e)}",
                )
                return

        # Store the result
        self.result = {
            "type": indicator_type,
            "params": params,
        }
        
        self.accept()

    def get_indicator_config(self):
        """Get the created indicator configuration."""
        return getattr(self, "result", None)