# -*- coding: utf-8 -*-
"""界面句子检查。

中文是原文。某种语言一旦写入任何一句，就必须覆盖全部句子，缺一句就失败。
空着的语言不算失败，语言列表里也不会出现。
tr() 的句子要直接写在引号里，检查才数得见。
按钮定义处如果要把句子存进 lpt_msgid，同一句必须再出现一次 tr("句子")。
"""

import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {"__pycache__", "i18n"}
SKIP_FILES = {"check_i18n.py", "self_test.py"}
_HAN = __import__("re").compile(r"[\u4e00-\u9fff]")


def _load_tables():
    path = ROOT / "i18n" / "catalog_data.py"
    spec = importlib.util.spec_from_file_location("lpt_catalog_data", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (("en", module.EN), ("es", module.ES), ("fr", module.FR), ("ar", module.AR))


def _docstrings(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                found.add(doc)
    return found


def _parents(tree):
    found = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            found[child] = node
    return found


def _is_tr_arg(node, parents):
    parent = parents.get(node)
    if not isinstance(parent, ast.Call) or not parent.args or parent.args[0] is not node:
        return False
    func = parent.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
    return name == "tr"


def _tr_keys(tree):
    keys = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name != "tr":
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            keys.append(arg.value)
    return keys


def _raw_chinese(tree, translated):
    docs = _docstrings(tree)
    parents = _parents(tree)
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value
        if not _HAN.search(text) or text in docs or text in translated:
            continue
        if _is_tr_arg(node, parents):
            continue
        bad.append(text)
    return bad


def collect_messages():
    messages = []
    for path in sorted(ROOT.rglob("*.py")):
        if SKIP_DIRS.intersection(path.parts) or path.name in SKIP_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        messages.extend(_tr_keys(tree))
    return list(dict.fromkeys(messages))


def missing_by_language(messages=None):
    if messages is None:
        messages = collect_messages()
    found = {}
    for name, table in _load_tables():
        if not table:
            continue
        missing = [text for text in messages if not table.get(text)]
        if missing:
            found[name] = missing
    return found


_ENDONYMS = (
    ("zh", "中文"),
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("ar", "العربية"),
)


def language_endonym(code):
    """语言在自身语言里的名字（endonym），不随界面语言翻译。"""
    for known, name in _ENDONYMS:
        if known == str(code or ""):
            return name
    return code


def offered_languages():
    """Chinese, plus any language whose catalog covers every current sentence."""
    messages = collect_messages()
    missing = missing_by_language(messages)
    tables = dict(_load_tables())
    ready = [("zh", "中文")]
    for code, label in ((c, n) for c, n in _ENDONYMS if c != "zh"):
        table = tables.get(code) or {}
        if table and code not in missing:
            ready.append((code, label))
    return ready


def audit_errors():
    errors = []
    messages = []
    for path in sorted(ROOT.rglob("*.py")):
        if SKIP_DIRS.intersection(path.parts) or path.name in SKIP_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        messages.extend(_tr_keys(tree))
    translated = set(messages)
    for path in sorted(ROOT.rglob("*.py")):
        if SKIP_DIRS.intersection(path.parts) or path.name in SKIP_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for text in _raw_chinese(tree, translated):
            errors.append("%s 有中文没进 tr()：%s" % (path.name, text[:80]))
    unique = list(dict.fromkeys(messages))
    for name, missing in missing_by_language(unique).items():
        errors.append("%s 只翻译了部分句子，缺 %d 句，第一句：%s" % (name, len(missing), missing[0][:60]))
    return errors


def main():
    from order_logic import self_check
    from scheme_logic import self_check as scheme_check

    self_check()
    scheme_check()
    try:
        from export_logic import self_check as export_logic_check

        export_logic_check()
    except ImportError:
        pass
    try:
        from config_registry import self_check as config_check

        config_check()
    except ImportError:
        pass
    try:
        import file_logic
        import find_logic

        assert find_logic.matches(["a1", "b2"], "1") == [0]  # nosec
        assert file_logic.is_sidecar("roads.dbf", "roads")  # nosec
    except ImportError:
        pass
    errors = audit_errors()
    if errors:
        print("\n".join(errors))
        return 1
    ready = ", ".join(code for code, _label in offered_languages())
    print("界面句子 %d 句。可切换：%s。" % (len(collect_messages()), ready))
    return 0


if __name__ == "__main__":
    sys.exit(main())
