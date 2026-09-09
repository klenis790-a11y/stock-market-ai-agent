"""Offline specialist data contracts; no agent execution or provider requests."""
import unittest
from dataclasses import fields
from src.models import (
    SpecialistAnalysis, SpecialistContext, MultiAgentSynthesisContext,
    InterpretationStatement, ForecastStatement, InvestmentAnalysis,
    DecisionMemoryContext, PortfolioInput,
)
from src.specialists import ACTIVE_SPECIALISTS
from src.portfolio_calculations import build_portfolio_snapshot
from src.portfolio_risk import assess_portfolio_risk
from src.portfolio_context import build_portfolio_analysis_context


def result(**overrides):
    return SpecialistAnalysis(**(dict(
        specialist_name='fundamental', ticker='TEST', summary='Evidence interpretation',
        key_findings=[InterpretationStatement('Finding', ['E001'])],
        risks=[InterpretationStatement('Risk', ['E002'])],
        scenarios=[ForecastStatement('Scenario', ['E001'])],
        confidence_score=60, missing_data=['Unavailable context'],
    ) | overrides))


class SpecialistContractTests(unittest.TestCase):
    def test_valid_analysis(self):
        item = result()
        self.assertIsInstance(item.key_findings[0], InterpretationStatement)
        self.assertIsInstance(item.risks[0], InterpretationStatement)
        self.assertIsInstance(item.scenarios[0], ForecastStatement)
        self.assertEqual(item.key_findings[0].evidence_refs, ['E001'])

    def test_normalization(self):
        self.assertEqual(result(ticker=' test ').ticker, 'TEST')
        self.assertEqual(SpecialistContext(' test ', ' risk ', {}).ticker, 'TEST')

    def test_empty_name(self):
        for name in ('', ' ', None):
            with self.subTest(name=name):
                with self.assertRaises(ValueError): result(specialist_name=name)
                with self.assertRaises(ValueError): SpecialistContext('TEST', name, {})

    def test_empty_ticker(self):
        with self.assertRaises(ValueError): result(ticker=' ')
        with self.assertRaises(ValueError): SpecialistContext(' ', 'risk', {})

    def test_empty_summary(self):
        for summary in ('', ' ', None):
            with self.assertRaises(ValueError): result(summary=summary)

    def test_confidence(self):
        for score in (-1, 101, float('nan'), float('inf'), True, '60'):
            with self.assertRaises(ValueError): result(confidence_score=score)
        for score in (0, 100): self.assertEqual(result(confidence_score=score).confidence_score, score)

    def test_context_defaults(self):
        context = SpecialistContext('TEST', 'risk', {'missing_data': ['missing']})
        self.assertIsNone(context.portfolio_context)
        self.assertIsNone(context.decision_memory)
        self.assertEqual(context.research_evidence['missing_data'], ['missing'])

    def test_optional_portfolio(self):
        snapshot = build_portfolio_snapshot(PortfolioInput([], 100), {})
        portfolio = build_portfolio_analysis_context(snapshot, assess_portfolio_risk(snapshot), 'TEST')
        self.assertIs(SpecialistContext('TEST', 'risk', {}, portfolio).portfolio_context, portfolio)

    def test_optional_memory(self):
        memory = DecisionMemoryContext('TEST', [])
        context = SpecialistContext('TEST', 'risk', {}, decision_memory=memory)
        self.assertIs(context.decision_memory, memory)
        self.assertNotIn('prior_decisions', context.research_evidence)

    def test_synthesis_order(self):
        items = [result(specialist_name=name) for name in ('risk', 'fundamental', 'hypothetical')]
        synthesis = MultiAgentSynthesisContext('TEST', items)
        self.assertEqual([x.specialist_name for x in synthesis.specialist_results], ['risk', 'fundamental', 'hypothetical'])
        self.assertEqual(MultiAgentSynthesisContext('TEST', []).specialist_results, [])

    def test_generic_names(self):
        for name in ('fundamental', 'risk', 'hypothetical'):
            self.assertEqual(result(specialist_name=name).specialist_name, name)
            self.assertEqual(SpecialistContext('TEST', name, {}).specialist_name, name)

    def test_activation_separate(self):
        self.assertEqual(ACTIVE_SPECIALISTS, ('fundamental', 'risk'))
        self.assertNotIn('hypothetical', ACTIVE_SPECIALISTS)

    def test_shared_fields(self):
        self.assertEqual({f.name for f in fields(SpecialistAnalysis)}, {
            'specialist_name', 'ticker', 'summary', 'key_findings', 'risks',
            'scenarios', 'confidence_score', 'missing_data'})
        self.assertEqual({f.name for f in fields(SpecialistContext)}, {
            'ticker', 'specialist_name', 'research_evidence', 'portfolio_context', 'decision_memory'})
        self.assertEqual({f.name for f in fields(MultiAgentSynthesisContext)}, {
            'ticker', 'specialist_results', 'portfolio_context', 'decision_memory'})

    def test_existing_final_contract(self):
        self.assertEqual({f.name for f in fields(InvestmentAnalysis)}, {
            'ticker', 'recommendation', 'confidence_score', 'fundamental_assessment',
            'valuation_assessment', 'earnings_assessment', 'bull_case', 'bear_case',
            'supporting_evidence', 'major_risks', 'thesis_invalidation_conditions',
            'scenarios', 'missing_data', 'reasoning_summary', 'material_evidence_review',
            'portfolio_assessment'})


class FundamentalEvidenceTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        self.network = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.evidence = {
            'ticker': 'TEST', 'source': 'fixture', 'generated_at': '2026-01-01',
            'retrieved_facts': {
                'stock': {'ticker': 'TEST', 'company_name': 'Test', 'pe_ratio': 20,
                          'revenue': 100, 'net_income': 10, 'free_cash_flow': 7},
                'news': [{'title': 'Excluded', 'sentiment': 1}],
                'income_statements': [{'fiscal_date_ending': '2025-12-31',
                                      'total_revenue': 100, 'operating_income': 20, 'net_income': 10}],
                'balance_sheets': [{'fiscal_date_ending': '2025-12-31',
                                   'cash_and_cash_equivalents': 5, 'total_debt': 10,
                                   'shareholder_equity': 20, 'total_assets': 50, 'total_liabilities': 30}],
                'cash_flows': [{'fiscal_date_ending': '2025-12-31',
                                'operating_cash_flow': 10, 'capital_expenditures': 3}],
                'earnings': [{'surprise_percentage': 4}],
                'earnings_call_transcript': [{'content': 'Excluded transcript'}],
            },
            'calculated_metrics': {
                'income_statement_metrics': {'revenue_growth': 0.1, 'net_income_growth': 0.2,
                                             'operating_margin': 0.2, 'net_margin': 0.1},
                'cash_flow_metrics': {'free_cash_flow': 7, 'free_cash_flow_growth': -0.1,
                                     'free_cash_flow_margin': 0.07},
                'balance_sheet_metrics': {'debt_to_equity': 0.5, 'liabilities_to_assets': 0.6,
                                         'cash_to_debt': 0.5},
                'earnings_metrics': {'latest_surprise_percentage': 4},
            },
            'missing_data': ['Fixture missing data'],
        }

    def selected(self):
        from src.specialists import select_fundamental_evidence
        return select_fundamental_evidence(self.evidence)

    def test_financial_fields_preserved(self):
        selected = {e['path']: e['value'] for e in self.selected()['EVIDENCE_CATALOG']}
        for group in ('income_statements', 'balance_sheets', 'cash_flows'):
            for name, value in self.evidence['retrieved_facts'][group][0].items():
                self.assertEqual(selected[f'retrieved_facts.{group}.0.{name}'], value)
        for name in ('revenue', 'net_income', 'free_cash_flow', 'company_name'):
            self.assertEqual(selected[f'retrieved_facts.stock.{name}'], self.evidence['retrieved_facts']['stock'][name])

    def test_metrics_preserved_without_calculation(self):
        self.evidence['calculated_metrics']['cash_flow_metrics']['free_cash_flow'] = 123
        selected = {e['path']: e['value'] for e in self.selected()['EVIDENCE_CATALOG']}
        for group, metrics in self.evidence['calculated_metrics'].items():
            if group != 'earnings_metrics':
                for name, value in metrics.items():
                    self.assertEqual(selected[f'calculated_metrics.{group}.{name}'], value)

    def test_canonical_provenance(self):
        from src.evidence import build_evidence_catalog, resolve_evidence_id
        catalog = build_evidence_catalog(self.evidence)
        selected = self.selected()['EVIDENCE_CATALOG']
        self.assertEqual(selected, [e for e in catalog if e in selected])
        for entry in selected:
            self.assertEqual(resolve_evidence_id(entry['evidence_id'], catalog, self.evidence), entry)

    def test_numbering_changes_follow_original_catalog(self):
        from src.evidence import build_evidence_catalog
        self.evidence['retrieved_facts'] = {'unrelated': 999, **self.evidence['retrieved_facts']}
        catalog = build_evidence_catalog(self.evidence)
        self.assertEqual(self.selected()['EVIDENCE_CATALOG'][0], catalog[1])

    def test_unrelated_excluded(self):
        paths = [e['path'] for e in self.selected()['EVIDENCE_CATALOG']]
        for word in ('news', 'earnings', 'pe_ratio', 'transcript'):
            self.assertFalse(any(word in path for path in paths))
        self.assertNotIn('recommendation', self.selected())

    def test_missing_not_fabricated(self):
        self.evidence['calculated_metrics']['cash_flow_metrics']['free_cash_flow_growth'] = None
        del self.evidence['calculated_metrics']['income_statement_metrics']['revenue_growth']
        paths = [e['path'] for e in self.selected()['EVIDENCE_CATALOG']]
        self.assertFalse(any(p.endswith(('free_cash_flow_growth', 'revenue_growth')) for p in paths))
        self.assertEqual(self.selected()['missing_data'], self.evidence['missing_data'])

    def test_determinism_and_copy_isolation(self):
        from copy import deepcopy
        original = deepcopy(self.evidence)
        a, b = self.selected(), self.selected()
        self.assertEqual(a, b)
        a['EVIDENCE_CATALOG'][0]['value'] = 'changed'
        a['missing_data'].append('changed')
        self.assertEqual(self.evidence, original)
        self.assertEqual(b, self.selected())

    def test_context_and_separation(self):
        from src.specialists import build_fundamental_context
        from src.models import DecisionMemoryItem
        snapshot = build_portfolio_snapshot(PortfolioInput([], 100), {})
        portfolio = build_portfolio_analysis_context(snapshot, assess_portfolio_risk(snapshot), 'TEST')
        memory = DecisionMemoryContext('TEST', [DecisionMemoryItem(
            'old', 'TEST', '2020-01-01', 'Hold', 50, None,
            'Historical free cash flow growth was 9%', [], [], [], [], [])])
        self.evidence['calculated_metrics']['cash_flow_metrics']['free_cash_flow_growth'] = None
        context = build_fundamental_context(self.evidence, portfolio, memory)
        self.assertEqual(context.specialist_name, 'fundamental')
        self.assertEqual(context.research_evidence, self.selected())
        self.assertIs(context.portfolio_context, portfolio)
        self.assertIs(context.decision_memory, memory)
        self.assertNotIn('portfolio_context', context.research_evidence)
        self.assertNotIn('decision_memory', context.research_evidence)
        self.assertFalse(any(e['path'].endswith('free_cash_flow_growth')
                             for e in context.research_evidence['EVIDENCE_CATALOG']))

    def test_context_ticker_and_defaults(self):
        from src.specialists import build_fundamental_context
        self.evidence['ticker'] = ' test '
        context = build_fundamental_context(self.evidence)
        self.assertEqual(context.ticker, 'TEST')
        self.assertIsNone(context.portfolio_context)
        self.assertIsNone(context.decision_memory)
