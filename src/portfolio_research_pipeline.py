from src.decision_memory import build_decision_memory_context
from src.decision_history import save_analysis_decision
from src.decision_store import DecisionStore
"""Portfolio-aware research orchestration using the existing evidence and analysis layers."""
from collections.abc import Callable

from src.analysis import analyze_investment
from src.models import DecisionMemoryContext, InvestmentAnalysis, PortfolioInput, PortfolioAnalysisContext
from src.portfolio_context import build_portfolio_analysis_context
from src.portfolio_data import build_live_portfolio_snapshot
from src.portfolio_risk import assess_portfolio_risk
from src.research_pipeline import build_stock_evidence


def run_portfolio_aware_research(
    target_ticker: str, portfolio_input: PortfolioInput,
    *, decision_store: DecisionStore | None = None,
    decision_timestamp: str | None = None, investment_horizon: str | None = None,
    memory_context: DecisionMemoryContext | None = None,
    use_decision_memory: bool = False, memory_limit: int = 5,
    persist_decision: bool = True,
    on_context: Callable[[PortfolioAnalysisContext], None] | None = None,
) -> InvestmentAnalysis:
    """Assemble portfolio and stock evidence, then request analysis exactly once.

    Stock research runs first; its target price (including None) is reused for
    portfolio valuation. Other holdings are quoted once in portfolio order.
    """
    if not isinstance(target_ticker, str) or not target_ticker.strip():
        raise ValueError("A non-empty ticker is required.")
    # Preserve legacy store-implies-save behavior; False permits read-only use.
    if type(memory_limit) is not int or memory_limit < 0:
        raise ValueError("memory_limit must be a non-negative integer.")
    if use_decision_memory and decision_store is None:
        raise ValueError("decision_store is required for automatic memory retrieval.")
    if use_decision_memory and memory_context is not None:
        raise ValueError("Supply explicit memory or enable retrieval, not both.")
    if persist_decision and decision_store is not None and (
        not isinstance(decision_timestamp, str) or not decision_timestamp.strip()
    ):
        raise ValueError("decision_timestamp is required for decision persistence.")
    ticker = target_ticker.strip().upper()
    evidence = build_stock_evidence(ticker)
    snapshot = build_live_portfolio_snapshot(
        portfolio_input, known_prices={ticker: evidence["retrieved_facts"]["stock"]["current_price"]},
    )
    risk = assess_portfolio_risk(snapshot)
    context = build_portfolio_analysis_context(snapshot, risk, ticker)
    if use_decision_memory:
        memory_context = build_decision_memory_context(decision_store, ticker, memory_limit)
    result = analyze_investment(evidence, context,
                                **({"memory_context": memory_context} if memory_context is not None else {}))
    if on_context is not None:
        on_context(context)
    if persist_decision and decision_store is not None:
        save_analysis_decision(result, decision_store, decision_timestamp, investment_horizon)
    return result
