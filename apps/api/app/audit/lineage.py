"""Conservative, source-backed unit lineage and after-edition responsibility risks.

The parser owns extraction and ``align_functions`` owns function statuses. This
module consumes their clauses, units and structural findings; it never turns a
mention into a unit, changes a Finding, or treats lexical similarity as proof of
identity. A rejected/uncertain inference stays reviewable rather than becoming
an invented predecessor, loss, duplication or legal conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from .align import _governing_context
from .citations import check_citation, cite_context, clause_index
from .models import Citation, Clause, ClauseRef, Document, Finding, Risk, Unit, UnitChange, UnitRef
from .parser import owner_keys, unit_key
from .text import dice, normalize, sequence_ratio, stems

_Key = tuple[str, str]
_ALIAS = re.compile(r"\(([А-ЯЁA-Z][А-ЯЁA-Z-]+)\)\s*$")
_SPLIT = re.compile(r"\b(?:раздел\w*|выдел\w*|разукрупн\w*)\b", re.I)
_MERGE = re.compile(r"\b(?:объедин\w*|слиян\w*|слит\w*|укрупн\w*)\b", re.I)
_RENAME = re.compile(r"\b(?:переимен\w*|преобраз\w*|реорганиз\w*)\b", re.I)
_SCOPE = re.compile(
    r"\b(?:в области|по вопросам|в части|в отношении|в рамках|по направлению|в пределах)\s+([^.;:\n]+)",
    re.I,
)
_GOVERNING = re.compile(
    r"\b(?:долж\w*|обязан\w*|вправе|разреш\w*|запрещ\w*|делегир\w*|"
    r"возлага\w*|поруча\w*|отвеча\w*|ответствен\w*|подчиня\w*)\b", re.I,
)
_COOPERATION = re.compile(r"\b(?:участву\w*|участи\w*|совместно|содейств\w*|взаимодейств\w*|по\s+согласованию)\b", re.I)
_EXECUTE = {
    "ведение": re.compile(r"\b(?:ведени\w*|вед[её]т|ведут|вести)\b", re.I),
    "подготовка": re.compile(r"\b(?:подготовк\w*|подготавлива(?:ет|ют|ть)|подготов(?:ить|ит|ят)|составлени\w*|составля(?:ет|ют|ть)|состав(?:ить|ит|ят))\b", re.I),
    "разработка": re.compile(r"\b(?:разработк\w*|разрабатыва(?:ет|ют|ть)|разработ(?:ать|ает|ают)|формировани\w*|формиру(?:ет|ют|ть))\b", re.I),
    "исполнение": re.compile(r"\b(?:исполнени\w*|исполня(?:ет|ют|ть)|выполнени\w*|выполня(?:ет|ют|ть)|проведени\w*|провод(?:ит|ят|ить))\b", re.I),
    "регистрация": re.compile(r"\b(?:регистраци\w*|регистриру(?:ет|ют|ть)|учитыва(?:ет|ют|ть))\b", re.I),
    "оформление": re.compile(r"\b(?:оформлени\w*|оформля(?:ет|ют|ть)|обработк\w*|обрабатыва(?:ет|ют|ть)|внос(?:ит|ят|ить))\b", re.I),
    "выбор": re.compile(r"\b(?:выбор\w*|выбира(?:ет|ют|ть))\b", re.I),
}
_REVIEW = re.compile(r"\b(?:проверк\w*|проверя\w*|проверит\w*|сверк\w*|сверя\w*|ревизи\w*|аудит(?:а|у|ом|ы|е)?)\b", re.I)
_CONTROL_WORK = re.compile(
    r"\bконтрол\w*(?:\s+\S+){0,3}\s+(?:исполнени\w*|выполнени\w*|результат\w*|"
    r"правильност\w*|качеств\w*)\b", re.I,
)
_WORK_PRODUCT = re.compile(
    r"\b(?:реестр\w*|отч[её]т\w*|плат[её]ж\w*|операци\w*|результат\w*|акт(?:а|ы|ов|ом|е|ам|ами|ах)?|документ\w*|"
    r"договор\w*|заявк\w*|запис\w*|смет\w*|проект\w*|план\w*|бюджет\w*|решени\w*)\b", re.I,
)
_GENERIC = stems(
    "блок департамент управление отдел служба центр дирекция комитет сектор группа "
    "подразделение организация осуществление обеспечение функция задача работа "
    "деятельность контроль проверка проведение ведение подготовка разработка "
    "формирование исполнение регистрация оформление сотрудник ответственность"
)
_UNIT_TYPES = stems("блок департамент управление отдел служба центр дирекция комитет сектор группа подразделение структурное")
_UNSUPPORTED_LEGAL = re.compile(r"\b(?:доказан\w*|незакон\w*|наруш\w*\s+закон\w*|винов\w*)\b", re.I)


def _key(ref: Unit | UnitRef | Clause | ClauseRef | Citation) -> _Key:
    if isinstance(ref, (Unit, UnitRef)):
        return ref.doc, ref.unit_id
    return ref.doc, ref.clause_id


def _ref(unit: Unit) -> UnitRef:
    return UnitRef(doc=unit.doc, unit_id=unit.unit_id)


def _clause_ref(clause: Clause) -> ClauseRef:
    return ClauseRef(doc=clause.doc, clause_id=clause.clause_id)


def _id(prefix: str, kind: str, refs: list[UnitRef | ClauseRef]) -> str:
    identity = "|".join((kind, *sorted(
        f"{r.doc}:{r.unit_id if isinstance(r, UnitRef) else r.clause_id}" for r in refs
    )))
    return prefix + sha256(identity.encode("utf-8")).hexdigest()[:12]


def _unique_citations(citations: list[Citation]) -> list[Citation]:
    return list({(c.doc, c.clause_id, c.quote): c for c in citations}.values())


def _name(unit: Unit) -> str:
    return normalize(_ALIAS.sub("", unit.name).strip())


def _alias(unit: Unit) -> str | None:
    match = _ALIAS.search(unit.name)
    return match.group(1) if match else None


def _mentions(unit: Unit, text: str) -> bool:
    full = _name(unit)
    content = " " + normalize(text) + " "
    if full and " " + full + " " in content:
        return True
    alias = _alias(unit)
    return bool(alias and re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text))


def _distinct_name(unit: Unit) -> bool:
    """A type alone is ambiguous; its qualifier is part of a full unit name."""
    return bool(stems(_name(unit)) - _UNIT_TYPES)


def _active_verb(text: str, match: re.Match[str]) -> bool:
    """Do not infer an assigned duty from a local denial or prohibition."""
    lead = text[max(0, match.start() - 48):match.start()]
    return not re.search(r"\b(?:не|нельзя|запрещено|без права)\s+(?:\w+\s+){0,2}$", lead, re.I)


def _shared_product(first: Clause, second: Clause) -> bool:
    def products(text: str) -> set[str]:
        return {normalize(match.group())[:3 if match.group().lower().startswith("акт") else 4]
                for match in _WORK_PRODUCT.finditer(text)}

    return bool(products(first.text) & products(second.text))


@dataclass
class _Domain:
    documents: list[Document]
    clauses: list[Clause]
    units: list[Unit]
    findings: list[Finding]

    def __post_init__(self) -> None:
        self.by_clause = clause_index(self.clauses)
        self.by_unit = {_key(u): u for u in self.units}
        self.edition = {d.doc: d.edition for d in self.documents}
        self.by_doc_clause: dict[str, dict[str, Clause]] = {}
        self.by_doc_unit: dict[str, dict[str, Unit]] = {}
        for clause in self.clauses:
            self.by_doc_clause.setdefault(clause.doc, {})[clause.clause_id] = clause
        for unit in self.units:
            self.by_doc_unit.setdefault(unit.doc, {})[unit.unit_id] = unit
        self.structural = {
            _key(u): u for u in self.units if u.kind == "unit" and self.definition(u) is not None
        }
        self.before = [u for u in self.structural.values() if self.edition.get(u.doc) == "before"]
        self.after = [u for u in self.structural.values() if self.edition.get(u.doc) == "after"]
        self.before.sort(key=self.unit_order)
        self.after.sort(key=self.unit_order)

    def unit_order(self, unit: Unit) -> tuple[str, int, str]:
        definition = self.definition(unit)
        return unit.doc, definition.ordinal if definition else 0, unit.unit_id

    def definition(self, unit: Unit) -> Clause | None:
        for citation in unit.citations:
            source = self.by_clause.get(_key(citation))
            if (source is not None and source.kind == "structure" and source.doc == unit.doc
                    and check_citation(citation, self.by_clause) is None and _mentions(unit, citation.quote)):
                return source
        return None

    def evidence(self, selected: list[Unit], *, extra: Citation | None = None,
                 refs: list[ClauseRef] | None = None) -> list[Citation]:
        citations = [c for u in selected for c in u.citations
                     if self.definition(u) is not None and check_citation(c, self.by_clause) is None
                     and _mentions(u, c.quote)]
        for unit in selected:
            parent = self.by_unit.get((unit.doc, unit.parent_unit_id)) if unit.parent_unit_id else None
            if parent is not None:
                citations.extend(c for c in parent.citations if check_citation(c, self.by_clause) is None)
        if refs:
            citations.extend(cite_context(refs, self.by_clause, self.by_unit))
        if extra is not None:
            citations.append(extra)
        return _unique_citations(citations)

    def parent(self, unit: Unit) -> Unit | None:
        return self.by_unit.get((unit.doc, unit.parent_unit_id)) if unit.parent_unit_id else None

    def parent_changed(self, old: Unit, new: Unit) -> bool:
        before, after = self.parent(old), self.parent(new)
        return before is not None and after is not None and _name(before) != _name(after)

    def parent_uncertain(self, old: Unit, new: Unit) -> bool:
        before, after = self.parent(old), self.parent(new)
        return (before is None) != (after is None) or (
            before is not None and after is not None
            and (not _distinct_name(before) or not _distinct_name(after))
        )

    def unique_identity(self, old: Unit, new: Unit) -> bool:
        return (_name(old) == _name(new) and _distinct_name(old)
                and sum(_name(u) == _name(old) for u in self.before) == 1
                and sum(_name(u) == _name(new) for u in self.after) == 1)

    def structural_candidates(self, after: Unit) -> list[Unit]:
        """Inspect aligner's offered structural refs, not its lexical prose."""
        source = self.definition(after)
        if source is None:
            return []
        candidate_ids = {
            _key(ref) for f in self.findings for ref in f.before
            if any(_key(r) == _key(source) for r in f.after)
            and all(self.by_clause.get(_key(r), source).kind == "structure" for r in f.before + f.after)
        }
        return [u for u in self.before if _key(self.definition(u)) in candidate_ids]

    def predecessors(self, after: Unit) -> list[Unit]:
        """Full run-local review: structure, names, transitions and substantial transferred duties.

        Similarity and duty transfer are abstention triggers, never proofs of
        organisational identity. Do not turn a missing transfer statement into
        a created unit if the source still raises a plausible predecessor.
        """
        candidates = {_key(u): u for u in self.structural_candidates(after)}
        after_duties = [c for c in self.clauses if c.doc == after.doc and c.kind == "function"
                        and after.unit_id in c.unit_ids]
        signatures = [(c, stems(c.text) - _GENERIC) for c in after_duties]
        for old in self.before:
            if (_name(old) == _name(after) or _alias(old) and _alias(old) == _alias(after)
                    or len(_name(old)) > 10 and sequence_ratio(_name(old), _name(after)) >= .86):
                candidates[_key(old)] = old
            if signatures:
                old_duties = [c for c in self.clauses if c.doc == old.doc and c.kind == "function"
                              and old.unit_id in c.unit_ids]
                if any(len(a_words & b_words) >= 2 and dice(a_words, b_words) >= .8
                       for _, a_words in signatures if len(a_words) >= 2
                       for b_words in (stems(b.text) - _GENERIC for b in old_duties)):
                    candidates[_key(old)] = old
        for clause in self.clauses:
            if self.edition.get(clause.doc) not in ("before", "after") or not _mentions(after, clause.text):
                continue
            if _transition_kind(clause.text) is not None:
                for old in self.before:
                    if _mentions(old, clause.text):
                        candidates[_key(old)] = old
        return sorted(candidates.values(), key=self.unit_order)


def _transition_kind(text: str) -> str | None:
    if re.search(r"\b(?:не|нельзя|запрещ\w*|планир\w*|возможн\w*|предлага\w*)\b", text, re.I):
        return None
    if _SPLIT.search(text):
        return "split"
    if _MERGE.search(text):
        return "merge"
    if _RENAME.search(text):
        return "rename"
    return None


def _transition(d: _Domain, before: list[Unit], after: list[Unit],
                citations: list[Citation] | None = None) -> Citation | None:
    if not before or not after:
        return None
    for clause in d.clauses:
        if d.edition.get(clause.doc) not in ("before", "after"):
            continue
        for sentence in re.split(r"(?<=[.;])\s+|\n", clause.text):
            kind = _transition_kind(sentence)
            if kind is None:
                continue
            if len(before) > 1 and len(after) == 1 and kind != "merge":
                continue
            if len(before) == 1 and len(after) > 1 and kind != "split":
                continue
            if len(before) > 1 and len(after) > 1 and kind != "rename":
                continue
            if len(before) == len(after) == 1 and kind in ("split", "merge"):
                continue
            action = {"split": _SPLIT, "merge": _MERGE, "rename": _RENAME}[kind].search(sentence)
            if action is None:
                continue
            left, right = sentence[:action.start()], sentence[action.end():]
            # A list of names near the word \"reorganisation\" is not an
            # assignment. Require old endpoints before the transition and new
            # endpoints after an explicit directional preposition.
            if not re.match(r"^\s*(?:в|во|на|из)\b", right, re.I):
                continue
            if not all(_mentions(unit, left) for unit in before):
                continue
            if not all(_mentions(unit, right) for unit in after):
                continue
            selected = {_key(u) for u in before + after}
            if any(_key(u) not in selected and (_mentions(u, left) or _mentions(u, right))
                   for u in d.before + d.after):
                continue
            witness = Citation(doc=clause.doc, clause_id=clause.clause_id, quote=sentence)
            if citations is None:
                return witness
            if any(c.doc == witness.doc and c.clause_id == witness.clause_id
                   and sentence in c.quote for c in citations):
                return witness
    return None


def _reason_names(reason: str, selected: list[Unit]) -> bool:
    if not reason.strip():
        return False
    mentioned = stems(reason)
    return all(bool((stems(_name(u)) - _GENERIC) & mentioned) or _name(u) in normalize(reason)
               or bool(_alias(u) and _alias(u).lower() in normalize(reason).split())
               for u in selected)


def validate_unit_change(
    change: UnitChange, documents: list[Document], clauses: list[Clause], units: list[Unit],
    *, reviewed_predecessors: bool = False,
) -> str | None:
    """Reject unsupported unit proposals; ``None`` means validated.

    ``reviewed_predecessors`` is an assertion by the caller that a real,
    exhaustive search of this run's before structural units has been performed.
    It must not be set merely because model prose says it searched. The
    independent full-set checks below still reject a missed candidate.
    """
    d = _Domain(documents, clauses, units, [])
    if not change.id.strip():
        return "unit change has no id"
    if not change.before and not change.after:
        return "unit change has no structural unit references"
    if len({_key(r) for r in change.before}) != len(change.before) or len({_key(r) for r in change.after}) != len(change.after):
        return "repeated unit reference"
    if any(_key(r) not in d.structural for r in change.before + change.after):
        return "unit reference is not an explicitly defined structural unit"
    if any(d.edition.get(r.doc) != "before" for r in change.before) or any(d.edition.get(r.doc) != "after" for r in change.after):
        return "unit reference belongs to the wrong edition"
    before = [d.structural[_key(r)] for r in change.before]
    after = [d.structural[_key(r)] for r in change.after]
    selected = before + after
    if not _reason_names(change.reason, selected):
        return "reason does not identify the cited structural units"
    if change.status != "retained" and not change.review_required:
        return "uncertain or changed unit lineage requires human review"
    if change.status == "unresolved" and not re.search(
            r"не\s+(?:установ|подтвержд|найден)|возможн|требует проверки|неясн", change.reason, re.I):
        return "unresolved reason must disclose that identity is not established"
    if not change.citations:
        return "unit change has no source citations"
    for citation in change.citations:
        problem = check_citation(citation, d.by_clause)
        if problem is not None:
            return problem
        if not any(citation.doc == unit.doc and _mentions(unit, citation.quote)
                   and any(_key(citation) == _key(source) for source in unit.citations)
                   and d.by_clause[_key(citation)].kind == "structure"
                   for unit in selected) and not (
            _transition(d, before, after, [citation]) is not None
            or any(d.parent(unit) is not None and citation.doc == unit.doc
                   and any(c.doc == citation.doc and c.clause_id == citation.clause_id
                           and c.quote in citation.quote and _mentions(d.parent(unit), citation.quote)
                           for c in d.parent(unit).citations) for unit in selected)
        ):
            return "citation is unrelated to the named units or their structural change"
    for unit in selected:
        definition = d.definition(unit)
        if not any(c.doc == unit.doc and c.clause_id == definition.clause_id
                   and _mentions(unit, c.quote) for c in change.citations):
            return f"missing defining citation for {unit.doc}:{unit.unit_id}"
    if change.status == "retained":
        if len(before) != 1 or len(after) != 1 or not d.unique_identity(before[0], after[0]):
            return "retained needs unique, source-defined full-name identity, not acronym or generic name"
        if d.parent_changed(before[0], after[0]) or d.parent_uncertain(before[0], after[0]):
            return "changed or missing explicit parent cannot support unchanged retention"
    elif change.status == "reorganised":
        if not before or not after:
            return "reorganised needs predecessors and successors"
        if len(before) == len(after) == 1 and d.unique_identity(before[0], after[0]) and d.parent_uncertain(before[0], after[0]):
            return "source does not establish a comparable, distinctive parent hierarchy"
        if len(before) == len(after) == 1 and d.unique_identity(before[0], after[0]) and d.parent_changed(before[0], after[0]):
            for unit in (before[0], after[0]):
                parent = d.parent(unit)
                if not any(c.doc == parent.doc and c.clause_id == source.clause_id
                           and _mentions(parent, c.quote) for source in
                           (d.by_clause.get(_key(parent_c)) for parent_c in parent.citations)
                           if source is not None
                           for c in change.citations):
                    return "changed parent needs both parent definitions cited"
        elif _transition(d, before, after, change.citations) is None:
            return "rename, split or merge lacks a cited, directional transition naming every endpoint"
    elif change.status == "created":
        if before or len(after) != 1:
            return "created needs exactly one after unit and no before unit"
        if not reviewed_predecessors:
            return "created requires an actual run-local predecessor search"
        if not d.before:
            return "before documents contain no comparable structural units; creation is uncertain"
        predecessors = d.predecessors(after[0])
        if predecessors:
            return "possible predecessor or structural transition remains unreviewed: " + ", ".join(
                f"{u.doc}:{u.unit_id}" for u in predecessors)
    elif change.status == "unresolved":
        if not change.review_required:
            return "uncertain lineage requires human review"
        if before and after and any(_key(old) not in {_key(u) for new in after for u in d.predecessors(new)}
                                    for old in before):
            return "unrelated before/after units cannot be presented as one unresolved transition"
    else:
        return "unknown unit status"
    if _UNSUPPORTED_LEGAL.search(change.reason):
        return "reason asserts an unsupported definitive legal conclusion"
    return None


@dataclass(frozen=True)
class _Duty:
    clause: Clause
    owner: Unit
    actions: frozenset[str]
    review: bool
    object_words: frozenset[str]
    scopes: frozenset[str]
    action_targets: tuple[tuple[str, frozenset[str]], ...]


def _primary_statement(text: str) -> str:
    # A later explanation is not part of the object assigned by the first predicate.
    # Scope/restriction checks still read the complete source and its parents.
    return re.split(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z])", text, maxsplit=1)[0]


def _scope(d: _Domain, clause: Clause) -> frozenset[str]:
    scopes: set[str] = set()
    visited: set[_Key] = set()
    current: Clause | None = clause
    while current is not None and _key(current) not in visited:
        visited.add(_key(current))
        scopes.update(normalize(match.group(1)) for match in _SCOPE.finditer(current.text))
        current = d.by_clause.get((clause.doc, current.parent_id)) if current.parent_id else None
    return frozenset(scopes)


def _cooperative_context(d: _Domain, clause: Clause) -> bool:
    current: Clause | None = clause
    visited: set[_Key] = set()
    while current is not None and _key(current) not in visited:
        visited.add(_key(current))
        if _COOPERATION.search(current.text):
            return True
        current = d.by_clause.get((clause.doc, current.parent_id)) if current.parent_id else None
    return False


def _duty(d: _Domain, clause: Clause) -> _Duty | None:
    if d.edition.get(clause.doc) != "after" or clause.kind != "function":
        return None
    if any(rule in ("negation", "prohibition") for rule in _governing_context(
            clause, d.by_doc_clause.get(clause.doc, {}), d.by_doc_unit.get(clause.doc, {}))):
        return None
    if _cooperative_context(d, clause):
        return None
    owners = owner_keys(clause, d.by_doc_clause.get(clause.doc, {}), d.by_doc_unit.get(clause.doc, {}))
    if len(owners) != 1:
        return None
    matches = [u for u in d.by_doc_unit.get(clause.doc, {}).values() if unit_key(u) in owners]
    if len(matches) != 1 or not matches[0].citations:
        return None  # ambiguous title, or mere unit mention rather than an accountable owner
    owner = matches[0]
    text = _primary_statement(clause.text)
    matches = [
        (name, match) for name, pattern in _EXECUTE.items() for match in pattern.finditer(text)
        if _active_verb(text, match) and not re.search(
            r"\b(?:провер\w*|контрол\w*|свер\w*|ревизи\w*|аудит\w*|согласу\w*|утвержда\w*)\b",
            re.split(r"[;:.]", text[:match.start()])[-1], re.I,
        )
    ]
    actions = frozenset(name for name, _ in matches)
    review = any(_active_verb(text, match) for match in _REVIEW.finditer(text))
    review = review or bool(_CONTROL_WORK.search(text))
    if not actions and not review:
        return None
    owner_words = stems(owner.name)
    words = stems(text) - _GENERIC - owner_words
    targets = []
    for name, match in matches:
        phrase = re.split(r"\s+(?:и|по|в|на|согласно|после|перед|для)\b|[.,;:]",
                          text[match.end():], maxsplit=1, flags=re.I)[0]
        target = frozenset(stems(phrase) - _GENERIC - owner_words)
        if target:
            targets.append((name, target))
    for pattern in (*_EXECUTE.values(), _REVIEW):
        words -= stems(" ".join(match.group() for match in pattern.finditer(text)))
    return _Duty(clause, owner, actions, review, frozenset(words), _scope(d, clause), tuple(targets))


def _same_object(a: _Duty, b: _Duty) -> bool:
    shared = a.object_words & b.object_words
    return (len(shared) >= 2 and len(shared) / max(len(a.object_words), len(b.object_words)) >= .65
            and a.scopes == b.scopes)


def _self_review_product(execution: _Duty, review: _Duty) -> bool:
    if not execution.actions or not review.review or execution.scopes != review.scopes:
        return False
    if _same_object(execution, review) and _shared_product(execution.clause, review.clause):
        return True
    text = _primary_statement(review.clause.text)
    if not re.search(r"\bсобственн\w*|\b(?:выполненн|подготовленн|составленн)\w*\s+(?:им|ими)\b", text, re.I):
        return False
    # Explicitly reviewing one's own operation can name its direct object rather
    # than repeat the entire execution sentence (criteria, procedure, side effects).
    return any(_EXECUTE[action].search(text) and target <= review.object_words
               for action, target in execution.action_targets)


def _object_label(a: _Duty, b: _Duty) -> str:
    common = a.object_words & b.object_words
    words = (word for word in re.findall(r"[0-9a-zа-яё]+", a.clause.text, re.I)
             if stems(word) & common)
    return " ".join(list(words)[:8])


def _risk_evidence(d: _Domain, duties: list[_Duty]) -> list[Citation]:
    refs = [_clause_ref(duty.clause) for duty in duties]
    duty_keys = {_key(ref) for ref in refs}
    common = duties[0].object_words & duties[1].object_words
    evidence = [c for c in cite_context(refs, d.by_clause, d.by_unit)
                if _key(c) not in duty_keys and
                _related_risk_citation(d, c, duties, common)]
    evidence.extend(Citation(doc=duty.clause.doc, clause_id=duty.clause.clause_id,
                             quote=duty.clause.text) for duty in duties if duty.clause.text)
    return _unique_citations(evidence)


def _related_risk_citation(d: _Domain, citation: Citation, duties: list[_Duty],
                           common: frozenset[str]) -> bool:
    source = d.by_clause[_key(citation)]
    for duty in duties:
        if _key(source) == _key(duty.clause):
            # A real quote from a long clause still must state the action AND
            # the shared object. An unrelated sentence in the same clause is
            # not evidence for the claimed overlap.
            has_action = any(_EXECUTE[action].search(citation.quote) for action in duty.actions)
            has_review = duty.review and (
                _REVIEW.search(citation.quote) or _CONTROL_WORK.search(citation.quote)
            )
            object_count = len(stems(citation.quote) & common)
            # A single direct-object anchor is sufficient only for the full
            # validated duty, never for a fragment omitting self-ownership.
            return bool(common and (has_action or has_review) and (
                object_count >= 2 or (object_count == 1 and citation.quote == source.text)
            ))
        if source.doc != duty.clause.doc:
            continue
        parent = duty.clause.parent_id
        while parent is not None:
            if source.clause_id == parent:
                return bool(citation.quote == source.text and (
                    _mentions(duty.owner, citation.quote)
                    or _SCOPE.search(citation.quote)
                    or _GOVERNING.search(citation.quote)
                ))
            node = d.by_clause.get((source.doc, parent))
            parent = node.parent_id if node else None
        if any(c.doc == source.doc and c.clause_id == source.clause_id
               and c.quote in citation.quote and _mentions(duty.owner, citation.quote)
               for c in duty.owner.citations):
            return True
    return False


def validate_risk(risk: Risk, documents: list[Document], clauses: list[Clause], units: list[Unit]) -> str | None:
    """Require a source-supported actor, action and object relation in the after set."""
    d = _Domain(documents, clauses, units, [])
    if not risk.id.strip():
        return "risk has no id"
    if not risk.review_required:
        return "risk must require human review"
    if len(risk.refs) < 2 or len({_key(r) for r in risk.refs}) != len(risk.refs):
        return "risk needs distinct after-edition duty references"
    if len(risk.units) < 1 or len({_key(r) for r in risk.units}) != len(risk.units):
        return "risk needs distinct accountable unit or role references"
    if any(_key(r) not in d.by_unit or d.edition.get(r.doc) != "after" for r in risk.units):
        return "risk unit is missing or belongs to the wrong edition"
    if any(_key(r) not in d.by_clause or d.edition.get(r.doc) != "after" for r in risk.refs):
        return "risk duty is missing or belongs to the wrong edition"
    duties = [_duty(d, d.by_clause[_key(r)]) for r in risk.refs]
    if any(duty is None for duty in duties):
        return "risk must cite after-edition functions with explicit accountable actors"
    if {_key(duty.owner) for duty in duties} != {_key(unit) for unit in risk.units}:
        return "risk units must be the accountable actors, not incidental mentions or delegates"
    if risk.kind == "potential_duplication":
        if len(duties) != 2 or len(risk.units) != 2 or unit_key(duties[0].owner) == unit_key(duties[1].owner):
            return "cross-unit overlap needs two distinct accountable owners and duties"
        if not duties[0].actions.intersection(duties[1].actions) or not _same_object(*duties):
            return "no source-supported same-action, same-object and same-scope overlap"
    elif risk.kind == "potential_conflict_of_interest":
        if len(duties) != 2 or len(risk.units) != 1 or _key(duties[0].owner) != _key(duties[1].owner):
            return "self-review needs separate execution and review duties of the same accountable actor"
        execution, review = duties
        if not execution.actions or not review.review:
            execution, review = review, execution
        if not _self_review_product(execution, review):
            return "same actor's execution and review of the same work product are not evidenced"
    else:
        return "unknown risk kind"
    if not risk.reason.strip() or _UNSUPPORTED_LEGAL.search(risk.reason):
        return "risk reason is empty or asserts a definitive legal conclusion"
    common = duties[0].object_words & duties[1].object_words
    if not common.intersection(stems(risk.reason)):
        return "reason does not identify the overlapping work product"
    if not all(_name(duty.owner) in normalize(risk.reason) for duty in duties):
        return "risk reason does not name its accountable actors"
    if risk.kind == "potential_duplication" and not re.search(r"возможн|пересеч|дублир|потенциал", risk.reason, re.I):
        return "duplication reason must remain advisory"
    if risk.kind == "potential_conflict_of_interest" and not re.search(r"потенциал|самопроверк|возможн", risk.reason, re.I):
        return "conflict reason must remain advisory"
    if not risk.citations:
        return "risk has no source citations"
    for citation in risk.citations:
        problem = check_citation(citation, d.by_clause)
        if problem is not None:
            return problem
        if not _related_risk_citation(d, citation, duties, common):
            return "citation is unrelated to the cited duty, owner or governing context"
    for duty in duties:
        if not any(_key(c) == _key(duty.clause) and
                   _related_risk_citation(d, c, [duty], common)
                   for c in risk.citations):
            return f"missing substantive duty citation for {duty.clause.doc}:{duty.clause.clause_id}"
    return None


def analyze_domain(
    documents: list[Document], clauses: list[Clause], units: list[Unit], findings: list[Finding],
) -> tuple[list[UnitChange], list[Risk], list[str]]:
    """Derive deterministic domain outputs and explicit limitations from one run.

    Structural Findings supply candidate links; no second extraction or change
    to the seven function statuses occurs here. Model proposals may supplement
    these conservative outputs only through the public validators above.
    """
    d = _Domain(documents, clauses, units, findings)
    warnings: list[str] = []
    changes: list[UnitChange] = []
    risks: list[Risk] = []
    used_before: set[_Key] = set()
    used_after: set[_Key] = set()

    def add(status: str, old: list[Unit], new: list[Unit], reason: str,
            *, witness: Citation | None = None) -> bool:
        old_refs, new_refs = [_ref(u) for u in old], [_ref(u) for u in new]
        change = UnitChange(
            id=_id("U", status, old_refs + new_refs), status=status, before=old_refs,
            after=new_refs, citations=d.evidence(old + new, extra=witness),
            reason=reason, method="exact", review_required=status != "retained",
        )
        problem = validate_unit_change(change, documents, clauses, units, reviewed_predecessors=True)
        if problem is not None:
            warnings.append(f"{change.id}: вывод о подразделении не опубликован: {problem}.")
            return False
        changes.append(change)
        used_before.update(_key(u) for u in old)
        used_after.update(_key(u) for u in new)
        return True

    if not d.before or not d.after:
        warnings.append("Не во всех редакциях найдены явно определённые структурные подразделения; преемственность и создание могут остаться неустановленными.")

    # Explicit source statements can connect renamed and compound transitions.
    # Endpoints must occur in *one* directional sentence, not just in a list.
    for clause in d.clauses:
        if d.edition.get(clause.doc) not in ("before", "after"):
            continue
        for sentence in re.split(r"(?<=[.;])\s+|\n", clause.text):
            if _transition_kind(sentence) is None:
                continue
            old = [u for u in d.before if _key(u) not in used_before and _mentions(u, sentence)]
            new = [u for u in d.after if _key(u) not in used_after and _mentions(u, sentence)]
            witness = _transition(d, old, new)
            if witness is not None:
                names = ", ".join(u.name for u in old) + " → " + ", ".join(u.name for u in new)
                add("reorganised", old, new, f"В документе прямо указано преобразование {names}; требуется проверка границ функций.", witness=witness)
    # The structural rows from aligner already distinguish uniquely matched
    # identities from repeated names. Require the *whole* unit name here: a
    # recycled acronym by itself is never a retained department.
    for finding in findings:
        if finding.status not in ("unchanged", "moved") or len(finding.before) != 1 or len(finding.after) != 1:
            continue
        old = [u for u in d.before if _key(d.definition(u)) == _key(finding.before[0])]
        new = [u for u in d.after if _key(d.definition(u)) == _key(finding.after[0])]
        if len(old) != 1 or len(new) != 1 or _key(old[0]) in used_before or _key(new[0]) in used_after:
            continue
        if not d.unique_identity(old[0], new[0]) or d.parent_uncertain(old[0], new[0]):
            continue
        changed = d.parent_changed(old[0], new[0])
        reason = (f"Подразделение {old[0].name} сохранено; определяющие пункты обеих редакций совпадают по полному названию."
                  if not changed else f"Подразделение {old[0].name} сохранено с изменением прямо указанного подчинения: "
                  f"{d.parent(old[0]).name} → {d.parent(new[0]).name}.")
        add("reorganised" if changed else "retained", old, new, reason)

    # Same full title remains identity evidence even if an abbreviation changed
    # and _unit_rows had no same-key pair. Repeated titles stay ambiguous.
    for old in d.before:
        if _key(old) in used_before:
            continue
        peers = [u for u in d.after if _key(u) not in used_after and _name(u) == _name(old)]
        rivals = [u for u in d.before if _key(u) not in used_before and _name(u) == _name(old)]
        if len(peers) == len(rivals) == 1 and d.unique_identity(old, peers[0]) and not d.parent_uncertain(old, peers[0]):
            new = peers[0]
            changed = d.parent_changed(old, new)
            reason = (f"Полное название подразделения {old.name} подтверждено в обеих редакциях; "
                      + (f"явно указанное подчинение {d.parent(old).name} → {d.parent(new).name} изменилось."
                         if changed else "преемственность подтверждена независимо от номера пункта."))
            add("reorganised" if changed else "retained", [old], [new], reason)


    # Ambiguous candidates are kept together for review; a before-only unit is
    # never automatically called dissolved or lost.
    for new in d.after:
        if _key(new) in used_after:
            continue
        candidates = d.predecessors(new)
        free = [u for u in candidates if _key(u) not in used_before]
        if free:
            add("unresolved", free, [new],
                f"Преемственность подразделения {new.name} с возможными предшественниками "
                + ", ".join(u.name for u in free) + " не подтверждена источником перехода.")
        elif candidates:
            add("unresolved", [], [new],
                f"Преемственность подразделения {new.name} остаётся неустановленной: "
                "возможные предшественники уже участвуют в других сопоставлениях.")
        elif d.before:
            add("created", [], [new],
                f"Подразделение {new.name} указано в новой структуре; просмотрены все явно определённые "
                "подразделения исходной редакции, подтверждённый предшественник не найден. Требуется проверка.")
        else:
            add("unresolved", [], [new],
                f"Подразделение {new.name} есть в новой структуре, но исходная структура не извлечена; создание не установлено.")
    for old in d.before:
        if _key(old) not in used_before:
            add("unresolved", [old], [],
                f"Подразделение {old.name} есть в исходной структуре, но достоверное прекращение или преемник не установлены.")

    duties = [duty for clause in d.clauses if (duty := _duty(d, clause)) is not None]
    existing_duplicates = [frozenset(_key(r) for r in f.after) for f in findings if f.status == "duplicate"]
    seen_pairs: set[frozenset[_Key]] = set()
    for i, first in enumerate(duties):
        for second in duties[i + 1:]:
            if _key(first.owner) == _key(second.owner) or unit_key(first.owner) == unit_key(second.owner):
                continue
            pair = frozenset((_key(first.clause), _key(second.clause)))
            if pair in seen_pairs or any(pair <= existing for existing in existing_duplicates):
                continue
            if not first.actions.intersection(second.actions) or not _same_object(first, second):
                continue
            refs = [_clause_ref(first.clause), _clause_ref(second.clause)]
            anchor = _object_label(first, second)
            risk = Risk(
                id=_id("R", "potential_duplication", refs), kind="potential_duplication",
                units=[_ref(first.owner), _ref(second.owner)], refs=refs,
                citations=_risk_evidence(d, [first, second]),
                reason=f"Возможное пересечение: {first.owner.name} и {second.owner.name} "
                       f"выполняют однотипное действие с общим предметом ({anchor}); "
                       "объём полномочий требует проверки.",
                method="lexical", review_required=True,
            )
            problem = validate_risk(risk, documents, clauses, units)
            if problem is None:
                risks.append(risk)
                seen_pairs.add(pair)
            else:
                warnings.append(f"{risk.id}: риск не опубликован: {problem}.")

    for i, first in enumerate(duties):
        for second in duties[i + 1:]:
            if _key(first.owner) != _key(second.owner):
                continue
            execution, review = first, second
            if not execution.actions or not review.review:
                execution, review = second, first
            if not _self_review_product(execution, review):
                continue
            refs = [_clause_ref(execution.clause), _clause_ref(review.clause)]
            anchor = _object_label(first, second)
            risk = Risk(
                id=_id("R", "potential_conflict_of_interest", refs), kind="potential_conflict_of_interest",
                units=[_ref(first.owner)], refs=refs, citations=_risk_evidence(d, [execution, review]),
                reason=f"Потенциальный конфликт интересов: {first.owner.name} исполняет и проверяет "
                       f"собственную работу по общему предмету ({anchor}); необходима проверка разделения полномочий.",
                method="lexical", review_required=True,
            )
            problem = validate_risk(risk, documents, clauses, units)
            if problem is None:
                risks.append(risk)
            else:
                warnings.append(f"{risk.id}: риск не опубликован: {problem}.")

    if not duties:
        warnings.append("Не извлечены функции с однозначным ответственным в новой редакции; межподразделенческие риски не оценены.")
    elif not risks:
        warnings.append("Подтверждённых правилами исходного текста пересечений и самопроверки не найдено; это не доказывает отсутствие рисков в документах.")
    if any(c.status == "unresolved" for c in changes):
        warnings.append("Для неустановленной преемственности требуется просмотр приложений и решений о реорганизации человеком.")
    return changes, risks, warnings
