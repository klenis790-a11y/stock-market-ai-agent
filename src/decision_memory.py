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
