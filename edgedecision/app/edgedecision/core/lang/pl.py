"""Polski - runtime words (values, replies). See core/lang/__init__.py."""

LANG = "pl"
NUMBER_LANG = "pl"

COLORS = {"red": ["czerwony", "czerwone", "czerwoną", "czerwień"], "green": ["zielony", "zielone", "zieloną"],
          "blue": ["niebieski", "niebieskie", "niebieską"], "lightblue": ["jasnoniebieski", "błękitny", "błękitne"],
          "yellow": ["żółty", "żółte", "żółtą"], "orange": ["pomarańczowy", "pomarańczowe"],
          "purple": ["fioletowy", "fioletowe", "fiolet"], "pink": ["różowy", "różowe"], "white": ["biały", "białe", "białą"],
          "turquoise": ["turkusowy", "turkus"], "magenta": ["magenta", "fuksja"], "gold": ["złoty", "złote"]}
COLOR_TEMPS = {"warm": ["ciepłe", "ciepły", "ciepła biel", "ciepłe światło"], "neutral": ["neutralne", "dzienne", "naturalne"],
               "cool": ["zimne", "zimny", "chłodne", "zimna biel"]}
HVAC = {"heat": ["grzanie", "grzania", "ogrzewanie"], "cool": ["chłodzenie", "chłodzenia", "zimno"],
        "auto": ["automatyczny", "auto"], "dry": ["osuszanie", "osuszania"], "fan_only": ["wentylacja", "wentylacji", "nawiew"]}
DOMAIN_KEYWORDS = {"light": ["światło", "światła", "lampa", "lampę", "lampka", "led"], "switch": ["gniazdko", "włącznik"],
                   "cover": ["roleta", "rolety", "roletę", "żaluzja", "zasłona", "markiza"],
                   "climate": ["termostat", "ogrzewanie", "klimatyzacja", "temperatura", "stopni"],
                   "media_player": ["telewizor", "tv", "muzyka", "głośność", "głośnik", "piosenka"], "fan": ["wentylator"],
                   "lock": ["zamek", "drzwi"], "sensor": ["temperatura", "wilgotność", "czujnik"],
                   "binary_sensor": ["okno", "drzwi", "otwarte", "zamknięte"], "vacuum": ["odkurzacz", "robot"],
                   "scene": ["scena", "nastrój"], "weather": ["pogoda", "prognoza", "deszcz", "parasol"], "alarm_control_panel": ["alarm"]}
DAYS = {"today": ["dzisiaj", "dziś", "teraz"], "tomorrow": ["jutro"], "day_after": ["pojutrze"],
        "monday": ["poniedziałek"], "tuesday": ["wtorek"], "wednesday": ["środa", "środę"], "thursday": ["czwartek"],
        "friday": ["piątek"], "saturday": ["sobota", "sobotę"], "sunday": ["niedziela", "niedzielę"]}
ON = ["włącz", "włączyć", "zapal", "uruchom"]
OFF = ["wyłącz", "wyłączyć", "zgaś", "zatrzymaj"]
STATE = ["czy", "stan", "ile", "jaka"]

# core/specific.py: generic device nouns, words that never name a device, command verbs ("włącz telewizor")
KIND_NOUNS = {"light": "światło światła lampa lampę lampy lampka lampkę oświetlenie", "cover.shutter": "roleta rolety roletę żaluzja żaluzje",
              "cover.curtain": "zasłona zasłony zasłonę", "cover.awning": "markiza markizę", "cover.garage": "garaż bramę garażową",
              "cover.gate": "brama bramę", "climate.thermostat": "termostat ogrzewanie grzejnik kaloryfer",
              "climate.ac": "klimatyzacja klimatyzację klimatyzator", "media_player.tv": "telewizor tv telewizję",
              "media_player.speaker": "radio głośnik muzyka muzykę", "fan": "wentylator wiatrak", "lock": "zamek",
              "vacuum": "odkurzacz robot", "alarm": "alarm"}
FUNCTION_WORDS = """w we na do z ze o od po przy dla mój moja moje proszę dziękuję trochę połowy połowę pół więcej mniej
głośność jasność temperatura temperaturę stopni procent poziom prędkość max min"""
VERBS = """włącz włączyć wyłącz wyłączyć zapal zapalić zgaś zgasić otwórz otworzyć zamknij zamknąć podnieś podnieść
opuść opuścić zwiększ zwiększyć zmniejsz zmniejszyć ustaw ustawić uruchom uruchomić zatrzymaj aktywuj dezaktywuj
zablokuj odblokuj podgłośnij ścisz"""

PERCENT_UNITS = [("procent",), ("procenty",), ("procentach",)]
DEGREE_UNITS = [("stopni",), ("stopnie",), ("stopien",), ("stopnia",)]
HALF_SUFFIX = [("i", "pol"), ("przecinek", "piec")]
HALF_WORDS = ["polowy", "pol", "polowe"]
MAX_WORDS = ["maksimum", "maksa", "maksymalnie", "full"]
MIN_WORDS = ["minimum", "minimalnie"]
SMALL_STEP = ["troche", "troszke", "lekko"]
LARGE_STEP = ["duzo", "mocno"]
ABS_MARKERS = ["na", "do"]
REL_MARKERS = ["o"]
AMBIGUOUS_NUMBERS = ["raz", "sto"]

MESSAGES = {"ok": "Zrobione.", "ambiguous": "Chodzi ci o {opts}?", "low_confidence": "Nie jestem pewien: chodzi ci o {opts}?",
            "missing_param": "Na jaką wartość?", "invalid_param": "Ta wartość jest nieprawidłowa.",
            "confirm_high_risk": "Potwierdzasz operację: {opts}?", "cancelled": "Dobrze, anulowane.",
            "not_understood": "Nie zrozumiałem, możesz powtórzyć?",
            "unsupported": "Nie mogę tego zrobić z dostępnymi urządzeniami.",
            "unavailable": "Urządzenie jest niedostępne.", "noop": "Dobrze.", "escalate": "Chwileczkę...",
            "read": "{name}: {state}."}
OR = " czy "
AND = " i "
DOING = {"turn_on": "włączam:", "turn_off": "wyłączam:", "open": "otwieram:", "close": "zamykam:", "stop": "zatrzymuję:",
         "set": "ustawiam:", "set_color": "zmieniam kolor:", "volume_set": "ustawiam głośność:", "up": "zwiększam:",
         "down": "zmniejszam:", "volume_up": "podgłaśniam:", "volume_down": "ściszam:", "play_content": "włączam muzykę:", "play": "wznawiam:",
         "pause": "wstrzymuję:", "next_track": "następny utwór:", "previous_track": "poprzedni utwór:", "mute": "wyciszam:",
         "lock": "zamykam na klucz:", "unlock": "otwieram zamek:", "start": "uruchamiam:", "return_to_base": "odsyłam do bazy:",
         "activate": "włączam:", "arm": "uzbrajam:", "disarm": "rozbrajam:"}
DONE = {"turn_on": "włączyłem:", "turn_off": "wyłączyłem:", "open": "otworzyłem:", "close": "zamknąłem:",
        "stop": "zatrzymałem:", "set": "ustawiłem:", "set_color": "zmieniłem kolor:", "volume_set": "ustawiłem głośność:",
        "up": "zwiększyłem:", "down": "zmniejszyłem:", "volume_up": "podgłośniłem:", "volume_down": "ściszyłem:",
        "play_content": "włączyłem muzykę:", "play": "wznowiłem:", "pause": "wstrzymałem:", "next_track": "przełączyłem dalej:", "previous_track": "cofnąłem:",
        "mute": "wyciszyłem:", "lock": "zamknąłem na klucz:", "unlock": "otworzyłem zamek:", "start": "uruchomiłem:",
        "return_to_base": "odesłałem do bazy:", "activate": "włączyłem:", "arm": "uzbroiłem:", "disarm": "rozbroiłem:"}
GROUP = {"light": "światła", "cover.shutter": "rolety", "cover": "rolety", "switch": "gniazdka", "fan": "wentylatory",
         "media_player": "urządzenia", "climate": "termostaty", "_": "urządzenia"}
GROUP_ALL = {"light": "wszystkie światła", "cover.shutter": "wszystkie rolety", "cover": "wszystkie rolety",
             "switch": "wszystkie gniazdka", "fan": "wszystkie wentylatory", "media_player": "wszystkie urządzenia",
             "climate": "wszystkie termostaty", "_": "wszystkie urządzenia"}
IN = "w pokoju:"
AGO = {"now": "przed chwilą", "min": "{n} minut temu", "hour": "{n} godzin temu"}
NOTHING = "Jeszcze nic nie zrobiłem."
