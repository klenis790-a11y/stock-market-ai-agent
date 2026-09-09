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
        self.assertEqual(tuple(ACTIVE_SPECIALISTS), ('fundamental', 'risk'))
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


class RiskAITests(unittest.TestCase):
    def setUp(self):
        import json
        from unittest.mock import patch
        from src.specialists import build_risk_context
        for patcher in (patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')),
                        patch.dict('os.environ', {}, clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.context = build_risk_context({
            'ticker': ' test ', 'retrieved_facts': {'stock': {'pe_ratio': 20, 'free_cash_flow': 7}},
            'calculated_metrics': {}, 'missing_data': ['Debt unavailable']})
        self.ref = self.context.research_evidence['EVIDENCE_CATALOG'][0]['evidence_id']
        self.data = dict(specialist_name='risk', ticker='TEST', summary='Risk summary',
                         confidence_score=60, missing_data=[], **{
                             name: [{'text': 'Fixture', 'evidence_refs': [self.ref]}]
                             for name in ('key_findings', 'risks', 'scenarios')})
        patcher = patch('src.risk_analysis.request_text', return_value=json.dumps(self.data))
        self.mock = patcher.start()
        self.addCleanup(patcher.stop)

    def run_analysis(self):
        from src.risk_analysis import analyze_risk_specialist
        return analyze_risk_specialist(self.context)

    def respond(self, data):
        import json
        self.mock.return_value = json.dumps(data)
        return self.run_analysis()

    def test_valid_types_and_identity(self):
        item = self.run_analysis()
        self.assertEqual((item.specialist_name, item.ticker), ('risk', 'TEST'))
        self.assertIsInstance(item, SpecialistAnalysis)
        for name in ('key_findings', 'risks'):
            self.assertIsInstance(getattr(item, name)[0], InterpretationStatement)
        self.assertIsInstance(item.scenarios[0], ForecastStatement)
        self.assertEqual(item.risks[0].evidence_refs, [self.ref])
        self.mock.assert_called_once()

    def test_schema_and_instructions(self):
        from src.fundamental_analysis import FUNDAMENTAL_SCHEMA
        self.run_analysis()
        args = self.mock.call_args.kwargs
        schema = args['text']['format']['schema']
        self.assertEqual(schema['properties']['specialist_name']['enum'], ['risk'])
        self.assertEqual(FUNDAMENTAL_SCHEMA['properties']['specialist_name']['enum'], ['fundamental'])
        self.assertEqual(set(schema['required']), set(self.data))
        for field in ('recommendation', 'position_size', 'risk_score'):
            self.assertNotIn(field, schema['properties'])
        for phrase in ('You are the Risk Analyst', 'portfolio-only reasoning explicitly',
                       'Policy\nflags are authoritative', 'Memory cannot replace missing current facts',
                       'Current verified evidence takes priority', 'explicitly forward-looking',
                       'Missing means unknown', 'Do not make Buy'):
            self.assertIn(phrase, args['instructions'])

    def test_separate_context_and_missing_data(self):
        import copy
        import json
        from src.models import DecisionMemoryItem
        snapshot = build_portfolio_snapshot(PortfolioInput([], 100), {})
        self.context.portfolio_context = build_portfolio_analysis_context(snapshot, assess_portfolio_risk(snapshot), 'TEST')
        self.context.decision_memory = DecisionMemoryContext('TEST', [DecisionMemoryItem(
            'old', 'TEST', '2020', 'Hold', 50, None, 'Historical debt was 10',
            [InterpretationStatement('Historical risk', ['E777'])], [], [], [], [])])
        before = copy.deepcopy(self.context)
        item = self.run_analysis()
        payload = json.loads(self.mock.call_args.kwargs['input'])
        self.assertEqual(payload['CURRENT VERIFIED EVIDENCE'], before.research_evidence)
        self.assertIn('PORTFOLIO CONTEXT', payload)
        self.assertIn('HISTORICAL DECISION MEMORY', payload)
        self.assertNotIn('E777', json.dumps(payload['HISTORICAL DECISION MEMORY']))
        self.assertEqual(item.missing_data, ['Debt unavailable'])
        self.assertEqual(self.context, before)

    def test_invalid_company_refs(self):
        for ref in ('E999', 'E001', 'cash_weight', 'retrieved_facts.stock.free_cash_flow', 'old'):
            self.data['risks'][0]['evidence_refs'] = [ref]
            with self.assertRaises(ValueError): self.respond(self.data)

    def test_empty_refs_still_rejected(self):
        self.data['risks'][0]['evidence_refs'] = []
        with self.assertRaises(ValueError): self.respond(self.data)

    def test_wrong_context(self):
        self.context.specialist_name = 'fundamental'
        with self.assertRaises(ValueError): self.run_analysis()
        self.mock.assert_not_called()

    def test_malformed(self):
        self.mock.return_value = 'invalid'
        with self.assertRaisesRegex(ValueError, 'invalid specialist JSON'): self.run_analysis()
        for data in ([], {}, dict(self.data, risk_score=2), dict(self.data, recommendation='Hold')):
            with self.assertRaises(ValueError): self.respond(data)

    def test_required_fields(self):
        for field in self.data:
            data = dict(self.data)
            del data[field]
            with self.assertRaises(ValueError): self.respond(data)

    def test_confidence(self):
        for score in (-1, 101, None, True):
            with self.assertRaises(ValueError): self.respond(dict(self.data, confidence_score=score))
        for score in (0, 100):
            self.assertEqual(self.respond(dict(self.data, confidence_score=score)).confidence_score, score)

    def test_wrong_response_identity(self):
        for field, value in (('ticker', 'OTHER'), ('specialist_name', 'fundamental')):
            with self.assertRaises(ValueError): self.respond(dict(self.data, **{field: value}))

    def test_provider_failure_no_retry(self):
        self.mock.side_effect = RuntimeError('OpenAI request failed.')
        with self.assertRaises(RuntimeError): self.run_analysis()
        self.mock.assert_called_once()


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import Mock, patch
        from src.specialists import ACTIVE_SPECIALISTS
        self.events = []
        self.evidence = {'ticker': 'TEST', 'retrieved_facts': {
            'stock': {'revenue': 100, 'free_cash_flow': 5},
            'earnings': [{'surprise_percentage': 3}]}, 'calculated_metrics': {}, 'missing_data': []}
        self.registry = {}
        for name, (builder, analyzer) in ACTIVE_SPECIALISTS.items():
            def analyze(context, name=name):
                self.events.append(name)
                return result(specialist_name=name)
            self.registry[name] = (Mock(wraps=builder), Mock(side_effect=analyze))
        patcher = patch.dict(ACTIVE_SPECIALISTS, self.registry, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        for target in ('socket.socket.connect', 'src.analysis.analyze_investment'):
            guard = patch(target, side_effect=AssertionError('Unexpected call'))
            guard.start()
            self.addCleanup(guard.stop)

    def run_specialists(self, names=None, **kwargs):
        from src.multi_agent import run_specialists
        return run_specialists(' test ', self.evidence, specialist_names=names, **kwargs)

    def test_default_order_counts_types(self):
        context = self.run_specialists()
        self.assertIsInstance(context, MultiAgentSynthesisContext)
        self.assertEqual(self.events, ['fundamental', 'risk'])
        self.assertEqual([r.specialist_name for r in context.specialist_results], self.events)
        for builder, analyzer in self.registry.values():
            builder.assert_called_once()
            analyzer.assert_called_once()
        self.assertTrue(all(isinstance(r, SpecialistAnalysis) for r in context.specialist_results))
        self.assertFalse(hasattr(context, 'recommendation'))

    def test_subsets_and_order(self):
        for names in (['fundamental'], ['risk'], ['risk', 'fundamental'], []):
            self.events.clear()
            context = self.run_specialists(names)
            self.assertEqual(self.events, names)
            self.assertEqual([r.specialist_name for r in context.specialist_results], names)

    def test_invalid_selection_preflight(self):
        for names in (['unknown'], ['risk', 'risk'], ['fundamental', 'unknown'], 'risk'):
            with self.assertRaises(ValueError): self.run_specialists(names)
        for builder, analyzer in self.registry.values():
            builder.assert_not_called()
            analyzer.assert_not_called()

    def test_selected_contexts_and_input_isolation(self):
        from copy import deepcopy
        from src.specialists import select_fundamental_evidence, select_risk_evidence
        snapshot = build_portfolio_snapshot(PortfolioInput([], 100), {})
        portfolio = build_portfolio_analysis_context(snapshot, assess_portfolio_risk(snapshot), 'TEST')
        memory = DecisionMemoryContext('TEST', [])
        before = deepcopy((self.evidence, portfolio, memory))
        self.run_specialists(portfolio_context=portfolio, decision_memory=memory)
        contexts = [self.registry[n][1].call_args.args[0] for n in ('fundamental', 'risk')]
        self.assertIsNot(contexts[0], contexts[1])
        for c, selector in zip(contexts, (select_fundamental_evidence, select_risk_evidence)):
            self.assertEqual(c.research_evidence, selector(self.evidence))
            self.assertEqual(c.portfolio_context, portfolio)
            self.assertEqual(c.decision_memory, memory)
        contexts[0].portfolio_context.cash_weight = 0
        contexts[0].research_evidence['missing_data'].append('changed')
        self.assertEqual(before, (self.evidence, portfolio, memory))
        self.assertEqual(contexts[1].research_evidence['missing_data'], [])

    def test_first_failure_stops(self):
        self.registry['fundamental'][1].side_effect = RuntimeError('failed')
        with self.assertRaises(RuntimeError): self.run_specialists()
        self.registry['fundamental'][1].assert_called_once()
        self.registry['risk'][0].assert_not_called()
        self.registry['risk'][1].assert_not_called()

    def test_second_failure_no_partial(self):
        self.registry['risk'][1].side_effect = ValueError('invalid response')
        with self.assertRaises(ValueError): self.run_specialists()
        for _, analyzer in self.registry.values(): analyzer.assert_called_once()

    def test_builder_failure(self):
        self.registry['fundamental'][0].side_effect = ValueError('context failure')
        with self.assertRaises(ValueError): self.run_specialists()
        for _, analyzer in self.registry.values(): analyzer.assert_not_called()

    def test_invalid_result(self):
        bad_score = result()
        bad_score.confidence_score = 101
        for value in (None, result(specialist_name='risk'), result(ticker='OTHER'), bad_score):
            self.registry['fundamental'][1].side_effect = None
            self.registry['fundamental'][1].return_value = value
            with self.assertRaises(ValueError): self.run_specialists()
        self.registry['risk'][1].assert_not_called()

    def test_generic_registration(self):
        from unittest.mock import Mock, patch
        from src.specialists import ACTIVE_SPECIALISTS
        builder = Mock(return_value=SpecialistContext('TEST', 'hypothetical', {}))
        analyzer = Mock(return_value=result(specialist_name='hypothetical'))
        with patch.dict(ACTIVE_SPECIALISTS, {'hypothetical': (builder, analyzer)}):
            context = self.run_specialists(['hypothetical'])
        self.assertEqual(context.specialist_results[0].specialist_name, 'hypothetical')
        builder.assert_called_once()
        analyzer.assert_called_once()
        self.assertNotIn('hypothetical', ACTIVE_SPECIALISTS)


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        import json
        from unittest.mock import patch
        from test_v01 import evidence, payload
        self.evidence = evidence()
        self.data = payload(self.evidence)
        self.context = MultiAgentSynthesisContext('TEST', [result(), result(specialist_name='risk')])
        for patcher in (patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')),
                        patch.dict('os.environ', {}, clear=True),
                        patch('src.analysis.analyze_investment', side_effect=AssertionError('No fallback')),
                        patch('src.multi_agent.run_specialists', side_effect=AssertionError('No reruns'))):
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch('src.synthesis.request_text', return_value=json.dumps(self.data))
        self.mock = patcher.start()
        self.addCleanup(patcher.stop)

    def run_synthesis(self):
        from src.synthesis import synthesize_investment_analysis
        return synthesize_investment_analysis(self.context, self.evidence)

    def respond(self, data):
        import json
        self.mock.return_value = json.dumps(data)
        return self.run_synthesis()

    def test_existing_output(self):
        item = self.run_synthesis()
        self.assertIsInstance(item, InvestmentAnalysis)
        self.assertIsInstance(item.bull_case[0], InterpretationStatement)
        self.assertIsInstance(item.scenarios[0], ForecastStatement)
        self.mock.assert_called_once()
        self.assertEqual(item.missing_data, self.evidence['missing_data'])

    def test_variable_count_order(self):
        import json
        for names in (['fundamental'], ['fundamental', 'risk'], ['risk', 'fundamental'], ['hypothetical', 'risk', 'fundamental']):
            self.context.specialist_results = [result(specialist_name=n) for n in names]
            self.run_synthesis()
            payload = json.loads(self.mock.call_args.kwargs['input'])
            self.assertEqual([x['specialist_name'] for x in payload['SPECIALIST_INTERPRETATIONS']], names)
            self.assertEqual(payload['evidence_package'], self.evidence)

    def test_recommendations(self):
        for rec in ('Buy', 'Accumulate', 'Hold', 'Trim', 'Avoid'):
            self.assertEqual(self.respond(dict(self.data, recommendation=rec)).recommendation, rec)
        with self.assertRaises(ValueError): self.respond(dict(self.data, recommendation='Sell'))

    def test_confidence(self):
        for score in (0, 100):
            self.assertEqual(self.respond(dict(self.data, confidence_score=score)).confidence_score, score)
        for score in (-1, 101, True, None):
            with self.assertRaises(ValueError): self.respond(dict(self.data, confidence_score=score))

    def test_current_ids_only(self):
        self.context.specialist_results[0].key_findings[0].evidence_refs = ['E999']
        self.data['bull_case'][0]['evidence_refs'] = ['E999']
        with self.assertRaises(ValueError): self.respond(self.data)

    def test_material_coverage_not_satisfied_by_advice(self):
        self.data['material_evidence_review'] = {}
        with self.assertRaises(ValueError): self.respond(self.data)

    def test_separate_optional_contexts(self):
        import copy
        import json
        from src.analysis import INSTRUCTIONS, PORTFOLIO_INSTRUCTIONS, MEMORY_INSTRUCTIONS
        snapshot = build_portfolio_snapshot(PortfolioInput([], 100), {})
        self.context.portfolio_context = build_portfolio_analysis_context(snapshot, assess_portfolio_risk(snapshot), 'TEST')
        self.context.decision_memory = DecisionMemoryContext('TEST', [])
        before = copy.deepcopy((self.context, self.evidence))
        self.data['portfolio_assessment'] = 'Supplied portfolio context.'
        self.respond(self.data)
        args = self.mock.call_args.kwargs
        payload = json.loads(args['input'])
        self.assertEqual(payload['evidence_package'], self.evidence)
        self.assertIn('PORTFOLIO_CONTEXT', payload)
        self.assertIn('HISTORICAL_DECISION_MEMORY', payload)
        for instructions in (INSTRUCTIONS, PORTFOLIO_INSTRUCTIONS, MEMORY_INSTRUCTIONS):
            self.assertIn(instructions, args['instructions'])
        self.assertEqual(before, (self.context, self.evidence))

    def test_advisory_and_temporal_instructions(self):
        from src.analysis import INSTRUCTIONS
        self.run_synthesis()
        instructions = self.mock.call_args.kwargs['instructions']
        self.assertIn(INSTRUCTIONS, instructions)
        for phrase in ('Portfolio Manager / Final Synthesis Analyst', 'is authoritative',
                       'not retrieved facts', 'Do not use voting', 'Do not average specialist',
                       'Preserve material', 'disagreement', 'fill missing current evidence',
                       'valuation/earnings specialists exist unless supplied', 'temporal'):
            self.assertIn(phrase, instructions)

    def test_malformed_and_failure(self):
        self.mock.return_value = 'invalid'
        with self.assertRaisesRegex(ValueError, 'invalid synthesis JSON'): self.run_synthesis()
        self.mock.reset_mock()
        self.mock.side_effect = RuntimeError('OpenAI failed')
        with self.assertRaises(RuntimeError): self.run_synthesis()
        self.mock.assert_called_once()

    def test_identity_and_schema_rejection(self):
        with self.assertRaises(ValueError): self.respond(dict(self.data, ticker='OTHER'))
        with self.assertRaises(ValueError): self.respond(dict(self.data, specialist_votes=[]))
        self.context.ticker = 'OTHER'
        self.mock.reset_mock()
        with self.assertRaises(ValueError): self.run_synthesis()
        self.mock.assert_not_called()


    def test_current_risk_and_forecast_instructions(self):
        self.run_synthesis()
        instructions = self.mock.call_args.kwargs['instructions']
        for phrase in ('major_risks contains current identifiable risks/vulnerabilities only',
                       'not predicted future outcomes', 'expectations in scenarios',
                       'observations/events in thesis_invalidation_conditions',
                       'Do not duplicate', 'Ordinary conditional explanations'):
            self.assertIn(phrase, instructions)

    def test_current_vulnerability_and_forecast_types(self):
        self.data['major_risks'][0]['text'] = 'Existing leverage may reduce flexibility when cash generation weakens.'
        self.data['scenarios'][0]['text'] = 'If cash flow declines further, financial flexibility could deteriorate.'
        item = self.respond(self.data)
        self.assertIsInstance(item.major_risks[0], InterpretationStatement)
        self.assertNotIsInstance(item.major_risks[0], ForecastStatement)
        self.assertIsInstance(item.scenarios[0], ForecastStatement)
        self.assertIsInstance(item.thesis_invalidation_conditions[0], ForecastStatement)

    def test_statement_type_cannot_override_collection(self):
        self.data['major_risks'][0]['statement_type'] = 'forecast'
        with self.assertRaises(ValueError):
            self.respond(self.data)

    def test_valuation_grounding_instructions(self):
        self.run_synthesis()
        instructions = self.mock.call_args.kwargs['instructions']
        for phrase in ('specific supplied current valuation', 'metrics and values',
                       'valid current evidence citations', 'do not invent peer comparisons',
                       'No fixed cheap/expensive', 'valuation is uncertain',
                       'interpretations, historical memory and portfolio context cannot establish current valuation'):
            self.assertIn(phrase, instructions)

    def test_quantitative_valuation_preserves_evidence(self):
        from src.evidence import build_evidence_catalog
        catalog = build_evidence_catalog(self.evidence)
        pe = next(e for e in catalog if e['path'].endswith('.pe_ratio'))
        text = 'The supplied trailing P/E of 20 is an absolute earnings multiple; relative attractiveness is uncertain.'
        self.data['valuation_assessment'] = text
        self.data['bear_case'][0] = {'text': text, 'evidence_refs': [pe['evidence_id']]}
        item = self.respond(self.data)
        self.assertEqual(item.valuation_assessment, text)
        self.assertEqual(item.bear_case[0].evidence_refs, [pe['evidence_id']])

    def test_missing_valuation_stays_missing(self):
        import json
        from test_v01 import payload
        self.evidence['retrieved_facts']['stock']['pe_ratio'] = None
        self.evidence['retrieved_facts']['stock']['forward_pe'] = None
        self.evidence['missing_data'].append('Valuation multiples unavailable')
        self.context.specialist_results[0].summary = 'Historical valuation was attractive.'
        data = payload(self.evidence)
        data['valuation_assessment'] = 'Valuation is uncertain because current multiples are unavailable.'
        item = self.respond(data)
        sent = json.loads(self.mock.call_args.kwargs['input'])
        self.assertIsNone(sent['evidence_package']['retrieved_facts']['stock']['pe_ratio'])
        self.assertFalse(any(e['path'].endswith(('.pe_ratio', '.forward_pe')) for e in sent['EVIDENCE_CATALOG']))
        self.assertIn('Valuation multiples unavailable', item.missing_data)
        self.assertEqual(item.valuation_assessment, data['valuation_assessment'])


class MultiAgentPipelineTests(unittest.TestCase):
    def setUp(self):
        from contextlib import ExitStack
        from unittest.mock import patch
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')))

    def setup_pipeline(self, portfolio=False):
        from unittest.mock import patch
        from test_v01 import evidence, payload
        from src import analysis, research_pipeline, portfolio_research_pipeline
        module = portfolio_research_pipeline if portfolio else research_pipeline
        self.module = module
        self.evidence = evidence()
        self.result = analysis._validate_analysis(payload(self.evidence), self.evidence)
        self.build = self.stack.enter_context(patch.object(module, 'build_stock_evidence', return_value=self.evidence))
        self.old = self.stack.enter_context(patch.object(module, 'analyze_investment', return_value=self.result))
        self.specialists = self.stack.enter_context(patch.object(module, 'run_specialists', side_effect=lambda ticker, evidence, **kw: MultiAgentSynthesisContext(ticker, [result()], kw.get('portfolio_context'), kw.get('decision_memory'))))
        self.synthesis = self.stack.enter_context(patch.object(module, 'synthesize_investment_analysis', return_value=self.result))
        self.save = self.stack.enter_context(patch.object(module, 'save_analysis_decision'))
        self.memory = self.stack.enter_context(patch.object(module, 'build_decision_memory_context', return_value=DecisionMemoryContext('TEST', [])))
        if portfolio:
            self.snapshot = self.stack.enter_context(patch.object(module, 'build_live_portfolio_snapshot', return_value=build_portfolio_snapshot(PortfolioInput([], 100), {})))
            self.run = lambda **kw: module.run_portfolio_aware_research('TEST', PortfolioInput([], 100), **kw)
        else:
            self.run = lambda **kw: module.run_stock_research('TEST', **kw)

    def test_default_standalone(self):
        self.setup_pipeline()
        self.assertIs(self.run(), self.result)
        self.old.assert_called_once_with(self.evidence)
        self.specialists.assert_not_called()
        self.synthesis.assert_not_called()

    def test_default_portfolio(self):
        self.setup_pipeline(True)
        self.assertIs(self.run(), self.result)
        self.old.assert_called_once()
        self.specialists.assert_not_called()
        self.synthesis.assert_not_called()

    def test_multi_standalone(self):
        self.setup_pipeline()
        self.assertIs(self.run(use_multi_agent=True), self.result)
        self.old.assert_not_called()
        self.build.assert_called_once()
        self.specialists.assert_called_once_with('TEST', self.evidence, decision_memory=None, specialist_names=None)
        self.synthesis.assert_called_once()
        self.assertIs(self.synthesis.call_args.args[1], self.evidence)

    def test_multi_portfolio_context(self):
        self.setup_pipeline(True)
        self.run(use_multi_agent=True)
        context = self.specialists.call_args.kwargs['portfolio_context']
        self.assertIsInstance(context, type(self.synthesis.call_args.args[0].portfolio_context))
        self.assertIs(context, self.synthesis.call_args.args[0].portfolio_context)
        self.assertNotIn('portfolio_context', self.evidence)
        self.old.assert_not_called()
        self.snapshot.assert_called_once()

    def test_selection_pass_through(self):
        self.setup_pipeline()
        for names in (['risk'], ['risk', 'fundamental']):
            self.run(use_multi_agent=True, specialist_names=names)
            self.assertEqual(self.specialists.call_args.kwargs['specialist_names'], names)

    def test_disabled_selection_fails_before_retrieval(self):
        self.setup_pipeline()
        with self.assertRaises(ValueError): self.run(specialist_names=['risk'])
        self.build.assert_not_called()

    def test_memory_order_and_persistence(self):
        self.setup_pipeline()
        events = []
        memory = DecisionMemoryContext('TEST', [])
        self.memory.side_effect = lambda *a: events.append('memory') or memory
        self.specialists.side_effect = lambda ticker, evidence, **kw: events.append('specialists') or MultiAgentSynthesisContext(ticker, [], decision_memory=kw['decision_memory'])
        self.synthesis.side_effect = lambda *a: events.append('synthesis') or self.result
        self.save.side_effect = lambda *a: events.append('save')
        store = object()
        self.run(use_multi_agent=True, use_decision_memory=True, decision_store=store, decision_timestamp='2026-01-01')
        self.assertEqual(events, ['memory', 'specialists', 'synthesis', 'save'])
        self.assertIs(self.synthesis.call_args.args[0].decision_memory, memory)
        self.assertEqual(memory.prior_decisions, [])
        self.save.assert_called_once_with(self.result, store, '2026-01-01', None)

    def test_explicit_portfolio_memory(self):
        self.setup_pipeline(True)
        memory = DecisionMemoryContext('TEST', [])
        self.run(use_multi_agent=True, memory_context=memory)
        self.assertIs(self.synthesis.call_args.args[0].decision_memory, memory)
        self.memory.assert_not_called()

    def test_specialist_failure(self):
        self.setup_pipeline()
        self.specialists.side_effect = ValueError('Unknown specialist or failed specialist')
        with self.assertRaises(ValueError): self.run(use_multi_agent=True, decision_store=object(), decision_timestamp='now')
        self.synthesis.assert_not_called()
        self.save.assert_not_called()
        self.old.assert_not_called()

    def test_synthesis_failure(self):
        self.setup_pipeline(True)
        self.synthesis.side_effect = ValueError('Invalid synthesis')
        with self.assertRaises(ValueError): self.run(use_multi_agent=True, decision_store=object(), decision_timestamp='now')
        self.save.assert_not_called()
        self.old.assert_not_called()
        self.specialists.assert_called_once()
        self.synthesis.assert_called_once()

    def test_save_failure_no_reruns(self):
        self.setup_pipeline()
        self.save.side_effect = RuntimeError('Store failed')
        with self.assertRaises(RuntimeError): self.run(use_multi_agent=True, decision_store=object(), decision_timestamp='now')
        self.specialists.assert_called_once()
        self.synthesis.assert_called_once()
        self.build.assert_called_once()
        self.old.assert_not_called()

    def test_real_decision_persistence(self):
        import tempfile
        from pathlib import Path
        from src.decision_store import DecisionStore
        from src.decision_history import save_analysis_decision
        self.setup_pipeline()
        self.save.side_effect = save_analysis_decision
        with tempfile.TemporaryDirectory() as directory:
            store = DecisionStore(str(Path(directory) / 'decisions.db'))
            store.initialize()
            self.run(use_multi_agent=True, decision_store=store, decision_timestamp='2026-01-01')
            records = store.get_decisions_for_ticker('TEST')
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].recommendation, self.result.recommendation)
            self.assertEqual(store.get_outcomes_for_decision(records[0].decision_id), [])
