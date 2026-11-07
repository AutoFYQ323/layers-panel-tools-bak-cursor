# -*- coding: utf-8 -*-
"""Solo: one click shows only the selected layers and remembers the rest; click again to restore."""

from qgis.core import QgsProject

from .buttons import make_menu_action as build_menu_action, make_toolbar_button, report
from .i18n import tr
from .icons import load_icon
from .scope import (
    is_basemap,
    legend_is_on,
    legend_nodes_of_layer,
    legend_rule_key,
    legend_selection,
    selected_layers,
    set_legend_on,
    tree_nodes,
)

_saved = None
_saved_categories = None  # 图层 id → [(分类键, 独显前是否勾选), ...]
_HOOKED = False


def _hook():
    global _HOOKED
    if _HOOKED:
        return
    _HOOKED = True
    try:
        QgsProject.instance().readProject.connect(lambda *_args: reset_solo())
    except Exception:
        pass  # nosec


def make_action(iface):
    tr("独显图层")
    tr("一键只显示所选图层或分类并记住原状态，再点一次还原")
    _hook()
    return make_toolbar_button(
        iface,
        "lpt:solo",
        "LayersPanelToolsSolo",
        "独显图层",
        "一键只显示所选图层或分类并记住原状态，再点一次还原",
        load_icon("solo"),
        lambda: toggle_solo(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsSoloMenu",
        "独显图层",
        "一键只显示所选图层或分类并记住原状态，再点一次还原",
        load_icon("solo"),
        lambda: toggle_solo(iface),
    )


def solo_active():
    return _saved is not None


def reset_solo():
    global _saved, _saved_categories
    _saved = None
    _saved_categories = None


def _node_states():
    root = QgsProject.instance().layerTreeRoot()
    states = {}
    for layer in QgsProject.instance().mapLayers().values():
        if is_basemap(layer):
            continue
        try:
            node = root.findLayer(layer.id())
        except Exception:
            node = None
        if node is None:
            continue
        try:
            states[layer.id()] = bool(node.itemVisibilityChecked())
        except Exception:
            pass  # nosec
    return states


def _category_targets(iface):
    if tree_nodes(iface):
        return []
    found = []
    seen = set()
    for layer, legend in legend_selection(iface):
        if is_basemap(layer):
            continue
        key = legend_rule_key(legend)
        if not key:
            continue
        try:
            ident = (layer.id(), key)
        except Exception:
            continue  # nosec
        if ident in seen:
            continue
        seen.add(ident)
        found.append((layer, key))
    return found


def _snapshot_categories(iface, layers):
    snap = {}
    for layer in layers:
        try:
            layer_id = layer.id()
        except Exception:
            continue  # nosec
        items = []
        for legend in legend_nodes_of_layer(iface, layer):
            key = legend_rule_key(legend)
            if not key:
                continue
            items.append((key, legend_is_on(legend)))
        snap[layer_id] = items
    return snap


def _apply_categories(iface, layer, wanted):
    changed = False
    for legend in legend_nodes_of_layer(iface, layer):
        key = legend_rule_key(legend)
        if key not in wanted:
            continue
        if legend_is_on(legend) == bool(wanted[key]):
            continue
        if set_legend_on(legend, bool(wanted[key])):
            changed = True
    if changed:
        try:
            layer.triggerRepaint()
        except Exception:
            pass  # nosec


def _restore_categories(iface):
    if not _saved_categories:
        return
    for layer_id, items in _saved_categories.items():
        try:
            layer = QgsProject.instance().mapLayer(layer_id)
        except Exception:
            layer = None
        if layer is None:
            continue
        _apply_categories(iface, layer, dict(items))


def _solo_categories(iface, categories):
    global _saved, _saved_categories
    root = QgsProject.instance().layerTreeRoot()
    by_layer = {}
    layers = []
    for layer, key in categories:
        try:
            layer_id = layer.id()
        except Exception:
            continue  # nosec
        if layer_id not in by_layer:
            by_layer[layer_id] = set()
            layers.append(layer)
        by_layer[layer_id].add(key)
    _saved = _node_states()
    _saved_categories = _snapshot_categories(iface, layers)
    keep = set(by_layer)
    for layer_id in _saved:
        try:
            node = root.findLayer(layer_id)
        except Exception:
            node = None
        if node is None:
            continue
        try:
            node.setItemVisibilityChecked(layer_id in keep)
        except Exception:
            pass  # nosec
    for layer in layers:
        try:
            layer_id = layer.id()
        except Exception:
            continue  # nosec
        wanted = {}
        for key, _on in _saved_categories.get(layer_id) or []:
            wanted[key] = key in by_layer.get(layer_id, ())
        _apply_categories(iface, layer, wanted)
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec


def toggle_solo(iface):
    global _saved, _saved_categories
    root = QgsProject.instance().layerTreeRoot()
    if solo_active():
        _restore_categories(iface)
        for layer_id, checked in _saved.items():
            try:
                node = root.findLayer(layer_id)
                if node is not None:
                    node.setItemVisibilityChecked(checked)
            except Exception:
                pass  # nosec
        reset_solo()
        try:
            iface.mapCanvas().refresh()
        except Exception:
            pass  # nosec
        return
    categories = _category_targets(iface)
    if categories:
        _solo_categories(iface, categories)
        return
    picked = selected_layers(iface)
    if not picked:
        report(
            iface.mainWindow(),
            tr("独显图层"),
            tr("请先在图层面板里选中要独显的图层或分类，再点这个按钮。"),
            warning=True,
        )
        return
    keep = set()
    for layer in picked:
        try:
            keep.add(layer.id())
        except Exception:
            pass  # nosec
    _saved = _node_states()
    for layer_id, checked in _saved.items():
        if layer_id in keep:
            continue
        try:
            node = root.findLayer(layer_id)
            if node is not None:
                node.setItemVisibilityChecked(False)
        except Exception:
            pass  # nosec
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec
