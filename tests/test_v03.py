"""Decision history contracts only; no persistence, credentials, or providers."""
import unittest
from dataclasses import fields

from src.models import (
    DecisionRecord, DecisionOutcome, InterpretationStatement, ForecastStatement,
    MaterialEvidenceReview,
)


def record(**overrides):
    values = dict(
        decision_id='fixture-1', ticker='TEST', decision_timestamp='2026-01-01',
        recommendation='Hold', confidence_score=60, investment_horizon=None,
        reasoning_summary='Fixture reasoning', fundamental_assessment='Fixture fundamentals',
        valuation_assessment='Fixture valuation', earnings_assessment='Fixture earnings',
        portfolio_assessment=None,
        bull_case=[InterpretationStatement('Fixture interpretation', ['E001'])],
        bear_case=[], supporting_evidence=[], major_risks=[],
        thesis_invalidation_conditions=[], scenarios=[ForecastStatement('Fixture scenario', ['E001'])],
        missing_data=[], material_evidence_review={'E001': MaterialEvidenceReview('Observation', 'Relevance')},
    )
    return DecisionRecord(**(values | overrides))


def outcome(**overrides):
    values = dict(decision_id='fixture-1', evaluation_timestamp='2026-02-01',
                  evaluation_horizon='1 month', stock_start_price=100, stock_end_price=90,
                  stock_return=None, benchmark_ticker=None, benchmark_start_price=None,
                  benchmark_end_price=None, benchmark_return=None, excess_return=None)
    return DecisionOutcome(**(values | overrides))


class DecisionModelTests(unittest.TestCase):
    def test_valid_record(self):
        result = record()
        self.assertEqual(result.decision_id, 'fixture-1')
        self.assertIsInstance(result.bull_case[0], InterpretationStatement)
        self.assertIsInstance(result.scenarios[0], ForecastStatement)
        self.assertIsInstance(result.material_evidence_review['E001'], MaterialEvidenceReview)

    def test_ticker_normalized(self):
        self.assertEqual(record(ticker=' test ').ticker, 'TEST')

    def test_required_record_text(self):
        for name in ('decision_id', 'ticker', 'decision_timestamp'):
            for value in ('', ' ', None):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    record(**{name: value})

    def test_recommendations(self):
        from src.analysis import RECOMMENDATIONS
        for value in RECOMMENDATIONS:
            self.assertEqual(record(recommendation=value).recommendation, value)
        for value in ('Sell', 'buy', '', None):
            with self.assertRaises(ValueError):
                record(recommendation=value)

    def test_confidence(self):
        for value in (0, 100, 63.5):
            self.assertEqual(record(confidence_score=value).confidence_score, value)
        for value in (-1, 101, float('nan'), float('inf'), True, '60'):
            with self.assertRaises(ValueError):
                record(confidence_score=value)

    def test_valid_outcome_no_calculation(self):
        result = outcome()
        self.assertEqual(result.stock_end_price, 90)
        self.assertIsNone(result.stock_return)
        self.assertIsNone(result.excess_return)
        self.assertEqual(outcome(stock_return=-.1).stock_return, -.1)

    def test_outcome_required_text(self):
        for name in ('decision_id', 'evaluation_timestamp', 'evaluation_horizon'):
            for value in ('', ' ', None):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    outcome(**{name: value})

    def test_prices(self):
        for name in ('stock_start_price', 'stock_end_price', 'benchmark_start_price', 'benchmark_end_price'):
            for value in (-1, float('nan'), float('inf'), True, '100'):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    outcome(**{name: value})
            for value in (0, None, 10.5):
                self.assertEqual(getattr(outcome(**{name: value}), name), value)

    def test_separate_contracts(self):
        decision_fields = {f.name for f in fields(DecisionRecord)}
        outcome_fields = {f.name for f in fields(DecisionOutcome)}
        self.assertEqual(decision_fields & outcome_fields, {'decision_id'})
        self.assertNotIn('stock_return', decision_fields)
        self.assertNotIn('recommendation', outcome_fields)
        with self.assertRaises(TypeError):
            record(stock_return=.1)
        with self.assertRaises(TypeError):
            outcome(recommendation='Hold')


class DecisionBuilderTests(unittest.TestCase):
    def setUp(self):
        from src.models import InvestmentAnalysis
        from src.decision_history import build_decision_record
        self.build = build_decision_record
        source = record()
        self.analysis = InvestmentAnalysis(**{
            f.name: getattr(source, f.name) for f in fields(InvestmentAnalysis)
        })
        for name in ('bull_case', 'bear_case', 'supporting_evidence', 'major_risks'):
            setattr(self.analysis, name, [InterpretationStatement(name, ['E001'])])
        for name in ('scenarios', 'thesis_invalidation_conditions'):
            setattr(self.analysis, name, [ForecastStatement(name, ['E001'])])
        self.analysis.missing_data = ['Fixture limitation']

    def test_all_fields_map(self):
        from src.models import InvestmentAnalysis
        result = self.build(self.analysis, '20260908T201500Z', '12 months', 'fixture')
        self.assertIsInstance(result, DecisionRecord)
        for field in fields(InvestmentAnalysis):
            self.assertEqual(getattr(result, field.name), getattr(self.analysis, field.name))
        self.assertEqual(result.decision_timestamp, '20260908T201500Z')
        self.assertEqual(result.investment_horizon, '12 months')

    def test_portfolio_assessment(self):
        for value in ('Portfolio context', None):
            self.analysis.portfolio_assessment = value
            self.assertEqual(self.build(self.analysis, 'timestamp').portfolio_assessment, value)

    def test_custom_id(self):
        self.assertEqual(self.build(self.analysis, 'timestamp', decision_id=' custom ').decision_id, 'custom')
        for value in ('', ' ', 123):
            with self.assertRaises(ValueError):
                self.build(self.analysis, 'timestamp', decision_id=value)

    def test_generated_id_format_and_unique(self):
        self.analysis.ticker = ' test '
        first = self.build(self.analysis, '20260908T201500Z')
        second = self.build(self.analysis, '20260908T201500Z')
        self.assertRegex(first.decision_id, r'^TEST-20260908T201500Z-[0-9a-f]{8}$')
        self.assertNotEqual(first.decision_id, second.decision_id)
        self.assertEqual(first.ticker, 'TEST')

    def test_optional_horizon(self):
        for supplied, expected in [(None, None), (' ', None), (' 3 months ', '3 months'),
                                   ('long term', 'long term')]:
            self.assertEqual(self.build(self.analysis, 'timestamp', supplied).investment_horizon, expected)

    def test_timestamp_not_reinterpreted(self):
        timestamp = ' 2026-09-08T10:00:00-04:00 '
        self.assertEqual(self.build(self.analysis, timestamp).decision_timestamp, timestamp)
        for value in ('', ' ', None):
            with self.assertRaises(ValueError):
                self.build(self.analysis, value)

    def test_deep_mutable_isolation(self):
        from copy import deepcopy
        before = deepcopy(self.analysis)
        result = self.build(self.analysis, 'timestamp')
        self.assertEqual(self.analysis, before)
        for name in ('bull_case', 'bear_case', 'supporting_evidence', 'major_risks',
                     'scenarios', 'thesis_invalidation_conditions'):
            original = getattr(self.analysis, name)
            copied = getattr(result, name)
            self.assertIsNot(original, copied)
            self.assertIsNot(original[0], copied[0])
            original[0].evidence_refs.append('E002')
            original[0].text = 'Changed'
            self.assertEqual(copied, getattr(before, name))
        self.analysis.missing_data.append('New')
        self.analysis.material_evidence_review['E001'].observation = 'Changed'
        self.analysis.material_evidence_review['E002'] = MaterialEvidenceReview('New', 'New')
        self.assertEqual(result.missing_data, before.missing_data)
        self.assertEqual(result.material_evidence_review, before.material_evidence_review)
        result.material_evidence_review['E001'].thesis_relevance = 'Record-only change'
        self.assertEqual(self.analysis.material_evidence_review['E001'].thesis_relevance, 'Relevance')

    def test_decision_only_signature(self):
        import inspect
        self.assertEqual(list(inspect.signature(self.build).parameters),
                         ['analysis', 'decision_timestamp', 'investment_horizon', 'decision_id'])
        with self.assertRaises(TypeError):
            self.build(self.analysis, 'timestamp', stock_end_price=100)


if __name__ == '__main__':
    unittest.main()
