from src.models import BalanceSheetPeriod, IncomeStatementPeriod


def calculate_ratio(
    numerator: float | None, denominator: float | None
) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def calculate_growth_rate(
    current: float | None, previous: float | None
) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous


def calculate_margin(
    income: float | None, revenue: float | None
) -> float | None:
    return calculate_ratio(income, revenue)


def calculate_income_statement_metrics(
    periods: list[IncomeStatementPeriod],
) -> dict:
    """Calculate decimal metrics from periods supplied newest first."""
    metrics = {
        "revenue_growth": None,
        "net_income_growth": None,
        "operating_margin": None,
        "net_margin": None,
    }
    if not periods:
        return metrics

    newest = periods[0]
    metrics["operating_margin"] = calculate_margin(
        newest.operating_income, newest.total_revenue
    )
    metrics["net_margin"] = calculate_margin(newest.net_income, newest.total_revenue)
    if len(periods) >= 2:
        previous = periods[1]
        metrics["revenue_growth"] = calculate_growth_rate(
            newest.total_revenue, previous.total_revenue
        )
        metrics["net_income_growth"] = calculate_growth_rate(
            newest.net_income, previous.net_income
        )
    return metrics


def calculate_balance_sheet_metrics(periods: list[BalanceSheetPeriod]) -> dict:
    """Calculate ratios from the first period; periods must be newest first."""
    if not periods:
        return {
            "debt_to_equity": None,
            "liabilities_to_assets": None,
            "cash_to_debt": None,
        }
    newest = periods[0]
    return {
        "debt_to_equity": calculate_ratio(
            newest.total_debt, newest.shareholder_equity
        ),
        "liabilities_to_assets": calculate_ratio(
            newest.total_liabilities, newest.total_assets
        ),
        "cash_to_debt": calculate_ratio(
            newest.cash_and_cash_equivalents, newest.total_debt
        ),
    }
