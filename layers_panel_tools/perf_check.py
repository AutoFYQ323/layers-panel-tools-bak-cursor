# -*- coding: utf-8 -*-
"""Render check: time how long each visible layer takes to draw in the current view."""

from qgis.PyQt.QtCore import QCoreApplication, QElapsedTimer, QSize, Qt, QThread

from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from qgis.core import QgsMapRendererSequentialJob, QgsProject

from .buttons import make_menu_action as build_menu_action, make_toolbar_button
from .i18n import apply_direction, tr, subscribe
from .icons import load_icon
from .qt_compat import qt_attr, run_dialog, user_role

_TIMEOUT_MS = 5000
_DIALOG = None


def make_action(iface):
    tr("渲染体检")
    tr("按当前视图逐层测量渲染耗时，找出拖慢工程的图层")
    return make_toolbar_button(
        iface,
        "lpt:perf",
        "LayersPanelToolsPerf",
        "渲染体检",
        "按当前视图逐层测量渲染耗时，找出拖慢工程的图层",
        load_icon("perf"),
        lambda: open_perf(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsPerfMenu",
        "渲染体检",
        "按当前视图逐层测量渲染耗时，找出拖慢工程的图层",
        load_icon("perf"),
        lambda: open_perf(iface),
    )


def close_perf():
    global _DIALOG
    if _DIALOG is not None:
        try:
            _DIALOG.close()
        except RuntimeError:
            pass
    _DIALOG = None


def open_perf(iface):
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = PerfDialog(iface)
    _DIALOG.retranslate()
    run_dialog(_DIALOG)


class PerfDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle(tr("渲染体检"))
        layout = QVBoxLayout(self)
        self.hint = QLabel()
        layout.addWidget(self.hint)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.list)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        layout.addWidget(self.bar)
        row = QHBoxLayout()
        self.btn_run = QPushButton()
        self.btn_off = QPushButton()
        self.btn_run.clicked.connect(self._measure)
        self.btn_off.clicked.connect(self._turn_off_checked)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_off)
        row.addStretch(1)
        layout.addLayout(row)
        self.box = QDialogButtonBox()
        close_flag = qt_attr(QDialogButtonBox, "Close")
        self.box.addButton(close_flag)
        self.box.rejected.connect(self.reject)
        from .i18n import localize_button_box

        localize_button_box(self.box)
        layout.addWidget(self.box)
        apply_direction(self)
        subscribe(self, self.retranslate)
        self.retranslate()

    def retranslate(self):
        self.setWindowTitle(tr("渲染体检"))
        self.hint.setText(tr("逐层单独渲染当前视图并计时（在线服务超时按 5 秒计）。结果按耗时从多到少排列。"))
        self.btn_run.setText(tr("开始测量"))
        self.btn_off.setText(tr("关闭勾选图层的开关"))

    def _visible_layers(self):
        root = QgsProject.instance().layerTreeRoot()
        found = []
        for layer in QgsProject.instance().mapLayers().values():
            try:
                node = root.findLayer(layer.id())
                if node is not None and node.itemVisibilityChecked():
                    found.append(layer)
            except Exception:
                pass  # nosec
        return found

    def _measure(self):
        # processEvents 会把点击送回来。测量中再点「开始测量」会叠两轮渲染任务。
        if getattr(self, "_busy", False):
            return
        self._busy = True
        try:
            self.btn_run.setEnabled(False)
        except Exception:
            pass  # nosec
        try:
            self._measure_now()
        finally:
            self._busy = False
            try:
                self.btn_run.setEnabled(True)
            except RuntimeError:
                pass

    def _measure_now(self):
        canvas = None
        try:
            canvas = self.iface.mapCanvas()
        except Exception:
            canvas = None
        if canvas is None:
            return
        layers = self._visible_layers()
        self.list.clear()
        self.bar.setRange(0, 0)
        results = []
        for layer in layers:
            try:
                name = layer.name()
                ms = self._time_layer(canvas, layer)
                results.append((ms, name, layer.id()))
            except Exception:
                continue  # nosec
            QCoreApplication.processEvents()
        results.sort(key=lambda item: -item[0])
        for ms, name, layer_id in results:
            text = tr("%6d 毫秒  %s") % (ms, name) if ms <= _TIMEOUT_MS else tr("超过 %d 毫秒  %s") % (_TIMEOUT_MS, name)
            item = QListWidgetItem(text)
            item.setData(user_role(), layer_id)
            try:
                item.setCheckState(Qt.CheckState.Unchecked)
            except Exception:
                pass  # nosec
            self.list.addItem(item)
        self.bar.setRange(0, 1)
        if not results:
            self.list.addItem(tr("当前没有打开的图层可测。"))
        else:
            total = sum(item[0] for item in results)
            self.list.addItem(tr("合计约 %d 毫秒（不含图层间叠加影响）。") % total)

    def _time_layer(self, canvas, layer):
        # 复制一份设置再改。直接改 canvas.mapSettings() 会把真实地图改成只剩这一层、480×360。
        # 3.28 没有 clone()，用拷贝构造；拷贝失败就跳过这一层，绝不改画布本身。
        from qgis.core import QgsMapSettings

        try:
            settings = QgsMapSettings(canvas.mapSettings())
        except Exception:
            return _TIMEOUT_MS + 1
        settings.setLayers([layer])
        settings.setOutputSize(QSize(480, 360))
        job = QgsMapRendererSequentialJob(settings)
        timer = QElapsedTimer()
        timer.start()
        job.start()
        while True:
            QThread.msleep(10)
            QCoreApplication.processEvents()
            try:
                if not job.isActive():
                    break
            except Exception:
                break
            try:
                still_open = self.isVisible()
            except RuntimeError:
                still_open = False
            if not still_open or timer.elapsed() > _TIMEOUT_MS:
                try:
                    job.cancel()
                except Exception:
                    pass  # nosec
                return _TIMEOUT_MS + 1
        return int(timer.elapsed())

    def _turn_off_checked(self):
        root = QgsProject.instance().layerTreeRoot()
        for index in range(self.list.count()):
            item = self.list.item(index)
            layer_id = item.data(user_role())
            if not layer_id:
                continue
            try:
                if item.checkState() != Qt.CheckState.Checked:
                    continue
            except Exception:
                continue  # nosec
            node = root.findLayer(layer_id)
            if node is not None:
                node.setItemVisibilityChecked(False)
