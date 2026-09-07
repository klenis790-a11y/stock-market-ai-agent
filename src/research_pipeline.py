from dataclasses import replace
from datetime import date
import logging

from src import alpha_vantage_client as api
from src import normalizers as normalize
from src.analysis import analyze_investment
from src.evidence import build_evidence_package
from src.models import InvestmentAnalysis
from src.research_snapshot import build_research_snapshot


def _retrieve_optional(function, *args) -> dict:
    try:
        return function(*args)
    except RuntimeError as error:
        # The existing client supplies secret-safe diagnostics.
        logging.getLogger(__name__).warning("%s unavailable: %s", function.__name__, error)
        return {}


def run_stock_research(ticker: str) -> InvestmentAnalysis:
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
    return analyze_investment(build_evidence_package(snapshot))
