"""Entities that are not devices but stand for what the voice assistant can do (round 7b).

* ``assist.voice``  timers, alarms, announcements (Home Assistant's own intents on the satellite)
* ``home.house``    "turn off everything", "what is still on"
* ``agent.other``   requests the home cannot fulfil itself but another assistant can: the weather without a weather
  entity, a shopping list without a list, music by name without a Music Assistant player. Choosing it means
  ESCALATE (reason "delegated"): the sentence goes to the fallback agent.

The same function completes the catalogue in training homes, in test homes and in Home Assistant, so a request is
always the same kind of request (a device request) whatever the home has; only the target changes.
"""
from __future__ import annotations

from typing import Optional

from .types import Catalog, Entity

NAMES = {
    "it": {"assist.voice": "Assistente vocale", "home.house": "Tutta la casa", "agent.other": "Altro assistente"},
    "en": {"assist.voice": "Voice assistant", "home.house": "Whole house", "agent.other": "Other assistant"},
    "es": {"assist.voice": "Asistente de voz", "home.house": "Toda la casa", "agent.other": "Otro asistente"},
    "fr": {"assist.voice": "Assistant vocal", "home.house": "Toute la maison", "agent.other": "Autre assistant"},
    "de": {"assist.voice": "Sprachassistent", "home.house": "Ganzes Haus", "agent.other": "Anderer Assistent"},
    "nl": {"assist.voice": "Spraakassistent", "home.house": "Hele huis", "agent.other": "Andere assistent"},
    "pt": {"assist.voice": "Assistente de voz", "home.house": "Casa toda", "agent.other": "Outro assistente"},
    "pl": {"assist.voice": "Asystent głosowy", "home.house": "Cały dom", "agent.other": "Inny asystent"},
    "sv": {"assist.voice": "Röstassistent", "home.house": "Hela huset", "agent.other": "Annan assistent"},
}
DOMAINS = ("assist", "home", "agent")


def delegations(cat: Catalog) -> list[str]:
    """What the home cannot do itself: features of the agent.other entity."""
    ents = [e for e in cat.entities.values() if e.domain not in DOMAINS]
    out = []
    if not any(e.domain == "weather" for e in ents):
        out.append("weather")
    if not any(e.domain == "todo" for e in ents):
        out.append("todo")
    if not any(e.domain == "media_player" and "search" in (e.features or []) for e in ents):
        out.append("search")
    return out


def complete(cat: Catalog, lang: Optional[str] = None) -> Catalog:
    """The catalogue with assist.voice, home.house and (if needed) agent.other; capabilities rebuilt.
    Idempotent; the catalogue passed in is not modified."""
    from .registry import build_capabilities, default_actions
    lang = (lang or (cat.meta or {}).get("home_lang") or "it")[:2]
    names = NAMES.get(lang, NAMES["en"])
    ents = [e for e in cat.entities.values() if e.id != "agent.other"]
    have = {e.id for e in ents}
    for eid, dom in (("assist.voice", "assist"), ("home.house", "home")):
        if eid not in have:
            ents.append(Entity(id=eid, domain=dom, name=names[eid], state={}))
    feats = delegations(Catalog(list(cat.areas.values()), ents))
    if feats:
        ents.append(Entity(id="agent.other", domain="agent", name=names["agent.other"], features=feats, state={}))
    old = cat.entities.get("agent.other")
    if old is not None and sorted(old.features) == sorted(feats) and len(ents) == len(cat.entities):
        return cat
    areas = list(cat.areas.values())
    acts = default_actions()
    caps = build_capabilities(areas, ents, acts)
    used = {c.action for c in caps}
    return Catalog(areas, ents, [a for a in acts if a.action in used], caps, cat.meta)
