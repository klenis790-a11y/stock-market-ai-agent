from src.multi_agent import run_specialists
from src.synthesis import synthesize_investment_analysis
from collections.abc import Callable
from copy import deepcopy
from src.decision_memory import build_decision_memory_context
from src.decision_history import save_analysis_decision
from src.decision_store import DecisionStore
from dataclasses import replace
from datetime import date, datetime, timezone
import logging

from src import alpha_vantage_client as api
from src import normalizers as normalize
from src.analysis import analyze_investment
from src.evidence import build_evidence_package
from src.models import DecisionRecord, DecisionMemoryContext, InvestmentAnalysis, SpecialistAnalysis
from src.research_snapshot import build_research_snapshot


def _retrieve_optional(function, *args) -> dict:
    try:
        return function(*args)
    except RuntimeError:
        # Provider message text may contain arbitrary payload despite secret redaction.
        # The client already logs fixed operation/classification metadata.
        logging.getLogger(__name__).warning("Optional Fundamental source unavailable; detail=withheld.")
        return {}


def build_stock_evidence(ticker: str) -> dict:
    """Retrieve and assemble stock evidence without requesting AI analysis."""
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("A non-empty ticker is required.")
    ticker = ticker.strip().upper()
    overview = api.get_company_overview(ticker)
    stock = normalize.normalize_company_overview(overview)
    if stock.ticker.upper() != ticker or not stock.company_name.strip():
        raise RuntimeError("Company overview is unusable or does not match the ticker.")
    stock = replace(stock, ticker=ticker)
    quote = normalize.normalize_global_quote(_retrieve_optional(api.get_global_quote, ticker))
    stock = replace(stock, **{key: value for key, value in quote.items() if value is not None})
    income = normalize.normalize_annual_income_statements(api.get_income_statement(ticker))
    balance = normalize.normalize_annual_balance_sheets(api.get_balance_sheet(ticker))
    cash = normalize.normalize_annual_cash_flows(api.get_cash_flow(ticker))
    raw_earnings = api.get_earnings(ticker)
    earnings = normalize.normalize_quarterly_earnings(raw_earnings)
    news = normalize.normalize_relevant_news(_retrieve_optional(api.get_news_sentiment, ticker), ticker)

    # Inspect all already-retrieved records so missing recent dates don't hide a usable date.
    records = raw_earnings.get("quarterlyEarnings")
    all_earnings = normalize.normalize_quarterly_earnings(
        raw_earnings, limit=len(records) if isinstance(records, list) else 0
    )
    dates = []
    for period in all_earnings:
        try:
            dates.append(date.fromisoformat(period.fiscal_date_ending))
        except ValueError:
            continue
    transcript = []
    if dates:
        latest = max(dates)
        quarter = f"{latest.year}Q{(latest.month - 1) // 3 + 1}"
        transcript = normalize.normalize_earnings_call_transcript(
            _retrieve_optional(api.get_earnings_call_transcript, ticker, quarter)
        )
    snapshot = build_research_snapshot(stock, income, balance, cash, earnings, news, transcript)
    return build_evidence_package(snapshot)


def run_stock_research(
    ticker: str, *, decision_store: DecisionStore | None = None,
    decision_timestamp: str | None = None, investment_horizon: str | None = None,
    memory_context: DecisionMemoryContext | None = None,
    use_decision_memory: bool = False, memory_limit: int = 5,
    persist_decision: bool = True,
    use_multi_agent: bool = False,
    specialist_names: list[str] | None = None,
    integration_run_id: str | None = None,
    on_fundamental_artifact: Callable | None = None,
    on_memory: Callable[[DecisionMemoryContext], None] | None = None,
    on_decision_saved: Callable[[DecisionRecord], None] | None = None,
    on_specialists_complete: Callable[[list[SpecialistAnalysis]], None] | None = None,
) -> InvestmentAnalysis:
    """Return final analysis; optional multi-agent observation never changes its type.

    The observer receives defensive copies of the same-run ordered typed results,
    protecting synthesis from observer mutations. Observer errors propagate before
    synthesis/persistence, with no retries. Single-agent runs do not notify it.
    """
    if not use_multi_agent and specialist_names is not None:
        raise ValueError("specialist_names requires use_multi_agent=True.")
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
    if on_fundamental_artifact is not None and (
        not isinstance(integration_run_id, str) or not integration_run_id.strip()
    ):
        raise ValueError("Explicit integration_run_id required for provenance capture.")
    retrieval_started = datetime.now(timezone.utc) if on_fundamental_artifact is not None else None
    evidence = build_stock_evidence(ticker)
    retrieval_completed = datetime.now(timezone.utc) if on_fundamental_artifact is not None else None
    if use_decision_memory:
        memory_context = build_decision_memory_context(decision_store, evidence["ticker"], memory_limit)
    if memory_context is not None and on_memory is not None:
        on_memory(memory_context)
    if use_multi_agent:
        synthesis_context = run_specialists(
            evidence["ticker"], evidence, decision_memory=memory_context,
            specialist_names=specialist_names,
        )
        if on_specialists_complete is not None:
            on_specialists_complete(deepcopy(synthesis_context.specialist_results))
        result = synthesize_investment_analysis(synthesis_context, evidence)
    else:
        result = analyze_investment(evidence,
                                    **({"memory_context": memory_context} if memory_context is not None else {}))
    if on_fundamental_artifact is not None:
        from src.fundamental_provenance import _capture
        from src.openai_client import MODEL
        artifact = _capture(result, evidence, run_id=integration_run_id,
            native_horizon=investment_horizon, started=retrieval_started,
            cutoff=retrieval_completed, completed=datetime.now(timezone.utc),
            multi_agent=use_multi_agent,
            specialists=[item.specialist_name for item in synthesis_context.specialist_results] if use_multi_agent else [],
            model=MODEL, memory_used=memory_context is not None)
        on_fundamental_artifact(artifact)
    if persist_decision and decision_store is not None:
        saved = save_analysis_decision(result, decision_store, decision_timestamp, investment_horizon)
        if on_decision_saved is not None:
            on_decision_saved(saved)
    return result
