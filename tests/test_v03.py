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


class PersistenceIntegrationTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from contextlib import ExitStack
        from unittest.mock import patch
        from src import analysis, research_pipeline, portfolio_research_pipeline
        from src.decision_store import DecisionStore
        from test_v01 import evidence, payload
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.store = DecisionStore(str(Path(temp) / 'test.sqlite'))
        self.store.initialize()
        self.data = evidence()
        self.good = payload(self.data)
        self.analysis = analysis._validate_analysis(self.good, self.data)
        self.modules = [research_pipeline, portfolio_research_pipeline]
        self.stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')))

    def invoke(self, module, **kwargs):
        from src.models import PortfolioInput
        if module is self.modules[0]:
            return module.run_stock_research('TEST', **kwargs)
        return module.run_portfolio_aware_research('TEST', PortfolioInput([], 100), **kwargs)

    def test_helper_round_trip_custom_metadata_and_copy(self):
        from copy import deepcopy
        from src.decision_history import save_analysis_decision
        before = deepcopy(self.analysis)
        saved = save_analysis_decision(self.analysis, self.store, '2026-01-01', '12 months', 'custom')
        self.assertEqual(saved, self.store.get_decision('custom'))
        self.assertEqual(saved.investment_horizon, '12 months')
        self.assertEqual(self.analysis, before)
        self.assertNotIn('stock_return', {f.name for f in fields(saved)})

    def test_success_both_pipelines(self):
        import json
        from unittest.mock import patch
        from src import analysis
        from src.models import InvestmentAnalysis
        for index, module in enumerate(self.modules):
            good = dict(self.good)
            if index:
                good['portfolio_assessment'] = 'Fixture portfolio assessment'
            with patch.object(module, 'build_stock_evidence', return_value=self.data) as retrieve, patch.object(
                analysis, 'request_text', return_value=json.dumps(good)
            ) as request, patch.object(self.store, 'save_decision', wraps=self.store.save_decision) as save:
                result = self.invoke(module, decision_store=self.store,
                                     decision_timestamp='2026-01-01', investment_horizon='long term')
                self.assertIsInstance(result, InvestmentAnalysis)
                save.assert_called_once()
                request.assert_called_once()
                retrieve.assert_called_once()
        self.assertEqual(len(self.store.get_decisions_for_ticker('TEST')), 2)

    def test_no_store_no_write(self):
        from unittest.mock import patch
        for module in self.modules:
            with patch.object(module, 'build_stock_evidence', return_value=self.data), patch.object(
                module, 'analyze_investment', return_value=self.analysis
            ), patch.object(module, 'save_analysis_decision') as save:
                self.assertIs(self.invoke(module), self.analysis)
                save.assert_not_called()

    def test_retrieval_failure_no_save(self):
        from unittest.mock import patch
        for module in self.modules:
            with patch.object(module, 'build_stock_evidence', side_effect=RuntimeError('Retrieval failed')), patch.object(
                module, 'analyze_investment'
            ) as analyze, patch.object(self.store, 'save_decision') as save:
                with self.assertRaises(RuntimeError):
                    self.invoke(module, decision_store=self.store, decision_timestamp='date')
                save.assert_not_called()
                analyze.assert_not_called()

    def test_analysis_and_real_validation_failures_no_save(self):
        from unittest.mock import patch
        from src import analysis
        for module in self.modules:
            for failure in (RuntimeError('Analysis failed'), '{}'):
                with patch.object(module, 'build_stock_evidence', return_value=self.data), patch.object(
                    analysis, 'request_text', **({'side_effect': failure} if isinstance(failure, Exception)
                                              else {'return_value': failure})
                ) as request, patch.object(self.store, 'save_decision') as save:
                    with self.assertRaises((RuntimeError, ValueError)):
                        self.invoke(module, decision_store=self.store, decision_timestamp='date')
                    request.assert_called_once()
                    save.assert_not_called()

    def test_portfolio_failure_no_save(self):
        from unittest.mock import patch
        module = self.modules[1]
        with patch.object(module, 'build_stock_evidence', return_value=self.data), patch.object(
            module, 'build_live_portfolio_snapshot', side_effect=RuntimeError('Portfolio failed')
        ), patch.object(module, 'analyze_investment') as analyze:
            with self.assertRaises(RuntimeError):
                self.invoke(module, decision_store=self.store, decision_timestamp='date')
            analyze.assert_not_called()
        self.assertEqual(self.store.get_decisions_for_ticker('TEST'), [])

    def test_save_failure_no_repeat(self):
        import sqlite3
        from unittest.mock import patch
        for module in self.modules:
            with patch.object(module, 'build_stock_evidence', return_value=self.data) as retrieve, patch.object(
                module, 'analyze_investment', return_value=self.analysis
            ) as analyze, patch.object(self.store, 'save_decision', side_effect=sqlite3.OperationalError('Write failed')) as save:
                with self.assertRaises(sqlite3.OperationalError):
                    self.invoke(module, decision_store=self.store, decision_timestamp='date')
                retrieve.assert_called_once()
                analyze.assert_called_once()
                save.assert_called_once()
        self.assertEqual(self.store.get_decisions_for_ticker('TEST'), [])

    def test_missing_timestamp_fails_before_research(self):
        from unittest.mock import patch
        for module in self.modules:
            with patch.object(module, 'build_stock_evidence') as retrieve:
                with self.assertRaisesRegex(ValueError, 'decision_timestamp'):
                    self.invoke(module, decision_store=self.store)
                retrieve.assert_not_called()


class DecisionMemoryTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from src.decision_store import DecisionStore
        from src.decision_memory import build_decision_memory_context
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = DecisionStore(str(Path(temporary.name) / 'memory.sqlite'))
        self.store.initialize()
        self.build = build_decision_memory_context
        blocker = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def test_empty_context(self):
        result = self.build(self.store, ' test ')
        self.assertEqual(result.ticker, 'TEST')
        self.assertEqual(result.prior_decisions, [])

    def test_one_record_preserves_compact_fields(self):
        original = record(major_risks=[InterpretationStatement('Risk', ['E001'])],
                          thesis_invalidation_conditions=[ForecastStatement('Condition', ['E001'])],
                          missing_data=['Missing'], investment_horizon='1 year')
        self.store.save_decision(original)
        item = self.build(self.store, 'TEST').prior_decisions[0]
        for field in fields(item):
            if field.name != 'outcomes':
                self.assertEqual(getattr(item, field.name), getattr(original, field.name))
        self.assertEqual(item.outcomes, [])

    def test_recency_default_custom_limit_and_filter(self):
        for i in range(7):
            self.store.save_decision(record(decision_id=str(i), decision_timestamp=f'2026-01-0{i+1}'))
        self.store.save_decision(record(decision_id='other', ticker='OTHER', decision_timestamp='2027-01-01'))
        self.assertEqual([x.decision_id for x in self.build(self.store, ' test ').prior_decisions],
                         ['6', '5', '4', '3', '2'])
        self.assertEqual([x.decision_id for x in self.build(self.store, 'TEST', 2).prior_decisions], ['6', '5'])
        self.assertEqual(len(self.build(self.store, 'TEST', 100).prior_decisions), 7)

    def test_zero_limit_no_queries(self):
        from unittest.mock import patch
        with patch.object(self.store, 'get_decisions_for_ticker') as query:
            self.assertEqual(self.build(self.store, 'TEST', 0).prior_decisions, [])
            query.assert_not_called()

    def test_invalid_arguments(self):
        for limit in (-1, 1.5, True, '5'):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.build(self.store, 'TEST', limit)
        for ticker in ('', ' ', None):
            with self.assertRaises(ValueError):
                self.build(self.store, ticker)

    def test_outcomes_attached_and_ordered(self):
        self.store.save_decision(record())
        self.store.save_decision(record(decision_id='new', decision_timestamp='2026-02-01'))
        self.store.save_decision(record(decision_id='other', ticker='OTHER'))
        for horizon, timestamp in [('90 days', '2026-04-01'), ('30 days', '2026-02-01')]:
            self.store.save_outcome(outcome(evaluation_horizon=horizon, evaluation_timestamp=timestamp))
        self.store.save_outcome(outcome(decision_id='other'))
        items = self.build(self.store, 'TEST').prior_decisions
        self.assertEqual(items[0].decision_id, 'new')
        self.assertEqual(items[0].outcomes, [])
        self.assertEqual([o.evaluation_horizon for o in items[1].outcomes], ['30 days', '90 days'])
        self.assertTrue(all(o.decision_id == 'fixture-1' for o in items[1].outcomes))

    def test_copy_isolation_from_loaded_objects_and_database(self):
        from copy import deepcopy
        from unittest.mock import patch
        self.store.save_decision(record(major_risks=[InterpretationStatement('Risk', ['E001'])]))
        self.store.save_outcome(outcome())
        loaded = self.store.get_decisions_for_ticker('TEST')
        outcomes = self.store.get_outcomes_for_decision('fixture-1')
        before = deepcopy((loaded, outcomes))
        with patch.object(self.store, 'get_decisions_for_ticker', return_value=loaded), patch.object(
            self.store, 'get_outcomes_for_decision', return_value=outcomes
        ):
            item = self.build(self.store, 'TEST').prior_decisions[0]
        for name in ('major_risks', 'scenarios', 'thesis_invalidation_conditions', 'missing_data'):
            self.assertIsNot(getattr(item, name), getattr(loaded[0], name))
        item.major_risks[0].evidence_refs.append('E999')
        item.scenarios[0].text = 'Changed'
        item.missing_data.append('Changed')
        item.outcomes[0].stock_return = 999
        self.assertEqual((loaded, outcomes), before)
        self.assertEqual(self.store.get_decision('fixture-1'), before[0][0])
        self.assertEqual(self.store.get_outcomes_for_decision('fixture-1'), before[1])

    def test_scope_and_only_selected_outcomes_queried(self):
        from src.models import DecisionMemoryItem
        from unittest.mock import patch
        names = {f.name for f in fields(DecisionMemoryItem)}
        self.assertFalse(names & {'bull_case', 'bear_case', 'supporting_evidence',
                                 'material_evidence_review', 'successful', 'failed', 'evidence_catalog'})
        self.store.save_decision(record())
        self.store.save_decision(record(decision_id='new', decision_timestamp='2026-02-01'))
        with patch.object(self.store, 'get_outcomes_for_decision', wraps=self.store.get_outcomes_for_decision) as query:
            self.build(self.store, 'TEST', 1)
            query.assert_called_once_with('new')


class HistoryCLITests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from src.decision_store import DecisionStore
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'history ?#.sqlite'
        self.store = DecisionStore(str(self.path))
        self.store.initialize()

    def cli(self, *args):
        import io
        from contextlib import ExitStack, redirect_stdout, redirect_stderr
        from unittest.mock import patch
        from src import main
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch('sys.argv', ['main.py', 'history', *args]))
            stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')))
            stock = stack.enter_context(patch.object(main, 'run_stock_research'))
            portfolio = stack.enter_context(patch.object(main, 'run_portfolio_aware_research'))
            stack.enter_context(redirect_stdout(output))
            stack.enter_context(redirect_stderr(output))
            code = 0
            try:
                main.main()
            except SystemExit as error:
                code = error.code
            stock.assert_not_called()
            portfolio.assert_not_called()
        return code, output.getvalue()

    def test_one_decision_output(self):
        self.store.save_decision(record(major_risks=[InterpretationStatement('Fixture risk', ['E001'])],
                                       missing_data=['Fixture missing']))
        code, text = self.cli(' test ', '--db', str(self.path))
        self.assertEqual(code, 0)
        for value in ('TEST', 'Hold', '60', 'Fixture reasoning', 'Fixture risk', 'Fixture missing', 'None recorded'):
            self.assertIn(value, text)
        self.assertNotIn('material_evidence_review', text)

    def test_multiple_order_and_limits(self):
        for i in range(7):
            self.store.save_decision(record(decision_id=str(i), decision_timestamp=f'2026-01-0{i+1}'))
        code, text = self.cli('TEST', '--db', str(self.path))
        self.assertEqual(code, 0)
        self.assertEqual(text.count('Confidence:'), 5)
        self.assertLess(text.index('2026-01-07'), text.index('2026-01-06'))
        self.assertEqual(self.cli('TEST', '--db', str(self.path), '--limit', '2')[1].count('Confidence:'), 2)

    def test_empty_history(self):
        self.assertEqual(self.cli('OTHER', '--db', str(self.path)), (0, 'No stored decisions for OTHER.\n'))

    def test_missing_database_no_creation(self):
        missing = self.path.parent / 'missing.sqlite'
        code, text = self.cli('TEST', '--db', str(missing))
        self.assertNotEqual(code, 0)
        self.assertIn('does not exist', text)
        self.assertFalse(missing.exists())

    def test_bad_arguments(self):
        for args in [('TEST', '--db', str(self.path), '--limit', '-1'),
                     (' ', '--db', str(self.path)), ('TEST',),
                     ('TEST', '--db', str(self.path), '--limit', 'abc')]:
            code, text = self.cli(*args)
            self.assertNotEqual(code, 0)
            self.assertNotIn('Traceback', text)

    def test_outcome_association(self):
        self.store.save_decision(record())
        self.store.save_decision(record(decision_id='new', decision_timestamp='2026-03-01'))
        self.store.save_outcome(outcome(stock_return=.1, benchmark_return=.05, excess_return=.05))
        code, text = self.cli('TEST', '--db', str(self.path))
        self.assertEqual(code, 0)
        self.assertLess(text.index('None recorded'), text.index('2026-01-01'))
        self.assertIn('1 month: stock return=0.1, benchmark return=0.05, excess return=0.05', text)

    def test_read_only_enforced_and_unchanged(self):
        import sqlite3
        from src.decision_store import DecisionStore
        self.store.save_decision(record())
        before = self.path.read_bytes()
        self.cli('TEST', '--db', str(self.path))
        self.assertEqual(self.path.read_bytes(), before)
        readonly = DecisionStore(str(self.path), read_only=True)
        with self.assertRaises(sqlite3.OperationalError):
            readonly.save_decision(record(decision_id='forbidden'))
        self.assertEqual(self.store.get_decision('fixture-1'), record())

    def test_unreadable_database(self):
        self.path.write_text('Not SQLite')
        code, text = self.cli('TEST', '--db', str(self.path))
        self.assertNotEqual(code, 0)
        self.assertIn('unable to read', text)
        self.assertNotIn('Traceback', text)


class OptionalMemoryAnalysisTests(unittest.TestCase):
    def setUp(self):
        from src.models import DecisionMemoryContext, DecisionMemoryItem
        from test_v01 import evidence, payload
        from unittest.mock import patch
        self.data = evidence()
        self.good = payload(self.data)
        self.memory = DecisionMemoryContext('TEST', [DecisionMemoryItem(
            'past', 'TEST', '2025-01-01', 'Hold', 60, None, 'Past reasoning',
            [InterpretationStatement('Historical risk', ['E001'])],
            [ForecastStatement('Past condition', ['E001'])], [], ['Past missing'], [outcome()])])
        blocker = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def test_none_request_unchanged(self):
        import json
        from unittest.mock import patch
        from src import analysis
        with patch.object(analysis, 'request_text', return_value=json.dumps(self.good)) as request:
            analysis.analyze_investment(self.data)
            first = request.call_args
            analysis.analyze_investment(self.data, memory_context=None)
            self.assertEqual(first, request.call_args)
            self.assertEqual(first.kwargs['instructions'], analysis.INSTRUCTIONS)
            self.assertNotIn('HISTORICAL_DECISION_MEMORY', json.loads(first.kwargs['input']))

    def test_serialization_scope_determinism_and_isolation(self):
        from copy import deepcopy
        from src.decision_memory import serialize_decision_memory
        before = deepcopy(self.memory)
        data = serialize_decision_memory(self.memory)
        self.assertEqual(data, serialize_decision_memory(self.memory))
        item = data['prior_decisions'][0]
        self.assertEqual(set(item), {'decision_id', 'ticker', 'decision_timestamp', 'recommendation',
                                    'confidence_score', 'investment_horizon', 'reasoning_summary',
                                    'major_risks', 'thesis_invalidation_conditions', 'scenarios', 'missing_data', 'outcomes'})
        self.assertEqual(item['major_risks'], ['Historical risk'])
        self.assertNotIn('E001', str(data))
        item['missing_data'].append('Changed')
        item['outcomes'][0]['stock_return'] = 999
        self.assertEqual(self.memory, before)

    def test_memory_input_current_catalog_unchanged(self):
        import json
        from copy import deepcopy
        from unittest.mock import patch
        from src import analysis
        from src.evidence import build_evidence_catalog
        before = deepcopy(self.memory)
        with patch.object(analysis, 'request_text', return_value=json.dumps(self.good)) as request:
            result = analysis.analyze_investment(self.data, memory_context=self.memory)
        request.assert_called_once()
        sent = json.loads(request.call_args.kwargs['input'])
        self.assertIn('HISTORICAL_DECISION_MEMORY', sent)
        self.assertEqual(sent['evidence_package'], self.data)
        self.assertEqual(sent['EVIDENCE_CATALOG'], build_evidence_catalog(self.data))
        self.assertEqual(result.missing_data, self.data['missing_data'])
        self.assertEqual(self.memory, before)
        instructions = request.call_args.kwargs['instructions']
        for text in ('CURRENT VERIFIED EVIDENCE', 'HISTORICAL DECISION MEMORY',
                     'authoritative for current facts', 'Missing current evidence must remain missing',
                     'Previous recommendations are not evidence', 'cannot\nsatisfy current material-evidence review',
                     'what was knowable at decision time'):
            self.assertIn(text, instructions)

    def test_memory_does_not_relax_coverage_or_ids(self):
        import json
        from copy import deepcopy
        from unittest.mock import patch
        from src import analysis
        for field in ('material_evidence_review', 'bull_case'):
            bad = deepcopy(self.good)
            if field == 'material_evidence_review':
                bad[field] = {}
            else:
                bad[field][0]['evidence_refs'] = ['past']
            with patch.object(analysis, 'request_text', return_value=json.dumps(bad)), self.assertRaises(ValueError):
                analysis.analyze_investment(self.data, memory_context=self.memory)

    def test_both_pipelines_forward_without_history_queries(self):
        from unittest.mock import patch
        from contextlib import ExitStack
        from src import analysis, research_pipeline, portfolio_research_pipeline
        from src.models import PortfolioInput
        from src.decision_store import DecisionStore
        result = analysis._validate_analysis(self.good, self.data)
        for module in (research_pipeline, portfolio_research_pipeline):
            with ExitStack() as stack:
                stack.enter_context(patch.object(module, 'build_stock_evidence', return_value=self.data))
                analyze = stack.enter_context(patch.object(module, 'analyze_investment', return_value=result))
                query = stack.enter_context(patch.object(DecisionStore, 'get_decisions_for_ticker', side_effect=AssertionError('No history query')))
                if module is research_pipeline:
                    returned = module.run_stock_research('TEST', memory_context=self.memory)
                else:
                    returned = module.run_portfolio_aware_research('TEST', PortfolioInput([], 100), memory_context=self.memory)
                self.assertIs(returned, result)
                analyze.assert_called_once()
                self.assertIs(analyze.call_args.kwargs['memory_context'], self.memory)
                query.assert_not_called()

    def test_memory_ticker_mismatch_rejected(self):
        from unittest.mock import patch
        from src import analysis
        self.memory.ticker = 'OTHER'
        with patch.object(analysis, 'request_text') as request, self.assertRaises(ValueError):
            analysis.analyze_investment(self.data, memory_context=self.memory)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
