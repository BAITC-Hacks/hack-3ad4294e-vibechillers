"""Deterministic before→after alignment of function clauses.

Order of evidence, strongest first:

1. **Exact** — identical text after matching-only normalisation. A single copy on
   each side is a pair (``unchanged`` if clause number and owner context agree,
   otherwise ``moved``). Repeated identical text is paired only when location or
   owner context tells the copies apart; the rest stays ``unresolved`` or, when an
   extra copy appears under a different owner, ``duplicate``.
2. **Lexical** — mutual best candidates above ``STRONG`` with a clear ``MARGIN``
   become ``changed``, or ``moved`` when source-backed owners change but the
   complete duty after their leading names is identical. Iterated until stable.
3. **Leftovers** — no candidate at all gives ``missing``/``added``; candidates
   that are ambiguous or weak give ``unresolved`` listing every candidate ref;
   one predecessor strongly matching several owners gives ``duplicate``.

Every before/after function clause ends up in at least one finding. Structure
units present on one side only are reported as ``added``/``missing`` as well.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from .citations import cite_context, clause_index
from .models import Clause, ClauseRef, Finding, Unit
from .parser import owner_keys
from .text import normalize, similarity, stems

STRONG = 0.72
WEAK = 0.45
MARGIN = 0.06
REVIEW_BELOW = 0.85
_PREFILTER_DICE = 0.2
_TOPK = 12
_MAX_CANDIDATES = 3

# Compare explicit modality, not every edit to an ancestor's prose.
_MODALITY = (
    ("negation", re.compile(r"\bне\b", re.I)),
    ("optional", re.compile(r"\b(?:может|могут)\b", re.I)),
    ("obligation", re.compile(r"\b(?:обязан|обязана|обязано|обязаны|должен|должна|должны)\b", re.I)),
    ("permission", re.compile(r"\b(?:вправе|име\w*\s+право|разрешен\w*)\b", re.I)),
    ("prohibition", re.compile(r"\b(?:запрещ\w*|недопустим\w*)\b", re.I)),
)
_CONDITION = re.compile(
    r"\b(?:только|исключительно|за\s+исключением|при\s+условии|"
    r"в\s+пределах|без\s+права|по\s+согласованию|с\s+согласия)\b[^;:.!?]*", re.I,
)
_DELEGATION = re.compile(r"\b(?:делегир\w*|поруча\w*|возлага\w*)\b", re.I)
_DELEGATED_ACTION = re.compile(
    r"\b(?:подготов\w*|выполн\w*|ведени\w*|организаци\w*|"
    r"обязанност\w*|полномочи\w*|функци\w*|задач\w*)\b", re.I,
)


@dataclass(frozen=True)
class _Item:
    clause: Clause
    norm: str
    stems: frozenset[str]
    body_norm: str
    base_id: str
    owners: frozenset[str]
    context: tuple[str, ...] = ()

    @property
    def ref(self) -> ClauseRef:
        return ClauseRef(doc=self.clause.doc, clause_id=self.clause.clause_id)

    @property
    def where(self) -> str:
        return f"{self.clause.doc}:{self.clause.clause_id}"


def _base_id(clause_id: str) -> str:
    return clause_id.split("@", 1)[0]


def _governing_context(clause: Clause, clauses: dict[str, Clause], units: dict[str, Unit]) -> tuple[str, ...]:
    """Compare explicit governing modality/conditions, including standalone roles."""
    sources: list[Clause] = []
    seen = {clause.clause_id}
    parent = clauses.get(clause.parent_id) if clause.parent_id else None
    while parent is not None and parent.clause_id not in seen:
        seen.add(parent.clause_id)
        sources.append(parent)
        parent = clauses.get(parent.parent_id) if parent.parent_id else None
    # Unnumbered role headings scope siblings without changing numeric parent_id.
    for uid in clause.unit_ids:
        unit = units.get(uid)
        if unit is None or unit.kind != "role":
            continue
        for citation in unit.citations:
            source = clauses.get(citation.clause_id)
            if (source is not None and citation.doc == clause.doc and not source.label
                    and source.clause_id not in seen and citation.quote in source.text):
                seen.add(source.clause_id)
                sources.append(source)
    context: set[str] = set()
    for source in sources:
        text = source.text
        context.update(name for name, pattern in _MODALITY if pattern.search(text))
        context.update("condition:" + normalize(match.group()) for match in _CONDITION.finditer(text))
        # A changed delegation recipient is material even when accountability
        # remains with the same source-backed role.
        for delegation in _DELEGATION.finditer(text):
            prefix = text[:delegation.start()].strip()
            if prefix and delegation.group().lower().endswith(("ется", "ются")):
                # Dative-first / "На отдел возлагаются ..." introductions:
                # changing "следующие функции" to "задачи и функции" is not
                # changing the recipient.
                scope = prefix
            else:
                remainder = text[delegation.end():].strip()
                action = _DELEGATED_ACTION.search(remainder)
                scope = remainder[:action.start()].strip() if action else remainder
                # Unrecognised order remains conservative, not guessed.
                scope = scope or remainder
            context.add("delegation:" + normalize(scope))
    return tuple(sorted(context))


def _body_without_owner(norm: str, owners: frozenset[str]) -> str:
    """Only strip a leading name when the parser sourced exactly that owner."""
    if len(owners) != 1:
        return ""
    prefix = normalize(next(iter(owners))) + " "
    return norm[len(prefix):] if norm.startswith(prefix) else ""


def _owner_transfer_preserves_duty(b: _Item, a: _Item) -> bool:
    return bool(
        b.owners and a.owners and b.owners != a.owners
        and b.context == a.context and b.body_norm and b.body_norm == a.body_norm
    )


def _items(clauses: list[Clause], units: list[Unit], docs: list[str]) -> list[_Item]:
    wanted = set(docs)
    by_doc_clause: dict[str, dict[str, Clause]] = {}
    by_doc_unit: dict[str, dict[str, Unit]] = {}
    for clause in clauses:
        by_doc_clause.setdefault(clause.doc, {})[clause.clause_id] = clause
    for unit in units:
        by_doc_unit.setdefault(unit.doc, {})[unit.unit_id] = unit
    order = {doc: i for i, doc in enumerate(docs)}
    items = []
    for clause in sorted((c for c in clauses if c.doc in wanted and c.kind == "function"),
                         key=lambda c: (order[c.doc], c.ordinal)):
        owners = owner_keys(clause, by_doc_clause.get(clause.doc, {}), by_doc_unit.get(clause.doc, {}))
        # An explicit absence of partitioning is evidence of shared scope, not
        # an additional operational action. Keep the full original citation.
        sentences = re.split(r"(?<=[.!?])\s+", clause.text.strip(), maxsplit=1)
        duty_text = clause.text
        if len(sentences) == 2 and re.fullmatch(
            r"(?:Разделение|Разграничение)\b[^.!?]{1,400}\bне\s+"
            r"(?:установлено|предусмотрено|определено)\s*[.!?]?",
            sentences[1], re.IGNORECASE,
        ):
            duty_text = sentences[0]
        norm = normalize(duty_text)
        items.append(
            _Item(
                clause=clause,
                norm=norm,
                body_norm=_body_without_owner(norm, owners),
                stems=stems(clause.text),
                base_id=_base_id(clause.clause_id),
                owners=owners,
                context=_governing_context(clause, by_doc_clause.get(clause.doc, {}), by_doc_unit.get(clause.doc, {})),
            )
        )
    return items


class _Scorer:
    """Cached lexical similarity with an inverted-index prefilter."""

    def __init__(self, before: list[_Item], after: list[_Item]):
        self.before, self.after = before, after
        self._cache: dict[tuple[int, int], float] = {}
        self._b_index = self._index(before)
        self._a_index = self._index(after)
        self._after_cands: dict[int, list[tuple[float, int]]] = {}
        self._before_cands: dict[int, list[tuple[float, int]]] = {}

    @staticmethod
    def _index(items: list[_Item]) -> dict[str, list[int]]:
        index: dict[str, list[int]] = {}
        for i, item in enumerate(items):
            for stem in item.stems:
                index.setdefault(stem, []).append(i)
        return index

    def score(self, bi: int, ai: int) -> float:
        key = (bi, ai)
        if key not in self._cache:
            b, a = self.before[bi], self.after[ai]
            self._cache[key] = (
                1.0 if (b.norm and b.norm == a.norm) or _owner_transfer_preserves_duty(b, a)
                else similarity(b.norm, b.stems, a.norm, a.stems)
            )
        return self._cache[key]

    def _candidates(self, item: _Item, index: dict[str, list[int]], others: list[_Item]) -> list[int]:
        shared: Counter[int] = Counter()
        for stem in item.stems:
            shared.update(index.get(stem, ()))
        ranked = []
        for j, n in shared.items():
            d = 2.0 * n / (len(item.stems) + len(others[j].stems))
            if d >= _PREFILTER_DICE:
                ranked.append((d, j))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        return [j for _, j in ranked[:_TOPK]]

    def after_of(self, bi: int) -> list[tuple[float, int]]:
        """After candidates of before item `bi` scoring ≥ WEAK, best first."""
        if bi not in self._after_cands:
            scored = [(self.score(bi, ai), ai) for ai in self._candidates(self.before[bi], self._a_index, self.after)]
            self._after_cands[bi] = sorted((t for t in scored if t[0] >= WEAK), key=lambda t: (-t[0], t[1]))
        return self._after_cands[bi]

    def before_of(self, ai: int) -> list[tuple[float, int]]:
        """Before candidates of after item `ai` scoring ≥ WEAK, best first."""
        if ai not in self._before_cands:
            scored = [(self.score(bi, ai), bi) for bi in self._candidates(self.after[ai], self._b_index, self.before)]
            self._before_cands[ai] = sorted((t for t in scored if t[0] >= WEAK), key=lambda t: (-t[0], t[1]))
        return self._before_cands[ai]


def _owners_text(owners: frozenset[str]) -> str:
    return ", ".join(sorted(owners)) if owners else "не указан"


def _context_note(b: _Item, a: _Item) -> str:
    notes = []
    if b.base_id != a.base_id:
        notes.append(f"пункт {b.base_id} → {a.base_id}")
    if b.owners and a.owners and b.owners != a.owners:
        notes.append(f"владелец {_owners_text(b.owners)} → {_owners_text(a.owners)}")
    return "; ".join(notes)


def _same_context(b: _Item, a: _Item) -> bool:
    owners_agree = not b.owners or not a.owners or b.owners == a.owners
    return b.base_id == a.base_id and owners_agree


def _context_score(b: _Item, a: _Item) -> int:
    return 2 * (b.base_id == a.base_id) + (bool(b.owners) and b.owners == a.owners)


def _distinct_owners(items: list[_Item]) -> bool:
    owners = [i.owners for i in items]
    return all(owners) and len(set(owners)) == len(owners)


class _Builder:
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, status: str, before: list[_Item], after: list[_Item], reason: str, method: str, review: bool):
        self.rows.append(dict(status=status, before=before, after=after, reason=reason, method=method, review=review))


def _pair_status(b: _Item, a: _Item) -> tuple[str, str]:
    if b.context != a.context:
        return "unresolved", (
            "Текст дочернего пункта совпадает, но определяющий родительский контекст изменён; "
            "сохранность смысла, роли или ограничения требует проверки по отдельным цитатам родителей."
        )
    if _same_context(b, a):
        return "unchanged", f"Текст совпадает (без учёта пунктуации и регистра), пункт {a.base_id} и контекст сохранены."
    return "moved", f"Текст совпадает, изменено расположение: {_context_note(b, a)}."


def _exact_phase(before, after, out: _Builder, paired_b: dict[int, int], paired_a: dict[int, int], handled_b, handled_a):
    groups: dict[str, tuple[list[int], list[int]]] = {}
    for i, item in enumerate(before):
        key = item.body_norm or item.norm
        if key:
            groups.setdefault(key, ([], []))[0].append(i)
    for i, item in enumerate(after):
        key = item.body_norm or item.norm
        if key and key in groups:
            groups[key][1].append(i)
    for norm, (bs, as_) in groups.items():
        if not as_:
            continue
        if (len(bs) == 1 and len(as_) > 1
                and _distinct_owners([after[a] for a in as_])
                and all(before[bs[0]].context == after[a].context for a in as_)):
            out.add("duplicate", [before[bs[0]]], [after[a] for a in as_],
                    "Та же функция закреплена за несколькими различными владельцами "
                    "новой редакции без установленного разделения объёма; требуется проверка.",
                    "exact", True)
            handled_b.update(bs)
            handled_a.update(as_)
            continue
        pairs: list[tuple[int, int]] = []
        if len(bs) == 1 and len(as_) == 1:
            pairs.append((bs[0], as_[0]))
        else:
            free_b, free_a = set(bs), set(as_)
            progress = True
            while progress and free_b and free_a:
                progress = False
                scored = sorted(((_context_score(before[b], after[a]), b, a) for b in free_b for a in free_a),
                                key=lambda t: (-t[0], t[1], t[2]))
                top, b, a = scored[0]
                if top == 0:
                    break
                rivals = [t for t in scored[1:] if t[0] == top and (t[1] == b or t[2] == a)]
                if rivals:
                    break
                pairs.append((b, a))
                free_b.discard(b)
                free_a.discard(a)
                progress = True
        for b, a in pairs:
            status, reason = _pair_status(before[b], after[a])
            owner_changed = before[b].owners != after[a].owners
            out.add(status, [before[b]], [after[a]], reason, "exact", status == "unresolved" or owner_changed)
            paired_b[b], paired_a[a] = a, b
        rem_b = [b for b in bs if b not in paired_b]
        rem_a = [a for a in as_ if a not in paired_a]
        group_b = [before[b] for b in bs]
        if rem_b and rem_a:
            out.add("unresolved", [before[b] for b in rem_b], [after[a] for a in rem_a],
                    "Одинаковый текст встречается в нескольких местах обеих редакций; соответствие копий "
                    "по номеру пункта и владельцу однозначно не устанавливается.", "exact", True)
        elif rem_a:
            context_changed = any(before[b].context != after[a].context for b, a in pairs)
            if context_changed:
                # A restriction change prevents treating the extra copy as
                # established overlap; keep the complete candidate group once.
                out.rows = [
                    row for row in out.rows
                    if not any(row["before"] == [before[b]] and row["after"] == [after[a]] for b, a in pairs)
                ]
                out.add("unresolved", group_b, [after[a] for a in as_],
                        "Повторяющийся текст сопровождается изменённым родительским контекстом; "
                        "перенос, разделение или пересечение ответственности не подтверждены.", "exact", True)
                handled_b.update(bs)
                handled_a.update(as_)
                continue
            paired_owners = {after[a].owners for a in as_ if a in paired_a}
            for a in rem_a:
                item = after[a]
                others = [after[x] for x in as_ if x != a]
                if item.owners and paired_owners and item.owners not in paired_owners:
                    # The overlap row already accounts for the preserved copy;
                    # publishing a second unchanged row would double-claim it.
                    if len(bs) == 1 and bs[0] in paired_b:
                        original = before[bs[0]]
                        successor = after[paired_b[bs[0]]]
                        out.rows = [
                            row for row in out.rows
                            if not (row["before"] == [original] and row["after"] == [successor]
                                    and row["status"] in ("unchanged", "moved"))
                        ]
                    out.add("duplicate", group_b, [item] + others,
                            f"Тот же текст функции появился у дополнительного владельца ({_owners_text(item.owners)}); "
                            "возможное пересечение ответственности, требуется проверка.", "exact", True)
                else:
                    out.add("unresolved", group_b, [item],
                            "Текст встречается в новой редакции больше раз, чем в исходной; "
                            "дополнительную копию нельзя однозначно отнести.", "exact", True)
        elif rem_b:
            for b in rem_b:
                out.add("unresolved", [before[b]], [after[a] for a in as_],
                        "Тот же текст сохранился в новой редакции, но все копии уже сопоставлены с другими пунктами; "
                        "возможное объединение функций.", "exact", True)
        handled_b.update(bs)
        handled_a.update(as_)


def _lexical_phase(before, after, scorer: _Scorer, out: _Builder, paired_b, paired_a, handled_b, handled_a):
    changed = True
    while changed:
        changed = False
        for bi in range(len(before)):
            if bi in handled_b:
                continue
            cands = [t for t in scorer.after_of(bi) if t[1] not in handled_a]
            if not cands or cands[0][0] < STRONG:
                continue
            s1, ai = cands[0]
            if len(cands) > 1 and s1 - cands[1][0] < MARGIN:
                continue
            back = [t for t in scorer.before_of(ai) if t[1] not in handled_b]
            if not back or back[0][1] != bi or (len(back) > 1 and back[0][0] - back[1][0] < MARGIN):
                continue
            b, a = before[bi], after[ai]
            note = _context_note(b, a)
            preserved_transfer = _owner_transfer_preserves_duty(b, a)
            if preserved_transfer:
                reason = f"После обозначения владельца текст функции совпадает; {note}."
            else:
                reason = f"Лексическое сходство {s1:.2f}; формулировка изменена" + (f"; {note}." if note else ".")
            context_changed = b.context != a.context
            if context_changed:
                reason += " Родительский контекст изменён; смысл и ограничения требуют отдельной проверки."
            out.add("moved" if preserved_transfer else "changed", [b], [a], reason, "lexical",
                    preserved_transfer or s1 < REVIEW_BELOW or context_changed or b.owners != a.owners)
            paired_b[bi], paired_a[ai] = ai, bi
            handled_b.add(bi)
            handled_a.add(ai)
            changed = True


def _leftovers(before, after, scorer: _Scorer, out: _Builder, paired_b, paired_a, handled_b, handled_a):
    missing_b: set[int] = set()
    for bi in range(len(before)):
        if bi in handled_b:
            continue
        b = before[bi]
        cands = scorer.after_of(bi)
        strong_free = [ai for s, ai in cands if s >= STRONG and ai not in handled_a]
        free = [ai for _, ai in cands if ai not in handled_a]
        if len(strong_free) >= 2:
            group = [after[ai] for ai in strong_free]
            own_best = all(scorer.before_of(ai) and scorer.before_of(ai)[0][1] == bi for ai in strong_free)
            if own_best and _distinct_owners(group):
                out.add("duplicate", [b], group,
                        "Одна исходная функция близко соответствует нескольким пунктам новой редакции у разных "
                        "владельцев; возможное дублирование ответственности, требуется проверка.", "lexical", True)
            else:
                out.add("unresolved", [b], group,
                        "Несколько близких кандидатов-преемников без явного лидера; возможное разделение функции.",
                        "lexical", True)
            handled_a.update(strong_free)
        elif free:
            picked = [ai for _, ai in cands if ai in set(free)][:_MAX_CANDIDATES]
            top = max(s for s, ai in cands if ai in set(free))
            out.add("unresolved", [b], [after[ai] for ai in picked],
                    f"Найдены только неоднозначные или слабые кандидаты (сходство до {top:.2f}); "
                    "преемник не подтверждён.", "lexical", True)
            handled_a.update(picked)
        else:
            nearest = ", ".join(after[ai].where for _, ai in cands[:_MAX_CANDIDATES])
            reason = "В представленной новой редакции не найден подтверждённый преемник функции"
            reason += f" (ближайшие пункты уже сопоставлены: {nearest})." if nearest else "."
            out.add("missing", [b], [], reason, "lexical" if cands else "exact", True)
            missing_b.add(bi)
        handled_b.add(bi)

    for ai in range(len(after)):
        if ai in handled_a:
            continue
        a = after[ai]
        cands = scorer.before_of(ai)
        if cands and cands[0][0] >= STRONG and cands[0][1] in paired_b:
            bi = cands[0][1]
            partner = after[paired_b[bi]]
            if a.owners and partner.owners and a.owners != partner.owners:
                out.add("duplicate", [before[bi]], [partner, a],
                        f"Пункт близок (сходство {cands[0][0]:.2f}) к функции, уже сопоставленной с "
                        f"{partner.where}, но закреплён за другим владельцем ({_owners_text(a.owners)}); "
                        "возможное дублирование ответственности.", "lexical", True)
                handled_a.add(ai)
                continue
        free = [bi for _, bi in cands if bi not in paired_b and bi not in missing_b]
        if free or (cands and cands[0][0] >= STRONG):
            picked = (free if free else [bi for _, bi in cands])[:_MAX_CANDIDATES]
            out.add("unresolved", [before[bi] for bi in picked], [a],
                    f"Возможный предшественник найден с неоднозначным сходством (до {cands[0][0]:.2f}); "
                    "требуется решение эксперта.", "lexical", True)
        else:
            out.add("added", [], [a], "В исходной редакции не найден подтверждённый предшественник функции.",
                    "lexical" if cands else "exact", True)
        handled_a.add(ai)




def align_functions(clauses: list[Clause], units: list[Unit], before_docs: list[str], after_docs: list[str]) -> list[Finding]:
    """Deterministic findings covering every function clause of the given documents."""
    before = _items(clauses, units, before_docs)
    after = _items(clauses, units, after_docs)
    out = _Builder()
    paired_b: dict[int, int] = {}
    paired_a: dict[int, int] = {}
    handled_b: set[int] = set()
    handled_a: set[int] = set()
    scorer = _Scorer(before, after)
    _exact_phase(before, after, out, paired_b, paired_a, handled_b, handled_a)
    _lexical_phase(before, after, scorer, out, paired_b, paired_a, handled_b, handled_a)
    _leftovers(before, after, scorer, out, paired_b, paired_a, handled_b, handled_a)

    order = {doc: i for i, doc in enumerate(list(before_docs) + list(after_docs))}

    def sort_key(row: dict):
        anchor = (row["before"] or row["after"])[0].clause
        return (0 if row["before"] else 1, order.get(anchor.doc, 0), anchor.ordinal)

    index = clause_index(clauses)
    unit_index = {(u.doc, u.unit_id): u for u in units}
    findings: list[Finding] = []
    for n, row in enumerate(sorted(out.rows, key=sort_key), start=1):
        before_refs = [i.ref for i in row["before"]]
        after_refs = [i.ref for i in row["after"]]
        findings.append(
            Finding(
                id=f"F{n:03d}",
                status=row["status"],
                before=before_refs,
                after=after_refs,
                citations=cite_context(before_refs + after_refs, index, unit_index),
                reason=row["reason"],
                method=row["method"],
                review_required=row["review"],
            )
        )
    return findings
