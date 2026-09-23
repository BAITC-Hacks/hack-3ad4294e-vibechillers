"""Source-context regressions; run with `python -m unittest app.audit.test_context`."""
from __future__ import annotations

import unittest

from . import Document, run_deterministic_audit, verify_citations
from .models import ClauseRef, Finding
from .report import resolve_alignment
from .parser import owner_keys


def audit(before: str, after: str):
    documents = [
        Document(doc=side, doc_id=side, sha256=side[0] * 64, edition=side, source=side + '.txt')
        for side in ('before', 'after')
    ]
    return run_deterministic_audit('context-regression', documents, {
        'before': [{'page': 1, 'text': before}],
        'after': [{'page': 1, 'text': after}],
    })


def child_findings(report, clause_id='1.1.1'):
    return [f for f in report.findings if any(r.clause_id == clause_id for r in f.before)]


class SourceContextTests(unittest.TestCase):
    def test_role_change_keeps_duty_and_cites_accountability(self):
        duty = 'Ведение реестра оборудования.'
        report = audit(
            '1. Ответственность\n1.1. Главный инженер отвечает за:\n1.1.1. ' + duty,
            '1. Ответственность\n1.1. Технический директор отвечает за:\n1.1.1. ' + duty,
        )
        finding, = child_findings(report)
        self.assertEqual(finding.status, 'moved')
        self.assertTrue(finding.review_required)
        self.assertTrue({('before', '1.1'), ('after', '1.1')} <= {(c.doc, c.clause_id) for c in finding.citations})
        self.assertEqual([c.text for c in report.clauses if c.clause_id == '1.1.1'], [duty, duty])
        self.assertFalse(verify_citations(finding.citations + [c for u in report.units for c in u.citations], report.clauses).invalid)

    def test_parent_rewording_alone_does_not_change_preserved_duty(self):
        report = audit(
            '1. Ответственность\n1.1. Координатор проверки информирует о планируемой проверке:\n'
            'а) О сроках проведения.',
            '1. Обязанности работников\n1.1. Координатор информирует о проверке:\n'
            'а) О сроках проведения.',
        )
        finding, = child_findings(report, '1.1/а')
        self.assertEqual(finding.status, 'unchanged')

    def test_owner_transfer_with_reworded_intro_remains_moved(self):
        report = audit(
            '1. Права\n1.1. Директор отдела обязан обеспечить выполнение задач и имеет право:\n'
            '1.1.1. Вести переписку по вопросам деятельности.',
            '1. Права\n1.1. Руководители служб обязаны обеспечить выполнение всех задач и имеют право:\n'
            '1.1.1. Вести переписку по вопросам деятельности.',
        )
        finding, = child_findings(report)
        self.assertEqual(finding.status, 'moved')
        self.assertTrue(finding.review_required)
    def test_passive_assignment_intro_rewording_keeps_child(self):
        report = audit(
            '1. На Отдел возлагаются следующие функции:\n1.1. Ведение реестра.',
            '1. На Отдел возлагаются следующие задачи и функции:\n1.1. Ведение реестра.',
        )
        finding, = report.findings
        self.assertEqual(finding.status, 'unchanged')


    def test_parent_citation_cannot_substitute_missing_child_evidence(self):
        from .models import Citation
        from .report import build_report
        report = audit('1. Обязанности\n1.1. Ведение реестра.', '1. Обязанности\n1.1. Ведение реестра.')
        finding, = report.findings
        broken = finding.model_copy(update={'citations': [
            Citation(doc='before', clause_id='1', quote='Обязанности'),
            Citation(doc='after', clause_id='1', quote='Обязанности'),
        ]})
        checked = build_report(report.run_id, report.documents, report.clauses, report.units, [broken])
        self.assertEqual(checked.findings[0].status, 'unresolved')
        self.assertTrue(checked.findings[0].review_required)

    def test_changed_permission_cannot_be_confident_unchanged(self):
        report = audit(
            '1. Ответственность\n1.1. Главный инженер вправе:\n1.1.1. Передавать сведения подрядчику.',
            '1. Ответственность\n1.1. Главному инженеру запрещено:\n1.1.1. Передавать сведения подрядчику.',
        )
        finding, = child_findings(report)
        self.assertEqual(finding.status, 'unresolved')
        self.assertTrue(finding.review_required)
        self.assertTrue(any('запрещено' in c.quote and c.clause_id == '1.1' for c in finding.citations))

    def test_delegate_mention_does_not_become_descendant_owner(self):
        report = audit(
            '1. Ответственность\n1.1. Главный инженер отвечает за:\n1.1.1. Делегирует начальнику отдела подготовку отчета:\nа) Ведение реестра оборудования.',
            '1. Ответственность\n1.1. Главный инженер отвечает за:\n1.1.1. Делегирует руководителю службы подготовку отчета:\nа) Ведение реестра оборудования.',
        )
        owners = []
        for doc in ('before', 'after'):
            clauses = {c.clause_id:c for c in report.clauses if c.doc == doc}
            units = {u.unit_id:u for u in report.units if u.doc == doc}
            owners.append(owner_keys(clauses['1.1.1/а'], clauses, units))
        self.assertTrue(owners[0])
        self.assertEqual(owners[0], owners[1])
        self.assertTrue(all('главный инженер' in key for key in owners[0]))
        finding, = child_findings(report, '1.1.1/а')
        self.assertEqual(finding.status, 'unresolved')

    def test_shared_existing_duties_are_not_new_duplication(self):
        text = ('1. Ответственность\n1.1. Главный инженер отвечает за:\n1.1.1. Ведение реестра оборудования.'
                '\n1.2. Технический директор отвечает за:\n1.2.1. Ведение реестра оборудования.')
        report = audit(text, text)
        self.assertTrue(all(f.status == 'unchanged' for f in report.findings))
        self.assertEqual(report.coverage.before_total, report.coverage.before_accounted)
        self.assertEqual(report.coverage.after_total, report.coverage.after_accounted)

    def test_unique_same_number_weak_candidate_remains_unresolved(self):
        report = audit('1. Обязанности\n1.1. Подготовка годового отчета о финансовых рисках.',
                       '1. Обязанности\n1.1. Подготовка ежемесячного отчета о технических авариях.')
        finding, = report.findings
        self.assertEqual(finding.status, 'unresolved')
        self.assertTrue(finding.review_required)

    def test_near_exact_child_does_not_bypass_parent_review(self):
        report = audit(
            '1. Обязанности\n1.1. Главный инженер вправе:\n1.1.1. Передавать сведения об оборудовании подрядчику.',
            '1. Обязанности\n1.1. Главному инженеру запрещено:\n1.1.1. Передавать сведения об оборудовании подрядчикам.',
        )
        finding, = child_findings(report)
        self.assertTrue(finding.review_required)
        self.assertTrue(any('запрещено' in c.quote for c in finding.citations))

    def test_context_ambiguous_repeat_keeps_one_candidate_group(self):
        report = audit(
            '1. Обязанности\n1.1. Начальник отдела обязан:\n1.1.1. Вести реестр оборудования.',
            '1. Обязанности\n1.1. Начальник отдела имеет право:\n1.1.1. Вести реестр оборудования.'
            '\n1.2. Директор обязан:\n1.2.1. Вести реестр оборудования.',
        )
        finding, = child_findings(report)
        self.assertEqual(finding.status, 'unresolved')
        self.assertEqual({r.clause_id for r in finding.after}, {'1.1.1', '1.2.1'})

    def test_negation_stays_in_governing_predicate_not_role_name(self):
        for before, after in (
            ('Главный инженер может:', 'Главный инженер не может:'),
            ('Главный инженер отвечает за:', 'Главный инженер не отвечает за:'),
            ('Работники должны:', 'Работники не должны:'),
        ):
            with self.subTest(before=before, after=after):
                report = audit(
                    '1. Обязанности\n1.1. ' + before + '\n1.1.1. Передавать сведения подрядчику.',
                    '1. Обязанности\n1.1. ' + after + '\n1.1.1. Передавать сведения подрядчику.',
                )
                finding, = child_findings(report)
                self.assertEqual(finding.status, 'unresolved')
                self.assertTrue(finding.review_required)

    def test_standalone_role_restriction_is_not_unchanged(self):
        report = audit(
            '1. Обязанности\nГлавный инженер вправе:\n1.1. Передавать сведения подрядчику.',
            '1. Обязанности\nГлавный инженер не вправе:\n1.1. Передавать сведения подрядчику.',
        )
        finding, = report.findings
        self.assertEqual(finding.status, 'unresolved')
        self.assertTrue(any('не вправе' in c.quote for c in finding.citations))

    def test_delegate_first_passive_clause_does_not_define_accountability(self):
        report = audit(
            '1. Обязанности\n1.1. Главный инженер отвечает за:\n'
            '1.1.1. Начальнику отдела делегируется подготовка отчета:\nа) Ведение реестра.',
            '1. Обязанности\n1.1. Главный инженер отвечает за:\n'
            '1.1.1. Руководителю службы делегируется подготовка отчета:\nа) Ведение реестра.',
        )
        for doc in ('before', 'after'):
            clauses = {c.clause_id:c for c in report.clauses if c.doc == doc}
            units = {u.unit_id:u for u in report.units if u.doc == doc}
            self.assertEqual(owner_keys(clauses['1.1.1/а'], clauses, units), frozenset({'главный инженер'}))
        finding, = child_findings(report, '1.1.1/а')
        self.assertEqual(finding.status, 'unresolved')

    def test_plain_role_after_nested_item_resets_scope_at_next_list_level(self):
        prefix = ('1. Обязанности\nГлавный аудитор:\n1.1. Подготовка отчета:'
                  '\n1.1.1. Ведение реестра.\nа) Регистрация записей.\n')
        report = audit(prefix + 'Директор:\n1.2. Архивирование отчета.',
                       prefix + 'Директор не вправе:\n1.2. Архивирование отчета.')
        finding, = child_findings(report, '1.2')
        self.assertEqual(finding.status, 'unresolved')
        self.assertTrue(finding.review_required)
        for doc in ('before', 'after'):
            clauses = {c.clause_id:c for c in report.clauses if c.doc == doc}
            units = {u.unit_id:u for u in report.units if u.doc == doc}
            self.assertEqual(owner_keys(clauses['1.2'], clauses, units), frozenset({'директор'}))

    def test_later_plain_role_heading_does_not_leak_previous_owner(self):
        text = ('1. Обязанности\nГлавный аудитор:\n1.1. Подготовка отчета.'
                '\n1.2. Ведение реестра.\nДиректор:\n1.3. Архивирование отчета.')
        report = audit(text, text)
        clauses = {c.clause_id:c for c in report.clauses if c.doc == 'before'}
        units = {u.unit_id:u for u in report.units if u.doc == 'before'}
        self.assertEqual(owner_keys(clauses['1.1'], clauses, units), frozenset({'главный аудитор'}))
        self.assertEqual(owner_keys(clauses['1.3'], clauses, units), frozenset({'директор'}))
        from ..agent.audit_llm import _adjudication_prompt
        from ..agent.audit_tools import AuditContext
        import json
        finding, = child_findings(report, '1.3')
        prompt = json.loads(_adjudication_prompt(AuditContext.from_report(report), [finding]).split('\n', 2)[2])
        candidate = prompt[0]['offered_before'][0]
        self.assertEqual([units[uid].name for uid in candidate['governing_role_unit_ids']], ['Директор'])

    def test_standalone_role_scopes_siblings_until_next_role(self):
        text = (
            '1. Обязанности\nГлавный аудитор:\n1.1. Подготавливает отчет.\n1.1.1. Ведение реестра.'
            '\n1.2. Передает отчет комиссии.\n1.3. Директор отдела качества и методологии:'
            '\n1.3.1. Проверка реестра.\n1.4. Архивирование отчета.'
        )
        report = audit(text, text)
        clauses = {c.clause_id: c for c in report.clauses if c.doc == 'before'}
        units = {u.unit_id: u for u in report.units if u.doc == 'before'}
        for cid in ('1.1', '1.1.1', '1.2'):
            self.assertEqual(owner_keys(clauses[cid], clauses, units), frozenset({'главный аудитор'}))
        self.assertEqual(owner_keys(clauses['1.3.1'], clauses, units),
                         frozenset({'директор отдела качества и методологии'}))
        self.assertFalse(owner_keys(clauses['1.4'], clauses, units))
        self.assertEqual(clauses['1.1'].parent_id, '1')
        from ..agent.audit_llm import _adjudication_prompt
        from ..agent.audit_tools import AuditContext
        import json
        finding, = child_findings(report)
        prompt = json.loads(_adjudication_prompt(AuditContext.from_report(report), [finding]).split('\n', 2)[2])
        candidate = prompt[0]['offered_before'][0]
        self.assertTrue(candidate['governing_role_unit_ids'])
        source = candidate['context_only']['sibling_role_scope']
        self.assertIsNotNone(source)
        self.assertEqual(source['clause_id'], next(u.citations[0].clause_id for u in units.values() if u.name == 'Главный аудитор'))

    def test_offered_split_and_merge_remain_many_ref_and_reviewable(self):
        report = audit('1. Функции\n1.1. Ведение реестра и подготовка отчета.\n1.2. Согласование отчета.',
                       '1. Функции\n1.1. Ведение реестра.\n1.2. Подготовка и согласование отчета.')
        refs = {side: [ClauseRef(doc=side, clause_id=cid) for cid in ('1.1', '1.2')]
                for side in ('before', 'after')}
        for before, after in ((refs['before'][:1], refs['after']), (refs['before'], refs['after'][:1])):
            with self.subTest(before=len(before), after=len(after)):
                offered = Finding(id='compound', status='unresolved', before=before, after=after,
                                  citations=[], reason='Ambiguous compound duty', method='lexical', review_required=True)
                result = resolve_alignment(offered, report.clauses, before=before, after=after,
                                           status='changed', reason='Explicit compound duty retained across the offered clauses.')
                self.assertEqual(result.status, 'changed')
                self.assertEqual(result.before, before)
                self.assertEqual(result.after, after)
                self.assertTrue(result.review_required)
                self.assertFalse(verify_citations(result.citations, report.clauses).invalid)


if __name__ == '__main__':
    unittest.main()
