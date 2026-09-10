"""One explicit standalone pipeline invocation; no UI orchestration of specialists."""
import logging
import os
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


# Only recognized application diagnostics may pass through; arbitrary exception
# text may contain full provider/model payloads. Never log traceback locals.
_SAFE_MESSAGES = {
    'ALPHA_VANTAGE_API_KEY must be configured.', 'OPENAI_API_KEY must be configured.',
    'Alpha Vantage network request failed or timed out.',
    'Alpha Vantage returned invalid JSON.',
    'Alpha Vantage returned an unexpected response format.',
    'OpenAI connection failed or timed out.', 'OpenAI request failed.',
    'OpenAI returned no text.', 'OpenAI returned invalid specialist JSON.',
    'OpenAI returned invalid synthesis JSON.', 'OpenAI returned invalid analysis JSON.',
    'Specialist response has missing or unexpected fields.',
    'Specialist response identity does not match context.',
    'Specialist evidence reference is absent from supplied context.',
    'Analysis has missing or unexpected fields.',
    'Material evidence review keys must exactly match the checklist.',
    'Analysis confidence_score must be between 0 and 100.',
    'Company overview is unusable or does not match the ticker.',
}


def _diagnostic(error):
    stage = 'UNKNOWN'
    stages = {
        'src.alpha_vantage_client': 'RETRIEVAL',
        'src.normalizers': 'RETRIEVAL', 'src.research_snapshot': 'RETRIEVAL',
        'src.fundamental_analysis': 'FUNDAMENTAL', 'src.risk_analysis': 'RISK',
        'src.synthesis': 'SYNTHESIS', 'src.analysis': 'VALIDATION',
    }
    frame = error.__traceback__
    while frame is not None:
        module = frame.tb_frame.f_globals.get('__name__')
        # Risk reuses Fundamental parsing helpers; retain the outer Risk stage.
        if module in stages and not (module == 'src.fundamental_analysis' and stage == 'RISK'):
            stage = stages[module]
        if module == 'src.research_pipeline' and frame.tb_frame.f_code.co_name == 'build_stock_evidence':
            stage = 'RETRIEVAL'
        frame = frame.tb_next
    message = str(error)
    if message not in _SAFE_MESSAGES:
        match = re.fullmatch(r'Alpha Vantage (Error Message|Note|Information):.*', message, re.S)
        if match:
            message = 'Alpha Vantage ' + match.group(1) + ': [provider detail withheld]'
        elif not re.fullmatch(r'(Alpha Vantage HTTP error: [0-9]{3}\.|OpenAI API HTTP error: [0-9]{3} \([A-Za-z]+\)\.)', message):
            message = 'Unrecognized exception detail withheld to protect sensitive data.'
    for key, value in os.environ.items():
        if value and any(marker in key.upper() for marker in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'AUTHORIZATION')):
            message = message.replace(value, '[REDACTED]')
    return stage, message


def run_research(value: str) -> ResearchPageData:
    ticker = normalize_ticker(value)
    try:
        analysis = run_stock_research(ticker, use_multi_agent=True,
                                      persist_decision=False, use_decision_memory=False)
    except (RuntimeError, ValueError) as error:
        stage, message = _diagnostic(error)
        logging.getLogger(__name__).error(
            "Dashboard research failed stage=%s exception=%s message=%s",
            stage, type(error).__name__, message,
        )
        # Never display arbitrary exception text, which might contain credentials.
        raise ResearchRunError('Research failed during retrieval, AI analysis or validation. Check server configuration and try again explicitly.') from None
    return ResearchPageData(analysis=analysis, availability={
        'evidence': UISectionAvailability(False, False, 'Evidence IDs are preserved below. Same-run catalog resolution is unavailable through the current pipeline return value.'),
        'specialists': UISectionAvailability(False, False, 'Individual specialist results are not exposed by the current pipeline return value.'),
    })
