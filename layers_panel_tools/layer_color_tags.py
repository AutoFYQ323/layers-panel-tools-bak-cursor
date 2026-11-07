# -*- coding: utf-8 -*-
"""Color tags on layers, shown as colored indicators in the Layers panel."""

from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
from qgis.core import QgsProject

from .buttons import add_item, make_popup_menu_action, make_popup_tool, report
from .i18n import tr
from .icons import load_icon
from .scope import is_basemap, selected_layers, tell

_PROP = "lpt/color_tag"

tr("红")
tr("橙")
tr("黄")
tr("绿")
tr("蓝")
tr("紫")
tr("灰")

_TAGS = (
    ("red", "红", QColor("#e74c3c")),
    ("orange", "橙", QColor("#e67e22")),
    ("yellow", "黄", QColor("#f1c40f")),
    ("green", "绿", QColor("#27ae60")),
    ("blue", "蓝", QColor("#3498db")),
    ("purple", "紫", QColor("#9b59b6")),
    ("gray", "灰", QColor("#7f8c8d")),
)

_INDICATORS = {}
_HOOKED = False


def tag_of(layer):
    if layer is None:
        return ""
    try:
        return str(layer.customProperty(_PROP, "") or "")
    except Exception:
        return ""


def tag_label(tag_id):
    for tid, msgid, _color in _TAGS:
        if tid == tag_id:
            return tr(msgid)
    return tag_id


def tag_color(tag_id):
    for tid, _msgid, color in _TAGS:
        if tid == tag_id:
            return color
    return QColor("#7f8c8d")


def tag_icon(tag_id, size=16):
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    from qgis.PyQt.QtGui import QPainter, QPen

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(tag_color(tag_id))
    painter.setPen(QPen(QColor(60, 60, 60), 1))
    painter.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    painter.end()
    return QIcon(pixmap)


def make_action(iface):
    tr("图层颜色标签")
    tr("给图层打颜色标签（面板里显示彩色小图标），可按颜色筛选")
    _hook(iface)
    return make_popup_tool(
        iface,
        "lpt:layer_tags",
        "LayersPanelToolsLayerTags",
        "图层颜色标签",
        "给图层打颜色标签（面板里显示彩色小图标），可按颜色筛选",
        load_icon("layer_tags"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    _hook(iface)
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsLayerTagsMenu",
        "图层颜色标签",
        "给图层打颜色标签（面板里显示彩色小图标），可按颜色筛选",
        load_icon("layer_tags"),
        lambda menu: _fill(iface, menu),
    )


_HOOKED_ROOT = [None]


def _hook(iface):
    global _HOOKED
    first = not _HOOKED
    _HOOKED = True
    if first:
        project = QgsProject.instance()
        # 打开工程文件走 readProject；新建空白工程只发 cleared，不发 readProject。
        for signal_name in ("readProject", "cleared"):
            try:
                getattr(project, signal_name).connect(lambda *_a: _rebind(iface))
            except Exception:
                pass  # nosec
    _rebind(iface)


def _rebind(iface):
    """把 addedChildren 挂到当前工程的 root 上。工程切换后 root 会换，旧连接不再有效。"""
    try:
        root = QgsProject.instance().layerTreeRoot()
    except Exception:
        return
    if root is None or root is _HOOKED_ROOT[0]:
        _after_bind(iface)
        return
    try:
        root.addedChildren.connect(lambda *_args: refresh_indicators(iface))
    except Exception:
        pass  # nosec
    _HOOKED_ROOT[0] = root
    _after_bind(iface)


def _after_bind(iface):
    try:
        refresh_indicators(iface)
    except Exception:
        pass  # nosec


def refresh_indicators(iface):
    """Re-create panel indicators from saved tags (project reopened, layers added)."""
    try:
        from qgis.gui import QgsLayerTreeViewIndicator
    except ImportError:
        return
    view = None
    try:
        view = iface.layerTreeView()
    except Exception:
        view = None
    if view is None:
        return
    root = QgsProject.instance().layerTreeRoot()
    alive = set()
    for layer in QgsProject.instance().mapLayers().values():
        try:
            layer_id = layer.id()
            node = root.findLayer(layer_id)
        except Exception:
            continue  # nosec
        tag = tag_of(layer)
        old = _INDICATORS.get(layer_id)
        if not tag or node is None:
            if old is not None and node is not None:
                try:
                    view.removeIndicator(node, old)
                except Exception:
                    pass  # nosec
            _INDICATORS.pop(layer_id, None)
            continue
        alive.add(layer_id)
        if old is not None:
            try:
                view.removeIndicator(node, old)
            except Exception:
                pass  # nosec
        try:
            indicator = QgsLayerTreeViewIndicator()
            indicator.setIcon(tag_icon(tag))
            indicator.setToolTip(tr("颜色标签：%s") % tag_label(tag))
            view.addIndicator(node, indicator)
            _INDICATORS[layer_id] = indicator
        except Exception:
            _INDICATORS.pop(layer_id, None)
    for layer_id in list(_INDICATORS):
        if layer_id not in alive:
            _INDICATORS.pop(layer_id, None)


def _fill(iface, menu):
    menu.clear()
    sub = menu.addMenu(tr("为所选图层设标签"))
    for tag_id, msgid, _color in _TAGS:
        add_item(sub, tr(msgid), lambda tag=tag_id: _set_tag(iface, tag))
    menu.addSeparator()
    subcommands.add_to_menu(iface, "lpt:layer_tags", menu, "lpt:layer_tags:clear")
    menu.addSeparator()
    only = menu.addMenu(tr("只打开该颜色的图层"))
    for tag_id, msgid, _color in _TAGS:
        add_item(only, tr(msgid), lambda tag=tag_id: _filter_visible(iface, tag))
    subcommands.add_to_menu(iface, "lpt:layer_tags", menu, "lpt:layer_tags:unfilter")


def _set_tag(iface, tag_id):
    layers = selected_layers(iface)
    if not layers:
        report(iface.mainWindow(), tr("图层颜色标签"), tr("请先在图层面板里选中图层。"), warning=True)
        return
    for layer in layers:
        try:
            if tag_id:
                layer.setCustomProperty(_PROP, tag_id)
            else:
                layer.removeCustomProperty(_PROP)
        except Exception:
            pass  # nosec
    refresh_indicators(iface)


def _filter_visible(iface, tag_id):
    root = QgsProject.instance().layerTreeRoot()
    for layer in QgsProject.instance().mapLayers().values():
        if is_basemap(layer):
            continue
        try:
            node = root.findLayer(layer.id())
        except Exception:
            node = None
        if node is None:
            continue
        on = tag_of(layer) == tag_id
        try:
            node.setItemVisibilityChecked(on)
        except Exception:
            pass  # nosec


def _show_all(iface):
    root = QgsProject.instance().layerTreeRoot()
    for layer in QgsProject.instance().mapLayers().values():
        if is_basemap(layer):
            continue
        try:
            node = root.findLayer(layer.id())
            if node is not None:
                node.setItemVisibilityChecked(True)
        except Exception:
            pass  # nosec


from . import subcommands

tr("清除所选图层的标签")
tr("取消颜色筛选（全部图层开）")
subcommands.register("lpt:layer_tags", [
    ("clear", "清除所选图层的标签", lambda iface: _set_tag(iface, "")),
    ("unfilter", "取消颜色筛选（全部图层开）", lambda iface: _show_all(iface)),
])