"""Synthetic source-first domain invariants (no organiser/holdout fixtures)."""

from __future__ import annotations

import unittest

from .lineage import analyze_domain, validate_risk, validate_unit_change
from .models import Citation, Clause, Document, Unit, UnitChange, UnitRef


def document(side: str) -> Document:
    return Document(doc=side, doc_id=side, sha256=side[0] * 64,
                    edition=side, source=f"{side}.txt")


def source(side: str, number: str, text: str, kind: str = "structure",
           parent: str | None = None, *, unit_ids: list[str] | None = None) -> Clause:
    return Clause(doc=side, clause_id=number, label=number, parent_id=parent,
                  text=text, ordinal=int(number.split(".")[0]), kind=kind,
                  unit_ids=unit_ids if unit_ids is not None else ([number] if kind == "structure" else []))


def unit(side: str, number: str, name: str) -> Unit:
    return Unit(doc=side, unit_id=number, name=name, kind="unit", parent_unit_id=None,
                citations=[Citation(doc=side, clause_id=number, quote=name)])


class DomainLineageTests(unittest.TestCase):
    def test_after_only_overlap_and_own_review_have_distinct_reviewable_risks(self) -> None:
        documents = [document("before"), document("after")]
        clauses = [
            source("before", "1", "Отдел учёта"),
            source("after", "10", "Общие положения.", "heading"),
            source("after", "1", "Отдел учёта", parent="10"),
            source("after", "2", "Служба качества", parent="10"),
            source("after", "1.1", "Ведение реестра оборудования.", "function", "1", unit_ids=["1"]),
            source("after", "1.2", "Проверка реестра оборудования.", "function", "1", unit_ids=["1"]),
            source("after", "2.1", "Ведение реестра оборудования.", "function", "2", unit_ids=["2"]),
        ]
        units = [unit("before", "1", "Отдел учёта"), unit("after", "1", "Отдел учёта"),
                 unit("after", "2", "Служба качества")]
        changes, risks, _ = analyze_domain(documents, clauses, units, [])
        self.assertEqual({change.status for change in changes}, {"retained", "created"})
        self.assertEqual({risk.kind for risk in risks},
                         {"potential_duplication", "potential_conflict_of_interest"})
        self.assertTrue(all(risk.review_required and validate_risk(risk, documents, clauses, units) is None
                            for risk in risks))
        self.assertEqual({len(risk.units) for risk in risks}, {1, 2})
        self.assertFalse(any(c.clause_id == "10" for risk in risks for c in risk.citations))
        unrelated_ancestor = risks[0].model_copy(update={"citations": risks[0].citations + [
            Citation(doc="after", clause_id="10", quote="Общие положения.")
        ]})
        self.assertIsNotNone(validate_risk(unrelated_ancestor, documents, clauses, units))

        unrelated = source("after", "9", "Независимый обзор.", "other")
        corrupted = risks[0].model_copy(update={"citations": risks[0].citations + [
            Citation(doc="after", clause_id="9", quote="Независимый обзор.")
        ]})
        self.assertIsNotNone(validate_risk(corrupted, documents, clauses + [unrelated], units))

        different_actors = next(r for r in risks if r.kind == "potential_duplication")
        fabricated_conflict = different_actors.model_copy(update={"kind": "potential_conflict_of_interest"})
        self.assertIsNotNone(validate_risk(fabricated_conflict, documents, clauses, units))

    def test_created_requires_real_search_and_abstains_on_transferred_duty(self) -> None:
        documents = [document("before"), document("after")]
        clauses = [source("before", "1", "Отдел учёта"),
                   source("before", "1.1", "Ведение реестра оборудования.", "function", "1", unit_ids=["1"]),
                   source("after", "2", "Служба качества"),
                   source("after", "2.1", "Ведение реестра оборудования.", "function", "2", unit_ids=["2"])]
        units = [unit("before", "1", "Отдел учёта"), unit("after", "2", "Служба качества")]
        proposal = UnitChange(id="candidate", status="created", before=[],
                              after=[UnitRef(doc="after", unit_id="2")],
                              citations=units[1].citations,
                              reason="Служба качества создана в новой структуре.",
                              method="llm", review_required=True)
        self.assertIsNotNone(validate_unit_change(proposal, documents, clauses, units))
        self.assertIsNotNone(validate_unit_change(proposal, documents, clauses, units,
                                                  reviewed_predecessors=True))
        changes, _, _ = analyze_domain(documents, clauses, units, [])
        self.assertNotIn("created", [change.status for change in changes])
        self.assertIn("unresolved", [change.status for change in changes])

    def test_directional_split_and_unrelated_exact_quote(self) -> None:
        documents = [document("before"), document("after")]
        old = "Управление информационных систем"
        successors = ["Отдел инфраструктуры", "Отдел разработки"]
        statement = f"{old} разделено на {successors[0]} и {successors[1]}."
        clauses = [source("before", "1", old),
                   source("after", "2", successors[0]),
                   source("after", "3", successors[1]),
                   source("after", "4", statement, "other"),
                   source("after", "9", "Решение об инвентаризации.", "other")]
        units = [unit("before", "1", old), unit("after", "2", successors[0]),
                 unit("after", "3", successors[1])]
        changes, _, _ = analyze_domain(documents, clauses, units, [])
        split = next(change for change in changes if change.status == "reorganised")
        self.assertEqual((len(split.before), len(split.after)), (1, 2))
        self.assertIsNone(validate_unit_change(split, documents, clauses, units))
        self.assertIsNotNone(validate_unit_change(split.model_copy(update={
            "citations": [c for c in split.citations if c.clause_id != "4"] +
                         [Citation(doc="after", clause_id="9", quote="Решение об инвентаризации.")]
        }), documents, clauses, units))
        role = Unit(doc="after", unit_id="9", name="Директор", kind="role", parent_unit_id=None,
                    citations=[Citation(doc="after", clause_id="9", quote="Решение")])
        promoted = split.model_copy(update={"after": [UnitRef(doc="after", unit_id="9")]})
        self.assertIsNotNone(validate_unit_change(promoted, documents, clauses, units + [role]))

    def test_different_accountable_actors_do_not_create_self_review(self) -> None:
        documents = [document("before"), document("after")]
        clauses = [source("before", "1", "Отдел учёта"),
                   source("after", "1", "Отдел учёта"),
                   source("after", "2", "Служба качества"),
                   source("after", "1.1", "Ведение реестра оборудования.", "function", "1", unit_ids=["1"]),
                   source("after", "2.1", "Проверка реестра оборудования.", "function", "2", unit_ids=["2"])]
        units = [unit("before", "1", "Отдел учёта"), unit("after", "1", "Отдел учёта"),
                 unit("after", "2", "Служба качества")]
        _, risks, _ = analyze_domain(documents, clauses, units, [])
        self.assertFalse(any(risk.kind == "potential_conflict_of_interest" for risk in risks))

    def test_cooperation_and_different_scopes_are_not_overlap(self) -> None:
        documents = [document("before"), document("after")]
        units = [unit("before", "1", "Отдел учёта"), unit("after", "1", "Отдел учёта"),
                 unit("after", "2", "Служба качества")]
        prefix = [source("before", "1", "Отдел учёта"),
                  source("after", "1", "Отдел учёта"),
                  source("after", "2", "Служба качества")]
        for left, right in (
            ("Совместно ведёт реестр оборудования.", "Ведёт реестр оборудования."),
            ("Ведение реестра оборудования в части поставок.",
             "Ведение реестра оборудования в части ремонтов."),
        ):
            with self.subTest(left=left, right=right):
                clauses = prefix + [
                    source("after", "1.1", left, "function", "1", unit_ids=["1"]),
                    source("after", "2.1", right, "function", "2", unit_ids=["2"]),
                ]
                _, risks, _ = analyze_domain(documents, clauses, units, [])
                self.assertFalse(any(risk.kind == "potential_duplication" for risk in risks))

    def test_explanatory_sentence_does_not_change_assigned_work_object(self) -> None:
        documents = [document("before"), document("after")]
        units = [unit("after", "1", "Центр приёма"), unit("after", "2", "Группа сервиса")]
        assignment = "Регистрирует входящие письма граждан в общем журнале."
        clauses = [
            source("after", "1", "Центр приёма"), source("after", "2", "Группа сервиса"),
            source("after", "1.1", assignment, "function", "1", unit_ids=["1"]),
            source("after", "2.1", assignment + " Разделение потоков и этапов обработки не установлено.",
                   "function", "2", unit_ids=["2"]),
        ]
        risks = analyze_domain(documents, clauses, units, [])[1]
        self.assertEqual([risk.kind for risk in risks], ["potential_duplication"])
        self.assertIsNone(validate_risk(risks[0], documents, clauses, units))
        clauses[-1] = clauses[-1].model_copy(update={
            "text": assignment + " Работа ограничена в части внутренних обращений."
        })
        self.assertEqual(analyze_domain(documents, clauses, units, [])[1], [])

    def test_own_operation_review_needs_the_same_direct_object(self) -> None:
        documents = [document("before"), document("after")]
        units = [unit("after", "1", "Комитет организации работ")]
        clauses = [
            source("after", "1", "Комитет организации работ"),
            source("after", "1.1", "Выбирает подрядчика по опубликованным требованиям и оформляет решение.",
                   "function", "1", unit_ids=["1"]),
            source("after", "1.2", "Проверяет обоснованность собственного выбора подрядчика и утверждает заключение.",
                   "function", "1", unit_ids=["1"]),
        ]
        risks = analyze_domain(documents, clauses, units, [])[1]
        self.assertEqual([risk.kind for risk in risks], ["potential_conflict_of_interest"])
        self.assertIsNone(validate_risk(risks[0], documents, clauses, units))
        clauses[-1] = clauses[-1].model_copy(update={
            "text": "Проверяет обоснованность собственного выбора оборудования и утверждает заключение."
        })
        self.assertEqual(analyze_domain(documents, clauses, units, [])[1], [])


if __name__ == "__main__":
    unittest.main()
