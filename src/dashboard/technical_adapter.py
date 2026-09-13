"""Explicit technical application actions; render helpers never retrieve or initialize."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from contextlib import closing
import logging
import sqlite3
from functools import wraps

from src.historical_market_data import retrieve_historical_ohlcv
from src.technical_features import build_technical_feature_snapshot
from src.technical_evidence import build_technical_research_snapshot, build_technical_evidence_catalog
from src.technical_analyst import analyze_technical_snapshot, HORIZONS
from src.market_data_models import normalize_symbol
from src.market_calendar import aware_utc
from src.observation_resolution import SUPPORTED_MARKET
from src.technical_signal_store import TechnicalSignalStore, create_technical_signal_record
from src.technical_evaluation_store import TechnicalEvaluationStore
from src.technical_evaluation import (prepare_technical_enrollment, enroll_technical_signal,
    resolve_technical_target, collect_technical_observations, get_technical_result,
    aggregate_technical_evaluations)

HORIZON_LABELS = dict(zip(HORIZONS, ('1–5 trading sessions', '1–4 weeks')))


class TechnicalActionError(RuntimeError):
    """Only fixed application messages may reach the browser."""


def now():
    return datetime.now(timezone.utc)


def safe_action(stage):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except TechnicalActionError:
                raise
            except Exception as error:
                logging.getLogger(__name__).error('Technical workflow failed stage=%s exception=%s detail=withheld', stage, type(error).__name__)
                raise TechnicalActionError(f'Technical {stage.lower().replace("_", " ")} unavailable. Check inputs, source and server configuration; no automatic retry occurs.') from None
        return wrapped
    return decorate


@dataclass(frozen=True)
class TechnicalRun:
    snapshot: object
    catalog: object
    signal: object


@safe_action('INPUT')
def run_technical_research(ticker, horizon, as_of, *, market_verified):
    ticker = normalize_symbol(ticker)
    as_of = aware_utc(as_of)
    if horizon not in HORIZONS or not market_verified:
        raise ValueError('Approved horizon and confirmed market required.')
    data = safe_action('MARKET_DATA')(retrieve_historical_ohlcv)(ticker, as_of, market=SUPPORTED_MARKET)
    features = safe_action('FEATURES')(build_technical_feature_snapshot)(data)
    snapshot = safe_action('EVIDENCE')(build_technical_research_snapshot)(data, features)
    catalog = safe_action('EVIDENCE')(build_technical_evidence_catalog)(snapshot)
    signal = safe_action('TECHNICAL_ANALYST')(analyze_technical_snapshot)(snapshot, catalog, horizon)
    return TechnicalRun(snapshot, catalog, signal)


def local_path(path, *, existing=False):
    if not isinstance(path,str) or not path.strip() or '://' in path or path.strip()==':memory:':
        raise ValueError('Explicit local database path required.')
    resolved = Path(path.strip()).expanduser()
    if existing and not resolved.is_file():
        raise ValueError('Existing source required.')
    return str(resolved)


@safe_action('SAVE')
def prepare_save(run, created_at):
    return create_technical_signal_record(run.signal, run.catalog, created_at=created_at)


@safe_action('SAVE')
def save_signal(record, path):
    store = TechnicalSignalStore(local_path(path))
    store.initialize()  # Explicit save only.
    prior = store.get_technical_signal(record.record_id)
    if prior is not None:
        if prior != record:
            raise ValueError('Record identity collision.')
        return prior
    try:
        store.save_technical_signal(record)
    except sqlite3.IntegrityError:
        if store.get_technical_signal(record.record_id) != record:
            raise
    return record


@safe_action('HISTORY')
def load_history(path, ticker):
    store = TechnicalSignalStore(local_path(path,existing=True),read_only=True)
    ticker = normalize_symbol(ticker)
    with closing(store._connect()) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='technical_signals' AND type='table'").fetchone():
            return []
    return store.list_technical_signals(ticker)


def evidence_rows(packet, ids=None):
    items = packet['items']
    if ids is not None:
        by_id = {i['evidence_id']:i for i in items}
        items = [by_id[ref] for ref in ids]
    return [{'ID':i['evidence_id'], 'Category':i['category'], 'Evidence':i['label'],
             'Value':'Unavailable' if i['value'] is None else str(i['value']),
             'Unit':i['unit'], 'Classification':i['classification'].replace('_',' '),
             'Availability':i['unavailable_reason'] or 'Available'} for i in items]


@safe_action('EVALUATION')
def evaluation_view(path, record, as_of, *, market_verified):
    store = TechnicalEvaluationStore(local_path(path,existing=True),read_only=True)
    entries = store.get_enrollments_for_signal(record.record_id)
    if not entries:
        can_enroll=False
        reason='Confirm US equity/ETF market scope to inspect prospective eligibility.'
        if market_verified:
            try:
                prepare_technical_enrollment(record,as_of,market=SUPPORTED_MARKET)
                can_enroll=True;reason='Eligible for explicit prospective enrollment.'
            except ValueError:
                reason='This signal cannot be prospectively enrolled under technical-signal-evaluation-v1. Its timing or methodology is unsupported, or the reference close has passed.'
        return dict(can_enroll=can_enroll, can_collect=False, reason=reason, enrollment=None)
    if len(entries)!=1:
        raise ValueError('Multiple enrollments require review.')
    item=entries[0]
    target=resolve_technical_target(item,as_of)
    observations=tuple(store.get_observations_for_enrollment(item.enrollment_id))
    result=get_technical_result(store,item.enrollment_id)
    return dict(can_enroll=False,can_collect=market_verified and target.eligibility=='ELIGIBLE' and not observations,
        reason=target.reason, enrollment=item,target=target,observations=observations,result=result)


@safe_action('ENROLLMENT')
def enroll(path, record_id, as_of, *, market_verified):
    if not market_verified:raise ValueError('Market confirmation required.')
    store=TechnicalEvaluationStore(local_path(path,existing=True))
    existing=store.get_enrollments_for_signal(record_id)
    if existing:return existing[0]
    record=store.get_signal_record(record_id)
    prepare_technical_enrollment(record,as_of,market=SUPPORTED_MARKET)  # Gate before schema write.
    store.initialize()
    return enroll_technical_signal(store,record_id,as_of,market=SUPPORTED_MARKET)


@safe_action('COLLECTION')
def collect(path, enrollment_id, as_of, *, market_verified):
    if not market_verified:raise ValueError('Market confirmation required.')
    return collect_technical_observations(TechnicalEvaluationStore(local_path(path,existing=True)), enrollment_id,as_of)


@safe_action('EVALUATION')
def summary(path, records):
    store=TechnicalEvaluationStore(local_path(path,existing=True),read_only=True)
    results=[get_technical_result(store,e.enrollment_id) for record in records
             for e in store.get_enrollments_for_signal(record.record_id)]
    return aggregate_technical_evaluations(results)


def result_rows(result):
    e=result.evaluation
    rows=[{'Metric':name,'Value':'Unavailable' if value is None else f'{value:.2%}'} for name,value in (
        ('Stock provider-adjusted return',e.stock_return),('Benchmark provider-adjusted return',e.benchmark_return),('Excess return',e.excess_return))]
    rows.append({'Metric':'Directional success','Value':
        'Not defined under technical-signal-evaluation-v1' if result.signal=='NEUTRAL'
        else 'Unavailable' if result.directional_success is None else str(result.directional_success)})
    rows.append({'Metric':'Benchmark outperformance','Value':'Unavailable' if result.benchmark_outperformance is None else str(result.benchmark_outperformance)})
    return rows


def signal_data(run):
    return asdict(run.signal)
