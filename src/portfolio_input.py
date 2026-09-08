"""Parse explicit CLI holdings; model constructors own financial validation."""
from src.models import PortfolioInput, PortfolioPositionInput


def parse_portfolio_input(value: str, cash: float = 0.0) -> PortfolioInput:
    """Comma-separated TICKER:SHARES:AVERAGE_COST; empty text means cash-only."""
    positions = []
    if value.strip():
        for entry in value.split(','):
            parts = entry.split(':')
            if len(parts) != 3:
                raise ValueError("Portfolio entries must use TICKER:SHARES:AVERAGE_COST.")
            try:
                shares, cost = float(parts[1]), float(parts[2])
            except ValueError:
                raise ValueError("Portfolio shares and average cost must be numeric.") from None
            positions.append(PortfolioPositionInput(parts[0], shares, cost))
    return PortfolioInput(positions, cash)
