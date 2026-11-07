# -*- coding: utf-8 -*-
"""Copy one layer's style, then paste all of it, or only symbols or labels, onto the selection."""

from qgis.PyQt.QtCore import QMimeData
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtXml import QDomDocument
from qgis.core import QgsMapLayer, QgsReadWriteContext

from .buttons import make_popup_menu_action, make_popup_tool
from .i18n import tr
from .icons import load_icon
from .qt_compat import qt_attr
from .scope import geometry_code, is_vector, selected_layers, tell

# Same clipboard format QGIS uses for Styles > Copy Style, so either side can paste.
_MIME = "application/qgis.style"
_copied = {"xml": "", "name": ""}


def make_action(iface):
    tr("复制粘贴样式")
    tr("复制当前图层的样式，粘贴到已选图层：全部、只要符号或只要标注")
    return make_popup_tool(
        iface,
        "lpt:style",
        "LayersPanelToolsStyle",
        "复制粘贴样式",
        "复制当前图层的样式，粘贴到已选图层：全部、只要符号或只要标注",
        load_icon("style"),
        lambda menu: _fill(iface, menu),
    )


def make_menu_action(iface):
    return make_popup_menu_action(
        iface,
        "LayersPanelToolsStyleMenu",
        "复制粘贴样式",
        "复制当前图层的样式，粘贴到已选图层：全部、只要符号或只要标注",
        load_icon("style"),
        lambda menu: _fill(iface, menu),
    )


def _category(name):
    try:
        return qt_attr(QgsMapLayer, name)
    except AttributeError:
        return None


def _active_layer(iface):
    try:
        return iface.activeLayer()
    except Exception:
        return None


def _clipboard_xml():
    try:
        data = QApplication.clipboard().mimeData()
    except Exception:
        return ""
    if data is None or not data.hasFormat(_MIME):
        return ""
    try:
        return bytes(data.data(_MIME)).decode("utf-8", "replace")
    except Exception:
        return ""


def _source():
    """Style waiting to be pasted, and the layer name it came from."""
    xml = _clipboard_xml()
    if xml and xml == _copied.get("xml"):
        return xml, _copied.get("name") or ""
    if xml:
        return xml, ""
    return _copied.get("xml") or "", _copied.get("name") or ""


def _fill(iface, menu):
    menu.clear()
    layer = _active_layer(iface)
    copy_action = subcommands.add_to_menu(iface, "lpt:style", menu, "lpt:style:copy")
    if copy_action is not None:
        if layer is not None:
            copy_action.setText(tr("复制「%s」的样式") % layer.name())
            copy_action.setEnabled(True)
        else:
            copy_action.setEnabled(False)
    xml, name = _source()
    menu.addSeparator()
    if xml:
        note = menu.addAction(tr("已复制：%s") % (name or tr("剪贴板里的样式")))
    else:
        note = menu.addAction(tr("还没有复制样式"))
    note.setEnabled(False)
    ready = bool(xml)
    for suffix in ("paste_all", "paste_symbols", "paste_labels"):
        action = subcommands.add_to_menu(iface, "lpt:style", menu, "lpt:style:" + suffix)
        if action is not None:
            action.setEnabled(ready)


def copy_style_from_layer(iface, layer):
    """供其它窗口调用：把指定图层的样式写入插件剪贴板与系统剪贴板。"""
    if layer is None:
        tell(iface, tr("复制粘贴样式"), tr("请先在图层面板里点一下要复制样式的图层。"), warning=True)
        return False
    doc = QDomDocument()
    try:
        error = layer.exportNamedStyle(doc, QgsReadWriteContext())
    except TypeError:
        error = layer.exportNamedStyle(doc)
    if isinstance(error, tuple):
        error = error[-1]
    if error:
        tell(iface, tr("复制粘贴样式"), tr("复制样式失败：%s") % error, warning=True)
        return False
    xml = doc.toString()
    _copied["xml"] = xml
    _copied["name"] = layer.name()
    try:
        data = QMimeData()
        data.setData(_MIME, doc.toByteArray())
        data.setText(xml)
        QApplication.clipboard().setMimeData(data)
    except Exception:
        pass  # nosec
    tell(iface, tr("复制粘贴样式"), tr("已复制「%s」的样式。") % layer.name())
    return True


def _copy(iface):
    return copy_style_from_layer(iface, _active_layer(iface))


def paste_style_onto_layers(iface, targets, part="all"):
    """part: all | symbols | labels"""
    if not targets:
        tell(iface, tr("复制粘贴样式"), tr("图层面板里没有选中图层。"), warning=True)
        return
    xml, _name = _source()
    if not xml:
        tell(iface, tr("复制粘贴样式"), tr("还没有复制样式"), warning=True)
        return
    kind, geometry = style_shape(xml)
    categories = _categories(part)
    done = 0
    skipped = 0
    failed = 0
    for layer in targets:
        if not _fits(layer, kind, geometry, part):
            skipped += 1
            continue
        doc = QDomDocument()
        doc.setContent(xml)
        try:
            if categories is None:
                result = layer.importNamedStyle(doc)
            else:
                result = layer.importNamedStyle(doc, categories)
        except Exception:
            failed += 1
            continue
        ok = result[0] if isinstance(result, tuple) else bool(result)
        if not ok:
            failed += 1
            continue
        done += 1
        _refresh(iface, layer)
    text = tr("已把样式粘贴到 %d 个图层。") % done
    if skipped:
        text = text + " " + tr("跳过 %d 个类型或几何不同的图层。") % skipped
    if failed:
        text = text + " " + tr("%d 个图层没能套用。") % failed
    tell(iface, tr("复制粘贴样式"), text, warning=bool(skipped or failed) or done == 0)


def style_shape(xml):
    """(kind, geometry) of a copied style: ("vector", "point"/"line"/"polygon"/""), ("raster", ""), or ("", "")."""
    doc = QDomDocument()
    try:
        parsed = doc.setContent(xml)
    except Exception:
        parsed = False
    if isinstance(parsed, tuple):
        parsed = parsed[0]
    if not parsed:
        return "", ""
    if doc.elementsByTagName("pipe").count():
        return "raster", ""
    nodes = doc.elementsByTagName("layerGeometryType")
    if nodes.count():
        try:
            number = int(nodes.item(0).toElement().text().strip())
        except ValueError:
            number = -1
        return "vector", {0: "point", 1: "line", 2: "polygon"}.get(number, "")
    if doc.elementsByTagName("renderer-v2").count() or doc.elementsByTagName("labeling").count():
        return "vector", ""
    return "", ""


def _fits(layer, kind, geometry, part):
    if part == "labels":
        return is_vector(layer)
    if kind == "raster":
        return not is_vector(layer) and geometry_code(layer) == "raster"
    if kind == "vector":
        if not is_vector(layer):
            return False
        return not geometry or geometry_code(layer) == geometry
    return True


def _categories(part):
    if part == "symbols":
        return _category("Symbology")
    if part == "labels":
        return _category("Labeling")
    return _category("AllStyleCategories")


def _paste(iface, part):
    targets = selected_layers(iface)
    if not targets:
        tell(iface, tr("复制粘贴样式"), tr("图层面板里没有选中图层。"), warning=True)
        return
    paste_style_onto_layers(iface, targets, part)


def _refresh(iface, layer):
    for step in (layer.triggerRepaint, layer.emitStyleChanged):
        try:
            step()
        except Exception:
            pass  # nosec
    try:
        iface.layerTreeView().refreshLayerSymbology(layer.id())
    except Exception:
        pass  # nosec


from . import subcommands

tr("复制当前图层的样式")
tr("粘贴全部样式到已选图层")
tr("只粘贴符号到已选图层")
tr("只粘贴标注到已选图层")
subcommands.register("lpt:style", [
    ("copy", "复制当前图层的样式", lambda iface: _copy(iface)),
    ("paste_all", "粘贴全部样式到已选图层", lambda iface: _paste(iface, "all")),
    ("paste_symbols", "只粘贴符号到已选图层", lambda iface: _paste(iface, "symbols")),
    ("paste_labels", "只粘贴标注到已选图层", lambda iface: _paste(iface, "labels")),
])