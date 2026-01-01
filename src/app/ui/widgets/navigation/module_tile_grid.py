from __future__ import annotations

from typing import Dict, List, Optional
from PySide6.QtWidgets import QScrollArea, QWidget, QGridLayout, QVBoxLayout
from PySide6.QtCore import Signal, Qt

from app.core.theme_manager import ThemeManager
from app.core.config import MODULE_SECTIONS, TILE_COLS, TILE_SPACING
from app.services.favorites_service import FavoritesService
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from .module_tile import ModuleTile


class ModuleTileGrid(LazyThemeMixin, QScrollArea):
    """
    Grid layout for module tiles with filtering and sorting capabilities.
    """

    tile_clicked = Signal(str)  # Forward tile click signal
    favorite_toggled = Signal(str, bool)  # Forward favorite toggle signal

    def __init__(self, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self.tiles: Dict[str, ModuleTile] = {}
        self.current_section_filter = ""  # "" means show all
        self.current_search_filter = ""   # "" means no search filtering

        self._setup_ui()
        self._create_all_tiles()
        self._layout_tiles()

        # Connect to theme changes (lazy - only apply when visible)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)
        self._apply_theme()

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self) -> None:
        """Setup the scroll area and grid."""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container widget
        self.container = QWidget()
        self.setWidget(self.container)

        # Main layout
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 20, 20, 0)  # 20px padding on left, top, right
        container_layout.setSpacing(0)

        # Grid layout
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(TILE_SPACING)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)  # Center horizontally
        container_layout.addLayout(self.grid_layout)

        # Add stretch to push grid to top
        container_layout.addStretch(1)

    def _create_all_tiles(self) -> None:
        """Create tiles for all modules."""
        for section_name, modules in MODULE_SECTIONS.items():
            for module in modules:
                module_id = module["id"]
                label = module["label"]

                # Create tile
                tile = ModuleTile(
                    module_id=module_id,
                    label=label,
                    section=section_name,
                    theme_manager=self.theme_manager
                )

                # Connect signals
                tile.clicked.connect(self._on_tile_clicked)
                tile.favorite_toggled.connect(self._on_favorite_toggled)

                # Store tile
                self.tiles[module_id] = tile

    def _on_tile_clicked(self, module_id: str) -> None:
        """Handle tile click."""
        self.tile_clicked.emit(module_id)

    def _on_favorite_toggled(self, module_id: str, is_favorite: bool) -> None:
        """Handle favorite toggle."""
        self.favorite_toggled.emit(module_id, is_favorite)
        # Re-sort tiles to move favorites to top
        self.refresh_tiles()

    def set_section_filter(self, section: str) -> None:
        """
        Set section filter to show only modules from a specific section.
        Pass "" to show all modules.
        """
        self.current_section_filter = section
        self.refresh_tiles()

    def set_search_filter(self, query: str) -> None:
        """
        Set search filter to show only modules matching the query.
        Pass "" to clear search filter.
        Search is case-insensitive and matches against module labels.
        """
        self.current_search_filter = query.strip()
        self.refresh_tiles()

    def refresh_tiles(self) -> None:
        """Refresh tile layout (re-sort and re-layout)."""
        self._layout_tiles()

    def _get_filtered_tiles(self) -> List[ModuleTile]:
        """Get tiles filtered by current section filter AND search filter."""
        # Start with all tiles
        tiles = list(self.tiles.values())

        # Apply section filter first
        if self.current_section_filter:
            modules_in_section = MODULE_SECTIONS.get(self.current_section_filter, [])
            module_ids_in_section = [m["id"] for m in modules_in_section]
            tiles = [t for t in tiles if t.module_id in module_ids_in_section]

        # Apply search filter on top of section filter
        if self.current_search_filter:
            search_lower = self.current_search_filter.lower()
            tiles = [t for t in tiles if search_lower in t.label.lower()]

        return tiles

    def _sort_tiles(self, tiles: List[ModuleTile]) -> List[ModuleTile]:
        """Sort tiles: favorites first, then alphabetical by label."""
        return sorted(
            tiles,
            key=lambda t: (
                not FavoritesService.is_favorite(t.module_id),  # Favorites first (False < True)
                t.label.lower()  # Then alphabetical
            )
        )

    def _layout_tiles(self) -> None:
        """Layout tiles in grid."""
        # Clear existing layout
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        # Get filtered and sorted tiles
        filtered_tiles = self._get_filtered_tiles()
        sorted_tiles = self._sort_tiles(filtered_tiles)

        # Hide all tiles first
        for tile in self.tiles.values():
            tile.hide()

        # Layout visible tiles in 3-column grid
        for idx, tile in enumerate(sorted_tiles):
            row = idx // TILE_COLS
            col = idx % TILE_COLS
            self.grid_layout.addWidget(tile, row, col)
            tile.show()

        # Update tile favorite status (in case it changed externally)
        for tile in sorted_tiles:
            is_favorite = FavoritesService.is_favorite(tile.module_id)
            tile.set_favorite(is_favorite)

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "dark":
            self.setStyleSheet("""
                QScrollArea {
                    background-color: #1e1e1e;
                    border: none;
                }
                QWidget#container {
                    background-color: #1e1e1e;
                }
            """)
        elif theme == "bloomberg":
            self.setStyleSheet("""
                QScrollArea {
                    background-color: #000814;
                    border: none;
                }
                QWidget#container {
                    background-color: #000814;
                }
            """)
        else:  # light theme
            self.setStyleSheet("""
                QScrollArea {
                    background-color: #ffffff;
                    border: none;
                }
                QWidget#container {
                    background-color: #ffffff;
                }
            """)

        # Set object name for styling
        self.container.setObjectName("container")
