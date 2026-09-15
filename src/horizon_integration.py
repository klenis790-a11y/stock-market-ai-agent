"""Pure V0.8A admission, approved freshness and readiness. No AI synthesis.

Provenance attestations are caller-owned facts, not proof inferred from text. The
context applies versioned policies and blocks unresolved applicability/risk facts.
Lower-level policy functions are independently testable.
"""
from dataclasses import asdict, dataclass, replace, field
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
    freshness_policy_version: str = 'technical-freshness-v1'
    technical_session_age: int | None = None
    fundamental_provenance_status: str = 'LEGACY_UNKNOWN'
    fundamental_applicability: str = 'UNKNOWN'
    technical_applicability: str = 'UNKNOWN'
    readiness: str = 'BLOCKED'
    integration_policy_version: str = 'horizon-readiness-v1'
    fundamental_policy_version: str = 'fundamental-provenance-v1'
    calendar_version: str = USMarketCalendar.version
    # Retain immutable originals, including the existing prospective capability.
    # These are policy inputs, never a replacement for recomputation.
    fundamental_source: object = field(default=None, repr=False)
    technical_source: TechnicalSignalRecord | None = field(default=None, repr=False)
    integration_run_id: str | None = None


@dataclass(frozen=True)
class TechnicalFreshness:
    state: Freshness
    completed_session_age: int | None
    reason: str
    policy_version: str = 'technical-freshness-v1'
    calendar_version: str = USMarketCalendar.version


def technical_freshness(record, integration_as_of, *, calendar=None):
    """Completed sessions strictly after the preserved signal session, never days."""
    try:
        instant = aware_utc(integration_as_of)
        checked = admit_technical(record, record.symbol, instant, calendar=calendar)
        if checked.status != Admission.ADMITTED:
            return TechnicalFreshness(Freshness.UNKNOWN, None, 'RESEARCH_NOT_ADMITTED')
        limits = {'SHORT_TERM_1_TO_5_SESSIONS': (2, 5), 'SWING_1_TO_4_WEEKS': (10, 20)}
        fresh, last = limits[checked.native_horizon]
        session = date.fromisoformat(checked.latest_completed_session)
        cal = calendar or USMarketCalendar()
        age = sum(day > session for day in cal.completed_sessions(session, instant))
        state = Freshness.FRESH if age <= fresh else Freshness.AGING if age <= last else Freshness.STALE
        return TechnicalFreshness(state, age, 'COMPLETED_XNYS_SESSION_AGE')
    except (ValueError, TypeError, KeyError, AttributeError):
        return TechnicalFreshness(Freshness.UNKNOWN, None, 'INVALID_TIME_SESSION_OR_HORIZON')


def _admit_current(artifact, ticker, instant):
    from src.fundamental_provenance import CurrentFundamentalArtifact
    if not isinstance(artifact, CurrentFundamentalArtifact):
        return admit_fundamental(artifact, ticker, instant), None
    try:
        p = artifact.verified()
        a, packet = artifact.analysis, artifact.evidence
        if a['ticker'] != ticker or packet['ticker'] != ticker:
            return _reject('FUNDAMENTAL', 'TICKER_MISMATCH'), None
        direction = normalize_fundamental(a['recommendation'])
        if utc_timestamp(p['available_at']) > _timestamp(instant):
            return _reject('FUNDAMENTAL', 'INVALID_TEMPORAL_ORDER'), None
        return ResearchAdmission('FUNDAMENTAL', Admission.ADMITTED, (), artifact.analysis_json,
            artifact.evidence_json, a['recommendation'], p['native_horizon'], a['confidence_score'],
            p['research_as_of'], p['available_at'], direction=direction,
            metadata_json=artifact.provenance_json), p
    except (ValueError, TypeError, KeyError, AttributeError):
        return _reject('FUNDAMENTAL', 'INVALID_PROVENANCE'), None


def build_integration_context(ticker, decision_horizon, integration_as_of, *,
                              fundamental=None, technical=None, calendar=None, integration_run_id=None):
    ticker = normalize_symbol(ticker)
    horizon = DecisionHorizon(decision_horizon)
    instant = aware_utc(integration_as_of)
    authority = primary_authority(horizon)
    f, provenance = _admit_current(fundamental, ticker, instant)
    t = admit_technical(technical, ticker, instant, calendar=calendar)
    if 'TICKER_MISMATCH' in f.reasons or 'TICKER_MISMATCH' in t.reasons:
        raise ValueError('Research ticker mismatch.')
    tf = technical_freshness(technical, instant, calendar=calendar)
    # Bind to this run and its exact completed assessment point, not reusable ID alone.
    current = bool(provenance and integration_run_id and provenance['run_id'] == integration_run_id
                   and utc_timestamp(provenance['available_at']) == _timestamp(instant))
    ff = Freshness.FRESH if current else Freshness.UNKNOWN
    f_role = ('PRIMARY' if horizon in (DecisionHorizon.MEDIUM, DecisionHorizon.LONG)
              else 'CONTEXT_ONLY' if horizon == DecisionHorizon.SHORT else 'SECONDARY')
    t_role = ('PRIMARY' if horizon in (DecisionHorizon.SHORT, DecisionHorizon.SWING)
              else 'CONTEXT_ONLY' if horizon == DecisionHorizon.LONG else 'SECONDARY')
    if f.status != Admission.ADMITTED:
        f_role = 'NOT_APPLICABLE'
    elif f_role == 'PRIMARY' and f.native_horizon != horizon.value:
        f_role = 'UNKNOWN'  # No invented parsing of legacy free-form native horizons.
    if t.status != Admission.ADMITTED:
        t_role = 'NOT_APPLICABLE'
    elif t_role == 'PRIMARY' and t.native_horizon != {
            DecisionHorizon.SHORT: 'SHORT_TERM_1_TO_5_SESSIONS',
            DecisionHorizon.SWING: 'SWING_1_TO_4_WEEKS'}[horizon]:
        t_role = 'UNKNOWN'
    technical_primary = authority == Authority.TECHNICAL_PRIMARY
    primary, secondary = (t, f) if technical_primary else (f, t)
    primary_state = tf.state if technical_primary else ff
    role = t_role if technical_primary else f_role
    blocking = [f'{primary.namespace}:{reason}' for reason in primary.reasons]
    if primary_state not in (Freshness.FRESH, Freshness.AGING):
        blocking.append('PRIMARY_RESEARCH_' + primary_state.value)
    if role != 'PRIMARY':
        blocking.append('PRIMARY_APPLICABILITY_UNRESOLVED')
    nonblocking, warnings = [], ['PROVIDER_PUBLICATION_VINTAGE_UNVERIFIED',
                                'FUNDAMENTAL_MATERIAL_EVENT_COVERAGE_UNKNOWN']
    for item in (f, t):
        if item.status == Admission.ADMITTED:
            source = item.source
            missing = (source['analysis']['missing_evidence_ids'] if item.namespace == 'TECHNICAL'
                       else source['missing_data'])
            nonblocking.extend(item.namespace + ':' + value for value in missing)
    # The approved policy does not define which omitted secondary risk checks are safe.
    # Do not waive unknown requirements to manufacture a ready primary-only view.
    secondary_state = ff if technical_primary else tf.state
    if secondary.status != Admission.ADMITTED or secondary_state not in (Freshness.FRESH, Freshness.AGING):
        blocking.append('SECONDARY_REQUIRED_RISK_COVERAGE_UNRESOLVED')
        warnings.extend(secondary.namespace + ':' + r for r in secondary.reasons)
    if tf.state == Freshness.AGING:
        warnings.append('TECHNICAL_AGING_CAUTION')
    # Existing validity is not a structured assertion of cross-horizon risk scope.
    # Keep unresolved material-risk relevance blocked rather than parsing prose.
    if f.status == Admission.ADMITTED:
        fs = f.source
        if fs['major_risks'] or fs['bear_case']:
            blocking.append('FUNDAMENTAL_RISK_APPLICABILITY_UNRESOLVED')
        if not technical_primary and fs['missing_data']:
            blocking.append('PRIMARY_MISSING_DATA_SEVERITY_UNRESOLVED')
    if t.status == Admission.ADMITTED:
        ts = t.source['analysis']
        if ts['risk_notes'] or ts['conflicting_evidence_ids']:
            blocking.append('TECHNICAL_RISK_APPLICABILITY_UNRESOLVED')
    # Native scope facts resolve different scopes; natural-language risk conflicts
    # remain unclassified. No semantic inference from prose is performed here.
    classification = ConflictAssessment(Conflict.INSUFFICIENT_EVIDENCE, 'POLICY_GATES_BLOCKED')
    if not blocking:
        if not provenance or f.native_horizon not in ('MEDIUM', 'LONG'):
            blocking.append('FUNDAMENTAL_SCOPE_UNRESOLVED')
        else:
            classification = classify_conflict(horizon, f.direction, t.recommendation,
                scope=ScopeRelation.DISTINCT, evidence_ready=True)
    return IntegrationContext(ticker, horizon, _timestamp(instant), f, t, authority,
        None if blocking else authority, ff, tf.state, classification, tuple(blocking),
        tuple(nonblocking), tuple(warnings), technical_session_age=tf.completed_session_age,
        fundamental_provenance_status='CURRENT_SYSTEM_TRUSTED' if provenance else 'LEGACY_UNKNOWN',
        fundamental_applicability=f_role, technical_applicability=t_role,
        readiness='BLOCKED' if blocking else 'SYNTHESIS_READY',
        fundamental_source=_retained_fundamental(fundamental),
        technical_source=technical if isinstance(technical, TechnicalSignalRecord) else None,
        integration_run_id=integration_run_id)


def _retained_fundamental(source):
    from src.fundamental_provenance import CurrentFundamentalArtifact
    # Legacy envelopes contain mutable DecisionRecord data. Their detached snapshot
    # remains in admission metadata, but cannot qualify current readiness.
    return source if isinstance(source, CurrentFundamentalArtifact) else None


class SynthesisReadinessError(ValueError):
    """Safe deterministic reasons, not source prose or provider payloads."""
    def __init__(self, reasons):
        self.reasons = tuple(dict.fromkeys(reasons))
        super().__init__('Integration context is not trusted synthesis-ready: ' + ', '.join(self.reasons))


def require_synthesis_ready(context):
    """Recompute current policy from retained immutable sources before downstream use.

    Frozen/ready flags are not credentials. No caller-supplied calendar is accepted
    at this boundary. Return the recomputed context, not the caller's assertions.
    The existing Fundamental origin capability is revalidated by the normal builder.
    """
    if not isinstance(context, IntegrationContext):
        raise SynthesisReadinessError(('INVALID_CONTEXT_TYPE',))
    original_reasons = context.blocking_missing_data
    if not isinstance(original_reasons, tuple) or any(not isinstance(r, str) for r in original_reasons):
        raise SynthesisReadinessError(('INVALID_BLOCKING_REASONS',))
    try:
        from src.fundamental_provenance import CurrentFundamentalArtifact
        if (not isinstance(context.fundamental_source, CurrentFundamentalArtifact) or
                not isinstance(context.technical_source, TechnicalSignalRecord)):
            raise SynthesisReadinessError((*original_reasons, 'REQUIRED_POLICY_SOURCES_UNAVAILABLE'))
        derived = build_integration_context(context.ticker, context.decision_horizon,
            datetime.fromisoformat(utc_timestamp(context.integration_as_of).replace('Z', '+00:00')),
            fundamental=context.fundamental_source, technical=context.technical_source,
            integration_run_id=context.integration_run_id)
    except SynthesisReadinessError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise SynthesisReadinessError((*original_reasons, 'INVALID_POLICY_INPUTS')) from None
    reasons = list(derived.blocking_missing_data)
    if derived != context:
        reasons.append('CONTEXT_DIFFERS_FROM_POLICY_RECOMPUTATION')
    if derived.readiness != 'SYNTHESIS_READY' or derived.blocking_missing_data:
        reasons.append('POLICY_CONTEXT_BLOCKED')
    if reasons:
        raise SynthesisReadinessError((*original_reasons, *reasons))
    return derived
