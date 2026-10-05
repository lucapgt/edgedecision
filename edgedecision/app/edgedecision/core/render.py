"""Textual rendering of queries and capabilities for the semantic model.

The model only ever sees these strings, which is what makes the action space
dynamic: a new capability is just a new string.
"""
from __future__ import annotations

from typing import Optional

from .registry import DOMAIN_NOUN_EN
from .types import NO_ACTION, Capability, Catalog, Entity

NO_ACTION_TEXT = "no action: none of the available actions matches this request"


def query_text(utterance: str, context_area: Optional[str] = None) -> str:
    utterance = " ".join((utterance or "").split())
    if context_area:
        return f"{utterance} || user is in: {context_area}"
    return utterance


def _fmt_num(v) -> str:
    try:
        f = float(v)
        return str(int(f)) if f.is_integer() else f"{f:.1f}"
    except (TypeError, ValueError):
        return str(v)


def state_summary(e: Entity) -> str:
    st = e.state or {}
    s = str(st.get("state", "")).lower()
    if not s:
        return ""
    if s == "unavailable":
        return "unavailable"
    parts = []
    d = e.domain
    if d == "sensor":
        unit = e.attributes.get("unit") or st.get("unit") or ""
        return f"{_fmt_num(s)} {unit}".strip()
    parts.append(s)
    if d == "light" and s == "on":
        if "brightness" in st:
            parts.append(f"brightness {_fmt_num(st['brightness'])}%")
        if st.get("color"):
            parts.append(f"color {st['color']}")
    elif d == "cover" and "position" in st:
        parts.append(f"position {_fmt_num(st['position'])}%")
    elif d == "climate":
        if "temperature" in st:
            parts.append(f"target {_fmt_num(st['temperature'])}°C")
        if "current_temperature" in st:
            parts.append(f"current {_fmt_num(st['current_temperature'])}°C")
    elif d == "media_player":
        if "volume" in st:
            parts.append(f"volume {_fmt_num(st['volume'])}%")
        if st.get("media_title"):
            parts.append(f"playing {st['media_title']}")
    elif d == "weather":
        if st.get("temperature") is not None:
            parts.append(f"{_fmt_num(st['temperature'])}°C")
        if st.get("humidity") is not None:
            parts.append(f"humidity {_fmt_num(st['humidity'])}%")
    elif d == "fan" and s == "on" and "percentage" in st:
        parts.append(f"speed {_fmt_num(st['percentage'])}%")
    return ", ".join(parts)


def _entity_label(e: Entity, with_class: bool = True) -> str:
    noun = DOMAIN_NOUN_EN.get(e.domain, (e.domain, e.domain))[0]
    cls = f" {e.device_class}" if (with_class and e.device_class) else ""
    lab = f"{e.name} ({noun}{cls})"
    if e.aliases:
        lab += " aka " + ", ".join(e.aliases[:3])
    return lab


def _area_label(cat: Catalog, area_id: Optional[str]) -> str:
    if not area_id:
        return "none"
    a = cat.areas.get(area_id)
    if not a:
        return area_id
    return a.name + (" / " + " / ".join(a.aliases[:2]) if a.aliases else "")


def _args_label(cat: Catalog, action: str, entity: Optional[Entity] = None) -> str:
    spec = cat.actions.get(action)
    if not spec or not spec.args:
        return ""
    out = []
    for a in spec.args:
        if a.kind == "enum":
            opts = list(a.choices or {})
            if a.name == "hvac_mode" and entity is not None and entity.attributes.get("hvac_modes"):
                opts = [m for m in opts if m in entity.attributes["hvac_modes"]]  # what THIS device supports
            out.append(f"{a.name}: {'/'.join(opts[:8])}")
        elif a.kind == "step":
            out.append(f"optional {a.name} {a.unit or ''}".strip())
        else:
            rng = f" {_fmt_num(a.min)}-{_fmt_num(a.max)}{a.unit or ''}" if a.min is not None else ""
            out.append(f"{a.name}{rng}")
    return "; ".join(out)


def action_label(cat: Catalog, action: str) -> str:
    spec = cat.actions.get(action)
    name = action.replace(".", " ").replace("_", " ")
    return f"{name}: {spec.description}" if spec else name


def target_parts(cat: Catalog, cap: Capability):
    if cap.target_kind == "entity":
        e = cat.entities[cap.target]
        return _entity_label(e), _area_label(cat, e.area), state_summary(e)
    key = cap.target.split(":")[-1]
    domain, _, cls = key.partition(".")
    plural = DOMAIN_NOUN_EN.get(domain, (domain, domain + "s"))[1] + (f" ({cls})" if cls else "")
    members = [cat.entities[m] for m in cap.entities if m in cat.entities]
    states = [str(m.state.get("state", "")) for m in members]
    summary = f"{len(members)} {plural}: " + ", ".join(f"{states.count(s)} {s}" for s in sorted(set(states)) if s)
    if cap.target_kind == "area_group":
        area = cap.target.split(":")[1]
        return f"all {plural} in {cat.area_name(area)}", _area_label(cat, area), summary
    if cap.target_kind == "floor_group":
        fid = cap.target.split(":")[1]
        al = cat.floor_aliases(fid)
        fl = cat.floor_name(fid) + (" / " + " / ".join(al[:2]) if al else "")
        return f"all {plural} on the floor {cat.floor_name(fid)}", f"floor {fl}", summary
    return f"all {plural} in the house", "whole house", summary


def capability_text(cat: Catalog, cap_id: str, with_state: bool = True) -> str:
    """Cross-encoder rendering (with state) or bi-encoder rendering (without state)."""
    if cap_id == NO_ACTION:
        return NO_ACTION_TEXT
    cap = cat.cap(cap_id)
    target, area, state = target_parts(cat, cap)
    s = f"{action_label(cat, cap.action)} || target: {target} || area: {area}"
    args = _args_label(cat, cap.action, cat.entities.get(cap.target) if cap.target_kind == "entity" else None)
    if args:
        s += f" || args: {args}"
    if with_state and state:
        s += f" || state: {state}"
    return s


def lexical_doc(cat: Catalog, cap_id: str) -> str:
    """Bag of words used by the lexical part of retrieval (multilingual keywords + names)."""
    from .registry import DOMAIN_KEYWORDS

    cap = cat.cap(cap_id)
    spec = cat.actions.get(cap.action)
    domain = cap.action.split(".")[0]
    toks = []
    for e_id in cap.entities[:1] if cap.target_kind == "entity" else []:
        e = cat.entities[e_id]
        toks += [e.name] + e.aliases
        if e.area:
            a = cat.areas.get(e.area)
            if a:
                toks += [a.name] + a.aliases
    if cap.target_kind == "area_group":
        a = cat.areas.get(cap.target.split(":")[1])
        if a:
            toks += [a.name] + a.aliases
    if cap.target_kind == "floor_group":
        fid = cap.target.split(":")[1]
        toks += [cat.floor_name(fid)] + cat.floor_aliases(fid)
    # keywords of Italian / English / Spanish (as the first models were built) + the language of this home
    langs = {"it", "en", "es", (cat.meta or {}).get("home_lang") or "it"}
    if spec:
        for lang, kws in spec.keywords.items():
            if lang in langs:
                toks += kws
    for lang, kws in DOMAIN_KEYWORDS.get(domain, {}).items():
        if lang in langs:
            toks += kws
    return " ".join(toks)
