"""Decision builders and opt-in saving; no recommendation evaluation."""
from copy import deepcopy
from dataclasses import fields
import uuid

from src.decision_store import DecisionStore
from src.models import DecisionRecord, DecisionOutcome, InvestmentAnalysis


def build_decision_record(
    analysis: InvestmentAnalysis,
    decision_timestamp: str,
    investment_horizon: str | None = None,
    decision_id: str | None = None,
) -> DecisionRecord:
    """Copy a validated analysis without retaining mutable aliases.

    IDs use normalized ticker, caller timestamp verbatim, and eight UUID4 hex
    characters. The caller may supply a compact UTC timestamp for that ID style;
    no timestamp parsing, timezone assumption, or current-clock lookup occurs.
    The format is deterministic; the UUID suffix supplies uniqueness entropy.
    """
    if decision_id is not None:
        if not isinstance(decision_id, str) or not decision_id.strip():
            raise ValueError("decision_id must be non-empty.")
        decision_id = decision_id.strip()
    else:
        decision_id = f"{analysis.ticker.strip().upper()}-{decision_timestamp}-{uuid.uuid4().hex[:8]}"
    if investment_horizon is not None:
        if not isinstance(investment_horizon, str):
            raise ValueError("investment_horizon must be a string or None.")
        investment_horizon = investment_horizon.strip() or None
    return DecisionRecord(
        **deepcopy({field.name: getattr(analysis, field.name) for field in fields(InvestmentAnalysis)}),
        decision_id=decision_id,
        decision_timestamp=decision_timestamp,
        investment_horizon=investment_horizon,
    )


def build_decision_outcome(
    decision_id: str,
    evaluation_timestamp: str,
    evaluation_horizon: str,
    stock_start_price: float | None,
    stock_end_price: float | None,
    benchmark_ticker: str | None = None,
    benchmark_start_price: float | None = None,
    benchmark_end_price: float | None = None,
) -> DecisionOutcome:
    """Calculate unannualized decimal returns from supplied, validated prices only."""
    outcome = DecisionOutcome(
        decision_id, evaluation_timestamp, evaluation_horizon,
        stock_start_price, stock_end_price, None, benchmark_ticker,
        benchmark_start_price, benchmark_end_price, None, None,
    )
    if stock_start_price is not None and stock_start_price > 0 and stock_end_price is not None:
        outcome.stock_return = stock_end_price / stock_start_price - 1
    if benchmark_start_price is not None and benchmark_start_price > 0 and benchmark_end_price is not None:
        outcome.benchmark_return = benchmark_end_price / benchmark_start_price - 1
    if outcome.stock_return is not None and outcome.benchmark_return is not None:
        outcome.excess_return = outcome.stock_return - outcome.benchmark_return
    return outcome


def save_analysis_decision(
    analysis: InvestmentAnalysis,
    store: DecisionStore,
    decision_timestamp: str,
    investment_horizon: str | None = None,
    decision_id: str | None = None,
) -> DecisionRecord:
    """Save an already validated analysis; initialization is the caller's responsibility."""
    record = build_decision_record(analysis, decision_timestamp, investment_horizon, decision_id)
    store.save_decision(record)
    return record
