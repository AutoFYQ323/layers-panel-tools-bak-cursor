# -*- coding: utf-8 -*-
"""Find the Layers panel toolbar and apply show, hide, and order."""

import zlib
import re

from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QSize
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDockWidget, QSizePolicy, QToolBar, QWidgetAction

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from qgis.core import Qgis, QgsApplication, QgsMessageLog

from . import settings_store
from .button_help import help_msgid_for, hover_tip
from .i18n import tr
from .order_logic import (
    MAX_ROWS,
    SETTINGS_ID,
    clean_hidden,
    clean_rows,
    clean_titles,
    factory_hidden,
    factory_row,
    hidden_for_load,
    sort_plugin_tools,
    is_separator,
    merge_order,
)
from .qt_compat import qt_attr
from .tools import extra_actions

_LOG = "LayersPanelTools"

# Same theme paths QgisApp::initLayerTreeView passes to getThemeIcon.
_ICON_ROLES = (
    ("/propertyicons/symbology.svg", "layer_styling"),
    ("/mActionAddGroup.svg", "add_group"),
    ("/mActionShowAllLayers.svg", "map_themes"),
    ("/mActionFilter2.svg", "filter_legend"),
    ("/mActionFilter.svg", "filter_legend_alt"),
    ("/mActionExpandTree.svg", "expand_all"),
    ("/mActionCollapseTree.svg", "collapse_all"),
    ("/mActionRemoveLayer.svg", "remove_layer"),
)

_PLAIN_BUTTONS = {"QToolButton", "QgsToolButton", "QAction", "QWidgetAction", "QgsToolButtonAction"}

# Order used by QgisApp::initLayerTreeView when a button has no tooltip and no icon of its own.
_INDEX_ROLES = (
    "layer_styling",
    "add_group",
    "map_themes",
    "filter_legend",
    "expression_filter",
    "expand_all",
    "collapse_all",
    "remove_layer",
)

_ROLE_LABELS = {
    "layer styling": "layer_styling",
    "打开图层样式面板": "layer_styling",
    "图层样式": "layer_styling",
    "add group": "add_group",
    "添加组": "add_group",
    "manage map themes": "map_themes",
    "管理地图主题": "map_themes",
    "filter legend": "filter_legend",
    "过滤图例": "filter_legend",
    "filter legend by expression": "expression_filter",
    "按表达式过滤图例": "expression_filter",
    "expand all": "expand_all",
    "全部展开": "expand_all",
    "collapse all": "collapse_all",
    "全部折叠": "collapse_all",
    "remove layer/group": "remove_layer",
    "移除图层/组": "remove_layer",
}


def find_toolbar(iface):
    main = iface.mainWindow()
    dock = main.findChild(QDockWidget, "Layers") if main is not None else None
    view = iface.layerTreeView()
    if dock is None and view is not None and view.parent() is not None:
        dock = view.parent().parent()
    if dock is None:
        return None
    container = dock.widget()
    layout = container.layout() if container is not None else None
    if layout is not None:
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, QToolBar):
                return widget
    bars = dock.findChildren(QToolBar)
    return bars[0] if bars else None


def _icon_mode():
    mode = getattr(QIcon, "Normal", None)
    state = getattr(QIcon, "Off", None)
    if mode is None:
        mode = QIcon.Mode.Normal
        state = QIcon.State.Off
    return mode, state


def _png(icon, size):
    if icon is None or icon.isNull():
        return b""
    mode, state = _icon_mode()
    try:
        pixmap = icon.pixmap(size, mode, state)
    except TypeError:
        pixmap = icon.pixmap(size)
    if pixmap.isNull():
        return b""
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(qt_attr(QIODevice, "WriteOnly"))
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def _toolbar_icon_size(toolbar):
    size = toolbar.iconSize()
    if size.isEmpty():
        return QSize(16, 16)
    return size


def _theme_icons(size):
    found = []
    for path, role in _ICON_ROLES:
        icon = QgsApplication.getThemeIcon(path)
        payload = _png(icon, size)
        if payload:
            found.append((role, payload))
    return found


def plain_title(text):
    """QGIS tooltips are HTML, such as <b>添加组</b> (Ctrl+D). The list shows the words only."""
    raw = str(text or "")
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    raw = raw.replace("\xa0", " ")
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw)
    return " ".join(raw.split())


def _toolbar_widget(action, toolbar):
    if toolbar is None:
        return None
    try:
        return toolbar.widgetForAction(action)
    except Exception:
        return None


def _widget_text(widget):
    if widget is None:
        return ""
    reader = getattr(widget, "text", None)
    if not callable(reader):
        return ""
    try:
        return reader() or ""
    except Exception:
        return ""


def face_of(action, toolbar):
    """Icon and plain title actually drawn on the Layers toolbar."""
    widget = _toolbar_widget(action, toolbar)
    icon = action.icon() if action is not None else QIcon()
    if (icon is None or icon.isNull()) and widget is not None:
        icon = widget.icon()
    if icon is None:
        icon = QIcon()
    chunks = []
    if action is not None:
        chunks.extend((action.toolTip(), action.text(), action.iconText(), action.statusTip()))
    if widget is not None:
        chunks.extend((widget.toolTip(), _widget_text(widget), widget.statusTip()))
    label = ""
    for chunk in chunks:
        label = plain_title(chunk)
        if label:
            break
    return icon, label


def _role_from_label(label):
    if not label:
        return ""
    return _ROLE_LABELS.get(label.casefold(), "") or _ROLE_LABELS.get(label, "")


def _role_from_icon(icon, size, theme_icons, used_roles):
    payload = _png(icon, size)
    if not payload:
        return ""
    for role, theme_payload in theme_icons:
        if role in used_roles or payload != theme_payload:
            continue
        return role
    return ""


def role_title(role):
    from .i18n import tr

    if role == "layer_styling":
        tr("图层样式")
        return tr("打开图层样式面板")
    if role == "add_group":
        return tr("添加组")
    if role == "map_themes":
        return tr("管理地图主题")
    if role == "filter_legend":
        return tr("过滤图例")
    if role == "expression_filter":
        return tr("按表达式过滤图例")
    if role == "expand_all":
        return tr("全部展开")
    if role == "collapse_all":
        return tr("全部折叠")
    if role == "remove_layer":
        return tr("移除图层/组")
    return ""


def _unique(base, used):
    if base not in used:
        return base
    number = 2
    while "%s#%d" % (base, number) in used:
        number += 1
    return "%s#%d" % (base, number)


def _fallback_id(label, index, used):
    if label:
        digest = "%08x" % (zlib.crc32(label.encode("utf-8")) & 0xFFFFFFFF)
        base = "tip:" + digest
    else:
        base = "slot:%d" % index
    return _unique(base, used)


def identify_action(action, index, toolbar, size, theme_icons, used_roles, used_ids):
    """Stable id. Prefer the visible title, then the icon, then the stock toolbar position."""
    if not str(action.property("lpt_help") or ""):
        action.setProperty("lpt_help", plain_title(action.toolTip() or action.text() or ""))
    icon, label = face_of(action, toolbar)
    action.setProperty("lpt_face_label", label)
    widget = _toolbar_widget(action, toolbar)
    widget_class = type(widget).__name__ if widget is not None else ""
    role = _role_from_label(label)
    if not role:
        role = _role_from_icon(icon, size, theme_icons, used_roles)
    if not role and widget_class == "QgsLegendFilterButton":
        role = "expression_filter"
    if (not role) and 0 <= index < len(_INDEX_ROLES) and _INDEX_ROLES[index] not in used_roles:
        role = _INDEX_ROLES[index]
    if role and role not in used_roles:
        used_roles.add(role)
        action.setProperty("lpt_role_msgid", {
            "layer_styling": "打开图层样式面板",
            "add_group": "添加组",
            "map_themes": "管理地图主题",
            "filter_legend": "过滤图例",
            "expression_filter": "按表达式过滤图例",
            "expand_all": "全部展开",
            "collapse_all": "全部折叠",
            "remove_layer": "移除图层/组",
        }.get(role, ""))
        return _unique("builtin:" + role, used_ids)
    action.setProperty("lpt_role_msgid", "")
    return _fallback_id(label, index, used_ids)


class ToolbarHost:
    def __init__(self, iface, settings_action):
        self.iface = iface
        self.settings_action = settings_action
        self.toolbar = None
        self.original = []
        self.by_id = {}
        self.order = []
        self.hidden = []
        self.rows = {}
        self.titles = {}
        self.extra_bars = []
        self.owned = []
        self.attached = False
        self.fallbacks = []

    def attach(self):
        if self.attached:
            return True
        toolbar = find_toolbar(self.iface)
        if toolbar is None:
            return False
        self.toolbar = toolbar
        self.original = []
        for action in list(toolbar.actions()):
            button_id = str(action.property("lpt_id") or "")
            object_name = action.objectName() or ""
            if button_id.startswith("lpt:") or object_name.startswith("LayersPanelTools"):
                continue
            self.original.append((action, action.isVisible()))
        self.attached = True
        try:
            self._bind_native()
            self._own(self.settings_action)
            for action in extra_actions(self.iface):
                self._own(action)
            self._load_and_apply()
        except Exception:
            self.detach()
            raise
        return True

    def detach(self):
        if not self.attached:
            return
        self._restore()
        self.attached = False

    def current_rows(self):
        hidden = set(self.hidden)
        return [self._row(button_id, button_id not in hidden) for button_id in self.order]

    def default_rows(self):
        rows = []
        hidden = set(factory_hidden(self._default_ids()))
        for button_id in self._default_ids():
            item = self._row(button_id, button_id not in hidden)
            item["row"] = self._factory_row(button_id)
            rows.append(item)
        return rows

    def _factory_row(self, button_id):
        return factory_row(button_id)

    def apply_saved(self, order, hidden, rows=None, titles=None, shortcuts=None):
        self.order = merge_order(order, self._living_ids(), self._default_ids())
        self.hidden = clean_hidden(hidden, self.order)
        self._assign_rows(rows or {})
        if titles is None:
            titles = self.titles
        self.titles = clean_titles(titles, self.order)
        settings_store.save(self.order, self.hidden, self.rows, self.titles, shortcuts)
        self._place()

    def _own(self, action):
        button_id = str(action.property("lpt_id") or "")
        if not button_id:
            return
        self.by_id[button_id] = action
        if action not in self.owned:
            self.owned.append(action)

    def _bind_native(self):
        size = _toolbar_icon_size(self.toolbar)
        theme_icons = _theme_icons(size)
        used_roles = set()
        used_ids = set()
        self.by_id = {}
        self.fallbacks = []
        for index, (action, _visible) in enumerate(self.original):
            button_id = identify_action(action, index, self.toolbar, size, theme_icons, used_roles, used_ids)
            used_ids.add(button_id)
            action.setProperty("lpt_id", button_id)
            self.by_id[button_id] = action
            if button_id.startswith("tip:") or button_id.startswith("slot:"):
                label = str(action.property("lpt_face_label") or button_id)
                self.fallbacks.append(label)
                QgsMessageLog.logMessage(
                    "unmatched toolbar button %s: %s" % (button_id, label),
                    _LOG,
                    Qgis.Warning,
                )

    def _default_ids(self):
        native = []
        tools = []
        for action, _visible in self.original:
            button_id = str(action.property("lpt_id") or "")
            if button_id:
                native.append(button_id)
        for action in self.owned:
            button_id = str(action.property("lpt_id") or "")
            if not button_id or is_separator(button_id) or button_id == SETTINGS_ID:
                continue
            if button_id not in tools:
                tools.append(button_id)
        tools = sort_plugin_tools(tools)
        if SETTINGS_ID in self.by_id:
            return native + tools + [SETTINGS_ID]
        return native + tools

    def _living_ids(self):
        return set(self._default_ids())

    def _load_and_apply(self):
        saved = settings_store.load_order()
        stale = bool(saved) and any(str(item).startswith("slot:") or str(item).startswith("tip:") for item in saved)
        if stale:
            saved = None
        order = merge_order(saved, self._living_ids(), self._default_ids())
        stored = [] if saved is None else settings_store.load_hidden()
        self.order = order
        self.hidden = clean_hidden(hidden_for_load(saved, stored, order), order)
        saved_rows = {} if saved is None else settings_store.load_rows()
        saved_titles = {} if saved is None else settings_store.load_titles()
        self._assign_rows(saved_rows)
        self.titles = clean_titles(saved_titles, self.order)
        if stale:
            settings_store.save(self.order, self.hidden, self.rows, self.titles)
        self._place()

    def _assign_rows(self, saved_rows):
        source = saved_rows or {}
        self.rows = clean_rows(source, self.order)
        for button_id in self.order:
            if button_id in source:
                continue
            self.rows[button_id] = factory_row(button_id)

    def _row_number(self, button_id):
        try:
            number = int(self.rows.get(button_id, 1))
        except (TypeError, ValueError):
            number = 1
        if number < 1 or number > MAX_ROWS:
            return 1
        return number

    def _separator(self, button_id):
        action = self.by_id.get(button_id)
        if action is None:
            action = QAction(self.iface.mainWindow())
            action.setSeparator(True)
            action.setProperty("lpt_id", button_id)
            self.by_id[button_id] = action
            self.owned.append(action)
        return action

    def _place(self):
        if self.toolbar is None:
            return
        self._clear_extra_bars()
        try:
            for action in list(self.toolbar.actions()):
                self.toolbar.removeAction(action)
        except RuntimeError:
            return
        hidden = set(self.hidden)
        buckets = {}
        placed = set()
        for button_id in self.order:
            action = self._separator(button_id) if is_separator(button_id) else self.by_id.get(button_id)
            if action is None:
                continue
            show = button_id not in hidden
            try:
                action.setVisible(show)
            except RuntimeError:
                continue
            placed.add(id(action))
            if not show:
                continue
            buckets.setdefault(self._row_number(button_id), []).append(action)
        for action, _visible in self.original:
            if id(action) in placed:
                continue
            try:
                action.setVisible(True)
            except RuntimeError:
                continue
            buckets.setdefault(1, []).append(action)
        for action in buckets.get(1) or []:
            self.toolbar.addAction(action)
        try:
            self.toolbar.setVisible(bool(buckets.get(1)))
        except RuntimeError:
            return
        parent = self.toolbar.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is None:
            self._paint_tips()
            return
        index = layout.indexOf(self.toolbar)
        insert_at = index + 1 if index >= 0 else layout.count()
        for row in range(2, MAX_ROWS + 1):
            actions = buckets.get(row) or []
            if not actions:
                continue
            bar = self._make_row_bar(parent)
            bar.setObjectName("LayersPanelToolsRow%d" % row)
            layout.insertWidget(insert_at, bar)
            insert_at += 1
            self.extra_bars.append(bar)
            for action in actions:
                bar.addAction(action)
        self._paint_tips()

    def _paint_tips(self):
        for button_id, action in list(self.by_id.items()):
            self._paint_tip(action, button_id)

    def _paint_tip(self, action, button_id):
        if action is None or is_separator(button_id):
            return
        custom = str(self.titles.get(button_id) or "").strip()
        try:
            action.setProperty("lpt_custom_tip", custom)
        except RuntimeError:
            return
        name = custom or self._stock_name(action)
        if not name:
            return
        msgid = str(action.property("lpt_msgid") or "")
        tip_msgid = str(action.property("lpt_tip_msgid") or "")
        try:
            tip = hover_tip(button_id, msgid, tip_msgid, custom)
        except Exception:
            tip = ""
        if not tip:
            tip = name
        try:
            action.setToolTip(tip)
            if custom:
                action.setText(name)
        except RuntimeError:
            return
        widget = None
        for bar in [self.toolbar] + list(self.extra_bars):
            if bar is None:
                continue
            try:
                widget = bar.widgetForAction(action)
            except Exception:
                widget = None
            if widget is not None:
                break
        if widget is None:
            getter = getattr(action, "defaultWidget", None)
            if callable(getter):
                try:
                    widget = getter()
                except Exception:
                    widget = None
        if widget is not None:
            try:
                widget.setToolTip(tip)
            except RuntimeError:
                pass

    def _stock_name(self, action):
        msgid = str(action.property("lpt_msgid") or "") or str(action.property("lpt_role_msgid") or "")
        if msgid:
            return tr(msgid)
        native = plain_title(action.property("lpt_face_label") or "")
        if native:
            return native
        return plain_title(action.text() or "")

    def refresh_tips(self):
        self._paint_tips()

    def _make_row_bar(self, parent):
        bar = QToolBar(parent)
        try:
            bar.setIconSize(self.toolbar.iconSize())
            bar.setToolButtonStyle(self.toolbar.toolButtonStyle())
        except RuntimeError:
            pass
        bar.setMovable(False)
        bar.setFloatable(False)
        horizontal = getattr(QSizePolicy, "Expanding", None)
        vertical = getattr(QSizePolicy, "Fixed", None)
        if horizontal is None:
            horizontal = QSizePolicy.Policy.Expanding
            vertical = QSizePolicy.Policy.Fixed
        bar.setSizePolicy(QSizePolicy(horizontal, vertical))
        bar.setMaximumHeight(40)
        return bar

    def _clear_extra_bars(self):
        parent = None
        if self.toolbar is not None:
            try:
                parent = self.toolbar.parentWidget()
            except RuntimeError:
                parent = None
        for bar in list(self.extra_bars):
            self._drop_bar(bar)
        self.extra_bars = []
        if parent is None:
            return
        try:
            found = parent.findChildren(QToolBar)
        except RuntimeError:
            return
        for bar in found:
            try:
                name = bar.objectName() or ""
            except RuntimeError:
                continue
            if name.startswith("LayersPanelToolsRow"):
                self._drop_bar(bar)

    def _drop_bar(self, bar):
        try:
            for action in list(bar.actions()):
                bar.removeAction(action)
            bar.hide()
            bar.setParent(None)
            bar.deleteLater()
        except RuntimeError:
            pass

    def _restore(self):
        self._clear_extra_bars()
        toolbar = self.toolbar
        self.toolbar = None
        if toolbar is not None:
            try:
                toolbar.setVisible(True)
            except RuntimeError:
                pass
            try:
                current = list(toolbar.actions())
            except RuntimeError:
                current = []
            for action in current:
                try:
                    toolbar.removeAction(action)
                except RuntimeError:
                    pass
            for action, visible in self.original:
                try:
                    action.setVisible(visible)
                    toolbar.addAction(action)
                except RuntimeError:
                    pass
        for action in self.owned:
            if action is self.settings_action:
                continue
            try:
                action.deleteLater()
            except RuntimeError:
                pass
        self.owned = []
        self.by_id = {}
        self.original = []

    def _row(self, button_id, visible):
        if is_separator(button_id):
            return {
                "id": button_id,
                "kind": "sep",
                "visible": True,
                "icon": QIcon(),
                "msgid": "",
                "native": "",
                "row": self._row_number(button_id),
                "title": self.titles.get(button_id, ""),
                "help_msgid": help_msgid_for(button_id),
                "help": "",
            }
        action = self.by_id.get(button_id)
        icon = QIcon()
        msgid = ""
        native = ""
        if action is not None:
            icon, _label = face_of(action, self.toolbar)
            msgid = str(action.property("lpt_msgid") or "")
            if not msgid:
                msgid = str(action.property("lpt_role_msgid") or "")
            native = plain_title(action.property("lpt_face_label") or "")
            if not native and not str(button_id).startswith("lpt:"):
                native = plain_title(action.toolTip() or action.text() or "")
            help_msgid = str(action.property("lpt_help_msgid") or "") or help_msgid_for(button_id)
            if not help_msgid:
                help_msgid = str(action.property("lpt_tip_msgid") or "")
            help_text = "" if help_msgid else str(action.property("lpt_help") or "")
        else:
            help_msgid = ""
            help_text = ""
        if button_id == SETTINGS_ID:
            kind = "settings"
        elif str(button_id).startswith("lpt:"):
            kind = "plugin"
        else:
            kind = "native"
        return {
            "id": button_id,
            "kind": kind,
            "visible": visible,
            "icon": icon,
            "msgid": msgid,
            "native": native,
            "row": self._row_number(button_id),
            "title": self.titles.get(button_id, ""),
            "help_msgid": help_msgid,
            "help": help_text,
        }
