# -*- coding: utf-8 -*-
"""Split a vector layer into one subset layer per unique field value."""

from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
)

from qgis.core import QgsExpression, QgsProject, QgsVectorLayer

from .buttons import make_menu_action as build_menu_action, make_toolbar_button, report
from .i18n import apply_direction, tr, subscribe
from .icons import load_icon
from .qt_compat import qt_attr, run_dialog
from .scope import is_vector, selected_layers

_MAX_DEFAULT = 50
_PREVIEW = 50
_DIALOG = None


def make_action(iface):
    tr("按字段拆分图层")
    tr("按字段值拆分为多个子集图层，可预览、可放进新组")
    return make_toolbar_button(
        iface,
        "lpt:split_field",
        "LayersPanelToolsSplitField",
        "按字段拆分图层",
        "按字段值拆分为多个子集图层，可预览、可放进新组",
        load_icon("split_field"),
        lambda: open_split(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsSplitFieldMenu",
        "按字段拆分图层",
        "按字段值拆分为多个子集图层，可预览、可放进新组",
        load_icon("split_field"),
        lambda: open_split(iface),
    )


def close_split():
    global _DIALOG
    if _DIALOG is not None:
        try:
            _DIALOG.close()
        except RuntimeError:
            pass
    _DIALOG = None


def open_split(iface):
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = SplitDialog(iface)
    _DIALOG.prepare()
    run_dialog(_DIALOG)


class SplitDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle(tr("按字段拆分图层"))
        layout = QVBoxLayout(self)
        self.hint = QLabel()
        layout.addWidget(self.hint)
        self.layer = QComboBox()
        layout.addWidget(self.layer)
        row = layout
        self.field = QComboBox()
        layout.addWidget(self.field)
        self.chk_group = QCheckBox()
        self.chk_group.setChecked(True)
        layout.addWidget(self.chk_group)
        self.chk_hide = QCheckBox()
        layout.addWidget(self.chk_hide)
        self.max_box = QSpinBox()
        self.max_box.setRange(2, 500)
        self.max_box.setValue(_MAX_DEFAULT)
        layout.addWidget(QLabel(tr("最多拆分多少个值（超出会提示）")))
        layout.addWidget(self.max_box)
        self.preview = QListWidget()
        self.preview.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.preview)
        self.box = QDialogButtonBox()
        cancel_flag = qt_attr(QDialogButtonBox, "Cancel")
        self.box.addButton(cancel_flag)
        self.run_btn = self.box.addButton(tr("拆分"), qt_attr(QDialogButtonBox, "ActionRole"))
        self.run_btn.clicked.connect(self._accept)
        self.box.rejected.connect(self.reject)
        layout.addWidget(self.box)
        apply_direction(self)
        subscribe(self, self._retranslate)
        self._retranslate()

    def _retranslate(self):
        self.setWindowTitle(tr("按字段拆分图层"))
        self.hint.setText(tr("默认带出当前图层，也可改选其它矢量图层。按字段的每个不同值各建一个子集图层（同源过滤，不改原数据）。"))
        self.chk_group.setText(tr("把子集图层放进新组"))
        self.chk_hide.setText(tr("拆分后隐藏原图层"))
        self.run_btn.setText(tr("拆分"))

    def prepare(self):
        self._retranslate()
        try:
            self.layer.currentIndexChanged.disconnect(self._refill)
        except Exception:
            pass  # nosec
        try:
            self.field.currentIndexChanged.disconnect(self._preview)
        except Exception:
            pass  # nosec
        self.layer.clear()
        self.field.clear()
        self.preview.clear()
        self._value_cache = {}
        vectors = [layer for layer in QgsProject.instance().mapLayers().values() if is_vector(layer)]
        try:
            vectors.sort(key=lambda layer: (str(layer.name() or "").casefold()))
        except Exception:
            pass  # nosec
        default = -1
        try:
            active = self.iface.activeLayer()
        except Exception:
            active = None
        selected_ids = set()
        try:
            for layer in selected_layers(self.iface):
                selected_ids.add(layer.id())
        except Exception:
            pass  # nosec
        for position, layer in enumerate(vectors):
            self.layer.addItem(layer.name(), layer)
            if active is not None and layer.id() == active.id():
                default = position
            elif default < 0 and layer.id() in selected_ids:
                default = position
        if default < 0 and self.layer.count():
            default = 0
        self.layer.currentIndexChanged.connect(self._refill)
        self.field.currentIndexChanged.connect(self._preview)
        if default >= 0:
            self.layer.setCurrentIndex(default)
        self._refill_fields()
        self._preview()

    def _refill(self, *_args):
        self._refill_fields()
        self._preview()

    def _refill_fields(self):
        self.field.clear()
        layer = self.layer.currentData()
        if layer is None or not is_vector(layer):
            return
        for field in layer.fields():
            self.field.addItem(field.name())

    def _unique_values(self, layer, field_name):
        index = -1
        try:
            index = layer.fields().indexOf(field_name)
        except Exception:
            return []
        if index < 0:
            return []
        cache = getattr(self, "_value_cache", None)
        if cache is None:
            cache = {}
            self._value_cache = cache
        # 只向数据源要「上限 + 1」个不同值。大表上无上限的 uniqueValues 会把界面卡住，
        # 而拆分本来就会在超过上限时被拦下，多出来的值用不到。
        try:
            cap = int(self.max_box.value()) + 1
        except Exception:
            cap = _MAX_DEFAULT + 1
        key = (layer.id(), field_name, index, cap)
        if key in cache:
            return cache[key]
        try:
            values = list(layer.uniqueValues(index, cap))
        except TypeError:
            try:
                values = list(layer.uniqueValues(index))
            except Exception:
                values = []
        except Exception:
            values = []
        cache[key] = values
        return values

    def _preview(self, *_args):
        self.preview.clear()
        layer = self.layer.currentData()
        field_name = self.field.currentText()
        if layer is None or not field_name:
            return
        values = self._unique_values(layer, field_name)
        try:
            values.sort(key=lambda v: (v is None, str(v).casefold()))
        except Exception:
            pass  # nosec
        limit = int(self.max_box.value())
        shown = values[:_PREVIEW]
        for value in shown:
            text = "NULL" if value is None else str(value)
            item = QListWidgetItem(text)
            self.preview.addItem(item)
        tail = tr("共 %d 个不同值。") % len(values)
        if len(values) > _PREVIEW:
            tail = tr("共 %d 个不同值，只列前 %d 个。") % (len(values), _PREVIEW)
        if len(values) > limit:
            tail += " " + tr("超过上限 %d，拆分会被拦下。") % limit
        QListWidgetItem(tail, self.preview)

    def _accept(self):
        layer = self.layer.currentData()
        if layer is None or not is_vector(layer):
            return
        field_name = self.field.currentText()
        if not field_name:
            return
        limit = int(self.max_box.value())
        values = self._unique_values(layer, field_name)
        try:
            values.sort(key=lambda v: (v is None, str(v).casefold()))
        except Exception:
            pass  # nosec
        if len(values) > limit:
            report(self, tr("按字段拆分图层"), tr("不同值有 %d 个，超过上限 %d。请换字段或提高上限。") % (len(values), limit), warning=True)
            return
        if not values:
            report(self, tr("按字段拆分图层"), tr("这个字段没有可用值。"), warning=True)
            return
        root = QgsProject.instance().layerTreeRoot()
        target = root
        try:
            node = root.findLayer(layer.id())
            parent = node.parent() if node is not None else root
        except Exception:
            parent = root
        use_group = self.chk_group.isChecked()
        if use_group:
            group_name = "%s · %s" % (layer.name(), field_name)
            try:
                existing = parent.findGroup(group_name)
            except Exception:
                existing = None
            if existing is None:
                try:
                    index = None
                    try:
                        index = parent.children().index(node) + 1 if node is not None else 0
                    except (ValueError, Exception):
                        index = 0
                    target = parent.insertGroup(index, group_name)
                except Exception:
                    target = root.addGroup(group_name)
            else:
                target = existing
        renderer = None
        try:
            renderer = layer.renderer().clone()
        except Exception:
            renderer = None
        base_index = 0
        try:
            base_index = parent.children().index(node) + 1 if node is not None else 0
        except Exception:
            base_index = len(parent.children())
        for value in values:
            if value is None:
                label = tr("空值")
                subset = "%s IS NULL" % QgsExpression.quotedColumnRef(field_name)
            else:
                label = str(value)
                subset = "%s = %s" % (QgsExpression.quotedColumnRef(field_name), QgsExpression.quotedValue(value))
            child_name = label if use_group else "%s — %s" % (layer.name(), label)
            child = QgsVectorLayer(layer.source(), child_name, layer.providerType())
            if not child.isValid():
                continue
            try:
                child.setSubsetString(subset)
            except Exception:
                continue  # nosec
            try:
                child.setCrs(layer.crs())
            except Exception:
                pass  # nosec
            if renderer is not None:
                try:
                    child.setRenderer(renderer.clone())
                except Exception:
                    pass  # nosec
            QgsProject.instance().addMapLayer(child, False)
            try:
                if use_group:
                    target.addLayer(child)
                else:
                    parent.insertLayer(base_index, child)
                    base_index += 1
            except Exception:
                QgsProject.instance().layerTreeRoot().addLayer(child)
        if self.chk_hide.isChecked():
            try:
                node.setItemVisibilityChecked(False)
            except Exception:
                pass  # nosec
        self.accept()
