"""Deterministic guards that complement the model.

complex_marker(): conditional / scheduled / "everything" requests (IT/EN/ES; conditions also FR/DE/NL/PT/PL/SV). Such requests cannot be served
by a single capability executed now, so when a marker is found and the model would act (EXECUTE) or ask
(CLARIFY), the request is escalated. The patterns are deliberately conservative (high precision): polite
forms ("se puoi", "if you can", "si puedes") and state checks ("controlla se...", "check if...",
"mira si...") are not markers.
"""
from __future__ import annotations

import re

from .text import normalize

# words that turn a following se/if/si into an indirect question ("check if the door is closed")
_CHECK = {"controlla", "controllami", "verifica", "vedi", "guarda", "sai", "dimmi", "chiedi", "sapere", "capire",
          "check", "see", "tell", "know", "verify", "wonder", "ask", "find", "out", "whether",
          "mira", "comprueba", "dime", "sabes", "saber", "pregunta", "averigua", "revisa", "fijate",
          "verifie", "regarde", "dis", "sais", "prufe", "pruf", "sag", "weisst", "kijk", "controleer", "zeg", "weet",
          "verifica", "diz", "sabes", "sprawdz", "powiedz", "wiesz", "kolla", "sag", "vet", "se"}

_NUM = r"(?:\d+|un|una|uno|a|an|one|two|three|five|ten|fifteen|twenty|thirty|half an|due|tre|cinque|dieci|quindici" \
       r"|venti|trenta|quaranta|mezz' ora|mezzora|mezz'|dos|tres|cinco|diez|quince|veinte|treinta|media)"

_COND = [
    # Italian
    r"\bse (?:fa|e|c' e|ci sono|non c' e|piove|nevica|qualcuno|nessuno|esco|usciamo|entro|torno|rientro|arrivo|"
    r"vado|sono|siamo|scende|sale|supera|tramonta|diventa|arriva|rientra|la temperatura|la porta|la finestra|"
    r"il sensore|l' allarme|il sole|fa buio|viene|suona|apre|apro|si apre|si accende|si spegne)\b",
    r"\b(?:quando|non appena|ogni volta che|finche|fino a quando|prima che|dopo che|nel caso)\b",
    # English ("once" is Spanish "eleven", so it is not used)
    r"\b(?:if|when|whenever|as soon as|until|unless|in case)\b(?! (?:you|u|possible|it' s ok|ok)\b)",
    # Spanish
    r"\b(?:cuando|en cuanto|tan pronto como|siempre que|hasta que|a menos que|en caso de que)\b",
    r"\bsi (?:hace|esta|llueve|nieva|alguien|nadie|hay|no hay|salgo|salimos|entro|vuelvo|llego|baja|sube|"
    r"la temperatura|la puerta|la ventana|anochece|oscurece|se hace|se abre|suena)\b",
    # French, German, Dutch, Portuguese, Polish, Swedish (the query-type head covers the rest)
    r"\b(?:quand|lorsque|des que|jusqu' a ce que|a moins que|au cas ou)\b",
    r"\bs' il (?:pleut|fait|y a|neige)\b|\bsi (?:il|elle|quelqu' un|personne|on)\b",
    r"\b(?:wenn|falls|sobald|solange|sofern)\b",
    r"\b(?:wanneer|zodra|totdat|tenzij)\b|\bals (?:het|er|iemand|niemand|de temperatuur|de deur)\b",
    r"\bse (?:chover|estiver|fizer|houver|alguem|ninguem|eu sair|eu chegar|a temperatura|a porta|a janela)\b",
    r"\b(?:assim que|ate que|a menos que|no caso de|caso (?:a|o|haja|esteja|chova|alguem|ninguem))\b",
    r"\b(?:jesli|jezeli|gdy|jak tylko|dopoki)\b",
    r"\b(?:nar|sa fort|tills|ifall)\b|\bom (?:det|nagon|ingen|temperaturen|dorren)\b",
]
_TIME = [
    r"\b(?:tra|fra) " + _NUM + r" ?(?:minut|or[ae]\b|second)",
    r"\balle (?:ore )?\d{1,2}(?:[:.]\d{2})?\b(?! ?(?:gradi|%|per ?cento|percento))",
    r"\b(?:domani|dopodomani|stanotte alle|stasera alle|tutti i giorni|tutte le (?:sere|mattine|notti)|"
    r"ogni (?:giorno|sera|mattina|notte|ora|lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica))\b",
    r"\bin " + _NUM + r" ?(?:minute|min|hour|second)s?\b",
    r"\bat \d{1,2}(?:[:.]\d{2})? ?(?:am|pm|o' ?clock)\b|\bat (?:noon|midnight)\b",
    r"\b(?:tomorrow|tonight at|every (?:day|night|morning|evening|hour|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday))\b",
    r"\b(?:en|dentro de) " + _NUM + r" ?(?:minuto|hora|segundo)s?\b",
    r"\ba las \d{1,2}(?:[:.]\d{2})?\b",
    r"\b(?:pasado manana|manana a las|manana por la|todos los dias|todas las (?:noches|mananas)|"
    r"cada (?:dia|noche|manana|hora))\b",
]
# "turn off everything (in the kitchen)" spans several domains; "tutta la casa", "todo el salon" and
# "del tutto" / "del todo" (= completely: "abre del todo las cortinas") do not match
_ALL = (r"(?<!\bdel )\b(?:tutto|everything|todo)\b"
        r"(?! (?:il|lo|la|l'|i|gli|le|el|los|las|todas|todos|the|bene|ok|a posto|apposto|bien|okay)\b)")

_COND_RE = [re.compile(p) for p in _COND]
_TIME_RE = [re.compile(p) for p in _TIME]
_ALL_RE = re.compile(_ALL)


def complex_marker(text: str) -> str | None:
    """Return the matched marker (for logging) or None."""
    t = normalize(text)
    for rx in _COND_RE:
        for m in rx.finditer(t):
            before = t[:m.start()].split()[-3:]
            if m.group(0).split()[0] in ("se", "if", "si", "when", "quando", "cuando", "s'", "om", "als", "wenn", "ob",
                                         "falls", "jesli", "jezeli", "czy", "quand", "wanneer", "nar") \
                    and _CHECK & set(before):
                continue
            return m.group(0)
    for rx in _TIME_RE:
        m = rx.search(t)
        if m:
            return m.group(0)
    m = _ALL_RE.search(t)
    return m.group(0) if m else None
