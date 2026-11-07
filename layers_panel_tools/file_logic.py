# -*- coding: utf-8 -*-
"""Layer file helpers: sidecar detection and collision-free target names. No QGIS import."""

import os

# Data files that belong with a layer's main file. Matching by "starts with stem."
# alone would also grab unrelated files such as roads_2020.dbf, so keep a whitelist.
SIDECAR_EXT = (
    ".shx",
    ".dbf",
    ".prj",
    ".cpg",
    ".sbn",
    ".sbx",
    ".qix",
    ".shp.xml",
    ".tfw",
    ".tifw",
    ".jgw",
    ".pgw",
    ".wld",
    ".aux.xml",
    ".qml",
    ".qmd",
    ".qpj",
    ".csvt",
    ".gfs",
    ".gml",
)

# Unreliable while the dataset is open, or pure noise.
EXCLUDE_EXT = (".wal", ".shm", ".lock", ".tmp", ".bak")


def sidecar_suffix(entry, stem):
    """Suffix after the stem, lowercased; "" when the entry has a different stem."""
    if not stem or not entry.startswith(stem + "."):
        return ""
    return entry[len(stem):].lower()


def is_sidecar(entry, stem):
    suffix = sidecar_suffix(entry, stem)
    if not suffix or suffix in EXCLUDE_EXT:
        return False
    return suffix in SIDECAR_EXT or suffix.endswith(".shp.xml")


def unique_name(folder, filename, used):
    """Pick a name that neither collides on disk nor with names chosen in this run."""
    stem, ext = os.path.splitext(filename)
    name = filename
    counter = 1
    while name in used or os.path.exists(os.path.join(folder, name)):
        name = "%s_%d%s" % (stem, counter, ext)
        counter += 1
    used.add(name)
    return name


def human_size(count):
    """Bytes as a short readable string (used by the CSV export)."""
    try:
        value = float(count)
    except (TypeError, ValueError):
        return ""
    if value < 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return "%d %s" % (int(value), unit)
            return "%.1f %s" % (value, unit)
        value /= 1024.0
    return ""
