"""Spoken replies for timers, alarms and announcements (copy of the add-on's core/assist.py tables)."""
from __future__ import annotations

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
    "it": {"alarm_at": "La sveglia è alle {t}.", "start": "Timer di {d} avviato.", "cancel": "Timer annullato.", "pause": "Timer in pausa.",
           "resume": "Il timer riparte.", "add": "Ho aggiunto {d} al timer.", "status": "Mancano {d}.",
           "alarm": "Sveglia impostata alle {t}.", "alarm_cancel": "Sveglia annullata.", "broadcast": "Annuncio fatto.",
           "no_timer": "Non c'è nessun timer attivo.", "no_device": "Questo dispositivo non supporta i timer.",
           "status_paused": "Il timer è in pausa, mancano {d}.", "alarm_name": "Sveglia"},
    "en": {"alarm_at": "The alarm is set for {t}.", "start": "{d} timer started.", "cancel": "Timer cancelled.", "pause": "Timer paused.",
           "resume": "Timer resumed.", "add": "I added {d} to the timer.", "status": "{d} left.",
           "alarm": "Alarm set for {t}.", "alarm_cancel": "Alarm cancelled.", "broadcast": "Announced.",
           "no_timer": "There is no timer running.", "no_device": "This device does not support timers.",
           "status_paused": "The timer is paused, {d} left.", "alarm_name": "Alarm"},
    "es": {"alarm_at": "La alarma está puesta a las {t}.", "start": "Temporizador de {d} iniciado.", "cancel": "Temporizador cancelado.", "pause": "Temporizador en pausa.",
           "resume": "El temporizador sigue.", "add": "He añadido {d} al temporizador.", "status": "Quedan {d}.",
           "alarm": "Alarma puesta a las {t}.", "alarm_cancel": "Alarma cancelada.", "broadcast": "Anuncio hecho.",
           "no_timer": "No hay ningún temporizador activo.", "no_device": "Este dispositivo no admite temporizadores.",
           "status_paused": "El temporizador está en pausa, quedan {d}.", "alarm_name": "Alarma"},
    "fr": {"alarm_at": "Le réveil est réglé à {t}.", "start": "Minuteur de {d} lancé.", "cancel": "Minuteur annulé.", "pause": "Minuteur en pause.",
           "resume": "Le minuteur repart.", "add": "J'ai ajouté {d} au minuteur.", "status": "Il reste {d}.",
           "alarm": "Réveil réglé à {t}.", "alarm_cancel": "Réveil annulé.", "broadcast": "Annonce faite.",
           "no_timer": "Aucun minuteur en cours.", "no_device": "Cet appareil ne gère pas les minuteurs.",
           "status_paused": "Le minuteur est en pause, il reste {d}.", "alarm_name": "Réveil"},
    "de": {"alarm_at": "Der Wecker ist auf {t} Uhr gestellt.", "start": "Timer für {d} gestartet.", "cancel": "Timer gelöscht.", "pause": "Timer pausiert.",
           "resume": "Der Timer läuft weiter.", "add": "Ich habe {d} zum Timer hinzugefügt.", "status": "Noch {d}.",
           "alarm": "Wecker auf {t} gestellt.", "alarm_cancel": "Wecker gelöscht.", "broadcast": "Durchsage gemacht.",
           "no_timer": "Es läuft kein Timer.", "no_device": "Dieses Gerät unterstützt keine Timer.",
           "status_paused": "Der Timer ist pausiert, noch {d}.", "alarm_name": "Wecker"},
    "nl": {"alarm_at": "De wekker staat op {t}.", "start": "Timer van {d} gestart.", "cancel": "Timer geannuleerd.", "pause": "Timer gepauzeerd.",
           "resume": "De timer loopt weer.", "add": "Ik heb {d} aan de timer toegevoegd.", "status": "Nog {d}.",
           "alarm": "Wekker gezet om {t}.", "alarm_cancel": "Wekker geannuleerd.", "broadcast": "Omgeroepen.",
           "no_timer": "Er loopt geen timer.", "no_device": "Dit apparaat ondersteunt geen timers.",
           "status_paused": "De timer staat op pauze, nog {d}.", "alarm_name": "Wekker"},
    "pt": {"alarm_at": "O alarme está marcado para as {t}.", "start": "Temporizador de {d} iniciado.", "cancel": "Temporizador cancelado.", "pause": "Temporizador em pausa.",
           "resume": "O temporizador continua.", "add": "Acrescentei {d} ao temporizador.", "status": "Faltam {d}.",
           "alarm": "Alarme para as {t}.", "alarm_cancel": "Alarme cancelado.", "broadcast": "Anúncio feito.",
           "no_timer": "Não há nenhum temporizador ativo.", "no_device": "Este dispositivo não suporta temporizadores.",
           "status_paused": "O temporizador está em pausa, faltam {d}.", "alarm_name": "Alarme"},
    "pl": {"alarm_at": "Budzik jest ustawiony na {t}.", "start": "Minutnik na {d} włączony.", "cancel": "Minutnik anulowany.", "pause": "Minutnik wstrzymany.",
           "resume": "Minutnik wznowiony.", "add": "Dodałem {d} do minutnika.", "status": "Zostało {d}.",
           "alarm": "Budzik ustawiony na {t}.", "alarm_cancel": "Budzik anulowany.", "broadcast": "Ogłoszenie wysłane.",
           "no_timer": "Żaden minutnik nie działa.", "no_device": "To urządzenie nie obsługuje minutników.",
           "status_paused": "Minutnik jest wstrzymany, zostało {d}.", "alarm_name": "Budzik"},
    "sv": {"alarm_at": "Väckarklockan är ställd på {t}.", "start": "Timer på {d} startad.", "cancel": "Timern avbruten.", "pause": "Timern pausad.",
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


