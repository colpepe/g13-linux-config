from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QWidget

from conftest import key_event
from g13config.capture import KeyCaptureField


def _field_with_focus_chain(qapp):
    """A capture field with a sibling to tab to.

    The sibling matters: a lone widget has nowhere to move focus, so
    QWidget::event() declines to consume Tab and the bug does not
    reproduce. With a sibling, focus navigation eats Tab before
    keyPressEvent ever runs.
    """
    host = QWidget()
    field = KeyCaptureField(parent=host)
    QLineEdit(parent=host)
    host.show()
    return host, field


def test_armed_field_captures_tab(qapp):
    host, field = _field_with_focus_chain(qapp)
    field._arm()
    qapp.sendEvent(field, key_event(23, Qt.Key_Tab, text="\t"))
    assert field.codes == [15]
    assert not field._armed


def test_armed_field_captures_escape(qapp):
    host, field = _field_with_focus_chain(qapp)
    field._arm()
    qapp.sendEvent(field, key_event(9, Qt.Key_Escape))
    assert field.codes == [1]
    assert not field._armed


def test_armed_field_captures_shift_tab_as_combo(qapp):
    host, field = _field_with_focus_chain(qapp)
    field._arm()
    qapp.sendEvent(field, key_event(50, Qt.Key_Shift, Qt.ShiftModifier))
    qapp.sendEvent(field, key_event(23, Qt.Key_Backtab, Qt.ShiftModifier, "\t"))
    assert field.codes == [42, 15]
    assert not field._armed


def test_unarmed_field_ignores_tab(qapp):
    host, field = _field_with_focus_chain(qapp)
    qapp.sendEvent(field, key_event(23, Qt.Key_Tab, text="\t"))
    assert field.codes == []


def test_capture_emits_chord_signal(qapp):
    host, field = _field_with_focus_chain(qapp)
    seen = []
    field.chordCaptured.connect(seen.append)
    field._arm()
    qapp.sendEvent(field, key_event(38, Qt.Key_A, text="a"))
    assert seen == [[30]]
