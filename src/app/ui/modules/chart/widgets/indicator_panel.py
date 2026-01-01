"""Indicator Panel Widget - Sidebar for managing technical indicators."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common.lazy_theme_mixin import LazyThemeMixin
from ..services import ChartThemeService, IndicatorService


class IndicatorPanel(LazyThemeMixin, QWidget):
    """Sidebar panel for technical indicator selection and management.

    Provides lists of overlay and oscillator indicators with buttons
    for creating, applying, editing, and deleting custom indicators.
    """

    # Signals
    create_clicked = Signal()  # Create new indicator button
    apply_clicked = Signal()  # Apply indicators button
    clear_clicked = Signal()  # Clear selected indicators button
    clear_all_clicked = Signal()  # Clear all indicators button
    edit_clicked = Signal()  # Edit selected indicator button
    delete_clicked = Signal()  # Delete selected indicator button
    indicator_double_clicked = Signal(str)  # Indicator name when double-clicked

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application
        self._setup_ui()
        self._connect_signals()
        self._apply_theme()

        # Connect to theme changes (lazy - only apply when visible)
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self) -> None:
        """Create the indicator panel UI layout."""
        self.setFixedWidth(250)
        self.setObjectName("indicatorPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header = QLabel("Technical Indicators")
        header.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
                background-color: transparent;
            }
        """)
        layout.addWidget(header)

        # Create New Indicator button
        create_btn = QPushButton("Create New Indicator")
        create_btn.setObjectName("createButton")
        layout.addWidget(create_btn)
        self.create_btn = create_btn

        # Overlay indicators section
        overlay_label = QLabel("Overlays:")
        overlay_label.setStyleSheet("font-size: 12px; font-weight: bold; background-color: transparent;")
        layout.addWidget(overlay_label)

        self.overlay_list = QListWidget()
        self.overlay_list.setSelectionMode(QListWidget.MultiSelection)
        self.overlay_list.addItems(IndicatorService.get_overlay_names())
        self.overlay_list.setMaximumHeight(200)
        layout.addWidget(self.overlay_list)

        # Oscillator indicators section
        oscillator_label = QLabel("Oscillators")
        oscillator_label.setStyleSheet("font-size: 12px; font-weight: bold; background-color: transparent;")
        layout.addWidget(oscillator_label)

        self.oscillator_list = QListWidget()
        self.oscillator_list.setSelectionMode(QListWidget.MultiSelection)
        self.oscillator_list.addItems(IndicatorService.get_oscillator_names())
        self.oscillator_list.setMaximumHeight(150)
        layout.addWidget(self.oscillator_list)

        # Apply button
        apply_btn = QPushButton("Apply Indicators")
        layout.addWidget(apply_btn)
        self.apply_btn = apply_btn

        # Clear Selected button
        clear_btn = QPushButton("Clear Selected")
        layout.addWidget(clear_btn)
        self.clear_btn = clear_btn

        # Clear All button
        clear_all_btn = QPushButton("Clear All")
        layout.addWidget(clear_all_btn)
        self.clear_all_btn = clear_all_btn

        # Edit button
        edit_btn = QPushButton("Edit Selected")
        layout.addWidget(edit_btn)
        self.edit_btn = edit_btn

        # Delete selected indicator button
        delete_btn = QPushButton("Delete Selected")
        layout.addWidget(delete_btn)
        self.delete_btn = delete_btn

        layout.addStretch(1)

    def _connect_signals(self) -> None:
        """Connect internal widget signals to external signals."""
        self.create_btn.clicked.connect(self.create_clicked.emit)
        self.apply_btn.clicked.connect(self.apply_clicked.emit)
        self.clear_btn.clicked.connect(self.clear_clicked.emit)
        self.clear_all_btn.clicked.connect(self.clear_all_clicked.emit)
        self.edit_btn.clicked.connect(self.edit_clicked.emit)
        self.delete_btn.clicked.connect(self.delete_clicked.emit)

        # Double-click to edit
        self.overlay_list.itemDoubleClicked.connect(
            lambda item: self.indicator_double_clicked.emit(item.text())
        )
        self.oscillator_list.itemDoubleClicked.connect(
            lambda item: self.indicator_double_clicked.emit(item.text())
        )

    def _apply_theme(self) -> None:
        """Apply theme-specific styling to the indicator panel."""
        theme = self.theme_manager.current_theme
        stylesheet = ChartThemeService.get_indicator_panel_stylesheet(theme)
        self.setStyleSheet(stylesheet)

    # Public methods for indicator management
    def get_selected_overlays(self) -> list[str]:
        """Get list of selected overlay indicator names."""
        return [item.text() for item in self.overlay_list.selectedItems()]

    def get_selected_oscillators(self) -> list[str]:
        """Get list of selected oscillator indicator names."""
        return [item.text() for item in self.oscillator_list.selectedItems()]

    def get_all_selected(self) -> tuple[list[str], list[str]]:
        """Get both overlay and oscillator selections.

        Returns:
            Tuple of (overlay_names, oscillator_names)
        """
        return (self.get_selected_overlays(), self.get_selected_oscillators())

    def clear_selections(self) -> None:
        """Clear all indicator selections."""
        self.overlay_list.clearSelection()
        self.oscillator_list.clearSelection()

    def refresh_indicators(self, preserve_selection: bool = True) -> None:
        """Refresh indicator lists from IndicatorService.

        Args:
            preserve_selection: If True, restore previous selections after refresh
        """
        if preserve_selection:
            # Save current selections
            overlay_selected = self.get_selected_overlays()
            oscillator_selected = self.get_selected_oscillators()

        # Refresh lists
        self.overlay_list.clear()
        self.overlay_list.addItems(sorted(IndicatorService.get_overlay_names()))

        self.oscillator_list.clear()
        self.oscillator_list.addItems(sorted(IndicatorService.get_oscillator_names()))

        if preserve_selection:
            # Restore selections
            for i in range(self.overlay_list.count()):
                item = self.overlay_list.item(i)
                if item.text() in overlay_selected:
                    item.setSelected(True)

            for i in range(self.oscillator_list.count()):
                item = self.oscillator_list.item(i)
                if item.text() in oscillator_selected:
                    item.setSelected(True)
