"""Historical feature access: offline normalized fixtures, no provider calls."""
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from src.market_calendar import USMarketCalendar
from src.market_data_models import HistoricalOHLCV, MarketBar
from src.technical_features import build_technical_feature_snapshot
from src.historical_feature_context import build_historical_feature_index


class HistoricalFeatureContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = USMarketCalendar()
        cls.acquired = datetime(2026, 9, 1, tzinfo=timezone.utc)

    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No live network'))
        guard.start()
        self.addCleanup(guard.stop)

    def source(self, count=60, start='2025-01-02'):
        first = date.fromisoformat(start)
        days = [first]+[self.calendar.advance_sessions(first, n).date for n in range(1, count)]
        bars = tuple(MarketBar('TEST', day, 100+i, 103+i+(i % 7), 97+i,
                              101+i, 1000+i*37) for i, day in enumerate(days))
        return HistoricalOHLCV('TEST', bars, self.calendar.session_on_or_after(days[-1]).closes_at,
            self.acquired, self.calendar.version, days[-1], ())

    def build(self, source, targets, **kwargs):
        args = dict(market_as_of=source.requested_as_of, knowledge_as_of=self.acquired,
                    computed_at=self.acquired+timedelta(seconds=1), calendar=self.calendar)
        args.update(kwargs)
        return build_historical_feature_index(source, targets, **args)

    def prefix(self, source, target):
        return replace(source, bars=tuple(b for b in source.bars if b.session_date <= target),
            requested_as_of=self.calendar.session_on_or_after(target).closes_at,
            expected_last_session=target,
            missing_sessions=tuple(d for d in source.missing_sessions if d <= target))

    def test_historical_values_match_engine(self):
        source = self.source()
        for i in (14, 19, 35, 59):
            target = source.bars[i].session_date
            context = self.build(source, [target]).resolve(target)
            expected = build_technical_feature_snapshot(self.prefix(source, target))
            self.assertEqual(context.atr_14.feature, expected.feature('atr_14'))
            self.assertEqual(context.volume_ratio_20.feature, expected.feature('volume_ratio_20'))

    def test_future_changes_additions_and_gaps_do_not_influence_target(self):
        source = self.source()
        target = source.bars[29].session_date
        original = self.build(self.prefix(source, target), [target]).resolve(target)
        changed = replace(source, bars=source.bars[:30]+tuple(
            replace(b, high=b.high+500, volume=999999) for b in source.bars[30:]))
        gap = changed.bars[40].session_date
        changed = replace(changed, bars=changed.bars[:40]+changed.bars[41:], missing_sessions=(gap,))
        future = self.build(changed, [target]).resolve(target)
        self.assertEqual(original, future)  # values, availability, IDs AND prefix provenance
        latest = self.build(changed, [changed.expected_last_session]).resolve(changed.expected_last_session)
        self.assertNotEqual(original.volume_ratio_20.feature, latest.volume_ratio_20.feature)

    def test_identity_sessions_computation_and_input_order(self):
        source = self.source()
        targets = [source.bars[i].session_date for i in (25, 30)]
        a = self.build(source, targets)
        b = self.build(source, list(reversed(targets))+targets,
                       computed_at=self.acquired+timedelta(days=1))
        self.assertEqual(len(b.contexts), 2)
        for left, right in zip(a.contexts, b.contexts):
            self.assertEqual(left.atr_14, right.atr_14)
            self.assertEqual(left.volume_ratio_20, right.volume_ratio_20)
            self.assertEqual(left.source_prefix_id, right.source_prefix_id)
        self.assertNotEqual(a.contexts[0].atr_14.logical_id, a.contexts[1].atr_14.logical_id)
        self.assertNotEqual(a.contexts[0].atr_14.logical_id, a.contexts[0].volume_ratio_20.logical_id)

    def test_source_revision_changes_state_not_logical_identity(self):
        source = self.source()
        target = source.bars[30].session_date
        a = self.build(source, [target]).resolve(target)
        bars = list(source.bars)
        bars[20] = replace(bars[20], high=bars[20].high+10, volume=5000)
        b = self.build(replace(source, bars=tuple(bars)), [target]).resolve(target)
        self.assertEqual(a.atr_14.logical_id, b.atr_14.logical_id)
        self.assertNotEqual(a.atr_14.state_id, b.atr_14.state_id)
        self.assertNotEqual(a.source_prefix_id, b.source_prefix_id)
        self.assertNotEqual(a.atr_14.feature.value, b.atr_14.feature.value)
        self.assertNotEqual(a.volume_ratio_20.feature.value, b.volume_ratio_20.feature.value)

    def test_warmup_precedes_126_session_window(self):
        source = self.source(180)
        target = source.bars[-126].session_date
        context = self.build(source, [target]).resolve(target)
        expected = build_technical_feature_snapshot(self.prefix(source, target))
        self.assertEqual(context.atr_14.feature, expected.feature('atr_14'))
        self.assertEqual(context.volume_ratio_20.feature, expected.feature('volume_ratio_20'))
        self.assertIsNotNone(context.atr_14.feature.value)
        self.assertIsNotNone(context.volume_ratio_20.feature.value)
        truncated = replace(self.prefix(source, target), bars=(source.bars[-126],))
        self.assertIsNone(build_technical_feature_snapshot(truncated).feature('atr_14').value)
        self.assertIsNone(build_technical_feature_snapshot(truncated).feature('volume_ratio_20').value)

    def test_insufficient_history_and_zero_volume(self):
        source = self.source()
        for i in (0, 13, 14, 18, 19):
            target = source.bars[i].session_date
            c = self.build(source, [target]).resolve(target)
            self.assertEqual(c.atr_14.feature.value is None, i < 14)
            self.assertEqual(c.volume_ratio_20.feature.value is None, i < 19)
            if i < 14:
                self.assertEqual(c.atr_14.feature.unavailable_reason, 'UNAVAILABLE_DUE_TO_HISTORY')
            if i < 19:
                self.assertEqual(c.volume_ratio_20.feature.unavailable_reason, 'UNAVAILABLE_DUE_TO_HISTORY')
        zero = replace(source, bars=tuple(replace(b, volume=0) for b in source.bars))
        c = self.build(zero, [zero.expected_last_session]).resolve(zero.expected_last_session)
        self.assertEqual(c.volume_ratio_20.feature.unavailable_reason, 'UNAVAILABLE_ZERO_DENOMINATOR')

    def test_missing_sessions_do_not_restart_or_compress(self):
        source = self.source()
        gap = source.bars[20].session_date
        source = replace(source, bars=source.bars[:20]+source.bars[21:], missing_sessions=(gap,))
        for target, volume_missing in [(gap, True), (source.bars[25].session_date, True),
                                       (source.expected_last_session, False)]:
            c = self.build(source, [target]).resolve(target)
            self.assertEqual(c.atr_14.feature.unavailable_reason, 'UNAVAILABLE_DUE_TO_MISSING_SESSIONS')
            self.assertEqual(c.volume_ratio_20.feature.value is None, volume_missing)
            if target != gap:
                expected = build_technical_feature_snapshot(self.prefix(source, target))
                self.assertEqual(c.atr_14.feature, expected.feature('atr_14'))
                self.assertEqual(c.volume_ratio_20.feature, expected.feature('volume_ratio_20'))
        with self.assertRaises(ValueError):
            self.build(replace(source, missing_sessions=()), [source.expected_last_session])

    def test_weekend_holiday_and_early_close(self):
        source = self.source(30, '2025-06-02')
        target = date(2025, 7, 3)
        c = self.build(source, [target]).resolve(target)
        self.assertEqual(c.market_as_of.hour, 17)
        self.assertIsNotNone(c.atr_14.feature.value)
        self.assertIsNotNone(c.volume_ratio_20.feature.value)
        for invalid in (date(2025, 7, 4), date(2025, 7, 5)):
            with self.assertRaises(ValueError):
                self.build(source, [invalid])
        with self.assertRaises(ValueError):
            self.build(source, [target], market_as_of=c.market_as_of-timedelta(microseconds=1))

    def test_availability_immutability_and_cutoff_validation(self):
        source = self.source()
        target = source.expected_last_session
        index = self.build(source, [target])
        c = index.resolve(target)
        self.assertEqual(c.available_at, c.computed_at)
        self.assertGreater(c.available_at, c.market_as_of)
        self.assertEqual(c.source_retrieved_at, source.retrieved_at)
        self.assertEqual(c.knowledge_as_of, self.acquired)
        self.assertIn('HISTORICAL_AVAILABILITY_UNVERIFIED', c.limitations)
        with self.assertRaises(FrozenInstanceError):
            c.atr_14.feature.value = 2
        for kwargs in [dict(knowledge_as_of=self.acquired-timedelta(seconds=1)),
                       dict(computed_at=self.acquired-timedelta(seconds=1)),
                       dict(market_as_of=source.requested_as_of+timedelta(days=1)),
                       dict(computed_at=datetime(2026, 9, 1))]:
            with self.assertRaises(ValueError):
                self.build(source, [target], **kwargs)

    def test_unique_targets_computed_once_lookup_never_recomputes(self):
        source = self.source()
        targets = [source.bars[i].session_date for i in (20, 30)]
        with patch('src.historical_feature_context.build_technical_feature_snapshot',
                   wraps=build_technical_feature_snapshot) as builder:
            index = self.build(source, targets+targets)
            self.assertEqual(builder.call_count, 2)
            for _ in range(5):
                self.assertIs(index.resolve(targets[0]), index.contexts[0])
            self.assertEqual(builder.call_count, 2)
        with self.assertRaises(ValueError):
            index.resolve(source.bars[0].session_date)
        with self.assertRaises(ValueError):
            index.resolve(str(targets[0]))

    def test_invalid_source_provenance_fails_closed(self):
        source = self.source()
        for bad in [replace(source, calendar_version='unknown'),
                    replace(source, expected_last_session=source.bars[0].session_date),
                    replace(source, retrieved_at=source.requested_as_of-timedelta(days=1)),
                    replace(source, exchange_calendar='OTHER')]:
            with self.assertRaises(ValueError):
                self.build(bad, [source.expected_last_session])

    def test_empty_history_and_missing_latest_do_not_use_previous_value(self):
        source = self.source()
        target = source.expected_last_session
        missing = replace(source, bars=source.bars[:-1], missing_sessions=(target,))
        c = self.build(missing, [target]).resolve(target)
        self.assertEqual(c.target_session, target)
        self.assertEqual(c.atr_14.feature.unavailable_reason, 'UNAVAILABLE_DUE_TO_MISSING_SESSIONS')
        self.assertEqual(c.volume_ratio_20.feature.unavailable_reason, 'UNAVAILABLE_DUE_TO_MISSING_SESSIONS')
        empty = replace(source, bars=())
        c = self.build(empty, [target]).resolve(target)
        self.assertEqual(c.atr_14.feature.unavailable_reason, 'UNAVAILABLE_DUE_TO_HISTORY')
