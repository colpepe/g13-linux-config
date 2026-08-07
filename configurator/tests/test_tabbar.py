from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from g13config.tabbar import RenamableTabBar


def _bar(qapp):
    bar = RenamableTabBar()
    for text in ("FUSION 360", "GAMING", "Slot 3", "Slot 4"):
        bar.addTab(text)
    bar.show()
    return bar


def test_begin_edit_shows_editor_with_current_text(qapp):
    bar = _bar(qapp)
    bar._begin_edit(1)
    assert bar._editor is not None
    assert bar._editor.isVisible()
    assert bar._editor.text() == "GAMING"
    bar.close()


def test_enter_commits_and_emits_rename(qapp):
    bar = _bar(qapp)
    seen = []
    bar.tabRenamed.connect(lambda i, t: seen.append((i, t)))
    bar._begin_edit(2)
    bar._editor.setText("Gaming 2")
    bar._editor.returnPressed.emit()
    assert seen == [(2, "Gaming 2")]
    assert bar.tabText(2) == "Gaming 2"
    assert bar._editor is None
    bar.close()


def test_escape_cancels_without_emitting(qapp):
    bar = _bar(qapp)
    seen = []
    bar.tabRenamed.connect(lambda i, t: seen.append((i, t)))
    bar._begin_edit(2)
    bar._editor.setText("discard me")
    bar._editor.keyPressEvent(
        QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    assert seen == []
    assert bar.tabText(2) == "Slot 3"
    assert bar._editor is None
    bar.close()


def test_commit_of_unchanged_text_emits_nothing(qapp):
    bar = _bar(qapp)
    seen = []
    bar.tabRenamed.connect(lambda i, t: seen.append((i, t)))
    bar._begin_edit(0)
    bar._editor.returnPressed.emit()
    assert seen == []
    bar.close()


def test_empty_name_is_allowed(qapp):
    bar = _bar(qapp)
    seen = []
    bar.tabRenamed.connect(lambda i, t: seen.append((i, t)))
    bar._begin_edit(0)
    bar._editor.setText("")
    bar._editor.returnPressed.emit()
    assert seen == [(0, "")]
    bar.close()


def test_double_click_on_a_tab_begins_edit(qapp):
    bar = _bar(qapp)
    pos = QPointF(bar.tabRect(1).center())
    ev = QMouseEvent(QEvent.MouseButtonDblClick, pos, pos, Qt.LeftButton,
                     Qt.LeftButton, Qt.NoModifier)
    bar.mouseDoubleClickEvent(ev)
    assert bar._editor is not None
    assert bar._editor.text() == "GAMING"
    bar.close()


def test_double_click_off_any_tab_does_nothing(qapp):
    bar = _bar(qapp)
    pos = QPointF(bar.width() + 50, bar.height() + 50)
    ev = QMouseEvent(QEvent.MouseButtonDblClick, pos, pos, Qt.LeftButton,
                     Qt.LeftButton, Qt.NoModifier)
    bar.mouseDoubleClickEvent(ev)
    assert bar._editor is None
    bar.close()
