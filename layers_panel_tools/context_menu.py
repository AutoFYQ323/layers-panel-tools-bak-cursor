# -*- coding: utf-8 -*-
"""图层面板右键菜单：调顺序、改显示名、隐藏，并用下拉框加入适合的本插件功能。"""

import json

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr
from .icons import load_icon
from .plugin_settings import flush, plugin_qsettings
from .qt_compat import enum_int, qt_attr, user_role

_KEY = "menu_context"
_HOST = None

# 对着当前图层能做的功能，以及图层管理、按多边形选择、图层开关、底图切换、分类导出。
CANDIDATES = (
    ("lpt:solo", "独显图层"),
    ("lpt:flash", "闪烁定位"),
    ("lpt:opacity", "透明度"),
    ("lpt:layer_tags", "图层颜色标签"),
    ("lpt:repair", "修复数据源"),
    ("lpt:copy_files", "复制图层文件"),
    ("lpt:layer_ops", "图层操作"),
    ("lpt:class_export", "分类导出"),
    ("lpt:layer_manager", "图层管理"),
    ("lpt:poly_select", "按多边形选择"),
    ("lpt:switch", "图层开关"),
    ("lpt:basemap", "底图切换"),
)
_CANDIDATE_IDS = {item[0]: item[1] for item in CANDIDATES}

_ID = user_role()
_KIND = user_role(1)
_TITLE = user_role(2)


_HOST = None
_IFACE = None


def bind_host(host, iface=None):
    global _HOST, _IFACE
    _HOST = host
    if iface is not None:
        _IFACE = iface


def _empty():
    return {"order": [], "hidden": [], "titles": {}, "labels": {}, "added": []}


def load_menu():
    try:
        raw = plugin_qsettings().value(_KEY, "")
    except Exception:
        raw = ""
    if raw in (None, ""):
        return _empty()
    if not isinstance(raw, str):
        raw = str(raw)
    try:
        data = json.loads(raw)
    except Exception:
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    found = _empty()
    found["order"] = [str(item) for item in data.get("order") or [] if str(item)]
    found["hidden"] = [str(item) for item in data.get("hidden") or [] if str(item)]
    titles = data.get("titles") if isinstance(data.get("titles"), dict) else {}
    labels = data.get("labels") if isinstance(data.get("labels"), dict) else {}
    found["titles"] = {str(key): str(value) for key, value in titles.items() if str(value or "").strip()}
    found["labels"] = {str(key): str(value) for key, value in labels.items() if str(value or "").strip()}
    found["added"] = [str(item) for item in data.get("added") or [] if str(item) in _CANDIDATE_IDS]
    return found


def save_menu(data):
    payload = {
        "order": list(data.get("order") or []),
        "hidden": list(data.get("hidden") or []),
        "titles": dict(data.get("titles") or {}),
        "labels": dict(data.get("labels") or {}),
        "added": [item for item in data.get("added") or [] if item in _CANDIDATE_IDS],
    }
    settings = plugin_qsettings()
    settings.setValue(_KEY, json.dumps(payload, ensure_ascii=False))
    flush()


def _clean_text(text):
    return str(text or "").replace("&", "").strip()


def _unique(base, seen):
    if base not in seen:
        return base
    number = 2
    while "%s#%d" % (base, number) in seen:
        number += 1
    return "%s#%d" % (base, number)


def describe_menu(menu):
    """(key, label, separator?) for each top-level action. Submenus stay one item."""
    actions = list(menu.actions()) if menu is not None else []
    found = []
    seen = set()
    for index, action in enumerate(actions):
        try:
            if action.property("lpt_ctx_id"):
                continue
            name = action.objectName() or ""
            if name.startswith("LayersPanelTools"):
                continue
        except Exception:
            continue  # nosec
        if action.isSeparator():
            anchor = ""
            for later in actions[index + 1:]:
                try:
                    if later.isSeparator():
                        continue
                    anchor = later.objectName() or _clean_text(later.text())
                except Exception:
                    continue  # nosec
                if anchor:
                    break
            key = _unique("sep:" + (anchor or str(index)), seen)
            seen.add(key)
            found.append((key, "", True))
            continue
        try:
            object_name = action.objectName() or ""
            label = _clean_text(action.text())
        except Exception:
            continue  # nosec
        if object_name:
            base = "obj:" + object_name
        else:
            base = "txt:" + (label or str(index))
        key = _unique(base, seen)
        seen.add(key)
        found.append((key, label, False))
    return found


def _remember(pairs, refresh_labels):
    data = load_menu()
    changed = False
    known = set(data["order"])
    for key, label, _separator in pairs:
        if key not in known:
            data["order"].append(key)
            known.add(key)
            changed = True
        if not label:
            continue
        saved_title = str(data["titles"].get(key) or "").strip()
        if saved_title and label == saved_title and data["labels"].get(key):
            continue
        if refresh_labels or key not in data["labels"]:
            if data["labels"].get(key) != label:
                data["labels"][key] = label
                changed = True
    if changed:
        save_menu(data)
    return data


def snapshot(iface):
    if iface is None:
        return []
    try:
        view = iface.layerTreeView()
    except Exception:
        view = None
    if view is None:
        return []
    try:
        provider = view.menuProvider()
    except Exception:
        provider = None
    if provider is None:
        return []
    try:
        menu = provider.createContextMenu()
    except Exception:
        return []
    if menu is None:
        return []
    try:
        return describe_menu(menu)
    finally:
        try:
            menu.deleteLater()
        except Exception:
            pass  # nosec


def _toolbar_custom(button_id):
    host = _HOST
    if host is None:
        return ""
    try:
        return str(host.titles.get(button_id) or "").strip()
    except Exception:
        return ""


def _shown_title(key, saved):
    """右键上只显示自定义名。本插件按钮的自定义名跟工具条是同一份。"""
    if key in _CANDIDATE_IDS:
        return _toolbar_custom(key)
    return str(saved or "").strip()


def _display_name(base, custom):
    custom = str(custom or "").strip()
    base = str(base or "")
    if not custom:
        return base
    return "%s(%s)" % (base, custom)


def _toolbar_action(button_id):
    host = _HOST
    if host is None:
        return None
    try:
        return host.by_id.get(button_id)
    except Exception:
        return None


def _icon_for(button_id):
    action = _toolbar_action(button_id)
    if action is not None:
        try:
            icon = action.icon()
            if icon is not None and not icon.isNull():
                return icon
        except Exception:
            pass  # nosec
    return QIcon()


def _copy_tool_menu(button_id, proxy):
    proxy.clear()
    action = _toolbar_action(button_id)
    widget = None
    if action is not None:
        getter = getattr(action, "defaultWidget", None)
        if callable(getter):
            try:
                widget = getter()
            except Exception:
                widget = None
    source = None
    if widget is not None:
        try:
            source = widget.menu()
        except Exception:
            source = None
    if source is None:
        from . import subcommands

        iface = _IFACE
        if iface is None:
            return
        for sub_id, _msgid, _runner in subcommands.subcommands_of(button_id):
            subcommands.add_to_menu(iface, button_id, proxy, sub_id)
        return
    try:
        source.aboutToShow.emit()
    except Exception:
        pass  # nosec
    for item in list(source.actions()):
        proxy.addAction(item)


def _plugin_action(menu, button_id, title):
    msgid = _CANDIDATE_IDS.get(button_id, button_id)
    text = title or tr(msgid)
    action = QAction(_icon_for(button_id), text, menu)
    action.setProperty("lpt_ctx_id", button_id)
    tool = _toolbar_action(button_id)
    widget = None
    if tool is not None:
        getter = getattr(tool, "defaultWidget", None)
        if callable(getter):
            try:
                widget = getter()
            except Exception:
                widget = None
    has_menu = False
    if widget is not None:
        try:
            has_menu = widget.menu() is not None
        except Exception:
            has_menu = False
    if not has_menu:
        from . import subcommands

        has_menu = subcommands.has_subcommands(button_id)
    if has_menu:
        sub = QMenu(menu)
        sub.aboutToShow.connect(lambda bid=button_id, box=sub: _copy_tool_menu(bid, box))
        action.setMenu(sub)
        return action

    def fire(_checked=False, bid=button_id):
        target = _toolbar_action(bid)
        button = None
        if target is not None:
            getter = getattr(target, "defaultWidget", None)
            if callable(getter):
                try:
                    button = getter()
                except Exception:
                    button = None
        if button is not None:
            try:
                button.click()
                return
            except Exception:
                pass  # nosec
        if target is not None:
            try:
                target.trigger()
            except Exception:
                pass  # nosec

    action.triggered.connect(fire)
    return action


def apply_menu(menu, iface):
    """QGIS 生成菜单之后调用：重排、改名、隐藏，再插入用户加进来的功能。"""
    if menu is None:
        return
    described = []
    actions = []
    for key, label, separator in describe_menu(menu):
        described.append((key, label, separator))
    by_key = {}
    seen = set()
    raw = list(menu.actions())
    # describe_menu and this walk must agree. Rebuild the map from the same rules.
    for index, action in enumerate(raw):
        try:
            if action.property("lpt_ctx_id"):
                continue
            name = action.objectName() or ""
            if name.startswith("LayersPanelTools"):
                continue
        except Exception:
            continue  # nosec
        if action.isSeparator():
            anchor = ""
            for later in raw[index + 1:]:
                try:
                    if later.isSeparator():
                        continue
                    anchor = later.objectName() or _clean_text(later.text())
                except Exception:
                    continue  # nosec
                if anchor:
                    break
            key = _unique("sep:" + (anchor or str(index)), seen)
        else:
            try:
                object_name = action.objectName() or ""
                label = _clean_text(action.text())
            except Exception:
                continue  # nosec
            base = ("obj:" + object_name) if object_name else ("txt:" + (label or str(index)))
            key = _unique(base, seen)
        seen.add(key)
        by_key[key] = action
        actions.append(action)
    data = _remember([(key, label, sep) for key, label, sep in described], refresh_labels=False)
    hidden = set(data["hidden"])
    titles = data["titles"]
    added = [item for item in data["added"] if item in _CANDIDATE_IDS]
    present = set(by_key) | set(added)
    order = [key for key in data["order"] if key in present]
    for key in by_key:
        if key not in order:
            order.append(key)
    for key in added:
        if key not in order:
            order.append(key)
    for action in raw:
        try:
            menu.removeAction(action)
        except Exception:
            pass  # nosec
    for key in order:
        if key in by_key:
            action = by_key[key]
            try:
                menu.addAction(action)
                action.setVisible(key not in hidden)
            except Exception:
                continue  # nosec
            if action.isSeparator():
                continue
            custom = _shown_title(key, titles.get(key))
            try:
                if not str(action.property("_lpt_base_text") or ""):
                    action.setProperty("_lpt_base_text", action.text())
                if custom:
                    action.setText(custom)
                else:
                    base = str(action.property("_lpt_base_text") or "")
                    if base:
                        action.setText(base)
            except Exception:
                pass  # nosec
            continue
        if key in added and key not in hidden:
            try:
                menu.addAction(_plugin_action(menu, key, _shown_title(key, "")))
            except Exception:
                continue  # nosec


class ContextMenus:
    def __init__(self, iface, host):
        self.iface = iface
        self.host = host
        self._view = None
        self._on = False

    def attach(self):
        bind_host(self.host, self.iface)
        try:
            view = self.iface.layerTreeView()
        except Exception:
            view = None
        if view is None:
            return False
        if self._on and self._view is view:
            return True
        self.detach()
        signal = getattr(view, "contextMenuAboutToShow", None)
        if signal is None:
            return False
        try:
            signal.connect(self._on_menu)
        except Exception:
            return False
        self._view = view
        self._on = True
        return True

    def detach(self):
        view = self._view
        self._view = None
        self._on = False
        if view is None:
            return
        signal = getattr(view, "contextMenuAboutToShow", None)
        if signal is None:
            return
        try:
            signal.disconnect(self._on_menu)
        except Exception:
            pass  # nosec

    def _on_menu(self, menu):
        apply_menu(menu, self.iface)


class _StillCombo(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class MenuSettingsPage(QWidget):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self._filling = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.list = QListWidget()
        self.list.setDragDropMode(qt_attr(QAbstractItemView, "InternalMove"))
        self.list.setSelectionMode(qt_attr(QAbstractItemView, "SingleSelection"))
        layout.addWidget(self.list, 1)
        title_row = QHBoxLayout()
        self.btn_reset = QPushButton()
        self.btn_up = QPushButton()
        self.btn_down = QPushButton()
        self.title_label = QLabel()
        self.title_edit = QLineEdit()
        title_row.addWidget(self.btn_reset)
        title_row.addWidget(self.btn_up)
        title_row.addWidget(self.btn_down)
        title_row.addWidget(self.title_label)
        title_row.addWidget(self.title_edit, 1)
        layout.addLayout(title_row)
        add_row = QHBoxLayout()
        self.add_label = QLabel()
        self.add_combo = _StillCombo()
        self.btn_add = QPushButton()
        self.btn_remove = QPushButton()
        add_row.addWidget(self.add_label)
        add_row.addWidget(self.add_combo, 1)
        add_row.addWidget(self.btn_add)
        add_row.addWidget(self.btn_remove)
        layout.addLayout(add_row)
        self.list.currentItemChanged.connect(lambda *_args: self._show_title())
        self.title_edit.textChanged.connect(self._on_title)
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down.clicked.connect(lambda: self._move(1))
        self.btn_reset.clicked.connect(self._reset)
        self.btn_add.clicked.connect(self._add)
        self.btn_remove.clicked.connect(self._remove)
        self.retranslate()

    def retranslate(self):
        self.hint.setText(tr(
            "管理图层右键菜单。勾选为显示，拖动或用上下箭头改顺序。"
            "自定义名称留空就用原来的名字；写了名字后，列表显示成原名(自定义名)，图层右键里只显示括号里的名字。"
            "工具条上改过的按钮名字会同步到这里。恢复默认只还原这一页，不动工具条。"
            "下面的下拉框用来加入本插件功能。打开这一页时会读取当前右键菜单；若列表还空，先在图层面板上对图层右键一次。"
        ))
        self.title_label.setText(tr("自定义名称"))
        self.title_edit.setPlaceholderText(tr("留空使用原名"))
        self.btn_reset.setText(tr("恢复默认"))
        self.btn_reset.setToolTip(tr("只恢复图层右键菜单，不动工具条。"))
        self.btn_up.setText(tr("上移"))
        self.btn_down.setText(tr("下移"))
        self.add_label.setText(tr("添加功能"))
        self.btn_add.setText(tr("添加"))
        self.btn_remove.setText(tr("移除"))
        self._fill_combo()
        self._retitle_rows()

    def refresh(self):
        pairs = snapshot(self.iface)
        if pairs:
            _remember(pairs, refresh_labels=True)
        self._fill_list()

    def commit(self):
        data = load_menu()
        order = []
        hidden = []
        titles = {}
        added = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            key = str(item.data(_ID) or "")
            if not key:
                continue
            order.append(key)
            if enum_int(item.checkState(), 2) == 0:
                hidden.append(key)
            title = str(item.data(_TITLE) or "").strip()
            if title and str(item.data(_KIND) or "") != "plugin":
                titles[key] = title
            if str(item.data(_KIND) or "") == "plugin":
                added.append(key)
        data["order"] = order
        data["hidden"] = hidden
        data["titles"] = titles
        data["added"] = added
        save_menu(data)

    def _fill_list(self):
        data = load_menu()
        order = list(data["order"])
        known = set(order)
        for key in data["added"]:
            if key not in known:
                order.append(key)
        self._filling = True
        self.list.clear()
        for key in order:
            if str(key).startswith("lpt:") and key not in _CANDIDATE_IDS:
                continue
            kind = "plugin" if key in _CANDIDATE_IDS else ("sep" if key.startswith("sep:") else "native")
            if kind == "plugin" and key not in data["added"] and key not in data["order"]:
                continue
            item = QListWidgetItem()
            item.setData(_ID, key)
            item.setData(_KIND, kind)
            item.setData(_TITLE, self._initial_title(key, kind, data))
            flags = (
                qt_attr(Qt, "ItemIsEnabled")
                | qt_attr(Qt, "ItemIsSelectable")
                | qt_attr(Qt, "ItemIsDragEnabled")
                | qt_attr(Qt, "ItemIsUserCheckable")
            )
            item.setFlags(flags)
            visible = key not in set(data["hidden"])
            item.setCheckState(qt_attr(Qt, "Checked" if visible else "Unchecked"))
            if kind == "plugin":
                icon = _icon_for(key)
                if icon is not None and not icon.isNull():
                    item.setIcon(icon)
            self.list.addItem(item)
            self._paint_item(item)
        self._filling = False
        self._fill_combo()
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self._show_title()

    def _retitle_rows(self):
        if self._filling:
            return
        for row in range(self.list.count()):
            self._paint_item(self.list.item(row))

    def _settings(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "title_for") and hasattr(parent, "set_button_title"):
                return parent
            parent = parent.parent()
        return None

    def _initial_title(self, key, kind, data):
        if kind == "plugin":
            dialog = self._settings()
            if dialog is not None:
                return str(dialog.title_for(key) or "").strip()
            return _toolbar_custom(key)
        return str(data["titles"].get(key) or "").strip()

    def _base_label(self, item):
        kind = str(item.data(_KIND) or "")
        key = str(item.data(_ID) or "")
        if kind == "plugin":
            return tr(_CANDIDATE_IDS.get(key, key))
        if kind == "sep":
            return tr("—— 分隔线 ——")
        return load_menu()["labels"].get(key) or key

    def _paint_item(self, item):
        if item is None:
            return
        item.setText(_display_name(self._base_label(item), item.data(_TITLE)))

    def sync_toolbar_titles(self):
        dialog = self._settings()
        if dialog is None:
            return
        self._filling = True
        for row in range(self.list.count()):
            item = self.list.item(row)
            if str(item.data(_KIND) or "") != "plugin":
                continue
            item.setData(_TITLE, dialog.title_for(str(item.data(_ID) or "")))
        self._filling = False
        self._retitle_rows()
        self._show_title()

    def _reset(self):
        save_menu(_empty())
        self.refresh()

    def _fill_combo(self):
        present = set()
        for row in range(self.list.count()):
            present.add(str(self.list.item(row).data(_ID) or ""))
        current = str(self.add_combo.currentData() or "")
        self.add_combo.blockSignals(True)
        self.add_combo.clear()
        for button_id, msgid in CANDIDATES:
            if button_id in present:
                continue
            self.add_combo.addItem(tr(msgid), button_id)
        if current:
            index = self.add_combo.findData(current)
            if index >= 0:
                self.add_combo.setCurrentIndex(index)
        self.add_combo.blockSignals(False)
        self.btn_add.setEnabled(self.add_combo.count() > 0)

    def _show_title(self):
        item = self.list.currentItem()
        plugin = item is not None and str(item.data(_KIND) or "") == "plugin"
        editable = item is not None and str(item.data(_KIND) or "") != "sep"
        self.title_edit.blockSignals(True)
        self.title_edit.setEnabled(editable)
        self.title_edit.setText(str(item.data(_TITLE) or "") if editable else "")
        self.title_edit.blockSignals(False)
        self.btn_remove.setEnabled(plugin)

    def _on_title(self, text):
        item = self.list.currentItem()
        if item is None or not self.title_edit.isEnabled():
            return
        item.setData(_TITLE, text)
        if str(item.data(_KIND) or "") == "plugin":
            dialog = self._settings()
            if dialog is not None:
                dialog.set_button_title(str(item.data(_ID) or ""), text)
        self._paint_item(item)

    def _move(self, delta):
        row = self.list.currentRow()
        if row < 0:
            return
        target = row + delta
        if target < 0 or target >= self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)

    def _add(self):
        button_id = str(self.add_combo.currentData() or "")
        if not button_id:
            return
        item = QListWidgetItem()
        item.setData(_ID, button_id)
        item.setData(_KIND, "plugin")
        item.setData(_TITLE, "")
        dialog = self._settings()
        if dialog is not None:
            item.setData(_TITLE, dialog.title_for(button_id))
        item.setFlags(
            qt_attr(Qt, "ItemIsEnabled")
            | qt_attr(Qt, "ItemIsSelectable")
            | qt_attr(Qt, "ItemIsDragEnabled")
            | qt_attr(Qt, "ItemIsUserCheckable")
        )
        item.setCheckState(qt_attr(Qt, "Checked"))
        icon = _icon_for(button_id)
        if icon is not None and not icon.isNull():
            item.setIcon(icon)
        self.list.addItem(item)
        self._paint_item(item)
        self.list.setCurrentItem(item)
        self._fill_combo()

    def _remove(self):
        item = self.list.currentItem()
        if item is None or str(item.data(_KIND) or "") != "plugin":
            return
        row = self.list.row(item)
        self.list.takeItem(row)
        self._fill_combo()
        self._show_title()
