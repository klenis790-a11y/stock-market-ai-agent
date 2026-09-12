"""Daily-only provider normalization and pure calendar filtering, separate from V0.6."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from src import alpha_vantage_client
from src.market_calendar import USMarketCalendar, aware_utc
from src.market_data_models import (MarketBar, HistoricalOHLCV, normalize_symbol)
from src.observation_resolution import SUPPORTED_MARKET


def _inputs(symbol, as_of, market, timeframe):
    symbol = normalize_symbol(symbol)
    as_of = aware_utc(as_of)
    if timeframe != '1d':
        raise ValueError('Only 1d timeframe is supported.')
    if market != SUPPORTED_MARKET:
        raise ValueError('Verified US equity/ETF XNYS scope is required; no symbol mapping is inferred.')
    return symbol, as_of


def _number(value):
    if type(value) not in (str, int, float):
        raise ValueError('Missing or invalid OHLCV number.')
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid OHLCV number.') from None
    if not number.is_finite():
        raise ValueError('OHLCV number must be finite.')
    return number


def build_historical_ohlcv(symbol, payload, as_of, *, retrieved_at, market,
                           timeframe='1d', calendar=None):
    """Pure build from one supplied provider vintage. Completion is NOT proof of
    historical publication time. Bars are bounded by both as_of and retrieval time.
    All session keys are validated; OHLCV validation applies to completed rows only.
    """
    symbol, as_of = _inputs(symbol, as_of, market, timeframe)
    retrieved_at = aware_utc(retrieved_at)
    calendar = calendar or USMarketCalendar()
    cutoff = min(as_of, retrieved_at)
    if calendar.calendar_id != 'XNYS':
        raise ValueError('Unsupported calendar.')
    expected_last = calendar.last_completed_session(cutoff)
    if not isinstance(payload, dict) or any(k in payload for k in ('Information', 'Note', 'Error Message')):
        raise ValueError('Historical daily provider response unavailable.')
    metadata, series = payload.get('Meta Data'), payload.get('Time Series (Daily)')
    if (not isinstance(metadata, dict) or metadata.get('2. Symbol') != symbol
            or metadata.get('5. Time Zone') not in ('US/Eastern', 'America/New_York')):
        raise ValueError('Provider symbol/timezone metadata missing or unsupported.')
    if not isinstance(series, dict) or not series:
        raise ValueError('Historical daily series is missing or empty.')
    bars, seen = [], set()
    for key, row in series.items():
        if not isinstance(key, str):
            raise ValueError('Daily session key must be YYYY-MM-DD.')
        try:
            day = date.fromisoformat(key)
        except ValueError:
            raise ValueError('Daily session key must be YYYY-MM-DD.') from None
        if day in seen:
            raise ValueError('Duplicate normalized session.')
        seen.add(day)
        if key != day.isoformat():
            raise ValueError('Daily session key must be YYYY-MM-DD.')
        session = calendar.session_on_or_after(day)
        if session.date != day:
            raise ValueError('Provider date is not an XNYS session.')
        if session.closes_at > cutoff:
            continue
        if not isinstance(row, dict):
            raise ValueError('Malformed daily row.')
        prices = [_number(row.get(name)) for name in ('1. open', '2. high', '3. low', '4. close')]
        volume = _number(row.get('5. volume'))
        if volume < 0 or volume != volume.to_integral_value():
            raise ValueError('Volume must be a nonnegative integer.')
        bars.append(MarketBar(symbol, day, *(float(p) for p in prices), int(volume)))
    bars.sort(key=lambda b: b.session_date)
    # Gaps are visible, including a missing latest completed session. No fill/repair.
    included = {bar.session_date for bar in bars}
    missing = tuple(day for day in calendar.completed_sessions(bars[0].session_date, cutoff)
                    if day not in included) if bars else ()
    return HistoricalOHLCV(symbol, tuple(bars), as_of, retrieved_at, calendar.version,
                           expected_last, missing)


def retrieve_historical_ohlcv(symbol, as_of, *, market, timeframe='1d'):
    """Explicit one-request operation. No automatic refresh, persistence or retries."""
    symbol, as_of = _inputs(symbol, as_of, market, timeframe)
    calendar = USMarketCalendar()
    calendar.last_completed_session(as_of)  # Reject unsupported time coverage before IO.
    payload = alpha_vantage_client.get_daily_raw(symbol)
    retrieved_at = datetime.now(timezone.utc)  # IO timestamp; core builder has no clock.
    return build_historical_ohlcv(symbol, payload, as_of, retrieved_at=retrieved_at,
                                   market=market, timeframe=timeframe, calendar=calendar)
