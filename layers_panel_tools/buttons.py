# -*- coding: utf-8 -*-
"""Shared toolbar button. The Layers bar hides text on an ordinary action."""

from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtWidgets import QMenu, QMessageBox, QToolButton, QWidgetAction

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .i18n import language_changed, tr
from .qt_compat import enum_int, qt_attr, run_dialog

__all__ = [
    "qt_attr",
    "enum_int",
    "make_toolbar_button",
    "make_menu_action",
    "make_popup_tool",
    "make_popup_menu_action",
    "add_item",
    "ask",
    "report",
]


def _hover_tip(button_id, msgid, tip_msgid, custom=""):
    """标题 + 一句话说明 + 换行的功能说明及使用技巧。"""
    try:
        from . import button_help

        return button_help.hover_tip(button_id, msgid, tip_msgid, custom)
    except Exception:
        return tr(tip_msgid or msgid)


def make_toolbar_button(iface, button_id, object_name, msgid, tip_msgid, icon, on_click, menu=None, popup=None, tip_live=False):
    button = QToolButton(iface.mainWindow())
    button.setObjectName(object_name + "Button")
    button.setAutoRaise(True)
    button.setToolButtonStyle(qt_attr(Qt, "ToolButtonIconOnly"))
    button.setIcon(icon)
    button.setIconSize(QSize(24, 24))
    button.setText("")
    if not tip_live:
        button.setToolTip(_hover_tip(button_id, msgid, tip_msgid))
    if menu is not None:
        button.setMenu(menu)
        button.setPopupMode(qt_attr(QToolButton, popup or "InstantPopup"))
    if on_click is not None and menu is None:
        button.clicked.connect(lambda *_args: on_click())
    elif on_click is not None and popup == "MenuButtonPopup":
        button.clicked.connect(lambda *_args: on_click())
    action = QWidgetAction(iface.mainWindow())
    action.setDefaultWidget(button)
    action.setIcon(icon)
    action.setObjectName(object_name)
    action.setProperty("lpt_id", button_id)
    action.setProperty("lpt_msgid", msgid)
    if tip_msgid:
        action.setProperty("lpt_tip_msgid", tip_msgid)
    if tip_live:
        action.setProperty("lpt_tip_live", True)
    action.setText(tr(msgid))
    if not tip_live:
        action.setToolTip(_hover_tip(button_id, msgid, tip_msgid))

    def _retitle(*_args):
        try:
            button.setText("")
            action.setText(tr(msgid))
            if not tip_live:
                custom = str(action.property("lpt_custom_tip") or "").strip()
                tip = _hover_tip(button_id, msgid, tip_msgid, custom)
                if not tip:
                    tip = tr(tip_msgid or msgid)
                button.setToolTip(tip)
                action.setToolTip(tip)
                if custom:
                    action.setText(custom)
        except RuntimeError:
            try:
                language_changed().disconnect(_retitle)
            except Exception:
                pass  # nosec

    language_changed().connect(_retitle)
    return action


def make_menu_action(iface, object_name, msgid, tip_msgid, icon, callback):
    action = QAction(icon, tr(msgid), iface.mainWindow())
    action.setObjectName(object_name)
    action.setProperty("lpt_msgid", msgid)
    if tip_msgid:
        action.setProperty("lpt_tip_msgid", tip_msgid)
        action.setToolTip(tr(tip_msgid))
    else:
        action.setToolTip(tr(msgid))
    if callback is not None:
        action.triggered.connect(lambda *_args: callback())
    return action


def _popup_menu(parent, object_name, fill):
    menu = QMenu(parent)
    menu.setObjectName(object_name)
    menu.setToolTipsVisible(True)
    menu.aboutToShow.connect(lambda menu=menu: fill(menu))
    return menu


def make_popup_tool(iface, button_id, object_name, msgid, tip_msgid, icon, fill):
    """Icon on the Layers bar. A click lists the choices; picking one runs it."""
    return make_toolbar_button(
        iface,
        button_id,
        object_name,
        msgid,
        tip_msgid,
        icon,
        None,
        menu=_popup_menu(iface.mainWindow(), object_name + "Popup", fill),
        popup="InstantPopup",
    )


def make_popup_menu_action(iface, object_name, msgid, tip_msgid, icon, fill):
    action = make_menu_action(iface, object_name, msgid, tip_msgid, icon, None)
    action.setMenu(_popup_menu(iface.mainWindow(), object_name + "Popup", fill))
    return action


def add_item(menu, text, callback, enabled=True, tip=""):
    action = QAction(text, menu)
    action.setEnabled(bool(enabled))
    if tip:
        action.setToolTip(tip)
    action.triggered.connect(lambda *_args: callback())
    menu.addAction(action)
    return action


def ask(parent, title, text):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    yes_flag = qt_attr(QMessageBox, "Yes")
    no_flag = qt_attr(QMessageBox, "No")
    box.setStandardButtons(yes_flag | no_flag)
    yes = box.button(yes_flag)
    no = box.button(no_flag)
    if yes is not None:
        yes.setText(tr("是"))
    if no is not None:
        no.setText(tr("否"))
    return run_dialog(box) == enum_int(yes_flag)


_REPORT_BOXES = []


def _key_sequence(text):
    from qgis.PyQt.QtGui import QKeySequence

    try:
        seq = QKeySequence.fromString(str(text or ""))
    except Exception:
        return None
    try:
        if seq.isEmpty():
            return None
    except Exception:
        return None
    return seq


def _portable(seq):
    from qgis.PyQt.QtGui import QKeySequence

    try:
        return str(seq.toString(qt_attr(QKeySequence, "PortableText")))
    except Exception:
        try:
            return str(seq.toString())
        except Exception:
            return ""


def _same_sequence(left, right):
    if left is None or right is None:
        return False
    try:
        if left.isEmpty() or right.isEmpty():
            return False
    except Exception:
        return False
    if _portable(left) and _portable(left) == _portable(right):
        return True
    try:
        from qgis.PyQt.QtGui import QKeySequence

        return enum_int(left.matches(right), -1) == enum_int(qt_attr(QKeySequence, "ExactMatch"), -2)
    except Exception:
        return False


def _object_sequences(obj):
    found = []
    for name in ("shortcuts", "shortcut", "key"):
        probe = getattr(obj, name, None)
        if not callable(probe):
            continue
        try:
            value = probe()
        except Exception:
            continue  # nosec
        if isinstance(value, (list, tuple)):
            found.extend(value)
        elif value is not None:
            found.append(value)
    return found


def _is_our_shortcut(obj, own_id):
    own = str(own_id or "")
    if not own:
        return False
    for prop in ("lpt_shortcut_id", "lpt_id", "lpt_sub_id"):
        try:
            value = str(obj.property(prop) or "")
        except Exception:
            value = ""
        if value and value == own:
            return True
    return False


def _holder_label(obj):
    from .toolbar_host import plain_title

    try:
        from qgis.gui import QgsGui

        namer = getattr(QgsGui.shortcutsManager(), "objectName", None)
        if callable(namer):
            named = plain_title(str(namer(obj) or ""))
            if named:
                return named
    except Exception:
        pass  # nosec
    for name in ("text", "toolTip", "whatsThis"):
        probe = getattr(obj, name, None)
        if not callable(probe):
            continue
        try:
            label = plain_title(str(probe() or ""))
        except Exception:
            label = ""
        if label:
            return label
    try:
        return str(obj.objectName() or "") or "QGIS"
    except Exception:
        return "QGIS"


def shortcut_holder(sequence_text, own_id=""):
    """QGIS 快捷键管理器里、以及主窗口上正在响应该组合键的功能名。没有则返回空。

    图层面板工具自己的载体动作（正在改的那一条）不算占用。
    """
    seq = _key_sequence(sequence_text)
    if seq is None:
        return ""
    try:
        from qgis.utils import iface
    except Exception:
        return ""
    window = None
    try:
        window = iface.mainWindow()
    except Exception:
        window = None
    objects = []
    try:
        from qgis.gui import QgsGui

        manager = QgsGui.shortcutsManager()
        found = manager.objectForSequence(seq)
        if found is not None and not _is_our_shortcut(found, own_id):
            try:
                if not str(found.property("lpt_shortcut_id") or ""):
                    return _holder_label(found)
            except Exception:
                return _holder_label(found)
        lister = getattr(manager, "listAll", None)
        if callable(lister):
            try:
                objects.extend(list(lister()))
            except Exception:
                pass  # nosec
    except Exception:
        pass  # nosec
    if window is not None:
        try:
            from qgis.PyQt.QtWidgets import QAction
        except Exception:
            from qgis.PyQt.QtGui import QAction
        try:
            objects.extend(window.findChildren(QAction))
        except Exception:
            pass  # nosec
        shortcut_type = None
        try:
            from qgis.PyQt.QtGui import QShortcut as shortcut_type
        except Exception:
            try:
                from qgis.PyQt.QtWidgets import QShortcut as shortcut_type
            except Exception:
                shortcut_type = None
        if shortcut_type is not None:
            try:
                objects.extend(window.findChildren(shortcut_type))
            except Exception:
                pass  # nosec
    seen = set()
    for obj in objects:
        if obj is None:
            continue
        ident = id(obj)
        if ident in seen:
            continue
        seen.add(ident)
        if _is_our_shortcut(obj, own_id):
            continue
        try:
            if str(obj.property("lpt_shortcut_id") or ""):
                # 另一条自己的快捷键：设置表里会单独报，这里不把它说成 QGIS 的功能。
                continue
        except Exception:
            pass  # nosec
        for other in _object_sequences(obj):
            if _same_sequence(seq, other):
                return _holder_label(obj)
    return ""


def report(parent, title, text, warning=False):
    """结果框。失败用警告图标，做成了用提示图标。"""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    try:
        box.setIcon(qt_attr(QMessageBox, "Warning" if warning else "Information"))
    except Exception:
        pass  # nosec
    ok_flag = qt_attr(QMessageBox, "Ok")
    box.setStandardButtons(ok_flag)
    ok = box.button(ok_flag)
    if ok is not None:
        ok.setText(tr("确定"))
    _REPORT_BOXES.append(box)

    def _drop(*_args):
        try:
            _REPORT_BOXES.remove(box)
        except ValueError:
            pass

    box.finished.connect(_drop)
    box.show()
