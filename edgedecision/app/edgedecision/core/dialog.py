"""Short dialogue memory: answers to EdgeDecision's own questions.

After a CLARIFY ("Intendi TV cucina o TV soggiorno?", "Confermi l'apertura del garage?", "A che valore?") the next
utterance of the same session, within `ttl` seconds, is first read as an answer:

  confirm_high_risk   "sì" / "confermo" / "yes" / "sí"      -> the pending action is executed
  any question        "no" / "annulla" / "lascia stare"      -> cancelled
  ambiguous options   "la seconda" / "the first" / "la última"   -> that option
                      "cucina" / "quella del soggiorno" / "TV cucina" -> the option in that room / with that name
                      "entrambe" / "both" / "ambas"          -> all the options (low/none risk only)
  missing / invalid   "al 40 per cento" / "rosso" / "22"     -> original sentence + answer, decided again

Anything that is not recognised as an answer is handled as a new command (the question is dropped).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, replace
from typing import Optional

from .text import find_span, normalize
from .types import NO_ACTION, Decision

_YES = re.compile(r"^(?:si|sì|sí|yes|yeah|yep|ok|okay|va bene|certo|certamente|confermo|conferma|procedi|vai|fallo|"
                  r"sure|confirm|do it|go ahead|claro|confirmo|adelante|hazlo|dale|vale)(?:\s+(?:grazie|thanks|gracias|"
                  r"per favore|please|por favor|dai|pure))*$")
_NO = re.compile(r"^(?:no|nope|annulla|lascia stare|lascia perdere|niente|non importa|stop|basta|cancel|never ?mind|"
                 r"forget it|cancela|olvidalo|déjalo|dejalo|nada)(?:\s+(?:grazie|thanks|gracias))*$")
_ORD = [(re.compile(r"\b(?:prim[ao]|first|primer[ao]?|uno|una|1)\b"), 0),
        (re.compile(r"\b(?:second[ao]|second|segund[ao]|due|dos|two|2)\b"), 1),
        (re.compile(r"\b(?:terz[ao]|third|tercer[ao]?|tre|tres|three|3)\b"), 2),
        (re.compile(r"\b(?:ultim[ao]|last|ultim[ao])\b"), -1)]
_ALL = re.compile(r"\b(?:entramb[ei]|tutt[ei] e due|tutt[ei]|both|all of them|ambas|ambos|tod[ao]s)\b")
_WORDS_MAX = 6  # an answer is short; longer sentences are new commands


@dataclass
class Pending:
    decision: Decision
    text: str
    context_area: Optional[str]
    t: float
    reasked: bool = False


class Dialog:
    def __init__(self, engine, ttl: float = 30.0):
        self.engine = engine
        self.ttl = ttl
        self.pending: dict[str, Pending] = {}
        self.unanswered: dict[str, Pending] = {}   # question whose answer was not understood (this turn only)

    def remember(self, session: str, d: Decision, text: str, context_area: Optional[str], reasked: bool = False):
        if d.policy == "CLARIFY":
            self.pending[session] = Pending(d, text, context_area, time.time(), reasked)
        else:
            self.pending.pop(session, None)

    def follow_up(self, session: str, answer: str, context_area: Optional[str]) -> Optional[Decision]:
        self.unanswered.pop(session, None)
        p = self.pending.pop(session, None)
        if p is None or time.time() - p.t > self.ttl:
            return None
        d = self._follow_up(p, answer)
        if d is None:
            self.unanswered[session] = p
        return d

    def reask(self, session: str, d: Decision, answer: str) -> Optional[Decision]:
        """A short reply that is neither an answer nor a command ("sì" to a three-way question, "boh"):
        ask the same question once more instead of dropping it."""
        p = self.unanswered.pop(session, None)
        if p is None or p.reasked or len(normalize(answer).split()) > 3:
            return None
        if d.policy == "REJECT" and d.reason in ("noop", "unsupported"):
            p.reasked, p.t = True, time.time()
            return replace(p.decision, text=p.text)
        return None

    def _follow_up(self, p: Pending, answer: str) -> Optional[Decision]:
        a = normalize(answer).strip(" .!?")
        if not a:
            return None
        kind = p.decision.reason.split(":")[0]
        if _NO.match(a) or (not _YES.match(a) and self._model_says(answer, "NOOP")):
            return Decision(policy="REJECT", reason="cancelled", text=answer)
        if kind == "confirm_high_risk":
            if _YES.match(a) or self._model_says(answer, "CONFIRM"):
                return replace(p.decision, policy="EXECUTE", reason="confirmed", text=f"{p.text} → {answer}")
            return None
        alts = [x for x in p.decision.alternatives if x.get("capability") not in (None, NO_ACTION)]
        # the options actually proposed: the top one and those with a real probability (not the 1e-7 tail)
        options = [x["capability"] for i, x in enumerate(alts) if i == 0 or x.get("prob") is None or x["prob"] >= 0.02]
        if not options and kind == "low_confidence" and p.decision.capability:
            options = [p.decision.capability]  # "Non sono sicuro: intendi Portone box?" names the top candidate
        options = list(dict.fromkeys(options))
        if kind in ("ambiguous", "low_confidence") and options and len(a.split()) >= 3 and not _YES.match(a):
            # a new command instead of an answer ("Allume la lumière du salon" after a question about the weather):
            # if on its own it is clear and is none of the options, it is a new request
            alone = self.engine._decide(answer, p.context_area)
            if alone.policy == "EXECUTE" and alone.capability and alone.capability not in options:
                return None
        if kind in ("ambiguous", "low_confidence") and options and len(a.split()) <= _WORDS_MAX:
            pick = self._pick(options, a, answer)
            if pick == "ALL":
                return self._all(options, p)
            if pick:
                return self._finalize(pick, p, answer)
            if (_YES.match(a) or self._model_says(answer, "CONFIRM")) \
                    and len({self.engine.catalog.cap(o).target for o in options}) == 1:
                # "Non sono sicuro: intendi Portone box?" - "sì": the one device named in the question
                # (a high-risk action is then still confirmed separately)
                return self._finalize(options[0], p, answer)
        spec = self.engine.catalog.actions.get(p.decision.action or "")
        if kind == "missing_param" and p.decision.capability and spec is not None \
                and any(a_.kind in ("text", "duration", "time", "source") for a_ in spec.args):
            # "Cosa vuoi ascoltare?" - "radio deejay" / "Per quanto tempo?" - "dieci minuti" / "Cosa aggiungo alla
            # lista?" - "il latte": the whole answer is the value
            from .policy import finalize
            d = finalize(self.engine.policy, self.engine.catalog, f"{p.text} {answer}", p.decision.capability,
                         value_text=answer)
            d.text = f"{p.text} → {answer}"
            if d.policy == "EXECUTE":
                d.reason = "clarified"
            return d
        if kind in ("ambiguous", "low_confidence", "missing_param", "invalid_param") and len(a.split()) <= _WORDS_MAX:
            merged = f"{p.text} {answer}"
            d = self.engine._decide(merged, p.context_area)
            if d.policy == "EXECUTE" and (not options or kind in ("missing_param", "invalid_param")
                                          or d.capability in options):
                d.reason = "clarified"
                return d
            if d.policy == "CLARIFY" and kind in ("missing_param", "invalid_param"):
                return d
        return None

    # ------------------------------------------------------------------ helpers
    def _model_says(self, answer: str, qtype: str, threshold: float = 0.6) -> bool:
        """For the languages without word lists: the query-type head recognises "ja" / "oui" (CONFIRM) and
        "nee" / "non merci" (NOOP). Only short answers; models without these types simply answer False."""
        if len(normalize(answer).split()) > 4:
            return False
        try:
            qt = self.engine.query_type(answer)
            if "CONFIRM" not in qt:  # model trained before the CONFIRM / HISTORY types: it cannot tell yes from no
                return False
            return qt.get(qtype, 0.0) >= threshold
        except Exception:  # noqa: BLE001  (backend without type head...)
            return False

    def _pick(self, options: list[str], a: str, raw: str):
        cat = self.engine.catalog
        if _ALL.search(a):
            return "ALL"
        for rx, i in _ORD:
            if rx.search(a) and len(a.split()) <= 3:
                return options[i] if -len(options) <= i < len(options) else None
        # a room: "cucina", "quella del soggiorno"
        area = self.engine.mentioned_area(raw)
        if area:
            hits = [o for o in options if self._area_of(o) == area]
            if len(hits) == 1:
                return hits[0]
        # a device name: "TV cucina", "l'abat-jour di Paolo"
        best, best_len = None, 0
        for o in options:
            for eid in cat.cap(o).entities[:1]:
                e = cat.entities.get(eid)
                for name in ([e.name] + e.aliases) if e else []:
                    if len(name) > best_len and find_span(raw, name, 0.85):
                        best, best_len = o, len(name)
        if best is None:  # "quello di servizio": a word that only one option has
            from .specific import distinguished
            best = distinguished(cat, raw, options)
        if best is None and len(a.split()) <= 3:
            # "climatizzatore" for "Climatizzatore mansarda" when several options are actions on the same device
            from .specific import tokens
            words = {w for w in tokens(raw) if len(w) >= 4}
            hit = [o for o in options if cat.cap(o).target in cat.entities
                   and words & set(tokens(cat.entities[cat.cap(o).target].name))]
            if hit and len({cat.cap(o).target for o in hit}) == 1:
                best = hit[0]
        return best

    def _area_of(self, cap_id: str) -> Optional[str]:
        cat = self.engine.catalog
        cap = cat.cap(cap_id)
        if cap.target_kind == "area_group":
            return cap.target.split(":")[1]
        e = cat.entities.get(cap.target)
        return e.area if e else None

    def _finalize(self, cap_id: str, p: Pending, answer: str) -> Decision:
        from .policy import finalize

        d = finalize(self.engine.policy, self.engine.catalog, p.text, cap_id)
        d.text = f"{p.text} → {answer}"
        if d.policy == "EXECUTE":
            d.reason = "clarified"
        return d

    def _all(self, options: list[str], p: Pending) -> Optional[Decision]:
        cat = self.engine.catalog
        if len(options) > 4 or any(cat.cap(o).risk not in ("none", "low") for o in options) \
                or len({cat.cap(o).action for o in options}) > 1:
            return None  # "tutte" picks every option of the same action, never two different actions
        parts = [self._finalize(o, p, "tutte") for o in options]
        if all(x.policy == "EXECUTE" for x in parts):
            return Decision(policy="EXECUTE", reason="multi_intent", parts=parts, text=p.text,
                            confidence=min(x.confidence for x in parts))
        return None
