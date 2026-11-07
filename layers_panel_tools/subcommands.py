# -*- coding: utf-8 -*-
"""多功能按钮的子功能登记表。

一个按钮带弹出菜单（多种功能）时，子功能在这里登记；
设置窗口可以展开这个按钮，逐项配自定义标题与快捷键。
每个子功能持有一个挂在主窗口上的 QAction，快捷键由它承载，弹出菜单也复用它。
"""

try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .i18n import tr

_registry = {}  # button_id -> [(sub_id, msgid, runner)]
_actions = {}   # sub_id -> QAction


def register(button_id, items):
    """items: [(后缀, 中文句子, runner)]。runner 收到 iface 就能独立运行。

    子功能 id 是「按钮id:后缀」（如 lpt:labels:all_on），与按钮共用
    titles / shortcuts 两个配置键。
    """
    _registry[str(button_id)] = [
        (str(button_id) + ":" + str(suffix), str(msgid), runner)
        for suffix, msgid, runner in items
    ]


def has_subcommands(button_id):
    return bool(_registry.get(str(button_id)))


def subcommands_of(button_id):
    return list(_registry.get(str(button_id)) or ())


def subcommand_of_id(sub_id):
    for items in _registry.values():
        for entry in items:
            if entry[0] == str(sub_id):
                return entry
    return None


def display_title(sub_id, msgid, titles=None):
    """子功能当前显示名：自定义标题优先，否则按界面语言翻译。"""
    if titles is None:
        from .settings_store import load_titles

        titles = load_titles()
    custom = str(titles.get(str(sub_id), "") or "").strip()
    return custom or tr(msgid)


def ensure_actions(iface, button_id=None):
    """为登记过的子功能各建一个 QAction（只建一次）。返回新建的动作列表。"""
    created = []
    targets = [str(button_id)] if button_id else list(_registry.keys())
    for bid in targets:
        for sub_id, msgid, runner in _registry.get(bid) or ():
            if sub_id in _actions:
                continue
            try:
                action = QAction(display_title(sub_id, msgid), iface.mainWindow())
                action.setObjectName("LayersPanelToolsSubAction")
                action.setProperty("lpt_sub_id", sub_id)
                action.setProperty("lpt_msgid", msgid)
                action.setProperty("lpt_parent", bid)
                action.triggered.connect(lambda _checked=False, run=runner: run(iface))
            except Exception:
                continue  # nosec
            _actions[sub_id] = action
            created.append(action)
    return created


def action_of(sub_id):
    return _actions.get(str(sub_id))


def all_actions():
    return list(_actions.values())


def retitle():
    """语言切换或改了标题后，把所有子功能动作的显示名刷一遍。"""
    from .settings_store import load_titles

    titles = load_titles()
    for action in list(_actions.values()):
        try:
            sub_id = str(action.property("lpt_sub_id") or "")
            msgid = str(action.property("lpt_msgid") or "")
            action.setText(display_title(sub_id, msgid, titles))
        except Exception:
            continue  # nosec


def add_to_menu(iface, button_id, menu, sub_id):
    """把子功能的持久动作加进弹出菜单（不存在则先创建）。"""
    ensure_actions(iface, button_id)
    action = action_of(sub_id)
    if action is not None:
        menu.addAction(action)
    return action
