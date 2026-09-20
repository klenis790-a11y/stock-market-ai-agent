"""ATS-1 fixtures use only normalized in-memory bars and the offline XNYS calendar."""
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from src.market_calendar import USMarketCalendar
from src.market_data_models import HistoricalOHLCV, MarketBar
from src.structural_pivots import detect_confirmed_pivots, PivotType, UnavailableReason


class ConfirmedPivotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = USMarketCalendar()
        cls.acquired = datetime(2026, 9, 1, tzinfo=timezone.utc)

    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No network'))
        guard.start()
        self.addCleanup(guard.stop)

    def days(self, start='2025-03-05', count=5):
        first = self.calendar.session_on_or_after(date.fromisoformat(start)).date
        return [first] + [self.calendar.advance_sessions(first, n).date for n in range(1, count)]

    def source(self, days, high=True, low=False, center=2):
        bars = tuple(MarketBar('TEST', day, 100, 110 if high and i == center else 105,
                              90 if low and i == center else 95, 100, 1000)
                     for i, day in enumerate(days))
        cutoff = self.calendar.session_on_or_after(days[-1]).closes_at
        return HistoricalOHLCV('TEST', bars, cutoff, self.acquired, self.calendar.version,
                               days[-1], ())

    def run_detector(self, source, **kwargs):
        args = dict(market_as_of=source.requested_as_of, knowledge_as_of=self.acquired,
                    computed_at=self.acquired + timedelta(seconds=1), calendar=self.calendar)
        args.update(kwargs)
        return detect_confirmed_pivots(source, **args)

    def test_basic_high_low_and_same_bar(self):
        for high, low, expected in [(True, False, [PivotType.HIGH]),
                                    (False, True, [PivotType.LOW]),
                                    (True, True, [PivotType.HIGH, PivotType.LOW])]:
            with self.subTest(high=high, low=low):
                days = self.days()
                result = self.run_detector(self.source(days, high, low))
                self.assertEqual([p.pivot_type for p in result.pivots], expected)
                for p in result.pivots:
                    self.assertEqual(p.event_session, days[2])
                    self.assertEqual(p.left_sessions, tuple(days[:2]))
                    self.assertEqual(p.right_sessions, tuple(days[3:]))
                    self.assertIsNone(p.event_time)

    def test_ties_with_each_neighbor_reject(self):
        source = self.source(self.days(), True, True)
        for field, value, rejected in [('high', 110, PivotType.HIGH), ('low', 90, PivotType.LOW)]:
            for neighbor in (0, 1, 3, 4):
                with self.subTest(field=field, neighbor=neighbor):
                    bars = list(source.bars)
                    bars[neighbor] = replace(bars[neighbor], **{field: value})
                    result = self.run_detector(replace(source, bars=tuple(bars)))
                    self.assertNotIn(rejected, [p.pivot_type for p in result.pivots
                                               if p.event_session == source.bars[2].session_date])

    def test_exact_confirmation_and_unconfirmed_end(self):
        source = self.source(self.days())
        close = source.requested_as_of
        before = self.run_detector(source, market_as_of=close-timedelta(microseconds=1))
        self.assertEqual(before.pivots, ())
        result = self.run_detector(source)
        self.assertEqual(result.pivots[0].confirmed_at, close)
        self.assertEqual([u.event_session for u in result.unavailable
                          if u.reason == UnavailableReason.RIGHT_CONTEXT_NOT_COMPLETED],
                         [b.session_date for b in source.bars[-2:]])

    def test_weekend_holiday_and_early_close(self):
        for start, expected in [('2025-03-05', date(2025, 3, 7)),
                                ('2025-06-30', date(2025, 7, 2)),
                                ('2025-11-21', date(2025, 11, 25))]:
            days = self.days(start)
            p = self.run_detector(self.source(days)).pivots[0]
            self.assertEqual(p.event_session, expected)
            self.assertEqual(p.confirmed_at, self.calendar.session_on_or_after(days[4]).closes_at)
        days = self.days('2025-11-21')
        self.assertEqual(days[-1], date(2025, 11, 28))
        self.assertEqual(self.run_detector(self.source(days)).pivots[0].confirmed_at.hour, 18)

    def test_missing_each_required_session_and_missing_anchor(self):
        source = self.source(self.days())
        for i in range(5):
            with self.subTest(missing=i):
                absent = source.bars[i].session_date
                data = replace(source, bars=source.bars[:i]+source.bars[i+1:],
                               missing_sessions=(absent,))
                result = self.run_detector(data)
                self.assertEqual(result.pivots, ())
                issue = next(u for u in result.unavailable if u.event_session == source.bars[2].session_date)
                self.assertEqual(issue.reason, UnavailableReason.MISSING_SESSION)
                self.assertIn(absent, issue.missing_sessions)
                self.assertEqual(result.anchor_session, source.expected_last_session)

    def test_window_boundary_and_external_left_context(self):
        days = self.days('2024-08-01', 130)
        # 130 bars: oldest eligible index is 4, using external indices 2 and 3.
        result = self.run_detector(self.source(days, center=4))
        self.assertEqual(result.window_start, days[4])
        self.assertEqual([p.event_session for p in result.pivots], [days[4]])
        self.assertEqual(result.pivots[0].left_sessions, tuple(days[2:4]))
        older = self.run_detector(self.source(days, center=3))
        self.assertEqual(older.pivots, ())
        self.assertEqual(result.window_start, days[4])  # prior immutable snapshot unchanged

    def test_insufficient_history_is_not_successful_no_pivot(self):
        source = self.source(self.days(count=3))
        result = self.run_detector(source)
        issue = next(u for u in result.unavailable if u.event_session == source.bars[0].session_date)
        self.assertEqual(issue.reason, UnavailableReason.INSUFFICIENT_DATA)
        empty = self.run_detector(replace(source, bars=()))
        self.assertEqual(empty.pivots, ())
        self.assertEqual(len(empty.unavailable), 126)

    def test_normalized_order_and_duplicates_reject(self):
        source = self.source(self.days())
        with self.assertRaises(ValueError):
            replace(source, bars=tuple(reversed(source.bars)))
        with self.assertRaises(ValueError):
            replace(source, bars=source.bars[:1]+source.bars)

    def test_temporal_provenance_and_immutability(self):
        source = self.source(self.days())
        result = self.run_detector(source)
        p = result.pivots[0]
        self.assertEqual(p.available_at, self.acquired+timedelta(seconds=1))
        self.assertGreater(p.available_at, p.confirmed_at)
        self.assertEqual(p.knowledge_as_of, self.acquired)
        self.assertEqual(p.source_retrieved_at, source.retrieved_at)
        self.assertEqual(result.source_dataset, source)
        self.assertIn('HISTORICAL_AVAILABILITY_UNVERIFIED', p.limitations)
        with self.assertRaises(FrozenInstanceError):
            p.price = 999
        for kwargs in [dict(knowledge_as_of=self.acquired-timedelta(seconds=1)),
                       dict(computed_at=self.acquired-timedelta(seconds=1)),
                       dict(market_as_of=source.requested_as_of+timedelta(days=1)),
                       dict(computed_at=datetime(2026, 9, 1))]:
            with self.assertRaises(ValueError):
                self.run_detector(source, **kwargs)

    def test_identity_and_no_future_leakage(self):
        source = self.source(self.days(count=8), True, True)
        original = self.run_detector(source)
        later = self.run_detector(source, computed_at=self.acquired+timedelta(days=1))
        self.assertEqual([(p.logical_id, p.state_id) for p in original.pivots],
                         [(p.logical_id, p.state_id) for p in later.pivots])
        self.assertEqual(len({p.logical_id for p in original.pivots}), 2)
        bars = source.bars[:5]+tuple(replace(b, high=120, low=80) for b in source.bars[5:])
        changed = self.run_detector(replace(source, bars=bars))
        event = source.bars[2].session_date
        self.assertEqual([(p.logical_id, p.state_id) for p in original.pivots],
                         [(p.logical_id, p.state_id) for p in changed.pivots if p.event_session == event])
        bars = list(source.bars)
        bars[2] = replace(bars[2], high=111)
        revised = self.run_detector(replace(source, bars=tuple(bars))).pivots[0]
        self.assertEqual(revised.logical_id, original.pivots[0].logical_id)
        self.assertNotEqual(revised.state_id, original.pivots[0].state_id)

    def test_fail_closed_source_contract(self):
        source = self.source(self.days())
        for bad in [replace(source, calendar_version='unknown'),
                    replace(source, exchange_calendar='OTHER'),
                    replace(source, missing_sessions=(source.bars[0].session_date,)),
                    replace(source, retrieved_at=source.requested_as_of-timedelta(days=1))]:
            with self.assertRaises(ValueError):
                self.run_detector(bad)


if __name__ == '__main__':
    unittest.main()
