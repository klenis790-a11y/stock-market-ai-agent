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


class FundamentalAITests(unittest.TestCase):
    def setUp(self):
        import json
        from unittest.mock import patch
        from src.specialists import build_fundamental_context
        self.network = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.environment = patch.dict('os.environ', {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.context = build_fundamental_context({
            'ticker': ' test ', 'retrieved_facts': {'stock': {'pe_ratio': 20, 'revenue': 100}},
            'calculated_metrics': {}, 'missing_data': ['Cash flow unavailable'],
        })
        self.ref = self.context.research_evidence['EVIDENCE_CATALOG'][0]['evidence_id']
        self.data = dict(specialist_name='fundamental', ticker='TEST', summary='Summary',
                         confidence_score=60, missing_data=['Other limitation'],
                         **{name: [{'text': 'Fixture text', 'evidence_refs': [self.ref]}]
                            for name in ('key_findings', 'risks', 'scenarios')})
        self.request = patch('src.fundamental_analysis.request_text', return_value=json.dumps(self.data))
        self.mock = self.request.start()
        self.addCleanup(self.request.stop)

    def run_analysis(self):
        from src.fundamental_analysis import analyze_fundamental_specialist
        return analyze_fundamental_specialist(self.context)

    def respond(self, data):
        import json
        self.mock.return_value = json.dumps(data)
        return self.run_analysis()

    def test_valid_mocked_response(self):
        item = self.run_analysis()
        self.assertIsInstance(item, SpecialistAnalysis)
        self.assertEqual((item.specialist_name, item.ticker, item.confidence_score), ('fundamental', 'TEST', 60))
        self.assertIsInstance(item.key_findings[0], InterpretationStatement)
        self.assertIsInstance(item.risks[0], InterpretationStatement)
        self.assertIsInstance(item.scenarios[0], ForecastStatement)
        self.assertEqual(item.key_findings[0].evidence_refs, [self.ref])
        self.mock.assert_called_once()

    def test_selected_input_and_schema(self):
        import json
        self.run_analysis()
        args = self.mock.call_args.kwargs
        self.assertEqual(json.loads(args['input'])['CURRENT VERIFIED EVIDENCE'], self.context.research_evidence)
        schema = args['text']['format']['schema']
        self.assertTrue(args['text']['format']['strict'])
        self.assertNotIn('recommendation', schema['properties'])
        self.assertEqual(set(schema['required']), set(self.data))

    def test_role_and_boundaries(self):
        self.run_analysis()
        instructions = self.mock.call_args.kwargs['instructions']
        for text in ('You are the Fundamental Analyst', 'Do not make Buy',
                     'Current verified evidence is authoritative',
                     'Memory cannot replace missing current evidence',
                     'Prior recommendations are not current evidence',
                     'PORTFOLIO CONTEXT is separate', 'explicitly forward-looking',
                     'Retrieval or', 'historical', 'missing_data'):
            self.assertIn(text, instructions)

    def test_missing_data_preserved(self):
        self.assertEqual(self.run_analysis().missing_data, ['Other limitation', 'Cash flow unavailable'])

    def test_invalid_refs(self):
        for ref in ('E999', 'E001', 'retrieved_facts.stock.revenue', 'portfolio_weight'):
            with self.subTest(ref=ref):
                self.data['key_findings'][0]['evidence_refs'] = [ref]
                with self.assertRaises(ValueError): self.respond(self.data)

    def test_empty_refs_rejected(self):
        self.data['risks'][0]['evidence_refs'] = []
        with self.assertRaises(ValueError): self.respond(self.data)

    def test_wrong_context_before_request(self):
        self.context.specialist_name = 'risk'
        with self.assertRaises(ValueError): self.run_analysis()
        self.mock.assert_not_called()

    def test_wrong_response_identity(self):
        for field, value in (('ticker', 'OTHER'), ('specialist_name', 'risk')):
            data = dict(self.data, **{field: value})
            with self.assertRaises(ValueError): self.respond(data)

    def test_malformed_json(self):
        self.mock.return_value = 'not JSON'
        with self.assertRaisesRegex(ValueError, 'invalid specialist JSON'): self.run_analysis()

    def test_required_and_extra_fields(self):
        for field in self.data:
            data = dict(self.data)
            del data[field]
            with self.assertRaises(ValueError): self.respond(data)
        with self.assertRaises(ValueError): self.respond(dict(self.data, recommendation='Hold'))
        with self.assertRaises(ValueError): self.respond([])

    def test_confidence_validation(self):
        for score in (-1, 101, True, None):
            with self.assertRaises(ValueError): self.respond(dict(self.data, confidence_score=score))
        for score in (0, 100):
            self.assertEqual(self.respond(dict(self.data, confidence_score=score)).confidence_score, score)

    def test_statement_shape(self):
        self.data['scenarios'][0]['statement_type'] = 'retrieved_fact'
        with self.assertRaises(ValueError): self.respond(self.data)

    def test_context_separation_and_no_mutation(self):
        import copy
        import json
        from src.models import DecisionMemoryItem
        self.context.decision_memory = DecisionMemoryContext('TEST', [DecisionMemoryItem(
            'old', 'TEST', '2020-01-01', 'Hold', 50, None, 'Historical cash flow was 100',
            [InterpretationStatement('Old risk', ['E777'])], [], [], [], [])])
        snapshot = build_portfolio_snapshot(PortfolioInput([], 100), {})
        self.context.portfolio_context = build_portfolio_analysis_context(snapshot, assess_portfolio_risk(snapshot), 'TEST')
        before = copy.deepcopy(self.context)
        item = self.run_analysis()
        payload = json.loads(self.mock.call_args.kwargs['input'])
        self.assertEqual(payload['CURRENT VERIFIED EVIDENCE'], before.research_evidence)
        self.assertIn('HISTORICAL DECISION MEMORY', payload)
        self.assertIn('PORTFOLIO CONTEXT', payload)
        self.assertNotIn('E777', json.dumps(payload['HISTORICAL DECISION MEMORY']))
        self.assertIn('Cash flow unavailable', item.missing_data)
        self.assertEqual(before, self.context)

    def test_provider_error_propagates_without_retry(self):
        self.mock.side_effect = RuntimeError('OpenAI request failed.')
        with self.assertRaises(RuntimeError): self.run_analysis()
        self.mock.assert_called_once()


class RiskEvidenceTests(unittest.TestCase):
    def setUp(self):
        # Reuse the normalized financial fixture without inheriting its test cases.
        FundamentalEvidenceTests.setUp(self)
        self.evidence['retrieved_facts']['balance_sheets'][0]['long_term_debt'] = 8
        self.evidence['retrieved_facts']['earnings'][0].update(
            fiscal_date_ending='2025-12-31', reported_date='2026-01-20',
            reported_eps=2, estimated_eps=1.9)
        self.evidence['calculated_metrics']['earnings_metrics'].update(
            average_surprise_percentage=3, beats_last_4_quarters=4, misses_last_4_quarters=0)

    def selected(self):
        from src.specialists import select_risk_evidence
        return select_risk_evidence(self.evidence)

    def test_balance_and_cash_flow(self):
        values = {e['path']: e['value'] for e in self.selected()['EVIDENCE_CATALOG']}
        for group in ('balance_sheets', 'cash_flows'):
            for name, value in self.evidence['retrieved_facts'][group][0].items():
                self.assertEqual(values[f'retrieved_facts.{group}.0.{name}'], value)

    def test_growth_leverage_and_earnings_metrics(self):
        values = {e['path']: e['value'] for e in self.selected()['EVIDENCE_CATALOG']}
        for group, names in (
            ('balance_sheet_metrics', ('debt_to_equity', 'liabilities_to_assets', 'cash_to_debt')),
            ('cash_flow_metrics', ('free_cash_flow', 'free_cash_flow_growth')),
            ('income_statement_metrics', ('revenue_growth', 'net_income_growth')),
            ('earnings_metrics', ('latest_surprise_percentage', 'average_surprise_percentage',
                                 'beats_last_4_quarters', 'misses_last_4_quarters')),
        ):
            for name in names:
                self.assertEqual(values[f'calculated_metrics.{group}.{name}'], self.evidence['calculated_metrics'][group][name])
        self.assertEqual(values['retrieved_facts.earnings.0.reported_date'], '2026-01-20')
        self.assertEqual(values['retrieved_facts.earnings.0.fiscal_date_ending'], '2025-12-31')

    def test_provenance_and_overlap(self):
        from src.evidence import build_evidence_catalog, resolve_evidence_id
        from src.specialists import select_fundamental_evidence
        catalog = build_evidence_catalog(self.evidence)
        selected = self.selected()['EVIDENCE_CATALOG']
        for entry in selected:
            self.assertEqual(resolve_evidence_id(entry['evidence_id'], catalog, self.evidence), entry)
        fundamental = select_fundamental_evidence(self.evidence)['EVIDENCE_CATALOG']
        common = [e for e in selected if e in fundamental]
        self.assertTrue(any(e['path'].endswith('free_cash_flow_growth') for e in common))
        self.assertEqual(selected, [e for e in catalog if e in selected])

    def test_unrelated_and_no_scores(self):
        paths = [e['path'] for e in self.selected()['EVIDENCE_CATALOG']]
        for word in ('news', 'transcript', 'pe_ratio', 'portfolio', 'risk_score'):
            self.assertFalse(any(word in path for path in paths))
        self.assertNotIn('recommendation', self.selected())

    def test_no_calculation_or_missing_substitution(self):
        self.evidence['calculated_metrics']['cash_flow_metrics']['free_cash_flow'] = 987
        self.evidence['calculated_metrics']['cash_flow_metrics']['free_cash_flow_growth'] = None
        del self.evidence['calculated_metrics']['balance_sheet_metrics']['cash_to_debt']
        values = {e['path']: e['value'] for e in self.selected()['EVIDENCE_CATALOG']}
        self.assertEqual(values['calculated_metrics.cash_flow_metrics.free_cash_flow'], 987)
        self.assertNotIn('calculated_metrics.cash_flow_metrics.free_cash_flow_growth', values)
        self.assertNotIn('calculated_metrics.balance_sheet_metrics.cash_to_debt', values)
        self.assertEqual(self.selected()['missing_data'], self.evidence['missing_data'])

    def test_deterministic_independent_view(self):
        from copy import deepcopy
        before = deepcopy(self.evidence)
        a, b = self.selected(), self.selected()
        self.assertEqual(a, b)
        a['EVIDENCE_CATALOG'][0]['value'] = 'changed'
        a['missing_data'].append('changed')
        self.assertEqual(before, self.evidence)
        self.assertEqual(b, self.selected())

    def test_context_defaults_and_ticker(self):
        from src.specialists import build_risk_context
        self.evidence['ticker'] = ' test '
        context = build_risk_context(self.evidence)
        self.assertIsInstance(context, SpecialistContext)
        self.assertEqual((context.ticker, context.specialist_name), ('TEST', 'risk'))
        self.assertIsNone(context.portfolio_context)
        self.assertIsNone(context.decision_memory)

    def test_portfolio_policy_and_memory_stay_separate(self):
        from copy import deepcopy
        from src.specialists import build_risk_context
        from src.models import PortfolioPositionInput, DecisionMemoryItem
        snapshot = build_portfolio_snapshot(PortfolioInput([PortfolioPositionInput('TEST', 10, 5)], 0), {})
        portfolio = build_portfolio_analysis_context(snapshot, assess_portfolio_risk(snapshot), 'TEST')
        memory = DecisionMemoryContext('TEST', [DecisionMemoryItem(
            'old', 'TEST', '2020-01-01', 'Hold', 50, None, 'Historical cash-to-debt was 3',
            [], [], [], [], [])])
        self.evidence['calculated_metrics']['balance_sheet_metrics']['cash_to_debt'] = None
        before = deepcopy((self.evidence, portfolio, memory))
        context = build_risk_context(self.evidence, portfolio, memory)
        self.assertIs(context.portfolio_context, portfolio)
        self.assertIs(context.decision_memory, memory)
        self.assertFalse(context.portfolio_context.portfolio_risk_assessment.concentration_policy_evaluable)
        self.assertEqual(context.research_evidence, self.selected())
        self.assertFalse(any(e['path'].endswith('cash_to_debt') for e in context.research_evidence['EVIDENCE_CATALOG']))
        self.assertEqual(before, (self.evidence, portfolio, memory))
