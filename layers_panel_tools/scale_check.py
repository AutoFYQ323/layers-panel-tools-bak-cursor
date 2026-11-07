# -*- coding: utf-8 -*-
"""Scale check: list layers that are on but hidden by their scale range right now."""

from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from qgis.core import QgsProject

from .buttons import make_menu_action as build_menu_action, make_toolbar_button
from .i18n import apply_direction, tr, subscribe
from .icons import load_icon
from .qt_compat import run_dialog, user_role
from .scope import is_basemap

_DIALOG = None


def make_action(iface):
    tr("比例尺体检")
    tr("找出开关开着、却被比例尺范围挡住的图层，可一键跳到可见比例尺")
    return make_toolbar_button(
        iface,
        "lpt:scale_check",
        "LayersPanelToolsScaleCheck",
        "比例尺体检",
        "找出开关开着、却被比例尺范围挡住的图层，可一键跳到可见比例尺",
        load_icon("scale_check"),
        lambda: open_scale_check(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsScaleCheckMenu",
        "比例尺体检",
        "找出开关开着、却被比例尺范围挡住的图层，可一键跳到可见比例尺",
        load_icon("scale_check"),
        lambda: open_scale_check(iface),
    )


def close_scale_check():
    global _DIALOG
    if _DIALOG is not None:
        try:
            _DIALOG.close()
        except RuntimeError:
            pass
    _DIALOG = None


def open_scale_check(iface):
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = ScaleCheckDialog(iface)
    _DIALOG.refresh()
    run_dialog(_DIALOG)


def _fmt(value):
    if not value:
        return "—"
    return "1:%d" % int(value)


def _out_of_range(layer, scale):
    try:
        low = layer.minimumScale()
        high = layer.maximumScale()
    except Exception:
        return False
    if low and scale < low:
        return True
    if high and scale > high:
        return True
    return False


class ScaleCheckDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle(tr("比例尺体检"))
        layout = QVBoxLayout(self)
        self.scale = QLabel()
        layout.addWidget(self.scale)
        self.hint = QLabel()
        layout.addWidget(self.hint)
        self.list = QListWidget()
        layout.addWidget(self.list)
        row = QHBoxLayout()
        self.btn_turn_off = QPushButton()
        self.btn_select = QPushButton()
        self.btn_zoom = QPushButton()
        self.btn_refresh = QPushButton()
        self.btn_turn_off.clicked.connect(self._turn_off)
        self.btn_select.clicked.connect(self._select)
        self.btn_zoom.clicked.connect(self._zoom)
        self.btn_refresh.clicked.connect(self.refresh)
        row.addWidget(self.btn_turn_off)
        row.addWidget(self.btn_select)
        row.addWidget(self.btn_zoom)
        row.addStretch(1)
        row.addWidget(self.btn_refresh)
        layout.addLayout(row)
        apply_direction(self)
        self.list.itemDoubleClicked.connect(self._double)
        subscribe(self, self._retranslate)
        self._retranslate()

    def _retranslate(self):
        self.setWindowTitle(tr("比例尺体检"))
        self.hint.setText(tr("双击一行可缩放到该图层可见的比例尺并居中。"))
        self.btn_turn_off.setText(tr("关闭勾选图层的开关"))
        self.btn_select.setText(tr("选中勾选的图层"))
        self.btn_zoom.setText(tr("缩放到勾选图层可见"))
        self.btn_refresh.setText(tr("刷新"))

    def refresh(self):
        self._retranslate()
        self.list.clear()
        try:
            scale = self.iface.mapCanvas().scale()
        except Exception:
            scale = 0.0
        self.scale.setText(tr("当前比例尺：1:%d") % int(scale))
        root = QgsProject.instance().layerTreeRoot()
        for layer in QgsProject.instance().mapLayers().values():
            if is_basemap(layer):
                continue
            try:
                node = root.findLayer(layer.id())
                on = node is not None and node.itemVisibilityChecked()
            except Exception:
                on = False
            if not on:
                continue
            if not _out_of_range(layer, scale):
                continue
            text = tr("%s（可见范围 %s 至 %s）") % (
                layer.name(),
                _fmt(layer.minimumScale()),
                _fmt(layer.maximumScale()),
            )
            item = QListWidgetItem(text)
            item.setData(user_role(), layer.id())
            try:
                from qgis.PyQt.QtCore import Qt

                item.setCheckState(Qt.CheckState.Checked)
            except Exception:
                pass  # nosec
            self.list.addItem(item)
        if not self.list.count():
            self.list.addItem(tr("当前比例尺下没有图层被范围挡住。"))

    def _checked_ids(self):
        from qgis.PyQt.QtCore import Qt

        ids = []
        for index in range(self.list.count()):
            item = self.list.item(index)
            layer_id = item.data(user_role())
            if not layer_id:
                continue
            try:
                if item.checkState() == Qt.CheckState.Checked:
                    ids.append(layer_id)
            except Exception:
                pass  # nosec
        return ids

    def _checked_layers(self):
        return [QgsProject.instance().mapLayer(layer_id) for layer_id in self._checked_ids()]

    def _double(self, item):
        layer_id = item.data(user_role())
        if not layer_id:
            return
        layer = QgsProject.instance().mapLayer(layer_id)
        canvas = None
        try:
            canvas = self.iface.mapCanvas()
        except Exception:
            canvas = None
        if layer is None or canvas is None:
            return
        try:
            extent = layer.extent()
            if extent is not None and not extent.isEmpty():
                canvas.setExtent(extent)
        except Exception:
            pass  # nosec
        scale = _visible_scale(layer)
        if scale:
            canvas.zoomScale(scale)
        canvas.refresh()

    def _turn_off(self):
        root = QgsProject.instance().layerTreeRoot()
        for layer in self._checked_layers():
            if layer is None:
                continue
            try:
                node = root.findLayer(layer.id())
                if node is not None:
                    node.setItemVisibilityChecked(False)
            except Exception:
                pass  # nosec
        self.refresh()

    def _select(self):
        from .scope import select_nodes

        nodes = []
        root = QgsProject.instance().layerTreeRoot()
        for layer in self._checked_layers():
            if layer is None:
                continue
            try:
                node = root.findLayer(layer.id())
                if node is not None:
                    nodes.append(node)
            except Exception:
                pass  # nosec
        select_nodes(self.iface, nodes)

    def _zoom(self):
        canvas = None
        try:
            canvas = self.iface.mapCanvas()
        except Exception:
            canvas = None
        if canvas is None:
            return
        moved = 0
        for layer in self._checked_layers():
            if layer is None:
                continue
            try:
                scale = _visible_scale(layer)
                if scale:
                    canvas.zoomScale(scale)
                    moved += 1
                    break
            except Exception:
                pass  # nosec
        if moved:
            try:
                canvas.refresh()
            except Exception:
                pass  # nosec


def _visible_scale(layer):
    low = layer.minimumScale()
    high = layer.maximumScale()
    if low and high:
        return int((low + high) / 2)
    if high:
        return int(high * 0.9)
    if low:
        return int(low * 1.5)
    return 0
