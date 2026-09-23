"""Behavioral regressions for the offline public Report export."""

import unittest
from html.parser import HTMLParser

from export_report import anchor, render_report


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.text = []
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "script":
            self.scripts += 1

    def handle_data(self, data):
        self.text.append(data)


class UnitCitationTest(unittest.TestCase):
    def test_role_only_citation_remains_navigable_and_inert(self):
        quote = '<script>alert("role")</script>'
        report = {
            "run_id": "unit-citation-regression", "mode": "deterministic",
            "documents": [], "findings": [], "conclusion": [],
            "warnings": [], "coverage": {},
            "clauses": [{"doc": "before-1", "clause_id": "1",
                         "label": "1.", "text": quote, "ordinal": 1,
                         "kind": "heading", "parent_id": None,
                         "unit_ids": ["chief"]}],
            "units": [{"doc": "before-1", "unit_id": "chief",
                       "name": "Chief " + quote, "kind": "role",
                       "parent_unit_id": "board",
                       "citations": [{"doc": "before-1", "clause_id": "1",
                                      "quote": quote}]}],
        }
        page = Page()
        page.feed(render_report(report))
        text = "".join(page.text)
        self.assertIn("Chief " + quote, text)
        self.assertIn("board", text)
        self.assertIn(quote, text)
        self.assertEqual(page.scripts, 0)
        self.assertIn("#" + anchor("clause", "before-1", "1"), page.links)
        self.assertTrue(all(href[1:] in page.ids for href in page.links))


class StageThreeExportTest(unittest.TestCase):
    def page(self, report):
        page = Page()
        page.feed(render_report(report))
        return page

    def test_conclusion_unit_risk_and_context_links_are_document_scoped(self):
        hostile = '<img src="https://invalid.example/x" onerror="alert(1)">'
        clauses, units = [], []
        for doc in ("before-1", "after-1"):
            clauses.extend([
                {"doc": doc, "clause_id": "parent", "text": "Руководитель " + doc,
                 "kind": "heading", "unit_ids": ["chief"]},
                {"doc": doc, "clause_id": "duty", "text": hostile + " " + doc,
                 "parent_id": "parent", "unit_ids": ["operations"], "kind": "function",
                 "location": {"page": 2, "block": 0, "sheet": hostile, "cell_range": "B3:C4"}},
            ])
            units.extend([
                {"doc": doc, "unit_id": "chief", "name": "Руководитель", "kind": "role",
                 "citations": [{"doc": doc, "clause_id": "parent", "quote": "Руководитель " + doc}]},
                {"doc": doc, "unit_id": "operations", "name": hostile, "kind": "unit",
                 "parent_unit_id": "chief", "citations": []},
            ])
        citation = {"doc": "after-1", "clause_id": "duty", "quote": hostile}
        # IDs may coincide across result kinds and source editions.
        report = {
            "clauses": clauses, "units": units,
            "findings": [{"id": "same", "status": "changed", "before": [
                {"doc": "before-1", "clause_id": "duty"}], "after": [
                {"doc": "after-1", "clause_id": "duty"}], "citations": [citation]}],
            "unit_changes": [{"id": "same", "status": "reorganised", "before": [
                {"doc": "before-1", "unit_id": "operations"}], "after": [
                {"doc": "after-1", "unit_id": "operations"}], "citations": [citation]}],
            "risks": [{"id": "same", "kind": "potential_conflict_of_interest",
                       "units": [{"doc": "after-1", "unit_id": "chief"}],
                       "refs": [{"doc": "after-1", "clause_id": "duty"}],
                       "citations": [citation], "reason": hostile, "review_required": True}],
            "conclusion": [{"text": hostile, "finding_ids": ["same"],
                            "unit_change_ids": ["same"], "risk_ids": ["same"],
                            "citations": [citation]}],
            "agent": {"status": "partial", "model": hostile, "turns": 2, "tool_calls": 3,
                      "investigated_finding_ids": ["same"], "stop_reason": "Лимит"},
        }
        page = self.page(report)
        text = "".join(page.text)
        for kind in ("finding", "unit-change", "risk"):
            self.assertIn("#" + anchor(kind, "same"), page.links)
        for doc in ("before-1", "after-1"):
            for kind, ids in (("clause", ("parent", "duty")), ("unit", ("chief", "operations"))):
                for source_id in ids:
                    self.assertIn("#" + anchor(kind, doc, source_id), page.links)
        self.assertTrue(all(href.startswith("#") and href[1:] in page.ids for href in page.links))
        self.assertIn("Лист: " + hostile, text)
        self.assertIn("Ячейки: B3:C4", text)
        self.assertIn("Страница: 2", text)
        self.assertIn("Блок: 0", text)
        self.assertIn(hostile, text)
        self.assertNotIn("<img", render_report(report))
        self.assertEqual(page.scripts, 0)

    def test_missing_stage_three_fields_are_not_empty_assessments(self):
        missing = "".join(self.page({}).text)
        null = "".join(self.page({"unit_changes": None, "risks": None, "agent": None}).text)
        empty = "".join(self.page({"unit_changes": [], "risks": [],
                                 "agent": {"status": "not_requested", "model": None,
                                           "turns": 0, "tool_calls": 0,
                                           "investigated_finding_ids": [],
                                           "stop_reason": "Не запрашивался"}}).text)
        for text in (missing, null):
            self.assertIn("Не оценивалось: поле unit_changes", text)
            self.assertIn("Не оценивалось: поле risks", text)
            self.assertIn("сведения о выполнении агента отсутствуют", text)
        self.assertNotIn("Не оценивалось", empty)
        self.assertIn("Список изменений подразделений пуст", empty)
        self.assertIn("Список межподразделенческих рисков пуст", empty)
        self.assertIn("не доказывает отсутствие", empty)
        self.assertIn("Не запрашивался", empty)

    def test_missing_sources_and_inexact_quotes_never_become_citation_links(self):
        report = {
            "clauses": [
                {"doc": "before", "clause_id": "1", "text": "before exact",
                 "parent_id": "missing", "unit_ids": ["missing"]},
                {"doc": "after", "clause_id": "1", "text": "after exact"},
            ],
            "conclusion": [{"text": "Проверить", "finding_ids": ["missing"],
                            "unit_change_ids": ["missing"], "risk_ids": ["missing"],
                            "citations": [
                                {"doc": "before", "clause_id": "1", "quote": "before exact"},
                                {"doc": "before", "clause_id": "1", "quote": "after exact"},
                                {"doc": "after", "clause_id": "1", "quote": ""},
                                {"doc": "unknown", "clause_id": "1", "quote": "after exact"},
                            ]}],
        }
        page = self.page(report)
        # Only the verified exact quote can navigate; wrong-edition, empty and
        # dangling citations remain visible but do not masquerade as evidence.
        self.assertEqual(page.links, ["#" + anchor("clause", "before", "1")])
        text = "".join(page.text)
        self.assertIn("after exact", text)
        self.assertIn("Точная цитата не подтверждена", text)
        self.assertIn("Исходный пункт отсутствует", text)
        self.assertIn("источник или результат отсутствует", text)

    def test_duplicate_source_keys_cannot_ambiguously_target_a_quote(self):
        report = {"clauses": [
            {"doc": "after", "clause_id": "1", "text": "Unrelated first text"},
            {"doc": "after", "clause_id": "1", "text": "Quoted second text"},
        ], "conclusion": [{"text": "Review", "citations": [
            {"doc": "after", "clause_id": "1", "quote": "Quoted second text"}
        ]}]}
        with self.assertRaises(ValueError):
            render_report(report)

    def test_wrong_edition_and_nonstructural_lineage_are_visible(self):
        report = {
            "documents": [{"doc": "old", "edition": "before"}],
            "clauses": [{"doc": "old", "clause_id": "1", "text": "Duty"}],
            "units": [{"doc": "old", "unit_id": "r", "kind": "role", "name": "Role"}],
            "unit_changes": [{"id": "u", "status": "created", "before": [],
                              "after": [{"doc": "old", "unit_id": "r"}]}],
            "risks": [{"id": "r", "kind": "potential_conflict_of_interest",
                       "refs": [{"doc": "old", "clause_id": "1"}],
                       "units": [{"doc": "old", "unit_id": "r"}]}],
        }
        page = self.page(report)
        text = "".join(page.text)
        self.assertIn("не соответствует редакции", text)
        self.assertIn("роль, а не структурное подразделение", text)
        self.assertIn("Duty", text)
        self.assertTrue(all(href[1:] in page.ids for href in page.links))

if __name__ == "__main__":
    unittest.main()
