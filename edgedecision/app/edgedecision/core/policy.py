"""Decision policy: turns calibrated scores into EXECUTE / CLARIFY / REJECT / ESCALATE.

Confidence alone never authorises execution: probability, margin against
incompatible alternatives, query-type head, availability, parameter validity
and risk level are all checked.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .params import extract_params, validate_and_resolve
from .rules import _ALL_RE, complex_marker
from .text import find_span
from .types import NO_ACTION, QUERY_TYPES, Capability, Catalog, Decision


# actions whose sentences may name a time or a piece of content without being complex requests
# ("previsioni per domani", "metti la radio"): not escalated by the time/condition rules or the COMPLEX type
SELF_TIMED = {"weather.get_state", "media_player.play_content", "agent.weather", "agent.play_content"}
# starting sound on one player: playing a named content also plays, playing also turns the player on
MEDIA_START = {"media_player.turn_on": 0, "media_player.play": 1, "media_player.play_content": 2}


def softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    e = np.exp(x - x.max())
    return e / e.sum()


@dataclass
class PolicyConfig:
    temperature: float = 1.0          # listwise score temperature (calibrated)
    type_temperature: float = 1.0     # query-type head temperature (calibrated)
    exec_prob: dict = field(default_factory=lambda: {"none": 0.45, "low": 0.6, "medium": 0.75, "high": 0.85})
    exec_margin: dict = field(default_factory=lambda: {"none": 0.1, "low": 0.25, "medium": 0.4, "high": 0.5})
    amb_ratio: float = 0.4            # competitor with p >= amb_ratio * p1 -> ambiguity
    amb_min_prob: float = 0.12
    member_tie: float = 1.01          # group vs member within this ratio -> choose the member (>1 = off)
    member_mode: str = "auto"         # how members of the chosen group support it: "sum", "max" or "auto":
    member_ratio: float = 0.6         #   auto = sum when p(group) >= member_ratio * sum(p(members)), else max
    complex_rules: bool = True        # deterministic conditional/scheduled/"everything" guard (core/rules.py)
    scene_keep: float = 0.9           # a scene this likely is not overridden by the NOOP head ("buonanotte")
    complex_override: float = 0.6     # type head: COMPLEX prob that forces ESCALATE
    noop_override: float = 0.6        # type head: NOOP prob that forces REJECT
    ood_override: float = 0.7
    ood_policy: str = "ESCALATE"      # what to do with out-of-domain requests (ESCALATE if an LLM exists)
    confirm_high_risk: bool = True    # high risk actions always require confirmation
    top_k: int = 12
    content_min: float = 0.03         # play_content with tagged content: minimum chance next to NO_ACTION
    media_upgrade: float = 0.25       # turn_on -> play -> play_content on the same player from this probability
    unsupported_min_device: float = 0.6   # NO_ACTION first: "unsupported" only when DEVICE is at least this sure
    catalog_virtual: bool = False     # round 7b+: complete every catalogue with core/virtual.py (assist, house, agent)
    # per-language calibration (lang -> value); a language not listed uses the global value
    lang_temperature: dict = field(default_factory=dict)
    lang_type_temperature: dict = field(default_factory=dict)
    lang_exec_prob: dict = field(default_factory=dict)   # lang -> {risk: min probability} (overrides exec_prob)

    def for_lang(self, lang: Optional[str]) -> "PolicyConfig":
        """The same policy with the temperatures calibrated on this language (itself if none)."""
        lang = (lang or "")[:2].lower()
        if not any(lang in d for d in (self.lang_temperature, self.lang_type_temperature, self.lang_exec_prob)):
            return self
        from dataclasses import replace as _replace
        return _replace(self, temperature=self.lang_temperature.get(lang, self.temperature),
                        type_temperature=self.lang_type_temperature.get(lang, self.type_temperature),
                        exec_prob={**self.exec_prob, **self.lang_exec_prob.get(lang, {})})

    def save(self, path):
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @staticmethod
    def load(path) -> "PolicyConfig":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return PolicyConfig(**{k: v for k, v in d.items() if k in PolicyConfig.__dataclass_fields__})


def _area_of(cat: Catalog, cap: Capability):
    if cap.target_kind == "area_group":
        return cap.target.split(":")[1]
    if cap.target_kind == "all_group":
        return "*"
    if cap.target_kind == "floor_group":
        return cap.target
    e = cat.entities.get(cap.target)
    return e.area if e else None


def compatible(cat: Catalog, a: str, b: str) -> bool:
    """Would executing `a` also satisfy a user who meant `b`? (no clarification needed)"""
    if a == b:
        return True
    if NO_ACTION in (a, b) or not (cat.has_cap(a) and cat.has_cap(b)):
        return False
    ca, cb = cat.cap(a), cat.cap(b)
    sa, sb = cat.actions.get(ca.action), cat.actions.get(cb.action)
    if ca.action in MEDIA_START and cb.action in MEDIA_START and set(ca.entities) == set(cb.entities):
        # "metti radio deejay" executed as play_content also satisfies "turn the radio on" (not the other way round)
        return MEDIA_START[ca.action] >= MEDIA_START[cb.action]
    if sa and sb and sa.kind == "read" and sb.kind == "read":
        return bool(set(ca.entities) & set(cb.entities)) or (_area_of(cat, ca) == _area_of(cat, cb) is not None)
    if ca.action != cb.action:
        return False
    # group vs member of the same group
    return set(cb.entities) <= set(ca.entities) or set(ca.entities) <= set(cb.entities)


def exclude_names_for(cat: Catalog, cap: Capability) -> list[str]:
    names = []
    for eid in cap.entities:
        e = cat.entities.get(eid)
        if e:
            names += [e.name] + e.aliases
            tw = cat.entities.get((e.attributes or {}).get("twin") or "")
            if tw is not None:  # "sul satellite" names the Music Assistant player's twin
                names += [tw.name] + tw.aliases
            a = cat.areas.get(e.area) if e.area else None
            if a:
                names += [a.name] + a.aliases
    for a in cat.areas.values():
        names += [a.name] + a.aliases
    return list(dict.fromkeys(names))


def decide(cfg: PolicyConfig, cat: Catalog, text: str, cand_ids: list[str], scores: np.ndarray,
           type_logits: np.ndarray, value_text: Optional[str] = None) -> Decision:
    """cand_ids[i] <-> scores[i]; NO_ACTION must be one of the candidates.
    value_text: the words the tagging head marked as the value ("al 40%"), parsed instead of the whole sentence."""
    d = _decide(cfg, cat, text, cand_ids, scores, type_logits, value_text)
    if cfg.complex_rules and (d.policy in ("EXECUTE", "CLARIFY") or d.reason == "unsupported") \
            and d.action != "weather.get_state" and not (d.action or "").startswith("assist."):
        # a weather question names a day ("domani", "sabato") and a timer / alarm a time ("alle 7", "tra 10 minuti")
        # without being scheduled requests
        m = complex_marker(text)
        if m and (d.action or "").startswith("home.") and _ALL_RE.fullmatch(m):
            m = None  # "spegni tutto" IS the whole-house action
        if m:
            d.policy, d.reason = "ESCALATE", f"complex_rule:{m}"
    return d


def _decide(cfg: PolicyConfig, cat: Catalog, text: str, cand_ids: list[str], scores: np.ndarray,
            type_logits: np.ndarray, value_text: Optional[str] = None) -> Decision:
    probs = softmax(np.asarray(scores) / cfg.temperature)
    tprobs = softmax(np.asarray(type_logits) / cfg.type_temperature)
    qtype = {t: float(p) for t, p in zip(QUERY_TYPES, tprobs)}
    order = np.argsort(-probs)
    alts = [{"capability": cand_ids[i], "prob": float(probs[i])} for i in order[:5]]
    no_idx = cand_ids.index(NO_ACTION)
    p_no = float(probs[no_idx])
    top = int(order[0])

    def mk(policy, reason, **kw):
        return Decision(policy=policy, reason=reason, query_type=qtype, alternatives=alts, text=text, **kw)

    # "metti un po' di jazz", no room said: the type head reads a request for content as COMPLEX and NO_ACTION takes
    # much of the mass, but the home has a Music Assistant player, the model tagged the content and gives that
    # player the only real chance -> NO_ACTION is not a reading of its own here (the room checks come later)
    real = [int(i) for i in order if int(i) != no_idx]
    content_first = False
    if real and cat.cap(cand_ids[real[0]]).action == "media_player.play_content":
        r = real[0]
        if not value_text and probs[r] >= cfg.content_min and not any(
                find_span(text, n, 0.85) for a in cat.areas.values() for n in [a.name] + a.aliases):
            # the tagging head saw no content (it was trained on homes without Music Assistant too): the words after
            # the play verb ("spiel etwas Jazz")
            from .media import guess_content
            value_text = guess_content(text, exclude_names_for(cat, cat.cap(cand_ids[r])))
        if value_text and probs[r] >= cfg.content_min and probs[r] + p_no >= 0.95 \
                and max(qtype["OUT_OF_DOMAIN"], qtype["NOOP"]) < 0.3:  # "metti un timer": not music
            content_first = True
            probs = probs.copy()
            probs[no_idx] = 0.0
            probs = probs / probs.sum()
            order = np.argsort(-probs)
            p_no, top = 0.0, r

    # 0) not a command: "what did you do?" / an answer "yes" (handled by the server / the dialogue)
    if qtype.get("HISTORY", 0.0) >= 0.5:
        return mk("REJECT", "history", confidence=qtype["HISTORY"])
    if qtype.get("CONFIRM", 0.0) >= 0.5:
        return mk("REJECT", "confirm", confidence=qtype["CONFIRM"])

    # 1) query-type overrides (conditional / scheduled / multi-step, negations)
    # "metti radio deejay" / "che tempo farà sabato" are single capabilities in a home that has them, even if the
    # sentence looks like a content request or has a time word: the capability, when clearly first, wins
    top_act = cat.cap(cand_ids[top]).action if cand_ids[top] != NO_ACTION else None
    if content_first or (top_act in SELF_TIMED and probs[top] >= 0.5):
        pass
    elif qtype["COMPLEX"] >= cfg.complex_override:
        return mk("ESCALATE", "complex_request", confidence=qtype["COMPLEX"])
    if qtype["NOOP"] >= cfg.noop_override:
        # scene names are free phrases ("Buonanotte", "Sono a casa") that look like chit-chat to the type head
        tid = cand_ids[top]
        if not (tid != NO_ACTION and cat.cap(tid).action == "scene.activate" and probs[top] >= cfg.scene_keep):
            return mk("REJECT", "noop", confidence=qtype["NOOP"])

    # 2) NO_ACTION wins
    if top == no_idx:
        t = max(qtype, key=qtype.get)
        if t == "DEVICE" and qtype["DEVICE"] < cfg.unsupported_min_device:
            # "che tempo farà domani?" / "mets France Inter dans le salon" in a home without a weather entity or a
            # Music Assistant player there: the type head is torn between a device command and a question or request
            # for something else -> the other assistant may answer it; "I can't" only for clear device commands
            other = max(("OUT_OF_DOMAIN", "COMPLEX"), key=lambda k: qtype[k])
            return mk(cfg.ood_policy if other == "OUT_OF_DOMAIN" else "ESCALATE",
                      "out_of_domain" if other == "OUT_OF_DOMAIN" else "complex_request", confidence=p_no)
        if t == "DEVICE":
            return mk("REJECT", "unsupported", confidence=p_no)
        if t == "OUT_OF_DOMAIN":
            return mk(cfg.ood_policy, "out_of_domain", confidence=p_no)
        if t == "COMPLEX":
            return mk("ESCALATE", "complex_request", confidence=p_no)
        if t in ("HISTORY", "CONFIRM"):
            return mk("REJECT", t.lower(), confidence=p_no)
        return mk("REJECT", "noop", confidence=p_no)
    if qtype["OUT_OF_DOMAIN"] >= cfg.ood_override and probs[top] < 0.5:
        return mk(cfg.ood_policy, "out_of_domain", confidence=qtype["OUT_OF_DOMAIN"])

    # least impact: if a group ("all lights in the kitchen") and one of its members are nearly tied,
    # act on the member (smaller blast radius, and it is correct in both readings)
    cap = cat.cap(cand_ids[top])
    if cap.target_kind != "entity":
        for i in order[1:]:
            cid = cand_ids[i]
            if probs[i] < cfg.member_tie * probs[top]:
                break
            if cid != NO_ACTION:
                c2 = cat.cap(cid)
                if c2.action == cap.action and set(c2.entities) < set(cap.entities):
                    top = int(i)
                    break
    if cap.action in MEDIA_START:
        # "mach Musik in der Küche an": turn_on 0.65 / play 0.34 on the same radio -> play (it turns the radio on too);
        # play_content only when the model tagged what to play
        for i in order[1:]:
            cid = cand_ids[i]
            if cid == NO_ACTION or probs[i] < cfg.media_upgrade:
                continue
            c2 = cat.cap(cid)
            if c2.action in MEDIA_START and set(c2.entities) == set(cap.entities) \
                    and MEDIA_START[c2.action] > MEDIA_START[cap.action] \
                    and (c2.action != "media_player.play_content" or value_text):
                top, cap = int(i), c2
    top_id = cand_ids[top]
    cap = cat.cap(top_id)
    p1 = float(probs[top])
    comp_mass, member_max, member_sum, incompat = 0.0, 0.0, 0.0, []
    for i in order:
        if int(i) == top:
            continue
        cid = cand_ids[i]
        if cid != NO_ACTION and compatible(cat, top_id, cid):
            c2 = cat.cap(cid)
            if c2.action == cap.action and set(c2.entities) < set(cap.entities):
                # members of the chosen group: probability spread over many single lights is uncertainty about
                # WHICH light, not support for "all of them" -> count only the best member
                member_max = max(member_max, float(probs[i]))
                member_sum += float(probs[i])
            else:
                comp_mass += float(probs[i])
        else:
            incompat.append((cid, float(probs[i])))
    # members of the chosen group: when the group itself is the dominant reading they support it ("the kitchen
    # lights" = group 0.53 + single kitchen lights 0.47); when the mass is spread over many single lights and the
    # group is only marginally ahead ("turn on a light"), it is uncertainty about WHICH light -> count the best one
    use_sum = cfg.member_mode == "sum" or (cfg.member_mode == "auto" and p1 >= cfg.member_ratio * member_sum)
    comp_mass += member_sum if use_sum else member_max
    p_eff = p1 + comp_mass
    p2 = incompat[0][1] if incompat else 0.0
    margin = p_eff - p2
    base = dict(capability=top_id, action=cap.action, target=cap.target, entities=list(cap.entities),
                confidence=p_eff, margin=margin, risk=cap.risk)

    # 3) ambiguity between incompatible real candidates -> ask
    competitors = [(c, p) for c, p in incompat if c != NO_ACTION and p >= max(cfg.amb_ratio * p1, cfg.amb_min_prob)]
    if competitors:
        d = mk("CLARIFY", "ambiguous", **base)
        d.alternatives = [{"capability": top_id, "prob": p1}] + [{"capability": c, "prob": p} for c, p in competitors]
        return d

    # 4) not confident enough
    if p_eff < cfg.exec_prob.get(cap.risk, 0.9) or margin < cfg.exec_margin.get(cap.risk, 0.5):
        if qtype["COMPLEX"] > qtype["DEVICE"]:
            return mk("ESCALATE", "complex_low_confidence", **base)
        if p_no >= p1 * 0.8 and qtype["OUT_OF_DOMAIN"] > qtype["DEVICE"]:
            return mk(cfg.ood_policy, "out_of_domain", **base)
        return mk("CLARIFY", "low_confidence", **base)

    return finalize(cfg, cat, text, top_id, base, mk, value_text)


def finalize(cfg: PolicyConfig, cat: Catalog, text: str, cap_id: str, base: Optional[dict] = None, mk=None,
             value_text: Optional[str] = None) -> Decision:
    """Steps after the capability is chosen: availability, deterministic parameters, risk.

    Also used by the dialogue follow-up ("la seconda", "quella in cucina") once the user has picked an option.
    """
    cap = cat.cap(cap_id)
    spec = cat.actions.get(cap.action)
    if base is None:
        base = dict(capability=cap_id, action=cap.action, target=cap.target, entities=list(cap.entities),
                    confidence=1.0, margin=1.0, risk=cap.risk)
    if mk is None:
        def mk(policy, reason, **kw):
            return Decision(policy=policy, reason=reason, text=text, **kw)

    # 4b) the home cannot do it itself (no weather entity, no list, no Music Assistant): the other agent does
    if cap.action.startswith("agent."):
        return mk("ESCALATE", "delegated", **base)

    # 5) availability
    ents = [cat.entities[e] for e in cap.entities if e in cat.entities]
    if ents and all(not e.available for e in ents):
        return mk("REJECT", "unavailable", **base)

    # 6) deterministic parameters + validation
    names = exclude_names_for(cat, cap)
    if spec is not None and any(a.kind == "text" for a in spec.args):
        # free text (the song / station to play) comes ONLY from the words the model marked as the value: the whole
        # sentence ("metti radio deejay in cucina") is never searched for
        params, missing, meta = extract_params(value_text or "", spec, names)
        if cap.action == "media_player.play_content":
            from .media import guess_content, is_generic_music, media_type, strip_target
            if params.get("content"):
                # the player's own name is not the content ("riproduci radio dj su Musica", player "Musica")
                c = strip_target(params["content"], names)
                if not c or is_generic_music(c):
                    c = guess_content(text, names) or c
                if c:
                    from .media import spoken_digits
                    params["content"] = spoken_digits(c)
                    missing = [m for m in missing if m != "content"]
                else:
                    params.pop("content", None)
            if is_generic_music(params.get("content")):
                params.pop("content", None)  # "metti della musica": nothing to search for
                missing = list(dict.fromkeys(list(missing) + ["content"]))
            kind = media_type(text)
            if kind and not missing:
                params["media_type"] = kind
    elif spec is not None and any(a.kind == "source" for a in spec.args):
        # "metti HDMI 1", "passa a Netflix": the tagged words, else a source of the device said in the sentence
        params, missing, meta = extract_params(value_text or "", spec, names)
        if missing and ents:
            from .text import normalize as _n
            t = " " + _n(text) + " "
            hit = [src for src in (ents[0].attributes or {}).get("sources") or [] if " " + _n(str(src)) + " " in t]
            if hit:
                params, missing, meta = {"source": max(hit, key=len)}, [], {"source": {"source": "word"}}
    elif value_text:
        params, missing, meta = extract_params(value_text, spec, names)
        if missing:  # the tagging head missed the value: read the whole sentence as before
            params, missing, meta = extract_params(text, spec, names)
    else:
        params, missing, meta = extract_params(text, spec, names)
    resolved, invalid = validate_and_resolve(spec, params, meta, ents) if spec else ({}, [])
    base.update(params=params, resolved=resolved, missing_params=missing)
    if missing:
        return mk("CLARIFY", "missing_param", **base)
    if invalid:
        return mk("CLARIFY", "invalid_param:" + ",".join(f"{a}={r}" for a, r in invalid), **base)

    # 7) risk
    if cap.risk == "high" and cfg.confirm_high_risk:
        return mk("CLARIFY", "confirm_high_risk", **base)
    return mk("EXECUTE", "ok", **base)
