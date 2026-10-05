"""Timers, alarms and announcements: what EdgeDecision asks of the voice assistant itself.

The model chooses the action (assist.timer_start, assist.alarm_set, ...) and core/params.py reads the duration or the
time of day. Home Assistant runs them: its own timer intents (HassStartTimer, HassCancelTimer, ...) on the voice
satellite that heard the sentence, and HassBroadcast for announcements. The add-on cannot call intents: it returns
`intent_for(decision)` and the EdgeDecision integration (custom_components/edgedecision) calls it, then speaks
`assist_reply(...)`, or a reply built from the intent's answer (time left on a timer, errors).

An alarm is a timer that ends at the time asked ("svegliami alle 7" = a timer until 7:00, named "Sveglia"):
Home Assistant has no alarm clock of its own. Within 24 hours; like every Assist timer it is lost on restart.
"""
from __future__ import annotations

from typing import Optional

LANGS = ["it", "en", "es", "fr", "de", "nl", "pt", "pl", "sv"]

# unit words: (singular, plural) - Polish (1, 2-4, 5+)
UNITS = {
    "it": {"h": ("ora", "ore"), "m": ("minuto", "minuti"), "s": ("secondo", "secondi")},
    "en": {"h": ("hour", "hours"), "m": ("minute", "minutes"), "s": ("second", "seconds")},
    "es": {"h": ("hora", "horas"), "m": ("minuto", "minutos"), "s": ("segundo", "segundos")},
    "fr": {"h": ("heure", "heures"), "m": ("minute", "minutes"), "s": ("seconde", "secondes")},
    "de": {"h": ("Stunde", "Stunden"), "m": ("Minute", "Minuten"), "s": ("Sekunde", "Sekunden")},
    "nl": {"h": ("uur", "uur"), "m": ("minuut", "minuten"), "s": ("seconde", "seconden")},
    "pt": {"h": ("hora", "horas"), "m": ("minuto", "minutos"), "s": ("segundo", "segundos")},
    "pl": {"h": ("godzina", "godziny", "godzin"), "m": ("minuta", "minuty", "minut"),
           "s": ("sekunda", "sekundy", "sekund")},
    "sv": {"h": ("timme", "timmar"), "m": ("minut", "minuter"), "s": ("sekund", "sekunder")},
}
AND = {"it": " e ", "en": " and ", "es": " y ", "fr": " et ", "de": " und ", "nl": " en ", "pt": " e ", "pl": " i ",
       "sv": " och "}

REPLY = {
    "it": {"start": "Timer di {d} avviato.", "cancel": "Timer annullato.", "pause": "Timer in pausa.",
           "resume": "Il timer riparte.", "add": "Ho aggiunto {d} al timer.", "status": "Mancano {d}.",
           "alarm": "Sveglia impostata alle {t}.", "alarm_cancel": "Sveglia annullata.", "broadcast": "Annuncio fatto.",
           "no_timer": "Non c'è nessun timer attivo.", "no_device": "Questo dispositivo non supporta i timer.",
           "status_paused": "Il timer è in pausa, mancano {d}.", "alarm_name": "Sveglia"},
    "en": {"start": "{d} timer started.", "cancel": "Timer cancelled.", "pause": "Timer paused.",
           "resume": "Timer resumed.", "add": "I added {d} to the timer.", "status": "{d} left.",
           "alarm": "Alarm set for {t}.", "alarm_cancel": "Alarm cancelled.", "broadcast": "Announced.",
           "no_timer": "There is no timer running.", "no_device": "This device does not support timers.",
           "status_paused": "The timer is paused, {d} left.", "alarm_name": "Alarm"},
    "es": {"start": "Temporizador de {d} iniciado.", "cancel": "Temporizador cancelado.", "pause": "Temporizador en pausa.",
           "resume": "El temporizador sigue.", "add": "He añadido {d} al temporizador.", "status": "Quedan {d}.",
           "alarm": "Alarma puesta a las {t}.", "alarm_cancel": "Alarma cancelada.", "broadcast": "Anuncio hecho.",
           "no_timer": "No hay ningún temporizador activo.", "no_device": "Este dispositivo no admite temporizadores.",
           "status_paused": "El temporizador está en pausa, quedan {d}.", "alarm_name": "Alarma"},
    "fr": {"start": "Minuteur de {d} lancé.", "cancel": "Minuteur annulé.", "pause": "Minuteur en pause.",
           "resume": "Le minuteur repart.", "add": "J'ai ajouté {d} au minuteur.", "status": "Il reste {d}.",
           "alarm": "Réveil réglé à {t}.", "alarm_cancel": "Réveil annulé.", "broadcast": "Annonce faite.",
           "no_timer": "Aucun minuteur en cours.", "no_device": "Cet appareil ne gère pas les minuteurs.",
           "status_paused": "Le minuteur est en pause, il reste {d}.", "alarm_name": "Réveil"},
    "de": {"start": "Timer für {d} gestartet.", "cancel": "Timer gelöscht.", "pause": "Timer pausiert.",
           "resume": "Der Timer läuft weiter.", "add": "Ich habe {d} zum Timer hinzugefügt.", "status": "Noch {d}.",
           "alarm": "Wecker auf {t} gestellt.", "alarm_cancel": "Wecker gelöscht.", "broadcast": "Durchsage gemacht.",
           "no_timer": "Es läuft kein Timer.", "no_device": "Dieses Gerät unterstützt keine Timer.",
           "status_paused": "Der Timer ist pausiert, noch {d}.", "alarm_name": "Wecker"},
    "nl": {"start": "Timer van {d} gestart.", "cancel": "Timer geannuleerd.", "pause": "Timer gepauzeerd.",
           "resume": "De timer loopt weer.", "add": "Ik heb {d} aan de timer toegevoegd.", "status": "Nog {d}.",
           "alarm": "Wekker gezet om {t}.", "alarm_cancel": "Wekker geannuleerd.", "broadcast": "Omgeroepen.",
           "no_timer": "Er loopt geen timer.", "no_device": "Dit apparaat ondersteunt geen timers.",
           "status_paused": "De timer staat op pauze, nog {d}.", "alarm_name": "Wekker"},
    "pt": {"start": "Temporizador de {d} iniciado.", "cancel": "Temporizador cancelado.", "pause": "Temporizador em pausa.",
           "resume": "O temporizador continua.", "add": "Acrescentei {d} ao temporizador.", "status": "Faltam {d}.",
           "alarm": "Alarme para as {t}.", "alarm_cancel": "Alarme cancelado.", "broadcast": "Anúncio feito.",
           "no_timer": "Não há nenhum temporizador ativo.", "no_device": "Este dispositivo não suporta temporizadores.",
           "status_paused": "O temporizador está em pausa, faltam {d}.", "alarm_name": "Alarme"},
    "pl": {"start": "Minutnik na {d} włączony.", "cancel": "Minutnik anulowany.", "pause": "Minutnik wstrzymany.",
           "resume": "Minutnik wznowiony.", "add": "Dodałem {d} do minutnika.", "status": "Zostało {d}.",
           "alarm": "Budzik ustawiony na {t}.", "alarm_cancel": "Budzik anulowany.", "broadcast": "Ogłoszenie wysłane.",
           "no_timer": "Żaden minutnik nie działa.", "no_device": "To urządzenie nie obsługuje minutników.",
           "status_paused": "Minutnik jest wstrzymany, zostało {d}.", "alarm_name": "Budzik"},
    "sv": {"start": "Timer på {d} startad.", "cancel": "Timern avbruten.", "pause": "Timern pausad.",
           "resume": "Timern fortsätter.", "add": "Jag lade till {d} på timern.", "status": "{d} kvar.",
           "alarm": "Alarm ställt på {t}.", "alarm_cancel": "Alarmet avbrutet.", "broadcast": "Utropat.",
           "no_timer": "Ingen timer är igång.", "no_device": "Den här enheten stöder inte timers.",
           "status_paused": "Timern är pausad, {d} kvar.", "alarm_name": "Alarm"},
}


def _unit(lang: str, u: str, n: int) -> str:
    forms = UNITS.get(lang, UNITS["en"])[u]
    if lang == "pl":
        if n == 1:
            return forms[0]
        return forms[1] if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else forms[2]
    return forms[0] if n == 1 else forms[1]


def say_duration(seconds: float, lang: str) -> str:
    """3690 -> "1 ora, 1 minuto e 30 secondi" (no zero parts)."""
    t = int(round(seconds or 0))
    h, rest = divmod(t, 3600)
    m, s = divmod(rest, 60)
    parts = [f"{n} {_unit(lang, u, n)}" for n, u in ((h, "h"), (m, "m"), (s, "s")) if n]
    if not parts:
        parts = [f"0 {_unit(lang, 's', 0)}"]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + AND.get(lang, " and ") + parts[-1]


def split(seconds: float) -> dict:
    t = int(round(seconds or 0))
    h, rest = divmod(t, 3600)
    m, s = divmod(rest, 60)
    return {k: v for k, v in (("hours", h), ("minutes", m), ("seconds", s)) if v}


def assist_reply(decision, lang: str) -> str:
    R = REPLY.get(lang, REPLY["en"])
    p = decision.params or {}
    a = (decision.action or "").split(".", 1)[-1]
    if a == "timer_start":
        return R["start"].format(d=say_duration(p.get("duration"), lang))
    if a == "timer_add":
        return R["add"].format(d=say_duration(p.get("duration"), lang))
    if a == "alarm_set":
        return R["alarm"].format(t=p.get("time") or "")
    key = {"timer_cancel": "cancel", "timer_pause": "pause", "timer_resume": "resume", "alarm_cancel": "alarm_cancel",
           "broadcast": "broadcast", "timer_status": "no_timer"}.get(a, "cancel")
    return R[key]


def intent_for(decision, lang: str) -> Optional[dict]:
    """The Home Assistant intent that carries out an assist.* decision (called by the integration)."""
    if decision.policy != "EXECUTE" or not (decision.action or "").startswith("assist."):
        return None
    p = decision.params or {}
    a = decision.action.split(".", 1)[1]
    name = REPLY.get(lang, REPLY["en"])["alarm_name"]
    if a == "timer_start":
        return {"intent": "HassStartTimer", "slots": split(p.get("duration"))}
    if a == "timer_add":
        return {"intent": "HassIncreaseTimer", "slots": split(p.get("duration"))}
    if a == "timer_cancel":
        return {"intent": "HassCancelTimer", "slots": {}}
    if a == "timer_pause":
        return {"intent": "HassPauseTimer", "slots": {}}
    if a == "timer_resume":
        return {"intent": "HassUnpauseTimer", "slots": {}}
    if a == "timer_status":
        return {"intent": "HassTimerStatus", "slots": {}}
    if a == "alarm_set":  # the integration turns the time of day into a duration (Home Assistant's clock)
        return {"intent": "HassStartTimer", "slots": {"name": name}, "alarm_time": p.get("time")}
    if a == "alarm_cancel":
        return {"intent": "HassCancelTimer", "slots": {"name": name}}
    if a == "broadcast":
        return {"intent": "HassBroadcast", "slots": {"message": p.get("message") or ""}}
    return None


# question when the value is missing ("imposta un timer" -> "Per quanto tempo?")
ASK = {
    "it": {"duration": "Per quanto tempo?", "time": "A che ora?", "item": "Cosa aggiungo alla lista?",
           "message": "Cosa devo annunciare?", "source": "Su quale ingresso o app?", "preset": "In quale modalità?"},
    "en": {"duration": "For how long?", "time": "What time?", "item": "What should I add to the list?",
           "message": "What should I announce?", "source": "Which input or app?", "preset": "Which mode?"},
    "es": {"duration": "¿Por cuánto tiempo?", "time": "¿A qué hora?", "item": "¿Qué añado a la lista?",
           "message": "¿Qué quieres que anuncie?", "source": "¿Qué entrada o aplicación?", "preset": "¿En qué modo?"},
    "fr": {"duration": "Pour combien de temps ?", "time": "À quelle heure ?", "item": "Qu'est-ce que j'ajoute à la liste ?",
           "message": "Qu'est-ce que je dois annoncer ?", "source": "Quelle entrée ou application ?",
           "preset": "Quel mode ?"},
    "de": {"duration": "Für wie lange?", "time": "Um wie viel Uhr?", "item": "Was soll ich auf die Liste setzen?",
           "message": "Was soll ich durchsagen?", "source": "Welcher Eingang oder welche App?", "preset": "Welcher Modus?"},
    "nl": {"duration": "Hoe lang?", "time": "Hoe laat?", "item": "Wat zet ik op de lijst?",
           "message": "Wat moet ik omroepen?", "source": "Welke ingang of app?", "preset": "Welke stand?"},
    "pt": {"duration": "Durante quanto tempo?", "time": "A que horas?", "item": "O que acrescento à lista?",
           "message": "O que devo anunciar?", "source": "Que entrada ou aplicação?", "preset": "Em que modo?"},
    "pl": {"duration": "Na jak długo?", "time": "Na którą godzinę?", "item": "Co mam dodać do listy?",
           "message": "Co mam ogłosić?", "source": "Które wejście lub aplikacja?", "preset": "Jaki tryb?"},
    "sv": {"duration": "Hur länge?", "time": "Vilken tid?", "item": "Vad ska jag lägga till på listan?",
           "message": "Vad ska jag ropa ut?", "source": "Vilken ingång eller app?", "preset": "Vilket läge?"},
}


def ask_missing(arg_name: str, lang: str) -> Optional[str]:
    return ASK.get(lang, ASK["en"]).get(arg_name)
