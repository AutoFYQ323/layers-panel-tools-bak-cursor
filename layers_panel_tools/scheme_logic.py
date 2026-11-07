# -*- coding: utf-8 -*-
"""Match layer-name sets to a saved project, and rename layers inside it."""


def _clean(name):
    return " ".join(str(name or "").split())


def resolve_name(name, renames):
    current = _clean(name)
    seen = set()
    table = renames or {}
    while current in table and current not in seen:
        seen.add(current)
        nxt = _clean(table.get(current))
        if not nxt or nxt == current:
            break
        current = nxt
    return current


def _clean_list(names):
    found = []
    seen = set()
    for name in names or []:
        text = _clean(name)
        if not text or text in seen:
            continue
        seen.add(text)
        found.append(text)
    return found


def pair_saved_to_current(saved_names, current_names):
    """Pair each saved layer with a current one. Exact wins; otherwise 123 matches 123A."""
    current = _clean_list(current_names)
    saved = _clean_list(saved_names)
    used = set()
    pairs = {}
    for name in saved:
        if name in current and name not in used:
            pairs[name] = name
            used.add(name)
    rest = sorted((name for name in saved if name not in pairs), key=len, reverse=True)
    for name in rest:
        hits = [item for item in current if item not in used and item.startswith(name)]
        if not hits:
            continue
        hits.sort(key=lambda item: (len(item) - len(name), item))
        chosen = hits[0]
        pairs[name] = chosen
        used.add(chosen)
    return pairs


def best_current_name(saved, current_names):
    pairs = pair_saved_to_current([saved], current_names)
    return pairs.get(_clean(saved), "")


def project_layer_names(project):
    found = []
    seen = set()
    renames = project.get("renames") or {}
    for name in project.get("layers") or []:
        current = resolve_name(name, renames)
        if not current or current in seen:
            continue
        seen.add(current)
        found.append(current)
    return found


def match_project(projects, current_names):
    """Return the saved project id whose layer names best fit the open layers."""
    current = []
    seen = set()
    for name in current_names or []:
        text = _clean(name)
        if not text or text in seen:
            continue
        seen.add(text)
        current.append(text)
    if not current:
        return None
    best_id = None
    best_rank = None
    for project in projects or []:
        saved = project_layer_names(project)
        if not saved:
            continue
        overlap = len(pair_saved_to_current(saved, current))
        recall = overlap / float(len(saved))
        if recall < 0.75:
            continue
        rank = (overlap, recall)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_id = project.get("id")
    return best_id


def replace_layer_name(project, old, new):
    """Point every saved use of old at new. Returns False when nothing changed."""
    old = _clean(old)
    new = _clean(new)
    if not old or not new or old == new:
        return False
    changed = False
    layers = []
    renames = dict(project.get("renames") or {})
    for name in project.get("layers") or []:
        if _clean(name) == old or resolve_name(name, renames) == old:
            layers.append(new)
            changed = True
        else:
            layers.append(name)
    if old not in [_clean(name) for name in layers] and old not in [_clean(name) for name in (project.get("layers") or [])]:
        pass
    project["layers"] = layers
    for key, value in list(renames.items()):
        if _clean(value) == old:
            renames[key] = new
            changed = True
    if renames.get(old) != new:
        renames[old] = new
        changed = True
    project["renames"] = renames
    for scheme in project.get("schemes") or []:
        states = dict(scheme.get("states") or {})
        if old in states:
            states[new] = states.pop(old)
            scheme["states"] = states
            changed = True
    return changed


def add_layer_names(project, names, states):
    """Remember layers that showed up after the project was saved."""
    have = project_layer_names(project)
    covered = set(pair_saved_to_current(have, names).values())
    have = set(have)
    added = False
    incoming = states or {}
    for name in names or []:
        text = _clean(name)
        if not text or text in have or text in covered:
            continue
        project.setdefault("layers", []).append(text)
        have.add(text)
        added = True
        source = incoming.get(text) or {"visible": True, "categories": []}
        for scheme in project.get("schemes") or []:
            scheme.setdefault("states", {})
            if text in scheme["states"]:
                continue
            copied = []
            for item in source.get("categories") or []:
                copied.append({"label": item.get("label") or "", "on": bool(item.get("on"))})
            scheme["states"][text] = {"visible": bool(source.get("visible", True)), "categories": copied}
    return added


def saved_is_subset(project, current_names):
    saved = project_layer_names(project)
    if not saved:
        return False
    return len(pair_saved_to_current(saved, current_names)) == len(saved)


def self_check():
    roads = {"id": "p1", "layers": ["roads", "buildings"], "renames": {}, "schemes": [{"states": {"roads": {"visible": True}}}]}
    houses = {"id": "p2", "layers": ["houses"], "renames": {}, "schemes": []}
    assert match_project([roads, houses], ["buildings", "roads"]) == "p1"  # nosec
    assert match_project([roads, houses], ["buildings", "roads", "labels"]) == "p1"  # nosec
    assert match_project([roads, houses], ["houses", "yards"]) == "p2"  # nosec
    assert match_project([roads], ["other"]) is None  # nosec
    assert match_project([roads], []) is None  # nosec
    assert replace_layer_name(roads, "roads", "network") is True  # nosec
    assert "network" in project_layer_names(roads)  # nosec
    assert roads["schemes"][0]["states"]["network"]["visible"] is True  # nosec
    assert "roads" not in roads["schemes"][0]["states"]  # nosec
    assert add_layer_names(roads, ["network", "edge"], {"edge": {"visible": False, "categories": []}}) is True  # nosec
    assert "edge" in project_layer_names(roads)  # nosec
    assert saved_is_subset(houses, ["houses", "walls"]) is True  # nosec
    assert saved_is_subset(houses, ["walls"]) is False  # nosec
    numbered = {"id": "p3", "layers": ["123"], "renames": {}, "schemes": []}
    assert match_project([numbered], ["123A"]) == "p3"  # nosec
    assert best_current_name("123", ["123A", "999"]) == "123A"  # nosec
    assert best_current_name("123", ["123", "123A"]) == "123"  # nosec
    assert pair_saved_to_current(["123", "1234"], ["1234A", "123B"]) == {"1234": "1234A", "123": "123B"}  # nosec
    assert add_layer_names(numbered, ["123A"], {}) is False  # nosec
    assert saved_is_subset(numbered, ["123A"]) is True  # nosec
    return True
