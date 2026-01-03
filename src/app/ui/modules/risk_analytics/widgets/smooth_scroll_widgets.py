"""Smooth Scroll Widgets - Slower, smoother scrolling for tables and lists."""

from PySide6.QtWidgets import QTableWidget, QListWidget, QAbstractItemView
from PySide6.QtGui import QWheelEvent


class SmoothScrollTableWidget(QTableWidget):
    """QTableWidget with smoother, slower scrolling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

    def wheelEvent(self, event: QWheelEvent):
        """Override wheel event to reduce scroll speed."""
        delta = event.angleDelta().y()
        pixels_to_scroll = int(delta / 4)  # Divide by 4 to slow down scrolling
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - pixels_to_scroll)
        event.accept()


class SmoothScrollListWidget(QListWidget):
    """QListWidget with smoother, slower scrolling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    def wheelEvent(self, event: QWheelEvent):
        """Override wheel event to reduce scroll speed."""
        delta = event.angleDelta().y()
        pixels_to_scroll = int(delta / 4)  # Divide by 4 to slow down scrolling
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - pixels_to_scroll)
        event.accept()
