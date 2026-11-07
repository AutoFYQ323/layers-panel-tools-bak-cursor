# -*- coding: utf-8 -*-
"""Basemap presets: add/remove definitions and switch visibility in one click."""

import json
import uuid
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from qgis.core import QgsMapLayer, QgsProject, QgsRasterLayer

from .buttons import ask, make_popup_menu_action, make_popup_tool, qt_attr
from .i18n import tr
from .icons import load_icon
from .plugin_settings import plugin_qsettings, set_value
from .qt_compat import user_role

_KEY = "basemap_presets2"
_PROP_PRESET = "lpt_basemap_preset"
_PROP_SLOT = "lpt_basemap_slot"

_panels = {}


def make_action(iface):
    tr("底图切换")
    tr("一键显示某套底图并隐藏其它底图预设")
    tr("管理底图预设…")
    tr("用当前图层加入预设")
    tr("底图预设")
    tr("选择一个预设后，点「应用」即可切换底图显示。")
    tr("应用")
    tr("从当前图层添加")
    tr("该预设还没有保存任何图层，请先在「管理底图预设」里添加。")
    tr("请先选中一个预设。")
    tr("请先在图层面板里选中一个栅格图层作为底图。")
    tr("新预设名称：")
    tr("名称不能为空。")
    tr("未命名")
    tr("请先在图层面板里选中一个栅格图层。")
    tr("预设名称：")
    tr("确定删除该底图预设吗？工程里的图层不会被移除。")
    tr("底图")
    tr("重命名预设")
    tr("新名称：")
    return make_popup_tool(
        iface,
        "lpt:basemap",
        "LayersPanelToolsBasemap",
        "底图切换",
        "一键显示某套底图并隐藏其它底图预设",
        load_icon("basemap"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsBasemapMenu",
        "底图切换",
        "一键显示某套底图并隐藏其它底图预设",
        load_icon("basemap"),
        lambda menu: _fill(iface, menu),
    )


def close_basemap():
    _panels.clear()


def _load_store():
    ps = plugin_qsettings()
    try:
        raw = ps.value(_KEY, "") or ""
    except Exception:
        raw = ""
    if not isinstance(raw, str):
        raw = str(raw)
    if not raw.strip():
        raw = ""
    if not raw.strip():
        return {"presets": []}
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("presets", [])
    if not isinstance(data["presets"], list):
        data["presets"] = []
    return data


def _save_store(store):
    try:
        set_value(_KEY, json.dumps(store, ensure_ascii=False))
    except Exception:
        pass  # nosec


def _preset_by_id(store, pid):
    for item in store.get("presets") or []:
        if str(item.get("id")) == str(pid):
            return item
    return None


def _layer_signature(layer):
    try:
        uri = layer.source() or ""
    except Exception:
        uri = ""
    try:
        provider = layer.providerType() or ""
    except Exception:
        provider = ""
    try:
        name = layer.name() or ""
    except Exception:
        name = ""
    return provider, uri, name


def _find_matching_layer(provider, uri):
    for layer in QgsProject.instance().mapLayers().values():
        if layer is None:
            continue
        try:
            if layer.providerType() != provider:
                continue
            if (layer.source() or "") != uri:
                continue
        except Exception:
            continue  # nosec
        return layer
    return None


def _is_basemap_candidate(layer):
    if layer is None:
        return False
    try:
        if layer.type() == QgsMapLayer.LayerType.RasterLayer:
            return True
    except Exception:
        pass  # nosec
    return False


def _tag_layer(layer, preset_id):
    try:
        layer.setCustomProperty(_PROP_PRESET, str(preset_id))
    except Exception:
        pass  # nosec


def _clear_basemap_tags(preset_id=None):
    for layer in QgsProject.instance().mapLayers().values():
        if layer is None:
            continue
        try:
            pid = str(layer.customProperty(_PROP_PRESET) or "")
        except Exception:
            pid = ""
        if not pid:
            continue
        if preset_id is not None and pid != str(preset_id):
            continue
        try:
            layer.removeCustomProperty(_PROP_PRESET)
            layer.removeCustomProperty(_PROP_SLOT)
        except Exception:
            pass  # nosec


def _hide_other_presets(active_id):
    root = QgsProject.instance().layerTreeRoot()
    for layer in QgsProject.instance().mapLayers().values():
        if layer is None:
            continue
        try:
            pid = str(layer.customProperty(_PROP_PRESET) or "")
        except Exception:
            pid = ""
        if not pid or pid == str(active_id):
            continue
        node = root.findLayer(layer.id())
        if node is None:
            continue
        try:
            node.setItemVisibilityChecked(False)
        except Exception:
            pass  # nosec


def _apply_preset(iface, preset_id):
    store = _load_store()
    preset = _preset_by_id(store, preset_id)
    if preset is None:
        return
    entries = preset.get("layers") or []
    if not isinstance(entries, list) or not entries:
        QMessageBox.warning(
            iface.mainWindow(),
            tr("底图切换"),
            tr("该预设还没有保存任何图层，请先在「管理底图预设」里添加。"),
        )
        return
    _hide_other_presets(preset_id)
    root = QgsProject.instance().layerTreeRoot()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        uri = str(entry.get("uri") or "")
        provider = str(entry.get("provider") or "wms")
        title = str(entry.get("name") or tr("底图"))
        if not uri:
            continue
        layer = _find_matching_layer(provider, uri)
        if layer is None:
            layer = QgsRasterLayer(uri, title, provider)
            if not layer.isValid():
                continue
            QgsProject.instance().addMapLayer(layer, False)
            try:
                idx = len(list(root.children()))
                root.insertLayer(idx, layer)
            except Exception:
                QgsProject.instance().addMapLayer(layer, True)
        _tag_layer(layer, preset_id)
        try:
            layer.setCustomProperty(_PROP_SLOT, str(index))
        except Exception:
            pass  # nosec
        node = root.findLayer(layer.id())
        if node is not None:
            try:
                node.setItemVisibilityChecked(True)
            except Exception:
                pass  # nosec
    try:
        iface.mapCanvas().refresh()
    except Exception:
        pass  # nosec


def _add_from_active(iface):
    layer = iface.activeLayer()
    if not _is_basemap_candidate(layer):
        QMessageBox.information(
            iface.mainWindow(),
            tr("底图切换"),
            tr("请先在图层面板里选中一个栅格图层作为底图。"),
        )
        return
    store = _load_store()
    text, ok = QInputDialog.getText(iface.mainWindow(), tr("底图切换"), tr("新预设名称："))
    if not ok:
        return
    name = " ".join(str(text or "").split())
    if not name:
        QMessageBox.warning(iface.mainWindow(), tr("底图切换"), tr("名称不能为空。"))
        return
    provider, uri, lname = _layer_signature(layer)
    pid = str(uuid.uuid4())
    store.setdefault("presets", []).append(
        {
            "id": pid,
            "title": name,
            "layers": [{"provider": provider, "uri": uri, "name": lname or name}],
        }
    )
    _save_store(store)
    _apply_preset(iface, pid)


def _fill(iface, menu):
    panel = _panels.get(id(menu))
    if panel is None or not panel.alive():
        menu.clear()
        panel = BasemapMenuPanel(iface, menu)
        _panels[id(menu)] = panel
    panel.reset()


class BasemapMenuPanel:
    def __init__(self, iface, menu):
        self.iface = iface
        self.menu = menu

    def alive(self):
        try:
            return self.menu is not None and hasattr(self.menu, "clear")
        except RuntimeError:
            return False

    def reset(self):
        menu = self.menu
        menu.clear()
        store = _load_store()
        presets = list(store.get("presets") or [])
        for preset in presets:
            pid = str(preset.get("id") or "")
            title = str(preset.get("title") or tr("未命名"))
            if not pid:
                continue
            act = menu.addAction(title)
            act.triggered.connect(lambda checked=False, p=pid: _apply_preset(self.iface, p))
        menu.addSeparator()
        subcommands.add_to_menu(self.iface, "lpt:basemap", menu, "lpt:basemap:add_current")
        subcommands.add_to_menu(self.iface, "lpt:basemap", menu, "lpt:basemap:manage")


class BasemapManagerDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle(tr("底图预设"))
        self.resize(420, 320)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("选择一个预设后，点「应用」即可切换底图显示。")))
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.btn_apply = QPushButton(tr("应用"))
        self.btn_rename = QPushButton(tr("重命名预设"))
        self.btn_add = QPushButton(tr("从当前图层添加"))
        self.btn_del = QPushButton(tr("删除所选预设"))
        row.addWidget(self.btn_apply)
        row.addWidget(self.btn_rename)
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_del)
        layout.addLayout(row)
        box = QDialogButtonBox(qt_attr(QDialogButtonBox, "Close"))
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_rename.clicked.connect(self._rename)
        self.btn_add.clicked.connect(self._add)
        self.btn_del.clicked.connect(self._delete)
        self.reload()

    def exec_dialog(self):
        from .qt_compat import run_dialog

        return run_dialog(self)

    def reload(self):
        self.list.clear()
        store = _load_store()
        for preset in store.get("presets") or []:
            pid = str(preset.get("id") or "")
            title = str(preset.get("title") or tr("未命名"))
            if not pid:
                continue
            item = QListWidgetItem(title)
            item.setData(user_role(), pid)
            self.list.addItem(item)

    def _current_id(self):
        item = self.list.currentItem()
        if item is None:
            return ""
        try:
            return str(item.data(user_role()) or "")
        except Exception:
            return ""

    def _apply(self):
        pid = self._current_id()
        if not pid:
            QMessageBox.information(self, tr("底图切换"), tr("请先选中一个预设。"))
            return
        _apply_preset(self.iface, pid)
        self.accept()

    def _rename(self):
        pid = self._current_id()
        if not pid:
            QMessageBox.information(self, tr("底图切换"), tr("请先选中一个预设。"))
            return
        item = self.list.currentItem()
        old = item.text() if item is not None else ""
        text, ok = QInputDialog.getText(self, tr("底图切换"), tr("新名称："), text=old)
        if not ok:
            return
        name = " ".join(str(text or "").split())
        if not name:
            QMessageBox.warning(self, tr("底图切换"), tr("名称不能为空。"))
            return
        store = _load_store()
        for p in store.get("presets") or []:
            if str(p.get("id")) == str(pid):
                p["title"] = name
                break
        _save_store(store)
        self.reload()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it is not None and str(it.data(user_role()) or "") == str(pid):
                self.list.setCurrentItem(it)
                break

    def _add(self):
        layer = self.iface.activeLayer()
        if not _is_basemap_candidate(layer):
            QMessageBox.information(self, tr("底图切换"), tr("请先在图层面板里选中一个栅格图层。"))
            return
        text, ok = QInputDialog.getText(self, tr("底图切换"), tr("预设名称："))
        if not ok:
            return
        name = " ".join(str(text or "").split())
        if not name:
            QMessageBox.warning(self, tr("底图切换"), tr("名称不能为空。"))
            return
        provider, uri, lname = _layer_signature(layer)
        store = _load_store()
        pid = str(uuid.uuid4())
        store.setdefault("presets", []).append(
            {
                "id": pid,
                "title": name,
                "layers": [{"provider": provider, "uri": uri, "name": lname or name}],
            }
        )
        _save_store(store)
        self.reload()
        _apply_preset(self.iface, pid)

    def _delete(self):
        pid = self._current_id()
        if not pid:
            QMessageBox.information(self, tr("底图切换"), tr("请先选中一个预设。"))
            return
        if not ask(self, tr("底图切换"), tr("确定删除该底图预设吗？工程里的图层不会被移除。")):
            return
        store = _load_store()
        store["presets"] = [p for p in (store.get("presets") or []) if str(p.get("id")) != str(pid)]
        _save_store(store)
        _clear_basemap_tags(pid)
        self.reload()


from . import subcommands


def _manage_dialog(iface):
    BasemapManagerDialog(iface, iface.mainWindow()).exec_dialog()


tr("用当前图层加入预设")
tr("管理底图预设…")
subcommands.register("lpt:basemap", [
    ("add_current", "用当前图层加入预设", lambda iface: _add_from_active(iface)),
    ("manage", "管理底图预设…", _manage_dialog),
])