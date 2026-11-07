# -*- coding: utf-8 -*-
"""Turn layer labels on or off for every layer, or for the current selection."""

from qgis.PyQt.QtWidgets import QMenu
from qgis.core import QgsPalLayerSettings, QgsVectorLayerSimpleLabeling

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .buttons import make_toolbar_button
from .i18n import tr
from .icons import load_icon
from .scope import geometry_code, is_vector, layers_for_scope, selected_layers, tell


def make_action(iface):
    tr("标注")
    tr("打开或关闭图层标注")
    return make_toolbar_button(
        iface,
        "lpt:labels",
        "LayersPanelToolsLabels",
        "标注",
        "打开或关闭图层标注",
        load_icon("labels"),
        None,
        menu=_build_menu(iface, iface.mainWindow()),
        popup="InstantPopup",
    )


def make_menu_action(iface):
    action = QAction(load_icon("labels"), tr("标注"), iface.mainWindow())
    action.setObjectName("LayersPanelToolsLabelsMenu")
    action.setProperty("lpt_msgid", "标注")
    action.setProperty("lpt_tip_msgid", "打开或关闭图层标注")
    action.setToolTip(tr("打开或关闭图层标注"))
    action.setMenu(_build_menu(iface, iface.mainWindow()))
    return action


def _build_menu(iface, parent):
    menu = QMenu(parent)
    menu.setObjectName("LayersPanelToolsLabelMenu")
    menu.aboutToShow.connect(lambda menu=menu: _fill_menu(iface, menu))
    return menu


def _add_item(menu, text, callback):
    action = QAction(text, menu)
    action.triggered.connect(callback)
    menu.addAction(action)
    return action


def _fill_menu(iface, menu):
    menu.clear()
    subcommands.add_to_menu(iface, "lpt:labels", menu, "lpt:labels:all_on")
    subcommands.add_to_menu(iface, "lpt:labels", menu, "lpt:labels:all_off")
    menu.addSeparator()
    subcommands.add_to_menu(iface, "lpt:labels", menu, "lpt:labels:sel_on")
    subcommands.add_to_menu(iface, "lpt:labels", menu, "lpt:labels:sel_off")
    subcommands.add_to_menu(iface, "lpt:labels", menu, "lpt:labels:sel_toggle")


def _vectors(iface, scope):
    return [layer for layer in layers_for_scope(iface, scope) if is_vector(layer)]


def _is_on(layer):
    try:
        if layer.labeling() is None:
            return False
        return bool(layer.labelsEnabled())
    except Exception:
        return False


def _toggle(iface, scope):
    layers = _vectors(iface, scope)
    _run(iface, any(not _is_on(layer) for layer in layers), scope)


def _run(iface, enabled, scope):
    if scope == "selected" and not selected_layers(iface):
        tell(iface, tr("标注"), tr("图层面板里没有选中图层。"), warning=True)
        return
    layers = _vectors(iface, scope)
    changed, created = _apply(layers, enabled)
    if changed <= 0:
        tell(iface, tr("标注"), tr("没有矢量图层可切换标注。"), warning=True)
    elif enabled:
        if created:
            text = tr("已打开 %d 个图层的标注。其中 %d 个原来没有标注，已按显示字段补上。") % (changed, created)
        else:
            text = tr("已打开 %d 个图层的标注。") % changed
        tell(iface, tr("标注"), text)
    else:
        tell(iface, tr("标注"), tr("已关闭 %d 个图层的标注。") % changed)
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec


def _apply(layers, enabled):
    changed = 0
    created = 0
    for layer in layers:
        made = False
        if enabled and layer.labeling() is None:
            if not _ensure_labeling(layer):
                continue
            made = True
        try:
            layer.setLabelsEnabled(bool(enabled))
        except Exception:
            continue  # nosec
        if made:
            created += 1
        try:
            layer.emitStyleChanged()
        except Exception:
            pass  # nosec
        try:
            layer.triggerRepaint()
        except Exception:
            pass  # nosec
        changed += 1
    return changed, created


def _ensure_labeling(layer):
    if _geometry_kind(layer) in ("unknown", "null"):
        return False
    field = _label_field(layer)
    if not field:
        return False
    settings = QgsPalLayerSettings()
    settings.fieldName = field
    placement = _placement(layer)
    if placement is not None:
        try:
            settings.placement = placement
        except Exception:
            pass  # nosec
    try:
        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    except Exception:
        return False
    return True


def _geometry_kind(layer):
    code = geometry_code(layer)
    if code == "nogeometry":
        return "null"
    if code in ("line", "polygon", "point"):
        return code
    return "unknown"


def _placement(layer):
    kind = _geometry_kind(layer)
    if kind == "line":
        return _pal("Line")
    if kind == "polygon":
        return _pal("Horizontal", "OverPoint")
    return _pal("AroundPoint")


def _pal(*names):
    for name in names:
        value = getattr(QgsPalLayerSettings, name, None)
        if value is not None:
            return value
        nested = getattr(QgsPalLayerSettings, "Placement", None)
        if nested is not None and hasattr(nested, name):
            return getattr(nested, name)
    return None


def _label_field(layer):
    try:
        fields = list(layer.fields())
    except Exception:
        return ""
    names = []
    for field in fields:
        try:
            names.append(field.name())
        except Exception:
            continue  # nosec
    try:
        display = layer.displayField() or ""
    except Exception:
        display = ""
    if display and display in names:
        return display
    folded = {name.lower(): name for name in names}
    for key in ("name", "title", "label", "名称", "id"):
        found = folded.get(key.lower())
        if found:
            return found
    for field in fields:
        try:
            type_name = str(field.typeName() or "").lower()
            numeric = bool(field.isNumeric())
        except Exception:
            continue  # nosec
        if not numeric and any(word in type_name for word in ("string", "text", "char")):
            return field.name()
    return names[0] if names else ""


from . import subcommands

tr("打开全部图层的标注")
tr("关闭全部图层的标注")
tr("打开已选图层的标注")
tr("关闭已选图层的标注")
tr("切换已选图层的标注")
subcommands.register("lpt:labels", [
    ("all_on", "打开全部图层的标注", lambda iface: _run(iface, True, "all")),
    ("all_off", "关闭全部图层的标注", lambda iface: _run(iface, False, "all")),
    ("sel_on", "打开已选图层的标注", lambda iface: _run(iface, True, "selected")),
    ("sel_off", "关闭已选图层的标注", lambda iface: _run(iface, False, "selected")),
    ("sel_toggle", "切换已选图层的标注", lambda iface: _toggle(iface, "selected")),
])