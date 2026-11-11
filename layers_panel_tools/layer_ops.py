# -*- coding: utf-8 -*-
"""图层操作：清空数据、打开编辑、保存关闭、复制到空、复制图层。

行为与 KMZ Exporter 主页左侧五项一致。前三项作用于当前工程的全部矢量图层。
后两项只作用于图层面板里当前选中的那一个矢量图层，样式跟着走。
"""

import os

from qgis.PyQt.QtWidgets import QFileDialog, QInputDialog, QMessageBox
from qgis.core import (
    QgsFeature,
    QgsMapLayerStyle,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)

from .buttons import (
    make_popup_menu_action,
    make_popup_tool,
    report,
)
from .i18n import tr
from .icons import load_icon
from .qt_compat import enum_int, qt_attr, run_dialog

_BUTTON = "lpt:layer_ops"

_FORMATS = (
    ("ESRI Shapefile", "ESRI Shapefile", ".shp"),
    ("GeoPackage", "GPKG", ".gpkg"),
    ("GeoJSON", "GeoJSON", ".geojson"),
    ("KML", "KML", ".kml"),
    ("MapInfo TAB", "MapInfo File", ".tab"),
    ("FlatGeobuf", "FlatGeobuf", ".fgb"),
    ("CSV", "CSV", ".csv"),
)


def _rollback(layer):
    try:
        if layer.isEditable():
            layer.rollBack()
    except Exception:  # nosec B110
        pass


def _vectors():
    layers = []
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            layers.append(layer)
    layers.sort(key=lambda layer: (layer.name() or "").casefold())
    return layers


def _parent(iface):
    try:
        return iface.mainWindow()
    except Exception:
        return None


def _tell(iface, text, warning=False):
    report(_parent(iface), tr("图层操作"), text, warning=warning)


def _no_layers(iface):
    _tell(iface, tr("当前没有可处理的矢量图层。"), warning=True)


def clear_all(iface):
    layers = _vectors()
    if not layers:
        _no_layers(iface)
        return
    if not _confirm_clear(_parent(iface)):
        return
    failed = []
    for layer in layers:
        try:
            if not layer.isEditable():
                layer.startEditing()
            layer.selectAll()
            layer.deleteSelectedFeatures()
            if not layer.commitChanges():
                _rollback(layer)
                failed.append(layer.name() or "")
        except Exception:
            _rollback(layer)
            failed.append(layer.name() or "")
    if failed:
        _tell(iface, tr("以下图层清空失败：\n%s") % "\n".join(failed), warning=True)
        return
    _tell(iface, tr("所有图层数据已清空"))


def editing_on(iface):
    layers = _vectors()
    if not layers:
        _no_layers(iface)
        return
    failed = []
    for layer in layers:
        if layer.isEditable():
            continue
        try:
            if not layer.startEditing():
                failed.append(layer.name() or "")
        except Exception:
            failed.append(layer.name() or "")
    if failed:
        _tell(iface, tr("以下图层未能打开编辑：\n%s") % "\n".join(failed), warning=True)


def editing_off(iface):
    layers = _vectors()
    if not layers:
        _no_layers(iface)
        return
    failed = []
    for layer in layers:
        if not layer.isEditable():
            continue
        try:
            if not layer.commitChanges():
                _rollback(layer)
                failed.append(layer.name() or "")
        except Exception:
            _rollback(layer)
            failed.append(layer.name() or "")
    if failed:
        _tell(iface, tr("以下图层保存失败：\n%s") % "\n".join(failed), warning=True)


def _confirm_clear(parent):
    text, ok = QInputDialog.getText(
        parent,
        tr("确认清空"),
        tr("将删除当前工程里全部矢量图层的全部要素。图层还在，要素删掉后不能恢复。\n请输入 OK 确认："),
    )
    if not ok or str(text or "").strip().upper() != "OK":
        return False
    box = QMessageBox(parent)
    box.setWindowTitle(tr("二次确认"))
    box.setText(tr("确认删除全部要素？这一步不能返回，也不能撤销。"))
    try:
        box.setIcon(qt_attr(QMessageBox, "Warning"))
    except Exception:
        pass  # nosec
    yes_flag = qt_attr(QMessageBox, "Yes")
    no_flag = qt_attr(QMessageBox, "No")
    box.setStandardButtons(yes_flag | no_flag)
    try:
        box.setDefaultButton(no_flag)
    except Exception:
        pass  # nosec
    yes = box.button(yes_flag)
    no = box.button(no_flag)
    if yes is not None:
        yes.setText(tr("删除全部"))
    if no is not None:
        no.setText(tr("取消"))
    return enum_int(run_dialog(box)) == enum_int(yes_flag)


def _active_vector():
    try:
        from qgis.utils import iface

        layer = iface.activeLayer() if iface is not None else None
    except Exception:
        layer = None
    if isinstance(layer, QgsVectorLayer) and layer.isValid():
        return layer
    return None


def _source_file(layer):
    raw = (layer.source() or "").split("|")[0].strip().strip('"')
    if raw.lower().startswith("file:"):
        from qgis.PyQt.QtCore import QUrl

        raw = QUrl(raw).toLocalFile()
    return raw


def _format_index(layer):
    storage = (layer.storageType() or "").lower()
    path = _source_file(layer).lower()
    blob = storage + " " + path
    if "shape" in blob or path.endswith(".shp"):
        return 0
    if "gpkg" in blob or path.endswith(".gpkg"):
        return 1
    if "json" in blob or path.endswith(".geojson") or path.endswith(".json"):
        return 2
    if "kml" in blob or "kmz" in blob or path.endswith(".kml") or path.endswith(".kmz"):
        return 3
    if "mapinfo" in blob or path.endswith(".tab"):
        return 4
    if "flatgeobuf" in blob or path.endswith(".fgb"):
        return 5
    if "csv" in blob or path.endswith(".csv"):
        return 6
    return 1


def copy_current(iface, with_features):
    """None means the user cancelled. Otherwise (ok, message)."""
    parent = _parent(iface)
    layer = _active_vector()
    if layer is None:
        _tell(iface, tr("请先在图层面板选中一个矢量图层。"), warning=True)
        return
    name = layer.name() or tr("图层")
    source = _source_file(layer)
    folder = os.path.dirname(source) if source and os.path.dirname(source) else ""
    if not folder or not os.path.isdir(folder):
        project = QgsProject.instance()
        folder = os.path.dirname(project.fileName() or "") or (project.homePath() or "")
    index = _format_index(layer)
    label, driver, ext = _FORMATS[index]
    kind = tr("连同全部要素一起复制，样式与所选图层相同。") if with_features else tr("不复制要素，只保留字段和样式。")
    where = source or tr("这个图层没有文件路径，默认保存到工程所在文件夹。")
    box = QMessageBox(parent)
    box.setWindowTitle(tr("复制当前图层") if with_features else tr("复制当前图层为空"))
    try:
        box.setIcon(qt_attr(QMessageBox, "Information"))
    except Exception:
        pass  # nosec
    box.setText(
        tr("当前所选图层：%s\n路径：%s\n原格式：%s\n%s\n\n下一步选择保存位置。默认就在这个文件夹，格式默认与原图层相同。")
        % (name, where, label, kind)
    )
    ok_flag = qt_attr(QMessageBox, "Ok")
    cancel_flag = qt_attr(QMessageBox, "Cancel")
    box.setStandardButtons(ok_flag | cancel_flag)
    ok_button = box.button(ok_flag)
    cancel_button = box.button(cancel_flag)
    if ok_button is not None:
        ok_button.setText(tr("继续"))
    if cancel_button is not None:
        cancel_button.setText(tr("取消"))
    if enum_int(run_dialog(box)) != enum_int(ok_flag):
        return
    filters = ";;".join("%s (*%s)" % (item[0], item[2]) for item in _FORMATS)
    initial = "%s (*%s)" % (label, ext)
    stem = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in name).strip() or "layer"
    stem += "" if with_features else tr("_空")
    default_path = os.path.join(folder, stem + ext) if folder else (stem + ext)
    path, chosen = QFileDialog.getSaveFileName(parent, tr("保存复制图层"), default_path, filters, initial)
    if not path:
        return
    chosen_index = index
    for item_index, item in enumerate(_FORMATS):
        if str(chosen or "").startswith(item[0]):
            chosen_index = item_index
            break
    label, driver, ext = _FORMATS[chosen_index]
    if not path.lower().endswith(ext):
        path += ext
    crs = ""
    try:
        if layer.crs().isValid() and layer.crs().authid():
            crs = layer.crs().authid()
    except Exception:
        crs = ""
    uri = QgsWkbTypes.displayString(layer.wkbType())
    if crs:
        uri += "?crs=" + crs
    memory = QgsVectorLayer(uri, name, "memory")
    provider = memory.dataProvider()
    provider.addAttributes(layer.fields())
    memory.updateFields()
    if with_features:
        features = []
        for source_feature in layer.getFeatures():
            feature = QgsFeature(memory.fields())
            feature.setGeometry(source_feature.geometry())
            feature.setAttributes(source_feature.attributes())
            features.append(feature)
        if features:
            provider.addFeatures(features)
    memory.updateExtents()
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = driver
    options.fileEncoding = "UTF-8"
    options.layerName = os.path.splitext(os.path.basename(path))[0]
    try:
        nested = getattr(QgsVectorFileWriter, "ActionOnExistingFile", None)
        action = None
        if nested is not None and hasattr(nested, "CreateOrOverwriteFile"):
            action = nested.CreateOrOverwriteFile
        else:
            action = getattr(QgsVectorFileWriter, "CreateOrOverwriteFile", None)
        if action is not None:
            options.actionOnExistingFile = action
    except Exception:  # nosec B110
        pass
    writer = getattr(QgsVectorFileWriter, "writeAsVectorFormatV3", None)
    result = writer(memory, path, QgsProject.instance().transformContext(), options)
    error = result[0] if isinstance(result, tuple) else result
    message = result[1] if isinstance(result, tuple) and len(result) > 1 else ""
    no_error = getattr(QgsVectorFileWriter, "NoError", 0)
    nested_error = getattr(QgsVectorFileWriter, "WriterError", None)
    if nested_error is not None and hasattr(nested_error, "NoError"):
        no_error = nested_error.NoError
    if enum_int(error, 0) != enum_int(no_error, 0):
        _tell(iface, message or tr("没有写成文件。"), warning=True)
        return
    loaded_uri = path
    if driver == "GPKG":
        loaded_uri = path + "|layername=" + options.layerName
    loaded = QgsVectorLayer(loaded_uri, os.path.splitext(os.path.basename(path))[0], "ogr")
    if not loaded.isValid():
        _tell(iface, tr("文件已保存：%s") % path)
        return
    style = QgsMapLayerStyle()
    style.readFromLayer(layer)
    if style.isValid():
        style.writeToLayer(loaded)
    QgsProject.instance().addMapLayer(loaded, False)
    root = QgsProject.instance().layerTreeRoot()
    node = root.findLayer(layer.id())
    if node is not None and node.parent() is not None:
        parent_node = node.parent()
        try:
            parent_node.insertLayer(parent_node.children().index(node) + 1, loaded)
        except Exception:
            root.addLayer(loaded)
    else:
        root.addLayer(loaded)
    try:
        loaded.triggerRepaint()
    except Exception:
        pass  # nosec
    _tell(iface, tr("已复制图层「%s」到：\n%s") % (name, path))


def _fill(iface, menu):
    from . import subcommands

    menu.clear()
    for sub_id, _msgid, _runner in subcommands.subcommands_of(_BUTTON):
        subcommands.add_to_menu(iface, _BUTTON, menu, sub_id)


def make_action(iface):
    tr("图层操作")
    tr("清空数据、开关编辑，或把当前图层复制成新文件")
    return make_popup_tool(
        iface,
        _BUTTON,
        "LayersPanelToolsLayerOps",
        "图层操作",
        "清空数据、开关编辑，或把当前图层复制成新文件",
        load_icon("layer_ops"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsLayerOpsMenu",
        "图层操作",
        "清空数据、开关编辑，或把当前图层复制成新文件",
        load_icon("layer_ops"),
        lambda menu: _fill(iface, menu),
    )


from . import subcommands

tr("清空数据")
tr("打开编辑")
tr("保存关闭")
tr("复制到空")
tr("复制图层")
subcommands.register(_BUTTON, [
    ("clear", "清空数据", lambda iface: clear_all(iface)),
    ("edit_on", "打开编辑", lambda iface: editing_on(iface)),
    ("edit_off", "保存关闭", lambda iface: editing_off(iface)),
    ("copy_empty", "复制到空", lambda iface: copy_current(iface, False)),
    ("copy_full", "复制图层", lambda iface: copy_current(iface, True)),
])
