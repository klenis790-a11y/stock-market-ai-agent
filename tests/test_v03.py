"""Decision contracts and temporary SQLite tests; no credentials or providers."""
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


class DecisionStoreTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from src.decision_store import DecisionStore
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / 'decisions.sqlite')
        self.store = DecisionStore(self.path)
        self.store.initialize()

    def test_initialization_idempotent_and_boundary(self):
        import sqlite3
        from contextlib import closing
        self.store.initialize()
        with closing(sqlite3.connect(self.path)) as connection:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            self.assertEqual(set(tables), {('decisions',), ('decision_outcomes',)})
            columns = connection.execute('PRAGMA table_info(decisions)').fetchall()
            self.assertEqual({c[1] for c in columns}, {f.name for f in fields(DecisionRecord)})
            self.assertEqual(next(c for c in columns if c[1] == 'decision_id')[5], 1)

    def test_complete_round_trip_and_types(self):
        original = record(missing_data=['Unavailable'], investment_horizon='12 months',
                          portfolio_assessment='Context')
        original.bear_case = [InterpretationStatement('Bear', ['E002'])]
        original.supporting_evidence = [InterpretationStatement('Support', ['E003'])]
        original.major_risks = [InterpretationStatement('Risk', ['E004'])]
        original.thesis_invalidation_conditions = [ForecastStatement('Condition', ['E005'])]
        self.store.save_decision(original)
        loaded = self.store.get_decision(original.decision_id)
        self.assertEqual(loaded, original)
        for name in ('bull_case', 'bear_case', 'supporting_evidence', 'major_risks'):
            self.assertIsInstance(getattr(loaded, name)[0], InterpretationStatement)
        for name in ('scenarios', 'thesis_invalidation_conditions'):
            self.assertIsInstance(getattr(loaded, name)[0], ForecastStatement)
        self.assertIsInstance(loaded.material_evidence_review['E001'], MaterialEvidenceReview)

    def test_optional_none_and_durability(self):
        from src.decision_store import DecisionStore
        self.store.save_decision(record())
        loaded = DecisionStore(self.path).get_decision('fixture-1')
        self.assertIsNone(loaded.portfolio_assessment)
        self.assertIsNone(loaded.investment_horizon)
        self.assertEqual(loaded, record())

    def test_duplicate_rejected_without_overwrite(self):
        import sqlite3
        self.store.save_decision(record())
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_decision(record(reasoning_summary='Replacement'))
        self.assertEqual(self.store.get_decision('fixture-1'), record())
        self.store.save_decision(record(decision_id='second'))
        self.assertEqual(len(self.store.get_decisions_for_ticker('TEST')), 2)

    def test_missing(self):
        self.assertIsNone(self.store.get_decision('absent'))
        self.assertEqual(self.store.get_decisions_for_ticker('NONE'), [])

    def test_history_order_filter_normalization(self):
        for ident, ticker, timestamp in [('old', 'TEST', '2026-01-01'),
                                          ('other', 'OTHER', '2026-03-01'),
                                          ('new', 'TEST', '2026-02-01')]:
            self.store.save_decision(record(decision_id=ident, ticker=ticker, decision_timestamp=timestamp))
        self.assertEqual([r.decision_id for r in self.store.get_decisions_for_ticker(' test ')], ['new', 'old'])

    def test_special_characters_safe(self):
        original = record(decision_id="x'; DROP TABLE decisions; --", reasoning_summary="Quote ' 雪\nNewline",
                          ticker="O'X", missing_data=['\\quoted"'])
        self.store.save_decision(original)
        self.assertEqual(self.store.get_decision(original.decision_id), original)
        self.assertEqual(self.store.get_decisions_for_ticker("o'x"), [original])
        self.assertEqual(self.store.get_decisions_for_ticker("' OR 1=1 --"), [])

    def test_no_mutation_and_independent_reads(self):
        from copy import deepcopy
        original = record()
        before = deepcopy(original)
        self.store.save_decision(original)
        self.assertEqual(original, before)
        loaded = self.store.get_decision(original.decision_id)
        loaded.bull_case[0].evidence_refs.append('E999')
        self.assertEqual(self.store.get_decision(original.decision_id), before)

    def test_deterministic_json(self):
        from src.decision_store import _serialize
        first = record(material_evidence_review={'E002': MaterialEvidenceReview('Two', 'R'),
                                                'E001': MaterialEvidenceReview('One', 'R')})
        second = record(material_evidence_review=dict(reversed(list(first.material_evidence_review.items()))))
        self.assertEqual(_serialize(first), _serialize(second))


class OutcomePersistenceTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from src.decision_store import DecisionStore
        from src.decision_history import build_decision_outcome
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = DecisionStore(str(Path(self.temp.name) / 'test.sqlite'))
        self.store.initialize()
        self.store.save_decision(record())
        self.build = build_decision_outcome

    def test_returns_and_excess(self):
        result = self.build('fixture-1', '2026-02-01', '30 days', 100, 120, 'BENCH', 100, 110)
        self.assertAlmostEqual(result.stock_return, .2)
        self.assertAlmostEqual(result.benchmark_return, .1)
        self.assertAlmostEqual(result.excess_return, .1)
        self.assertAlmostEqual(self.build('fixture-1', 'date', 'horizon', 100, 80).stock_return, -.2)

    def test_missing_and_zero_prices(self):
        for start, end in [(None, 100), (100, None), (0, 100), (None, None)]:
            result = self.build('fixture-1', 'date', 'horizon', start, end, 'BENCH', start, end)
            self.assertIsNone(result.stock_return)
            self.assertIsNone(result.benchmark_return)
            self.assertIsNone(result.excess_return)
        result = self.build('fixture-1', 'date', 'horizon', 100, 0)
        self.assertEqual(result.stock_return, -1)
        self.assertIsNone(result.benchmark_return)
        self.assertIsNone(result.excess_return)

    def test_negative_prices_fail(self):
        for name in ('stock_start_price', 'stock_end_price', 'benchmark_start_price', 'benchmark_end_price'):
            args = dict(decision_id='fixture-1', evaluation_timestamp='date', evaluation_horizon='horizon',
                        stock_start_price=100, stock_end_price=110)
            args[name] = -1
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.build(**args)

    def test_round_trip_durability_and_immutability(self):
        from copy import deepcopy
        from src.decision_store import DecisionStore
        decision_before = self.store.get_decision('fixture-1')
        result = self.build('fixture-1', '2026-02-01', '30 days', 100, 120, 'BENCH', 100, 110)
        before = deepcopy(result)
        self.store.save_outcome(result)
        self.assertEqual(DecisionStore(self.store.database_path).get_outcome('fixture-1', '30 days'), before)
        self.assertEqual(result, before)
        self.assertEqual(self.store.get_decision('fixture-1'), decision_before)
        self.assertNotIn('stock_return', {f.name for f in fields(decision_before)})

    def test_duplicate_rejected(self):
        import sqlite3
        self.store.save_outcome(outcome())
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_outcome(outcome(stock_return=.5))
        self.assertEqual(self.store.get_outcome('fixture-1', '1 month'), outcome())

    def test_foreign_key_rejected(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_outcome(outcome(decision_id='absent'))
        self.assertEqual(self.store.get_outcomes_for_decision('absent'), [])
        self.assertIsNone(self.store.get_decision('absent'))

    def test_multiple_horizons_order_and_filter(self):
        self.store.save_decision(record(decision_id='other'))
        for ident, stamp, horizon in [('fixture-1', '2026-04-01', '90 days'),
                                      ('other', '2026-01-01', 'other'),
                                      ('fixture-1', '2026-02-01', '30 days'),
                                      ('fixture-1', '2026-02-01', '1 month')]:
            self.store.save_outcome(outcome(decision_id=ident, evaluation_timestamp=stamp,
                                           evaluation_horizon=horizon))
        self.assertEqual([o.evaluation_horizon for o in self.store.get_outcomes_for_decision('fixture-1')],
                         ['1 month', '30 days', '90 days'])
        self.assertIsNone(self.store.get_outcome('fixture-1', 'unknown'))

    def test_schema_and_null_round_trip(self):
        from contextlib import closing
        with closing(self.store._connect()) as connection:
            self.assertEqual(connection.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            columns = connection.execute('PRAGMA table_info(decision_outcomes)').fetchall()
            self.assertEqual({c[1] for c in columns}, {f.name for f in fields(DecisionOutcome)})
            self.assertEqual({c[1]: c[5] for c in columns if c[5]},
                             {'decision_id': 1, 'evaluation_horizon': 2})
        result = outcome(stock_start_price=None, stock_end_price=None)
        self.store.save_outcome(result)
        self.assertEqual(self.store.get_outcome(result.decision_id, result.evaluation_horizon), result)


if __name__ == '__main__':
    unittest.main()
