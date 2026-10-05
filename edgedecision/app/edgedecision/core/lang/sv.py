"""Svenska - runtime words (values, replies). See core/lang/__init__.py."""

LANG = "sv"
NUMBER_LANG = "sv"

COLORS = {"red": ["röd", "rött", "röda"], "green": ["grön", "grönt", "gröna"], "blue": ["blå", "blått", "blåa"],
          "lightblue": ["ljusblå", "ljusblått"], "yellow": ["gul", "gult", "gula"], "orange": ["orange"],
          "purple": ["lila", "violett"], "pink": ["rosa"], "white": ["vit", "vitt", "vita"], "turquoise": ["turkos"],
          "magenta": ["magenta", "cerise"], "gold": ["guld", "gyllene"]}
COLOR_TEMPS = {"warm": ["varm", "varmt", "varmvit", "varmt ljus"], "neutral": ["neutral", "neutralt", "dagsljus"],
               "cool": ["kall", "kallt", "kallvit", "kallt ljus"]}
HVAC = {"heat": ["värme", "värmeläge", "värma"], "cool": ["kyla", "kylläge", "kyl"], "auto": ["automatisk", "auto"],
        "dry": ["avfuktning", "avfukta"], "fan_only": ["fläkt", "bara fläkt", "ventilation"]}
DOMAIN_KEYWORDS = {"light": ["ljus", "lampa", "lampan", "lampor", "belysning", "led"], "switch": ["uttag", "kontakt", "strömbrytare"],
                   "cover": ["rullgardin", "persienn", "gardin", "gardiner", "markis"],
                   "climate": ["termostat", "värme", "ac", "värmepump", "temperatur", "grader"],
                   "media_player": ["tv", "musik", "volym", "högtalare", "låt"], "fan": ["fläkt"],
                   "lock": ["lås", "dörr"], "sensor": ["temperatur", "luftfuktighet", "sensor"],
                   "binary_sensor": ["fönster", "dörr", "öppen", "stängd"], "vacuum": ["dammsugare", "robot"],
                   "scene": ["scen", "stämning"], "weather": ["väder", "vädret", "prognos", "regn", "paraply"], "alarm_control_panel": ["larm"]}
DAYS = {"today": ["idag", "i dag", "nu"], "tomorrow": ["imorgon", "i morgon"],
        "day_after": ["i övermorgon", "övermorgon"], "monday": ["måndag"], "tuesday": ["tisdag"], "wednesday": ["onsdag"],
        "thursday": ["torsdag"], "friday": ["fredag"], "saturday": ["lördag"], "sunday": ["söndag"]}
ON = ["tänd", "sätt på", "slå på", "på"]
OFF = ["släck", "stäng av", "slå av", "av"]
STATE = ["är", "status", "hur", "vilken"]

# core/specific.py: generic device nouns, words that never name a device, command verbs ("sätt på tv:n")
KIND_NOUNS = {"light": "ljus ljuset lampa lampan lampor lamporna belysning belysningen", "cover.shutter": "rullgardin rullgardinen persienn persiennen",
              "cover.curtain": "gardin gardinen gardiner", "cover.awning": "markis markisen", "cover.garage": "garage garageporten",
              "cover.gate": "grind grinden", "climate.thermostat": "termostat termostaten värme värmen element",
              "climate.ac": "ac luftkonditionering", "media_player.tv": "tv teven tvn",
              "media_player.speaker": "radio radion högtalare högtalaren musik musiken", "fan": "fläkt fläkten",
              "lock": "lås låset", "vacuum": "dammsugare dammsugaren robot", "alarm": "larm larmet"}
FUNCTION_WORDS = """en ett den det de i på till för med av min mitt mina tack snälla lite hälften halvt mer mindre volym
volymen ljusstyrka ljusstyrkan temperatur temperaturen grader procent nivå max min"""
VERBS = """tänd tända släck släcka sätt sätta slå på av öppna stäng stänga höj höja sänk sänka starta stoppa stopp
aktivera avaktivera lås lås upp dra ner upp skruva"""

PERCENT_UNITS = [("procent",)]
DEGREE_UNITS = [("grader",), ("grad",)]
HALF_SUFFIX = [("och", "en", "halv"), ("komma", "fem")]
HALF_WORDS = ["halvt", "halften", "halvvags"]
MAX_WORDS = ["max", "maximum", "fullt"]
MIN_WORDS = ["minimum", "min"]
SMALL_STEP = ["lite", "aning", "grann"]
LARGE_STEP = ["mycket"]
ABS_MARKERS = ["till", "pa"]
REL_MARKERS = ["med"]
AMBIGUOUS_NUMBERS = ["en", "ett", "sex"]

MESSAGES = {"ok": "Klart.", "ambiguous": "Menar du {opts}?", "low_confidence": "Jag är inte säker: menar du {opts}?",
            "missing_param": "Till vilket värde?", "invalid_param": "Det värdet är inte giltigt.",
            "confirm_high_risk": "Bekräftar du åtgärden på {opts}?", "cancelled": "Okej, avbrutet.",
            "not_understood": "Jag förstod inte, kan du upprepa?",
            "unsupported": "Det kan jag inte göra med de enheter som finns.",
            "unavailable": "Enheten går inte att nå.", "noop": "Okej.", "escalate": "Låt mig tänka...",
            "read": "{name}: {state}."}
OR = " eller "
AND = " och "
DOING = {"turn_on": "jag sätter på", "turn_off": "jag stänger av", "open": "jag öppnar", "close": "jag stänger",
         "stop": "jag stoppar", "set": "jag ställer in", "set_color": "jag ändrar färgen på", "volume_set": "jag ställer in volymen på",
         "up": "jag höjer", "down": "jag sänker", "volume_up": "jag höjer volymen på", "volume_down": "jag sänker volymen på",
         "play_content": "jag spelar musik på", "play": "jag fortsätter", "pause": "jag pausar", "next_track": "nästa på", "previous_track": "föregående på",
         "mute": "jag tystar", "lock": "jag låser", "unlock": "jag låser upp", "start": "jag startar",
         "return_to_base": "jag skickar hem", "activate": "jag aktiverar", "arm": "jag larmar på", "disarm": "jag larmar av"}
DONE = {"turn_on": "jag satte på", "turn_off": "jag stängde av", "open": "jag öppnade", "close": "jag stängde",
        "stop": "jag stoppade", "set": "jag ställde in", "set_color": "jag ändrade färgen på",
        "volume_set": "jag ställde in volymen på", "up": "jag höjde", "down": "jag sänkte", "volume_up": "jag höjde volymen på",
        "volume_down": "jag sänkte volymen på", "play_content": "jag spelade musik på", "play": "jag fortsatte", "pause": "jag pausade", "next_track": "nästa på",
        "previous_track": "föregående på", "mute": "jag tystade", "lock": "jag låste", "unlock": "jag låste upp",
        "start": "jag startade", "return_to_base": "jag skickade hem", "activate": "jag aktiverade", "arm": "jag larmade på",
        "disarm": "jag larmade av"}
GROUP = {"light": "lamporna", "cover.shutter": "rullgardinerna", "cover": "rullgardinerna", "switch": "uttagen",
         "fan": "fläktarna", "media_player": "enheterna", "climate": "termostaterna", "_": "enheterna"}
GROUP_ALL = {"light": "alla lampor", "cover.shutter": "alla rullgardiner", "cover": "alla rullgardiner",
             "switch": "alla uttag", "fan": "alla fläktar", "media_player": "alla enheter", "climate": "alla termostater",
             "_": "alla enheter"}
IN = "i"
AGO = {"now": "nyss", "min": "för {n} minuter sedan", "hour": "för {n} timmar sedan"}
NOTHING = "Jag har inte gjort något än."
HISTORY_FMT = "{said} ({ago})"
