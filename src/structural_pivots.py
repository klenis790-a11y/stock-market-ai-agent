"""ATS-1: pure confirmed RAW daily pivots, not connected to analyst generation.

Caller supplies the actual materialization time. Knowledge cutoff constrains source
acquisition; available_at describes this newly materialized artifact, never a claim
of historical provider publication. No clock, provider, persistence or UI access.
"""
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import Enum
from hashlib import sha256
import json

from src.market_calendar import USMarketCalendar, aware_utc
from src.market_data_models import HistoricalOHLCV, METHODOLOGY_VERSION as DATA_VERSION

METHODOLOGY_VERSION = 'advanced-technical-structure-v1'
LOOKBACK_SESSIONS = 126
LEFT_STRENGTH = RIGHT_STRENGTH = 2
HISTORICAL_LIMITATION = 'HISTORICAL_AVAILABILITY_UNVERIFIED'


class PivotType(str, Enum):
    HIGH = 'HIGH'
    LOW = 'LOW'


class UnavailableReason(str, Enum):
    INSUFFICIENT_DATA = 'INSUFFICIENT_DATA'
    MISSING_SESSION = 'MISSING_SESSION'
    RIGHT_CONTEXT_NOT_COMPLETED = 'RIGHT_CONTEXT_NOT_COMPLETED'


@dataclass(frozen=True)
class ConfirmedPivot:
    symbol: str
    timeframe: str
    methodology_version: str
    pivot_type: PivotType
    event_session: date
    event_time: None
    price: float
    left_sessions: tuple[date, ...]
    right_sessions: tuple[date, ...]
    confirmed_at: datetime
    available_at: datetime
    computed_at: datetime
    market_as_of: datetime
    knowledge_as_of: datetime
    logical_id: str
    state_id: str
    source_retrieved_at: datetime
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class PivotUnavailable:
    event_session: date
    reason: UnavailableReason
    missing_sessions: tuple[date, ...]


@dataclass(frozen=True)
class PivotSnapshot:
    source_dataset: HistoricalOHLCV
    anchor_session: date
    window_start: date
    market_as_of: datetime
    knowledge_as_of: datetime
    computed_at: datetime
    pivots: tuple[ConfirmedPivot, ...]
    unavailable: tuple[PivotUnavailable, ...]
    methodology_version: str = METHODOLOGY_VERSION
    limitations: tuple[str, ...] = (HISTORICAL_LIMITATION,)


def _identity(fields):
    return sha256(json.dumps(fields, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def detect_confirmed_pivots(dataset, *, market_as_of, knowledge_as_of, computed_at,
                            calendar=None):
    """Return current pivots and per-session unavailability, in session/type order.

    Identity uses the exact five-bar source content, not subsequent bars, retrieval
    time or computation time. The result retains the full immutable source lineage.
    Unsupported calendar coverage/version and invalid provenance fail closed.
    """
    if not isinstance(dataset, HistoricalOHLCV):
        raise ValueError('HistoricalOHLCV required.')
    replace(dataset, bars=tuple(replace(bar) for bar in dataset.bars))
    calendar = calendar or USMarketCalendar()
    market, knowledge, computed = map(aware_utc, (market_as_of, knowledge_as_of, computed_at))
    if (dataset.methodology_version != DATA_VERSION or dataset.exchange_calendar != 'XNYS'
            or dataset.calendar_version != calendar.version
            or dataset.exchange_timezone != str(calendar.timezone)):
        raise ValueError('Unsupported source/calendar provenance.')
    if not (market <= dataset.requested_as_of and market <= knowledge <= computed
            and dataset.retrieved_at <= knowledge):
        raise ValueError('Source or cutoff exceeds declared knowledge/materialization time.')
    for bar in dataset.bars:
        session = calendar.session_on_or_after(bar.session_date)
        if (session.date != bar.session_date or session.closes_at > dataset.requested_as_of
                or session.closes_at > dataset.retrieved_at):
            raise ValueError('Source contains non-session or uncompleted/unacquired bars.')
    if set(dataset.missing_sessions) & {bar.session_date for bar in dataset.bars}:
        raise ValueError('Source marks an observed session missing.')

    anchor = calendar.last_completed_session(market)
    # Walk actual exchange sessions; calendar coverage errors propagate, never a
    # weekday approximation or an arbitrary calendar-day lookback.
    backward = [anchor]
    for _ in range(LOOKBACK_SESSIONS + LEFT_STRENGTH - 1):
        session = calendar.session_on_or_after(backward[-1])
        backward.append(calendar.last_completed_session(session.opens_at - timedelta(microseconds=1)))
    sessions = list(reversed(backward))
    sessions.extend(calendar.advance_sessions(anchor, n).date for n in (1, 2))
    bars = {bar.session_date: bar for bar in dataset.bars if bar.session_date <= anchor}
    first = dataset.data_window_start
    pivots, unavailable = [], []
    for i in range(LEFT_STRENGTH, LEFT_STRENGTH + LOOKBACK_SESSIONS):
        event = sessions[i]
        neighbors = sessions[i-2:i+3]
        if neighbors[-1] > anchor:
            unavailable.append(PivotUnavailable(event, UnavailableReason.RIGHT_CONTEXT_NOT_COMPLETED, ()))
            continue
        absent = tuple(day for day in neighbors if day not in bars)
        if absent:
            gap = any(day in dataset.missing_sessions or (first is not None and day >= first)
                      for day in absent)
            reason = UnavailableReason.MISSING_SESSION if gap else UnavailableReason.INSUFFICIENT_DATA
            unavailable.append(PivotUnavailable(event, reason, absent))
            continue
        pattern = [bars[day] for day in neighbors]
        center = pattern[2]
        others = pattern[:2] + pattern[3:]
        for kind in PivotType:
            value = center.high if kind == PivotType.HIGH else center.low
            valid = (all(value > b.high for b in others) if kind == PivotType.HIGH
                     else all(value < b.low for b in others))
            if not valid:
                continue
            key = [dataset.symbol, 'DAILY', 'XNYS', METHODOLOGY_VERSION, str(event), kind.value]
            logical = 'PIVOT:' + _identity(key)
            # Canonical numeric representation also treats integer/float inputs
            # equivalently, consistent with the released numeric price model.
            content = [[str(b.session_date), *[float(v).hex() for v in
                        (b.open, b.high, b.low, b.close)], b.volume] for b in pattern]
            confirmed = aware_utc(calendar.session_on_or_after(neighbors[-1]).closes_at)
            state = 'PIVOT_STATE:' + _identity([key, content, dataset.provider,
                dataset.provider_function, dataset.adjustment_mode, dataset.methodology_version,
                dataset.calendar_version, confirmed.isoformat()])
            pivots.append(ConfirmedPivot(dataset.symbol, 'DAILY', METHODOLOGY_VERSION, kind,
                event, None, value, tuple(neighbors[:2]), tuple(neighbors[3:]), confirmed,
                computed, computed, market, knowledge, logical, state, dataset.retrieved_at,
                (HISTORICAL_LIMITATION,)))
    return PivotSnapshot(dataset, anchor, sessions[LEFT_STRENGTH], market, knowledge,
                         computed, tuple(pivots), tuple(unavailable))
