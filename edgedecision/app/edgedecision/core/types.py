"""Generic EdgeDecision data model.

Nothing in this module knows about Home Assistant: adapters translate their
own world (entities, services, areas...) into these structures.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

NO_ACTION = "NO_ACTION"

RISK_LEVELS = ["none", "low", "medium", "high"]
POLICIES = ["EXECUTE", "CLARIFY", "REJECT", "ESCALATE"]

# Query-type head classes (predicted from the command alone).
QUERY_TYPES = ["DEVICE", "OUT_OF_DOMAIN", "COMPLEX", "NOOP", "CONFIRM", "HISTORY"]
# word tags of the tagging head: command words, object / room, value, separator between two commands
WORD_TAGS = ["O", "CMD", "OBJ", "VAL", "SEP"]


def max_risk(*levels: str) -> str:
    return max((l for l in levels if l), key=RISK_LEVELS.index, default="low")


@dataclass
class ArgSpec:
    name: str
    kind: str  # percent | temperature | step | enum | number | string
    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = None
    required: bool = True
    default: Any = None
    # enum: canonical value -> {lang: [synonyms]}
    choices: Optional[dict] = None
    # step: which state attribute the step is applied to (for resolution)
    applies_to: Optional[str] = None
    sign: int = 1  # step direction (+1 increase, -1 decrease)

    @staticmethod
    def from_dict(d: dict) -> "ArgSpec":
        return ArgSpec(**d)


@dataclass
class ActionSpec:
    action: str                      # e.g. "light.set_brightness"
    description: str                 # short English description (used by the model)
    domain: str = ""
    args: list[ArgSpec] = field(default_factory=list)
    risk: str = "low"                # none | low | medium | high
    kind: str = "actuate"            # actuate | read
    requires: list[str] = field(default_factory=list)   # entity features required
    groupable: bool = False          # can target "all X in area" groups
    keywords: dict = field(default_factory=dict)          # lang -> [keywords] (lexical retrieval only)
    execute: Optional[dict] = None   # adapter specific mapping (e.g. HA service)

    def __post_init__(self):
        if not self.domain:
            self.domain = self.action.split(".")[0]
        self.args = [a if isinstance(a, ArgSpec) else ArgSpec.from_dict(a) for a in self.args]

    @staticmethod
    def from_dict(d: dict) -> "ActionSpec":
        return ActionSpec(**d)


@dataclass
class Area:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    floor: Optional[str] = None      # floor id ("ground_floor"); the floors' names are in Catalog.meta["floors"]


@dataclass
class Entity:
    id: str
    domain: str
    name: str
    area: Optional[str] = None
    aliases: list[str] = field(default_factory=list)
    device_class: Optional[str] = None
    features: list[str] = field(default_factory=list)
    state: dict = field(default_factory=dict)   # {"state": "on", "brightness": 40, ...}
    attributes: dict = field(default_factory=dict)  # static attrs (min_temp, max_temp, unit...)
    risk_overrides: dict = field(default_factory=dict)  # action -> risk

    @property
    def available(self) -> bool:
        return str(self.state.get("state", "")).lower() not in ("unavailable",)


@dataclass
class Capability:
    id: str
    action: str
    target: str                 # entity id | "area:<area_id>:<domain>" | "all:<domain>"
    target_kind: str = "entity"  # entity | area_group | all_group
    entities: list[str] = field(default_factory=list)
    risk: str = "low"


class Catalog:
    """Runtime set of areas, entities, action specs and capabilities."""

    def __init__(self, areas=None, entities=None, actions=None, capabilities=None, meta=None):
        self.areas: dict[str, Area] = {a.id: a for a in (areas or [])}
        self.entities: dict[str, Entity] = {e.id: e for e in (entities or [])}
        self.actions: dict[str, ActionSpec] = {a.action: a for a in (actions or [])}
        self.capabilities: list[Capability] = list(capabilities or [])
        self.meta: dict = dict(meta or {})
        self._by_id = {c.id: c for c in self.capabilities}

    # ------------------------------------------------------------------ access
    def cap(self, cap_id: str) -> Capability:
        c = self._by_id.get(cap_id)
        if c is None:
            c = self._group_read(cap_id)
            if c is None:
                raise KeyError(cap_id)
        return c

    def _group_read(self, cap_id: str) -> Optional[Capability]:
        """A room / floor / house read built by the runtime ("light.get_state@area:salone:light",
        "humidifier.get_state@all:humidifier"): not in the catalogue (the model does not choose it), but rules and
        logs downstream look it up like any capability. Never added to `capabilities` (retrieval is unchanged)."""
        action, _, target = cap_id.partition("@")
        if not action.endswith(".get_state") or not target:
            return None
        parts = target.split(":")
        if parts[0] == "all" and len(parts) == 2:
            kind, scope, key = "all_group", None, parts[1]
        elif parts[0] in ("area", "floor") and len(parts) == 3:
            kind, scope, key = parts[0] + "_group", parts[1], parts[2]
        else:
            return None
        from .registry import group_key
        ents = []
        for e in self.entities.values():
            if group_key(e) != key and e.domain != key:
                continue
            ar = self.areas.get(e.area or "")
            if kind == "area_group" and e.area != scope:
                continue
            if kind == "floor_group" and (ar is None or ar.floor != scope):
                continue
            ents.append(e.id)
        return Capability(id=cap_id, action=action, target=target, target_kind=kind, entities=ents, risk="none")

    def has_cap(self, cap_id: str) -> bool:
        return cap_id in self._by_id

    def floor_name(self, floor_id: Optional[str]) -> str:
        f = ((self.meta or {}).get("floors") or {}).get(floor_id or "")
        return (f or {}).get("name") or (floor_id or "")

    def floor_aliases(self, floor_id: Optional[str]) -> list:
        f = ((self.meta or {}).get("floors") or {}).get(floor_id or "")
        return list((f or {}).get("aliases") or [])

    def area_name(self, area_id: Optional[str]) -> str:
        if not area_id:
            return ""
        a = self.areas.get(area_id)
        return a.name if a else area_id

    def without(self, cap_ids) -> "Catalog":
        """Copy of the catalog with some capabilities removed."""
        drop = set(cap_ids)
        c = Catalog(list(self.areas.values()), list(self.entities.values()),
                    list(self.actions.values()),
                    [x for x in self.capabilities if x.id not in drop], self.meta)
        return c

    # ------------------------------------------------------------- (de)serialise
    def to_dict(self) -> dict:
        return {
            "meta": self.meta,
            "areas": [asdict(a) for a in self.areas.values()],
            "entities": [asdict(e) for e in self.entities.values()],
            "actions": [asdict(a) for a in self.actions.values()],
            "capabilities": [asdict(c) for c in self.capabilities],
        }

    @staticmethod
    def from_dict(d: dict, build_missing: bool = True) -> "Catalog":
        from .registry import build_capabilities, default_actions

        areas = [Area(**a) for a in d.get("areas", [])]
        entities = [Entity(**e) for e in d.get("entities", [])]
        acts = {a.action: a for a in default_actions()}
        saved = set()
        for a in d.get("actions", []):  # user supplied specs override built-ins
            spec = ActionSpec.from_dict(a)
            if spec.action in acts:
                _add_languages(spec, acts[spec.action])
            acts[spec.action] = spec
            saved.add(spec.action)
        caps = [Capability(**c) for c in d.get("capabilities", [])]
        if not caps and build_missing:
            caps = build_capabilities(areas, entities, list(acts.values()))
        elif caps and saved and build_missing:
            # a catalog saved by an older version: built-in actions added since then get their capabilities
            # (e.g. media_player.get_state, 0.7.1), exactly as a fresh Home Assistant catalog would
            new = [a for name, a in acts.items() if name not in saved and name not in {c.action for c in caps}]
            if new:
                caps = caps + build_capabilities(areas, entities, new)
        used = {c.action for c in caps}
        return Catalog(areas, entities, [acts[a] for a in acts if a in used], caps, d.get("meta"))

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")

    @staticmethod
    def load(path) -> "Catalog":
        return Catalog.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _add_languages(spec: ActionSpec, builtin: ActionSpec) -> None:
    """A saved catalog may predate some languages: keep its words, add the built-in ones it lacks
    (keywords and enum choices such as colour names)."""
    for lang, words in (builtin.keywords or {}).items():
        spec.keywords.setdefault(lang, list(words))
    by_name = {a.name: a for a in builtin.args}
    for arg in spec.args:
        ref = by_name.get(arg.name)
        if arg.choices and ref is not None and ref.choices:
            for value, per_lang in ref.choices.items():
                if value in arg.choices and isinstance(arg.choices[value], dict):
                    for lang, words in per_lang.items():
                        arg.choices[value].setdefault(lang, list(words))


@dataclass
class Decision:
    policy: str                         # EXECUTE | CLARIFY | REJECT | ESCALATE
    reason: str                         # machine readable reason code
    capability: Optional[str] = None
    action: Optional[str] = None
    target: Optional[str] = None
    entities: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    resolved: dict = field(default_factory=dict)     # params resolved against state
    missing_params: list[str] = field(default_factory=list)
    confidence: float = 0.0
    margin: float = 0.0
    risk: str = "low"
    query_type: dict = field(default_factory=dict)
    alternatives: list[dict] = field(default_factory=list)
    text: str = ""
    latency_ms: float = 0.0
    parts: list["Decision"] = field(default_factory=list)  # multi-intent split

    def to_dict(self) -> dict:
        d = asdict(self)
        d["parts"] = [p.to_dict() if isinstance(p, Decision) else p for p in self.parts]
        return d
