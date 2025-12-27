from __future__ import annotations

from typing import Optional, Dict
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.core.config import MODULE_SECTIONS


class SectionTabBar(QWidget):
    """
    Horizontal tab bar for filtering modules by section.
    """

    section_changed = Signal(str)  # Emits section name or "" for all

    def __init__(self, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.theme_manager = theme_manager
        self.buttons: Dict[str, QPushButton] = {}
        self.button_group: Optional[QButtonGroup] = None

        self._setup_ui()
        self._apply_theme()

        # Connect to theme changes
        self.theme_manager.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self) -> None:
        """Setup the tab bar UI."""
        self.setFixedHeight(50)
        self.setObjectName("sectionTabBar")

        # Horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(30, 10, 30, 10)
        layout.setSpacing(5)

        # Button group for exclusive selection
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(False)  # Allow deselecting to show all

        # Create tab for each section
        for section_name in MODULE_SECTIONS.keys():
            btn = QPushButton(section_name)
            btn.setObjectName("sectionTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumWidth(120)
            btn.setFixedHeight(40)

            # Connect click handler
            btn.clicked.connect(lambda checked, s=section_name: self._on_tab_clicked(s, checked))

            layout.addWidget(btn)
            self.buttons[section_name] = btn
            self.button_group.addButton(btn)

        # Add stretch to push tabs to left
        layout.addStretch(1)

    def _on_tab_clicked(self, section_name: str, checked: bool) -> None:
        """Handle tab button click."""
        if checked:
            # Tab was selected - deselect other tabs
            for name, btn in self.buttons.items():
                if name != section_name:
                    btn.setChecked(False)

            # Emit section name
            self.section_changed.emit(section_name)
        else:
            # Tab was deselected - show all modules
            self.section_changed.emit("")

    def set_active_section(self, section: str) -> None:
        """Set active section programmatically."""
        for name, btn in self.buttons.items():
            btn.setChecked(name == section)

    def clear_selection(self) -> None:
        """Clear all tab selections (show all modules)."""
        for btn in self.buttons.values():
            btn.setChecked(False)

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "dark":
            self.setStyleSheet("""
                #sectionTabBar {
                    background-color: #2d2d2d;
                    border-bottom: 2px solid #00d4ff;
                }
                #sectionTab {
                    background-color: transparent;
                    color: #cccccc;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 500;
                }
                #sectionTab:hover {
                    background-color: #3d3d3d;
                    color: #ffffff;
                }
                #sectionTab:checked {
                    background-color: #00d4ff;
                    color: #000000;
                    font-weight: bold;
                }
            """)
        else:  # light theme
            self.setStyleSheet("""
                #sectionTabBar {
                    background-color: #f5f5f5;
                    border-bottom: 2px solid #0066cc;
                }
                #sectionTab {
                    background-color: transparent;
                    color: #333333;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 500;
                }
                #sectionTab:hover {
                    background-color: #e0e0e0;
                    color: #000000;
                }
                #sectionTab:checked {
                    background-color: #0066cc;
                    color: #ffffff;
                    font-weight: bold;
                }
            """)
