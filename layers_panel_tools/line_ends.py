# -*- coding: utf-8 -*-
"""当前所选线的起点/终点画布标注。不写图层、不抢选线工具。"""
import math

from qgis.core import (
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsFeatureRequest,
    QgsPointXY,
    QgsProject,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsVertexMarker
from qgis.PyQt.QtCore import QEvent, Qt, QTimer

from .buttons import make_menu_action as build_menu_action, make_toolbar_button
from .i18n import subscribe, tr
from .icons import load_icon
from .qt_compat import qt_attr
from qgis.PyQt.QtGui import QColor, QPalette
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

COLORS = (
    QColor(255, 0, 0, 220),
    QColor(0, 170, 0, 220),
    QColor(0, 90, 220, 220),
    QColor(200, 0, 200, 220),
    QColor(0, 170, 170, 220),
    QColor(255, 140, 0, 220),
    QColor(200, 180, 0, 220),
)
MAX_LINES = 80
MAX_LIST_PX = 360
CLOSED_W = 96
CLOSED_H = 68
_PANEL = None


def _qt_flag(*names):
    for name in names:
        if hasattr(Qt, name):
            return getattr(Qt, name)
        types = getattr(Qt, "WindowType", None)
        if types is not None and hasattr(types, name):
            return getattr(types, name)
        widget = getattr(Qt, "WidgetAttribute", None)
        if widget is not None and hasattr(widget, name):
            return getattr(widget, name)
    return 0


def _qt_enum(group, name, fallback):
    holder = getattr(Qt, group, None)
    if holder is not None and hasattr(holder, name):
        return getattr(holder, name)
    return getattr(Qt, fallback, 0)


CHECKED = _qt_enum("CheckState", "Checked", "Checked")
UNCHECKED = _qt_enum("CheckState", "Unchecked", "Unchecked")
ITEM_USER_CHECKABLE = _qt_enum("ItemFlag", "ItemIsUserCheckable", "ItemIsUserCheckable")
USER_ROLE = _qt_enum("ItemDataRole", "UserRole", "UserRole")
NO_SELECTION = _qt_enum("SelectionMode", "NoSelection", "NoSelection")
NO_FOCUS = _qt_enum("FocusPolicy", "NoFocus", "NoFocus")
SCROLL_IF = _qt_enum("ScrollBarPolicy", "ScrollBarAsNeeded", "ScrollBarAsNeeded")
SCROLL_OFF = _qt_enum("ScrollBarPolicy", "ScrollBarAlwaysOff", "ScrollBarAlwaysOff")
ELIDE_NONE = _qt_enum("TextElideMode", "ElideNone", "ElideNone")
ARROW = _qt_enum("CursorShape", "ArrowCursor", "ArrowCursor")


def _is_line_layer(layer):
    if layer is None or not isinstance(layer, QgsVectorLayer):
        return False
    try:
        if not layer.isValid():
            return False
        return layer.geometryType() == QgsWkbTypes.GeometryType.LineGeometry
    except Exception:
        return False


def _first_part(geom):
    if geom is None or geom.isEmpty():
        return None
    try:
        if geom.type() != QgsWkbTypes.GeometryType.LineGeometry:
            return None
    except Exception:
        return None
    if geom.isMultipart():
        parts = geom.asMultiPolyline()
        line = parts[0] if parts else None
    else:
        line = geom.asPolyline()
    if not line or len(line) < 2:
        return None
    start, end = line[0], line[-1]
    start_next = end
    for pt in line[1:]:
        if math.hypot(pt.x() - start.x(), pt.y() - start.y()) > 1e-9:
            start_next = pt
            break
    end_prev = start
    for pt in reversed(line[:-1]):
        if math.hypot(pt.x() - end.x(), pt.y() - end.y()) > 1e-9:
            end_prev = pt
            break
    return start, end, start_next, end_prev


def _meters_unit():
    try:
        return QgsUnitTypes.DistanceUnit.DistanceMeters
    except AttributeError:
        holder = getattr(QgsUnitTypes, "DistanceUnit", None)
        if holder is not None:
            return getattr(holder, "Meters", None)
    return None


def _length_m(layer, geom):
    if geom is None or geom.isEmpty() or layer is None:
        return None
    da = QgsDistanceArea()
    try:
        da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
        ell = QgsProject.instance().ellipsoid()
        if ell:
            da.setEllipsoid(ell)
    except Exception:
        pass  # nosec
    try:
        length = da.measureLength(geom)
    except Exception:
        try:
            length = geom.length()
        except Exception:
            return None
    unit = _meters_unit()
    if unit is not None:
        try:
            length = da.convertLengthMeasurement(length, unit)
        except Exception:
            pass  # nosec
    try:
        return float(length)
    except (TypeError, ValueError):
        return None


def _fmt_len(meters):
    if meters is None:
        return "—"
    return tr("%.2f米") % meters


def _icon_type(name, fallback):
    try:
        return getattr(QgsVertexMarker, name)
    except Exception:
        try:
            return getattr(QgsVertexMarker.IconType, name)
        except Exception:
            return fallback


class _Tag(QLabel):
    def __init__(self, canvas):
        super(_Tag, self).__init__(canvas)
        try:
            self.setAttribute(_qt_flag("WA_TransparentForMouseEvents"), True)
        except Exception:
            pass  # nosec
        try:
            self.setAlignment(qt_attr(Qt, "AlignLeft") | qt_attr(Qt, "AlignVCenter"))
        except Exception:
            pass  # nosec
        self.hide()

    def apply(self, text, color):
        self.setText(text)
        self.setStyleSheet(
            "background: rgba(255,255,255,230); padding: 1px 4px;"
            "border: 1px solid rgb(%d,%d,%d); border-radius: 3px;"
            "font-size: 11px; font-weight: 700;"
            "color: rgb(%d,%d,%d);"
            % (color.red(), color.green(), color.blue(),
               color.red(), color.green(), color.blue())
        )
        self.adjustSize()


def _end_key(pt, digits=6):
    if pt is None:
        return None
    try:
        return (round(float(pt.x()), digits), round(float(pt.y()), digits))
    except Exception:
        return None


def _fmt_seq_nums(nums):
    return "，".join(str(n) for n in nums)


def _merged_end_text(starts, ends):
    """同一端点：全是起点/终点则一行；两类都有则换行，起点在上。"""
    lines = []
    if starts:
        lines.append(tr("起点%s") % _fmt_seq_nums(starts))
    if ends:
        lines.append(tr("终点%s") % _fmt_seq_nums(ends))
    return "\n".join(lines)


def _paint_solid(widget, bg, fg=None):
    widget.setAutoFillBackground(True)
    try:
        widget.setAttribute(_qt_flag("WA_StyledBackground"), True)
    except Exception:
        pass  # nosec
    pal = widget.palette()
    color = QColor(bg)
    text = QColor(fg) if fg else QColor("#1b1b1b")
    roles = []
    try:
        roles = [
            (QPalette.ColorRole.Window, color),
            (QPalette.ColorRole.Base, color),
            (QPalette.ColorRole.Button, color),
            (QPalette.ColorRole.WindowText, text),
            (QPalette.ColorRole.Text, text),
            (QPalette.ColorRole.ButtonText, text),
        ]
    except Exception:
        roles = [
            (QPalette.ColorRole.Window, color),
            (QPalette.ColorRole.Base, color),
            (QPalette.ColorRole.Button, color),
            (QPalette.ColorRole.WindowText, text),
            (QPalette.ColorRole.Text, text),
            (QPalette.ColorRole.ButtonText, text),
        ]
    for role, value in roles:
        try:
            pal.setColor(role, value)
        except Exception:
            pass  # nosec
    widget.setPalette(pal)


def _global_pos(event):
    try:
        return event.globalPosition().toPoint()
    except Exception:
        return event.globalPos()


class _DragHeader(QWidget):
    def __init__(self, panel):
        super(_DragHeader, self).__init__(panel)
        self._panel = panel
        self._last = None

    def mousePressEvent(self, event):
        left = Qt.MouseButton.LeftButton
        if event.button() == left:
            self._last = _global_pos(event)
        super(_DragHeader, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._last is None:
            return
        now = _global_pos(event)
        delta = now - self._last
        self._last = now
        self._panel.move(self._panel.x() + delta.x(), self._panel.y() + delta.y())
        self._panel._clamp()

    def mouseReleaseEvent(self, event):
        self._last = None
        super(_DragHeader, self).mouseReleaseEvent(event)


class LinePickList(QListWidget):
    """整行点击与勾选框同一效果。"""

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item is not None:
            on = item.checkState() == CHECKED
            item.setCheckState(UNCHECKED if on else CHECKED)
            event.accept()
            return
        super(LinePickList, self).mousePressEvent(event)


class LineEndsController:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas() if iface is not None else None
        self.listening = False
        self.enabled = False
        self.fold_open = False
        self.snapshot = []
        self.checked_keys = set()
        self.rows_changed = None
        self.truncated = False
        self._applying = False
        self._rebuild_snapshot = False
        self._redraw_only = False
        self._bound = {}
        self._markers = []
        self._tags = []
        self._items = []
        self._proj_ok = False
        self._canvas_ok = False
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self.refresh)

    def bind(self):
        self.listening = True
        self._bind_project()
        self._bind_canvas()

    def unbind(self):
        self.listening = False
        self.enabled = False
        self._timer.stop()
        self._clear_draw()
        self._unbind_layers()
        self._unbind_canvas()
        self._unbind_project()

    def set_draw(self, on):
        self.enabled = bool(on)
        if self.enabled:
            self.bind()
            self.refresh()
            return
        self._clear_draw()
        if self.listening:
            self.refresh()

    def set_fold_open(self, on):
        self.fold_open = bool(on)
        if self.fold_open:
            self._rebuild_snapshot = True
        self.refresh()

    def apply_checked(self, keys):
        wanted = set()
        for key in keys or []:
            if isinstance(key, (list, tuple)) and len(key) >= 2:
                wanted.add((key[0], int(key[1])))
        self.checked_keys = wanted
        snap_by = {}
        want_by = {}
        for row in self.snapshot:
            lid, fid = row[1], int(row[2])
            snap_by.setdefault(lid, set()).add(fid)
            if (lid, fid) in wanted:
                want_by.setdefault(lid, set()).add(fid)
        self._applying = True
        self._redraw_only = True
        try:
            for lid, snap_fids in snap_by.items():
                layer = QgsProject.instance().mapLayer(lid)
                if layer is None or not _is_line_layer(layer):
                    continue
                try:
                    current = set(int(x) for x in (layer.selectedFeatureIds() or []))
                except Exception:
                    current = set()
                new_sel = (current - snap_fids) | want_by.get(lid, set())
                if new_sel == current:
                    continue
                try:
                    layer.selectByIds(list(new_sel))
                except Exception:
                    pass  # nosec
        finally:
            self._applying = False
        self.refresh()

    def start(self):
        self.bind()
        self.set_draw(True)

    def stop(self):
        self.unbind()

    def _kick(self, *args):
        if self.listening:
            self._timer.start()

    def _kick_selection(self, *args):
        if not self.listening:
            return
        if self._applying:
            self._redraw_only = True
        elif self.fold_open:
            self._rebuild_snapshot = True
        self._timer.start()

    def _bind_project(self):
        if self._proj_ok:
            return
        proj = QgsProject.instance()
        try:
            proj.layersAdded.connect(self._on_layers_added)
            proj.layersWillBeRemoved.connect(self._on_layers_removed)
            self._proj_ok = True
        except Exception:
            self._proj_ok = False
        self._bind_all_layers()

    def _unbind_project(self):
        if not self._proj_ok:
            return
        proj = QgsProject.instance()
        try:
            proj.layersAdded.disconnect(self._on_layers_added)
        except Exception:
            pass  # nosec
        try:
            proj.layersWillBeRemoved.disconnect(self._on_layers_removed)
        except Exception:
            pass  # nosec
        self._proj_ok = False

    def _bind_canvas(self):
        if self._canvas_ok or self.canvas is None:
            return
        for sig in ("extentsChanged", "scaleChanged", "rotationChanged"):
            try:
                getattr(self.canvas, sig).connect(self._kick)
            except Exception:
                pass  # nosec
        self._canvas_ok = True

    def _unbind_canvas(self):
        if not self._canvas_ok or self.canvas is None:
            return
        for sig in ("extentsChanged", "scaleChanged", "rotationChanged"):
            try:
                getattr(self.canvas, sig).disconnect(self._kick)
            except Exception:
                pass  # nosec
        self._canvas_ok = False

    def _bind_all_layers(self):
        for layer in QgsProject.instance().mapLayers().values():
            self._bind_layer(layer)

    def _bind_layer(self, layer):
        if not _is_line_layer(layer):
            return
        lid = layer.id()
        if lid in self._bound:
            return
        try:
            layer.selectionChanged.connect(self._kick_selection)
        except Exception:
            return
        try:
            layer.geometryChanged.connect(self._kick)
        except Exception:
            pass  # nosec
        self._bound[lid] = layer

    def _unbind_layers(self):
        for layer in list(self._bound.values()):
            try:
                layer.selectionChanged.disconnect(self._kick_selection)
            except Exception:
                pass  # nosec
            try:
                layer.geometryChanged.disconnect(self._kick)
            except Exception:
                pass  # nosec
        self._bound.clear()

    def _on_layers_added(self, layers):
        for layer in layers or []:
            self._bind_layer(layer)
        self._kick()

    def _on_layers_removed(self, ids):
        for lid in ids or []:
            layer = self._bound.pop(lid, None)
            if layer is None:
                continue
            try:
                layer.selectionChanged.disconnect(self._kick_selection)
            except Exception:
                pass  # nosec
            try:
                layer.geometryChanged.disconnect(self._kick)
            except Exception:
                pass  # nosec
        if self.fold_open:
            self._rebuild_snapshot = True
        self._kick()

    def _collect(self):
        rows = []
        self.truncated = False
        dst = None
        if self.canvas is not None:
            try:
                dst = self.canvas.mapSettings().destinationCrs()
            except Exception:
                dst = None
        for layer in QgsProject.instance().mapLayers().values():
            if not _is_line_layer(layer):
                continue
            try:
                fids = layer.selectedFeatureIds()
            except Exception:
                continue  # nosec
            if not fids:
                continue
            xform = None
            if dst is not None:
                try:
                    if layer.crs() != dst:
                        xform = QgsCoordinateTransform(
                            layer.crs(), dst, QgsProject.instance()
                        )
                except Exception:
                    xform = None
            req = QgsFeatureRequest().setFilterFids(list(fids))
            for feat in layer.getFeatures(req):
                geom = feat.geometry()
                part = _first_part(geom)
                if part is None:
                    continue
                pts = []
                for pt in part:
                    p = QgsPointXY(pt.x(), pt.y())
                    if xform is not None:
                        try:
                            p = xform.transform(p)
                        except Exception:
                            pass  # nosec
                    pts.append(p)
                rows.append((
                    layer.name(),
                    layer.id(),
                    feat.id(),
                    pts[0],
                    pts[1],
                    pts[2],
                    pts[3],
                    _length_m(layer, geom),
                ))
                if len(rows) >= MAX_LINES:
                    self.truncated = True
                    rows.sort()
                    return rows
        rows.sort()
        return rows

    def _visible_rows(self, rows, checked):
        out = []
        for i, row in enumerate(rows):
            key = (row[1], int(row[2]))
            if checked is not None and key not in checked:
                continue
            out.append((i, row))
        return out

    def _screen(self, pt, toward, pixels):
        if self.canvas is None or pt is None:
            return 8, 8
        try:
            tr = self.canvas.getCoordinateTransform()
            a = tr.transform(pt)
            b = tr.transform(toward) if toward is not None else a
            dx = b.x() - a.x()
            dy = b.y() - a.y()
            dist = math.hypot(dx, dy)
            if dist < 1.0:
                return int(a.x() + 8), int(a.y() - 10)
            ux, uy = dx / dist, dy / dist
            return int(a.x() + ux * pixels), int(a.y() + uy * pixels)
        except Exception:
            return 8, 8

    def _clear_draw(self):
        for mk in self._markers:
            try:
                self.canvas.scene().removeItem(mk)
            except Exception:
                pass  # nosec
            try:
                mk.hide()
            except Exception:
                pass  # nosec
        self._markers = []
        for tag in self._tags:
            try:
                tag.hide()
                tag.setParent(None)
                tag.deleteLater()
            except Exception:
                pass  # nosec
        self._tags = []
        self._items = []

    def _marker(self, pt, color, start):
        mk = QgsVertexMarker(self.canvas)
        mk.setColor(color)
        try:
            mk.setFillColor(QColor(color.red(), color.green(), color.blue(), 80))
        except Exception:
            pass  # nosec
        mk.setIconType(_icon_type("ICON_CIRCLE", 4) if start else _icon_type("ICON_BOX", 3))
        mk.setIconSize(11)
        mk.setPenWidth(2)
        mk.setCenter(pt)
        mk.show()
        self._markers.append(mk)

    def _tag(self, text, color, x, y):
        tag = _Tag(self.canvas)
        tag.apply(text, color)
        try:
            canvas_rect = self.canvas.rect()
            x = max(2, min(x, canvas_rect.width() - tag.width() - 2))
            y = max(2, min(y, canvas_rect.height() - tag.height() - 2))
        except Exception:
            pass  # nosec
        tag.move(x, y)
        tag.show()
        tag.raise_()
        self._tags.append(tag)

    def refresh(self):
        if not self.listening:
            self._clear_draw()
            return
        rebuild = self._rebuild_snapshot
        self._rebuild_snapshot = False
        redraw_only = self._redraw_only
        self._redraw_only = False
        if self.fold_open:
            if rebuild and not self._applying:
                self.snapshot = self._collect()
                self.checked_keys = {(row[1], int(row[2])) for row in self.snapshot}
                cb = self.rows_changed
                if callable(cb):
                    try:
                        cb(self.snapshot)
                    except Exception:
                        pass  # nosec
            rows = self.snapshot
            visible = self._visible_rows(rows, self.checked_keys)
        else:
            rows = self._collect()
            visible = self._visible_rows(rows, None)
        if not self.enabled or self.canvas is None:
            self._clear_draw()
            return
        if not visible:
            self._clear_draw()
            return
        if len(self._markers) != len(visible) * 2:
            self._clear_draw()
        if not self._markers:
            for i, row in visible:
                color = COLORS[i % len(COLORS)]
                self._marker(row[3], color, True)
                self._marker(row[4], color, False)
        else:
            for n, (i, row) in enumerate(visible):
                try:
                    self._markers[n * 2].setCenter(row[3])
                    self._markers[n * 2 + 1].setCenter(row[4])
                except Exception:
                    self._clear_draw()
                    self._redraw_only = redraw_only
                    self._rebuild_snapshot = False
                    return self.refresh()
        groups = {}
        order = []
        for i, row in visible:
            color = COLORS[i % len(COLORS)]
            seq = i + 1
            for kind, pt, toward in (
                ("start", row[3], row[5]),
                ("end", row[4], row[6]),
            ):
                key = _end_key(pt)
                if key is None:
                    continue
                group = groups.get(key)
                if group is None:
                    group = {
                        "pt": pt,
                        "toward": toward,
                        "starts": [],
                        "ends": [],
                        "color": color,
                    }
                    groups[key] = group
                    order.append(key)
                if kind == "start":
                    group["starts"].append(seq)
                else:
                    group["ends"].append(seq)
        while len(self._tags) > len(order):
            tag = self._tags.pop()
            try:
                tag.hide()
                tag.setParent(None)
                tag.deleteLater()
            except Exception:
                pass  # nosec
        while len(self._tags) < len(order):
            self._tag("", COLORS[0], 0, 0)
        for n, key in enumerate(order):
            group = groups[key]
            text = _merged_end_text(group["starts"], group["ends"])
            sx, sy = self._screen(group["pt"], group["toward"], 16)
            try:
                self._tags[n].apply(text, group["color"])
                self._tags[n].move(sx, sy)
                self._tags[n].show()
                self._tags[n].raise_()
            except Exception:
                pass  # nosec


class LineEndsPanel(QWidget):
    def __init__(self, iface, parent=None):
        canvas = None
        host = parent
        try:
            canvas = iface.mapCanvas() if iface is not None else None
        except Exception:
            canvas = None
        if canvas is not None:
            try:
                vp = canvas.viewport()
                if vp is not None:
                    host = vp
                else:
                    host = canvas
            except Exception:
                host = canvas
        super(LineEndsPanel, self).__init__(host)
        self.iface = iface
        self._canvas = host
        self.controller = LineEndsController(iface)
        self._row_keys = []
        self._fitting = False
        self.setObjectName("lineEndsPanel")
        self.setWindowTitle(tr("线标注"))
        try:
            self.setCursor(ARROW)
        except Exception:
            pass  # nosec
        _paint_solid(self, "#eceff1", "#1b1b1b")
        self.setStyleSheet(
            "QWidget#lineEndsPanel { background-color: #eceff1; border: 1px solid #546e7a; }"
            "QWidget#dragHeader { background-color: #cfd8dc; }"
            "QPushButton { min-height: 28px; font-weight: 700; font-size: 14px;"
            " background: #90a4ae; color: #ffffff; border: 2px solid #546e7a; border-radius: 6px; }"
            "QPushButton:hover { background: #78909c; }"
            "QPushButton:checked { background: #1b5e20; color: #fff59d; border: 2px solid #33691e; }"
            "QPushButton#btnOn { min-width: 40px; }"
            "QPushButton#btnFold { min-width: 24px; font-size: 16px; }"
            "QPushButton#miniAll { min-height: 18px; max-height: 20px;"
            " font-size: 12px; font-weight: 700; padding: 0 4px;"
            " background: #2e7d32; color: #fff59d; border: 1px solid #1b5e20; }"
            "QPushButton#miniAll:hover { background: #388e3c; }"
            "QPushButton#miniNone { min-height: 18px; max-height: 20px;"
            " font-size: 12px; font-weight: 700; padding: 0 4px;"
            " background: #546e7a; color: #eceff1; border: 1px solid #37474f; }"
            "QPushButton#miniNone:hover { background: #607d8b; }"
            "QPushButton#btnClose { min-height: 18px; max-height: 18px; min-width: 18px; max-width: 18px;"
            " padding: 0; font-size: 13px; font-weight: 700; border-radius: 3px;"
            " background: #78909c; color: #ffffff; border: 1px solid #546e7a; }"
            "QLabel#titleLab { background: #cfd8dc; color: #1b1b1b; font-size: 12px; font-weight: 700; }"
            "QListWidget { background: #ffffff; color: #1b1b1b; border: 1px solid #90a4ae;"
            " font-size: 12px; font-weight: 700; }"
            "QListWidget::item { min-height: 22px; padding: 2px 6px; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(4)
        header = _DragHeader(self)
        header.setObjectName("dragHeader")
        header.setFixedHeight(22)
        _paint_solid(header, "#cfd8dc", "#1b1b1b")
        head = QHBoxLayout(header)
        head.setContentsMargins(2, 0, 0, 0)
        head.setSpacing(4)
        self.title_label = QLabel(tr("线标注"))
        self.title_label.setObjectName("titleLab")
        title = self.title_label
        _paint_solid(title, "#cfd8dc", "#1b1b1b")
        head.addWidget(title)
        head.addStretch(1)
        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.setToolTip(tr("关闭"))
        self.btn_close.clicked.connect(self.close)
        head.addWidget(self.btn_close)
        root.addWidget(header)
        top = QHBoxLayout()
        top.setSpacing(2)
        self.btn_on = QPushButton(tr("开"))
        self.btn_on.setObjectName("btnOn")
        self.btn_on.setCheckable(True)
        self.btn_on.setChecked(True)
        self.btn_on.setFixedHeight(28)
        self.btn_on.setSizePolicy(qt_attr(QSizePolicy, "Expanding"), qt_attr(QSizePolicy, "Fixed"))
        self.btn_fold = QPushButton("▸")
        self.btn_fold.setObjectName("btnFold")
        self.btn_fold.setCheckable(True)
        self.btn_fold.setChecked(False)
        self.btn_fold.setToolTip(tr("列出所选线及长度。勾选会改 QGIS 选中；名单只在地图/表里重新选线后更新。"))
        self.btn_fold.setFixedHeight(28)
        self.btn_fold.setSizePolicy(qt_attr(QSizePolicy, "Expanding"), qt_attr(QSizePolicy, "Fixed"))
        top.addWidget(self.btn_on, 2)
        top.addWidget(self.btn_fold, 1)
        root.addLayout(top)
        self.pick_box = QWidget()
        _paint_solid(self.pick_box, "#eceff1", "#1b1b1b")
        pick_root = QVBoxLayout(self.pick_box)
        pick_root.setContentsMargins(0, 0, 0, 0)
        pick_root.setSpacing(2)
        tools = QHBoxLayout()
        tools.setSpacing(4)
        self.btn_all = QPushButton(tr("全部"))
        self.btn_all.setObjectName("miniAll")
        self.btn_all.setFixedHeight(20)
        self.btn_all.setSizePolicy(qt_attr(QSizePolicy, "Expanding"), qt_attr(QSizePolicy, "Fixed"))
        self.btn_none = QPushButton(tr("全不选"))
        self.btn_none.setObjectName("miniNone")
        self.btn_none.setFixedHeight(20)
        self.btn_none.setSizePolicy(qt_attr(QSizePolicy, "Expanding"), qt_attr(QSizePolicy, "Fixed"))
        tools.addWidget(self.btn_all, 1)
        tools.addWidget(self.btn_none, 1)
        pick_root.addLayout(tools)
        self.list = LinePickList()
        self.list.setSelectionMode(NO_SELECTION or QAbstractItemView.SelectionMode.NoSelection)
        try:
            self.list.setFocusPolicy(NO_FOCUS)
        except Exception:
            pass  # nosec
        self.list.setHorizontalScrollBarPolicy(SCROLL_OFF)
        self.list.setVerticalScrollBarPolicy(SCROLL_IF)
        try:
            self.list.setTextElideMode(ELIDE_NONE)
        except Exception:
            pass  # nosec
        pick_root.addWidget(self.list)
        self.pick_box.hide()
        root.addWidget(self.pick_box)
        self.btn_on.toggled.connect(self._on_toggled)
        self.btn_fold.toggled.connect(self._on_fold)
        self.btn_all.clicked.connect(lambda: self._set_all_checked(True))
        self.btn_none.clicked.connect(lambda: self._set_all_checked(False))
        self.list.itemChanged.connect(self._on_item_changed)
        try:
            self.setAttribute(_qt_flag("WA_DeleteOnClose"), True)
        except Exception:
            pass  # nosec
        self.controller.rows_changed = self._sync_list
        self._fit_window(False)
        if self._canvas is not None:
            self._canvas.installEventFilter(self)
        self.move(8, 8)
        self._clamp()
        self.controller.start()
        self._retranslate()
        subscribe(self, self._retranslate)

    def _retranslate(self, *_args):
        self.setWindowTitle(tr("线标注"))
        self.title_label.setText(tr("线标注"))
        self.btn_close.setToolTip(tr("关闭"))
        self.btn_on.setText(tr("开") if self.btn_on.isChecked() else tr("关"))
        self.btn_fold.setToolTip(tr("列出所选线及长度。勾选会改 QGIS 选中；名单只在地图/表里重新选线后更新。"))
        self.btn_all.setText(tr("全部"))
        self.btn_none.setText(tr("全不选"))

    def _on_toggled(self, on):
        self.btn_on.setText(tr("开") if on else tr("关"))
        self.controller.set_draw(on)

    def _on_fold(self, on):
        self.btn_fold.setText("▾" if on else "▸")
        self.pick_box.setVisible(on)
        self.controller.set_fold_open(on)
        self._fit_window(on)

    def _sync_list(self, rows):
        keys = [(row[1], int(row[2])) for row in rows]
        self._row_keys = keys
        self.list.blockSignals(True)
        try:
            self.list.clear()
            for i, row in enumerate(rows):
                item = QListWidgetItem(tr("起点%d  %s") % (i + 1, _fmt_len(row[7])))
                item.setFlags(item.flags() | ITEM_USER_CHECKABLE)
                item.setData(USER_ROLE, (row[1], int(row[2])))
                item.setCheckState(CHECKED)
                color = COLORS[i % len(COLORS)]
                item.setForeground(color)
                self.list.addItem(item)
            if getattr(self.controller, "truncated", False):
                note = QListWidgetItem(tr("只标前 %d 条，其余未显示") % MAX_LINES)
                note.setFlags(Qt.ItemFlag.NoItemFlags)
                self.list.addItem(note)
        finally:
            self.list.blockSignals(False)
        if self.btn_fold.isChecked():
            self._fit_window(True)

    def _checked_keys(self):
        keys = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it is None or it.checkState() != CHECKED:
                continue
            key = it.data(USER_ROLE)
            if isinstance(key, (list, tuple)) and len(key) >= 2:
                keys.append((key[0], int(key[1])))
        return keys

    def _set_all_checked(self, on):
        self.list.blockSignals(True)
        try:
            state = CHECKED if on else UNCHECKED
            for i in range(self.list.count()):
                it = self.list.item(i)
                if it is not None:
                    it.setCheckState(state)
        finally:
            self.list.blockSignals(False)
        self.controller.apply_checked(self._checked_keys())

    def _on_item_changed(self, item):
        if item is None:
            return
        self.controller.apply_checked(self._checked_keys())

    def _fit_window(self, opened):
        if self._fitting:
            return
        self._fitting = True
        try:
            n = self.list.count()
            if opened:
                self.pick_box.show()
                row_h = self.list.sizeHintForRow(0) if n else 22
                if row_h is None or row_h <= 0:
                    row_h = 22
                list_h = (n * row_h + 4) if n else 0
                if list_h > MAX_LIST_PX:
                    list_h = MAX_LIST_PX
                    self.list.setVerticalScrollBarPolicy(SCROLL_IF)
                else:
                    self.list.setVerticalScrollBarPolicy(SCROLL_OFF)
                self.list.setFixedHeight(max(list_h, 0))
                width = CLOSED_W
                try:
                    fm = self.list.fontMetrics()
                    for i in range(n):
                        item = self.list.item(i)
                        if item is None:
                            continue
                        need = fm.boundingRect(item.text()).width() + 72
                        if need > width:
                            width = need
                except Exception:
                    pass  # nosec
                try:
                    if self._canvas is not None:
                        limit = max(CLOSED_W, self._canvas.width() - 16)
                        if width > limit:
                            width = limit
                except Exception:
                    pass  # nosec
                height = CLOSED_H + 22 + max(list_h, 0)
                self.setFixedSize(width, height)
            else:
                self.pick_box.hide()
                self.list.setFixedHeight(0)
                self.setFixedSize(CLOSED_W, CLOSED_H)
            self._clamp()
        finally:
            self._fitting = False

    def eventFilter(self, obj, event):
        if obj is self._canvas:
            et = event.type()
            try:
                resize = QEvent.Type.Resize
            except AttributeError:
                resize = QEvent.Type.Resize
            if et == resize:
                self._clamp()
        return False

    def _clamp(self):
        host = self._canvas
        if host is None:
            return
        try:
            r = host.rect()
            x = min(max(0, self.x()), max(0, r.width() - self.width()))
            y = min(max(0, self.y()), max(0, r.height() - self.height()))
            if x != self.x() or y != self.y():
                self.move(x, y)
        except Exception:
            pass  # nosec

    def closeEvent(self, event):
        try:
            if self._canvas is not None:
                self._canvas.removeEventFilter(self)
        except Exception:
            pass  # nosec
        try:
            self.controller.rows_changed = None
            self.controller.stop()
        except Exception:
            pass  # nosec
        global _PANEL
        if _PANEL is self:
            _PANEL = None
        super(LineEndsPanel, self).closeEvent(event)


def open_line_ends(iface):
    global _PANEL
    panel = _PANEL
    try:
        if panel is not None:
            panel.windowTitle()
    except Exception:
        panel = None
        _PANEL = None
    if panel is None:
        panel = LineEndsPanel(iface)
        _PANEL = panel
    panel.show()
    panel.raise_()
    try:
        panel._clamp()
    except Exception:
        pass  # nosec
    if not panel.btn_on.isChecked():
        panel.btn_on.setChecked(True)
    else:
        panel.controller.start()
    return panel


def close_line_ends():
    global _PANEL
    panel = _PANEL
    _PANEL = None
    if panel is None:
        return
    try:
        panel.controller.stop()
    except Exception:
        pass  # nosec
    try:
        panel.close()
    except Exception:
        pass  # nosec


def make_action(iface):
    tr("线标注")
    tr("在所选线的两端标出起点和终点，并显示长度。不改图层数据。")
    return make_toolbar_button(
        iface,
        "lpt:line_ends",
        "LayersPanelToolsLineEnds",
        "线标注",
        "在所选线的两端标出起点和终点，并显示长度。不改图层数据。",
        load_icon("line_ends"),
        lambda: open_line_ends(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsLineEndsMenu",
        "线标注",
        "在所选线的两端标出起点和终点，并显示长度。不改图层数据。",
        load_icon("line_ends"),
        lambda: open_line_ends(iface),
    )
