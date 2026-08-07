"""Profile tab bar with inline rename (double-click a tab)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit, QTabBar


class _NameEdit(QLineEdit):
    """Line edit that reports Escape instead of letting it reach the dialog."""

    cancelled = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)


class RenamableTabBar(QTabBar):
    """A QTabBar whose tabs can be renamed in place.

    Double-click a tab to edit its label. Enter commits, Escape reverts,
    and clicking away commits (matching how file managers behave).
    ``tabRenamed`` fires only when the text actually changed.
    """

    tabRenamed = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editor: _NameEdit | None = None
        self._editing_index = -1
        self._original = ""

    def mouseDoubleClickEvent(self, event):
        index = self.tabAt(event.position().toPoint())
        if index >= 0:
            self._begin_edit(index)
            return
        super().mouseDoubleClickEvent(event)

    def _begin_edit(self, index: int):
        if self._editor is not None:
            self._finish_edit(commit=True)

        self._editing_index = index
        self._original = self.tabText(index)

        editor = _NameEdit(self)
        editor.setText(self._original)
        editor.selectAll()
        editor.setGeometry(self.tabRect(index))
        editor.returnPressed.connect(lambda: self._finish_edit(commit=True))
        editor.cancelled.connect(lambda: self._finish_edit(commit=False))
        editor.editingFinished.connect(self._on_editing_finished)
        self._editor = editor
        editor.show()
        editor.setFocus(Qt.OtherFocusReason)

    def _on_editing_finished(self):
        # Fires on Enter (already handled by returnPressed, hence the guard)
        # and on focus loss, where committing is the least surprising outcome.
        if self._editor is not None:
            self._finish_edit(commit=True)

    def _finish_edit(self, commit: bool):
        editor, self._editor = self._editor, None
        if editor is None:
            return
        index, original = self._editing_index, self._original
        self._editing_index = -1

        text = editor.text() if commit else original
        editor.deleteLater()

        if commit and text != original:
            self.setTabText(index, text)
            self.tabRenamed.emit(index, text)
