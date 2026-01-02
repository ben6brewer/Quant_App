"""Theme Stylesheet Service - Centralized widget stylesheets by theme."""

from typing import Dict


class ThemeStylesheetService:
    """
    Provides theme-aware stylesheets for common widget types.

    Centralizes theme colors and stylesheet generation to avoid duplication
    across modules. All colors are defined in COLORS dict for easy maintenance.
    """

    # Theme color constants
    COLORS: Dict[str, Dict[str, str]] = {
        "dark": {
            "accent": "#00d4ff",
            "accent_hover": "#00e5ff",
            "accent_selection": "#40e0ff",
            "bg": "#1e1e1e",
            "bg_alt": "#232323",
            "bg_header": "#2d2d2d",
            "border": "#3d3d3d",
            "text": "#ffffff",
            "text_muted": "#cccccc",
            "text_on_accent": "#000000",
        },
        "light": {
            "accent": "#0066cc",
            "accent_hover": "#0077dd",
            "accent_selection": "#0088ee",
            "bg": "#ffffff",
            "bg_alt": "#f5f5f5",
            "bg_header": "#f5f5f5",
            "border": "#cccccc",
            "text": "#000000",
            "text_muted": "#333333",
            "text_on_accent": "#ffffff",
        },
        "bloomberg": {
            "accent": "#FF8000",
            "accent_hover": "#FF9020",
            "accent_selection": "#FFa040",
            "bg": "#000814",
            "bg_alt": "#0a0f1c",
            "bg_header": "#0d1420",
            "border": "#1a2838",
            "text": "#e8e8e8",
            "text_muted": "#a8a8a8",
            "text_on_accent": "#000000",
        }
    }

    @classmethod
    def get_colors(cls, theme: str) -> Dict[str, str]:
        """Get color palette for a theme."""
        return cls.COLORS.get(theme, cls.COLORS["dark"])

    @classmethod
    def get_table_stylesheet(cls, theme: str) -> str:
        """Get QTableWidget stylesheet for a theme."""
        c = cls.get_colors(theme)
        return f"""
            QTableWidget {{
                background-color: {c['bg']};
                alternate-background-color: {c['bg_alt']};
                color: {c['text']};
                gridline-color: {c['border']};
                border: 1px solid {c['border']};
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
            }}
            QHeaderView::section {{
                background-color: {c['bg_header']};
                color: {c['text_muted']};
                padding: 8px;
                border: 1px solid {c['border']};
                font-weight: bold;
                font-size: 14px;
            }}
            QTableCornerButton::section {{
                background-color: {c['bg_header']};
                color: {c['text_muted']};
                border: 1px solid {c['border']};
                font-weight: bold;
                font-size: 13px;
                padding: 8px;
            }}
        """

    @classmethod
    def get_line_edit_stylesheet(cls, theme: str, highlighted: bool = True) -> str:
        """Get QLineEdit stylesheet for editable cells.

        Args:
            theme: Theme name ('dark', 'light', 'bloomberg')
            highlighted: If True, use accent color background. If False, transparent.
        """
        c = cls.get_colors(theme)

        if not highlighted:
            return f"""
                QLineEdit {{
                    background-color: transparent;
                    color: {c['text']};
                    border: none;
                    margin: 0px;
                    padding: 0px 8px;
                    font-size: 14px;
                }}
            """

        return f"""
            QLineEdit {{
                background-color: transparent;
                color: {c['text_on_accent']};
                border: none;
                margin: 0px;
                padding: 0px 4px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                background-color: transparent;
            }}
        """

    @classmethod
    def get_combobox_stylesheet(cls, theme: str, highlighted: bool = True) -> str:
        """Get QComboBox stylesheet for editable cells.

        Args:
            theme: Theme name ('dark', 'light', 'bloomberg')
            highlighted: If True, use accent color background. If False, transparent.
        """
        c = cls.get_colors(theme)

        if not highlighted:
            return f"""
                QComboBox {{
                    background-color: transparent;
                    color: {c['text']};
                    border: none;
                    padding: 4px 8px;
                    font-size: 14px;
                }}
                QComboBox::drop-down {{ border: none; width: 0px; }}
                QComboBox QAbstractItemView {{
                    background-color: {c['bg_header']};
                    color: {c['text']};
                    selection-background-color: {c['accent']};
                }}
            """

        return f"""
            QComboBox {{
                background-color: transparent;
                color: {c['text_on_accent']};
                border: none;
                padding: 4px 4px;
                font-size: 14px;
            }}
            QComboBox::drop-down {{ border: none; width: 0px; }}
            QComboBox:focus {{ background-color: transparent; }}
            QComboBox QAbstractItemView {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                selection-background-color: {c['accent_selection']};
            }}
        """

    @classmethod
    def get_dialog_stylesheet(cls, theme: str) -> str:
        """Get QDialog stylesheet for themed dialogs.

        Includes styling for:
        - Dialog background and title bar
        - Labels (regular and description)
        - Line edits
        - Buttons (regular and title bar close)
        - List widgets
        - Combo boxes
        - Radio buttons and checkboxes
        """
        c = cls.get_colors(theme)

        # Additional colors for dialogs
        bg_pressed = "#1a1a1a" if theme == "dark" else "#d0d0d0" if theme == "light" else "#060a10"
        bg_hover = "#3d3d3d" if theme == "dark" else "#e8e8e8" if theme == "light" else "#1a2838"
        text_desc = "#888888" if theme == "dark" else "#666666" if theme == "light" else "#666666"
        text_disabled = "#666666" if theme == "dark" else "#999999" if theme == "light" else "#555555"

        return f"""
            QDialog {{
                background-color: {c['bg']};
                color: {c['text']};
            }}
            QWidget#titleBar {{
                background-color: {c['bg_header']};
            }}
            QLabel#titleLabel {{
                color: {c['text']};
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }}
            QPushButton#titleBarCloseButton {{
                background-color: transparent;
                color: {c['text']};
                border: none;
                font-size: 16px;
            }}
            QPushButton#titleBarCloseButton:hover {{
                background-color: #d32f2f;
                color: #ffffff;
            }}
            QLabel {{
                color: {c['text_muted']};
                font-size: 13px;
                background-color: transparent;
            }}
            QLabel#descriptionLabel {{
                color: {text_desc};
                font-size: 12px;
                background-color: transparent;
            }}
            QLineEdit {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
            QListWidget {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                font-size: 13px;
            }}
            QListWidget::item:selected {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
            }}
            QListWidget::item:hover {{
                background-color: {bg_hover};
            }}
            QComboBox {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 5px 10px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {c['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {c['text']};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['bg_header']};
                color: {c['text']};
                selection-background-color: {c['accent']};
                selection-color: {c['text_on_accent']};
                font-size: 13px;
                padding: 4px;
            }}
            QRadioButton {{
                color: {c['text']};
                font-size: 13px;
                spacing: 8px;
                background-color: transparent;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid {c['border']};
                background-color: {c['bg_header']};
            }}
            QRadioButton::indicator:checked {{
                border-color: {c['accent']};
                background-color: {c['accent']};
            }}
            QRadioButton::indicator:hover {{
                border-color: {c['accent']};
            }}
            QCheckBox {{
                color: {c['text']};
                font-size: 13px;
                spacing: 8px;
                background-color: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid {c['border']};
                background-color: {c['bg_header']};
            }}
            QCheckBox::indicator:checked {{
                border-color: {c['accent']};
                background-color: {c['accent']};
            }}
            QCheckBox::indicator:hover {{
                border-color: {c['accent']};
            }}
            QCheckBox:disabled {{
                color: {text_disabled};
            }}
            QCheckBox::indicator:disabled {{
                border-color: {c['bg_header']};
                background-color: {bg_pressed};
            }}
            QPushButton {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                border-color: {c['accent']};
            }}
            QPushButton:pressed {{
                background-color: {bg_pressed};
            }}
            QPushButton#defaultButton {{
                background-color: {c['accent']};
                color: {c['text_on_accent']};
                border: 1px solid {c['accent']};
                font-weight: 600;
            }}
            QPushButton#defaultButton:hover {{
                background-color: {c['accent_hover']};
                border-color: {c['accent_hover']};
            }}
            QPushButton#defaultButton:pressed {{
                background-color: {c['accent']};
            }}
            QLabel#noteLabel {{
                color: {text_desc};
                font-style: italic;
                font-size: 11px;
                background-color: transparent;
            }}
            QGroupBox {{
                color: {c['text']};
                background-color: {c['bg']};
                border: 2px solid {c['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 20px;
                font-size: 14px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                background-color: {c['bg']};
            }}
            QSpinBox {{
                background-color: {c['bg_header']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 5px 8px;
                font-size: 13px;
            }}
            QSpinBox:hover {{
                border-color: {c['accent']};
            }}
            QSpinBox:focus {{
                border-color: {c['accent']};
            }}
            QScrollArea {{
                border: none;
                background-color: {c['bg']};
            }}
            QScrollBar:vertical {{
                background-color: {c['bg']};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {bg_hover};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c['border']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background-color: {c['bg']};
                height: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {bg_hover};
                border-radius: 6px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {c['border']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """
