"""Deutsch - runtime words (values, replies). See core/lang/__init__.py."""

LANG = "de"
NUMBER_LANG = "de"

COLORS = {"red": ["rot", "rote", "rotes"], "green": ["grün", "grüne", "grünes"], "blue": ["blau", "blaue", "blaues"],
          "lightblue": ["hellblau", "himmelblau"], "yellow": ["gelb", "gelbe"], "orange": ["orange"],
          "purple": ["lila", "violett"], "pink": ["rosa", "pink"], "white": ["weiß", "weiss", "weiße"],
          "turquoise": ["türkis"], "magenta": ["magenta", "fuchsia"], "gold": ["gold", "golden", "goldene"]}
COLOR_TEMPS = {"warm": ["warm", "warmweiß", "warmes licht"], "neutral": ["neutral", "neutralweiß", "tageslicht"],
               "cool": ["kalt", "kaltweiß", "kühl", "kaltes licht"]}
HVAC = {"heat": ["heizen", "heizung", "heizmodus", "wärme"], "cool": ["kühlen", "kühlung", "kühlmodus", "kalt"],
        "auto": ["automatik", "auto", "automatisch"], "dry": ["entfeuchten", "entfeuchtung", "trocken"],
        "fan_only": ["lüften", "nur lüfter", "ventilator"]}
DOMAIN_KEYWORDS = {"light": ["licht", "lichter", "lampe", "lampen", "leuchte", "led"], "switch": ["steckdose", "schalter"],
                   "cover": ["rollladen", "rollläden", "jalousie", "rollo", "vorhang", "markise"],
                   "climate": ["thermostat", "heizung", "klima", "klimaanlage", "temperatur", "grad"],
                   "media_player": ["fernseher", "tv", "musik", "lautstärke", "lautsprecher", "lied"], "fan": ["ventilator", "lüfter"],
                   "lock": ["schloss", "tür", "abschließen"], "sensor": ["temperatur", "luftfeuchtigkeit", "sensor"],
                   "binary_sensor": ["fenster", "tür", "offen", "zu"], "vacuum": ["staubsauger", "saugroboter", "roboter"],
                   "scene": ["szene", "stimmung"], "weather": ["wetter", "vorhersage", "regen", "regenschirm"], "alarm_control_panel": ["alarm", "alarmanlage"]}
DAYS = {"today": ["heute", "jetzt"], "tomorrow": ["morgen"], "day_after": ["übermorgen"],
        "monday": ["montag"], "tuesday": ["dienstag"], "wednesday": ["mittwoch"], "thursday": ["donnerstag"],
        "friday": ["freitag"], "saturday": ["samstag", "sonnabend"], "sunday": ["sonntag"]}
ON = ["ein", "an", "einschalten", "anmachen", "starte"]
OFF = ["aus", "ausschalten", "ausmachen", "stopp"]
STATE = ["ist", "status", "wie", "welche"]

# core/specific.py: generic device nouns, words that never name a device, command verbs ("mach den Fernseher an")
KIND_NOUNS = {"light": "licht lichter lampe lampen leuchte leuchten beleuchtung", "cover.shutter": "rollladen rolladen rollo jalousie",
              "cover.curtain": "vorhang vorhänge gardine", "cover.awning": "markise", "cover.garage": "garage garagentor",
              "cover.gate": "tor hoftor", "climate.thermostat": "thermostat heizung heizkörper",
              "climate.ac": "klima klimaanlage", "media_player.tv": "fernseher tv fernsehen glotze",
              "media_player.speaker": "radio lautsprecher musik box", "fan": "ventilator lüfter", "lock": "schloss",
              "vacuum": "staubsauger saugroboter roboter", "alarm": "alarm alarmanlage"}
FUNCTION_WORDS = """der die das den dem des ein eine einen einem einer im in am an auf zu zum zur für mit mein meine
meinen bitte danke mal etwas bisschen halb hälfte mehr weniger lautstärke helligkeit temperatur grad prozent stufe max min"""
VERBS = """mach mache machen schalte schalten schalt ein aus an öffne öffnen schließ schließe schließen stell stelle
stellen dreh drehe drehen fahr fahre fahren erhöhe erhöhen verringere senke senken starte starten stopp stoppe
aktiviere aktivieren deaktiviere deaktivieren sperre entsperre hoch runter lauter leiser heller dunkler"""

PERCENT_UNITS = [("prozent",)]
DEGREE_UNITS = [("grad",)]
HALF_SUFFIX = [("komma", "funf"), ("und", "halb"), ("einhalb",)]
HALF_WORDS = ["halb", "halfte"]
MAX_WORDS = ["maximum", "maximal", "ganz", "voll"]
MIN_WORDS = ["minimum", "minimal"]
SMALL_STEP = ["bisschen", "etwas", "wenig", "leicht"]
LARGE_STEP = ["viel", "deutlich", "stark"]
ABS_MARKERS = ["auf", "bis"]
REL_MARKERS = ["um"]
AMBIGUOUS_NUMBERS = ["ein", "eine", "einen", "eins", "elf"]

MESSAGES = {"ok": "Erledigt.", "ambiguous": "Meinst du {opts}?", "low_confidence": "Ich bin nicht sicher: meinst du {opts}?",
            "missing_param": "Auf welchen Wert?", "invalid_param": "Dieser Wert ist nicht gültig.",
            "confirm_high_risk": "Bestätigst du die Aktion für {opts}?", "cancelled": "Okay, abgebrochen.",
            "not_understood": "Das habe ich nicht verstanden, kannst du es wiederholen?",
            "unsupported": "Das kann ich mit den vorhandenen Geräten nicht machen.",
            "unavailable": "Das Gerät ist nicht erreichbar.", "noop": "Okay.", "escalate": "Einen Moment...",
            "read": "{name}: {state}."}
OR = " oder "
AND = " und "
DOING = {"turn_on": "ich schalte ein:", "turn_off": "ich schalte aus:", "open": "ich öffne", "close": "ich schließe",
         "stop": "ich stoppe", "set": "ich stelle ein:", "set_color": "ich ändere die Farbe:", "volume_set": "ich stelle die Lautstärke ein:",
         "up": "ich erhöhe", "down": "ich senke", "volume_up": "lauter:", "volume_down": "leiser:", "play_content": "Musik auf:", "play": "ich setze fort:",
         "pause": "ich pausiere", "next_track": "weiter auf", "previous_track": "zurück auf", "mute": "ich schalte stumm:",
         "lock": "ich schließe ab:", "unlock": "ich schließe auf:", "start": "ich starte", "return_to_base": "zurück zur Station:",
         "activate": "ich aktiviere", "arm": "ich schalte scharf:", "disarm": "ich schalte unscharf:"}
DONE = {"turn_on": "eingeschaltet:", "turn_off": "ausgeschaltet:", "open": "geöffnet:", "close": "geschlossen:",
        "stop": "gestoppt:", "set": "eingestellt:", "set_color": "Farbe geändert:", "volume_set": "Lautstärke eingestellt:",
        "up": "erhöht:", "down": "gesenkt:", "volume_up": "lauter gestellt:", "volume_down": "leiser gestellt:",
        "play_content": "Musik gestartet auf:", "play": "fortgesetzt:", "pause": "pausiert:", "next_track": "weitergeschaltet:", "previous_track": "zurückgeschaltet:",
        "mute": "stummgeschaltet:", "lock": "abgeschlossen:", "unlock": "aufgeschlossen:", "start": "gestartet:",
        "return_to_base": "zur Station geschickt:", "activate": "aktiviert:", "arm": "scharf geschaltet:",
        "disarm": "unscharf geschaltet:"}
GROUP = {"light": "die Lichter", "cover.shutter": "die Rollläden", "cover": "die Rollläden", "switch": "die Steckdosen",
         "fan": "die Ventilatoren", "media_player": "die Geräte", "climate": "die Thermostate", "_": "die Geräte"}
GROUP_ALL = {"light": "alle Lichter", "cover.shutter": "alle Rollläden", "cover": "alle Rollläden", "switch": "alle Steckdosen",
             "fan": "alle Ventilatoren", "media_player": "alle Geräte", "climate": "alle Thermostate", "_": "alle Geräte"}
IN = "in"
AGO = {"now": "gerade eben", "min": "vor {n} Minuten", "hour": "vor {n} Stunden"}
NOTHING = "Ich habe noch nichts gemacht."
