# -*- coding: utf-8 -*-
"""按多边形在多个矢量图层上选要素，再复制、拖动或删除。

QGIS 自带的选择、复制、移动和删除只作用于当前图层，所以这里单独做。
画多边形和相交判断按 Topology Preview 的做法：橡皮筋跟着鼠标走，每个图层只换算一次范围，
先比外包框，再用预编译的几何引擎做精确相交。
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsMapTool, QgsRubberBand

from .buttons import ask, make_popup_menu_action, make_popup_tool
from .i18n import apply_direction, tr
from .icons import load_icon
from .scope import geometry_code, tell

_tool = None
_move_tool = None
_dialog = None
_PREVIEW_LIMIT = 800


def make_action(iface):
    tr("按多边形选择")
    tr("不看当前图层，在多个矢量图层上画多边形选要素，再复制、平移或删除")
    tr("全选（所有矢量图层）")
    tr("只选当前可见图层")
    tr("先点起点，移动时能看到效果，再点终点。右键取消这一次，Esc 结束。")
    return make_popup_tool(
        iface,
        "lpt:poly_select",
        "LayersPanelToolsPolySelect",
        "按多边形选择",
        "不看当前图层，在多个矢量图层上画多边形选要素，再复制、平移或删除",
        load_icon("poly_select"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsPolySelectMenu",
        "按多边形选择",
        "不看当前图层，在多个矢量图层上画多边形选要素，再复制、平移或删除",
        load_icon("poly_select"),
        lambda menu: _fill(iface, menu),
    )


def close_poly_select():
    global _tool, _move_tool, _dialog
    for tool in (_tool, _move_tool):
        if tool is None:
            continue
        try:
            canvas = tool.canvas()
            if canvas is not None and canvas.mapTool() is tool:
                canvas.unsetMapTool(tool)
        except Exception:
            pass  # nosec
    _tool = None
    _move_tool = None
    dialog = _dialog
    _dialog = None
    if dialog is not None:
        try:
            dialog.close()
        except RuntimeError:
            pass


def _fill(iface, menu):
    menu.clear()
    subcommands.add_to_menu(iface, "lpt:poly_select", menu, "lpt:poly_select:all_vectors")
    subcommands.add_to_menu(iface, "lpt:poly_select", menu, "lpt:poly_select:visible_only")


def _start(iface, visible_only):
    global _tool
    canvas = iface.mapCanvas()
    if canvas is None:
        return
    _tool = PolySelectTool(canvas, iface, visible_only)
    canvas.setMapTool(_tool)
    try:
        canvas.setFocus()
    except Exception:
        pass  # nosec
    tell(iface, tr("按多边形选择"), tr("左键加点，右键或回车结束。按 Esc 取消。"))


def _wkb(name, qgis_name):
    try:
        from qgis.core import Qgis

        group = getattr(Qgis, "GeometryType", None)
        if group is not None and hasattr(group, qgis_name):
            return getattr(group, qgis_name)
    except Exception:
        pass  # nosec
    return getattr(QgsWkbTypes, name, 0)


def _button(name):
    value = getattr(Qt, name, None)
    if value is None:
        value = getattr(getattr(Qt, "MouseButton", Qt), name, None)
    return value


def _key(name):
    value = getattr(Qt, name, None)
    if value is None:
        value = getattr(getattr(Qt, "Key", Qt), name, None)
    return value


def _event_point(tool, event):
    pos = event.pos() if hasattr(event, "pos") else event.position().toPoint()
    return QgsPointXY(tool.toMapCoordinates(pos))


def _layer_shown(layer, canvas):
    node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
    if node is None:
        return False
    try:
        shown = node.isVisible()
    except Exception:
        try:
            shown = node.itemVisibilityChecked()
        except Exception:
            shown = True
    if not shown:
        return False
    try:
        if canvas is not None and not layer.isInScaleRange(canvas.scale()):
            return False
    except Exception:
        pass  # nosec
    return True


def _prepare_target(layer, geom, src_crs, project):
    """范围换到图层坐标系一次。返回 (外包框, 预编译引擎或 None, 几何)。"""
    target = QgsGeometry(geom)
    try:
        layer_crs = layer.crs()
    except Exception:
        layer_crs = None
    if (
        layer_crs is not None
        and layer_crs.isValid()
        and src_crs is not None
        and src_crs.isValid()
        and layer_crs != src_crs
    ):
        try:
            transform = QgsCoordinateTransform(src_crs, layer_crs, project)
            target.transform(transform)
        except Exception:
            return None
    box = target.boundingBox()
    try:
        pad = max(box.width(), box.height(), 1.0) * 1e-9
        box.grow(pad)
    except Exception:
        pass  # nosec
    engine = None
    try:
        engine = QgsGeometry.createGeometryEngine(target.constGet())
        engine.prepareGeometry()
    except Exception:
        engine = None
    return box, engine, target


def _feature_hits(feature, box, engine, target):
    geometry = feature.geometry()
    if geometry is None or geometry.isEmpty():
        return False
    try:
        if not box.intersects(geometry.boundingBox()):
            return False
        if engine is not None:
            return bool(engine.intersects(geometry.constGet()))
        return bool(geometry.intersects(target))
    except Exception:
        return False


def _select_by_polygon(iface, geom, visible_only):
    canvas = iface.mapCanvas()
    project = QgsProject.instance()
    try:
        canvas_crs = canvas.mapSettings().destinationCrs()
    except Exception:
        canvas_crs = None
    frozen = False
    try:
        canvas.freeze(True)
        frozen = True
    except Exception:
        frozen = False
    hit = 0
    layers_hit = 0
    try:
        for layer in list(project.mapLayers().values()):
            if not isinstance(layer, QgsVectorLayer):
                continue
            if visible_only and not _layer_shown(layer, canvas):
                try:
                    if layer.selectedFeatureCount():
                        layer.selectByIds([])
                except Exception:
                    pass  # nosec
                continue
            prepared = _prepare_target(layer, geom, canvas_crs, project)
            if prepared is None:
                continue
            box, engine, target = prepared
            try:
                extent = layer.extent()
                if extent is not None and not extent.isEmpty() and not extent.intersects(box):
                    if layer.selectedFeatureCount():
                        layer.selectByIds([])
                    continue
            except Exception:
                pass  # nosec
            request = QgsFeatureRequest().setFilterRect(box)
            try:
                request.setNoAttributes()
            except Exception:
                pass  # nosec
            ids = []
            try:
                for feature in layer.getFeatures(request):
                    if _feature_hits(feature, box, engine, target):
                        ids.append(feature.id())
            except Exception:
                ids = []
            try:
                if ids or layer.selectedFeatureCount():
                    layer.selectByIds(ids)
            except Exception:
                continue  # nosec
            if ids:
                layers_hit += 1
                hit += len(ids)
    finally:
        if frozen:
            try:
                canvas.freeze(False)
            except Exception:
                pass  # nosec
        try:
            canvas.refresh()
        except Exception:
            pass  # nosec
    if hit <= 0:
        tell(iface, tr("按多边形选择"), tr("多边形里没有选中要素。"), warning=True)
        return
    tell(iface, tr("按多边形选择"), tr("已在 %d 个图层选中 %d 个要素。") % (layers_hit, hit))
    _open_actions(iface)


def _open_actions(iface):
    global _dialog
    if _dialog is None:
        _dialog = MultiEditDialog(iface, iface.mainWindow())
    _dialog.refresh()
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


def _selected_layers():
    found = []
    for layer in list(QgsProject.instance().mapLayers().values()):
        if not isinstance(layer, QgsVectorLayer):
            continue
        try:
            count = int(layer.selectedFeatureCount())
        except Exception:
            count = 0
        if count > 0:
            found.append(layer)
    return found


def _run_edits(iface, mutate):
    layers = _selected_layers()
    if not layers:
        tell(iface, tr("按多边形选择"), tr("没有选中的要素。"), warning=True)
        return
    done = 0
    failed = []
    for layer in layers:
        started = False
        try:
            started = not layer.isEditable()
        except Exception:
            started = True
        if started:
            try:
                if not layer.startEditing():
                    failed.append(layer.name() or "")
                    continue
            except Exception:
                failed.append(layer.name() or "")
                continue
        try:
            mutate(layer)
            if started:
                if not layer.commitChanges():
                    try:
                        layer.rollBack()
                    except Exception:
                        pass  # nosec
                    failed.append(layer.name() or "")
                    continue
            done += 1
        except Exception:
            if started:
                try:
                    layer.rollBack()
                except Exception:
                    pass  # nosec
            failed.append(layer.name() or "")
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec
    if done:
        tell(iface, tr("按多边形选择"), tr("已处理 %d 个图层。") % done)
    if failed:
        tell(iface, tr("按多边形选择"), tr("这些图层没能改：%s") % "、".join(failed), warning=True)


def _delta_for_layer(layer, canvas, dx, dy):
    if canvas is None or (abs(dx) < 1e-12 and abs(dy) < 1e-12):
        return dx, dy
    try:
        source = canvas.mapSettings().destinationCrs()
        target = layer.crs()
    except Exception:
        return dx, dy
    if source == target:
        return dx, dy
    try:
        center = canvas.extent().center()
        transform = QgsCoordinateTransform(source, target, QgsProject.instance())
        start = transform.transform(QgsPointXY(center))
        end = transform.transform(QgsPointXY(center.x() + dx, center.y() + dy))
        return end.x() - start.x(), end.y() - start.y()
    except Exception:
        return dx, dy


class PolySelectTool(QgsMapTool):
    """和 Topology Preview 一样：第一下就出点，轮廓跟着鼠标。"""

    finished = pyqtSignal(object)

    def __init__(self, canvas, iface, visible_only):
        super().__init__(canvas)
        self.iface = iface
        self.visible_only = visible_only
        self._points = []
        self._done = False
        self._ghost = False
        stroke = QColor(21, 101, 192)
        self._points_band = QgsRubberBand(canvas, _wkb("PointGeometry", "Point"))
        self._line = QgsRubberBand(canvas, _wkb("LineGeometry", "Line"))
        self._fill = QgsRubberBand(canvas, _wkb("PolygonGeometry", "Polygon"))
        self._points_band.setColor(stroke)
        self._points_band.setIconSize(10)
        self._points_band.setWidth(2)
        self._line.setColor(stroke)
        self._line.setWidth(2)
        self._fill.setColor(QColor(21, 101, 192, 0))
        self._fill.setFillColor(QColor(21, 101, 192, 40))
        self.finished.connect(self._on_finished)

    def canvasPressEvent(self, event):
        if self._done:
            return
        if event.button() == _button("RightButton"):
            self._finish(True)
            return
        if event.button() != _button("LeftButton"):
            return
        point = _event_point(self, event)
        self._points.append(point)
        self._points_band.addPoint(point, True)
        if self._ghost:
            self._line.movePoint(len(self._points) - 1, point, True)
            self._ghost = False
        else:
            self._line.addPoint(point, True)
        self._refresh_fill()

    def canvasMoveEvent(self, event):
        if self._done or not self._points:
            return
        point = _event_point(self, event)
        if not self._ghost:
            self._line.addPoint(point, True)
            self._ghost = True
            return
        self._line.movePoint(len(self._points), point, True)

    def keyPressEvent(self, event):
        if event.key() == _key("Key_Escape"):
            self._finish(False)
            return
        if event.key() in (_key("Key_Return"), _key("Key_Enter")):
            self._finish(True)

    def _refresh_fill(self):
        polygon = _wkb("PolygonGeometry", "Polygon")
        self._fill.reset(polygon)
        if len(self._points) < 3:
            return
        for point in self._points:
            self._fill.addPoint(point, False)
        self._fill.addPoint(self._points[0], True)

    def _clear_bands(self):
        self._points_band.reset(_wkb("PointGeometry", "Point"))
        self._line.reset(_wkb("LineGeometry", "Line"))
        self._fill.reset(_wkb("PolygonGeometry", "Polygon"))
        self._ghost = False

    def _finish(self, ok):
        if self._done:
            return
        self._done = True
        geom = None
        if ok and len(self._points) >= 3:
            ring = list(self._points) + [self._points[0]]
            geom = QgsGeometry.fromPolygonXY([ring])
            if geom is None or geom.isEmpty():
                geom = None
        self._clear_bands()
        if ok and len(self._points) < 3:
            tell(self.iface, tr("按多边形选择"), tr("至少要点三个点。"), warning=True)
        self.finished.emit(geom)

    def _on_finished(self, geom):
        try:
            canvas = self.canvas()
            if canvas is not None and canvas.mapTool() is self:
                canvas.unsetMapTool(self)
        except Exception:
            pass  # nosec
        if geom is None or geom.isEmpty():
            return
        _select_by_polygon(self.iface, geom, self.visible_only)

    def deactivate(self):
        if not self._done:
            self._done = True
            self._clear_bands()
        else:
            self._clear_bands()
        try:
            super().deactivate()
        except Exception:
            pass  # nosec


class MultiMoveTool(QgsMapTool):
    """先点起点，鼠标移动时预览，再点终点。所有图层里选中的要素一起移动。"""

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self._origin = None
        self._bands = []
        stroke = QColor(21, 101, 192)
        for name, qgis_name in (("PointGeometry", "Point"), ("LineGeometry", "Line"), ("PolygonGeometry", "Polygon")):
            band = QgsRubberBand(canvas, _wkb(name, qgis_name))
            band.setColor(stroke)
            band.setWidth(2)
            if name == "PointGeometry":
                band.setIconSize(8)
            if name == "PolygonGeometry":
                band.setFillColor(QColor(21, 101, 192, 40))
            self._bands.append(band)

    def canvasMoveEvent(self, event):
        if self._origin is None:
            return
        point = _event_point(self, event)
        dx = point.x() - self._origin.x()
        dy = point.y() - self._origin.y()
        for band in self._bands:
            try:
                band.setTranslationOffset(dx, dy)
                band.updatePosition()
            except Exception:
                pass  # nosec

    def canvasReleaseEvent(self, event):
        if event.button() == _button("RightButton"):
            self._origin = None
            self._clear_preview()
            return
        if event.button() != _button("LeftButton"):
            return
        point = _event_point(self, event)
        if self._origin is None:
            self._origin = point
            self._build_preview()
            return
        dx = point.x() - self._origin.x()
        dy = point.y() - self._origin.y()
        self._origin = None
        self._clear_preview()
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return
        canvas = self.canvas()

        def mutate(layer, dx=dx, dy=dy):
            ox, oy = _delta_for_layer(layer, canvas, dx, dy)
            for feature in layer.selectedFeatures():
                geometry = feature.geometry()
                if geometry is None or geometry.isEmpty():
                    continue
                moved = QgsGeometry(geometry)
                moved.translate(ox, oy)
                layer.changeGeometry(feature.id(), moved)

        _run_edits(self.iface, mutate)
        if _dialog is not None:
            try:
                _dialog.refresh()
            except Exception:
                pass  # nosec

    def keyPressEvent(self, event):
        if event.key() == _key("Key_Escape"):
            self._origin = None
            self._clear_preview()
            try:
                self.canvas().unsetMapTool(self)
            except Exception:
                pass  # nosec

    def _build_preview(self):
        self._clear_preview()
        shown = 0
        for layer in _selected_layers():
            kind = geometry_code(layer)
            if kind == "point":
                band = self._bands[0]
            elif kind == "line":
                band = self._bands[1]
            else:
                band = self._bands[2]
            try:
                features = layer.selectedFeatures()
            except Exception:
                features = []
            for feature in features:
                if shown >= _PREVIEW_LIMIT:
                    return
                geometry = feature.geometry()
                if geometry is None or geometry.isEmpty():
                    continue
                try:
                    band.addGeometry(QgsGeometry(geometry), layer)
                    shown += 1
                except Exception:
                    continue  # nosec

    def _clear_preview(self):
        kinds = (
            ("PointGeometry", "Point"),
            ("LineGeometry", "Line"),
            ("PolygonGeometry", "Polygon"),
        )
        for band, (name, qgis_name) in zip(self._bands, kinds):
            try:
                band.setTranslationOffset(0, 0)
            except Exception:
                pass  # nosec
            try:
                band.reset(_wkb(name, qgis_name))
            except Exception:
                try:
                    band.reset()
                except Exception:
                    pass  # nosec

    def deactivate(self):
        self._origin = None
        self._clear_preview()
        try:
            super().deactivate()
        except Exception:
            pass  # nosec


def _begin_move(iface):
    global _move_tool
    canvas = iface.mapCanvas()
    if canvas is None:
        return
    if not _selected_layers():
        tell(iface, tr("按多边形选择"), tr("没有选中的要素。"), warning=True)
        return
    _move_tool = MultiMoveTool(canvas, iface)
    canvas.setMapTool(_move_tool)
    try:
        canvas.setFocus()
    except Exception:
        pass  # nosec
    tell(iface, tr("按多边形选择"), tr("先点起点，移动时能看到效果，再点终点。右键取消这一次，Esc 结束。"))


class MultiEditDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setObjectName("LayersPanelToolsPolyEdit")
        self.setWindowTitle(tr("所选要素"))
        self.setMinimumWidth(240)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.btn_delete = QPushButton(tr("删除"))
        self.btn_copy = QPushButton(tr("复制"))
        self.btn_move = QPushButton(tr("移动"))
        self.btn_close = QPushButton(tr("关闭"))
        for button in (self.btn_delete, self.btn_copy, self.btn_move, self.btn_close):
            row.addWidget(button)
        layout.addLayout(row)
        self.btn_delete.clicked.connect(self._delete)
        self.btn_copy.clicked.connect(self._copy)
        self.btn_move.clicked.connect(self._move)
        self.btn_close.clicked.connect(self.close)
        apply_direction(self)
        self.refresh()
        self.adjustSize()

    def refresh(self):
        layers = _selected_layers()
        count = 0
        for layer in layers:
            try:
                count += int(layer.selectedFeatureCount())
            except Exception:
                pass  # nosec
        self.summary.setText(tr("已在 %d 个图层选中 %d 个要素。") % (len(layers), count))

    def _delete(self):
        if not ask(self, tr("按多边形选择"), tr("确定删除各图层里当前选中的要素吗？")):
            return

        def mutate(layer):
            layer.deleteSelectedFeatures()

        _run_edits(self.iface, mutate)
        self.refresh()

    def _copy(self):
        def mutate(layer):
            for fid in list(layer.selectedFeatureIds()):
                feature = layer.getFeature(fid)
                if not feature.isValid():
                    continue
                clone = QgsFeature(layer.fields())
                try:
                    clone.setAttributes(feature.attributes())
                except Exception:
                    pass  # nosec
                try:
                    geometry = feature.geometry()
                    if geometry is not None and not geometry.isEmpty():
                        clone.setGeometry(QgsGeometry(geometry))
                except Exception:
                    pass  # nosec
                layer.addFeature(clone)

        _run_edits(self.iface, mutate)
        self.refresh()

    def _move(self):
        _begin_move(self.iface)


from . import subcommands

tr("全选（所有矢量图层）")
tr("只选当前可见图层")
subcommands.register("lpt:poly_select", [
    ("all_vectors", "全选（所有矢量图层）", lambda iface: _start(iface, False)),
    ("visible_only", "只选当前可见图层", lambda iface: _start(iface, True)),
])