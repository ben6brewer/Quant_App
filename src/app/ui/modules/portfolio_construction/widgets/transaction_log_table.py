"""Transaction Log Table Widget - Editable Transaction Table"""

from typing import Dict, List, Any, Optional
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QDoubleSpinBox, QAbstractButton, QWidget, QApplication,
    QHBoxLayout
)
from PySide6.QtCore import Qt, Signal, QDate, QTimer, QEvent
from PySide6.QtGui import QDoubleValidator, QKeySequence

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox
from ..services.portfolio_service import PortfolioService
from .no_scroll_combobox import NoScrollComboBox


class DateInputWidget(QLineEdit):
    """Free-form date input widget with live dash formatting and validation."""

    # Signal for QDateEdit compatibility
    date_changed = Signal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("YYYY-MM-DD")
        self.setMaxLength(10)  # "2025-01-15" = 10 chars

        # Parent reference for validation dialogs
        self._parent_table = None

        # Current valid date (or None if invalid/incomplete)
        self._current_date = QDate.currentDate()

    def keyPressEvent(self, event):
        """Handle key press for live dash formatting."""
        key = event.key()
        text_input = event.text()

        # Handle digit input
        if text_input.isdigit():
            current = self.text()
            cursor = self.cursorPosition()

            # If text is selected, replace selection with digit
            if self.hasSelectedText():
                start = self.selectionStart()
                end = start + len(self.selectedText())
                # Remove selected text
                new_text = current[:start] + text_input + current[end:]
                # Format with dashes
                formatted = self._format_with_dashes(new_text)
                # Cursor should be after the inserted digit
                digits_before = start  # Count of characters before selection
                # Find position after first digit in formatted text
                digit_count = 0
                new_cursor = 0
                for i, char in enumerate(formatted):
                    if char.isdigit():
                        digit_count += 1
                        if digit_count == 1:  # Position after first digit
                            new_cursor = i + 1
                            break
                self.setText(formatted)
                self.setCursorPosition(new_cursor)
                return

            # Insert digit at cursor (no selection)
            new_text = current[:cursor] + text_input + current[cursor:]

            # Format with dashes
            formatted = self._format_with_dashes(new_text)

            # Calculate new cursor position
            new_cursor = self._calculate_cursor_after_insert(cursor, formatted, current)

            # Update
            self.setText(formatted)
            self.setCursorPosition(new_cursor)
            return  # Consume event

        # Handle dash or slash input - accept but just reformat
        elif text_input in ('-', '/'):
            current = self.text()
            cursor = self.cursorPosition()

            # Just reformat current text (dash/slash gets ignored in formatting)
            # This allows typing "2025-01" naturally
            formatted = self._format_with_dashes(current)

            # If cursor is at a dash position after reformatting, move past it
            if cursor < len(formatted) and formatted[cursor:cursor+1] == '-':
                self.setCursorPosition(cursor + 1)

            return  # Consume event

        # Handle backspace
        elif key == Qt.Key_Backspace:
            self._handle_backspace()
            return

        # Handle Delete key
        elif key == Qt.Key_Delete:
            self._handle_delete()
            return

        # Handle Enter/Return (validate)
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if self._trigger_validation():
                self.clearFocus()
            return

        # Handle Tab (validate and move)
        elif key == Qt.Key_Tab:
            self._trigger_validation()
            super().keyPressEvent(event)  # Let Tab propagate
            return

        # Handle Escape (revert)
        elif key == Qt.Key_Escape:
            self._revert_to_last_valid()
            return

        # Handle Paste
        elif event.matches(QKeySequence.Paste):
            clipboard = QApplication.clipboard()
            pasted_text = clipboard.text()

            # Extract digits only (handles 2025/01/01, 2025-01-01, or any format)
            digits = ''.join(c for c in pasted_text if c.isdigit())[:8]
            formatted = self._format_with_dashes(digits)

            self.setText(formatted)
            self.setCursorPosition(len(formatted))
            return

        # Block all other keys (letters, symbols, etc.)
        return  # Consume event

    def _format_with_dashes(self, text: str) -> str:
        """Format text with dashes, allowing incomplete dates."""
        # Extract digits only
        digits = ''.join(c for c in text if c.isdigit())[:8]

        # Return empty if no digits
        if not digits:
            return ""

        # Format based on length
        if len(digits) <= 4:
            return digits
        elif len(digits) <= 6:
            return f"{digits[:4]}-{digits[4:]}"
        else:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"

    def _calculate_cursor_after_insert(self, old_cursor: int, new_text: str, old_text: str) -> int:
        """Calculate cursor position after inserting digit and auto-dashes."""
        old_dashes_before = old_text[:old_cursor].count('-')
        new_cursor = old_cursor + 1
        new_dashes_before = new_text[:new_cursor].count('-')

        if new_dashes_before > old_dashes_before:
            new_cursor += (new_dashes_before - old_dashes_before)

        return new_cursor

    def _find_cursor_after_n_digits(self, text: str, n: int) -> int:
        """Find cursor position after n digits (accounting for dashes)."""
        digit_count = 0
        for i, char in enumerate(text):
            if char.isdigit():
                digit_count += 1
                if digit_count == n:
                    return i + 1
        return len(text)

    def _handle_backspace(self):
        """Handle backspace with dash auto-removal."""
        current = self.text()
        cursor = self.cursorPosition()

        # If text is selected, delete selection
        if self.hasSelectedText():
            start = self.selectionStart()
            end = start + len(self.selectedText())
            new_text = current[:start] + current[end:]

            # Format remaining text
            formatted = self._format_with_dashes(new_text)
            self.setText(formatted)
            self.setCursorPosition(min(start, len(formatted)))
            return

        # Nothing to delete
        if cursor == 0:
            return

        # Get character before cursor
        char_before = current[cursor - 1]

        # If dash, skip it and delete digit before
        if char_before == '-':
            if cursor >= 2:
                # Delete digit before dash
                new_text = current[:cursor - 2] + current[cursor:]
                formatted = self._format_with_dashes(new_text)

                # Calculate cursor position
                digits_before = current[:cursor - 2].replace("-", "")
                new_cursor = self._find_cursor_after_n_digits(formatted, len(digits_before))

                self.setText(formatted)
                self.setCursorPosition(new_cursor)
            else:
                # Clear field (only 1 digit + dash)
                self.clear()
        else:
            # Delete digit
            new_text = current[:cursor - 1] + current[cursor:]
            formatted = self._format_with_dashes(new_text)

            # Calculate cursor position
            digits_before = current[:cursor - 1].replace("-", "")
            new_cursor = self._find_cursor_after_n_digits(formatted, len(digits_before))

            self.setText(formatted)
            self.setCursorPosition(new_cursor)

    def _handle_delete(self):
        """Handle Delete key (forward delete)."""
        current = self.text()
        cursor = self.cursorPosition()

        # If text is selected, delete selection (same as backspace)
        if self.hasSelectedText():
            self._handle_backspace()
            return

        # Nothing to delete
        if cursor >= len(current):
            return

        # Get character at cursor
        char_at_cursor = current[cursor]

        # If dash, skip it and delete digit after
        if char_at_cursor == '-':
            if cursor + 1 < len(current):
                # Delete digit after dash
                new_text = current[:cursor + 1] + current[cursor + 2:]
                formatted = self._format_with_dashes(new_text)

                # Keep cursor at same position
                digits_before = current[:cursor].replace("-", "")
                new_cursor = self._find_cursor_after_n_digits(formatted, len(digits_before))

                self.setText(formatted)
                self.setCursorPosition(new_cursor)
            else:
                # Dash at end, just remove it
                self.setText(current[:cursor])
        else:
            # Delete digit at cursor
            new_text = current[:cursor] + current[cursor + 1:]
            formatted = self._format_with_dashes(new_text)

            # Keep cursor at same position
            digits_before = current[:cursor].replace("-", "")
            new_cursor = self._find_cursor_after_n_digits(formatted, len(digits_before))

            self.setText(formatted)
            self.setCursorPosition(new_cursor)

    def _trigger_validation(self) -> bool:
        """Validate the current date and show error dialog if needed."""
        current = self.text()

        # Empty field is allowed (no error)
        if not current:
            self._current_date = None
            return True

        # Extract digits
        digits = current.replace("-", "")

        # Incomplete date (less than 8 digits)
        if len(digits) < 8:
            if self._parent_table:
                self._show_validation_error(
                    "Incomplete Date",
                    f"Please enter a complete date in YYYY-MM-DD format.\nCurrent input: {current}"
                )
                self.setFocus()
                self.selectAll()
            return False

        # Parse as QDate
        parsed_date = QDate.fromString(current, "yyyy-MM-dd")

        if not parsed_date.isValid():
            if self._parent_table:
                self._show_validation_error(
                    "Invalid Date",
                    f"The date '{current}' is not valid.\nPlease check the month and day values."
                )
                self.setFocus()
                self.selectAll()
            return False

        # Check future date
        if parsed_date > QDate.currentDate():
            if self._parent_table:
                self._show_validation_error(
                    "Future Date Not Allowed",
                    f"Transaction dates cannot be after today ({QDate.currentDate().toString('yyyy-MM-dd')})."
                )
                self.setFocus()
                self.selectAll()
            return False

        # Valid date - store and emit signal
        self._current_date = parsed_date
        self.date_changed.emit(parsed_date)
        return True

    def _show_validation_error(self, title: str, message: str):
        """Show validation error dialog."""
        from app.ui.widgets.common import CustomMessageBox

        if self._parent_table and hasattr(self._parent_table, 'theme_manager'):
            CustomMessageBox.warning(
                self._parent_table.theme_manager,
                self._parent_table,
                title,
                message
            )

    def _revert_to_last_valid(self):
        """Revert to last valid date (Escape key)."""
        if self._current_date and self._current_date.isValid():
            self.setText(self._current_date.toString("yyyy-MM-dd"))
        else:
            self.clear()
        self.clearFocus()

    def focusInEvent(self, event):
        """Select all text when focused."""
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusOutEvent(self, event):
        """Validate when focus leaves."""
        self._trigger_validation()
        super().focusOutEvent(event)

    # QDateEdit compatibility methods
    def setDate(self, date: QDate):
        """Set the date (for compatibility with QDateEdit)."""
        if date.isValid():
            self.setText(date.toString("yyyy-MM-dd"))
            self._current_date = date

    def date(self) -> QDate:
        """Get the current date (for compatibility with QDateEdit)."""
        return self._current_date if self._current_date and self._current_date.isValid() else QDate()

    def dateChanged(self):
        """For compatibility with QDateEdit signal."""
        return self.date_changed


class AutoSelectLineEdit(QLineEdit):
    """QLineEdit that auto-selects all text on focus or click and auto-capitalizes."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        # Connect to textEdited to auto-capitalize (textEdited only fires on user input)
        self.textEdited.connect(self._on_text_edited)

    def _on_text_edited(self, text: str):
        """Convert text to uppercase while preserving cursor position."""
        if text != text.upper():
            cursor_pos = self.cursorPosition()
            self.blockSignals(True)
            self.setText(text.upper())
            self.setCursorPosition(cursor_pos)
            self.blockSignals(False)
            # Emit textChanged manually since we blocked signals
            self.textChanged.emit(self.text())

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Select all text so typing replaces it
        self.selectAll()

    def mousePressEvent(self, event):
        # Select all text when clicked (whether already focused or not)
        super().mousePressEvent(event)
        self.selectAll()


class ValidatedNumericLineEdit(QLineEdit):
    """QLineEdit with numeric validation and optional prefix."""

    def __init__(self, min_value=0.0, max_value=1000000.0, decimals=2, prefix="", show_dash_for_zero=False, parent=None):
        super().__init__(parent)
        self.prefix = prefix
        self.decimals = decimals
        self.show_dash_for_zero = show_dash_for_zero

        self.validator = QDoubleValidator(min_value, max_value, decimals, self)
        self.validator.setNotation(QDoubleValidator.StandardNotation)
        self.setValidator(self.validator)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        if prefix:
            self.setPlaceholderText(f"{prefix}0.00")

    def value(self) -> float:
        text = self.text().replace(self.prefix, "").strip()
        if text == "--":
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    def setValue(self, value: float):
        # Show '--' for zero if enabled
        if self.show_dash_for_zero and value == 0.0:
            self.setText("--")
            return

        # Format with specified decimals, then strip trailing zeros
        formatted = f"{value:.{self.decimals}f}"
        # Remove trailing zeros and trailing decimal point
        formatted = formatted.rstrip('0').rstrip('.')

        self.setText(f"{self.prefix}{formatted}" if self.prefix else formatted)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Select all text so typing replaces it
        self.selectAll()

    def mousePressEvent(self, event):
        # Select all text when clicked (whether already focused or not)
        super().mousePressEvent(event)
        self.selectAll()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        text = self.text().strip()

        # Handle '--' display for zero
        if text == "--" or not text:
            if self.show_dash_for_zero:
                self.setText("--")
            else:
                formatted = "0"
                self.setText(f"{self.prefix}{formatted}" if self.prefix else formatted)
        else:
            # Remove prefix for validation
            if self.prefix and text.startswith(self.prefix):
                text = text.replace(self.prefix, "").strip()

            try:
                self.setValue(float(text))
            except ValueError:
                if self.show_dash_for_zero:
                    self.setText("--")
                else:
                    self.setText(f"{self.prefix}0" if self.prefix else "0")


class TransactionLogTable(QTableWidget):
    """
    Editable transaction log table (left side).
    Inline editing with date picker and dropdown.
    """

    # Signals
    transaction_added = Signal(dict)           # Emitted when row added
    transaction_modified = Signal(str, dict)   # (transaction_id, updated_transaction)
    transaction_deleted = Signal(str)          # (transaction_id)

    # Columns
    COLUMNS = [
        "Date",                # col 0 - DateInputWidget
        "Ticker",              # col 1 - AutoSelectLineEdit
        "Quantity",            # col 2 - ValidatedNumericLineEdit
        "Execution Price",     # col 3 - ValidatedNumericLineEdit
        "Fees",                # col 4 - ValidatedNumericLineEdit
        "Type",                # col 5 - NoScrollComboBox (Buy/Sell)
        "Daily Closing Price", # col 6 - Read-only (historical close on tx date)
        "Live Price",          # col 7 - Read-only (last daily close)
        "Principal",           # col 8 - Read-only (calculated)
        "Market Value"         # col 9 - Read-only (calculated)
    ]

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager

        # UUID-based transaction storage
        self._transactions_by_id: Dict[str, Dict[str, Any]] = {}  # Map transaction_id -> transaction_dict
        self._row_to_id: Dict[int, str] = {}  # Map row_index -> transaction_id

        # Legacy field for backwards compatibility (will be phased out)
        self._transactions = {}  # Map row_index -> transaction_dict

        self._current_prices: Dict[str, float] = {}  # Map ticker -> current_price
        self._historical_prices: Dict[str, Dict[str, float]] = {}  # Map ticker -> {date -> close_price}

        # Track original values for existing rows (for revert on invalid)
        # Map transaction_id -> {"ticker": str, "date": str}
        self._original_values: Dict[str, Dict[str, str]] = {}

        # Focus tracking for auto-delete
        self._current_editing_row: Optional[int] = None
        self._row_widgets_map: Dict[int, List[QWidget]] = {}
        self._skip_focus_validation: bool = False  # Prevent double validation dialogs

        # Highlight editable fields setting (default True)
        self._highlight_editable = True

        # Custom sorting state (blank row always stays at top)
        self._current_sort_column: int = -1
        self._current_sort_order: Qt.SortOrder = Qt.AscendingOrder

        # FREE CASH summary row tracking (pinned at row 1, below blank row)
        self._free_cash_row_id = "FREE_CASH_SUMMARY"

        self._setup_table()
        self._apply_theme()

        # Connect theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_table(self):
        """Configure table structure."""
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # Set header alignment to left
        header = self.horizontalHeader()
        for col in range(len(self.COLUMNS)):
            item = self.horizontalHeaderItem(col)
            if item:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Set column resize modes and widths
        self._reset_column_widths()

        # Table properties - fixed row heights
        v_header = self.verticalHeader()
        v_header.setVisible(True)  # Show row numbers
        v_header.setDefaultSectionSize(48)  # Fixed row height
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Hide vertical scrollbar but keep scroll functionality
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Enable smooth pixel-based scrolling instead of item-based
        self.setVerticalScrollMode(QTableWidget.ScrollPerPixel)

        # Disable built-in sorting - we handle it manually to keep blank row pinned at top
        self.setSortingEnabled(False)

        # Connect header click for custom sorting
        header = self.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)

        # Set corner label
        self._set_corner_label("Transaction")

    def _reset_column_widths(self):
        """Reset column widths to fixed values. Called after table content changes."""
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # Date
        self.setColumnWidth(0, 200)
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Ticker
        self.setColumnWidth(1, 300)
        header.setSectionResizeMode(2, QHeaderView.Interactive)  # Quantity
        self.setColumnWidth(2, 125)
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Execution Price
        self.setColumnWidth(3, 175)
        header.setSectionResizeMode(4, QHeaderView.Interactive)  # Fees
        self.setColumnWidth(4, 125)
        header.setSectionResizeMode(5, QHeaderView.Interactive)  # Type
        self.setColumnWidth(5, 125)
        header.setSectionResizeMode(6, QHeaderView.Interactive)  # Daily Closing Price
        self.setColumnWidth(6, 175)
        header.setSectionResizeMode(7, QHeaderView.Interactive)  # Live Price
        self.setColumnWidth(7, 175)
        header.setSectionResizeMode(8, QHeaderView.Stretch)  # Principal
        header.setSectionResizeMode(9, QHeaderView.Stretch)  # Market Value

    def _set_corner_label(self, text: str):
        """Set text for table corner button."""
        corner_button = self.findChild(QAbstractButton)
        if corner_button:
            corner_button.setText(text)
            corner_button.setEnabled(False)

    def _get_transaction_for_row(self, row: int) -> Optional[Dict[str, Any]]:
        """
        Get transaction dict for row index using ID mapping.

        Args:
            row: Row index

        Returns:
            Transaction dict or None if not found
        """
        tx_id = self._row_to_id.get(row)
        if tx_id:
            return self._transactions_by_id.get(tx_id)
        return None

    def _rebuild_transaction_map(self):
        """Rebuild row→id mapping after row operations."""
        new_row_to_id = {}
        for row in range(self.rowCount()):
            # Extract ID from widgets
            tx = self._extract_transaction_from_row(row)
            if tx and "id" in tx:
                new_row_to_id[row] = tx["id"]
        self._row_to_id = new_row_to_id

    def _ensure_blank_row(self):
        """Ensure blank row exists at top of table. Create if missing."""
        from datetime import datetime

        # Check if blank row already exists
        if self.rowCount() > 0:
            first_row_tx = self._get_transaction_for_row(0)
            if first_row_tx and first_row_tx.get("is_blank"):
                return  # Blank row already exists

        # Create blank transaction
        blank_transaction = {
            "id": "BLANK_ROW",
            "is_blank": True,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ticker": "",
            "transaction_type": "Buy",
            "quantity": 0.0,
            "entry_price": 0.0,
            "fees": 0.0
        }

        # Shift existing row indices down (before inserting at row 0)
        # Build new mappings with shifted indices
        new_row_to_id = {}
        new_transactions = {}
        new_row_widgets_map = {}

        for old_row in range(self.rowCount()):
            new_row = old_row + 1  # Shift down by 1
            if old_row in self._row_to_id:
                new_row_to_id[new_row] = self._row_to_id[old_row]
            if old_row in self._transactions:
                new_transactions[new_row] = self._transactions[old_row]
            if old_row in self._row_widgets_map:
                new_row_widgets_map[new_row] = self._row_widgets_map[old_row]

        # Insert at top (row 0)
        self.setSortingEnabled(False)
        self.insertRow(0)
        self.setRowHeight(0, 48)  # Ensure consistent row height

        # Set blank vertical header for dummy row (excludes from row count display)
        blank_header = QTableWidgetItem("")
        self.setVerticalHeaderItem(0, blank_header)

        # Apply shifted mappings
        self._row_to_id = new_row_to_id
        self._transactions = new_transactions
        self._row_widgets_map = new_row_widgets_map

        # Store blank row at index 0
        self._transactions_by_id["BLANK_ROW"] = blank_transaction
        self._row_to_id[0] = "BLANK_ROW"
        self._transactions[0] = blank_transaction

        # Get current theme stylesheets
        widget_style = self._get_current_widget_stylesheet()
        combo_style = self._get_combo_stylesheet()

        # Create widgets for blank row
        # Date cell
        date_edit = DateInputWidget()
        date_edit._parent_table = self  # Pass reference for validation dialogs
        date_edit.setDate(QDate.fromString(blank_transaction["date"], "yyyy-MM-dd"))
        date_edit.setStyleSheet(widget_style)
        date_edit.date_changed.connect(self._on_widget_changed)
        self._set_widget_position(date_edit, 0, 0)
        date_container = self._wrap_widget_in_cell(date_edit)
        self.setCellWidget(0, 0, date_container)

        # Ticker cell - column 1
        ticker_edit = AutoSelectLineEdit(blank_transaction["ticker"])
        ticker_edit.setPlaceholderText("Enter ticker...")
        ticker_edit.setStyleSheet(widget_style)
        ticker_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(ticker_edit, 0, 1)
        ticker_container = self._wrap_widget_in_cell(ticker_edit)
        self.setCellWidget(0, 1, ticker_container)

        # Quantity cell - column 2
        qty_edit = ValidatedNumericLineEdit(min_value=0.0001, max_value=1000000, decimals=4, prefix="", show_dash_for_zero=True)
        qty_edit.setValue(blank_transaction["quantity"])
        qty_edit.setStyleSheet(widget_style)
        qty_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(qty_edit, 0, 2)
        qty_container = self._wrap_widget_in_cell(qty_edit)
        self.setCellWidget(0, 2, qty_container)

        # Execution Price cell - column 3
        price_edit = ValidatedNumericLineEdit(min_value=0, max_value=1000000, decimals=2, prefix="", show_dash_for_zero=True)
        price_edit.setValue(blank_transaction["entry_price"])
        price_edit.setStyleSheet(widget_style)
        price_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(price_edit, 0, 3)
        price_container = self._wrap_widget_in_cell(price_edit)
        self.setCellWidget(0, 3, price_container)

        # Fees cell - column 4
        fees_edit = ValidatedNumericLineEdit(min_value=0, max_value=10000, decimals=2, prefix="", show_dash_for_zero=True)
        fees_edit.setValue(blank_transaction["fees"])
        fees_edit.setStyleSheet(widget_style)
        fees_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(fees_edit, 0, 4)
        fees_container = self._wrap_widget_in_cell(fees_edit)
        self.setCellWidget(0, 4, fees_container)

        # Type cell - column 5
        type_combo = NoScrollComboBox()
        type_combo.addItems(["Buy", "Sell"])
        type_combo.setCurrentText(blank_transaction["transaction_type"])
        type_combo.currentTextChanged.connect(self._on_widget_changed)
        type_combo.setStyleSheet(combo_style)
        self._set_widget_position(type_combo, 0, 5)
        type_container = self._wrap_widget_in_cell(type_combo)
        self.setCellWidget(0, 5, type_container)

        # Daily Closing Price cell (read-only) - column 6
        daily_close_item = QTableWidgetItem("--")
        daily_close_item.setFlags(daily_close_item.flags() & ~Qt.ItemIsEditable)
        daily_close_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(0, 6, daily_close_item)

        # Live Price cell (read-only) - column 7
        live_price_item = QTableWidgetItem("--")
        live_price_item.setFlags(live_price_item.flags() & ~Qt.ItemIsEditable)
        live_price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(0, 7, live_price_item)

        # Principal cell (read-only) - column 8
        principal_item = QTableWidgetItem("--")
        principal_item.setFlags(principal_item.flags() & ~Qt.ItemIsEditable)
        principal_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(0, 8, principal_item)

        # Market Value cell (read-only) - column 9
        market_value_item = QTableWidgetItem("--")
        market_value_item.setFlags(market_value_item.flags() & ~Qt.ItemIsEditable)
        market_value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(0, 9, market_value_item)

        # Install focus watchers for auto-delete functionality
        self._install_focus_watcher(0)

        # Update row positions for all shifted rows (rows 1+)
        self._update_row_positions(1)

        self.setSortingEnabled(False)  # Keep sorting disabled for manual control

        # Ensure FREE CASH summary row exists after blank row
        self._ensure_free_cash_summary_row()

    def _ensure_free_cash_summary_row(self):
        """
        Ensure FREE CASH summary row exists at index 1 (below blank row).
        Creates if missing, updates values if exists.
        """
        # Check if FREE CASH summary already exists anywhere in the table
        if self._free_cash_row_id in self._transactions_by_id:
            # Summary row exists - find its actual row position by scanning the table
            # (row mappings may be stale after row insert/remove operations)
            actual_row = None
            for row in range(self.rowCount()):
                # Check if this row has "FREE CASH" as ticker in column 1
                ticker_item = self.item(row, 1)
                if ticker_item and ticker_item.text() == "FREE CASH":
                    # Also verify it's the summary row by checking if column 0 has no widget
                    if self.cellWidget(row, 0) is None:
                        actual_row = row
                        break

            if actual_row is not None:
                # Update the mapping to the correct row
                # First remove any old mapping to this row ID
                for r in list(self._row_to_id.keys()):
                    if self._row_to_id[r] == self._free_cash_row_id:
                        del self._row_to_id[r]
                        if r in self._transactions:
                            del self._transactions[r]
                        break
                # Set correct mapping
                self._row_to_id[actual_row] = self._free_cash_row_id
                self._transactions[actual_row] = self._transactions_by_id[self._free_cash_row_id]

            # Now update values
            self._update_free_cash_summary_row()
            return

        # Need to insert FREE CASH summary row at index 1
        # First shift all existing rows down (except blank row at 0)
        new_row_to_id = {0: self._row_to_id.get(0)}  # Keep blank row mapping
        new_transactions = {0: self._transactions.get(0)}  # Keep blank row data
        new_row_widgets_map = {0: self._row_widgets_map.get(0)} if 0 in self._row_widgets_map else {}

        for old_row in range(1, self.rowCount()):
            new_row = old_row + 1  # Shift down by 1
            if old_row in self._row_to_id:
                new_row_to_id[new_row] = self._row_to_id[old_row]
            if old_row in self._transactions:
                new_transactions[new_row] = self._transactions[old_row]
            if old_row in self._row_widgets_map:
                new_row_widgets_map[new_row] = self._row_widgets_map[old_row]

        # Insert row at index 1
        self.insertRow(1)
        self.setRowHeight(1, 48)

        # Set blank vertical header (no row number)
        blank_header = QTableWidgetItem("")
        self.setVerticalHeaderItem(1, blank_header)

        # Apply shifted mappings
        self._row_to_id = new_row_to_id
        self._transactions = new_transactions
        self._row_widgets_map = new_row_widgets_map

        # Create FREE CASH summary transaction entry
        free_cash_summary = {
            "id": self._free_cash_row_id,
            "is_free_cash_summary": True,
            "date": "",
            "ticker": "FREE CASH",
            "transaction_type": "",
            "quantity": 0.0,
            "entry_price": 0.0,
            "fees": 0.0
        }

        # Store FREE CASH summary
        self._transactions_by_id[self._free_cash_row_id] = free_cash_summary
        self._row_to_id[1] = self._free_cash_row_id
        self._transactions[1] = free_cash_summary

        # Create read-only cells (no editable widgets, no highlight)
        # Date cell (empty)
        date_item = QTableWidgetItem("")
        date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
        date_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 0, date_item)

        # Ticker cell ("FREE CASH")
        ticker_item = QTableWidgetItem("FREE CASH")
        ticker_item.setFlags(ticker_item.flags() & ~Qt.ItemIsEditable)
        ticker_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 1, ticker_item)

        # Quantity cell (calculated)
        qty_item = QTableWidgetItem("--")
        qty_item.setFlags(qty_item.flags() & ~Qt.ItemIsEditable)
        qty_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 2, qty_item)

        # Execution Price cell (empty)
        price_item = QTableWidgetItem("")
        price_item.setFlags(price_item.flags() & ~Qt.ItemIsEditable)
        price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 3, price_item)

        # Fees cell (empty)
        fees_item = QTableWidgetItem("")
        fees_item.setFlags(fees_item.flags() & ~Qt.ItemIsEditable)
        fees_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 4, fees_item)

        # Type cell (empty)
        type_item = QTableWidgetItem("")
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        type_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 5, type_item)

        # Daily Closing Price cell (empty)
        daily_item = QTableWidgetItem("")
        daily_item.setFlags(daily_item.flags() & ~Qt.ItemIsEditable)
        daily_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 6, daily_item)

        # Live Price cell (empty)
        live_item = QTableWidgetItem("")
        live_item.setFlags(live_item.flags() & ~Qt.ItemIsEditable)
        live_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 7, live_item)

        # Principal cell (calculated)
        principal_item = QTableWidgetItem("--")
        principal_item.setFlags(principal_item.flags() & ~Qt.ItemIsEditable)
        principal_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 8, principal_item)

        # Market Value cell (calculated)
        mv_item = QTableWidgetItem("--")
        mv_item.setFlags(mv_item.flags() & ~Qt.ItemIsEditable)
        mv_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(1, 9, mv_item)

        # Update row positions for shifted rows (rows 2+)
        self._update_row_positions(2)

        # Update calculated values
        self._update_free_cash_summary_row()

    def _update_free_cash_summary_row(self):
        """Update FREE CASH summary row with calculated values."""
        # Find the FREE CASH summary row by scanning the table
        # (don't rely on _row_to_id which can be stale after row operations)
        row = None
        for r in range(self.rowCount()):
            # Check if this row has "FREE CASH" as ticker in column 1 (QTableWidgetItem, not widget)
            ticker_item = self.item(r, 1)
            if ticker_item and ticker_item.text() == "FREE CASH":
                # Verify it's the summary row by checking if column 0 has no widget (date widget)
                if self.cellWidget(r, 0) is None:
                    row = r
                    break

        if row is None:
            return  # Summary row doesn't exist yet

        # Get all real transactions (excluding blank and summary rows)
        transactions = self.get_all_transactions()

        # Calculate summary values
        summary = PortfolioService.calculate_free_cash_summary(transactions)

        # Update Quantity (col 2)
        qty_item = self.item(row, 2)
        if qty_item:
            qty = summary["quantity"]
            if qty != 0:
                qty_item.setText(f"${qty:,.2f}")
            else:
                qty_item.setText("--")

        # Update Principal (col 8)
        principal_item = self.item(row, 8)
        if principal_item:
            principal = summary["principal"]
            if principal < 0:
                principal_item.setText(f"-${abs(principal):,.2f}")
            elif principal > 0:
                principal_item.setText(f"${principal:,.2f}")
            else:
                principal_item.setText("--")

        # Update Market Value (col 9)
        mv_item = self.item(row, 9)
        if mv_item:
            mv = summary["market_value"]
            if mv != 0:
                mv_item.setText(f"${mv:,.2f}")
            else:
                mv_item.setText("--")

    def _is_transaction_complete(self, transaction: Dict[str, Any]) -> bool:
        """
        Check if transaction has all required fields filled.

        Args:
            transaction: Transaction dict

        Returns:
            True if ticker, qty > 0, and entry_price >= 0 are all filled
        """
        ticker = transaction.get("ticker", "").strip()
        quantity = transaction.get("quantity", 0.0)
        entry_price = transaction.get("entry_price", 0.0)

        return (
            ticker != "" and
            quantity > 0 and
            entry_price >= 0  # Allow 0 for gifts
        )

    def _transition_blank_to_real(self, row: int, transaction: Dict[str, Any]):
        """
        Convert blank row to real transaction and create new blank.

        Args:
            row: Row index of blank row
            transaction: Updated transaction data
        """
        import uuid

        # Assign new UUID
        new_id = str(uuid.uuid4())
        transaction["id"] = new_id
        transaction["is_blank"] = False
        transaction["ticker"] = transaction["ticker"].upper().strip()

        # For FREE CASH ticker, auto-set execution price to $1.00
        if transaction["ticker"] == PortfolioService.FREE_CASH_TICKER:
            transaction["entry_price"] = 1.0

        # Remove old blank entry from storage
        if "BLANK_ROW" in self._transactions_by_id:
            del self._transactions_by_id["BLANK_ROW"]
        if row in self._row_to_id:
            del self._row_to_id[row]
        if row in self._transactions:
            del self._transactions[row]
        if row in self._row_widgets_map:
            del self._row_widgets_map[row]

        # Remove the blank row from the table
        self.removeRow(row)

        # Rebuild mappings after row removal
        self._rebuild_transaction_map()

        # Create new blank row at top (also ensures FREE CASH summary at row 1)
        self._ensure_blank_row()

        # Add the new transaction at the end (after blank and FREE CASH summary)
        self.add_transaction_row(transaction)

        # Emit signal
        self.transaction_added.emit(transaction)

        # Update FREE CASH summary row
        self._update_free_cash_summary_row()

    def add_transaction_row(self, transaction: Dict[str, Any]) -> int:
        """
        Add a new transaction row.

        Args:
            transaction: Transaction dict

        Returns:
            Row index
        """
        # Disable sorting while adding row
        self.setSortingEnabled(False)

        row = self.rowCount()
        self.insertRow(row)
        self.setRowHeight(row, 48)  # Ensure consistent row height

        # Set row label (row number excludes blank row at 0 and FREE CASH summary at 1)
        # Row 2 = label "1", Row 3 = label "2", etc.
        row_header = QTableWidgetItem(str(row - 1))
        self.setVerticalHeaderItem(row, row_header)

        # Store transaction in UUID-based storage
        tx_id = transaction["id"]
        self._transactions_by_id[tx_id] = transaction
        self._row_to_id[row] = tx_id

        # Also store in legacy dict for backwards compatibility
        self._transactions[row] = transaction

        # Store original values for revert on invalid edit
        self._original_values[tx_id] = {
            "ticker": transaction.get("ticker", ""),
            "date": transaction.get("date", "")
        }

        # Get current theme stylesheets
        widget_style = self._get_current_widget_stylesheet()
        combo_style = self._get_combo_stylesheet()

        # Date cell - column 0
        date_edit = DateInputWidget()
        date_edit._parent_table = self  # Pass reference for validation dialogs
        date_edit.setDate(QDate.fromString(transaction["date"], "yyyy-MM-dd"))
        date_edit.setStyleSheet(widget_style)
        date_edit.date_changed.connect(self._on_widget_changed)
        self._set_widget_position(date_edit, row, 0)
        date_container = self._wrap_widget_in_cell(date_edit)
        self.setCellWidget(row, 0, date_container)

        # Ticker cell - column 1
        ticker_edit = AutoSelectLineEdit(transaction["ticker"])
        ticker_edit.setStyleSheet(widget_style)
        ticker_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(ticker_edit, row, 1)
        ticker_container = self._wrap_widget_in_cell(ticker_edit)
        self.setCellWidget(row, 1, ticker_container)

        # Quantity cell - column 2
        qty_edit = ValidatedNumericLineEdit(min_value=0.0001, max_value=1000000, decimals=4, prefix="", show_dash_for_zero=True)
        qty_edit.setValue(transaction["quantity"])
        qty_edit.setStyleSheet(widget_style)
        qty_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(qty_edit, row, 2)
        qty_container = self._wrap_widget_in_cell(qty_edit)
        self.setCellWidget(row, 2, qty_container)

        # Execution Price cell - column 3
        price_edit = ValidatedNumericLineEdit(min_value=0, max_value=1000000, decimals=2, prefix="", show_dash_for_zero=True)
        price_edit.setValue(transaction["entry_price"])
        price_edit.setStyleSheet(widget_style)
        price_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(price_edit, row, 3)
        price_container = self._wrap_widget_in_cell(price_edit)
        self.setCellWidget(row, 3, price_container)

        # Fees cell - column 4
        fees_edit = ValidatedNumericLineEdit(min_value=0, max_value=10000, decimals=2, prefix="", show_dash_for_zero=True)
        fees_edit.setValue(transaction["fees"])
        fees_edit.setStyleSheet(widget_style)
        fees_edit.textChanged.connect(self._on_widget_changed)
        self._set_widget_position(fees_edit, row, 4)
        fees_container = self._wrap_widget_in_cell(fees_edit)
        self.setCellWidget(row, 4, fees_container)

        # Type cell - column 5
        type_combo = NoScrollComboBox()
        type_combo.addItems(["Buy", "Sell"])
        type_combo.setCurrentText(transaction["transaction_type"])
        type_combo.currentTextChanged.connect(self._on_widget_changed)
        type_combo.setStyleSheet(combo_style)
        self._set_widget_position(type_combo, row, 5)
        type_container = self._wrap_widget_in_cell(type_combo)
        self.setCellWidget(row, 5, type_container)

        # Daily Closing Price cell (read-only) - column 6
        daily_close_item = QTableWidgetItem("--")
        daily_close_item.setFlags(daily_close_item.flags() & ~Qt.ItemIsEditable)
        daily_close_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 6, daily_close_item)

        # Live Price cell (read-only) - column 7
        live_price_item = QTableWidgetItem("--")
        live_price_item.setFlags(live_price_item.flags() & ~Qt.ItemIsEditable)
        live_price_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 7, live_price_item)

        # Principal cell (read-only) - column 8
        principal_item = QTableWidgetItem("--")
        principal_item.setFlags(principal_item.flags() & ~Qt.ItemIsEditable)
        principal_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 8, principal_item)

        # Market Value cell (read-only) - column 9
        market_value_item = QTableWidgetItem("--")
        market_value_item.setFlags(market_value_item.flags() & ~Qt.ItemIsEditable)
        market_value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setItem(row, 9, market_value_item)

        # Install focus watchers for auto-delete functionality
        self._install_focus_watcher(row)

        # Update FREE CASH summary if this is a FREE CASH transaction
        if transaction.get("ticker", "").upper() == PortfolioService.FREE_CASH_TICKER:
            self._update_free_cash_summary_row()

        return row

    def _on_cell_changed(self, row: int, col: int):
        """Handle cell value change."""
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        # Extract updated values
        updated = self._extract_transaction_from_row(row)
        if not updated:
            return

        # Check if this is the blank row
        if transaction.get("is_blank"):
            # Just update stored values without transitioning
            # Transition will happen on focus loss or Enter key to avoid lag while typing
            self._transactions_by_id["BLANK_ROW"].update(updated)
            self._transactions[row] = updated
            return

        # Normal transaction modification (not blank row)
        transaction_id = transaction["id"]

        # Always update stored transaction (even if invalid)
        # This allows focus loss detection to see empty tickers and delete the row
        self._transactions_by_id[transaction_id] = updated
        self._transactions[row] = updated

        # DON'T fetch prices here - that happens on focus loss only
        # This prevents lag when typing/deleting ticker symbols

    def _extract_transaction_from_row(self, row: int) -> Dict[str, Any]:
        """
        Extract transaction data from row widgets.

        Args:
            row: Row index

        Returns:
            Transaction dict or None if extraction fails
        """
        if row not in self._transactions:
            return None

        # Get existing transaction to preserve flags like is_blank
        existing_transaction = self._transactions[row]
        transaction_id = existing_transaction["id"]

        try:
            # Get inner widgets from cells (unwrap containers)
            date_edit = self._get_inner_widget(row, 0)
            ticker_edit = self._get_inner_widget(row, 1)
            qty_spin = self._get_inner_widget(row, 2)
            price_spin = self._get_inner_widget(row, 3)
            fees_spin = self._get_inner_widget(row, 4)
            type_combo = self._get_inner_widget(row, 5)
            # Columns 6-9 are read-only items, not widgets

            if not all([date_edit, ticker_edit, type_combo, qty_spin, price_spin, fees_spin]):
                return None

            extracted = {
                "id": transaction_id,
                "date": date_edit.date().toString("yyyy-MM-dd"),
                "ticker": ticker_edit.text().strip().upper(),
                "transaction_type": type_combo.currentText(),
                "quantity": qty_spin.value(),
                "entry_price": price_spin.value(),
                "fees": fees_spin.value()
            }

            # Preserve is_blank flag if it exists
            if "is_blank" in existing_transaction:
                extracted["is_blank"] = existing_transaction["is_blank"]

            return extracted
        except Exception as e:
            print(f"Error extracting transaction from row {row}: {e}")
            return None

    def _update_calculated_cells(self, row: int):
        """
        Update calculated cells: Daily Closing Price, Live Price, Principal, Market Value.

        Args:
            row: Row index
        """
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        # Skip FREE CASH summary row (it's handled separately)
        if transaction.get("is_free_cash_summary"):
            return

        ticker = transaction.get("ticker", "")
        tx_date = transaction.get("date", "")
        quantity = transaction.get("quantity", 0.0)

        # Check if this is a FREE CASH transaction
        is_free_cash = ticker.upper() == PortfolioService.FREE_CASH_TICKER

        # --- Daily Closing Price (col 6) ---
        item_6 = self.item(row, 6)
        if item_6:
            if is_free_cash:
                # FREE CASH: show blank (price is always $1, redundant to display)
                item_6.setText("")
            elif ticker and tx_date and ticker in self._historical_prices:
                daily_close = self._historical_prices[ticker].get(tx_date)
                if daily_close is not None:
                    item_6.setText(f"${daily_close:,.2f}")
                else:
                    item_6.setText("--")
            else:
                item_6.setText("--")

        # --- Live Price (col 7) ---
        item_7 = self.item(row, 7)
        if item_7:
            if is_free_cash:
                # FREE CASH: show blank (price is always $1, redundant to display)
                item_7.setText("")
            else:
                live_price = self._current_prices.get(ticker)
                if live_price is not None:
                    item_7.setText(f"${live_price:,.2f}")
                else:
                    item_7.setText("--")

        # --- Principal (col 8) ---
        item_8 = self.item(row, 8)
        if item_8:
            if is_free_cash:
                # FREE CASH principal: qty - fees for Buy, -(qty + fees) for Sell
                tx_type = transaction.get("transaction_type", "Buy")
                fees = transaction.get("fees", 0.0)
                if tx_type == "Buy":
                    principal = quantity - fees
                else:
                    principal = -(quantity + fees)
            else:
                principal = PortfolioService.calculate_principal(transaction)

            if principal != 0:
                # Format with sign: negative for buys, positive for sells
                if principal < 0:
                    item_8.setText(f"-${abs(principal):,.2f}")
                else:
                    item_8.setText(f"${principal:,.2f}")
            else:
                item_8.setText("--")

        # --- Market Value (col 9) ---
        item_9 = self.item(row, 9)
        if item_9:
            if is_free_cash:
                # FREE CASH: market value = quantity (since price is $1)
                if quantity > 0:
                    item_9.setText(f"${quantity:,.2f}")
                else:
                    item_9.setText("--")
            else:
                live_price = self._current_prices.get(ticker)
                if live_price is not None and quantity > 0:
                    market_value = live_price * quantity
                    item_9.setText(f"${market_value:,.2f}")
                else:
                    item_9.setText("--")

    def update_current_prices(self, prices: Dict[str, float]):
        """
        Update current prices and recalculate all rows.

        Args:
            prices: Dict mapping ticker -> price
        """
        self._current_prices = prices
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

    def update_historical_prices(self, historical_prices: Dict[str, Dict[str, float]]):
        """
        Update historical prices cache and recalculate all rows.

        Args:
            historical_prices: Dict mapping ticker -> {date -> close_price}
        """
        self._historical_prices = historical_prices
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

    def fetch_historical_prices_batch(self):
        """
        Fetch historical closing prices for all transactions in batch.
        Called on portfolio load and when transactions change.
        Only fetches prices for ticker/date pairs not already cached.
        """
        from typing import List, Tuple

        # Collect all ticker/date pairs that need fetching
        ticker_dates_to_fetch: List[Tuple[str, str]] = []
        for row in range(self.rowCount()):
            tx = self._get_transaction_for_row(row)
            if tx and not tx.get("is_blank"):
                ticker = tx.get("ticker", "")
                tx_date = tx.get("date", "")
                if ticker and tx_date:
                    # Only fetch if not already cached
                    if ticker not in self._historical_prices or tx_date not in self._historical_prices.get(ticker, {}):
                        ticker_dates_to_fetch.append((ticker, tx_date))

        # Fetch only new ticker/date pairs
        if ticker_dates_to_fetch:
            new_prices = PortfolioService.fetch_historical_closes_batch(ticker_dates_to_fetch)
            # Merge into existing cache
            for ticker, dates in new_prices.items():
                if ticker not in self._historical_prices:
                    self._historical_prices[ticker] = {}
                self._historical_prices[ticker].update(dates)

        # Update all calculated cells
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """
        Get all transactions from table (excluding blank row and FREE CASH summary).

        Returns:
            List of transaction dicts
        """
        transactions = []
        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            # Filter out blank row and FREE CASH summary row
            if tx and not tx.get("is_blank") and not tx.get("is_free_cash_summary"):
                transactions.append(tx)
        return transactions

    def clear_all_transactions(self):
        """Clear all transactions from table."""
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()  # Clear legacy storage too
        self._current_prices.clear()  # Clear current prices cache
        self._historical_prices.clear()  # Clear historical prices cache
        self._original_values.clear()  # Clear original values tracking
        self._reset_column_widths()  # Ensure consistent column widths

    def delete_selected_rows(self):
        """Delete selected rows and emit signals."""
        selected_rows = sorted(set(idx.row() for idx in self.selectedIndexes()), reverse=True)

        for row in selected_rows:
            # Get transaction using UUID-based lookup
            transaction = self._get_transaction_for_row(row)
            if transaction:
                transaction_id = transaction["id"]

                # Remove from UUID-based storage
                if transaction_id in self._transactions_by_id:
                    del self._transactions_by_id[transaction_id]

                # Remove from original values tracking
                if transaction_id in self._original_values:
                    del self._original_values[transaction_id]

                # Remove from row mapping
                if row in self._row_to_id:
                    del self._row_to_id[row]

                # Remove from legacy storage
                if row in self._transactions:
                    del self._transactions[row]

                # Remove row from table
                self.removeRow(row)

                # Emit signal
                self.transaction_deleted.emit(transaction_id)

        # Rebuild transaction map (row indices shifted after deletion)
        self._rebuild_transaction_map()

        # Also rebuild legacy map
        new_transactions = {}
        for row in range(self.rowCount()):
            tx = self._get_transaction_for_row(row)
            if tx:
                new_transactions[row] = tx
        self._transactions = new_transactions

        # Update all stored row positions after deletion
        self._update_row_positions(0)

        # Update FREE CASH summary row
        self._update_free_cash_summary_row()

    def _find_row_for_widget(self, widget: QWidget) -> Optional[int]:
        """
        Find the row index for a given widget using stored property (O(1) lookup).

        Args:
            widget: The widget to find

        Returns:
            Row index or None if not found
        """
        row = widget.property("_table_row")
        if row is not None:
            return row
        # Fallback to slow search (should not be needed)
        for r, widgets in self._row_widgets_map.items():
            if widget in widgets:
                return r
        return None

    def _find_cell_for_widget(self, widget: QWidget) -> tuple[Optional[int], Optional[int]]:
        """
        Find the (row, col) for a given widget using stored properties (O(1) lookup).

        Args:
            widget: The widget to find

        Returns:
            Tuple of (row, col) or (None, None) if not found
        """
        row = widget.property("_table_row")
        col = widget.property("_table_col")
        if row is not None and col is not None:
            return (row, col)
        return (None, None)

    def _set_widget_position(self, widget: QWidget, row: int, col: int):
        """
        Store row/col position on widget for O(1) lookup.

        Args:
            widget: The widget to tag
            row: Row index
            col: Column index
        """
        widget.setProperty("_table_row", row)
        widget.setProperty("_table_col", col)

    def _update_row_positions(self, start_row: int):
        """
        Update stored row positions for all widgets from start_row onwards.
        Called after row insertion/deletion to keep positions in sync.

        Args:
            start_row: First row to update
        """
        for row in range(start_row, self.rowCount()):
            for col in range(6):  # Columns 0-5 have widgets
                widget = self.cellWidget(row, col)
                if widget:
                    widget.setProperty("_table_row", row)

    def _on_widget_changed(self):
        """
        Generic handler for widget value changes.
        Uses sender() to find which widget changed, then looks up its position.
        """
        widget = self.sender()
        if not widget:
            return

        row, col = self._find_cell_for_widget(widget)
        if row is not None and col is not None:
            self._on_cell_changed(row, col)

    def _install_focus_watcher(self, row: int):
        """
        Install event filters on all widgets in a row for focus tracking.

        Args:
            row: Row index to install watchers on
        """
        widgets = []

        # Install event filters on all editable columns (0-5)
        for col in range(6):
            container = self.cellWidget(row, col)
            if container:
                # Get the inner widget (the actual editable widget, not the container)
                inner_widget = container.property("_inner_widget")
                if inner_widget:
                    inner_widget.installEventFilter(self)
                    widgets.append(inner_widget)
                else:
                    # Fallback if no inner widget (shouldn't happen)
                    container.installEventFilter(self)
                    widgets.append(container)

        # Store widget references for this row
        self._row_widgets_map[row] = widgets

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """
        Handle focus and key events on row widgets.

        Args:
            obj: The widget that received the event
            event: The event

        Returns:
            False to allow normal event processing
        """
        event_type = event.type()

        if event_type == QEvent.FocusIn:
            # Focus entered a widget - find which row
            row = self._find_row_for_widget(obj)
            if row is not None:
                self._current_editing_row = row
                # Select this row visually (sync with table selection)
                self.selectRow(row)

        elif event_type == QEvent.FocusOut:
            # Focus left a widget - defer check to see if it left the row
            QTimer.singleShot(0, self._check_row_focus_loss)

        elif event_type == QEvent.KeyPress:
            # Handle Enter key on any field
            from PySide6.QtGui import QKeyEvent
            key_event = event
            if isinstance(key_event, QKeyEvent):
                key = key_event.key()
                modifiers = key_event.modifiers()

                # Check for Enter/Return key (but NOT Shift+Enter - let that through for newlines)
                if key in (Qt.Key_Return, Qt.Key_Enter) and not (modifiers & Qt.ShiftModifier):
                    # Find which row this widget belongs to
                    row = self._find_row_for_widget(obj)
                    if row is not None:
                        # Get transaction
                        transaction = self._get_transaction_for_row(row)

                        # Check if blank row and complete - validate and transition if so
                        if transaction and transaction.get("is_blank"):
                            if self._is_transaction_complete(transaction):
                                # Validate ticker before transitioning
                                ticker = transaction.get("ticker", "").strip().upper()
                                tx_date = transaction.get("date", "")

                                # Validate ticker exists in Yahoo Finance
                                is_valid_ticker, ticker_error = PortfolioService.is_valid_ticker(ticker)
                                if not is_valid_ticker:
                                    self._skip_focus_validation = True  # Prevent double dialog
                                    CustomMessageBox.warning(
                                        self.theme_manager,
                                        self,
                                        "Invalid Ticker",
                                        ticker_error
                                    )
                                    return True  # Consume event, don't transition

                                # Validate trading day for stocks (non-crypto)
                                is_valid_day, day_error = PortfolioService.is_valid_trading_day(ticker, tx_date)
                                if not is_valid_day:
                                    self._skip_focus_validation = True  # Prevent double dialog
                                    CustomMessageBox.warning(
                                        self.theme_manager,
                                        self,
                                        "Invalid Trading Day",
                                        day_error
                                    )
                                    return True  # Consume event, don't transition

                                self._transition_blank_to_real(row, transaction)
                                # Move focus to new blank row's ticker field (row 0, col 1)
                                new_blank_ticker = self.cellWidget(0, 1)
                                if new_blank_ticker:
                                    new_blank_ticker.setFocus()
                                return True  # Consume event

                        # Handle normal rows (not blank)
                        if transaction and not transaction.get("is_blank"):
                            ticker = transaction.get("ticker", "").strip()
                            quantity = transaction.get("quantity", 0.0)
                            tx_date = transaction.get("date", "")
                            transaction_id = transaction.get("id")

                            if not ticker or quantity == 0.0:
                                # Empty ticker or zero quantity - delete row
                                self._delete_empty_row(row)
                                return True  # Consume event
                            else:
                                # Validate ticker and trading day
                                original = self._original_values.get(transaction_id, {})
                                original_ticker = original.get("ticker", "")
                                original_date = original.get("date", "")
                                ticker_upper = ticker.upper()

                                # Check if ticker changed
                                if ticker_upper != original_ticker.upper():
                                    is_valid_ticker, ticker_error = PortfolioService.is_valid_ticker(ticker_upper)
                                    if not is_valid_ticker:
                                        self._skip_focus_validation = True  # Prevent double dialog
                                        CustomMessageBox.warning(
                                            self.theme_manager,
                                            self,
                                            "Invalid Ticker",
                                            ticker_error
                                        )
                                        self._revert_ticker(row, original_ticker)
                                        return True  # Consume event

                                # Check if date or ticker changed
                                if tx_date != original_date or ticker_upper != original_ticker.upper():
                                    is_valid_day, day_error = PortfolioService.is_valid_trading_day(ticker_upper, tx_date)
                                    if not is_valid_day:
                                        self._skip_focus_validation = True  # Prevent double dialog
                                        CustomMessageBox.warning(
                                            self.theme_manager,
                                            self,
                                            "Invalid Trading Day",
                                            day_error
                                        )
                                        self._revert_date(row, original_date)
                                        return True  # Consume event

                                # Valid data - validate and fetch prices
                                is_valid, error = PortfolioService.validate_transaction(transaction)
                                if is_valid:
                                    # For FREE CASH ticker, auto-set execution price to $1.00
                                    if ticker_upper == PortfolioService.FREE_CASH_TICKER:
                                        transaction["entry_price"] = 1.0
                                        price_widget = self.cellWidget(row, 3)
                                        if price_widget:
                                            inner_widget = price_widget.findChild(ValidatedNumericLineEdit)
                                            if inner_widget:
                                                inner_widget.setValue(1.0)

                                    # Update original values
                                    if transaction_id:
                                        self._original_values[transaction_id] = {
                                            "ticker": ticker_upper,
                                            "date": tx_date
                                        }
                                    self._update_calculated_cells(row)
                                    if transaction_id:
                                        self.transaction_modified.emit(transaction_id, transaction)
                                    # Update FREE CASH summary row
                                    self._update_free_cash_summary_row()
                                # Clear selection and focus from the widget
                                self.clearSelection()
                                obj.clearFocus()  # Clear focus from the specific widget
                                return True  # Consume event

        return super().eventFilter(obj, event)

    def _check_row_focus_loss(self):
        """Check if focus has left the current editing row (deferred check)."""
        if self._current_editing_row is None:
            return

        # Get the currently focused widget
        focused_widget = QApplication.focusWidget()

        if not focused_widget:
            # Focus lost completely - trigger row focus lost
            self._on_row_focus_lost(self._current_editing_row)
            self._current_editing_row = None
            return

        # Check if focus is still in the same row
        new_row = self._find_row_for_widget(focused_widget)

        if new_row != self._current_editing_row:
            # Focus moved to different row - trigger row focus lost
            self._on_row_focus_lost(self._current_editing_row)
            self._current_editing_row = new_row

    def _on_row_focus_lost(self, row: int):
        """
        Handle when focus leaves a row.
        Auto-deletes empty rows (except blank row), or validates and fetches prices.
        Validates ticker existence and trading day for stocks.

        Args:
            row: Row index that lost focus
        """
        # Check if we should skip validation (already handled by Enter key)
        if self._skip_focus_validation:
            self._skip_focus_validation = False
            return

        # Get transaction for this row
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        # Check if this is blank row
        if transaction.get("is_blank"):
            # Check if it's complete, if so validate and transition to real
            if self._is_transaction_complete(transaction):
                # Validate ticker before transitioning
                ticker = transaction.get("ticker", "").strip().upper()
                tx_date = transaction.get("date", "")

                # Validate ticker exists in Yahoo Finance
                is_valid_ticker, ticker_error = PortfolioService.is_valid_ticker(ticker)
                if not is_valid_ticker:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Invalid Ticker",
                        ticker_error
                    )
                    # Don't transition - keep as blank row
                    return

                # Validate trading day for stocks (non-crypto)
                is_valid_day, day_error = PortfolioService.is_valid_trading_day(ticker, tx_date)
                if not is_valid_day:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Invalid Trading Day",
                        day_error
                    )
                    # Don't transition - keep as blank row
                    return

                self._transition_blank_to_real(row, transaction)
            return

        # Existing row - check if row should be deleted (ticker empty OR quantity is 0/blank)
        ticker = transaction.get("ticker", "").strip()
        quantity = transaction.get("quantity", 0.0)
        tx_date = transaction.get("date", "")
        transaction_id = transaction.get("id")

        if not ticker or quantity == 0.0:
            # Empty ticker or zero quantity - delete this row
            self._delete_empty_row(row)
        else:
            # Has ticker and quantity - validate ticker and date, then fetch prices
            original = self._original_values.get(transaction_id, {})
            original_ticker = original.get("ticker", "")
            original_date = original.get("date", "")

            ticker_upper = ticker.upper()

            # Check if ticker changed
            if ticker_upper != original_ticker.upper():
                # Validate new ticker
                is_valid_ticker, ticker_error = PortfolioService.is_valid_ticker(ticker_upper)
                if not is_valid_ticker:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Invalid Ticker",
                        ticker_error
                    )
                    # Revert to original ticker
                    self._revert_ticker(row, original_ticker)
                    return

            # Check if date changed or ticker changed (need to revalidate trading day)
            if tx_date != original_date or ticker_upper != original_ticker.upper():
                # Validate trading day for stocks
                is_valid_day, day_error = PortfolioService.is_valid_trading_day(ticker_upper, tx_date)
                if not is_valid_day:
                    CustomMessageBox.warning(
                        self.theme_manager,
                        self,
                        "Invalid Trading Day",
                        day_error
                    )
                    # Revert to original date
                    self._revert_date(row, original_date)
                    return

            # Validate transaction
            is_valid, error = PortfolioService.validate_transaction(transaction)
            if not is_valid:
                # Don't fetch prices for invalid transactions
                return

            # Update original values since validation passed
            if transaction_id:
                self._original_values[transaction_id] = {
                    "ticker": ticker_upper,
                    "date": tx_date
                }

            # Update calculated cells (fetch prices)
            self._update_calculated_cells(row)

            # Emit signal that transaction was modified
            if transaction_id:
                self.transaction_modified.emit(transaction_id, transaction)

            # Update FREE CASH summary row
            self._update_free_cash_summary_row()

    def _revert_ticker(self, row: int, original_ticker: str):
        """
        Revert ticker field to original value.

        Args:
            row: Row index
            original_ticker: Original ticker value to restore
        """
        ticker_widget = self._get_inner_widget(row, 1)
        if ticker_widget and isinstance(ticker_widget, QLineEdit):
            ticker_widget.blockSignals(True)
            ticker_widget.setText(original_ticker)
            ticker_widget.blockSignals(False)

        # Update stored transaction
        transaction = self._get_transaction_for_row(row)
        if transaction:
            transaction["ticker"] = original_ticker
            tx_id = transaction.get("id")
            if tx_id and tx_id in self._transactions_by_id:
                self._transactions_by_id[tx_id]["ticker"] = original_ticker

    def _revert_date(self, row: int, original_date: str):
        """
        Revert date field to original value.

        Args:
            row: Row index
            original_date: Original date value to restore (YYYY-MM-DD)
        """
        date_widget = self._get_inner_widget(row, 0)
        if date_widget and isinstance(date_widget, DateInputWidget):
            date_widget.blockSignals(True)
            date_widget.setDate(QDate.fromString(original_date, "yyyy-MM-dd"))
            date_widget.blockSignals(False)

        # Update stored transaction
        transaction = self._get_transaction_for_row(row)
        if transaction:
            transaction["date"] = original_date
            tx_id = transaction.get("id")
            if tx_id and tx_id in self._transactions_by_id:
                self._transactions_by_id[tx_id]["date"] = original_date

    def _delete_empty_row(self, row: int):
        """
        Delete a single empty row.

        Args:
            row: Row index to delete
        """
        # Get transaction
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        transaction_id = transaction["id"]

        # Remove from UUID-based storage
        if transaction_id in self._transactions_by_id:
            del self._transactions_by_id[transaction_id]

        # Remove from original values tracking
        if transaction_id in self._original_values:
            del self._original_values[transaction_id]

        # Remove row from table first (this shifts all rows below up by 1)
        self.removeRow(row)

        # Rebuild all mappings to account for shifted row indices
        new_row_to_id = {}
        new_transactions = {}
        new_row_widgets_map = {}

        for old_row in sorted(self._row_to_id.keys()):
            if old_row < row:
                # Rows above deleted row keep same index
                new_row_to_id[old_row] = self._row_to_id[old_row]
                if old_row in self._transactions:
                    new_transactions[old_row] = self._transactions[old_row]
                if old_row in self._row_widgets_map:
                    new_row_widgets_map[old_row] = self._row_widgets_map[old_row]
            elif old_row > row:
                # Rows below deleted row shift up by 1
                new_index = old_row - 1
                new_row_to_id[new_index] = self._row_to_id[old_row]
                if old_row in self._transactions:
                    new_transactions[new_index] = self._transactions[old_row]
                if old_row in self._row_widgets_map:
                    new_row_widgets_map[new_index] = self._row_widgets_map[old_row]
            # old_row == row is the deleted row, skip it

        self._row_to_id = new_row_to_id
        self._transactions = new_transactions
        self._row_widgets_map = new_row_widgets_map

        # Update stored row positions for all widgets from deleted row onwards
        self._update_row_positions(row)

        # Emit signal
        self.transaction_deleted.emit(transaction_id)

        # Update FREE CASH summary row
        self._update_free_cash_summary_row()

    def _on_header_clicked(self, column: int):
        """
        Handle column header click for custom sorting.
        Keeps blank row and FREE CASH summary row pinned at top while sorting transactions.

        Args:
            column: Column index that was clicked
        """
        # Collect all sortable transactions (exclude blank and FREE CASH summary)
        sortable_transactions = []
        blank_transaction = None

        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            if tx:
                if tx.get("is_blank"):
                    blank_transaction = tx
                elif tx.get("is_free_cash_summary"):
                    # Skip FREE CASH summary - it will be recreated
                    pass
                else:
                    sortable_transactions.append(tx)

        if not sortable_transactions:
            return

        # Toggle sort order if same column, otherwise default to ascending
        if column == self._current_sort_column:
            if self._current_sort_order == Qt.AscendingOrder:
                self._current_sort_order = Qt.DescendingOrder
            else:
                self._current_sort_order = Qt.AscendingOrder
        else:
            self._current_sort_column = column
            self._current_sort_order = Qt.AscendingOrder

        # Define sort key functions based on column
        # Columns 0-5: Editable fields stored in transaction dict
        # Columns 6-9: Calculated/read-only fields
        def get_sort_key(tx: Dict[str, Any]):
            ticker = tx.get("ticker", "")
            tx_date = tx.get("date", "")

            if column == 0:  # Date
                return tx_date
            elif column == 1:  # Ticker
                return ticker.lower()
            elif column == 2:  # Quantity
                return tx.get("quantity", 0.0)
            elif column == 3:  # Execution Price
                return tx.get("entry_price", 0.0)
            elif column == 4:  # Fees
                return tx.get("fees", 0.0)
            elif column == 5:  # Type
                return tx.get("transaction_type", "").lower()
            elif column == 6:  # Daily Closing Price
                if ticker and tx_date and ticker in self._historical_prices:
                    return self._historical_prices[ticker].get(tx_date, 0.0) or 0.0
                return 0.0
            elif column == 7:  # Live Price
                return self._current_prices.get(ticker, 0.0) or 0.0
            elif column == 8:  # Principal
                return PortfolioService.calculate_principal(tx)
            elif column == 9:  # Market Value
                live_price = self._current_prices.get(ticker, 0.0) or 0.0
                quantity = tx.get("quantity", 0.0)
                return live_price * quantity
            return 0

        reverse = self._current_sort_order == Qt.DescendingOrder

        # Sort the transactions
        sorted_transactions = sorted(sortable_transactions, key=get_sort_key, reverse=reverse)

        # Rebuild table
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()
        self._row_widgets_map.clear()

        # Add blank row first if it exists (pinned at top)
        # Note: _ensure_blank_row() also creates FREE CASH summary row at index 1
        if blank_transaction:
            self._ensure_blank_row()

        # Add sorted transactions (starting at row 2, after blank and FREE CASH summary)
        for tx in sorted_transactions:
            self.add_transaction_row(tx)

        # Update calculated cells
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

        # Update FREE CASH summary row after all transactions are added
        # (must be done after transactions are added, not before)
        self._update_free_cash_summary_row()

        # Reset column widths after rebuilding table
        self._reset_column_widths()

        # Update header sort indicator
        header = self.horizontalHeader()
        header.setSortIndicator(column, self._current_sort_order)

    def _sort_transactions(self):
        """
        Sort transactions: blank row at top, FREE CASH summary at row 1,
        completed transactions by date below.
        """
        # Get all sortable transactions (exclude blank and FREE CASH summary)
        sortable_transactions = []
        blank_transaction = None

        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            if tx:
                if tx.get("is_blank"):
                    blank_transaction = tx
                elif tx.get("is_free_cash_summary"):
                    # Skip FREE CASH summary - it will be recreated
                    pass
                else:
                    sortable_transactions.append(tx)

        # Sort transactions by date (oldest first)
        sortable_transactions.sort(key=lambda t: t.get("date", ""))

        # Rebuild table
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()
        self._row_widgets_map.clear()

        # Add blank row first if it exists (also creates FREE CASH summary at row 1)
        if blank_transaction:
            self._ensure_blank_row()

        # Add sorted transactions
        for tx in sortable_transactions:
            self.add_transaction_row(tx)

        # Update FREE CASH summary row after all transactions are added
        self._update_free_cash_summary_row()

        # Reset column widths after rebuilding table
        self._reset_column_widths()

    def _apply_theme(self):
        """Apply theme-specific styling."""
        theme = self.theme_manager.current_theme

        if theme == "light":
            stylesheet = self._get_light_stylesheet()
            widget_stylesheet = self._get_light_widget_stylesheet()
        elif theme == "bloomberg":
            stylesheet = self._get_bloomberg_stylesheet()
            widget_stylesheet = self._get_bloomberg_widget_stylesheet()
        else:
            stylesheet = self._get_dark_stylesheet()
            widget_stylesheet = self._get_dark_widget_stylesheet()

        self.setStyleSheet(stylesheet)

        # Apply styling to all editable cell widgets
        self._apply_widget_theme(widget_stylesheet)

    def _apply_widget_theme(self, widget_stylesheet: str):
        """Apply theme styling to all editable cell widgets."""
        bg_color = self._get_cell_background_color()
        combo_style = self._get_combo_stylesheet()

        for row in range(self.rowCount()):
            # Columns 0-5 have container widgets with inner widgets
            for col in range(6):
                container = self.cellWidget(row, col)
                if container:
                    # Update container background
                    container.setStyleSheet(f"background-color: {bg_color};")

                    # Update inner widget style
                    inner = container.property("_inner_widget")
                    if inner:
                        if col == 5:  # Combo box
                            inner.setStyleSheet(combo_style)
                        else:  # QLineEdit-based widgets
                            inner.setStyleSheet(widget_stylesheet)

    def _get_current_widget_stylesheet(self) -> str:
        """Get the current theme's widget stylesheet."""
        theme = self.theme_manager.current_theme
        if theme == "light":
            return self._get_light_widget_stylesheet()
        elif theme == "bloomberg":
            return self._get_bloomberg_widget_stylesheet()
        else:
            return self._get_dark_widget_stylesheet()

    def _get_cell_background_color(self) -> str:
        """Get the current theme's cell background color (or transparent if highlighting disabled)."""
        if not self._highlight_editable:
            return "transparent"

        theme = self.theme_manager.current_theme
        if theme == "light":
            return "#0066cc"
        elif theme == "bloomberg":
            return "#FF8000"
        else:
            return "#00d4ff"

    def set_highlight_editable(self, enabled: bool):
        """
        Enable or disable editable field highlighting.

        Args:
            enabled: True to show colored backgrounds on editable fields
        """
        self._highlight_editable = enabled
        # Re-apply theme to update all widget styles
        self._apply_theme()

    def _wrap_widget_in_cell(self, widget: QWidget) -> QWidget:
        """Wrap a widget in a container that fills the cell with themed background."""
        bg_color = self._get_cell_background_color()

        container = QWidget()
        container.setStyleSheet(f"background-color: {bg_color};")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)

        # Store reference to inner widget for later access
        container.setProperty("_inner_widget", widget)

        return container

    def _get_inner_widget(self, row: int, col: int) -> Optional[QWidget]:
        """Get the inner widget from a cell (unwraps container if needed)."""
        cell_widget = self.cellWidget(row, col)
        if cell_widget is None:
            return None

        # Check if it's a container with an inner widget
        inner = cell_widget.property("_inner_widget")
        if inner is not None:
            return inner

        # Otherwise return the cell widget directly
        return cell_widget

    def _get_dark_stylesheet(self) -> str:
        """Dark theme stylesheet."""
        return """
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #232323;
                color: #ffffff;
                gridline-color: #3d3d3d;
                border: 1px solid #3d3d3d;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 0px;
            }
            QTableWidget::item:selected {
                background-color: #00d4ff;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 8px;
                border: 1px solid #3d3d3d;
                font-weight: bold;
                font-size: 14px;
            }
            QTableCornerButton::section {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #3d3d3d;
                font-weight: bold;
                font-size: 13px;
                padding: 8px;
            }
        """

    def _get_light_stylesheet(self) -> str:
        """Light theme stylesheet."""
        return """
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f5f5f5;
                color: #000000;
                gridline-color: #cccccc;
                border: 1px solid #cccccc;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 0px;
            }
            QTableWidget::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #333333;
                padding: 8px;
                border: 1px solid #cccccc;
                font-weight: bold;
                font-size: 14px;
            }
            QTableCornerButton::section {
                background-color: #f5f5f5;
                color: #333333;
                border: 1px solid #cccccc;
                font-weight: bold;
                font-size: 13px;
                padding: 8px;
            }
        """

    def _get_bloomberg_stylesheet(self) -> str:
        """Bloomberg theme stylesheet."""
        return """
            QTableWidget {
                background-color: #000814;
                alternate-background-color: #0a0f1c;
                color: #e8e8e8;
                gridline-color: #1a2838;
                border: 1px solid #1a2838;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 0px;
            }
            QTableWidget::item:selected {
                background-color: #FF8000;
                color: #000000;
            }
            QHeaderView::section {
                background-color: #0d1420;
                color: #a8a8a8;
                padding: 8px;
                border: 1px solid #1a2838;
                font-weight: bold;
                font-size: 14px;
            }
            QTableCornerButton::section {
                background-color: #0d1420;
                color: #a8a8a8;
                border: 1px solid #1a2838;
                font-weight: bold;
                font-size: 13px;
                padding: 8px;
            }
        """

    def _get_dark_widget_stylesheet(self) -> str:
        """Dark theme stylesheet for editable cell widgets."""
        if not self._highlight_editable:
            return """
                QLineEdit {
                    background-color: transparent;
                    color: #ffffff;
                    border: none;
                    margin: 0px;
                    padding: 0px 8px;
                    font-size: 14px;
                }
            """
        return """
            QLineEdit {
                background-color: #00d4ff;
                color: #000000;
                border: none;
                margin: 0px;
                padding: 0px 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: #00e5ff;
            }
        """

    def _get_light_widget_stylesheet(self) -> str:
        """Light theme stylesheet for editable cell widgets."""
        if not self._highlight_editable:
            return """
                QLineEdit {
                    background-color: transparent;
                    color: #000000;
                    border: none;
                    margin: 0px;
                    padding: 0px 8px;
                    font-size: 14px;
                }
            """
        return """
            QLineEdit {
                background-color: #0066cc;
                color: #ffffff;
                border: none;
                margin: 0px;
                padding: 0px 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: #0077dd;
            }
        """

    def _get_bloomberg_widget_stylesheet(self) -> str:
        """Bloomberg theme stylesheet for editable cell widgets."""
        if not self._highlight_editable:
            return """
                QLineEdit {
                    background-color: transparent;
                    color: #e8e8e8;
                    border: none;
                    margin: 0px;
                    padding: 0px 8px;
                    font-size: 14px;
                }
            """
        return """
            QLineEdit {
                background-color: #FF8000;
                color: #000000;
                border: none;
                margin: 0px;
                padding: 0px 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: #FF9020;
            }
        """

    def _get_combo_stylesheet(self) -> str:
        """Get theme-aware stylesheet for combo box."""
        theme = self.theme_manager.current_theme

        if not self._highlight_editable:
            # Transparent combo styling when highlight is disabled
            if theme == "bloomberg":
                return """
                    QComboBox {
                        background-color: transparent;
                        color: #e8e8e8;
                        border: none;
                        padding: 4px 8px;
                        font-size: 14px;
                    }
                    QComboBox::drop-down { border: none; width: 0px; }
                    QComboBox QAbstractItemView {
                        background-color: #0d1420;
                        color: #e8e8e8;
                        selection-background-color: #FF8000;
                    }
                """
            elif theme == "light":
                return """
                    QComboBox {
                        background-color: transparent;
                        color: #000000;
                        border: none;
                        padding: 4px 8px;
                        font-size: 14px;
                    }
                    QComboBox::drop-down { border: none; width: 0px; }
                    QComboBox QAbstractItemView {
                        background-color: #ffffff;
                        color: #000000;
                        selection-background-color: #0066cc;
                    }
                """
            else:  # dark
                return """
                    QComboBox {
                        background-color: transparent;
                        color: #ffffff;
                        border: none;
                        padding: 4px 8px;
                        font-size: 14px;
                    }
                    QComboBox::drop-down { border: none; width: 0px; }
                    QComboBox QAbstractItemView {
                        background-color: #2d2d2d;
                        color: #ffffff;
                        selection-background-color: #00d4ff;
                    }
                """

        if theme == "bloomberg":
            return """
                QComboBox {
                    background-color: #FF8000;
                    color: #000000;
                    border: none;
                    padding: 4px 8px;
                    font-size: 14px;
                }
                QComboBox::drop-down { border: none; width: 0px; }
                QComboBox:focus { background-color: #FF9020; }
                QComboBox QAbstractItemView {
                    background-color: #FF8000;
                    color: #000000;
                    selection-background-color: #FFa040;
                }
            """
        elif theme == "light":
            return """
                QComboBox {
                    background-color: #0066cc;
                    color: #ffffff;
                    border: none;
                    padding: 4px 8px;
                    font-size: 14px;
                }
                QComboBox::drop-down { border: none; width: 0px; }
                QComboBox:focus { background-color: #0077dd; }
                QComboBox QAbstractItemView {
                    background-color: #0066cc;
                    color: #ffffff;
                    selection-background-color: #0088ee;
                }
            """
        else:  # dark
            return """
                QComboBox {
                    background-color: #00d4ff;
                    color: #000000;
                    border: none;
                    padding: 4px 8px;
                    font-size: 14px;
                }
                QComboBox::drop-down { border: none; width: 0px; }
                QComboBox:focus { background-color: #00e5ff; }
                QComboBox QAbstractItemView {
                    background-color: #00d4ff;
                    color: #000000;
                    selection-background-color: #40e0ff;
                }
            """
