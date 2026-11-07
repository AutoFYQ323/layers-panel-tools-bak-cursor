# -*- coding: utf-8 -*-
"""Local toolbar order, stored in the QGIS settings file."""

import json

from .plugin_settings import flush, plugin_qsettings

_ORDER = "order"
_HIDDEN = "hidden"
_ROWS = "rows"
_TITLES = "titles"
_SHORTCUTS = "shortcuts"


def _load_list(key):
    try:
        raw = plugin_qsettings().value(key, "")
    except Exception:
        return None
    if raw in (None, ""):
        return None
    if not isinstance(raw, str):
        raw = str(raw)
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    return [str(item) for item in data]


def load_order():
    return _load_list(_ORDER)


def load_hidden():
    found = _load_list(_HIDDEN)
    return found if found is not None else []


def load_rows():
    try:
        raw = plugin_qsettings().value(_ROWS, "")
    except Exception:
        return {}
    if raw in (None, ""):
        return {}
    if not isinstance(raw, str):
        raw = str(raw)
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    found = {}
    for key, value in data.items():
        try:
            found[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return found


def load_titles():
    try:
        raw = plugin_qsettings().value(_TITLES, "")
    except Exception:
        return {}
    if raw in (None, ""):
        return {}
    if not isinstance(raw, str):
        raw = str(raw)
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if str(value or "").strip()}


def load_shortcuts():
    try:
        raw = plugin_qsettings().value(_SHORTCUTS, "")
    except Exception:
        return {}
    if raw in (None, ""):
        return {}
    if not isinstance(raw, str):
        raw = str(raw)
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if str(value or "").strip()}


def save(order, hidden, rows, titles, shortcuts=None):
    settings = plugin_qsettings()
    settings.setValue(_ORDER, json.dumps(list(order), ensure_ascii=False))
    settings.setValue(_HIDDEN, json.dumps(list(hidden), ensure_ascii=False))
    settings.setValue(_ROWS, json.dumps(dict(rows), ensure_ascii=False))
    settings.setValue(_TITLES, json.dumps(dict(titles or {}), ensure_ascii=False))
    if shortcuts is not None:
        settings.setValue(_SHORTCUTS, json.dumps(dict(shortcuts), ensure_ascii=False))
    flush()
