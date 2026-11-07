# -*- coding: utf-8 -*-
"""Show or hide every layer node in the project (basemaps stay untouched)."""

from qgis.core import QgsLayerTree, QgsProject

from .buttons import make_menu_action as build_menu_action, make_toolbar_button
from .i18n import tr
from .icons import load_icon
from .scope import is_basemap, tell


def _walk(node):
    yield node
    try:
        children = list(node.children())
    except Exception:
        children = []
    for child in children:
        yield from _walk(child)


def _set_all(on):
    """Flip every non-basemap layer switch. Returns how many basemaps were left alone."""
    root = QgsProject.instance().layerTreeRoot()
    skipped = 0
    for item in _walk(root):
        try:
            if not QgsLayerTree.isLayer(item):
                continue
        except Exception:
            continue  # nosec
        try:
            layer = item.layer()
        except Exception:
            layer = None
        if is_basemap(layer):
            skipped += 1
            continue
        try:
            item.setItemVisibilityChecked(bool(on))
        except Exception:
            pass  # nosec
    return skipped


def make_action_show(iface):
    tr("显示所有图层")
    tr("打开工程里全部图层的开关（底图不动）")
    return make_toolbar_button(
        iface,
        "lpt:show_all",
        "LayersPanelToolsShowAll",
        "显示所有图层",
        "打开工程里全部图层的开关（底图不动）",
        load_icon("show_all"),
        lambda: _run_show(iface),
    )


def make_action_hide(iface):
    tr("隐藏所有图层")
    tr("关闭工程里全部图层的开关（底图不动）")
    return make_toolbar_button(
        iface,
        "lpt:hide_all",
        "LayersPanelToolsHideAll",
        "隐藏所有图层",
        "关闭工程里全部图层的开关（底图不动）",
        load_icon("hide_all"),
        lambda: _run_hide(iface),
    )


def make_menu_action_show(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsShowAllMenu",
        "显示所有图层",
        "打开工程里全部图层的开关（底图不动）",
        load_icon("show_all"),
        lambda: _run_show(iface),
    )


def make_menu_action_hide(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsHideAllMenu",
        "隐藏所有图层",
        "关闭工程里全部图层的开关（底图不动）",
        load_icon("hide_all"),
        lambda: _run_hide(iface),
    )


def _run_show(iface):
    _set_all(True)
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec
    tell(iface, tr("显示所有图层"), tr("已全部显示。"))


def _run_hide(iface):
    _set_all(False)
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec
    tell(iface, tr("隐藏所有图层"), tr("已全部隐藏。"))
