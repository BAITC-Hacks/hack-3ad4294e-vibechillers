"""Matching-only text normalisation and lexical similarity.

Nothing here rewrites stored clause text: normalised forms are used to compare
clauses, never published as quotes.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_WORD = re.compile(r"[0-9a-zа-я]+", re.IGNORECASE)
_SPACE = re.compile(r"\s+")

# Function words that carry no duty content; kept small and generic.
_STOP = frozenset(
    """
    и в во на по с со к ко о об от до из за для при не а также как или либо что
    его ее её их то это этих этот эта этой том тем те так же в т ч т.ч. том числе
    числе иных иные иной других другие других всех все всего данным данного
    настоящего настоящим настоящей положения положением общества обществом общество
    of the and to in for on by with
    """.split()
)

_STEM_LEN = 6


def normalize(text: str) -> str:
    """Lower-case, fold ё, drop punctuation and collapse whitespace."""
    lowered = text.lower().replace("ё", "е")
    return " ".join(_WORD.findall(lowered))


def collapse_ws(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def stems(text: str) -> frozenset[str]:
    """Crude prefix stems of content words; adequate for Russian inflection."""
    out = set()
    for word in _WORD.findall(text.lower().replace("ё", "е")):
        if word in _STOP or (len(word) < 3 and not word.isdigit()):
            continue
        out.add(word[:_STEM_LEN])
    return frozenset(out)


def dice(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def sequence_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    # Junk heuristics keep very long blocks (glossaries) tractable; short clauses compare exactly.
    return SequenceMatcher(None, a, b, autojunk=max(len(a), len(b)) > 2000).ratio()


def similarity(norm_a: str, stems_a: frozenset[str], norm_b: str, stems_b: frozenset[str]) -> float:
    """Blend stem/character similarity; preserve a substantive verbatim duty extended in one edition."""
    shorter, longer = (norm_a, norm_b) if len(norm_a) <= len(norm_b) else (norm_b, norm_a)
    if len(shorter) >= 80 and shorter in longer:
        return 0.96
    return 0.5 * dice(stems_a, stems_b) + 0.5 * sequence_ratio(norm_a, norm_b)
