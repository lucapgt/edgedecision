"""Durations ("5 minuti", "un'ora e mezza", "anderthalb Stunden", "pół godziny", "1h30") and times of day ("alle 7 e
mezza", "at ten past 6", "um halb 8", "om kwart over 7", "o siódmej", "klockan 7 i kväll") in the 9 languages, for
timers and alarms.

Rules, not the model: the model marks which words are the value (tag VAL) and chooses the action; this module turns
the words into seconds or "HH:MM". A wrong alarm time is worse than a question, so anything not understood returns
None (the engine then asks "A che ora?").
"""
from __future__ import annotations

import re
from typing import Optional

from .text import normalize

# ------------------------------------------------------------------ numbers
_EXTRA_NUMBERS = {
    "duas": 2, "dwie": 2, "fyrtio": 40, "femtio": 50, "sextio": 60, "fjorton": 14, "fem": 5, "nittio": 90,
    "fuenfundvierzig": 45, "dreissig": 30, "zwolf": 12, "zwoelf": 12, "doze": 12, "dwanascie": 12,
    "quinze": 15, "vinte": 20, "noventa": 90, "dziewiecdziesiat": 90, "nonante": 90, "septante": 70,
    "quatre vingt dix": 90,
}
# Polish hours are ordinals: "o siódmej" (locative), "na siódmą" (accusative), "wpół do ósmej" (genitive)
_PL_ORD = ["pierwsz", "drugi", "trzeci", "czwart", "piat", "szost", "siodm", "osm", "dziewiat", "dziesiat", "jedenast",
           "dwunast", "trzynast", "czternast", "pietnast", "szesnast", "siedemnast", "osiemnast", "dziewietnast",
           "dwudziest"]
ONE = {"un", "una", "uno", "a", "an", "one", "ein", "eine", "einen", "einer", "een", "um", "uma", "jeden", "jedna",
       "jedno", "en", "ett", "une", "jedne", "jedna"}
_JOIN = {"e", "y", "und", "en", "och", "et", "i"}   # "vinte e cinco", "treinta y cinco", "twee en twintig"


def _word_num(tok: str) -> Optional[int]:
    from .params import NUMBER_WORDS
    if re.fullmatch(r"\d+", tok):
        return int(tok)
    if tok in NUMBER_WORDS:
        return int(NUMBER_WORDS[tok])
    if tok in _EXTRA_NUMBERS:
        return _EXTRA_NUMBERS[tok]
    # compounds written as one word: "fyrtiofem", "fünfundvierzig", "vijfenveertig", "venticinque"
    for tens, tv in (("fyrtio", 40), ("femtio", 50), ("trettio", 30), ("tjugo", 20)):
        if tok.startswith(tens) and len(tok) > len(tens):
            u = _word_num(tok[len(tens):])
            if u is not None and u < 10:
                return tv + u
    return None


def _pl_ordinal(tok: str) -> Optional[int]:
    for i, stem in enumerate(_PL_ORD):
        if tok.startswith(stem) and tok[len(stem):] in ("ej", "a", "y", "iej", "ia", "iego", "ego", "i", "e"):
            return 20 if i == 19 else i + 1
    return None


def read_number(toks: list, i: int) -> tuple:
    """(value, next index) of the number at toks[i] ("25", "venticinque", "vinte e cinco", "czterdzieści pięć",
    "quatre-vingt-dix"), or (None, i)."""
    from .params import NUMBER_PHRASES
    if i >= len(toks):
        return None, i
    t = toks[i]
    if re.fullmatch(r"\d+([.,]\d+)?", t):
        return float(t.replace(",", ".")), i + 1
    for k in (4, 3, 2):
        seq = tuple(toks[i:i + k])
        if len(seq) == k and (seq in NUMBER_PHRASES or " ".join(seq) in _EXTRA_NUMBERS):
            v = NUMBER_PHRASES.get(seq, _EXTRA_NUMBERS.get(" ".join(seq)))
            return float(v), i + k
    v = _word_num(t)
    if v is None:
        if t in ONE:
            return 1.0, i + 1
        return None, i
    j = i + 1
    if v % 10 == 0 and 20 <= v <= 90 and j < len(toks):
        # "vinte e cinco", "treinta y cinco", "czterdzieści pięć", "twenty five"
        k = j + 1 if toks[j] in _JOIN else j
        if k < len(toks):
            u = _word_num(toks[k])
            if u is not None and 1 <= u <= 9:
                return float(v + u), k + 1
    return float(v), j


def _tokens(text: str) -> list:
    t = normalize(text).replace("'", " ").replace("-", " ").replace("’", " ")
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)
    t = re.sub(r"([a-z])(\d)", r"\1 \2", t)
    return t.split()


# ------------------------------------------------------------------ durations
_UNITS = {
    1: """s sec secs sek secondo secondi second seconds segundo segundos seconde secondes sekunde sekunden seconden
          sekunda sekundy sekund sekunder""",
    60: """m min mins mn minuto minuti minute minutes minutos minuten minuut minuutje minuutjes minuta minuty minut
           minuter minutu minutinho minutinhos minute minutke minute""",
    3600: """h ora ore hour hours hr hrs hora horas heure heures stunde stunden std uur uren godzina godziny godzin
             godzine godzinke timme timmar tim horinha""",
}
UNIT = {w: v for v, ws in _UNITS.items() for w in ws.split()}

_PHRASES = {
    30: ["mezzo minuto", "half a minute", "medio minuto", "une demi minute", "eine halbe minute", "een halve minuut",
         "meio minuto", "pol minuty", "en halv minut"],
    60: ["un minutinho", "um minutinho", "une petite minute", "minute", "godzine"],
    90: ["un minuto e mezzo", "a minute and a half", "minute and a half", "un minuto y medio", "une minute et demie",
         "anderthalb minuten", "eineinhalb minuten", "anderhalve minuut", "um minuto e meio", "poltorej minuty",
         "en och en halv minut", "en och en halv minuter"],
    900: ["un quarto d ora", "quarto d ora", "a quarter of an hour", "quarter of an hour", "quarter hour",
          "un cuarto de hora", "cuarto de hora", "un quart d heure", "quart d heure", "eine viertelstunde",
          "einer viertelstunde", "viertelstunde", "een kwartier", "kwartier", "kwartiertje", "een kwartiertje",
          "um quarto de hora", "quarto de hora", "kwadrans", "en kvart", "en kvarts timme", "kvart"],
    1800: ["mezz ora", "mezzora", "mezza ora", "half an hour", "half hour", "a half hour", "media hora", "une demi heure",
           "demi heure", "eine halbe stunde", "einer halben stunde", "halbe stunde", "een half uur", "half uur",
           "halfuur", "halfuurtje", "een halfuurtje", "meia hora", "meia horinha", "pol godziny", "polgodziny",
           "en halvtimme", "halvtimme", "en halv timme", "halv timme"],
    2700: ["tre quarti d ora", "three quarters of an hour", "tres cuartos de hora", "trois quarts d heure",
           "dreiviertelstunde", "dreiviertel stunde", "drei viertelstunden", "drie kwartier", "tres quartos de hora",
           "trzy kwadranse", "tre kvart", "tre kvarts timme"],
    5400: ["un ora e mezza", "un ora e mezzo", "an hour and a half", "one and a half hours", "hour and a half",
           "una hora y media", "hora y media", "une heure et demie", "une heure et demi", "anderthalb stunden",
           "eineinhalb stunden", "anderhalf uur", "uma hora e meia", "hora e meia", "poltorej godziny", "poltora godziny",
           "en och en halv timme", "en och en halv timmes", "en timme och en halv", "halvannan timme",
           "godzine i pol"],
    9000: ["zweieinhalb stunden", "tweeenhalf uur", "twee en een half uur", "duas horas e meia", "dwie i pol godziny",
           "two and a half hours", "due ore e mezza", "dos horas y media", "deux heures et demie", "tva och en halv timme"],
    4500: ["godzine i kwadrans"],
}
PHRASES = sorted(((tuple(p.split()), v) for v, ps in _PHRASES.items() for p in ps), key=lambda x: -len(x[0]))
HALF_AFTER = [("e", "mezza"), ("e", "mezzo"), ("and", "a", "half"), ("y", "media"), ("y", "medio"), ("et", "demie"),
              ("et", "demi"), ("und", "eine", "halbe"), ("en", "een", "half"), ("e", "meia"), ("e", "meio"),
              ("i", "pol"), ("och", "en", "halv")]
QUARTER_AFTER = [("e", "un", "quarto"), ("e", "um", "quarto"), ("and", "a", "quarter"), ("y", "cuarto"),
                 ("y", "un", "cuarto"), ("et", "quart"), ("et", "un", "quart"), ("und", "eine", "viertel"),
                 ("en", "een", "kwart"), ("i", "kwadrans"), ("och", "en", "kvart")]


def _seq_at(toks, i, seqs) -> int:
    for seq in seqs:
        if tuple(toks[i:i + len(seq)]) == seq:
            return len(seq)
    return 0


def parse_duration(text: str) -> Optional[float]:
    """Seconds, or None when no duration is said."""
    toks = _tokens(text)
    total, found, i, n = 0.0, False, 0, len(toks)
    while i < n:
        hit = next(((k, v) for k, v in PHRASES if tuple(toks[i:i + len(k)]) == k
                    and not (len(k) == 1 and k[0] in ("minute", "godzine") and i > 0 and read_number(toks, i - 1)[0]
                             is not None)), None)
        if hit:
            total += hit[1]
            found = True
            i += len(hit[0])
            continue
        v, j = read_number(toks, i)
        if v is not None:
            # "twee en een half uur": the half before the unit
            half = _seq_at(toks, j, [("en", "een", "half"), ("e", "mezzo"), ("y", "medio")])
            jj = j + half
            if jj < n and toks[jj] in UNIT and not (toks[i] in ONE and toks[jj] in ("m", "s", "h")):
                u = UNIT[toks[jj]]
                total += (v + (0.5 if half else 0)) * u
                found = True
                i = jj + 1
                k = _seq_at(toks, i, HALF_AFTER)
                if k:
                    total += 0.5 * u
                    i += k
                    continue
                k = _seq_at(toks, i, QUARTER_AFTER)
                if k and u == 3600:
                    total += 900
                    i += k
                    continue
                # "1h30", "une heure vingt", "1 min 30": a bare number after hours / minutes is the next unit down
                w, k2 = read_number(toks, i)
                if w is not None and toks[i] not in ONE and u in (3600, 60) and 0 < w < 60 and \
                        (k2 >= n or toks[k2] not in UNIT):
                    total += w * (60 if u == 3600 else 1)
                    i = k2
                continue
        i += 1
    return total if found and total > 0 else None


# ------------------------------------------------------------------ time of day
_PM = [("di", "sera"), ("della", "sera"), ("di", "pomeriggio"), ("del", "pomeriggio"), ("stasera",), ("pm",), ("p", "m"),
       ("in", "the", "evening"), ("in", "the", "afternoon"), ("tonight",), ("this", "evening"), ("de", "la", "tarde"),
       ("de", "la", "noche"), ("esta", "noche"), ("esta", "tarde"), ("du", "soir"), ("ce", "soir"),
       ("de", "l", "apres", "midi"), ("abends",), ("nachmittags",), ("am", "abend"), ("heute", "abend"),
       ("s", "avonds"), ("vanavond",), ("s", "middags"), ("da", "tarde"), ("da", "noite"), ("hoje", "a", "noite"),
       ("esta", "noite"), ("wieczorem",), ("po", "poludniu"), ("pa", "kvallen"), ("pa", "eftermiddagen"),
       ("i", "kvall"), ("ikvall",)]
_AM = [("di", "mattina"), ("del", "mattino"), ("della", "mattina"), ("am",), ("a", "m"), ("in", "the", "morning"),
       ("de", "la", "manana"), ("du", "matin"), ("morgens",), ("fruh",), ("s", "ochtends"), ("da", "manha"), ("rano",),
       ("pa", "morgonen")]
_MARK = {"alle", "all", "le", "ore", "at", "las", "la", "a", "um", "om", "as", "o", "klockan", "kl", "vid", "for",
         "per", "para", "pour", "fur", "voor", "till", "na", "on", "uhr", "h", "heures", "heure", "uur", "godzinie",
         "godz", "punkt", "around", "verso", "gegen", "rond", "omkring", "ao", "al"}
_AFTER_HOUR = {"uhr", "uur", "h", "heures", "heure", "am", "pm", "oclock", "horas", "hora", "rano", "wieczorem"}
_NOON = {"mezzogiorno": 12, "midday": 12, "noon": 12, "mediodia": 12, "midi": 12, "mittag": 12, "poludnie": 12,
         "mezzanotte": 0, "midnight": 0, "medianoche": 0, "minuit": 0, "mitternacht": 0, "middernacht": 0,
         "polnoc": 0, "midnatt": 0}
_PAST_W = {"past", "after", "nach", "over", "po"}
_TO_W = {"to", "before", "vor", "voor", "i", "para"}
_HALF_BEFORE = {"halb", "half", "halv"}          # "halb 8" = 7:30
_QUARTER = {"quarter", "viertel", "kwart", "kvart", "kwadrans", "quarto", "cuarto", "quart"}
_HALF_W = {"half", "halb", "halv", "mezza", "mezzo", "media", "medio", "demie", "demi", "meia", "meio", "pol"}
_PLUS = {"e", "y", "et", "und", "en", "och", "i"}
_MINUS = {"meno", "menos", "moins"}
_ARTS = {"un", "um", "une", "ein", "een", "en", "a", "le"}


def _hour_tok(toks, i):
    """(hour, next index) for an hour at toks[i]: digits, number words, Polish ordinals, noon / midnight."""
    if i >= len(toks):
        return None, i
    t = toks[i]
    if t in _NOON:
        return _NOON[t], i + 1
    if t == "meio" and i + 1 < len(toks) and toks[i + 1] == "dia":
        return 12, i + 2
    if t == "meia" and i + 1 < len(toks) and toks[i + 1] == "noite":
        return 0, i + 2
    v = _pl_ordinal(t)
    if v is not None:
        j = i + 1
        if v == 20 and j < len(toks):
            u = _pl_ordinal(toks[j])
            if u is not None and u < 4:
                return 20 + u, j + 1
        return v, j
    if t in ONE and t not in ("one", "uno", "una", "uma", "een", "eins", "jedna", "ett"):
        return None, i
    v, j = read_number(toks, i)
    if v is None or not float(v).is_integer() or not 0 <= v <= 24:
        return None, i
    return int(v), j


def _minutes_word(toks, i):
    """(minutes, next index): "10", "dieci", "quarto", "mezza", "un quarto", "trenta", "kwadrans"..."""
    if i < 0 or i >= len(toks):
        return None, i
    k = 1 if toks[i] in _ARTS and i + 1 < len(toks) and toks[i + 1] in _QUARTER | _HALF_W else 0
    t = toks[i + k]
    if t in _QUARTER:
        return 15, i + k + 1
    if t in _HALF_W:
        return 30, i + k + 1
    v, j = read_number(toks, i)
    if v is not None and float(v).is_integer() and 0 < v < 60:
        if j < len(toks) and toks[j] in UNIT and UNIT[toks[j]] == 60:
            j += 1  # "zehn Minuten nach 7"
        return int(v), j
    return None, i


_ZERO = {"zero", "oh", "cero", "null", "nul", "nula", "noll", "zero"}


def _clock(h: int, m: int) -> tuple:
    tot = h * 60 + m
    return (tot // 60) % 24, tot % 60


def parse_time(text: str) -> Optional[str]:
    """"HH:MM" of a time of day, or None."""
    raw = (text or "").lower()
    toks = _tokens(text)
    hour = minute = None
    m = re.search(r"\b(\d{1,2})\s*[:.h]\s*(\d{2})\b", raw)
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        hour, minute = int(m.group(1)), int(m.group(2))
    n = len(toks)
    i = 0
    while hour is None and i < n:
        t = toks[i]
        prev = toks[i - 1] if i else ""
        # "halb 8" / "half 8" / "halv 8" (= 7:30), "wpół do ósmej", "dreiviertel 8", "viertel 8"
        if (t in _HALF_BEFORE and prev not in ("and", "past")) or (t == "wpol" and i + 1 < n and toks[i + 1] == "do") \
                or t == "dreiviertel" or (t == "viertel" and i + 1 < n and toks[i + 1] not in ("nach", "vor")):
            j = i + (2 if t == "wpol" else 1)
            h, _ = _hour_tok(toks, j)
            if h is not None:
                dm = 0
                if i >= 2 and toks[i - 1] in ("voor", "over"):   # "vijf voor half acht"
                    w, wj = _minutes_word(toks, i - 2)
                    if w and wj == i - 1:
                        dm = -w if toks[i - 1] == "voor" else w
                base = 45 if t == "dreiviertel" else (15 if t == "viertel" else 30)
                hour, minute = _clock(h - 1, base + dm)
                break
        # "<minutes> past|nach|over|po <hour>", "<minutes> to|vor|voor|i|para <hour>"
        if t in _PAST_W | _TO_W and i > 0 and not (t == "para" and i < 2):
            for start in (i - 2, i - 1):
                w, wj = _minutes_word(toks, start)
                if w is not None and wj == i:
                    j = i + 1
                    if t == "para" and j < n and toks[j] in ("as", "las", "la", "a"):
                        j += 1
                    h, _ = _hour_tok(toks, j)
                    if h is not None and (t not in ("i", "para") or w in (5, 10, 15, 20, 25)):
                        hour, minute = _clock(h, w if t in _PAST_W else -w)
                    break
            if hour is not None:
                break
        # Polish "za kwadrans ósma" / "za dziesięć ósma"
        if t == "za" and i + 2 < n:
            w, wj = _minutes_word(toks, i + 1)
            h, _ = _hour_tok(toks, wj)
            if w is not None and h is not None:
                hour, minute = _clock(h, -w)
                break
        i += 1
    i = 0
    while hour is None and i < n:
        t = toks[i]
        prev = toks[i - 1] if i else ""
        # an hour after a marker ("alle 7", "um 7", "o siódmej"), or followed by Uhr / heures / am / pm
        h, j = _hour_tok(toks, i)
        if h is not None:
            nxt = toks[j] if j < n else ""
            if prev in _MARK or nxt in _AFTER_HOUR or t in _NOON or t in ("meio", "meia") or _pl_ordinal(t) is not None:
                hour, minute = h, 0
                k = j
                if k < n and toks[k] in ("uhr", "uur", "h", "heures", "heure", "horas", "hora", "godzina", "oclock"):
                    k += 1
                if k + 1 < n and toks[k] in _ZERO:  # "tredici zero cinque", "seven oh five" -> 13:05, 7:05
                    w, k2 = _minutes_word(toks, k + 1)
                    if w is not None and w < 10 and not (k2 < n and toks[k2] in UNIT):
                        minute = w
                    break
                if k < n and toks[k] in _PLUS:
                    w, k2 = _minutes_word(toks, k + 1)
                    if w is not None and not (k2 < n and toks[k2] in UNIT):
                        minute = w
                elif k < n and toks[k] in _MINUS:
                    k1 = k + 1 + (1 if k + 1 < n and toks[k + 1] in ("le", "un", "um") and k + 2 < n
                                  and toks[k + 2] in _QUARTER else 0)
                    w, _ = _minutes_word(toks, k1)
                    if w is not None:
                        hour, minute = _clock(hour, -w)
                elif k < n:
                    w, k2 = _minutes_word(toks, k)
                    if w is not None and toks[k] not in _QUARTER | _HALF_W | _ARTS and not (k2 < n and toks[k2] in UNIT) \
                            and (re.fullmatch(r"\d+", toks[k]) or k > j or _pl_ordinal(t) is not None):
                        minute = w
                break
        i += 1
    if hour is None:
        return None
    joined = " " + " ".join(toks) + " "
    if any(" " + " ".join(p) + " " in joined for p in _PM) and hour < 12:
        hour += 12
    elif any(" " + " ".join(p) + " " in joined for p in _AM) and hour == 12:
        hour = 0
    hour %= 24
    return f"{hour:02d}:{(minute or 0) % 60:02d}"
