"""Spoken answer to a weather question, in every supported language.

The model chooses the capability "weather.get_state@weather.<home>" and the day ("today", "tomorrow", "saturday"...);
the numbers come from Home Assistant: the current state of the weather entity, and for other days the daily forecast
(service weather.get_forecasts, fetched by the adapter just before the reply).
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

# Home Assistant weather conditions
COND = {
    "it": {"clear-night": "sereno", "cloudy": "nuvoloso", "exceptional": "condizioni eccezionali", "fog": "nebbia",
           "hail": "grandine", "lightning": "temporale", "lightning-rainy": "temporale con pioggia",
           "partlycloudy": "parzialmente nuvoloso", "pouring": "pioggia forte", "rainy": "pioggia", "snowy": "neve",
           "snowy-rainy": "pioggia e neve", "sunny": "soleggiato", "windy": "ventoso", "windy-variant": "ventoso e nuvoloso"},
    "en": {"clear-night": "clear", "cloudy": "cloudy", "exceptional": "exceptional conditions", "fog": "fog",
           "hail": "hail", "lightning": "thunderstorm", "lightning-rainy": "thunderstorm with rain",
           "partlycloudy": "partly cloudy", "pouring": "heavy rain", "rainy": "rain", "snowy": "snow",
           "snowy-rainy": "sleet", "sunny": "sunny", "windy": "windy", "windy-variant": "windy and cloudy"},
    "es": {"clear-night": "despejado", "cloudy": "nublado", "exceptional": "condiciones excepcionales", "fog": "niebla",
           "hail": "granizo", "lightning": "tormenta", "lightning-rainy": "tormenta con lluvia",
           "partlycloudy": "parcialmente nublado", "pouring": "lluvia intensa", "rainy": "lluvia", "snowy": "nieve",
           "snowy-rainy": "aguanieve", "sunny": "soleado", "windy": "ventoso", "windy-variant": "ventoso y nublado"},
    "fr": {"clear-night": "ciel dégagé", "cloudy": "nuageux", "exceptional": "conditions exceptionnelles",
           "fog": "brouillard", "hail": "grêle", "lightning": "orage", "lightning-rainy": "orage avec pluie",
           "partlycloudy": "partiellement nuageux", "pouring": "forte pluie", "rainy": "pluie", "snowy": "neige",
           "snowy-rainy": "pluie et neige", "sunny": "ensoleillé", "windy": "venteux", "windy-variant": "venteux et nuageux"},
    "de": {"clear-night": "klar", "cloudy": "bewölkt", "exceptional": "außergewöhnliche Bedingungen", "fog": "Nebel",
           "hail": "Hagel", "lightning": "Gewitter", "lightning-rainy": "Gewitter mit Regen",
           "partlycloudy": "teilweise bewölkt", "pouring": "starker Regen", "rainy": "Regen", "snowy": "Schnee",
           "snowy-rainy": "Schneeregen", "sunny": "sonnig", "windy": "windig", "windy-variant": "windig und bewölkt"},
    "nl": {"clear-night": "helder", "cloudy": "bewolkt", "exceptional": "uitzonderlijk weer", "fog": "mist",
           "hail": "hagel", "lightning": "onweer", "lightning-rainy": "onweer met regen",
           "partlycloudy": "half bewolkt", "pouring": "zware regen", "rainy": "regen", "snowy": "sneeuw",
           "snowy-rainy": "natte sneeuw", "sunny": "zonnig", "windy": "winderig", "windy-variant": "winderig en bewolkt"},
    "pt": {"clear-night": "céu limpo", "cloudy": "nublado", "exceptional": "condições excecionais", "fog": "nevoeiro",
           "hail": "granizo", "lightning": "trovoada", "lightning-rainy": "trovoada com chuva",
           "partlycloudy": "parcialmente nublado", "pouring": "chuva forte", "rainy": "chuva", "snowy": "neve",
           "snowy-rainy": "chuva e neve", "sunny": "sol", "windy": "vento", "windy-variant": "vento e nuvens"},
    "pl": {"clear-night": "bezchmurnie", "cloudy": "pochmurno", "exceptional": "wyjątkowe warunki", "fog": "mgła",
           "hail": "grad", "lightning": "burza", "lightning-rainy": "burza z deszczem",
           "partlycloudy": "częściowe zachmurzenie", "pouring": "ulewa", "rainy": "deszcz", "snowy": "śnieg",
           "snowy-rainy": "deszcz ze śniegiem", "sunny": "słonecznie", "windy": "wietrznie",
           "windy-variant": "wietrznie i pochmurno"},
    "sv": {"clear-night": "klart", "cloudy": "mulet", "exceptional": "exceptionellt väder", "fog": "dimma",
           "hail": "hagel", "lightning": "åska", "lightning-rainy": "åska och regn", "partlycloudy": "halvklart",
           "pouring": "kraftigt regn", "rainy": "regn", "snowy": "snö", "snowy-rainy": "snöblandat regn",
           "sunny": "soligt", "windy": "blåsigt", "windy-variant": "blåsigt och molnigt"},
}

DAY_NAMES = {
    "it": {"now": "Adesso", "today": "Oggi", "tomorrow": "Domani", "day_after": "Dopodomani", "monday": "Lunedì",
           "tuesday": "Martedì", "wednesday": "Mercoledì", "thursday": "Giovedì", "friday": "Venerdì",
           "saturday": "Sabato", "sunday": "Domenica"},
    "en": {"now": "Right now", "today": "Today", "tomorrow": "Tomorrow", "day_after": "The day after tomorrow",
           "monday": "Monday", "tuesday": "Tuesday", "wednesday": "Wednesday", "thursday": "Thursday",
           "friday": "Friday", "saturday": "Saturday", "sunday": "Sunday"},
    "es": {"now": "Ahora", "today": "Hoy", "tomorrow": "Mañana", "day_after": "Pasado mañana", "monday": "El lunes",
           "tuesday": "El martes", "wednesday": "El miércoles", "thursday": "El jueves", "friday": "El viernes",
           "saturday": "El sábado", "sunday": "El domingo"},
    "fr": {"now": "En ce moment", "today": "Aujourd'hui", "tomorrow": "Demain", "day_after": "Après-demain",
           "monday": "Lundi", "tuesday": "Mardi", "wednesday": "Mercredi", "thursday": "Jeudi", "friday": "Vendredi",
           "saturday": "Samedi", "sunday": "Dimanche"},
    "de": {"now": "Gerade", "today": "Heute", "tomorrow": "Morgen", "day_after": "Übermorgen", "monday": "Am Montag",
           "tuesday": "Am Dienstag", "wednesday": "Am Mittwoch", "thursday": "Am Donnerstag", "friday": "Am Freitag",
           "saturday": "Am Samstag", "sunday": "Am Sonntag"},
    "nl": {"now": "Nu", "today": "Vandaag", "tomorrow": "Morgen", "day_after": "Overmorgen", "monday": "Maandag",
           "tuesday": "Dinsdag", "wednesday": "Woensdag", "thursday": "Donderdag", "friday": "Vrijdag",
           "saturday": "Zaterdag", "sunday": "Zondag"},
    "pt": {"now": "Agora", "today": "Hoje", "tomorrow": "Amanhã", "day_after": "Depois de amanhã",
           "monday": "Segunda-feira", "tuesday": "Terça-feira", "wednesday": "Quarta-feira", "thursday": "Quinta-feira",
           "friday": "Sexta-feira", "saturday": "Sábado", "sunday": "Domingo"},
    "pl": {"now": "Teraz", "today": "Dzisiaj", "tomorrow": "Jutro", "day_after": "Pojutrze",
           "monday": "W poniedziałek", "tuesday": "We wtorek", "wednesday": "W środę", "thursday": "W czwartek",
           "friday": "W piątek", "saturday": "W sobotę", "sunday": "W niedzielę"},
    "sv": {"now": "Just nu", "today": "Idag", "tomorrow": "Imorgon", "day_after": "I övermorgon", "monday": "På måndag",
           "tuesday": "På tisdag", "wednesday": "På onsdag", "thursday": "På torsdag", "friday": "På fredag",
           "saturday": "På lördag", "sunday": "På söndag"},
}

# {d} day, {c} condition, {hi}/{lo} temperatures, {p} probability of precipitation
FMT = {
    "it": {"now": "{d}: {c}, {t} gradi.", "day": "{d}: {c}, massima {hi}, minima {lo} gradi.",
           "rain": " Probabilità di pioggia {p}%.", "none": "Non ho le previsioni per quel giorno."},
    "en": {"now": "{d}: {c}, {t} degrees.", "day": "{d}: {c}, high {hi}, low {lo} degrees.",
           "rain": " {p}% chance of rain.", "none": "I don't have the forecast for that day."},
    "es": {"now": "{d}: {c}, {t} grados.", "day": "{d}: {c}, máxima {hi}, mínima {lo} grados.",
           "rain": " Probabilidad de lluvia del {p}%.", "none": "No tengo la previsión para ese día."},
    "fr": {"now": "{d} : {c}, {t} degrés.", "day": "{d} : {c}, maximum {hi}, minimum {lo} degrés.",
           "rain": " Risque de pluie {p} %.", "none": "Je n'ai pas les prévisions pour ce jour-là."},
    "de": {"now": "{d}: {c}, {t} Grad.", "day": "{d}: {c}, höchstens {hi}, mindestens {lo} Grad.",
           "rain": " Regenwahrscheinlichkeit {p} %.", "none": "Für diesen Tag habe ich keine Vorhersage."},
    "nl": {"now": "{d}: {c}, {t} graden.", "day": "{d}: {c}, maximaal {hi}, minimaal {lo} graden.",
           "rain": " Kans op regen {p}%.", "none": "Voor die dag heb ik geen verwachting."},
    "pt": {"now": "{d}: {c}, {t} graus.", "day": "{d}: {c}, máxima de {hi}, mínima de {lo} graus.",
           "rain": " Probabilidade de chuva de {p}%.", "none": "Não tenho a previsão para esse dia."},
    "pl": {"now": "{d}: {c}, {t} stopni.", "day": "{d}: {c}, maksymalnie {hi}, minimalnie {lo} stopni.",
           "rain": " Szansa na opady {p}%.", "none": "Nie mam prognozy na ten dzień."},
    "sv": {"now": "{d}: {c}, {t} grader.", "day": "{d}: {c}, högst {hi}, lägst {lo} grader.",
           "rain": " Risk för regn {p} %.", "none": "Jag har ingen prognos för den dagen."},
}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def target_date(day: str, today: _dt.date) -> _dt.date:
    if day in ("today", "now", None):
        return today
    if day == "tomorrow":
        return today + _dt.timedelta(days=1)
    if day == "day_after":
        return today + _dt.timedelta(days=2)
    if day in WEEKDAYS:
        return today + _dt.timedelta(days=(WEEKDAYS.index(day) - today.weekday()) % 7)
    return today


def _num(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(round(f)))


def weather_reply(state: dict, day: Optional[str], forecast: Optional[list], lang: str,
                  today: Optional[_dt.date] = None) -> str:
    """state: current state of the weather entity ({"state": "sunny", "temperature": 21, ...});
    forecast: daily forecast from weather.get_forecasts ([{"datetime", "condition", "temperature", "templow",
    "precipitation_probability"}, ...]) or None."""
    lang = lang if lang in FMT else "en"
    f, names, cond = FMT[lang], DAY_NAMES[lang], COND[lang]
    today = today or _dt.date.today()
    day = day or "today"
    if day == "today" and (not forecast or state.get("temperature") is not None):
        c = cond.get(str(state.get("state")), str(state.get("state") or ""))
        if state.get("temperature") is not None:
            return f["now"].format(d=names["now"], c=c, t=_num(state["temperature"]))
    want = target_date(day, today)
    for item in forecast or []:
        try:
            d = _dt.date.fromisoformat(str(item.get("datetime", ""))[:10])
        except ValueError:
            continue
        if d == want:
            out = f["day"].format(d=names.get(day, names["today"]), c=cond.get(item.get("condition"), item.get("condition", "")),
                                  hi=_num(item.get("temperature")), lo=_num(item.get("templow", item.get("temperature"))))
            p = item.get("precipitation_probability")
            if p is not None and float(p) >= 10:
                out += f["rain"].format(p=_num(p))
            return out
    return f["none"]
