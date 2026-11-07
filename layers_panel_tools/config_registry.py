# -*- coding: utf-8 -*-
"""Settings key registry for Layers Panel Tools.

Rules:
- Only store what should travel with the machine, never tied to one QGIS project.
- Project-scoped data (organize snapshots, layer color tags) lives in the project file
  via customProperty and must NOT appear here.
- Transient run state (solo restore list, running flicker, find-panel checkboxes)
  is never persisted.

Keys are registered here so migration, export, reset, and support can rely on one list.
"""

import json

from .plugin_settings import plugin_qsettings

# key -> (owner feature, required, note). Notes stay English-only: they never reach the UI.
KEYS = {
    "order": ("toolbar settings", True, "toolbar button order"),
    "hidden": ("toolbar settings", True, "buttons that stay unchecked"),
    "rows": ("toolbar settings", True, "which row a button sits on"),
    "titles": ("toolbar settings", True, "custom button titles"),
    "shortcuts": ("toolbar settings", True, "per-button keyboard shortcuts"),
    "ui_language": ("language", True, "interface language"),
    "basemap_presets2": ("basemap presets", True, "preset list: url, name, tag"),
    "switch_book": ("visibility schemes", True, "per-project layer and category switches"),
    "opacity_scope": ("opacity", False, "last scope choice, convenience only"),
    "flash_interval": ("flash locate", False, "last flicker interval, convenience only"),
}

# Convenience keys: losing them costs nothing; reset clears them too.
OPTIONAL = ("opacity_scope", "flash_interval")

# Project-scoped data that must never be written to the ini file (documentation for support).
PROJECT_SCOPED = ("lpt/snapshots", "lpt/color_tag")


def key_names():
    return tuple(KEYS)


def reset_all():
    """Clear every Layers Panel Tools key in the ini file (reset button or troubleshooting)."""
    settings = plugin_qsettings()
    for name in KEYS:
        try:
            settings.remove(name)
        except Exception:
            pass  # nosec
    try:
        settings.sync()
    except Exception:
        pass  # nosec


def human_size(count):
    """Bytes as a short readable string (re-exported for the CSV export)."""
    from .file_logic import human_size as _human

    return _human(count)


def dump():
    """Readable snapshot of current settings, handy when a user reports a problem."""
    found = {}
    settings = plugin_qsettings()
    for name in KEYS:
        try:
            found[name] = settings.value(name, "")
        except Exception:
            found[name] = ""
    return json.dumps(found, ensure_ascii=False, indent=2)


def self_check():
    """Key-list sanity checks with no Qt dependency."""
    assert "order" in KEYS  # nosec
    assert "ui_language" in KEYS  # nosec
    for name in OPTIONAL:
        assert name in KEYS, name  # nosec
    for name in KEYS:
        _owner, required, note = KEYS[name]
        assert isinstance(required, bool), name  # nosec
        assert note, name  # nosec
    assert all(not str(item).startswith(("lpt/", "LayersPanelTools/")) for item in KEYS)  # nosec
    return True
