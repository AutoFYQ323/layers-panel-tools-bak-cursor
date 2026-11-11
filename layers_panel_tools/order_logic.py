# -*- coding: utf-8 -*-
"""Toolbar order rules with no Qt dependency, so they can be checked outside QGIS."""

SETTINGS_ID = "lpt:settings"
SEP_PREFIX = "lpt:sep:"
MAX_ROWS = 10
# 首次安装和「恢复默认」时不勾选。默认勾选的按钮不在这张表里：
# 标注、批量选择图层、图层管理、编辑记录、批量导出、按多边形选择、底图切换、图层开关、
# 独显图层、闪烁定位、图层操作、线标注、分类导出。
DEFAULT_HIDDEN = (
    "lpt:organize",
    "lpt:repair",
    "lpt:find",
    "lpt:show_all",
    "lpt:hide_all",
    "lpt:move",
    "lpt:opacity",
    "lpt:style",
    "lpt:rename",
    "lpt:copy_files",
    "lpt:layer_tags",
    "lpt:scale_check",
    "lpt:perf",
)

# 图层面板工具设置里列表顺序：先默认显示的插件按钮，再默认隐藏的，与 tools.extra_actions 一致。
DEFAULT_PLUGIN_ORDER = (
    "lpt:labels",
    "lpt:select",
    "lpt:layer_manager",
    "lpt:edit_timeline",
    "lpt:export",
    "lpt:poly_select",
    "lpt:feature_count",
    "lpt:switch",
    "lpt:basemap",
    "lpt:solo",
    "lpt:flash",
    "lpt:layer_ops",
    "lpt:line_ends",
    "lpt:class_export",
    "lpt:organize",
    "lpt:repair",
    "lpt:find",
    "lpt:show_all",
    "lpt:hide_all",
    "lpt:move",
    "lpt:opacity",
    "lpt:style",
    "lpt:rename",
    "lpt:copy_files",
    "lpt:layer_tags",
    "lpt:scale_check",
    "lpt:perf",
)


def is_separator(button_id):
    return str(button_id).startswith(SEP_PREFIX)


def merge_order(saved_order, current_ids, original_ids):
    """Keep a saved order. Buttons that were not in it are appended in the default order."""
    current = set(current_ids)
    result = []
    seen = set()
    for item in saved_order or []:
        item = str(item)
        if item in seen:
            continue
        if is_separator(item) or item in current:
            result.append(item)
            seen.add(item)
    for item in original_ids:
        if item in seen or item not in current:
            continue
        result.append(item)
        seen.add(item)
    return result


def clean_hidden(hidden, order, pinned=None):
    if pinned is None:
        pinned = (SETTINGS_ID,)
    pinned = set(pinned)
    allowed = set(order)
    result = []
    for item in hidden or []:
        item = str(item)
        if item in result or item not in allowed:
            continue
        if item in pinned or is_separator(item):
            continue
        result.append(item)
    return result


def clean_rows(rows, order):
    """Each button sits on row 1..MAX_ROWS. Missing values stay on row 1."""
    source = rows or {}
    result = {}
    for item in order:
        try:
            number = int(source.get(item, 1))
        except (TypeError, ValueError):
            number = 1
        if number < 1:
            number = 1
        if number > MAX_ROWS:
            number = MAX_ROWS
        result[str(item)] = number
    return result


def clean_titles(titles, order):
    """按钮的自定义标题。子功能（lpt:按钮:功能）跟着保存，即使不在排序表里。"""
    source = titles or {}
    allowed = set(str(item) for item in order)
    result = {}
    for key, value in source.items():
        text = str(value or "").strip()
        if not text:
            continue
        key = str(key)
        is_sub = key.startswith("lpt:") and key.count(":") >= 2 and not is_separator(key)
        if key in allowed or is_sub:
            result[key] = text
    return result


def factory_hidden(order):
    """Buttons that stay off until the user checks them."""
    allowed = set(str(item) for item in order or [])
    return [item for item in DEFAULT_HIDDEN if item in allowed]


def factory_row(button_id):
    """Native QGIS row 1; default-on plugin buttons row 2; default-off plugin row 3."""
    bid = str(button_id)
    if not bid.startswith("lpt:"):
        return 1
    if bid == SETTINGS_ID:
        return 2
    if bid in DEFAULT_HIDDEN:
        return 3
    return 2


def sort_plugin_tools(tool_ids):
    """Put plugin tool ids in DEFAULT_PLUGIN_ORDER; unknown ids keep relative order at end."""
    order_index = {bid: index for index, bid in enumerate(DEFAULT_PLUGIN_ORDER)}
    extras = []
    sorted_known = []
    for bid in tool_ids:
        bid = str(bid)
        if bid in order_index:
            sorted_known.append((order_index[bid], bid))
        else:
            extras.append(bid)
    sorted_known.sort(key=lambda pair: pair[0])
    return [bid for _index, bid in sorted_known] + extras


def hidden_for_load(saved_order, stored_hidden, order):
    """First launch uses the factory set. A button never saved before stays off if it is in that set."""
    if not saved_order:
        return factory_hidden(order)
    hidden = list(stored_hidden or [])
    known = set(str(item) for item in saved_order)
    for item in factory_hidden(order):
        if item not in known and item not in hidden:
            hidden.append(item)
    return hidden


def self_check():
    original = ["a", "b", "c", "s"]
    current = set(original)
    assert merge_order(["c", "a", "s"], current, original) == ["c", "a", "s", "b"]  # nosec
    assert merge_order(["c", "z", "a"], current, original) == ["c", "a", "b", "s"]  # nosec
    assert merge_order([], current, original) == ["a", "b", "c", "s"]  # nosec
    assert merge_order(["c", "b", "a"], current, original) == ["c", "b", "a", "s"]  # nosec
    with_sep = merge_order(["a", "lpt:sep:1", "c"], current, original)
    assert with_sep == ["a", "lpt:sep:1", "c", "b", "s"]  # nosec
    assert clean_hidden(  # nosec
        [SETTINGS_ID, "b", "lpt:sep:1", "missing"],
        ["a", "b", SETTINGS_ID, "lpt:sep:1"],
    ) == ["b"]
    assert clean_rows({"a": 3, "b": 99, "z": 2}, ["a", "b", "s"]) == {"a": 3, "b": MAX_ROWS, "s": 1}  # nosec
    assert clean_rows(None, ["a"]) == {"a": 1}  # nosec
    assert clean_titles({"a": " Custom ", "b": "  ", "z": "x"}, ["a", "b"]) == {"a": "Custom"}  # nosec
    assert clean_titles(
        {"lpt:labels:all_on": "X", "lpt:labels": "Y", "lpt:sep:1": "Z", "native:1": "N"},
        ["lpt:labels"],
    ) == {"lpt:labels:all_on": "X", "lpt:labels": "Y"}  # nosec
    order = ["lpt:labels", "lpt:find", "lpt:settings"]
    assert factory_hidden(order) == ["lpt:find"]  # nosec
    assert hidden_for_load(None, [], order) == ["lpt:find"]  # nosec
    assert hidden_for_load(["lpt:labels"], [], order) == ["lpt:find"]  # nosec
    assert hidden_for_load(["lpt:find", "lpt:labels"], [], order) == []  # nosec
    assert hidden_for_load(["lpt:find"], ["lpt:find"], order) == ["lpt:find"]  # nosec
    assert factory_row("native:1") == 1  # nosec
    assert factory_row("lpt:labels") == 2  # nosec
    assert factory_row("lpt:find") == 3  # nosec
    assert factory_row(SETTINGS_ID) == 2  # nosec
    assert sort_plugin_tools(["lpt:find", "lpt:labels"]) == ["lpt:labels", "lpt:find"]  # nosec
    return True
