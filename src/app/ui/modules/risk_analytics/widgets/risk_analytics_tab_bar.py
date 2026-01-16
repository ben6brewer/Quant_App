"""Risk Analytics Tab Bar - Switches between analysis views."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin


class RiskAnalyticsTabBar(LazyThemeMixin, QWidget):
    """
    Horizontal tab bar for Risk Analytics content views.

    Tabs:
    - Summary (0): Existing summary panels and decomposition
    - Attribution (1): Brinson-Fachler attribution analysis
    - Selection (2): Detailed selection effects by security
    - Risk (3): Security risk table (CTEV breakdown)
    """

    view_changed = Signal(int)  # Emits tab index

    TABS = ["Summary", "Attribution", "Selection", "Risk"]

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
        """Setup tab bar UI."""
        self.setFixedHeight(52)
        self.setObjectName("riskTabBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)

        # Button group for exclusive selection
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.tab_buttons = []

        for i, label in enumerate(self.TABS):
            btn = QPushButton(label)
            btn.setObjectName("riskTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(120)
            btn.setFixedHeight(40)

            # First tab is default
            if i == 0:
                btn.setChecked(True)

            # Connect with captured index
            btn.clicked.connect(lambda checked, idx=i: self.view_changed.emit(idx))

            layout.addWidget(btn)
            self.button_group.addButton(btn)
            self.tab_buttons.append(btn)

        layout.addStretch()

    def set_active_view(self, index: int):
        """Set active view programmatically."""
        if 0 <= index < len(self.tab_buttons):
            self.tab_buttons[index].setChecked(True)

    def get_active_view(self) -> int:
        """Get current active view index."""
        for i, btn in enumerate(self.tab_buttons):
            if btn.isChecked():
                return i
        return 0

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
            #riskTabBar {
                background-color: #1e1e1e;
                border-bottom: 1px solid #3d3d3d;
            }
            #riskTab {
                background-color: transparent;
                color: #cccccc;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #riskTab:hover {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            #riskTab:checked {
                background-color: #00d4ff;
                color: #000000;
                font-weight: bold;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            #riskTabBar {
                background-color: #ffffff;
                border-bottom: 1px solid #cccccc;
            }
            #riskTab {
                background-color: transparent;
                color: #333333;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #riskTab:hover {
                background-color: #f0f0f0;
                color: #000000;
            }
            #riskTab:checked {
                background-color: #0066cc;
                color: #ffffff;
                font-weight: bold;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            #riskTabBar {
                background-color: #000814;
                border-bottom: 1px solid #1a2838;
            }
            #riskTab {
                background-color: transparent;
                color: #a8a8a8;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #riskTab:hover {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            #riskTab:checked {
                background-color: #FF8000;
                color: #000000;
                font-weight: bold;
            }
        """
