"""Date Input Widget - Free-form date input with live dash formatting and validation."""

from PySide6.QtWidgets import QLineEdit, QApplication
from PySide6.QtCore import Qt, Signal, QDate, QTimer
from PySide6.QtGui import QKeySequence


class DateInputWidget(QLineEdit):
    """Free-form date input widget with live dash formatting and validation.

    Features:
    - Auto-formatting with dashes (YYYY-MM-DD)
    - Live validation on focus out
    - QDateEdit compatibility methods (setDate, date)
    - Paste support (handles various date formats)

    Signals:
        date_changed: Emitted when a valid date is entered
        validation_error: Emitted when validation fails (title, message)
    """

    # Signal for QDateEdit compatibility
    date_changed = Signal(QDate)

    # Signal for validation errors (decoupled from parent)
    validation_error = Signal(str, str)  # (title, message)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("YYYY-MM-DD")
        self.setMaxLength(10)  # "2025-01-15" = 10 chars

        # Current valid date (None until user enters a valid date)
        self._current_date = None

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
        """Validate the current date and emit error signal if needed.

        Returns:
            True if valid or empty, False if invalid
        """
        current = self.text()

        # Empty field is allowed (no error)
        if not current:
            self._current_date = None
            return True

        # Extract digits
        digits = current.replace("-", "")

        # Incomplete date (less than 8 digits)
        if len(digits) < 8:
            self.validation_error.emit(
                "Incomplete Date",
                f"Please enter a complete date in YYYY-MM-DD format.\nCurrent input: {current}"
            )
            self.setFocus()
            self.selectAll()
            return False

        # Parse as QDate
        parsed_date = QDate.fromString(current, "yyyy-MM-dd")

        if not parsed_date.isValid():
            self.validation_error.emit(
                "Invalid Date",
                f"The date '{current}' is not valid.\nPlease check the month and day values."
            )
            self.setFocus()
            self.selectAll()
            return False

        # Check future date
        if parsed_date > QDate.currentDate():
            self.validation_error.emit(
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
        # Return invalid date if text field is empty or incomplete
        text = self.text().strip()
        if not text or len(text.replace("-", "")) < 8:
            return QDate()  # Invalid date
        return self._current_date if self._current_date and self._current_date.isValid() else QDate()

    def dateChanged(self):
        """For compatibility with QDateEdit signal."""
        return self.date_changed
