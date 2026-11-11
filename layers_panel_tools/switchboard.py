# -*- coding: utf-8 -*-
"""Remember which layers are on, per named project, and apply that set automatically."""

import json
import os

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsProject

try:
    from qgis.PyQt.QtGui import QAction, QActionGroup
except ImportError:
    from qgis.PyQt.QtWidgets import QAction, QActionGroup

from .buttons import ask, make_menu_action as menu_action
from .buttons import make_toolbar_button, qt_attr, report
from .qt_compat import accepted, run_dialog, user_role
from .i18n import apply_direction, localize_button_box, subscribe, tr
from .icons import load_icon
from .plugin_settings import plugin_qsettings, set_value
from .scheme_logic import add_layer_names, match_project, project_layer_names, replace_layer_name, saved_is_subset
from .scope import tell

_KEY = "switch_book"
_controller = None


def make_action(iface):
    tr("图层开关")
    tr("按方案切换当前项目的图层显示")
    tr("%s（%s）")
    tr("保存当前开关方案")
    tr("方案名称")
    tr("保存到项目")
    tr("未保存工程")
    tr("自动匹配当前项目：%s")
    tr("请先填写方案名称。")
    tr("没有选择有效的项目。")
    tr("已有同名方案「%s」，要覆盖吗？")
    tr("当前项目")
    tr("手动指定")
    tr("自动匹配（按图层名称）")
    global _controller
    if _controller is None:
        _controller = SwitchController(iface)
    return _controller.toolbar_action()


def make_menu_action(iface):
    global _controller
    if _controller is None:
        _controller = SwitchController(iface)
    return _controller.plugin_action()


def close_switch():
    global _controller
    controller = _controller
    _controller = None
    if controller is not None:
        controller.dispose()


def _load_book():
    try:
        raw = plugin_qsettings().value(_KEY, "") or ""
    except Exception:
        raw = ""
    if not isinstance(raw, str):
        raw = str(raw)
    if not raw.strip():
        raw = ""
    if not raw.strip():
        return {"seq": 1, "projects": [], "scratch": "", "manual_lock": False, "lock_project_id": ""}
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("seq", 1)
    data.setdefault("projects", [])
    data.setdefault("scratch", "")
    data.setdefault("manual_lock", False)
    data.setdefault("lock_project_id", "")
    return data


def _save_book(book):
    set_value(_KEY, json.dumps(book, ensure_ascii=False))


def _next_id(book, prefix):
    number = int(book.get("seq") or 1)
    book["seq"] = number + 1
    return "%s%d" % (prefix, number), number


def _project_title():
    project = QgsProject.instance()
    try:
        title = project.title() or ""
    except Exception:
        title = ""
    if title.strip():
        return title.strip()
    try:
        path = project.fileName() or ""
    except Exception:
        path = ""
    base = os.path.splitext(os.path.basename(path))[0]
    return base


def _layer_names():
    found = []
    seen = set()
    try:
        layers = list(QgsProject.instance().mapLayers().values())
    except Exception:
        layers = []
    for layer in layers:
        try:
            name = layer.name() or ""
        except Exception:
            continue  # nosec
        text = " ".join(name.split())
        if not text or text in seen:
            continue
        seen.add(text)
        found.append(text)
    return found


def _categories(layer):
    try:
        renderer = layer.renderer()
    except Exception:
        return []
    if renderer is None:
        return []
    try:
        kind = renderer.type()
    except Exception:
        return []
    if kind == "categorized":
        found = []
        try:
            categories = list(renderer.categories())
        except Exception:
            categories = []
        for category in categories:
            try:
                label = category.label() or str(category.value())
                found.append({"label": label, "on": bool(category.renderState())})
            except Exception:
                continue  # nosec
        return found
    if kind == "graduatedSymbol":
        found = []
        try:
            ranges = list(renderer.ranges())
        except Exception:
            ranges = []
        for item in ranges:
            try:
                label = item.label() or ("%s - %s" % (item.lowerValue(), item.upperValue()))
                found.append({"label": label, "on": bool(item.renderState())})
            except Exception:
                continue  # nosec
        return found
    if kind == "RuleRenderer":
        try:
            return _rule_rows(renderer.rootRule())
        except Exception:
            return []
    return []


def _rule_rows(rule):
    found = []
    try:
        label = rule.label() or rule.filterExpression() or ""
    except Exception:
        label = ""
    parent = None
    try:
        parent = rule.parent()
    except Exception:
        parent = None
    if parent is not None and label:
        try:
            found.append({"label": label, "on": bool(rule.active())})
        except Exception:
            pass  # nosec
    try:
        children = list(rule.children())
    except Exception:
        children = []
    for child in children:
        found.extend(_rule_rows(child))
    return found


def _capture():
    states = {}
    root = QgsProject.instance().layerTreeRoot()
    try:
        layers = list(QgsProject.instance().mapLayers().values())
    except Exception:
        layers = []
    for layer in layers:
        try:
            name = " ".join((layer.name() or "").split())
        except Exception:
            continue  # nosec
        if not name:
            continue
        visible = True
        try:
            node = root.findLayer(layer.id())
            if node is not None:
                visible = bool(node.itemVisibilityChecked())
        except Exception:
            visible = True
        states[name] = {"visible": visible, "categories": _categories(layer)}
    return states


def _apply_state(name, state):
    root = QgsProject.instance().layerTreeRoot()
    try:
        layers = list(QgsProject.instance().mapLayers().values())
    except Exception:
        return
    for layer in layers:
        try:
            current = " ".join((layer.name() or "").split())
        except Exception:
            continue  # nosec
        if current != name:
            continue
        try:
            node = root.findLayer(layer.id())
            if node is not None:
                node.setItemVisibilityChecked(bool(state.get("visible")))
        except Exception:
            pass  # nosec
        _write_categories(layer, state.get("categories") or [])
        try:
            layer.triggerRepaint()
        except Exception:
            pass  # nosec


def _write_categories(layer, items):
    wanted = {}
    for item in items or []:
        label = item.get("label") or ""
        if label:
            wanted[label] = bool(item.get("on"))
    if not wanted:
        return
    try:
        renderer = layer.renderer()
    except Exception:
        return
    if renderer is None:
        return
    try:
        kind = renderer.type()
    except Exception:
        return
    try:
        clone = renderer.clone()
    except Exception:
        clone = renderer
    if kind == "categorized":
        try:
            categories = list(clone.categories())
        except Exception:
            categories = []
        for index, category in enumerate(categories):
            try:
                label = category.label() or str(category.value())
            except Exception:
                continue  # nosec
            if label not in wanted:
                continue
            writer = getattr(clone, "updateCategoryRenderState", None)
            if callable(writer):
                writer(index, wanted[label])
            else:
                try:
                    category.setRenderState(wanted[label])
                except Exception:
                    pass  # nosec
        try:
            layer.setRenderer(clone)
        except Exception:
            pass  # nosec
    elif kind == "graduatedSymbol":
        try:
            ranges = list(clone.ranges())
        except Exception:
            ranges = []
        for index, item in enumerate(ranges):
            try:
                label = item.label() or ("%s - %s" % (item.lowerValue(), item.upperValue()))
            except Exception:
                continue  # nosec
            if label not in wanted:
                continue
            try:
                clone.updateRangeRenderState(index, wanted[label])
            except Exception:
                pass  # nosec
        try:
            layer.setRenderer(clone)
        except Exception:
            pass  # nosec
    elif kind == "RuleRenderer":
        try:
            _write_rules(clone.rootRule(), wanted)
            layer.setRenderer(clone)
        except Exception:
            pass  # nosec
    try:
        layer.emitStyleChanged()
    except Exception:
        pass  # nosec
    try:
        from qgis.utils import iface as running

        running.layerTreeView().refreshLayerSymbology(layer.id())
    except Exception:
        pass  # nosec


def _write_rules(rule, wanted):
    try:
        label = rule.label() or rule.filterExpression() or ""
    except Exception:
        label = ""
    if label in wanted:
        try:
            rule.setActive(wanted[label])
        except Exception:
            pass  # nosec
    try:
        children = list(rule.children())
    except Exception:
        children = []
    for child in children:
        _write_rules(child, wanted)


def _find_project(book, project_id):
    for project in book.get("projects") or []:
        if project.get("id") == project_id:
            return project
    return None


def _find_scheme(project, scheme_id):
    for scheme in project.get("schemes") or []:
        if scheme.get("id") == scheme_id:
            return scheme
    return None


def _book_project_label(project):
    if project is None:
        return ""
    return (project.get("name") or project.get("id") or "").strip()


def _scheme_menu_caption(scheme, project):
    sname = (scheme.get("name") or "").strip() or tr("方案")
    pname = _book_project_label(project)
    if pname:
        return tr("%s（%s）") % (sname, pname)
    return sname


def add_scheme(book, project):
    """Store the current visibility as a new, active scheme. Returns its name."""
    scheme_id, number = _next_id(book, "s")
    existing = {item.get("name") for item in project.get("schemes") or []}
    name = tr("方案%d") % number
    while name in existing:
        scheme_id, number = _next_id(book, "s")
        name = tr("方案%d") % number
    project.setdefault("schemes", []).append({"id": scheme_id, "name": name, "states": _capture()})
    project["active"] = scheme_id
    return name


class SaveSchemeDialog(QDialog):
    """Save current visibility into a named scheme and optional target book project."""

    def __init__(self, parent, book, auto_match_project_id="", default_project_id=""):
        super().__init__(parent)
        self._book = book or {}
        self._auto_match_id = str(auto_match_project_id or "").strip()
        self.setObjectName("LayersPanelToolsSaveSchemeDialog")
        self.setWindowTitle(tr("保存当前开关方案"))
        self.resize(420, 160)
        layout = QVBoxLayout(self)
        self.lbl_name = QLabel()
        self.scheme_name = QLineEdit()
        self.lbl_project = QLabel()
        self.project_pick = QComboBox()
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.scheme_name)
        layout.addWidget(self.lbl_project)
        layout.addWidget(self.project_pick)
        close_flag = qt_attr(QDialogButtonBox, "Close")
        self.buttons = QDialogButtonBox(qt_attr(QDialogButtonBox, "Ok") | close_flag)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        try:
            self.buttons.button(close_flag).clicked.connect(self.reject)
        except Exception:
            pass  # nosec
        layout.addWidget(self.buttons)
        self._fill_projects(default_project_id)
        self._retranslate()
        subscribe(self, self._retranslate)
        self._listening = True

    def closeEvent(self, event):
        if self._listening:
            self._listening = False
        super().closeEvent(event)

    def _retranslate(self, *_args):
        self.lbl_name.setText(tr("方案名称"))
        self.lbl_project.setText(tr("保存到项目"))
        self.scheme_name.setPlaceholderText(tr("方案名称"))
        localize_button_box(self.buttons)
        apply_direction(self)
        text = self.scheme_name.text()
        pick = self._current_pick_id()
        self._fill_projects(pick, preserve_text=text)

    def _current_pick_id(self):
        data = self.project_pick.currentData()
        if data is None:
            return ""
        return str(data)

    def _fill_projects(self, preferred_id="", preserve_text=None):
        self.project_pick.blockSignals(True)
        self.project_pick.clear()
        projects = sorted(
            self._book.get("projects") or [],
            key=lambda item: (_book_project_label(item).casefold(), item.get("id") or ""),
        )
        auto_label = _project_title()
        if not auto_label.strip():
            auto_label = tr("未保存工程")
        tip = tr("自动匹配当前项目：%s") % auto_label
        self.project_pick.addItem(tip, "")
        chosen = 0
        row = 1
        for project in projects:
            pid = str(project.get("id") or "")
            label = _book_project_label(project) or pid
            self.project_pick.addItem(label, pid)
            if pid and pid == preferred_id:
                chosen = row
            row += 1
        auto_id = str(self._auto_match_id or "").strip()
        if not preferred_id and auto_id:
            idx = self.project_pick.findData(auto_id)
            if idx >= 0:
                chosen = idx
        elif not preferred_id and chosen == 0 and auto_id:
            idx = self.project_pick.findData(auto_id)
            if idx >= 0:
                chosen = idx
        self.project_pick.setCurrentIndex(chosen)
        self.project_pick.blockSignals(False)
        if preserve_text is not None:
            self.scheme_name.setText(preserve_text)

    def values(self):
        name = self.scheme_name.text().strip()
        data = self.project_pick.currentData()
        project_id = ""
        if data is not None and str(data).strip():
            project_id = str(data).strip()
        else:
            project_id = str(self._auto_match_id or "").strip()
        return name, project_id


# 同一次 QGIS 进程里，插件重新启用不再把已记住的图层开关套回去。
# 记在 qgis.utils 上：插件模块被整包重新载入后，这个标记还在。
# 打开工程时的自动套用仍由 readProject 触发。
def _session_ready():
    try:
        import qgis.utils as qutils
    except Exception:
        return False
    return bool(getattr(qutils, "_lpt_switch_session_ready", False))


def _mark_session():
    try:
        import qgis.utils as qutils
    except Exception:
        return
    qutils._lpt_switch_session_ready = True


class SwitchController:
    def __init__(self, iface):
        self.iface = iface
        self.current_id = ""
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.sync)
        self._listening = False
        self._dialog = None
        self._toolbar = make_toolbar_button(
            iface,
            "lpt:switch",
            "LayersPanelToolsSwitch",
            "图层开关",
            "按方案切换当前项目的图层显示",
            load_icon("switch"),
            None,
            menu=self._make_menu(iface.mainWindow()),
            popup="InstantPopup",
        )
        self._plugin = menu_action(
            iface,
            "LayersPanelToolsSwitchMenu",
            "图层开关",
            "按方案切换当前项目的图层显示",
            load_icon("switch"),
            None,
        )
        self._plugin.setMenu(self._make_menu(iface.mainWindow()))
        self._hook()
        if not _session_ready():
            _mark_session()
            self._schedule()

    def toolbar_action(self):
        return self._toolbar

    def plugin_action(self):
        return self._plugin

    def _make_menu(self, parent):
        from qgis.PyQt.QtWidgets import QMenu

        menu = QMenu(parent)
        menu.aboutToShow.connect(lambda menu=menu: self._fill_menu(menu))
        return menu

    def _hook(self):
        if self._listening:
            return
        project = QgsProject.instance()
        project.layersAdded.connect(self._schedule)
        project.layersRemoved.connect(self._schedule)
        reader = getattr(project, "readProject", None)
        if reader is not None:
            try:
                reader.connect(self._schedule)
            except Exception:
                pass  # nosec
        self._listening = True

    def dispose(self):
        self._timer.stop()
        project = QgsProject.instance()
        for signal in (project.layersAdded, project.layersRemoved):
            try:
                signal.disconnect(self._schedule)
            except Exception:
                pass  # nosec
        reader = getattr(project, "readProject", None)
        if reader is not None:
            try:
                reader.disconnect(self._schedule)
            except Exception:
                pass  # nosec
        dialog = self._dialog
        self._dialog = None
        if dialog is not None:
            try:
                dialog.close()
            except RuntimeError:
                pass

    def _schedule(self, *_args):
        self._timer.start(1500)

    def sync(self):
        names = _layer_names()
        book = _load_book()
        projects = book.get("projects") or []
        manual_lock = bool(book.get("manual_lock"))
        lock_id = str(book.get("lock_project_id") or "").strip()
        locked = manual_lock and bool(lock_id) and _find_project(book, lock_id) is not None

        if locked:
            found = lock_id
        else:
            found = match_project(projects, names)

        if found:
            if found != book.get("scratch"):
                book["scratch"] = ""
            project = _find_project(book, found)
            if project is not None and add_layer_names(project, names, _capture()):
                _save_book(book)
            if found != self.current_id:
                self.current_id = found
                self._apply_active(project)
            return

        if locked:
            if not names:
                self.current_id = ""
            elif lock_id != self.current_id:
                self.current_id = lock_id
            return

        scratch = _find_project(book, book.get("scratch"))
        if scratch is not None and names and saved_is_subset(scratch, names):
            if add_layer_names(scratch, names, _capture()):
                _save_book(book)
            self.current_id = scratch.get("id") or ""
            return
        if not names:
            self.current_id = ""
            return
        project = self._create_project(book, names, _capture())
        book.setdefault("projects", []).append(project)
        book["scratch"] = project["id"]
        _save_book(book)
        self.current_id = project["id"]

    def _create_project(self, book, names, states):
        project_id, number = _next_id(book, "p")
        scheme_id, _scheme_number = _next_id(book, "s")
        title = _project_title() or (tr("项目%d") % number)
        return {
            "id": project_id,
            "name": title,
            "layers": list(names),
            "renames": {},
            "schemes": [{"id": scheme_id, "name": tr("方案%d") % 1, "states": states}],
            "active": scheme_id,
        }

    def _apply_active(self, project):
        if project is None:
            return
        scheme = _find_scheme(project, project.get("active")) or (project.get("schemes") or [None])[0]
        if scheme is None:
            return
        # 打开 QGIS、工程对上已有方案时自动套用，不弹「已套用方案」。
        self._apply_scheme(project, scheme, quiet=True)

    def _apply_scheme(self, project, scheme, quiet):
        states = scheme.get("states") or {}
        renames = project.get("renames") or {}
        from .scheme_logic import pair_saved_to_current, resolve_name

        resolved = [(resolve_name(saved_name, renames), state) for saved_name, state in list(states.items())]
        pairs = pair_saved_to_current([name for name, _state in resolved], _layer_names())
        for name, state in resolved:
            _apply_state(pairs.get(name) or name, state)
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            pass  # nosec
        project["active"] = scheme.get("id")
        if not quiet:
            tell(self.iface, tr("图层开关"), tr("已套用方案「%s」。") % (scheme.get("name") or ""))

    def _toggle_selected_categories(self):
        from .scope import legend_is_on, legend_rule_key, legend_selection, set_legend_on

        pairs = legend_selection(self.iface)
        if not pairs:
            report(self.iface.mainWindow(), tr("图层开关"), tr("请先在图层面板里选中一个分类。"), warning=True)
            return
        seen = set()
        changed = 0
        layers = {}
        for layer, legend in pairs:
            key = legend_rule_key(legend)
            try:
                ident = (layer.id(), key or str(id(legend)))
            except Exception:
                continue  # nosec
            if ident in seen:
                continue
            seen.add(ident)
            if set_legend_on(legend, not legend_is_on(legend)):
                changed += 1
                layers[ident[0]] = layer
        for layer in layers.values():
            try:
                layer.triggerRepaint()
            except Exception:
                pass  # nosec
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            pass  # nosec
        if not changed:
            report(self.iface.mainWindow(), tr("图层开关"), tr("请先在图层面板里选中一个分类。"), warning=True)

    def _fill_menu(self, menu):
        menu.clear()
        toggle = menu.addAction(tr("切换选中分类的开关"))
        toggle.triggered.connect(lambda *_args: self._toggle_selected_categories())
        menu.addSeparator()
        book = _load_book()
        if not self.current_id:
            self.sync()
            book = _load_book()
        project = _find_project(book, self.current_id)
        if project is None or not project.get("schemes"):
            empty = menu.addAction(tr("还没有项目"))
            empty.setEnabled(False)
        else:
            group = QActionGroup(menu)
            group.setExclusive(True)
            for scheme in project.get("schemes") or []:
                action = QAction(_scheme_menu_caption(scheme, project), menu)
                action.setCheckable(True)
                action.setChecked(scheme.get("id") == project.get("active"))
                group.addAction(action)
                menu.addAction(action)
                action.triggered.connect(lambda *_args, pid=project.get("id"), sid=scheme.get("id"): self._use(pid, sid))
            menu.addSeparator()
            save = menu.addAction(tr("保存当前开关方案"))
            save.triggered.connect(lambda *_args: self._open_save_dialog())
        menu.addSeparator()
        settings = menu.addAction(tr("设置"))
        settings.triggered.connect(self.open_settings)

    def _open_save_dialog(self):
        if not self.current_id:
            self.sync()
        book = _load_book()
        default_id = self.current_id or ""
        if not default_id and book.get("projects"):
            default_id = (book.get("projects") or [{}])[0].get("id") or ""
        dialog = SaveSchemeDialog(
            self.iface.mainWindow(),
            book,
            auto_match_project_id=self.current_id,
            default_project_id=default_id,
        )
        if not accepted(run_dialog(dialog)):
            return
        name, project_id = dialog.values()
        if not name:
            tell(self.iface, tr("图层开关"), tr("请先填写方案名称。"), warning=True)
            return
        if not project_id:
            tell(self.iface, tr("图层开关"), tr("没有选择有效的项目。"), warning=True)
            return
        book = _load_book()
        project = _find_project(book, project_id)
        if project is None:
            tell(self.iface, tr("图层开关"), tr("没有选择有效的项目。"), warning=True)
            return
        states = _capture()
        for scheme in project.get("schemes") or []:
            if (scheme.get("name") or "").strip() == name:
                if not ask(self.iface.mainWindow(), tr("图层开关"), tr("已有同名方案「%s」，要覆盖吗？") % name):
                    return
                scheme["states"] = states
                project["active"] = scheme.get("id")
                _save_book(book)
                self.current_id = project.get("id") or self.current_id
                self._reload_dialog()
                tell(self.iface, tr("图层开关"), tr("已更新方案「%s」。") % name)
                return
        scheme_id, _number = _next_id(book, "s")
        project.setdefault("schemes", []).append({"id": scheme_id, "name": name, "states": states})
        project["active"] = scheme_id
        _save_book(book)
        self.current_id = project.get("id") or self.current_id
        self._reload_dialog()
        tell(self.iface, tr("图层开关"), tr("已保存方案「%s」。") % name)

    def _reload_dialog(self):
        dialog = self._dialog
        if dialog is None:
            return
        try:
            if dialog.isVisible():
                dialog.reload()
        except RuntimeError:
            self._dialog = None

    def _use(self, project_id, scheme_id):
        book = _load_book()
        project = _find_project(book, project_id)
        scheme = _find_scheme(project, scheme_id) if project else None
        if project is None or scheme is None:
            return
        self.current_id = project_id
        self._apply_scheme(project, scheme, quiet=False)
        _save_book(book)

    def open_settings(self):
        if self._dialog is None:
            self._dialog = SwitchSettings(self, self.iface.mainWindow())
        self._dialog.reload()
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()


class SwitchSettings(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("LayersPanelToolsSwitchSettings")
        self.resize(760, 520)
        self._book = _load_book()
        self._listening = False

        layout = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        lock_row = QHBoxLayout()
        self.lbl_lock = QLabel()
        self.chk_manual_lock = QCheckBox()
        self.combo_lock_project = QComboBox()
        lock_row.addWidget(self.lbl_lock)
        lock_row.addWidget(self.chk_manual_lock)
        lock_row.addWidget(self.combo_lock_project, 1)
        layout.addLayout(lock_row)

        body = QHBoxLayout()
        left = QVBoxLayout()
        self.lbl_projects = QLabel()
        self.projects = QListWidget()
        self.projects.currentRowChanged.connect(lambda *_args: self._show_project())
        self.project_name = QLineEdit()
        self.btn_rename_project = QPushButton()
        self.btn_delete_project = QPushButton()
        self.btn_rename_project.clicked.connect(self._rename_project)
        self.btn_delete_project.clicked.connect(self._delete_project)
        left.addWidget(self.lbl_projects)
        left.addWidget(self.projects, 1)
        left.addWidget(self.project_name)
        left.addWidget(self.btn_rename_project)
        left.addWidget(self.btn_delete_project)
        body.addLayout(left, 1)

        right = QVBoxLayout()
        self.lbl_schemes = QLabel()
        self.schemes = QListWidget()
        self.schemes.currentRowChanged.connect(lambda *_args: self._show_scheme())
        self.scheme_name = QLineEdit()
        scheme_buttons = QHBoxLayout()
        self.btn_rename_scheme = QPushButton()
        self.btn_delete_scheme = QPushButton()
        self.btn_save_scheme = QPushButton()
        self.btn_rename_scheme.clicked.connect(self._rename_scheme)
        self.btn_delete_scheme.clicked.connect(self._delete_scheme)
        self.btn_save_scheme.clicked.connect(self._save_scheme)
        scheme_buttons.addWidget(self.btn_rename_scheme)
        scheme_buttons.addWidget(self.btn_delete_scheme)
        scheme_buttons.addWidget(self.btn_save_scheme)
        self.table = QTableWidget(0, 3)
        self.table.setEditTriggers(qt_attr(QAbstractItemView, "NoEditTriggers"))
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._edit_cell)
        self.table.setSelectionBehavior(qt_attr(QAbstractItemView, "SelectRows"))
        self.table.currentCellChanged.connect(self._use_selected_layer)
        self._filling = False
        rename_row = QHBoxLayout()
        self.lbl_old = QLabel()
        self.old_name = QLineEdit()
        self.lbl_new = QLabel()
        self.new_name = QComboBox()
        self.btn_replace = QPushButton()
        self.btn_replace.clicked.connect(self._replace)
        rename_row.addWidget(self.lbl_old)
        rename_row.addWidget(self.old_name, 1)
        rename_row.addWidget(self.lbl_new)
        rename_row.addWidget(self.new_name, 1)
        rename_row.addWidget(self.btn_replace)
        right.addWidget(self.lbl_schemes)
        right.addWidget(self.schemes, 1)
        right.addWidget(self.scheme_name)
        right.addLayout(scheme_buttons)
        right.addWidget(self.table, 2)
        right.addLayout(rename_row)
        body.addLayout(right, 2)
        layout.addLayout(body, 1)

        close_flag = qt_attr(QDialogButtonBox, "Close")
        self.buttons = QDialogButtonBox(close_flag)
        self.buttons.rejected.connect(self.close)
        try:
            self.buttons.button(close_flag).clicked.connect(self.close)
        except Exception:
            pass  # nosec
        layout.addWidget(self.buttons)
        self.retranslate()
        subscribe(self, self.retranslate)
        self._listening = True
        self.chk_manual_lock.toggled.connect(self._on_manual_lock_changed)
        self.combo_lock_project.currentIndexChanged.connect(self._persist_lock)

    def reload(self):
        self._book = _load_book()
        self._fill_new_names()
        self._fill_lock_controls()
        self._fill_projects()

    def closeEvent(self, event):
        # 对话框是关了再开的同一个对象。这里断开的话，第二次打开「手动指定」不再写回配置。
        super().closeEvent(event)

    def retranslate(self, *_args):
        self.setWindowTitle(tr("图层开关"))
        self.note.setText(
            tr("图层组合和已有项目对得上时，会自动切过去并套用上次的方案。对不上就自动新增项目。")
            + " "
            + tr("双击表格里的开关或分类，可以改勾选。")
        )
        self.lbl_lock.setText(tr("当前项目"))
        self.chk_manual_lock.setText(tr("手动指定"))
        self.lbl_projects.setText(tr("项目"))
        self.lbl_schemes.setText(tr("方案"))
        self.btn_rename_project.setText(tr("改项目名"))
        self.btn_delete_project.setText(tr("删除项目"))
        self.btn_rename_scheme.setText(tr("改方案名"))
        self.btn_delete_scheme.setText(tr("删除方案"))
        self.btn_save_scheme.setText(tr("保存当前为新方案"))
        self.lbl_old.setText(tr("旧名称"))
        self.lbl_new.setText(tr("新名称"))
        self.btn_replace.setText(tr("替换"))
        self.table.setHorizontalHeaderLabels([tr("图层"), tr("开关"), tr("分类")])
        self._fill_new_names()
        self._fill_lock_controls()
        localize_button_box(self.buttons)
        apply_direction(self)
        self._fill_projects()

    def _fill_lock_controls(self):
        book = self._book
        manual = bool(book.get("manual_lock"))
        lock_id = str(book.get("lock_project_id") or "").strip()
        self.chk_manual_lock.blockSignals(True)
        self.combo_lock_project.blockSignals(True)
        self.chk_manual_lock.setChecked(manual)
        self.combo_lock_project.clear()
        self.combo_lock_project.addItem(tr("自动匹配（按图层名称）"), "")
        projects = book.get("projects") or []
        for project in sorted(projects, key=lambda item: (_book_project_label(item).casefold(), item.get("id") or "")):
            pid = project.get("id") or ""
            label = _book_project_label(project) or pid
            self.combo_lock_project.addItem(label, pid)
        chosen = 0
        if lock_id:
            found = self.combo_lock_project.findData(lock_id)
            if found >= 0:
                chosen = found
        self.combo_lock_project.setCurrentIndex(chosen)
        self.combo_lock_project.setEnabled(manual)
        self.chk_manual_lock.blockSignals(False)
        self.combo_lock_project.blockSignals(False)

    def _on_manual_lock_changed(self, checked):
        self.combo_lock_project.setEnabled(bool(checked))
        self._persist_lock()

    def _persist_lock(self):
        if not getattr(self, "_listening", False):
            return
        self._book = _load_book()
        manual = self.chk_manual_lock.isChecked()
        pid = ""
        if manual:
            data = self.combo_lock_project.currentData()
            pid = str(data).strip() if data is not None else ""
            if not pid:
                manual = False
        self._book["manual_lock"] = manual
        self._book["lock_project_id"] = pid if manual else ""
        _save_book(self._book)
        self.controller._schedule()

    def _fill_projects(self):
        selected = ""
        current = self.projects.currentItem()
        if current is not None:
            selected = current.data(user_role()) or ""
        if not selected:
            selected = self.controller.current_id
        self.projects.blockSignals(True)
        self.projects.clear()
        row = 0
        chosen = 0
        for project in self._book.get("projects") or []:
            item = QListWidgetItem(project.get("name") or project.get("id") or "")
            item.setData(user_role(), project.get("id"))
            self.projects.addItem(item)
            if project.get("id") == selected:
                chosen = row
            row += 1
        self.projects.blockSignals(False)
        if self.projects.count():
            self.projects.setCurrentRow(chosen)
        else:
            self._show_project()

    def _current_project(self):
        item = self.projects.currentItem()
        if item is None:
            return None
        return _find_project(self._book, item.data(user_role()))

    def _show_project(self):
        project = self._current_project()
        self.project_name.setText(project.get("name") if project else "")
        self.schemes.blockSignals(True)
        self.schemes.clear()
        if project is not None:
            chosen = 0
            for index, scheme in enumerate(project.get("schemes") or []):
                item = QListWidgetItem(scheme.get("name") or "")
                item.setData(user_role(), scheme.get("id"))
                self.schemes.addItem(item)
                if scheme.get("id") == project.get("active"):
                    chosen = index
            if self.schemes.count():
                self.schemes.setCurrentRow(chosen)
        self.schemes.blockSignals(False)
        self._show_scheme()

    def _current_scheme(self):
        project = self._current_project()
        item = self.schemes.currentItem()
        if project is None or item is None:
            return None
        return _find_scheme(project, item.data(user_role()))

    def _fill_new_names(self):
        chosen = self.new_name.currentText()
        self.new_name.blockSignals(True)
        self.new_name.clear()
        for name in _layer_names():
            self.new_name.addItem(name)
        index = self.new_name.findText(chosen)
        self.new_name.setCurrentIndex(index)
        self.new_name.blockSignals(False)

    def _use_selected_layer(self, row, _column, _previous_row, _previous_column):
        if self._filling or row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        shown = item.text()
        self.old_name.setText(shown)
        from .scheme_logic import best_current_name

        target = best_current_name(shown, [self.new_name.itemText(i) for i in range(self.new_name.count())])
        found = self.new_name.findText(target) if target else -1
        if found >= 0:
            self.new_name.setCurrentIndex(found)

    def _show_scheme(self):
        scheme = self._current_scheme()
        self.scheme_name.setText(scheme.get("name") if scheme else "")
        self._filling = True
        self.table.setRowCount(0)
        states = {} if scheme is None else (scheme.get("states") or {})
        project = self._current_project()
        renames = {} if project is None else (project.get("renames") or {})
        from .scheme_logic import resolve_name

        for name, state in states.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            shown = resolve_name(name, renames)
            name_item = QTableWidgetItem(shown)
            name_item.setData(user_role(), name)
            self.table.setItem(row, 0, name_item)
            flag = tr("开") if state.get("visible") else tr("关")
            self.table.setItem(row, 1, QTableWidgetItem(flag))
            categories = state.get("categories") or []
            if not categories:
                summary = tr("没有分类")
            else:
                on_labels = [item.get("label") or "" for item in categories if item.get("on") and item.get("label")]
                summary = tr("开 %d / 共 %d") % (len(on_labels), len(categories))
                if on_labels:
                    summary = summary + " " + "、".join(on_labels[:6])
            cell = QTableWidgetItem(summary)
            lines = []
            for item in categories:
                mark = tr("开") if item.get("on") else tr("关")
                lines.append("%s %s" % (item.get("label") or "", mark))
            cell.setToolTip("\n".join(lines))
            self.table.setItem(row, 2, cell)
        self._filling = False

    def _edit_cell(self, row, column):
        scheme = self._current_scheme()
        name_item = self.table.item(row, 0)
        if scheme is None or name_item is None:
            return
        key = name_item.data(user_role())
        states = scheme.setdefault("states", {})
        state = states.get(key)
        if not isinstance(state, dict):
            return
        if column == 1:
            state["visible"] = not bool(state.get("visible"))
            _save_book(self._book)
            self._show_scheme()
            return
        if column != 2:
            return
        categories = state.get("categories") or []
        if not categories:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("分类"))
        dialog.resize(360, 420)
        layout = QVBoxLayout(dialog)
        holder = QWidget()
        checks = QVBoxLayout(holder)
        boxes = []
        for item in categories:
            box = QCheckBox(item.get("label") or "")
            box.setChecked(bool(item.get("on")))
            checks.addWidget(box)
            boxes.append(box)
        checks.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(qt_attr(QDialogButtonBox, "Ok") | qt_attr(QDialogButtonBox, "Cancel"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        localize_button_box(buttons)
        if not accepted(run_dialog(dialog)):
            return
        for item, box in zip(categories, boxes):
            item["on"] = box.isChecked()
        _save_book(self._book)
        self._show_scheme()

    def _rename_project(self):
        project = self._current_project()
        name = self.project_name.text().strip()
        if project is None or not name:
            return
        project["name"] = name
        _save_book(self._book)
        self._fill_projects()

    def _delete_project(self):
        project = self._current_project()
        if project is None:
            return
        if not self._ask(tr("确定删除项目「%s」吗？") % (project.get("name") or "")):
            return
        self._book["projects"] = [item for item in self._book.get("projects") or [] if item.get("id") != project.get("id")]
        if self._book.get("scratch") == project.get("id"):
            self._book["scratch"] = ""
        if self.controller.current_id == project.get("id"):
            self.controller.current_id = ""
        _save_book(self._book)
        self._fill_projects()

    def _rename_scheme(self):
        scheme = self._current_scheme()
        name = self.scheme_name.text().strip()
        if scheme is None or not name:
            return
        scheme["name"] = name
        _save_book(self._book)
        self._show_project()

    def _delete_scheme(self):
        project = self._current_project()
        scheme = self._current_scheme()
        if project is None or scheme is None:
            return
        if len(project.get("schemes") or []) <= 1:
            tell(self.controller.iface, tr("图层开关"), tr("至少留一个方案。"), warning=True)
            return
        if not self._ask(tr("确定删除方案「%s」吗？") % (scheme.get("name") or "")):
            return
        project["schemes"] = [item for item in project.get("schemes") or [] if item.get("id") != scheme.get("id")]
        if project.get("active") == scheme.get("id"):
            project["active"] = project["schemes"][0]["id"]
        _save_book(self._book)
        self._show_project()

    def _save_scheme(self):
        project = self._current_project()
        if project is None:
            return
        name = add_scheme(self._book, project)
        _save_book(self._book)
        self._show_project()
        tell(self.controller.iface, tr("图层开关"), tr("已保存方案「%s」。") % name)

    def _replace(self):
        project = self._current_project()
        old = self.old_name.text().strip()
        new = self.new_name.currentText().strip()
        if project is None:
            return
        if not old or not new:
            tell(self.controller.iface, tr("图层开关"), tr("请先填写旧名称和新名称。"), warning=True)
            return
        known = set(project_layer_names(project))
        if old not in known and old not in (project.get("renames") or {}):
            tell(self.controller.iface, tr("图层开关"), tr("没有叫「%s」的图层。") % old, warning=True)
            return
        replace_layer_name(project, old, new)
        _save_book(self._book)
        self.old_name.clear()
        self.new_name.setCurrentIndex(-1)
        self._show_scheme()
        tell(self.controller.iface, tr("图层开关"), tr("已把「%s」换成「%s」。") % (old, new))

    def _ask(self, text):
        return ask(self, tr("图层开关"), text)
