import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import ForecastStatement, InvestmentAnalysis
from src.research_pipeline import run_stock_research


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
    lines.append("\nMissing data:")
    lines.extend(f"- {item}" for item in analysis.missing_data)
    lines.append(f"\nReasoning summary: {analysis.reasoning_summary}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="V0.1 single-stock research (environment keys required)")
    parser.add_argument("ticker")
    args = parser.parse_args()
    try:
        result = run_stock_research(args.ticker)
    except (RuntimeError, ValueError) as error:
        parser.exit(1, f"Research failed: {error}\n")
    print(format_analysis(result))


if __name__ == "__main__":
    main()
