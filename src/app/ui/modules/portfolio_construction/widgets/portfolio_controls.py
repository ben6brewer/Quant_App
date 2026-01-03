"""Portfolio Controls Widget - Top Control Bar"""

from typing import List
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PySide6.QtCore import Signal

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import LazyThemeMixin, SmoothScrollListView


class PortfolioControls(LazyThemeMixin, QWidget):
    """
    Control bar at top of portfolio module.
    Contains: Home button, Portfolio selector, New/Save (transaction view only).
    """

    # Signals
    home_clicked = Signal()
    portfolio_changed = Signal(str)       # Portfolio name changed
    save_clicked = Signal()
    import_clicked = Signal()
    export_clicked = Signal()
    new_portfolio_clicked = Signal()
    rename_portfolio_clicked = Signal()
    delete_portfolio_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._theme_dirty = False  # For lazy theme application

        self._setup_ui()
        self._apply_theme()

        # Lazy theme - only apply when visible
        self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)

    def showEvent(self, event):
        """Handle show event - apply pending theme if needed."""
        super().showEvent(event)
        self._check_theme_dirty()

    def _setup_ui(self):
        """Setup control bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Home button (leftmost)
        self.home_btn = QPushButton("Home")
        self.home_btn.setFixedSize(100, 40)
        self.home_btn.setObjectName("home_btn")
        self.home_btn.clicked.connect(self.home_clicked.emit)
        layout.addWidget(self.home_btn)

        # Add stretch to push portfolio selector toward center
        layout.addStretch(1)

        # Portfolio selector (editable with read-only line edit for display control)
        self.portfolio_label = QLabel("Portfolio:")
        self.portfolio_label.setObjectName("portfolio_label")
        layout.addWidget(self.portfolio_label)
        self.portfolio_combo = QComboBox()
        self.portfolio_combo.setEditable(True)
        self.portfolio_combo.lineEdit().setReadOnly(True)
        self.portfolio_combo.lineEdit().setPlaceholderText("Select Portfolio...")
        self.portfolio_combo.setFixedWidth(250)
        self.portfolio_combo.setFixedHeight(45)
        # Use custom smooth scroll view for the dropdown
        smooth_view = SmoothScrollListView(self.portfolio_combo)
        smooth_view.setAlternatingRowColors(True)
        self.portfolio_combo.setView(smooth_view)
        self.portfolio_combo.currentTextChanged.connect(self._on_portfolio_changed)
        layout.addWidget(self.portfolio_combo)

        layout.addSpacing(8)

        # Save button
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedSize(80, 40)
        self.save_btn.clicked.connect(self.save_clicked.emit)
        layout.addWidget(self.save_btn)

        layout.addSpacing(8)

        # Import button
        self.import_btn = QPushButton("Import")
        self.import_btn.setFixedSize(80, 40)
        self.import_btn.clicked.connect(self.import_clicked.emit)
        layout.addWidget(self.import_btn)

        layout.addSpacing(8)

        # Export button
        self.export_btn = QPushButton("Export")
        self.export_btn.setFixedSize(80, 40)
        self.export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self.export_btn)

        layout.addSpacing(8)

        # Rename button
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setFixedSize(80, 40)
        self.rename_btn.clicked.connect(self.rename_portfolio_clicked.emit)
        layout.addWidget(self.rename_btn)

        layout.addSpacing(8)

        # Delete button
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setFixedSize(80, 40)
        self.delete_btn.setObjectName("delete_btn")
        self.delete_btn.clicked.connect(self.delete_portfolio_clicked.emit)
        layout.addWidget(self.delete_btn)

        # Add stretch to push settings button to the right
        layout.addStretch(1)

        # Settings button (right-aligned)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedSize(100, 40)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

    def _on_portfolio_changed(self, name: str):
        """Handle portfolio dropdown selection."""
        if name == "Create New Portfolio":
            # Reset to previous selection before emitting new portfolio signal
            self.portfolio_combo.blockSignals(True)
            # Find first real portfolio (not "Create New Portfolio")
            found_portfolio = False
            for i in range(self.portfolio_combo.count()):
                item_text = self.portfolio_combo.itemText(i)
                if item_text != "Create New Portfolio":
                    self.portfolio_combo.setCurrentIndex(i)
                    # Show name without prefix in the display
                    if item_text.startswith("[Port] "):
                        self.portfolio_combo.lineEdit().setText(item_text[7:])
                    found_portfolio = True
                    break
            if not found_portfolio:
                # No portfolios exist, reset to placeholder (index -1 shows placeholder)
                self.portfolio_combo.setCurrentIndex(-1)
            self.portfolio_combo.blockSignals(False)
            # Emit signal to create new portfolio
            self.new_portfolio_clicked.emit()
        elif name:
            # Show name without prefix in the display
            if name.startswith("[Port] "):
                self.portfolio_combo.lineEdit().setText(name[7:])
            self.portfolio_changed.emit(name)

    def set_view_mode(self, is_transaction_view: bool):
        """
        Show/hide buttons based on active view.

        Args:
            is_transaction_view: True for Transaction Log (show Save/Import/Rename/Delete buttons),
                                False for Portfolio Holdings (hide editing buttons)
        """
        self.save_btn.setVisible(is_transaction_view)
        self.import_btn.setVisible(is_transaction_view)
        self.rename_btn.setVisible(is_transaction_view)
        self.delete_btn.setVisible(is_transaction_view)

    def update_portfolio_list(self, portfolios: List[str], current: str = None):
        """
        Update portfolio dropdown.

        Args:
            portfolios: List of portfolio names
            current: Currently selected portfolio name (None to show placeholder)
        """
        self.portfolio_combo.blockSignals(True)
        self.portfolio_combo.clear()
        # Add "Create New Portfolio" as first option
        self.portfolio_combo.addItem("Create New Portfolio")
        for p in portfolios:
            self.portfolio_combo.addItem(f"[Port] {p}")
        if current and current in portfolios:
            self.portfolio_combo.setCurrentText(f"[Port] {current}")
            # Show name without prefix in the display
            self.portfolio_combo.lineEdit().setText(current)
        else:
            # Default to placeholder (index -1 shows placeholder text)
            self.portfolio_combo.setCurrentIndex(-1)
        self.portfolio_combo.blockSignals(False)

        # Update button states based on whether a portfolio is selected
        self._update_button_states(current is not None and current in portfolios)

    def _update_button_states(self, portfolio_loaded: bool):
        """
        Enable/disable buttons based on whether a portfolio is loaded.

        Args:
            portfolio_loaded: True if a portfolio is currently loaded
        """
        self.save_btn.setEnabled(portfolio_loaded)
        self.import_btn.setEnabled(portfolio_loaded)
        self.export_btn.setEnabled(portfolio_loaded)
        self.rename_btn.setEnabled(portfolio_loaded)
        self.delete_btn.setEnabled(portfolio_loaded)

    def get_current_portfolio(self) -> str:
        """
        Get currently selected portfolio name.

        Returns:
            Portfolio name or empty string
        """
        current = self.portfolio_combo.currentText()
        # Return empty string for special items or placeholder (empty text)
        if not current or current == "Create New Portfolio":
            return ""
        return current

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
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                font-size: 13px;
            }
            QLabel#portfolio_label {
                color: #ffffff;
                font-size: 15px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 16px;
            }
            QComboBox:hover {
                border-color: #00d4ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #ffffff;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #ffffff;
                selection-background-color: #00d4ff;
                selection-color: #000000;
                font-size: 15px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 10px 12px;
                min-height: 28px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #252525;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #00d4ff;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
            QPushButton#delete_btn:hover {
                background-color: #5c1a1a;
                border-color: #d32f2f;
            }
            QPushButton#delete_btn:pressed {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #666666;
                border-color: #2d2d2d;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QLabel {
                color: #333333;
                font-size: 13px;
            }
            QLabel#portfolio_label {
                color: #000000;
                font-size: 15px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 16px;
            }
            QComboBox:hover {
                border-color: #0066cc;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #000000;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #f5f5f5;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
                font-size: 15px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 10px 12px;
                min-height: 28px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #e8e8e8;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QPushButton {
                background-color: #f5f5f5;
                color: #000000;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
                border-color: #0066cc;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton#delete_btn:hover {
                background-color: #ffebee;
                border-color: #d32f2f;
            }
            QPushButton#delete_btn:pressed {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #999999;
                border-color: #cccccc;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QWidget {
                background-color: #000814;
                color: #e8e8e8;
            }
            QLabel {
                color: #a8a8a8;
                font-size: 13px;
            }
            QLabel#portfolio_label {
                color: #e8e8e8;
                font-size: 15px;
                font-weight: 500;
            }
            QComboBox {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 8px 12px;
                font-size: 16px;
            }
            QComboBox:hover {
                border-color: #FF8000;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #e8e8e8;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #0d1420;
                color: #e8e8e8;
                selection-background-color: #FF8000;
                selection-color: #000000;
                font-size: 15px;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 10px 12px;
                min-height: 28px;
            }
            QComboBox QAbstractItemView::item:alternate {
                background-color: #0a1018;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #FF8000;
                color: #000000;
            }
            QPushButton {
                background-color: #0d1420;
                color: #e8e8e8;
                border: 1px solid #1a2838;
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1a2838;
                border-color: #FF8000;
            }
            QPushButton:pressed {
                background-color: #060a10;
            }
            QPushButton#delete_btn:hover {
                background-color: #3d1a1a;
                border-color: #d32f2f;
            }
            QPushButton#delete_btn:pressed {
                background-color: #d32f2f;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #060a10;
                color: #555555;
                border-color: #1a2838;
            }
        """
