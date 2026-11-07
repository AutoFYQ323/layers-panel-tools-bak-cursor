# -*- coding: utf-8 -*-
"""Long help text for each toolbar control (settings list tooltip and help dialog)."""

import html

from .i18n import tr
from .order_logic import SETTINGS_ID, is_separator

tr(
    "勾选要在图层面板工具条上显示的按钮，拖动调整顺序，"
    "选择放在第几行，可写自定义标题。恢复默认会回到推荐的显示、顺序与行号。"
)
tr(
    "点图标打开菜单，可一次打开或关闭全部图层、已选图层的标注，"
    "或切换已选图层的标注开关。"
)
tr(
    "点图标打开菜单。「全图居中」缩放到点/线/面矢量范围（不含底图）。"
    "「选中地图可见图层」「全选」「反选」等同栏：按当前地图视口或全部开关图层。"
    "点/线/面/栅格等项只打开符合类型的图层开关，其余关闭。所有开关操作都不动底图。"
)
tr(
    "打开表格管理工程图层。点「显示」「标注」列切换开关；"
    "可筛选、改透明度（可滚轮）、跳转符号化/标注/字段/属性，以及复制粘贴样式。"
)
tr("查看本次打开工程以来的操作记录，可按条或按图层回退（仅内存，换工程会清空）。")
tr("勾选多个矢量图层，选文件夹与格式，按图层名各导出一份。")
tr(
    "在地图上画多边形，对多个图层选中/复制/移动/删除范围内要素，"
    "或把选中结果批量导出到文件夹。"
)
tr("控制图层面板图层名旁是否显示要素个数，可作用于全部或已选矢量图层。")
tr("按方案记住各图层及分类的开关状态，可套用、保存、管理多套方案。")
tr("用预设一键显示某套栅格底图并隐藏其它预设底图，可管理预设列表。")
tr(
    "点图标打开菜单，可按名称/几何/目录/要素数/坐标系等排序或分组，"
    "导出图层清单 CSV，保存与恢复快照开关，删除空组，或打开整理窗口细调。"
)
tr("列出图层路径，批量替换、按目录匹配文件或逐行指定新数据源后写回。")
tr(
    "搜索框旁可勾选「含字段」以匹配字段名和属性值；"
    "类型按钮可只看点/线/面/表/栅格；文字支持 * 和 ? 通配符。"
    "回车定位，可一次选中所有匹配项。"
)
tr("把所选或全部图层的本地数据文件（连同同名辅助文件）复制到所选文件夹。")
tr("按矢量字段的不同值各建一个子集图层，可预览、可放进新组、可沿用原符号。")
tr("给图层打颜色标签（面板显示彩色小图标），可按颜色只开这些图层。")
tr("一键只显示所选图层并记住其它图层的状态；再点一次全部还原。")
tr("查找替换（可正则）、前后缀、序号、大小写批量改图层名，实时预览后应用。")
tr(
    "两种闪烁方式——自动开关所选图层的开关（影像对比，停止还原），"
    "或让要素在地图上反复闪亮（快速看到画在哪）；可调间隔，一键停止。"
)
tr(
    "列出开关开着、却被比例尺可见范围挡住的图层；"
    "双击行可跳到该图层可见的比例尺，也可一键关掉这些图层。"
)
tr("按当前视图逐层单独渲染并计时，按耗时列出图层，找出拖慢工程的元凶。")
tr("打开工程里全部图层的开关（底图不动）。")
tr("关闭工程里全部图层的开关（底图不动）。")
tr("在图层面板里移动已选图层或组的位置（组内上下、移出组、工程顶底等）。")
tr("打开滑块窗口，调节全部图层或已选图层的整体不透明度。")
tr("复制当前图层样式，粘贴到已选图层（全部、仅符号或仅标注）。")
tr("图层面板自带按钮，功能与 QGIS 默认一致，详见 QGIS 帮助文档。")

_BUTTON_SETTINGS = (
    "勾选要在图层面板工具条上显示的按钮，拖动调整顺序，"
    "选择放在第几行，可写自定义标题。恢复默认会回到推荐的显示、顺序与行号。"
)
_BUTTON_LABELS = (
    "点图标打开菜单，可一次打开或关闭全部图层、已选图层的标注，"
    "或切换已选图层的标注开关。"
)
_BUTTON_SELECT = (
    "点图标打开菜单。「全图居中」缩放到点/线/面矢量范围（不含底图）。"
    "「选中地图可见图层」「全选」「反选」等同栏：按当前地图视口或全部开关图层。"
    "点/线/面/栅格等项只打开符合类型的图层开关，其余关闭。所有开关操作都不动底图。"
)
_BUTTON_MANAGER = (
    "打开表格管理工程图层。点「显示」「标注」列切换开关；"
    "可筛选、改透明度（可滚轮）、跳转符号化/标注/字段/属性，以及复制粘贴样式。"
)
_BUTTON_TIMELINE = "查看本次打开工程以来的操作记录，可按条或按图层回退（仅内存，换工程会清空）。"
_BUTTON_EXPORT = "勾选多个矢量图层，选文件夹与格式，按图层名各导出一份。"
_BUTTON_POLY = (
    "在地图上画多边形，对多个图层选中/复制/移动/删除范围内要素，"
    "或把选中结果批量导出到文件夹。"
)
_BUTTON_FEATURE_COUNT = "控制图层面板图层名旁是否显示要素个数，可作用于全部或已选矢量图层。"
_BUTTON_SWITCH = "按方案记住各图层及分类的开关状态，可套用、保存、管理多套方案。"
_BUTTON_BASEMAP = "用预设一键显示某套栅格底图并隐藏其它预设底图，可管理预设列表。"
_BUTTON_ORGANIZE = (
    "点图标打开菜单，可按名称/几何/目录/要素数/坐标系等排序或分组，"
    "导出图层清单 CSV，保存与恢复快照开关，删除空组，或打开整理窗口细调。"
)
_BUTTON_REPAIR = "列出图层路径，批量替换、按目录匹配文件或逐行指定新数据源后写回。"
_BUTTON_FIND = (
    "搜索框旁可勾选「含字段」以匹配字段名和属性值；"
    "类型按钮可只看点/线/面/表/栅格；文字支持 * 和 ? 通配符。"
    "回车定位，可一次选中所有匹配项。"
)
_BUTTON_COPY_FILES = "把所选或全部图层的本地数据文件（连同同名辅助文件）复制到所选文件夹。"
_BUTTON_SPLIT_FIELD = "按矢量字段的不同值各建一个子集图层，可预览、可放进新组、可沿用原符号。"
_BUTTON_LAYER_TAGS = "给图层打颜色标签（面板显示彩色小图标），可按颜色只开这些图层。"
_BUTTON_SOLO = "一键只显示所选图层并记住其它图层的状态；再点一次全部还原。"
_BUTTON_RENAME = "查找替换（可正则）、前后缀、序号、大小写批量改图层名，实时预览后应用。"
_BUTTON_FLASH = (
    "两种闪烁方式——自动开关所选图层的开关（影像对比，停止还原），"
    "或让要素在地图上反复闪亮（快速看到画在哪）；可调间隔，一键停止。"
)
_BUTTON_SCALE_CHECK = (
    "列出开关开着、却被比例尺可见范围挡住的图层；"
    "双击行可跳到该图层可见的比例尺，也可一键关掉这些图层。"
)
_BUTTON_PERF = "按当前视图逐层单独渲染并计时，按耗时列出图层，找出拖慢工程的元凶。"
_BUTTON_SHOW = "打开工程里全部图层的开关（底图不动）。"
_BUTTON_HIDE = "关闭工程里全部图层的开关（底图不动）。"
_BUTTON_MOVE = "在图层面板里移动已选图层或组的位置（组内上下、移出组、工程顶底等）。"
_BUTTON_OPACITY = "打开滑块窗口，调节全部图层或已选图层的整体不透明度。"
_BUTTON_STYLE = "复制当前图层样式，粘贴到已选图层（全部、仅符号或仅标注）。"
_NATIVE_HELP = "图层面板自带按钮，功能与 QGIS 默认一致，详见 QGIS 帮助文档。"

BUTTON_HELP = {
    SETTINGS_ID: _BUTTON_SETTINGS,
    "lpt:labels": _BUTTON_LABELS,
    "lpt:select": _BUTTON_SELECT,
    "lpt:layer_manager": _BUTTON_MANAGER,
    "lpt:edit_timeline": _BUTTON_TIMELINE,
    "lpt:export": _BUTTON_EXPORT,
    "lpt:poly_select": _BUTTON_POLY,
    "lpt:feature_count": _BUTTON_FEATURE_COUNT,
    "lpt:switch": _BUTTON_SWITCH,
    "lpt:basemap": _BUTTON_BASEMAP,
    "lpt:organize": _BUTTON_ORGANIZE,
    "lpt:repair": _BUTTON_REPAIR,
    "lpt:find": _BUTTON_FIND,
    "lpt:show_all": _BUTTON_SHOW,
    "lpt:hide_all": _BUTTON_HIDE,
    "lpt:move": _BUTTON_MOVE,
    "lpt:opacity": _BUTTON_OPACITY,
    "lpt:style": _BUTTON_STYLE,
    "lpt:copy_files": _BUTTON_COPY_FILES,
    "lpt:split_field": _BUTTON_SPLIT_FIELD,
    "lpt:layer_tags": _BUTTON_LAYER_TAGS,
    "lpt:solo": _BUTTON_SOLO,
    "lpt:rename": _BUTTON_RENAME,
    "lpt:flash": _BUTTON_FLASH,
    "lpt:scale_check": _BUTTON_SCALE_CHECK,
    "lpt:perf": _BUTTON_PERF,
}


def help_msgid_for(button_id):
    bid = str(button_id or "")
    if bid in BUTTON_HELP:
        return BUTTON_HELP[bid]
    if is_separator(bid):
        return "在工具条上把相邻按钮隔开。"
    if bid.startswith("lpt:"):
        return ""
    if bid == SETTINGS_ID:
        return _BUTTON_SETTINGS
    return _NATIVE_HELP


def _esc(text):
    return html.escape(str(text or ""), quote=False)


def hover_tip(button_id, msgid, tip_msgid="", custom=""):
    """悬停提示（富文本）：加粗大一号标题 + 一句话说明 + 空行 + 功能说明及使用技巧。

    自定义标题优先；没有长说明的按钮（未知 lpt: id、原生按钮）只显示标题和短说明。
    """
    title = str(custom or "").strip() or tr(msgid or "")
    if not title:
        return ""
    parts = ["<b><span style=\"font-size:large\">%s</span></b>" % _esc(title)]
    short = tr(tip_msgid) if tip_msgid else ""
    if short and short != title:
        parts.append(_esc(short))
    help_id = ""
    bid = str(button_id or "")
    if bid.startswith("lpt:") and bid != SETTINGS_ID and not is_separator(bid):
        help_id = help_msgid_for(bid)
    if help_id:
        parts.append("")
        parts.append(_esc(tr(help_id)))
    return "<br>".join(parts)


def title_tip(title, body=""):
    """设置列表悬停用（富文本）：加粗大一号标题 + 空行 + 说明正文。"""
    title = str(title or "")
    body = str(body or "")
    head = "<b><span style=\"font-size:large\">%s</span></b>" % _esc(title)
    if not body:
        return head
    return "%s<br><br>%s" % (head, _esc(body))
