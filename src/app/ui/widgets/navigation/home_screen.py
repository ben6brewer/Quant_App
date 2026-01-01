from __future__ import annotations

from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.core.config import MODULE_SECTIONS
from .section_tab_bar import SectionTabBar
from .module_tile_grid import ModuleTileGrid


class HomeScreen(QWidget):
    """
    Main home screen combining section tabs and module tile grid.
    """

    module_selected = Signal(str)  # Emitted when user selects a module
    settings_requested = Signal()  # Emitted when Settings button is clicked

    def __init__(self, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.theme_manager = theme_manager

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Setup the home screen UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar: Section tabs + Settings button
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(0)

        # Section tab bar (left)
        self.tab_bar = SectionTabBar(self.theme_manager)
        top_bar_layout.addWidget(self.tab_bar)

        # Settings button (right) - styled with background to match module settings buttons
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setFixedSize(120, 40)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        top_bar_layout.addWidget(self.settings_btn, alignment=Qt.AlignRight)

        # Apply settings button styling
        self._apply_settings_btn_styling()

        # Connect theme changes for settings button
        self.theme_manager.theme_changed.connect(self._on_settings_btn_theme_changed)

        layout.addWidget(top_bar)

        # Search bar container (centered, width of 2 tiles)
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 40, 0, 10)  # Add vertical spacing (more on top)
        search_layout.setSpacing(0)

        # Add stretch before search box
        search_layout.addStretch(1)

        # Search bar (width of 2 tiles: 453*2 + 20 = 926px)
        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("Search modules...")
        self.search_box.setFixedSize(926, 40)
        self.search_box.setClearButtonEnabled(True)  # Add X button to clear
        search_layout.addWidget(self.search_box)

        # Add stretch after search box
        search_layout.addStretch(1)

        layout.addWidget(search_container)

        # Apply search box styling
        self._apply_search_styling()

        # Connect theme changes for search box
        self.theme_manager.theme_changed.connect(self._on_search_theme_changed)

        # Module tile grid below
        self.tile_grid = ModuleTileGrid(self.theme_manager)
        layout.addWidget(self.tile_grid, stretch=1)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Tab bar section changes
        self.tab_bar.section_changed.connect(self._on_section_changed)

        # Tile clicks
        self.tile_grid.tile_clicked.connect(self._on_tile_clicked)

        # Favorite toggles
        self.tile_grid.favorite_toggled.connect(self._on_favorite_toggled)

        # Search box text changes
        self.search_box.textChanged.connect(self._on_search_changed)

    def _on_section_changed(self, section: str) -> None:
        """
        Handle section tab change.

        Special case: If "Charting" section is selected and it has only 1 module,
        auto-open that module instead of filtering.
        """
        if section == "Charting":
            # Check if Charting section has only 1 module
            charting_modules = MODULE_SECTIONS.get("Charting", [])
            if len(charting_modules) == 1:
                # Auto-open the Charts module
                module_id = charting_modules[0]["id"]
                self.module_selected.emit(module_id)
                # Clear tab selection
                self.tab_bar.clear_selection()
                return

        # Normal case: filter tiles by section
        self.tile_grid.set_section_filter(section)

    def _on_tile_clicked(self, module_id: str) -> None:
        """Handle tile click - emit module_selected signal."""
        self.module_selected.emit(module_id)

    def _on_favorite_toggled(self, module_id: str, is_favorite: bool) -> None:
        """Handle favorite toggle - grid already refreshes itself."""
        pass  # Grid handles refresh internally

    def _on_settings_clicked(self) -> None:
        """Handle Settings button click."""
        self.settings_requested.emit()

    def _on_search_changed(self, text: str) -> None:
        """Handle search box text change."""
        self.tile_grid.set_search_filter(text)

    def refresh(self) -> None:
        """Refresh the home screen (reload favorites and refresh grid)."""
        self.tile_grid.refresh_tiles()

    def reset_to_all_modules(self) -> None:
        """Reset view to show all modules (no section filter)."""
        self.tab_bar.clear_selection()
        self.tile_grid.set_section_filter("")

    def _on_search_theme_changed(self, theme: str) -> None:
        """Handle theme change for search box."""
        self._apply_search_styling()

    def _on_settings_btn_theme_changed(self, theme: str) -> None:
        """Handle theme change for settings button."""
        self._apply_settings_btn_styling()

    def _apply_settings_btn_styling(self) -> None:
        """Apply theme-specific styling to settings button (matches module settings buttons)."""
        theme = self.theme_manager.current_theme

        if theme == "dark":
            self.settings_btn.setStyleSheet("""
                #settingsBtn {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                    border-radius: 3px;
                    padding: 6px 12px;
                    font-size: 13px;
                }
                #settingsBtn:hover {
                    background-color: #3d3d3d;
                    border-color: #00d4ff;
                }
                #settingsBtn:pressed {
                    background-color: #1a1a1a;
                }
            """)
        elif theme == "bloomberg":
            self.settings_btn.setStyleSheet("""
                #settingsBtn {
                    background-color: #0d1420;
                    color: #e8e8e8;
                    border: 1px solid #1a2838;
                    border-radius: 3px;
                    padding: 6px 12px;
                    font-size: 13px;
                }
                #settingsBtn:hover {
                    background-color: #1a2838;
                    border-color: #FF8000;
                }
                #settingsBtn:pressed {
                    background-color: #060a10;
                }
            """)
        else:  # light theme
            self.settings_btn.setStyleSheet("""
                #settingsBtn {
                    background-color: #f5f5f5;
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                    padding: 6px 12px;
                    font-size: 13px;
                }
                #settingsBtn:hover {
                    background-color: #e8e8e8;
                    border-color: #0066cc;
                }
                #settingsBtn:pressed {
                    background-color: #d0d0d0;
                }
            """)

    def _apply_search_styling(self) -> None:
        """Apply theme-specific styling to search box."""
        theme = self.theme_manager.current_theme

        if theme == "dark":
            self.search_box.setStyleSheet("""
                #searchBox {
                    background-color: #1e1e1e;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                    border-radius: 2px;
                    padding: 0px 10px;
                    font-size: 13px;
                    font-weight: 500;
                }
                #searchBox:hover {
                    border: 1px solid #00d4ff;
                    background-color: #252525;
                }
                #searchBox:focus {
                    border: 1px solid #00d4ff;
                    background-color: #252525;
                }
            """)
        elif theme == "bloomberg":
            self.search_box.setStyleSheet("""
                #searchBox {
                    background-color: #0a1018;
                    color: #e8e8e8;
                    border: 1px solid #1a2332;
                    border-radius: 2px;
                    padding: 0px 10px;
                    font-size: 13px;
                    font-weight: 500;
                    font-family: "Consolas", "Monaco", "Courier New", monospace;
                }
                #searchBox:hover {
                    border: 1px solid #FF8000;
                    background-color: #0d1420;
                }
                #searchBox:focus {
                    border: 1px solid #FF8000;
                    background-color: #0d1420;
                }
            """)
        else:  # light theme
            self.search_box.setStyleSheet("""
                #searchBox {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 2px;
                    padding: 0px 10px;
                    font-size: 13px;
                    font-weight: 500;
                }
                #searchBox:hover {
                    border: 1px solid #0066cc;
                    background-color: #f9f9f9;
                }
                #searchBox:focus {
                    border: 1px solid #0066cc;
                    background-color: #ffffff;
                }
            """)
