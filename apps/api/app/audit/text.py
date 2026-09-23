"""Source-text predicates and matching-only lexical normalisation.

Neither matching nor governance classification rewrites stored clause text:
normalised forms are used for comparison, never published as quotes.
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

# A governance clause remains source evidence, but is not an ongoing function.
# Match the statement, not just a topic word: a duty may itself concern orders
# or reorganisation. The parser supplies ancestor headings for context.
_UNIT_SUBJECT = (
    r"(?:отдел\w*|служб\w*|управлени\w*|департамент\w*|центр\w*|"
    r"дирекци\w*|сектор\w*|подразделени\w*|групп\w*|комитет\w*|"
    r"блок\w*|(?-i:[А-ЯЁA-Z]{2,8}))"
)
_STRUCTURAL_EVENT = re.compile(
    rf"^(?:на\s+основании\s+(?:приказа|распоряжения)\b[^.;!?]{{0,120}}?\s+)?"
    rf"{_UNIT_SUBJECT}\b[^.;!?]{{0,180}}\b"
    r"(?:переименован[аыо]?|реорганизован[аыо]?|преобразован[аыо]?|"
    r"разделен[аыо]?|объединен[аыо]?|создан[аыо]?|образован[аыо]?|"
    r"упразднен[аыо]?|ликвидирован[аыо]?|"
    r"сохранен[аыо]?\s+без\s+изменени\w*)\b", re.IGNORECASE,
)
_SUCCESSION = re.compile(
    rf"^{_UNIT_SUBJECT}\b[^.;!?]{{0,140}}\bявляется\s+правопреемником\b", re.IGNORECASE,
)
_COMPLETENESS = re.compile(
    r"^(?:настоящ\w*|данн\w*)\s+(?:приложени\w*|комплект\w*|документ\w*|"
    r"положени\w*)\b[^.;!?]{0,140}\b(?:полный|исчерпывающий)\s+перечень\b",
    re.IGNORECASE,
)
_GOVERNANCE_HEADING = re.compile(
    r"\b(?:распорядительн\w*\s+(?:основани\w*|документ\w*|акт\w*)|"
    r"реорганизаци\w*|организационн\w*\s+изменени\w*)\b", re.IGNORECASE,
)
_TRANSFER = re.compile(
    r"^[^.;!?]{0,180}\bпередан[аыо]?\s+из\s+[^.;!?]{1,100}\bв\s+\S+",
    re.IGNORECASE,
)
_ORDER_BASIS = re.compile(
    r"^(?:(?:настоящ\w*\s+)?(?:положени\w*|регламент\w*|приложени\w*|"
    r"штатное\s+расписание|организационн\w*\s+структур\w*)\b"
    r"[^.;!?]{0,160}\b(?:утвержден[аыо]?|введен[аыо]?\s+в\s+действие)\b|"
    r"(?:приказ|распоряжение)\s+(?:об?\s+|№\s*)[^.;!?]{1,160})",
    re.IGNORECASE,
)
_ONGOING_DUTY = re.compile(
    r"\b(?:вед[её]т|проводит|обеспечивает|осуществляет|исполняет|готовит|"
    r"составляет|согласует|проверяет|регистрирует|разрабатывает|"
    r"поддерживает|утверждает|принимает|организует|реорганизует)\b",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    """Lower-case, fold ё, drop punctuation and collapse whitespace."""
    lowered = text.lower().replace("ё", "е")
    return " ".join(_WORD.findall(lowered))


def collapse_ws(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def is_governance_statement(text: str, ancestors: list[str]) -> bool:
    """Identify an explicit organisational decision or annex declaration, not a duty.

    Ancestors can support an order/transfer reading, but cannot turn an
    operational sentence about maintaining orders into governance on their own.
    Source text and clause identity are untouched; the parser decides its kind.
    """
    statement = collapse_ws(text).replace("ё", "е").replace("Ё", "Е")
    if not statement or _ONGOING_DUTY.search(statement):
        return False
    if _STRUCTURAL_EVENT.search(statement) or _SUCCESSION.search(statement):
        return True
    if _COMPLETENESS.search(statement):
        return True
    if any(_GOVERNANCE_HEADING.search(ancestor) for ancestor in ancestors):
        return bool(_TRANSFER.search(statement) or _ORDER_BASIS.search(statement))
    return False


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
