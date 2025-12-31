"""Portfolio Dialogs - New/Load/Rename/Import Portfolio Dialogs"""

from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QComboBox, QRadioButton,
    QCheckBox, QButtonGroup
)

from app.core.theme_manager import ThemeManager
from app.ui.widgets.common import CustomMessageBox, ThemedDialog
from ..services.portfolio_persistence import PortfolioPersistence


class NewPortfolioDialog(ThemedDialog):
    """Dialog to create a new portfolio."""

    def __init__(self, theme_manager: ThemeManager, existing_names: List[str], parent=None):
        self.existing_names = existing_names
        self.name_edit: QLineEdit = None
        super().__init__(theme_manager, "New Portfolio", parent)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        layout.addWidget(QLabel("Portfolio Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter portfolio name...")
        self.name_edit.returnPressed.connect(self._validate_and_accept)
        layout.addWidget(self.name_edit)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        create_btn = QPushButton("Create")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(create_btn)

        layout.addLayout(button_layout)

    def _validate_and_accept(self):
        """Validate name and accept."""
        name = self.name_edit.text().strip()

        if not name:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Invalid Name",
                "Please enter a portfolio name."
            )
            return

        if name in self.existing_names:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Name Exists",
                f"A portfolio named '{name}' already exists."
            )
            return

        self.accept()

    def get_name(self) -> str:
        """Get entered portfolio name."""
        return self.name_edit.text().strip()


class RenamePortfolioDialog(ThemedDialog):
    """Dialog to rename a portfolio."""

    def __init__(self, theme_manager: ThemeManager, current_name: str, existing_names: List[str], parent=None):
        self.current_name = current_name
        self.existing_names = [n for n in existing_names if n != current_name]
        self.name_edit: QLineEdit = None
        super().__init__(theme_manager, "Rename Portfolio", parent)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        layout.addWidget(QLabel("New Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.current_name)
        self.name_edit.selectAll()
        self.name_edit.returnPressed.connect(self._validate_and_accept)
        layout.addWidget(self.name_edit)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def _validate_and_accept(self):
        """Validate name and accept."""
        name = self.name_edit.text().strip()

        if not name:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Invalid Name",
                "Please enter a portfolio name."
            )
            return

        if name in self.existing_names:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "Name Exists",
                f"A portfolio named '{name}' already exists."
            )
            return

        self.accept()

    def get_name(self) -> str:
        """Get entered portfolio name."""
        return self.name_edit.text().strip()


class LoadPortfolioDialog(ThemedDialog):
    """Dialog to load an existing portfolio."""

    def __init__(self, theme_manager: ThemeManager, portfolios: List[str], parent=None):
        self.portfolios = portfolios
        self.portfolio_list: QListWidget = None
        super().__init__(theme_manager, "Load Portfolio", parent, min_height=300)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        layout.addWidget(QLabel("Select Portfolio:"))
        self.portfolio_list = QListWidget()
        self.portfolio_list.addItems(self.portfolios)
        self.portfolio_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.portfolio_list)

        # Buttons
        button_layout = QHBoxLayout()

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_selected)
        button_layout.addWidget(delete_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        load_btn = QPushButton("Load")
        load_btn.setDefault(True)
        load_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(load_btn)

        layout.addLayout(button_layout)

    def _validate_and_accept(self):
        """Validate selection and accept."""
        if not self.portfolio_list.currentItem():
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Selection",
                "Please select a portfolio to load."
            )
            return
        self.accept()

    def _delete_selected(self):
        """Delete selected portfolio."""
        current_item = self.portfolio_list.currentItem()
        if not current_item:
            CustomMessageBox.information(
                self.theme_manager,
                self,
                "No Selection",
                "Please select a portfolio to delete."
            )
            return

        name = current_item.text()

        reply = CustomMessageBox.question(
            self.theme_manager,
            self,
            "Delete Portfolio",
            f"Are you sure you want to delete '{name}'?",
            CustomMessageBox.Yes | CustomMessageBox.No,
            CustomMessageBox.No
        )

        if reply == CustomMessageBox.Yes:
            if PortfolioPersistence.delete_portfolio(name):
                row = self.portfolio_list.row(current_item)
                self.portfolio_list.takeItem(row)
                CustomMessageBox.information(
                    self.theme_manager,
                    self,
                    "Deleted",
                    f"Portfolio '{name}' deleted successfully."
                )
            else:
                CustomMessageBox.critical(
                    self.theme_manager,
                    self,
                    "Delete Error",
                    f"Failed to delete portfolio '{name}'."
                )

    def get_selected_name(self) -> Optional[str]:
        """Get selected portfolio name."""
        current_item = self.portfolio_list.currentItem()
        return current_item.text() if current_item else None


class ImportPortfolioDialog(ThemedDialog):
    """Dialog to import transactions from another portfolio."""

    def __init__(self, theme_manager: ThemeManager, available_portfolios: List[str], parent=None):
        self.available_portfolios = available_portfolios
        self.source_combo: QComboBox = None
        self.mode_group: QButtonGroup = None
        self.full_history_radio: QRadioButton = None
        self.flat_radio: QRadioButton = None
        self.include_fees_checkbox: QCheckBox = None
        self.skip_zero_checkbox: QCheckBox = None
        super().__init__(theme_manager, "Import Transactions", parent, min_width=450, min_height=350)

    def _setup_content(self, layout: QVBoxLayout):
        """Setup dialog content."""
        # Source portfolio dropdown
        layout.addWidget(QLabel("Source Portfolio:"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("Select a portfolio...")
        self.source_combo.addItems(self.available_portfolios)
        layout.addWidget(self.source_combo)

        layout.addSpacing(10)

        # Import mode radio buttons
        mode_label = QLabel("Import Mode:")
        layout.addWidget(mode_label)

        self.mode_group = QButtonGroup(self)

        # Full history option
        self.full_history_radio = QRadioButton("Import with transaction dates")
        self.full_history_radio.setChecked(True)
        self.full_history_radio.toggled.connect(self._on_mode_changed)
        self.mode_group.addButton(self.full_history_radio)
        layout.addWidget(self.full_history_radio)

        full_history_desc = QLabel("Keep full history with original dates")
        full_history_desc.setObjectName("descriptionLabel")
        full_history_desc.setContentsMargins(20, 0, 0, 0)
        layout.addWidget(full_history_desc)

        layout.addSpacing(5)

        # Flat import option
        self.flat_radio = QRadioButton("Import flat (all dates set to today)")
        self.flat_radio.toggled.connect(self._on_mode_changed)
        self.mode_group.addButton(self.flat_radio)
        layout.addWidget(self.flat_radio)

        flat_desc = QLabel("Consolidate to net positions with average cost basis")
        flat_desc.setObjectName("descriptionLabel")
        flat_desc.setContentsMargins(20, 0, 0, 0)
        layout.addWidget(flat_desc)

        layout.addSpacing(15)

        # Options section
        options_label = QLabel("Options:")
        layout.addWidget(options_label)

        self.include_fees_checkbox = QCheckBox("Include fees")
        self.include_fees_checkbox.setChecked(True)
        layout.addWidget(self.include_fees_checkbox)

        self.skip_zero_checkbox = QCheckBox("Skip net zero positions")
        self.skip_zero_checkbox.setChecked(False)
        self.skip_zero_checkbox.setEnabled(False)  # Disabled by default (full history mode)
        layout.addWidget(self.skip_zero_checkbox)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        import_btn = QPushButton("Import")
        import_btn.setDefault(True)
        import_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(import_btn)

        layout.addLayout(button_layout)

    def _on_mode_changed(self):
        """Handle import mode radio button change."""
        is_flat_mode = self.flat_radio.isChecked()
        self.skip_zero_checkbox.setEnabled(is_flat_mode)
        if not is_flat_mode:
            self.skip_zero_checkbox.setChecked(False)

    def _validate_and_accept(self):
        """Validate selection and accept."""
        if self.source_combo.currentIndex() == 0:
            CustomMessageBox.warning(
                self.theme_manager,
                self,
                "No Selection",
                "Please select a source portfolio to import from."
            )
            return
        self.accept()

    def get_import_config(self) -> Optional[Dict[str, Any]]:
        """
        Get import configuration.

        Returns:
            Dict with import settings or None if cancelled.
        """
        if self.result() != QDialog.Accepted:
            return None

        return {
            "source_portfolio": self.source_combo.currentText(),
            "import_mode": "flat" if self.flat_radio.isChecked() else "full_history",
            "include_fees": self.include_fees_checkbox.isChecked(),
            "skip_zero_positions": self.skip_zero_checkbox.isChecked()
        }
