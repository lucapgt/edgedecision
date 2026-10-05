"""Nederlands - runtime words (values, replies). See core/lang/__init__.py."""

LANG = "nl"
NUMBER_LANG = "nl"

COLORS = {"red": ["rood", "rode"], "green": ["groen", "groene"], "blue": ["blauw", "blauwe"], "lightblue": ["lichtblauw"],
          "yellow": ["geel", "gele"], "orange": ["oranje"], "purple": ["paars", "paarse", "violet"], "pink": ["roze"],
          "white": ["wit", "witte"], "turquoise": ["turquoise", "turkoois"], "magenta": ["magenta", "fuchsia"],
          "gold": ["goud", "gouden"]}
COLOR_TEMPS = {"warm": ["warm", "warmwit", "warm licht"], "neutral": ["neutraal", "daglicht"],
               "cool": ["koud", "koel", "koudwit", "koud licht"]}
HVAC = {"heat": ["verwarmen", "verwarming", "warm"], "cool": ["koelen", "koeling", "koud"], "auto": ["automatisch", "auto"],
        "dry": ["ontvochtigen", "droog"], "fan_only": ["ventileren", "alleen ventilator", "ventilatie"]}
DOMAIN_KEYWORDS = {"light": ["licht", "lichten", "lamp", "lampen", "led"], "switch": ["stekker", "stopcontact", "schakelaar"],
                   "cover": ["rolluik", "rolluiken", "jaloezie", "gordijn", "gordijnen", "zonnescherm"],
                   "climate": ["thermostaat", "verwarming", "airco", "temperatuur", "graden"],
                   "media_player": ["tv", "televisie", "muziek", "volume", "speaker", "nummer"], "fan": ["ventilator"],
                   "lock": ["slot", "deur"], "sensor": ["temperatuur", "luchtvochtigheid", "sensor"],
                   "binary_sensor": ["raam", "deur", "open", "dicht"], "vacuum": ["stofzuiger", "robot"],
                   "scene": ["scène", "sfeer"], "weather": ["weer", "weersverwachting", "regen", "paraplu"], "alarm_control_panel": ["alarm"]}
DAYS = {"today": ["vandaag", "nu"], "tomorrow": ["morgen"], "day_after": ["overmorgen"],
        "monday": ["maandag"], "tuesday": ["dinsdag"], "wednesday": ["woensdag"], "thursday": ["donderdag"],
        "friday": ["vrijdag"], "saturday": ["zaterdag"], "sunday": ["zondag"]}
ON = ["aan", "aanzetten", "inschakelen"]
OFF = ["uit", "uitzetten", "uitschakelen"]
STATE = ["staat", "status", "hoe", "welke"]

# core/specific.py: generic device nouns, words that never name a device, command verbs ("zet de tv aan")
KIND_NOUNS = {"light": "licht lichten lamp lampen verlichting", "cover.shutter": "rolluik rolluiken luik luiken jaloezie",
              "cover.curtain": "gordijn gordijnen", "cover.awning": "zonnescherm luifel", "cover.garage": "garage garagedeur",
              "cover.gate": "poort hek", "climate.thermostat": "thermostaat verwarming radiator",
              "climate.ac": "airco airconditioning", "media_player.tv": "tv televisie teevee",
              "media_player.speaker": "radio speaker muziek luidspreker", "fan": "ventilator", "lock": "slot",
              "vacuum": "stofzuiger robot", "alarm": "alarm"}
FUNCTION_WORDS = """de het een van in op aan naar voor met mijn mij me alsjeblieft alstublieft graag dank bedankt beetje
half helft meer minder volume helderheid temperatuur graden procent stand max min"""
VERBS = """zet zetten doe doen aan uit schakel schakelen open openen doe dicht sluit sluiten draai draaien verhoog verhogen
verlaag verlagen dim dimmen start starten stop stoppen activeer activeren deactiveer vergrendel ontgrendel omhoog omlaag
harder zachter"""

PERCENT_UNITS = [("procent",)]
DEGREE_UNITS = [("graden",), ("graad",)]
HALF_SUFFIX = [("en", "een", "half"), ("komma", "vijf"), ("en", "een", "halve")]
HALF_WORDS = ["half", "helft"]
MAX_WORDS = ["maximaal", "maximum", "helemaal", "vol"]
MIN_WORDS = ["minimaal", "minimum"]
SMALL_STEP = ["beetje", "iets", "tikje"]
LARGE_STEP = ["veel", "flink"]
ABS_MARKERS = ["op", "naar"]
REL_MARKERS = ["met"]
AMBIGUOUS_NUMBERS = ["een", "één"]

MESSAGES = {"ok": "Gedaan.", "ambiguous": "Bedoel je {opts}?", "low_confidence": "Ik weet het niet zeker: bedoel je {opts}?",
            "missing_param": "Op welke waarde?", "invalid_param": "Die waarde is niet geldig.",
            "confirm_high_risk": "Bevestig je de actie op {opts}?", "cancelled": "Oké, geannuleerd.",
            "not_understood": "Dat heb ik niet begrepen, kun je het herhalen?",
            "unsupported": "Dat kan ik niet met de beschikbare apparaten.",
            "unavailable": "Het apparaat is niet bereikbaar.", "noop": "Oké.", "escalate": "Even denken...",
            "read": "{name}: {state}."}
OR = " of "
AND = " en "
DOING = {"turn_on": "ik zet aan:", "turn_off": "ik zet uit:", "open": "ik open", "close": "ik sluit", "stop": "ik stop",
         "set": "ik stel in:", "set_color": "ik verander de kleur van", "volume_set": "ik stel het volume in van",
         "up": "ik verhoog", "down": "ik verlaag", "volume_up": "harder:", "volume_down": "zachter:", "play_content": "ik speel muziek op", "play": "ik hervat",
         "pause": "ik pauzeer", "next_track": "volgende op", "previous_track": "vorige op", "mute": "ik demp",
         "lock": "ik vergrendel", "unlock": "ik ontgrendel", "start": "ik start", "return_to_base": "terug naar de basis:",
         "activate": "ik activeer", "arm": "ik schakel in:", "disarm": "ik schakel uit:"}
DONE = {"turn_on": "aangezet:", "turn_off": "uitgezet:", "open": "geopend:", "close": "gesloten:", "stop": "gestopt:",
        "set": "ingesteld:", "set_color": "kleur veranderd:", "volume_set": "volume ingesteld:", "up": "verhoogd:",
        "down": "verlaagd:", "volume_up": "harder gezet:", "volume_down": "zachter gezet:", "play_content": "muziek gestart op", "play": "hervat:",
        "pause": "gepauzeerd:", "next_track": "volgende gekozen:", "previous_track": "vorige gekozen:", "mute": "gedempt:",
        "lock": "vergrendeld:", "unlock": "ontgrendeld:", "start": "gestart:", "return_to_base": "naar de basis gestuurd:",
        "activate": "geactiveerd:", "arm": "ingeschakeld:", "disarm": "uitgeschakeld:"}
GROUP = {"light": "de lampen", "cover.shutter": "de rolluiken", "cover": "de rolluiken", "switch": "de stekkers",
         "fan": "de ventilatoren", "media_player": "de apparaten", "climate": "de thermostaten", "_": "de apparaten"}
GROUP_ALL = {"light": "alle lampen", "cover.shutter": "alle rolluiken", "cover": "alle rolluiken", "switch": "alle stekkers",
             "fan": "alle ventilatoren", "media_player": "alle apparaten", "climate": "alle thermostaten", "_": "alle apparaten"}
IN = "in"
AGO = {"now": "zojuist", "min": "{n} minuten geleden", "hour": "{n} uur geleden"}
NOTHING = "Ik heb nog niets gedaan."
