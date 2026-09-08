"""Portfolio-aware research orchestration using the existing evidence and analysis layers."""
from collections.abc import Callable

from src.analysis import analyze_investment
from src.models import InvestmentAnalysis, PortfolioInput, PortfolioAnalysisContext
from src.portfolio_context import build_portfolio_analysis_context
from src.portfolio_data import build_live_portfolio_snapshot
from src.portfolio_risk import assess_portfolio_risk
from src.research_pipeline import build_stock_evidence


def run_portfolio_aware_research(
    target_ticker: str, portfolio_input: PortfolioInput,
    *, on_context: Callable[[PortfolioAnalysisContext], None] | None = None,
) -> InvestmentAnalysis:
    """Assemble portfolio and stock evidence, then request analysis exactly once.

    Known inefficiency: a held target's quote is requested once for portfolio
    pricing and again for stock research (which retains additional quote fields).
    These independent snapshots may differ in time; no quote is retried here.
    """
    if not isinstance(target_ticker, str) or not target_ticker.strip():
        raise ValueError("A non-empty ticker is required.")
    ticker = target_ticker.strip().upper()
    snapshot = build_live_portfolio_snapshot(portfolio_input)
    risk = assess_portfolio_risk(snapshot)
    evidence = build_stock_evidence(ticker)
    context = build_portfolio_analysis_context(snapshot, risk, ticker)
    result = analyze_investment(evidence, context)
    if on_context is not None:
        on_context(context)
    return result
