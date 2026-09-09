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


if __name__ == '__main__':
    unittest.main()
