# -*- coding: utf-8 -*-
"""Layers Panel Tools — buttons on the QGIS Layers panel toolbar."""


def classFactory(iface):
    from .plugin import LayersPanelToolsPlugin

    return LayersPanelToolsPlugin(iface)
