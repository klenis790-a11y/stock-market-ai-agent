"""Portfolio latest available prices using the existing paced Alpha Vantage client."""
import logging

from src import alpha_vantage_client as api
from src.models import PortfolioInput, PortfolioSnapshot
from src.normalizers import normalize_global_quote
from src.portfolio_calculations import build_portfolio_snapshot


def get_portfolio_prices(portfolio_input: PortfolioInput) -> dict[str, float | None]:
    """Request each ticker once in input order; unavailable quotes remain None."""
    prices = {}
    for position in portfolio_input.positions:
        ticker = position.ticker
        if ticker in prices:
            continue
        try:
            quote = api.get_global_quote(ticker)
        except RuntimeError as error:
            # The existing client provides sanitized provider diagnostics.
            logging.getLogger(__name__).warning("Portfolio quote unavailable: %s", error)
            prices[ticker] = None
            continue
        price = normalize_global_quote(quote)["current_price"]
        # A negative vendor price is unusable, rather than a portfolio-wide failure.
        prices[ticker] = price if price is not None and price >= 0 else None
    return prices


def build_live_portfolio_snapshot(portfolio_input: PortfolioInput) -> PortfolioSnapshot:
    """Retrieve latest available prices (not assumed real-time), then calculate."""
    return build_portfolio_snapshot(portfolio_input, get_portfolio_prices(portfolio_input))
