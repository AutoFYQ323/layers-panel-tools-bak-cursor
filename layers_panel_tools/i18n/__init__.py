# -*- coding: utf-8 -*-
"""UI language. First launch follows QGIS, then the system locale."""

from qgis.PyQt.QtCore import QLocale, QObject, Qt, pyqtSignal

from .catalog import LANG_ZH, detect_initial_language, known_languages, text_for
from ..plugin_settings import plugin_qsettings, set_value

_KEY = "ui_language"
_hub = None


class LanguageHub(QObject):
    changed = pyqtSignal(str)


def hub():
    global _hub
    if _hub is None:
        _hub = LanguageHub()
    return _hub


def language_changed():
    return hub().changed


def subscribe(widget, callback):
    """Bind a language callback to a widget's lifetime.

    Previously every dialog connected to the global hub signal and never disconnected,
    so switching language after closing a dialog called into a destroyed object.
    Disconnect happens automatically when the widget is destroyed.
    """
    if widget is None or not callable(callback):
        return
    try:
        hub().changed.connect(callback)
        destroyed = getattr(widget, "destroyed", None)
        if destroyed is not None:
            destroyed.connect(lambda *_args, cb=callback: _safe_disconnect(cb))
    except Exception:
        pass  # nosec


def _safe_disconnect(callback):
    try:
        hub().changed.disconnect(callback)
    except Exception:
        pass  # nosec


def _settings():
    return plugin_qsettings()


def current_language():
    stored = ""
    try:
        stored = str(_settings().value(_KEY, "") or "").strip().lower()
    except Exception:
        stored = ""
    if stored in known_languages():
        return stored
    qloc = ""
    try:
        from qgis.core import QgsApplication

        qloc = QgsApplication.locale() or ""
    except Exception:
        qloc = ""
    try:
        sysloc = QLocale.system().name()
    except Exception:
        sysloc = ""
    lang = detect_initial_language(qloc, sysloc)
    try:
        set_value(_KEY, lang)
    except Exception:
        pass  # nosec
    return lang


def set_language(lang):
    text = str(lang or "").strip().lower().replace("_", "-")
    primary = text.split("-", 1)[0]
    if primary not in known_languages():
        primary = LANG_ZH
    try:
        set_value(_KEY, primary)
    except Exception:
        pass  # nosec
    hub().changed.emit(primary)
    return primary


def tr(msgid, *args, **kwargs):
    text = msgid if isinstance(msgid, str) else str(msgid)
    mapped = text_for(current_language(), text)
    if mapped:
        text = mapped
    if args or kwargs:
        try:
            text = text % (args if args else kwargs) if args else text % kwargs
        except Exception:
            pass  # nosec
    return text


def apply_direction(widget):
    """Arabic, once its catalog is complete, lays the plugin windows out from the right."""
    if widget is None:
        return widget
    from ..qt_compat import qt_attr

    rtl = current_language() == "ar"
    widget.setLayoutDirection(qt_attr(Qt, "RightToLeft" if rtl else "LeftToRight"))
    return widget


def localize_button_box(box):
    if box is None:
        return box
    try:
        from qgis.PyQt.QtWidgets import QDialogButtonBox

        from ..qt_compat import qt_attr
    except Exception:
        return box
    mapping = (
        ("Ok", "确定"),
        ("Cancel", "取消"),
        ("Close", "关闭"),
    )
    for flag, msgid in mapping:
        try:
            button = box.button(qt_attr(QDialogButtonBox, flag))
        except Exception:
            button = None
        if button is not None:
            button.setText(tr(msgid))
    return box
