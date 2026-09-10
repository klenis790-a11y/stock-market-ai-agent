"""Explicit V0.2 loading and presentation mapping; no financial calculations."""
from dataclasses import asdict
from src.models import PortfolioSnapshot, PortfolioRiskAssessment
from src.portfolio_input import parse_portfolio_input
from src.portfolio_data import build_live_portfolio_snapshot
from src.portfolio_risk import assess_portfolio_risk
from src.ui_contracts import PortfolioPageData


class PortfolioLoadError(ValueError):
    pass


def portfolio_page_data(snapshot: PortfolioSnapshot, risk: PortfolioRiskAssessment) -> PortfolioPageData:
    return PortfolioPageData(snapshot=snapshot, risk_assessment=risk)


def position_rows(data: PortfolioPageData) -> list[dict]:
    return [asdict(position) for position in data.snapshot.positions]


def load_portfolio(positions: str, cash: float) -> PortfolioPageData:
    try:
        inputs = parse_portfolio_input(positions, cash)
    except (ValueError, TypeError):
        raise PortfolioLoadError('Check TICKER:SHARES:AVERAGE_COST entries, duplicate tickers and non-negative cash/quantities.') from None
    try:
        snapshot = build_live_portfolio_snapshot(inputs)
        return portfolio_page_data(snapshot, assess_portfolio_risk(snapshot))
    except (ValueError, RuntimeError):
        raise PortfolioLoadError('Portfolio could not be loaded. Check server configuration and inputs.') from None
