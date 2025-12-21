from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.widgets.price_chart import PriceChart


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt Investing App (Starter)")
        self.resize(1100, 700)

        central = QWidget(self)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Ticker:"))
        self.ticker_input = QLineEdit()
        self.ticker_input.setText("BTC-USD")
        self.ticker_input.setMaximumWidth(220)
        controls.addWidget(self.ticker_input)

        controls.addWidget(QLabel("Interval:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["daily", "weekly", "monthly", "yearly"])
        self.interval_combo.setCurrentText("1d")
        self.interval_combo.setMaximumWidth(120)
        controls.addWidget(self.interval_combo)

        controls.addWidget(QLabel("Chart:"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["Candles", "Line"])
        self.chart_type_combo.setCurrentText("Candles")
        self.chart_type_combo.setMaximumWidth(120)
        controls.addWidget(self.chart_type_combo)

        controls.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["Regular", "Logarithmic"])
        self.scale_combo.setCurrentText("Logarithmic")
        self.scale_combo.setMaximumWidth(120)
        controls.addWidget(self.scale_combo)


        controls.addStretch(1)
        root.addLayout(controls)

        self.chart = PriceChart()
        root.addWidget(self.chart, stretch=1)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")
