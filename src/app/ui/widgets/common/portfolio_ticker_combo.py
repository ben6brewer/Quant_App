"""Portfolio/Ticker ComboBox - Reusable editable combo for portfolios and tickers."""

from typing import List, Optional

from PySide6.QtWidgets import QComboBox, QAbstractItemView, QListView
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QWheelEvent


class SmoothScrollListView(QListView):
    """QListView with smoother, slower scrolling for combo box dropdowns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def wheelEvent(self, event: QWheelEvent):
        """Override wheel event to reduce scroll speed."""
        delta = event.angleDelta().y()
        pixels_to_scroll = int(delta / 4)
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - pixels_to_scroll)
        event.accept()


class PortfolioTickerComboBox(QComboBox):
    """
    Editable combo box for selecting portfolios or typing tickers.

    Features:
    - Portfolios are stored with "[Port] " prefix internally
    - Display shows portfolio names without prefix
    - Typed text is uppercased (for tickers)
    - Handles focus-out correctly without triggering unnecessary reloads
    - Emits value_changed signal with full value (including [Port] prefix for portfolios)

    Usage:
        combo = PortfolioTickerComboBox()
        combo.set_portfolios(["Portfolio A", "Portfolio B"])
        combo.value_changed.connect(self._on_value_changed)
    """

    # Signal emitted when value changes (includes [Port] prefix for portfolios)
    value_changed = Signal(str)

    # Prefix used for portfolio items
    PORTFOLIO_PREFIX = "[Port] "

    def __init__(self, placeholder: str = "Type ticker or select...", parent=None):
        super().__init__(parent)
        self._last_value: str = ""
        self._placeholder = placeholder

        self._setup()

    def _setup(self):
        """Setup the combo box."""
        self.setEditable(True)
        self.lineEdit().setPlaceholderText(self._placeholder)

        # Use smooth scrolling list view
        smooth_view = SmoothScrollListView(self)
        smooth_view.setAlternatingRowColors(True)
        self.setView(smooth_view)

        # Connect signals
        self.lineEdit().editingFinished.connect(self._on_editing_finished)
        self.lineEdit().returnPressed.connect(self._on_editing_finished)
        self.currentIndexChanged.connect(self._on_index_changed)

    def _on_editing_finished(self):
        """Handle Enter key or focus out."""
        text = self.currentText().strip()

        if not text:
            return

        # Check if this matches a portfolio name (case-insensitive)
        portfolio_match = self._find_portfolio_match(text)

        if portfolio_match:
            # Use the full portfolio item (with prefix)
            full_value = portfolio_match
        else:
            # Uppercase for ticker lookup
            full_value = text.upper()

        # Update display (strip prefix for portfolios)
        display_text = self._strip_prefix(full_value)
        self.blockSignals(True)
        self.lineEdit().blockSignals(True)
        self.lineEdit().setText(display_text)
        self.lineEdit().blockSignals(False)
        self.blockSignals(False)

        # Only emit if value actually changed
        if full_value != self._last_value:
            self._last_value = full_value
            self.value_changed.emit(full_value)

    def _on_index_changed(self, index: int):
        """Handle dropdown selection."""
        if index >= 0:
            text = self.currentText()
            if text and text != self._last_value:
                self._last_value = text
                # Show name without prefix in display
                if text.startswith(self.PORTFOLIO_PREFIX):
                    self.lineEdit().setText(text[len(self.PORTFOLIO_PREFIX):])
                self.value_changed.emit(text)

    def _find_portfolio_match(self, text: str) -> Optional[str]:
        """
        Find a portfolio item matching the given text (case-insensitive).

        Args:
            text: The text to match (without prefix)

        Returns:
            The full item text (with prefix) if found, None otherwise.
        """
        text_lower = text.lower()
        for i in range(self.count()):
            item = self.itemText(i)
            # Strip prefix for comparison
            item_name = self._strip_prefix(item)
            if item_name.lower() == text_lower:
                return item
        return None

    def _strip_prefix(self, text: str) -> str:
        """Strip the [Port] prefix from text if present."""
        if text.startswith(self.PORTFOLIO_PREFIX):
            return text[len(self.PORTFOLIO_PREFIX):]
        return text

    def set_portfolios(self, portfolios: List[str], current: Optional[str] = None):
        """
        Set the list of available portfolios.

        Args:
            portfolios: List of portfolio names (without prefix)
            current: Currently selected portfolio name (without prefix), or None
        """
        self.blockSignals(True)
        self.clear()
        for p in portfolios:
            self.addItem(f"{self.PORTFOLIO_PREFIX}{p}")

        if current and current in portfolios:
            self.setCurrentText(f"{self.PORTFOLIO_PREFIX}{current}")
            self.lineEdit().setText(current)  # Display without prefix
            self._last_value = f"{self.PORTFOLIO_PREFIX}{current}"
        else:
            self.setCurrentIndex(-1)  # Show placeholder
            self._last_value = ""

        self.blockSignals(False)

    def set_value(self, value: str):
        """
        Set the current value.

        Args:
            value: The value to set (can include [Port] prefix or be a ticker)
        """
        self.blockSignals(True)
        self.lineEdit().blockSignals(True)

        display_text = self._strip_prefix(value)
        self.lineEdit().setText(display_text)
        self._last_value = value

        self.lineEdit().blockSignals(False)
        self.blockSignals(False)

    def get_value(self) -> str:
        """
        Get the current value.

        Returns:
            The full value (including [Port] prefix for portfolios)
        """
        return self._last_value or self.currentText() or ""

    def get_display_value(self) -> str:
        """
        Get the displayed value (without [Port] prefix).

        Returns:
            The display text
        """
        return self.lineEdit().text() or ""

    def reset(self):
        """Reset to show placeholder."""
        self.blockSignals(True)
        self.setCurrentIndex(-1)
        self.lineEdit().clear()
        self._last_value = ""
        self.blockSignals(False)


class BenchmarkComboBox(PortfolioTickerComboBox):
    """
    Specialized combo box for benchmark selection.

    Same as PortfolioTickerComboBox but:
    - Uses "None" as default placeholder (customizable)
    - Treats empty/NONE as clearing the benchmark
    """

    def __init__(self, placeholder: str = "None", parent=None):
        super().__init__(placeholder=placeholder, parent=parent)

    def _on_editing_finished(self):
        """Handle Enter key or focus out - treats NONE/empty as clearing."""
        text = self.currentText().strip()

        # Treat "NONE" or empty as no benchmark
        if not text or text.upper() == "NONE":
            if self._last_value != "":
                self._last_value = ""
                self.blockSignals(True)
                self.lineEdit().clear()
                self.setCurrentIndex(-1)
                self.blockSignals(False)
                self.value_changed.emit("")
            return

        # Use parent logic for normal cases
        super()._on_editing_finished()


class PortfolioComboBox(QComboBox):
    """
    Read-only combo box for selecting portfolios only (no ticker typing).

    Features:
    - Portfolios are stored with "[Port] " prefix internally
    - Display shows portfolio names without prefix
    - Line edit is read-only (no typing allowed, dropdown only)
    - Emits value_changed signal with full value (including [Port] prefix)

    Usage:
        combo = PortfolioComboBox()
        combo.set_portfolios(["Portfolio A", "Portfolio B"])
        combo.value_changed.connect(self._on_value_changed)
    """

    value_changed = Signal(str)
    PORTFOLIO_PREFIX = "[Port] "

    def __init__(self, placeholder: str = "Select Portfolio...", parent=None):
        super().__init__(parent)
        self._last_value: str = ""
        self._placeholder = placeholder
        self._setup()

    def _setup(self):
        """Setup the combo box."""
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText(self._placeholder)

        # Use smooth scrolling list view
        smooth_view = SmoothScrollListView(self)
        smooth_view.setAlternatingRowColors(True)
        self.setView(smooth_view)

        # Connect selection signal
        self.currentTextChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str):
        """Handle dropdown selection."""
        if text and text != self._last_value:
            self._last_value = text
            # Show name without prefix in display (block signals to prevent re-trigger)
            if text.startswith(self.PORTFOLIO_PREFIX):
                self.blockSignals(True)
                self.lineEdit().setText(text[len(self.PORTFOLIO_PREFIX):])
                self.blockSignals(False)
            self.value_changed.emit(text)

    def set_portfolios(self, portfolios: List[str], current: Optional[str] = None):
        """
        Set the list of available portfolios.

        Args:
            portfolios: List of portfolio names (without prefix)
            current: Currently selected portfolio name (without prefix), or None
        """
        self.blockSignals(True)
        self.clear()
        for p in portfolios:
            self.addItem(f"{self.PORTFOLIO_PREFIX}{p}")

        if current and current in portfolios:
            self.setCurrentText(f"{self.PORTFOLIO_PREFIX}{current}")
            self.lineEdit().setText(current)
            self._last_value = f"{self.PORTFOLIO_PREFIX}{current}"
        else:
            self.setCurrentIndex(-1)
            self._last_value = ""

        self.blockSignals(False)

    def get_value(self) -> str:
        """Get the current value (with [Port] prefix)."""
        return self._last_value or self.currentText() or ""

    def get_display_value(self) -> str:
        """Get the displayed value (without [Port] prefix)."""
        return self.lineEdit().text() or ""

    def reset(self):
        """Reset to show placeholder."""
        self.blockSignals(True)
        self.setCurrentIndex(-1)
        self.lineEdit().clear()
        self._last_value = ""
        self.blockSignals(False)
