# -*- coding: utf-8 -*-
"""Language list. Chinese is the source text."""

from .catalog_data import AR, EN, ES, FR

LANG_ZH = "zh"
LANG_EN = "en"
LANG_ES = "es"
LANG_FR = "fr"
LANG_AR = "ar"

_LOCALE_PREFIX = (
    ("zh", LANG_ZH),
    ("es", LANG_ES),
    ("fr", LANG_FR),
    ("ar", LANG_AR),
    ("en", LANG_EN),
)

_TABLES = {
    LANG_EN: EN,
    LANG_ES: ES,
    LANG_FR: FR,
    LANG_AR: AR,
}

_LABELS = (
    (LANG_EN, "English"),
    (LANG_ES, "Español"),
    (LANG_FR, "Français"),
    (LANG_AR, "العربية"),
)


def known_languages():
    return (LANG_ZH, LANG_EN, LANG_ES, LANG_FR, LANG_AR)


def tables():
    return _TABLES


def language_labels():
    return _LABELS


def detect_initial_language(qgis_locale=None, system_locale=None):
    saw = False
    for raw in (qgis_locale, system_locale):
        text = str(raw or "").strip().lower().replace("_", "-")
        if not text:
            continue
        saw = True
        primary = text.split("-", 1)[0]
        for prefix, lang in _LOCALE_PREFIX:
            if primary == prefix:
                return lang
        return LANG_EN
    return LANG_ZH if not saw else LANG_EN


def text_for(language, msgid):
    if language == LANG_ZH or not msgid:
        return ""
    table = _TABLES.get(language) or {}
    mapped = table.get(msgid)
    if mapped:
        return mapped
    return ""
