# -*- coding: utf-8 -*-
"""Sort, group, and save layer-visibility snapshots from the Layers toolbar."""

import csv
import json
import os
import re
from datetime import datetime

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QFileDialog,
)

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from qgis.core import QgsApplication, QgsLayerTree, QgsProject, QgsVectorLayer

from .buttons import ask, make_toolbar_button, qt_attr
from .i18n import apply_direction, localize_button_box, tr, subscribe
from .icons import load_icon
from .qt_compat import accepted, run_dialog
from .file_logic import human_size
from .scope import geometry_code, group_path, layer_file_path, relocate, reorder_children, tell

_ORGANIZE_ID = "lpt:organize"
_PROP = "lpt/snapshots"
_dialog = None


def make_action(iface):
    tr("整理")
    tr("排序、分组，以及保存图层开关")
    return make_toolbar_button(
        iface,
        _ORGANIZE_ID,
        "LayersPanelToolsOrganize",
        "整理",
        "排序、分组，以及保存图层开关",
        _organize_icon(),
        None,
        menu=_build_menu(iface, iface.mainWindow()),
        popup="InstantPopup",
    )


def make_menu_action(iface):
    action = QAction(_organize_icon(), tr("整理"), iface.mainWindow())
    action.setObjectName("LayersPanelToolsOrganizeMenu")
    action.setProperty("lpt_msgid", "整理")
    action.setProperty("lpt_tip_msgid", "排序、分组，以及保存图层开关")
    action.setToolTip(tr("排序、分组，以及保存图层开关"))
    action.setMenu(_build_menu(iface, iface.mainWindow()))
    return action


def _build_menu(iface, parent):
    menu = QMenu(parent)
    menu.setObjectName("LayersPanelToolsOrganizeMenuPopup")
    menu.aboutToShow.connect(lambda menu=menu: _fill_menu(iface, menu))
    return menu


def _add_item(menu, text, callback):
    action = QAction(text, menu)
    action.triggered.connect(callback)
    menu.addAction(action)
    return action


def _fill_menu(iface, menu):
    menu.clear()
    for suffix in ("name", "geometry", "directory", "feature_count", "crs", "provider", "filesize", "mtime"):
        subcommands.add_to_menu(iface, "lpt:organize", menu, "lpt:organize:sort_" + suffix)
    menu.addSeparator()
    for suffix in ("geometry", "directory", "crs", "provider", "feature_count"):
        subcommands.add_to_menu(iface, "lpt:organize", menu, "lpt:organize:group_" + suffix)
    menu.addSeparator()
    subcommands.add_to_menu(iface, "lpt:organize", menu, "lpt:organize:save_snapshot")
    restore = menu.addMenu(tr("恢复"))
    items = _read_snapshots()
    if not items:
        empty = restore.addAction(tr("还没有快照"))
        empty.setEnabled(False)
    else:
        for item in items:
            payload = item
            restore.addAction(str(payload.get("name") or "")).triggered.connect(
                lambda *_args, chosen=payload: _restore_now(iface, chosen)
            )
    menu.addSeparator()
    subcommands.add_to_menu(iface, "lpt:organize", menu, "lpt:organize:prune")
    menu.addSeparator()
    subcommands.add_to_menu(iface, "lpt:organize", menu, "lpt:organize:export_csv")
    menu.addSeparator()
    subcommands.add_to_menu(iface, "lpt:organize", menu, "lpt:organize:open_dialog")


def _prune_now(iface):
    removed = remove_empty_groups(QgsProject.instance().layerTreeRoot())
    if removed:
        tell(iface, tr("整理"), tr("已删除 %d 个空组。") % removed)
    else:
        tell(iface, tr("整理"), tr("没有空组。"))


def remove_empty_groups(group):
    """Drop groups that hold no layer at any depth. Returns how many were removed."""
    removed = 0
    for child in list(group.children()):
        if not _is_group(child):
            continue
        removed += remove_empty_groups(child)
        if not list(child.children()):
            group.removeChildNode(child)
            removed += 1
    return removed


def _sort_now(iface, basis):
    groups = _collect_groups(QgsProject.instance().layerTreeRoot(), True)
    changed = sort_groups(groups, basis, False)
    if changed:
        tell(iface, tr("整理"), tr("已在 %d 个组内排序。") % changed)
    else:
        tell(iface, tr("整理"), tr("当前范围内没有需要排序的图层。"))


def _group_now(iface, basis, label):
    if not _ask(iface.mainWindow(), tr("确定要按「%s」分组吗？图层会移到对应的组里。") % label):
        return
    groups = _collect_groups(QgsProject.instance().layerTreeRoot(), True)
    moved = group_layers(groups, basis)
    tell(iface, tr("整理"), tr("已把 %d 个图层移进组。") % moved)


def _export_csv(iface):
    path, _filter = QFileDialog.getSaveFileName(
        iface.mainWindow(),
        tr("导出图层清单"),
        "",
        tr("CSV (*.csv)"),
    )
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path += ".csv"
    root = QgsProject.instance().layerTreeRoot()
    header = [
        tr("图层名"),
        tr("类型"),
        tr("数据源"),
        tr("路径"),
        tr("坐标系"),
        tr("要素数"),
        tr("文件大小"),
        tr("修改时间"),
        tr("可见"),
        tr("组路径"),
    ]
    rows = []
    for layer in QgsProject.instance().mapLayers().values():
        node = None
        try:
            node = root.findLayer(layer.id())
        except Exception:
            node = None
        visible = tr("是")
        try:
            if node is not None and not node.itemVisibilityChecked():
                visible = tr("否")
        except Exception:
            pass  # nosec
        path_src = layer_file_path(layer)
        size = ""
        mtime = ""
        if path_src and os.path.isfile(path_src):
            try:
                size = human_size(os.path.getsize(path_src))
                stamp = os.path.getmtime(path_src)
                mtime = datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M:%S")
            except (OSError, ValueError, OverflowError):
                pass
        count = ""
        if isinstance(layer, QgsVectorLayer):
            try:
                count = str(layer.featureCount())
            except Exception:
                pass  # nosec
        crs = _crs_label(layer)
        geom = geometry_name(geometry_code(layer))
        group = ""
        if node is not None:
            try:
                group = group_path(node) or ""
            except Exception:
                group = ""
        rows.append(
            [
                layer.name() or "",
                geom,
                layer.providerType() or "",
                path_src,
                crs,
                count,
                size,
                mtime,
                visible,
                group,
            ]
        )
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
    except OSError:
        tell(iface, tr("整理"), tr("无法写入该文件。"), warning=True)
        return
    tell(iface, tr("整理"), tr("已导出 %d 行到 CSV。") % len(rows))


def _save_now(iface):
    name = _prompt_name(iface.mainWindow())
    if name is None:
        return
    if not name:
        tell(iface, tr("整理"), tr("请先填写快照名称。"))
        return
    items = _read_snapshots()
    payload = capture_visibility()
    payload["name"] = name
    for index, item in enumerate(items):
        if item.get("name") == name:
            if not _ask(iface.mainWindow(), tr("已有同名快照「%s」，要覆盖吗？") % name):
                return
            items[index] = payload
            break
    else:
        items.append(payload)
    _write_snapshots(items)
    tell(iface, tr("整理"), tr("已保存图层开关「%s」。请保存工程。") % name)


def _restore_now(iface, payload):
    restore_visibility(payload)
    tell(iface, tr("整理"), tr("已恢复图层开关「%s」。") % (payload.get("name") or ""))


def _ask(parent, text):
    return ask(parent, tr("整理"), text)


def _prompt_name(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle(tr("整理"))
    layout = QVBoxLayout(dialog)
    edit = QLineEdit()
    edit.setPlaceholderText(tr("快照名称"))
    layout.addWidget(edit)
    buttons = QDialogButtonBox(qt_attr(QDialogButtonBox, "Ok") | qt_attr(QDialogButtonBox, "Cancel"))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    localize_button_box(buttons)
    if not accepted(run_dialog(dialog)):
        return None
    return edit.text().strip()


def open_organize(iface):
    global _dialog
    if _dialog is None:
        _dialog = OrganizeDialog(iface, iface.mainWindow())
    else:
        _dialog.iface = iface
        _dialog.reload_snapshots()
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


def close_organize():
    global _dialog
    dialog = _dialog
    _dialog = None
    if dialog is None:
        return
    try:
        dialog.close()
        dialog.deleteLater()
    except RuntimeError:
        pass


def _organize_icon():
    icon = load_icon("organize")
    if icon is not None and not icon.isNull():
        return icon
    for path in ("/mActionSaveEdits.svg", "/mActionFileSave.svg", "/mIconFolder.svg"):
        icon = QgsApplication.getThemeIcon(path)
        if icon is not None and not icon.isNull():
            return icon
    return QIcon()


def _is_group(node):
    try:
        return bool(QgsLayerTree.isGroup(node))
    except Exception:
        return False


def _is_layer(node):
    try:
        return bool(QgsLayerTree.isLayer(node))
    except Exception:
        return False


def _reorder(group, new_children):
    reorder_children(group, new_children)


def _natural_key(text):
    parts = re.split(r"(\d+)", str(text or "").casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def _layer_of(node):
    if not _is_layer(node):
        return None
    try:
        return node.layer()
    except Exception:
        return None


def _geometry_code(layer):
    return geometry_code(layer)


def geometry_name(code):
    if code == "point":
        return tr("点")
    if code == "line":
        return tr("线")
    if code == "polygon":
        return tr("面")
    if code == "nogeometry":
        return tr("无几何")
    if code == "raster":
        return tr("栅格")
    if code == "mesh":
        return tr("网格")
    if code == "pointcloud":
        return tr("点云")
    if code == "unknown":
        return tr("未知几何")
    return tr("其他")


def _geometry_rank(code):
    order = {
        "point": 0,
        "line": 1,
        "polygon": 2,
        "nogeometry": 3,
        "raster": 4,
        "mesh": 5,
        "pointcloud": 6,
        "unknown": 7,
        "other": 8,
    }
    return order.get(code, 9)


def _source_path(layer):
    source = layer.source() or ""
    match = re.search(r"path='([^']+)'", source)
    if match:
        return match.group(1)
    path = source.split("|")[0].strip().strip('"')
    if path.lower().startswith("file:"):
        path = path[5:]
    return path


def directory_bucket(layer):
    if layer is None:
        return ("special", "未落盘")
    provider = (layer.providerType() or "").lower()
    if provider in ("postgres", "mssql", "oracle", "hana"):
        return ("special", "数据库")
    if provider in ("wms", "xyz", "wfs", "vectortile", "arcgismapserver", "arcgisfeatureserver"):
        return ("special", "在线服务")
    path = _source_path(layer)
    if provider == "memory" or not path:
        return ("special", "内存图层" if provider == "memory" else "未落盘")
    folder = os.path.basename(os.path.dirname(path))
    if not folder:
        return ("special", "未落盘")
    return ("folder", folder)


def place_name(bucket):
    kind, value = bucket
    if kind != "special":
        return value
    if value == "数据库":
        return tr("数据库")
    if value == "在线服务":
        return tr("在线服务")
    if value == "内存图层":
        return tr("内存图层")
    return tr("未落盘")


def _collect_groups(start, recursive):
    found = [start]
    if not recursive:
        return found

    def walk(group):
        for child in list(group.children()):
            if _is_group(child):
                found.append(child)
                walk(child)

    walk(start)
    return found


def _file_stat(layer):
    path = layer_file_path(layer) if layer is not None else ""
    if not path or not os.path.isfile(path):
        return (0, 0)
    try:
        return (os.path.getsize(path), os.path.getmtime(path))
    except OSError:
        return (0, 0)


def _crs_label(layer):
    if layer is None:
        return tr("无坐标系")
    try:
        crs = layer.crs()
        if crs is not None and crs.isValid():
            auth = crs.authid() or crs.description() or ""
            if auth:
                return auth
    except Exception:
        pass  # nosec
    return tr("无坐标系")


def _feature_count(layer):
    if layer is None or not isinstance(layer, QgsVectorLayer):
        return -1
    try:
        return int(layer.featureCount())
    except Exception:
        return -1


def _feature_count_band(count):
    if count < 0:
        return tr("非矢量")
    if count == 0:
        return tr("0 个要素")
    if count <= 100:
        return tr("1–100 个要素")
    if count <= 1000:
        return tr("101–1000 个要素")
    return tr("1000 个以上要素")


def _sort_key(node, basis):
    if basis == "name":
        return _natural_key(node.name())
    if basis == "geometry":
        layer = _layer_of(node)
        if layer is None:
            return (100, _natural_key(node.name()))
        code = _geometry_code(layer)
        return (_geometry_rank(code), _natural_key(node.name()))
    layer = _layer_of(node)
    if layer is None:
        return ("~", _natural_key(node.name()))
    if basis == "directory":
        return (place_name(directory_bucket(layer)).casefold(), _natural_key(node.name()))
    if basis == "feature_count":
        return (_feature_count(layer), _natural_key(node.name()))
    if basis == "crs":
        return (_crs_label(layer).casefold(), _natural_key(node.name()))
    if basis == "provider":
        provider = (layer.providerType() or "").casefold()
        return (provider, _natural_key(node.name()))
    if basis == "filesize":
        size, _mtime = _file_stat(layer)
        return (-size, _natural_key(node.name()))
    if basis == "mtime":
        _size, mtime = _file_stat(layer)
        return (-mtime, _natural_key(node.name()))
    return (place_name(directory_bucket(layer)).casefold(), _natural_key(node.name()))


def sort_groups(groups, basis, reverse):
    changed = 0
    for group in reversed(list(groups)):
        children = list(group.children())
        layers = [child for child in children if _is_layer(child)]
        if len(layers) < 2:
            continue
        ordered = sorted(layers, key=lambda node: _sort_key(node, basis), reverse=reverse)
        if ordered == layers:
            continue
        cursor = 0
        rebuilt = []
        for child in children:
            if _is_layer(child):
                rebuilt.append(ordered[cursor])
                cursor += 1
            else:
                rebuilt.append(child)
        _reorder(group, rebuilt)
        changed += 1
    return changed


def _find_group(parent, name):
    for child in list(parent.children()):
        if _is_group(child) and child.name() == name:
            return child
    return None


def group_layers(groups, basis):
    moved = 0
    for parent in groups:
        buckets = {}
        for child in list(parent.children()):
            layer = _layer_of(child)
            if layer is None:
                continue
            if basis == "geometry":
                code = _geometry_code(layer)
                key = (_geometry_rank(code), geometry_name(code))
            elif basis == "crs":
                label = _crs_label(layer)
                key = (label.casefold(), label)
            elif basis == "provider":
                label = layer.providerType() or tr("未知")
                key = (label.casefold(), label)
            elif basis == "feature_count":
                band = _feature_count_band(_feature_count(layer))
                key = (band, band)
            else:
                bucket = directory_bucket(layer)
                key = (0, place_name(bucket))
            buckets.setdefault(key, []).append(child)
        for key in sorted(buckets):
            name = key[1]
            nodes = buckets[key]
            if not nodes:
                continue
            if parent.parent() is not None and parent.name() == name:
                continue
            existing = _find_group(parent, name)
            if existing is None:
                first = 0
                for index, child in enumerate(list(parent.children())):
                    if child == nodes[0]:
                        first = index
                        break
                existing = parent.insertGroup(first, name)
            for node in nodes:
                if node.parent() is not parent:
                    continue
                relocate(node, existing, len(list(existing.children())))
                moved += 1
    return moved


def _project_text(project):
    found = ""
    try:
        found = project.readEntry("LayersPanelTools", "snapshots", "")
    except TypeError:
        try:
            found = project.readEntry("LayersPanelTools", "snapshots")
        except Exception:
            found = ""
    except Exception:
        found = ""
    text = ""
    if isinstance(found, tuple):
        text = found[0] or ""
    elif found:
        text = str(found)
    if str(text).strip():
        return str(text)
    reader = getattr(project, "customProperty", None)
    if not callable(reader):
        return ""
    try:
        legacy = reader(_PROP, "") or ""
    except Exception:
        return ""
    return str(legacy) if legacy else ""


def _read_snapshots():
    raw = _project_text(QgsProject.instance())
    if not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _write_snapshots(items):
    text = json.dumps(items, ensure_ascii=False)
    project = QgsProject.instance()
    try:
        project.writeEntry("LayersPanelTools", "snapshots", text)
    except Exception:
        pass  # nosec
    writer = getattr(project, "setCustomProperty", None)
    if callable(writer):
        try:
            writer(_PROP, text)
        except Exception:
            pass  # nosec
    try:
        project.setDirty(True)
    except Exception:
        pass  # nosec


def capture_visibility():
    layers = {}
    groups = {}

    def walk(node, path):
        if _is_group(node) and path:
            groups["/".join(path)] = bool(node.itemVisibilityChecked())
        for child in list(node.children()):
            if _is_layer(child):
                layer = _layer_of(child)
                if layer is not None:
                    layers[layer.id()] = bool(child.itemVisibilityChecked())
            elif _is_group(child):
                walk(child, path + [child.name()])

    walk(QgsProject.instance().layerTreeRoot(), [])
    return {"layers": layers, "groups": groups}


def restore_visibility(payload):
    layers = payload.get("layers") or {}
    groups = payload.get("groups") or {}

    def walk(node, path):
        if _is_group(node) and path:
            key = "/".join(path)
            if key in groups:
                node.setItemVisibilityChecked(bool(groups[key]))
        for child in list(node.children()):
            if _is_layer(child):
                layer = _layer_of(child)
                if layer is not None and layer.id() in layers:
                    child.setItemVisibilityChecked(bool(layers[layer.id()]))
            elif _is_group(child):
                walk(child, path + [child.name()])

    walk(QgsProject.instance().layerTreeRoot(), [])


class OrganizeDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setObjectName("LayersPanelToolsOrganizeDialog")
        self.resize(460, 640)
        self._listening = False
        self._snapshots = []

        layout = QVBoxLayout(self)
        self.scope_box = QGroupBox()
        scope_layout = QVBoxLayout(self.scope_box)
        scope_row = QHBoxLayout()
        self.lbl_scope = QLabel()
        self.scope = QComboBox()
        scope_row.addWidget(self.lbl_scope)
        scope_row.addWidget(self.scope, 1)
        scope_layout.addLayout(scope_row)
        self.chk_recursive = QCheckBox()
        self.chk_recursive.setChecked(True)
        scope_layout.addWidget(self.chk_recursive)
        layout.addWidget(self.scope_box)

        self.sort_box = QGroupBox()
        sort_layout = QVBoxLayout(self.sort_box)
        basis_row = QHBoxLayout()
        self.lbl_basis = QLabel()
        self.basis = QComboBox()
        basis_row.addWidget(self.lbl_basis)
        basis_row.addWidget(self.basis, 1)
        sort_layout.addLayout(basis_row)
        order_row = QHBoxLayout()
        self.lbl_order = QLabel()
        self.order = QComboBox()
        order_row.addWidget(self.lbl_order)
        order_row.addWidget(self.order, 1)
        sort_layout.addLayout(order_row)
        self.btn_sort = QPushButton()
        self.btn_sort.clicked.connect(self._sort)
        sort_layout.addWidget(self.btn_sort)
        layout.addWidget(self.sort_box)

        self.group_box = QGroupBox()
        group_layout = QVBoxLayout(self.group_box)
        grow = QHBoxLayout()
        self.lbl_group = QLabel()
        self.group_by = QComboBox()
        grow.addWidget(self.lbl_group)
        grow.addWidget(self.group_by, 1)
        group_layout.addLayout(grow)
        self.btn_group = QPushButton()
        self.btn_group.clicked.connect(self._group)
        group_layout.addWidget(self.btn_group)
        layout.addWidget(self.group_box)

        self.snap_box = QGroupBox()
        snap_layout = QVBoxLayout(self.snap_box)
        name_row = QHBoxLayout()
        self.snap_name = QLineEdit()
        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self._save_snapshot)
        name_row.addWidget(self.snap_name, 1)
        name_row.addWidget(self.btn_save)
        snap_layout.addLayout(name_row)
        self.snap_list = QListWidget()
        snap_layout.addWidget(self.snap_list, 1)
        snap_buttons = QHBoxLayout()
        self.btn_restore = QPushButton()
        self.btn_delete = QPushButton()
        self.btn_restore.clicked.connect(self._restore_snapshot)
        self.btn_delete.clicked.connect(self._delete_snapshot)
        snap_buttons.addWidget(self.btn_restore)
        snap_buttons.addWidget(self.btn_delete)
        snap_layout.addLayout(snap_buttons)
        self.snap_note = QLabel()
        self.snap_note.setWordWrap(True)
        snap_layout.addWidget(self.snap_note)
        layout.addWidget(self.snap_box, 1)

        close_flag = qt_attr(QDialogButtonBox, "Close")
        self.buttons = QDialogButtonBox(close_flag)
        self.buttons.rejected.connect(self.close)
        self.buttons.accepted.connect(self.close)
        try:
            self.buttons.button(close_flag).clicked.connect(self.close)
        except Exception:
            pass  # nosec
        layout.addWidget(self.buttons)

        self.retranslate()
        self.reload_snapshots()
        subscribe(self, self.retranslate)
        self._listening = True

    def closeEvent(self, event):
        super().closeEvent(event)

    def retranslate(self, *_args):
        self.setWindowTitle(tr("整理"))
        self.scope_box.setTitle(tr("范围"))
        self.lbl_scope.setText(tr("范围"))
        self._fill_combo(self.scope, (("project", tr("整个工程")), ("group", tr("当前组"))))
        self.chk_recursive.setText(tr("包含子组"))
        self.sort_box.setTitle(tr("排序"))
        self.lbl_basis.setText(tr("排序依据"))
        self._fill_combo(
            self.basis,
            (("name", tr("名称")), ("geometry", tr("几何类型")), ("directory", tr("所在目录"))),
        )
        self.lbl_order.setText(tr("顺序"))
        self._fill_combo(self.order, (("asc", tr("升序")), ("desc", tr("降序"))))
        self.btn_sort.setText(tr("开始排序"))
        self.group_box.setTitle(tr("分组"))
        self.lbl_group.setText(tr("分组依据"))
        self._fill_combo(self.group_by, (("geometry", tr("几何类型")), ("directory", tr("所在目录"))))
        self.btn_group.setText(tr("开始分组"))
        self.snap_box.setTitle(tr("图层开关"))
        self.snap_name.setPlaceholderText(tr("快照名称"))
        self.btn_save.setText(tr("保存当前开关"))
        self.btn_restore.setText(tr("恢复"))
        self.btn_delete.setText(tr("删除"))
        self.snap_note.setText(tr("快照保存在当前工程里。保存工程后，下次打开还能用。"))
        localize_button_box(self.buttons)
        apply_direction(self)

    def _fill_combo(self, combo, pairs):
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        selected = 0
        for index, (code, label) in enumerate(pairs):
            combo.addItem(label, code)
            if code == current:
                selected = index
        combo.setCurrentIndex(selected)
        combo.blockSignals(False)

    def _target_groups(self):
        root = QgsProject.instance().layerTreeRoot()
        whole = self.scope.currentData() != "group"
        if whole:
            return _collect_groups(root, True), False
        node = None
        view = self.iface.layerTreeView()
        if view is not None:
            node = view.currentNode()
        if node is None:
            return _collect_groups(root, True), True
        if _is_group(node):
            start = node
        else:
            start = node.parent() or root
        return _collect_groups(start, bool(self.chk_recursive.isChecked())), False

    def _sort(self):
        groups, fell_back = self._target_groups()
        changed = sort_groups(groups, self.basis.currentData() or "name", self.order.currentData() == "desc")
        if fell_back:
            self._info(tr("没有找到当前组，已改为整个工程。"))
        if changed:
            self._info(tr("已在 %d 个组内排序。") % changed)
        else:
            self._info(tr("当前范围内没有需要排序的图层。"))

    def _ask(self, text):
        return ask(self, tr("整理"), text)

    def _group(self):
        label = self.group_by.currentText()
        if not self._ask(tr("确定要按「%s」分组吗？图层会移到对应的组里。") % label):
            return
        basis = self.group_by.currentData() or "geometry"
        groups, fell_back = self._target_groups()
        moved = group_layers(groups, basis)
        if fell_back:
            self._info(tr("没有找到当前组，已改为整个工程。"))
        self._info(tr("已把 %d 个图层移进组。") % moved)

    def reload_snapshots(self):
        self._snapshots = _read_snapshots()
        selected = self.snap_list.currentRow()
        self.snap_list.clear()
        for item in self._snapshots:
            self.snap_list.addItem(str(item.get("name") or ""))
        if 0 <= selected < self.snap_list.count():
            self.snap_list.setCurrentRow(selected)

    def _save_snapshot(self):
        name = self.snap_name.text().strip()
        if not name:
            self._info(tr("请先填写快照名称。"))
            return
        items = _read_snapshots()
        payload = capture_visibility()
        payload["name"] = name
        replaced = False
        for index, item in enumerate(items):
            if item.get("name") == name:
                if not self._ask(tr("已有同名快照「%s」，要覆盖吗？") % name):
                    return
                items[index] = payload
                replaced = True
                break
        if not replaced:
            items.append(payload)
        _write_snapshots(items)
        self.snap_name.clear()
        self.reload_snapshots()
        self._info(tr("已保存图层开关「%s」。请保存工程。") % name)

    def _selected_snapshot(self):
        row = self.snap_list.currentRow()
        if row < 0 or row >= len(self._snapshots):
            self._info(tr("还没有选中快照。"))
            return None
        return row, self._snapshots[row]

    def _restore_snapshot(self):
        found = self._selected_snapshot()
        if found is None:
            return
        _index, item = found
        restore_visibility(item)
        self._info(tr("已恢复图层开关「%s」。") % item.get("name", ""))

    def _delete_snapshot(self):
        found = self._selected_snapshot()
        if found is None:
            return
        index, item = found
        items = _read_snapshots()
        if 0 <= index < len(items):
            del items[index]
            _write_snapshots(items)
        self.reload_snapshots()
        self._info(tr("已删除快照「%s」。") % item.get("name", ""))

    def _info(self, text):
        return


from . import subcommands

_GROUP_LABELS = {
    "geometry": "几何类型",
    "directory": "所在目录",
    "crs": "坐标系",
    "provider": "数据源",
    "feature_count": "要素数量档",
}

tr("按名称排序")
tr("按几何类型排序")
tr("按所在目录排序")
tr("按要素数量排序")
tr("按坐标系排序")
tr("按数据源排序")
tr("按文件大小排序")
tr("按文件修改时间排序")
tr("按几何类型分组")
tr("按所在目录分组")
tr("按坐标系分组")
tr("按数据源分组")
tr("按要素数量档分组")
tr("保存当前开关")
tr("删除空组")
tr("导出图层清单 CSV")
tr("打开整理")
subcommands.register("lpt:organize", [
    ("sort_name", "按名称排序", lambda iface: _sort_now(iface, "name")),
    ("sort_geometry", "按几何类型排序", lambda iface: _sort_now(iface, "geometry")),
    ("sort_directory", "按所在目录排序", lambda iface: _sort_now(iface, "directory")),
    ("sort_feature_count", "按要素数量排序", lambda iface: _sort_now(iface, "feature_count")),
    ("sort_crs", "按坐标系排序", lambda iface: _sort_now(iface, "crs")),
    ("sort_provider", "按数据源排序", lambda iface: _sort_now(iface, "provider")),
    ("sort_filesize", "按文件大小排序", lambda iface: _sort_now(iface, "filesize")),
    ("sort_mtime", "按文件修改时间排序", lambda iface: _sort_now(iface, "mtime")),
    ("group_geometry", "按几何类型分组", lambda iface: _group_now(iface, "geometry", tr("几何类型"))),
    ("group_directory", "按所在目录分组", lambda iface: _group_now(iface, "directory", tr("所在目录"))),
    ("group_crs", "按坐标系分组", lambda iface: _group_now(iface, "crs", tr("坐标系"))),
    ("group_provider", "按数据源分组", lambda iface: _group_now(iface, "provider", tr("数据源"))),
    ("group_feature_count", "按要素数量档分组", lambda iface: _group_now(iface, "feature_count", tr("要素数量档"))),
    ("save_snapshot", "保存当前开关", lambda iface: _save_now(iface)),
    ("prune", "删除空组", lambda iface: _prune_now(iface)),
    ("export_csv", "导出图层清单 CSV", lambda iface: _export_csv(iface)),
    ("open_dialog", "打开整理", lambda iface: open_organize(iface)),
])