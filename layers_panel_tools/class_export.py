# -*- coding: utf-8 -*-
"""分类导出：按 QGIS 图例分类，或按字段的每个值，各写一个文件。"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush, QColor, QFont
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)
from qgis.core import QgsExpression, QgsProject, QgsVectorFileWriter, QgsVectorLayer

from .buttons import make_menu_action as build_menu_action, make_toolbar_button, report
from .export_layers import _extension, _formats, _no_error, _options_for, _safe_name, _writer_action
from .i18n import apply_direction, subscribe, tr
from .icons import load_icon
from .qt_compat import enum_int, qt_attr, run_dialog, user_role
from .scope import selected_layers

_DIALOG = None
_CAP = 50


def make_action(iface):
    tr("分类导出")
    tr("按图例分类或按字段，把一个图层拆成多个文件")
    return make_toolbar_button(
        iface,
        "lpt:class_export",
        "LayersPanelToolsClassExport",
        "分类导出",
        "按图例分类或按字段，把一个图层拆成多个文件",
        load_icon("class_export"),
        lambda: open_class_export(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsClassExportMenu",
        "分类导出",
        "按图例分类或按字段，把一个图层拆成多个文件",
        load_icon("class_export"),
        lambda: open_class_export(iface),
    )


def close_class_export():
    global _DIALOG
    if _DIALOG is not None:
        try:
            _DIALOG.close()
        except RuntimeError:
            pass
    _DIALOG = None


def open_class_export(iface):
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = ClassExportDialog(iface)
    _DIALOG.reload()
    run_dialog(_DIALOG)


def project_folder():
    project = QgsProject.instance()
    path = ""
    try:
        path = project.fileName() or ""
    except Exception:
        path = ""
    folder = os.path.dirname(path) if path else ""
    if folder and os.path.isdir(folder):
        return folder
    home = ""
    try:
        home = project.homePath() or ""
    except Exception:
        home = ""
    if home and os.path.isdir(home):
        return home
    return ""


def _null(value):
    if value is None:
        return True
    try:
        if hasattr(value, "isNull") and value.isNull():
            return True
    except Exception:
        pass  # nosec
    return False


def _one_filter(attr, value):
    text = str(attr or "").strip()
    if not text:
        return ""
    expression = "(" in text or " " in text
    if not expression:
        try:
            return QgsExpression.createFieldEqualityExpression(text, None if _null(value) else value)
        except Exception:
            pass  # nosec
    if _null(value):
        return "(%s) IS NULL" % text
    if isinstance(value, str):
        return "(%s) = '%s'" % (text, value.replace("'", "''"))
    return "(%s) = %s" % (text, value)


def _or_filter(attr, values):
    parts = [item for item in (_one_filter(attr, value) for value in values) if item]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return " OR ".join("(%s)" % item for item in parts)


def legend_classes(layer):
    """(label, filter expression) for a categorized, graduated, or rule renderer."""
    try:
        renderer = layer.renderer()
    except Exception:
        renderer = None
    if renderer is None:
        return []
    try:
        kind = str(renderer.type() or "")
    except Exception:
        return []
    if kind == "categorizedSymbol":
        try:
            attr = renderer.classAttribute() or ""
        except Exception:
            attr = ""
        found = []
        try:
            categories = list(renderer.categories())
        except Exception:
            categories = []
        for category in categories:
            try:
                label = category.label() or ""
            except Exception:
                label = ""
            try:
                value = category.value()
            except Exception:
                value = None
            values = list(value) if isinstance(value, (list, tuple)) else [value]
            if not label:
                label = tr("空值") if len(values) == 1 and _null(values[0]) else "、".join(str(item) for item in values)
            found.append((label, _or_filter(attr, values)))
        return [(label, expr) for label, expr in found if expr]
    if kind == "graduatedSymbol":
        try:
            attr = renderer.classAttribute() or ""
        except Exception:
            attr = ""
        try:
            ranges = list(renderer.ranges())
        except Exception:
            ranges = []
        quoted = attr
        try:
            if attr and "(" not in attr and " " not in attr:
                quoted = QgsExpression.quotedColumnRef(attr)
        except Exception:
            quoted = attr
        found = []
        last = len(ranges) - 1
        for index, item in enumerate(ranges):
            try:
                label = item.label() or ""
                lower = item.lowerValue()
                upper = item.upperValue()
            except Exception:
                continue  # nosec
            if not label:
                label = "%s – %s" % (lower, upper)
            end = "<=" if index == last else "<"
            found.append((label, "(%s >= %s) AND (%s %s %s)" % (quoted, lower, quoted, end, upper)))
        return found
    if kind != "ruleBased":
        return []
    try:
        root = renderer.rootRule()
    except Exception:
        return []
    found = []

    def walk(rule, prefix):
        try:
            children = list(rule.children())
        except Exception:
            children = []
        try:
            label = rule.label() or ""
        except Exception:
            label = ""
        try:
            filt = rule.filterExpression() or ""
        except Exception:
            filt = ""
        title = " / ".join(part for part in (prefix, label) if part)
        if filt.strip() and rule is not root:
            found.append((title or filt, filt))
        for child in children:
            walk(child, title)

    walk(root, "")
    return found


def is_classified(layer):
    try:
        renderer = layer.renderer()
    except Exception:
        return False
    if renderer is None:
        return False
    try:
        kind = str(renderer.type() or "")
    except Exception:
        return False
    return kind in ("categorizedSymbol", "graduatedSymbol", "ruleBased")


def _field_names(layer):
    names = []
    try:
        fields = layer.fields()
        count = fields.count()
    except Exception:
        return names
    for index in range(count):
        try:
            name = fields.at(index).name()
        except Exception:
            name = ""
        if name:
            names.append(name)
    return names


def _combine_subset(current, expression):
    current = str(current or "").strip()
    if not current:
        return expression
    return "(%s) AND (%s)" % (current, expression)


class _LayerCombo(QComboBox):
    """图层只能点选。滚轮留给对话框，避免划过时把图层改掉。"""

    def wheelEvent(self, event):
        event.ignore()


class ClassExportDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setObjectName("LayersPanelToolsClassExportDialog")
        self.resize(460, 280)
        layout = QVBoxLayout(self)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layer_row = QHBoxLayout()
        self.layer_label = QLabel()
        self.layer_box = _LayerCombo()
        layer_row.addWidget(self.layer_label)
        layer_row.addWidget(self.layer_box, 1)
        layout.addLayout(layer_row)
        mode_row = QHBoxLayout()
        self.mode_legend = QRadioButton()
        self.mode_field = QRadioButton()
        self.mode_legend.setChecked(True)
        mode_row.addWidget(self.mode_legend)
        mode_row.addWidget(self.mode_field)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)
        field_row = QHBoxLayout()
        self.field_label = QLabel()
        self.field_box = QComboBox()
        field_row.addWidget(self.field_label)
        field_row.addWidget(self.field_box, 1)
        layout.addLayout(field_row)
        cap_row = QHBoxLayout()
        self.cap_label = QLabel()
        self.cap_box = QSpinBox()
        self.cap_box.setRange(1, 500)
        self.cap_box.setValue(_CAP)
        cap_row.addWidget(self.cap_label)
        cap_row.addWidget(self.cap_box)
        cap_row.addStretch(1)
        layout.addLayout(cap_row)
        format_row = QHBoxLayout()
        self.format_label = QLabel()
        self.format_box = QComboBox()
        for label, driver in _formats():
            self.format_box.addItem(label, driver)
        preferred = self.format_box.findData("ESRI Shapefile")
        if preferred < 0:
            preferred = self.format_box.findData("GPKG")
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
        actions = QHBoxLayout()
        self.btn_export = QPushButton()
        self.btn_close = QPushButton()
        actions.addWidget(self.btn_export)
        actions.addStretch(1)
        actions.addWidget(self.btn_close)
        layout.addLayout(actions)
        self.layer_box.currentIndexChanged.connect(self._on_layer)
        self.mode_legend.toggled.connect(self._sync_mode)
        self.mode_field.toggled.connect(self._sync_mode)
        self.btn_browse.clicked.connect(self._browse)
        self.btn_export.clicked.connect(self._export)
        self.btn_close.clicked.connect(self.close)
        self.retranslate()
        subscribe(self, self.retranslate)

    def retranslate(self, *_args):
        self.setWindowTitle(tr("分类导出"))
        self.hint.setText(tr("选择一个图层。分类图层默认按图例，普通图层默认按字段。每一类或每个不同的值写成一个文件。"))
        self.layer_label.setText(tr("图层"))
        self.mode_legend.setText(tr("按图例分类"))
        self.mode_field.setText(tr("按字段"))
        self.field_label.setText(tr("字段"))
        self.cap_label.setText(tr("每层最多"))
        self.format_label.setText(tr("格式"))
        self.encoding_label.setText(tr("编码"))
        self.folder_label.setText(tr("文件夹"))
        self.btn_browse.setText(tr("浏览"))
        self.btn_export.setText(tr("导出"))
        self.btn_close.setText(tr("关闭"))
        self.cap_box.setToolTip(tr("超过这个数量就跳过该图层，避免一次写出过多文件。"))
        apply_direction(self)
        self._sync_mode()

    def reload(self):
        preferred = ""
        try:
            active = self.iface.activeLayer()
        except Exception:
            active = None
        if isinstance(active, QgsVectorLayer) and active.isValid():
            preferred = active.id()
        if not preferred:
            for layer in selected_layers(self.iface):
                try:
                    if isinstance(layer, QgsVectorLayer) and layer.isValid():
                        preferred = layer.id()
                        break
                except Exception:
                    continue  # nosec
        self.layer_box.blockSignals(True)
        self.layer_box.clear()
        layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                layers.append(layer)
        layers.sort(key=lambda item: (item.name() or "").casefold())
        bold = QFont(self.layer_box.font())
        bold.setBold(True)
        red = QBrush(QColor(176, 0, 0))
        font_role = qt_attr(Qt, "FontRole")
        color_role = qt_attr(Qt, "ForegroundRole")
        for layer in layers:
            count = -1
            try:
                count = int(layer.featureCount())
            except Exception:
                count = -1
            name = layer.name() or ""
            text = "%s（%d）" % (name, count) if count >= 0 else name
            self.layer_box.addItem(text, layer.id())
            row = self.layer_box.count() - 1
            classified = is_classified(layer)
            self.layer_box.setItemData(row, classified, user_role(1))
            if classified:
                self.layer_box.setItemData(row, bold, font_role)
                self.layer_box.setItemData(row, red, color_role)
        if preferred:
            index = self.layer_box.findData(preferred)
            if index >= 0:
                self.layer_box.setCurrentIndex(index)
        self.layer_box.blockSignals(False)
        if not self.folder_edit.text().strip():
            self.folder_edit.setText(project_folder())
        self._on_layer()

    def _current_layer(self):
        layer_id = self.layer_box.currentData()
        if not layer_id:
            return None
        try:
            layer = QgsProject.instance().mapLayer(layer_id)
        except Exception:
            return None
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            return layer
        return None

    def _on_layer(self, *_args):
        classified = bool(self.layer_box.currentData(user_role(1)))
        self.mode_legend.blockSignals(True)
        self.mode_field.blockSignals(True)
        self.mode_legend.setChecked(classified)
        self.mode_field.setChecked(not classified)
        self.mode_legend.blockSignals(False)
        self.mode_field.blockSignals(False)
        self._sync_mode()
        self._fill_fields()

    def _fill_fields(self):
        layer = self._current_layer()
        previous = str(self.field_box.currentText() or "")
        names = _field_names(layer) if layer is not None else []
        self.field_box.blockSignals(True)
        self.field_box.clear()
        for name in names:
            self.field_box.addItem(name)
        if previous:
            index = self.field_box.findText(previous)
            if index >= 0:
                self.field_box.setCurrentIndex(index)
        self.field_box.blockSignals(False)

    def _sync_mode(self, *_args):
        by_field = self.mode_field.isChecked()
        self.field_label.setEnabled(by_field)
        self.field_box.setEnabled(by_field)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, tr("选择导出文件夹"), self.folder_edit.text().strip())
        if folder:
            self.folder_edit.setText(folder)

    def _classes_for(self, layer, field, limit):
        if self.mode_legend.isChecked():
            classes = legend_classes(layer)
            if not classes:
                return None, tr("没有图例分类")
            if len(classes) > limit:
                return None, tr("分类有 %d 个，超过上限 %d") % (len(classes), limit)
            return classes, ""
        if not field:
            return None, tr("请先选择字段。")
        try:
            index = layer.fields().indexFromName(field)
        except Exception:
            index = -1
        if index < 0:
            return None, tr("没有字段「%s」") % field
        try:
            values = list(layer.uniqueValues(index, limit + 1))
        except Exception:
            values = []
        if len(values) > limit:
            return None, tr("不同值超过上限 %d。请提高「每层最多」或换一个字段。") % limit
        classes = []
        for value in values:
            if _null(value):
                label = tr("空值")
            else:
                label = str(value)
            classes.append((label, _one_filter(field, value)))
        classes = [(label, expr) for label, expr in classes if expr]
        if not classes:
            return None, tr("这个字段没有值")
        return classes, ""

    def _export(self):
        layer = self._current_layer()
        if layer is None:
            report(self, tr("分类导出"), tr("请先选择一个图层。"), warning=True)
            return
        folder = self.folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            report(self, tr("分类导出"), tr("请先选择导出文件夹。工程还没保存时，需要指定一个文件夹。"), warning=True)
            return
        driver = str(self.format_box.currentData() or "")
        ext = _extension(driver)
        if not driver or not ext:
            report(self, tr("分类导出"), tr("这个格式不能按文件导出。"), warning=True)
            return
        field = str(self.field_box.currentText() or "") if self.mode_field.isChecked() else ""
        if self.mode_field.isChecked() and not field:
            report(self, tr("分类导出"), tr("这个图层没有可用字段。"), warning=True)
            return
        limit = int(self.cap_box.value())
        classes, reason = self._classes_for(layer, field, limit)
        if not classes:
            report(self, tr("分类导出"), reason, warning=True)
            return
        plan = [(layer, label, expression) for label, expression in classes]
        self._write(plan, folder, driver, ext, [])

    def _write(self, plan, folder, driver, ext, skipped):
        encoding = str(self.encoding_box.currentText() or "UTF-8").strip() or "UTF-8"
        action = _writer_action("CreateOrOverwriteFile")
        used = set()
        targets = []
        for layer, label, expression in plan:
            stem = _safe_name("%s_%s" % (layer.name() or "layer", label or "class"))
            path = os.path.join(folder, stem + ext)
            path = _unique_path(path, used)
            used.add(path.casefold())
            targets.append((layer, label, expression, path))
        progress = QProgressDialog(tr("正在导出…"), tr("取消"), 0, len(targets), self)
        progress.setWindowTitle(tr("分类导出"))
        progress.setMinimumDuration(0)
        try:
            progress.setWindowModality(qt_attr(Qt, "WindowModal"))
        except Exception:
            pass  # nosec
        done = []
        failed = list(skipped)
        no_error = _no_error()
        for index, (layer, label, expression, path) in enumerate(targets):
            if progress.wasCanceled():
                break
            progress.setValue(index)
            progress.setLabelText("%s / %s" % (layer.name() or "", label))
            try:
                from qgis.PyQt.QtWidgets import QApplication

                QApplication.processEvents()
            except Exception:
                pass  # nosec
            old = ""
            try:
                old = layer.subsetString() or ""
            except Exception:
                old = ""
            try:
                layer.setSubsetString(_combine_subset(old, expression))
                options = _options_for(driver, encoding, _safe_name(label), action)
                result = QgsVectorFileWriter.writeAsVectorFormatV3(
                    layer,
                    path,
                    QgsProject.instance().transformContext(),
                    options,
                )
            except Exception as exc:
                failed.append("%s / %s（%s）" % (layer.name() or "", label, exc))
                result = None
            finally:
                try:
                    layer.setSubsetString(old)
                except Exception:
                    pass  # nosec
            if result is None:
                continue
            error = result[0] if isinstance(result, tuple) else result
            message = ""
            if isinstance(result, tuple) and len(result) > 1:
                message = str(result[1] or "")
            if enum_int(error, 0) != enum_int(no_error, 0):
                failed.append("%s / %s（%s）" % (layer.name() or "", label, message or tr("写回失败。")))
                continue
            done.append(path)
        progress.setValue(len(targets))
        try:
            for layer, _label, _expression, _path in targets:
                layer.triggerRepaint()
        except Exception:
            pass  # nosec
        if done and not failed:
            report(self, tr("分类导出"), tr("已导出 %d 个文件到：\n%s") % (len(done), folder))
        elif failed:
            report(
                self,
                tr("分类导出"),
                tr("写成 %d 个文件，%d 个没能导出：%s") % (len(done), len(failed), "、".join(failed[:8])),
                warning=True,
            )


def _unique_path(path, used):
    if not os.path.exists(path) and path.casefold() not in used:
        return path
    folder, filename = os.path.split(path)
    stem, ext = os.path.splitext(filename)
    number = 2
    while True:
        candidate = os.path.join(folder, "%s_%d%s" % (stem, number, ext))
        if not os.path.exists(candidate) and candidate.casefold() not in used:
            return candidate
        number += 1
