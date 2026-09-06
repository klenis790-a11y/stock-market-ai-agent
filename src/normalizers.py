from datetime import datetime, timezone
from math import isfinite

from src.models import IncomeStatementPeriod, StockResearchData


def _to_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


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
