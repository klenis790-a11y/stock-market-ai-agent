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
