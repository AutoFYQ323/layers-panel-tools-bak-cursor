# -*- coding: utf-8 -*-
"""批量要素另存为：勾选多个点、线、面图层，选一个文件夹，用 QGIS 的写出接口各存一份。"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)
from qgis.core import QgsProject, QgsVectorFileWriter, QgsVectorLayer

from .buttons import ask, make_menu_action as build_menu_action, make_toolbar_button, qt_attr
from .i18n import apply_direction, tr, subscribe
from .icons import load_icon
from .qt_compat import enum_int, user_role
from .scope import geometry_code, tell

_DIALOG = None


def make_action(iface):
    tr("批量导出")
    tr("勾选点、线、面图层，选一个文件夹一次导出")
    return make_toolbar_button(
        iface,
        "lpt:export",
        "LayersPanelToolsExport",
        "批量导出",
        "勾选点、线、面图层，选一个文件夹一次导出",
        load_icon("export"),
        lambda: open_export(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsExportMenu",
        "批量导出",
        "勾选点、线、面图层，选一个文件夹一次导出",
        load_icon("export"),
        lambda: open_export(iface),
    )


def open_export(iface):
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = ExportDialog(iface, iface.mainWindow())
    # closeEvent 会把 _listening 关掉，reload 看见它就直接返回，第二次打开列表是空的。
    _DIALOG._listening = True
    _DIALOG.reload()
    _DIALOG.show()
    _DIALOG.raise_()
    _DIALOG.activateWindow()


def close_export():
    global _DIALOG
    dialog = _DIALOG
    _DIALOG = None
    if dialog is not None:
        try:
            dialog.close()
        except RuntimeError:
            pass


def _vector_layers():
    found = []
    for layer in QgsProject.instance().mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        if geometry_code(layer) not in ("point", "line", "polygon"):
            continue
        found.append(layer)
    found.sort(key=lambda layer: (layer.name() or "").casefold())
    return found


def _safe_name(name):
    bad = '\\/:*?"<>|'
    text = "".join("_" if char in bad else char for char in (name or "")).strip().rstrip(".")
    return text or "layer"


def _writer_action(name):
    nested = getattr(QgsVectorFileWriter, "ActionOnExistingFile", None)
    if nested is not None and hasattr(nested, name):
        return getattr(nested, name)
    return getattr(QgsVectorFileWriter, name, None)


def _no_error():
    nested = getattr(QgsVectorFileWriter, "WriterError", None)
    if nested is not None and hasattr(nested, "NoError"):
        return nested.NoError
    return getattr(QgsVectorFileWriter, "NoError", 0)


def _formats():
    found = []
    option = None
    nested = getattr(QgsVectorFileWriter, "VectorFormatOption", None)
    if nested is not None and hasattr(nested, "SkipNonSpatialFormats"):
        option = nested.SkipNonSpatialFormats
    else:
        option = getattr(QgsVectorFileWriter, "SkipNonSpatialFormats", None)
    details = []
    try:
        if option is None:
            details = QgsVectorFileWriter.supportedFiltersAndFormats()
        else:
            details = QgsVectorFileWriter.supportedFiltersAndFormats(option)
    except Exception:
        details = []
    for item in details or []:
        driver = str(getattr(item, "driverName", "") or "").strip()
        label = str(getattr(item, "filterString", "") or driver).split("(")[0].strip()
        if driver:
            found.append((label or driver, driver))
    if not found:
        found = [
            ("GeoPackage", "GPKG"),
            ("ESRI Shapefile", "ESRI Shapefile"),
            ("GeoJSON", "GeoJSON"),
        ]
    return found


def _extension(driver):
    known = {
        "GPKG": ".gpkg",
        "ESRI Shapefile": ".shp",
        "GeoJSON": ".geojson",
        "KML": ".kml",
        "LIBKML": ".kml",
        "GML": ".gml",
        "CSV": ".csv",
        "FlatGeobuf": ".fgb",
        "MapInfo File": ".tab",
        "DXF": ".dxf",
        "SQLite": ".sqlite",
        "XLSX": ".xlsx",
        "GPX": ".gpx",
    }
    try:
        meta = QgsVectorFileWriter.MetaData()
        result = QgsVectorFileWriter.driverMetadata(driver, meta)
        if isinstance(result, tuple):
            ok = bool(result[0])
            if len(result) > 1 and result[1] is not None:
                meta = result[1]
        else:
            ok = bool(result)
        if ok:
            ext = str(getattr(meta, "ext", "") or "").strip()
            if ext:
                return ext if ext.startswith(".") else "." + ext
    except Exception:
        pass  # nosec
    return known.get(str(driver or ""), "")


def _unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    number = 2
    while os.path.exists("%s_%d%s" % (base, number, ext)):
        number += 1
    return "%s_%d%s" % (base, number, ext)


class ExportDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setObjectName("LayersPanelToolsExport")
        self.resize(480, 520)
        self._listening = False
        layout = QVBoxLayout(self)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.search = QLineEdit()
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.setSelectionMode(qt_attr(QAbstractItemView, "NoSelection"))
        layout.addWidget(self.list, 1)
        filters = QHBoxLayout()
        self.btn_all = QPushButton()
        self.btn_none = QPushButton()
        self.btn_point = QPushButton()
        self.btn_line = QPushButton()
        self.btn_polygon = QPushButton()
        for button in (self.btn_all, self.btn_none, self.btn_point, self.btn_line, self.btn_polygon):
            filters.addWidget(button)
        filters.addStretch(1)
        layout.addLayout(filters)
        format_row = QHBoxLayout()
        self.format_label = QLabel()
        self.format_box = QComboBox()
        for label, driver in _formats():
            self.format_box.addItem(label, driver)
        preferred = self.format_box.findData("GPKG")
        if preferred < 0:
            preferred = self.format_box.findData("ESRI Shapefile")
        if preferred >= 0:
            self.format_box.setCurrentIndex(preferred)
        format_row.addWidget(self.format_label)
        format_row.addWidget(self.format_box, 1)
        layout.addLayout(format_row)
        encoding_row = QHBoxLayout()
        self.encoding_label = QLabel()
        self.encoding_box = QComboBox()
        self.encoding_box.setEditable(True)
        for name in ("UTF-8", "GBK", "GB18030", "System", "ISO-8859-1"):
            self.encoding_box.addItem(name)
        encoding_row.addWidget(self.encoding_label)
        encoding_row.addWidget(self.encoding_box, 1)
        layout.addLayout(encoding_row)
        folder_row = QHBoxLayout()
        self.folder_label = QLabel()
        self.folder_edit = QLineEdit()
        self.btn_browse = QPushButton()
        folder_row.addWidget(self.folder_label)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.btn_browse)
        layout.addLayout(folder_row)
        self.add_canvas = QCheckBox()
        layout.addWidget(self.add_canvas)
        actions = QHBoxLayout()
        self.btn_export = QPushButton()
        self.btn_close = QPushButton()
        actions.addWidget(self.btn_export)
        actions.addStretch(1)
        actions.addWidget(self.btn_close)
        layout.addLayout(actions)
        self.search.textChanged.connect(self._filter)
        self.btn_all.clicked.connect(lambda: self._check("all", True))
        self.btn_none.clicked.connect(lambda: self._check("all", False))
        self.btn_point.clicked.connect(lambda: self._check("point", True))
        self.btn_line.clicked.connect(lambda: self._check("line", True))
        self.btn_polygon.clicked.connect(lambda: self._check("polygon", True))
        self.btn_browse.clicked.connect(self._browse)
        self.btn_export.clicked.connect(self._export)
        self.btn_close.clicked.connect(self.close)
        self.retranslate()
        subscribe(self, self.retranslate)
        self._listening = True
        self.reload()

    def retranslate(self, *_args):
        self.setWindowTitle(tr("批量导出"))
        self.hint.setText(tr("勾选点、线、面图层，选一个文件夹一次导出"))
        self.search.setPlaceholderText(tr("筛选图层名称…"))
        self.btn_all.setText(tr("全选"))
        self.btn_none.setText(tr("全不选"))
        self.btn_point.setText(tr("只选点"))
        self.btn_line.setText(tr("只选线"))
        self.btn_polygon.setText(tr("只选面"))
        self.format_label.setText(tr("格式"))
        self.encoding_label.setText(tr("编码"))
        self.folder_label.setText(tr("文件夹"))
        self.btn_browse.setText(tr("浏览"))
        self.add_canvas.setText(tr("导出后添加到地图"))
        self.btn_export.setText(tr("导出"))
        self.btn_close.setText(tr("关闭"))
        apply_direction(self)
        self.reload()

    def closeEvent(self, event):
        if self._listening:
            self._listening = False
        super().closeEvent(event)

    def reload(self):
        if not self._listening:
            return
        needle = self.search.text().strip().casefold()
        checked = set()
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.checkState() == qt_attr(Qt, "Checked"):
                checked.add(str(item.data(user_role()) or ""))
        self.list.clear()
        layers = _vector_layers()
        if not layers:
            self.hint.setText(tr("工程里没有点、线、面图层。"))
        else:
            self.hint.setText(tr("勾选点、线、面图层，选一个文件夹一次导出"))
        fresh = not checked
        for layer in layers:
            kind = geometry_code(layer)
            item = QListWidgetItem("%s    %s" % (layer.name() or "", _type_label(kind)))
            item.setFlags(item.flags() | qt_attr(Qt, "ItemIsUserCheckable"))
            layer_id = layer.id()
            item.setData(user_role(), layer_id)
            item.setData(user_role(1), kind)
            if fresh or layer_id in checked:
                item.setCheckState(qt_attr(Qt, "Checked"))
            else:
                item.setCheckState(qt_attr(Qt, "Unchecked"))
            self.list.addItem(item)
            name = (layer.name() or "").casefold()
            item.setHidden(bool(needle and needle not in name))

    def _filter(self, _text):
        needle = self.search.text().strip().casefold()
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is None:
                continue
            item.setHidden(bool(needle and needle not in item.text().casefold()))

    def _check(self, kind, on):
        state = qt_attr(Qt, "Checked" if on else "Unchecked")
        off = qt_attr(Qt, "Unchecked")
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is None:
                continue
            item_kind = str(item.data(user_role(1)) or "")
            if kind == "all" or item_kind == kind:
                item.setCheckState(state)
            elif kind != "all":
                item.setCheckState(off)

    def _chosen_layers(self):
        found = []
        project = QgsProject.instance()
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is None or item.checkState() != qt_attr(Qt, "Checked"):
                continue
            layer = project.mapLayer(item.data(user_role()))
            if isinstance(layer, QgsVectorLayer):
                found.append(layer)
        return found

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, tr("选择导出文件夹"), self.folder_edit.text().strip())
        if folder:
            self.folder_edit.setText(folder)

    def _export(self):
        layers = self._chosen_layers()
        if not layers:
            tell(self.iface, tr("批量导出"), tr("请先勾选要导出的图层。"), warning=True)
            return
        folder = self.folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            tell(self.iface, tr("批量导出"), tr("请先选择导出文件夹。"), warning=True)
            return
        driver = str(self.format_box.currentData() or "")
        encoding = str(self.encoding_box.currentText() or "UTF-8").strip() or "UTF-8"
        ext = _extension(driver)
        if not driver or not ext:
            tell(self.iface, tr("批量导出"), tr("这个格式不能按文件导出。"), warning=True)
            return
        _write_layers(
            self.iface,
            self,
            layers,
            folder,
            driver,
            ext,
            encoding,
            self.add_canvas.isChecked(),
        )


def _type_label(kind):
    if kind == "point":
        return tr("点")
    if kind == "line":
        return tr("线")
    if kind == "polygon":
        return tr("面")
    return ""


def _options_for(driver, encoding, layer_name, existing_action):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = driver
    options.fileEncoding = encoding or "UTF-8"
    if layer_name:
        options.layerName = layer_name
    if existing_action is not None:
        try:
            options.actionOnExistingFile = existing_action
        except Exception:
            pass  # nosec
    return options


def _output_plan(layers, folder, ext, overwrite):
    used = set()
    plan = []
    for layer in layers:
        name = _safe_name(layer.name())
        candidate = os.path.join(folder, name + ext)
        if not overwrite:
            candidate = _unique_path(candidate)
        while candidate.casefold() in used:
            base, suffix = os.path.splitext(candidate)
            candidate = _unique_path(base + "_x" + suffix)
        used.add(candidate.casefold())
        plan.append((layer, candidate, name))
    return plan


def _add_output(iface, path, layer_name, title):
    uri = path
    if layer_name:
        uri = "%s|layername=%s" % (path, layer_name)
    layer = QgsVectorLayer(uri, title or layer_name or os.path.basename(path), "ogr")
    try:
        if not layer.isValid():
            return
    except Exception:
        return
    try:
        QgsProject.instance().addMapLayer(layer)
    except Exception:
        pass  # nosec


def _write_layers(iface, parent, layers, folder, driver, ext, encoding, add_to_canvas):
    overwrite = True
    planned = _output_plan(layers, folder, ext, True)
    if any(os.path.exists(path) for _layer, path, _name in planned):
        overwrite = ask(parent, tr("批量导出"), tr("文件夹里已有同名文件，是否覆盖？"))
    plan = planned if overwrite else _output_plan(layers, folder, ext, False)
    action = _writer_action("CreateOrOverwriteFile")
    progress = QProgressDialog(tr("正在导出…"), tr("取消"), 0, len(plan), parent)
    progress.setWindowTitle(tr("批量导出"))
    progress.setMinimumDuration(0)
    try:
        # 非模态时，导出过程里的 processEvents 会让用户再点一次导出，两轮写出叠在一起。
        progress.setWindowModality(qt_attr(Qt, "WindowModal"))
    except Exception:
        pass  # nosec
    done = []
    failed = []
    no_error = _no_error()
    for index, (layer, target, layer_name) in enumerate(plan):
        if progress.wasCanceled():
            break
        progress.setValue(index)
        progress.setLabelText(layer.name() or "")
        try:
            from qgis.PyQt.QtWidgets import QApplication

            QApplication.processEvents()
        except Exception:
            pass  # nosec
        options = _options_for(driver, encoding, layer_name, action)
        try:
            result = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                target,
                QgsProject.instance().transformContext(),
                options,
            )
        except Exception as exc:
            failed.append("%s（%s）" % (layer.name() or "", exc))
            continue
        error = result[0] if isinstance(result, tuple) else result
        message = ""
        if isinstance(result, tuple) and len(result) > 1:
            message = str(result[1] or "")
        if enum_int(error, 0) != enum_int(no_error, 0):
            failed.append("%s（%s）" % (layer.name() or "", message or tr("写回失败。")))
            continue
        done.append(layer.name() or target)
        if add_to_canvas:
            _add_output(iface, target, "", layer.name())
    progress.setValue(len(plan))
    if done:
        tell(iface, tr("批量导出"), tr("已导出 %d 个图层。") % len(done))
    if failed:
        tell(
            iface,
            tr("批量导出"),
            tr("%d 个图层没能导出：%s") % (len(failed), "、".join(failed[:8])),
            warning=True,
        )
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec
