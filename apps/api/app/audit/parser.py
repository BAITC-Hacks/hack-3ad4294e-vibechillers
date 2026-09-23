"""Hierarchical regulation parser over ingested ``ParsedDoc.pages``.

Input is the kit's page list (``[{"page": int, "text": str}]``); for DOCX a page
is one body block, for TXT the whole file. Every line becomes at least one
clause, so no source span is dropped: numbered clauses (``2.4.1.``), lettered
sub-clauses (``а.``) and unlabelled blocks (``@p<ordinal>``). Numeric markers
embedded after a sentence end are split out when they continue the current
numbering (``... направления. 3.10.Рабочие места ...``).

Clause text is the source span after its marker with surrounding whitespace
trimmed; ``label`` keeps the literal marker. Quotes are cut from this text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Citation, Clause, Document, ParseResult, Unit
from .text import normalize, stems

_NUM_START = re.compile(r"^(?P<label>(?P<path>\d{1,3}(?:\.\d{1,3})*)\.)(?=\s|[^\d\s.])")
_LETTER_START = re.compile(r"^(?P<label>(?P<letter>[а-яё])[.)])(?:\s+|(?=[А-ЯЁ]))")
# A numeric marker inside a line: after sentence-ending punctuation, followed by a capitalised word.
_NUM_EMBEDDED = re.compile(
    r"(?<=[.;:!?)»])\s+(?P<label>(?P<path>\d{1,3}(?:\.\d{1,3})*)\.)\s*(?=[А-ЯЁA-Z])"
)
# "п. 3." / "No 7." style cross-references are not clause markers.
_REF_BEFORE = re.compile(
    r"(?<!\w)(?:п|пп|ст|ч|гл|разд|пункт\w*|подпункт\w*|раздел\w*|№|No)\.?\s*$", re.IGNORECASE
)
_TOC_TITLE = re.compile(r"^(оглавление|содержание)\s*$", re.IGNORECASE)
_TOC_ENTRY_TAIL = re.compile(r"\s\d{1,4}\s*$")

# A list-introducing clause about composition or subordination is org structure.
_COMPOSITION = re.compile(r"состо[ия]т\s+из|входят\s+следующ|в\s+состав\s+\S+\s+входят", re.IGNORECASE)
_SUBORDINATION = re.compile(r"подчиня[ею]тся|в\s+составе\s+следующих\s+должностей", re.IGNORECASE)

# Depth-1 clauses are section headings unless their block carries substantive body text.
_HEADING_BODY_LIMIT = 200

_UNIT_WORDS = r"(?:Блок|Департамент|Управлени|Отдел|Служб|Центр|Дирекци|Комитет|Сектор|Групп|Подразделени)"
_ABBR_DEF = re.compile(
    r"(?P<name>" + _UNIT_WORDS + r"[^():;,]{0,80}?)\s*\((?:далее\s*[-–—]?\s*)?(?P<abbr>[А-ЯЁA-Z][^()]{0,40}?)\)"
)
_WORKERS_OF = re.compile(r"работник\w*\s+(?P<abbr>[А-ЯЁA-Z][А-ЯЁA-Z-]+)\b")


@dataclass
class _Segment:
    label: str
    kind: str  # "num" | "letter" | "plain" | "toc"
    path: tuple[int, ...] | None
    letter: str | None
    text: str


def _parse_path(raw: str) -> tuple[int, ...]:
    return tuple(int(part) for part in raw.split("."))


def _is_successor(candidate: tuple[int, ...], current: tuple[int, ...] | None) -> bool:
    """True when `candidate` is the first child or a next sibling at some level of `current`."""
    if current is None:
        return candidate == (1,)
    if candidate == current + (1,):
        return True
    for level in range(len(current)):
        if candidate == current[:level] + (current[level] + 1,):
            return True
    return False


def _split_embedded(label: str, kind: str, path, letter, body: str, current):
    """Split `body` at embedded numeric markers that continue the numbering."""
    segments: list[_Segment] = []
    start = 0
    head_label, head_kind, head_path, head_letter = label, kind, path, letter
    running = path if path is not None else current
    for match in _NUM_EMBEDDED.finditer(body):
        candidate = _parse_path(match.group("path"))
        if not _is_successor(candidate, running) or _REF_BEFORE.search(body[: match.start()]):
            continue
        segments.append(_Segment(head_label, head_kind, head_path, head_letter, body[start : match.start()].strip()))
        head_label, head_kind, head_path, head_letter = match.group("label"), "num", candidate, None
        running = candidate
        start = match.end()
    segments.append(_Segment(head_label, head_kind, head_path, head_letter, body[start:].strip()))
    return segments, running


def _segments(pages: list[dict]) -> tuple[list[_Segment], int]:
    """Turn page texts into labelled segments; returns (segments, embedded_split_count)."""
    out: list[_Segment] = []
    current: tuple[int, ...] | None = None
    in_toc = False
    embedded = 0
    for page in pages:
        for raw_line in str(page.get("text") or "").splitlines():
            line = raw_line.strip().lstrip("\ufeff").strip()
            if not line:
                continue
            if _TOC_TITLE.match(line):
                in_toc = True
                out.append(_Segment("", "plain", None, None, line))
                continue
            num = _NUM_START.match(line)
            if in_toc:
                if num and _TOC_ENTRY_TAIL.search(line):
                    out.append(_Segment(num.group("label"), "toc", _parse_path(num.group("path")), None,
                                        line[num.end():].strip()))
                    continue
                in_toc = False
            if num:
                path = _parse_path(num.group("path"))
                segs, current = _split_embedded(num.group("label"), "num", path, None, line[num.end():], current)
            else:
                letter = _LETTER_START.match(line)
                if letter:
                    segs, current = _split_embedded(letter.group("label"), "letter", None, letter.group("letter"),
                                                    line[letter.end():], current)
                else:
                    segs, current = _split_embedded("", "plain", None, None, line, current)
            embedded += len(segs) - 1
            out.extend(segs)
    return out, embedded


def _classify_numeric(path: tuple[int, ...], text: str) -> str:
    if not any(char.isalnum() for char in text):
        return "other"
    if len(path) == 1:
        return "function" if len(text) > _HEADING_BODY_LIMIT else "heading"
    if text.rstrip().endswith(":") and (_COMPOSITION.search(text) or _SUBORDINATION.search(text)):
        return "structure"
    return "function"


def parse_clauses(doc: str, pages: list[dict]) -> tuple[list[Clause], list[str]]:
    """Parse one document's pages into clauses with unique IDs; returns (clauses, warnings)."""
    segments, embedded = _segments(pages)
    clauses: list[Clause] = []
    used: dict[str, int] = {}
    latest_by_path: dict[tuple[int, ...], str] = {}
    kind_by_id: dict[str, str] = {}
    numeric_ctx: str | None = None  # latest numeric clause id
    labelled_ctx: str | None = None  # latest numeric or letter clause id
    toc_parent: str | None = None
    orphan_letters = 0
    unlabelled = 0
    duplicates: list[str] = []

    def unique(base: str) -> str:
        count = used.get(base, 0) + 1
        used[base] = count
        if count == 1:
            return base
        duplicates.append(f"{base}@{count}")
        return f"{base}@{count}"

    for ordinal, seg in enumerate(segments, start=1):
        if seg.kind == "num":
            base = ".".join(str(p) for p in seg.path)
            clause_id = unique(base)
            parent_id = latest_by_path.get(seg.path[:-1]) if len(seg.path) > 1 else None
            kind = _classify_numeric(seg.path, seg.text)
            # A new numeric clause closes every deeper open level.
            for key in [k for k in latest_by_path if len(k) > len(seg.path)]:
                del latest_by_path[key]
            latest_by_path[seg.path] = clause_id
            numeric_ctx = labelled_ctx = clause_id
            toc_parent = None
        elif seg.kind == "letter" and numeric_ctx is not None:
            clause_id = unique(f"{numeric_ctx}/{seg.letter}")
            parent_id = numeric_ctx
            kind = "structure" if kind_by_id.get(numeric_ctx) == "structure" else "function"
            labelled_ctx = clause_id
        elif seg.kind == "toc":
            base = ".".join(str(p) for p in seg.path)
            clause_id = unique(base)
            parent_id = toc_parent
            kind = "other"
        else:
            if seg.kind == "letter":
                orphan_letters += 1
            else:
                unlabelled += 1
            clause_id = f"@p{ordinal}"
            used[clause_id] = 1
            parent_id = labelled_ctx
            kind = "other"
            if _TOC_TITLE.match(seg.text):
                toc_parent = clause_id
                kind = "heading"
        kind_by_id[clause_id] = kind
        clauses.append(
            Clause(doc=doc, clause_id=clause_id, label=seg.label, parent_id=parent_id, text=seg.text,
                   ordinal=ordinal, kind=kind, unit_ids=[])
        )

    warnings: list[str] = []
    if not any(c.kind == "function" for c in clauses):
        warnings.append(f"{doc}: no numbered function clauses were recognised; the document cannot be compared.")
    if embedded:
        warnings.append(f"{doc}: {embedded} numbered clause(s) were split out of a shared text block.")
    if unlabelled:
        warnings.append(f"{doc}: {unlabelled} unlabelled block(s) kept as kind=other and excluded from alignment.")
    empty_numbered = [
        c.clause_id for c in clauses
        if c.label and c.kind == "other" and not any(char.isalnum() for char in c.text)
    ]
    if empty_numbered:
        shown = ", ".join(empty_numbered[:10])
        warnings.append(
            f"{doc}: {len(empty_numbered)} numbered marker(s) have no function text "
            f"and were excluded from alignment: {shown}."
        )
    if orphan_letters:
        warnings.append(f"{doc}: {orphan_letters} lettered block(s) had no numbered parent; kept as kind=other.")
    if duplicates:
        shown = ", ".join(duplicates[:10]) + (" …" if len(duplicates) > 10 else "")
        warnings.append(f"{doc}: repeated clause numbers disambiguated as {shown}.")
    return clauses, warnings


def _quote_name(text: str) -> str:
    return text.strip().rstrip(".;, ").strip()


def extract_units(doc: str, clauses: list[Clause]) -> list[Unit]:
    """Units and roles with explicit textual evidence; mutates ``Clause.unit_ids``.

    - ``Name (далее - ABBR)`` / ``Name (ABBR)`` with a unit keyword defines a unit.
    - Children of a composition clause (``X состоит из ...:``) are units whose parent is X.
    - Children of a subordination clause naming ``работники ABBR`` are roles of ABBR.
    Parent links are set only from such explicit wording, otherwise null.
    """
    units: list[Unit] = []
    by_key: dict[str, Unit] = {}
    ids: set[str] = set()
    children: dict[str, list[Clause]] = {}
    for clause in clauses:
        if clause.parent_id is not None:
            children.setdefault(clause.parent_id, []).append(clause)

    def new_id(clause_id: str) -> str:
        unit_id, n = clause_id, 1
        while unit_id in ids:
            n += 1
            unit_id = f"{clause_id}#{n}"
        ids.add(unit_id)
        return unit_id

    def add(clause: Clause, name: str, kind: str, key: str, parent_unit_id: str | None,
            quote: str | None = None) -> Unit:
        unit = Unit(doc=doc, unit_id=new_id(clause.clause_id), name=name, kind=kind,
                    parent_unit_id=parent_unit_id,
                    citations=[Citation(doc=doc, clause_id=clause.clause_id, quote=quote or name)])
        units.append(unit)
        if key and key not in by_key:
            by_key[key] = unit
        return unit

    structure_ids = {c.clause_id for c in clauses if c.kind == "structure"}
    # Pass 1: abbreviation definitions outside structure lists.
    for clause in clauses:
        if clause.kind == "structure" or clause.parent_id in structure_ids:
            continue
        for match in _ABBR_DEF.finditer(clause.text):
            abbr = match.group("abbr").strip()
            if abbr in by_key:
                continue
            name = match.group("name").strip()
            # Name carries the abbreviation so unit_key() resolves it; the quote stays verbatim.
            add(clause, f"{name} ({abbr})", "unit", abbr, None, quote=match.group(0).strip())

    # Pass 2: enumerated composition / subordination lists.
    for clause in clauses:
        if clause.kind != "structure":
            continue
        is_roles = bool(_SUBORDINATION.search(clause.text)) and not _COMPOSITION.search(clause.text)
        parent_unit: Unit | None = None
        if is_roles:
            owner = _WORKERS_OF.search(clause.text)
            if owner:
                parent_unit = by_key.get(owner.group("abbr"))
        else:
            head = _COMPOSITION.split(clause.text, maxsplit=1)[0]
            parent_unit = next((u for k, u in by_key.items() if re.search(rf"(?<!\w){re.escape(k)}(?!\w)", head)), None)
        for child in children.get(clause.clause_id, []):
            if child.kind != "structure":
                continue
            name = _quote_name(child.text)
            if not name:
                continue
            abbr_match = re.search(r"\(([А-ЯЁA-Z][А-ЯЁA-Z-]+)\)", name)
            key = abbr_match.group(1) if abbr_match else ""
            existing = by_key.get(key) if key else None
            if existing is not None and existing.kind == "unit" and not is_roles:
                # Pass 1 already recorded it from a (далее ...) phrase; the list is the defining clause.
                units.remove(existing)
                ids.discard(existing.unit_id)
                del by_key[key]
            unit = add(child, name, "role" if is_roles else "unit", key,
                       parent_unit.unit_id if parent_unit else None)
            child.unit_ids = [unit.unit_id]

    _attach_unit_ids(clauses, units)
    return units


def unit_key(unit: Unit) -> str:
    """Cross-document identity of a unit: its abbreviation if present, else its normalised name."""
    match = re.search(r"\(([А-ЯЁA-Z][А-ЯЁA-Z-]+)\)\s*$", unit.name)
    if match:
        return match.group(1)
    quote = unit.citations[0].quote if unit.citations else unit.name
    return normalize(quote)


def _attach_unit_ids(clauses: list[Clause], units: list[Unit]) -> None:
    """Attach explicitly named units and inherit the nearest named owner."""
    patterns: list[tuple[str, re.Pattern]] = []
    spelled: list[tuple[Unit, frozenset[str]]] = []
    for unit in units:
        if unit.kind != "unit":
            continue
        token = unit_key(unit)
        if re.fullmatch(r"[А-ЯЁA-Z][А-ЯЁA-Z-]+", token):
            patterns.append((unit.unit_id, re.compile(rf"(?<!\w){re.escape(token)}(?!\w)")))
        terms = stems(unit.name.split("(", 1)[0])
        if len(terms) >= 3:
            spelled.append((unit, terms))

    by_id = {c.clause_id: c for c in clauses}
    own: dict[str, list[str]] = {}
    for clause in clauses:
        named = [uid for uid, pat in patterns if pat.search(clause.text)]
        if re.match(r"^(?:Директор|Руководитель|Начальник)\b", clause.text, re.IGNORECASE):
            heading_terms = stems(clause.text)
            matches = [unit for unit, terms in spelled if terms <= heading_terms]
            if len(matches) == 1 and matches[0].unit_id not in named:
                named.append(matches[0].unit_id)
        own[clause.clause_id] = named
    for clause in clauses:
        found = list(dict.fromkeys(clause.unit_ids + own[clause.clause_id]))
        parent = by_id.get(clause.parent_id) if clause.parent_id else None
        while parent is not None:
            if own.get(parent.clause_id):
                found.extend(u for u in own[parent.clause_id] if u not in found)
                break
            parent = by_id.get(parent.parent_id) if parent.parent_id else None
        clause.unit_ids = found


def owner_keys(clause: Clause, clauses_by_id: dict[str, Clause], units_by_id: dict[str, Unit]) -> frozenset[str]:
    """Unit keys named by the clause's nearest ancestor: the owner context of a function."""
    parent = clauses_by_id.get(clause.parent_id) if clause.parent_id else None
    while parent is not None:
        keys = [unit_key(units_by_id[u]) for u in parent.unit_ids if u in units_by_id]
        if keys:
            return frozenset(keys)
        parent = clauses_by_id.get(parent.parent_id) if parent.parent_id else None
    return frozenset()


def parse_document(document: Document, pages: list[dict]) -> ParseResult:
    """Clauses, units and parse warnings for one ingested document."""
    clauses, warnings = parse_clauses(document.doc, pages)
    units = extract_units(document.doc, clauses)
    return ParseResult(clauses=clauses, units=units, warnings=warnings)


def parse_documents(documents: list[Document], pages_by_doc: dict[str, list[dict]]) -> ParseResult:
    """Parse every document; a document without pages yields a warning, not an exception."""
    result = ParseResult()
    for document in documents:
        pages = pages_by_doc.get(document.doc)
        if pages is None:
            result.warnings.append(f"{document.doc}: no ingested pages were supplied; document skipped.")
            continue
        parsed = parse_document(document, pages)
        result.clauses.extend(parsed.clauses)
        result.units.extend(parsed.units)
        result.warnings.extend(parsed.warnings)
    return result
