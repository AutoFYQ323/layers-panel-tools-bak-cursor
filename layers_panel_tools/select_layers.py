# -*- coding: utf-8 -*-
"""按类型或状态，在图层面板里只打开符合条件的图层开关。"""

from .buttons import make_popup_menu_action, make_popup_tool
from .i18n import tr
from .icons import load_icon
from qgis.core import QgsCoordinateTransform, QgsProject, QgsRectangle

from .scope import geometry_code, is_basemap, is_layer_node, is_raster, is_vector, layer_map_visible, layer_nodes, select_nodes

_BASEMAP_PROP = "lpt_basemap_preset"

_RULES = (
    ("fit_view", False),
    ("-", False),
    ("map_visible", True),
    ("all", False),
    ("invert", False),
    ("-", False),
    ("point", True),
    ("line", True),
    ("polygon", True),
    ("raster", True),
    ("-", False),
    ("nogeometry", True),
    ("broken", True),
    ("editing", True),
)


def make_action(iface):
    tr("批量选择图层")
    tr("按类型或状态，只打开符合条件的图层开关")
    tr("全图居中显示")
    return make_popup_tool(
        iface,
        "lpt:select",
        "LayersPanelToolsSelect",
        "批量选择图层",
        "按类型或状态，只打开符合条件的图层开关",
        load_icon("select"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsSelectMenu",
        "批量选择图层",
        "按类型或状态，只打开符合条件的图层开关",
        load_icon("select"),
        lambda menu: _fill(iface, menu),
    )


def _title(rule):
    if rule == "fit_view":
        return tr("全图居中显示")
    if rule == "all":
        return tr("全选图层")
    if rule == "invert":
        return tr("反选")
    if rule == "map_visible":
        return tr("选中地图可见图层")
    if rule == "point":
        return tr("选中点图层")
    if rule == "line":
        return tr("选中线图层")
    if rule == "polygon":
        return tr("选中面图层")
    if rule == "raster":
        return tr("选中栅格图层")
    if rule == "nogeometry":
        return tr("选中无几何的表")
    if rule == "broken":
        return tr("选中失效图层")
    if rule == "editing":
        return tr("选中正在编辑的图层")
    return rule


def _wants(rule, node, layer, iface):
    if rule == "all":
        return True
    if rule == "map_visible":
        return layer_map_visible(layer, node, iface)
    if layer is None:
        return rule == "broken"
    if rule == "broken":
        try:
            return not bool(layer.isValid())
        except Exception:
            return False
    if rule == "editing":
        checker = getattr(layer, "isEditable", None)
        try:
            return bool(checker()) if callable(checker) else False
        except Exception:
            return False
    return geometry_code(layer) == rule


def pick(iface, rule):
    found = []
    for node in layer_nodes():
        if not is_layer_node(node):
            continue
        try:
            layer = node.layer()
        except Exception:
            layer = None
        if is_basemap(layer):
            continue
        try:
            if _wants(rule, node, layer, iface):
                found.append(node)
        except Exception:
            continue  # nosec
    return found


def _apply_visibility(iface, rule):
    on = []
    off = 0
    for node in layer_nodes():
        if not is_layer_node(node):
            continue
        try:
            layer = node.layer()
        except Exception:
            layer = None
        if is_basemap(layer):
            continue
        try:
            want = _wants(rule, node, layer, iface)
        except Exception:
            want = False
        try:
            node.setItemVisibilityChecked(bool(want))
        except Exception:
            continue  # nosec
        if want:
            on.append(node)
        else:
            off += 1
    select_nodes(iface, on, reveal=True)
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec
    return len(on), off


def _is_basemap_layer(layer):
    if layer is None:
        return True
    if is_raster(layer):
        return True
    try:
        if str(layer.customProperty(_BASEMAP_PROP) or "").strip():
            return True
    except Exception:
        pass  # nosec
    return False


def _layers_for_fit_view():
    found = []
    for layer in QgsProject.instance().mapLayers().values():
        if layer is None or not is_vector(layer):
            continue
        if _is_basemap_layer(layer):
            continue
        try:
            code = geometry_code(layer)
        except Exception:
            code = ""
        if code not in ("point", "line", "polygon"):
            continue
        try:
            if not layer.isValid():
                continue
        except Exception:
            continue  # nosec
        found.append(layer)
    return found


def _fit_point_line_polygon(iface):
    try:
        canvas = iface.mapCanvas()
    except Exception:
        return False
    if canvas is None:
        return False
    try:
        settings = canvas.mapSettings()
        dest = settings.destinationCrs()
    except Exception:
        dest = None
    if dest is None or not dest.isValid():
        try:
            dest = QgsProject.instance().crs()
        except Exception:
            dest = None
    project = QgsProject.instance()
    combined = None
    for layer in _layers_for_fit_view():
        try:
            ext = layer.extent()
        except Exception:
            continue  # nosec
        if ext is None or ext.isEmpty():
            continue
        try:
            layer_crs = layer.crs()
        except Exception:
            layer_crs = None
        if (
            layer_crs is not None
            and layer_crs.isValid()
            and dest is not None
            and dest.isValid()
            and layer_crs != dest
        ):
            try:
                ext = QgsCoordinateTransform(layer_crs, dest, project).transform(ext)
            except Exception:
                continue  # nosec
        if combined is None:
            combined = QgsRectangle(ext)
        else:
            combined.combineExtentWith(ext)
    if combined is None or combined.isEmpty():
        return False
    try:
        combined.scale(1.08)
    except Exception:
        pass  # nosec
    try:
        canvas.setExtent(combined)
        canvas.refresh()
    except Exception:
        return False
    return True


def _invert_visibility(iface):
    flipped = 0
    for node in layer_nodes():
        if not is_layer_node(node):
            continue
        try:
            checked = bool(node.itemVisibilityChecked())
        except Exception:
            try:
                checked = bool(node.isVisible())
            except Exception:
                checked = True
        try:
            node.setItemVisibilityChecked(not checked)
            flipped += 1
        except Exception:
            continue  # nosec
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec
    return flipped


def _fill(iface, menu):
    menu.clear()
    for rule, counted in _RULES:
        if rule == "-":
            menu.addSeparator()
            continue
        action = subcommands.add_to_menu(iface, "lpt:select", menu, "lpt:select:" + str(rule))
        if action is None:
            continue
        if rule == "fit_view":
            action.setEnabled(bool(_layers_for_fit_view()))
        elif counted:
            count = len(pick(iface, rule))
            action.setText("%s  (%d)" % (action.text(), count))
            action.setEnabled(count > 0)


def _run(iface, rule):
    if rule == "fit_view":
        _fit_point_line_polygon(iface)
        return
    if rule == "invert":
        _invert_visibility(iface)
        return
    _apply_visibility(iface, rule)


from . import subcommands

tr("全图居中显示")
tr("全选图层")
tr("反选")
tr("选中地图可见图层")
tr("选中点图层")
tr("选中线图层")
tr("选中面图层")
tr("选中栅格图层")
tr("选中无几何的表")
tr("选中失效图层")
tr("选中正在编辑的图层")
subcommands.register("lpt:select", [
    ("fit_view", "全图居中显示", lambda iface: _run(iface, "fit_view")),
    ("all", "全选图层", lambda iface: _run(iface, "all")),
    ("invert", "反选", lambda iface: _run(iface, "invert")),
    ("map_visible", "选中地图可见图层", lambda iface: _run(iface, "map_visible")),
    ("point", "选中点图层", lambda iface: _run(iface, "point")),
    ("line", "选中线图层", lambda iface: _run(iface, "line")),
    ("polygon", "选中面图层", lambda iface: _run(iface, "polygon")),
    ("raster", "选中栅格图层", lambda iface: _run(iface, "raster")),
    ("nogeometry", "选中无几何的表", lambda iface: _run(iface, "nogeometry")),
    ("broken", "选中失效图层", lambda iface: _run(iface, "broken")),
    ("editing", "选中正在编辑的图层", lambda iface: _run(iface, "editing")),
])