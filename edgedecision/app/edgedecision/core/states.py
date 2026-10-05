"""Spoken device states in the 9 languages: "Tapparella cucina: chiusa", "In Salone: Lampada ad arco accesa e
Faretti salone spenti", "Luci accese: Lampada ad arco e Luce taverna".

The model only decides WHICH state is asked for; this module turns Home Assistant states ("on", "closed", "locked",
"playing", hvac modes, brightness...) into words. Adjectives agree with the device name where the language needs it
(Italian, Spanish, Portuguese, French, Polish), with a simple rule on the first word of the name ("Lampada" -> f,
"Faretti" -> m. pl.); the other languages use forms that never change.
"""
from __future__ import annotations

from typing import Optional

from .text import normalize

LANGS = ["it", "en", "es", "fr", "de", "nl", "pt", "pl", "sv"]

# state -> forms: one string (invariable) or {"m", "f", "mp", "fp", "n"} (Polish neuter "n")
W = {
    "it": {"on": dict(m="acceso", f="accesa", mp="accesi", fp="accese"),
           "off": dict(m="spento", f="spenta", mp="spenti", fp="spente"),
           "open": dict(m="aperto", f="aperta", mp="aperti", fp="aperte"),
           "closed": dict(m="chiuso", f="chiusa", mp="chiusi", fp="chiuse"),
           "locked": dict(m="chiuso a chiave", f="chiusa a chiave", mp="chiusi a chiave", fp="chiuse a chiave"),
           "unlocked": dict(m="aperto", f="aperta", mp="aperti", fp="aperte"),
           "opening": "in apertura", "closing": "in chiusura", "playing": "in riproduzione", "paused": "in pausa",
           "idle": "in attesa", "unavailable": "non raggiungibile",
           "brightness": "luminosità {n}%", "position": "posizione {n}%", "target": "impostata a {n} gradi",
           "current": "ora ci sono {n} gradi", "volume": "volume {n}%", "title": "in riproduzione {t}",
           "speed": "velocità {n}%",
           "hvac": {"heat": "in riscaldamento", "cool": "in raffrescamento", "auto": "in automatico",
                    "heat_cool": "in automatico", "dry": "in deumidificazione", "fan_only": "in ventilazione"}},
    "en": {"on": "on", "off": "off", "open": "open", "closed": "closed", "locked": "locked", "unlocked": "unlocked",
           "opening": "opening", "closing": "closing", "playing": "playing", "paused": "paused", "idle": "idle",
           "unavailable": "unavailable", "brightness": "brightness {n}%", "position": "position {n}%",
           "target": "set to {n} degrees", "current": "currently {n} degrees", "volume": "volume {n}%",
           "title": "playing {t}", "speed": "speed {n}%",
           "hvac": {"heat": "heating", "cool": "cooling", "auto": "on auto", "heat_cool": "on auto", "dry": "drying",
                    "fan_only": "on fan only"}},
    "es": {"on": dict(m="encendido", f="encendida", mp="encendidos", fp="encendidas"),
           "off": dict(m="apagado", f="apagada", mp="apagados", fp="apagadas"),
           "open": dict(m="abierto", f="abierta", mp="abiertos", fp="abiertas"),
           "closed": dict(m="cerrado", f="cerrada", mp="cerrados", fp="cerradas"),
           "locked": dict(m="cerrado con llave", f="cerrada con llave", mp="cerrados con llave", fp="cerradas con llave"),
           "unlocked": dict(m="sin llave", f="sin llave", mp="sin llave", fp="sin llave"),
           "opening": "abriéndose", "closing": "cerrándose", "playing": "reproduciendo", "paused": "en pausa",
           "idle": "en espera", "unavailable": "no disponible",
           "brightness": "brillo {n}%", "position": "posición {n}%", "target": "fijada a {n} grados",
           "current": "ahora hay {n} grados", "volume": "volumen {n}%", "title": "reproduciendo {t}",
           "speed": "velocidad {n}%",
           "hvac": {"heat": "calentando", "cool": "enfriando", "auto": "en automático", "heat_cool": "en automático",
                    "dry": "deshumidificando", "fan_only": "en ventilación"}},
    "fr": {"on": dict(m="allumé", f="allumée", mp="allumés", fp="allumées"),
           "off": dict(m="éteint", f="éteinte", mp="éteints", fp="éteintes"),
           "open": dict(m="ouvert", f="ouverte", mp="ouverts", fp="ouvertes"),
           "closed": dict(m="fermé", f="fermée", mp="fermés", fp="fermées"),
           "locked": dict(m="verrouillé", f="verrouillée", mp="verrouillés", fp="verrouillées"),
           "unlocked": dict(m="déverrouillé", f="déverrouillée", mp="déverrouillés", fp="déverrouillées"),
           "opening": "en ouverture", "closing": "en fermeture", "playing": "en lecture", "paused": "en pause",
           "idle": "en veille", "unavailable": "injoignable",
           "brightness": "luminosité {n} %", "position": "position {n} %", "target": "réglé sur {n} degrés",
           "current": "il fait {n} degrés", "volume": "volume {n} %", "title": "lecture de {t}",
           "speed": "vitesse {n} %",
           "hvac": {"heat": "en chauffage", "cool": "en climatisation", "auto": "en automatique",
                    "heat_cool": "en automatique", "dry": "en déshumidification", "fan_only": "en ventilation"}},
    "de": {"on": "an", "off": "aus", "open": "offen", "closed": "geschlossen", "locked": "abgeschlossen",
           "unlocked": "nicht abgeschlossen", "opening": "öffnet", "closing": "schließt", "playing": "spielt",
           "paused": "pausiert", "idle": "bereit", "unavailable": "nicht erreichbar",
           "brightness": "Helligkeit {n} %", "position": "Position {n} %", "target": "eingestellt auf {n} Grad",
           "current": "aktuell {n} Grad", "volume": "Lautstärke {n} %", "title": "spielt {t}",
           "speed": "Geschwindigkeit {n} %",
           "hvac": {"heat": "heizt", "cool": "kühlt", "auto": "auf Automatik", "heat_cool": "auf Automatik",
                    "dry": "entfeuchtet", "fan_only": "lüftet"}},
    "nl": {"on": "aan", "off": "uit", "open": "open", "closed": "dicht", "locked": "op slot", "unlocked": "niet op slot",
           "opening": "gaat open", "closing": "gaat dicht", "playing": "speelt", "paused": "gepauzeerd",
           "idle": "stand-by", "unavailable": "niet bereikbaar",
           "brightness": "helderheid {n}%", "position": "positie {n}%", "target": "ingesteld op {n} graden",
           "current": "nu {n} graden", "volume": "volume {n}%", "title": "speelt {t}", "speed": "snelheid {n}%",
           "hvac": {"heat": "verwarmt", "cool": "koelt", "auto": "op automatisch", "heat_cool": "op automatisch",
                    "dry": "ontvochtigt", "fan_only": "ventileert"}},
    "pt": {"on": dict(m="aceso", f="acesa", mp="acesos", fp="acesas"),
           "off": dict(m="apagado", f="apagada", mp="apagados", fp="apagadas"),
           "open": dict(m="aberto", f="aberta", mp="abertos", fp="abertas"),
           "closed": dict(m="fechado", f="fechada", mp="fechados", fp="fechadas"),
           "locked": dict(m="trancado", f="trancada", mp="trancados", fp="trancadas"),
           "unlocked": dict(m="destrancado", f="destrancada", mp="destrancados", fp="destrancadas"),
           "opening": "a abrir", "closing": "a fechar", "playing": "a tocar", "paused": "em pausa",
           "idle": "em espera", "unavailable": "indisponível",
           "brightness": "brilho {n}%", "position": "posição {n}%", "target": "definida para {n} graus",
           "current": "agora estão {n} graus", "volume": "volume {n}%", "title": "a tocar {t}",
           "speed": "velocidade {n}%",
           "hvac": {"heat": "a aquecer", "cool": "a arrefecer", "auto": "em automático", "heat_cool": "em automático",
                    "dry": "a desumidificar", "fan_only": "em ventilação"}},
    "pl": {"on": dict(m="włączony", f="włączona", n="włączone", mp="włączone", fp="włączone"),
           "off": dict(m="wyłączony", f="wyłączona", n="wyłączone", mp="wyłączone", fp="wyłączone"),
           "open": dict(m="otwarty", f="otwarta", n="otwarte", mp="otwarte", fp="otwarte"),
           "closed": dict(m="zamknięty", f="zamknięta", n="zamknięte", mp="zamknięte", fp="zamknięte"),
           "locked": dict(m="zamknięty na klucz", f="zamknięta na klucz", n="zamknięte na klucz", mp="zamknięte na klucz",
                          fp="zamknięte na klucz"),
           "unlocked": dict(m="otwarty", f="otwarta", n="otwarte", mp="otwarte", fp="otwarte"),
           "opening": "otwiera się", "closing": "zamyka się", "playing": "odtwarza", "paused": "pauza",
           "idle": "w gotowości", "unavailable": "niedostępne",
           "brightness": "jasność {n}%", "position": "pozycja {n}%", "target": "ustawione {n} stopni",
           "current": "teraz {n} stopni", "volume": "głośność {n}%", "title": "odtwarza {t}",
           "speed": "prędkość {n}%",
           "hvac": {"heat": "grzanie", "cool": "chłodzenie", "auto": "tryb automatyczny", "heat_cool": "tryb automatyczny",
                    "dry": "osuszanie", "fan_only": "wentylacja"}},
    "sv": {"on": "på", "off": "av", "open": "öppen", "closed": "stängd", "locked": "låst", "unlocked": "olåst",
           "opening": "öppnas", "closing": "stängs", "playing": "spelar", "paused": "pausad", "idle": "i viloläge",
           "unavailable": "inte nåbar",
           "brightness": "ljusstyrka {n} %", "position": "position {n} %", "target": "inställd på {n} grader",
           "current": "just nu {n} grader", "volume": "volym {n} %", "title": "spelar {t}",
           "speed": "hastighet {n} %",
           "hvac": {"heat": "värmer", "cool": "kyler", "auto": "på automatik", "heat_cool": "på automatik",
                    "dry": "avfuktar", "fan_only": "fläkt"}},
}


# round 7: more device kinds
W2 = {
    "it": {"home": "a casa", "not_home": "fuori casa", "mowing": "sta tagliando l'erba", "docked": "alla base",
           "returning": "sta rientrando", "error": "in errore", "detected": {"moisture": "perdita d'acqua rilevata",
           "smoke": "fumo rilevato", "gas": "gas rilevato", "motion": "movimento rilevato", "occupancy": "presenza rilevata"},
           "clear": {"moisture": "nessuna perdita", "smoke": "nessun fumo", "gas": "nessuna fuga di gas",
                     "motion": "nessun movimento", "occupancy": "nessuna presenza"},
           "hum_target": "umidità impostata al {n}%", "water_target": "acqua a {n} gradi",
           "people_home": ("A casa: {names}.", "Non c'è nessuno a casa."),
           "all_quiet": "È tutto spento e chiuso.", "list_added": "Ho aggiunto {item} a {list}."},
    "en": {"home": "at home", "not_home": "away", "mowing": "mowing", "docked": "docked", "returning": "returning",
           "error": "in error", "detected": {"moisture": "water leak detected", "smoke": "smoke detected",
           "gas": "gas detected", "motion": "motion detected", "occupancy": "someone detected"},
           "clear": {"moisture": "no leak", "smoke": "no smoke", "gas": "no gas", "motion": "no motion",
                     "occupancy": "nobody detected"},
           "hum_target": "target humidity {n}%", "water_target": "water at {n} degrees",
           "people_home": ("At home: {names}.", "Nobody is home."),
           "all_quiet": "Everything is off and closed.", "list_added": "I added {item} to {list}."},
    "es": {"home": "en casa", "not_home": "fuera de casa", "mowing": "cortando el césped", "docked": "en la base",
           "returning": "volviendo", "error": "con error", "detected": {"moisture": "fuga de agua detectada",
           "smoke": "humo detectado", "gas": "gas detectado", "motion": "movimiento detectado",
           "occupancy": "presencia detectada"},
           "clear": {"moisture": "sin fugas", "smoke": "sin humo", "gas": "sin gas", "motion": "sin movimiento",
                     "occupancy": "sin presencia"},
           "hum_target": "humedad fijada al {n}%", "water_target": "agua a {n} grados",
           "people_home": ("En casa: {names}.", "No hay nadie en casa."),
           "all_quiet": "Todo está apagado y cerrado.", "list_added": "He añadido {item} a {list}."},
    "fr": {"home": "à la maison", "not_home": "absent", "mowing": "en train de tondre", "docked": "sur sa base",
           "returning": "en retour", "error": "en erreur", "detected": {"moisture": "fuite d'eau détectée",
           "smoke": "fumée détectée", "gas": "gaz détecté", "motion": "mouvement détecté", "occupancy": "présence détectée"},
           "clear": {"moisture": "pas de fuite", "smoke": "pas de fumée", "gas": "pas de gaz", "motion": "aucun mouvement",
                     "occupancy": "personne"},
           "hum_target": "humidité réglée à {n} %", "water_target": "eau à {n} degrés",
           "people_home": ("À la maison : {names}.", "Il n'y a personne à la maison."),
           "all_quiet": "Tout est éteint et fermé.", "list_added": "J'ai ajouté {item} à {list}."},
    "de": {"home": "zu Hause", "not_home": "unterwegs", "mowing": "mäht", "docked": "in der Station",
           "returning": "fährt zurück", "error": "Fehler", "detected": {"moisture": "Wasserleck erkannt",
           "smoke": "Rauch erkannt", "gas": "Gas erkannt", "motion": "Bewegung erkannt", "occupancy": "Anwesenheit erkannt"},
           "clear": {"moisture": "kein Leck", "smoke": "kein Rauch", "gas": "kein Gas", "motion": "keine Bewegung",
                     "occupancy": "niemand"},
           "hum_target": "Zielfeuchte {n} %", "water_target": "Wasser auf {n} Grad",
           "people_home": ("Zu Hause: {names}.", "Niemand ist zu Hause."),
           "all_quiet": "Alles ist aus und geschlossen.", "list_added": "Ich habe {item} zu {list} hinzugefügt."},
    "nl": {"home": "thuis", "not_home": "weg", "mowing": "aan het maaien", "docked": "in het laadstation",
           "returning": "keert terug", "error": "fout", "detected": {"moisture": "waterlek gedetecteerd",
           "smoke": "rook gedetecteerd", "gas": "gas gedetecteerd", "motion": "beweging gedetecteerd",
           "occupancy": "aanwezigheid gedetecteerd"},
           "clear": {"moisture": "geen lek", "smoke": "geen rook", "gas": "geen gas", "motion": "geen beweging",
                     "occupancy": "niemand"},
           "hum_target": "doelvochtigheid {n}%", "water_target": "water op {n} graden",
           "people_home": ("Thuis: {names}.", "Er is niemand thuis."),
           "all_quiet": "Alles is uit en dicht.", "list_added": "Ik heb {item} aan {list} toegevoegd."},
    "pt": {"home": "em casa", "not_home": "fora de casa", "mowing": "a cortar a relva", "docked": "na base",
           "returning": "a regressar", "error": "com erro", "detected": {"moisture": "fuga de água detetada",
           "smoke": "fumo detetado", "gas": "gás detetado", "motion": "movimento detetado", "occupancy": "presença detetada"},
           "clear": {"moisture": "sem fugas", "smoke": "sem fumo", "gas": "sem gás", "motion": "sem movimento",
                     "occupancy": "sem presença"},
           "hum_target": "humidade definida para {n}%", "water_target": "água a {n} graus",
           "people_home": ("Em casa: {names}.", "Não está ninguém em casa."),
           "all_quiet": "Está tudo desligado e fechado.", "list_added": "Adicionei {item} a {list}."},
    "pl": {"home": "w domu", "not_home": "poza domem", "mowing": "kosi trawę", "docked": "w stacji",
           "returning": "wraca", "error": "błąd", "detected": {"moisture": "wykryto wyciek wody", "smoke": "wykryto dym",
           "gas": "wykryto gaz", "motion": "wykryto ruch", "occupancy": "wykryto obecność"},
           "clear": {"moisture": "brak wycieku", "smoke": "brak dymu", "gas": "brak gazu", "motion": "brak ruchu",
                     "occupancy": "brak obecności"},
           "hum_target": "docelowa wilgotność {n}%", "water_target": "woda {n} stopni",
           "people_home": ("W domu: {names}.", "Nikogo nie ma w domu."),
           "all_quiet": "Wszystko jest wyłączone i zamknięte.", "list_added": "Dodałem {item} do {list}."},
    "sv": {"home": "hemma", "not_home": "borta", "mowing": "klipper gräset", "docked": "i laddstationen",
           "returning": "på väg tillbaka", "error": "fel", "detected": {"moisture": "vattenläcka upptäckt",
           "smoke": "rök upptäckt", "gas": "gas upptäckt", "motion": "rörelse upptäckt", "occupancy": "närvaro upptäckt"},
           "clear": {"moisture": "ingen läcka", "smoke": "ingen rök", "gas": "ingen gas", "motion": "ingen rörelse",
                     "occupancy": "ingen närvaro"},
           "hum_target": "målfuktighet {n} %", "water_target": "vatten på {n} grader",
           "people_home": ("Hemma: {names}.", "Ingen är hemma."),
           "all_quiet": "Allt är avstängt och stängt.", "list_added": "Jag lade till {item} i {list}."},
}
ALARM_CLASSES = {"moisture", "smoke", "gas", "motion", "occupancy", "carbon_monoxide"}

AND = {"it": " e ", "en": " and ", "es": " y ", "fr": " et ", "de": " und ", "nl": " en ", "pt": " e ", "pl": " i ",
       "sv": " och "}

# "is anything on?": (some on / open, none) per kind of device
SUMMARY = {
    "light": {"it": ("Luci accese: {names}.", "Nessuna luce accesa."),
              "en": ("Lights on: {names}.", "No lights are on."),
              "es": ("Luces encendidas: {names}.", "No hay luces encendidas."),
              "fr": ("Lumières allumées : {names}.", "Aucune lumière allumée."),
              "de": ("Eingeschaltete Lichter: {names}.", "Kein Licht ist an."),
              "nl": ("Lampen aan: {names}.", "Er zijn geen lampen aan."),
              "pt": ("Luzes acesas: {names}.", "Não há luzes acesas."),
              "pl": ("Włączone światła: {names}.", "Żadne światło nie jest włączone."),
              "sv": ("Tända lampor: {names}.", "Inga lampor är tända.")},
    "cover": {"it": ("Aperte: {names}.", "Tapparelle e tende sono tutte chiuse."),
              "en": ("Open: {names}.", "All blinds and covers are closed."),
              "es": ("Abiertas: {names}.", "Todas las persianas están cerradas."),
              "fr": ("Ouverts : {names}.", "Tous les volets sont fermés."),
              "de": ("Offen: {names}.", "Alle Rollläden sind geschlossen."),
              "nl": ("Open: {names}.", "Alle rolluiken zijn dicht."),
              "pt": ("Abertos: {names}.", "Todos os estores estão fechados."),
              "pl": ("Otwarte: {names}.", "Wszystkie rolety są zamknięte."),
              "sv": ("Öppna: {names}.", "Alla persienner är stängda.")},
    "binary_sensor": {"it": ("Aperte: {names}.", "Porte e finestre sono tutte chiuse."),
                      "en": ("Open: {names}.", "All doors and windows are closed."),
                      "es": ("Abiertas: {names}.", "Todas las puertas y ventanas están cerradas."),
                      "fr": ("Ouvertes : {names}.", "Portes et fenêtres sont toutes fermées."),
                      "de": ("Offen: {names}.", "Alle Türen und Fenster sind geschlossen."),
                      "nl": ("Open: {names}.", "Alle deuren en ramen zijn dicht."),
                      "pt": ("Abertas: {names}.", "Portas e janelas estão todas fechadas."),
                      "pl": ("Otwarte: {names}.", "Wszystkie drzwi i okna są zamknięte."),
                      "sv": ("Öppna: {names}.", "Alla dörrar och fönster är stängda.")},
    "lock": {"it": ("Non chiuse a chiave: {names}.", "Tutte le serrature sono chiuse a chiave."),
             "en": ("Unlocked: {names}.", "All locks are locked."),
             "es": ("Sin cerrar con llave: {names}.", "Todas las cerraduras están cerradas con llave."),
             "fr": ("Non verrouillées : {names}.", "Toutes les serrures sont verrouillées."),
             "de": ("Nicht abgeschlossen: {names}.", "Alle Schlösser sind abgeschlossen."),
             "nl": ("Niet op slot: {names}.", "Alle sloten zijn op slot."),
             "pt": ("Destrancadas: {names}.", "Todas as fechaduras estão trancadas."),
             "pl": ("Niezamknięte na klucz: {names}.", "Wszystkie zamki są zamknięte na klucz."),
             "sv": ("Olåsta: {names}.", "Alla lås är låsta.")},
    "switch": {"it": ("Accesi: {names}.", "Nessuna presa accesa."),
               "en": ("On: {names}.", "No switches are on."),
               "es": ("Encendidos: {names}.", "No hay enchufes encendidos."),
               "fr": ("Allumés : {names}.", "Aucune prise allumée."),
               "de": ("An: {names}.", "Keine Steckdose ist an."),
               "nl": ("Aan: {names}.", "Er staat geen stopcontact aan."),
               "pt": ("Ligados: {names}.", "Não há tomadas ligadas."),
               "pl": ("Włączone: {names}.", "Żadne gniazdko nie jest włączone."),
               "sv": ("På: {names}.", "Inga uttag är på.")},
    "media_player": {"it": ("Accesi: {names}.", "TV e casse sono tutte spente."),
                     "en": ("On: {names}.", "All TVs and speakers are off."),
                     "es": ("Encendidos: {names}.", "Las teles y los altavoces están apagados."),
                     "fr": ("Allumés : {names}.", "Télés et enceintes sont éteintes."),
                     "de": ("An: {names}.", "Alle Fernseher und Lautsprecher sind aus."),
                     "nl": ("Aan: {names}.", "Alle tv's en speakers zijn uit."),
                     "pt": ("Ligados: {names}.", "As TVs e as colunas estão todas desligadas."),
                     "pl": ("Włączone: {names}.", "Wszystkie telewizory i głośniki są wyłączone."),
                     "sv": ("På: {names}.", "Alla tv-apparater och högtalare är av.")},
    "fan": {"it": ("Accesi: {names}.", "Nessun ventilatore acceso."),
            "en": ("On: {names}.", "No fans are on."),
            "es": ("Encendidos: {names}.", "No hay ventiladores encendidos."),
            "fr": ("Allumés : {names}.", "Aucun ventilateur allumé."),
            "de": ("An: {names}.", "Kein Ventilator ist an."),
            "nl": ("Aan: {names}.", "Er staat geen ventilator aan."),
            "pt": ("Ligados: {names}.", "Não há ventoinhas ligadas."),
            "pl": ("Włączone: {names}.", "Żaden wentylator nie jest włączony."),
            "sv": ("På: {names}.", "Inga fläktar är på.")},
}

# first words of names whose gender the endings get wrong
_FEM = {"it": {"luce", "luci", "tv", "tele", "televisione", "radio", "tivu", "stampante", "lavastoviglie", "presa",
               "abat-jour", "chiave", "corrente", "pompa"},
        "es": {"luz", "luces", "tele", "tv", "televisión", "television", "radio", "lámpara"},
        "pt": {"luz", "luzes", "tv", "televisão", "televisao", "rádio", "coluna", "máquina"},
        "fr": {"lumière", "lumières", "lampe", "lampes", "prise", "fenêtre", "porte", "télé", "tv", "télévision",
               "enceinte", "radio", "machine", "cafetière", "lanterne", "lanternes", "applique", "guirlande",
               "suspension", "veilleuse", "chaudière", "pompe", "serrure", "baie", "bouilloire", "hotte", "barrière"},
        "pl": {"tv"}}
_MASC = {"it": {"abat-jour"}, "es": {"día", "sofá"}, "pt": {"sofá"}, "pl": {"telewizor", "głośnik"}}


def form(name: str, lang: str) -> str:
    """'m', 'f', 'mp', 'fp' or 'n' for the adjective that follows the name."""
    w = normalize(name, accents=True).split()[0] if name.strip() else ""
    if lang == "it":
        if w in _MASC["it"]:
            return "m"
        if w in ("luci",):
            return "fp"
        if w in _FEM["it"] or w.endswith("a"):
            return "f"
        if w.endswith("i"):
            return "mp"
        if w.endswith(("lle", "rne", "nde", "tte", "ole", "ine", "ghe", "che", "ere")) and len(w) > 4:
            return "fp"
        return "m"
    if lang in ("es", "pt"):
        if w in _MASC[lang]:
            return "m"
        plural = w.endswith("s") and len(w) > 3 and w not in ("gás", "gas", "mes", "más")
        stem = w[:-1] if plural else w
        fem = w in _FEM[lang] or stem.endswith("a") or stem.endswith(("ción", "cion", "ção", "cao", "dad", "ade"))
        return ("fp" if fem else "mp") if plural else ("f" if fem else "m")
    if lang == "fr":
        plural = w.endswith(("s", "x")) and len(w) > 3
        fem = w in _FEM["fr"] or w.endswith(("ière", "ières", "tte", "ttes", "elle", "elles", "tion", "tions"))
        return ("fp" if fem else "mp") if plural else ("f" if fem else "m")
    if lang == "pl":
        if w in _MASC["pl"]:
            return "m"
        if w in _FEM["pl"] or w.endswith("a"):
            return "f"
        if w.endswith(("o", "e", "um")):
            return "n"
        return "m"
    return "m"


def word(key: str, name: str, lang: str) -> str:
    x = W.get(lang, W["en"]).get(key, key)
    if isinstance(x, dict):
        f = form(name, lang)
        return x.get(f) or x.get({"n": "m", "fp": "f", "mp": "m"}.get(f, "m")) or x["m"]
    return x


def _num(x) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return str(int(v)) if v.is_integer() else f"{v:.1f}"


def describe(e, lang: str) -> str:
    """State of one entity in words, without the name: "accesa, luminosità 60%", "chiusa", "21 °C"."""
    st = e.state or {}
    s = str(st.get("state", "")).lower()
    L = W.get(lang, W["en"])
    if not s:
        return ""
    if s == "unavailable":
        return L["unavailable"]
    d = e.domain
    X = W2.get(lang, W2["en"])
    if d == "sensor":
        unit = (e.attributes or {}).get("unit") or st.get("unit") or ""
        return f"{_num(s)} {unit}".strip()
    if d == "binary_sensor" and (e.device_class or "") in ALARM_CLASSES:
        cls = "gas" if e.device_class == "carbon_monoxide" else e.device_class
        return X["detected" if s == "on" else "clear"].get(cls, s)
    if d == "person":
        return X.get(s, s)  # "home", "not_home" or the name of a zone ("Lavoro")
    if d == "lawn_mower":
        return X.get(s) or L.get(s) or s
    if d == "water_heater":
        parts = [word("off", e.name, lang) if s == "off" else word("on", e.name, lang)]
        if s != "off" and st.get("temperature") is not None:
            parts.append(X["water_target"].format(n=_num(st["temperature"])))
        return ", ".join(parts)
    if d == "humidifier":
        parts = [word("on" if s == "on" else "off", e.name, lang)]
        if s == "on" and st.get("humidity") is not None:
            parts.append(X["hum_target"].format(n=_num(st["humidity"])))
        return ", ".join(parts)
    if d == "climate":
        parts = [word("off", e.name, lang)] if s == "off" else [L["hvac"].get(s, s)]
        if s != "off" and st.get("temperature") is not None:
            parts.append(L["target"].format(n=_num(st["temperature"])))
        if st.get("current_temperature") is not None:
            parts.append(L["current"].format(n=_num(st["current_temperature"])))
        return ", ".join(parts)
    if d == "media_player":
        if s in ("off", "standby"):
            return word("off", e.name, lang)
        parts = [L.get(s) if s in ("playing", "paused", "idle") else word("on", e.name, lang)]
        if st.get("media_title") and s in ("playing", "paused"):
            parts = [L["title"].format(t=st["media_title"])] + (["(" + L["paused"] + ")"] if s == "paused" else [])
        if st.get("volume") is not None:
            parts.append(L["volume"].format(n=_num(st["volume"])))
        return ", ".join(parts)
    key = {"on": "on", "off": "off", "open": "open", "closed": "closed", "locked": "locked", "unlocked": "unlocked",
           "opening": "opening", "closing": "closing", "jammed": "unavailable"}.get(s)
    if key is None:
        return s
    parts = [word(key, e.name, lang) if key in ("on", "off", "open", "closed", "locked", "unlocked") else L[key]]
    if d == "light" and s == "on" and st.get("brightness") is not None:
        parts.append(L["brightness"].format(n=_num(st["brightness"])))
    if d == "cover" and s == "open" and st.get("position") is not None and 0 < float(st["position"]) < 100:
        parts.append(L["position"].format(n=_num(st["position"])))
    if d == "fan" and s == "on" and st.get("percentage") is not None:
        parts.append(L["speed"].format(n=_num(st["percentage"])))
    return ", ".join(parts)


def join(items: list, lang: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + AND.get(lang, " and ") + items[-1]


def is_active(e) -> bool:
    """On / open / unlocked / at home: what a "is anything ...?" question lists."""
    s = str((e.state or {}).get("state", "")).lower()
    if e.domain == "lock":
        return s == "unlocked"
    if e.domain == "person":
        return s == "home"
    if e.domain == "binary_sensor" and (e.device_class or "") in ALARM_CLASSES:
        return s == "on"
    if e.domain in ("cover", "binary_sensor", "valve"):
        return s in ("open", "opening", "on")
    return s not in ("off", "standby", "unavailable", "unknown", "")


def summary_key(e) -> str:
    return e.domain if e.domain in SUMMARY else ""


def area_reply(ents: list, area_name: Optional[str], lang: str) -> str:
    """"Salone: Lampada ad arco accesa, luminosità 60%; Faretti salone spenti." """
    items = [f"{e.name} {describe(e, lang)}".strip() for e in ents]
    body = "; ".join(items)
    return f"{area_name}: {body}." if area_name else f"{body}."


def people_reply(ents: list, lang: str) -> str:
    some, none = W2.get(lang, W2["en"])["people_home"]
    on = [e.name for e in ents if is_active(e)]
    return some.format(names=join(on, lang)) if on else none


def home_reply(cat, lang: str) -> str:
    """"cosa è rimasto acceso?": lights, TVs and plugs on, covers / doors / windows open, locks open."""
    out = []
    for dom in ("light", "media_player", "switch", "fan", "cover", "binary_sensor", "lock"):
        ents = [e for e in cat.entities.values() if e.domain == dom
                and not (dom == "binary_sensor" and (e.device_class or "") not in ("window", "door"))
                and not (dom == "switch" and protected(e))]
        if any(is_active(e) for e in ents):
            out.append(house_reply(ents, lang))
    return " ".join(out) if out else W2.get(lang, W2["en"])["all_quiet"]


# never switched off by "spegni tutto" (they keep the house safe or working)
PROTECTED_WORDS = set(normalize("""frigo frigorifero congelatore freezer fridge refrigerator nevera refrigerador
congelador frigorifique congelateur kuhlschrank gefrier gefriertruhe koelkast vriezer geladeira frigorifico arca
lodowka zamrazarka kylskap frys router modem server nas wifi pompa pump bomba pompe pumpe caldaia boiler caldera
chaudiere heizung ketel caldeira kociol panna acquario aquarium acuario allarme alarm alarma alarme larm
telecamera camera camara kamera nvr irrigazione""").split())


def protected(e) -> bool:
    toks = set(normalize(e.name).replace("-", " ").split()) | {normalize(a) for a in (e.aliases or [])}
    return bool(toks & PROTECTED_WORDS) or any(w in normalize(e.name).replace(" ", "") for w in
                                                 ("kuhlschrank", "gefrier", "koelkast", "kylskap", "lodowk"))


def house_reply(ents: list, lang: str, count: bool = False) -> str:
    """"Luci accese: Lampada ad arco e Luce taverna." / "Nessuna luce accesa." count=True ("quante luci sono
    accese?"): "(3) Luci accese: ..." with the number first."""
    key = summary_key(ents[0]) if ents else "light"
    some, none = SUMMARY.get(key, SUMMARY["light"]).get(lang) or SUMMARY.get(key, SUMMARY["light"])["en"]
    on = [e.name for e in ents if is_active(e)]
    if not on:
        return none
    out = some.format(names=join(on, lang))
    return f"{len(on)}. {out}" if count else out


COUNT_WORDS = set(normalize("""quante quanti how many cuantas cuantos combien wie viele hoeveel quantas quantos ile
hur manga""").split()) - {"how", "many", "wie", "hur"} | {"many", "viele", "manga"}


# words of a question about states, any language (normalised): "accese", "open", "an", "aperte"... + question words
def state_words() -> set:
    out = set()
    for lang, t in W.items():
        for k in ("on", "off", "open", "closed", "locked", "unlocked"):
            v = t[k]
            for s in (v.values() if isinstance(v, dict) else [v]):
                out.update(normalize(s).split())
    return out - {"a", "na", "op", "slot", "con", "sin", "la", "chiave", "klucz", "llave", "niet", "nicht"}


# words that make a state question about the whole house ("ci sono luci accese?", "which lights are on?")
QUESTION_WORDS = set(normalize("""quali quale quante qualche qualcuna nessuna nessun ci sono which any anything
cuales cual hay alguna algun alguno cuantas quels quelles quel quelle welche welcher irgendein irgendwelche welke
nog quais qual algum alguma quantas ktore ktory jakies jakis ile vilka vilken finns nagon nagot nagra""").split())
