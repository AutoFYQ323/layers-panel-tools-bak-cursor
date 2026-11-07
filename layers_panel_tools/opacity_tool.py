# -*- coding: utf-8 -*-
"""One slider for the whole-layer opacity of every layer, or of the selection."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from .buttons import enum_int, make_menu_action as menu_action, make_toolbar_button, qt_attr
from .plugin_settings import plugin_qsettings, set_value
from .i18n import apply_direction, localize_button_box, subscribe, tr
from .icons import load_icon
from .scope import layer_tree_view, layers_for_scope, tell

_SCOPE_KEY = "opacity_scope"
_dialog = None


def make_action(iface):
    tr("透明度")
    tr("调节图层的整体不透明度")
    return make_toolbar_button(
        iface,
        "lpt:opacity",
        "LayersPanelToolsOpacity",
        "透明度",
        "调节图层的整体不透明度",
        load_icon("opacity"),
        lambda: open_opacity(iface),
    )


def make_menu_action(iface):
    return menu_action(
        iface,
        "LayersPanelToolsOpacityMenu",
        "透明度",
        "调节图层的整体不透明度",
        load_icon("opacity"),
        lambda: open_opacity(iface),
    )


def open_opacity(iface):
    global _dialog
    if _dialog is None:
        _dialog = OpacityDialog(iface, iface.mainWindow())
    else:
        _dialog.iface = iface
        _dialog.show_current()
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


def close_opacity():
    global _dialog
    dialog = _dialog
    _dialog = None
    if dialog is None:
        return
    try:
        dialog.close()
        dialog.deleteLater()
    except RuntimeError:
        pass


def saved_scope():
    ps = plugin_qsettings()
    value = str(ps.value(_SCOPE_KEY, "all") or "all")
    if value not in ("all", "selected"):
        return "all"
    return value


class OpacityDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setObjectName("LayersPanelToolsOpacityDialog")
        self.resize(420, 180)
        self._blocked = True
        self._listening = False

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.lbl_scope = QLabel()
        self.scope = QComboBox()
        self.scope.currentIndexChanged.connect(self._on_scope)
        row.addWidget(self.lbl_scope)
        row.addWidget(self.scope, 1)
        layout.addLayout(row)

        slider_row = QHBoxLayout()
        self.slider = QSlider(qt_attr(Qt, "Horizontal"))
        self.slider.setRange(0, 100)
        self.spin = QSpinBox()
        self.spin.setRange(0, 100)
        self.spin.setSuffix("%")
        self.slider.valueChanged.connect(self._on_slider)
        self.spin.valueChanged.connect(self._on_spin)
        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(self.spin)
        layout.addLayout(slider_row)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        close_flag = qt_attr(QDialogButtonBox, "Close")
        self.buttons = QDialogButtonBox(close_flag)
        self.buttons.rejected.connect(self.close)
        try:
            self.buttons.button(close_flag).clicked.connect(self.close)
        except Exception:
            pass  # nosec
        layout.addWidget(self.buttons)

        self._watched = None
        self._blocked = False
        self.retranslate()
        self.show_current()
        subscribe(self, self.retranslate)
        self._listening = True

    def showEvent(self, event):
        self._watch_selection()
        super().showEvent(event)

    def _watch_selection(self):
        view = layer_tree_view(self.iface)
        model = view.selectionModel() if view is not None else None
        if model is None or model is self._watched:
            return
        self._unwatch_selection()
        try:
            model.selectionChanged.connect(self._on_selection)
            self._watched = model
        except Exception:
            self._watched = None

    def _unwatch_selection(self):
        model = self._watched
        self._watched = None
        if model is None:
            return
        try:
            model.selectionChanged.disconnect(self._on_selection)
        except Exception:
            pass  # nosec

    def _on_selection(self, *_args):
        if (self.scope.currentData() or "all") == "selected" and self.isVisible():
            self.show_current()

    def show_current(self):
        self._fill_scope(saved_scope())
        layers = layers_for_scope(self.iface, self.scope.currentData() or "all")
        values = []
        for layer in layers:
            try:
                values.append(int(round(float(layer.opacity()) * 100)))
            except Exception:
                continue  # nosec
        self._blocked = True
        if values:
            self.slider.setValue(values[0])
            self.spin.setValue(values[0])
        self._blocked = False
        self._paint_hint(len(set(values)) > 1, not layers, len(layers))

    def retranslate(self, *_args):
        self.setWindowTitle(tr("透明度"))
        self.lbl_scope.setText(tr("范围"))
        self.note.setText(tr("这是图层的整体不透明度，不是符号里的填充透明度。"))
        self.scope.setToolTip(tr("已选图层包含选中组里面的图层。"))
        localize_button_box(self.buttons)
        current = self.scope.currentData() or saved_scope()
        self._fill_scope(current)
        apply_direction(self)
        self._paint_hint(
            self.hint.property("lpt_mixed"),
            self.hint.property("lpt_empty"),
            enum_int(self.hint.property("lpt_count"), 0),
        )

    def closeEvent(self, event):
        self._unwatch_selection()
        super().closeEvent(event)

    def _fill_scope(self, current):
        self._blocked = True
        self.scope.blockSignals(True)
        self.scope.clear()
        self.scope.addItem(tr("全部图层"), "all")
        self.scope.addItem(tr("已选图层"), "selected")
        index = self.scope.findData(current)
        self.scope.setCurrentIndex(index if index >= 0 else 0)
        self.scope.blockSignals(False)
        self._blocked = False

    def _on_scope(self, *_args):
        if self._blocked or self.scope.signalsBlocked():
            return
        set_value(_SCOPE_KEY, self.scope.currentData() or "all")
        self.show_current()

    def _on_slider(self, value):
        if self._blocked:
            return
        self._blocked = True
        self.spin.setValue(value)
        self._blocked = False
        self._apply(value)

    def _on_spin(self, value):
        if self._blocked:
            return
        self._blocked = True
        self.slider.setValue(value)
        self._blocked = False
        self._apply(value)

    def _apply(self, value):
        scope = self.scope.currentData() or "all"
        layers = layers_for_scope(self.iface, scope)
        if scope == "selected" and not layers:
            if not self.hint.property("lpt_empty"):
                tell(self.iface, tr("透明度"), tr("图层面板里没有选中图层。"), warning=True)
            self._paint_hint(False, True, 0)
            return
        fraction = max(0.0, min(1.0, float(value) / 100.0))
        for layer in layers:
            try:
                layer.setOpacity(fraction)
                layer.triggerRepaint()
            except Exception:
                continue  # nosec
        try:
            self.iface.mapCanvas().refresh()
        except Exception:
            pass  # nosec
        self._paint_hint(False, not layers, len(layers))

    def _paint_hint(self, mixed, empty, count=0):
        self.hint.setProperty("lpt_mixed", bool(mixed))
        self.hint.setProperty("lpt_empty", bool(empty))
        self.hint.setProperty("lpt_count", int(count or 0))
        if empty:
            self.hint.setText(tr("没有可调节的图层。"))
        elif mixed:
            self.hint.setText(
                tr("作用于 %d 个图层。") % count
                + " "
                + tr("当前这些图层的不透明度不一致，拖动后会收成同一个值。")
            )
        else:
            self.hint.setText(tr("作用于 %d 个图层。") % count)
