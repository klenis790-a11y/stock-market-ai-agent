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
