# -*- coding: utf-8 -*-
"""Show, hide, reorder, and choose a row for the Layers panel toolbar."""

from qgis.PyQt.QtCore import QEvent, QObject, QRectF, QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPen, QPixmap

from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QKeySequenceEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QDialogButtonBox,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
)

from .button_help import help_msgid_for, title_tip
from .buttons import report
from .check_i18n import language_endonym, offered_languages
from .i18n import apply_direction, current_language, set_language, tr, subscribe
from . import subcommands
from .order_logic import MAX_ROWS, SEP_PREFIX
from .settings_store import load_shortcuts, load_titles
from .qt_compat import accepted, enum_int, qt_attr, run_dialog, user_role
from .toolbar_host import plain_title


_ID = user_role()
_KIND = user_role(1)
_MSGID = user_role(2)
_NATIVE = user_role(3)
_ROW = user_role(4)
_HELP_MSGID = user_role(5)
_TITLE = user_role(6)
_HELP = user_role(7)
_SHORTCUT = user_role(8)
_PARENT = user_role(9)


def _event_type(name):
    return enum_int(qt_attr(QEvent, name))


class _ComboPlacer(QObject):
    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog
        self._types = {_event_type("Resize"), _event_type("Show")}

    def eventFilter(self, watched, event):
        kind = enum_int(event.type())
        if kind < 0:
            return False
        if kind in self._types:
            self._dialog._place_combos()
        return False


_BUTTON_QSS = """
QToolButton {
    border: 1px solid #e4e7ee;
    border-radius: 8px;
    background: #ffffff;
    padding: 0px;
}
QToolButton:hover {
    background: #f3f6fb;
    border-color: #c5d0e0;
}
QToolButton:pressed {
    background: #e7eef8;
}
QToolButton:disabled {
    background: #f7f7f8;
    border-color: #ececec;
}
QToolButton::menu-indicator {
    image: none;
    width: 0px;
    height: 0px;
}
"""

_LANGUAGE_MARK = {"zh": "CN", "en": "EN", "es": "ES", "fr": "FR", "ar": "AR"}


class _ShortcutEdit(QKeySequenceEdit):
    """按 Backspace 或 Delete 清空已配置的快捷键；带修饰键的组合照常录制。"""

    def keyPressEvent(self, event):
        try:
            key = enum_int(event.key(), -1)
            mods = enum_int(event.modifiers(), 0)
        except Exception:
            super().keyPressEvent(event)
            return
        plain_backspace = enum_int(qt_attr(Qt, "Key_Backspace"), -1)
        plain_delete = enum_int(qt_attr(Qt, "Key_Delete"), -1)
        if mods == 0 and key in (plain_backspace, plain_delete):
            self.clear()
            return
        super().keyPressEvent(event)


def _pen(color, width):
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    cap = getattr(Qt, "RoundCap", None)
    join = getattr(Qt, "RoundJoin", None)
    if cap is None:
        cap = Qt.PenCapStyle.RoundCap
        join = Qt.PenJoinStyle.RoundJoin
    pen.setCapStyle(cap)
    pen.setJoinStyle(join)
    return pen


def _paint_icon(draw):
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    try:
        hint = getattr(QPainter, "Antialiasing", None)
        if hint is None:
            hint = QPainter.RenderHint.Antialiasing
        painter.setRenderHint(hint, True)
        draw(painter)
    finally:
        painter.end()
    return QIcon(pixmap)


def _arrow_icon(down):
    def draw(painter):
        painter.setPen(_pen("#2f6fed", 2.4))
        if down:
            painter.drawLine(16, 8, 16, 23)
            painter.drawLine(16, 23, 9, 16)
            painter.drawLine(16, 23, 23, 16)
        else:
            painter.drawLine(16, 24, 16, 9)
            painter.drawLine(16, 9, 9, 16)
            painter.drawLine(16, 9, 23, 16)
    return _paint_icon(draw)


def _separator_icon(remove):
    def draw(painter):
        painter.setPen(_pen("#d4554c" if remove else "#1aa58a", 2.2))
        painter.drawLine(6, 10, 18, 10)
        painter.drawLine(6, 16, 18, 16)
        painter.drawLine(6, 22, 18, 22)
        if remove:
            painter.drawLine(21, 12, 28, 20)
            painter.drawLine(28, 12, 21, 20)
        else:
            painter.drawLine(24, 11, 24, 21)
            painter.drawLine(19, 16, 29, 16)
    return _paint_icon(draw)


def _reset_icon():
    def draw(painter):
        painter.setPen(_pen("#e39b2b", 2.4))
        painter.drawArc(QRectF(8, 8, 16, 16), 40 * 16, 280 * 16)
        painter.drawLine(22, 9, 26, 8)
        painter.drawLine(22, 9, 21, 13)
    return _paint_icon(draw)


def _help_icon():
    def draw(painter):
        painter.setBrush(QColor("#2f6fed"))
        painter.setPen(QPen(Qt.GlobalColor.transparent))
        painter.drawEllipse(QRectF(7, 7, 18, 18))
        painter.setPen(QPen(QColor("#ffffff")))
        font = QFont()
        font.setPixelSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(7, 7, 18, 18), enum_int(qt_attr(Qt, "AlignCenter"), 0x84), "?")
    return _paint_icon(draw)


def _ok_icon():
    def draw(painter):
        painter.setPen(_pen("#2f9e44", 2.6))
        painter.drawLine(8, 17, 14, 23)
        painter.drawLine(14, 23, 24, 10)

    return _paint_icon(draw)


def _cancel_icon():
    def draw(painter):
        painter.setPen(_pen("#d4554c", 2.6))
        painter.drawLine(10, 10, 22, 22)
        painter.drawLine(22, 10, 10, 22)

    return _paint_icon(draw)


def _language_icon(code):
    mark = _LANGUAGE_MARK.get(code) or "A"

    def draw(painter):
        painter.setPen(QPen(QColor("#2f6fed")))
        font = QFont()
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, 32, 32), enum_int(qt_attr(Qt, "AlignCenter"), 0x84), mark)

    return _paint_icon(draw)


def _icon_button(button):
    button.setFixedSize(40, 40)
    button.setIconSize(QSize(24, 24))
    button.setToolButtonStyle(qt_attr(Qt, "ToolButtonIconOnly"))
    button.setStyleSheet(_BUTTON_QSS)
    button.setAutoRaise(False)


def _language_text(code):
    """语言名用各自语言的写法（endonym），不随界面语言翻译。"""
    return language_endonym(code)


class HelpDialog(QDialog):
    def __init__(self, lines, parent=None):
        super().__init__(parent)
        self.setObjectName("LayersPanelToolsHelpDialog")
        self.resize(520, 480)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setPlainText("\n\n".join(lines))
        layout.addWidget(self.browser, 1)
        box = QDialogButtonBox(qt_attr(QDialogButtonBox, "Close"))
        box.rejected.connect(self.reject)
        close_btn = box.button(qt_attr(QDialogButtonBox, "Close"))
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(box)
        self._box = box
        self.retranslate()

    def retranslate(self, *_args):
        self.setWindowTitle(tr("图层面板工具帮助"))
        self._box.button(qt_attr(QDialogButtonBox, "Close")).setText(tr("关闭"))
        apply_direction(self)

    def exec_dialog(self):
        return accepted(run_dialog(self))


class SettingsDialog(QDialog):
    def __init__(self, rows, default_rows, parent=None):
        super().__init__(parent)
        self.setObjectName("LayersPanelToolsSettingsDialog")
        self.resize(550, 550)
        self._defaults = list(default_rows)
        self._languages = offered_languages()
        self._listening = False
        self._combos = {}
        self._title_edits = {}
        self._shortcut_edits = {}
        self._shortcuts = dict(load_shortcuts())
        self._expanded = set()
        self._expand_buttons = {}
        self._titles_all = load_titles()
        self._moving = False

        layout = QVBoxLayout(self)
        self._head = QHBoxLayout()
        self._head.setContentsMargins(0, 0, 0, 0)
        self._head.setSpacing(0)
        self.lbl_buttons = QLabel()
        self.lbl_row = QLabel()
        self.lbl_row.setAlignment(qt_attr(Qt, "AlignCenter"))
        self.lbl_title = QLabel()
        self.lbl_title.setAlignment(qt_attr(Qt, "AlignCenter"))
        self.lbl_shortcut = QLabel()
        self.lbl_shortcut.setAlignment(qt_attr(Qt, "AlignCenter"))
        self._head.addWidget(self.lbl_buttons, 50)
        self._head.addWidget(self.lbl_row, 10)
        self._head.addWidget(self.lbl_title, 27)
        self._head.addWidget(self.lbl_shortcut, 13)
        layout.addLayout(self._head)

        self.list = QListWidget()
        self.list.setDragDropMode(qt_attr(QAbstractItemView, "InternalMove"))
        self.list.setSelectionMode(qt_attr(QAbstractItemView, "SingleSelection"))
        self.list.currentItemChanged.connect(lambda *_args: self._update_delete())
        self.list.verticalScrollBar().valueChanged.connect(self._place_combos)
        self._placer = _ComboPlacer(self)
        self.list.viewport().installEventFilter(self._placer)
        self.list.model().rowsMoved.connect(self._after_rows_moved)
        layout.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setSpacing(0)
        self.btn_lang = QToolButton()
        self.lang_menu = QMenu(self.btn_lang)
        try:
            menu_font = self.lang_menu.font()
            point = menu_font.pointSize()
            if point > 0:
                menu_font.setPointSize(point + 2)
                self.lang_menu.setFont(menu_font)
        except Exception:
            pass  # nosec
        self.btn_lang.setMenu(self.lang_menu)
        self.btn_lang.setPopupMode(qt_attr(QToolButton, "InstantPopup"))
        self.btn_help = QToolButton()
        self.btn_help.setIcon(_help_icon())
        self.btn_up = QToolButton()
        self.btn_down = QToolButton()
        self.btn_sep = QToolButton()
        self.btn_delete = QToolButton()
        self.btn_reset = QToolButton()
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down.clicked.connect(lambda: self._move(1))
        self.btn_sep.clicked.connect(self._insert_sep)
        self.btn_delete.clicked.connect(self._delete_sep)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_help.clicked.connect(self._show_help)
        self.btn_up.setIcon(_arrow_icon(False))
        self.btn_down.setIcon(_arrow_icon(True))
        self.btn_sep.setIcon(_separator_icon(False))
        self.btn_delete.setIcon(_separator_icon(True))
        self.btn_reset.setIcon(_reset_icon())
        self.btn_ok = QToolButton()
        self.btn_cancel = QToolButton()
        self.btn_ok.setIcon(_ok_icon())
        self.btn_cancel.setIcon(_cancel_icon())
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        buttons = (
            self.btn_lang,
            self.btn_help,
            self.btn_up,
            self.btn_down,
            self.btn_sep,
            self.btn_delete,
            self.btn_reset,
            self.btn_ok,
            self.btn_cancel,
        )
        for index, button in enumerate(buttons):
            if index:
                row.addStretch(1)
            _icon_button(button)
            row.addWidget(button)
        layout.addLayout(row)

        for item in rows:
            self._add_row(item)
        self._update_delete()
        self.retranslate()
        subscribe(self, self.retranslate)
        self._listening = True

    def exec_dialog(self):
        return accepted(run_dialog(self))

    def showEvent(self, event):
        super().showEvent(event)
        self._place_combos()

    def result_order(self):
        self._sync_rows()
        order = []
        hidden = []
        rows = {}
        for index in range(self.list.count()):
            item = self.list.item(index)
            button_id = item.data(_ID)
            kind = item.data(_KIND)
            if kind == "sub":
                continue
            order.append(button_id)
            rows[button_id] = self._item_row(item)
            if kind in ("native", "plugin") and enum_int(item.checkState(), 2) == 0:
                hidden.append(button_id)
        titles = {}
        shortcuts = {}
        for index in range(self.list.count()):
            item = self.list.item(index)
            button_id = item.data(_ID)
            text = str(item.data(_TITLE) or "").strip()
            if text:
                titles[button_id] = text
            if item.data(_KIND) in ("plugin", "settings", "sub"):
                seq = str(item.data(_SHORTCUT) or "").strip()
                if seq:
                    shortcuts[button_id] = seq
        return order, hidden, rows, titles, shortcuts

    def retranslate(self, *_args):
        self.setWindowTitle(tr("图层面板工具设置"))
        self.lbl_buttons.setText(tr("按钮"))
        self.lbl_title.setText(tr("自定义标题"))
        self.lbl_shortcut.setText(tr("快捷键"))
        self.lbl_row.setText(tr("行"))
        self.btn_lang.setText("")
        self.btn_lang.setToolTip(tr("语言"))
        self.btn_help.setToolTip(tr("帮助"))
        self.btn_up.setText("")
        self.btn_up.setToolTip(tr("上移"))
        self.btn_down.setText("")
        self.btn_down.setToolTip(tr("下移"))
        self.btn_sep.setText("")
        self.btn_sep.setToolTip(tr("插入分隔线"))
        self.btn_delete.setText("")
        self.btn_delete.setToolTip(tr("删除分隔线"))
        self.btn_reset.setText("")
        self.btn_reset.setToolTip(tr("恢复默认"))
        self.btn_ok.setText("")
        self.btn_ok.setToolTip(tr("确定"))
        self.btn_cancel.setText("")
        self.btn_cancel.setToolTip(tr("取消"))
        tr("在工具条上把相邻按钮隔开。")
        tr("显示、隐藏和排列图层面板上的按钮，并可改按钮名字。")
        tr("图层面板工具帮助")
        tip = tr("放在第几行")
        for combo in self._combos.values():
            combo.setToolTip(tip)
        placeholder = tr("自定义标题")
        for edit in self._title_edits.values():
            edit.setPlaceholderText(placeholder)
            edit.setToolTip(placeholder)
        shortcut_tip = tr("按组合键录制；按 Backspace 或 Delete 清除。只在 QGIS 窗口内响应，不是系统全局。")
        for edit in self._shortcut_edits.values():
            edit.setToolTip(shortcut_tip)
        expand_tip = tr("展开或收起这个按钮的子功能")
        for arrow in self._expand_buttons.values():
            arrow.setToolTip(expand_tip)
        self._fill_languages()
        for index in range(self.list.count()):
            self._refresh_text(self.list.item(index))
        apply_direction(self)
        self._place_combos()

    def _fill_languages(self):
        self.lang_menu.clear()
        current = current_language()
        for code, _msgid in self._languages:
            action = self.lang_menu.addAction(_language_text(code))
            action.setCheckable(True)
            action.setChecked(code == current)
            action.triggered.connect(lambda *_args, picked=code: self._choose_language(picked))
        self.btn_lang.setIcon(_language_icon(current))

    def _choose_language(self, code):
        if code and code != current_language():
            set_language(code)

    def _show_help(self):
        lines = []
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item is None:
                continue
            kind = item.data(_KIND)
            text = plain_title(item.text() or "")
            for suffix in (tr("（自有）"), tr("（第三方）")):
                if text.endswith(suffix):
                    text = text[: -len(suffix)].rstrip()
            help_msgid = str(item.data(_HELP_MSGID) or "") or help_msgid_for(item.data(_ID))
            body = tr(help_msgid) if help_msgid else ""
            if kind == "sep":
                if body:
                    lines.append("%s\n%s" % (tr("—— 分隔线 ——"), body))
                continue
            if not body:
                continue
            name = text or str(item.data(_ID) or "")
            lines.append("%s\n%s" % (name, body))
        if not lines:
            return
        dialog = HelpDialog(lines, self)
        dialog.exec_dialog()

    def _add_row(self, row):
        item = QListWidgetItem()
        item.setData(_ID, row["id"])
        item.setData(_KIND, row["kind"])
        item.setData(_MSGID, row.get("msgid") or "")
        item.setData(_NATIVE, row.get("native") or "")
        item.setData(_ROW, self._clamp_row(row.get("row")))
        item.setData(_TITLE, row.get("title") or "")
        item.setData(_HELP_MSGID, row.get("help_msgid") or "")
        item.setData(_HELP, row.get("help") or "")
        item.setData(_SHORTCUT, str(self._shortcuts.get(str(row.get("id") or "") or "", "")))
        item.setSizeHint(QSize(1, 30))
        icon = row.get("icon")
        if icon is not None and not icon.isNull():
            item.setIcon(icon)
        flags = qt_attr(Qt, "ItemIsEnabled") | qt_attr(Qt, "ItemIsSelectable") | qt_attr(Qt, "ItemIsDragEnabled")
        if row["kind"] in ("native", "plugin"):
            flags = flags | qt_attr(Qt, "ItemIsUserCheckable")
            item.setFlags(flags)
            item.setCheckState(qt_attr(Qt, "Checked" if row.get("visible", True) else "Unchecked"))
        else:
            item.setFlags(flags)
        self._refresh_text(item)
        self.list.addItem(item)
        self._ensure_combo(item)
        self._ensure_title(item)
        self._ensure_shortcut(item)
        self._ensure_expand(item)

    def _clamp_row(self, number):
        try:
            number = int(number)
        except (TypeError, ValueError):
            number = 1
        if number < 1 or number > MAX_ROWS:
            return 1
        return number

    def _item_row(self, item):
        return self._clamp_row(item.data(_ROW))

    def _ensure_combo(self, item):
        button_id = str(item.data(_ID))
        combo = self._combos.get(button_id)
        if combo is None:
            combo = QComboBox(self.list.viewport())
            combo.setObjectName("LayersPanelToolsRowCombo")
            for number in range(1, MAX_ROWS + 1):
                combo.addItem(str(number), number)
            combo.currentIndexChanged.connect(lambda _index, box=combo, row_item=item: self._on_row_picked(row_item, box))
            self._combos[button_id] = combo
        combo.blockSignals(True)
        combo.setCurrentIndex(self._item_row(item) - 1)
        combo.blockSignals(False)
        combo.setToolTip(tr("放在第几行"))
        return combo

    def _on_row_picked(self, item, combo):
        data = combo.currentData()
        if data is not None:
            item.setData(_ROW, self._clamp_row(data))

    def _ensure_title(self, item):
        button_id = str(item.data(_ID))
        edit = self._title_edits.get(button_id)
        if edit is None:
            edit = QLineEdit(self.list.viewport())
            edit.setObjectName("LayersPanelToolsTitleEdit")
            edit.textChanged.connect(lambda text, row_item=item: self._on_title(row_item, text))
            self._title_edits[button_id] = edit
        edit.blockSignals(True)
        edit.setText(str(item.data(_TITLE) or ""))
        edit.blockSignals(False)
        edit.setPlaceholderText(tr("自定义标题"))
        edit.setToolTip(tr("自定义标题"))
        return edit

    def _on_title(self, item, text):
        item.setData(_TITLE, text)
        self._refresh_text(item)

    def _ensure_shortcut(self, item):
        """快捷键只在插件自己的按钮和子功能上提供（原生按钮的快捷键归 QGIS 管）。"""
        if str(item.data(_KIND)) not in ("plugin", "settings", "sub"):
            return None
        button_id = str(item.data(_ID))
        edit = self._shortcut_edits.get(button_id)
        if edit is None:
            edit = _ShortcutEdit(self.list.viewport())
            edit.setObjectName("LayersPanelToolsShortcutEdit")
            edit.keySequenceChanged.connect(
                lambda *_args, box=edit, row_item=item: self._on_shortcut(row_item, box)
            )
            self._shortcut_edits[button_id] = edit
        edit.blockSignals(True)
        edit.setKeySequence(QKeySequence.fromString(str(item.data(_SHORTCUT) or "")))
        edit.blockSignals(False)
        edit.setToolTip(tr("按组合键录制；按 Backspace 或 Delete 清除。只在 QGIS 窗口内响应，不是系统全局。"))
        return edit

    def _on_shortcut(self, item, edit):
        """录入即查占用：被占用就不接受，清空显示并提示占用者。"""
        sequence = edit.keySequence().toString()
        holder = self._shortcut_taken(sequence, str(item.data(_ID)))
        if sequence and holder:
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
            self._show_status(tr("快捷键 %s 已被占用，未设置。") % sequence, holder)
            return
        item.setData(_SHORTCUT, sequence)
        self._shortcuts[str(item.data(_ID))] = str(sequence)

    def _shortcut_taken(self, sequence, own_id):
        """返回占用者的名字；没人占用返回空。查本窗口各行、已保存的子功能、QGIS 主窗口。"""
        wanted = str(sequence or "")
        if not wanted:
            return ""
        for index in range(self.list.count()):
            other = self.list.item(index)
            if str(other.data(_ID)) == str(own_id):
                continue
            if str(other.data(_SHORTCUT) or "") == wanted:
                return self._row_name(other)
        for other_id, text in (self._shortcuts or {}).items():
            if str(other_id) == str(own_id):
                continue
            if str(text or "") == wanted:
                entry = subcommands.subcommand_of_id(other_id)
                return tr(entry[1]) if entry is not None else str(other_id)
        from .buttons import shortcut_holder

        return shortcut_holder(wanted, own_id)

    def _row_name(self, item):
        custom = str(item.data(_TITLE) or "").strip()
        if custom:
            return custom
        msgid = str(item.data(_MSGID) or "")
        if msgid:
            return tr(msgid)
        return plain_title(str(item.data(_NATIVE) or "")) or str(item.data(_ID) or "")

    def _show_status(self, text, holder):
        """被占用的快捷键用弹窗提示，写明占用者。"""
        if holder:
            text = "%s（%s）" % (text, holder)
        report(self, tr("快捷键"), text, warning=True)

    def _ensure_expand(self, item):
        """多功能按钮名称右边的小箭头。"""
        button_id = str(item.data(_ID))
        if str(item.data(_KIND)) not in ("plugin", "settings") or not subcommands.has_subcommands(button_id):
            return None
        arrow = self._expand_buttons.get(button_id)
        if arrow is None:
            arrow = QToolButton(self.list.viewport())
            arrow.setObjectName("LayersPanelToolsExpandButton")
            arrow.setAutoRaise(True)
            arrow.setToolButtonStyle(qt_attr(Qt, "ToolButtonTextOnly"))
            arrow.setFocusPolicy(qt_attr(Qt, "NoFocus"))
            arrow.setStyleSheet("QToolButton { border: none; background: transparent; font-size: 11px; }")
            arrow.clicked.connect(lambda _checked=False, bid=button_id: self._toggle_expand(bid))
            self._expand_buttons[button_id] = arrow
        self._update_expand_button(button_id)
        return arrow

    def _update_expand_button(self, button_id):
        arrow = self._expand_buttons.get(str(button_id))
        if arrow is None:
            return
        arrow.setText("▼" if str(button_id) in self._expanded else "▸")

    def _toggle_expand(self, button_id):
        button_id = str(button_id)
        if button_id in self._expanded:
            self._expanded.discard(button_id)
            row = 0
            while row < self.list.count():
                item = self.list.item(row)
                if str(item.data(_PARENT)) == button_id and item.data(_KIND) == "sub":
                    self.list.takeItem(row)
                    continue
                row += 1
        else:
            self._expanded.add(button_id)
            parent_row = -1
            for index in range(self.list.count()):
                if str(self.list.item(index).data(_ID)) == button_id:
                    parent_row = index
                    break
            if parent_row < 0:
                return
            at = parent_row + 1
            for sub_id, msgid, _runner in subcommands.subcommands_of(button_id):
                self._add_sub_row(button_id, sub_id, msgid, at)
                at += 1
        self._update_expand_button(button_id)
        self._update_delete()
        self._place_combos()

    def _add_sub_row(self, parent_id, sub_id, msgid, at_row):
        item = QListWidgetItem()
        item.setData(_ID, str(sub_id))
        item.setData(_KIND, "sub")
        item.setData(_PARENT, str(parent_id))
        item.setData(_MSGID, str(msgid))
        item.setData(_NATIVE, "")
        item.setData(_ROW, 1)
        item.setData(_TITLE, str(self._titles_all.get(str(sub_id), "") or ""))
        item.setData(_SHORTCUT, str(self._shortcuts.get(str(sub_id), "") or ""))
        item.setSizeHint(QSize(1, 26))
        item.setFlags(qt_attr(Qt, "ItemIsEnabled") | qt_attr(Qt, "ItemIsSelectable"))
        self._refresh_text(item)
        self.list.insertItem(at_row, item)
        self._ensure_title(item)
        self._ensure_shortcut(item)

    def _sync_rows(self):
        for index in range(self.list.count()):
            item = self.list.item(index)
            button_id = str(item.data(_ID))
            combo = self._combos.get(button_id)
            if combo is not None and combo.currentData() is not None:
                item.setData(_ROW, self._clamp_row(combo.currentData()))
            edit = self._title_edits.get(button_id)
            if edit is not None:
                item.setData(_TITLE, edit.text())
            short = self._shortcut_edits.get(button_id)
            if short is not None:
                item.setData(_SHORTCUT, short.keySequence().toString())

    def _bands(self):
        width = max(self.list.viewport().width(), 1)
        name_w = int(width * 0.50)
        row_w = max(1, int(width * 0.10))
        title_w = max(1, int(width * 0.27))
        short_w = max(1, width - name_w - row_w - title_w)
        rtl = self.layoutDirection() == qt_attr(Qt, "RightToLeft")
        if rtl:
            short_x = 0
            title_x = short_w
            row_x = short_w + title_w
        else:
            row_x = name_w
            title_x = name_w + row_w
            short_x = name_w + row_w + title_w
        return name_w, row_x, row_w, title_x, title_w, short_x, short_w, rtl

    def _place_combos(self, *_args):
        viewport = self.list.viewport()
        height_limit = viewport.height()
        name_w, row_x, row_w, title_x, title_w, short_x, short_w, rtl = self._bands()
        if rtl:
            arrow_x = row_x + row_w + 2
        else:
            arrow_x = name_w - 26
        bar = self.list.verticalScrollBar()
        extra = bar.width() if bar.isVisible() else 0
        pad_key = (rtl, row_w + title_w + short_w, extra)
        if pad_key != getattr(self, "_pad_key", None):
            self._pad_key = pad_key
            if rtl:
                self._head.setContentsMargins(extra, 0, 0, 0)
                self.list.setStyleSheet("QListWidget::item { padding-left: %dpx; }" % (row_w + title_w + short_w))
            else:
                self._head.setContentsMargins(0, 0, extra, 0)
                self.list.setStyleSheet("QListWidget::item { padding-right: %dpx; }" % (row_w + title_w + short_w))
        seen = set()
        for index in range(self.list.count()):
            item = self.list.item(index)
            button_id = str(item.data(_ID))
            seen.add(button_id)
            widgets = []
            combo = self._combos.get(button_id)
            if combo is not None:
                widgets.append((combo, row_x, row_w))
            edit = self._title_edits.get(button_id)
            if edit is not None:
                widgets.append((edit, title_x, title_w))
            short = self._shortcut_edits.get(button_id)
            if short is not None:
                widgets.append((short, short_x, short_w))
            arrow = self._expand_buttons.get(button_id)
            if arrow is not None:
                widgets.append((arrow, arrow_x, 24))
            rect = self.list.visualItemRect(item)
            if (not rect.isValid()) or rect.bottom() < 0 or rect.top() > height_limit:
                for widget, _x, _w in widgets:
                    widget.hide()
                continue
            hint = max(rect.height() - 4, 1)
            for widget, x, w in widgets:
                height = min(hint, widget.sizeHint().height())
                top = rect.top() + max(0, (rect.height() - height) // 2)
                widget.setFixedWidth(w)
                widget.setGeometry(x, top, w, height)
                widget.show()
                widget.raise_()
        stale = (
            set(self._combos)
            | set(self._title_edits)
            | set(self._shortcut_edits)
            | set(self._expand_buttons)
        ) - seen
        for button_id in stale:
            self._drop_combo(button_id)
            self._drop_title(button_id)
            self._drop_shortcut(button_id)
            self._drop_expand(button_id)

    def _drop_combo(self, button_id):
        combo = self._combos.pop(str(button_id), None)
        if combo is None:
            return
        combo.hide()
        combo.deleteLater()

    def _drop_title(self, button_id):
        edit = self._title_edits.pop(str(button_id), None)
        if edit is None:
            return
        edit.hide()
        edit.deleteLater()

    def _drop_shortcut(self, button_id):
        edit = self._shortcut_edits.pop(str(button_id), None)
        if edit is None:
            return
        edit.hide()
        edit.deleteLater()

    def _drop_expand(self, button_id):
        arrow = self._expand_buttons.pop(str(button_id), None)
        if arrow is None:
            return
        arrow.hide()
        arrow.deleteLater()

    def _after_rows_moved(self, *_args):
        if self._moving:
            return
        self._place_combos()

    def _refresh_text(self, item):
        kind = item.data(_KIND)
        msgid = item.data(_MSGID) or ""
        native = item.data(_NATIVE) or ""
        custom = str(item.data(_TITLE) or "").strip()
        if kind == "sub":
            name = custom or tr(msgid)
            item.setText("    " + name)
            item.setToolTip(title_tip(name, ""))
            return
        if kind == "sep":
            name = tr("—— 分隔线 ——")
        elif custom:
            name = custom
        elif kind == "settings":
            name = tr("图层面板工具设置")
        elif kind == "plugin":
            name = tr(msgid) if msgid else native
        else:
            name = plain_title(native)
            if not name and msgid:
                name = tr(msgid)
            if not name:
                name = str(item.data(_ID) or "")
        text = name
        if kind == "native":
            text = text + tr("（自有）")
        elif kind in ("plugin", "settings"):
            text = text + tr("（第三方）")
        item.setText(text)
        help_msgid = str(item.data(_HELP_MSGID) or "")
        help_text = tr(help_msgid) if help_msgid else str(item.data(_HELP) or "")
        body = help_text if (help_text and help_text != name) else ""
        item.setToolTip(title_tip(text, body))

    def _move(self, delta):
        row = self.list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.list.count():
            return
        self._moving = True
        try:
            item = self.list.takeItem(row)
            self.list.insertItem(target, item)
            self.list.setCurrentRow(target)
        finally:
            self._moving = False
        self._place_combos()

    def _insert_sep(self):
        existing = {
            self.list.item(index).data(_ID)
            for index in range(self.list.count())
        }
        number = 1
        while ("%s%d" % (SEP_PREFIX, number)) in existing:
            number += 1
        current = self.list.currentItem()
        item_row = {
            "id": "%s%d" % (SEP_PREFIX, number),
            "kind": "sep",
            "visible": True,
            "msgid": "",
            "native": "",
            "icon": None,
            "row": self._item_row(current) if current is not None else 1,
        }
        cursor = self.list.currentRow()
        self._moving = True
        try:
            self._add_row(item_row)
            inserted = self.list.takeItem(self.list.count() - 1)
            at = self.list.count() if cursor < 0 else cursor + 1
            self.list.insertItem(at, inserted)
            self.list.setCurrentRow(at)
        finally:
            self._moving = False
        self._update_delete()
        self._place_combos()

    def _delete_sep(self):
        item = self.list.currentItem()
        if item is None or item.data(_KIND) != "sep":
            return
        self._drop_combo(item.data(_ID))
        self._drop_title(item.data(_ID))
        self.list.takeItem(self.list.row(item))
        self._update_delete()
        self._place_combos()

    def _update_delete(self):
        item = self.list.currentItem()
        self.btn_delete.setEnabled(item is not None and item.data(_KIND) == "sep")

    def _reset(self):
        self._moving = True
        try:
            self.list.clear()
            self._expanded.clear()
            for button_id in list(self._combos):
                self._drop_combo(button_id)
            for button_id in list(self._title_edits):
                self._drop_title(button_id)
            for button_id in list(self._shortcut_edits):
                self._drop_shortcut(button_id)
            for button_id in list(self._expand_buttons):
                self._drop_expand(button_id)
            for row in self._defaults:
                self._add_row(dict(row))
        finally:
            self._moving = False
        self._update_delete()
        self._place_combos()
