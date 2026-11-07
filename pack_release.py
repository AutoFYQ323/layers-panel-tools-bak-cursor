# -*- coding: utf-8 -*-
"""Build the Layers Panel Tools plugin zip for plugins.qgis.org. Run from this folder (the parent of layers_panel_tools)."""

import pathlib
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
PLUGIN = ROOT / "layers_panel_tools"
OUT = ROOT / "layers_panel_tools_1.0.3.zip"
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {"self_test.py"}


def main():
    check = subprocess.run([sys.executable, str(PLUGIN / "check_i18n.py")], check=False)  # check_i18n ships: the plugin imports it at runtime
    if check.returncode != 0:
        raise SystemExit(check.returncode)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in PLUGIN.rglob("*"):
            if not path.is_file():
                continue
            if SKIP_DIRS.intersection(path.parts) or path.name in SKIP_FILES or path.suffix == ".pyc":
                continue
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(OUT)


if __name__ == "__main__":
    main()
