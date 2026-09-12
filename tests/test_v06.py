"""Offline evaluation metadata/persistence foundation, no prices fetched or returns computed."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace, fields, FrozenInstanceError
from unittest.mock import patch
from src.decision_store import DecisionStore
from src.evaluation_store import EvaluationStore
from src.evaluation_models import (EvaluationHorizon, ACTIVE_HORIZONS, EvaluationMethodology,
    EvaluationEnrollment, EvaluationObservation, EvaluationPrice, utc_timestamp)
from test_v03 import record, outcome


def enrollment(**changes):
    return EvaluationEnrollment(**(dict(enrollment_id='enroll', decision_id='fixture-1', ticker='TEST',
        enrolled_at='2026-01-02T12:00:00Z', horizon=ACTIVE_HORIZONS[0],
        methodology=EvaluationMethodology()) | changes))


def observation(**changes):
    return EvaluationObservation(**(dict(observation_id='obs', enrollment_id='enroll', point='reference',
        effective_at='2026-01-03T21:00:00Z', recorded_at='2026-01-04T12:00:00Z',
        missing_reason='Prices not supplied') | changes))


class EvaluationFoundationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'legacy.db'
        self.legacy = DecisionStore(str(self.path))
        self.legacy.initialize()
        self.decision = record()
        self.outcome = outcome()
        self.legacy.save_decision(self.decision)
        self.legacy.save_outcome(self.outcome)
        self.store = EvaluationStore(str(self.path))
        guard = patch('socket.socket.connect', side_effect=AssertionError('No network'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_additive_legacy_and_new_database(self):
        from src.dashboard.history_adapter import load_history
        from src.dashboard.performance_adapter import load_performance
        before = self.path.read_bytes()
        reader = EvaluationStore(str(self.path), read_only=True)
        self.assertIsNone(reader.get_enrollment('none'))
        self.assertEqual(reader.get_observations_for_enrollment('none'), [])
        self.assertEqual(self.path.read_bytes(), before)
        with sqlite3.connect(self.path) as db:
            old_schema = db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        self.store.initialize()
        self.store.initialize()
        with sqlite3.connect(self.path) as db:
            for name, sql in old_schema:
                self.assertEqual(db.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()[0], sql)
        self.assertEqual(self.legacy.get_decision('fixture-1'), self.decision)
        self.assertEqual(self.legacy.get_outcome('fixture-1', '1 month'), self.outcome)
        self.assertEqual(load_history(str(self.path), 'TEST').decisions, [self.decision])
        self.assertFalse(load_performance(str(self.path), 'TEST').availability.data_available)
        fresh = EvaluationStore(str(self.path.parent / 'new.db'))
        fresh.initialize()
        fresh.initialize()
        self.assertEqual(fresh.get_enrollments_for_ticker('TEST'), [])

    def test_enrollment_roundtrip_identity_and_duplicates(self):
        self.store.initialize()
        item = enrollment()
        self.store.save_enrollment(item)
        self.assertEqual(self.store.get_enrollment('enroll'), item)
        self.assertEqual(self.store.get_enrollments_for_ticker(' test '), [item])
        self.assertEqual(self.store.get_enrollments_for_decision('fixture-1'), [item])
        self.assertEqual(self.store.get_enrollment('enroll').methodology.snapshot, item.methodology.snapshot)
        self.assertEqual(self.store.get_enrollment('enroll').methodology.digest, item.methodology.digest)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_enrollment(replace(item, enrollment_id='duplicate'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_enrollment(replace(item, decision_id='unknown'))
        with self.assertRaises(ValueError):
            self.store.save_enrollment(replace(item, ticker='OTHER'))
        with self.assertRaises(ValueError):
            self.store.save_enrollment(replace(item, enrollment_id='changed', horizon=ACTIVE_HORIZONS[1],
                methodology=replace(item.methodology, benchmark_symbol='OTHER')))
        self.assertIsNone(item.decision_available_at)
        self.assertEqual(item.time_provenance, 'legacy_time_unverified')
        self.assertEqual(self.legacy.get_decision('fixture-1'), self.decision)
        self.assertEqual(self.legacy.get_outcome('fixture-1', '1 month'), self.outcome)

    def test_observation_missing_price_revision_and_idempotency(self):
        self.store.initialize()
        self.store.save_enrollment(enrollment())
        first = observation()
        self.store.save_observation(first)
        self.assertEqual(self.store.get_observations_for_enrollment('enroll'), [first])
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_observation(replace(first, observation_id='duplicate'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_observation(replace(first, enrollment_id='unknown'))
        price = EvaluationPrice('TEST', 100, first.effective_at, first.recorded_at,
            'fixture source', 'regular_close', enrollment().methodology.adjustment_policy, 'USD')
        revised = replace(first, observation_id='revision', stock=price, supersedes_id='obs', revision_reason='Price now supplied')
        self.store.save_observation(revised)
        self.assertEqual(self.store.get_observations_for_enrollment('enroll'), [first, revised])
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_observation(replace(revised, observation_id='duplicate revision'))
        with self.assertRaises(ValueError):
            self.store.save_observation(replace(revised, observation_id='wrong', stock=replace(price, symbol='OTHER')))
        self.assertFalse(any('return' in f.name for f in fields(first)))

    def test_timestamps_horizons_and_validation(self):
        self.assertEqual(utc_timestamp('20260102T120000.000000Z'), '2026-01-02T12:00:00.000000Z')
        self.assertEqual(utc_timestamp('2026-01-02T07:00:00-05:00'), '2026-01-02T12:00:00.000000Z')
        for timestamp in ('2026-01-02', '2026-01-02T12:00:00', '', 'invalid'):
            with self.assertRaises(ValueError): utc_timestamp(timestamp)
        self.assertEqual([x.length for x in ACTIVE_HORIZONS], [90, 365])
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError): EvaluationHorizon(value)
        with self.assertRaises(ValueError): EvaluationHorizon(90, 'months')
        with self.assertRaises(ValueError): EvaluationMethodology(version='')
        with self.assertRaises(ValueError): enrollment(time_provenance='captured_analysis_completion')
        with self.assertRaises(ValueError): enrollment(decision_available_at='2027-01-01T00:00:00Z')
        with self.assertRaises(ValueError): observation(missing_reason=None)
        with self.assertRaises(ValueError): observation(recorded_at='2025-01-01T00:00:00Z')
        with self.assertRaises(FrozenInstanceError): enrollment().ticker = 'OTHER'

    def test_readonly_and_no_automatic_enrollment(self):
        self.store.initialize()
        self.legacy.save_decision(record(decision_id='later'))
        self.assertEqual(self.store.get_enrollments_for_decision('later'), [])
        reader = EvaluationStore(str(self.path), read_only=True)
        with self.assertRaises(ValueError): reader.initialize()
        with self.assertRaises(sqlite3.OperationalError): reader.save_enrollment(enrollment())
        missing = EvaluationStore(str(self.path.parent / 'absent.db'), read_only=True)
        with self.assertRaises(sqlite3.OperationalError): missing.get_enrollment('x')
        self.assertFalse((self.path.parent / 'absent.db').exists())


class EvaluationEngineTests(unittest.TestCase):
    def inputs(self, end=110, benchmark=105):
        contract = enrollment()
        def point(role, timestamp, price, bench):
            def fact(symbol, amount):
                return None if amount is None else EvaluationPrice(symbol, amount, timestamp, timestamp,
                    'fixture', 'regular_close', contract.methodology.adjustment_policy, 'USD')
            return EvaluationObservation(role, 'enroll', role, timestamp, timestamp,
                fact('TEST', price), fact('VOO', bench), 'Unavailable fixture price' if price is None or bench is None else None)
        return contract, point('reference', '2026-01-03T21:00:00Z', 100, 100), point('endpoint', '2026-04-03T21:00:00Z', end, benchmark), record()

    def test_returns_metadata_and_determinism(self):
        from src.evaluation_engine import evaluate_observations
        from copy import deepcopy
        for price, expected in ((110, .1), (90, -.1), (100, 0)):
            for recommendation in ('Buy', 'Accumulate', 'Hold', 'Trim', 'Avoid'):
                args = list(self.inputs(price))
                args[3] = replace(args[3], recommendation=recommendation)
                before = deepcopy(args)
                result = evaluate_observations(*args)
                self.assertAlmostEqual(result.stock_return, expected)
                self.assertAlmostEqual(result.benchmark_return, .05)
                self.assertAlmostEqual(result.excess_return, expected - .05)
                self.assertEqual(result.recommendation, recommendation)
                self.assertEqual(result.confidence_score, args[3].confidence_score)
                self.assertEqual(result.enrollment.horizon, args[0].horizon)
                self.assertEqual(result.enrollment.methodology.snapshot, args[0].methodology.snapshot)
                self.assertEqual(result.completeness, 'full')
                self.assertFalse(result.horizon_resolution_verified)
                self.assertEqual(evaluate_observations(*args), result)
                self.assertEqual(before, args)

    def test_missing_and_invalid_prices(self):
        from src.evaluation_engine import evaluate_observations
        result = evaluate_observations(*self.inputs(110, None))
        self.assertEqual(result.completeness, 'stock_only')
        self.assertIsNone(result.excess_return)
        result = evaluate_observations(*self.inputs(None, 110))
        self.assertEqual(result.completeness, 'not_evaluable')
        self.assertIsNone(result.stock_return)
        self.assertIsNotNone(result.benchmark_return)
        for amount in (0, -1, float('nan'), float('inf'), True, '100'):
            with self.assertRaises((ValueError, TypeError)):
                evaluate_observations(*self.inputs(amount))
        args = list(self.inputs())
        args[1] = replace(args[1], stock=replace(args[1].stock, price=0))
        with self.assertRaises(ValueError): evaluate_observations(*args)

    def test_identity_time_basis_and_revision_pinning(self):
        from src.evaluation_engine import evaluate_observations
        args = self.inputs()
        for bad in (replace(args[2], enrollment_id='other'),
                    replace(args[2], point='reference'),
                    replace(args[2], stock=replace(args[2].stock, currency='OTHER')),
                    replace(args[2], stock=replace(args[2].stock, price_type='open'))):
            with self.assertRaises(ValueError): evaluate_observations(args[0], args[1], bad, args[3])
        with self.assertRaises(ValueError): evaluate_observations(args[0], args[1], args[2], replace(args[3], ticker='OTHER'))
        early = EvaluationObservation('early', 'enroll', 'endpoint', '2026-01-03T20:00:00Z', '2026-01-04T00:00:00Z', missing_reason='missing')
        with self.assertRaises(ValueError): evaluate_observations(args[0], args[1], early, args[3])
        revised = replace(args[2], observation_id='revision', supersedes_id='endpoint', revision_reason='corrected source')
        self.assertEqual(evaluate_observations(args[0], args[1], revised, args[3]).endpoint_observation_id, 'revision')

    def test_aggregate_denominators_and_missing(self):
        from src.evaluation_engine import evaluate_observations, aggregate_evaluations
        results = []
        for i in range(10):
            args = list(self.inputs(110, 100 if i < 3 else 120 if i == 3 else None))
            identity = 'enroll-' + str(i)
            args[0] = replace(args[0], enrollment_id=identity)
            args[1] = replace(args[1], enrollment_id=identity)
            args[2] = replace(args[2], enrollment_id=identity)
            results.append(evaluate_observations(*args))
        args = list(self.inputs(None, 110))
        results.append(evaluate_observations(*args))
        summary = aggregate_evaluations(results)
        self.assertEqual(summary['evaluated_count'], 10)
        self.assertEqual(summary['unevaluated_count'], 1)
        self.assertEqual(summary['benchmark_count'], 4)
        self.assertEqual(summary['benchmark_outperformance_rate'], .75)
        self.assertEqual(summary['positive_return_rate'], 1)
        self.assertAlmostEqual(summary['average_stock_return'], .1)
        self.assertAlmostEqual(summary['median_stock_return'], .1)
        self.assertAlmostEqual(summary['average_benchmark_return'], .05)
        self.assertAlmostEqual(summary['median_excess_return'], .1)
        self.assertIsNone(aggregate_evaluations([])['positive_return_rate'])
        with self.assertRaises(ValueError): aggregate_evaluations(results + [results[0]])
        different = replace(results[0], enrollment=replace(results[0].enrollment, enrollment_id='different', horizon=ACTIVE_HORIZONS[1]))
        with self.assertRaises(ValueError): aggregate_evaluations([results[0], different])

    def test_pure_no_io_and_legacy_unchanged(self):
        from src.evaluation_engine import evaluate_observations, aggregate_evaluations
        from copy import deepcopy
        args = self.inputs()
        legacy = outcome()
        before = deepcopy((args, legacy))
        with patch('sqlite3.connect', side_effect=AssertionError('No DB')), patch('socket.socket.connect', side_effect=AssertionError('No network')):
            aggregate_evaluations([evaluate_observations(*args)])
        self.assertEqual((args, legacy), before)
