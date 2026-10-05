"""What time / what day is it: answered by EdgeDecision itself with the clock of the machine it runs on.

Only short sentences that are just the question ("che ore sono?", "il giorno è oggi" as Whisper sometimes writes
"che giorno è oggi", "what's the date today") are recognised: a longer sentence that merely contains the words
("a che ora è il tramonto?", a TV programme heard in the background) is left to the model.
"""
from __future__ import annotations

import re
import time
from typing import Optional

from .text import normalize

_TIME = [  # normalised (lower case, no accents), one regex per question
    r"(?:che )?ore sono", r"che ora (?:e|e adesso)", r"(?:mi )?(?:dici|dai) l ora", r"dimmi l ora", r"l ora esatta",
    r"what time is it", r"what s the time", r"what is the time", r"tell me the time", r"the time",
    r"(?:que|a que) hora es", r"dime la hora", r"que hora tienes",
    r"quelle heure (?:est il|il est)", r"il est quelle heure", r"tu as l heure", r"vous avez l heure",
    r"wie spat ist (?:es|das|s)", r"wie viel uhr ist es", r"wieviel uhr ist es", r"wie spat",
    r"che ore so no", r"che ore son", r"che or[ae] sono",
    r"hoe laat is het", r"hoe laat",
    r"que horas sao", r"que horas e", r"diz me as horas", r"diga me as horas",
    r"ktora (?:jest )?godzina", r"ktora godzina jest", r"jaka jest godzina",
    r"vad ar klockan", r"hur mycket ar klockan", r"vad e klockan",
]
_DATE = [
    r"(?:che|il|quale|in che) giorno (?:e|e oggi|siamo|siamo oggi)", r"(?:che|il) giorno e oggi", r"oggi che giorno e",
    r"che giorno e oggi", r"(?:che|qual e la) data (?:e|di oggi|e oggi)", r"la data di oggi", r"quanti ne abbiamo(?: oggi)?",
    r"what day is (?:it|today)", r"what s (?:the date|today s date|today)", r"what is (?:the date|today s date|today)",
    r"what date is (?:it|today)", r"today s date",
    r"que dia es(?: hoy)?", r"a que dia estamos", r"a que estamos(?: hoy)?", r"que fecha es(?: hoy)?",
    r"cual es la fecha(?: de hoy)?", r"la fecha de hoy",
    r"quel jour (?:sommes nous|on est|est on|est ce|est ce aujourd hui|nous sommes)", r"on est quel jour",
    r"quelle est la date(?: d aujourd hui)?", r"quelle date (?:sommes nous|on est|est on)",
    r"welcher tag ist (?:heute|es|es heute)", r"welches datum (?:ist|haben wir)(?: heute)?",
    r"den wievielten haben wir(?: heute)?", r"der wievielte ist heute", r"was fur ein tag ist heute",
    r"welke dag is het(?: vandaag)?", r"wat is de datum(?: vandaag)?", r"welke datum is het(?: vandaag)?",
    r"de hoeveelste is het(?: vandaag)?",
    r"que dia e (?:hoje|e hoje)", r"que dia e", r"qual e a data(?: de hoje)?", r"em que dia estamos",
    r"jaki (?:jest )?(?:dzis|dzisiaj)? ?dzien", r"jaki dzien jest(?: dzisiaj| dzis)?", r"jaka (?:jest )?(?:dzis|dzisiaj)? ?data",
    r"ktorego (?:jest )?(?:dzis|dzisiaj)",
    r"vilken dag ar det(?: idag)?", r"vilket datum ar det(?: idag)?", r"vad ar det for dag(?: idag)?",
    r"vad ar det for datum(?: idag)?",
]
_TIME_RX = [re.compile(rf"\b{p}\b") for p in _TIME]
_DATE_RX = [re.compile(rf"\b{p}\b") for p in _DATE]
# words that may surround the question without changing it
_FILLER = set(normalize("""ok okay ehi hey ciao scusa scusami dici dai per favore piacere mi sai dirmi puoi dire dimmi adesso ora
oggi esatta esattamente please can you could tell me now right today exactly por favor puedes decirme me dices ahora hoy
s il te plait vous pouvez peux tu dire maintenant aujourd hui bitte kannst du mir sagen jetzt heute genau alstublieft kun
je zeggen nu vandaag precies se faz favor podes dizer me agora hoje prosze powiedz mi teraz dzisiaj dzis snalla kan du
saga nu idag exakt jasne powtarzam ripeto repeat repito repete""").split())
_ALARM = re.compile(r"\b(?:sveglia|alarm|alarma|despertador|reveil|wecker|wekker|alarme|budzik|vackarklocka|larm|timer|"
                    r"minuteur|temporizador|minutnik|tramonto|alba|sunset|sunrise|ocaso|amanecer|coucher|lever|"
                    r"sonnenuntergang|sonnenaufgang|zonsondergang|zonsopgang|por do sol|nascer|zachod|wschod|"
                    r"solnedgang|soluppgang)\b")


def _rest_is_filler(t: str, m: re.Match) -> bool:
    rest = (t[:m.start()] + " " + t[m.end():]).split()
    return all(w in _FILLER for w in rest) or len([w for w in rest if w not in _FILLER]) == 0


def clock_question(text: str) -> Optional[str]:
    """"time", "date" or None."""
    t = " ".join(normalize((text or "").replace("'", " ").replace("’", " ").replace("-", " ")).split())
    t = re.sub(r"[^\w ]", " ", t)
    t = " ".join(t.split())
    if not t or len(t.split()) > 9 or _ALARM.search(t):
        return None
    for kind, rxs in (("date", _DATE_RX), ("time", _TIME_RX)):
        for rx in rxs:
            m = rx.search(t)
            if m and _rest_is_filler(t, m):
                return kind
    return None


_WD = {
    "it": ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    "nl": ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"],
    "pt": ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"],
    "pl": ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"],
    "sv": ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"],
}
_MON = {
    "it": "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
    "en": "January February March April May June July August September October November December",
    "es": "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
    "fr": "janvier février mars avril mai juin juillet août septembre octobre novembre décembre",
    "de": "Januar Februar März April Mai Juni Juli August September Oktober November Dezember",
    "nl": "januari februari maart april mei juni juli augustus september oktober november december",
    "pt": "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro",
    "pl": "stycznia lutego marca kwietnia maja czerwca lipca sierpnia września października listopada grudnia",
    "sv": "januari februari mars april maj juni juli augusti september oktober november december",
}


def clock_reply(kind: str, lang: str, now: Optional[time.struct_time] = None) -> str:
    n = now or time.localtime()
    lang = lang if lang in _WD else "en"
    if kind == "date":
        wd, d, mon = _WD[lang][n.tm_wday], n.tm_mday, _MON[lang].split()[n.tm_mon - 1]
        return {"it": f"Oggi è {wd} {d} {mon}.", "en": f"Today is {wd}, {mon} {d}.",
                "es": f"Hoy es {wd}, {d} de {mon}.", "fr": f"Nous sommes le {wd} {d} {mon}.",
                "de": f"Heute ist {wd}, der {d}. {mon}.", "nl": f"Vandaag is het {wd} {d} {mon}.",
                "pt": f"Hoje é {wd}, {d} de {mon}.", "pl": f"Dzisiaj jest {wd}, {d} {mon}.",
                "sv": f"Idag är det {wd} den {d} {mon}."}[lang]
    h, m = n.tm_hour, n.tm_min
    hm = f"{h}:{m:02d}"
    if lang == "it":
        if h == 1:
            return f"È l'una e {m}." if m else "È l'una."
        return f"Sono le {hm}." if m else f"Sono le {h}."
    return {"en": f"It's {hm}.", "es": f"Es la {hm}." if h == 1 else f"Son las {hm}.",
            "fr": f"Il est {h} h {m:02d}." if m else f"Il est {h} h.", "de": f"Es ist {h}:{m:02d} Uhr.",
            "nl": f"Het is {hm}.", "pt": f"É {hm}." if h == 1 else f"São {hm}.", "pl": f"Jest {hm}.",
            "sv": f"Klockan är {hm}."}[lang]
