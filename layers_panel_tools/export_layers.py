# -*- coding: utf-8 -*-
"""批量要素另存为：勾选多个点、线、面图层，选一个文件夹，用 QGIS 的写出接口各存一份。"""

import csv
import os
import shutil
import tempfile

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
from qgis.core import (
    QgsCoordinateTransform,
    QgsField,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from .buttons import ask, make_menu_action as build_menu_action, make_toolbar_button, qt_attr, report
from .export_logic import merge_kind, merged_extension, unique_layer_name
from .i18n import apply_direction, tr, subscribe
from .icons import load_icon
from .qt_compat import enum_int, user_role
from .scope import geometry_code

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
    _DIALOG.stack_box.setChecked(False)
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
        "ODS": ".ods",
        "OpenFileGDB": ".gdb",
        "FileGDB": ".gdb",
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
        self.merge_box = QCheckBox()
        self.stack_box = QCheckBox()
        option_row = QHBoxLayout()
        option_row.addWidget(self.add_canvas)
        option_row.addSpacing(18)
        option_row.addWidget(self.merge_box)
        option_row.addSpacing(18)
        option_row.addWidget(self.stack_box)
        option_row.addStretch(1)
        layout.addLayout(option_row)
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
        self.format_box.currentIndexChanged.connect(self._sync_merge)
        self.merge_box.toggled.connect(self._sync_merge)
        self.merge_box.setChecked(False)
        self.stack_box.setChecked(False)
        self.stack_box.setVisible(False)
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
        self.merge_box.setText(tr("合并为一个文件"))
        self.stack_box.setText(tr("并成同一个表"))
        self.stack_box.setToolTip(tr(
            "不勾选时，每个图层一个工作表，表名是图层名。"
            "CSV 本身不能有多个工作表，所以会写成同名的 Excel 文件。"
            "勾选后并进同一个 CSV 表：同名字段只出现一次，每个图层的字段都会保留，并加一列记下原来的图层名。"
        ))
        self.btn_export.setText(tr("导出"))
        self.btn_close.setText(tr("关闭"))
        apply_direction(self)
        self._sync_merge()
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
        current = self.folder_edit.text().strip()
        if self._merge_on():
            driver = str(self.format_box.currentData() or "")
            ext = merged_extension(driver, _extension(driver))
            start_dir = current if os.path.isdir(current) else os.path.dirname(current)
            if not start_dir or not os.path.isdir(start_dir):
                start_dir = _project_dir()
            stem = ""
            if current and not os.path.isdir(current):
                stem = os.path.splitext(os.path.basename(current))[0]
            if not stem:
                stem = os.path.splitext(os.path.basename(_merged_filename(start_dir or ".", ext or "")))[0]
            suggestion = os.path.join(start_dir, stem + ext) if start_dir else (stem + ext)
            label = self.format_box.currentText() or driver
            chosen, _selected = QFileDialog.getSaveFileName(
                self,
                tr("保存合并文件"),
                suggestion,
                "%s (*%s)" % (label, ext or ".*"),
            )
            if chosen:
                if ext and not chosen.lower().endswith(ext.lower()):
                    chosen += ext
                self.folder_edit.setText(chosen)
            return
        start = os.path.dirname(current) if current and not os.path.isdir(current) else current
        folder = QFileDialog.getExistingDirectory(self, tr("选择导出文件夹"), start)
        if folder:
            self.folder_edit.setText(folder)

    def _merge_on(self):
        return self.merge_box.isEnabled() and self.merge_box.isChecked()

    def _export(self):
        layers = self._chosen_layers()
        if not layers:
            report(self, tr("批量导出"), tr("请先勾选要导出的图层。"), warning=True)
            return
        driver = str(self.format_box.currentData() or "")
        encoding = str(self.encoding_box.currentText() or "UTF-8").strip() or "UTF-8"
        ext = _extension(driver)
        if not driver or not ext:
            report(self, tr("批量导出"), tr("这个格式不能按文件导出。"), warning=True)
            return
        text = self.folder_edit.text().strip()
        merge = self._merge_on()
        target = ""
        if merge:
            if not text or os.path.isdir(text):
                report(self, tr("批量导出"), tr("请先选择要保存的文件。"), warning=True)
                return
            folder = os.path.dirname(text)
            if folder and not os.path.isdir(folder):
                report(self, tr("批量导出"), tr("请先选择导出文件夹。"), warning=True)
                return
            target = text
        else:
            folder = text
            if not folder or not os.path.isdir(folder):
                report(self, tr("批量导出"), tr("请先选择导出文件夹。"), warning=True)
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
            merge,
            target,
            self.stack_box.isChecked(),
        )

    def _sync_merge(self, *_args):
        driver = str(self.format_box.currentData() or "")
        kind = merge_kind(driver)
        self.merge_box.setEnabled(bool(kind))
        if not kind and self.merge_box.isChecked():
            self.merge_box.blockSignals(True)
            self.merge_box.setChecked(False)
            self.merge_box.blockSignals(False)
        if kind == "stack":
            self.merge_box.setToolTip(tr("勾选后，这些图层的要素写入同一个文件，并加一列记下原来的图层名。点、线、面可以放在一起。"))
        elif kind:
            self.merge_box.setToolTip(tr("勾选后，多个图层写入你选定的那一个文件。"))
        else:
            self.merge_box.setToolTip(tr("这个格式一个文件只能放一个图层。"))
        show_stack = kind == "stack" and self._merge_on()
        self.stack_box.setVisible(show_stack)
        if not show_stack and self.stack_box.isChecked():
            self.stack_box.blockSignals(True)
            self.stack_box.setChecked(False)
            self.stack_box.blockSignals(False)
        self._sync_target_mode()

    def _sync_target_mode(self):
        merge = self._merge_on()
        self.folder_label.setText(tr("文件") if merge else tr("文件夹"))
        text = self.folder_edit.text().strip()
        driver = str(self.format_box.currentData() or "")
        ext = merged_extension(driver, _extension(driver))
        if merge:
            if not text or not ext:
                return
            if os.path.isdir(text):
                self.folder_edit.setText(_merged_filename(text, ext))
                return
            root, old_ext = os.path.splitext(text)
            if old_ext.lower() != ext.lower():
                self.folder_edit.setText(root + ext)
            return
        if text and not os.path.isdir(text):
            folder = os.path.dirname(text)
            if folder:
                self.folder_edit.setText(folder)


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


def _write_layers(iface, parent, layers, folder, driver, ext, encoding, add_to_canvas, merge=False, target="", one_table=False):
    if merge and merge_kind(driver):
        _write_merged(iface, parent, layers, folder, driver, ext, encoding, add_to_canvas, target, one_table)
        return
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
    if failed:
        report(
            parent,
            tr("批量导出"),
            tr("%d 个图层没能导出：%s") % (len(failed), "、".join(failed[:8])),
            warning=True,
        )
    elif done:
        report(parent, tr("批量导出"), tr("已导出 %d 个文件到：\n%s") % (len(done), folder))
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec


def _merged_filename(folder, ext):
    project = QgsProject.instance()
    stem = ""
    try:
        stem = os.path.splitext(os.path.basename(project.fileName() or ""))[0]
    except Exception:
        stem = ""
    stem = _safe_name(stem or tr("合并图层"))
    return os.path.join(folder, stem + ext)


def _project_dir():
    project = QgsProject.instance()
    path = ""
    try:
        path = project.fileName() or ""
    except Exception:
        path = ""
    folder = os.path.dirname(path) if path else ""
    if folder and os.path.isdir(folder):
        return folder
    try:
        home = project.homePath() or ""
    except Exception:
        home = ""
    if home and os.path.isdir(home):
        return home
    return ""


def _string_field(name):
    try:
        from qgis.PyQt.QtCore import QVariant

        return QgsField(name, QVariant.String)
    except Exception:
        from qgis.PyQt.QtCore import QMetaType

        return QgsField(name, QMetaType.Type.QString)


def _stack_field_name(layers):
    used = set()
    for layer in layers:
        try:
            fields = layer.fields()
            for index in range(fields.count()):
                used.add(str(fields.at(index).name() or "").casefold())
        except Exception:
            continue  # nosec
    candidate = "layer"
    number = 2
    while candidate.casefold() in used:
        candidate = "layer_%d" % number
        number += 1
    return candidate


def _text_encoding(name):
    text = str(name or "UTF-8").strip() or "UTF-8"
    if text.lower() == "system":
        return "mbcs" if os.name == "nt" else "utf-8"
    return text


def _read_csv_table(path, encoding):
    last = None
    for codec in (encoding, "utf-8-sig", "utf-8"):
        try:
            with open(path, "r", encoding=codec, newline="") as handle:
                rows = list(csv.reader(handle))
        except Exception as exc:
            last = exc
            continue
        if not rows:
            return [], []
        return list(rows[0]), [list(row) for row in rows[1:]]
    if last is not None:
        raise last
    return [], []


def _write_csv_table(path, encoding, headers, rows):
    with open(path, "w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
    types = []
    for name in headers:
        types.append("WKT" if str(name).casefold() in ("wkt", "geometry") else "String")
    csvt = os.path.splitext(path)[0] + ".csvt"
    with open(csvt, "w", encoding="utf-8", newline="") as handle:
        handle.write(",".join('"%s"' % item for item in types))


def _write_one_csv(iface, parent, layers, encoding, add_to_canvas, target, first_action):
    """One CSV table: same field name once, every field from every layer kept."""
    if first_action is None:
        report(parent, tr("批量导出"), tr("这一版 QGIS 不能把多个图层写进同一个文件。"), warning=True)
        return
    codec = _text_encoding(encoding)
    source_field = _stack_field_name(layers)
    anchor = None
    if layers:
        try:
            anchor = layers[0].crs()
        except Exception:
            anchor = None
    progress = QProgressDialog(tr("正在导出…"), tr("取消"), 0, len(layers), parent)
    progress.setWindowTitle(tr("批量导出"))
    progress.setMinimumDuration(0)
    try:
        progress.setWindowModality(qt_attr(Qt, "WindowModal"))
    except Exception:
        pass  # nosec
    no_error = _no_error()
    tables = []
    failed = []
    folder = tempfile.mkdtemp(prefix="lpt_csv_")
    try:
        for index, layer in enumerate(layers):
            if progress.wasCanceled():
                break
            progress.setValue(index)
            progress.setLabelText(layer.name() or "")
            try:
                from qgis.PyQt.QtWidgets import QApplication

                QApplication.processEvents()
            except Exception:
                pass  # nosec
            part = os.path.join(folder, "part_%d.csv" % index)
            options = _options_for("CSV", encoding, "part", first_action)
            options.layerOptions = ["GEOMETRY=AS_WKT", "CREATE_CSVT=YES"]
            if anchor is not None:
                try:
                    source_crs = layer.crs()
                    if source_crs.isValid() and anchor.isValid() and source_crs != anchor:
                        options.ct = QgsCoordinateTransform(source_crs, anchor, QgsProject.instance())
                except Exception:
                    pass  # nosec
            try:
                result = QgsVectorFileWriter.writeAsVectorFormatV3(
                    layer,
                    part,
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
            try:
                header, rows = _read_csv_table(part, codec)
            except Exception as exc:
                failed.append("%s（%s）" % (layer.name() or "", exc))
                continue
            tables.append((layer.name() or "", header, rows))
        progress.setValue(len(layers))
        if tables:
            headers = []
            seen = set()
            for _name, header, _rows in tables:
                for column in header:
                    if column in seen:
                        continue
                    seen.add(column)
                    headers.append(column)
            if source_field not in seen:
                headers.append(source_field)
            body = []
            for layer_name, header, rows in tables:
                index_of = {}
                for column_index, column in enumerate(header):
                    index_of.setdefault(column, column_index)
                for row in rows:
                    out = []
                    for column in headers:
                        if column == source_field and column not in index_of:
                            out.append(layer_name)
                        elif column in index_of and index_of[column] < len(row):
                            out.append(row[index_of[column]])
                        else:
                            out.append(layer_name if column == source_field else "")
                    body.append(out)
            try:
                _write_csv_table(target, codec, headers, body)
            except Exception as exc:
                failed.append("%s（%s）" % (os.path.basename(target), exc))
                tables = []
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if add_to_canvas and tables:
        _add_output(iface, target, "", os.path.splitext(os.path.basename(target))[0])
    if tables and not failed:
        report(parent, tr("批量导出"), tr("已写入 %s，共 %d 个图层。") % (target, len(tables)))
    elif failed:
        report(
            parent,
            tr("批量导出"),
            tr("合并文件 %s 里写入了 %d 个图层，%d 个没能写入：%s")
            % (target, len(tables), len(failed), "、".join(failed[:8])),
            warning=True,
        )
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec


def _write_merged(iface, parent, layers, folder, driver, ext, encoding, add_to_canvas, target="", one_table=False):
    kind = merge_kind(driver)
    csv_as_book = kind == "stack" and not one_table
    if csv_as_book:
        driver = "XLSX"
        ext = ".xlsx"
        kind = "sheets"
    else:
        ext = merged_extension(driver, ext)
    if target:
        if csv_as_book:
            target = os.path.splitext(target)[0] + ext
        elif ext and not str(target).lower().endswith(ext.lower()):
            target = target + ext
    else:
        target = _unique_path(_merged_filename(folder, ext))
    if os.path.exists(target):
        if not ask(parent, tr("批量导出"), tr("这个文件已经存在，是否覆盖？")):
            return
    first_action = _writer_action("CreateOrOverwriteFile")
    next_action = _writer_action("CreateOrOverwriteLayer")
    if kind == "stack":
        _write_one_csv(iface, parent, layers, encoding, add_to_canvas, target, first_action)
        return
    if first_action is None or next_action is None:
        report(parent, tr("批量导出"), tr("这一版 QGIS 不能把多个图层写进同一个文件。"), warning=True)
        return
    limit = 31 if kind == "sheets" else 0
    progress = QProgressDialog(tr("正在导出…"), tr("取消"), 0, len(layers), parent)
    progress.setWindowTitle(tr("批量导出"))
    progress.setMinimumDuration(0)
    try:
        progress.setWindowModality(qt_attr(Qt, "WindowModal"))
    except Exception:
        pass  # nosec
    used_names = []
    written = []
    failed = []
    started = False
    no_error = _no_error()
    for index, layer in enumerate(layers):
        if progress.wasCanceled():
            break
        progress.setValue(index)
        progress.setLabelText(layer.name() or "")
        try:
            from qgis.PyQt.QtWidgets import QApplication

            QApplication.processEvents()
        except Exception:
            pass  # nosec
        layer_name = unique_layer_name(layer.name() or "layer", used_names, limit)
        action = next_action if started else first_action
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
        started = True
        written.append((layer_name, layer.name() or layer_name))
    progress.setValue(len(layers))
    if add_to_canvas and written:
        if kind == "dxf":
            _add_output(iface, target, "", os.path.splitext(os.path.basename(target))[0])
        else:
            for layer_name, title in written:
                _add_output(iface, target, layer_name, title)
    if written and not failed:
        if csv_as_book:
            report(
                parent,
                tr("批量导出"),
                tr("已写入 %s。CSV 不能分成多个工作表，已改写成 Excel：每个图层一个表，表名是图层名。") % target,
            )
        elif kind == "dxf":
            report(parent, tr("批量导出"), tr("已写入 %s。DXF 会丢掉大部分属性，只保留几何和图层名。") % target, warning=True)
        else:
            report(parent, tr("批量导出"), tr("已写入 %s，共 %d 个图层。") % (target, len(written)))
    elif failed:
        report(
            parent,
            tr("批量导出"),
            tr("合并文件 %s 里写入了 %d 个图层，%d 个没能写入：%s")
            % (target, len(written), len(failed), "、".join(failed[:8])),
            warning=True,
        )
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec
