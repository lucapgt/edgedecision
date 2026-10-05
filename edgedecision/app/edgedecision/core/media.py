"""What to play: the content of "metti radio deejay in cucina" and its kind (radio / playlist / album / track).

The model marks the content words (tag VAL, e.g. "deejay", "bohemian rhapsody", "jazz"); this module only cleans
them and reads the kind from the words around them ("la RADIO deejay", "la PLAYLIST relax"). The search itself is
done by Music Assistant (music_assistant.play_media), which finds artists, songs, playlists and stations by name.
"""
from __future__ import annotations

from typing import Optional

from .text import normalize

# words that name the kind of content, in every supported language (normalised, accents removed)
MEDIA_TYPE_WORDS = {
    "radio": ["radio", "webradio", "web radio", "stazione radio", "emittente", "station", "radio station", "emisora",
              "radiosender", "sender", "zender", "radiozender", "estacao", "estacao de radio", "radia", "stacja",
              "stacje", "rozglosnia", "radiokanal", "radiostation", "kanal"],
    "playlist": ["playlist", "play list", "lista de reproduccion", "liste de lecture", "wiedergabeliste",
                 "afspeellijst", "lista de reproducao", "spellista", "spellistan", "playliste", "playlista",
                 "playlisty", "playlisten"],
    "album": ["album", "l album", "albumet", "albumu"],
    "track": ["canzone", "brano", "pezzo", "song", "track", "cancion", "tema", "chanson", "morceau", "titre", "lied",
              "liedje", "nummer", "cancao", "faixa", "piosenka", "piosenke", "utwor", "lat", "laten"],
}

# leading words that are not part of the name ("la radio DEEJAY", "some JAZZ", "un po' di JAZZ")
_LEAD = set(normalize("""il lo la l i gli le un una uno di del della dei degli delle po un po the a an some my of by
el los las unos unas de del mi un poco algo le la les l du des de d un une mon ma mes quelque chose der die das den
dem des ein eine einen meine meinen etwas von de het een mijn wat iets van o a os as um uma meu minha umas uns do da
dos das algum alguma pouco w na z moja moje moj troche en ett min mitt mina lite nagot med""").split())


def media_type(text: str) -> Optional[str]:
    """radio / playlist / album / track when the sentence names the kind of content, else None (any kind)."""
    t = " " + " ".join(normalize(text).replace("'", " ").split()) + " "
    for kind, words in MEDIA_TYPE_WORDS.items():
        if any(f" {w} " in t for w in words):
            return kind
    return None


def clean_content(value: Optional[str]) -> Optional[str]:
    """The name to search for: the VAL words without leading articles and content-kind words."""
    if not value:
        return None
    words = value.replace("’", "'").split()
    kind_words = {w for ws in MEDIA_TYPE_WORDS.values() for w in ws if " " not in w}
    while words:
        n = normalize(words[0]).replace("'", " ").split()
        if n and all(x in _LEAD or x in kind_words for x in n):
            words = words[1:]
            continue
        break
    # trailing kind word too ("Entspannungs-Playlist", "ontspanning afspeellijst" -> the name only)
    while words:
        last = normalize(words[-1]).replace("'", " ")
        head, _, tail = last.rpartition("-")
        if last in kind_words and len(words) > 1:
            words = words[:-1]
        elif head and tail in kind_words:
            words[-1] = words[-1][:len(head)]
        else:
            break
    out = " ".join(words).strip(" ,.;:!?\"'«»-")
    return out or None


# verbs that open a request to play something ("metti", "spiel", "sätt på", "ik wil naar ... luisteren")
_PLAY_LEAD = set(normalize("""metti mettimi mettici suona suonami riproduci fai partire voglio ascoltare sentire play put
on start me i want to listen hear pon ponme ponnos reproduce toca tocame quiero escuchar oir mets mettez lance lancez joue
jouez je veux ecouter ich will mochte horen hoeren spiel spiele starte mach zet speel start wil naar luisteren ik poe
ponha toca coloca quero ouvir wlacz pusc puscie zagraj chce posluchac sluchac satt pa spela starta jag vill lyssna
play me""").split())


# "music" itself is not something to search for ("riproduci della musica", "spiel Musik")
GENERIC_MUSIC = set(normalize("""musica musics music musik musique muziek muzyka muzyke muzyki música musica qualcosa
something algo quelque chose etwas iets algo cos coś nagot något un po po' di bit some poco peu bisschen beetje pouco
troche trochę lite""").split())


MUSIC_WORDS = set(normalize("musica music musik musique muziek muzyka muzyke muzyki musikk").split())


def _name_span(words: list, names) -> Optional[tuple]:
    """(start, end) of the first run of words that belong to the player's / room's name, or None."""
    keys = {w for n in names or [] for w in normalize(n).split() if len(w) >= 4}
    for i, w in enumerate(words):
        if normalize(w).strip(" ,.;:!?'") in keys:
            j = i + 1
            full = {w2 for n in names or [] for w2 in normalize(n).split()}
            while j < len(words) and normalize(words[j]).strip(" ,.;:!?'") in full:
                j += 1
            return i, j
    return None


def _target_cut(words: list, names) -> list:
    """Drop the words that name where to play it. At the end ("musica su satellite" -> "musica"): from the
    preposition before the name. At the start ("su Musica Dire Straits" -> "Dire Straits"): up to the name."""
    span = _name_span(words, names)
    if span is None:
        return words
    i, j = span
    if i <= 1 and j < len(words):  # "su musica dire straits", "musica dire straits"
        return words[j:]
    return words[:max(0, i - 1)] if i >= 1 and len(normalize(words[i - 1])) <= 5 else words[:i]


def strip_target(value: Optional[str], names) -> Optional[str]:
    """The tagged content without the player's name in it ("radio dj su musica" -> "radio dj" when the player is
    called "Musica"); None when nothing else is left."""
    if not value:
        return value
    out = " ".join(_target_cut(value.replace("’", "'").split(), names)).strip(" ,.;:!?\"'«»-")
    return out or None


def spoken_digits(value: Optional[str]) -> Optional[str]:
    """"otto otto tre" -> "883" (a band / station said digit by digit); anything else unchanged."""
    if not value:
        return value
    from .when import _word_num
    toks = normalize(value).split()
    nums = [_word_num(t) for t in toks]
    if len(toks) >= 2 and all(n is not None and 0 <= n <= 9 for n in nums):
        return "".join(str(n) for n in nums)
    return value


def is_generic_music(value: Optional[str]) -> bool:
    toks = normalize((value or "").replace("'", " ")).split()
    return bool(toks) and all(t in GENERIC_MUSIC or t in _LEAD for t in toks)


def guess_content(text: str, names=None) -> Optional[str]:
    """The content of a play request when the model tagged none: the sentence after its opening play verb(s)
    ("spiel etwas Jazz" -> "Jazz", "lance ma playlist détente" -> "détente"). None when there is no play verb first
    or nothing is left (\"metti la radio\")."""
    words = text.replace("’", "'").split()
    k = 0
    while k < len(words) and normalize(words[k]).strip(" ,.;:!?'") in _PLAY_LEAD:
        k += 1
    if k == 0:
        return None
    rest = [w for w in words[k:] if normalize(w).strip(" ,.;:!?'") not in ("luisteren", "ouvir", "escuchar",
                                                                           "ecouter", "horen", "lyssna", "listen")]
    out = clean_content(" ".join(_target_cut(rest, names)))
    if is_generic_music(out):
        return None
    return out if out and len(out.split()) <= 5 else None


# question when the content is missing ("metti qualcosa sulla cassa della cucina")
WHAT_TO_PLAY = {"it": "Cosa vuoi ascoltare?", "en": "What would you like to listen to?", "es": "¿Qué quieres escuchar?",
                "fr": "Qu'est-ce que vous voulez écouter ?", "de": "Was möchtest du hören?",
                "nl": "Waar wil je naar luisteren?", "pt": "O que queres ouvir?", "pl": "Czego chcesz posłuchać?",
                "sv": "Vad vill du lyssna på?"}
