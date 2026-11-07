# -*- coding: utf-8 -*-
"""Layers panel toolbar buttons, with one settings button for show, hide, and order."""

from qgis.PyQt.QtGui import QIcon
from qgis.core import Qgis, QgsApplication, QgsMessageLog

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .basemap_switch import close_basemap, make_menu_action as basemap_menu_action
from . import button_help  # noqa: F401 — register help strings for i18n
from . import subcommands
from .check_i18n import audit_errors
from .edit_timeline import close_timeline, ensure_listening, make_menu_action as edit_timeline_menu_action
from .export_layers import close_export, make_menu_action as export_menu_action
from .feature_count_toggle import make_menu_action as feature_count_menu_action
from .find_layer import close_find
from .find_layer import make_menu_action as find_menu_action
from .flash_locate import make_menu_action as flash_menu_action
from .flash_locate import stop_flash
from .i18n import language_changed, tr
from .label_toggle import make_menu_action as label_menu_action
from .layer_color_tags import make_menu_action as layer_tags_menu_action
from .layer_manager import close_layer_manager, make_menu_action as layer_manager_menu_action
from .move_layers import make_menu_action as move_menu_action
from .opacity_tool import close_opacity
from .opacity_tool import make_menu_action as opacity_menu_action
from .order_logic import SETTINGS_ID
from .organize import close_organize, make_menu_action
from .perf_check import close_perf, make_menu_action as perf_menu_action
from .poly_select import close_poly_select, make_menu_action as poly_select_menu_action
from .rename_layers import close_rename, make_menu_action as rename_menu_action
from .scale_check import close_scale_check, make_menu_action as scale_check_menu_action
from .select_layers import make_menu_action as select_menu_action
from .settings_dialog import SettingsDialog
from .solo_layers import make_menu_action as solo_menu_action
from .solo_layers import reset_solo
from .source_repair import close_repair
from .source_repair import make_menu_action as repair_menu_action
from .split_by_field import close_split, make_menu_action as split_field_menu_action
from .copy_layer_files import make_menu_action as copy_files_menu_action
from .style_copy import make_menu_action as style_menu_action
from .switchboard import close_switch
from .switchboard import make_menu_action as switch_menu_action
from .toolbar_host import ToolbarHost, plain_title
from .visibility_all import make_menu_action_hide as hide_all_menu_action, make_menu_action_show as show_all_menu_action

_LOG = "LayersPanelTools"


def _settings_icon():
    for path in ("/mActionOptions.svg", "/mIconProperties.svg"):
        icon = QgsApplication.getThemeIcon(path)
        if icon is not None and not icon.isNull():
            return icon
    return QIcon()


class LayersPanelToolsPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.menu_actions = []
        self.host = None
        self.menu_title = ""
        self.dialog = None
        self._warned_fallback = False
        self._shortcut_actions = {}

    def initGui(self):
        self._audit()
        try:
            ensure_listening()
        except Exception:
            pass  # nosec
        self.action = QAction(_settings_icon(), tr("图层面板工具设置"), self.iface.mainWindow())
        self.action.setObjectName("LayersPanelToolsSettings")
        self.action.setProperty("lpt_id", SETTINGS_ID)
        self.action.setProperty("lpt_msgid", "图层面板工具设置")
        self.action.setProperty("lpt_tip_msgid", "显示、隐藏和排列图层面板上的按钮，并可改按钮名字。")
        self.action.setToolTip(tr("图层面板工具设置"))
        self.action.triggered.connect(self.open_settings)
        self.menu_actions = [
            make_menu_action(self.iface),
            repair_menu_action(self.iface),
            find_menu_action(self.iface),
            layer_manager_menu_action(self.iface),
            show_all_menu_action(self.iface),
            hide_all_menu_action(self.iface),
            edit_timeline_menu_action(self.iface),
            export_menu_action(self.iface),
            poly_select_menu_action(self.iface),
            select_menu_action(self.iface),
            feature_count_menu_action(self.iface),
            move_menu_action(self.iface),
            opacity_menu_action(self.iface),
            label_menu_action(self.iface),
            switch_menu_action(self.iface),
            basemap_menu_action(self.iface),
            style_menu_action(self.iface),
            copy_files_menu_action(self.iface),
            split_field_menu_action(self.iface),
            layer_tags_menu_action(self.iface),
            solo_menu_action(self.iface),
            rename_menu_action(self.iface),
            flash_menu_action(self.iface),
            scale_check_menu_action(self.iface),
            perf_menu_action(self.iface),
        ]
        self._mount_menu()
        language_changed().connect(self._on_language)
        self.host = ToolbarHost(self.iface, self.action)
        try:
            attached = self.host.attach()
        except Exception as exc:
            QgsMessageLog.logMessage("attach failed: %s" % exc, _LOG, Qgis.Critical)
            attached = False
        subcommands.ensure_actions(self.iface)
        self._apply_shortcuts()
        if attached and self.host.fallbacks and not self._warned_fallback:
            self._warned_fallback = True
            QgsMessageLog.logMessage(
                tr("图层面板上有按钮没对上已知图标，已按它自己的提示文字记住。打开设置可以核对。"),
                _LOG,
                Qgis.Warning,
            )

    def unload(self):
        self._drop_shortcut_actions()
        try:
            language_changed().disconnect(self._on_language)
        except Exception:
            pass  # nosec
        dialog = self.dialog
        self.dialog = None
        if dialog is not None:
            try:
                dialog.close()
            except RuntimeError:
                pass
        close_organize()
        close_repair()
        close_opacity()
        close_switch()
        close_find()
        close_layer_manager()
        close_timeline()
        close_export()
        close_poly_select()
        close_basemap()
        close_split()
        close_rename()
        close_scale_check()
        close_perf()
        try:
            stop_flash()
        except Exception:
            pass  # nosec
        try:
            reset_solo()
        except Exception:
            pass  # nosec
        self._remove_menu()
        host = self.host
        self.host = None
        if host is not None:
            try:
                host.detach()
            except Exception as exc:
                QgsMessageLog.logMessage("detach failed: %s" % exc, _LOG, Qgis.Warning)
        if self.action is not None:
            try:
                self.action.deleteLater()
            except RuntimeError:
                pass
        self.action = None
        for action in list(self.menu_actions):
            try:
                action.deleteLater()
            except RuntimeError:
                pass
        self.menu_actions = []

    def open_settings(self):
        if self.host is None:
            return
        if not self.host.attached:
            try:
                self.host.attach()
            except Exception as exc:
                QgsMessageLog.logMessage("attach failed: %s" % exc, _LOG, Qgis.Critical)
        if not self.host.attached:
            QgsMessageLog.logMessage(tr("没有找到图层面板的工具条。"), _LOG, Qgis.Warning)
            return
        dialog = SettingsDialog(
            self.host.current_rows(),
            self.host.default_rows(),
            self.iface.mainWindow(),
        )
        self.dialog = dialog
        try:
            accepted = dialog.exec_dialog()
            if accepted:
                order, hidden, rows, titles, shortcuts = dialog.result_order()
                self.host.apply_saved(order, hidden, rows, titles, shortcuts)
                self._apply_shortcuts(shortcuts, warn=True)
        finally:
            self.dialog = None

    def _apply_shortcuts(self, shortcuts=None, warn=False):
        """把设置里的快捷键挂到主窗口能收到的动作上。

        工具条按钮是 QWidgetAction，快捷键不会变成按钮点击。
        子功能动作原先只在弹出菜单打开时才挂上，按键到不了它。
        这里为每一条单独建一个挂在主窗口上的动作，窗口有焦点时响应，不是系统全局。
        """
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QKeySequence
        from qgis.PyQt.QtWidgets import QWidgetAction

        from . import settings_store
        from .buttons import shortcut_holder
        from .qt_compat import qt_attr

        if shortcuts is None:
            shortcuts = settings_store.load_shortcuts()
        window = None
        try:
            window = self.iface.mainWindow()
        except Exception:
            window = None
        if window is None:
            return
        context = qt_attr(Qt, "WindowShortcut")
        wanted = {}
        for key, text in (shortcuts or {}).items():
            text = str(text or "").strip()
            if text:
                wanted[str(key)] = text
        targets = self._shortcut_targets()
        blocked = []
        for target_id, source in targets.items():
            text = wanted.get(target_id, "")
            holder = shortcut_holder(text, target_id) if text else ""
            sequence = QKeySequence.fromString(text) if text and not holder else QKeySequence()
            if text and holder:
                blocked.append("%s（%s）" % (text, holder))
            if isinstance(source, QWidgetAction):
                # 工具条上的 QWidgetAction 收到快捷键也不会去点那个按钮，所以快捷键只放在载体上。
                try:
                    source.setShortcut(QKeySequence())
                except Exception:
                    pass  # nosec
                carrier = self._shortcut_actions.get(target_id)
                if carrier is None:
                    carrier = QAction(window)
                    carrier.setObjectName("LayersPanelToolsShortcut")
                    carrier.setProperty("lpt_shortcut_id", target_id)
                    carrier.setShortcutContext(context)
                    carrier.triggered.connect(lambda _checked=False, src=source: self._fire_shortcut(src))
                    window.addAction(carrier)
                    self._shortcut_actions[target_id] = carrier
                try:
                    carrier.setText(plain_title(source.text() or "") or target_id)
                    carrier.setShortcut(sequence)
                except Exception:
                    pass  # nosec
                continue
            stale = self._shortcut_actions.pop(target_id, None)
            if stale is not None:
                try:
                    window.removeAction(stale)
                    stale.deleteLater()
                except Exception:
                    pass  # nosec
            try:
                if source not in window.actions():
                    window.addAction(source)
                source.setShortcutContext(context)
                source.setShortcut(sequence)
            except Exception:
                pass  # nosec
        if warn and blocked:
            from .buttons import report

            report(
                window,
                tr("快捷键"),
                tr("这些快捷键已被 QGIS 的其它功能占用：%s") % "、".join(blocked),
                warning=True,
            )

    def _shortcut_targets(self):
        """可配快捷键的按钮和子功能 → 真正要触发的动作。"""
        from .order_logic import SETTINGS_ID

        found = {}
        host = self.host
        if host is not None:
            for button_id, action in list(getattr(host, "by_id", {}).items()):
                token = str(button_id)
                if token.startswith("lpt:") or token == SETTINGS_ID:
                    found[token] = action
        if self.action is not None and SETTINGS_ID not in found:
            found[SETTINGS_ID] = self.action
        for action in subcommands.all_actions():
            try:
                sub_id = str(action.property("lpt_sub_id") or "")
            except Exception:
                sub_id = ""
            if sub_id:
                found[sub_id] = action
        return found

    def _fire_shortcut(self, source):
        """载体动作被按下：弹出菜单的按钮打开菜单，其余直接执行。"""
        widget = None
        getter = getattr(source, "defaultWidget", None)
        if callable(getter):
            try:
                widget = getter()
            except RuntimeError:
                widget = None
        if widget is not None:
            menu = None
            try:
                menu = widget.menu()
            except Exception:
                menu = None
            if menu is not None:
                try:
                    widget.showMenu()
                    return
                except Exception:
                    pass  # nosec
            try:
                widget.click()
                return
            except Exception:
                pass  # nosec
        try:
            source.trigger()
        except Exception:
            pass  # nosec

    def _drop_shortcut_actions(self):
        window = None
        try:
            window = self.iface.mainWindow()
        except Exception:
            window = None
        for action in list(getattr(self, "_shortcut_actions", {}).values()):
            if window is not None:
                try:
                    window.removeAction(action)
                except Exception:
                    pass  # nosec
            try:
                action.deleteLater()
            except RuntimeError:
                pass
        self._shortcut_actions = {}

    def _audit(self):
        errors = audit_errors()
        if not errors:
            return
        for line in errors:
            QgsMessageLog.logMessage(line, _LOG, Qgis.Warning)
        QgsMessageLog.logMessage(
            tr("有语言只翻译了一部分，语言列表里不会出现它。详情在日志面板的 LayersPanelTools。"),
            _LOG,
            Qgis.Warning,
        )

    def _on_language(self, *_args):
        self._retitle(self.action)
        for action in list(self.menu_actions):
            self._retitle(action)
        if self.host is not None:
            for action in list(self.host.owned):
                self._retitle(action)
            self.host.refresh_tips()
        subcommands.retitle()
        self._mount_menu()

    def _retitle(self, action):
        if action is None:
            return
        msgid = str(action.property("lpt_msgid") or "")
        tip_id = str(action.property("lpt_tip_msgid") or "")
        text = tr(msgid) if msgid else ""
        tip = ""
        custom = ""
        if action.property("lpt_id"):
            custom = str(action.property("lpt_custom_tip") or "").strip()
            tip = custom or text
        elif not action.property("lpt_tip_live"):
            if tip_id:
                tip = tr(tip_id)
            elif msgid:
                tip = text
        if text:
            action.setText(custom or text)
        if tip:
            action.setToolTip(tip)
        getter = getattr(action, "defaultWidget", None)
        if not callable(getter):
            return
        try:
            widget = getter()
        except Exception:
            return
        if widget is None:
            return
        try:
            if hasattr(widget, "setToolButtonStyle"):
                widget.setText("")
            elif text and hasattr(widget, "setText"):
                widget.setText(text)
            if tip and hasattr(widget, "setToolTip"):
                widget.setToolTip(tip)
        except RuntimeError:
            pass

    def _mount_menu(self):
        self._remove_menu()
        self.menu_title = tr("图层面板工具")
        for action in self.menu_actions:
            if action is not None:
                self.iface.addPluginToMenu(self.menu_title, action)
        self.iface.addPluginToMenu(self.menu_title, self.action)

    def _remove_menu(self):
        if not self.menu_title:
            return
        for action in list(self.menu_actions):
            try:
                self.iface.removePluginMenu(self.menu_title, action)
            except Exception:
                pass  # nosec
        if self.action is not None:
            try:
                self.iface.removePluginMenu(self.menu_title, self.action)
            except Exception:
                pass  # nosec
        self.menu_title = ""
