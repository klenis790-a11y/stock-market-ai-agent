"""Daily raw data, local calendars and mocked IO only; no live provider calls."""
import io
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone
from unittest.mock import patch
from urllib.error import URLError

from src.market_calendar import USMarketCalendar
from src.market_data_models import MarketBar, require_minimum_history
from src.historical_market_data import build_historical_ohlcv, retrieve_historical_ohlcv
from src.observation_resolution import SUPPORTED_MARKET


def instant(text):
    return datetime.fromisoformat(text)


def payload(days):
    return {'Meta Data': {'2. Symbol': 'TEST', '5. Time Zone': 'US/Eastern'},
            'Time Series (Daily)': {str(day): {'1. open': '100', '2. high': '105',
            '3. low': '95', '4. close': '102', '5. volume': '1234'} for day in days}}


class DailyMarketDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = USMarketCalendar()

    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('Live network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def build(self, data, at='2025-03-10T17:00:00-04:00', **kwargs):
        return build_historical_ohlcv(' test ', data, instant(at),
            retrieved_at=instant('2026-09-01T00:00:00+00:00'), market=SUPPORTED_MARKET,
            calendar=self.calendar, **kwargs)

    def test_calendar_completion_matrix(self):
        data = payload(['2025-03-07', '2025-03-10'])
        for at, last in [
            ('2025-03-10T08:00:00-04:00', '2025-03-07'),
            ('2025-03-10T10:17:00-04:00', '2025-03-07'),
            ('2025-03-10T15:59:59-04:00', '2025-03-07'),
            ('2025-03-10T16:00:00-04:00', '2025-03-10'),
            ('2025-03-10T16:30:00-04:00', '2025-03-10'),
            ('2025-03-08T12:00:00-05:00', '2025-03-07'),
            ('2025-03-09T12:00:00-04:00', '2025-03-07')]:
            with self.subTest(at=at):
                result = self.build(data, at)
                self.assertEqual(str(result.effective_last_session), last)
                self.assertEqual(result.effective_last_session, result.expected_last_session)
                self.assertEqual(result.requested_as_of.utcoffset().total_seconds(), 0)
        self.assertEqual(self.build(data, '2025-03-10T10:17:00-04:00').bars,
                         self.build(data).bars[:1])

    def test_holiday_halfday_and_dst(self):
        for days, at, last in [
            (['2025-07-03'], '2025-07-04T12:00:00-04:00', '2025-07-03'),
            (['2021-07-02'], '2021-07-05T12:00:00-04:00', '2021-07-02'),
            (['2025-11-26', '2025-11-28'], '2025-11-28T12:30:00-05:00', '2025-11-26'),
            (['2025-11-26', '2025-11-28'], '2025-11-28T13:01:00-05:00', '2025-11-28'),
            (['2025-03-06', '2025-03-07'], '2025-03-07T20:30:00+00:00', '2025-03-06'),
            (['2025-03-07', '2025-03-10'], '2025-03-10T20:30:00+00:00', '2025-03-10')]:
            with self.subTest(at=at):
                self.assertEqual(str(self.build(payload(days), at).effective_last_session), last)

    def test_naive_scope_timeframe_and_retrieval_bound(self):
        data = payload(['2025-03-07', '2025-03-10'])
        args = dict(symbol='TEST', payload=data, as_of=instant('2025-03-10T17:00:00-04:00'),
                    retrieved_at=instant('2025-03-10T10:00:00-04:00'), market=SUPPORTED_MARKET)
        self.assertEqual(str(build_historical_ohlcv(**args).effective_last_session), '2025-03-07')
        for change in ({'as_of': datetime(2025, 3, 10)}, {'retrieved_at': datetime(2025, 3, 10)},
                       {'market': 'CRYPTO'}, {'timeframe': '1h'}, {'symbol': ' '}):
            with self.assertRaises(ValueError):
                build_historical_ohlcv(**(args | change))
        with patch('src.alpha_vantage_client.get_daily_raw') as client:
            for at, market in ((datetime(2025, 3, 10), SUPPORTED_MARKET),
                               (args['as_of'], 'CRYPTO')):
                with self.assertRaises(ValueError):
                    retrieve_historical_ohlcv('TEST', at, market=market)
            client.assert_not_called()

    def test_all_required_fields_and_numeric_relationships(self):
        day = '2025-03-10'
        for field in ('1. open', '2. high', '3. low', '4. close', '5. volume'):
            data = payload([day])
            del data['Time Series (Daily)'][day][field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.build(data)
        for field, value in [
            ('1. open', '0'), ('1. open', '-1'), ('1. open', 'NaN'),
            ('2. high', 'Infinity'), ('3. low', '-Infinity'), ('4. close', 'bad'),
            ('5. volume', '-1'), ('5. volume', '1.5'), ('5. volume', 'NaN'),
            ('5. volume', True), ('1. open', True), ('1. open', '1e999'),
            ('2. high', '94'), ('1. open', '106'), ('4. close', '106'),
            ('1. open', '94'), ('4. close', '94')]:
            data = payload([day]); data['Time Series (Daily)'][day][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.build(data)
        for volume in ('0', '1234', '1234.0', '12345678901234567890'):
            data = payload([day]); data['Time Series (Daily)'][day]['5. volume'] = volume
            result = self.build(data)
            self.assertIs(type(result.bars[0].volume), int)

    def test_raw_adjusted_separation(self):
        data = payload(['2025-03-10'])
        data['Time Series (Daily)']['2025-03-10']['5. adjusted close'] = '1'
        result = self.build(data)
        self.assertEqual(result.bars[0].close, 102)
        self.assertEqual(result.bars[0].open, 100)
        self.assertEqual(result.adjustment_mode, 'RAW')
        self.assertEqual(result.provider_function, 'TIME_SERIES_DAILY')
        with self.assertRaises(ValueError):
            replace(result, adjustment_mode='ADJUSTED')

    def test_provider_payload_errors(self):
        for data in ({'Information': 'premium'}, {'Note': 'limit'}, {'Error Message': 'invalid'},
                     {}, [], {'Meta Data': {}, 'Time Series (Daily)': {}},
                     payload([])):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.build(data)
        for value in ([], None, 'bad'):
            data = payload(['2025-03-10']); data['Time Series (Daily)'] = value
            with self.assertRaises(ValueError): self.build(data)
        for key, value in (('2. Symbol', 'OTHER'), ('5. Time Zone', 'UTC')):
            data = payload(['2025-03-10']); data['Meta Data'][key] = value
            with self.assertRaises(ValueError): self.build(data)

    def test_sessions_and_duplicates_rejected(self):
        for day in ('2025-03-08', '2025-07-04', 'not-a-date', '20250310'):
            with self.subTest(day=day), self.assertRaises(ValueError): self.build(payload([day]))
        data = payload(['2025-03-10', '20250310'])
        with self.assertRaises(ValueError): self.build(data)
        from src.alpha_vantage_client import get_daily_raw
        duplicate = b'{"Time Series (Daily)":{"2025-03-10":{},"2025-03-10":{}}}'
        with patch('src.alpha_vantage_client.urlopen', return_value=io.BytesIO(duplicate)), \
             patch.dict('os.environ', {'ALPHA_VANTAGE_API_KEY': 'offline-fixture'}), \
             patch('src.alpha_vantage_client._pace_request'):
            with self.assertRaises(RuntimeError): get_daily_raw('TEST')

    def test_reproducibility_immutability_order_provenance(self):
        data = payload(['2025-03-10', '2025-03-07'])
        result = self.build(data)
        self.assertEqual(result, self.build(payload(['2025-03-07', '2025-03-10'])))
        self.assertEqual([str(b.session_date) for b in result.bars], ['2025-03-07', '2025-03-10'])
        self.assertEqual(result.symbol, 'TEST')
        self.assertEqual(result.timeframe, '1d')
        self.assertEqual(result.exchange_calendar, 'XNYS')
        self.assertEqual(result.exchange_timezone, 'America/New_York')
        self.assertEqual(result.calendar_version, self.calendar.version)
        self.assertEqual(result.methodology_version, 'daily-ohlcv-normalization-v1')
        self.assertEqual(result.retrieved_at.utcoffset().total_seconds(), 0)
        self.assertIn('unverified', result.availability_basis)
        with self.assertRaises(FrozenInstanceError): result.bars[0].close = 0
        with self.assertRaises(FrozenInstanceError): result.symbol = 'OTHER'
        with self.assertRaises(ValueError): replace(result, bars=(result.bars[0], result.bars[0]))
        data['Time Series (Daily)'].clear()
        self.assertEqual(len(result.bars), 2)

    def test_minimum_history_and_gaps(self):
        days = self.calendar.completed_sessions(date(2024, 1, 1), instant('2025-03-10T21:00:00+00:00'))[-200:]
        result = self.build(payload(days))
        self.assertIs(require_minimum_history(result, 200), result)
        with self.assertRaises(ValueError): require_minimum_history(self.build(payload(days[1:])), 200)
        self.assertIsNotNone(require_minimum_history(self.build(payload([days[-1]])), 1))
        for n in (0, -1, True, 1.5):
            with self.assertRaises(ValueError): require_minimum_history(result, n)
        gap = self.build(payload([days[-3], days[-1]]))
        self.assertEqual(gap.missing_sessions, (days[-2],))
        with self.assertRaises(ValueError): require_minimum_history(gap, 2)
        stale = self.build(payload([days[-2]]))
        with self.assertRaises(ValueError): require_minimum_history(stale, 1)

    def test_no_completed_rows_is_honest(self):
        result = self.build(payload(['2025-03-10']), '2025-03-10T10:17:00-04:00')
        self.assertEqual(result.bars, ())
        self.assertIsNone(result.effective_last_session)
        with self.assertRaises(ValueError): require_minimum_history(result, 1)

    def test_explicit_retrieval_once_and_network_failure(self):
        with patch('src.alpha_vantage_client.get_daily_raw', return_value=payload(['2025-03-10'])) as client:
            result = retrieve_historical_ohlcv(' test ', instant('2025-03-10T17:00:00-04:00'), market=SUPPORTED_MARKET)
            client.assert_called_once_with('TEST')
            self.assertEqual(result.bars[0].close, 102)
        with patch('src.alpha_vantage_client.get_daily_raw', side_effect=RuntimeError('network unavailable')) as client:
            with self.assertRaises(RuntimeError):
                retrieve_historical_ohlcv('TEST', instant('2025-03-10T17:00:00-04:00'), market=SUPPORTED_MARKET)
            self.assertEqual(client.call_count, 1)

    def test_client_endpoint_and_legacy_decoder_unchanged(self):
        from src.alpha_vantage_client import get_daily_raw, get_daily_adjusted
        with patch('src.alpha_vantage_client._request', return_value={}) as request:
            get_daily_raw('TEST')
            request.assert_called_once_with('TIME_SERIES_DAILY', 'TEST', outputsize='full', reject_duplicate_keys=True)
            request.reset_mock()
            get_daily_adjusted('TEST')
            request.assert_called_once_with('TIME_SERIES_DAILY_ADJUSTED', 'TEST', outputsize='full')
        with patch('src.alpha_vantage_client.urlopen', side_effect=URLError('offline failure')), \
             patch.dict('os.environ', {'ALPHA_VANTAGE_API_KEY': 'offline-fixture'}), \
             patch('src.alpha_vantage_client._pace_request'):
            with self.assertRaises(RuntimeError): get_daily_raw('TEST')


class TechnicalFeatureTests(unittest.TestCase):
    def fixture(self, closes, volumes=None, ranges=None):
        from datetime import timedelta
        from src.market_data_models import HistoricalOHLCV
        # Synthetic ordered observations; calendar normalization is tested separately above.
        dates = USMarketCalendar().completed_sessions(date(2024, 1, 1), instant('2025-03-10T21:00:00+00:00'))[-len(closes):] if closes else ()
        bars = tuple(MarketBar('TEST', day, close, close if ranges is None else ranges[i][0],
                              close if ranges is None else ranges[i][1], close,
                              100 if volumes is None else volumes[i]) for i, (day, close) in enumerate(zip(dates, closes)))
        return HistoricalOHLCV('TEST', bars, instant('2025-03-10T21:00:00+00:00'),
            instant('2025-03-10T21:00:00+00:00'), USMarketCalendar.version, dates[-1] if dates else None, ())

    def build(self, closes, **kwargs):
        from src.technical_features import build_technical_feature_snapshot
        return build_technical_feature_snapshot(self.fixture(closes, **kwargs))

    def test_smas_percent_and_stacks(self):
        up = self.build(list(range(1, 201)))
        for name, value in (('sma_20', 190.5), ('sma_50', 175.5), ('sma_200', 100.5)):
            self.assertEqual(up.feature(name).value, value)
        self.assertAlmostEqual(up.feature('close_vs_sma_20_pct').value, (200/190.5-1)*100)
        self.assertEqual(up.feature('trend_structure').value, 'BULLISH_STACK')
        self.assertEqual(self.build(list(range(200, 0, -1))).feature('trend_structure').value, 'BEARISH_STACK')
        self.assertEqual(self.build([100]*200).feature('trend_structure').value, 'MIXED')
        self.assertIsNone(self.build([100]*199).feature('sma_200').value)
        self.assertIsNone(self.build([100]*199).feature('trend_structure').value)

    def test_rsi_wilder_known_and_edges(self):
        # Standard hand-worked Wilder initialization: gains .238571..., losses .10.
        prices = [44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,45.84,46.08,45.89,46.03,45.61,46.28,46.28]
        self.assertAlmostEqual(self.build(prices).feature('rsi_14').value, 70.4641350211, places=8)
        self.assertAlmostEqual(self.build(prices+[46.0]).feature('rsi_14').value, 66.2496185536, places=8)
        for closes, expected in ((list(range(1, 31)),100), (list(range(30, 0, -1)),0), ([100]*30,50)):
            self.assertAlmostEqual(self.build(closes).feature('rsi_14').value, expected)
        self.assertIsNone(self.build([100]*14).feature('rsi_14').value)

    def test_macd_seeding_and_impulse(self):
        ramp = self.build(list(range(1, 35)))
        self.assertAlmostEqual(ramp.feature('macd_line').value, 7)
        self.assertAlmostEqual(ramp.feature('macd_signal').value, 7)
        self.assertAlmostEqual(ramp.feature('macd_histogram').value, 0)
        flat = self.build([100]*34)
        for name in ('macd_line','macd_signal','macd_histogram'):
            self.assertAlmostEqual(flat.feature(name).value, 0)
        impulse = self.build([100]*34+[110])
        self.assertAlmostEqual(impulse.feature('macd_line').value, 0.7977207977208)
        self.assertAlmostEqual(impulse.feature('macd_signal').value, 0.1595441595442)
        self.assertAlmostEqual(impulse.feature('macd_histogram').value, 0.6381766381766)
        self.assertIsNone(self.build([100]*25).feature('macd_line').value)
        self.assertIsNotNone(self.build([100]*26).feature('macd_line').value)
        self.assertIsNone(self.build([100]*33).feature('macd_signal').value)

    def test_atr_normal_gaps_flat_and_smoothing(self):
        normal = self.build([100]*15, ranges=[(102,98)]*15)
        self.assertEqual(normal.feature('atr_14').value, 4)
        self.assertEqual(normal.feature('atr_pct').value, 4)
        for end, high, low in ((110,112,108),(90,92,88)):
            gap = self.build([100]*14+[end], ranges=[(102,98)]*14+[(high,low)])
            self.assertAlmostEqual(gap.feature('atr_14').value, 32/7)
        smoothed = self.build([100]*16, ranges=[(102,98)]*15+[(107,93)])
        self.assertAlmostEqual(smoothed.feature('atr_14').value, 66/14)
        self.assertEqual(self.build([100]*15).feature('atr_14').value, 0)
        self.assertIsNone(self.build([100]*14).feature('atr_14').value)

    def test_momentum_and_volume(self):
        for closes, expected in (([100]*5+[110],.1), ([100]*5+[90],-.1), ([100]*6,0)):
            self.assertAlmostEqual(self.build(closes).feature('momentum_5').value, expected)
        self.assertAlmostEqual(self.build([100]*20+[120]).feature('momentum_20').value, .2)
        self.assertIsNone(self.build([100]*5).feature('momentum_5').value)
        for latest in (200,50,0):
            result = self.build([100]*20, volumes=[100]*19+[latest])
            self.assertEqual(result.feature('average_volume_20').value, (1900+latest)/20)
            self.assertEqual(result.feature('volume_ratio_20').value, latest/((1900+latest)/20))
        zero = self.build([100]*20, volumes=[0]*20)
        self.assertEqual(zero.feature('average_volume_20').value, 0)
        self.assertEqual(zero.feature('volume_ratio_20').unavailable_reason, 'UNAVAILABLE_ZERO_DENOMINATOR')
        self.assertIsNone(self.build([100]*19).feature('average_volume_20').value)

    def test_partial_snapshot_and_missing_sessions(self):
        from src.technical_features import build_technical_feature_snapshot
        result = self.build([100]*50)
        for name in ('sma_20','sma_50','rsi_14','macd_signal','atr_14','average_volume_20'):
            self.assertIsNotNone(result.feature(name).value)
        self.assertEqual(result.feature('sma_200').unavailable_reason, 'UNAVAILABLE_DUE_TO_HISTORY')
        data = self.fixture([100]*50)
        gap = replace(data, bars=data.bars[:5]+data.bars[6:], missing_sessions=(data.bars[5].session_date,))
        result = build_technical_feature_snapshot(gap)
        self.assertIsNotNone(result.feature('sma_20').value)
        self.assertEqual(result.feature('rsi_14').unavailable_reason, 'UNAVAILABLE_DUE_TO_MISSING_SESSIONS')
        self.assertEqual(result.feature('macd_line').unavailable_reason, 'UNAVAILABLE_DUE_TO_MISSING_SESSIONS')
        self.assertTrue(all(f.value is None for f in self.build([]).features))

    def test_pure_immutable_provenance_and_numeric_safety(self):
        from src.technical_features import build_technical_feature_snapshot, FeatureValue
        data = self.fixture(list(range(1, 201)))
        before = repr(data)
        with patch('socket.socket.connect', side_effect=AssertionError('No network')), \
             patch('src.alpha_vantage_client._request', side_effect=AssertionError('No provider')):
            result = build_technical_feature_snapshot(data)
            self.assertEqual(result, build_technical_feature_snapshot(data))
        self.assertEqual(before, repr(data))
        self.assertIs(result.source_dataset, data)
        self.assertEqual(result.as_of, data.requested_as_of)
        self.assertEqual(result.latest_session, data.effective_last_session)
        self.assertEqual(result.methodology_version, 'technical-features-v1')
        self.assertIn(('MACD_SMA_SEEDED_EMA',(12,26,9)), result.indicator_parameters)
        with self.assertRaises(FrozenInstanceError): result.methodology_version = 'x'
        for value in (float('nan'),float('inf')):
            with self.assertRaises(ValueError): FeatureValue('bad',value,'price')

    def test_uncompleted_future_bar_cannot_change_features(self):
        from src.technical_features import build_technical_feature_snapshot
        data = payload(['2025-03-07','2025-03-10'])
        args = dict(as_of=instant('2025-03-10T10:17:00-04:00'),
                    retrieved_at=instant('2025-03-11T00:00:00+00:00'),market=SUPPORTED_MARKET)
        before = build_technical_feature_snapshot(build_historical_ohlcv('TEST',data,**args))
        data['Time Series (Daily)']['2025-03-10']['4. close'] = '999999'
        after = build_technical_feature_snapshot(build_historical_ohlcv('TEST',data,**args))
        self.assertEqual(before,after)


class TechnicalEvidenceTests(unittest.TestCase):
    def inputs(self):
        from src.technical_features import build_technical_feature_snapshot
        data = TechnicalFeatureTests().fixture(list(range(100, 150)))
        return data, build_technical_feature_snapshot(data)

    def catalog(self):
        from src.technical_evidence import build_technical_research_snapshot, build_technical_evidence_catalog
        return build_technical_evidence_catalog(build_technical_research_snapshot(*self.inputs()))

    def test_source_matching_and_stale_protection(self):
        from datetime import timedelta
        from src.technical_evidence import build_technical_research_snapshot
        data, features = self.inputs()
        self.assertIs(build_technical_research_snapshot(data, features).historical_ohlcv, data)
        for other in (replace(data, symbol='OTHER', bars=tuple(replace(b,symbol='OTHER') for b in data.bars)),
                      replace(data, requested_as_of=data.requested_as_of-timedelta(hours=1)),
                      replace(data, bars=data.bars[:-1]),
                      replace(data, retrieved_at=data.retrieved_at+timedelta(hours=1))):
            with self.assertRaises(ValueError): build_technical_research_snapshot(other, features)
        with self.assertRaises(ValueError):
            build_technical_research_snapshot(data, replace(features, methodology_version='future'))
        with self.assertRaises(ValueError):
            build_technical_research_snapshot(data, replace(features, features=features.features[:-1]))

    def test_fixed_ids_categories_and_order_independent(self):
        from src.technical_evidence import build_technical_research_snapshot, build_technical_evidence_catalog
        data, features = self.inputs()
        first = self.catalog()
        reversed_features = replace(features, features=tuple(reversed(features.features)))
        second = build_technical_evidence_catalog(build_technical_research_snapshot(data,reversed_features))
        self.assertEqual(first, second)
        self.assertEqual(first, self.catalog())
        self.assertEqual([i.evidence_id for i in first.items], [f'T{i:03d}' for i in range(1,len(first.items)+1)])
        categories = list(dict.fromkeys(i.category for i in first.items))
        self.assertEqual(categories, ['PRICE','TREND','MOMENTUM','VOLATILITY','VOLUME','DATA_QUALITY'])
        self.assertEqual(first.resolve('T001').label,'latest_close')
        with self.assertRaises(ValueError): first.resolve('E001')
        with self.assertRaises(ValueError): first.resolve('T999')

    def test_classification_units_and_missing(self):
        data, features = self.inputs()
        catalog = self.catalog()
        by_name = {i.label:i for i in catalog.items}
        for name in ('latest_close','latest_high','latest_low','latest_volume'):
            self.assertEqual(by_name[name].classification,'RETRIEVED_FACT')
        for feature in features.features:
            item = by_name[feature.name]
            self.assertEqual(item.classification,'CALCULATED_METRIC')
            self.assertEqual(item.value,feature.value)
            self.assertEqual(item.unit,feature.unit)
            self.assertEqual(item.unavailable_reason,feature.unavailable_reason)
        self.assertIsNone(by_name['sma_200'].value)
        self.assertEqual(by_name['sma_200'].unavailable_reason,'UNAVAILABLE_DUE_TO_HISTORY')
        self.assertIsNotNone(by_name['sma_50'].value)
        self.assertEqual(by_name['momentum_5'].unit,'decimal_return')
        self.assertEqual(by_name['close_vs_sma_20_pct'].unit,'percent')
        self.assertIsInstance(by_name['latest_close'].value,(int,float))

    def test_bounded_packet_provenance_no_signal_and_pure(self):
        from src.technical_evidence import build_technical_research_snapshot, build_technical_evidence_catalog
        from dataclasses import fields
        data, features = self.inputs()
        before = repr((data,features))
        with patch('socket.socket.connect',side_effect=AssertionError('No network')), \
             patch('src.alpha_vantage_client._request',side_effect=AssertionError('No provider')), \
             patch('src.technical_features.build_technical_feature_snapshot',side_effect=AssertionError('No recalculation')):
            snapshot = build_technical_research_snapshot(data,features)
            catalog = build_technical_evidence_catalog(snapshot)
            packet = catalog.to_packet()
            json.dumps(packet,allow_nan=False)
        self.assertEqual(before,repr((data,features)))
        self.assertEqual(catalog.provenance.requested_as_of,data.requested_as_of)
        self.assertEqual(catalog.provenance.latest_completed_session,data.effective_last_session)
        self.assertEqual(catalog.provenance.adjustment_mode,'RAW')
        self.assertEqual(catalog.provenance.market_data_methodology,data.methodology_version)
        self.assertEqual(catalog.provenance.feature_methodology,features.methodology_version)
        self.assertEqual(catalog.methodology_version,'technical-evidence-v1')
        self.assertNotIn('bars', packet)
        self.assertNotIn('source_dataset',json.dumps(packet))
        forbidden = {'recommendation','signal','technical_rating','confidence','price_target','expected_return'}
        self.assertFalse(forbidden & {f.name for f in fields(snapshot)})
        self.assertFalse(forbidden & {i.label for i in catalog.items})
        self.assertEqual({i.classification for i in catalog.items},{'RETRIEVED_FACT','CALCULATED_METRIC'})
        with self.assertRaises(FrozenInstanceError): catalog.items[0].value = 0
        packet['items'][0]['value'] = 0
        self.assertNotEqual(catalog.items[0].value,0)

    def test_invalid_features_and_empty_snapshot(self):
        from src.technical_evidence import build_technical_research_snapshot, build_technical_evidence_catalog, TechnicalEvidenceItem
        from src.technical_features import build_technical_feature_snapshot
        data, features = self.inputs()
        for changed in (replace(features.features[0],unit='incorrect'),
                        replace(features.features[0],value='fabricated prose')):
            with self.assertRaises(ValueError):
                build_technical_research_snapshot(data,replace(features,features=(changed,)+features.features[1:]))
        for bad in (float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                TechnicalEvidenceItem('T001','PRICE','close',bad,'price','RETRIEVED_FACT','source')
        empty = TechnicalFeatureTests().fixture([])
        catalog = build_technical_evidence_catalog(build_technical_research_snapshot(empty,build_technical_feature_snapshot(empty)))
        self.assertIsNone(catalog.items[0].value)
        self.assertEqual(catalog.items[0].unavailable_reason,'NO_COMPLETED_BARS')


class TechnicalAnalystTests(unittest.TestCase):
    def fixture(self, size=50):
        from src.technical_features import build_technical_feature_snapshot
        from src.technical_evidence import build_technical_research_snapshot, build_technical_evidence_catalog
        data = TechnicalFeatureTests().fixture(list(range(100,100+size)))
        snapshot = build_technical_research_snapshot(data,build_technical_feature_snapshot(data))
        return snapshot,build_technical_evidence_catalog(snapshot)

    def output(self,catalog,signal='NEUTRAL'):
        ids = {i.label:i.evidence_id for i in catalog.items}
        statement = lambda text: {'text':text,'evidence_ids':[ids['momentum_5']]}
        return dict(signal=signal,confidence=60,
            summary=statement('The near-term evidence is mixed.'),
            thesis=statement('momentum_5 informs this interpretation.'),
            supporting_evidence_ids=[ids['momentum_5']],conflicting_evidence_ids=[],
            confirmation_conditions=[statement('The interpretation strengthens if momentum_5 remains positive.')],
            invalidation_conditions=[statement('A reversal in momentum_5 would undermine the interpretation.')],
            risk_notes=[statement('Recent momentum may not persist.')],
            missing_evidence_ids=[i.evidence_id for i in catalog.items if i.value is None],
            missing_data_acknowledgement='Longer trend evidence is incomplete.')

    def run_output(self,output,snapshot=None,catalog=None,horizon=None):
        from src.technical_analyst import analyze_technical_snapshot,HORIZONS
        if snapshot is None: snapshot,catalog=self.fixture()
        with patch('src.openai_client.request_text',return_value=json.dumps(output)) as request:
            result=analyze_technical_snapshot(snapshot,catalog,horizon or HORIZONS[0])
            request.assert_called_once()
            sent=json.loads(request.call_args.kwargs['input'])
            self.assertNotIn('bars',sent['technical_evidence'])
            self.assertTrue(request.call_args.kwargs['text']['format']['strict'])
            return result

    def test_valid_signals_horizons_and_trusted_provenance(self):
        from src.technical_analyst import HORIZONS
        snapshot,catalog=self.fixture()
        for signal in ('BULLISH','NEUTRAL','BEARISH'):
            for horizon in HORIZONS:
                result=self.run_output(self.output(catalog,signal),snapshot,catalog,horizon)
                self.assertEqual(result.analysis.signal,signal)
                self.assertEqual(result.horizon,horizon)
                self.assertEqual(result.provenance,catalog.provenance)
                self.assertEqual(result.analyst_methodology_version,'technical-analyst-v1')
                with self.assertRaises(FrozenInstanceError): result.horizon='other'
        full,full_catalog=self.fixture(200)
        for confidence in (0,100):
            output=self.output(full_catalog);output['confidence']=confidence
            self.assertEqual(self.run_output(output,full,full_catalog).analysis.confidence,confidence)

    def test_invalid_confidence_enum_and_provenance_injection(self):
        _,catalog=self.fixture()
        for key,value in [('confidence',-1),('confidence',101),('confidence',1.5),('confidence',True),
                          ('confidence',95),('signal','Hold'),('symbol','EVIL'),('horizon','other')]:
            output=self.output(catalog);output[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): self.run_output(output)

    def test_citation_and_missing_validation(self):
        _,catalog=self.fixture()
        for key,value in [('supporting_evidence_ids',[]),('supporting_evidence_ids',['T999']),
                          ('supporting_evidence_ids',['T001','T001']),('supporting_evidence_ids',['T006']),
                          ('conflicting_evidence_ids',['T999']),('missing_evidence_ids',[])]:
            output=self.output(catalog);output[key]=value
            with self.assertRaises(ValueError): self.run_output(output)
        output=self.output(catalog);output['conflicting_evidence_ids']=['T001']
        self.assertEqual(self.run_output(output).analysis.conflicting_evidence_ids,('T001',))
        output['conflicting_evidence_ids']=output['supporting_evidence_ids']
        with self.assertRaises(ValueError): self.run_output(output)

    def test_hallucinations_and_obvious_contradictions(self):
        _,catalog=self.fixture()
        for text in ('Support is $193.47.', 'Resistance is nearby.', 'RSI is 71.3.',
                     'SMA is 123.4.', 'The current quote is favorable.',
                     'A future breakout already occurred.', 'Price is above sma_200.',
                     'The technical setup is strongly bearish.'):
            output=self.output(catalog,'BULLISH');output['thesis']['text']=text
            with self.subTest(text=text),self.assertRaises(ValueError): self.run_output(output)
        output=self.output(catalog);output['thesis']['evidence_ids']=['T999']
        with self.assertRaises(ValueError): self.run_output(output)

    def test_preflight_no_requests(self):
        from src.technical_analyst import analyze_technical_snapshot,HORIZONS
        snapshot,catalog=self.fixture()
        tiny,tiny_catalog=self.fixture(1)
        wrong=replace(catalog,provenance=replace(catalog.provenance,symbol='OTHER'))
        with patch('src.openai_client.request_text') as request:
            for s,c,h in ((tiny,tiny_catalog,HORIZONS[0]),(snapshot,catalog,'one day'),
                          (snapshot,wrong,HORIZONS[0]),
                          (snapshot,replace(catalog,methodology_version='future'),HORIZONS[0]),
                          (snapshot,replace(catalog,items=catalog.items+(catalog.items[0],)),HORIZONS[0])):
                with self.assertRaises(ValueError): analyze_technical_snapshot(s,c,h)
            request.assert_not_called()

    def test_conditions_and_no_fallback(self):
        from src.technical_analyst import analyze_technical_snapshot,HORIZONS
        snapshot,catalog=self.fixture()
        for key in ('confirmation_conditions','invalidation_conditions'):
            output=self.output(catalog,'BEARISH');output[key]=[]
            with self.assertRaises(ValueError): self.run_output(output)
        for response in ('not json','{}'):
            with patch('src.openai_client.request_text',return_value=response) as request:
                with self.assertRaises(ValueError): analyze_technical_snapshot(snapshot,catalog,HORIZONS[0])
                self.assertEqual(request.call_count,1)
        with patch('src.openai_client.request_text',side_effect=RuntimeError('timeout')) as request:
            with self.assertRaises(RuntimeError): analyze_technical_snapshot(snapshot,catalog,HORIZONS[0])
            self.assertEqual(request.call_count,1)

    def test_packet_only_no_provider_and_prompt_boundaries(self):
        from src.technical_analyst import INSTRUCTIONS
        _,catalog=self.fixture()
        with patch('socket.socket.connect',side_effect=AssertionError('No network')), \
             patch('src.alpha_vantage_client._request',side_effect=AssertionError('No market calls')):
            result=self.run_output(self.output(catalog))
        self.assertEqual(result.analysis.signal,'NEUTRAL')
        for phrase in ('not a trader','No outside/current market knowledge','not neutral','FUTURE',
                       'No support/resistance','NO numeric literals','never mechanically map'):
            self.assertIn(phrase,INSTRUCTIONS)
