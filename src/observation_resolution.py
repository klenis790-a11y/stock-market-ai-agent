"""Derived observation windows only. No prices, persistence, or wall clock.

A future reference close is an evaluation anchor, never decision-time evidence.
Existing v1 enrollments are not reinterpreted under the v2 close policy.
"""
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from src.evaluation_models import EvaluationEnrollment, EvaluationMethodology, ACTIVE_HORIZONS
from src.market_calendar import USMarketCalendar, MarketSession, aware_utc

PRICE_POLICY_VERSION = 'next-completed-regular-close-v1'
RESOLUTION_VERSION = 'xnys-calendar-target-v1'
SUPPORTED_MARKET = 'US_EQUITY_ETF_XNYS'


def close_methodology() -> EvaluationMethodology:
    return EvaluationMethodology(version='fundamental-price-v2',
        price_policy_version=PRICE_POLICY_VERSION,
        calendar_id=USMarketCalendar.calendar_id, calendar_version=USMarketCalendar.version,
        baseline_rule='first regular session close strictly after captured analysis completion')


@dataclass(frozen=True)
class ObservationTarget:
    enrollment: EvaluationEnrollment
    decision_at: datetime | None
    reference: MarketSession | None
    nominal_target_date: date | None
    target: MarketSession | None
    eligibility: str
    reason: str | None
    reference_available: bool = False
    exchange_timezone: str = 'America/New_York'
    resolution_version: str = RESOLUTION_VERSION
    price_type: str = 'regular-session split-consistent close excluding cash dividends'
    # One window applies to both stock and the enrolled benchmark.


def resolve_observation_target(enrollment: EvaluationEnrollment, as_of: datetime, *,
                               market: str, calendar: USMarketCalendar | None = None
                               ) -> ObservationTarget:
    """Market scope must be explicitly verified by the caller, never guessed from ticker.
    Late enrollment is unresolved, not moved forward to a more convenient reference.
    """
    as_of = aware_utc(as_of)
    if not isinstance(enrollment, EvaluationEnrollment):
        raise ValueError('EvaluationEnrollment is required.')
    def unavailable(status, reason):
        return ObservationTarget(enrollment, None, None, None, None, status, reason)
    if market != SUPPORTED_MARKET:
        return unavailable('UNSUPPORTED', 'Only verified US equities/ETFs under XNYS are supported.')
    if enrollment.methodology != close_methodology() or enrollment.horizon not in ACTIVE_HORIZONS:
        return unavailable('UNSUPPORTED', 'Unsupported methodology, calendar version or active horizon.')
    if enrollment.time_provenance != 'captured_analysis_completion' or not enrollment.decision_available_at:
        return unavailable('UNRESOLVABLE', 'Verified analysis completion time was not preserved.')
    decision_at = datetime.fromisoformat(enrollment.decision_available_at.replace('Z', '+00:00'))
    enrolled_at = datetime.fromisoformat(enrollment.enrolled_at.replace('Z', '+00:00'))
    calendar = calendar or USMarketCalendar()
    if (calendar.calendar_id, calendar.version) != (enrollment.methodology.calendar_id,
                                                    enrollment.methodology.calendar_version):
        return unavailable('UNSUPPORTED', 'Calendar provenance mismatch.')
    try:
        reference = calendar.session_on_or_after(decision_at.astimezone(calendar.timezone).date())
        if reference.closes_at <= decision_at:
            reference = calendar.session_on_or_after(reference.date + timedelta(days=1))
        nominal = reference.date + timedelta(days=enrollment.horizon.length)
        target = calendar.session_on_or_after(nominal)
    except (ValueError, OverflowError):
        return unavailable('UNRESOLVABLE', 'Timestamp is outside supported calendar coverage.')
    if target.closes_at <= reference.closes_at:
        raise ValueError('Target must follow the reference session.')
    if enrolled_at >= reference.closes_at:
        status, reason = 'UNRESOLVABLE', 'Enrollment occurred too late for the declared prospective reference.'
    else:
        status = 'ELIGIBLE' if as_of >= target.closes_at else 'NOT_YET_ELIGIBLE'
        reason = None
    return ObservationTarget(enrollment, decision_at, reference, nominal, target, status, reason,
                             as_of >= reference.closes_at)
