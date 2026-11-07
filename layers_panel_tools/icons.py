# -*- coding: utf-8 -*-
"""Toolbar icons stored next to the plugin."""

import os

from qgis.PyQt.QtGui import QIcon


def load_icon(name):
    path = os.path.join(os.path.dirname(__file__), "icons", "%s.png" % name)
    if not os.path.isfile(path):
        return QIcon()
    icon = QIcon(path)
    if icon.isNull():
        return QIcon()
    return icon
