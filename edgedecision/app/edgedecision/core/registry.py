"""Built-in action specifications (generic, HA-inspired) and capability builder.

Adapters can override or extend these specs: the model never sees a fixed
output space, only the textual rendering of each runtime capability.
"""
from __future__ import annotations

from collections import defaultdict

from .types import ActionSpec, ArgSpec, Area, Capability, Entity, max_risk

# ----------------------------------------------------------------- enum choices
# day of a weather request (weather.get_state): canonical value -> spoken words. Weekday words match the day
# itself ("sabato", "am Samstag"); the Polish accusative forms ("w sobotę") are listed with the nominative.
DAY_CHOICES = {
    "today": {"it": ["oggi", "adesso", "ora"], "en": ["today", "now", "right now"], "es": ["hoy", "ahora"]},
    "tomorrow": {"it": ["domani"], "en": ["tomorrow"], "es": ["mañana"]},
    "day_after": {"it": ["dopodomani"], "en": ["day after tomorrow", "the day after tomorrow"],
                  "es": ["pasado mañana"]},
    "monday": {"it": ["lunedì", "lunedi"], "en": ["monday"], "es": ["lunes"]},
    "tuesday": {"it": ["martedì", "martedi"], "en": ["tuesday"], "es": ["martes"]},
    "wednesday": {"it": ["mercoledì", "mercoledi"], "en": ["wednesday"], "es": ["miércoles", "miercoles"]},
    "thursday": {"it": ["giovedì", "giovedi"], "en": ["thursday"], "es": ["jueves"]},
    "friday": {"it": ["venerdì", "venerdi"], "en": ["friday"], "es": ["viernes"]},
    "saturday": {"it": ["sabato"], "en": ["saturday"], "es": ["sábado", "sabado"]},
    "sunday": {"it": ["domenica"], "en": ["sunday"], "es": ["domingo"]},
}

COLOR_CHOICES = {
    "red": {"it": ["rosso", "rossa", "rossi", "rosse"], "en": ["red"], "es": ["rojo", "roja", "rojos", "rojas"]},
    "green": {"it": ["verde", "verdi"], "en": ["green"], "es": ["verde", "verdes"]},
    "blue": {"it": ["blu"], "en": ["blue"], "es": ["azul", "azules"]},
    "lightblue": {"it": ["azzurro", "azzurra", "celeste"], "en": ["light blue", "sky blue"], "es": ["celeste", "azul claro"]},
    "yellow": {"it": ["giallo", "gialla", "gialle", "gialli"], "en": ["yellow"], "es": ["amarillo", "amarilla"]},
    "orange": {"it": ["arancione", "arancio", "arancioni"], "en": ["orange"], "es": ["naranja"]},
    "purple": {"it": ["viola"], "en": ["purple", "violet"], "es": ["morado", "morada", "violeta", "lila"]},
    "pink": {"it": ["rosa"], "en": ["pink"], "es": ["rosa", "rosado", "rosada"]},
    "white": {"it": ["bianco", "bianca", "bianche", "bianchi"], "en": ["white"], "es": ["blanco", "blanca"]},
    "turquoise": {"it": ["turchese"], "en": ["turquoise", "teal"], "es": ["turquesa"]},
    "magenta": {"it": ["magenta", "fucsia"], "en": ["magenta", "fuchsia"], "es": ["magenta", "fucsia"]},
    "gold": {"it": ["oro", "dorato", "dorata"], "en": ["gold", "golden"], "es": ["dorado", "dorada", "oro"]},
}

COLOR_TEMP_CHOICES = {
    "warm": {"it": ["calda", "caldo", "calde", "bianco caldo", "luce calda"], "en": ["warm", "warm white", "warmer"],
             "es": ["cálida", "cálido", "calida", "blanco cálido", "más cálida"]},
    "neutral": {"it": ["neutra", "neutro", "naturale", "bianco naturale"], "en": ["neutral", "natural", "daylight"],
                "es": ["neutra", "neutro", "natural", "luz natural"]},
    "cool": {"it": ["fredda", "freddo", "fredde", "bianco freddo", "luce fredda"], "en": ["cool", "cold", "cool white", "cooler"],
             "es": ["fría", "fria", "frío", "blanco frío", "más fría"]},
}

HVAC_CHOICES = {
    "heat": {"it": ["modalità riscaldamento", "caldo", "modalità caldo", "riscaldare", "scaldare"],
             "en": ["heat", "heat mode", "heating mode"], "es": ["modo calefacción", "calor", "modo calor", "calentar"]},
    "cool": {"it": ["raffrescamento", "freddo", "modalità freddo", "raffreddare", "raffreddamento"],
             "en": ["cool", "cooling", "cool mode", "cold"],
             "es": ["frío", "frio", "modo frío", "refrigeración", "enfriar"]},
    "auto": {"it": ["automatico", "auto", "modalità automatica"], "en": ["auto", "automatic"],
             "es": ["automático", "auto", "modo automático"]},
    "dry": {"it": ["deumidificazione", "deumidificare", "dry"], "en": ["dry", "dehumidify", "dehumidifier mode"],
            "es": ["deshumidificar", "deshumidificación", "seco"]},
    "fan_only": {"it": ["ventilazione", "solo ventilazione", "ventola"], "en": ["fan only", "fan mode", "ventilation"],
                 "es": ["ventilación", "solo ventilador", "modo ventilador"]},
}

# climate presets: canonical value -> spoken words (the device's own preset is matched at execution time)
PRESET_CHOICES = {
    "eco": {"it": ["eco", "risparmio", "risparmio energetico", "economia"], "en": ["eco", "economy", "energy saving"],
            "es": ["eco", "ahorro", "ahorro de energía"]},
    "away": {"it": ["fuori casa", "assenza", "vacanza", "via"], "en": ["away", "vacation", "holiday", "away mode"],
             "es": ["fuera de casa", "ausente", "vacaciones"]},
    "home": {"it": ["in casa", "presenza", "casa"], "en": ["home", "home mode"], "es": ["en casa", "presencia"]},
    "comfort": {"it": ["comfort", "confort"], "en": ["comfort"], "es": ["confort", "comodidad"]},
    "sleep": {"it": ["notte", "notturna", "sonno", "dormire"], "en": ["sleep", "night"], "es": ["noche", "dormir", "sueño"]},
    "boost": {"it": ["boost", "massima potenza", "turbo"], "en": ["boost", "turbo"], "es": ["boost", "turbo", "máxima potencia"]},
    "frost": {"it": ["antigelo", "protezione antigelo", "antigelo casa"], "en": ["frost protection", "frost", "anti freeze"],
              "es": ["antihielo", "anticongelante", "protección antiheladas"]},
}

_PRESET_MORE = {
    "eco": {"fr": ["eco", "économie", "mode éco"], "de": ["eco", "spar", "sparmodus", "energiesparen"],
            "nl": ["eco", "spaarstand", "besparing"], "pt": ["eco", "poupança", "económico"],
            "pl": ["eco", "oszczędny", "ekonomiczny"], "sv": ["eco", "spar", "sparläge"]},
    "away": {"fr": ["absence", "absent", "vacances"], "de": ["abwesend", "abwesenheit", "urlaub"],
             "nl": ["afwezig", "vakantie", "weg"], "pt": ["ausente", "ausência", "férias"],
             "pl": ["poza domem", "nieobecność", "urlop", "wakacje"], "sv": ["borta", "semester", "bortaläge"]},
    "home": {"fr": ["présence", "maison"], "de": ["zuhause", "anwesend"], "nl": ["thuis", "aanwezig"],
             "pt": ["em casa", "presença"], "pl": ["w domu", "obecność"], "sv": ["hemma", "hemmaläge"]},
    "comfort": {"fr": ["confort"], "de": ["komfort"], "nl": ["comfort"], "pt": ["conforto"], "pl": ["komfort"],
                "sv": ["komfort"]},
    "sleep": {"fr": ["nuit", "sommeil"], "de": ["nacht", "schlafen", "nachtmodus"], "nl": ["nacht", "slapen"],
              "pt": ["noite", "dormir"], "pl": ["noc", "nocny", "sen"], "sv": ["natt", "sova", "nattläge"]},
    "boost": {"fr": ["boost", "turbo"], "de": ["boost", "turbo"], "nl": ["boost", "turbo"], "pt": ["boost", "turbo"],
              "pl": ["boost", "turbo"], "sv": ["boost", "turbo"]},
    "frost": {"fr": ["hors gel", "hors-gel", "antigel"], "de": ["frostschutz", "frostschutzmodus"],
              "nl": ["vorstbeveiliging", "vorstbescherming", "antivries"], "pt": ["anticongelamento", "antigelo"],
              "pl": ["przeciwzamarzaniowy", "ochrona przed zamarzaniem"], "sv": ["frostskydd", "frostvakt"]},
}
for _k, _v in _PRESET_MORE.items():
    PRESET_CHOICES[_k].update(_v)

# ----------------------------------------------------------- domain keywords
DOMAIN_KEYWORDS = {
    "light": {"it": ["luce", "luci", "lampada", "lampadario", "faretti", "led"], "en": ["light", "lights", "lamp", "lamps"],
              "es": ["luz", "luces", "lámpara", "foco", "focos"]},
    "switch": {"it": ["presa", "interruttore"], "en": ["plug", "switch", "outlet"], "es": ["enchufe", "interruptor"]},
    "cover": {"it": ["tapparella", "tapparelle", "tenda", "tende", "persiana", "persiane", "serranda", "tapparelle"],
              "en": ["blind", "blinds", "shutter", "shutters", "curtain", "curtains", "shade"],
              "es": ["persiana", "persianas", "cortina", "cortinas", "toldo", "estor"]},
    "climate": {"it": ["termostato", "riscaldamento", "clima", "condizionatore", "temperatura", "gradi"],
                "en": ["thermostat", "heating", "ac", "air conditioner", "temperature", "degrees"],
                "es": ["termostato", "calefacción", "aire", "clima", "temperatura", "grados"]},
    "media_player": {"it": ["tv", "televisione", "musica", "volume", "stereo", "cassa", "canzone"],
                     "en": ["tv", "television", "music", "volume", "speaker", "song", "track"],
                     "es": ["tele", "televisión", "música", "volumen", "altavoz", "canción"]},
    "fan": {"it": ["ventilatore", "ventola"], "en": ["fan"], "es": ["ventilador"]},
    "lock": {"it": ["serratura", "porta", "chiave"], "en": ["lock", "door"], "es": ["cerradura", "puerta", "llave"]},
    "sensor": {"it": ["temperatura", "umidità", "gradi", "sensore"], "en": ["temperature", "humidity", "sensor", "degrees"],
               "es": ["temperatura", "humedad", "sensor", "grados"]},
    "binary_sensor": {"it": ["finestra", "porta", "aperta", "chiusa"], "en": ["window", "door", "open", "closed"],
                      "es": ["ventana", "puerta", "abierta", "cerrada"]},
    "vacuum": {"it": ["robot", "aspirapolvere", "pulizia"], "en": ["vacuum", "robot", "cleaning"],
               "es": ["robot", "aspiradora", "limpieza"]},
    "scene": {"it": ["scena", "atmosfera"], "en": ["scene", "mode"], "es": ["escena", "ambiente"]},
    "alarm_control_panel": {"it": ["allarme", "antifurto"], "en": ["alarm", "security"], "es": ["alarma"]},
    "valve": {"it": ["valvola", "acqua", "gas", "rubinetto"], "en": ["valve", "water", "gas", "tap"],
              "es": ["válvula", "agua", "gas", "llave de paso"]},
    "water_heater": {"it": ["scaldabagno", "boiler", "acqua calda", "caldaia"], "en": ["water heater", "boiler", "hot water"],
                     "es": ["calentador", "termo", "agua caliente", "caldera"]},
    "humidifier": {"it": ["umidificatore", "deumidificatore", "umidità"], "en": ["humidifier", "dehumidifier", "humidity"],
                   "es": ["humidificador", "deshumidificador", "humedad"]},
    "lawn_mower": {"it": ["tosaerba", "robot rasaerba", "prato"], "en": ["lawn mower", "mower", "lawn"],
                   "es": ["cortacésped", "robot cortacésped", "césped"]},
    "button": {"it": ["pulsante", "bottone", "apri", "premi"], "en": ["button", "press", "open"], "es": ["botón", "pulsa", "abre"]},
    "script": {"it": ["routine", "script", "avvia", "esegui"], "en": ["routine", "script", "run"], "es": ["rutina", "script", "ejecuta"]},
    "automation": {"it": ["automazione", "automatismo"], "en": ["automation"], "es": ["automatización", "automatismo"]},
    "person": {"it": ["casa", "chi", "dove", "a casa"], "en": ["home", "who", "where"], "es": ["casa", "quién", "dónde"]},
    "todo": {"it": ["lista", "lista della spesa", "aggiungi", "promemoria"], "en": ["list", "shopping list", "add", "to-do"],
             "es": ["lista", "lista de la compra", "añade", "tareas"]},
    "assist": {"it": ["timer", "sveglia", "annuncia", "minuti"], "en": ["timer", "alarm", "announce", "minutes"],
               "es": ["temporizador", "alarma", "despertador", "anuncia", "minutos"]},
    "home": {"it": ["tutto", "casa", "spegni tutto", "acceso"], "en": ["everything", "house", "all off", "left on"],
             "es": ["todo", "casa", "apaga todo", "encendido"]},
    "weather": {"it": ["meteo", "tempo", "previsioni", "pioggia", "piove", "sole"],
                "en": ["weather", "forecast", "rain", "sunny", "umbrella"],
                "es": ["tiempo", "clima", "previsión", "pronóstico", "lluvia", "llover"]},
}

DOMAIN_NOUN_EN = {
    "light": ("light", "lights"), "switch": ("switch", "switches"), "cover": ("cover/blind", "covers/blinds"),
    "climate": ("thermostat", "thermostats"), "media_player": ("media player", "media players"),
    "fan": ("fan", "fans"), "lock": ("lock", "locks"), "sensor": ("sensor", "sensors"),
    "binary_sensor": ("contact sensor", "contact sensors"), "vacuum": ("robot vacuum", "robot vacuums"),
    "scene": ("scene", "scenes"), "alarm_control_panel": ("alarm", "alarms"),
    "weather": ("weather service", "weather services"),
    "valve": ("valve", "valves"), "water_heater": ("water heater", "water heaters"),
    "humidifier": ("humidifier", "humidifiers"), "lawn_mower": ("lawn mower", "lawn mowers"),
    "button": ("button", "buttons"), "script": ("script / routine", "scripts"), "automation": ("automation", "automations"),
    "person": ("person", "people"), "todo": ("to-do list", "to-do lists"),
    "assist": ("voice assistant", "voice assistants"), "home": ("whole home", "whole home"),
    "agent": ("other assistant", "other assistants"),
}


def _pct(name, lo=0, hi=100, required=True):
    return ArgSpec(name=name, kind="percent", min=lo, max=hi, unit="%", required=required)


def _step(name, applies_to, sign, default, unit="%", lo=0, hi=100):
    return ArgSpec(name=name, kind="step", min=lo, max=hi, unit=unit, required=False, default=default,
                   applies_to=applies_to, sign=sign)


def _kw(it, en, es):
    return {"it": it, "en": en, "es": es}


ON_KW = _kw(["accendi", "accendere", "accesa", "acceso", "attiva", "on"], ["turn on", "switch on", "on", "start"],
            ["enciende", "encender", "prende", "activa", "encendida"])
OFF_KW = _kw(["spegni", "spegnere", "spenta", "spento", "disattiva", "off"], ["turn off", "switch off", "off", "stop"],
             ["apaga", "apagar", "desactiva", "apagada"])
STATE_KW = _kw(["è", "com'è", "stato", "accesa", "aperta", "quanti", "quanto"], ["is", "status", "state", "what", "how"],
               ["está", "estado", "cuánto", "qué"])


def default_actions() -> list[ActionSpec]:
    A = ActionSpec
    acts = [
        # ------------------------------------------------------------ light
        A("light.turn_on", "turn on / switch on a light", groupable=True, keywords=ON_KW,
          execute={"service": "light.turn_on"}),
        A("light.turn_off", "turn off / switch off a light", groupable=True, keywords=OFF_KW,
          execute={"service": "light.turn_off"}),
        A("light.set_brightness", "set light brightness to a given level", args=[_pct("brightness", 1, 100)],
          requires=["brightness"], groupable=True,
          keywords=_kw(["luminosità", "intensità", "percento", "%"], ["brightness", "dim", "percent", "%"],
                       ["brillo", "intensidad", "por ciento", "%"]),
          execute={"service": "light.turn_on", "data": {"brightness_pct": "{brightness}"}}),
        A("light.brightness_up", "increase light brightness, make the light brighter",
          args=[_step("step", "brightness", +1, 15)], requires=["brightness"], groupable=True,
          keywords=_kw(["alza", "aumenta", "più luce", "più forte", "luminosa"], ["brighter", "increase", "brighten", "turn up"],
                       ["sube", "aumenta", "más luz", "más brillo"]),
          execute={"service": "light.turn_on", "data": {"brightness_step_pct": "{step}"}}),
        A("light.brightness_down", "decrease light brightness, dim the light",
          args=[_step("step", "brightness", -1, 15)], requires=["brightness"], groupable=True,
          keywords=_kw(["abbassa", "diminuisci", "attenua", "meno luce", "soffusa"], ["dim", "dimmer", "decrease", "lower", "turn down"],
                       ["baja", "atenúa", "disminuye", "menos luz", "menos brillo"]),
          execute={"service": "light.turn_on", "data": {"brightness_step_pct": "-{step}"}}),
        A("light.set_color", "change the light color", args=[ArgSpec("color", "enum", choices=COLOR_CHOICES)],
          requires=["color"], groupable=True, keywords=_kw(["colore", "rosso", "blu", "verde"], ["color", "colour", "red", "blue"],
                                                           ["color", "rojo", "azul", "verde"]),
          execute={"service": "light.turn_on", "data": {"color_name": "{color}"}}),
        A("light.set_color_temp", "set light white temperature (warm or cool white)",
          args=[ArgSpec("color_temp", "enum", choices=COLOR_TEMP_CHOICES)], requires=["color_temp"], groupable=True,
          keywords=_kw(["calda", "fredda", "bianco"], ["warm", "cool", "white"], ["cálida", "fría", "blanco"]),
          execute={"service": "light.turn_on", "data": {"color_temp_kelvin": {"warm": 2700, "neutral": 4000, "cool": 6000}}}),
        A("light.get_state", "ask whether a light is on or off", risk="none", kind="read", groupable=True, keywords=STATE_KW),
        # ----------------------------------------------------------- switch
        A("switch.turn_on", "turn on / power on a switch or smart plug", keywords=ON_KW, execute={"service": "switch.turn_on"}),
        A("switch.turn_off", "turn off / power off a switch or smart plug", keywords=OFF_KW, execute={"service": "switch.turn_off"}),
        A("switch.get_state", "ask whether a switch or plug is on or off", risk="none", kind="read", groupable=True, keywords=STATE_KW),
        # ------------------------------------------------------------ cover
        A("cover.open", "open / raise a cover (blinds, shutters, curtains, doors)", groupable=True,
          keywords=_kw(["apri", "alza", "tira su", "aprire"], ["open", "raise", "lift", "up"], ["abre", "sube", "levanta", "abrir"]),
          execute={"service": "cover.open_cover"}),
        A("cover.close", "close / lower a cover (blinds, shutters, curtains, doors)", groupable=True,
          keywords=_kw(["chiudi", "abbassa", "tira giù", "chiudere"], ["close", "lower", "shut", "down"], ["cierra", "baja", "cerrar"]),
          execute={"service": "cover.close_cover"}),
        A("cover.stop", "stop a moving cover", keywords=_kw(["ferma", "stop", "blocca"], ["stop", "halt"], ["para", "detén", "stop"]),
          execute={"service": "cover.stop_cover"}),
        A("cover.set_position", "set a cover to a given opening position", args=[_pct("position", 0, 100)],
          requires=["position"], groupable=True,
          keywords=_kw(["posizione", "percento", "metà", "%"], ["position", "percent", "halfway", "%"],
                       ["posición", "por ciento", "mitad", "%"]),
          execute={"service": "cover.set_cover_position", "data": {"position": "{position}"}}),
        A("cover.get_state", "ask whether a cover is open or closed", risk="none", kind="read", groupable=True, keywords=STATE_KW),
        # ---------------------------------------------------------- climate
        A("climate.set_temperature", "set the target temperature of the thermostat / heating / air conditioning",
          args=[ArgSpec("temperature", "temperature", min=5, max=35, unit="°C")],
          keywords=_kw(["gradi", "temperatura", "imposta"], ["degrees", "temperature", "set"], ["grados", "temperatura", "pon"]),
          execute={"service": "climate.set_temperature", "data": {"temperature": "{temperature}"}}),
        A("climate.temperature_up", "raise the thermostat target temperature, make it warmer",
          args=[_step("step", "temperature", +1, 1, unit="°C", lo=0, hi=10)],
          keywords=_kw(["alza", "aumenta", "più caldo", "freddo"], ["warmer", "raise", "increase", "cold"], ["sube", "más calor", "frío"]),
          execute={"service": "climate.set_temperature", "data": {"temperature": "{temperature}"}}),
        A("climate.temperature_down", "lower the thermostat target temperature, make it cooler",
          args=[_step("step", "temperature", -1, 1, unit="°C", lo=0, hi=10)],
          keywords=_kw(["abbassa", "diminuisci", "più fresco", "caldo"], ["cooler", "lower", "decrease", "hot"], ["baja", "más fresco", "calor"]),
          execute={"service": "climate.set_temperature", "data": {"temperature": "{temperature}"}}),
        A("climate.set_hvac_mode", "change the climate operating mode (heat, cool, auto, dry, fan)",
          args=[ArgSpec("hvac_mode", "enum", choices=HVAC_CHOICES)], requires=["hvac_modes"],
          keywords=_kw(["modalità", "riscaldamento", "raffrescamento"], ["mode", "heat", "cool"], ["modo", "calor", "frío"]),
          execute={"service": "climate.set_hvac_mode", "data": {"hvac_mode": "{hvac_mode}"}}),
        A("climate.turn_on", "turn on the heating / air conditioning / climate device", keywords=ON_KW,
          execute={"service": "climate.turn_on"}),
        A("climate.turn_off", "turn off the heating / air conditioning / climate device", keywords=OFF_KW,
          execute={"service": "climate.turn_off"}),
        A("climate.get_state", "ask the current temperature or thermostat setting", risk="none", kind="read", keywords=STATE_KW),
        # ----------------------------------------------------- media player
        A("media_player.get_state", "ask whether a TV or speaker is on and what it is playing", risk="none",
          kind="read", groupable=True, keywords=STATE_KW),
        A("media_player.turn_on", "turn on a TV / speaker / media player", keywords=ON_KW, execute={"service": "media_player.turn_on"}),
        A("media_player.turn_off", "turn off a TV / speaker / media player", keywords=OFF_KW, execute={"service": "media_player.turn_off"}),
        A("media_player.play", "play / resume music or video playback", requires=["playback"],
          keywords=_kw(["play", "riproduci", "metti", "musica", "riprendi"], ["play", "resume", "music"], ["reproduce", "pon", "música", "continúa"]),
          execute={"service": "media_player.media_play"}),
        A("media_player.pause", "pause music or video playback", requires=["playback"],
          keywords=_kw(["pausa", "metti in pausa", "ferma"], ["pause", "hold"], ["pausa", "pausar"]),
          execute={"service": "media_player.media_pause"}),
        A("media_player.next_track", "skip to the next song / track", requires=["tracks"],
          keywords=_kw(["prossima", "successiva", "avanti", "salta"], ["next", "skip"], ["siguiente", "salta", "próxima"]),
          execute={"service": "media_player.media_next_track"}),
        A("media_player.previous_track", "go back to the previous song / track", requires=["tracks"],
          keywords=_kw(["precedente", "indietro"], ["previous", "back", "last song"], ["anterior", "atrás"]),
          execute={"service": "media_player.media_previous_track"}),
        A("media_player.volume_set", "set the volume to a given level", args=[_pct("volume", 0, 100)], requires=["volume"],
          keywords=_kw(["volume", "percento"], ["volume", "percent"], ["volumen", "por ciento"]),
          execute={"service": "media_player.volume_set", "data": {"volume_level": "{volume/100}"}}),
        A("media_player.volume_up", "turn the volume up, louder", args=[_step("step", "volume", +1, 10)], requires=["volume"],
          keywords=_kw(["alza", "volume", "più forte"], ["louder", "volume up", "turn up"], ["sube", "volumen", "más alto"]),
          execute={"service": "media_player.volume_set", "data": {"volume_level": "{volume/100}"}}),
        A("media_player.volume_down", "turn the volume down, quieter", args=[_step("step", "volume", -1, 10)], requires=["volume"],
          keywords=_kw(["abbassa", "volume", "più piano"], ["quieter", "volume down", "turn down"], ["baja", "volumen", "más bajo"]),
          execute={"service": "media_player.volume_set", "data": {"volume_level": "{volume/100}"}}),
        A("media_player.play_content", "play a specific song, artist, album, playlist or radio station by name",
          args=[ArgSpec(name="content", kind="text", required=True)], requires=["search"],
          keywords=_kw(["metti", "riproduci", "ascoltare", "radio", "playlist", "canzone"],
                       ["play", "listen", "radio", "playlist", "song"], ["pon", "reproduce", "escuchar", "radio", "canción"]),
          execute={"service": "music_assistant.play_media",
                   "data": {"media_id": "{content}", "media_type": "{media_type}"}}),
        A("media_player.mute", "mute the audio", requires=["volume"],
          keywords=_kw(["muto", "silenzia", "togli l'audio"], ["mute", "silence"], ["silencia", "mute", "quita el sonido"]),
          execute={"service": "media_player.volume_mute", "data": {"is_volume_muted": True}}),
        # -------------------------------------------------------------- fan
        A("fan.turn_on", "turn on a fan", keywords=ON_KW, execute={"service": "fan.turn_on"}),
        A("fan.turn_off", "turn off a fan", keywords=OFF_KW, execute={"service": "fan.turn_off"}),
        A("fan.set_speed", "set fan speed to a given percentage", args=[_pct("percentage", 0, 100)], requires=["speed"],
          keywords=_kw(["velocità", "percento"], ["speed", "percent"], ["velocidad", "por ciento"]),
          execute={"service": "fan.set_percentage", "data": {"percentage": "{percentage}"}}),
        # ------------------------------------------------------------- lock
        A("lock.lock", "lock a door lock", risk="medium",
          keywords=_kw(["chiudi a chiave", "blocca", "serratura"], ["lock"], ["cierra con llave", "bloquea"]),
          execute={"service": "lock.lock"}),
        A("lock.unlock", "unlock a door lock", risk="high",
          keywords=_kw(["apri", "sblocca", "serratura"], ["unlock", "open"], ["abre", "desbloquea"]),
          execute={"service": "lock.unlock"}),
        A("lock.get_state", "ask whether a door is locked", risk="none", kind="read", groupable=True, keywords=STATE_KW),
        # ----------------------------------------------------------- sensors
        A("sensor.get_state", "read a sensor value (temperature, humidity, power...)", risk="none", kind="read",
          keywords=_kw(["quanti gradi", "temperatura", "umidità", "quanto"], ["temperature", "humidity", "how much", "what is"],
                       ["temperatura", "humedad", "cuánto", "cuántos grados"])),
        A("binary_sensor.get_state", "check a door / window (open or closed) or an alarm sensor (water leak, smoke, gas, "
          "motion)", risk="none", kind="read", groupable=True,
          keywords=_kw(["aperta", "chiusa", "finestra", "porta"], ["open", "closed", "window", "door"], ["abierta", "cerrada", "ventana"])),
        # ----------------------------------------------------------- weather
        A("weather.get_state", "tell the weather: current conditions or the forecast for a day", risk="none",
          kind="read", args=[ArgSpec(name="day", kind="enum", choices=DAY_CHOICES, required=False, default="today")],
          keywords=_kw(["meteo", "tempo", "previsioni", "pioverà", "ombrello"], ["weather", "forecast", "rain", "umbrella"],
                       ["tiempo", "previsión", "lloverá", "paraguas"])),
        # ------------------------------------------------------------ vacuum
        A("vacuum.start", "start the robot vacuum cleaning",
          keywords=_kw(["pulisci", "aspira", "avvia", "fai partire"], ["clean", "vacuum", "start"], ["limpia", "aspira", "inicia"]),
          execute={"service": "vacuum.start"}),
        A("vacuum.pause", "pause / stop the robot vacuum",
          keywords=_kw(["ferma", "pausa", "stop"], ["stop", "pause"], ["para", "pausa", "detén"]),
          execute={"service": "vacuum.pause"}),
        A("vacuum.return_to_base", "send the robot vacuum back to its charging dock", requires=["return_home"],
          keywords=_kw(["base", "torna", "ricarica"], ["dock", "home", "base", "charge"], ["base", "vuelve", "carga"]),
          execute={"service": "vacuum.return_to_base"}),
        # ------------------------------------------------------------- scene
        A("scene.activate", "activate a scene", keywords=_kw(["scena", "attiva", "modalità"], ["scene", "activate", "mode"],
                                                            ["escena", "activa", "modo"]),
          execute={"service": "scene.turn_on"}),
        # ------------------------------------------------------------- alarm
        A("alarm_control_panel.arm_away", "arm the alarm in away mode (nobody home)", risk="medium",
          keywords=_kw(["inserisci", "attiva", "allarme"], ["arm", "alarm"], ["activa", "conecta", "alarma"]),
          execute={"service": "alarm_control_panel.alarm_arm_away"}),
        A("alarm_control_panel.arm_home", "arm the alarm in home / night mode (people inside)", risk="medium",
          keywords=_kw(["notte", "perimetrale", "allarme"], ["night", "home", "arm"], ["noche", "perimetral", "alarma"]),
          execute={"service": "alarm_control_panel.alarm_arm_home"}),
        A("alarm_control_panel.disarm", "disarm / turn off the alarm", risk="high",
          keywords=_kw(["disinserisci", "disattiva", "spegni", "allarme"], ["disarm", "turn off"], ["desactiva", "desconecta", "alarma"]),
          execute={"service": "alarm_control_panel.alarm_disarm"}),
        # ================================================================ round 7
        A("fan.get_state", "ask whether a fan is on or off", risk="none", kind="read", groupable=True, keywords=STATE_KW),
        # ----------------------------------------------------- climate presets
        A("climate.set_preset_mode", "set the climate preset (eco, away, comfort, sleep, boost, frost protection)",
          args=[ArgSpec("preset", "enum", choices=PRESET_CHOICES)], requires=["presets"],
          keywords=_kw(["modalità", "eco", "antigelo", "vacanza"], ["mode", "eco", "away", "frost"],
                       ["modo", "eco", "antihielo", "vacaciones"]),
          execute={"service": "climate.set_preset_mode", "data": {"preset_mode": "{preset}"}}),
        # ---------------------------------------------------------------- valve
        A("valve.open", "open a valve (water, gas, irrigation)", risk="medium", groupable=True,
          keywords=_kw(["apri", "acqua", "gas", "valvola"], ["open", "water", "turn on"], ["abre", "agua", "gas"]),
          execute={"service": "valve.open_valve"}),
        A("valve.close", "close / shut off a valve (main water, gas, irrigation)", groupable=True,
          keywords=_kw(["chiudi", "acqua", "gas", "valvola"], ["close", "shut off", "turn off the water"], ["cierra", "corta"]),
          execute={"service": "valve.close_valve"}),
        A("valve.get_state", "ask whether a valve is open or closed", risk="none", kind="read", groupable=True,
          keywords=STATE_KW),
        # --------------------------------------------------------- water heater
        A("water_heater.turn_on", "turn on the water heater / boiler (hot water)", keywords=ON_KW,
          execute={"service": "water_heater.turn_on"}),
        A("water_heater.turn_off", "turn off the water heater / boiler (hot water)", keywords=OFF_KW,
          execute={"service": "water_heater.turn_off"}),
        A("water_heater.set_temperature", "set the hot water temperature of the water heater",
          args=[ArgSpec("temperature", "temperature", min=30, max=75, unit="°C")],
          keywords=_kw(["gradi", "acqua calda", "temperatura"], ["degrees", "hot water", "temperature"],
                       ["grados", "agua caliente", "temperatura"]),
          execute={"service": "water_heater.set_temperature", "data": {"temperature": "{temperature}"}}),
        A("water_heater.get_state", "ask the state or temperature of the water heater", risk="none", kind="read",
          keywords=STATE_KW),
        # ---------------------------------------------------------- humidifier
        A("humidifier.turn_on", "turn on a humidifier or dehumidifier", keywords=ON_KW,
          execute={"service": "humidifier.turn_on"}),
        A("humidifier.turn_off", "turn off a humidifier or dehumidifier", keywords=OFF_KW,
          execute={"service": "humidifier.turn_off"}),
        A("humidifier.set_humidity", "set the target humidity of a humidifier or dehumidifier",
          args=[_pct("humidity", 20, 90)], requires=["humidity"],
          keywords=_kw(["umidità", "percento"], ["humidity", "percent"], ["humedad", "por ciento"]),
          execute={"service": "humidifier.set_humidity", "data": {"humidity": "{humidity}"}}),
        A("humidifier.get_state", "ask whether a humidifier / dehumidifier is on", risk="none", kind="read",
          keywords=STATE_KW),
        # ----------------------------------------------------------- lawn mower
        A("lawn_mower.start_mowing", "start the robot lawn mower",
          keywords=_kw(["taglia", "tosaerba", "prato"], ["mow", "mower", "lawn"], ["corta", "césped"]),
          execute={"service": "lawn_mower.start_mowing"}),
        A("lawn_mower.pause", "pause / stop the robot lawn mower",
          keywords=_kw(["ferma", "pausa"], ["stop", "pause"], ["para", "pausa"]), execute={"service": "lawn_mower.pause"}),
        A("lawn_mower.dock", "send the robot lawn mower back to its base",
          keywords=_kw(["base", "rientra"], ["dock", "home", "base"], ["base", "vuelve"]), execute={"service": "lawn_mower.dock"}),
        # --------------------------------------------------------------- button
        A("button.press", "press a button (open a gate, restart a device, ring)", risk="medium",
          keywords=_kw(["premi", "apri", "pulsante"], ["press", "push", "open"], ["pulsa", "abre", "botón"]),
          execute={"service": "button.press"}),
        # ---------------------------------------------------------- cover tilt
        A("cover.open_tilt", "open the slats of venetian blinds (tilt open)", requires=["tilt"], groupable=True,
          keywords=_kw(["lamelle", "orienta", "inclina", "apri"], ["slats", "tilt", "open"], ["lamas", "orienta", "inclina"]),
          execute={"service": "cover.open_cover_tilt"}),
        A("cover.close_tilt", "close the slats of venetian blinds (tilt closed)", requires=["tilt"], groupable=True,
          keywords=_kw(["lamelle", "orienta", "inclina", "chiudi"], ["slats", "tilt", "close"], ["lamas", "orienta", "cierra"]),
          execute={"service": "cover.close_cover_tilt"}),
        A("cover.set_tilt_position", "set the slat angle of venetian blinds", args=[_pct("tilt", 0, 100)],
          requires=["tilt_position"], groupable=True,
          keywords=_kw(["lamelle", "inclinazione"], ["slats", "tilt"], ["lamas", "inclinación"]),
          execute={"service": "cover.set_cover_tilt_position", "data": {"tilt_position": "{tilt}"}}),
        # ---------------------------------------------------------------- media
        A("media_player.select_source", "switch the input / source / app of a TV or player (HDMI, Netflix, radio)",
          args=[ArgSpec("source", "source", required=True)], requires=["sources"],
          keywords=_kw(["sorgente", "hdmi", "ingresso", "netflix", "canale"], ["source", "input", "hdmi", "netflix", "channel"],
                       ["fuente", "entrada", "hdmi", "netflix", "canal"]),
          execute={"service": "media_player.select_source", "data": {"source": "{source}"}}),
        A("media_player.shuffle", "turn on shuffle (random order)", requires=["shuffle"],
          keywords=_kw(["casuale", "shuffle", "mescola"], ["shuffle", "random"], ["aleatorio", "mezcla"]),
          execute={"service": "media_player.shuffle_set", "data": {"shuffle": True}}),
        # ----------------------------------------------------- scripts, automations
        A("script.run", "run a script / routine", keywords=_kw(["avvia", "esegui", "routine"], ["run", "start", "routine"],
                                                              ["ejecuta", "inicia", "rutina"]),
          execute={"service": "script.turn_on"}),
        A("automation.turn_on", "enable an automation", keywords=_kw(["attiva", "abilita", "automazione"],
                                                                     ["enable", "turn on", "automation"],
                                                                     ["activa", "habilita", "automatización"]),
          execute={"service": "automation.turn_on"}),
        A("automation.turn_off", "disable an automation", keywords=_kw(["disattiva", "disabilita", "automazione"],
                                                                       ["disable", "turn off", "automation"],
                                                                       ["desactiva", "deshabilita", "automatización"]),
          execute={"service": "automation.turn_off"}),
        # --------------------------------------------------------------- people
        A("person.get_state", "ask whether a person is at home / where someone is", risk="none", kind="read",
          groupable=True, keywords=_kw(["a casa", "chi", "dove"], ["home", "who", "where"], ["en casa", "quién", "dónde"])),
        # ------------------------------------------------------------ to-do lists
        A("todo.add_item", "add an item to a list (shopping list, to-do list)",
          args=[ArgSpec("item", "text", required=True)],
          keywords=_kw(["aggiungi", "lista", "spesa", "comprare"], ["add", "list", "shopping", "buy"],
                       ["añade", "lista", "compra", "comprar"]),
          execute={"service": "todo.add_item", "data": {"item": "{item}"}}),
        # --------------------------------------------- the voice assistant itself (timers, alarms, announcements)
        A("assist.timer_start", "start a countdown timer", args=[ArgSpec("duration", "duration", required=True)],
          keywords=_kw(["timer", "minuti", "imposta"], ["timer", "minutes", "set"], ["temporizador", "minutos", "pon"])),
        A("assist.timer_cancel", "cancel / stop the timer", keywords=_kw(["annulla", "ferma", "timer"], ["cancel", "stop", "timer"],
                                                                        ["cancela", "para", "temporizador"])),
        A("assist.timer_status", "how much time is left on the timer", risk="none", kind="read",
          keywords=_kw(["quanto manca", "timer"], ["how long", "left", "timer"], ["cuánto falta", "temporizador"])),
        A("assist.timer_pause", "pause the timer", keywords=_kw(["pausa", "timer"], ["pause", "timer"], ["pausa", "temporizador"])),
        A("assist.timer_resume", "resume the paused timer", keywords=_kw(["riprendi", "timer"], ["resume", "timer"],
                                                                         ["reanuda", "temporizador"])),
        A("assist.timer_add", "add time to the running timer", args=[ArgSpec("duration", "duration", required=True)],
          keywords=_kw(["aggiungi", "timer", "minuti"], ["add", "timer", "more"], ["añade", "temporizador", "más"])),
        A("assist.alarm_set", "set an alarm / wake-up call at a time of day", args=[ArgSpec("time", "time", required=True)],
          keywords=_kw(["sveglia", "svegliami", "alle"], ["alarm", "wake me", "at"], ["alarma", "despiértame", "a las"])),
        A("assist.alarm_cancel", "cancel / turn off the alarm", keywords=_kw(["sveglia", "annulla", "spegni"],
                                                                             ["alarm", "cancel", "turn off"],
                                                                             ["alarma", "despertador", "cancela"])),
        A("assist.broadcast", "announce a message on all the speakers of the house",
          args=[ArgSpec("message", "text", required=True)],
          keywords=_kw(["annuncia", "di a tutti", "avvisa"], ["announce", "broadcast", "tell everyone"],
                       ["anuncia", "avisa", "di a todos"])),
        # ------------------------- another assistant (core/virtual.py): what the home cannot do itself -> ESCALATE
        A("agent.weather", "tell the weather: current conditions or the forecast for a day (answered by another "
          "assistant)", risk="none", kind="read", requires=["weather"],
          keywords=_kw(["meteo", "tempo", "previsioni", "pioverà", "ombrello"], ["weather", "forecast", "rain", "umbrella"],
                       ["tiempo", "previsión", "lloverá", "paraguas"])),
        A("agent.todo_add", "add an item to a list (shopping list, to-do list) (done by another assistant)",
          risk="none", requires=["todo"],
          keywords=_kw(["aggiungi", "lista", "spesa", "comprare"], ["add", "list", "shopping", "buy"],
                       ["añade", "lista", "compra", "comprar"])),
        A("agent.play_content", "play a specific song, artist, album, playlist or radio station by name (played by "
          "another assistant)", risk="none", requires=["search"],
          keywords=_kw(["metti", "riproduci", "ascoltare", "radio", "playlist", "canzone"],
                       ["play", "listen", "radio", "playlist", "song"], ["pon", "reproduce", "escuchar", "radio", "canción"])),
        # ------------------------------------------------------------ whole home
        A("home.turn_off_all", "turn off everything in the house (lights, TVs, speakers, fans, plugs)",
          keywords=_kw(["spegni tutto", "tutto"], ["turn off everything", "all off"], ["apaga todo", "todo"])),
        A("home.get_state", "what is still on, open or unlocked in the house", risk="none", kind="read",
          keywords=_kw(["acceso", "aperto", "tutto", "rimasto"], ["left on", "open", "everything"], ["encendido", "abierto", "todo"])),
    ]
    return acts


# Device-class based risk overrides (garage doors and gates are dangerous to open).
DEVICE_CLASS_RISK = {
    ("cover", "garage"): {"cover.open": "high", "cover.close": "medium", "cover.set_position": "high"},
    ("cover", "gate"): {"cover.open": "high", "cover.close": "medium", "cover.set_position": "high"},
    ("cover", "door"): {"cover.open": "medium", "cover.close": "medium"},
    ("valve", "gas"): {"valve.open": "high", "valve.close": "low"},
    ("button", "gate"): {"button.press": "high"},
}


def entity_action_risk(entity: Entity, spec: ActionSpec) -> str:
    extra = DEVICE_CLASS_RISK.get((entity.domain, entity.device_class or ""), {})
    return max_risk(spec.risk, extra.get(spec.action, "none"), entity.risk_overrides.get(spec.action, "none"))


def entity_supports(entity: Entity, spec: ActionSpec) -> bool:
    if spec.domain != entity.domain:
        return False
    if spec.action == "cover.stop" and "no_stop" in entity.features:
        return False
    return all(f in entity.features for f in spec.requires)


def group_key(e: Entity) -> str:
    """Entities are grouped by domain (+ device class for covers/media), e.g. 'light', 'cover.shutter'."""
    if e.domain in ("cover", "media_player", "binary_sensor") and e.device_class:
        return f"{e.domain}.{e.device_class}"
    return e.domain


def build_capabilities(areas: list[Area], entities: list[Entity], actions: list[ActionSpec],
                       groups: bool = True) -> list[Capability]:
    caps: list[Capability] = []
    floor_of = {a.id: getattr(a, "floor", None) for a in areas}
    by_key: dict = defaultdict(lambda: defaultdict(list))
    for e in entities:
        for spec in actions:
            if not entity_supports(e, spec):
                continue
            caps.append(Capability(id=f"{spec.action}@{e.id}", action=spec.action, target=e.id, target_kind="entity",
                                   entities=[e.id], risk=entity_action_risk(e, spec)))
            if spec.groupable:
                by_key[(spec.action, group_key(e))][e.area].append(e)
    if groups:
        specs = {a.action: a for a in actions}
        for (action, key), per_area in by_key.items():
            spec = specs[action]
            all_members = []
            for area, members in per_area.items():
                all_members += members
                if area and len(members) >= 2:
                    caps.append(Capability(id=f"{action}@area:{area}:{key}", action=action,
                                           target=f"area:{area}:{key}", target_kind="area_group",
                                           entities=[m.id for m in members],
                                           risk=max_risk(*[entity_action_risk(m, spec) for m in members])))
            n_areas = len([a for a in per_area if a])
            # floors ("le luci del piano di sopra"): areas that share a floor, two of them at least with such devices
            floors: dict = defaultdict(list)
            for area, members in per_area.items():
                f = floor_of.get(area)
                if f:
                    floors[f].append((area, members))
            if len(floors) >= 2:
                for f, rooms in floors.items():
                    fm = [m for _, ms in rooms for m in ms]
                    if len(rooms) >= 2 and len(fm) >= 2:
                        caps.append(Capability(id=f"{action}@floor:{f}:{key}", action=action, target=f"floor:{f}:{key}",
                                               target_kind="floor_group", entities=[m.id for m in fm],
                                               risk=max_risk(*[entity_action_risk(m, spec) for m in fm])))
            # people have no room: "chi è a casa?" reads them all
            if len(all_members) >= 2 and (n_areas >= 2 or (n_areas == 0 and key == "person")):
                caps.append(Capability(id=f"{action}@all:{key}", action=action, target=f"all:{key}",
                                       target_kind="all_group", entities=[m.id for m in all_members],
                                       risk=max_risk(*[entity_action_risk(m, spec) for m in all_members])))
    return caps


# extra languages (core/lang/*.py): colours, modes and keywords
from .lang import apply_registry as _apply_lang  # noqa: E402

_apply_lang(globals())
