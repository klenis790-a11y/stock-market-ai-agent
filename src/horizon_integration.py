"""Pure V0.8A admission/context foundation. No freshness thresholds or AI synthesis.

Provenance attestations are caller-owned facts, not proof inferred from text. The
current context builder has no operational freshness/applicability policy and thus
cannot authorize synthesis. Lower-level policy functions are independently testable.
"""
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from enum import StrEnum
import json

from src.evaluation_models import canonical_json, utc_timestamp
from src.evidence import resolve_evidence_id
from src.market_calendar import USMarketCalendar, aware_utc
from src.market_data_models import normalize_symbol
from src.models import DecisionRecord
from src.technical_signal_store import TechnicalSignalRecord
from src.technical_features import PARAMETERS

CONTEXT_VERSION = 'horizon-synthesis-context-v1'
NORMALIZATION_VERSION = 'fundamental-direction-normalization-v1'
ADMISSION_VERSION = 'horizon-research-admission-v1'
CONFLICT_VERSION = 'horizon-conflict-foundation-v1'


class DecisionHorizon(StrEnum):
    SHORT = 'SHORT'
    SWING = 'SWING'
    MEDIUM = 'MEDIUM'
    LONG = 'LONG'


class Authority(StrEnum):
    TECHNICAL_PRIMARY = 'TECHNICAL_PRIMARY'
    FUNDAMENTAL_PRIMARY = 'FUNDAMENTAL_PRIMARY'


class FundamentalDirection(StrEnum):
    FAVORABLE = 'FAVORABLE'
    NEUTRAL = 'NEUTRAL'
    UNFAVORABLE = 'UNFAVORABLE'


class Admission(StrEnum):
    ADMITTED = 'ADMITTED'
    REJECTED = 'REJECTED'


class Freshness(StrEnum):
    FRESH = 'FRESH'
    AGING = 'AGING'
    STALE = 'STALE'
    UNKNOWN = 'UNKNOWN'


class Conflict(StrEnum):
    ALIGNED = 'ALIGNED'
    TIMING_CONFLICT = 'TIMING_CONFLICT'
    THESIS_CONFLICT = 'THESIS_CONFLICT'
    HORIZON_DIVERGENCE = 'HORIZON_DIVERGENCE'
    INSUFFICIENT_EVIDENCE = 'INSUFFICIENT_EVIDENCE'


class ScopeRelation(StrEnum):
    UNKNOWN = 'UNKNOWN'
    COMPATIBLE = 'COMPATIBLE'
    DISTINCT = 'DISTINCT'
    OPPOSING_SAME_SCOPE = 'OPPOSING_SAME_SCOPE'


def primary_authority(horizon):
    horizon = DecisionHorizon(horizon)
    return (Authority.TECHNICAL_PRIMARY if horizon in (DecisionHorizon.SHORT, DecisionHorizon.SWING)
            else Authority.FUNDAMENTAL_PRIMARY)


def normalize_fundamental(recommendation):
    # Exact repository vocabulary; no case conversion of preserved conclusions.
    mapping = {'Buy': FundamentalDirection.FAVORABLE, 'Accumulate': FundamentalDirection.FAVORABLE,
               'Hold': FundamentalDirection.NEUTRAL, 'Trim': FundamentalDirection.UNFAVORABLE,
               'Avoid': FundamentalDirection.UNFAVORABLE}
    if not isinstance(recommendation, str) or recommendation not in mapping:
        raise ValueError('Unsupported Fundamental recommendation.')
    return mapping[recommendation]


@dataclass(frozen=True)
class FundamentalArtifact:
    """Source envelope, not a new recommendation.

    record/evidence are copied into immutable JSON at admission. Explicit as-of and
    available-at must have factual provenance; origin_reference identifies the
    caller's verification that this report did not consume portfolio context.
    Missing attestation is rejected, never inferred from portfolio_assessment.
    evidence_json holds the ORIGINAL package plus its ORIGINAL catalog under
    'catalog'. IDs are resolved, never rebuilt. No methodology is invented for
    legacy Fundamental records that expose none.
    """
    record: DecisionRecord
    evidence_json: str
    research_as_of: datetime | None = None
    available_at: datetime | None = None
    origin_reference: str | None = None
    timing_reference: str | None = None


@dataclass(frozen=True)
class ResearchAdmission:
    namespace: str
    status: Admission
    reasons: tuple[str, ...]
    source_json: str | None
    evidence_json: str | None
    recommendation: str | None = None
    native_horizon: str | None = None
    confidence: float | int | None = None
    research_as_of: str | None = None
    available_at: str | None = None
    latest_completed_session: str | None = None
    direction: FundamentalDirection | None = None
    metadata_json: str = '{}'

    @property
    def source(self):
        return json.loads(self.source_json) if self.source_json is not None else None

    @property
    def evidence(self):
        return json.loads(self.evidence_json) if self.evidence_json is not None else None


@dataclass(frozen=True)
class Participation:
    freshness: Freshness
    usable: bool
    reasons: tuple[str, ...]


def participation(admission, freshness):
    """State behavior only; does not calculate freshness or repair admission."""
    status, state = Admission(admission), Freshness(freshness)
    if status == Admission.REJECTED:
        return Participation(state, False, ('REJECTED_ARTIFACT',))
    if state in (Freshness.STALE, Freshness.UNKNOWN):
        return Participation(state, False, (f'FRESHNESS_{state.value}',))
    return Participation(state, True, ('AGING_CAUTION',) if state == Freshness.AGING else ())


@dataclass(frozen=True)
class ConflictAssessment:
    classification: Conflict
    reason: str
    version: str = CONFLICT_VERSION


def classify_conflict(horizon, fundamental_direction, technical_signal, *,
                      scope=ScopeRelation.UNKNOWN, evidence_ready=False):
    """Conditional rules on validated policy facts, not a recommendation matrix.

    Scope is the output of a FUTURE applicability policy, never an LLM judgment.
    The context builder currently cannot establish evidence_ready.
    """
    authority = primary_authority(horizon)
    direction = FundamentalDirection(fundamental_direction)
    if technical_signal not in ('BULLISH', 'NEUTRAL', 'BEARISH'):
        raise ValueError('Unsupported Technical signal.')
    relation = ScopeRelation(scope)
    if type(evidence_ready) is not bool:
        raise ValueError('Explicit readiness boolean required.')
    if not evidence_ready or relation == ScopeRelation.UNKNOWN:
        return ConflictAssessment(Conflict.INSUFFICIENT_EVIDENCE, 'UNRESOLVED_RELIABILITY_OR_SCOPE')
    if relation == ScopeRelation.OPPOSING_SAME_SCOPE:
        return ConflictAssessment(Conflict.THESIS_CONFLICT, 'VERIFIED_SAME_SCOPE_OPPOSITION')
    opposing = ((direction == FundamentalDirection.FAVORABLE and technical_signal == 'BEARISH') or
                (direction == FundamentalDirection.UNFAVORABLE and technical_signal == 'BULLISH'))
    if opposing and authority == Authority.FUNDAMENTAL_PRIMARY and direction == FundamentalDirection.FAVORABLE:
        return ConflictAssessment(Conflict.TIMING_CONFLICT, 'SECONDARY_TECHNICAL_TIMING_OPPOSITION')
    if opposing and relation == ScopeRelation.DISTINCT:
        return ConflictAssessment(Conflict.HORIZON_DIVERGENCE, 'VERIFIED_DISTINCT_SCOPE_OPPOSITION')
    if opposing:
        return ConflictAssessment(Conflict.INSUFFICIENT_EVIDENCE, 'OPPOSITION_SCOPE_AMBIGUOUS')
    return ConflictAssessment(Conflict.ALIGNED, 'COMPATIBLE_ADMITTED_CONCLUSIONS')


def _timestamp(value):
    return utc_timestamp(aware_utc(value).isoformat())


def _present(value):
    return isinstance(value, str) and bool(value.strip())


def _reject(namespace, reason):
    return ResearchAdmission(namespace, Admission.REJECTED, (reason,), None, None)


def admit_fundamental(artifact, ticker, integration_as_of):
    ticker, cutoff = normalize_symbol(ticker), _timestamp(integration_as_of)
    if artifact is None:
        return _reject('FUNDAMENTAL', 'MISSING_RESEARCH')
    if not isinstance(artifact, FundamentalArtifact) or not isinstance(artifact.record, DecisionRecord):
        return _reject('FUNDAMENTAL', 'INVALID_RESEARCH_TYPE')
    record = artifact.record
    reasons = []
    if record.ticker != ticker:
        reasons.append('TICKER_MISMATCH')
    direction = None
    try:
        direction = normalize_fundamental(record.recommendation)
    except ValueError:
        reasons.append('INVALID_RECOMMENDATION')
    try:
        replace(record)
        if not _present(record.investment_horizon):
            reasons.append('MISSING_NATIVE_HORIZON')
    except (ValueError, TypeError):
        reasons.append('INVALID_RESEARCH_CONTRACT')
    if not _present(artifact.origin_reference):
        reasons.append('UNVERIFIED_PORTFOLIO_INDEPENDENCE')
    if not _present(artifact.timing_reference):
        reasons.append('MISSING_TIMING_PROVENANCE')
    research_time = available = None
    try:
        research_time, available = _timestamp(artifact.research_as_of), _timestamp(artifact.available_at)
        saved = utc_timestamp(record.decision_timestamp)
        if not research_time <= available <= saved <= cutoff:
            reasons.append('INVALID_TEMPORAL_ORDER')
    except (ValueError, TypeError):
        reasons.append('INVALID_TIMESTAMP')
    source_json = packet_json = None
    try:
        source_json = canonical_json(asdict(record))
        packet = json.loads(artifact.evidence_json)
        packet_json = canonical_json(packet)
        if packet['ticker'] != ticker:
            reasons.append('TICKER_MISMATCH')
        catalog = packet['catalog']
        if not isinstance(catalog, list) or not catalog:
            raise ValueError('Missing catalog.')
        ids = [item['evidence_id'] for item in catalog]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate evidence.')
        for eid in ids:
            resolve_evidence_id(eid, catalog, packet)
        for name in ('bull_case', 'bear_case', 'supporting_evidence', 'major_risks',
                     'thesis_invalidation_conditions', 'scenarios'):
            values = getattr(record, name)
            if not isinstance(values, list):
                raise ValueError('Invalid statements.')
            for statement in values:
                if not _present(statement.text) or not isinstance(statement.evidence_refs, list) or not statement.evidence_refs:
                    raise ValueError('Invalid statement.')
                for eid in statement.evidence_refs:
                    resolve_evidence_id(eid, catalog, packet)
        for name in ('reasoning_summary', 'fundamental_assessment', 'valuation_assessment', 'earnings_assessment'):
            if not isinstance(getattr(record, name), str):
                raise ValueError('Invalid research text.')
        for eid, review in record.material_evidence_review.items():
            resolve_evidence_id(eid, catalog, packet)
            if not isinstance(review.observation, str) or not isinstance(review.thesis_relevance, str):
                raise ValueError('Invalid evidence review.')
        if 'generated_at' in packet and (available is None or utc_timestamp(packet['generated_at']) > available):
            reasons.append('INVALID_TEMPORAL_ORDER')
        if not isinstance(record.missing_data, list) or any(not _present(v) for v in record.missing_data):
            raise ValueError('Invalid missing data.')
    except (ValueError, TypeError, KeyError, AttributeError):
        reasons.append('INVALID_EVIDENCE_OR_SOURCE')
    return ResearchAdmission('FUNDAMENTAL', Admission.REJECTED if reasons else Admission.ADMITTED,
        tuple(dict.fromkeys(reasons)), source_json, packet_json, record.recommendation,
        record.investment_horizon, record.confidence_score, research_time, available,
        direction=direction, metadata_json=canonical_json({
            'origin_reference': artifact.origin_reference, 'timing_reference': artifact.timing_reference,
            'source_methodology': None, 'limitation': 'Legacy contract exposes no methodology identifier'}))


def admit_technical(record, ticker, integration_as_of, *, calendar=None):
    ticker, cutoff = normalize_symbol(ticker), _timestamp(integration_as_of)
    if record is None:
        return _reject('TECHNICAL', 'MISSING_RESEARCH')
    if not isinstance(record, TechnicalSignalRecord):
        return _reject('TECHNICAL', 'INVALID_RESEARCH_TYPE')
    try:
        replace(record)  # Existing immutable historical shape/citation validation.
        signal, packet = record.signal, record.evidence_packet
    except (ValueError, TypeError):
        return _reject('TECHNICAL', 'INVALID_RESEARCH_CONTRACT')
    p, a = signal['provenance'], signal['analysis']
    reasons = []
    if p['symbol'] != ticker:
        reasons.append('TICKER_MISMATCH')
    expected = {'market_data_methodology': 'daily-ohlcv-normalization-v1',
                'feature_methodology': 'technical-features-v1', 'adjustment_mode': 'RAW',
                'timeframe': '1d', 'calendar': 'XNYS', 'exchange_timezone': 'America/New_York',
                'provider': 'Alpha Vantage', 'provider_function': 'TIME_SERIES_DAILY',
                'calendar_version': USMarketCalendar.version}
    if (any(p.get(k) != v for k, v in expected.items()) or
            signal['evidence_catalog_version'] != 'technical-evidence-v1' or
            signal['analyst_methodology_version'] != 'technical-analyst-v1' or
            p.get('indicator_parameters') != json.loads(canonical_json(PARAMETERS))):
        reasons.append('UNSUPPORTED_METHODOLOGY')
    research_time = None
    try:
        research_time = utc_timestamp(p['requested_as_of'])
        retrieved = utc_timestamp(p['retrieved_at'])
        saved = utc_timestamp(record.created_at)
        if research_time > saved or retrieved > saved or saved > cutoff:
            reasons.append('INVALID_TEMPORAL_ORDER')
        local_calendar = calendar or USMarketCalendar()
        latest = date.fromisoformat(p['latest_completed_session'])
        research_dt = datetime.fromisoformat(research_time.replace('Z', '+00:00'))
        if (date.fromisoformat(p['first_included_session']) > latest or
                date.fromisoformat(p['expected_last_session']) != latest or
                local_calendar.last_completed_session(research_dt) != latest or
                utc_timestamp(local_calendar.session_on_or_after(latest).closes_at.isoformat()) > retrieved):
            reasons.append('INVALID_COMPLETED_SESSION')
    except (ValueError, TypeError, KeyError):
        reasons.append('INVALID_TIMESTAMP_OR_SESSION')
    return ResearchAdmission('TECHNICAL', Admission.REJECTED if reasons else Admission.ADMITTED,
        tuple(reasons), record.signal_json, record.evidence_json, a['signal'], signal['horizon'],
        a['confidence'], research_time, record.created_at, p['latest_completed_session'],
        metadata_json=canonical_json({'record_id': record.record_id, 'record_version': record.record_version,
                                      'availability_basis': 'preserved record creation, not generation time'}))


@dataclass(frozen=True)
class IntegrationContext:
    ticker: str
    decision_horizon: DecisionHorizon
    integration_as_of: str
    fundamental: ResearchAdmission
    technical: ResearchAdmission
    primary_authority: Authority
    usable_primary_authority: Authority | None
    fundamental_freshness: Freshness
    technical_freshness: Freshness
    conflict: ConflictAssessment
    blocking_missing_data: tuple[str, ...]
    non_blocking_missing_data: tuple[str, ...]
    warnings: tuple[str, ...]
    methodology_version: str = CONTEXT_VERSION
    admission_version: str = ADMISSION_VERSION
    normalization_version: str = NORMALIZATION_VERSION
    freshness_policy_version: None = None


def build_integration_context(ticker, decision_horizon, integration_as_of, *,
                              fundamental=None, technical=None, calendar=None):
    ticker = normalize_symbol(ticker)
    horizon = DecisionHorizon(decision_horizon)
    instant = aware_utc(integration_as_of)
    authority = primary_authority(horizon)
    f = admit_fundamental(fundamental, ticker, instant)
    t = admit_technical(technical, ticker, instant, calendar=calendar)
    if 'TICKER_MISMATCH' in f.reasons or 'TICKER_MISMATCH' in t.reasons:
        raise ValueError('Research ticker mismatch.')
    primary, secondary = (t, f) if authority == Authority.TECHNICAL_PRIMARY else (f, t)
    blocking = [f'{primary.namespace}:{reason}' for reason in primary.reasons]
    blocking.extend(('PRIMARY_FRESHNESS_POLICY_UNAVAILABLE', 'PRIMARY_APPLICABILITY_POLICY_UNAVAILABLE',
                     'MISSING_DATA_SEVERITY_POLICY_UNAVAILABLE'))
    nonblocking = []
    warnings = [f'{secondary.namespace}:{reason}' for reason in secondary.reasons]
    for item in (f, t):
        if item.status == Admission.ADMITTED:
            source = item.source
            if item.namespace == 'TECHNICAL':
                # Missing optional features remain visible; no feature-count gate.
                missing = tuple(f'TECHNICAL:{eid}' for eid in source['analysis']['missing_evidence_ids'])
                if authority == Authority.FUNDAMENTAL_PRIMARY:
                    nonblocking.extend(missing)
                elif missing:
                    warnings.extend(missing)
                    warnings.append('TECHNICAL_PRIMARY_MISSING_DATA_SEVERITY_UNRESOLVED')
            elif source['missing_data']:
                warnings.append('FUNDAMENTAL_MISSING_DATA_SEVERITY_UNRESOLVED')
    warnings.extend(('SECONDARY_RISK_REQUIREMENTS_UNRESOLVED',
                     'PROVIDER_PUBLICATION_VINTAGE_UNVERIFIED', 'CALLER_PROVENANCE_REQUIRES_TRUST'))
    return IntegrationContext(ticker, horizon, _timestamp(instant), f, t, authority, None,
        Freshness.UNKNOWN, Freshness.UNKNOWN,
        ConflictAssessment(Conflict.INSUFFICIENT_EVIDENCE, 'FRESHNESS_AND_APPLICABILITY_POLICY_UNAVAILABLE'),
        tuple(blocking), tuple(nonblocking), tuple(warnings))
