"""Deterministic checks on WHICH device the sentence designates (after the model has scored the candidates).

1. Generic reference, several candidates  ->  ask
   "accendi la tv" in a home with two TVs: the sentence contains nothing but a verb and a generic noun, so it does
   not say which TV. The model may still prefer one (training homes usually have one TV, in the living room), but
   that preference is a prior, not something the user said. Unless the microphone room settles it, EdgeDecision
   asks "Intendi TV salone o TV taverna?".

2. A word that only one candidate has  ->  that candidate
   "accendi i faretti dell'isola" with "Faretti isola" and "Faretti salone": the model hesitates between two
   targets of the same action, but "isola" belongs to one of them only. The top candidate is taken when it is the
   only one whose distinguishing words appear in the sentence.

Both checks look at words only; they never create a candidate the model did not propose.
"""
from __future__ import annotations

import re
from typing import Optional

from .text import normalize
from .types import NO_ACTION, Catalog, Entity

# generic nouns -> kind (see entity_kind)
_KIND_NOUNS = {
    "light": "luce luci lampada lampade lampadina light lights lamp lamps luz luces lampara lamparas",
    "cover.shutter": "tapparella tapparelle persiana persiane serranda serrande shutter shutters blind blinds "
                     "persianas estor",
    "cover.curtain": "tenda tende curtain curtains cortina cortinas",
    "cover.awning": "awning toldo",
    "cover.garage": "garage basculante garaje",
    "cover.gate": "cancello gate porton verja",
    "climate.thermostat": "termostato termostati riscaldamento termosifoni thermostat heating heat calefaccion",
    "climate.ac": "condizionatore condizionatori climatizzatore clima ac aire conditioner conditioning",
    "media_player.tv": "tv tivu televisione televisore tele television televisor",
    "media_player.speaker": "radio stereo cassa casse speaker speakers altavoz musica music",
    "fan": "ventilatore ventilatori ventola fan fans ventilador ventiladores",
    "lock": "serratura lock cerradura",
    "vacuum": "robot robottino aspirapolvere vacuum aspiradora",
    "alarm": "allarme antifurto alarm alarma",
}
KIND_OF = {w: k for k, ws in _KIND_NOUNS.items() for w in ws.split()}

# words that never designate a device: articles, prepositions, politeness, attributes, units, quantifiers
_IGNORE = set("""
il lo la i gli le l giu un uno una del dello della dei degli delle dell al allo alla ai agli alle all nel nella nei
nelle sul sulla sui di da in a per con su che quella quello quelle quelli questa questo po poco un' pure
the a an of in on at to for my please this that some bit little up down off
el los las un una unos unas de del al en con por para mi esto esta ese esa poco un
per favore grazie thanks gracias favor por
volume volumen luminosita brightness brillo intensita temperatura temperature grados gradi degrees percent
cento ciento livello level potenza velocita speed massimo minimo max min meta half medio mitad
piu meno more less mas
""".split())
_NUM = re.compile(r"^\d+([.,]\d+)?%?$")
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))


LANG_VERBS: set = set()   # command verbs of the extra languages (core/lang/*.py VERBS, ON, OFF)
from .lang import apply_specific as _apply_lang  # noqa: E402

_apply_lang(KIND_OF, _IGNORE, LANG_VERBS, tokens)


def entity_kind(e: Entity) -> str:
    if e.domain == "cover":
        return f"cover.{e.device_class or 'shutter'}"
    if e.domain == "climate":
        return "climate.ac" if "cool" in (e.attributes or {}).get("hvac_modes", []) else "climate.thermostat"
    if e.domain == "media_player":
        return "media_player.tv" if e.device_class == "tv" else "media_player.speaker"
    if e.domain == "alarm_control_panel":
        return "alarm"
    return e.domain


def bare_kind(text: str, verb_rx, names: set = frozenset()) -> Optional[str]:
    """The kind named by a sentence made only of a verb and a generic noun ("accendi la tv"), else None.
    names: words of the home's device and room names; they are never verbs ("Partykeller" is not "par...")."""
    kinds = set()
    for t in tokens(text):
        if t in KIND_OF:
            kinds.add(KIND_OF[t])
        elif t in names or not (t in _IGNORE or _NUM.match(t) or verb_rx.fullmatch(t) or t in LANG_VERBS):
            return None  # any other word (a name, a room, "soffitto", ...) may designate the device
    return kinds.pop() if len(kinds) == 1 else None


def generic_kinds(text: str, verb_rx, names: set = frozenset()) -> Optional[set]:
    """Kinds named by a sentence made only of verbs, function words, numbers and generic nouns ("accendi la luce",
    "alza la temperatura" -> set(), "mach das Licht an" -> {"light"}); None when some word may name a device or room."""
    kinds = set()
    for t in tokens(text):
        if t in KIND_OF:
            kinds.add(KIND_OF[t])
        elif t in _IGNORE or _NUM.match(t):
            continue  # "temperatura" stays generic even if a sensor is called "Temperatura mansarda"
        elif t in names or not (verb_rx.fullmatch(t) or t in LANG_VERBS):
            return None
    return kinds


def _same(a: str, b: str) -> bool:
    """salon ~ salone, tavern ~ taverna: equal, or one extends the other by at most 2 letters."""
    if a == b:
        return True
    s, l_ = sorted((a, b), key=len)
    return len(s) >= 4 and l_.startswith(s) and len(l_) - len(s) <= 2


def descriptor(cat: Catalog, cap_id: str) -> set[str]:
    """Words of the target: device names and aliases, room names and aliases."""
    cap = cat.cap(cap_id)
    words: list[str] = []
    areas = set()
    if cap.target_kind == "area_group":
        areas.add(cap.target.split(":")[1])
    for eid in cap.entities:
        e = cat.entities.get(eid)
        if e is None:
            continue
        if cap.target_kind == "entity":
            words += tokens(" ".join([e.name] + list(e.aliases)))
        if e.area:
            areas.add(e.area)
    for a in areas:
        ar = cat.areas.get(a)
        if ar:
            words += tokens(" ".join([ar.name] + list(ar.aliases)))
    return {w for w in words if len(w) >= 3 and w not in _IGNORE and w not in KIND_OF}


def evidence(text_tokens: list[str], own: set[str], others: set[str]) -> set[str]:
    dist = {w for w in own if not any(_same(w, o) for o in others)}
    return {w for w in dist if any(_same(w, t) for t in text_tokens)}


def named(e: Entity, text: str) -> bool:
    """Does the device name carry the generic noun spoken in the text? ("Ventilatore a soffitto" for "ventilatore")"""
    nouns = {t for t in tokens(text) if t in KIND_OF}
    return bool(nouns & set(tokens(" ".join([e.name] + list(e.aliases)))))


def siblings(cat: Catalog, cap_id: str, text: str = "", area: Optional[str] = None) -> list[str]:
    """Other devices the generic reference of `text` can designate, with the same action.

    Devices of the same kind; when some of them carry the spoken noun in their name ("accendi il ventilatore":
    "Ventilatore a soffitto", not "Aspiratore") only those count.
    With `area` (the chosen device is in the microphone room) the model's choice is kept unless its name lacks the
    spoken noun while another device of the room has it ("accendi la lampada": "Lampada scrivania").
    """
    cap = cat.cap(cap_id)
    if cap.target_kind != "entity" or cap.target not in cat.entities:
        return []
    kind = entity_kind(cat.entities[cap.target])
    same = [e for e in cat.entities.values() if entity_kind(e) == kind and cat.has_cap(f"{cap.action}@{e.id}")
            and (area is None or e.area == area)]
    with_noun = [e for e in same if named(e, text)]
    chosen_named = any(e.id == cap.target for e in with_noun)
    if area is not None:
        pool = with_noun if with_noun and not chosen_named else []
    else:
        pool = with_noun or same
    return [f"{cap.action}@{e.id}" for e in pool if e.id != cap.target]


def unsupported_choice(cat: Catalog, cap_id: str, text: str, alternatives: list, p_top: float,
                       ratio: float = 0.15) -> list:
    """Language-independent version of rule 1: devices of the same kind and action that the model also considers
    (probability >= ratio x the chosen one) while the sentence contains no word that belongs to the chosen device
    only (its name or room, compared with those devices). Returns [(capability, prob)] or []."""
    cap = cat.cap(cap_id)
    if cap.target_kind != "entity" or cap.target not in cat.entities:
        return []
    kind = entity_kind(cat.entities[cap.target])
    rivals = []
    for a in alternatives:
        c, p = a.get("capability"), a.get("prob")
        if not c or c in (cap_id, NO_ACTION) or p is None or p < ratio * max(p_top, 1e-9):
            continue
        c2 = cat.cap(c)
        if c2.action != cap.action or c2.target_kind != "entity" or c2.target not in cat.entities:
            continue
        if entity_kind(cat.entities[c2.target]) == kind:
            rivals.append((c, float(p)))
    if not rivals:
        return []
    toks = tokens(text)
    others = set().union(*(descriptor(cat, c) for c, _ in rivals))
    if evidence(toks, descriptor(cat, cap_id), others):
        return []
    # a rival the sentence does designate is not a real alternative either way: leave it to the model
    rivals = [(c, p) for c, p in rivals if not evidence(toks, descriptor(cat, c), descriptor(cat, cap_id))]
    return rivals


def distinguished(cat: Catalog, text: str, options: list[str]) -> Optional[str]:
    """The option whose own words (and only its words) appear in the text."""
    options = [o for o in dict.fromkeys(options) if o and o != NO_ACTION]
    if len(options) < 2 or len({cat.cap(o).action for o in options}) != 1:
        return None
    toks = tokens(text)
    desc = {o: descriptor(cat, o) for o in options}
    hits = []
    for o in options:
        others = set().union(*(desc[x] for x in options if x != o))
        if evidence(toks, desc[o], others):
            hits.append(o)
    return hits[0] if len(hits) == 1 else None


# ------------------------------------------------------------------ garbled speech-to-text output
_VOCAB: Optional[set] = None


def vocab() -> set:
    global _VOCAB
    if _VOCAB is None:
        from pathlib import Path
        f = Path(__file__).with_name("vocab.txt")
        _VOCAB = set(f.read_text(encoding="utf-8").split()) if f.exists() else set()
    return _VOCAB


def catalog_words(cat: Catalog) -> set:
    words = set()
    for e in cat.entities.values():
        words.update(tokens(" ".join([e.name] + list(e.aliases))))
    for a in cat.areas.values():
        words.update(tokens(" ".join([a.name] + list(a.aliases))))
    return words


def understood(text: str, cat_words: set, verb_rx) -> bool:
    """False when no word of the sentence is known: "a cendilati mu" (speech recognition gone wrong).
    Words of 1-2 letters and numbers do not count as evidence either way."""
    voc = vocab()
    if not voc:
        return True
    content = [t for t in tokens(text) if len(t) >= 3 and not _NUM.match(t)]
    if not content:
        return bool(tokens(text))  # "ok", "sì", "no", "22": short answers are fine
    return any(t in voc or t in cat_words or t in KIND_OF or verb_rx.fullmatch(t)
               or any(_same(t, w) for w in cat_words) for t in content)


# ------------------------------------------------------------------ speech-to-text confusions
_STT: Optional[dict] = None


def canon(text: str, cat_words: set, verb_rx) -> str:
    """Undo the speech-to-text confusions the model was trained with, for verbs and generic nouns only
    ("a cendi la tivu" -> "accendi la tivu"). A variant that is a word of this home (e.g. a person called Luca)
    is left alone."""
    global _STT
    if _STT is None:
        import json
        from pathlib import Path
        f = Path(__file__).with_name("stt.json")
        _STT = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        x = Path(__file__).with_name("stt_extra.json")  # variants seen with the streaming recogniser (EdgeSTT)
        if x.exists():
            _STT = {**json.loads(x.read_text(encoding="utf-8")), **_STT}
    t = " " + " ".join(tokens(text)) + " "
    for var, word in sorted(_STT.items(), key=lambda kv: -len(kv[0])):
        if var in cat_words or _common(var) or not (word in KIND_OF or verb_rx.fullmatch(word)):
            continue
        t = t.replace(f" {var} ", f" {word} ")
    return t.strip()


def _common(var: str) -> bool:
    """A confusion learnt from the speech round trip that is a short or grammatical word in some language ("a" ->
    "ar", "het" -> "zet", "por" -> "pon"): replacing it would break ordinary sentences ("liga a televisão")."""
    return " " not in var and (len(var) <= 3 or var in _IGNORE)


_REAL_WORDS = {"which"}  # confusions that are also ordinary words ("which lights are on?" is not "switch")


def canon_verbs(text: str, cat_words: set, verb_rx) -> str:
    """Only the command verbs, on the original text (accents, punctuation and case kept):
    "Spendi tutte le luci" -> "spegni tutte le luci" (speech recognition), so that the verb is recognised when
    the sentence is split into commands and when it is scored."""
    canon("", cat_words, verb_rx)  # loads the table
    out = text
    for var, word in sorted(_STT.items(), key=lambda kv: -len(kv[0])):
        if var in cat_words or var in _REAL_WORDS or _common(var) or not verb_rx.fullmatch(word) \
                or verb_rx.fullmatch(var.replace(" ", "")):
            continue
        out = re.sub(r"(?<!\w)" + re.escape(var).replace("\\ ", r"\s+") + r"(?!\w)", word, out, flags=re.IGNORECASE)
    return out


# ------------------------------------------------------------------ a room word shared by several rooms
def partial_areas(cat: Catalog, text: str) -> list[str]:
    """Rooms that share a word of the sentence ("bagno" -> Bagno padronale, Bagno di servizio)."""
    toks = set(tokens(text))
    out = []
    for a in cat.areas.values():
        words = {w for n in [a.name] + list(a.aliases) for w in tokens(n) if len(w) >= 4 and w not in _IGNORE}
        if words & toks:
            out.append(a.id)
    return out


def name_said(e: Entity, text: str) -> bool:
    """All the content words of the device name are in the sentence ("tapparella della camera" for
    "Tapparella camera")."""
    toks = set(tokens(text))
    for n in [e.name] + list(e.aliases):
        words = {w for w in tokens(n) if len(w) >= 3 and w not in _IGNORE}
        if words and all(any(_same(w, t) for t in toks) for w in words):
            return True
    return False


def name_touched(e: Entity, text: str) -> bool:
    """Some content word of the device name (or alias) is in the sentence."""
    toks = [t for t in tokens(text) if len(t) >= 4]
    for n in [e.name] + list(e.aliases):
        for w in tokens(n):
            if len(w) >= 4 and w not in _IGNORE and any(_same(w, t) for t in toks):
                return True
    return False


def same_in_areas(cat: Catalog, cap_id: str, areas: list[str]) -> list[str]:
    """The same action on devices of the same kind in other rooms (room group if there is one)."""
    cap = cat.cap(cap_id)
    ents = [cat.entities[x] for x in cap.entities if x in cat.entities]
    if not ents:
        return []
    kind = entity_kind(ents[0])
    out = []
    for a in areas:
        groups = [c.id for c in cat.capabilities if c.action == cap.action and c.target_kind == "area_group"
                  and c.target.split(":")[1] == a and all(entity_kind(cat.entities[x]) == kind
                                                          for x in c.entities if x in cat.entities)]
        singles = [f"{cap.action}@{e.id}" for e in cat.entities.values()
                   if e.area == a and entity_kind(e) == kind and cat.has_cap(f"{cap.action}@{e.id}")]
        out += groups[:1] or singles
    return out


# ------------------------------------------------------------------ scene named alone
_SCENE_WORDS = set("attiva avvia metti scena modalita activate start scene mode activa pon escena modo".split())


def scene_named(cat: Catalog, text: str) -> Optional[str]:
    """"buongiorno", "esco di casa", "attiva serata film": the sentence is just the name of one scene."""
    toks = [t for t in tokens(text) if t not in _IGNORE and t not in _SCENE_WORDS]
    if not toks:
        return None
    hits = []
    for c in cat.capabilities:
        if c.action != "scene.activate" or c.target not in cat.entities:
            continue
        e = cat.entities[c.target]
        for n in [e.name] + list(e.aliases):
            words = [w for w in tokens(n) if w not in _IGNORE]
            if words and len(words) == len(toks) and all(_same(a, b) for a, b in zip(words, toks)):
                hits.append(c.id)
                break
    return hits[0] if len(hits) == 1 else None
