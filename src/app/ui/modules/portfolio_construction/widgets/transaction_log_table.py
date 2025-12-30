"""Transaction Log Table Widget - Editable Transaction Table"""

from typing import Dict, List, Any, Optional
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QDoubleSpinBox, QAbstractButton, QWidget, QApplication
)
from PySide6.QtCore import Qt, Signal, QDate, QTimer, QEvent
from PySide6.QtGui import QDoubleValidator, QKeySequence

from app.core.theme_manager import ThemeManager
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
    """QLineEdit that auto-selects all text on focus or click."""

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
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

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
        "Date",              # QDateEdit
        "Ticker",            # QLineEdit
        "Type",              # QComboBox (Buy/Sell)
        "Quantity",          # QDoubleSpinBox
        "Transaction Price", # QDoubleSpinBox
        "Fees",              # QDoubleSpinBox
        "Market Value"       # Read-only label (calculated)
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

        # Focus tracking for auto-delete
        self._current_editing_row: Optional[int] = None
        self._row_widgets_map: Dict[int, List[QWidget]] = {}

        self._setup_table()
        self._apply_theme()

        # Connect theme changes
        self.theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_table(self):
        """Configure table structure."""
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # Column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Date
        self.setColumnWidth(0, 130)
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Ticker
        self.setColumnWidth(1, 110)
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Type
        self.setColumnWidth(2, 80)
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Quantity
        self.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.Interactive)  # Transaction Price
        self.setColumnWidth(4, 140)
        header.setSectionResizeMode(5, QHeaderView.Interactive)  # Fees
        self.setColumnWidth(5, 100)
        header.setSectionResizeMode(6, QHeaderView.Stretch)  # Market Value (stretches)

        # Table properties - fixed row heights
        v_header = self.verticalHeader()
        v_header.setVisible(True)  # Show row numbers
        v_header.setDefaultSectionSize(48)  # Fixed row height
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Enable sorting
        self.setSortingEnabled(True)

        # Set corner label
        self._set_corner_label("Transaction")

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

        # Apply shifted mappings
        self._row_to_id = new_row_to_id
        self._transactions = new_transactions
        self._row_widgets_map = new_row_widgets_map

        # Store blank row at index 0
        self._transactions_by_id["BLANK_ROW"] = blank_transaction
        self._row_to_id[0] = "BLANK_ROW"
        self._transactions[0] = blank_transaction

        # Create widgets for blank row
        # Date cell
        date_edit = DateInputWidget()
        date_edit._parent_table = self  # Pass reference for validation dialogs
        date_edit.setDate(QDate.fromString(blank_transaction["date"], "yyyy-MM-dd"))
        date_edit.date_changed.connect(self._on_widget_changed)
        self.setCellWidget(0, 0, date_edit)

        # Ticker cell
        ticker_edit = AutoSelectLineEdit(blank_transaction["ticker"])
        ticker_edit.setPlaceholderText("Enter ticker...")
        ticker_edit.textChanged.connect(self._on_widget_changed)
        self.setCellWidget(0, 1, ticker_edit)

        # Type cell
        type_combo = NoScrollComboBox()
        type_combo.addItems(["Buy", "Sell"])
        type_combo.setCurrentText(blank_transaction["transaction_type"])
        type_combo.currentTextChanged.connect(self._on_widget_changed)
        # Hide dropdown arrow and remove all highlight effects
        type_combo.setStyleSheet("""
            QComboBox { border: none; font-size: 14px; }
            QComboBox::drop-down { border: none; width: 0px; }
            QComboBox:focus { border: none; outline: none; }
            QComboBox:on { border: none; }
        """)
        self.setCellWidget(0, 2, type_combo)

        # Quantity cell
        qty_edit = ValidatedNumericLineEdit(min_value=0.0001, max_value=1000000, decimals=4, prefix="", show_dash_for_zero=True)
        qty_edit.setValue(blank_transaction["quantity"])
        qty_edit.textChanged.connect(self._on_widget_changed)
        self.setCellWidget(0, 3, qty_edit)

        # Transaction Price cell
        price_edit = ValidatedNumericLineEdit(min_value=0.01, max_value=1000000, decimals=2, prefix="", show_dash_for_zero=True)
        price_edit.setValue(blank_transaction["entry_price"])
        price_edit.textChanged.connect(self._on_widget_changed)
        self.setCellWidget(0, 4, price_edit)

        # Fees cell
        fees_edit = ValidatedNumericLineEdit(min_value=0, max_value=10000, decimals=2, prefix="", show_dash_for_zero=True)
        fees_edit.setValue(blank_transaction["fees"])
        fees_edit.textChanged.connect(self._on_widget_changed)
        self.setCellWidget(0, 5, fees_edit)

        # Market Value cell (read-only) - column 6
        market_value_item = QTableWidgetItem("--")
        market_value_item.setFlags(market_value_item.flags() & ~Qt.ItemIsEditable)
        market_value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(0, 6, market_value_item)

        # Install focus watchers for auto-delete functionality
        self._install_focus_watcher(0)

        self.setSortingEnabled(False)  # Keep sorting disabled for manual control

    def _is_transaction_complete(self, transaction: Dict[str, Any]) -> bool:
        """
        Check if transaction has all required fields filled.

        Args:
            transaction: Transaction dict

        Returns:
            True if ticker, qty > 0, and entry_price > 0 are all filled
        """
        ticker = transaction.get("ticker", "").strip()
        quantity = transaction.get("quantity", 0.0)
        entry_price = transaction.get("entry_price", 0.0)

        return (
            ticker != "" and
            quantity > 0 and
            entry_price > 0
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

        # Update UUID-based storage
        # Remove old blank entry
        if "BLANK_ROW" in self._transactions_by_id:
            del self._transactions_by_id["BLANK_ROW"]

        # Add new real transaction
        self._transactions_by_id[new_id] = transaction
        self._row_to_id[row] = new_id
        self._transactions[row] = transaction

        # Update calculated cells
        self._update_calculated_cells(row)

        # Emit signal
        self.transaction_added.emit(transaction)

        # Create new blank row at top
        self._ensure_blank_row()

        # Note: Don't sort here - blank is already at top (row 0)
        # Sorting happens on portfolio load to order by date

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

        # Store transaction in UUID-based storage
        tx_id = transaction["id"]
        self._transactions_by_id[tx_id] = transaction
        self._row_to_id[row] = tx_id

        # Also store in legacy dict for backwards compatibility
        self._transactions[row] = transaction

        # Date cell
        date_edit = DateInputWidget()
        date_edit._parent_table = self  # Pass reference for validation dialogs
        date_edit.setDate(QDate.fromString(transaction["date"], "yyyy-MM-dd"))
        date_edit.date_changed.connect(self._on_widget_changed)
        self.setCellWidget(row, 0, date_edit)

        # Ticker cell
        ticker_edit = AutoSelectLineEdit(transaction["ticker"])
        ticker_edit.textChanged.connect(self._on_widget_changed)
        self.setCellWidget(row, 1, ticker_edit)

        # Type cell
        type_combo = NoScrollComboBox()
        type_combo.addItems(["Buy", "Sell"])
        type_combo.setCurrentText(transaction["transaction_type"])
        type_combo.currentTextChanged.connect(self._on_widget_changed)
        # Hide dropdown arrow and remove all highlight effects
        type_combo.setStyleSheet("""
            QComboBox { border: none; font-size: 14px; }
            QComboBox::drop-down { border: none; width: 0px; }
            QComboBox:focus { border: none; outline: none; }
            QComboBox:on { border: none; }
        """)
        self.setCellWidget(row, 2, type_combo)

        # Quantity cell
        qty_edit = ValidatedNumericLineEdit(min_value=0.0001, max_value=1000000, decimals=4, prefix="", show_dash_for_zero=True)
        qty_edit.setValue(transaction["quantity"])
        qty_edit.textChanged.connect(self._on_widget_changed)
        self.setCellWidget(row, 3, qty_edit)

        # Transaction Price cell
        price_edit = ValidatedNumericLineEdit(min_value=0.01, max_value=1000000, decimals=2, prefix="", show_dash_for_zero=True)
        price_edit.setValue(transaction["entry_price"])
        price_edit.textChanged.connect(self._on_widget_changed)
        self.setCellWidget(row, 4, price_edit)

        # Fees cell
        fees_edit = ValidatedNumericLineEdit(min_value=0, max_value=10000, decimals=2, prefix="", show_dash_for_zero=True)
        fees_edit.setValue(transaction["fees"])
        fees_edit.textChanged.connect(self._on_widget_changed)
        self.setCellWidget(row, 5, fees_edit)

        # Market Value cell (read-only) - column 6
        market_value_item = QTableWidgetItem("--")
        market_value_item.setFlags(market_value_item.flags() & ~Qt.ItemIsEditable)
        market_value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setItem(row, 6, market_value_item)

        # Install focus watchers for auto-delete functionality
        self._install_focus_watcher(row)

        # Re-enable sorting
        self.setSortingEnabled(True)

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
            # Get widgets directly from cells
            date_edit = self.cellWidget(row, 0)
            ticker_edit = self.cellWidget(row, 1)
            type_combo = self.cellWidget(row, 2)
            qty_spin = self.cellWidget(row, 3)
            price_spin = self.cellWidget(row, 4)
            fees_spin = self.cellWidget(row, 5)
            # Column 6 is Market Value (read-only item, not widget)

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
        Update Market Value cell.

        Args:
            row: Row index
        """
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        ticker = transaction["ticker"]

        # Get current price
        current_price = self._current_prices.get(ticker)

        if current_price is None:
            self.item(row, 6).setText("--")  # Market Value is now column 6
            return

        # Calculate market value
        market_value = current_price * transaction["quantity"]

        # Update cell
        self.item(row, 6).setText(f"${market_value:,.2f}")  # Market Value is now column 6

    def update_current_prices(self, prices: Dict[str, float]):
        """
        Update current prices and recalculate all rows.

        Args:
            prices: Dict mapping ticker -> price
        """
        self._current_prices = prices
        for row in range(self.rowCount()):
            self._update_calculated_cells(row)

    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """
        Get all transactions from table (excluding blank row).

        Returns:
            List of transaction dicts
        """
        transactions = []
        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            if tx and not tx.get("is_blank"):  # Filter out blank row
                transactions.append(tx)
        return transactions

    def clear_all_transactions(self):
        """Clear all transactions from table."""
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()  # Clear legacy storage too

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

    def _find_row_for_widget(self, widget: QWidget) -> Optional[int]:
        """
        Find the row index for a given widget.

        Args:
            widget: The widget to find

        Returns:
            Row index or None if not found
        """
        for row, widgets in self._row_widgets_map.items():
            if widget in widgets:
                return row
        return None

    def _find_cell_for_widget(self, widget: QWidget) -> tuple[Optional[int], Optional[int]]:
        """
        Find the (row, col) for a given widget by searching all cells.

        Args:
            widget: The widget to find

        Returns:
            Tuple of (row, col) or (None, None) if not found
        """
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                cell_widget = self.cellWidget(row, col)
                if cell_widget == widget:
                    return (row, col)
        return (None, None)

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
            widget = self.cellWidget(row, col)
            if widget:
                widget.installEventFilter(self)
                widgets.append(widget)

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

                        # Check if blank row and complete - transition if so
                        if transaction and transaction.get("is_blank"):
                            if self._is_transaction_complete(transaction):
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

                            if not ticker or quantity == 0.0:
                                # Empty ticker or zero quantity - delete row
                                self._delete_empty_row(row)
                                return True  # Consume event
                            else:
                                # Valid data - validate and fetch prices (same as focus loss)
                                is_valid, error = PortfolioService.validate_transaction(transaction)
                                if is_valid:
                                    self._update_calculated_cells(row)
                                    transaction_id = transaction.get("id")
                                    if transaction_id:
                                        self.transaction_modified.emit(transaction_id, transaction)
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

        Args:
            row: Row index that lost focus
        """
        # Get transaction for this row
        transaction = self._get_transaction_for_row(row)
        if not transaction:
            return

        # Check if this is blank row
        if transaction.get("is_blank"):
            # Check if it's complete, if so transition to real
            if self._is_transaction_complete(transaction):
                self._transition_blank_to_real(row, transaction)
            return

        # Check if row should be deleted (ticker empty OR quantity is 0/blank)
        ticker = transaction.get("ticker", "").strip()
        quantity = transaction.get("quantity", 0.0)

        if not ticker or quantity == 0.0:
            # Empty ticker or zero quantity - delete this row
            self._delete_empty_row(row)
        else:
            # Has ticker and quantity - validate and fetch prices
            # Validate transaction
            is_valid, error = PortfolioService.validate_transaction(transaction)
            if not is_valid:
                # Don't fetch prices for invalid transactions
                return

            # Update calculated cells (fetch prices)
            self._update_calculated_cells(row)

            # Emit signal that transaction was modified
            transaction_id = transaction.get("id")
            if transaction_id:
                self.transaction_modified.emit(transaction_id, transaction)

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

        # Emit signal
        self.transaction_deleted.emit(transaction_id)

    def _sort_transactions(self):
        """
        Sort transactions: blank row at top, completed transactions by date below.
        """
        # Get all transactions
        all_transactions = []
        blank_transaction = None

        for row in range(self.rowCount()):
            tx = self._extract_transaction_from_row(row)
            if tx:
                if tx.get("is_blank"):
                    blank_transaction = tx
                else:
                    all_transactions.append(tx)

        # Sort non-blank transactions by date (oldest first)
        all_transactions.sort(key=lambda t: t.get("date", ""))

        # Rebuild table
        self.setRowCount(0)
        self._transactions_by_id.clear()
        self._row_to_id.clear()
        self._transactions.clear()
        self._row_widgets_map.clear()

        # Add blank row first if it exists
        if blank_transaction:
            self._ensure_blank_row()

        # Add sorted transactions
        for tx in all_transactions:
            self.add_transaction_row(tx)

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
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #232323;
                color: #ffffff;
                gridline-color: #3d3d3d;
                border: 1px solid #3d3d3d;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 8px;
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
                padding: 8px;
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
                padding: 8px;
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
