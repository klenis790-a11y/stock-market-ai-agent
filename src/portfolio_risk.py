"""Compare portfolio metrics with configured limits without recommending actions."""
from src.models import PortfolioRiskAssessment, PortfolioRiskPolicy, PortfolioSnapshot


def assess_portfolio_risk(
    snapshot: PortfolioSnapshot,
    policy: PortfolioRiskPolicy | None = None,
) -> PortfolioRiskAssessment:
    """Use strict limits; unavailable inputs stay unknown, never partially inferred.

    An empty cash-only portfolio has no oversized stock position. With a defined
    cash weight and top-three weight it is evaluable despite no largest position.
    """
    if policy is None:
        policy = PortfolioRiskPolicy()
    weights_available = all(p.portfolio_weight is not None for p in snapshot.positions)
    oversized = [p.ticker for p in snapshot.positions
                 if p.portfolio_weight > policy.max_single_position_weight] if weights_available else []
    largest = None
    if weights_available:
        if snapshot.largest_position_weight is not None:
            largest = snapshot.largest_position_weight > policy.max_single_position_weight
        elif not snapshot.positions and snapshot.cash_weight is not None:
            largest = False
    top_three = (snapshot.top_3_weight > policy.max_top_3_weight
                 if snapshot.top_3_weight is not None else None)
    cash = (snapshot.cash_weight < policy.minimum_cash_weight
            if snapshot.cash_weight is not None else None)
    evaluable = weights_available and largest is not None and top_three is not None and cash is not None
    notes = [f"{ticker} exceeds max single-position weight." for ticker in oversized]
    if top_three:
        notes.append("Top 3 positions exceed configured concentration limit.")
    if cash:
        notes.append("Cash weight is below configured target.")
    if not evaluable:
        if any(p.current_price is None for p in snapshot.positions):
            notes.append("Concentration policy unavailable because one or more position prices are missing.")
        else:
            notes.append("Concentration policy unavailable because required weights are undefined.")
    return PortfolioRiskAssessment(oversized, largest, top_three, cash, evaluable, notes)
