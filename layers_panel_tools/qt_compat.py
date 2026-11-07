# -*- coding: utf-8 -*-
"""Qt5 and Qt6 spell enum members differently. Qt6 only keeps the scoped form."""

_NESTED = (
    "ToolButtonPopupMode",
    "ToolButtonStyle",
    "TextElideMode",
    "Orientation",
    "SelectionBehavior",
    "SelectionMode",
    "SelectionFlag",
    "EditTrigger",
    "FocusPolicy",
    "FocusReason",
    "ItemDataRole",
    "ItemFlag",
    "CheckState",
    "AlignmentFlag",
    "LayoutDirection",
    "StandardButton",
    "DialogCode",
    "DragDropMode",
    "OpenModeFlag",
    "ResizeMode",
    "ScrollHint",
    "Policy",
    "Mode",
    "State",
    "Key",
    "KeyboardModifier",
    "MatchFlag",
    "CaseSensitivity",
    "WindowType",
    "StyleCategory",
    "Type",
    "ShortcutContext",
    "SequenceFormat",
    "SequenceMatch",
    "Icon",
)


def qt_attr(owner, name):
    value = getattr(owner, name, None)
    if value is not None:
        return value
    for nested_name in _NESTED:
        nested = getattr(owner, nested_name, None)
        if nested is not None and hasattr(nested, name):
            return getattr(nested, name)
    raise AttributeError(name)


def enum_int(value, default=-1):
    """PyQt6 enums are Python enums, so int() alone fails on many of them."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    inner = getattr(value, "value", None)
    if inner is None:
        return default
    try:
        return int(inner)
    except (TypeError, ValueError):
        return default


def user_role(offset=0):
    from qgis.PyQt.QtCore import Qt

    return enum_int(qt_attr(Qt, "UserRole"), 256) + int(offset)


def run_dialog(dialog):
    runner = getattr(dialog, "exec", None)
    if not callable(runner):
        runner = getattr(dialog, "exec_")
    return enum_int(runner(), 0)


def accepted(code):
    from qgis.PyQt.QtWidgets import QDialog

    return enum_int(code, 0) == enum_int(qt_attr(QDialog, "Accepted"), 1)
