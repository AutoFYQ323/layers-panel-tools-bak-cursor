# -*- coding: utf-8 -*-
"""Buttons added on the Layers panel toolbar."""

from .basemap_switch import make_action as basemap_action
from .edit_timeline import make_action as edit_timeline_action
from .export_layers import make_action as export_action
from .feature_count_toggle import make_action as feature_count_action
from .find_layer import make_action as find_action
from .flash_locate import make_action as flash_action
from .label_toggle import make_action as label_action
from .layer_color_tags import make_action as layer_tags_action
from .layer_manager import make_action as layer_manager_action
from .move_layers import make_action as move_action
from .opacity_tool import make_action as opacity_action
from .organize import make_action as organize_action
from .perf_check import make_action as perf_action
from .poly_select import make_action as poly_select_action
from .rename_layers import make_action as rename_action
from .scale_check import make_action as scale_check_action
from .select_layers import make_action as select_action
from .solo_layers import make_action as solo_action
from .source_repair import make_action as repair_action
from .style_copy import make_action as style_action
from .switchboard import make_action as switch_action
from .visibility_all import make_action_hide as hide_all_action, make_action_show as show_all_action
from .copy_layer_files import make_action as copy_files_action
from .layer_ops import make_action as layer_ops_action
from .line_ends import make_action as line_ends_action
from .class_export import make_action as class_export_action


def extra_actions(iface):
    # 顺序与 order_logic.DEFAULT_PLUGIN_ORDER 一致：默认显示在前，默认隐藏在后。
    return [
        label_action(iface),
        select_action(iface),
        layer_manager_action(iface),
        edit_timeline_action(iface),
        export_action(iface),
        poly_select_action(iface),
        feature_count_action(iface),
        switch_action(iface),
        basemap_action(iface),
        solo_action(iface),
        flash_action(iface),
        layer_ops_action(iface),
        line_ends_action(iface),
        class_export_action(iface),
        organize_action(iface),
        repair_action(iface),
        find_action(iface),
        show_all_action(iface),
        hide_all_action(iface),
        move_action(iface),
        opacity_action(iface),
        style_action(iface),
        rename_action(iface),
        copy_files_action(iface),
        layer_tags_action(iface),
        scale_check_action(iface),
        perf_action(iface),
    ]
