"""Français - runtime words: values (colours, modes, units), spoken replies. Small on purpose: understanding the
sentence is the model's job; this file only turns values into numbers and decisions into speech."""

LANG = "fr"

COLORS = {"red": ["rouge", "rouges"], "green": ["vert", "verte", "verts"], "blue": ["bleu", "bleue", "bleus"],
          "lightblue": ["bleu clair", "bleu ciel", "azur"], "yellow": ["jaune", "jaunes"], "orange": ["orange"],
          "purple": ["violet", "violette", "mauve"], "pink": ["rose", "roses"], "white": ["blanc", "blanche"],
          "turquoise": ["turquoise"], "magenta": ["magenta", "fuchsia"], "gold": ["doré", "dorée", "or"]}
COLOR_TEMPS = {"warm": ["chaude", "chaud", "blanc chaud", "lumière chaude"],
               "neutral": ["neutre", "naturelle", "blanc neutre", "lumière du jour"],
               "cool": ["froide", "froid", "blanc froid", "lumière froide"]}
HVAC = {"heat": ["chauffage", "mode chauffage", "chaud", "chauffer"], "cool": ["froid", "climatisation", "refroidir", "mode froid"],
        "auto": ["automatique", "auto", "mode automatique"], "dry": ["déshumidification", "déshumidifier", "sec"],
        "fan_only": ["ventilation", "ventilation seule", "mode ventilateur"]}
DOMAIN_KEYWORDS = {"light": ["lumière", "lumières", "lampe", "lustre", "spots", "led"], "switch": ["prise", "interrupteur"],
                   "cover": ["volet", "volets", "store", "stores", "rideau", "rideaux"],
                   "climate": ["thermostat", "chauffage", "clim", "climatisation", "température", "degrés"],
                   "media_player": ["télé", "tv", "musique", "volume", "enceinte", "chanson"], "fan": ["ventilateur"],
                   "lock": ["serrure", "porte", "clé"], "sensor": ["température", "humidité", "capteur"],
                   "binary_sensor": ["fenêtre", "porte", "ouverte", "fermée"], "vacuum": ["aspirateur", "robot", "ménage"],
                   "scene": ["scène", "ambiance"], "weather": ["météo", "temps", "prévisions", "pluie", "parapluie"], "alarm_control_panel": ["alarme"]}
DAYS = {"today": ["aujourd'hui", "maintenant"], "tomorrow": ["demain"], "day_after": ["après-demain"],
        "monday": ["lundi"], "tuesday": ["mardi"], "wednesday": ["mercredi"], "thursday": ["jeudi"],
        "friday": ["vendredi"], "saturday": ["samedi"], "sunday": ["dimanche"]}
ON = ["allume", "allumer", "allumée", "active", "mets"]
OFF = ["éteins", "éteindre", "éteinte", "désactive", "coupe"]
STATE = ["est", "état", "combien", "quelle"]

# core/specific.py: generic device nouns, words that never name a device, command verbs ("allume la télé")
KIND_NOUNS = {"light": "lumière lumières lampe lampes lampadaire éclairage", "cover.shutter": "volet volets persienne persiennes",
              "cover.curtain": "rideau rideaux", "cover.awning": "store banne", "cover.garage": "garage", "cover.gate": "portail",
              "climate.thermostat": "thermostat chauffage radiateur radiateurs", "climate.ac": "clim climatisation climatiseur",
              "media_player.tv": "télé tv télévision téléviseur", "media_player.speaker": "radio enceinte musique chaîne",
              "fan": "ventilateur ventilateurs", "lock": "serrure", "vacuum": "aspirateur robot", "alarm": "alarme"}
FUNCTION_WORDS = """le la les l un une des du de d au aux en dans sur à a pour avec ce cet cette ces mon ma mes ton ta
s il te plaît plait merci un peu moitié plus moins volume luminosité température degrés pour cent niveau vitesse max min"""
VERBS = """allume allumer éteins éteindre éteint mets mettre met ouvre ouvrir ferme fermer monte monter baisse baisser
augmente augmenter diminue diminuer règle régler active activer désactive désactiver lance lancer arrête arrêter
coupe couper démarre démarrer verrouille déverrouille remonte descends descendre"""

PERCENT_UNITS = [("pour", "cent"), ("pourcent",)]
DEGREE_UNITS = [("degres",), ("degre",)]
HALF_SUFFIX = [("et", "demi"), ("et", "demie"), ("virgule", "cinq")]
HALF_WORDS = ["moitie", "mi"]
MAX_WORDS = ["maximum", "fond"]
MIN_WORDS = ["minimum"]
SMALL_STEP = ["peu", "legerement"]
LARGE_STEP = ["beaucoup"]
ABS_MARKERS = ["a", "au", "sur", "jusqu"]
REL_MARKERS = ["de", "du"]

MESSAGES = {"ok": "C'est fait.", "ambiguous": "Tu veux dire {opts} ?", "low_confidence": "Je ne suis pas sûr : tu veux dire {opts} ?",
            "missing_param": "À quelle valeur ?", "invalid_param": "Cette valeur n'est pas valide.",
            "confirm_high_risk": "Tu confirmes l'action sur {opts} ?", "cancelled": "D'accord, j'annule.",
            "not_understood": "Je n'ai pas compris, tu peux répéter ?",
            "unsupported": "Je ne peux pas le faire avec les appareils disponibles.",
            "unavailable": "L'appareil n'est pas joignable.", "noop": "D'accord.", "escalate": "Je réfléchis...",
            "read": "{name} : {state}."}
OR = " ou "
AND = " et "
DOING = {"turn_on": "j'allume", "turn_off": "j'éteins", "open": "j'ouvre", "close": "je ferme", "stop": "j'arrête",
         "set": "je règle", "set_color": "je change la couleur de", "volume_set": "je règle le volume de",
         "up": "j'augmente", "down": "je baisse", "volume_up": "je monte le son de", "volume_down": "je baisse le son de",
         "play_content": "je lance la musique sur", "play": "je relance", "pause": "je mets en pause", "next_track": "je passe au suivant sur",
         "previous_track": "je reviens en arrière sur", "mute": "je coupe le son de", "lock": "je verrouille",
         "unlock": "je déverrouille", "start": "je lance", "return_to_base": "je renvoie à la base",
         "activate": "j'active", "arm": "j'active", "disarm": "je désactive"}
DONE = {"turn_on": "j'ai allumé", "turn_off": "j'ai éteint", "open": "j'ai ouvert", "close": "j'ai fermé",
        "stop": "j'ai arrêté", "set": "j'ai réglé", "set_color": "j'ai changé la couleur de",
        "volume_set": "j'ai réglé le volume de", "up": "j'ai augmenté", "down": "j'ai baissé",
        "volume_up": "j'ai monté le son de", "volume_down": "j'ai baissé le son de", "play_content": "j'ai lancé la musique sur", "play": "j'ai relancé",
        "pause": "j'ai mis en pause", "next_track": "je suis passé au suivant sur",
        "previous_track": "je suis revenu en arrière sur", "mute": "j'ai coupé le son de", "lock": "j'ai verrouillé",
        "unlock": "j'ai déverrouillé", "start": "j'ai lancé", "return_to_base": "j'ai renvoyé à la base",
        "activate": "j'ai activé", "arm": "j'ai activé", "disarm": "j'ai désactivé"}
GROUP = {"light": "les lumières", "cover.shutter": "les volets", "cover": "les volets", "switch": "les prises",
         "fan": "les ventilateurs", "media_player": "les appareils", "climate": "les thermostats", "_": "les appareils"}
GROUP_ALL = {"light": "toutes les lumières", "cover.shutter": "tous les volets", "cover": "tous les volets",
             "switch": "toutes les prises", "fan": "tous les ventilateurs", "media_player": "tous les appareils",
             "climate": "tous les thermostats", "_": "tous les appareils"}
AMBIGUOUS_NUMBERS = ["un", "une", "neuf"]   # also articles / ordinary words: a number only when a unit follows
NUMBER_LANG = "fr"                          # num2words language code
IN = "dans"
AGO = {"now": "à l'instant", "min": "il y a {n} minutes", "hour": "il y a {n} heures"}
NOTHING = "Je n'ai encore rien fait."
