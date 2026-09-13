"""Technical source adapter for V0.6 calendars, factual collection and arithmetic.

No fundamental DecisionRecord is constructed. Record creation is a conservative
existence anchor, explicitly distinct from unknown analyst generation time.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, date
from hashlib import sha256
import re

from src.evaluation_models import (EvaluationHorizon, EvaluationMethodology,
                                   canonical_json, utc_timestamp, text)
from src.evaluation_engine import EvaluationResult, _evaluate_source_observations, _aggregate_return_metrics
from src.evaluation_collection import _collect_target_observations, now_utc
from src.observation_resolution import (adjusted_close_methodology, _resolve_close_target,
    PRICE_POLICY_VERSION, SUPPORTED_MARKET)
from src.market_calendar import USMarketCalendar, aware_utc
from src.technical_signal_store import TechnicalSignalRecord

EVALUATION_VERSION = 'technical-signal-evaluation-v1'
HORIZON_MAP_VERSION = 'technical-signal-horizon-map-v1'
TECHNICAL_RESOLUTION_VERSION = 'xnys-session-target-v1'
HORIZON_MAP = (('SHORT_TERM_1_TO_5_SESSIONS', 5), ('SWING_1_TO_4_WEEKS', 20))


def mapped_horizon(analysis_horizon):
    for name, count in HORIZON_MAP:
        if name == analysis_horizon:
            return EvaluationHorizon(count, 'trading_sessions')
    raise ValueError('Unsupported technical analysis horizon.')


def technical_methodology():
    return replace(adjusted_close_methodology(), version=EVALUATION_VERSION,
        baseline_rule='first regular session close strictly after preserved record creation',
        endpoint_rule='Nth XNYS session close strictly after reference session; technical-signal-horizon-map-v1')


def record_digest(record):
    return sha256(canonical_json(asdict(record)).encode()).hexdigest()


@dataclass(frozen=True)
class TechnicalEvaluationEnrollment:
    enrollment_id: str
    signal_record_id: str
    ticker: str
    enrolled_at: str
    record_created_at: str
    signal_digest: str
    analysis_horizon: str
    horizon: EvaluationHorizon
    methodology: EvaluationMethodology
    market: str
    horizon_mapping_version: str = HORIZON_MAP_VERSION
    reference_policy_version: str = PRICE_POLICY_VERSION
    resolution_version: str = TECHNICAL_RESOLUTION_VERSION
    time_provenance: str = 'preserved_record_creation'

    def __post_init__(self):
        for key in ('enrollment_id', 'signal_record_id', 'ticker', 'signal_digest'):
            text(getattr(self, key), key)
        if not re.fullmatch(r'[A-Z0-9]+(?:[.:-][A-Z0-9]+)*', self.ticker):
            raise ValueError('Invalid normalized symbol.')
        if self.horizon != mapped_horizon(self.analysis_horizon) or self.methodology != technical_methodology():
            raise ValueError('Unsupported technical evaluation contract.')
        if (self.horizon_mapping_version, self.reference_policy_version, self.resolution_version,
                self.time_provenance, self.market) != (HORIZON_MAP_VERSION, PRICE_POLICY_VERSION,
                TECHNICAL_RESOLUTION_VERSION, 'preserved_record_creation', SUPPORTED_MARKET):
            raise ValueError('Unsupported technical evaluation provenance or market.')
        for key in ('enrolled_at', 'record_created_at'):
            object.__setattr__(self, key, utc_timestamp(getattr(self, key)))
        if self.enrolled_at < self.record_created_at:
            raise ValueError('Enrollment cannot precede record creation.')


def _validate_source(record, enrollment=None):
    if not isinstance(record, TechnicalSignalRecord):
        raise ValueError('Preserved technical signal record required.')
    replace(record)  # Revalidate stored shape without rerunning evidence or analysis.
    signal = record.signal
    p = signal['provenance']
    if (p['market_data_methodology'], p['feature_methodology'], signal['evidence_catalog_version'],
        signal['analyst_methodology_version'], p['adjustment_mode'], p['timeframe'], p['calendar'],
        p['exchange_timezone'], p['calendar_version']) != (
        'daily-ohlcv-normalization-v1', 'technical-features-v1', 'technical-evidence-v1',
        'technical-analyst-v1', 'RAW', '1d', 'XNYS', 'America/New_York', USMarketCalendar.version):
        raise ValueError('Unsupported historical technical methodology.')
    as_of = aware_utc(datetime.fromisoformat(p['requested_as_of'].replace('Z', '+00:00')))
    retrieved = utc_timestamp(p['retrieved_at'])
    if utc_timestamp(as_of.isoformat()) > record.created_at or retrieved > record.created_at:
        raise ValueError('Source timestamps cannot follow preserved record creation.')
    calendar = USMarketCalendar()
    if not p['latest_completed_session'] or calendar.last_completed_session(as_of) != date.fromisoformat(p['latest_completed_session']):
        raise ValueError('Latest completed session is missing, stale or inconsistent.')
    latest_close = calendar.session_on_or_after(date.fromisoformat(p['latest_completed_session'])).closes_at
    if retrieved < utc_timestamp(latest_close.isoformat()):
        raise ValueError('Provider retrieval predates the latest completed session.')
    if enrollment is not None:
        replace(enrollment)
        if (record.record_id, record.symbol, record.created_at, signal['horizon'], record_digest(record)) != (
            enrollment.signal_record_id, enrollment.ticker, enrollment.record_created_at,
            enrollment.analysis_horizon, enrollment.signal_digest):
            raise ValueError('Enrollment does not match the preserved signal/evidence.')
    return signal


def resolve_technical_target(enrollment, as_of):
    if not isinstance(enrollment, TechnicalEvaluationEnrollment):
        raise ValueError('TechnicalEvaluationEnrollment required.')
    replace(enrollment)
    target = _resolve_close_target(enrollment, as_of, enrollment.record_created_at, market=enrollment.market)
    return replace(target, resolution_version=enrollment.resolution_version)


def prepare_technical_enrollment(record, enrolled_at, *, market):
    """Pure preparation. Caller supplies trustworthy UTC application event time."""
    signal = _validate_source(record)
    enrolled_at = utc_timestamp(aware_utc(enrolled_at).isoformat())
    enrollment_id = sha256(canonical_json([record.record_id, EVALUATION_VERSION]).encode()).hexdigest()
    enrollment = TechnicalEvaluationEnrollment(enrollment_id, record.record_id, record.symbol,
        enrolled_at, record.created_at, record_digest(record), signal['horizon'],
        mapped_horizon(signal['horizon']), technical_methodology(), market)
    target = resolve_technical_target(enrollment, datetime.fromisoformat(enrolled_at.replace('Z', '+00:00')))
    # V0.6's pre-reference guard is stronger than merely rejecting completed targets.
    if target.eligibility != 'NOT_YET_ELIGIBLE':
        raise ValueError('Prospective enrollment must precede the reference close and target.')
    return enrollment


def enroll_technical_signal(store, record_id, enrolled_at, *, market):
    record = store.get_signal_record(record_id)
    if record is None:
        raise ValueError('Technical signal record does not exist.')
    enrollment = prepare_technical_enrollment(record, enrolled_at, market=market)
    store.save_enrollment(enrollment)
    return enrollment


def collect_technical_observations(store, enrollment_id, as_of, *, clock=now_utc):
    enrollment = store.get_enrollment(enrollment_id)
    if enrollment is None:
        raise ValueError('Technical enrollment does not exist.')
    _validate_source(store.get_signal_record(enrollment.signal_record_id), enrollment)
    target = resolve_technical_target(enrollment, as_of)
    return _collect_target_observations(store, enrollment, target, clock=clock)


@dataclass(frozen=True)
class TechnicalSignalEvaluationResult:
    """Composition: original signal metadata plus V0.6 provider-adjusted arithmetic.

    The wrapped result's recommendation label is the original technical direction;
    no fundamental recommendation or DecisionRecord is created.
    """
    evaluation: EvaluationResult

    def __post_init__(self):
        if not isinstance(self.evaluation, EvaluationResult) or not isinstance(self.evaluation.enrollment, TechnicalEvaluationEnrollment):
            raise ValueError('Technical enrollment and calculated evaluation required.')
        if self.evaluation.recommendation not in ('BULLISH', 'NEUTRAL', 'BEARISH'):
            raise ValueError('Unknown technical signal direction.')
        if (type(self.evaluation.confidence_score) is not int or not 0 <= self.evaluation.confidence_score <= 100
                or self.evaluation.decision_timestamp != self.evaluation.enrollment.record_created_at):
            raise ValueError('Invalid original technical metadata.')

    @property
    def enrollment(self):
        return self.evaluation.enrollment

    @property
    def signal(self):
        return self.evaluation.recommendation

    @property
    def directional_success(self):
        value = self.evaluation.stock_return
        if value is None or self.signal == 'NEUTRAL':
            return None
        return value > 0 if self.signal == 'BULLISH' else value < 0

    @property
    def benchmark_outperformance(self):
        value = self.evaluation.excess_return
        return value > 0 if value is not None else None


def evaluate_technical_signal(record, enrollment, reference=None, endpoint=None):
    signal = _validate_source(record, enrollment)
    # Resolution is independent of as_of; this only checks expected timestamps.
    target = resolve_technical_target(enrollment, datetime.fromisoformat(enrollment.enrolled_at.replace('Z', '+00:00')))
    if target.eligibility != 'NOT_YET_ELIGIBLE':
        raise ValueError('Enrollment is not prospective.')
    for item, session in ((reference, target.reference), (endpoint, target.target)):
        if item is not None:
            if item.supersedes_id or item.effective_at != utc_timestamp(session.closes_at.isoformat()):
                raise ValueError('Observation does not match the immutable resolved window.')
            for price in (item.stock, item.benchmark):
                if price is not None and (price.source != 'Alpha Vantage / TIME_SERIES_DAILY_ADJUSTED'
                        or price.price_type != '5. adjusted close / alpha-vantage-adjusted-close-v1'):
                    raise ValueError('Observation provider/price policy mismatch.')
    result = _evaluate_source_observations(enrollment, reference, endpoint,
        source_label=signal['analysis']['signal'], confidence=signal['analysis']['confidence'],
        source_timestamp=record.created_at)
    result = replace(result, horizon_resolution_verified=True,
        limitations=tuple(x for x in result.limitations if not x.startswith('Declared horizon retained;')) + (
            'Record creation is an existence anchor, not verified analyst generation time.',))
    return TechnicalSignalEvaluationResult(result)


def get_technical_result(store, enrollment_id):
    enrollment = store.get_enrollment(enrollment_id)
    if enrollment is None:
        raise ValueError('Technical enrollment does not exist.')
    observations = store.get_observations_for_enrollment(enrollment_id)
    by_point = {item.point: item for item in observations}
    if len(by_point) != len(observations):
        raise ValueError('Duplicate observation points.')
    return evaluate_technical_signal(store.get_signal_record(enrollment.signal_record_id), enrollment,
                                    by_point.get('reference'), by_point.get('endpoint'))


def aggregate_technical_evaluations(results):
    """One supplied result per enrollment; missing results must also be supplied.

    Pooled metrics describe predeclared endpoints, not one uniform holding horizon.
    Mandatory horizon breakdowns keep different observation lengths visible.
    """
    results = tuple(results)
    if any(not isinstance(r, TechnicalSignalEvaluationResult) or r.signal not in ('BULLISH','NEUTRAL','BEARISH') for r in results):
        raise ValueError('Technical evaluation results required.')
    if len({r.enrollment.enrollment_id for r in results}) != len(results):
        raise ValueError('Duplicate technical enrollment results.')
    for r in results:
        replace(r.enrollment)
    def metrics(items):
        base = _aggregate_return_metrics([r.evaluation for r in items], len(items))
        base['unique_signal_count'] = base.pop('unique_decision_count')
        directional = [r.directional_success for r in items if r.directional_success is not None]
        base.update(total_enrolled=len(items), directional_count=len(directional),
            directional_success_count=sum(directional),
            directional_success_rate=sum(directional)/len(directional) if directional else None)
        return base
    output = metrics(results)
    output['by_signal'] = {name: metrics([r for r in results if r.signal == name]) for name in ('BULLISH','BEARISH','NEUTRAL')}
    output['by_analysis_horizon'] = {name: metrics([r for r in results if r.enrollment.analysis_horizon == name]) for name,_ in HORIZON_MAP}
    output['pooled_horizons'] = len({r.enrollment.analysis_horizon for r in results}) > 1
    output['sample_warning'] = 'Descriptive sample counts only; correlated signals and small samples do not establish predictive quality.'
    return output
