"""View Tab Bar - Switches between Transaction Log and Portfolio Holdings views"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager


class ViewTabBar(QWidget):
    """
    Horizontal tab bar for switching between table views.
    Simpler than SectionTabBar - only 2 tabs with exclusive selection.
    """

    view_changed = Signal(int)  # Emits index: 0 = Transaction Log, 1 = Portfolio Holdings

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()
        self._apply_theme()
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self):
        """Setup tab bar UI."""
        self.setFixedHeight(52)
        self.setObjectName("viewTabBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(5)

        # Button group for exclusive selection
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        # Transaction Log tab
        self.transactions_tab = QPushButton("Transaction Log")
        self.transactions_tab.setObjectName("viewTab")
        self.transactions_tab.setCheckable(True)
        self.transactions_tab.setCursor(Qt.PointingHandCursor)
        self.transactions_tab.setMinimumWidth(170)
        self.transactions_tab.setFixedHeight(40)
        self.transactions_tab.setChecked(True)  # Default
        self.transactions_tab.clicked.connect(lambda: self.view_changed.emit(0))
        layout.addWidget(self.transactions_tab)
        self.button_group.addButton(self.transactions_tab)

        # Portfolio Holdings tab
        self.holdings_tab = QPushButton("Portfolio Holdings")
        self.holdings_tab.setObjectName("viewTab")
        self.holdings_tab.setCheckable(True)
        self.holdings_tab.setCursor(Qt.PointingHandCursor)
        self.holdings_tab.setMinimumWidth(175)
        self.holdings_tab.setFixedHeight(40)
        self.holdings_tab.clicked.connect(lambda: self.view_changed.emit(1))
        layout.addWidget(self.holdings_tab)
        self.button_group.addButton(self.holdings_tab)

        layout.addStretch()

    def set_active_view(self, index: int):
        """Set active view programmatically."""
        if index == 0:
            self.transactions_tab.setChecked(True)
        else:
            self.holdings_tab.setChecked(True)

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
            #viewTabBar {
                background-color: #1e1e1e;
                border-bottom: 1px solid #3d3d3d;
            }
            #viewTab {
                background-color: transparent;
                color: #cccccc;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #viewTab:hover {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            #viewTab:checked {
                background-color: #00d4ff;
                color: #000000;
                font-weight: bold;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            #viewTabBar {
                background-color: #ffffff;
                border-bottom: 1px solid #cccccc;
            }
            #viewTab {
                background-color: transparent;
                color: #333333;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #viewTab:hover {
                background-color: #f0f0f0;
                color: #000000;
            }
            #viewTab:checked {
                background-color: #0066cc;
                color: #ffffff;
                font-weight: bold;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            #viewTabBar {
                background-color: #000814;
                border-bottom: 1px solid #1a2838;
            }
            #viewTab {
                background-color: transparent;
                color: #a8a8a8;
                border: none;
                border-radius: 2px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
            }
            #viewTab:hover {
                background-color: #0d1420;
                color: #e8e8e8;
            }
            #viewTab:checked {
                background-color: #FF8000;
                color: #000000;
                font-weight: bold;
            }
        """
