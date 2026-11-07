# -*- coding: utf-8 -*-
"""编辑记录：内存统计，并按保存前的快照回退最近一批。"""

import time

from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from qgis.core import QgsFeature, QgsFeatureRequest, QgsGeometry, QgsProject, QgsRasterLayer, QgsVectorLayer

from .buttons import ask, make_menu_action as build_menu_action, make_toolbar_button, qt_attr
from .i18n import apply_direction, localize_button_box, tr, subscribe
from .icons import load_icon
from .qt_compat import user_role
from .scope import tell

_MAX_ENTRIES = 2000
_store = {"seq": 0, "events": []}
_batches = {}
_next_batch = 1
_suppress = False
_controller = None
_DIALOG = None


def make_action(iface):
    tr("编辑记录")
    tr("本次打开工程后的操作记录。每一条可以单独回退，也可以按图层逐条回退")
    tr("图层重命名")
    tr("备注")
    tr("工程中添加图层")
    tr("从工程移除图层")
    tr("几何改动")
    tr("导出 TXT…")
    tr("回退这一条")
    tr("回退该图层")
    return make_toolbar_button(
        iface,
        "lpt:edit_timeline",
        "LayersPanelToolsEditTimeline",
        "编辑记录",
        "本次打开工程后的操作记录。每一条可以单独回退，也可以按图层逐条回退",
        load_icon("edit_timeline"),
        lambda: open_timeline(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsEditTimelineMenu",
        "编辑记录",
        "本次打开工程后的操作记录。每一条可以单独回退，也可以按图层逐条回退",
        load_icon("edit_timeline"),
        lambda: open_timeline(iface),
    )


def open_timeline(iface):
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = EditTimelineDialog(iface, iface.mainWindow())
    _DIALOG.reload()
    _DIALOG.show()
    _DIALOG.raise_()
    _DIALOG.activateWindow()


def close_timeline():
    global _controller, _DIALOG
    dialog = _DIALOG
    _DIALOG = None
    if dialog is not None:
        try:
            dialog.close()
        except RuntimeError:
            pass
    controller = _controller
    _controller = None
    if controller is not None:
        controller.dispose()


def _new_batch(payload):
    global _next_batch
    batch_id = _next_batch
    _next_batch += 1
    data = dict(payload)
    data["id"] = batch_id
    _batches[batch_id] = data
    return batch_id


def _append_event(kind, layer_name, count, detail="", batch=None, layer_id="", undo=None):
    if _suppress:
        return
    _store["seq"] = int(_store.get("seq") or 0) + 1
    _store.setdefault("events", []).append(
        {
            "id": _store["seq"],
            "t": time.time(),
            "kind": kind,
            "layer": layer_name or "",
            "layer_id": str(layer_id or ""),
            "count": int(count),
            "detail": str(detail or "")[:500],
            "batch": batch,
            "undo": undo,
        }
    )
    overflow = len(_store["events"]) - _MAX_ENTRIES
    if overflow > 0:
        dropped = _store["events"][:overflow]
        _store["events"] = _store["events"][overflow:]
        live = set(item.get("batch") for item in _store["events"])
        for item in dropped:
            batch_id = item.get("batch")
            if batch_id not in live:
                _batches.pop(batch_id, None)


def _reset_session():
    global _next_batch
    _store["seq"] = 0
    _store["events"] = []
    _batches.clear()
    _next_batch = 1


def _as_items(obj):
    if obj is None:
        return []
    try:
        return list(obj.items())
    except Exception:
        pass  # nosec
    found = []
    try:
        keys = list(obj.keys())
    except Exception:
        return found
    for key in keys:
        try:
            found.append((key, obj[key]))
        except Exception:
            continue  # nosec
    return found


def _plain(value):
    if value is None:
        return None
    try:
        from qgis.PyQt.QtCore import QVariant

        if isinstance(value, QVariant):
            try:
                if value.isNull():
                    return None
            except Exception:
                pass  # nosec
            try:
                return value.value()
            except Exception:
                return None
    except Exception:
        pass  # nosec
    if hasattr(value, "toString") and not isinstance(value, str):
        try:
            return value.toString()
        except Exception:
            pass  # nosec
    return value


def _fetch_provider(provider, fid):
    try:
        request = QgsFeatureRequest(int(fid))
        for feature in provider.getFeatures(request):
            return feature
    except Exception:
        return None
    return None


def _pack_feature(feature):
    wkt = ""
    try:
        geometry = feature.geometry()
        if geometry is not None and not geometry.isEmpty():
            wkt = geometry.asWkt()
    except Exception:
        wkt = ""
    names = []
    attrs = []
    try:
        fields = feature.fields()
        for index in range(fields.count()):
            names.append(fields.at(index).name())
            attrs.append(_plain(feature.attribute(index)))
    except Exception:
        pass  # nosec
    return {"wkt": wkt, "names": names, "attrs": attrs}


def _add_packed(layer, pack):
    feature = QgsFeature(layer.fields())
    names = pack.get("names") or []
    attrs = pack.get("attrs") or []
    for name, value in zip(names, attrs):
        index = layer.fields().indexFromName(name)
        if index >= 0:
            try:
                feature.setAttribute(index, value)
            except Exception:
                pass  # nosec
    wkt = pack.get("wkt") or ""
    if wkt:
        try:
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
        except Exception:
            pass  # nosec
    layer.addFeature(feature)


def rollback_event(event):
    """回退表格里的一条。返回 (成功, 说明)。"""
    global _suppress
    if not event or not event.get("undo"):
        return False, tr("这一条没有可回退的数据。")
    _suppress = True
    try:
        ok, message = _apply_one(event.get("undo") or {})
    finally:
        _suppress = False
    if not ok:
        return False, message or tr("回退失败。")
    event_id = event.get("id")
    _store["events"] = [item for item in _store["events"] if item.get("id") != event_id]
    return True, tr("已回退这一条。")


def rollback_latest_for_layer(layer_id):
    wanted = str(layer_id or "")
    if not wanted:
        return False, tr("这个图层没有可以回退的记录。")
    for event in reversed(_store.get("events") or []):
        if str(event.get("layer_id") or "") == wanted and event.get("undo"):
            return rollback_event(event)
    return False, tr("这个图层没有可以回退的记录。")


def _apply_one(undo):
    op = undo.get("op")
    layer_id = undo.get("layer_id")
    if op == "rename":
        return _apply_undo({"layer_id": layer_id, "rename": (undo.get("old"), undo.get("new"))})
    if op == "project_add":
        return _apply_undo({"layer_id": layer_id, "project_add": True})
    if op == "project_remove":
        return _apply_undo({"project_remove": undo.get("info") or {}})
    if op == "add":
        return _apply_undo(
            {"layer_id": layer_id, "added": undo.get("fids") or [], "deleted": [], "attr_old": [], "geom_old": []}
        )
    if op == "delete":
        return _apply_undo(
            {
                "layer_id": layer_id,
                "added": [],
                "deleted": undo.get("features") or [],
                "attr_old": [],
                "geom_old": [],
            }
        )
    if op == "attr":
        return _apply_undo(
            {
                "layer_id": layer_id,
                "added": [],
                "deleted": [],
                "attr_old": undo.get("attr_old") or [],
                "geom_old": [],
            }
        )
    if op == "geom":
        return _apply_undo(
            {
                "layer_id": layer_id,
                "added": [],
                "deleted": [],
                "attr_old": [],
                "geom_old": undo.get("geom_old") or [],
            }
        )
    return False, tr("这一条没有可回退的数据。")


def _apply_undo(payload):
    project = QgsProject.instance()
    rename = payload.get("rename")
    if rename:
        layer = project.mapLayer(payload.get("layer_id"))
        if layer is None:
            return False, tr("图层已经不在工程里。")
        try:
            layer.setName(rename[0])
        except Exception as exc:
            return False, str(exc)
        return True, ""
    if payload.get("project_add"):
        layer_id = payload.get("layer_id")
        if project.mapLayer(layer_id) is None:
            return False, tr("图层已经不在工程里。")
        try:
            project.removeMapLayer(layer_id)
        except Exception as exc:
            return False, str(exc)
        return True, ""
    removed = payload.get("project_remove")
    if removed:
        return _restore_layer(removed)
    layer = project.mapLayer(payload.get("layer_id"))
    if not isinstance(layer, QgsVectorLayer):
        return False, tr("图层已经不在工程里。")
    started = False
    try:
        started = not layer.isEditable()
    except Exception:
        started = True
    if started:
        try:
            if not layer.startEditing():
                return False, tr("图层不能进入编辑。")
        except Exception as exc:
            return False, str(exc)
    try:
        for fid in payload.get("added") or []:
            try:
                layer.deleteFeature(int(fid))
            except Exception:
                pass  # nosec
        for fid, name, old in payload.get("attr_old") or []:
            index = layer.fields().indexFromName(name)
            if index < 0:
                continue
            try:
                layer.changeAttributeValue(int(fid), index, old)
            except Exception:
                pass  # nosec
        for fid, wkt in payload.get("geom_old") or []:
            try:
                geometry = QgsGeometry.fromWkt(wkt) if wkt else QgsGeometry()
                layer.changeGeometry(int(fid), geometry)
            except Exception:
                pass  # nosec
        for pack in payload.get("deleted") or []:
            _add_packed(layer, pack)
        if started:
            if not layer.commitChanges():
                errors = []
                try:
                    errors = [str(item) for item in (layer.commitErrors() or [])]
                except Exception:
                    errors = []
                try:
                    layer.rollBack()
                except Exception:
                    pass  # nosec
                return False, " ".join(errors) or tr("写回失败。")
    except Exception as exc:
        if started:
            try:
                layer.rollBack()
            except Exception:
                pass  # nosec
        return False, str(exc)
    return True, ""


def _restore_layer(info):
    provider = info.get("provider") or ""
    source = info.get("source") or ""
    name = info.get("name") or tr("图层")
    if not provider or not source:
        return False, tr("这一层当时没有数据源，无法加回去。")
    kind = info.get("kind") or "vector"
    if kind == "raster":
        layer = QgsRasterLayer(source, name, provider)
    else:
        layer = QgsVectorLayer(source, name, provider)
    try:
        valid = layer.isValid()
    except Exception:
        valid = False
    if not valid:
        return False, tr("按原数据源加回去失败。")
    try:
        QgsProject.instance().addMapLayer(layer)
    except Exception as exc:
        return False, str(exc)
    return True, ""


class EditTimelineController:
    def __init__(self):
        self._listening = False
        self._layer_hooks = {}
        self._last_layer_names = {}
        self._project_hooks = []
        self._open_batch = {}

    def hook(self):
        if self._listening:
            return
        self._listening = True
        proj = QgsProject.instance()

        def _on_project_reset(*_args):
            if _suppress:
                return
            _reset_session()
            self._open_batch.clear()

        for sig_name in ("cleared", "readProject"):
            sig = getattr(proj, sig_name, None)
            if sig is not None:
                try:
                    sig.connect(_on_project_reset)
                    self._project_hooks.append((sig, _on_project_reset))
                except Exception:
                    pass  # nosec

        def _on_layers_added(layers):
            for layer in layers or []:
                if layer is None:
                    continue
                try:
                    name = layer.name() or ""
                except Exception:
                    name = ""
                batch = None
                if not _suppress:
                    batch = _new_batch(
                        {
                            "layer_id": layer.id(),
                            "project_add": True,
                            "added": [],
                            "deleted": [],
                            "attr_old": [],
                            "geom_old": [],
                        }
                    )
                _append_event(
                    tr("工程中添加图层"),
                    name,
                    1,
                    layer.id() or "",
                    batch,
                    layer.id() or "",
                    {"op": "project_add", "layer_id": layer.id()} if batch else None,
                )
                self._attach_layer(layer)

        def _on_layers_will_remove(ids):
            for lid in ids or []:
                layer = proj.mapLayer(lid)
                try:
                    name = layer.name() if layer is not None else ""
                except Exception:
                    name = ""
                batch = None
                if layer is not None and not _suppress:
                    kind = "vector" if isinstance(layer, QgsVectorLayer) else "raster"
                    if not isinstance(layer, (QgsVectorLayer, QgsRasterLayer)):
                        kind = "other"
                    try:
                        source = layer.source() or ""
                    except Exception:
                        source = ""
                    try:
                        provider = layer.providerType() or ""
                    except Exception:
                        provider = ""
                    batch = _new_batch(
                        {
                            "project_remove": {
                                "name": name,
                                "source": source,
                                "provider": provider,
                                "kind": kind,
                            },
                            "added": [],
                            "deleted": [],
                            "attr_old": [],
                            "geom_old": [],
                        }
                    )
                info = None
                if batch and batch in _batches:
                    info = _batches[batch].get("project_remove")
                _append_event(
                    tr("从工程移除图层"),
                    name or str(lid),
                    1,
                    str(lid),
                    batch,
                    str(lid),
                    {"op": "project_remove", "info": info} if info else None,
                )
                self._detach_layer(str(lid))

        for signal, slot in ((proj.layersAdded, _on_layers_added), (proj.layersWillBeRemoved, _on_layers_will_remove)):
            if signal is not None:
                try:
                    signal.connect(slot)
                    self._project_hooks.append((signal, slot))
                except Exception:
                    pass  # nosec
        for layer in list(proj.mapLayers().values()):
            self._attach_layer(layer)

    def dispose(self):
        if not self._listening:
            return
        self._listening = False
        for signal, slot in self._project_hooks:
            try:
                signal.disconnect(slot)
            except Exception:
                pass  # nosec
        self._project_hooks.clear()
        for layer_id in list(self._layer_hooks.keys()):
            self._detach_layer(layer_id)
        self._last_layer_names.clear()
        self._open_batch.clear()

    def _attach_layer(self, layer):
        if not isinstance(layer, QgsVectorLayer):
            return
        try:
            lid = layer.id()
        except Exception:
            return
        if lid in self._layer_hooks:
            return
        hooks = []
        try:
            self._last_layer_names[lid] = layer.name() or ""
        except Exception:
            self._last_layer_names[lid] = ""

        def _name():
            try:
                return layer.name() or ""
            except Exception:
                return ""

        def on_before(*_args):
            if _suppress:
                return
            buffer = None
            try:
                buffer = layer.editBuffer()
            except Exception:
                buffer = None
            if buffer is None:
                return
            provider = None
            try:
                provider = layer.dataProvider()
            except Exception:
                provider = None
            deleted = []
            try:
                removed_ids = list(buffer.deletedFeatureIds())
            except Exception:
                removed_ids = []
            for fid in removed_ids:
                feature = _fetch_provider(provider, fid) if provider is not None else None
                if feature is not None:
                    deleted.append(_pack_feature(feature))
            attr_old = []
            try:
                changed = buffer.changedAttributeValues()
            except Exception:
                changed = {}
            for fid, amap in _as_items(changed):
                feature = _fetch_provider(provider, fid) if provider is not None else None
                if feature is None:
                    continue
                for index, _new in _as_items(amap):
                    try:
                        index = int(index)
                        field_name = feature.fields().at(index).name()
                        old = _plain(feature.attribute(index))
                    except Exception:
                        continue  # nosec
                    attr_old.append((int(fid), field_name, old))
            geom_old = []
            try:
                geoms = buffer.changedGeometries()
            except Exception:
                geoms = {}
            for fid, _geom in _as_items(geoms):
                feature = _fetch_provider(provider, fid) if provider is not None else None
                wkt = ""
                if feature is not None:
                    try:
                        geometry = feature.geometry()
                        if geometry is not None and not geometry.isEmpty():
                            wkt = geometry.asWkt()
                    except Exception:
                        wkt = ""
                try:
                    geom_old.append((int(fid), wkt))
                except Exception:
                    pass  # nosec
            batch = _new_batch(
                {
                    "layer_id": lid,
                    "added": [],
                    "deleted": deleted,
                    "attr_old": attr_old,
                    "geom_old": geom_old,
                }
            )
            self._open_batch[lid] = batch

        def on_editing_stopped():
            batch = self._open_batch.pop(lid, None)
            if batch and not any(item.get("batch") == batch for item in _store.get("events") or []):
                _batches.pop(batch, None)

        def on_renamed(*args):
            old = self._last_layer_names.get(lid, "")
            new = ""
            if len(args) >= 2:
                try:
                    new = str(args[1] or "")
                except Exception:
                    new = ""
            elif len(args) == 1:
                try:
                    new = str(args[0] or "")
                except Exception:
                    new = ""
            if not new:
                try:
                    new = layer.name() or ""
                except Exception:
                    new = ""
            self._last_layer_names[lid] = new
            if _suppress or old == new or not (old or new):
                return
            batch = _new_batch(
                {
                    "layer_id": lid,
                    "rename": (old, new),
                    "added": [],
                    "deleted": [],
                    "attr_old": [],
                    "geom_old": [],
                }
            )
            _append_event(
                tr("图层重命名"),
                new or _name(),
                1,
                "%s → %s" % (old, new),
                batch,
                lid,
                {"op": "rename", "layer_id": lid, "old": old, "new": new},
            )

        def _batch():
            return self._open_batch.get(lid)

        def on_added(_layer_id, feats):
            fids = []
            try:
                for feature in feats or []:
                    fids.append(int(feature.id()))
            except Exception:
                fids = []
            batch = _batch()
            if batch in _batches:
                _batches[batch]["added"].extend(fids)
            if fids:
                _append_event(
                    tr("新增要素"),
                    _name(),
                    len(fids),
                    "",
                    batch,
                    lid,
                    {"op": "add", "layer_id": lid, "fids": list(fids)},
                )

        def on_removed(_layer_id, ids):
            try:
                count = len(list(ids))
            except Exception:
                count = 0
            if count:
                batch = _batch()
                packs = []
                if batch in _batches:
                    packs = list(_batches[batch].get("deleted") or [])
                _append_event(
                    tr("删除要素"),
                    _name(),
                    count,
                    "",
                    batch,
                    lid,
                    {"op": "delete", "layer_id": lid, "features": packs} if packs else None,
                )

        def on_attrs(_layer_id, attrs):
            total = 0
            try:
                for _fid, amap in _as_items(attrs):
                    total += len(list(_as_items(amap)))
            except Exception:
                total = 1
            if total:
                batch = _batch()
                old_values = []
                if batch in _batches:
                    old_values = list(_batches[batch].get("attr_old") or [])
                _append_event(
                    tr("属性改动"),
                    _name(),
                    total,
                    "",
                    batch,
                    lid,
                    {"op": "attr", "layer_id": lid, "attr_old": old_values} if old_values else None,
                )

        def on_geom(_layer_id, feats):
            try:
                count = len(list(feats))
            except Exception:
                count = 0
            if count:
                batch = _batch()
                old_geoms = []
                if batch in _batches:
                    old_geoms = list(_batches[batch].get("geom_old") or [])
                _append_event(
                    tr("几何改动"),
                    _name(),
                    count,
                    "",
                    batch,
                    lid,
                    {"op": "geom", "layer_id": lid, "geom_old": old_geoms} if old_geoms else None,
                )

        for signal, slot in (
            ("beforeCommitChanges", on_before),
            ("editingStopped", on_editing_stopped),
            ("committedFeaturesAdded", on_added),
            ("committedFeaturesRemoved", on_removed),
            ("committedAttributeValuesChanges", on_attrs),
            ("committedGeometriesChanges", on_geom),
        ):
            sig = getattr(layer, signal, None)
            if sig is not None:
                try:
                    sig.connect(slot)
                    hooks.append((sig, slot))
                except Exception:
                    pass  # nosec
        ren = getattr(layer, "layerRenamed", None) or getattr(layer, "nameChanged", None)
        if ren is not None:
            try:
                ren.connect(on_renamed)
                hooks.append((ren, on_renamed))
            except Exception:
                pass  # nosec
        if hooks:
            self._layer_hooks[lid] = hooks

    def _detach_layer(self, layer_id):
        hooks = self._layer_hooks.pop(layer_id, None)
        self._last_layer_names.pop(str(layer_id), None)
        self._open_batch.pop(str(layer_id), None)
        if not hooks:
            return
        for sig, slot in hooks:
            try:
                sig.disconnect(slot)
            except Exception:
                pass  # nosec


def _ensure_controller():
    global _controller
    if _controller is None:
        _controller = EditTimelineController()
        _controller.hook()
    return _controller


def ensure_listening():
    return _ensure_controller()


class EditTimelineDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setObjectName("LayersPanelToolsEditTimeline")
        self.resize(780, 480)
        self._listening = False
        _ensure_controller()

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([tr("时间"), tr("操作"), tr("图层"), tr("数量"), tr("备注")])
        self.table.setEditTriggers(qt_attr(QAbstractItemView, "NoEditTriggers"))
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self.btn_undo = QPushButton()
        self.btn_undo.clicked.connect(self._undo)
        self.btn_undo_layer = QPushButton()
        self.btn_undo_layer.clicked.connect(self._undo_layer)
        self.btn_clear = QPushButton()
        self.btn_clear.clicked.connect(self._clear)
        self.btn_export = QPushButton()
        self.btn_export.clicked.connect(self._export_txt)

        self._buttons = QDialogButtonBox(qt_attr(QDialogButtonBox, "Close"))
        self._buttons.rejected.connect(self.close)
        try:
            self._buttons.button(qt_attr(QDialogButtonBox, "Close")).clicked.connect(self.close)
        except Exception:
            pass  # nosec

        row_btns = QHBoxLayout()
        row_btns.addWidget(self.btn_undo)
        row_btns.addWidget(self.btn_undo_layer)
        row_btns.addWidget(self.btn_clear)
        row_btns.addWidget(self.btn_export)
        row_btns.addStretch(1)
        row_btns.addWidget(self._buttons)
        layout.addLayout(row_btns)

        self.retranslate()
        subscribe(self, self.retranslate)
        self._listening = True
        self.reload()

    def retranslate(self, *_args):
        self.setWindowTitle(tr("编辑记录"))
        self.btn_undo.setText(tr("回退这一条"))
        self.btn_undo_layer.setText(tr("回退该图层"))
        self.btn_clear.setText(tr("清空记录"))
        self.btn_export.setText(tr("导出 TXT…"))
        self.table.setHorizontalHeaderLabels([tr("时间"), tr("操作"), tr("图层"), tr("数量"), tr("备注")])
        localize_button_box(self._buttons)
        apply_direction(self)
        self.reload()

    def closeEvent(self, event):
        if self._listening:
            self._listening = False
        super().closeEvent(event)

    def reload(self):
        events = list(reversed(_store.get("events") or []))
        self.table.setRowCount(0)
        for item in events[:800]:
            row = self.table.rowCount()
            self.table.insertRow(row)
            try:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(item.get("t") or 0)))
            except Exception:
                stamp = ""
            stamp_item = QTableWidgetItem(stamp)
            stamp_item.setData(user_role(), item.get("id"))
            self.table.setItem(row, 0, stamp_item)
            self.table.setItem(row, 1, QTableWidgetItem(str(item.get("kind") or "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(item.get("layer") or "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(int(item.get("count") or 0))))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.get("detail") or "")))

    def _event_at(self, row):
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        event_id = item.data(user_role())
        for event in _store.get("events") or []:
            if event.get("id") == event_id:
                return event
        return None

    def _finish_undo(self, ok, message):
        self.reload()
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            pass  # nosec
        tell(self.iface, tr("编辑记录"), message, warning=not ok)

    def _undo(self):
        event = self._event_at(self.table.currentRow())
        if event is None:
            events = _store.get("events") or []
            event = events[-1] if events else None
        if event is None:
            tell(self.iface, tr("编辑记录"), tr("没有可以回退的记录。"), warning=True)
            return
        if not ask(self, tr("编辑记录"), tr("确定回退这一条吗？")):
            return
        ok, message = rollback_event(event)
        self._finish_undo(ok, message)

    def _undo_layer(self):
        event = self._event_at(self.table.currentRow())
        if event is None:
            tell(self.iface, tr("编辑记录"), tr("请先选中一行。"), warning=True)
            return
        if not ask(self, tr("编辑记录"), tr("确定回退这个图层最近一条吗？")):
            return
        ok, message = rollback_latest_for_layer(event.get("layer_id"))
        self._finish_undo(ok, message)

    def _clear(self):
        if not ask(self, tr("编辑记录"), tr("确定清空全部编辑记录吗？")):
            return
        _reset_session()
        self.reload()

    def _export_txt(self):
        path, _filt = QFileDialog.getSaveFileName(
            self,
            tr("导出 TXT…"),
            "",
            tr("文本文件") + " (*.txt);;" + tr("所有文件") + " (*.*)",
        )
        if not path:
            return
        lines = []
        for item in list(_store.get("events") or []):
            try:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(item.get("t") or 0)))
            except Exception:
                stamp = ""
            lines.append(
                "\t".join(
                    [
                        stamp,
                        str(item.get("kind") or ""),
                        str(item.get("layer") or ""),
                        str(int(item.get("count") or 0)),
                        str(item.get("detail") or ""),
                    ]
                )
            )
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
                if lines:
                    handle.write("\n")
        except Exception as exc:
            from qgis.PyQt.QtWidgets import QMessageBox

            QMessageBox.warning(self, tr("编辑记录"), str(exc))
