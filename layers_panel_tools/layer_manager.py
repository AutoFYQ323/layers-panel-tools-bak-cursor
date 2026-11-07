# -*- coding: utf-8 -*-
"""图层管理：列表 + 字段、样式/标注、复制粘贴样式等。"""

from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from qgis.core import QgsMapLayer, QgsProject, QgsVectorLayer

from .buttons import make_menu_action as build_menu_action, make_toolbar_button, qt_attr
from .i18n import apply_direction, tr, subscribe
from .icons import load_icon
from .qt_compat import enum_int, qt_attr as qta
from .qt_compat import user_role
from .label_toggle import _apply as _apply_labels
from .scope import geometry_code, select_nodes, tell
from . import style_copy

_COL_VIS = 0
_COL_NAME = 1
_COL_COUNT = 2
_COL_GEOM = 3
_COL_STORE = 4
_COL_CRS = 5
_COL_FIELDS = 6
_COL_LABEL = 7
_COL_OPACITY = 8

_DIALOG = None


def make_action(iface):
    tr("图层管理")
    tr("列表中开关图层、改字段、打开符号/标注，并复制粘贴样式")
    return make_toolbar_button(
        iface,
        "lpt:layer_manager",
        "LayersPanelToolsLayerManager",
        "图层管理",
        "列表中开关图层、改字段、打开符号/标注，并复制粘贴样式",
        load_icon("layer_manager"),
        lambda: open_layer_manager(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsLayerManagerMenu",
        "图层管理",
        "列表中开关图层、改字段、打开符号/标注，并复制粘贴样式",
        load_icon("layer_manager"),
        lambda: open_layer_manager(iface),
    )


def open_layer_manager(iface):
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = LayerManagerDialog(iface, iface.mainWindow())
    elif not _DIALOG._listening:
        # ???????closeEvent ??????????????????????
        _DIALOG._unhook_project()
        _DIALOG._listening = True
        _DIALOG._hook_project()
    _DIALOG.reload()
    _DIALOG.show()
    _DIALOG.raise_()
    _DIALOG.activateWindow()


def close_layer_manager():
    global _DIALOG
    dialog = _DIALOG
    _DIALOG = None
    if dialog is not None:
        try:
            dialog.close()
        except RuntimeError:
            pass


def _fields_summary(layer):
    if not isinstance(layer, QgsVectorLayer):
        return ""
    try:
        fields = layer.fields()
    except Exception:
        return ""
    names = []
    try:
        for i in range(fields.count()):
            names.append(fields.at(i).name() or "")
    except Exception:
        return ""
    text = ", ".join([n for n in names if n][:12])
    if len(names) > 12:
        text = text + "…"
    return text


def _labels_on(layer):
    if not isinstance(layer, QgsVectorLayer):
        return False
    try:
        if layer.labeling() is None:
            return False
        return bool(layer.labelsEnabled())
    except Exception:
        return False


def _opacity_percent(layer):
    try:
        op = float(layer.opacity()) if layer.opacity() <= 1.0 else float(layer.opacity()) / 100.0
    except Exception:
        return ""
    try:
        return int(round(op * 100))
    except Exception:
        return ""


def _open_props(iface, layer, pages):
    if layer is None:
        return False
    showp = getattr(iface, "showLayerProperties", None)
    if not callable(showp):
        return False
    for page in pages:
        try:
            showp(layer, page)
            return True
        except TypeError:
            continue
        except Exception:
            continue  # nosec
    try:
        showp(layer)
    except Exception:
        return False
    return True


def _show_styling(iface, layer, category=None, prop_pages=()):
    if layer is None:
        return
    try:
        iface.layerTreeView().setCurrentLayer(layer)
    except Exception:
        pass  # nosec
    try:
        iface.setActiveLayer(layer)
    except Exception:
        pass  # nosec
    if prop_pages:
        if _open_props(iface, layer, prop_pages):
            return
    show = getattr(iface, "showLayerStylingPanel", None)
    opened = False
    if callable(show):
        try:
            show(layer)
            opened = True
        except Exception:
            opened = False
    if opened and category is not None:
        dock = getattr(iface, "mapStylingDock", None)
        widget = None
        if dock is not None:
            wfn = getattr(dock, "widget", None)
            if callable(wfn):
                try:
                    widget = wfn()
                except Exception:
                    widget = None
        if widget is None:
            widget = getattr(iface, "mapStyleWidget", None) or getattr(iface, "layerStyleWidget", None)
        if widget is not None:
            setter = getattr(widget, "setCurrentStyleCategory", None) or getattr(widget, "setLayerPanel", None)
            if callable(setter):
                try:
                    setter(category)
                except Exception:
                    pass  # nosec
        return
    if prop_pages:
        _open_props(iface, layer, prop_pages)


class LayerManagerDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setObjectName("LayersPanelToolsLayerManager")
        self.resize(900, 480)
        self._updating = False
        self._listening = False
        self._project_hooks = []

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        layout.addWidget(self.search)

        self.table = QTableWidget(0, 9)
        self._header_labels()
        self.table.setSelectionBehavior(qt_attr(QAbstractItemView, "SelectRows"))
        self.table.setEditTriggers(
            qt_attr(QAbstractItemView, "DoubleClicked") | qt_attr(QAbstractItemView, "EditKeyPressed")
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        row_work = QHBoxLayout()
        self.btn_jump = QPushButton()
        self.btn_symbology = QPushButton()
        self.btn_labels = QPushButton()
        self.btn_fields = QPushButton()
        self.btn_properties = QPushButton()
        for button in (self.btn_jump, self.btn_symbology, self.btn_labels, self.btn_fields, self.btn_properties):
            row_work.addWidget(button, 1)
        layout.addLayout(row_work)

        row_style = QHBoxLayout()
        self.btn_copy = QPushButton()
        self.btn_paste_all = QPushButton()
        self.btn_paste_sym = QPushButton()
        self.btn_paste_lbl = QPushButton()
        self.btn_close = QPushButton()
        for button in (self.btn_copy, self.btn_paste_all, self.btn_paste_sym, self.btn_paste_lbl, self.btn_close):
            row_style.addWidget(button, 1)
        layout.addLayout(row_style)

        self.search.textChanged.connect(self._filter_only)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.itemDoubleClicked.connect(self._on_double)
        self.table.viewport().installEventFilter(self)
        self.btn_jump.clicked.connect(self._jump)
        self.btn_symbology.clicked.connect(self._symbology)
        self.btn_labels.clicked.connect(self._labels)
        self.btn_fields.clicked.connect(self._fields)
        self.btn_properties.clicked.connect(self._properties)
        self.btn_copy.clicked.connect(self._copy_style)
        self.btn_paste_all.clicked.connect(lambda: self._paste_style("all"))
        self.btn_paste_sym.clicked.connect(lambda: self._paste_style("symbols"))
        self.btn_paste_lbl.clicked.connect(lambda: self._paste_style("labels"))
        self.btn_close.clicked.connect(self.close)

        self.retranslate()
        subscribe(self, self.retranslate)
        self._listening = True
        self._hook_project()

    def _header_labels(self):
        self.table.setHorizontalHeaderLabels(
            [
                tr("显示"),
                tr("名称"),
                tr("要素数"),
                tr("几何"),
                tr("存储格式"),
                tr("坐标系"),
                tr("字段摘要"),
                tr("标注"),
                tr("透明度%"),
            ]
        )

    def retranslate(self, *_args):
        self.setWindowTitle(tr("图层管理"))
        self.search.setPlaceholderText(tr("筛选名称、字段或存储格式…"))
        self.btn_jump.setText(tr("定位到图层面板"))
        self.btn_symbology.setText(tr("符号化"))
        self.btn_labels.setText(tr("标注"))
        self.btn_fields.setText(tr("字段"))
        self.btn_properties.setText(tr("属性"))
        self.btn_copy.setText(tr("复制样式"))
        self.btn_paste_all.setText(tr("粘贴全部样式"))
        self.btn_paste_sym.setText(tr("粘贴符号"))
        self.btn_paste_lbl.setText(tr("粘贴标注"))
        self.btn_close.setText(tr("关闭"))
        self._header_labels()
        apply_direction(self)
        self.reload()

    def closeEvent(self, event):
        if self._listening:
            self._listening = False
            self._unhook_project()
        super().closeEvent(event)

    def _hook_project(self):
        project = QgsProject.instance()
        root = project.layerTreeRoot()

        def _reload(*_args):
            if self._listening and not self._updating:
                self.reload()

        for signal in (project.layersAdded, project.layersWillBeRemoved):
            if signal is not None:
                try:
                    signal.connect(_reload)
                    self._project_hooks.append((signal, _reload))
                except Exception:
                    pass  # nosec
        vis = getattr(root, "visibilityChanged", None)
        if vis is not None:
            try:
                vis.connect(_reload)
                self._project_hooks.append((vis, _reload))
            except Exception:
                pass  # nosec

    def _unhook_project(self):
        for signal, slot in self._project_hooks:
            try:
                signal.disconnect(slot)
            except Exception:
                pass  # nosec
        self._project_hooks.clear()

    def reload(self):
        if not self._listening:
            return
        self._updating = True
        try:
            needle = self.search.text().strip().casefold()
            self.table.blockSignals(True)
            self.table.setRowCount(0)
            base_flags = qta(Qt, "ItemIsEnabled") | qta(Qt, "ItemIsSelectable")
            for layer in QgsProject.instance().mapLayers().values():
                if layer is None:
                    continue
                try:
                    name = layer.name() or ""
                except Exception:
                    continue  # nosec
                g = _geometry_kind(layer)
                row = self.table.rowCount()
                self.table.insertRow(row)
                vis_item = QTableWidgetItem(self._vis_text(layer))
                vis_item.setFlags(base_flags)
                vis_item.setData(user_role(), layer.id())
                vis_item.setTextAlignment(qta(Qt, "AlignCenter"))
                self.table.setItem(row, _COL_VIS, vis_item)

                name_item = QTableWidgetItem(name)
                name_item.setFlags(base_flags)
                self.table.setItem(row, _COL_NAME, name_item)

                count_item = QTableWidgetItem(_feature_count(layer))
                count_item.setFlags(base_flags)
                count_item.setTextAlignment(qta(Qt, "AlignRight") | qta(Qt, "AlignVCenter"))
                self.table.setItem(row, _COL_COUNT, count_item)

                geom_item = QTableWidgetItem(_type_label(g))
                geom_item.setFlags(base_flags)
                self.table.setItem(row, _COL_GEOM, geom_item)

                store_item = QTableWidgetItem(_storage_label(layer))
                store_item.setFlags(base_flags)
                self.table.setItem(row, _COL_STORE, store_item)

                crs_item = QTableWidgetItem(_crs_label(layer))
                crs_item.setFlags(base_flags)
                self.table.setItem(row, _COL_CRS, crs_item)

                fields_item = QTableWidgetItem(_fields_summary(layer))
                fields_item.setFlags(base_flags)
                self.table.setItem(row, _COL_FIELDS, fields_item)

                label_item = QTableWidgetItem(tr("开") if _labels_on(layer) else tr("关"))
                label_item.setFlags(base_flags)
                label_item.setTextAlignment(qta(Qt, "AlignCenter"))
                self.table.setItem(row, _COL_LABEL, label_item)

                op = _opacity_percent(layer)
                opacity_item = QTableWidgetItem("" if op == "" else str(op))
                opacity_item.setFlags(base_flags | qta(Qt, "ItemIsEditable"))
                self.table.setItem(row, _COL_OPACITY, opacity_item)

                hay = " ".join([name, _fields_summary(layer), _storage_label(layer)]).casefold()
                self.table.setRowHidden(row, bool(needle and needle not in hay))
        finally:
            self.table.blockSignals(False)
            self._updating = False

    def _filter_only(self, _text):
        needle = self.search.text().strip().casefold()
        for row in range(self.table.rowCount()):
            chunks = []
            for col in (_COL_NAME, _COL_FIELDS, _COL_STORE):
                it = self.table.item(row, col)
                chunks.append((it.text() or "") if it is not None else "")
            hay = " ".join(chunks).casefold()
            self.table.setRowHidden(row, bool(needle and needle not in hay))

    def _on_item_changed(self, item):
        if self._updating or item is None:
            return
        layer = self._layer_at(item.row())
        if layer is None:
            return
        if item.column() == _COL_OPACITY:
            self._set_opacity(layer, item)

    def _on_cell_clicked(self, row, column):
        if self._updating:
            return
        layer = self._layer_at(row)
        if layer is None:
            return
        self._updating = True
        try:
            if column == _COL_VIS:
                self._set_layer_visible(layer, not self._layer_is_visible(layer))
            elif column == _COL_LABEL:
                if not isinstance(layer, QgsVectorLayer):
                    return
                _apply_labels([layer], not _labels_on(layer))
                try:
                    self.iface.mapCanvas().refresh()
                except Exception:
                    pass  # nosec
            else:
                return
        finally:
            self._updating = False
        self.reload()

    def eventFilter(self, obj, event):
        wheel = enum_int(qt_attr(QEvent, "Wheel"), getattr(QEvent, "Wheel", None))
        if obj is self.table.viewport() and enum_int(event.type(), 0) == wheel:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            index = self.table.indexAt(pos)
            if index.isValid() and index.column() == _COL_OPACITY:
                item = self.table.item(index.row(), _COL_OPACITY)
                layer = self._layer_at(index.row())
                if item is not None and layer is not None:
                    delta = event.angleDelta().y()
                    step = 5 if delta > 0 else -5 if delta < 0 else 0
                    if step:
                        try:
                            current = int(item.text() or _opacity_percent(layer) or 100)
                        except ValueError:
                            current = 100
                        value = max(0, min(100, current + step))
                        self._updating = True
                        try:
                            item.setText(str(value))
                        finally:
                            self._updating = False
                        self._set_opacity(layer, item)
                        event.accept()
                        return True
        return super().eventFilter(obj, event)

    def _set_opacity(self, layer, item):
        raw = (item.text() or "").replace("%", "").strip()
        try:
            value = float(raw)
        except ValueError:
            value = None
        if value is None:
            self._updating = True
            try:
                current = _opacity_percent(layer)
                item.setText("" if current == "" else str(current))
            finally:
                self._updating = False
            return
        if value > 1:
            value = value / 100.0
        if value < 0:
            value = 0
        if value > 1:
            value = 1
        try:
            layer.setOpacity(value)
            layer.triggerRepaint()
        except Exception:
            pass  # nosec
        self._updating = True
        try:
            item.setText(str(int(round(value * 100))))
        finally:
            self._updating = False
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            pass  # nosec

    def _layer_at(self, row):
        vis = self.table.item(row, _COL_VIS)
        if vis is None:
            return None
        return QgsProject.instance().mapLayer(vis.data(user_role()))

    def _on_double(self, item):
        if item is None or item.column() in (_COL_VIS, _COL_LABEL, _COL_OPACITY):
            return
        self._jump()

    def _layer_is_visible(self, layer):
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node is None:
            return True
        try:
            return bool(node.itemVisibilityChecked())
        except Exception:
            return True

    def _vis_text(self, layer):
        return tr("开") if self._layer_is_visible(layer) else tr("关")

    def _set_layer_visible(self, layer, on):
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node is None:
            return
        try:
            node.setItemVisibilityChecked(bool(on))
        except Exception:
            pass  # nosec

    def _current_layer(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        vis = self.table.item(row, _COL_VIS)
        if vis is None:
            return None
        return QgsProject.instance().mapLayer(vis.data(user_role()))

    def _prepare_layer_selection(self, layer):
        if layer is None:
            return False
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node is None:
            tell(self.iface, tr("图层管理"), tr("该图层不在图层树中。"), warning=True)
            return False
        select_nodes(self.iface, [node], reveal=False)
        try:
            self.iface.setActiveLayer(layer)
        except Exception:
            pass  # nosec
        return True

    def _jump(self):
        layer = self._current_layer()
        if layer is None:
            tell(self.iface, tr("图层管理"), tr("请先选中一行。"), warning=True)
            return
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node is None:
            return
        select_nodes(self.iface, [node], reveal=True)

    def _symbology(self):
        layer = self._current_layer()
        if layer is None:
            tell(self.iface, tr("图层管理"), tr("请先选中一行。"), warning=True)
            return
        if not self._prepare_layer_selection(layer):
            return
        cat = getattr(QgsMapLayer, "StyleCategory", None)
        sym = getattr(cat, "Symbology", None) if cat is not None else getattr(QgsMapLayer, "Symbology", None)
        pages = ("mOptsPage_Style", "mOptsPage_Rendering")
        _show_styling(self.iface, layer, sym, prop_pages=pages)

    def _labels(self):
        layer = self._current_layer()
        if layer is None:
            tell(self.iface, tr("图层管理"), tr("请先选中一行。"), warning=True)
            return
        if not self._prepare_layer_selection(layer):
            return
        cat = getattr(QgsMapLayer, "StyleCategory", None)
        lbl = getattr(cat, "Labeling", None) if cat is not None else getattr(QgsMapLayer, "Labeling", None)
        _show_styling(self.iface, layer, lbl, prop_pages=("mOptsPage_Labels",))

    def _fields(self):
        layer = self._current_layer()
        if layer is None:
            tell(self.iface, tr("图层管理"), tr("请先选中一行。"), warning=True)
            return
        if not isinstance(layer, QgsVectorLayer):
            tell(self.iface, tr("图层管理"), tr("只有矢量图层才有字段。"), warning=True)
            return
        if not self._prepare_layer_selection(layer):
            return
        showp = getattr(self.iface, "showLayerProperties", None)
        if not callable(showp):
            tell(self.iface, tr("图层管理"), tr("无法打开图层属性。"), warning=True)
            return
        if not self._prepare_layer_selection(layer):
            return
        if _open_props(self.iface, layer, ("mOptsPage_SourceFields", "mOptsPage_Fields")):
            return
        tell(self.iface, tr("图层管理"), tr("无法打开字段页。"), warning=True)

    def _properties(self):
        layer = self._current_layer()
        if layer is None:
            tell(self.iface, tr("图层管理"), tr("请先选中一行。"), warning=True)
            return
        showp = getattr(self.iface, "showLayerProperties", None)
        if not callable(showp):
            tell(self.iface, tr("图层管理"), tr("无法打开图层属性。"), warning=True)
            return
        if not self._prepare_layer_selection(layer):
            return
        try:
            showp(layer)
        except Exception:
            pass  # nosec

    def _copy_style(self):
        layer = self._current_layer()
        if layer is None:
            tell(self.iface, tr("图层管理"), tr("请先选中一行。"), warning=True)
            return
        if not self._prepare_layer_selection(layer):
            return
        style_copy.copy_style_from_layer(self.iface, layer)

    def _paste_style(self, part):
        layer = self._current_layer()
        if layer is None:
            tell(self.iface, tr("图层管理"), tr("请先选中一行。"), warning=True)
            return
        if not self._prepare_layer_selection(layer):
            return
        style_copy.paste_style_onto_layers(self.iface, [layer], part)


def _geometry_kind(layer):
    return geometry_code(layer)


def _storage_label(layer):
    for getter in (
        lambda: layer.storageType(),
        lambda: layer.dataProvider().storageType(),
        lambda: layer.providerType(),
    ):
        try:
            text = str(getter() or "").strip()
        except Exception:
            text = ""
        if text:
            return text
    return ""


def _crs_label(layer):
    try:
        crs = layer.crs()
        text = crs.authid() or crs.description() or ""
        return str(text)
    except Exception:
        return ""


def _feature_count(layer):
    if not isinstance(layer, QgsVectorLayer):
        return ""
    try:
        return str(int(layer.featureCount()))
    except Exception:
        return ""


def _provider_label(layer):
    try:
        return layer.providerType() or ""
    except Exception:
        return ""


def _type_label(gcode):
    if gcode == "raster":
        return tr("栅格")
    if gcode == "mesh":
        return tr("网格")
    if gcode == "pointcloud":
        return tr("点云")
    if gcode == "point":
        return tr("点")
    if gcode == "line":
        return tr("线")
    if gcode == "polygon":
        return tr("面")
    if gcode == "nogeometry":
        return tr("无几何")
    return tr("其它")
