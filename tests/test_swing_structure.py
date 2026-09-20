"""ATS-3 synthetic normalized data and exact boundary arithmetic, no live IO."""
import unittest
from dataclasses import replace, FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from unittest.mock import patch

from src.market_calendar import USMarketCalendar
from src.market_data_models import HistoricalOHLCV, MarketBar
from src.structural_pivots import detect_confirmed_pivots, PivotType
from src.historical_feature_context import build_historical_feature_index
from src.swing_structure import build_swing_structure, _comparison_values, SwingClassification


class SwingStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = USMarketCalendar()
        cls.time = datetime(2026, 9, 1, tzinfo=timezone.utc)

    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def source(self, highs=None, lows=None, count=45):
        first = date(2025, 1, 2)
        days = [first]+[self.calendar.advance_sessions(first, n).date for n in range(1,count)]
        bars = tuple(MarketBar('TEST', d, 100, (highs or {}).get(i,105),
                              (lows or {}).get(i,95),100,1000) for i,d in enumerate(days))
        return HistoricalOHLCV('TEST',bars,self.calendar.session_on_or_after(days[-1]).closes_at,
            self.time,self.calendar.version,days[-1],())

    def pivots(self, source):
        return detect_confirmed_pivots(source, market_as_of=source.requested_as_of,
            knowledge_as_of=self.time,computed_at=self.time+timedelta(seconds=1),calendar=self.calendar)

    def swings(self, pivots, **kwargs):
        return build_swing_structure(pivots,computed_at=kwargs.get('computed_at',self.time+timedelta(seconds=2)),calendar=self.calendar)

    def test_all_six_states_through_real_dependencies(self):
        for highs,lows,expected in [({20:110,26:130},{},'HH'),({20:110,26:110},{},'EH'),
            ({20:130,26:110},{},'LH'),({},{20:70,26:90},'HL'),
            ({},{20:90,26:90},'EL'),({},{20:90,26:70},'LL')]:
            with self.subTest(expected=expected):
                result=self.swings(self.pivots(self.source(highs,lows)))
                self.assertEqual(len(result.comparisons),1)
                self.assertEqual(result.comparisons[0].classification,expected)

    def test_exact_positive_negative_boundaries_and_adjacent_values(self):
        for side,equal,up,down in [(PivotType.HIGH,'EH','HH','LH'),(PivotType.LOW,'EL','HL','LL')]:
            for new,expected in [('100.1',equal),('99.9',equal),('100.10000000000001',up),('99.89999999999999',down)]:
                with self.subTest(side=side,new=new), localcontext() as ambient:
                    ambient.prec=3
                    difference,tolerance,label=_comparison_values(100,Decimal(new),Decimal('0.4'),side)
                    self.assertEqual(tolerance,Decimal('0.10'))
                    self.assertEqual(label,expected)
                    if expected==equal:self.assertEqual(abs(difference),tolerance)

    def test_confirmation_session_atr_changes_classification(self):
        source=self.source({20:110,26:114},{28:20})
        p=self.pivots(source)
        comparison=self.swings(p).comparisons[0]
        event=comparison.later.event_session
        confirm=comparison.later.right_sessions[-1]
        index=build_historical_feature_index(source,[event,confirm],market_as_of=source.requested_as_of,
            knowledge_as_of=self.time,computed_at=self.time+timedelta(seconds=2),calendar=self.calendar)
        event_atr=index.resolve(event).atr_14.feature.value
        self.assertNotEqual(event_atr,index.resolve(confirm).atr_14.feature.value)
        self.assertEqual(comparison.atr_context,index.resolve(confirm))
        self.assertEqual(_comparison_values(110,114,event_atr,PivotType.HIGH)[2],'HH')
        self.assertEqual(comparison.classification,'EH')

    def test_future_suffix_latest_atr_does_not_change_historical_state(self):
        source=self.source({20:110,26:114})
        a=self.swings(self.pivots(source)).comparisons[0]
        changed=replace(source,bars=source.bars[:30]+tuple(replace(b,high=200,low=10) for b in source.bars[30:]))
        b=self.swings(self.pivots(changed)).comparisons[0]
        self.assertEqual((a.classification,a.difference,a.tolerance,a.state_id,a.atr_context),
                         (b.classification,b.difference,b.tolerance,b.state_id,b.atr_context))
        latest=build_historical_feature_index(changed,[changed.expected_last_session],
            market_as_of=changed.requested_as_of,knowledge_as_of=self.time,computed_at=self.time+timedelta(seconds=2),calendar=self.calendar)
        self.assertNotEqual(latest.contexts[0].atr_14.feature.value,b.atr_context.atr_14.feature.value)

    def test_unavailable_atr_preserves_pivots_and_pair(self):
        source=self.source({2:110,8:120},count=12)
        p=self.pivots(source)
        self.assertEqual(len(p.pivots),2)
        c=self.swings(p).comparisons[0]
        self.assertIsNone(c.classification)
        self.assertIsNone(c.tolerance)
        self.assertEqual(c.unavailable_reason,'UNAVAILABLE_DUE_TO_HISTORY')
        self.assertEqual(len(p.pivots),2)
        source=self.source({20:110,26:120})
        gap=source.bars[5].session_date
        source=replace(source,bars=source.bars[:5]+source.bars[6:],missing_sessions=(gap,))
        c=self.swings(self.pivots(source)).comparisons[0]
        self.assertEqual(c.unavailable_reason,'UNAVAILABLE_DUE_TO_MISSING_SESSIONS')
        self.assertIsNone(c.classification)
        self.assertIsNone(_comparison_values(100,110,0,PivotType.HIGH)[2])

    def test_consecutive_sequences_same_bar_and_order_independence(self):
        p=self.pivots(self.source({20:110,26:120,32:130},{20:90,26:80,32:70}))
        a=self.swings(p)
        b=self.swings(replace(p,pivots=tuple(reversed(p.pivots))))
        self.assertEqual(a.comparisons,b.comparisons)
        self.assertEqual(len(a.comparisons),4)
        self.assertEqual([c.later.pivot_type for c in a.comparisons],
                         [PivotType.HIGH,PivotType.LOW,PivotType.HIGH,PivotType.LOW])
        for side in PivotType:
            seq=[q for q in p.pivots if q.pivot_type==side]
            pairs=[(c.previous,c.later) for c in a.comparisons if c.later.pivot_type==side]
            self.assertEqual(pairs,list(zip(seq,seq[1:])))

    def test_oldest_eligible_has_no_outside_predecessor(self):
        source=self.source({2:110,8:120},count=130)
        p=self.pivots(source)
        self.assertEqual(len(p.pivots),1)
        self.assertEqual(self.swings(p).comparisons,())

    def test_identity_revision_materialization_and_limitations(self):
        source=self.source({20:110,26:120})
        p=self.pivots(source)
        a=self.swings(p).comparisons[0]
        b=self.swings(p,computed_at=self.time+timedelta(days=1)).comparisons[0]
        self.assertEqual((a.logical_id,a.state_id),(b.logical_id,b.state_id))
        self.assertGreater(b.available_at,a.available_at)
        self.assertGreaterEqual(a.available_at,a.later.available_at)
        self.assertGreaterEqual(a.available_at,a.atr_context.available_at)
        self.assertIn('HISTORICAL_AVAILABILITY_UNVERIFIED',a.limitations)
        with self.assertRaises(FrozenInstanceError):a.classification=SwingClassification.LH
        for position in (0,26):
            bars=list(source.bars)
            bars[position]=replace(bars[position],high=bars[position].high+1)
            revised=self.swings(self.pivots(replace(source,bars=tuple(bars)))).comparisons[0]
            self.assertEqual(a.logical_id,revised.logical_id)
            self.assertNotEqual(a.state_id,revised.state_id)

    def test_duplicate_and_inconsistent_dependencies_reject(self):
        p=self.pivots(self.source({20:110,26:120}))
        with self.assertRaises(ValueError):self.swings(replace(p,pivots=p.pivots+p.pivots[:1]))
        changed=replace(p.pivots[-1],confirmed_at=p.pivots[-1].confirmed_at-timedelta(days=1))
        with self.assertRaises(ValueError):self.swings(replace(p,pivots=p.pivots[:1]+(changed,)))
        with self.assertRaises(ValueError):self.swings(p,computed_at=self.time)

    def test_confirmation_targets_requested_once(self):
        p=self.pivots(self.source({20:110,26:120},{20:90,26:80}))
        with patch('src.swing_structure.build_historical_feature_index',wraps=build_historical_feature_index) as build:
            result=self.swings(p)
        build.assert_called_once()
        self.assertEqual(set(build.call_args.args[1]),{p.pivots[-1].right_sessions[-1]})
        self.assertEqual(len(result.comparisons),2)

    def test_equivalent_numeric_representations_preserve_state_identity(self):
        source = self.source({20:110,26:120})
        original = self.swings(self.pivots(source)).comparisons[0]
        equivalent = replace(source, bars=tuple(replace(bar,
            open=float(bar.open), high=float(bar.high), low=float(bar.low),
            close=float(bar.close)) for bar in source.bars))
        other = self.swings(self.pivots(equivalent)).comparisons[0]
        self.assertEqual(original.previous.state_id, other.previous.state_id)
        self.assertEqual(original.later.state_id, other.later.state_id)
        self.assertEqual(original.atr_context.atr_14.state_id, other.atr_context.atr_14.state_id)
        self.assertEqual(original.difference, other.difference)
        self.assertNotEqual(str(original.difference), str(other.difference))
        self.assertEqual(original.classification, other.classification)
        self.assertEqual(original.logical_id, other.logical_id)
        self.assertEqual(original.state_id, other.state_id)

    def test_canonical_numeric_identity_exact_forms(self):
        from src.swing_structure import _canonical_numeric_identity
        groups = [('10', ('10', '10.0', '10.00', '1E+1')),
                  ('0.25', ('0.25', '0.250', '0.2500')),
                  ('-3', ('-3', '-3.0')),
                  ('0', ('0', '0.0', '-0.0', '0E+10', '-0E-20'))]
        with localcontext() as context:
            context.prec = 2
            for expected, forms in groups:
                for form in forms:
                    self.assertEqual(_canonical_numeric_identity(Decimal(form)), expected)
            exact = Decimal('123456789.00000000000000000000001')
            self.assertEqual(_canonical_numeric_identity(exact), str(exact))
            self.assertNotEqual(_canonical_numeric_identity(exact), '123456789')
