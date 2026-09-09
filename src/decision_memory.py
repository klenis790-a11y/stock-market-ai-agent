"""Ticker/recency history only, with no evaluation or AI integration.

Current verified evidence must remain primary; memory is contextual history and
must never replace it. Outcomes remain distinct from decision-time beliefs.
"""
from copy import deepcopy

from src.decision_store import DecisionStore
from src.models import DecisionMemoryContext, DecisionMemoryItem


def build_decision_memory_context(
    store: DecisionStore, ticker: str, limit: int = 5,
) -> DecisionMemoryContext:
    """Reuse store ordering (newest lexical timestamp first) and outcome ordering.

    Callers must retain the store's consistent sortable timestamp convention.
    No inference, relevance scoring, or outcome-based ranking occurs.
    """
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError('A non-empty ticker is required.')
    if type(limit) is not int or limit < 0:
        raise ValueError('limit must be a non-negative integer.')
    ticker = ticker.strip().upper()
    context = DecisionMemoryContext(ticker=ticker, prior_decisions=[])
    if limit == 0:
        return context
    for record in store.get_decisions_for_ticker(ticker)[:limit]:
        context.prior_decisions.append(deepcopy(DecisionMemoryItem(
            decision_id=record.decision_id, ticker=record.ticker,
            decision_timestamp=record.decision_timestamp, recommendation=record.recommendation,
            confidence_score=record.confidence_score, investment_horizon=record.investment_horizon,
            reasoning_summary=record.reasoning_summary, major_risks=record.major_risks,
            thesis_invalidation_conditions=record.thesis_invalidation_conditions,
            scenarios=record.scenarios, missing_data=record.missing_data,
            outcomes=store.get_outcomes_for_decision(record.decision_id),
        )))
    return context


def serialize_decision_memory(context: DecisionMemoryContext) -> dict:
    """Compact historical input; omit old evidence IDs to prevent catalog collisions.

    Statement text remains historical context, not current citable evidence.
    Decision IDs identify history records only. No source object is mutated.
    """
    from dataclasses import asdict

    return {
        'ticker': context.ticker,
        'prior_decisions': [{
            'decision_id': item.decision_id,
            'ticker': item.ticker,
            'decision_timestamp': item.decision_timestamp,
            'recommendation': item.recommendation,
            'confidence_score': item.confidence_score,
            'investment_horizon': item.investment_horizon,
            'reasoning_summary': item.reasoning_summary,
            'major_risks': [statement.text for statement in item.major_risks],
            'thesis_invalidation_conditions': [statement.text for statement in item.thesis_invalidation_conditions],
            'scenarios': [statement.text for statement in item.scenarios],
            'missing_data': list(item.missing_data),
            'outcomes': [asdict(outcome) for outcome in item.outcomes],
        } for item in context.prior_decisions],
    }
