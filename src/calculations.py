from src.models import IncomeStatementPeriod


def calculate_growth_rate(
    current: float | None, previous: float | None
) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous


def calculate_margin(
    income: float | None, revenue: float | None
) -> float | None:
    if income is None or revenue is None or revenue == 0:
        return None
    return income / revenue


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
