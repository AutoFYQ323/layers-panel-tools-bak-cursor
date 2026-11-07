# -*- coding: utf-8 -*-
"""Type part of a name, then jump to that layer or group in the Layers panel."""

from qgis.PyQt.QtCore import QEvent, QObject, QSize, Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)
from qgis.core import QgsApplication, QgsFeatureRequest, QgsProject, QgsVectorLayer

from .buttons import make_popup_menu_action, make_popup_tool
from .i18n import tr
from .icons import load_icon
from .qt_compat import enum_int, qt_attr, user_role
from .find_logic import matches
from .scope import geometry_code, is_group_node, is_layer_node, group_path, select_nodes, tell

_LIMIT = 300
_FIELD_SAMPLE = 1500
_panels = {}

tr("点")
tr("线")
tr("面")
tr("表")
tr("栅格")
tr("其他")

_TYPE_KEYS = ("point", "line", "polygon", "nogeometry", "raster", "other")
_TYPE_LABELS = {
    "point": "点",
    "line": "线",
    "polygon": "面",
    "nogeometry": "表",
    "raster": "栅格",
    "other": "其他",
}


def make_action(iface):
    tr("查找图层")
    tr("按名称、字段名或字段内容查找图层或组，并在图层面板里定位")
    return make_popup_tool(
        iface,
        "lpt:find",
        "LayersPanelToolsFind",
        "查找图层",
        "按名称、字段名或字段内容查找图层或组，并在图层面板里定位",
        load_icon("find"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsFindMenu",
        "查找图层",
        "按名称、字段名或字段内容查找图层或组，并在图层面板里定位",
        load_icon("find"),
        lambda menu: _fill(iface, menu),
    )


def close_find():
    _panels.clear()


def _fill(iface, menu):
    panel = _panels.get(id(menu))
    if panel is None or not panel.alive():
        menu.clear()
        panel = FindPanel(iface, menu)
        _panels[id(menu)] = panel
    panel.reset()


def _layer_extra_text(layer, cache=None):
    if not isinstance(layer, QgsVectorLayer):
        return ""
    key = ""
    try:
        key = layer.id()
    except Exception:
        key = ""
    if cache is not None and key:
        if key in cache:
            return cache[key]
    parts = []
    try:
        if not layer.isValid():
            return ""
    except Exception:
        return ""
    for field in layer.fields():
        try:
            parts.append(field.name())
        except Exception:
            continue  # nosec
    try:
        request = QgsFeatureRequest()
        request.setLimit(_FIELD_SAMPLE)
        for feat in layer.getFeatures(request):
            for value in feat.attributes():
                if value is None:
                    continue
                parts.append(str(value))
    except Exception:
        pass  # nosec
    text = " ".join(parts)
    if cache is not None and key:
        cache[key] = text
    return text


def _all_nodes():
    found = []

    def walk(group):
        for child in list(group.children()):
            if is_group_node(child):
                found.append(child)
                walk(child)
            elif is_layer_node(child):
                found.append(child)

    walk(QgsProject.instance().layerTreeRoot())
    return found


def _node_icon(node):
    if is_group_node(node):
        return QgsApplication.getThemeIcon("/mActionFolder.svg")
    layer = None
    try:
        layer = node.layer()
    except Exception:
        layer = None
    utils = None
    try:
        from qgis.core import QgsIconUtils as utils
    except ImportError:
        utils = None
    if layer is not None and utils is not None:
        try:
            return utils.iconForLayer(layer)
        except Exception:
            pass  # nosec
    return QgsApplication.getThemeIcon("/mIconLayer.png")


class _ArrowKeys(QObject):
    """Up and Down typed in the search box move through the list."""

    def __init__(self, panel, parent):
        super().__init__(parent)
        self._panel = panel
        self._press = enum_int(qt_attr(QEvent, "KeyPress"))
        self._up = enum_int(qt_attr(Qt, "Key_Up"))
        self._down = enum_int(qt_attr(Qt, "Key_Down"))

    def eventFilter(self, watched, event):
        if enum_int(event.type()) != self._press:
            return False
        key = enum_int(event.key())
        if key not in (self._up, self._down):
            return False
        self._panel.step(-1 if key == self._up else 1)
        return True


class FindPanel:
    def __init__(self, iface, menu):
        self.iface = iface
        self.menu = menu
        self.nodes = []
        self.shown = []

        holder = QWidget(menu)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(6, 6, 6, 6)
        search_row = QHBoxLayout()
        self.edit = QLineEdit()
        self.edit.setClearButtonEnabled(True)
        self.edit.textChanged.connect(self._refill)
        self.edit.returnPressed.connect(self._pick_current)
        self._keys = _ArrowKeys(self, holder)
        self.edit.installEventFilter(self._keys)
        search_row.addWidget(self.edit, 1)
        self.chk_fields = QCheckBox()
        self.chk_fields.setChecked(True)
        self.chk_fields.stateChanged.connect(self._refill)
        search_row.addWidget(self.chk_fields)
        layout.addLayout(search_row)
        type_row = QHBoxLayout()
        self.type_buttons = {}
        for key in _TYPE_KEYS:
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setText(tr(_TYPE_LABELS[key]))
            btn.setToolTip(tr("只看%s") % tr(_TYPE_LABELS[key]))
            btn.toggled.connect(lambda _on: self._refill())
            type_row.addWidget(btn)
            self.type_buttons[key] = btn
        type_row.addStretch(1)
        layout.addLayout(type_row)
        self.list = QListWidget()
        self.list.setIconSize(QSize(16, 16))
        self.list.itemClicked.connect(lambda item: self._pick_item(item))
        self.list.itemActivated.connect(lambda item: self._pick_item(item))
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.count = QLabel()
        self.btn_all = QPushButton()
        self.btn_all.clicked.connect(self._pick_all)
        row.addWidget(self.count, 1)
        row.addWidget(self.btn_all)
        layout.addLayout(row)
        holder.setFixedSize(340, 360)
        self.holder = holder

        action = QWidgetAction(menu)
        action.setDefaultWidget(holder)
        menu.addAction(action)
        self.action = action

    def alive(self):
        try:
            self.holder.objectName()
            return True
        except RuntimeError:
            return False

    def reset(self):
        self.nodes = _all_nodes()
        self._extra_cache = {}
        self.edit.setPlaceholderText(tr("输入名称的一部分，回车定位第一个"))
        self.chk_fields.setText(tr("含字段"))
        self.chk_fields.setToolTip(tr("同时匹配字段名和字段中的属性值（仅矢量图层）"))
        self.btn_all.setText(tr("选中全部匹配"))
        self.btn_all.setToolTip(tr("把列表里的图层都选中，方便接着调透明度、标注或移动"))
        self.edit.blockSignals(True)
        self.edit.clear()
        self.edit.blockSignals(False)
        self._refill()
        QTimer.singleShot(0, self._focus)

    def _focus(self):
        try:
            self.edit.setFocus()
        except RuntimeError:
            pass

    def _refill(self, *_args):
        include_fields = self.chk_fields.isChecked()
        wanted_types = {key for key, btn in self.type_buttons.items() if btn is not None and btn.isChecked()}
        names = []
        usable = []
        for node in self.nodes:
            try:
                label = node.name()
            except Exception:
                label = ""
            if wanted_types:
                if not is_layer_node(node):
                    continue
                layer = None
                try:
                    layer = node.layer()
                except Exception:
                    layer = None
                code = geometry_code(layer)
                if code not in wanted_types and not ("other" in wanted_types and code in ("mesh", "pointcloud", "unknown", "other")):
                    continue
            if include_fields and is_layer_node(node):
                layer = None
                try:
                    layer = node.layer()
                except Exception:
                    layer = None
                extra = _layer_extra_text(layer, getattr(self, "_extra_cache", None))
                if extra:
                    label = "%s %s" % (label, extra)
            names.append(label)
            usable.append(node)
        order = matches(names, self.edit.text())
        self.list.clear()
        self.shown = []
        for position in order[:_LIMIT]:
            node = usable[position]
            item = QListWidgetItem(_node_icon(node), names[position])
            path = group_path(node)
            item.setToolTip(path or names[position])
            item.setData(user_role(), len(self.shown))
            self.list.addItem(item)
            self.shown.append(node)
        if self.list.count():
            self.list.setCurrentRow(0)
        total = len(order)
        if total > _LIMIT:
            self.count.setText(tr("找到 %d 个，只列出前 %d 个") % (total, _LIMIT))
        else:
            self.count.setText(tr("找到 %d 个") % total)
        self.btn_all.setEnabled(any(is_layer_node(node) for node in self.shown))

    def step(self, delta):
        count = self.list.count()
        if not count:
            return
        row = self.list.currentRow()
        self.list.setCurrentRow(max(0, min(count - 1, row + delta)))

    def _pick_current(self):
        item = self.list.currentItem()
        if item is None and self.list.count():
            item = self.list.item(0)
        if item is not None:
            self._pick_item(item)

    def _pick_item(self, item):
        try:
            index = int(item.data(user_role()))
        except (TypeError, ValueError):
            return
        if not 0 <= index < len(self.shown):
            return
        node = self.shown[index]
        self.menu.close()
        if not select_nodes(self.iface, [node]):
            tell(self.iface, tr("查找图层"), tr("这一项已经不在图层面板里了。"), warning=True)
            return
        if is_layer_node(node):
            try:
                self.iface.setActiveLayer(node.layer())
            except Exception:
                pass  # nosec

    def _pick_all(self):
        picked = [node for node in self.shown if is_layer_node(node)]
        self.menu.close()
        count = select_nodes(self.iface, picked)
        tell(self.iface, tr("查找图层"), tr("已选中 %d 个图层。") % count)
