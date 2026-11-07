# -*- coding: utf-8 -*-
"""Point broken or moved layers at a new file, folder, or path prefix."""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from qgis.core import QgsDataProvider, QgsProject, QgsProviderRegistry

from .buttons import make_menu_action as menu_action, make_toolbar_button, qt_attr
from .i18n import apply_direction, localize_button_box, tr, subscribe
from .icons import load_icon
from .qt_compat import user_role
from .scope import all_layers, tell

_dialog = None
_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "$recycle.bin", "system volume information"}


def make_action(iface):
    tr("修复数据源")
    tr("把图层指到新的文件或目录")
    return make_toolbar_button(
        iface,
        "lpt:repair",
        "LayersPanelToolsRepair",
        "修复数据源",
        "把图层指到新的文件或目录",
        load_icon("repair"),
        lambda: open_repair(iface),
    )


def make_menu_action(iface):
    return menu_action(
        iface,
        "LayersPanelToolsRepairMenu",
        "修复数据源",
        "把图层指到新的文件或目录",
        load_icon("repair"),
        lambda: open_repair(iface),
    )


def open_repair(iface):
    global _dialog
    if _dialog is None:
        _dialog = RepairDialog(iface, iface.mainWindow())
    else:
        _dialog.iface = iface
        _dialog.refresh()
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


def close_repair():
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


def _decode(layer):
    source = layer.source() or ""
    provider = ""
    try:
        provider = layer.providerType() or ""
    except Exception:
        provider = ""
    meta = None
    parts = {}
    try:
        meta = QgsProviderRegistry.instance().providerMetadata(provider)
    except Exception:
        meta = None
    if meta is not None:
        try:
            decoded = meta.decodeUri(source)
            if isinstance(decoded, dict):
                parts = decoded
        except Exception:
            parts = {}
    path = ""
    if isinstance(parts, dict):
        path = parts.get("path") or ""
    if not path:
        head = source.split("|")[0]
        if head.lower().startswith("file:"):
            try:
                from qgis.PyQt.QtCore import QUrl

                path = QUrl(head).toLocalFile() or ""
            except Exception:
                path = ""
        elif os.path.isabs(head):
            path = head
    return source, parts, meta, path


def _with_path(source, parts, meta, old_path, new_path):
    if meta is not None and isinstance(parts, dict) and (parts.get("path") or old_path):
        updated = dict(parts)
        updated["path"] = new_path
        try:
            encoded = meta.encodeUri(updated)
            if encoded:
                return encoded
        except Exception:
            pass  # nosec
    new_text = new_path.replace("\\", "/")
    for old in (old_path, (old_path or "").replace("\\", "/")):
        if old and old in source:
            replacement = new_path if "\\" in old else new_text
            return source.replace(old, replacement, 1)
    return ""


def _replace_prefix(source, old, new):
    if old and old in source:
        return source.replace(old, new, 1)
    old_fwd = old.replace("\\", "/")
    source_fwd = source.replace("\\", "/")
    if old_fwd and old_fwd in source_fwd:
        return source_fwd.replace(old_fwd, new.replace("\\", "/"), 1)
    return ""


def _commit(layer, new_source):
    provider = ""
    try:
        provider = layer.providerType() or ""
    except Exception:
        provider = ""
    try:
        name = layer.name()
    except Exception:
        name = ""
    options = None
    try:
        options = QgsDataProvider.ProviderOptions()
        try:
            options.transformContext = QgsProject.instance().transformContext()
        except Exception:
            pass  # nosec
    except Exception:
        options = None
    try:
        if options is not None:
            layer.setDataSource(new_source, name, provider, options)
        else:
            layer.setDataSource(new_source, name, provider)
    except TypeError:
        layer.setDataSource(new_source, name, provider)
    try:
        layer.reload()
    except Exception:
        pass  # nosec
    try:
        layer.triggerRepaint()
    except Exception:
        pass  # nosec
    try:
        return bool(layer.isValid())
    except Exception:
        return False


def _index_tree(root):
    found = {}
    seen_dirs = 0
    truncated = False
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        seen_dirs += 1
        if seen_dirs > 2500:
            truncated = True
            break
        relative = os.path.relpath(dirpath, root)
        depth = 0 if relative == "." else relative.count(os.sep) + 1
        if depth > 8:
            dirnames[:] = []
            continue
        dirnames[:] = [name for name in dirnames if name.lower() not in _SKIP_DIRS and not name.startswith(".")]
        for name in filenames:
            bucket = found.setdefault(name.lower(), [])
            if len(bucket) < 16:
                bucket.append(os.path.join(dirpath, name))
    return found, truncated


def _pick_match(paths, old_path):
    if not paths:
        return "", "missing"
    if len(paths) == 1:
        return paths[0], ""
    parent = os.path.basename(os.path.dirname(old_path or "")).lower()
    same_parent = [path for path in paths if parent and os.path.basename(os.path.dirname(path)).lower() == parent]
    if len(same_parent) == 1:
        return same_parent[0], ""
    return "", "ambiguous"


def _picked_file(parent):
    found = QFileDialog.getOpenFileName(parent, tr("选择文件"))
    if isinstance(found, tuple):
        return found[0] or ""
    return found or ""


def _picked_dir(parent):
    return QFileDialog.getExistingDirectory(parent, tr("选择新目录")) or ""


class RepairDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setObjectName("LayersPanelToolsRepairDialog")
        self.resize(920, 520)
        self._proposed = {}
        self._notes = {}
        self._listening = False

        layout = QVBoxLayout(self)
        self.only_broken = QCheckBox()
        self.only_broken.setChecked(True)
        self.only_broken.toggled.connect(lambda *_args: self.refresh())
        layout.addWidget(self.only_broken)

        self.intro = QLabel()
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)

        prefix = QHBoxLayout()
        self.lbl_old = QLabel()
        self.old_edit = QLineEdit()
        self.lbl_new = QLabel()
        self.new_edit = QLineEdit()
        self.btn_prefix = QPushButton()
        self.btn_prefix.clicked.connect(self._preview_prefix)
        prefix.addWidget(self.lbl_old)
        prefix.addWidget(self.old_edit, 1)
        prefix.addWidget(self.lbl_new)
        prefix.addWidget(self.new_edit, 1)
        prefix.addWidget(self.btn_prefix)
        layout.addLayout(prefix)

        actions = QHBoxLayout()
        self.btn_folder = QPushButton()
        self.btn_file = QPushButton()
        self.btn_clear = QPushButton()
        self.btn_reload = QPushButton()
        self.btn_folder.clicked.connect(self._match_folder)
        self.btn_file.clicked.connect(self._assign_file)
        self.btn_clear.clicked.connect(self._clear_preview)
        self.btn_reload.clicked.connect(self._reload_layers)
        for button in (self.btn_folder, self.btn_file, self.btn_clear, self.btn_reload):
            actions.addWidget(button)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 4)
        self.table.setSelectionBehavior(qt_attr(QAbstractItemView, "SelectRows"))
        self.table.setSelectionMode(qt_attr(QAbstractItemView, "ExtendedSelection"))
        self.table.setEditTriggers(qt_attr(QAbstractItemView, "NoEditTriggers"))
        self.table.setTextElideMode(qt_attr(Qt, "ElideMiddle"))
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 72)
        header = self.table.horizontalHeader()
        try:
            stretch = qt_attr(QHeaderView, "Stretch")
            header.setSectionResizeMode(2, stretch)
            header.setSectionResizeMode(3, stretch)
        except Exception:
            header.setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self.empty = QLabel()
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        self.count_label = QLabel()
        layout.addWidget(self.count_label)

        bottom = QHBoxLayout()
        self.btn_apply = QPushButton()
        self.btn_apply.clicked.connect(self._apply)
        bottom.addWidget(self.btn_apply)
        bottom.addStretch(1)
        close_flag = qt_attr(QDialogButtonBox, "Close")
        self.buttons = QDialogButtonBox(close_flag)
        self.buttons.rejected.connect(self.close)
        try:
            self.buttons.button(close_flag).clicked.connect(self.close)
        except Exception:
            pass  # nosec
        bottom.addWidget(self.buttons)
        layout.addLayout(bottom)

        self.retranslate()
        self.refresh()
        subscribe(self, self.retranslate)
        self._listening = True

    def closeEvent(self, event):
        if self._listening:
            self._listening = False
        super().closeEvent(event)

    def retranslate(self, *_args):
        self.setWindowTitle(tr("修复数据源"))
        self.only_broken.setText(tr("只看失效图层"))
        self.intro.setText(tr("先预览新路径，确认「新数据源」后再写回。"))
        self.lbl_old.setText(tr("原路径包含"))
        self.lbl_new.setText(tr("替换为"))
        self.btn_prefix.setText(tr("预览"))
        self.btn_folder.setText(tr("按新目录匹配同名文件"))
        self.btn_file.setText(tr("为所选行指定文件"))
        self.btn_clear.setText(tr("清除预览"))
        self.btn_reload.setText(tr("重新加载"))
        self.btn_apply.setText(tr("应用修改"))
        self.btn_apply.setToolTip(tr("按「新数据源」列写回图层。"))
        self.table.setHorizontalHeaderLabels([tr("图层"), tr("状态"), tr("当前数据源"), tr("新数据源")])
        localize_button_box(self.buttons)
        apply_direction(self)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        listed = 0
        for layer in all_layers():
            try:
                valid = bool(layer.isValid())
            except Exception:
                valid = False
            if self.only_broken.isChecked() and valid:
                continue
            try:
                layer_id = layer.id()
                name = layer.name()
            except Exception:
                continue  # nosec
            listed += 1
            row = self.table.rowCount()
            self.table.insertRow(row)
            source, _parts, _meta, _path = _decode(layer)
            proposed = self._proposed.get(layer_id) or ""
            note = self._notes.get(layer_id) or ""
            name_item = QTableWidgetItem(name)
            name_item.setData(user_role(), layer_id)
            name_item.setToolTip(name)
            self.table.setItem(row, 0, name_item)
            status = QTableWidgetItem(self._status_text(valid, proposed, source, note))
            self.table.setItem(row, 1, status)
            current_item = QTableWidgetItem(source)
            current_item.setToolTip(source)
            self.table.setItem(row, 2, current_item)
            new_item = QTableWidgetItem(proposed)
            new_item.setToolTip(proposed)
            self.table.setItem(row, 3, new_item)
        broken_only = self.only_broken.isChecked()
        if listed == 0:
            if broken_only and all_layers():
                self.empty.setText(tr("没有失效图层。取消勾选后可以重定向还正常的图层。"))
            else:
                self.empty.setText(tr("工程里没有图层。"))
            self.empty.setVisible(True)
        else:
            self.empty.setVisible(False)
        self.count_label.setText(tr("列出 %d 个图层。") % listed)

    def _status_text(self, valid, proposed, source, note):
        if note == "missing":
            return tr("没找到")
        if note == "ambiguous":
            return tr("多个同名")
        if proposed and proposed != source:
            return tr("将修改")
        if valid:
            return tr("正常")
        return tr("失效")

    def _target_ids(self, selection_only):
        if selection_only:
            rows = []
            try:
                rows = [index.row() for index in self.table.selectionModel().selectedRows()]
            except Exception:
                rows = []
            if not rows:
                return []
        else:
            try:
                selected = [index.row() for index in self.table.selectionModel().selectedRows()]
            except Exception:
                selected = []
            rows = selected or list(range(self.table.rowCount()))
        found = []
        for row in rows:
            item = self.table.item(row, 0)
            if item is None:
                continue
            layer_id = item.data(user_role())
            if layer_id:
                found.append(str(layer_id))
        return found

    def _layer(self, layer_id):
        try:
            return QgsProject.instance().mapLayer(layer_id)
        except Exception:
            return None

    def _preview_prefix(self):
        old = self.old_edit.text()
        new = self.new_edit.text()
        if not old.strip():
            tell(self.iface, tr("修复数据源"), tr("请先填写原路径里要替换的文字。"), warning=True)
            return
        filled = 0
        for layer_id in self._target_ids(False):
            layer = self._layer(layer_id)
            if layer is None:
                continue
            source, _parts, _meta, _path = _decode(layer)
            updated = _replace_prefix(source, old, new)
            self._notes[layer_id] = ""
            if updated and updated != source:
                self._proposed[layer_id] = updated
                filled += 1
            else:
                self._proposed.pop(layer_id, None)
        self.refresh()
        if filled:
            tell(self.iface, tr("修复数据源"), tr("已填好 %d 个新路径，确认后点「应用修改」。") % filled)
        else:
            tell(self.iface, tr("修复数据源"), tr("没有图层的路径里包含这段文字。"), warning=True)

    def _match_folder(self):
        root = _picked_dir(self)
        if not root:
            return
        index, truncated = _index_tree(root)
        missing = 0
        ambiguous = 0
        filled = 0
        for layer_id in self._target_ids(False):
            layer = self._layer(layer_id)
            if layer is None:
                continue
            source, parts, meta, path = _decode(layer)
            filename = os.path.basename(path) if path else ""
            if not filename:
                self._notes[layer_id] = "missing"
                self._proposed.pop(layer_id, None)
                missing += 1
                continue
            new_path, note = _pick_match(index.get(filename.lower(), []), path)
            self._notes[layer_id] = note
            if note == "missing":
                self._proposed.pop(layer_id, None)
                missing += 1
                continue
            if note == "ambiguous":
                self._proposed.pop(layer_id, None)
                ambiguous += 1
                continue
            updated = _with_path(source, parts, meta, path, new_path)
            if updated:
                self._proposed[layer_id] = updated
                filled += 1
            else:
                self._notes[layer_id] = "missing"
                missing += 1
        self.refresh()
        if truncated:
            tell(self.iface, tr("修复数据源"), tr("这个目录太大，没有全部查完。"), warning=True)
        if missing or ambiguous:
            tell(
                self.iface,
                tr("修复数据源"),
                tr("有 %d 个没找到同名文件，%d 个有多个同名文件。") % (missing, ambiguous),
                warning=True,
            )
        elif filled:
            tell(self.iface, tr("修复数据源"), tr("已填好 %d 个新路径，确认后点「应用修改」。") % filled)

    def _assign_file(self):
        layer_ids = self._target_ids(True)
        if not layer_ids:
            tell(self.iface, tr("修复数据源"), tr("请先在表里选中一行。"), warning=True)
            return
        picked = _picked_file(self)
        if not picked:
            return
        if len(layer_ids) == 1:
            layer = self._layer(layer_ids[0])
            if layer is None:
                return
            source, parts, meta, path = _decode(layer)
            updated = _with_path(source, parts, meta, path, picked) or picked
            self._notes[layer_ids[0]] = ""
            self._proposed[layer_ids[0]] = updated
            self.refresh()
            tell(self.iface, tr("修复数据源"), tr("已填好 %d 个新路径，确认后点「应用修改」。") % 1)
            return
        root = os.path.dirname(picked)
        index, truncated = _index_tree(root)
        self._apply_index(layer_ids, index, truncated)

    def _apply_index(self, layer_ids, index, truncated):
        missing = 0
        ambiguous = 0
        filled = 0
        for layer_id in layer_ids:
            layer = self._layer(layer_id)
            if layer is None:
                continue
            source, parts, meta, path = _decode(layer)
            filename = os.path.basename(path) if path else ""
            new_path, note = _pick_match(index.get(filename.lower(), []) if filename else [], path)
            self._notes[layer_id] = note
            if not new_path:
                self._proposed.pop(layer_id, None)
                if note == "ambiguous":
                    ambiguous += 1
                else:
                    missing += 1
                continue
            updated = _with_path(source, parts, meta, path, new_path)
            if not updated:
                self._notes[layer_id] = "missing"
                missing += 1
                continue
            self._proposed[layer_id] = updated
            filled += 1
        self.refresh()
        if truncated:
            tell(self.iface, tr("修复数据源"), tr("这个目录太大，没有全部查完。"), warning=True)
        if missing or ambiguous:
            tell(
                self.iface,
                tr("修复数据源"),
                tr("有 %d 个没找到同名文件，%d 个有多个同名文件。") % (missing, ambiguous),
                warning=True,
            )
        elif filled:
            tell(self.iface, tr("修复数据源"), tr("已填好 %d 个新路径，确认后点「应用修改」。") % filled)

    def _clear_preview(self):
        self._proposed.clear()
        self._notes.clear()
        self.refresh()

    def _reload_layers(self):
        layer_ids = self._target_ids(False)
        done = 0
        for layer_id in layer_ids:
            layer = self._layer(layer_id)
            if layer is None:
                continue
            try:
                layer.reload()
            except Exception:
                pass  # nosec
            try:
                provider = layer.dataProvider()
                if provider is not None:
                    provider.reloadData()
            except Exception:
                pass  # nosec
            try:
                layer.triggerRepaint()
            except Exception:
                pass  # nosec
            done += 1
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            pass  # nosec
        self.refresh()
        tell(self.iface, tr("修复数据源"), tr("已重新加载 %d 个图层。") % done)

    def _apply(self):
        done = 0
        still = 0
        for layer_id, new_source in list(self._proposed.items()):
            layer = self._layer(layer_id)
            if layer is None or not new_source:
                continue
            try:
                current = layer.source() or ""
            except Exception:
                current = ""
            if new_source == current:
                continue
            ok = False
            try:
                ok = _commit(layer, new_source)
            except Exception:
                ok = False
            done += 1
            if not ok:
                still += 1
        self._proposed.clear()
        self._notes.clear()
        try:
            QgsProject.instance().setDirty(True)
        except Exception:
            pass  # nosec
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            pass  # nosec
        self.refresh()
        if done <= 0:
            tell(self.iface, tr("修复数据源"), tr("没有需要写回的新路径。"), warning=True)
            return
        text = tr("已改 %d 个图层，其中 %d 个仍然失效。") % (done, still)
        tell(self.iface, tr("修复数据源"), text, warning=still > 0)
