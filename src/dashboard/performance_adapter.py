"""Descriptive outcome aggregates only; no market retrieval or historical rewriting."""
from math import isfinite
from src.dashboard.history_adapter import load_history
from src.ui_contracts import PerformancePageData, UISectionAvailability


def valid_return(value):
    return type(value) in (int, float) and isfinite(value)


def summarize(rows):
    values = {key: [row[key] for row in rows if valid_return(row[key])]
              for key in ('stock_return', 'benchmark_return', 'excess_return')}
    summary = {}
    for key, observations in values.items():
        summary[key + '_count'] = len(observations)
        summary['average_' + key] = sum(observations) / len(observations) if observations else None
    for label, key in (('positive_return', 'stock_return'), ('benchmark_outperformance', 'excess_return')):
        observations = values[key]
        count = sum(value > 0 for value in observations)
        summary[label + '_count'] = count if observations else None
        summary[label + '_rate'] = count / len(observations) if observations else None
    return summary


def confidence_bucket(score):
    for upper, label in ((50, '0–49'), (60, '50–59'), (70, '60–69'),
                         (80, '70–79'), (90, '80–89')):
        if score < upper:
            return label
    return '90–100'


def load_performance(database_path, ticker):
    """Ticker-scoped V0.3 read path. Each outcome horizon is one observation.

    Missing/non-finite returns are excluded independently per metric, never zeroed.
    Buckets use continuous boundaries [0,50), [50,60), etc. Returns remain decimals.
    No recommendation is treated as a trade; positive underlying stock returns
    do not establish recommendation correctness (particularly Trim/Avoid).
    """
    if not database_path or not database_path.strip():
        return PerformancePageData()
    history = load_history(database_path, ticker)
    if not history.availability['history'].data_available:
        return PerformancePageData(availability=history.availability['history'])
    parents = {item.decision_id: item for item in history.decisions}
    rows = []
    for outcome in history.outcomes:
        parent = parents.get(outcome.decision_id)
        if parent is None:
            continue
        returns = {key: getattr(outcome, key) if valid_return(getattr(outcome, key)) else None
                   for key in ('stock_return', 'benchmark_return', 'excess_return')}
        if not any(value is not None for value in returns.values()):
            continue
        rows.append(dict(decision_id=parent.decision_id, ticker=parent.ticker,
                         decision_timestamp=parent.decision_timestamp, recommendation=parent.recommendation,
                         confidence=parent.confidence_score, confidence_bucket=confidence_bucket(parent.confidence_score),
                         horizon=outcome.evaluation_horizon, evaluation_timestamp=outcome.evaluation_timestamp,
                         benchmark_ticker=outcome.benchmark_ticker, **returns))
    if not rows:
        return PerformancePageData(availability=UISectionAvailability(
            True, False, 'No evaluated decision outcomes are available yet.'))
    def groups(key):
        return {value: summarize([row for row in rows if row[key] == value])
                for value in sorted({row[key] for row in rows})}
    return PerformancePageData(availability=UISectionAvailability(True, True), rows=rows,
        summary=summarize(rows), recommendations=groups('recommendation'),
        horizons=groups('horizon'), confidence_groups=groups('confidence_bucket'))
