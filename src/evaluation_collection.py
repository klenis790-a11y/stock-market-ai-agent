"""Explicit historical fact collection. No scheduling, returns, or decision mutation."""
from dataclasses import dataclass
from datetime import datetime, timezone, date
from math import isfinite
from uuid import uuid4

from src import alpha_vantage_client
from src.evaluation_models import EvaluationPrice, EvaluationObservation, utc_timestamp
from src.observation_resolution import (resolve_observation_target, adjusted_close_methodology,
                                        ADJUSTED_PRICE_POLICY, ADJUSTMENT_BASIS)


def now_utc():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AdjustedDailyObservation:
    symbol: str
    session_date: date
    adjusted_close: float
    retrieved_at: str
    price_policy_version: str = ADJUSTED_PRICE_POLICY


def normalize_adjusted(payload, symbol, session, retrieved_at):
    """Exact-date extraction; missing/invalid inputs raise, never select nearby bars."""
    if not isinstance(payload, dict) or any(k in payload for k in ('Information', 'Note', 'Error Message')):
        raise ValueError('Historical provider response unavailable.')
    metadata = payload.get('Meta Data')
    series = payload.get('Time Series (Daily)')
    if not isinstance(metadata, dict) or metadata.get('2. Symbol') != symbol or not isinstance(series, dict):
        raise ValueError('Historical response identity/shape invalid.')
    row = series.get(session.isoformat())
    if not isinstance(row, dict):
        raise ValueError('Exact historical session unavailable.')
    value = row.get('5. adjusted close')
    if type(value) not in (str, int, float):
        raise ValueError('Adjusted close unavailable.')
    try:
        price = float(value)
    except (ValueError, OverflowError):
        raise ValueError('Adjusted close invalid.') from None
    if not isfinite(price) or price <= 0:
        raise ValueError('Adjusted close must be finite and positive.')
    return AdjustedDailyObservation(symbol, session, price, utc_timestamp(retrieved_at))


def collect_evaluation_observations(store, enrollment, as_of, *, market, clock=now_utc):
    """Return reference/endpoint facts, storing the pair atomically.

    An existing complete pair is returned without requests. Partial prior persistence
    or revisions raise before retrieval; no implicit repair/refresh occurs. Provider
    failures for stock abort without writes; benchmark failures become intentional
    missing facts with fixed safe reasons, never raw payload messages.
    """
    if enrollment.methodology != adjusted_close_methodology():
        raise ValueError('Unsupported adjusted-price policy.')
    target = resolve_observation_target(enrollment, as_of, market=market)
    return _collect_target_observations(store, enrollment, target, clock=clock)


def _collect_target_observations(store, enrollment, target, *, clock=now_utc):
    """Shared exact-window collection after source-specific resolution/policy checks."""
    if target.enrollment != enrollment:
        raise ValueError('Target enrollment mismatch.')
    if target.eligibility != 'ELIGIBLE':
        raise ValueError(f'Observation target {target.eligibility}.')
    if store.read_only:
        raise ValueError('Collection requires writable evaluation storage.')
    if store.get_enrollment(enrollment.enrollment_id) != enrollment:
        raise ValueError('Enrollment must match preserved enrollment.')
    sessions = (target.reference, target.target)
    existing = store.get_observations_for_enrollment(enrollment.enrollment_id)
    if existing:
        by_point = {item.point: item for item in existing}
        if len(existing) != 2 or set(by_point) != {'reference', 'endpoint'}:
            raise ValueError('Existing observations require explicit review; no refresh allowed.')
        result = tuple(by_point[p] for p in ('reference', 'endpoint'))
        if any(item.supersedes_id or item.effective_at != utc_timestamp(session.closes_at.isoformat())
               for item, session in zip(result, sessions)):
            raise ValueError('Existing observation window differs; no refresh allowed.')
        return result
    prices = {}
    for symbol in dict.fromkeys((enrollment.ticker, enrollment.methodology.benchmark_symbol)):
        try:
            payload = alpha_vantage_client.get_daily_adjusted(symbol)
        except RuntimeError:
            payload = None
        retrieved = utc_timestamp(clock().isoformat())
        values = []
        for session in sessions:
            try:
                normalized = normalize_adjusted(payload, symbol, session.date, retrieved)
            except ValueError:
                values.append(None)
                continue
            values.append(EvaluationPrice(symbol, normalized.adjusted_close,
                session.closes_at.isoformat(), normalized.retrieved_at,
                'Alpha Vantage / TIME_SERIES_DAILY_ADJUSTED',
                '5. adjusted close / ' + ADJUSTED_PRICE_POLICY, ADJUSTMENT_BASIS,
                enrollment.methodology.currency))
        if symbol == enrollment.ticker and any(value is None for value in values):
            raise ValueError('Required stock observations unavailable; nothing persisted.')
        prices[symbol] = values
    if any(price is None for price in prices[enrollment.ticker]):
        raise ValueError('Required stock observations unavailable; nothing persisted.')
    recorded = clock().isoformat()
    observations = []
    for index, (point, session) in enumerate(zip(('reference', 'endpoint'), sessions)):
        stock = prices[enrollment.ticker][index]
        benchmark = prices[enrollment.methodology.benchmark_symbol][index]
        missing = [name for name, value in (('stock', stock), ('benchmark', benchmark)) if value is None]
        observations.append(EvaluationObservation(str(uuid4()), enrollment.enrollment_id, point,
            session.closes_at.isoformat(), recorded, stock, benchmark,
            'Unavailable or invalid exact-session adjusted price: ' + ', '.join(missing) if missing else None))
    # Reference and endpoint are one logical collection, committed atomically.
    store.save_observations(observations)
    return tuple(observations)
