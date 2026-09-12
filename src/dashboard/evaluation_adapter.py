"""Explicit application boundary; read views never initialize storage or retrieve prices."""
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from collections import defaultdict
from src.evaluation_models import ACTIVE_HORIZONS, EvaluationEnrollment, utc_timestamp
from src.evaluation_store import EvaluationStore
from src.evaluation_engine import evaluate_observations, aggregate_evaluations
from src.evaluation_collection import collect_evaluation_observations
from src.observation_resolution import (resolve_observation_target, adjusted_close_methodology,
                                        SUPPORTED_MARKET)


def open_store(path, write=False):
    if not isinstance(path, str) or not path.strip() or not Path(path.strip()).expanduser().is_file():
        raise ValueError('Choose an existing decision database.')
    return EvaluationStore(str(Path(path.strip()).expanduser()), read_only=not write)


def enroll_decision(path, decision_id, horizon, as_of):
    if horizon not in ACTIVE_HORIZONS:
        raise ValueError('Choose an approved horizon.')
    store = open_store(path, write=True)
    decision = store.get_decision(decision_id)
    if decision is None:
        raise ValueError('Preserved decision unavailable.')
    method = adjusted_close_methodology()
    for item in store.get_enrollments_for_decision(decision_id):
        if item.horizon == horizon and item.methodology == method:
            return item
    # Save-time/start-time legacy timestamps do not prove analysis completion.
    item = EvaluationEnrollment(str(uuid4()), decision_id, decision.ticker,
        as_of.isoformat(), horizon, method)
    store.initialize()  # Only this explicit write action initializes additive tables.
    store.save_enrollment(item)
    return item


@dataclass(frozen=True)
class EvaluationView:
    enrollment: EvaluationEnrollment
    target: object
    observations: tuple
    result: object
    can_collect: bool


def decision_evaluations(path, decision_id, as_of, *, market_verified=False):
    store = open_store(path)
    decision = store.get_decision(decision_id)
    if decision is None:
        raise ValueError('Preserved decision unavailable.')
    views = []
    for item in store.get_enrollments_for_decision(decision_id):
        target = resolve_observation_target(item, as_of, market=SUPPORTED_MARKET if market_verified else '')
        observations = tuple(store.get_observations_for_enrollment(item.enrollment_id))
        supported = item.methodology == adjusted_close_methodology()
        result = None
        if supported and target.eligibility == 'ELIGIBLE' and len(observations) == 2:
            points = {o.point: o for o in observations}
            if set(points) == {'reference', 'endpoint'} and all(
                points[p].effective_at == utc_timestamp(session.closes_at.isoformat())
                and points[p].supersedes_id is None
                for p, session in (('reference', target.reference), ('endpoint', target.target))):
                result = evaluate_observations(item, points['reference'], points['endpoint'], decision)
        views.append(EvaluationView(item, target, observations, result,
            supported and target.eligibility == 'ELIGIBLE' and not observations))
    return views


def collect(path, enrollment_id, as_of, *, market_verified=False):
    if not market_verified:
        raise ValueError('Confirm supported market scope first.')
    store = open_store(path, write=True)
    item = store.get_enrollment(enrollment_id)
    if item is None:
        raise ValueError('Enrollment unavailable.')
    return collect_evaluation_observations(store, item, as_of, market=SUPPORTED_MARKET)


def performance_evaluations(path, ticker, as_of, *, market_verified=False):
    store = open_store(path)
    views = [view for decision in store.get_decisions_for_ticker(ticker.strip().upper())
             for view in decision_evaluations(path, decision.decision_id, as_of,
                                              market_verified=market_verified)]
    cohorts = defaultdict(list)
    for view in views:
        if view.result is not None:
            item = view.enrollment
            cohorts[(item.horizon, item.methodology.digest, item.time_provenance)].append(view.result)
    return views, [(results[0].enrollment, aggregate_evaluations(results)) for results in cohorts.values()]
