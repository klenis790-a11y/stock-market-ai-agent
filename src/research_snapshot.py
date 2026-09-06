from datetime import datetime, timezone

from src.calculations import (
    calculate_balance_sheet_metrics,
    calculate_cash_flow_metrics,
    calculate_earnings_metrics,
    calculate_income_statement_metrics,
)
from src.models import (
    BalanceSheetPeriod,
    CashFlowPeriod,
    EarningsPeriod,
    IncomeStatementPeriod,
    NewsItem,
    ResearchSnapshot,
    StockResearchData,
)


def build_research_snapshot(
    stock: StockResearchData,
    income_statements: list[IncomeStatementPeriod],
    balance_sheets: list[BalanceSheetPeriod],
    cash_flows: list[CashFlowPeriod],
    earnings: list[EarningsPeriod],
    news: list[NewsItem],
) -> ResearchSnapshot:
    income_metrics = calculate_income_statement_metrics(income_statements)
    balance_metrics = calculate_balance_sheet_metrics(balance_sheets)
    cash_metrics = calculate_cash_flow_metrics(cash_flows, income_statements)
    earnings_metrics = calculate_earnings_metrics(earnings)

    missing_data = []
    if not news:
        missing_data.append("Recent relevant news unavailable")
    for name in (
        "current_price", "market_cap", "pe_ratio", "forward_pe",
        "price_to_sales", "ev_to_ebitda",
    ):
        if getattr(stock, name) is None:
            missing_data.append(f"Stock: {name.replace('_', ' ')} unavailable")
    for label, periods in (
        ("Income statement history", income_statements),
        ("Balance sheet history", balance_sheets),
        ("Cash-flow history", cash_flows),
        ("Earnings history", earnings),
    ):
        if not periods:
            missing_data.append(f"{label} unavailable")
    for metrics in (income_metrics, balance_metrics, cash_metrics, earnings_metrics):
        for name, value in metrics.items():
            if value is None:
                missing_data.append(
                    f"Calculated metric: {name.replace('_', ' ')} unavailable"
                )

    return ResearchSnapshot(
        stock=stock,
        income_statements=income_statements,
        balance_sheets=balance_sheets,
        cash_flows=cash_flows,
        earnings=earnings,
        news=news,
        income_statement_metrics=income_metrics,
        balance_sheet_metrics=balance_metrics,
        cash_flow_metrics=cash_metrics,
        earnings_metrics=earnings_metrics,
        missing_data=missing_data,
        source=stock.data_source,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
