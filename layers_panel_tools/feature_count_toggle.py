# -*- coding: utf-8 -*-
"""图层面板图层名旁的要素数量：全部或所选图层显示/关闭。"""

from qgis.core import QgsVectorLayer

from .buttons import make_popup_menu_action, make_popup_tool
from .i18n import tr
from .icons import load_icon
from .scope import is_layer_node, layer_nodes, selected_nodes, tell


def make_action(iface):
    tr("要素数量")
    tr("在图层面板图层名旁显示或关闭要素数量")
    tr("全部图层显示要素数")
    tr("全部图层关闭要素数")
    tr("所选图层显示要素数")
    tr("所选图层关闭要素数")
    tr("请先在图层面板里选中图层。")
    tr("没有可设置的矢量图层。")
    tr("已在 %d 个图层显示要素数。")
    tr("已在 %d 个图层关闭要素数。")
    return make_popup_tool(
        iface,
        "lpt:feature_count",
        "LayersPanelToolsFeatureCount",
        "要素数量",
        "在图层面板图层名旁显示或关闭要素数量",
        load_icon("feature_count"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsFeatureCountMenu",
        "要素数量",
        "在图层面板图层名旁显示或关闭要素数量",
        load_icon("feature_count"),
        lambda menu: _fill(iface, menu),
    )


def _vector_nodes(iface, selected_only):
    if not selected_only:
        return layer_nodes()
    # 选中分类时 selected_nodes 回落到所属图层，要素数量是图层属性，跟分类走同一层。
    return [node for node in selected_nodes(iface) if is_layer_node(node)]


def _set_show(iface, nodes, on):
    view = iface.layerTreeView()
    model = view.layerTreeModel() if view is not None else None
    value = 1 if on else 0
    changed = 0
    for node in nodes:
        try:
            layer = node.layer()
        except Exception:
            layer = None
        if not isinstance(layer, QgsVectorLayer):
            continue
        try:
            node.setCustomProperty("showFeatureCount", value)
        except Exception:
            continue  # nosec
        changed += 1
        if model is not None:
            try:
                model.refreshLayerLegend(node)
            except Exception:
                pass  # nosec
    return changed


def _fill(iface, menu):
    menu.clear()
    for suffix in ("all_on", "all_off", "selected_on", "selected_off"):
        subcommands.add_to_menu(iface, "lpt:feature_count", menu, "lpt:feature_count:" + suffix)


def _run(iface, selected_only, show):
    nodes = _vector_nodes(iface, selected_only)
    if selected_only and not nodes:
        tell(iface, tr("要素数量"), tr("请先在图层面板里选中图层。"), warning=True)
        return
    count = _set_show(iface, nodes, show)
    if count <= 0:
        tell(iface, tr("要素数量"), tr("没有可设置的矢量图层。"), warning=True)
        return
    if show:
        tell(iface, tr("要素数量"), tr("已在 %d 个图层显示要素数。") % count)
    else:
        tell(iface, tr("要素数量"), tr("已在 %d 个图层关闭要素数。") % count)


from . import subcommands

tr("全部图层显示要素数")
tr("全部图层关闭要素数")
tr("所选图层显示要素数")
tr("所选图层关闭要素数")
subcommands.register("lpt:feature_count", [
    ("all_on", "全部图层显示要素数", lambda iface: _run(iface, False, True)),
    ("all_off", "全部图层关闭要素数", lambda iface: _run(iface, False, False)),
    ("selected_on", "所选图层显示要素数", lambda iface: _run(iface, True, True)),
    ("selected_off", "所选图层关闭要素数", lambda iface: _run(iface, True, False)),
])