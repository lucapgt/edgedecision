"""Português - runtime words (values, replies). See core/lang/__init__.py."""

LANG = "pt"
NUMBER_LANG = "pt"

COLORS = {"red": ["vermelho", "vermelha", "encarnado"], "green": ["verde"], "blue": ["azul"],
          "lightblue": ["azul claro", "azul céu", "celeste"], "yellow": ["amarelo", "amarela"], "orange": ["laranja"],
          "purple": ["roxo", "roxa", "violeta"], "pink": ["rosa", "cor de rosa"], "white": ["branco", "branca"],
          "turquoise": ["turquesa"], "magenta": ["magenta", "fúcsia"], "gold": ["dourado", "dourada", "ouro"]}
COLOR_TEMPS = {"warm": ["quente", "branco quente", "luz quente"], "neutral": ["neutra", "neutro", "natural", "luz do dia"],
               "cool": ["fria", "frio", "branco frio", "luz fria"]}
HVAC = {"heat": ["aquecimento", "aquecer", "modo aquecimento", "calor"], "cool": ["arrefecimento", "arrefecer", "frio", "resfriar"],
        "auto": ["automático", "auto"], "dry": ["desumidificar", "desumidificação", "seco"],
        "fan_only": ["ventilação", "só ventilação", "ventilar"]}
DOMAIN_KEYWORDS = {"light": ["luz", "luzes", "lâmpada", "candeeiro", "led"], "switch": ["tomada", "interruptor"],
                   "cover": ["estore", "estores", "persiana", "persianas", "cortina", "toldo"],
                   "climate": ["termóstato", "aquecimento", "ar condicionado", "temperatura", "graus"],
                   "media_player": ["tv", "televisão", "música", "volume", "coluna", "canção"],
                   "fan": ["ventoinha", "ventilador"], "lock": ["fechadura", "porta", "chave"],
                   "sensor": ["temperatura", "humidade", "sensor"], "binary_sensor": ["janela", "porta", "aberta", "fechada"],
                   "vacuum": ["aspirador", "robô"], "scene": ["cena", "ambiente"], "weather": ["tempo", "previsão", "chuva", "guarda-chuva"], "alarm_control_panel": ["alarme"]}
DAYS = {"today": ["hoje", "agora"], "tomorrow": ["amanhã"], "day_after": ["depois de amanhã"],
        "monday": ["segunda-feira", "segunda"], "tuesday": ["terça-feira", "terça"], "wednesday": ["quarta-feira", "quarta"],
        "thursday": ["quinta-feira", "quinta"], "friday": ["sexta-feira", "sexta"], "saturday": ["sábado"],
        "sunday": ["domingo"]}
ON = ["liga", "ligar", "acende", "acender", "ligada"]
OFF = ["desliga", "desligar", "apaga", "apagar", "desligada"]
STATE = ["está", "estado", "quanto", "qual"]

# core/specific.py: generic device nouns, words that never name a device, command verbs ("liga a tv")
KIND_NOUNS = {"light": "luz luzes lâmpada lâmpadas candeeiro iluminação", "cover.shutter": "estore estores persiana persianas",
              "cover.curtain": "cortina cortinas", "cover.awning": "toldo", "cover.garage": "garagem", "cover.gate": "portão",
              "climate.thermostat": "termóstato termostato aquecimento radiador",
              "climate.ac": "ar condicionado ac climatizador", "media_player.tv": "tv televisão televisor",
              "media_player.speaker": "rádio coluna música som", "fan": "ventoinha ventilador", "lock": "fechadura",
              "vacuum": "aspirador robô", "alarm": "alarme"}
FUNCTION_WORDS = """o a os as um uma uns umas de do da dos das no na nos nas em ao à para com por meu minha favor
obrigado obrigada pouco meio metade mais menos volume brilho temperatura graus por cento nível velocidade max min"""
VERBS = """liga ligar desliga desligar acende acender apaga apagar abre abrir fecha fechar sobe subir baixa baixar
aumenta aumentar diminui diminuir põe pôr coloca colocar ativa ativar desativa desativar para parar inicia iniciar
tranca destranca regula regular"""

PERCENT_UNITS = [("por", "cento"), ("porcento",)]
DEGREE_UNITS = [("graus",), ("grau",)]
HALF_SUFFIX = [("e", "meio"), ("e", "meia"), ("virgula", "cinco")]
HALF_WORDS = ["meio", "metade"]
MAX_WORDS = ["maximo", "tudo"]
MIN_WORDS = ["minimo"]
SMALL_STEP = ["pouco", "bocadinho", "ligeiramente"]
LARGE_STEP = ["muito", "bastante"]
ABS_MARKERS = ["para", "a", "ate", "em"]
REL_MARKERS = ["mais", "menos"]
AMBIGUOUS_NUMBERS = ["um", "uma"]

MESSAGES = {"ok": "Feito.", "ambiguous": "Queres dizer {opts}?", "low_confidence": "Não tenho a certeza: queres dizer {opts}?",
            "missing_param": "Para que valor?", "invalid_param": "Esse valor não é válido.",
            "confirm_high_risk": "Confirmas a ação em {opts}?", "cancelled": "Está bem, cancelado.",
            "not_understood": "Não percebi, podes repetir?",
            "unsupported": "Não consigo fazer isso com os dispositivos disponíveis.",
            "unavailable": "O dispositivo não está acessível.", "noop": "Está bem.", "escalate": "Deixa-me pensar...",
            "read": "{name}: {state}."}
OR = " ou "
AND = " e "
DOING = {"turn_on": "ligo", "turn_off": "desligo", "open": "abro", "close": "fecho", "stop": "paro", "set": "ajusto",
         "set_color": "mudo a cor de", "volume_set": "ajusto o volume de", "up": "aumento", "down": "baixo",
         "volume_up": "aumento o volume de", "volume_down": "baixo o volume de", "play_content": "ponho música em", "play": "retomo", "pause": "pauso",
         "next_track": "passo à seguinte em", "previous_track": "volto atrás em", "mute": "silencio", "lock": "tranco",
         "unlock": "destranco", "start": "inicio", "return_to_base": "mando para a base", "activate": "ativo", "arm": "ativo",
         "disarm": "desativo"}
DONE = {"turn_on": "liguei", "turn_off": "desliguei", "open": "abri", "close": "fechei", "stop": "parei", "set": "ajustei",
        "set_color": "mudei a cor de", "volume_set": "ajustei o volume de", "up": "aumentei", "down": "baixei",
        "volume_up": "aumentei o volume de", "volume_down": "baixei o volume de", "play_content": "pus música em", "play": "retomei", "pause": "pausei",
        "next_track": "passei à seguinte em", "previous_track": "voltei atrás em", "mute": "silenciei", "lock": "tranquei",
        "unlock": "destranquei", "start": "iniciei", "return_to_base": "mandei para a base", "activate": "ativei",
        "arm": "ativei", "disarm": "desativei"}
GROUP = {"light": "as luzes", "cover.shutter": "os estores", "cover": "os estores", "switch": "as tomadas",
         "fan": "as ventoinhas", "media_player": "os aparelhos", "climate": "os termóstatos", "_": "os aparelhos"}
GROUP_ALL = {"light": "todas as luzes", "cover.shutter": "todos os estores", "cover": "todos os estores",
             "switch": "todas as tomadas", "fan": "todas as ventoinhas", "media_player": "todos os aparelhos",
             "climate": "todos os termóstatos", "_": "todos os aparelhos"}
IN = "em"
AGO = {"now": "agora mesmo", "min": "há {n} minutos", "hour": "há {n} horas"}
NOTHING = "Ainda não fiz nada."
