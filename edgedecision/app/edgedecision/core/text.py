"""Text normalisation helpers (language agnostic, accent/punctuation robust)."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_APOS = re.compile(r"[’‘`´]")
_PUNCT = re.compile(r"[^\w%°\s.,'-]", re.UNICODE)
_SPACES = re.compile(r"\s+")


# letters that NFKD does not decompose into base letter + accent
_FOLD = str.maketrans({"ł": "l", "Ł": "l", "ß": "ss", "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe",
                       "đ": "d", "Đ": "d"})


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.translate(_FOLD)) if not unicodedata.combining(c))


def normalize(s: str, accents: bool = False) -> str:
    """Lowercase, unify apostrophes, drop exotic punctuation, collapse spaces."""
    s = _APOS.sub("'", s or "").lower()
    if not accents:
        s = strip_accents(s)
    s = _PUNCT.sub(" ", s)
    # keep decimal separators inside numbers only
    s = re.sub(r"(?<!\d)[.,]|[.,](?!\d)", " ", s)
    s = s.replace("'", "' ")
    return _SPACES.sub(" ", s).strip()


def words(s: str) -> list[str]:
    return normalize(s).replace("'", " ").split()


def fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def contains_fuzzy(haystack: str, needle: str, threshold: float = 0.84) -> bool:
    """True if `needle` (normalised) appears in `haystack` allowing typos."""
    h, n = normalize(haystack), normalize(needle)
    if not n:
        return False
    if n in h:
        return True
    hw, nw = h.split(), n.split()
    k = len(nw)
    for i in range(0, max(1, len(hw) - k + 1)):
        if fuzzy_ratio(" ".join(hw[i:i + k]), n) >= threshold:
            return True
    return False


def find_span(haystack: str, needle: str, threshold: float = 0.84):
    """Return (start_word, end_word) of the best fuzzy occurrence of needle in normalised haystack words."""
    hw, nw = normalize(haystack).replace("'", " ").split(), normalize(needle).replace("'", " ").split()
    k = len(nw)
    if not k or len(hw) < k:
        return None
    best, best_i = 0.0, None
    target = " ".join(nw)
    for i in range(0, len(hw) - k + 1):
        r = fuzzy_ratio(" ".join(hw[i:i + k]), target)
        if r > best:
            best, best_i = r, i
    if best >= threshold:
        return best_i, best_i + k
    return None
