# -*- coding: utf-8 -*-
"""Batch rename layers: find/replace, regex, prefix, suffix, numbering, case, with live preview."""

import re

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
)

from qgis.core import QgsProject

from .buttons import make_menu_action as build_menu_action, make_toolbar_button
from .i18n import apply_direction, tr, subscribe
from .icons import load_icon
from .qt_compat import qt_attr, run_dialog, user_role
from .scope import selected_layers

_DIALOG = None


def make_action(iface):
    tr("批量重命名")
    tr("查找替换、前后缀、序号、大小写批量改图层名，先预览再应用")
    return make_toolbar_button(
        iface,
        "lpt:rename",
        "LayersPanelToolsRename",
        "批量重命名",
        "查找替换、前后缀、序号、大小写批量改图层名，先预览再应用",
        load_icon("rename"),
        lambda: open_rename(iface),
    )


def make_menu_action(iface):
    return build_menu_action(
        iface,
        "LayersPanelToolsRenameMenu",
        "批量重命名",
        "查找替换、前后缀、序号、大小写批量改图层名，先预览再应用",
        load_icon("rename"),
        lambda: open_rename(iface),
    )


def close_rename():
    global _DIALOG
    if _DIALOG is not None:
        try:
            _DIALOG.close()
        except RuntimeError:
            pass
    _DIALOG = None


def open_rename(iface):
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = RenameDialog(iface)
    _DIALOG.refresh()
    run_dialog(_DIALOG)


def _transform(name, rules, index):
    text = name
    find = rules["find"]
    if find:
        try:
            if rules["regex"]:
                text = re.sub(find, rules["replace"], text)
            else:
                text = text.replace(find, rules["replace"])
        except re.error:
            pass
    if rules["prefix"]:
        text = rules["prefix"] + text
    if rules["suffix"]:
        text = text + rules["suffix"]
    if rules["number"]:
        text = "%s%s" % (text, str(rules["number_start"] + index).zfill(rules["number_width"]))
    mode = rules["case"]
    if mode == "upper":
        text = text.upper()
    elif mode == "lower":
        text = text.lower()
    elif mode == "title":
        text = text.title()
    return text


class RenameDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle(tr("批量重命名"))
        layout = QVBoxLayout(self)
        self.hint = QLabel()
        layout.addWidget(self.hint)
        grid = QGridLayout()
        self.lbl_find = QLabel()
        self.edit_find = QLineEdit()
        grid.addWidget(self.lbl_find, 0, 0)
        grid.addWidget(self.edit_find, 0, 1)
        self.lbl_replace = QLabel()
        self.edit_replace = QLineEdit()
        grid.addWidget(self.lbl_replace, 1, 0)
        grid.addWidget(self.edit_replace, 1, 1)
        self.chk_regex = QCheckBox()
        grid.addWidget(self.chk_regex, 1, 2)
        self.lbl_prefix = QLabel()
        self.edit_prefix = QLineEdit()
        grid.addWidget(self.lbl_prefix, 2, 0)
        grid.addWidget(self.edit_prefix, 2, 1)
        self.lbl_suffix = QLabel()
        self.edit_suffix = QLineEdit()
        grid.addWidget(self.lbl_suffix, 3, 0)
        grid.addWidget(self.edit_suffix, 3, 1)
        self.chk_number = QCheckBox()
        self.spin_start = QSpinBox()
        self.spin_start.setRange(0, 999999)
        self.spin_width = QSpinBox()
        self.spin_width.setRange(0, 5)
        self.spin_width.setValue(2)
        box = QHBoxLayout()
        box.addWidget(self.chk_number)
        box.addWidget(self.spin_start)
        box.addWidget(self.spin_width)
        grid.addLayout(box, 4, 1)
        self.lbl_case = QLabel()
        self.combo_case = QComboBox()
        grid.addWidget(self.lbl_case, 5, 0)
        grid.addWidget(self.combo_case, 5, 1)
        layout.addLayout(grid)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.box = QDialogButtonBox()
        self.btn_all = self.box.addButton(tr("全选"), qt_attr(QDialogButtonBox, "ActionRole"))
        self.btn_none = self.box.addButton(tr("全不选"), qt_attr(QDialogButtonBox, "ActionRole"))
        self.run_btn = self.box.addButton(tr("应用"), qt_attr(QDialogButtonBox, "ActionRole"))
        cancel_flag = qt_attr(QDialogButtonBox, "Cancel")
        self.box.addButton(cancel_flag)
        self.btn_all.clicked.connect(lambda: self._check_all(True))
        self.btn_none.clicked.connect(lambda: self._check_all(False))
        self.run_btn.clicked.connect(self._apply)
        self.box.rejected.connect(self.reject)
        layout.addWidget(self.box)
        for widget in (
            self.edit_find,
            self.edit_replace,
            self.edit_prefix,
            self.edit_suffix,
        ):
            widget.textChanged.connect(self.refresh)
        self.chk_regex.stateChanged.connect(self.refresh)
        self.chk_number.stateChanged.connect(self.refresh)
        self.spin_start.valueChanged.connect(self.refresh)
        self.spin_width.valueChanged.connect(self.refresh)
        self.combo_case.currentIndexChanged.connect(self.refresh)
        apply_direction(self)
        subscribe(self, self._retranslate)
        self._retranslate()

    def _retranslate(self):
        self.setWindowTitle(tr("批量重命名"))
        self.hint.setText(tr("左侧改规则，列表实时预览；勾选的图层才会被改名。"))
        self.lbl_find.setText(tr("查找"))
        self.lbl_replace.setText(tr("替换为"))
        self.lbl_prefix.setText(tr("加前缀"))
        self.lbl_suffix.setText(tr("加后缀"))
        self.lbl_case.setText(tr("大小写"))
        self.chk_regex.setText(tr("按正则"))
        self.chk_number.setText(tr("加序号（起始 / 位数）"))
        self.combo_case.clear()
        self.combo_case.addItem(tr("不变"))
        self.combo_case.addItem(tr("全大写"))
        self.combo_case.addItem(tr("全小写"))
        self.combo_case.addItem(tr("词首大写"))
        self.btn_all.setText(tr("全选"))
        self.btn_none.setText(tr("全不选"))
        self.run_btn.setText(tr("应用"))

    def _rules(self):
        return {
            "find": self.edit_find.text(),
            "replace": self.edit_replace.text(),
            "regex": self.chk_regex.isChecked(),
            "prefix": self.edit_prefix.text(),
            "suffix": self.edit_suffix.text(),
            "number": self.chk_number.isChecked(),
            "number_start": int(self.spin_start.value()),
            "number_width": int(self.spin_width.value()),
            "case": ("upper", "lower", "title")[max(0, self.combo_case.currentIndex() - 1)] if self.combo_case.currentIndex() > 0 else "keep",
        }

    def refresh(self):
        keep_checked = {}
        for index in range(self.list.count()):
            item = self.list.item(index)
            try:
                from qgis.PyQt.QtCore import Qt

                keep_checked[item.data(user_role())] = item.checkState() == Qt.Checked
            except Exception:
                pass  # nosec
        if not keep_checked:
            try:
                selected = set()
                for layer in selected_layers(self.iface):
                    selected.add(layer.id())
            except Exception:
                selected = set()
            for layer in QgsProject.instance().mapLayers().values():
                keep_checked[layer.id()] = not selected or layer.id() in selected
        self.list.clear()
        rules = self._rules()
        # 序号只按「列表顺序」走，这样预览与下面 _apply 的结果一定一致。
        number_index = 0
        for layer in QgsProject.instance().mapLayers().values():
            new_name = _transform(layer.name(), rules, number_index)
            if rules["number"]:
                number_index += 1
            text = "%s  →  %s" % (layer.name(), new_name) if new_name != layer.name() else layer.name()
            item = QListWidgetItem(text)
            item.setData(user_role(), layer.id())
            try:
                from qgis.PyQt.QtCore import Qt

                item.setCheckState(Qt.Checked if keep_checked.get(layer.id()) else Qt.Unchecked)
            except Exception:
                pass  # nosec
            self.list.addItem(item)

    def _check_all(self, on):
        from qgis.PyQt.QtCore import Qt

        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(user_role()):
                item.setCheckState(Qt.Checked if on else Qt.Unchecked)

    def _apply(self):
        from qgis.PyQt.QtCore import Qt

        rules = self._rules()
        # 按列表行顺序取图层并编号，保证与预览所见一致。
        plan = []
        number_index = 0
        for index in range(self.list.count()):
            item = self.list.item(index)
            layer_id = item.data(user_role())
            if not layer_id:
                continue
            try:
                checked = item.checkState() == Qt.Checked
            except Exception:
                checked = False
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is None:
                continue
            new_name = _transform(layer.name(), rules, number_index)
            if rules["number"]:
                number_index += 1
            if checked and new_name and new_name != layer.name():
                plan.append((layer, new_name))
        for layer, new_name in plan:
            try:
                layer.setName(new_name)
            except Exception:
                pass  # nosec
        self.refresh()
