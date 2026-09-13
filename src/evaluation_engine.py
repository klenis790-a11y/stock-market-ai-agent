"""Pure evaluation of explicitly selected observation revisions; no persistence or IO.

Unlike legacy DecisionOutcome (which allows a zero end price), Step 3 requires
strictly positive prices. Calendar eligibility remains unverified: arithmetic
completeness is not certification of the declared market-session horizon.
"""
from dataclasses import dataclass, replace
from math import isfinite
from statistics import mean, median

from src.models import DecisionRecord
from src.evaluation_models import EvaluationEnrollment, EvaluationObservation


@dataclass(frozen=True)
class EvaluationResult:
    enrollment: EvaluationEnrollment
    recommendation: str
    confidence_score: float
    decision_timestamp: str
    reference_observation_id: str | None
    endpoint_observation_id: str | None
    reference_at: str | None
    endpoint_at: str | None
    reference_recorded_at: str | None
    endpoint_recorded_at: str | None
    stock_return: float | None
    benchmark_return: float | None
    excess_return: float | None
    completeness: str
    limitations: tuple[str, ...]
    horizon_resolution_verified: bool = False


def _observation(item, enrollment, point):
    if item is None:
        return None
    if not isinstance(item, EvaluationObservation):
        raise ValueError('EvaluationObservation required.')
    prices = {}
    for key, symbol in (('stock', enrollment.ticker), ('benchmark', enrollment.methodology.benchmark_symbol)):
        price = getattr(item, key)
        if price is not None:
            price = replace(price)  # Revalidate even if a frozen object was bypassed.
            if price.price <= 0:
                raise ValueError('Evaluation prices must be strictly positive.')
            if (price.symbol != symbol or price.currency != enrollment.methodology.currency
                    or price.adjustment_policy != enrollment.methodology.adjustment_policy):
                raise ValueError('Price provenance differs from enrollment.')
        prices[key] = price
    item = replace(item, **prices)
    if item.enrollment_id != enrollment.enrollment_id or item.point != point:
        raise ValueError('Observation identity/role differs from enrollment.')
    if item.recorded_at < enrollment.enrolled_at:
        raise ValueError('Observation recording precedes enrollment.')
    if item.effective_at <= enrollment.enrolled_at:
        raise ValueError('Evaluation window must follow enrollment.')
    return item


def _return(start, end):
    if start is None or end is None:
        return None
    if start.price_type != end.price_type:
        raise ValueError('Price types must match across the window.')
    value = end.price / start.price - 1
    if not isfinite(value):
        raise ValueError('Calculated return is non-finite.')
    return value


def evaluate_observations(enrollment, reference, endpoint, decision):
    """Pin the two supplied revisions; never select a favorable/latest revision.

    No horizon override is accepted. Existing fields cannot prove session/calendar
    resolution, so that limitation is explicit in every transient result.
    """
    if not isinstance(enrollment, EvaluationEnrollment) or not isinstance(decision, DecisionRecord):
        raise ValueError('Enrollment and preserved DecisionRecord required.')
    enrollment = replace(enrollment, horizon=replace(enrollment.horizon), methodology=replace(enrollment.methodology))
    replace(decision)  # Validate without mutating legacy metadata.
    if (decision.decision_id, decision.ticker) != (enrollment.decision_id, enrollment.ticker):
        raise ValueError('Decision does not match enrollment.')
    return _evaluate_source_observations(enrollment, reference, endpoint,
        source_label=decision.recommendation, confidence=decision.confidence_score,
        source_timestamp=decision.decision_timestamp)


def _evaluate_source_observations(enrollment, reference, endpoint, *, source_label, confidence, source_timestamp):
    """Shared arithmetic kernel; caller validates its preserved source contract.

    EvaluationResult.recommendation is a source label, not a fundamental decision
    conversion, when this kernel is used by the technical evaluation adapter.
    """
    reference = _observation(reference, enrollment, 'reference')
    endpoint = _observation(endpoint, enrollment, 'endpoint')
    if reference and endpoint and reference.effective_at >= endpoint.effective_at:
        raise ValueError('Endpoint must follow reference observation.')
    stock = _return(reference.stock if reference else None, endpoint.stock if endpoint else None)
    benchmark = _return(reference.benchmark if reference else None, endpoint.benchmark if endpoint else None)
    if reference and endpoint and stock is not None and benchmark is not None:
        if reference.stock.price_type != reference.benchmark.price_type:
            raise ValueError('Stock and benchmark price types must match.')
    excess = stock - benchmark if stock is not None and benchmark is not None else None
    if excess is not None and not isfinite(excess):
        raise ValueError('Calculated excess return is non-finite.')
    limitations = ['Declared horizon retained; market-calendar/window resolution is not verified.']
    if enrollment.time_provenance == 'legacy_time_unverified':
        limitations.append('Original decision availability time is unverified.')
    if stock is None:
        limitations.append('Stock reference or endpoint is unavailable.')
    if benchmark is None:
        limitations.append('Benchmark reference or endpoint is unavailable.')
    for item in (reference, endpoint):
        if item and item.missing_reason:
            limitations.append(item.missing_reason)
    return EvaluationResult(enrollment, source_label, confidence,
        source_timestamp, reference.observation_id if reference else None,
        endpoint.observation_id if endpoint else None, reference.effective_at if reference else None,
        endpoint.effective_at if endpoint else None, reference.recorded_at if reference else None,
        endpoint.recorded_at if endpoint else None, stock, benchmark, excess,
        'full' if excess is not None else 'stock_only' if stock is not None else 'not_evaluable',
        tuple(limitations))


def aggregate_evaluations(results):
    """One result per enrollment, homogeneous methodology/horizon/time provenance.

    Benchmarks use stock-evaluable pairs, unlike the legacy UI's independent
    benchmark mean. Counts describe supplied results, not all enrolled decisions.
    No statistical significance or categorical recommendation score is inferred.
    """
    results = list(results)
    if any(not isinstance(r, EvaluationResult) for r in results):
        raise ValueError('EvaluationResult required.')
    if len({r.enrollment.enrollment_id for r in results}) != len(results):
        raise ValueError('Duplicate enrollment results cannot be aggregated.')
    cohorts = {(r.enrollment.horizon, r.enrollment.methodology.digest, r.enrollment.time_provenance) for r in results}
    if len(cohorts) > 1:
        raise ValueError('Aggregate only one horizon/methodology/time-provenance cohort.')
    return _aggregate_return_metrics(results, len({r.enrollment.decision_id for r in results}))


def _aggregate_return_metrics(results, unique_source_count):
    """Shared denominators/arithmetic; source adapters enforce identities/cohorts."""
    for r in results:
        for value in (r.stock_return, r.benchmark_return, r.excess_return):
            if value is not None and (type(value) not in (int, float) or not isfinite(value)):
                raise ValueError('Invalid return in result.')
        expected = r.stock_return - r.benchmark_return if r.stock_return is not None and r.benchmark_return is not None else None
        if r.excess_return != expected:
            raise ValueError('Inconsistent excess return.')
    stock = [r.stock_return for r in results if r.stock_return is not None]
    paired = [r for r in results if r.stock_return is not None and r.benchmark_return is not None]
    benchmark = [r.benchmark_return for r in paired]
    excess = [r.excess_return for r in paired]
    return dict(result_count=len(results), evaluated_count=len(stock), unevaluated_count=len(results)-len(stock),
        benchmark_count=len(paired), unique_decision_count=unique_source_count,
        average_stock_return=mean(stock) if stock else None, median_stock_return=median(stock) if stock else None,
        paired_average_stock_return=mean([r.stock_return for r in paired]) if paired else None,
        average_benchmark_return=mean(benchmark) if benchmark else None,
        average_excess_return=mean(excess) if excess else None, median_excess_return=median(excess) if excess else None,
        positive_return_count=sum(x > 0 for x in stock) if stock else None,
        positive_return_rate=sum(x > 0 for x in stock)/len(stock) if stock else None,
        benchmark_outperformance_count=sum(x > 0 for x in excess) if excess else None,
        benchmark_outperformance_rate=sum(x > 0 for x in excess)/len(excess) if excess else None)
