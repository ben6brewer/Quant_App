"""Risk Summary Panel Widget - Top summary metrics display."""

from typing import Dict, Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class MetricCard(QFrame):
    """Individual metric card displaying a label and value."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._value = "--"
        self._setup_ui()

    def _setup_ui(self):
        """Setup card UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Title label
        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("card_title")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        # Value label
        self.value_label = QLabel(self._value)
        self.value_label.setObjectName("card_value")
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)

        self.setObjectName("metric_card")

    def set_value(self, value: str):
        """Set the displayed value."""
        self._value = value
        self.value_label.setText(value)


class RiskSummaryPanel(LazyThemeMixin, QWidget):
    """
    Summary panel showing key risk metrics as card widgets.

    Displays: Total Active Risk, Factor Risk %, Idiosyncratic Risk %, Ex-Ante Beta
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False

        self._setup_ui()
        self._apply_theme()

        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup panel UI with 4 metric cards."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Total Active Risk card
        self.total_risk_card = MetricCard("Total Active Risk")
        layout.addWidget(self.total_risk_card)

        # Factor Risk % card
        self.factor_risk_card = MetricCard("Factor Risk")
        layout.addWidget(self.factor_risk_card)

        # Idiosyncratic Risk % card
        self.idio_risk_card = MetricCard("Idiosyncratic Risk")
        layout.addWidget(self.idio_risk_card)

        # Ex-Ante Beta card
        self.beta_card = MetricCard("Ex-Ante Beta")
        layout.addWidget(self.beta_card)

    def update_metrics(self, metrics: Optional[Dict[str, float]]):
        """
        Update displayed metric values.

        Args:
            metrics: Dict with keys: total_active_risk, factor_risk_pct,
                     idio_risk_pct, ex_ante_beta
        """
        if metrics is None:
            self.total_risk_card.set_value("--")
            self.factor_risk_card.set_value("--")
            self.idio_risk_card.set_value("--")
            self.beta_card.set_value("--")
            return

        # Format total active risk as percentage
        total_risk = metrics.get("total_active_risk", 0)
        self.total_risk_card.set_value(f"{total_risk:.2f}%")

        # Format factor risk as percentage
        factor_risk = metrics.get("factor_risk_pct", 0)
        self.factor_risk_card.set_value(f"{factor_risk:.1f}%")

        # Format idiosyncratic risk as percentage
        idio_risk = metrics.get("idio_risk_pct", 0)
        self.idio_risk_card.set_value(f"{idio_risk:.1f}%")

        # Format beta
        beta = metrics.get("ex_ante_beta", 1.0)
        self.beta_card.set_value(f"{beta:.2f}")

    def clear_metrics(self):
        """Clear all displayed values to placeholder."""
        self.update_metrics(None)

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()

        self.setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QFrame#metric_card {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
            }
            QLabel#card_title {
                color: #a0a0a0;
                font-size: 12px;
                font-weight: normal;
                background: transparent;
            }
            QLabel#card_value {
                color: #00d4ff;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QFrame#metric_card {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 6px;
            }
            QLabel#card_title {
                color: #666666;
                font-size: 12px;
                font-weight: normal;
                background: transparent;
            }
            QLabel#card_value {
                color: #0066cc;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: transparent;
            }
            QFrame#metric_card {
                background-color: #0d1420;
                border: 1px solid #1a2838;
                border-radius: 6px;
            }
            QLabel#card_title {
                color: #808080;
                font-size: 12px;
                font-weight: normal;
                background: transparent;
            }
            QLabel#card_value {
                color: #FF8000;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
            }
        """
