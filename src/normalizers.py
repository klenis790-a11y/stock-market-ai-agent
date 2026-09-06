from datetime import datetime, timezone
from math import isfinite

from src.models import (
    BalanceSheetPeriod,
    CashFlowPeriod,
    EarningsPeriod,
    IncomeStatementPeriod,
    NewsItem,
    StockResearchData,
)


def _to_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def normalize_relevant_news(
    data: dict,
    ticker: str,
    limit: int = 5,
    min_relevance_score: float = 0.5,
) -> list[NewsItem]:
    feed = data.get("feed")
    if not isinstance(feed, list) or limit <= 0:
        return []
    items = []
    for article in feed:
        if not isinstance(article, dict):
            continue
        title = article.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        entries = article.get("ticker_sentiment")
        if not isinstance(entries, list):
            continue
        relevance = None
        for entry in entries:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("ticker"), str)
                and entry["ticker"].casefold() == ticker.casefold()
            ):
                relevance = _to_float(entry.get("relevance_score"))
                break
        if relevance is None or relevance < min_relevance_score:
            continue
        optional_fields = {}
        for name in ("source", "time_published", "url"):
            value = article.get(name)
            optional_fields[name] = (
                value if isinstance(value, str) and value.strip() else None
            )
        items.append(NewsItem(
            title=title,
            ticker_relevance_score=relevance,
            **optional_fields,
        ))
        if len(items) == limit:
            break
    return items


def normalize_annual_income_statements(
    data: dict, limit: int = 3
) -> list[IncomeStatementPeriod]:
    reports = data.get("annualReports")
    if not isinstance(reports, list):
        return []
    return [
        IncomeStatementPeriod(
            fiscal_date_ending=str(report.get("fiscalDateEnding") or ""),
            total_revenue=_to_float(report.get("totalRevenue")),
            operating_income=_to_float(report.get("operatingIncome")),
            net_income=_to_float(report.get("netIncome")),
        )
        for report in reports[:max(0, limit)]
    ]


def normalize_annual_balance_sheets(
    data: dict, limit: int = 3
) -> list[BalanceSheetPeriod]:
    reports = data.get("annualReports")
    if not isinstance(reports, list):
        return []
    return [
        BalanceSheetPeriod(
            fiscal_date_ending=str(report.get("fiscalDateEnding") or ""),
            cash_and_cash_equivalents=_to_float(
                report.get("cashAndCashEquivalentsAtCarryingValue")
            ),
            total_assets=_to_float(report.get("totalAssets")),
            total_liabilities=_to_float(report.get("totalLiabilities")),
            long_term_debt=_to_float(report.get("longTermDebt")),
            total_debt=_to_float(report.get("shortLongTermDebtTotal")),
            shareholder_equity=_to_float(report.get("totalShareholderEquity")),
        )
        for report in reports[:max(0, limit)]
    ]


def normalize_annual_cash_flows(
    data: dict, limit: int = 3
) -> list[CashFlowPeriod]:
    reports = data.get("annualReports")
    if not isinstance(reports, list):
        return []
    return [
        CashFlowPeriod(
            fiscal_date_ending=str(report.get("fiscalDateEnding") or ""),
            operating_cash_flow=_to_float(report.get("operatingCashflow")),
            capital_expenditures=_to_float(report.get("capitalExpenditures")),
        )
        for report in reports[:max(0, limit)]
    ]


def normalize_quarterly_earnings(
    data: dict, limit: int = 4
) -> list[EarningsPeriod]:
    records = data.get("quarterlyEarnings")
    if not isinstance(records, list):
        return []
    periods = []
    for record in records[:max(0, limit)]:
        reported_date = record.get("reportedDate")
        if reported_date is not None:
            reported_date = str(reported_date)
            if reported_date.strip() in ("", "None", "-"):
                reported_date = None
        periods.append(
            EarningsPeriod(
                fiscal_date_ending=str(record.get("fiscalDateEnding") or ""),
                reported_date=reported_date,
                reported_eps=_to_float(record.get("reportedEPS")),
                estimated_eps=_to_float(record.get("estimatedEPS")),
                surprise=_to_float(record.get("surprise")),
                surprise_percentage=_to_float(record.get("surprisePercentage")),
            )
        )
    return periods


def normalize_company_overview(data: dict) -> StockResearchData:
    return StockResearchData(
        ticker=str(data.get("Symbol") or ""),
        company_name=str(data.get("Name") or ""),
        market_cap=_to_float(data.get("MarketCapitalization")),
        pe_ratio=_to_float(data.get("PERatio")),
        forward_pe=_to_float(data.get("ForwardPE")),
        price_to_sales=_to_float(data.get("PriceToSalesRatioTTM")),
        ev_to_ebitda=_to_float(data.get("EVToEBITDA")),
        data_source="Alpha Vantage",
        data_timestamp=datetime.now(timezone.utc).isoformat(),
    )
