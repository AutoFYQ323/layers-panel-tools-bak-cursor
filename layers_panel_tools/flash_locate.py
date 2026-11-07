# -*- coding: utf-8 -*-
"""Flash locate: blink layer switches, or flash features on the map — one button, shared interval."""

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QColor

from qgis.core import Qgis, QgsFeatureRequest, QgsGeometry, QgsProject, QgsVectorLayer, QgsWkbTypes
from qgis.gui import QgsRubberBand

from .buttons import add_item, make_menu_action as build_menu_action, make_popup_menu_action, make_popup_tool, report
from .i18n import tr
from .icons import load_icon
from .scope import (
    is_basemap,
    legend_is_on,
    legend_rule_key,
    legend_selection,
    selected_layers,
    set_legend_on,
    tree_nodes,
)

_CAP = 300
_CAP_TOTAL = 3000
_INTERVALS = (250, 500, 1000, 2000)

_timer = None
_mode = ""  # "" 关闭；"visibility" 开关闪烁；"features" 要素闪烁
_layers = []
_original = {}
_iface = None
_interval = 500
_actions = []  # 闪烁时跟着换图标的按钮（工具条 + 菜单两套 action）
_icon_flip = False
_filters = {}  # 图层 id → 分类过滤表达式；选中分类时只闪该分类
_legend_original = {}  # (图层 id, 分类键) → 闪烁前的勾选
_bands = []  # 地图上正在闪的橡皮筋。QGIS 自带的 flash 后一次会盖掉前一次。
_band_gen = 0


def _load_interval():
    """读电脑通用配置里记住的闪烁间隔。"""
    try:
        from .plugin_settings import plugin_qsettings

        value = int(plugin_qsettings().value("flash_interval", 0) or 0)
        if value in _INTERVALS:
            return value
    except Exception:
        pass  # nosec
    return 500


_interval = _load_interval()
_HOOKED = [False]


def _hook_project():
    """切工程时停掉闪烁：旧工程的图层节点已消失，继续闪只会报错。"""
    if _HOOKED[0]:
        return
    _HOOKED[0] = True
    try:
        QgsProject.instance().readProject.connect(lambda *_args: stop_flash(restore=False))
    except Exception:
        pass  # nosec


def make_action(iface):
    tr("闪烁定位")
    tr("闪烁所选图层或分类的开关，或让对应要素在地图上反复闪亮，可调间隔、一键停止")
    _hook_project()
    action = make_popup_tool(
        iface,
        "lpt:flash",
        "LayersPanelToolsFlash",
        "闪烁定位",
        "闪烁所选图层或分类的开关，或让对应要素在地图上反复闪亮，可调间隔、一键停止",
        load_icon("flash"),
        lambda menu: _fill(iface, menu),
    )
    _register(action)
    return action


def make_menu_action(iface):
    _hook_project()
    action = make_popup_menu_action(
        iface,
        "LayersPanelToolsFlashMenu",
        "闪烁定位",
        "闪烁所选图层或分类的开关，或让对应要素在地图上反复闪亮，可调间隔、一键停止",
        load_icon("flash"),
        lambda menu: _fill(iface, menu),
    )
    _register(action)
    return action


def _register(action):
    if action is not None and action not in _actions:
        _actions.append(action)


def _apply_icon(icon):
    """Swap the button icon; QToolButton inside QWidgetAction needs it too."""
    for action in list(_actions):
        try:
            action.setIcon(icon)
        except (RuntimeError, AttributeError):
            continue
        getter = getattr(action, "defaultWidget", None)
        widget = None
        if callable(getter):
            try:
                widget = getter()
            except RuntimeError:
                widget = None
        if widget is not None:
            try:
                widget.setIcon(icon)
            except RuntimeError:
                pass


def is_flashing():
    return _timer is not None and _timer.isActive()


def stop_flash(restore=True):
    global _timer, _mode, _layers, _original, _icon_flip, _filters, _legend_original, _band_gen
    _band_gen += 1
    _clear_bands()
    if _timer is not None:
        try:
            _timer.stop()
        except Exception:
            pass  # nosec
    _timer = None
    _mode = ""
    _layers = []
    _icon_flip = False
    _apply_icon(load_icon("flash"))
    if restore:
        root = QgsProject.instance().layerTreeRoot()
        for layer_id, checked in _original.items():
            try:
                node = root.findLayer(layer_id)
                if node is not None:
                    node.setItemVisibilityChecked(checked)
            except Exception:
                pass  # nosec
        _restore_legend_checks()
    _original = {}
    _filters = {}
    _legend_original = {}


def _expr_text(result):
    if isinstance(result, tuple):
        ok = bool(result[1]) if len(result) > 1 else True
        if not ok:
            return ""
        return str(result[0] or "").strip()
    return str(result or "").strip()


def _legend_expression(layer, legend):
    """把选中的分类图例节点翻译成过滤表达式；翻不出来返回 None（闪整个图层）。"""
    key = legend_rule_key(legend)
    if not key:
        return None
    try:
        renderer = layer.renderer()
    except Exception:
        return None
    if renderer is None:
        return None
    func = getattr(renderer, "legendKeyToExpression", None)
    if callable(func):
        result = None
        try:
            result = func(key, layer)
        except TypeError:
            try:
                result = func(key)
            except Exception:
                result = None
        except Exception:
            result = None
        expr = _expr_text(result)
        if expr:
            return expr
    return _expression_from_renderer(renderer, key)


def _expression_from_renderer(renderer, key):
    """legendKeyToExpression 不可用时，按分类 uuid / 规则键自己拼过滤。"""
    from qgis.core import QgsExpression

    try:
        kind = renderer.type()
    except Exception:
        return None
    if kind == "categorized":
        try:
            attr = renderer.classAttribute() or ""
        except Exception:
            attr = ""
        if not attr:
            return None
        try:
            categories = list(renderer.categories())
        except Exception:
            categories = []
        for category in categories:
            try:
                uid = str(category.uuid() or "")
            except Exception:
                uid = ""
            if uid != key:
                continue
            try:
                value = category.value()
            except Exception:
                return None
            try:
                return QgsExpression.createFieldEqualityExpression(attr, value)
            except Exception:
                column = QgsExpression.quotedColumnRef(attr)
                if value is None:
                    return "%s IS NULL" % column
                return "%s = %s" % (column, QgsExpression.quotedValue(value))
        return None
    if kind == "RuleRenderer":
        try:
            rule = renderer.rootRule().findRuleByKey(key)
            expr = (rule.filterExpression() or "").strip() if rule is not None else ""
        except Exception:
            expr = ""
        return expr or None
    if kind == "graduatedSymbol":
        try:
            attr = renderer.classAttribute() or ""
        except Exception:
            attr = ""
        if not attr:
            return None
        label = None
        try:
            items = list(renderer.legendSymbolItems())
        except Exception:
            items = []
        for item in items:
            try:
                if str(item.ruleKey() or "") == key:
                    label = item.label()
                    break
            except Exception:
                continue  # nosec
        if label is None:
            return None
        try:
            ranges = list(renderer.ranges())
        except Exception:
            ranges = []
        for item in ranges:
            try:
                item_label = item.label() or ""
                lower = item.lowerValue()
                upper = item.upperValue()
            except Exception:
                continue  # nosec
            if item_label != label:
                continue
            column = QgsExpression.quotedColumnRef(attr)
            return "(%s >= %s AND %s <= %s)" % (
                column,
                QgsExpression.quotedValue(lower),
                column,
                QgsExpression.quotedValue(upper),
            )
    return None


def _legend_filters(iface):
    """选中的图例（分类）节点 → {图层 id: 过滤表达式}。同一图层选了多个分类用 OR 连接。"""
    filters = {}
    try:
        pairs = legend_selection(iface)
    except Exception:
        pairs = []
    for layer, legend in pairs:
        expr = _legend_expression(layer, legend)
        if expr is None:
            continue
        filters.setdefault(layer.id(), []).append("(%s)" % expr)
    combined = {}
    for layer_id, parts in filters.items():
        combined[layer_id] = " OR ".join(parts)
    return combined


def _remember_layer(layer, found, seen):
    if layer is None or is_basemap(layer):
        return
    try:
        layer_id = layer.id()
    except Exception:
        return
    if not layer_id or layer_id in seen:
        return
    seen.add(layer_id)
    found.append(layer)


def _feature_flash_layers(iface):
    """图层面板里选中的图层，再加上工程里凡是有选中要素的图层。

    QGIS 的当前图层只有一个。在别的图层上选过的要素也要一起闪。
    """
    found = []
    seen = set()
    for layer in selected_layers(iface):
        _remember_layer(layer, found, seen)
    try:
        project_layers = list(QgsProject.instance().mapLayers().values())
    except Exception:
        project_layers = []
    for layer in project_layers:
        if not isinstance(layer, QgsVectorLayer):
            continue
        try:
            count = layer.selectedFeatureCount()
        except Exception:
            continue  # nosec
        if count:
            _remember_layer(layer, found, seen)
    return found


def _category_targets(iface):
    """只选了分类、没选图层行时，返回 [(图层, 图例, 分类键), ...]。"""
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
        found.append((layer, legend, key))
    return found


def _restore_legend_checks():
    from .scope import legend_nodes_of_layer

    if not _legend_original or _iface is None:
        return
    touched = {}
    for (layer_id, key), on in _legend_original.items():
        layer = None
        try:
            layer = QgsProject.instance().mapLayer(layer_id)
        except Exception:
            layer = None
        if layer is None:
            continue
        for legend in legend_nodes_of_layer(_iface, layer):
            if legend_rule_key(legend) != key:
                continue
            set_legend_on(legend, on)
            break
        touched[layer_id] = layer
    for layer in touched.values():
        try:
            layer.triggerRepaint()
        except Exception:
            pass  # nosec


def _start_categories(iface, mode, categories):
    global _timer, _mode, _layers, _filters, _iface, _legend_original
    _iface = iface
    layers = []
    seen = set()
    for layer, legend, key in categories:
        try:
            layer_id = layer.id()
        except Exception:
            continue  # nosec
        if layer_id not in seen:
            seen.add(layer_id)
            layers.append((layer_id, layer))
        if mode == "visibility":
            _legend_original[(layer_id, key)] = legend_is_on(legend)
    if mode != "visibility":
        for layer in _feature_flash_layers(iface):
            try:
                layer_id = layer.id()
            except Exception:
                continue  # nosec
            if layer_id in seen:
                continue
            seen.add(layer_id)
            layers.append((layer_id, layer))
    _layers = layers
    if not _layers:
        report(iface.mainWindow(), tr("闪烁定位"), tr("请先在图层面板里选中要闪烁的图层或分类。"), warning=True)
        return
    if mode == "visibility":
        _mode = "legend"
        _tick_legend()
    else:
        _mode = "features"
        _filters = _legend_filters(iface)
        _tick_features()
    _timer = QTimer()
    _timer.timeout.connect(_tick)
    _timer.start(_interval)


def _start(iface, mode):
    global _timer, _mode, _layers, _original, _iface, _filters
    stop_flash()
    categories = _category_targets(iface)
    if categories:
        _start_categories(iface, mode, categories)
        return
    filters = _legend_filters(iface) if mode == "features" else {}
    if mode == "features":
        picked = _feature_flash_layers(iface)
    else:
        picked = [layer for layer in selected_layers(iface) if not is_basemap(layer)]
    if not picked:
        report(iface.mainWindow(), tr("闪烁定位"), tr("请先在图层面板里选中要闪烁的图层或分类。"), warning=True)
        return
    _iface = iface
    _mode = mode
    _layers = []
    for layer in picked:
        try:
            _layers.append((layer.id(), layer))
        except Exception:
            continue  # nosec
    if not _layers:
        report(iface.mainWindow(), tr("闪烁定位"), tr("所选内容里没有可用图层。"), warning=True)
        return
    _filters = filters
    if mode == "visibility":
        root = QgsProject.instance().layerTreeRoot()
        for layer_id, _layer in _layers:
            try:
                node = root.findLayer(layer_id)
                if node is not None:
                    _original[layer_id] = bool(node.itemVisibilityChecked())
            except Exception:
                _original[layer_id] = True
        _tick_visibility()
    else:
        _tick_features()
    _timer = QTimer()
    _timer.timeout.connect(_tick)
    _timer.start(_interval)


def _tick():
    global _icon_flip
    if _mode == "visibility":
        _tick_visibility()
    elif _mode == "legend":
        _tick_legend()
    elif _mode == "features":
        _tick_features()
    if _timer is not None and _timer.isActive():
        _icon_flip = not _icon_flip
        _apply_icon(load_icon("flash_blink") if _icon_flip else load_icon("flash"))


def _tick_visibility():
    global _layers
    if not _layers:
        stop_flash()
        return
    root = QgsProject.instance().layerTreeRoot()
    for layer_id, _layer in list(_layers):
        try:
            node = root.findLayer(layer_id)
        except Exception:
            node = None
        if node is None:
            _layers = [(lid, lay) for lid, lay in _layers if lid != layer_id]
            continue
        try:
            node.setItemVisibilityChecked(not node.itemVisibilityChecked())
        except Exception:
            pass  # nosec
    if not _layers:
        stop_flash()


def _tick_legend():
    from .scope import legend_nodes_of_layer

    if not _legend_original:
        stop_flash()
        return
    touched = {}
    for layer_id, key in list(_legend_original):
        layer = None
        try:
            layer = QgsProject.instance().mapLayer(layer_id)
        except Exception:
            layer = None
        if layer is None or _iface is None:
            continue
        for legend in legend_nodes_of_layer(_iface, layer):
            if legend_rule_key(legend) != key:
                continue
            set_legend_on(legend, not legend_is_on(legend))
            break
        touched[layer_id] = layer
    for layer in touched.values():
        try:
            layer.triggerRepaint()
        except Exception:
            pass  # nosec
    if not touched:
        stop_flash()


def _tick_features():
    if _bands:
        _clear_bands()
        return
    canvas = None
    try:
        canvas = _iface.mapCanvas()
    except Exception:
        canvas = None
    if canvas is None or not _show_bands(canvas, _layers, _filters, False):
        stop_flash()


def _flash_once(iface, only_selected):
    global _band_gen
    picked = _feature_flash_layers(iface)
    filters = _legend_filters(iface)
    canvas = None
    try:
        canvas = iface.mapCanvas()
    except Exception:
        canvas = None
    if canvas is None or not picked:
        report(iface.mainWindow(), tr("闪烁定位"), tr("请先在图层面板里选中要闪烁的图层或分类。"), warning=True)
        return
    _band_gen += 1
    token = _band_gen
    _clear_bands()
    if not _show_bands(canvas, picked, filters, only_selected):
        report(
            iface.mainWindow(),
            tr("闪烁定位"),
            tr("没有闪出任何要素：请先在要素上框选，或改用「闪烁所选图层的要素」。"),
            warning=True,
        )
        return

    def _hide(expected=token):
        if _band_gen != expected or is_flashing():
            return
        _clear_bands()

    QTimer.singleShot(max(_interval, 400), _hide)


def _feature_ids(layer, only_selected, expression=None):
    ids = []
    try:
        if only_selected or layer.selectedFeatureCount():
            ids = list(layer.selectedFeatureIds())
    except Exception:
        ids = []
    if ids or (only_selected and not expression):
        return ids
    # 没有选中的要素：扫全图层；带分类表达式时只扫选中的分类。
    try:
        request = QgsFeatureRequest()
        if expression:
            request = request.setFilterExpression(expression)
        found = []
        for feature in layer.getFeatures(request):
            found.append(feature.id())
            if len(found) >= _CAP:
                break
        return found
    except Exception:
        if not expression:
            return []
        return _feature_ids(layer, False, None)  # 表达式不成立 → 退回整个图层


def _clone_geometry(geometry):
    """要素遍历会复用同一个几何对象，不复制的话列表里最后只剩最后一个点。"""
    if geometry is None:
        return None
    try:
        if geometry.isNull() or geometry.isEmpty():
            return None
    except Exception:
        return None
    try:
        cloned = QgsGeometry()
        cloned.fromWkb(geometry.asWkb())
        if not cloned.isNull() and not cloned.isEmpty():
            return cloned
    except Exception:
        pass  # nosec
    try:
        cloned = QgsGeometry(geometry)
        if cloned.isEmpty():
            return None
        return cloned
    except Exception:
        return None


def _geometry_kind(geometry):
    try:
        kind = QgsWkbTypes.geometryType(geometry.wkbType())
    except Exception:
        return None
    if kind not in (Qgis.GeometryType.Point, Qgis.GeometryType.Line, Qgis.GeometryType.Polygon):
        return None
    return kind


def _layer_geometries(layer, only_selected, expression, limit):
    found = []
    if limit <= 0:
        return found
    if isinstance(layer, QgsVectorLayer) and layer.isValid():
        ids = _feature_ids(layer, only_selected, expression)[:limit]
        if not ids:
            return found
        try:
            request = QgsFeatureRequest().setFilterFids(ids)
            try:
                request.setNoAttributes()
            except Exception:
                pass  # nosec
            for feature in layer.getFeatures(request):
                geometry = _clone_geometry(feature.geometry())
                if geometry is None:
                    continue
                found.append(geometry)
                if len(found) >= limit:
                    break
        except Exception:
            return found
        return found
    try:
        extent = layer.extent()
        if extent is None or extent.isEmpty():
            return found
        geometry = _clone_geometry(QgsGeometry.fromRect(extent))
        if geometry is not None:
            found.append(geometry)
    except Exception:
        return found
    return found


def _clear_bands():
    global _bands
    bands = _bands
    _bands = []
    for band in bands:
        try:
            band.reset()
        except Exception:
            pass  # nosec
        try:
            scene = band.scene()
            if scene is not None:
                scene.removeItem(band)
        except Exception:
            pass  # nosec
        try:
            band.deleteLater()
        except Exception:
            pass  # nosec


def _show_bands(canvas, layers, filters, only_selected):
    """点、线、面各用一条橡皮筋。QGIS 的 flashGeometries 只留住最后一笔。"""
    global _bands
    grouped = {}
    room = _CAP_TOTAL
    for item in layers:
        if room <= 0:
            break
        layer = item[1] if isinstance(item, (tuple, list)) else item
        try:
            layer_id = layer.id()
        except Exception:
            continue  # nosec
        expression = filters.get(layer_id) if filters else None
        batch = _layer_geometries(layer, only_selected, expression, min(_CAP, room))
        for geometry in batch:
            kind = _geometry_kind(geometry)
            if kind is None:
                continue
            grouped.setdefault(kind, []).append((geometry, layer))
            room -= 1
            if room <= 0:
                break
    if not grouped:
        return 0
    shown = 0
    for kind, pairs in grouped.items():
        try:
            band = QgsRubberBand(canvas, kind)
            band.setColor(QColor(220, 20, 20, 230))
            band.setFillColor(QColor(220, 20, 20, 70))
            band.setWidth(3)
            band.setIconSize(14)
        except Exception:
            continue  # nosec
        added = 0
        for geometry, layer in pairs:
            try:
                band.addGeometry(geometry, layer, False)
                added += 1
            except Exception:
                continue  # nosec
        if not added:
            try:
                band.reset()
                band.deleteLater()
            except Exception:
                pass  # nosec
            continue
        try:
            band.updatePosition()
            band.show()
        except Exception:
            pass  # nosec
        _bands.append(band)
        shown += added
    return shown


def _fill(iface, menu):
    menu.clear()
    if is_flashing():
        subcommands.add_to_menu(iface, "lpt:flash", menu, "lpt:flash:stop_restore")
        subcommands.add_to_menu(iface, "lpt:flash", menu, "lpt:flash:stop_keep")
    else:
        subcommands.add_to_menu(iface, "lpt:flash", menu, "lpt:flash:blink_switches")
        subcommands.add_to_menu(iface, "lpt:flash", menu, "lpt:flash:blink_features")
        subcommands.add_to_menu(iface, "lpt:flash", menu, "lpt:flash:flash_once")
    sub = menu.addMenu(tr("闪烁间隔"))
    for value in _INTERVALS:
        text = tr("%d 毫秒") % value
        if value == _interval:
            text = "√ " + text
        add_item(sub, text, lambda v=value: _set_interval(v))


def _set_interval(value):
    global _interval
    _interval = int(value)
    try:
        from .plugin_settings import set_value

        set_value("flash_interval", _interval)
    except Exception:
        pass  # nosec
    if is_flashing():
        try:
            _timer.setInterval(_interval)
        except Exception:
            pass  # nosec


from . import subcommands

tr("闪烁所选图层（自动开关闪烁）")
tr("闪烁所选图层的要素（地图上反复闪亮）")
tr("闪一下所选要素")
tr("停止闪烁（开关还原）")
tr("停止并保持当前状态")
subcommands.register("lpt:flash", [
    ("blink_switches", "闪烁所选图层（自动开关闪烁）", lambda iface: _start(iface, "visibility")),
    ("blink_features", "闪烁所选图层的要素（地图上反复闪亮）", lambda iface: _start(iface, "features")),
    ("flash_once", "闪一下所选要素", lambda iface: _flash_once(iface, True)),
    ("stop_restore", "停止闪烁（开关还原）", lambda iface: stop_flash(True)),
    ("stop_keep", "停止并保持当前状态", lambda iface: stop_flash(False)),
])