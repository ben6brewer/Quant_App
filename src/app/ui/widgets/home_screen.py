from __future__ import annotations

from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.core.config import MODULE_SECTIONS
from app.ui.widgets.section_tab_bar import SectionTabBar
from app.ui.widgets.module_tile_grid import ModuleTileGrid


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

        # Settings button (right)
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.setObjectName("settingsButton")
        self.settings_btn.setFixedSize(120, 40)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        top_bar_layout.addWidget(self.settings_btn, alignment=Qt.AlignRight)

        layout.addWidget(top_bar)

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

    def refresh(self) -> None:
        """Refresh the home screen (reload favorites and refresh grid)."""
        self.tile_grid.refresh_tiles()

    def reset_to_all_modules(self) -> None:
        """Reset view to show all modules (no section filter)."""
        self.tab_bar.clear_selection()
        self.tile_grid.set_section_filter("")
