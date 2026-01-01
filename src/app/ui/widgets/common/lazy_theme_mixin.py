"""Lazy theme mixin for deferred theme application."""

from __future__ import annotations


class LazyThemeMixin:
    """
    Mixin for widgets that defer theme application when not visible.

    This improves performance when changing themes with multiple modules loaded
    by only applying theme changes to visible widgets. Hidden widgets mark
    themselves as "dirty" and apply the theme when they become visible.

    Usage:
        1. Add this mixin to your widget class
        2. Initialize _theme_dirty = False in __init__
        3. Connect theme_changed to _on_theme_changed_lazy instead of _apply_theme
        4. Override showEvent to call _check_theme_dirty()

    Example:
        class MyWidget(LazyThemeMixin, QWidget):
            def __init__(self, theme_manager):
                super().__init__()
                self._theme_dirty = False
                self.theme_manager = theme_manager
                self.theme_manager.theme_changed.connect(self._on_theme_changed_lazy)
                self._apply_theme()

            def showEvent(self, event):
                super().showEvent(event)
                self._check_theme_dirty()

            def _apply_theme(self):
                # Your theme application logic
                pass
    """

    _theme_dirty: bool = False

    def _on_theme_changed_lazy(self) -> None:
        """
        Handle theme change signal with visibility check.

        Call this from theme_changed signal instead of _apply_theme directly.
        If the widget is visible, applies theme immediately.
        If hidden, marks as dirty for later application.
        """
        if self.isVisible():
            self._apply_theme()
        else:
            self._theme_dirty = True

    def _check_theme_dirty(self) -> None:
        """
        Check and apply pending theme if dirty.

        Call this from showEvent after calling super().showEvent(event).
        """
        if self._theme_dirty:
            self._apply_theme()
            self._theme_dirty = False
