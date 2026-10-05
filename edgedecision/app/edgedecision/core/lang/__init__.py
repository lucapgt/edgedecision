"""Runtime words per language (one small file each: fr.py, de.py, ...).

Italian, English and Spanish are still written inside registry.py / params.py / the Home Assistant adapter; the
languages added later live only here. What a file contains is deliberately limited to things the model cannot do:
turning value words into numbers ("vingt-deux", "à moitié"), colour / mode names, and the spoken replies.
Numbers in letters are generated with num2words when it is installed (the add-on image has it).
"""
from __future__ import annotations

import importlib
import pkgutil
import re

_MODS: dict = {}


def modules() -> dict:
    if not _MODS:
        for m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
            if not m.name.startswith("_"):
                mod = importlib.import_module(f"{__name__}.{m.name}")
                _MODS[mod.LANG] = mod
    return _MODS


def get(lang: str):
    return modules().get(lang)


def apply_registry(ns: dict) -> None:
    """Colours, colour temperatures, HVAC modes and keywords of the extra languages -> registry tables."""
    for lang, m in modules().items():
        for table, attr in (("COLOR_CHOICES", "COLORS"), ("COLOR_TEMP_CHOICES", "COLOR_TEMPS"),
                            ("HVAC_CHOICES", "HVAC"), ("DAY_CHOICES", "DAYS")):
            for value, words in getattr(m, attr, {}).items():
                if value in ns[table]:
                    ns[table][value][lang] = list(words)
        for domain, words in getattr(m, "DOMAIN_KEYWORDS", {}).items():
            ns["DOMAIN_KEYWORDS"].setdefault(domain, {})[lang] = list(words)
        for kw, attr in (("ON_KW", "ON"), ("OFF_KW", "OFF"), ("STATE_KW", "STATE")):
            ns[kw][lang] = list(getattr(m, attr, []))


def number_phrases(lang_code: str, normalize) -> dict:
    """{tuple of normalised tokens: value} for 0..100 in one language (num2words)."""
    try:
        from num2words import num2words
    except ImportError:
        return {}
    out = {}
    for n in range(0, 101):
        try:
            w = num2words(n, lang=lang_code)
        except Exception:  # noqa: BLE001
            continue
        toks = tuple(re.sub(r"[-‐]", " ", normalize(w)).replace("'", " ").split())
        if toks:
            out[toks] = n
    return out


def apply_params(ns: dict, normalize) -> None:
    for lang, m in modules().items():
        for name in ("PERCENT_UNITS", "DEGREE_UNITS", "HALF_SUFFIX"):
            ns[name].extend(tuple(x) for x in getattr(m, name, []))
        for name in ("HALF_WORDS", "MAX_WORDS", "MIN_WORDS", "SMALL_STEP", "LARGE_STEP", "ABS_MARKERS", "REL_MARKERS"):
            ns[name].update(getattr(m, name, []))
        for toks, v in number_phrases(getattr(m, "NUMBER_LANG", lang), normalize).items():
            if len(toks) == 1:
                ns["NUMBER_WORDS"].setdefault(toks[0], v)
            else:
                ns["NUMBER_PHRASES"].setdefault(toks, v)
        ns["STRONG_AMBIGUOUS"].update(getattr(m, "AMBIGUOUS_NUMBERS", []))


def apply_specific(kind_of: dict, ignore: set, verbs: set, tokens) -> None:
    """Generic device nouns, non-naming words and command verbs of the extra languages -> core/specific.py.
    A word that is a device noun in one language and a function word in another ("tv", "a") keeps its first role."""
    for lang, m in modules().items():
        for kind, words in getattr(m, "KIND_NOUNS", {}).items():
            for w in tokens(words):
                kind_of.setdefault(w, kind)
    for lang, m in modules().items():
        for w in tokens(getattr(m, "FUNCTION_WORDS", "")):
            if w not in kind_of:
                ignore.add(w)
        for w in tokens(getattr(m, "VERBS", "")) + tokens(" ".join(getattr(m, "ON", []) + getattr(m, "OFF", []))):
            if w not in kind_of:
                verbs.add(w)
