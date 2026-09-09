"""Decision-time transformations only; no persistence or outcome evaluation."""
from copy import deepcopy
from dataclasses import fields
import uuid

from src.models import DecisionRecord, InvestmentAnalysis


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
