"""Deterministic portfolio valuation from user holdings and supplied quote prices."""
from math import isfinite

from src.models import PortfolioInput, PortfolioPosition, PortfolioSnapshot


def build_portfolio_snapshot(
    portfolio_input: PortfolioInput,
    current_prices: dict[str, float | None],
) -> PortfolioSnapshot:
    """Use normalized ticker keys; missing/None prices prevent aggregate valuation.

    Zero prices are valid. No retrieval or investment judgment occurs here.
    Inputs are untouched; weights and percentage changes are decimal fractions.
    """
    for price in current_prices.values():
        if price is not None and (
            type(price) not in (int, float) or not isfinite(price) or price < 0
        ):
            raise ValueError("Current prices must be finite non-negative numbers or None.")

    positions = []
    for holding in portfolio_input.positions:
        price = current_prices.get(holding.ticker)
        cost_basis = holding.shares * holding.average_cost
        value = holding.shares * price if price is not None else None
        gain = value - cost_basis if value is not None else None
        positions.append(PortfolioPosition(
            ticker=holding.ticker, shares=holding.shares, average_cost=holding.average_cost,
            current_price=price, cost_basis=cost_basis, position_value=value,
            unrealized_gain_loss=gain,
            unrealized_gain_loss_percent=(gain / cost_basis
                                          if gain is not None and cost_basis > 0 else None),
            portfolio_weight=None,
        ))

    snapshot = PortfolioSnapshot(
        positions=positions, cash=portfolio_input.cash,
        total_positions_value=None, total_portfolio_value=None, cash_weight=None,
        largest_position_ticker=None, largest_position_weight=None,
    )
    if any(position.position_value is None for position in positions):
        return snapshot

    snapshot.total_positions_value = sum(position.position_value for position in positions)
    snapshot.total_portfolio_value = snapshot.total_positions_value + snapshot.cash
    if snapshot.total_portfolio_value > 0:
        snapshot.cash_weight = snapshot.cash / snapshot.total_portfolio_value
        for position in positions:
            position.portfolio_weight = position.position_value / snapshot.total_portfolio_value
        if positions:
            # max retains the first input position on equal weights.
            largest = max(positions, key=lambda position: position.portfolio_weight)
            snapshot.largest_position_ticker = largest.ticker
            snapshot.largest_position_weight = largest.portfolio_weight
    return snapshot
