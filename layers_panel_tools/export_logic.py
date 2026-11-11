# -*- coding: utf-8 -*-
"""Which export drivers can put several layers in one file. No QGIS import."""


def merge_kind(driver):
    """Return how a driver combines layers, or '' when one file can hold only one layer.

    layers: one dataset, one layer name each (GeoPackage, SQLite, KML, GML, FileGDB).
    kmz: LIBKML writes one KMZ.
    sheets: one workbook, one sheet each.
    dxf: one DXF. Most attributes are dropped by the format itself.
    stack: one table. CSV cannot keep a second layer inside the same file, so the
    features are appended and a column records the source layer name.
    """
    key = str(driver or "").replace(" ", "").upper()
    if key in ("GPKG", "GEOPACKAGE", "SQLITE", "SPATIALITE", "KML", "GML", "OPENFILEGDB", "FILEGDB"):
        return "layers"
    if key == "LIBKML":
        return "kmz"
    if key in ("XLSX", "XLS", "ODS"):
        return "sheets"
    if key == "DXF":
        return "dxf"
    if key == "CSV":
        return "stack"
    return ""


def merged_extension(driver, fallback):
    if merge_kind(driver) == "kmz":
        return ".kmz"
    ext = str(fallback or "")
    if ext and not ext.startswith("."):
        ext = "." + ext
    return ext


def unique_layer_name(name, used, limit=0):
    """A layer or sheet name that is not already in `used`. `used` is mutated."""
    bad = '\\/:*?"<>|[]'
    text = "".join("_" if char in bad else char for char in str(name or "")).strip().rstrip(".")
    if not text:
        text = "layer"
    if limit and len(text) > limit:
        text = text[:limit]
    taken = {item.casefold() for item in used}
    candidate = text
    number = 2
    while candidate.casefold() in taken:
        suffix = "_%d" % number
        head = text
        if limit and len(head) + len(suffix) > limit:
            head = head[: max(1, limit - len(suffix))]
        candidate = head + suffix
        number += 1
    used.append(candidate)
    return candidate


def self_check():
    assert merge_kind("GPKG") == "layers"  # nosec
    assert merge_kind("KML") == "layers"  # nosec
    assert merge_kind("GML") == "layers"  # nosec
    assert merge_kind("LIBKML") == "kmz"  # nosec
    assert merge_kind("XLSX") == "sheets"  # nosec
    assert merge_kind("ODS") == "sheets"  # nosec
    assert merge_kind("DXF") == "dxf"  # nosec
    assert merge_kind("CSV") == "stack"  # nosec
    assert merge_kind("ESRI Shapefile") == ""  # nosec
    assert merge_kind("GeoJSON") == ""  # nosec
    assert merged_extension("LIBKML", ".kml") == ".kmz"  # nosec
    assert merged_extension("GPKG", "gpkg") == ".gpkg"  # nosec
    used = []
    assert unique_layer_name("roads", used) == "roads"  # nosec
    assert unique_layer_name("roads", used) == "roads_2"  # nosec
    short = []
    assert unique_layer_name("abcdefghij", short, limit=6) == "abcdef"  # nosec
    assert unique_layer_name("abcdefghij", short, limit=6) == "abcd_2"  # nosec
    return True
