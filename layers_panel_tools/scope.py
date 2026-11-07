# -*- coding: utf-8 -*-
"""Layers chosen from the whole project or from the Layers panel selection."""

import os

from qgis.PyQt.QtCore import QItemSelectionModel, QUrl
from qgis.core import (
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsLayerTree,
    QgsProject,
    QgsProviderRegistry,
    QgsRasterLayer,
    QgsVectorLayer,
)

from .qt_compat import enum_int, qt_attr


def tell(iface, title, text, warning=False):
    """做成了、没做成，都不从这里弹框。必须让人看见的拒绝由调用处直接 report()。"""
    return


def all_layers():
    try:
        return list(QgsProject.instance().mapLayers().values())
    except Exception:
        return []


def _add_layer(layer, found, seen):
    if layer is None:
        return
    try:
        layer_id = layer.id()
    except Exception:
        return
    if not layer_id or layer_id in seen:
        return
    seen.add(layer_id)
    found.append(layer)


def _collect(node, found, seen):
    layer_fn = getattr(node, "layer", None)
    if callable(layer_fn):
        try:
            layer = layer_fn()
        except Exception:
            layer = None
        if layer is not None:
            _add_layer(layer, found, seen)
            return
    find_layers = getattr(node, "findLayers", None)
    if callable(find_layers):
        try:
            children = list(find_layers())
        except Exception:
            children = []
        for child in children:
            _collect(child, found, seen)
        return
    children_fn = getattr(node, "children", None)
    if callable(children_fn):
        try:
            children = list(children_fn())
        except Exception:
            children = []
        for child in children:
            _collect(child, found, seen)


def selected_layers(iface):
    found = []
    seen = set()
    view = None
    try:
        view = iface.layerTreeView()
    except Exception:
        view = None
    if view is None:
        return found
    try:
        nodes = list(view.selectedNodes())
    except Exception:
        nodes = []
    for node in nodes:
        _collect(node, found, seen)
    if found:
        return found
    try:
        for layer in view.selectedLayers():
            _add_layer(layer, found, seen)
    except Exception:
        pass  # nosec
    if found:
        return found
    # 选中了符号化的某个分类（图例节点）：QGIS 不把它当图层选择，这里映射回图层。
    try:
        for layer, _legend in legend_selection(iface):
            _add_layer(layer, found, seen)
    except Exception:
        pass  # nosec
    return found


def _legend_at(view, index):
    """图层面板的选中索引在代理模型上。图例节点要用视图自己的 index2legendNode，不能问代理模型。"""
    try:
        if index is None or not index.isValid():
            return None
    except Exception:
        return None
    try:
        legend = view.index2legendNode(index)
    except Exception:
        legend = None
    if legend is not None:
        return legend
    try:
        model = view.layerTreeModel()
        proxy = view.proxyModel()
        source = proxy.mapToSource(index)
        return model.index2legendNode(source)
    except Exception:
        return None


def _layer_of_legend(legend):
    try:
        node = legend.layerNode()
        return node.layer() if node is not None else None
    except Exception:
        return None


def legend_rule_key(legend):
    """分类在渲染器里的键。QGIS 3.40 的图例节点没有 ruleKey()，键在 RuleKeyRole 上。"""
    if legend is None:
        return ""
    try:
        from qgis.core import QgsLayerTreeModelLegendNode

        role = QgsLayerTreeModelLegendNode.RuleKeyRole
    except Exception:
        return ""
    try:
        value = legend.data(role)
    except Exception:
        return ""
    if value is None:
        return ""
    return str(value).strip()


def legend_is_on(legend):
    from qgis.PyQt.QtCore import Qt

    role = qt_attr(Qt, "CheckStateRole")
    checked = enum_int(qt_attr(Qt, "Checked"), 2)
    try:
        state = legend.data(role)
    except Exception:
        return True
    return enum_int(state, checked) == checked


def set_legend_on(legend, on):
    """勾上或取消一个分类。先走图例节点自己的勾选，失败再写渲染器。"""
    from qgis.PyQt.QtCore import Qt

    role = qt_attr(Qt, "CheckStateRole")
    flag = qt_attr(Qt, "Checked") if on else qt_attr(Qt, "Unchecked")
    for value in (flag, enum_int(flag, 2 if on else 0)):
        try:
            if legend.setData(value, role):
                return True
        except Exception:
            continue  # nosec
    return _set_legend_on_renderer(legend, on)


def _set_legend_on_renderer(legend, on):
    key = legend_rule_key(legend)
    layer = _layer_of_legend(legend)
    if not key or layer is None:
        return False
    try:
        renderer = layer.renderer()
    except Exception:
        return False
    writer = getattr(renderer, "checkLegendSymbolItem", None)
    if not callable(writer):
        return False
    try:
        writer(key, bool(on))
    except Exception:
        return False
    try:
        layer.emitStyleChanged()
    except Exception:
        pass  # nosec
    return True


def legend_selection(iface):
    """选中的图例（分类）节点 → [(图层, 图例节点), ...]。

    分类行不是图层行：selectedNodes()/selectedLayers() 都是空的。
    视图上的索引属于代理模型，必须用视图的 index2legendNode 才读得到分类。
    """
    view = layer_tree_view(iface)
    if view is None:
        return []
    indexes = []
    try:
        selection = view.selectionModel()
        if selection is not None:
            indexes.extend(list(selection.selectedIndexes()))
    except Exception:
        indexes = []
    try:
        current = view.currentIndex()
        if current is not None and current.isValid():
            indexes.append(current)
    except Exception:
        pass  # nosec
    pairs = []
    seen = set()
    for index in indexes:
        legend = _legend_at(view, index)
        if legend is None:
            continue
        layer = _layer_of_legend(legend)
        if layer is None:
            continue
        try:
            ident = (layer.id(), legend_rule_key(legend) or str(id(legend)))
        except Exception:
            ident = id(legend)
        if ident in seen:
            continue
        seen.add(ident)
        pairs.append((layer, legend))
    if pairs:
        return pairs
    try:
        legend = view.currentLegendNode()
    except Exception:
        legend = None
    layer = _layer_of_legend(legend) if legend is not None else None
    if layer is None:
        return []
    return [(layer, legend)]


def _collect_legend_children(model, parent, found, seen):
    try:
        rows = int(model.rowCount(parent))
    except Exception:
        return
    for row in range(rows):
        try:
            index = model.index(row, 0, parent)
        except Exception:
            continue  # nosec
        legend = None
        try:
            legend = model.index2legendNode(index)
        except Exception:
            legend = None
        if legend is not None and id(legend) not in seen:
            seen.add(id(legend))
            found.append(legend)
        _collect_legend_children(model, index, found, seen)


def legend_nodes_of_layer(iface, layer):
    """一个图层在图层面板里的全部分类节点，含嵌在图层行上的那个。"""
    view = layer_tree_view(iface)
    if view is None or layer is None:
        return []
    try:
        model = view.layerTreeModel()
    except Exception:
        return []
    if model is None:
        return []
    try:
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
    except Exception:
        node = None
    if node is None:
        return []
    found = []
    seen = set()
    try:
        embedded = model.legendNodeEmbeddedInParent(node)
    except Exception:
        embedded = None
    if embedded is not None:
        seen.add(id(embedded))
        found.append(embedded)
    try:
        parent = model.node2index(node)
    except Exception:
        return found
    _collect_legend_children(model, parent, found, seen)
    return found


def tree_nodes(iface):
    """图层面板里真正选中的图层行或组，不含分类行。"""
    view = layer_tree_view(iface)
    if view is None:
        return []
    try:
        nodes = list(view.selectedNodes(True))
    except TypeError:
        nodes = list(view.selectedNodes())
    except Exception:
        nodes = []
    return [node for node in nodes if node is not None]


def legend_parent_nodes(iface):
    """只选了分类时，返回这些分类所属的图层行。"""
    root = QgsProject.instance().layerTreeRoot()
    found = []
    seen = set()
    for layer, _legend in legend_selection(iface):
        try:
            layer_id = layer.id()
        except Exception:
            continue  # nosec
        if not layer_id or layer_id in seen:
            continue
        try:
            node = root.findLayer(layer_id)
        except Exception:
            node = None
        if node is None:
            continue
        seen.add(layer_id)
        found.append(node)
    return found


def layers_for_scope(iface, scope):
    if scope == "selected":
        return selected_layers(iface)
    return all_layers()


def is_vector(layer):
    return isinstance(layer, QgsVectorLayer)


def is_raster(layer):
    return isinstance(layer, QgsRasterLayer)


_BASEMAP_PROP = "lpt_basemap_preset"
_ONLINE_PROVIDERS = (
    "xyz",
    "wms",
    "wmts",
    "vectortile",
    "arcgismapserver",
    "arcgisfeatureserver",
)


def is_basemap(layer):
    """底图：带 lpt_basemap_preset 标记的图层，或 XYZ/WMS/瓦片在线服务。

    批量开/关图层的功能一律跳过底图，交给「底图切换」专门管理。
    """
    if layer is None:
        return True
    try:
        if str(layer.customProperty(_BASEMAP_PROP) or "").strip():
            return True
    except Exception:
        pass  # nosec
    try:
        provider = (layer.providerType() or "").lower()
    except Exception:
        return False
    return provider in _ONLINE_PROVIDERS


def geometry_code(layer):
    """point, line, polygon, nogeometry, unknown for vectors; raster, mesh, pointcloud, other otherwise."""
    if layer is None:
        return "other"
    if is_raster(layer):
        return "raster"
    if not is_vector(layer):
        kind = str(getattr(layer.type(), "name", "") or layer.type())
        if "Mesh" in kind:
            return "mesh"
        if "PointCloud" in kind:
            return "pointcloud"
        return "other"
    try:
        value = enum_int(layer.geometryType())
    except Exception:
        value = -1
    return {0: "point", 1: "line", 2: "polygon", 4: "nogeometry"}.get(value, "unknown")


def layer_file_path(layer):
    """Local file behind a layer, or "" for databases, services, and memory layers."""
    if layer is None:
        return ""
    try:
        source = layer.source() or ""
        provider = layer.providerType() or ""
    except Exception:
        return ""
    path = ""
    try:
        meta = QgsProviderRegistry.instance().providerMetadata(provider)
    except Exception:
        meta = None
    if meta is not None:
        try:
            decoded = meta.decodeUri(source)
        except Exception:
            decoded = None
        if isinstance(decoded, dict):
            path = str(decoded.get("path") or "")
    if not path:
        head = source.split("|")[0].strip().strip('"')
        if head.lower().startswith("file:"):
            try:
                path = QUrl(head).toLocalFile() or ""
            except Exception:
                path = ""
        elif os.path.isabs(head):
            path = head
    if not path or not os.path.isabs(path):
        return ""
    return os.path.normpath(path)


def layer_tree_view(iface):
    try:
        return iface.layerTreeView()
    except Exception:
        return None


def selected_nodes(iface):
    """Selected groups and layers. A category row counts as its parent layer."""
    nodes = tree_nodes(iface)
    if nodes:
        return nodes
    return legend_parent_nodes(iface)


def is_group_node(node):
    try:
        return bool(QgsLayerTree.isGroup(node))
    except Exception:
        return False


def is_layer_node(node):
    try:
        return bool(QgsLayerTree.isLayer(node))
    except Exception:
        return False


def _node_index(view, node):
    finder = getattr(view, "node2index", None)
    if callable(finder):
        try:
            return finder(node)
        except Exception:
            pass  # nosec
    try:
        return view.layerTreeModel().node2index(node)
    except Exception:
        return None


def expand_to(node):
    parent = node.parent() if node is not None else None
    while parent is not None:
        try:
            parent.setExpanded(True)
        except Exception:
            break
        parent = parent.parent()


def select_nodes(iface, nodes, reveal=True):
    """Make these nodes the Layers panel selection. Returns how many were selected."""
    view = layer_tree_view(iface)
    if view is None:
        return 0
    model = view.selectionModel()
    if model is None:
        return 0
    flags = qt_attr(QItemSelectionModel, "Select") | qt_attr(QItemSelectionModel, "Rows")
    picked = []
    for node in nodes:
        if reveal:
            expand_to(node)
        index = _node_index(view, node)
        if index is None or not index.isValid():
            continue
        picked.append(index)
    model.clearSelection()
    if not picked:
        return 0
    for index in picked:
        model.select(index, flags)
    first = picked[0]
    try:
        model.setCurrentIndex(first, qt_attr(QItemSelectionModel, "NoUpdate"))
    except Exception:
        pass  # nosec
    if reveal:
        try:
            view.scrollTo(first)
        except Exception:
            pass  # nosec
    return len(picked)


def relocate(node, target, index):
    """Put node at target[index] and return the node now in the tree.

    Clone first, then drop the original. Taking a layer node out of the tree
    before it is back makes QGIS remove that layer from the project.
    index counts positions before the original is dropped.
    """
    old = node.parent()
    copy = node.clone()
    count = len(list(target.children()))
    target.insertChildNode(max(0, min(int(index), count)), copy)
    if old is not None:
        old.removeChildNode(node)
    return copy


def reorder_children(parent, wanted):
    """Rearrange parent's children into wanted. Returns {original: node now in the tree}."""
    placed = {}
    for target, node in enumerate(wanted):
        current = list(parent.children())
        if target < len(current) and current[target] == node:
            placed[id(node)] = node
            continue
        placed[id(node)] = relocate(node, parent, target)
    return placed


def layer_nodes(root=None):
    if root is None:
        root = QgsProject.instance().layerTreeRoot()
    try:
        return [node for node in root.findLayers() if node is not None]
    except Exception:
        return []


def _canvas_visible_extent(iface):
    try:
        canvas = iface.mapCanvas()
    except Exception:
        return None, None
    if canvas is None:
        return None, None
    try:
        settings = canvas.mapSettings()
    except Exception:
        settings = None
    extent = None
    if settings is not None:
        for name in ("visibleExtent", "extent"):
            getter = getattr(settings, name, None)
            if callable(getter):
                try:
                    extent = getter()
                    if extent is not None and not extent.isEmpty():
                        break
                except Exception:
                    pass  # nosec
    if extent is None or extent.isEmpty():
        try:
            extent = canvas.extent()
        except Exception:
            extent = None
    map_crs = None
    if settings is not None:
        try:
            map_crs = settings.destinationCrs()
        except Exception:
            map_crs = None
    if map_crs is None or not map_crs.isValid():
        try:
            map_crs = QgsProject.instance().crs()
        except Exception:
            map_crs = None
    return extent, map_crs


def _rect_in_layer_crs(extent, map_crs, layer):
    if extent is None or extent.isEmpty():
        return None
    try:
        layer_crs = layer.crs()
    except Exception:
        layer_crs = None
    if layer_crs is None or not layer_crs.isValid() or map_crs is None or not map_crs.isValid():
        return extent
    if layer_crs == map_crs:
        return extent
    try:
        return QgsCoordinateTransform(map_crs, layer_crs, QgsProject.instance()).transform(extent)
    except Exception:
        return extent


def layer_map_visible(layer, node, iface):
    """Same idea as the attribute table «features visible on map»: current canvas extent + scale."""
    if layer is None:
        return False
    try:
        canvas = iface.mapCanvas()
    except Exception:
        canvas = None
    if canvas is not None:
        try:
            if not bool(layer.isInScaleRange(canvas.scale())):
                return False
        except Exception:
            pass  # nosec
    extent, map_crs = _canvas_visible_extent(iface)
    if extent is None or extent.isEmpty():
        return False
    filter_rect = _rect_in_layer_crs(extent, map_crs, layer)
    if filter_rect is None or filter_rect.isEmpty():
        return False
    if is_vector(layer):
        try:
            request = QgsFeatureRequest().setFilterRect(filter_rect)
            for _feat in layer.getFeatures(request):
                return True
            return False
        except Exception:
            return False
    try:
        layer_ext = layer.extent()
    except Exception:
        return False
    if layer_ext.isEmpty():
        return False
    try:
        layer_crs = layer.crs()
        if layer_crs.isValid() and map_crs is not None and map_crs.isValid() and layer_crs != map_crs:
            layer_ext = QgsCoordinateTransform(layer_crs, map_crs, QgsProject.instance()).transform(layer_ext)
    except Exception:
        pass  # nosec
    try:
        return bool(extent.intersects(layer_ext))
    except Exception:
        return False


def group_path(node):
    names = []
    parent = node.parent() if node is not None else None
    while parent is not None and parent.parent() is not None:
        names.append(parent.name())
        parent = parent.parent()
    return " / ".join(reversed(names))
