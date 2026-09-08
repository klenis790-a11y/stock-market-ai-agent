"""Build portfolio context without retrieval, recommendations, or input mutation."""
from copy import deepcopy

from src.models import PortfolioAnalysisContext, PortfolioRiskAssessment, PortfolioSnapshot


def build_portfolio_analysis_context(
    snapshot: PortfolioSnapshot, risk_assessment: PortfolioRiskAssessment, target_ticker: str,
) -> PortfolioAnalysisContext:
    if not isinstance(target_ticker, str) or not target_ticker.strip():
        raise ValueError("A non-empty target ticker is required.")
    ticker = target_ticker.strip().upper()
    target = next((p for p in snapshot.positions if p.ticker == ticker), None)
    return PortfolioAnalysisContext(
        target_ticker=ticker, owns_target=target is not None and target.shares > 0,
        target_shares=target.shares if target else 0,
        target_average_cost=target.average_cost if target else None,
        target_current_price=target.current_price if target else None,
        target_position_value=target.position_value if target else 0,
        target_unrealized_gain_loss=target.unrealized_gain_loss if target else None,
        target_unrealized_gain_loss_percent=target.unrealized_gain_loss_percent if target else None,
        target_portfolio_weight=(target.portfolio_weight if target else
                                 0 if snapshot.total_portfolio_value is not None
                                 and snapshot.total_portfolio_value > 0 else None),
        cash_weight=snapshot.cash_weight,
        largest_position_ticker=snapshot.largest_position_ticker,
        largest_position_weight=snapshot.largest_position_weight,
        top_3_weight=snapshot.top_3_weight, herfindahl_index=snapshot.herfindahl_index,
        effective_position_count=snapshot.effective_position_count,
        portfolio_risk_assessment=deepcopy(risk_assessment),
    )
