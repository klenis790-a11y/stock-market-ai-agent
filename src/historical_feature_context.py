"""ATS-2 historical access to technical-features-v1; no alternative formulas or IO.

Build once for the unique target sessions needed by a research run. Each target
uses the complete source prefix, never the structural participation window. Lookup
performs no feature calculation. Prefix calculation is intentionally straightforward
rather than a second incremental feature engine.
"""
from dataclasses import dataclass, replace
from datetime import date, datetime
from hashlib import sha256
import json

from src.market_calendar import USMarketCalendar, aware_utc
from src.market_data_models import HistoricalOHLCV, METHODOLOGY_VERSION as DATA_VERSION
from src.technical_features import (FeatureValue, METHODOLOGY_VERSION as FEATURE_VERSION,
                                    PARAMETERS, build_technical_feature_snapshot)

HISTORICAL_LIMITATION = 'HISTORICAL_AVAILABILITY_UNVERIFIED'


@dataclass(frozen=True)
class HistoricalFeatureObservation:
    feature: FeatureValue
    logical_id: str
    state_id: str


@dataclass(frozen=True)
class HistoricalFeatureContext:
    symbol: str
    target_session: date
    market_as_of: datetime
    knowledge_as_of: datetime
    source_retrieved_at: datetime
    computed_at: datetime
    available_at: datetime
    source_prefix_id: str
    atr_14: HistoricalFeatureObservation
    volume_ratio_20: HistoricalFeatureObservation
    feature_methodology_version: str = FEATURE_VERSION
    limitations: tuple[str, ...] = (HISTORICAL_LIMITATION,)


@dataclass(frozen=True)
class HistoricalFeatureIndex:
    source_dataset: HistoricalOHLCV
    market_as_of: datetime
    knowledge_as_of: datetime
    computed_at: datetime
    contexts: tuple[HistoricalFeatureContext, ...]

    def resolve(self, target_session):
        if type(target_session) is not date:
            raise ValueError('Exact target session date required.')
        for context in self.contexts:
            if context.target_session == target_session:
                return context
        raise ValueError('Target session not included in this historical context index.')


def _identity(fields):
    return sha256(json.dumps(fields, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def build_historical_feature_index(dataset, target_sessions, *, market_as_of,
                                   knowledge_as_of, computed_at, calendar=None):
    """Reuse the authoritative feature builder once per distinct requested session.

    market_as_of bounds the index; each context's market_as_of is its target close.
    knowledge_as_of bounds source acquisition, not a claim of historical availability.
    computed_at is caller-supplied actual materialization time, as in ATS-1.
    Observation identity excludes later bars and wall-clock acquisition/computation;
    source content revisions and calculation provenance remain identity-bearing.
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
    expected_last = calendar.last_completed_session(dataset.requested_as_of)
    if dataset.expected_last_session != expected_last:
        raise ValueError('Source anchor differs from calendar cutoff.')
    for bar in dataset.bars:
        session = calendar.session_on_or_after(bar.session_date)
        if (session.date != bar.session_date or session.closes_at > dataset.requested_as_of
                or session.closes_at > dataset.retrieved_at):
            raise ValueError('Source contains non-session or uncompleted/unacquired bars.')
    observed = {bar.session_date for bar in dataset.bars}
    expected_missing = (tuple(day for day in calendar.completed_sessions(
        dataset.data_window_start, dataset.requested_as_of) if day not in observed)
        if dataset.bars else ())
    if dataset.missing_sessions != expected_missing:
        raise ValueError('Source missing-session inventory differs from exchange calendar.')
    targets = tuple(target_sessions)
    if any(type(day) is not date for day in targets):
        raise ValueError('Exact target session dates required.')
    contexts = []
    for target in sorted(set(targets)):
        session = calendar.session_on_or_after(target)
        if session.date != target or session.closes_at > market:
            raise ValueError('Target must be a completed XNYS session within the market cutoff.')
        close = aware_utc(session.closes_at)
        prefix_bars = tuple(bar for bar in dataset.bars if bar.session_date <= target)
        missing = tuple(day for day in dataset.missing_sessions if day <= target)
        prefix = replace(dataset, bars=prefix_bars, requested_as_of=close,
                         expected_last_session=target, missing_sessions=missing)
        if target not in observed:
            # No feature at a missing target may masquerade as the latest observed
            # session. This is absence handling, not a replacement formula.
            reason = ('UNAVAILABLE_DUE_TO_MISSING_SESSIONS' if prefix_bars
                      else 'UNAVAILABLE_DUE_TO_HISTORY')
            values = (FeatureValue('atr_14', None, 'price', reason),
                      FeatureValue('volume_ratio_20', None, 'ratio', reason))
        else:
            snapshot = build_technical_feature_snapshot(prefix)
            values = (snapshot.feature('atr_14'), snapshot.feature('volume_ratio_20'))
        content = [[str(b.session_date), *[float(v).hex() for v in
                    (b.open, b.high, b.low, b.close)], b.volume] for b in prefix_bars]
        source_id = 'FEATURE_PREFIX:' + _identity([dataset.symbol, dataset.timeframe,
            dataset.provider, dataset.provider_function, dataset.adjustment_mode,
            dataset.methodology_version, dataset.exchange_calendar, dataset.calendar_version,
            dataset.exchange_timezone, str(target), content, [str(day) for day in missing]])
        observations = []
        for value in values:
            key = [dataset.symbol, dataset.timeframe, dataset.exchange_calendar,
                   FEATURE_VERSION, str(target), value.name]
            logical = 'FEATURE_OBSERVATION:' + _identity(key)
            state = 'FEATURE_OBSERVATION_STATE:' + _identity([key, source_id, PARAMETERS,
                value.value, value.unit, value.unavailable_reason])
            observations.append(HistoricalFeatureObservation(value, logical, state))
        contexts.append(HistoricalFeatureContext(dataset.symbol, target, close, knowledge,
            dataset.retrieved_at, computed, computed, source_id, *observations))
    return HistoricalFeatureIndex(dataset, market, knowledge, computed, tuple(contexts))
