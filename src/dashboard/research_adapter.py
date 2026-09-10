"""One explicit standalone pipeline invocation; no UI orchestration of specialists."""
import re
from src.research_pipeline import run_stock_research
from src.ui_contracts import ResearchPageData, UISectionAvailability


class ResearchInputError(ValueError):
    pass


class ResearchRunError(RuntimeError):
    pass


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper() if isinstance(value, str) else ''
    if not re.fullmatch(r'[A-Z0-9]+(?:[.:-][A-Z0-9]+)*', ticker):
        raise ResearchInputError('Enter a ticker using letters/numbers and optional dot, colon or hyphen separators.')
    return ticker


def run_research(value: str) -> ResearchPageData:
    ticker = normalize_ticker(value)
    try:
        analysis = run_stock_research(ticker, use_multi_agent=True,
                                      persist_decision=False, use_decision_memory=False)
    except (RuntimeError, ValueError):
        # Never display arbitrary exception text, which might contain credentials.
        raise ResearchRunError('Research failed during retrieval, AI analysis or validation. Check server configuration and try again explicitly.') from None
    return ResearchPageData(analysis=analysis, availability={
        'evidence': UISectionAvailability(False, False, 'Evidence IDs are preserved below. Same-run catalog resolution is unavailable through the current pipeline return value.'),
        'specialists': UISectionAvailability(False, False, 'Individual specialist results are not exposed by the current pipeline return value.'),
    })
