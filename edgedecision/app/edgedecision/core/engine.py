"""EdgeDecision engine: retrieval -> semantic scoring -> calibrated policy."""
from __future__ import annotations

import re
import time
from dataclasses import replace
from typing import Optional, Protocol

import numpy as np

from . import policy as pol
from . import specific
from .media import guess_content
from .render import NO_ACTION_TEXT, capability_text, lexical_doc, query_text
from .retrieval import HybridRetriever
from .text import find_span, normalize
from .types import NO_ACTION, Catalog, Decision


class Backend(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...

    def score(self, query: str, cand_texts: list[str]) -> tuple[np.ndarray, np.ndarray]: ...


# Conjunctions used to split multi-intent commands (applied on the raw text,
# so Italian "è" (is) is not confused with "e" (and)).
_SPLIT = re.compile(r"\s*(?:,\s*)?\b(?:e poi|e anche|and then|and also|y luego|y después|y despues|y también|"
                    r"poi|then|ed|e|and|y)\b\s+", re.IGNORECASE)


# conjunctions inside numbers are not command separators: "cuarenta y cinco", "one hundred and five", "e mezzo"
_NUM_CONJ = re.compile(r"\b(veinte|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|hundred|thousand|"
                       r"\d+)\s+(y|and|e)\s+(?=(uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|one|two|three|four|"
                       r"five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|a half|"
                       r"half|mezzo|mezza|medio|media|\d)\b)", re.IGNORECASE)


def split_intents(text: str) -> list[str]:
    guarded = _NUM_CONJ.sub(lambda m: m.group(1) + "\x00" + m.group(2) + "\x00", text)
    parts = [p.strip(" ,.").replace("\x00", " ") for p in _SPLIT.split(guarded) if p and p.strip(" ,.")]
    if len(parts) < 2 or any(len(p.split()) < 1 for p in parts):
        return [text]
    return parts


class EdgeDecisionEngine:
    def __init__(self, backend: Backend, policy: Optional[pol.PolicyConfig] = None, split_multi: bool = True,
                 dialog_ttl: float = 30.0):
        from .dialog import Dialog

        self.backend = backend
        self.policy = policy or pol.PolicyConfig()
        self.split_multi = split_multi
        self.catalog: Optional[Catalog] = None
        self.retriever: Optional[HybridRetriever] = None
        self.dialog = Dialog(self, ttl=dialog_ttl)
        self._tag_cache: dict = {}
        self._pol_cache: dict = {}
        self._lang: Optional[str] = None

    # --------------------------------------------------------------- catalog
    def set_catalog(self, catalog: Catalog) -> None:
        if getattr(self.policy, "catalog_virtual", False):
            from .virtual import complete
            catalog = complete(catalog)  # the virtual entities the model was trained with (core/virtual.py)
        self.catalog = catalog
        self._cat_words = specific.catalog_words(catalog)
        ids = [c.id for c in catalog.capabilities]
        embed = getattr(self.backend, "embed", None)
        self.retriever = HybridRetriever(ids, [lexical_doc(catalog, i) for i in ids], embed_fn=embed,
                                         bi_texts=[capability_text(catalog, i, with_state=False) for i in ids])

    def update_state(self, entity_id: str, state: dict) -> None:
        """States change often; embeddings do not depend on them, so this is free."""
        if self.catalog and entity_id in self.catalog.entities:
            self.catalog.entities[entity_id].state = dict(state)

    # ---------------------------------------------------------------- decide
    def candidates(self, text: str, context_area: Optional[str] = None) -> list[str]:
        cat = self.catalog
        q = query_text(text, cat.area_name(context_area) if context_area else None)
        k = self.policy.top_k
        if len(cat.capabilities) <= k:
            ids = [c.id for c in cat.capabilities]
        else:
            qemb = self.backend.embed([q])[0] if self.retriever.emb is not None else None
            lex_q = text + (" " + cat.area_name(context_area) if context_area else "")
            ids = [c for c, _ in self.retriever.retrieve(lex_q, k, qemb)]
        return [NO_ACTION] + ids

    # ------------------------------------------------------------ word tags (model with a tagging head)
    def tags(self, text: str) -> Optional[list]:
        """[(word, tag)] from the model (O / CMD / OBJ / VAL / SEP), None for models without a tagging head."""
        fn = getattr(self.backend, "tag", None)
        if fn is None:
            return None
        key = " ".join(text.split())
        if key not in self._tag_cache:
            if len(self._tag_cache) > 256:
                self._tag_cache.clear()
            self._tag_cache[key] = fn(key)
        return self._tag_cache[key]

    def query_type(self, text: str) -> dict:
        """Query-type probabilities of a short text (used for answers: "ja" -> CONFIRM, "nee" -> NOOP)."""
        from .types import QUERY_TYPES
        _, tl = self.backend.score(query_text(text), [NO_ACTION_TEXT])
        z = np.asarray(tl)[0] / max(1e-6, self.policy.type_temperature)
        p = np.exp(z - z.max())
        p /= p.sum()
        return {t: float(x) for t, x in zip(QUERY_TYPES, p)}

    @staticmethod
    def _value_text(tags: Optional[list]) -> Optional[str]:
        vals = [w for w, t in tags or [] if t == "VAL"]
        return " ".join(vals) if vals else None

    def _parts(self, text: str) -> list:
        """[(part text, part tags or None)]: the model's SEP words split the commands; regex split otherwise."""
        tags = self.tags(text)
        if not tags:
            return [(p, None) for p in split_intents(text)]
        parts, cur = [], []
        for w, t in tags:
            if t == "SEP":
                if cur:
                    parts.append(cur)
                cur = []
            else:
                cur.append((w, t))
        if cur:
            parts.append(cur)
        parts = [p for p in parts if any(t in ("CMD", "OBJ", "VAL") for _, t in p)]
        if len(parts) < 2:
            # the tagging head rarely marks "e"/"und"/"et" as SEP: split at conjunctions, using its CMD tags
            parts = self._split_at_conj(tags, self._lang)
        if len(parts) < 2:
            return [(text, tags)]
        return [(" ".join(w for w, _ in p).strip(" ,"), p) for p in parts]

    @staticmethod
    def _split_at_conj(tags: list, lang: Optional[str] = None) -> list:
        """Split [(word, tag)] at "and" words. A plain conjunction ("e", "und", "et", "och") always splits (so that
        "accendi la specchiera e l'aspiratore" gets its two parts); a word that is also an article or preposition
        in another language ("i", "en") splits only when a command word follows."""
        def bare(w):
            return normalize(w, accents=True).strip(" ,.;:!?")  # accents kept: Italian "è" is not "e"
        cuts = []
        for i, (w, _) in enumerate(tags):
            b = bare(w)
            if i == 0 or i == len(tags) - 1 or b not in _CONJ_ANY | set(_CONJ_CMD):
                continue
            prev, nxt = bare(tags[i - 1][0]), bare(tags[i + 1][0])
            if _NUMLIKE.fullmatch(prev) and (_NUMLIKE.fullmatch(nxt) or nxt in _HALFLIKE):
                continue  # "venti e mezzo", "cuarenta y cinco", "zwei und zwanzig"
            if tags[i][1] == "VAL" or (tags[i - 1][1] == "VAL" and tags[i + 1][1] == "VAL"):
                continue  # inside a value: "annuncia che la cena è pronta e venite a tavola", "pane e latte"
            j = i + 1
            while j < len(tags) and bare(tags[j][0]) in _THEN:
                j += 1
            rest = tags[j:]
            if b in _CONJ_CMD and lang and lang not in _CONJ_CMD[b]:
                continue  # Italian "i" is an article, Spanish/French "en" a preposition
            if b in _CONJ_CMD and not (rest and rest[0][1] == "CMD"):
                continue  # "zet het licht aan en doe ...", "włącz ... i wyłącz ..."; not "pon en marcha", "i faretti"
            if not rest:
                continue
            cuts.append((i, j))
        if not cuts:
            return []
        parts, start = [], 0
        for i, j in cuts:
            parts.append(tags[start:i])
            start = j
        parts.append(tags[start:])
        parts = [p for p in parts if p]
        if any(not any(t in ("CMD", "OBJ", "VAL") for _, t in p) for p in parts):
            return []
        return parts

    @staticmethod
    def _has_verb(part: str, ptags: Optional[list]) -> bool:
        if ptags is not None:
            return any(t == "CMD" for _, t in ptags)
        return bool(_VERB.search(normalize(part)))

    def decide_single(self, text: str, context_area: Optional[str] = None) -> Decision:
        t0 = time.perf_counter()
        cat = self.catalog
        cand = self.candidates(text, context_area)
        q = query_text(text, cat.area_name(context_area) if context_area else None)
        texts = [NO_ACTION_TEXT if c == NO_ACTION else capability_text(cat, c) for c in cand]
        scores, type_logits = self.backend.score(q, texts)
        d = pol.decide(self.policy, cat, text, cand, np.asarray(scores), np.asarray(type_logits)[0],
                       value_text=self._value_text(self.tags(text)))
        d = self._specific(d, text, context_area)
        d.latency_ms = (time.perf_counter() - t0) * 1000
        return d

    def decide(self, text: str, context_area: Optional[str] = None, session: Optional[str] = None,
               lang: Optional[str] = None, device: Optional[str] = None) -> Decision:
        """lang: language of the sentence (Assist sends it): the temperatures calibrated on that language are used,
        and conjunctions that are articles/prepositions in other languages are read with that language only.
        Not thread safe (the server serialises requests with a lock)."""
        base, self._lang = self.policy, (lang or "")[:2].lower() or None
        if lang:
            if lang not in self._pol_cache:
                self._pol_cache[lang] = base.for_lang(lang)
            self.policy = self._pol_cache[lang]
        self._device = device  # the HA device of the satellite that heard it (players of that device first)
        try:
            return self._decide_session(text, context_area, session)
        finally:
            self.policy, self._lang, self._device = base, None, None

    def _decide_session(self, text: str, context_area: Optional[str] = None, session: Optional[str] = None) -> Decision:
        """session: id of the conversation (e.g. the voice satellite). With a session, an answer to EdgeDecision's
        own question ("la seconda", "sì", "al 40%") is understood for `dialog_ttl` seconds (see core/dialog.py).
        Without a session every sentence is independent (evaluation, batch use)."""
        if self.catalog is None:
            raise RuntimeError("call set_catalog() first")
        t0 = time.perf_counter()
        if session is not None:
            d = self.dialog.follow_up(session, text, context_area)
            base_text, reasked = text, False
            if d is None:
                d = self._decide(text, context_area)
                again = self.dialog.reask(session, d, text)
                if again is not None:
                    d, base_text, reasked = again, again.text, True
            else:  # an answer: a further question refers to the original request, not to the answer alone
                base_text = d.text.split(" → ")[0]
            if d.policy == "CLARIFY" and d.parts:
                base_text = d.text  # the question is about one part of the sentence only
            self.dialog.remember(session, d, base_text, context_area, reasked)
            d.latency_ms = (time.perf_counter() - t0) * 1000
            return d
        return self._decide(text, context_area)

    def _decide(self, text: str, context_area: Optional[str] = None) -> Decision:
        if not normalize(text):
            return Decision(policy="REJECT", reason="empty", text=text)
        text = specific.canon_verbs(text, self._cat_words, _VERB)  # "Spendi tutte le luci" -> "spegni ..."
        if not specific.understood(text, self._cat_words, _VERB):
            # no known word at all: garbled speech recognition ("a cendilati mu"); never let the model guess
            return Decision(policy="CLARIFY", reason="not_understood", text=text)
        t0 = time.perf_counter()
        # the room named in the sentence wins over the room of the microphone ("abbassa la luce della cucina" said
        # in the bedroom); the model was trained with the microphone room only when no room is spoken
        if context_area and self.mentioned_area(text):
            context_area = None
        whole = self.decide_single(text, context_area)
        if context_area and whole.policy != "EXECUTE" and not whole.reason.startswith("complex") \
                and (whole.reason == "unsupported" or not self._room_has(context_area, whole.capability)):
            # nothing of that kind in this room ("accendi la tv" in a bedroom without a TV): look in the whole house;
            # if the house has exactly one, it is used (a choice confirmed by the user)
            alt = self.decide_single(text, None)
            if alt.policy == "EXECUTE" or (alt.policy != "REJECT" and whole.policy == "REJECT"):
                alt.reason = alt.reason if alt.policy != "EXECUTE" else "ok_whole_house"
                whole = alt
        if not self.split_multi or whole.reason.startswith("complex_rule"):
            return whole
        tagged_parts = self._parts(text)
        if len(tagged_parts) < 2:
            return whole
        parts = [p for p, _ in tagged_parts]
        ptags = [t for _, t in tagged_parts]
        # two parts with a verb each = two commands, whatever the whole-sentence score says; otherwise a confident
        # single decision wins (avoids false splits such as "la luce e accesa?", "è" typed without accent)
        n_verbs = sum(self._has_verb(p, t) for p, t in tagged_parts)
        first = None
        if whole.policy == "EXECUTE" and whole.query_type.get("COMPLEX", 0) < 0.3 and n_verbs < 2:
            # confident whole-sentence reading: keep it if the first clause alone agrees with it
            first = self.decide_single(parts[0], context_area)
            if first.policy != "EXECUTE" and self._only_later_part(whole, parts):
                pass  # "accendi la specchiera e l'aspiratore": the whole reading covers the aspiratore only
            elif first.policy != "EXECUTE" or (whole.capability and first.capability
                                               and pol.compatible(self.catalog, whole.capability, first.capability)):
                return whole
        ds = []
        for k, p in enumerate(parts):
            if k == 0 and first is not None:
                ds.append(first)
                continue
            if ds and not self._has_verb(p, ptags[k]):
                # a fragment without a verb ("… e del soggiorno") only makes sense with the previous verb: never
                # let the model decide it alone (it once picked "close the shutters" for "del soggiorno")
                d = self._ellipsis(ds[-1], p) if ds[-1].policy == "EXECUTE" else None
                if d is None and (ds[-1].policy == "EXECUTE" or (ds[-1].policy == "CLARIFY" and ds[-1].action)):
                    # the previous part may itself be a question ("la specchiera?"): its verb still applies here
                    d = self._ellipsis_device(ds[-1], parts[k - 1], p, context_area, ptags[k - 1])
                d = d or Decision(policy="CLARIFY", reason="fragment", text=p)
            else:
                d = self.decide_single(p, context_area)
                if d.policy != "EXECUTE" and ds and ds[-1].policy == "EXECUTE":
                    d = self._ellipsis(ds[-1], p, d) or d
            ds.append(d)
        # a part answered without any device ("dove sei ..." inside a sentence heard from the TV) is not a command
        ds = [d if d.capability or d.policy != "EXECUTE" else replace(d, policy="ESCALATE", reason="out_of_domain")
              for d in ds]
        caps = {d.capability for d in ds}
        if all(d.policy == "EXECUTE" for d in ds) and len(caps) == len(ds):
            return Decision(policy="EXECUTE", reason="multi_intent", parts=ds, text=text,
                            confidence=min(d.confidence for d in ds), latency_ms=(time.perf_counter() - t0) * 1000)
        unclear = [d for d in ds if d.policy != "EXECUTE"]
        if len(unclear) == 1 and unclear[0].policy == "CLARIFY" and unclear[0].reason != "fragment":
            # "accendi la luce del bagno e spegni la luce in cucina": do what is clear, ask about the rest
            # ("Spengo le luci in Cucina. Intendi Specchiera o Luce bagno di servizio?")
            q = unclear[0]
            return replace(q, parts=[d for d in ds if d.policy == "EXECUTE"],
                           latency_ms=(time.perf_counter() - t0) * 1000)
        if any(d.policy == "EXECUTE" for d in ds):
            # several commands, only some understood: never execute half of them, hand the whole request over
            return Decision(policy="ESCALATE", reason="multi_intent_partial", parts=ds, text=text,
                            query_type=whole.query_type, latency_ms=(time.perf_counter() - t0) * 1000)
        whole.latency_ms = (time.perf_counter() - t0) * 1000
        return whole

    def _specific(self, d: Decision, text: str, context_area: Optional[str]) -> Decision:
        d = self._specific_core(d, text, context_area)
        return self._after_rules(d, text, context_area)

    # ------------------------------------------------------------------ 0.7.1 rules
    _ALARM_Q = re.compile(r"\b(?:sveglia|alarm|alarma|despertador|r[ée]veil|wecker|wekker|alarme|budzik|v[äa]ckarklocka|"
                          r"larm|timer|minuteur|temporizador|minutnik)\b", re.I)
    _WHEN_Q = re.compile(r"\b(?:a che or\w*|quando|che or\w*|what time|when|a qu[ée] hora|cu[aá]ndo|[àa] quelle heure|quand|"
                         r"um wie viel uhr|wann|hoe laat|wanneer|a que horas|o kt[óo]rej|kiedy|vilken tid|n[äa]r|"
                         r"quanto manca|how long|cu[aá]nto falta|combien de temps|wie lange|hoe lang|quanto falta|"
                         r"ile zosta|hur l[äa]nge)\b", re.I)
    _WHERE_ME = re.compile(r"\b(?:in che stanza (?:sei|ti trovi)|dove (?:sei|ti trovi)|where are you|which room are you|"
                           r"d[óo]nde est[áa]s|en qu[ée] (?:habitaci[óo]n|cuarto) est[áa]s|o[ùu] es[- ]tu|o[ùu] [êe]tes[- ]vous|"
                           r"dans quelle pi[èe]ce|wo bist du|in welchem (?:raum|zimmer)|waar ben je|in welke kamer|"
                           r"onde est[áa]s|em que (?:divis[ãa]o|quarto|sala)|gdzie jeste[śs]|w kt[óo]rym pokoju|"
                           r"var [äa]r du|i vilket rum)\b", re.I)

    def _self_rules(self, d: Decision, text: str, context_area: Optional[str]) -> Optional[Decision]:
        """Questions about the assistant itself (no device): "in che stanza ti trovi?" -> the satellite's room;
        "a che ora è la sveglia?" -> the timers' state (an alarm is the timer "Sveglia")."""
        cat = self.catalog
        from .clock import clock_question
        kind = clock_question(text)
        if kind:  # "che ore sono?", "che giorno è oggi?": the clock of this machine
            return Decision(policy="EXECUTE", reason=f"self_{kind}", params={}, text=text, query_type=d.query_type)
        if self._WHERE_ME.search(text or "") and len((text or "").split()) <= 8:
            name = cat.area_name(context_area) if context_area and context_area in cat.areas else None
            return Decision(policy="EXECUTE" if name else "ESCALATE", reason="self_location" if name else "out_of_domain",
                            params={"area": name} if name else {}, text=text, query_type=d.query_type)
        if self._ALARM_Q.search(text or "") and self._WHEN_Q.search(text or "") \
                and cat.has_cap("assist.timer_status@assist.voice") \
                and not (d.policy == "EXECUTE" and (d.action or "").startswith("assist.")):
            cap = cat.cap("assist.timer_status@assist.voice")
            return replace(d, policy="EXECUTE", reason="ok_alarm_status", capability=cap.id, action=cap.action,
                           target=cap.target, entities=list(cap.entities), params={}, missing_params=[], risk="none")
        return None

    def _after_rules(self, d: Decision, text: str, context_area: Optional[str]) -> Decision:
        out = self._self_rules(d, text, context_area)
        if out is not None:
            return out
        out = self._state_question(d, text, context_area)
        if out is not None:
            return out
        out = self._room_only(d, text, context_area)
        if out is not None:
            return out
        out = self._resume_music(d)
        if out is not None:
            return self._media_route(out, text, context_area) or out
        out = self._media_route(d, text, context_area)
        if out is not None:
            return out
        out = self._kind_mismatch(d, text)
        if out is not None:
            return out
        out = self._close_not_off(d, text)
        if out is not None:
            return out
        out = self._lock_contradicted(d, text) or self._appliance_mismatch(d, text)
        if out is not None:
            return out
        out = self._content_not_track(d, text)
        return out if out is not None else d

    def _content_not_track(self, d: Decision, text: str) -> Optional[Decision]:
        """"ik wil naar andré hazes luisteren" executed as "previous track": a name to play was said and the player
        can search -> play it."""
        cat = self.catalog
        if d.policy != "EXECUTE" or d.action not in ("media_player.previous_track", "media_player.next_track") \
                or not d.target:
            return None
        cap_id = f"media_player.play_content@{d.target}"
        if not cat.has_cap(cap_id):
            return None
        from .media import guess_content, is_generic_music
        vt = self._value_text(self.tags(text)) or guess_content(text, pol.exclude_names_for(cat, cat.cap(cap_id)))
        if not vt or is_generic_music(vt) or len(specific.tokens(vt)) < 2 and not self._value_text(self.tags(text)):
            return None
        out = pol.finalize(self.policy, cat, text, cap_id, value_text=vt)
        return out if out.policy == "EXECUTE" and (out.params or {}).get("content") else None

    _CLOSE = set("chiudi chiudere close shut cierra cerrar ferme fermer fermez schliess schliesse schliessen schließ "
                 "schließe sluit sluiten fecha fechar zamknij zamknac stang stäng".split())
    _OPEN = set("apri aprire open abre abrir ouvre ouvrir ouvrez offne öffne oeffne open openen abre abrir otworz "
                "otwórz oppna öppna".split())

    def _close_not_off(self, d: Decision, text: str) -> Optional[Decision]:
        """"chiudi il lucernario della mansarda" executed as "turn off the attic light": closing / opening verbs are
        about covers; when a cover is a real alternative, ask instead of switching a light ("chiudi la luce" is
        still said in some regions, so the light stays an option)."""
        cat = self.catalog
        if d.policy != "EXECUTE" or d.action not in ("light.turn_off", "light.turn_on", "switch.turn_off",
                                                     "switch.turn_on"):
            return None
        toks = set(specific.tokens(text))
        want = "cover.close" if toks & self._CLOSE else "cover.open" if toks & self._OPEN else None
        if want is None or (want == "cover.close") != d.action.endswith("turn_off"):
            return None
        covers = [a for a in d.alternatives or [] if a.get("capability") and a["capability"] != NO_ACTION
                  and cat.has_cap(a["capability"]) and cat.cap(a["capability"]).action == want
                  and (a.get("prob") or 0) >= 0.03]
        if not covers:
            # 0.8.3: no cover among the alternatives, but the sentence names something the light is not
            # ("lucernario"): a cover of the home named that way is offered next to the light
            e = cat.entities.get(d.target or "")
            own = set(specific.tokens(" ".join([e.name] + list(e.aliases)))) if e else set()
            extra = [w for w in self._content_words(text) if w not in own and len(w) >= 4]
            if not extra:
                return None
            named = [c for c in cat.capabilities if c.action == want and c.target_kind == "entity"
                     and c.target in cat.entities
                     and set(specific.tokens(cat.entities[c.target].name)) & set(extra)]
            covers = [{"capability": c.id, "prob": 0.0} for c in named[:2]] or \
                [a for a in d.alternatives or [] if a.get("capability") and a["capability"] != NO_ACTION
                 and cat.has_cap(a["capability"]) and cat.cap(a["capability"]).action == want][:2]
            if not covers:
                return None
        alts = [{"capability": d.capability, "prob": d.confidence}] + covers[:2]
        return replace(d, policy="CLARIFY", reason="ambiguous", alternatives=alts)

    # unlock said, lock chosen ("doe de voordeur van het slot" = unlock the front door): never lock instead
    _UNLOCK_RX = re.compile(r"\b(?:sblocca|apri la serratura|unlock|desbloquea|abre la cerradura|d[ée]verrouill\w*|"
                            r"aufschlie\w*|aufsperr\w*|entriegel\w*|van het slot|ontgrendel\w*|destranc\w*|"
                            r"desbloqueia|odblokuj|otw[óo]rz zamek|l[åa]s upp)\b", re.I)

    def _lock_contradicted(self, d: Decision, text: str) -> Optional[Decision]:
        if d.policy != "EXECUTE" or d.action != "lock.lock" or not self._UNLOCK_RX.search(text or ""):
            return None
        unlock = f"lock.unlock@{d.target}"
        if not self.catalog.has_cap(unlock):
            return replace(d, policy="CLARIFY", reason="low_confidence")
        out = pol.finalize(self.policy, self.catalog, text, unlock)
        out.query_type, out.alternatives = d.query_type, d.alternatives
        if out.policy == "EXECUTE":  # unlocking is high risk: always confirmed
            out.policy, out.reason = "CLARIFY", "confirm_high_risk"
        return out

    # appliances that people tell apart by one word ("máquina de lavar loiça" is not "... roupa")
    _APPLIANCE = {
        "dishwasher": r"lavastoviglie|dishwasher|lavavajillas|lave[- ]vaisselle|geschirrsp[üu]l\w*|sp[üu]lmaschine|"
                      r"vaatwas\w*|lou[çc]a|loi[çc]a|lava[- ]lou[çc]as?|zmywark\w*|diskmaskin\w*",
        "washer": r"lavatrice|washing machine|washer|lavadora|lave[- ]linge|waschmaschine|wasmachine|roupa|pralk\w*|"
                  r"tv[äa]ttmaskin\w*",
        "dryer": r"asciugatrice|dryer|secadora|s[èe]che[- ]linge|trockner|droger|m[áa]quina de secar|suszark\w*|"
                 r"torktumlare",
        "oven": r"forno|oven|horno|four|backofen|ofen|piekarnik|ugn\w*",
        "coffee": r"caff[èe]|coffee|cafetera|caf[ée]|kaffee\w*|koffie\w*|ekspres|kaffe\w*",
    }
    _APPLIANCE_RX = {k: re.compile(rf"\b(?:{v})\b", re.I) for k, v in _APPLIANCE.items()}

    def _appliance_mismatch(self, d: Decision, text: str) -> Optional[Decision]:
        """"liga a máquina de lavar loiça" executed on the washing machine: the sentence names one appliance, the
        chosen device is another one -> not executed (the home has no dishwasher)."""
        if d.policy != "EXECUTE" or not d.target or d.target not in self.catalog.entities:
            return None
        said = {k for k, rx in self._APPLIANCE_RX.items() if rx.search(text or "")}
        if len(said) != 1:
            return None
        e = self.catalog.entities[d.target]
        name = " ".join([e.name, e.id.split(".", 1)[-1].replace("_", " ")] + list(e.aliases))
        is_ = {k for k, rx in self._APPLIANCE_RX.items() if rx.search(name)}
        if not is_ or is_ & said:
            return None
        return replace(d, policy="REJECT", reason="unsupported", capability=None, action=None, target=None,
                       entities=[])

    def _kind_mismatch(self, d: Decision, text: str) -> Optional[Decision]:
        """"accendi la tv" said in the kitchen executed on the kitchen radio: the sentence names a kind of player (tv)
        that the chosen one is not. The players of that kind decide: one -> it, several -> which one?"""
        cat = self.catalog
        if d.policy not in ("EXECUTE", "CLARIFY") or not d.target or d.target not in cat.entities or not d.action \
                or not d.action.startswith("media_player."):
            return None
        from .registry import group_key
        kinds = {specific.KIND_OF[t] for t in specific.tokens(text) if t in specific.KIND_OF}
        kinds = {k for k in kinds if k.startswith("media_player.")}
        if d.policy == "CLARIFY":
            # "which one?" offers only players of the kind said ("accendi la tv": not the radio)
            if d.reason not in ("ambiguous", "low_confidence") or len(kinds) != 1:
                return None
            kind = next(iter(kinds))
            alts = [a for a in d.alternatives or [] if a.get("capability") not in (None, NO_ACTION)
                    and cat.has_cap(a["capability"])]
            keep = [a for a in alts if cat.cap(a["capability"]).target in cat.entities
                    and group_key(cat.entities[cat.cap(a["capability"]).target]) == kind]
            if not keep or len(keep) == len(alts):
                return None
            if len(keep) == 1:
                c = cat.cap(keep[0]["capability"])
                return replace(d, policy="EXECUTE", reason="ok_kind", capability=c.id, target=c.target,
                               entities=list(c.entities), alternatives=keep)
            c = cat.cap(keep[0]["capability"])
            return replace(d, capability=c.id, target=c.target, entities=list(c.entities), alternatives=keep)
        e = cat.entities[d.target]
        if len(kinds) != 1 or group_key(e) in kinds or specific.name_said(e, text):
            return None
        kind = next(iter(kinds))
        opts = [x for x in cat.entities.values() if group_key(x) == kind and cat.has_cap(f"{d.action}@{x.id}")]
        if not opts:
            return None
        if len(opts) == 1:
            cap = f"{d.action}@{opts[0].id}"
            return replace(d, capability=cap, target=opts[0].id, entities=[opts[0].id], reason="ok_kind")
        alts = [{"capability": f"{d.action}@{x.id}", "prob": round(1.0 / len(opts), 3)} for x in opts]
        return replace(d, policy="CLARIFY", reason="ambiguous", alternatives=alts, capability=alts[0]["capability"],
                       target=opts[0].id, entities=[opts[0].id])

    def _resume_music(self, d: Decision) -> Optional[Decision]:
        """"riproduci della musica su satellite": music on a Music Assistant player without saying what.
        * the model hesitates between "play" and "play by name" on the SAME player (a question with the same name
          twice), or chose "play by name" with nothing to search: no content was said, so
        * the player has something to resume (a title in its state) -> play it;
        * otherwise -> "what do you want to listen to?" (play by name, missing content)."""
        cat = self.catalog
        if d.policy not in ("CLARIFY", "EXECUTE") or not d.target or d.target not in cat.entities:
            return None
        acts = {"media_player.play", "media_player.play_content", "media_player.turn_on"}
        if d.action not in acts:
            return None
        if d.policy == "CLARIFY":
            if d.reason == "missing_param":
                if d.action != "media_player.play_content" or "content" not in (d.missing_params or []):
                    return None
            elif d.reason in ("low_confidence", "ambiguous"):
                real = [a for a in d.alternatives or [] if a.get("capability") not in (None, NO_ACTION)
                        and (a.get("prob") or 0) >= 0.1]
                if not real or any(not cat.has_cap(a["capability"]) or cat.cap(a["capability"]).action not in acts
                                   for a in real):
                    return None
                targets = {cat.cap(a["capability"]).target for a in real}
                if len(targets) > 1:
                    # "metti la musica" between the TV and the Music Assistant speaker: music -> the speaker
                    from .media import MUSIC_WORDS
                    search = [t for t in targets if t in cat.entities and "search" in (cat.entities[t].features or [])]
                    if len(search) != 1 or not (set(specific.tokens(d.text or "")) & MUSIC_WORDS):
                        return None
                    d = replace(d, target=search[0])
                elif not any(cat.cap(a["capability"]).action == "media_player.play_content" for a in real):
                    return None
            else:
                return None
        elif d.action != "media_player.play_content":
            return None  # plain play chosen by the model: it stands
        from .media import is_generic_music
        vt = self._value_text(self.tags(d.text or ""))
        if vt and not is_generic_music(vt):
            return None  # something to search was said: the model's choice stands
        if d.policy == "EXECUTE" and (d.params or {}).get("content") and not is_generic_music(d.params["content"]):
            return None
        e = cat.entities[d.target]
        play, by_name = f"media_player.play@{d.target}", f"media_player.play_content@{d.target}"
        if (e.state or {}).get("media_title") and cat.has_cap(play):
            return replace(d, policy="EXECUTE", reason="ok_resume", capability=play, action="media_player.play",
                           params={}, missing_params=[], alternatives=[])
        if cat.has_cap(by_name):
            return replace(d, policy="CLARIFY", reason="missing_param", capability=by_name,
                           action="media_player.play_content", params={}, missing_params=["content"], alternatives=[])
        return None

    _PLAYER_ACTS = ("media_player.play_content", "media_player.play", "media_player.pause", "media_player.stop",
                    "media_player.next_track", "media_player.previous_track", "media_player.volume_up",
                    "media_player.volume_down", "media_player.volume_set", "media_player.mute")
    _STOP_ACTS = ("media_player.pause", "media_player.stop", "media_player.next_track", "media_player.previous_track",
                  "media_player.volume_up", "media_player.volume_down", "media_player.volume_set",
                  "media_player.mute")

    _STOP_ONLY = ("media_player.pause", "media_player.stop", "media_player.next_track", "media_player.previous_track")
    _VOLUME_ACTS = ("media_player.volume_up", "media_player.volume_down", "media_player.volume_set",
                    "media_player.mute")

    def _one_speaker(self, ents: list):
        """One entity when all of them are the same speaker (an ESPHome player and its Music Assistant twin): the
        one playing, else the ESPHome one; None for two different speakers."""
        if not ents:
            return None
        if len(ents) == 1:
            return ents[0]
        ids = {e.id for e in ents}
        if not all(((e.attributes or {}).get("twin") in ids) for e in ents) or len(ents) > 2:
            return None
        playing = [e for e in ents if str((e.state or {}).get("state")) == "playing"]
        if len(playing) == 1:
            return playing[0]
        return next((e for e in ents if (e.attributes or {}).get("platform") != "music_assistant"), ents[0])

    def _linked(self, eid: str) -> set:
        """The HA devices a player belongs to: its own and its twin's (the Music Assistant player of a Voice PE)."""
        cat = self.catalog
        e = cat.entities.get(eid)
        if e is None:
            return set()
        a = e.attributes or {}
        out = {a.get("device")}
        tw = cat.entities.get(a.get("twin") or "")
        if tw is not None:
            out.add((tw.attributes or {}).get("device"))
        return {x for x in out if x}

    def _media_route(self, d: Decision, text: str, context_area: Optional[str]) -> Optional[Decision]:
        """Which player, when the sentence does not say it (0.8.2):
        * a player named in the sentence that cannot do it, whose twin can ("metti Radio DJ sul satellite": the
          ESPHome player of the Voice PE cannot search, its Music Assistant twin can) -> the twin;
        * "ferma la musica" -> the one player that is playing;
        * the player of the satellite that heard the sentence (same device, or its twin);
        * the one candidate in the microphone's room, speakers before TVs; the one speaker among the candidates."""
        cat = self.catalog
        if not (d.action or "") in self._PLAYER_ACTS or d.policy not in ("CLARIFY", "EXECUTE"):
            return None
        if d.policy == "CLARIFY" and d.reason.split(":")[0] not in ("ambiguous", "low_confidence", "missing_param"):
            return None
        act = d.action
        rivals = [a for a in d.alternatives or [] if a.get("capability") not in (None, NO_ACTION)
                  and (a.get("prob") or 0) >= 0.05 and cat.has_cap(a["capability"])
                  and cat.cap(a["capability"]).action != act]
        if d.policy == "CLARIFY" and rivals:
            return None  # the model hesitates about WHAT to do ("meteo Milan aujourd'hui"), not about where
        if len([t for t in specific.tokens(text) if len(t) >= 3]) < 2:
            return None  # "By", "Ok": too little said to act on a player
        players = [e for e in cat.entities.values() if e.domain == "media_player"]
        able = [e for e in players if cat.has_cap(f"{act}@{e.id}")]
        if not able:
            return None
        from .media import MUSIC_WORDS, guess_content
        # a player called "Musica" is not named by "ferma la musica"
        named = [e for e in players if specific.name_said(e, text)
                 and not set(specific.tokens(e.name)) <= MUSIC_WORDS | specific._IGNORE]
        pick = None
        if named:
            ok = [e for e in named if e.id in {a.id for a in able}]
            if ok:
                return None  # a player that can do it is named: the model and the name rules decide
            else:
                tids = list(dict.fromkeys((e.attributes or {}).get("twin") for e in named))
                able_ids = {e.id for e in able}
                twins = [cat.entities[t] for t in tids if t in able_ids]
                if len(twins) != 1:
                    return None
                pick = twins[0]
        elif self.mentioned_area(text):
            return None  # "metti la radio in cucina": the model and the room rules decide
        else:
            if d.policy == "CLARIFY" and d.reason.split(":")[0] == "missing_param":
                return None
            pool = [cat.cap(a["capability"]).target for a in d.alternatives or []
                    if a.get("capability") not in (None, NO_ACTION) and cat.has_cap(a["capability"])
                    and cat.cap(a["capability"]).action == act]
            pool = [cat.entities[t] for t in dict.fromkeys(pool + [d.target]) if t in cat.entities]
            able_ids = {e.id for e in able}
            pool = [e for e in pool if e.id in able_ids]
            dev = getattr(self, "_device", None)
            mine = [e for e in able if dev and dev in self._linked(e.id)]
            if d.policy == "EXECUTE" and not (act in ("media_player.play_content", "media_player.play") and mine):
                return None  # the model chose a player: only the satellite's own player can override it
            toks = set(specific.tokens(text))
            kind_said = any(t in specific.KIND_OF and t not in MUSIC_WORDS for t in toks)
            music_said = bool(toks & MUSIC_WORDS)
            own = self._one_speaker(mine)  # the satellite's speaker (its ESPHome player and its twin = one)
            if act in self._STOP_ONLY and not kind_said:  # "ferma la musica", not "... la radio" / "... la tv"
                playing = [e for e in pool if str((e.state or {}).get("state")) == "playing"
                           and not (music_said and (e.device_class or "") == "tv")]
                mine_playing = [e for e in playing if e in mine]
                if mine_playing:
                    pick = self._one_speaker(mine_playing)
                elif len(playing) == 1:
                    pick = playing[0]
            elif act in self._VOLUME_ACTS and d.policy == "CLARIFY" and not kind_said:
                # "abbassa il volume" said to a satellite: its own speaker, else the one candidate in its room
                room = [e for e in pool if context_area and e.area == context_area]
                pick = own or (room[0] if len(room) == 1 else None)
            if pick is None and act in ("media_player.play_content", "media_player.play") and mine:
                search = [e for e in mine if "search" in (e.features or [])]
                pick = search[0] if act == "media_player.play_content" and len(search) == 1 else own
            if pick is None and d.policy == "CLARIFY" and len(pool) > 1 and act == "media_player.play_content":
                room = [e for e in pool if context_area and e.area == context_area]
                speakers = [e for e in (room or pool) if (e.device_class or "") != "tv"]
                for group in (room, speakers):
                    if len(group) == 1:
                        pick = group[0]
                        break
            if pick is None:
                return None
        cap_id = f"{act}@{pick.id}"
        if cap_id == d.capability and d.policy == "EXECUTE":
            return None
        cap = cat.cap(cap_id)
        vt = None
        if act == "media_player.play_content":
            vt = (d.params or {}).get("content") or self._value_text(self.tags(text)) \
                or guess_content(text, pol.exclude_names_for(cat, cap))
        out = pol.finalize(self.policy, cat, text, cap_id, dict(
            capability=cap_id, action=act, target=cap.target, entities=list(cap.entities),
            confidence=max(d.confidence or 0, 0.9), margin=d.margin, risk=cap.risk), value_text=vt)
        out.query_type, out.alternatives = d.query_type, d.alternatives
        if out.policy == "EXECUTE":
            out.reason = "ok_media_route"
        elif out.policy == "CLARIFY" and out.reason.split(":")[0] == "missing_param" and act == "media_player.play_content":
            pass  # the player is known, the content is asked
        else:
            return None
        return out

    def _content_words(self, text: str) -> list:
        """Words of the sentence that could name a device: not verbs, function words, numbers or room names."""
        cat = self.catalog
        area_words = set()
        for a in cat.areas.values():
            for n in [a.name] + a.aliases:
                area_words.update(specific.tokens(n))
        out = []
        for t in specific.tokens(text):
            if t in specific._IGNORE or specific._NUM.match(t) or _VERB.fullmatch(t) or t in specific.LANG_VERBS:
                continue
            if t in area_words or any(specific._same(t, w) or (len(w) >= 4 and t.startswith(w) and len(t) - len(w) <= 4)
                                      for w in area_words if len(w) >= 4):
                continue
            out.append(t)
        return out

    def _state_question(self, d: Decision, text: str, context_area: Optional[str]) -> Optional[Decision]:
        """"la luce del salone è accesa?" (two lights): the state of every light of the room, not "which one?".
        "ci sono luci accese?" / "quali finestre sono aperte?": the list over the whole house. Read only."""
        from . import states as S
        cat = self.catalog
        read = d.action and d.action.endswith(".get_state") and d.action != "weather.get_state" \
            and d.action != "sensor.get_state" and d.action != "climate.get_state"
        toks = set(specific.tokens(text))
        kinds = {specific.KIND_OF[t] for t in toks if t in specific.KIND_OF}
        domains = {k.split(".")[0] for k in kinds}
        asks_state = bool(toks & S.state_words())
        if not read:
            # the model escalated or hesitated on "quali luci sono accese?": a question, one kind of device, a state word
            if d.policy == "EXECUTE" or not asks_state or len(domains) != 1 or not (toks & S.QUESTION_WORDS):
                return None
            dom = next(iter(domains))
            if dom not in S.SUMMARY:
                return None
        else:
            dom = d.action.split(".")[0]
        if d.policy == "EXECUTE" and d.reason not in ("ok", "ok_room", "ok_full_name"):
            return None
        # a device named by its own name ("la lampada ad arco è accesa?") is answered by the model's own choice
        cand = [e for e in cat.entities.values() if e.domain == dom]
        if dom == "binary_sensor":
            cand = [e for e in cand if e.device_class in ("window", "door")]
        if read and d.entities:
            from .registry import group_key
            keys = {group_key(cat.entities[x]) for x in d.entities if x in cat.entities}
            if dom == "binary_sensor" and keys <= {"binary_sensor.window", "binary_sensor.door"}:
                keys = {"binary_sensor.window", "binary_sensor.door"}
            cand = [e for e in cat.entities.values() if e.domain == dom and group_key(e) in keys]
        if not cand:
            return None
        if any(specific.name_said(e, text) for e in cand if len([w for w in specific.tokens(e.name)
                                                                 if w not in specific._IGNORE]) >= 1
               and not set(specific.tokens(e.name)) <= self._area_and_kind_words()):
            return None
        area = self._loose_area(text)
        if area is None and d.policy == "EXECUTE":
            return None  # one device, no room said: the model's answer stands
        if area is None and read and d.policy == "CLARIFY":
            alts = [cat.cap(a["capability"]) for a in d.alternatives or [] if a.get("capability") not in (None, NO_ACTION)]
            rooms = {cat.entities[c.target].area for c in alts if c.target in cat.entities}
            if len(rooms) == 1 and not (toks & S.QUESTION_WORDS):
                area = next(iter(rooms))
        if area is None and context_area and not (toks & S.QUESTION_WORDS) and \
                any(e.area == context_area for e in cand):
            area = context_area  # "la luce è accesa?" in a room with two lights
        ents = [e for e in cand if e.area == area] if area else cand
        if not ents:
            return None
        if area and len(ents) == 1 and d.policy == "EXECUTE":
            return None
        cap_action = f"{dom}.get_state"
        if cap_action not in cat.actions:
            return None
        target = f"area:{area}:{dom}" if area else f"all:{dom}"
        # capability id in the usual form ("light.get_state@area:salone:light", "...@all:light"): not a capability of
        # the catalog (reading a whole room is done here, not by the model), only a name for logs and tests
        return Decision(policy="EXECUTE", reason="ok_room_state" if area else "ok_house_state",
                        capability=f"{cap_action}@{target}",
                        action=cap_action, target=target, entities=[e.id for e in ents], risk="none",
                        confidence=d.confidence, query_type=d.query_type, alternatives=d.alternatives, text=text)

    def _loose_area(self, text: str) -> Optional[str]:
        """mentioned_area, or a room whose name starts a word of the sentence with an inflection ("vardagsrummet",
        "salonie", "Wohnzimmers"): one-word room names only."""
        a = self.mentioned_area(text)
        if a:
            return a
        toks = specific.tokens(text)
        hits = set()
        for ar in self.catalog.areas.values():
            for n in [ar.name] + ar.aliases:
                nt = specific.tokens(n)
                if len(nt) == 1 and len(nt[0]) >= 4 and any(t.startswith(nt[0]) and len(t) - len(nt[0]) <= 4
                                                            for t in toks):
                    hits.add(ar.id)
        return next(iter(hits)) if len(hits) == 1 else None

    def _area_and_kind_words(self) -> set:
        out = set(specific.KIND_OF)
        for a in self.catalog.areas.values():
            for n in [a.name] + a.aliases:
                out.update(specific.tokens(n))
        return out

    def _room_only(self, d: Decision, text: str, context_area: Optional[str]) -> Optional[Decision]:
        """"allume le salon" / "tänd vardagsrummet": only a verb and a room. Said of a room, "turn on" means its light:
        never the TV or a plug chosen by the model."""
        if d.policy not in ("EXECUTE", "CLARIFY") or not d.action or d.parts:
            return None
        if d.policy == "CLARIFY" and d.reason not in ("low_confidence", "ambiguous"):
            return None
        dom, _, act = d.action.partition(".")
        if dom == "light" or act not in ("turn_on", "turn_off"):
            return None
        if self._content_words(text):
            return None  # the sentence names something ("accendi la tv del salone", "accendi la stufetta")
        cat = self.catalog
        area = self._loose_area(text) or context_area
        if not area:
            return None
        lights = [c for c in cat.capabilities if c.action == f"light.{act}" and
                  (c.target == f"area:{area}:light" or (c.target_kind == "entity" and c.target in cat.entities
                                                         and cat.entities[c.target].area == area))]
        group = [c for c in lights if c.target_kind == "area_group"]
        pick = group[0] if group else (lights[0] if len(lights) == 1 else None)
        if pick is None:
            return replace(d, policy="CLARIFY", reason="low_confidence")
        out = pol.finalize(self.policy, cat, text, pick.id)
        out.query_type, out.alternatives = d.query_type, d.alternatives
        if out.policy == "EXECUTE":
            out.reason = "ok_room_light"
        return out

    def _specific_core(self, d: Decision, text: str, context_area: Optional[str]) -> Decision:
        """Which device does the sentence designate? (see core/specific.py)"""
        cat = self.catalog
        if d.action == "media_player.play_content" and d.policy in ("EXECUTE", "CLARIFY") and d.capability:
            # "metti radio capital in taverna": the only Music Assistant player is in the kitchen; the room said has
            # none -> never play it elsewhere, the other assistant may know a way
            e = cat.entities.get(cat.cap(d.capability).target)
            said = self.mentioned_area(text)
            if e is not None and said and said != e.area:
                return replace(d, policy="ESCALATE", reason="content_other_room")
        if d.policy == "REJECT" and d.reason == "unsupported" and d.alternatives:
            # "accendi la stufetta del bagno" with NO_ACTION narrowly first: the sentence says the full name of the
            # runner-up device, so ask ("Intendi Stufetta bagno?") instead of answering "I can't do that"
            named_alt = [a for a in d.alternatives[1:3] if a.get("capability") not in (None, NO_ACTION)
                         and (a.get("prob") or 0) >= 0.2 and cat.cap(a["capability"]).target_kind == "entity"
                         and specific.name_said(cat.entities[cat.cap(a["capability"]).target], text)]
            if named_alt:
                cap = cat.cap(named_alt[0]["capability"])
                sure = self._name_and_verb_said(d, named_alt[0], text)
                if sure is not None:
                    return sure
                if cap.risk in ("none", "low"):
                    return replace(d, policy="CLARIFY", reason="low_confidence", capability=cap.id, action=cap.action,
                                   target=cap.target, entities=list(cap.entities), risk=cap.risk,
                                   confidence=named_alt[0]["prob"], alternatives=[dict(named_alt[0], by="name_said")])
            # "play some jazz in the kitchen" in a home without Music Assistant: a request for content, not a device
            # this home lacks -> the other assistant (or the player's own integration) may play it
            if d.query_type.get("COMPLEX", 0) >= 0.1 and guess_content(text) \
                    and any(e.domain == "media_player" for e in cat.entities.values()) \
                    and not any(specific.KIND_OF.get(w, "media_player").split(".")[0] != "media_player"
                                for w in specific.tokens(text)):
                return replace(d, policy="ESCALATE", reason="content_request")
        if d.policy == "EXECUTE" and d.reason == "ok" and d.capability:
            other = self._contradicted(d, text)
            if other is not None:
                return other
        if d.policy == "EXECUTE" and d.reason == "ok" and d.capability:
            cap = cat.cap(d.capability)
            e = cat.entities.get(cap.target) if cap.target_kind == "entity" else None
            ctext = specific.canon(text, self._cat_words, _VERB)  # "a cendi la tivu" -> "accendi la tivu"
            if e is not None and specific.bare_kind(ctext, _VERB, self._cat_words) == specific.entity_kind(e):
                in_room = bool(context_area) and e.area == context_area
                sib = specific.siblings(cat, d.capability, ctext, context_area if in_room else None)
                if sib:  # "accendi la tv" with two TVs and no TV in the microphone room: ask
                    alts = [{"capability": d.capability, "prob": d.confidence}] + \
                           [{"capability": s, "prob": None, "by": "generic_reference"} for s in sib]
                    return replace(d, policy="CLARIFY", reason="ambiguous", alternatives=alts[:5])
            elif e is not None and not (context_area and e.area == context_area):
                # any language, no word list: the sentence has nothing that tells the chosen device from others of
                # its kind, and the model itself gives one of them a real chance -> the choice is a prior, ask
                alt = specific.unsupported_choice(cat, d.capability, ctext, d.alternatives or [], d.confidence)
                if alt:
                    alts = [{"capability": d.capability, "prob": d.confidence}] + \
                           [{"capability": s, "prob": p, "by": "no_evidence"} for s, p in alt]
                    return replace(d, policy="CLARIFY", reason="ambiguous", alternatives=alts[:5])
            # "accendi la luce del bagno" with Bagno padronale and Bagno di servizio: the room is not said
            if cap.target_kind in ("entity", "area_group") and not d.parts:
                amb = self._ambiguous_room(d, text, context_area)
                if amb is not None:
                    return amb
        if d.policy == "CLARIFY" and d.reason in ("low_confidence", "ambiguous") and context_area and d.action:
            only = self._only_one_in_room(d, text, context_area)
            if only is not None:
                return only
        if d.policy == "CLARIFY" and d.reason == "low_confidence" and d.capability:
            named = self._full_name_said(d, text)
            if named is not None:
                return named
        if d.policy in ("CLARIFY", "REJECT") and d.reason in ("low_confidence", "ambiguous", "noop"):
            scene = specific.scene_named(cat, text)
            if scene and not _NEG.search(normalize(text)):  # "buongiorno" = the scene "Buongiorno"
                out = pol.finalize(self.policy, cat, text, scene)
                out.query_type = d.query_type
                if out.policy == "EXECUTE":
                    out.reason = "ok_scene"
                    return out
        if d.policy == "CLARIFY" and d.reason == "ambiguous" and d.capability and d.alternatives:
            opts = [a["capability"] for a in d.alternatives if a.get("capability") not in (None, NO_ACTION)]
            pick = specific.distinguished(cat, text, opts)
            if pick is None and specific.bare_kind(text, _VERB, self._cat_words):
                # "accendi il ventilatore": of "Ventilatore a soffitto" and "Aspiratore" only one is called that way
                hits = [o for o in dict.fromkeys(opts) if cat.cap(o).target_kind == "entity"
                        and cat.cap(o).target in cat.entities and specific.named(cat.entities[cat.cap(o).target], text)]
                pick = hits[0] if len(hits) == 1 and len({cat.cap(o).action for o in opts}) == 1 else None
            if pick == d.capability:  # "i faretti dell'isola": only one candidate is called "isola"
                cap = cat.cap(pick)
                base = dict(capability=pick, action=cap.action, target=cap.target, entities=list(cap.entities),
                            confidence=d.confidence, margin=d.margin, risk=cap.risk)
                out = pol.finalize(self.policy, cat, text, pick, base)
                out.query_type = d.query_type
                out.alternatives = d.alternatives
                if out.policy == "EXECUTE":
                    out.reason = "ok_name"
                return out
        return d

    def _name_and_verb_said(self, d: Decision, alt: dict, text: str) -> Optional[Decision]:
        """"schalte Saras Nachttischlampe ein" with NO_ACTION 0.62 and the lamp 0.36: the whole name of the device
        (two words or more) and a verb of exactly that action in the language spoken ("ein") are said, and the model
        considers nothing else on any device -> executed. A single-word name, another verb ("apri la macchina
        espresso") or any other real candidate keeps the question."""
        cat = self.catalog
        cap = cat.cap(alt["capability"])
        e = cat.entities.get(cap.target)
        spec = cat.actions.get(cap.action)
        if e is None or spec is None or cap.risk not in ("none", "low") or (alt.get("prob") or 0) < 0.3 or not self._lang:
            return None
        if len({w for w in specific.tokens(e.name) if len(w) >= 3 and w not in specific._IGNORE}) < 2:
            return None
        if any(a.get("capability") not in (None, NO_ACTION, cap.id) and (a.get("prob") or 0) >= 0.05
               for a in d.alternatives or []):
            return None
        toks = set(specific.tokens(text))
        kws = [specific.tokens(k) for k in (spec.keywords or {}).get(self._lang, [])]
        if not any(k and all(w in toks for w in k) for k in kws):
            return None
        out = pol.finalize(self.policy, cat, text, cap.id, dict(
            capability=cap.id, action=cap.action, target=cap.target, entities=list(cap.entities),
            confidence=alt["prob"], margin=alt["prob"], risk=cap.risk))
        out.query_type, out.alternatives = d.query_type, d.alternatives
        if out.policy != "EXECUTE":
            return None
        out.reason = "ok_name_and_verb"
        return out

    def _full_name_said(self, d: Decision, text: str) -> Optional[Decision]:
        """"accendi la specchiera" at 0.79 (threshold 0.85): the sentence says the whole name of the chosen device,
        no other candidate device has a word of the sentence that sets it apart, and no other action on the same
        device competes -> the device is certain, only the model's confidence was spread. Low risk only."""
        cat = self.catalog
        cap = cat.cap(d.capability)
        if cap.target_kind != "entity" or cap.target not in cat.entities or cap.risk not in ("none", "low"):
            return None
        if (d.confidence or 0) < 0.6 or not specific.name_said(cat.entities[cap.target], text):
            return None
        alts = [a for a in d.alternatives or [] if a.get("capability") not in (None, NO_ACTION, d.capability)]
        if any(cat.cap(a["capability"]).target == cap.target and (a.get("prob") or 0) >= 0.1 for a in alts):
            return None  # same device, another action is plausible ("ritira la tenda": close or stop?)
        # devices the model gives a real chance (a 0.0004 candidate is not a rival)
        rivals = [a["capability"] for a in alts if cat.cap(a["capability"]).target_kind == "entity"
                  and (a.get("prob") or 0) >= 0.03]
        if rivals and specific.distinguished(cat, text, [d.capability] + rivals) not in (None, d.capability):
            return None
        if any(cat.cap(r).target in cat.entities and specific.name_said(cat.entities[cat.cap(r).target], text)
               for r in rivals):
            return None  # two devices named in full
        out = pol.finalize(self.policy, cat, text, d.capability, dict(
            capability=d.capability, action=cap.action, target=cap.target, entities=list(cap.entities),
            confidence=d.confidence, margin=d.margin, risk=cap.risk))
        out.query_type, out.alternatives = d.query_type, d.alternatives
        if out.policy == "EXECUTE":
            out.reason = "ok_full_name"
        return out

    def _only_one_in_room(self, d: Decision, text: str, context_area: str) -> Optional[Decision]:
        """"accendi la luce" said in a bathroom whose only light is the Specchiera, "alza la temperatura" in an attic
        with one climatiser: a generic sentence, and the microphone room has exactly one device that can do the
        action (of the kind named, if a kind is named) -> that device, even when the model spread its probability over
        similar devices of other rooms. Only when the model itself lists that device among its alternatives."""
        cat = self.catalog
        kinds = specific.generic_kinds(text, _VERB, self._cat_words)
        if kinds is None or len(kinds) > 1:
            return None
        room = [c for c in cat.capabilities if c.action == d.action and c.target_kind == "entity"
                and c.target in cat.entities and cat.entities[c.target].area == context_area
                and (not kinds or specific.entity_kind(cat.entities[c.target]) in kinds
                     or cat.entities[c.target].domain in kinds)]
        if len(room) != 1 or room[0].risk not in ("none", "low"):
            return None
        pick = room[0].id
        listed = {a.get("capability") for a in d.alternatives or []} | {d.capability}
        if pick not in listed:
            return None
        base = dict(capability=pick, action=room[0].action, target=room[0].target, entities=list(room[0].entities),
                    confidence=d.confidence, margin=d.margin, risk=room[0].risk)
        out = pol.finalize(self.policy, cat, text, pick, base)
        out.query_type, out.alternatives = d.query_type, d.alternatives
        if out.policy == "EXECUTE":
            out.reason = "ok_room"
        return out

    def _contradicted(self, d: Decision, text: str) -> Optional[Decision]:
        """The sentence names something else than the model's choice.
        "esco di casa" is exactly the name of a scene: the scene is activated (the model picked "next track").
        "accendi i faretti dell'isola": only "Faretti isola" has a word of the sentence that no other light has, and
        the chosen "Faretti salone" has none: ask ("Faretti isola o Faretti salone?") instead of executing."""
        cat = self.catalog
        scene = specific.scene_named(cat, text)
        if scene and scene != d.capability and not _NEG.search(normalize(text)):
            out = pol.finalize(self.policy, cat, text, scene)
            out.query_type = d.query_type
            if out.policy == "EXECUTE":
                out.reason = "ok_scene"
                return out
        cap = cat.cap(d.capability)
        if cap.target_kind != "entity" or cap.target not in cat.entities:
            return None
        dom = cat.entities[cap.target].domain
        rivals = [c.id for c in cat.capabilities if c.action == cap.action and c.target_kind == "entity"
                  and c.target != cap.target and c.target in cat.entities and cat.entities[c.target].domain == dom]
        pick = specific.distinguished(cat, text, [d.capability] + rivals)
        if pick is None or pick == d.capability or cat.cap(pick).risk == "high":
            return None
        alts = [{"capability": pick, "prob": None, "by": "name_said"}, {"capability": d.capability, "prob": d.confidence}]
        return replace(d, policy="CLARIFY", reason="ambiguous", alternatives=alts)

    def _ambiguous_room(self, d: Decision, text: str, context_area: Optional[str]) -> Optional[Decision]:
        cat = self.catalog
        cap = cat.cap(d.capability)
        area = cap.target.split(":")[1] if cap.target_kind == "area_group" else \
            (cat.entities[cap.target].area if cap.target in cat.entities else None)
        rooms = specific.partial_areas(cat, text)
        if not area or area not in rooms or len(rooms) < 2 or context_area in rooms:
            return None
        if self.mentioned_area(text):
            return None  # "camera matrimoniale": the full name of a room is said
        if cap.target_kind == "entity" and specific.name_said(cat.entities[cap.target], text):
            return None  # "tapparella della camera" = the device called "Tapparella camera"
        others = specific.same_in_areas(cat, d.capability, [r for r in rooms if r != area])
        if not others:
            return None
        alts = [{"capability": d.capability, "prob": d.confidence}] + \
               [{"capability": o, "prob": None, "by": "room_name"} for o in others]
        return replace(d, policy="CLARIFY", reason="ambiguous", alternatives=alts[:5])

    def _room_has(self, area: str, cap_id: Optional[str]) -> bool:
        """Does the room contain a device of the same kind (domain + device class) as the candidate?"""
        if not cap_id or cap_id == NO_ACTION:
            return True
        cat = self.catalog
        ents = [cat.entities[e] for e in cat.cap(cap_id).entities if e in cat.entities]
        kinds = {(e.domain, e.device_class) for e in ents}
        return any((e.domain, e.device_class) in kinds and e.area == area for e in cat.entities.values())

    def mentioned_area(self, text: str) -> Optional[str]:
        """Area explicitly named in the text (name or alias), if any."""
        best, best_len = None, 0
        for a in self.catalog.areas.values():
            for name in [a.name] + a.aliases:
                if len(name) > best_len and find_span(text, name, 0.85):
                    best, best_len = a.id, len(name)
        return best

    def _only_later_part(self, whole: Decision, parts: list) -> bool:
        """The whole-sentence decision names a device that only a later part of the sentence mentions."""
        cap = self.catalog.cap(whole.capability) if whole.capability else None
        e = self.catalog.entities.get(cap.target) if cap is not None and cap.target_kind == "entity" else None
        if e is None:
            return False
        return not specific.name_touched(e, parts[0]) and any(specific.name_touched(e, p) for p in parts[1:])

    def _ellipsis_device(self, prev: Decision, prev_text: str, part: str,
                         context_area: Optional[str], prev_tags: Optional[list] = None) -> Optional[Decision]:
        """"accendi la specchiera e l'aspiratore": the fragment names another device; it gets the previous verb.
        Accepted only when the result is the same kind of action (turn_on ... turn_on)."""
        if prev_tags is not None:  # the command words of the previous part, as tagged by the model
            verb = " ".join(w for w, t in prev_tags if t == "CMD")
        else:
            m = _VERB.search(normalize(prev_text))
            verb = m.group(0) if m else ""
        if not verb or not prev.action:
            return None
        d = self.decide_single(f"{verb} {part}", context_area)
        if d.policy == "EXECUTE" and d.action and d.action.split(".")[1] == prev.action.split(".")[1]:
            d.reason, d.text = "ellipsis", part
            return d
        return None

    def _ellipsis(self, prev: Decision, part: str, own: Optional[Decision] = None) -> Optional[Decision]:
        """"accendi la luce della cucina e (quella) del soggiorno": reuse the previous action on a new area.

        Only for parts WITHOUT a verb of their own. "spegni la luce del bagno e accendi quella del salotto" must
        not copy "spegni": when the part has its own verb, the part's own decision is kept.
        """
        if _VERB.search(normalize(part)):
            return None
        cat = self.catalog
        best = None
        for a in cat.areas.values():
            for name in [a.name] + a.aliases:
                if find_span(part, name, 0.85):
                    best = a.id
        if not best:
            return None
        domain = prev.action.split(".")[0]
        same = [c for c in cat.capabilities if c.action == prev.action]
        group = [c for c in same if c.target == f"area:{best}:{domain}"]
        singles = [c for c in same if c.target_kind == "entity" and cat.entities[c.target].area == best]
        pick = group[0] if group else (singles[0] if len(singles) == 1 else None)
        if pick is None or pick.risk == "high":
            return None
        return Decision(policy="EXECUTE", reason="ellipsis", capability=pick.id, action=pick.action, target=pick.target,
                        entities=list(pick.entities), params=dict(prev.params), resolved=dict(prev.resolved),
                        confidence=prev.confidence, margin=prev.margin, risk=pick.risk, text=part)


_NEG = re.compile(r"\b(?:non|don't|dont|do not|no)\b")

# "and" in the supported languages; _CONJ_CMD words are also articles/prepositions elsewhere (it "i", es/fr "en")
_CONJ_ANY = {"e", "ed", "and", "y", "et", "und", "och", "oraz", "samt", "poi", "then", "puis", "dann", "daarna", "depois",
             "potem", "sedan", "luego"}
_CONJ_CMD = {"i": {"pl"}, "en": {"nl"}}   # word -> languages where it means "and"
_THEN = {"poi", "anche", "then", "also", "luego", "después", "despues", "también", "tambien", "puis", "aussi", "dann", "auch", "daarna", "ook",
         "depois", "também", "tambem", "potem", "sedan", "ocksa", "också"}
_NUMLIKE = re.compile(r"\d+([.,]\d+)?|veinte|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|hundred|"
                      r"venti|trenta|quaranta|cinquanta|vingt|trente|quarante|cinquante|soixante|zwanzig|dreissig|vierzig|"
                      r"funfzig|twintig|dertig|veertig|vijftig|tjugo|trettio|fyrtio|femtio|vinte|trinta|quarenta|cinquenta|"
                      r"dwadzieścia|trzydzieści|czterdzieści|pięćdziesiąt|fünfzig|dreißig|ein|eins|zwei|drei|vier|funf|fünf|sechs|sieben|acht|neun|"
                      r"een|twee|drie|vijf|zes|zeven|negen|uno|due|tre|one|two|three|un|une")
_HALFLIKE = {"mezzo", "mezza", "medio", "media", "half", "demi", "demie", "halb", "halv", "meio", "meia", "pol"}

# command verbs (IT/EN/ES, imperative and infinitive stems): a part that contains one is not an ellipsis
_VERB = re.compile(
    r"\b(?:accend|spegn|speng|alz|abbass|apr|chiud|mett|impost|attiv|disattiv|aument|diminu|regol|fai|ferm|avvi|"
    r"blocc|sblocc|accenda|spenga|togli|riprend|"
    r"turn|switch|open|close|shut|set|dim|raise|lower|increase|decrease|start|stop|lock|unlock|put|make|kill|"
    r"encend|enciend|apag|sub|baj|abr|cierr|pon|activ|desactiv|par|arranc)\w*", re.IGNORECASE)
