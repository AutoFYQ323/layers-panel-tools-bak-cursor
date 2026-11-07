# -*- coding: utf-8 -*-
"""Copy on-disk layer source files (plus same-name sidecars) into a chosen folder."""

import os
import shutil

from qgis.PyQt.QtWidgets import QFileDialog

from qgis.core import QgsProject

from .buttons import make_popup_menu_action, make_popup_tool, report
from .file_logic import is_sidecar, unique_name
from .i18n import tr
from .icons import load_icon
from .scope import layer_file_path, selected_layers


def make_action(iface):
    tr("复制图层文件")
    tr("把图层的本地数据文件和同名辅助文件复制到所选文件夹")
    return make_popup_tool(
        iface,
        "lpt:copy_files",
        "LayersPanelToolsCopyFiles",
        "复制图层文件",
        "把图层的本地数据文件和同名辅助文件复制到所选文件夹",
        load_icon("copy_files"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsCopyFilesMenu",
        "复制图层文件",
        "把图层的本地数据文件和同名辅助文件复制到所选文件夹",
        load_icon("copy_files"),
        lambda menu: _fill(iface, menu),
    )


def _fill(iface, menu):
    menu.clear()
    subcommands.add_to_menu(iface, "lpt:copy_files", menu, "lpt:copy_files:selected")
    subcommands.add_to_menu(iface, "lpt:copy_files", menu, "lpt:copy_files:all")


def _copy_one(path, folder, used):
    """Copy path and its sidecars. Returns how many files were copied."""
    if not path or not os.path.isfile(path):
        return 0
    copied = 0
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    names = [base]
    try:
        for entry in os.listdir(os.path.dirname(path)):
            if entry == base:
                continue
            if not is_sidecar(entry, stem):
                continue
            names.append(entry)
    except OSError:
        pass
    for name in names:
        try:
            target = unique_name(folder, name, used)
            shutil.copy2(os.path.join(os.path.dirname(path), name), os.path.join(folder, target))
            copied += 1
        except OSError:
            continue
    return copied


def _run(iface, selected):
    if selected:
        layers = selected_layers(iface)
    else:
        layers = list(QgsProject.instance().mapLayers().values())
    if not layers:
        report(iface.mainWindow(), tr("复制图层文件"), tr("没有可复制的图层。"), warning=True)
        return
    folder = QFileDialog.getExistingDirectory(
        iface.mainWindow(),
        tr("选择目标文件夹"),
        "",
    )
    if not folder:
        return
    used = set()
    skipped = []
    for layer in layers:
        path = layer_file_path(layer)
        if not path or not os.path.isfile(path):
            skipped.append(layer.name())
            continue
        if not _copy_one(path, folder, used):
            skipped.append(layer.name())
    if not skipped:
        return
    shown = "、".join(skipped[:10])
    more = "" if len(skipped) <= 10 else tr(" 等 %d 个") % len(skipped)
    report(iface.mainWindow(), tr("复制图层文件"), tr("没有本地文件而跳过：%s%s") % (shown, more), warning=True)


from . import subcommands

tr("复制所选图层的文件")
tr("复制全部图层的文件")
subcommands.register("lpt:copy_files", [
    ("selected", "复制所选图层的文件", lambda iface: _run(iface, True)),
    ("all", "复制全部图层的文件", lambda iface: _run(iface, False)),
])