from PySide6.QtCore import Qt

from conftest import key_event
from g13config import model
from g13config.binding_dialog import BindingEditorDialog
from g13config.macros import Macro


def _dialog(current, qapp):
    d = BindingEditorDialog("G1", current, {1: Macro(id=1, name="test")})
    d.show()
    qapp.processEvents()
    return d


def test_unbound_key_opens_on_key_radio_and_armed(qapp):
    d = _dialog(None, qapp)
    assert d.r_key.isChecked()
    assert d.capture._armed
    assert not d.pan_hold._armed
    d.close()


def test_existing_key_binding_opens_armed(qapp):
    d = _dialog(model.KeyBinding(codes=[30]), qapp)
    assert d.r_key.isChecked()
    assert d.capture._armed
    d.close()


def test_macro_binding_does_not_auto_arm(qapp):
    d = _dialog(model.MacroBinding(macro_id=1, repeats=0), qapp)
    assert d.r_macro.isChecked()
    assert not d.capture._armed
    d.close()


def test_pan_binding_does_not_auto_arm(qapp):
    d = _dialog(model.MousePanBinding(dx=5, dy=0), qapp)
    assert d.r_pan.isChecked()
    assert not d.capture._armed
    assert not d.pan_hold._armed
    d.close()


def test_escape_captures_then_second_escape_rejects(qapp):
    d = _dialog(None, qapp)
    qapp.sendEvent(d.capture, key_event(9, Qt.Key_Escape))
    assert d.capture.codes == [1]
    assert not d.capture._armed
    assert d.isVisible()

    qapp.sendEvent(d, key_event(9, Qt.Key_Escape))
    qapp.processEvents()
    assert d.result() == BindingEditorDialog.Rejected
