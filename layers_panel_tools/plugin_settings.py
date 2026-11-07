# -*- coding: utf-8 -*-
"""LayersPanelTools 专用配置文件：与 QGIS 全局及其它插件隔离（独立 ini），每个 QGIS 进程各自读写。"""

import os

from qgis.PyQt.QtCore import QSettings

from .qt_compat import qt_attr

try:
    from qgis.core import QgsApplication
except Exception:
    QgsApplication = None

_FILENAME = "LayersPanelTools.ini"
_GROUP = "LayersPanelTools"


def _ini_path():
    base = ""
    try:
        custom = os.environ.get("QGIS_CUSTOM_CONFIG_PATH") or ""
        if custom.strip():
            base = os.path.join(custom.strip(), "LayersPanelTools")
    except Exception:
        base = ""
    if not base:
        try:
            if QgsApplication is not None and callable(getattr(QgsApplication, "qgisSettingsDirPath", None)):
                base = os.path.join(str(QgsApplication.qgisSettingsDirPath()).rstrip("\\/"), "LayersPanelTools")
        except Exception:
            base = ""
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".qgis", "LayersPanelTools")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass  # nosec
    return os.path.join(base, _FILENAME)


_settings_obj = None


def plugin_qsettings():
    """独立 ini（[~]/.qgis/LayersPanelTools/LayersPanelTools.ini）下的 [LayersPanelTools] 节。与 QGIS 主配置分离。"""
    global _settings_obj
    if _settings_obj is None:
        _settings_obj = QSettings(_ini_path(), qt_attr(QSettings, "IniFormat"))
        _settings_obj.beginGroup(_GROUP)
    return _settings_obj


def flush():
    """立刻落盘。QSettings 默认延迟写，QGIS 崩溃时最后几次改动会丢。"""
    try:
        plugin_qsettings().sync()
    except Exception:
        pass  # nosec


def set_value(key, value):
    """写一个配置项并立刻落盘。"""
    settings = plugin_qsettings()
    settings.setValue(str(key), value)
    flush()
