# -*- coding: utf-8 -*-
"""Local checks that need no QGIS: run with `python self_test.py` in the plugin folder."""

import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_find_matches():
    """Field search reuses the same matcher as the name search."""
    import find_logic

    names = ["roads_2020", "parcels", "road_2021"]
    assert find_logic.matches(names, "road") == [0, 2]
    assert find_logic.matches(names, "road*20") == [0, 2]
    assert find_logic.matches(names, "road*_20?1") == [2]
    assert find_logic.matches(names, "roads*") == [0]
    assert find_logic.matches(names, "ROAD 2021") == [2]
    assert find_logic.matches(names, "") == [0, 1, 2]
    assert find_logic.matches(names, "zzz") == []


def test_sidecar_filter():
    """Only same-stem sidecars with known extensions travel along."""
    import file_logic

    assert file_logic.sidecar_suffix("roads.shx", "roads") == ".shx"
    assert file_logic.sidecar_suffix("roads.shp.xml", "roads") == ".shp.xml"
    assert file_logic.sidecar_suffix("roads_2020.dbf", "roads") == ""
    assert file_logic.sidecar_suffix("parcels.dbf", "roads") == ""
    assert file_logic.is_sidecar("roads.prj", "roads") is True
    assert file_logic.is_sidecar("roads_2020.dbf", "roads") is False
    assert file_logic.is_sidecar("roads.tmp", "roads") is False


def test_unique_names():
    import file_logic

    with tempfile.TemporaryDirectory() as dst:
        io.open(os.path.join(dst, "roads.shp"), "w").close()
        used = set()
        first = file_logic.unique_name(dst, "roads.shp", used)
        assert first == "roads_1.shp", first
        second = file_logic.unique_name(dst, "roads.shp", used)
        assert second == "roads_2.shp", second
    import file_logic

    with tempfile.TemporaryDirectory() as dst:
        io.open(os.path.join(dst, "roads.shp"), "w").close()
        used = set()
        first = file_logic.unique_name(dst, "roads.shp", used)
        assert first == "roads_1.shp", first
        second = file_logic.unique_name(dst, "roads.shp", used)
        assert second == "roads_2.shp", second


def test_human_size():
    import file_logic

    assert file_logic.human_size(0) == "0 B"
    assert file_logic.human_size(999) == "999 B"
    assert file_logic.human_size(1024) == "1.0 KB"
    assert file_logic.human_size(1536) == "1.5 KB"
    assert file_logic.human_size(None) == ""


def test_config_registry():
    """The key list must stay parseable without QGIS installed."""
    import ast

    with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_registry.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    keys = None
    optional = None
    scoped = None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        if target.id == "KEYS":
            keys = value
        elif target.id == "OPTIONAL":
            optional = value
        elif target.id == "PROJECT_SCOPED":
            scoped = value

    assert keys, "KEYS not found"
    assert "order" in keys and "ui_language" in keys
    assert optional and set(optional) <= set(keys)
    for name in keys:
        assert not str(name).startswith(("lpt/", "LayersPanelTools/")), name
    for name in scoped or ():
        assert "/" in str(name), name


def test_order_logic():
    import order_logic as mod

    assert mod.self_check() is True
    # 默认隐藏的按钮必须都在显示顺序里，否则恢复默认时会丢按钮
    order = set(mod.DEFAULT_PLUGIN_ORDER)
    missing = [item for item in mod.DEFAULT_HIDDEN if item not in order]
    assert not missing, missing
    # 不能有重复登记
    assert len(mod.DEFAULT_PLUGIN_ORDER) == len(order)


def test_scheme_logic():
    from scheme_logic import self_check

    assert self_check() is True


def test_import_surface():
    """Every module-level import of a local helper must exist in that module.

    This catches the class of bug where a refactor imports subscribe() from i18n
    but the helper never lands there, which makes the whole plugin fail to load.
    """
    import ast
    import importlib.util

    root = os.path.dirname(os.path.abspath(__file__))
    providers = {
        "i18n": os.path.join(root, "i18n", "__init__.py"),
        "buttons": os.path.join(root, "buttons.py"),
        "scope": os.path.join(root, "scope.py"),
        "file_logic": os.path.join(root, "file_logic.py"),
        "find_logic": os.path.join(root, "find_logic.py"),
        "qt_compat": os.path.join(root, "qt_compat.py"),
    }

    exported = {}
    for name, path in providers.items():
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        names = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
            elif isinstance(node, ast.ImportFrom):
                # Re-exports (buttons.py forwards qt_attr from qt_compat) are legitimate.
                for alias in node.names:
                    names.add(alias.asname or alias.name)
        exported[name] = names

    problems = []
    for filename in os.listdir(root):
        if not filename.endswith(".py"):
            continue
        tree = ast.parse(io.open(os.path.join(root, filename), encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            module = node.module.lstrip(".")
            simple = module.split(".")[-1]
            if simple not in exported:
                continue
            for alias in node.names:
                if alias.name != "*" and alias.name not in exported[simple]:
                    problems.append("%s: %s not in %s" % (filename, alias.name, simple))
    assert not problems, "; ".join(problems)


def test_self_members():
    """No class may call or read self._x that it never defines or assigns.

    Closes the crash class where closeEvent calls a helper that a refactor
    removed (for example _detach_language) and the dialog dies on close.
    """
    import ast

    def self_assigns(cls):
        found = set()
        for item in cls.body:
            for sub in ast.walk(item):
                targets = []
                if isinstance(sub, ast.Assign):
                    targets = sub.targets
                elif isinstance(sub, ast.AugAssign):
                    targets = [sub.target]
                for target in targets:
                    names = []
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                        names.append(target.attr)
                    elif isinstance(target, ast.Tuple):
                        for part in target.elts:
                            if isinstance(part, ast.Attribute) and isinstance(part.value, ast.Name) and part.value.id == "self":
                                names.append(part.attr)
                    found.update(names)
        return found

    root = os.path.dirname(os.path.abspath(__file__))
    problems = []
    for name in sorted(os.listdir(root)):
        if not name.endswith(".py") or name == "self_test.py":
            continue
        tree = ast.parse(io.open(os.path.join(root, name), encoding="utf-8").read())
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        for cls in classes.values():
            members = {item.name for item in cls.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
            members |= self_assigns(cls)
            for base in cls.bases:
                base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
                if base_name in classes:
                    parent = classes[base_name]
                    members |= {item.name for item in parent.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
                    members |= self_assigns(parent)
            for item in cls.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for sub in ast.walk(item):
                    if not (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self"):
                        continue
                    member = sub.attr
                    if not member.startswith("_") or member.startswith("__") or member in members:
                        continue
                    problems.append("%s: %s.%s uses undefined self.%s" % (name, cls.name, item.name, member))
    assert not problems, "; ".join(problems)


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failed = []
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failed.append("%s: %s" % (test.__name__, exc or "assertion failed"))
        except Exception as exc:  # noqa: BLE001 - report everything in one run
            failed.append("%s: %r" % (test.__name__, exc))
    if failed:
        print("\n".join(failed))
        return 1
    print("自检 %d 项通过。" % len(tests))
    return 0
if __name__ == "__main__":
    sys.exit(main())
