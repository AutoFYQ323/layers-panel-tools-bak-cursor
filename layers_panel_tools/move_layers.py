# -*- coding: utf-8 -*-
"""Move the selected layers or groups without dragging them through a long tree."""

from qgis.core import QgsProject

from .buttons import make_popup_menu_action, make_popup_tool
from .i18n import tr
from .icons import load_icon
from .scope import relocate, select_nodes, selected_nodes, tell


def make_action(iface):
    tr("移动图层")
    tr("把选中的图层或组移到最上、最下、上一层、下一层或移出组")
    return make_popup_tool(
        iface,
        "lpt:move",
        "LayersPanelToolsMove",
        "移动图层",
        "把选中的图层或组移到最上、最下、上一层、下一层或移出组",
        load_icon("move"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsMoveMenu",
        "移动图层",
        "把选中的图层或组移到最上、最下、上一层、下一层或移出组",
        load_icon("move"),
        lambda menu: _fill(iface, menu),
    )


def _fill(iface, menu):
    menu.clear()
    nodes = selected_nodes(iface)
    if not nodes:
        note = menu.addAction(tr("先在图层面板里选中图层或组"))
        note.setEnabled(False)
        return
    inside = any(_parent(node) is not None and _parent(node).parent() is not None for node in nodes)
    for suffix in ("top", "up", "down", "bottom"):
        subcommands.add_to_menu(iface, "lpt:move", menu, "lpt:move:" + suffix)
    menu.addSeparator()
    action = subcommands.add_to_menu(iface, "lpt:move", menu, "lpt:move:out")
    if action is not None:
        action.setEnabled(inside)
    subcommands.add_to_menu(iface, "lpt:move", menu, "lpt:move:root_top")
    subcommands.add_to_menu(iface, "lpt:move", menu, "lpt:move:root_bottom")


def _parent(node):
    try:
        return node.parent()
    except Exception:
        return None


def _position(parent, node):
    for index, child in enumerate(list(parent.children())):
        if child == node:
            return index
    return -1


def _by_parent(nodes):
    groups = []
    for node in nodes:
        parent = _parent(node)
        if parent is None:
            continue
        for entry in groups:
            if entry[0] == parent:
                entry[1].append(node)
                break
        else:
            groups.append((parent, [node]))
    return groups


def _reorder(parent, nodes, mode):
    """Only the chosen nodes are cloned, so no other node in the tree is replaced."""
    picked = [node for node in nodes if _position(parent, node) >= 0]
    picked.sort(key=lambda node: _position(parent, node))
    count = len(list(parent.children()))
    placed = []
    changed = False
    if mode == "top":
        for offset, node in enumerate(picked):
            if _position(parent, node) == offset:
                placed.append(node)
                continue
            placed.append(relocate(node, parent, offset))
            changed = True
    elif mode == "bottom":
        tail = list(range(count - len(picked), count))
        if [_position(parent, node) for node in picked] == tail:
            return picked, False
        for node in picked:
            placed.append(relocate(node, parent, count))
        changed = True
    elif mode == "up":
        settled = -1
        for node in picked:
            position = _position(parent, node)
            if position - 1 > settled:
                placed.append(relocate(node, parent, position - 1))
                settled = position - 1
                changed = True
            else:
                placed.append(node)
                settled = position
    elif mode == "down":
        settled = count
        moved = []
        for node in reversed(picked):
            position = _position(parent, node)
            if position + 1 < settled:
                moved.append(relocate(node, parent, position + 2))
                settled = position + 1
                changed = True
            else:
                moved.append(node)
                settled = position
        placed = list(reversed(moved))
    return placed, changed


def _move_out(nodes):
    placed = []
    for parent, members in _by_parent(nodes):
        grand = _parent(parent)
        if grand is None:
            placed.extend(members)
            continue
        base = _position(grand, parent) + 1
        for offset, node in enumerate(members):
            placed.append(relocate(node, grand, base + offset))
    return placed


def _move_root(nodes, at_top):
    root = QgsProject.instance().layerTreeRoot()
    placed = []
    for offset, node in enumerate(nodes):
        if _parent(node) is None:
            continue
        index = offset if at_top else len(list(root.children()))
        placed.append(relocate(node, root, index))
    return placed


def _run(iface, mode):
    nodes = selected_nodes(iface)
    if not nodes:
        tell(iface, tr("移动图层"), tr("先在图层面板里选中图层或组"), warning=True)
        return
    if mode == "out":
        if not any(_parent(node) is not None and _parent(node).parent() is not None for node in nodes):
            tell(iface, tr("移动图层"), tr("选中的已经在最外层了。"))
            return
        placed = _move_out(nodes)
    elif mode in ("root_top", "root_bottom"):
        placed = _move_root(nodes, mode == "root_top")
    else:
        placed = []
        changed = False
        for parent, members in _by_parent(nodes):
            moved, did = _reorder(parent, members, mode)
            placed.extend(moved)
            changed = changed or did
        if not changed:
            tell(iface, tr("移动图层"), tr("已经到头了，没有可移动的位置。"))
    if placed:
        select_nodes(iface, placed)


from . import subcommands

tr("移到本组最上")
tr("上移一层")
tr("下移一层")
tr("移到本组最下")
tr("移出所在组")
tr("移到整个工程最上")
tr("移到整个工程最下")
subcommands.register("lpt:move", [
    ("top", "移到本组最上", lambda iface: _run(iface, "top")),
    ("up", "上移一层", lambda iface: _run(iface, "up")),
    ("down", "下移一层", lambda iface: _run(iface, "down")),
    ("bottom", "移到本组最下", lambda iface: _run(iface, "bottom")),
    ("out", "移出所在组", lambda iface: _run(iface, "out")),
    ("root_top", "移到整个工程最上", lambda iface: _run(iface, "root_top")),
    ("root_bottom", "移到整个工程最下", lambda iface: _run(iface, "root_bottom")),
])