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


class ObservationResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.market_calendar import USMarketCalendar
        cls.calendar = USMarketCalendar()

    def resolve(self, instant, as_of='2027-01-01T00:00:00+00:00', **changes):
        from datetime import datetime
        from src.observation_resolution import resolve_observation_target, close_methodology, SUPPORTED_MARKET
        item = enrollment(enrolled_at=instant, decision_available_at=instant,
                          time_provenance='captured_analysis_completion',
                          methodology=close_methodology(), **changes)
        return resolve_observation_target(item, datetime.fromisoformat(as_of),
                                          market=SUPPORTED_MARKET, calendar=self.calendar)

    def test_aware_time_and_dst(self):
        from datetime import datetime
        from src.market_calendar import aware_utc
        self.assertEqual(aware_utc(datetime.fromisoformat('2025-03-10T10:00:00-04:00')).hour, 14)
        with self.assertRaises(ValueError):
            aware_utc(datetime(2025, 1, 1))
        self.assertEqual(self.resolve('2025-03-07T10:00:00-05:00').reference.closes_at.hour, 21)
        self.assertEqual(self.resolve('2025-03-10T10:00:00-04:00').reference.closes_at.hour, 20)

    def test_classifications_and_reference_boundaries(self):
        from datetime import datetime
        for instant, status, reference in [
            ('2025-03-10T08:00:00-04:00', 'PRE_MARKET', '2025-03-10'),
            ('2025-03-10T10:00:00-04:00', 'REGULAR_SESSION', '2025-03-10'),
            ('2025-03-10T17:00:00-04:00', 'AFTER_HOURS', '2025-03-11'),
            ('2025-03-10T16:00:00-04:00', 'AFTER_HOURS', '2025-03-11'),
            ('2025-03-08T12:00:00-05:00', 'MARKET_CLOSED', '2025-03-10'),
            ('2025-03-09T12:00:00-04:00', 'MARKET_CLOSED', '2025-03-10'),
            ('2025-07-04T12:00:00-04:00', 'MARKET_CLOSED', '2025-07-07'),
            ('2021-07-05T12:00:00-04:00', 'MARKET_CLOSED', '2021-07-06')]:
            with self.subTest(instant=instant):
                self.assertEqual(self.calendar.classify(datetime.fromisoformat(instant)), status)
                self.assertEqual(str(self.resolve(instant).reference.date), reference)

    def test_horizons_roll_forward_and_preserve_contract(self):
        # March 10 + 90 days is Sunday June 8; April 7 + 90 is Sunday July 6.
        for instant, nominal, target in [
            ('2025-03-10T10:00:00-04:00', '2025-06-08', '2025-06-09'),
            ('2025-04-07T10:00:00-04:00', '2025-07-06', '2025-07-07'),
            ('2025-04-05T12:00:00-04:00', '2025-07-06', '2025-07-07')]:
            result = self.resolve(instant)
            self.assertEqual(str(result.nominal_target_date), nominal)
            self.assertEqual(str(result.target.date), target)
            self.assertEqual(result.enrollment.horizon, ACTIVE_HORIZONS[0])
        result = self.resolve('2024-07-04T12:00:00-04:00', horizon=ACTIVE_HORIZONS[1])
        self.assertEqual(str(result.nominal_target_date), '2025-07-05')
        self.assertEqual(str(result.target.date), '2025-07-07')
        # A 365-day target lands on Independence Day itself.
        result = self.resolve('2023-07-05T10:00:00-04:00', horizon=ACTIVE_HORIZONS[1])
        self.assertEqual(str(result.nominal_target_date), '2024-07-04')
        self.assertEqual(str(result.target.date), '2024-07-05')

    def test_half_day_and_no_lookahead(self):
        result = self.resolve('2025-11-28T10:00:00-05:00', '2025-11-28T12:30:00-05:00')
        self.assertEqual(result.reference.closes_at.hour, 18)
        self.assertFalse(result.reference_available)
        later = self.resolve('2025-11-28T10:00:00-05:00', '2025-11-28T13:00:00-05:00')
        self.assertTrue(later.reference_available)
        self.assertEqual(result.target, later.target)
        exact = self.resolve('2025-11-28T13:00:00-05:00')
        self.assertEqual(str(exact.reference.date), '2025-12-01')

    def test_eligibility_as_of_only(self):
        from datetime import timedelta
        first = self.resolve('2024-11-27T10:00:00-05:00', horizon=ACTIVE_HORIZONS[1])
        self.assertEqual(str(first.target.date), '2025-11-28')
        before = self.resolve('2024-11-27T10:00:00-05:00',
            (first.target.closes_at - timedelta(seconds=1)).isoformat(), horizon=ACTIVE_HORIZONS[1])
        after = self.resolve('2024-11-27T10:00:00-05:00',
            first.target.closes_at.isoformat(), horizon=ACTIVE_HORIZONS[1])
        self.assertEqual(before.eligibility, 'NOT_YET_ELIGIBLE')
        self.assertEqual(after.eligibility, 'ELIGIBLE')
        self.assertEqual(before.target, after.target)
        self.assertEqual(first, self.resolve('2024-11-27T10:00:00-05:00', horizon=ACTIVE_HORIZONS[1]))

    def test_unsupported_legacy_and_late_enrollment(self):
        from datetime import datetime, timezone
        from src.observation_resolution import resolve_observation_target, close_methodology, SUPPORTED_MARKET
        now = datetime(2027, 1, 1, tzinfo=timezone.utc)
        legacy = enrollment(methodology=close_methodology())
        self.assertEqual(resolve_observation_target(legacy, now, market=SUPPORTED_MARKET).eligibility, 'UNRESOLVABLE')
        self.assertEqual(resolve_observation_target(legacy, now, market='CRYPTO').eligibility, 'UNSUPPORTED')
        self.assertEqual(resolve_observation_target(enrollment(), now, market=SUPPORTED_MARKET).eligibility, 'UNSUPPORTED')
        valid = self.resolve('2025-03-10T10:00:00-04:00')
        late = replace(valid.enrollment, enrolled_at='2025-03-11T21:00:00Z')
        result = resolve_observation_target(late, now, market=SUPPORTED_MARKET)
        self.assertEqual(result.eligibility, 'UNRESOLVABLE')
        self.assertEqual(result.target, valid.target)
        with self.assertRaises(ValueError):
            resolve_observation_target(legacy, datetime(2027, 1, 1), market=SUPPORTED_MARKET)

    def test_offline_pure_shared_window_and_provenance(self):
        import socket
        from src.observation_resolution import close_methodology
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \
             patch('sqlite3.connect', side_effect=AssertionError('Database forbidden')):
            result = self.resolve('2025-03-10T10:00:00-04:00')
            self.assertEqual(result.enrollment.methodology, close_methodology())
            self.assertEqual(result.enrollment.methodology.benchmark_symbol, 'VOO')
            self.assertFalse(hasattr(result, 'benchmark_target'))
            self.assertFalse(hasattr(result, 'prices'))
            self.assertEqual(result, self.resolve('2025-03-10T10:00:00-04:00'))


class AdjustedCollectionTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timezone
        from src.observation_resolution import adjusted_close_methodology
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = EvaluationStore(str(Path(self.temp.name) / 'evaluation.db'))
        self.store.initialize()
        self.store.save_decision(record())
        self.store.save_outcome(outcome())
        self.item = enrollment(methodology=adjusted_close_methodology(),
            decision_available_at='2026-01-02T12:00:00Z', time_provenance='captured_analysis_completion')
        self.store.save_enrollment(self.item)
        self.now = datetime(2026, 9, 1, tzinfo=timezone.utc)

    def payload(self, symbol):
        return {'Meta Data': {'2. Symbol': symbol}, 'Time Series (Daily)': {
            '2026-01-02': {'4. close': '999', '5. adjusted close': '100'},
            '2026-04-02': {'4. close': '888', '5. adjusted close': '110'}}}

    def collect(self):
        from src.evaluation_collection import collect_evaluation_observations
        from src.observation_resolution import SUPPORTED_MARKET
        return collect_evaluation_observations(self.store, self.item, self.now,
                                               market=SUPPORTED_MARKET, clock=lambda: self.now)

    def test_success_exact_fields_provenance_idempotency_and_legacy_integrity(self):
        from src.evaluation_collection import ADJUSTED_PRICE_POLICY
        with patch('src.alpha_vantage_client.get_daily_adjusted', side_effect=self.payload) as provider:
            first = self.collect()
            self.assertEqual(provider.call_count, 2)
            self.assertEqual([c.args[0] for c in provider.call_args_list], ['TEST', 'VOO'])
            self.assertEqual(self.collect(), first)
            self.assertEqual(provider.call_count, 2)
        for item, value, day in zip(first, (100, 110), ('2026-01-02', '2026-04-02')):
            self.assertEqual(item.stock.price, value)
            self.assertEqual(item.benchmark.price, value)
            self.assertTrue(item.effective_at.startswith(day))
            self.assertEqual(item.stock.observed_at, item.benchmark.observed_at)
            self.assertIn(ADJUSTED_PRICE_POLICY, item.stock.price_type)
            self.assertTrue(item.stock.retrieved_at.endswith('Z'))
        self.assertEqual(self.store.get_decision('fixture-1'), record())
        self.assertEqual(self.store.get_outcomes_for_decision('fixture-1'), [outcome()])
        self.assertEqual(len(self.store.get_observations_for_enrollment('enroll')), 2)
        with sqlite3.connect(str(Path(self.temp.name) / 'evaluation.db')) as db:
            self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='evaluation_results'").fetchall())

    def test_gates_make_zero_calls(self):
        from datetime import datetime, timezone
        from src.evaluation_collection import collect_evaluation_observations
        from src.observation_resolution import SUPPORTED_MARKET, close_methodology
        with patch('src.alpha_vantage_client.get_daily_adjusted') as provider:
            for item, at, market in (
                (replace(self.item, methodology=close_methodology()), self.now, SUPPORTED_MARKET),
                (self.item, datetime(2026, 1, 3, tzinfo=timezone.utc), SUPPORTED_MARKET),
                (replace(self.item, time_provenance='legacy_time_unverified'), self.now, SUPPORTED_MARKET),
                (self.item, self.now, 'CRYPTO')):
                with self.assertRaises(ValueError):
                    collect_evaluation_observations(self.store, item, at, market=market)
            provider.assert_not_called()

    def test_missing_benchmark_and_network_failure_preserve_stock(self):
        def provider(symbol):
            if symbol == 'VOO':
                raise RuntimeError('provider failure')
            return self.payload(symbol)
        with patch('src.alpha_vantage_client.get_daily_adjusted', side_effect=provider):
            result = self.collect()
        for item in result:
            self.assertIsNotNone(item.stock)
            self.assertIsNone(item.benchmark)
            self.assertIn('benchmark', item.missing_reason)

    def test_missing_exact_dates_remain_missing(self):
        def provider(symbol):
            data = self.payload(symbol)
            del data['Time Series (Daily)']['2026-04-02' if symbol == 'TEST' else '2026-01-02']
            data['Time Series (Daily)']['2026-04-01'] = {'5. adjusted close': '123'}
            return data
        with patch('src.alpha_vantage_client.get_daily_adjusted', side_effect=provider):
            reference, endpoint = self.collect()
        self.assertIsNone(reference.benchmark)
        self.assertIsNone(endpoint.stock)
        self.assertTrue(endpoint.effective_at.startswith('2026-04-02'))

    def test_normalization_rejects_bad_prices_and_payloads(self):
        from datetime import date
        from src.evaluation_collection import normalize_adjusted
        for value in (None, True, {}, 'bad', '0', '-1', 'NaN', 'Infinity'):
            data = self.payload('TEST')
            data['Time Series (Daily)']['2026-01-02']['5. adjusted close'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_adjusted(data, 'TEST', date(2026, 1, 2), self.now.isoformat())
        for data in ({'Information': 'rate limit'}, {'Note': 'limit'}, {'Error Message': 'error'}, [], {}, self.payload('WRONG')):
            with self.assertRaises(ValueError):
                normalize_adjusted(data, 'TEST', date(2026, 1, 2), self.now.isoformat())
        data = self.payload('TEST')
        del data['Time Series (Daily)']['2026-01-02']['5. adjusted close']
        with self.assertRaises(ValueError):
            normalize_adjusted(data, 'TEST', date(2026, 1, 2), self.now.isoformat())

    def test_endpoint_full_request_reuses_client(self):
        from src.alpha_vantage_client import get_daily_adjusted
        with patch('src.alpha_vantage_client._request', return_value={}) as request:
            get_daily_adjusted('TEST')
            request.assert_called_once_with('TIME_SERIES_DAILY_ADJUSTED', 'TEST', outputsize='full')

    def test_partial_persistence_is_not_silently_retried(self):
        original = self.store.save_observation
        count = 0
        def fail_second(item):
            nonlocal count
            count += 1
            if count == 2:
                raise sqlite3.OperationalError('fixture write failure')
            original(item)
        with patch('src.alpha_vantage_client.get_daily_adjusted', side_effect=self.payload), \
             patch.object(self.store, 'save_observation', side_effect=fail_second):
            with self.assertRaises(sqlite3.OperationalError):
                self.collect()
        with patch('src.alpha_vantage_client.get_daily_adjusted') as provider:
            with self.assertRaises(ValueError):
                self.collect()
            provider.assert_not_called()
        self.assertEqual(len(self.store.get_observations_for_enrollment('enroll')), 1)
