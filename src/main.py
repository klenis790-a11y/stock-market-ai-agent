import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import ForecastStatement, InvestmentAnalysis
from src.research_pipeline import run_stock_research
from src.portfolio_input import parse_portfolio_input
from src.portfolio_research_pipeline import run_portfolio_aware_research


def format_analysis(analysis: InvestmentAnalysis) -> str:
    lines = ["V0.1 — Single Stock Research Agent"]
    for name in (
        "ticker", "recommendation", "confidence_score", "fundamental_assessment",
        "valuation_assessment", "earnings_assessment",
    ):
        lines.append(f"{name.replace('_', ' ').title()}: {getattr(analysis, name)}")
    for name in (
        "bull_case", "bear_case", "supporting_evidence", "major_risks",
        "thesis_invalidation_conditions", "scenarios",
    ):
        lines.append(f"\n{name.replace('_', ' ').title()}:")
        for statement in getattr(analysis, name):
            category = "FORECAST" if isinstance(statement, ForecastStatement) else "AI INTERPRETATION"
            lines.append(f"- [{category}] {statement.text}")
            lines.append(f"  Evidence: {', '.join(statement.evidence_refs) or 'None'}")
    lines.append("\nMaterial Evidence Review:")
    for evidence_id, review in analysis.material_evidence_review.items():
        lines.append(evidence_id)
        lines.append(f"  Observation: {review.observation}")
        lines.append(f"  Thesis relevance: {review.thesis_relevance}")
    lines.append("\nMissing data:")
    lines.extend(f"- {item}" for item in analysis.missing_data)
    lines.append(f"\nReasoning summary: {analysis.reasoning_summary}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="V0.1 single-stock research (environment keys required)")
    parser.add_argument("ticker")
    parser.add_argument("--portfolio", help="Comma-separated TICKER:SHARES:AVERAGE_COST; empty for cash-only")
    parser.add_argument("--cash", type=float, default=0.0)
    args = parser.parse_args()
    contexts = []
    try:
        if args.portfolio is None:
            if args.cash != 0.0:
                raise ValueError("--cash requires --portfolio.")
            result = run_stock_research(args.ticker)
        else:
            portfolio = parse_portfolio_input(args.portfolio, args.cash)
            result = run_portfolio_aware_research(args.ticker, portfolio, on_context=contexts.append)
    except (RuntimeError, ValueError) as error:
        parser.exit(1, f"Research failed: {error}\n")
    print(format_analysis(result))
    if args.portfolio is not None:
        print(f"\nPortfolio assessment: {result.portfolio_assessment}")
        if contexts:
            context = contexts[0]
            print(f"Target owned: {context.owns_target}")
            print(f"Target portfolio weight: {context.target_portfolio_weight}")
            print(f"Largest position: {context.largest_position_ticker}; weight: {context.largest_position_weight}")
            print("Portfolio policy notes:")
            for note in context.portfolio_risk_assessment.notes:
                print(f"- {note}")


if __name__ == "__main__":
    main()
