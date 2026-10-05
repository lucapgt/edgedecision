"""Deterministic, multilingual (IT/EN/ES) parameter extraction.

The semantic model decides *what* to do; numbers, colours, modes and deltas
are extracted here with rules, then validated against the argument spec and
resolved against the current state.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .text import fuzzy_ratio, normalize
from .types import ActionSpec, ArgSpec, Entity

# ---------------------------------------------------------------- number words


def _build_numbers() -> dict[str, int]:
    nums: dict[str, int] = {}
    # Italian
    it_units = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci", "undici",
                "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto", "diciannove"]
    for i, w in enumerate(it_units):
        nums[w] = i
    it_tens = {20: "venti", 30: "trenta", 40: "quaranta", 50: "cinquanta", 60: "sessanta", 70: "settanta",
               80: "ottanta", 90: "novanta"}
    for t, w in it_tens.items():
        nums[w] = t
        for u in range(1, 10):
            nums[(w[:-1] + it_units[u]) if u in (1, 8) else (w + it_units[u])] = t + u
    nums["cento"] = 100
    # English
    en_units = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
                "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    for i, w in enumerate(en_units):
        nums[w] = i
    en_tens = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty",
               90: "ninety"}
    for t, w in en_tens.items():
        nums[w] = t
        for u in range(1, 10):
            nums[f"{w}{en_units[u]}"] = t + u  # "twentyone" after hyphen removal handled below
    nums["hundred"] = 100
    # Spanish
    es = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
          "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno",
          "veintidos", "veintitres", "veinticuatro", "veinticinco", "veintiseis", "veintisiete", "veintiocho",
          "veintinueve"]
    for i, w in enumerate(es):
        nums[w] = i
    nums["un"] = 1
    nums["una"] = 1
    nums["veintiun"] = 21
    es_tens = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta",
               90: "noventa"}
    for t, w in es_tens.items():
        nums[w] = t
    nums["cien"] = 100
    nums["ciento"] = 100
    return nums


NUMBER_WORDS = _build_numbers()
TENS_WORDS = {w for w, v in NUMBER_WORDS.items() if v in (20, 30, 40, 50, 60, 70, 80, 90)}
UNIT_ONLY = {w for w, v in NUMBER_WORDS.items() if 1 <= v <= 9}
# words that are numbers only if immediately followed by a unit
AMBIGUOUS = {"un", "una", "uno", "one", "a", "sei", "once", "otto", "tre", "due"}
STRONG_AMBIGUOUS = {"un", "una", "uno", "one", "a", "sei", "once"}

PERCENT_UNITS = [("per", "cento"), ("per", "cent"), ("por", "ciento"), ("%",), ("percento",), ("percent",),
                 ("porciento",), ("percentuale",), ("pc",)]
DEGREE_UNITS = [("°", "c"), ("°",), ("gradi",), ("grado",), ("degrees",), ("degree",), ("grados",), ("celsius",),
                ("centigradi",)]
FAHR_UNITS = [("°", "f"), ("fahrenheit",), ("f",)]
KELVIN_UNITS = [("kelvin",), ("k",)]
HALF_SUFFIX = [("e", "mezzo"), ("e", "mezza"), ("and", "a", "half"), ("y", "medio"), ("y", "media"),
               ("virgola", "cinque"), ("point", "five"), ("coma", "cinco"), ("punto", "cinco")]

HALF_WORDS = {"meta", "half", "halfway", "mitad"}
MAX_WORDS = {"massimo", "max", "maximum", "full", "maximo", "tope", "palla", "fondo"}
MIN_WORDS = {"minimo", "min", "minimum", "lowest"}

SMALL_STEP = {"po", "poco", "pochino", "pochettino", "leggermente", "appena", "bit", "little", "slightly", "tad",
              "touch", "poquito", "pelin", "ligeramente", "poquitin"}
LARGE_STEP = {"molto", "tanto", "parecchio", "decisamente", "lot", "lots", "much", "mucho", "bastante", "way"}
ABS_MARKERS = {"a", "al", "alla", "allo", "ai", "to", "at", "hasta", "sui", "sul", "sulla", "fino"}
REL_MARKERS = {"di", "del", "dello", "della", "by", "en", "de", "un", "extra", "altri", "altro", "more", "mas"}
NUMBER_PHRASES: dict = {}   # multi-word numbers of the extra languages ("quarante cinq"), see core/lang

from .lang import apply_params as _apply_lang  # noqa: E402

_apply_lang(globals(), normalize)


def tokenize(text: str) -> list[str]:
    t = normalize(text)
    t = t.replace("'", " ").replace("%", " % ").replace("°", " ° ").replace("-", " ")
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)
    t = re.sub(r"([a-z])(\d)", r"\1 \2", t)
    return t.split()


def _match_seq(toks, i, seqs) -> int:
    """Length of the first unit sequence matching at toks[i:], 0 if none."""
    for seq in seqs:
        if tuple(toks[i:i + len(seq)]) == seq:
            return len(seq)
    return 0


@dataclass
class NumberMention:
    value: float
    start: int
    end: int           # exclusive, including unit tokens
    unit: Optional[str]  # percent | degree | fahrenheit | kelvin | None
    prev: str          # token before the number (preposition)


def find_numbers(toks: list[str], excluded: set[int] = frozenset()) -> list[NumberMention]:
    out: list[NumberMention] = []
    i = 0
    n = len(toks)
    while i < n:
        if i in excluded:
            i += 1
            continue
        t = toks[i]
        val = None
        j = i + 1
        phrase = next(((k, NUMBER_PHRASES[tuple(toks[i:i + k])]) for k in (4, 3, 2)
                       if tuple(toks[i:i + k]) in NUMBER_PHRASES), None) if NUMBER_PHRASES else None
        if phrase:
            val, j = float(phrase[1]), i + phrase[0]
        elif re.fullmatch(r"\d+([.,]\d+)?", t):
            val = float(t.replace(",", "."))
        elif t in NUMBER_WORDS:
            val = float(NUMBER_WORDS[t])
            # english / spanish compounds: "twenty one", "treinta y cinco", "one hundred"
            if t in TENS_WORDS and j < n:
                if toks[j] in UNIT_ONLY and toks[j] not in ("un", "una"):
                    val += NUMBER_WORDS[toks[j]]
                    j += 1
                elif toks[j] == "y" and j + 1 < n and toks[j + 1] in NUMBER_WORDS and NUMBER_WORDS[toks[j + 1]] < 10:
                    val += NUMBER_WORDS[toks[j + 1]]
                    j += 2
            elif t in ("one", "a") and j < n and toks[j] == "hundred":
                val, j = 100.0, j + 1
        if val is None:
            i += 1
            continue
        # half / decimal suffix
        k_half = _match_seq(toks, j, HALF_SUFFIX)
        if k_half:
            val += 0.5
            j += k_half
        unit = None
        for name, seqs in (("percent", PERCENT_UNITS), ("fahrenheit", FAHR_UNITS), ("degree", DEGREE_UNITS),
                           ("kelvin", KELVIN_UNITS)):
            k = _match_seq(toks, j, seqs)
            if k:
                unit = name
                j += k
                break
        if unit and not k_half:  # "21 degrés et demi", "21 Grad und halb"
            k2 = _match_seq(toks, j, HALF_SUFFIX)
            if k2:
                val += 0.5
                j += k2
        if unit is None and t in STRONG_AMBIGUOUS:
            i += 1
            continue
        if unit is None and t in AMBIGUOUS and not re.fullmatch(r"\d.*", t):
            prev = toks[i - 1] if i else ""
            if prev not in ABS_MARKERS | REL_MARKERS:
                i += 1
                continue
        out.append(NumberMention(val, i, j, unit, toks[i - 1] if i else ""))
        i = j
    return out


def excluded_positions(toks: list[str], names: list[str], threshold: float = 0.84, numeric_only: bool = True) -> set[int]:
    """Token positions belonging to entity/area names (their digits/colours are not parameters)."""
    ex: set[int] = set()
    for name in names:
        nt = tokenize(name)
        if not nt or (numeric_only and not any(re.fullmatch(r"\d+", x) or x in NUMBER_WORDS for x in nt)):
            continue
        k = len(nt)
        target = " ".join(nt)
        for i in range(0, len(toks) - k + 1):
            if fuzzy_ratio(" ".join(toks[i:i + k]), target) >= threshold:
                ex.update(range(i, i + k))
    return ex


def _enum_match(text_toks: list[str], choices: dict, excluded: set[int]) -> Optional[str]:
    best = None  # (len, pos, value)
    for value, per_lang in choices.items():
        syns = {value.replace("_", " ")}
        for lst in per_lang.values():
            syns.update(lst)
        for syn in syns:
            st = tokenize(syn)
            k = len(st)
            for i in range(0, len(text_toks) - k + 1):
                if any(p in excluded for p in range(i, i + k)):
                    continue
                window = text_toks[i:i + k]
                ok = window == st or (k == 1 and len(st[0]) >= 5 and fuzzy_ratio(window[0], st[0]) >= 0.88)
                if ok and (best is None or k > best[0] or (k == best[0] and i > best[1])):
                    best = (k, i, value)
    return best[2] if best else None


def _round(v: float, unit: Optional[str]) -> float:
    return float(round(v * 2) / 2) if unit == "°C" else float(round(v))


@dataclass
class ArgResult:
    value: object = None
    found: bool = False
    source: str = ""          # explicit | word | qualitative | default
    absolute: bool = False    # step args: an absolute target was given instead of a delta


def extract_arg(text: str, arg: ArgSpec, exclude_names: list[str] = ()) -> ArgResult:
    toks = tokenize(text)
    kind = arg.kind
    if kind == "text":  # free text: the words the tagging head marked as the value, cleaned
        if arg.name == "content":  # what to play
            from .media import clean_content
            v = clean_content(text)
        elif arg.name == "item":   # "il latte" -> "latte" (shopping list)
            v = clean_item(text)
        else:                      # a message to announce: as said
            v = (text or "").strip(" ,.;:!?\"'«»") or None
        return ArgResult(v, v is not None, "word")
    if kind == "duration":
        from .when import parse_duration
        v = parse_duration(text)
        return ArgResult(v, v is not None, "explicit")
    if kind == "time":
        from .when import parse_time
        v = parse_time(text)
        return ArgResult(v, v is not None, "explicit")
    if kind == "source":  # the device's own source list decides (validate_and_resolve)
        v = clean_item(text)
        return ArgResult(v, v is not None, "word")
    if kind == "enum":
        ex = excluded_positions(toks, [n for n in exclude_names if len(tokenize(n)) > 1], numeric_only=False)
        v = _enum_match(toks, arg.choices or {}, ex)
        return ArgResult(v, v is not None, "word")

    ex = excluded_positions(toks, list(exclude_names))
    nums = find_numbers(toks, ex)
    tokset = set(toks)
    if kind == "percent":
        for m in nums:
            if m.unit == "percent":
                return ArgResult(_round(m.value, "%"), True, "explicit")
        if tokset & HALF_WORDS:
            return ArgResult(50.0, True, "word")
        if tokset & MAX_WORDS:
            return ArgResult(float(arg.max if arg.max is not None else 100), True, "word")
        if tokset & MIN_WORDS:
            return ArgResult(float(max(arg.min or 0, 1)), True, "word")
        for m in nums:
            if m.unit is None and (arg.min or 0) <= m.value <= (arg.max if arg.max is not None else 100):
                return ArgResult(_round(m.value, "%"), True, "explicit")
        return ArgResult()

    if kind == "temperature":
        lo, hi = (arg.min if arg.min is not None else 5), (arg.max if arg.max is not None else 35)
        cands = [m for m in nums if m.unit in ("degree", "fahrenheit")] or [m for m in nums if m.unit is None]
        for m in cands:
            v = m.value
            if m.unit == "fahrenheit" or (m.unit is None and 40 <= v <= 95 and hi <= 40):
                v = (v - 32) * 5 / 9
            if lo - 15 <= v <= hi + 15:  # keep out-of-range values so the validator can complain
                return ArgResult(_round(v, "°C"), True, "explicit")
        return ArgResult()

    if kind == "step":
        for m in nums:
            if m.unit in ("kelvin",):
                continue
            absolute = m.prev in ABS_MARKERS and m.prev not in REL_MARKERS
            if arg.unit == "°C" and m.unit == "percent":
                continue
            if arg.unit == "%" and m.unit in ("degree", "fahrenheit"):
                continue
            v = m.value
            if absolute:
                return ArgResult(_round(v, arg.unit), True, "explicit", absolute=True)
            return ArgResult(_round(v, arg.unit), True, "explicit")
        base = float(arg.default if arg.default is not None else (1 if arg.unit == "°C" else 10))
        if tokset & LARGE_STEP:
            return ArgResult(base * 2 if arg.unit == "°C" else min(base * 2.5, 50), True, "qualitative")
        if tokset & SMALL_STEP:
            return ArgResult(base, True, "qualitative")
        return ArgResult(base, False, "default")

    if kind == "number":
        for m in nums:
            return ArgResult(m.value, True, "explicit")
        return ArgResult()

    return ArgResult()


_ITEM_LEAD = set(normalize("""il lo la l i gli le un una uno dei degli delle del della dello di po the a an some
of el los las unos unas de del le les des du un une der die das den ein eine einen etwas het een wat o a os as um uma
uns umas do da dos das en ett lite pa na w z ze su sulla sul on""").split())


def clean_item(value: Optional[str]) -> Optional[str]:
    """Leading articles and quantity words out: "il latte" -> "latte", "some milk" -> "milk"."""
    if not value:
        return None
    words = value.replace("’", "'").split()
    while words and (normalize(words[0]).rstrip("'") in _ITEM_LEAD or normalize(words[0]).endswith("'")
                     and normalize(words[0]).rstrip("'") in {"l", "d", "un", "dell", "all", "sull", "nell"}):
        words = words[1:]
    out = " ".join(words).strip(" ,.;:!?\"'«»")
    return out or None


def match_source(value: str, sources: list) -> Optional[str]:
    """"hdmi 1" -> "HDMI 1", "netflix" -> "Netflix" among the device's sources."""
    from .sources import SOURCE_ALIASES
    from .text import fuzzy_ratio
    n = normalize(value)
    for canon, names in SOURCE_ALIASES.items():   # "la tdt" -> "TV", "the cable box" -> "Cable"
        if n in names or n.replace(" ", "") in [x.replace(" ", "") for x in names]:
            hit = [src for src in sources or [] if normalize(str(src)).replace(" ", "") == normalize(canon).replace(" ", "")]
            if hit:
                return hit[0]
    v = n.replace(" ", "")
    best, score = None, 0.0
    for src in sources or []:
        sv = normalize(str(src)).replace(" ", "")
        r = 1.0 if v == sv else (0.95 if v and (v in sv or sv in v) and min(len(v), len(sv)) >= 3 else fuzzy_ratio(v, sv))
        if r > score:
            best, score = src, r
    return best if score >= 0.8 else None


def extract_params(text: str, spec: Optional[ActionSpec], exclude_names: list[str] = ()):
    """Returns (params, missing, meta) for an action spec."""
    params, missing, meta = {}, [], {}
    if spec is None:
        return params, missing, meta
    for arg in spec.args:
        r = extract_arg(text, arg, exclude_names)
        if r.found or (arg.kind == "step" and r.value is not None):
            params[arg.name] = r.value
            meta[arg.name] = {"source": r.source, "absolute": r.absolute}
        elif arg.required:
            missing.append(arg.name)
        elif arg.default is not None:
            params[arg.name] = arg.default
            meta[arg.name] = {"source": "default", "absolute": False}
    return params, missing, meta


def validate_and_resolve(spec: ActionSpec, params: dict, meta: dict, entities: list[Entity]):
    """Range/type checks and resolution of relative steps against state.

    Returns (resolved, invalid) where invalid is a list of (arg, reason).
    """
    resolved: dict = {}
    invalid: list = []
    for arg in spec.args:
        if arg.name not in params:
            continue
        v = params[arg.name]
        lo, hi = arg.min, arg.max
        if arg.kind == "temperature" and entities:
            lo = entities[0].attributes.get("min_temp", lo)
            hi = entities[0].attributes.get("max_temp", hi)
        if arg.kind in ("percent", "temperature", "number"):
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                invalid.append((arg.name, f"out_of_range[{lo},{hi}]"))
            resolved[arg.name] = v
        elif arg.kind == "duration":
            if not (1 <= float(v) <= 24 * 3600):
                invalid.append((arg.name, "out_of_range[1s,24h]"))
            resolved[arg.name] = v
        elif arg.kind == "source":
            src = match_source(str(v), (entities[0].attributes or {}).get("sources") if entities else [])
            if src is None:
                invalid.append((arg.name, "unknown_source"))
            resolved[arg.name] = src or v
        elif arg.kind == "enum" and arg.name == "preset":
            presets = (entities[0].attributes or {}).get("presets") if entities else None
            pick = preset_for(v, presets) if presets else v
            if presets and pick is None:
                invalid.append((arg.name, "unsupported_value"))
            resolved[arg.name] = pick or v
        elif arg.kind == "enum":
            allowed = list(arg.choices or {})
            if arg.name == "hvac_mode" and entities and entities[0].attributes.get("hvac_modes"):
                allowed = [m for m in allowed if m in entities[0].attributes["hvac_modes"]]
            if v not in allowed:
                invalid.append((arg.name, "unsupported_value"))
            resolved[arg.name] = v
        elif arg.kind == "step":
            attr = arg.applies_to or arg.name
            if meta.get(arg.name, {}).get("absolute"):
                resolved[attr] = v
                resolved[arg.name] = v
                continue
            if lo is not None and hi is not None and not (0 <= v <= (hi - (lo or 0))):
                invalid.append((arg.name, "step_out_of_range"))
            resolved[arg.name] = v
            cur = None
            for e in entities:
                if attr in e.state:
                    cur = e.state[attr]
                    break
            if cur is not None:
                try:
                    new = float(cur) + arg.sign * float(v)
                    blo, bhi = (5, 35) if arg.unit == "°C" else (0, 100)
                    if entities and arg.unit == "°C":
                        blo = entities[0].attributes.get("min_temp", blo)
                        bhi = entities[0].attributes.get("max_temp", bhi)
                    resolved[attr] = max(blo, min(bhi, new))
                except (TypeError, ValueError):
                    pass
    return resolved, invalid


_PRESET_ALIASES = {"frost": ("frost", "antigelo", "anti_freeze", "antifreeze", "frost_protection", "hors_gel", "frostschutz",
                             "vorstbeveiliging", "away"),
                   "away": ("away", "vacation", "holiday", "absent"), "home": ("home", "comfort", "present"),
                   "sleep": ("sleep", "night", "notte"), "eco": ("eco", "economy", "energy_saving"),
                   "comfort": ("comfort", "home"), "boost": ("boost", "turbo")}


def preset_for(value: str, presets: list) -> Optional[str]:
    """The device's own preset name for a canonical preset ("frost" -> "frost_protection" or "Antigelo")."""
    low = {normalize(str(p)).replace(" ", "_"): p for p in presets}
    for alias in _PRESET_ALIASES.get(value, (value,)):
        for k, p in low.items():
            if k == alias or alias in k:
                return p
    return None
