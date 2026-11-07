# -*- coding: utf-8 -*-
"""Search matching with wildcard support. No QGIS import: unit-testable on its own."""

import re

_WILDCARD = ("*", "?")


def word_matches(folded, word):
    """Plain substring match, or wildcard match when the word contains * or ?."""
    if any(ch in word for ch in _WILDCARD):
        pattern = "".join(
            ".*" if ch == "*" else "." if ch == "?" else re.escape(ch) for ch in word
        )
        try:
            return re.search(pattern, folded) is not None
        except re.error:
            return word in folded
    return word in folded


def matches(names, query):
    """Every word of the query must appear; names starting with the first word come first."""
    words = [word for word in str(query or "").casefold().split() if word]
    found = []
    for position, name in enumerate(names):
        folded = str(name or "").casefold()
        if words and not all(word_matches(folded, word) for word in words):
            continue
        starts = bool(words) and folded.startswith(words[0].replace("*", "").replace("?", ""))
        found.append((0 if starts else 1, position))
    found.sort()
    return [position for _rank, position in found]
