"""Sequential specialist execution only; failures propagate without partial synthesis."""
from copy import deepcopy
from math import isfinite

from src.models import (
    SpecialistAnalysis, SpecialistContext, MultiAgentSynthesisContext,
    PortfolioAnalysisContext, DecisionMemoryContext,
)
from src.specialists import ACTIVE_SPECIALISTS


def run_specialists(
    ticker: str,
    research_evidence: dict,
    portfolio_context: PortfolioAnalysisContext | None = None,
    decision_memory: DecisionMemoryContext | None = None,
    specialist_names: list[str] | None = None,
) -> MultiAgentSynthesisContext:
    """Run registered implementations in requested order, exactly once each.

    Empty explicit selection returns an empty result collection. Each implementation
    owns evidence validation. No retrieval, final analysis, retries or persistence.
    Independent input copies prevent one implementation from changing another's data.
    """
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError('A non-empty target ticker is required.')
    ticker = ticker.strip().upper()
    if (not isinstance(research_evidence, dict) or
            not isinstance(research_evidence.get('ticker'), str) or
            research_evidence['ticker'].strip().upper() != ticker):
        raise ValueError('Research evidence ticker does not match target.')
    names = list(ACTIVE_SPECIALISTS) if specialist_names is None else specialist_names
    if not isinstance(names, list) or any(not isinstance(name, str) or name not in ACTIVE_SPECIALISTS for name in names):
        raise ValueError('Unknown or invalid specialist selection.')
    if len(names) != len(set(names)):
        raise ValueError('Duplicate specialists are not allowed.')
    results = []
    for name in names:
        builder, analyzer = ACTIVE_SPECIALISTS[name]
        context = builder(deepcopy(research_evidence), deepcopy(portfolio_context), deepcopy(decision_memory))
        if not isinstance(context, SpecialistContext) or context.specialist_name != name or context.ticker != ticker:
            raise ValueError('Specialist builder returned a mismatched context.')
        result = analyzer(context)
        if not isinstance(result, SpecialistAnalysis) or result.specialist_name != name or result.ticker != ticker:
            raise ValueError('Specialist returned a mismatched result.')
        score = result.confidence_score
        if type(score) not in (int, float) or not isfinite(score) or not 0 <= score <= 100:
            raise ValueError('Specialist confidence_score must be between 0 and 100.')
        results.append(result)
    return MultiAgentSynthesisContext(ticker, results, deepcopy(portfolio_context), deepcopy(decision_memory))
