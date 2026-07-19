"""Human-readable labels for bindings (keycaps and tooltips)."""
from . import keycodes, model
from .macros import Macro


def _combo_text(codes: list[int]) -> str:
    return "+".join(keycodes.label_for(c) for c in codes)


def short_label(binding: model.Binding | None, macro_pool: dict[int, Macro]) -> str:
    if binding is None:
        return ""
    if isinstance(binding, model.KeyBinding):
        return _combo_text(binding.codes)
    if isinstance(binding, model.MacroBinding):
        macro = macro_pool.get(binding.macro_id)
        return f"M: {macro.name}" if macro and macro.name else f"M: #{binding.macro_id}"
    if isinstance(binding, model.MousePanBinding):
        if binding.dx == 0 and binding.dy > 0:
            return "Pan ↓"
        if binding.dx == 0 and binding.dy < 0:
            return "Pan ↑"
        if binding.dy == 0 and binding.dx > 0:
            return "Pan →"
        if binding.dy == 0 and binding.dx < 0:
            return "Pan ←"
        return "Pan"
    return "?"


def long_label(binding: model.Binding | None, macro_pool: dict[int, Macro]) -> str:
    if binding is None:
        return "Unbound"
    if isinstance(binding, model.KeyBinding):
        names = "+".join(keycodes.name_for(c) for c in binding.codes)
        return f"Key: {_combo_text(binding.codes)} ({names})"
    if isinstance(binding, model.MacroBinding):
        return f"{short_label(binding, macro_pool)} (repeats={binding.repeats})"
    if isinstance(binding, model.MousePanBinding):
        hold = "+".join(keycodes.label_for(c) for c in binding.hold) if binding.hold else "default"
        return f"Mouse pan dx={binding.dx} dy={binding.dy} hold={hold}"
    return "?"
