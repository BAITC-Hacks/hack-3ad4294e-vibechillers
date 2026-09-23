"""Regression checks for citations available only through Report.units."""

import unittest
from html.parser import HTMLParser

from export_report import render_report


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
        self.assertEqual(len(page.links), 1)
        self.assertTrue(page.links[0].startswith("#"))
        self.assertIn(page.links[0][1:], page.ids)


if __name__ == "__main__":
    unittest.main()
