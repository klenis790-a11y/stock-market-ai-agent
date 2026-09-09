import argparse
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.decision_store import DecisionStore
from src.decision_history import utc_decision_timestamp
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


def history_main(argv):
    import sqlite3
    from src.decision_store import DecisionStore
    from src.decision_memory import build_decision_memory_context

    parser = argparse.ArgumentParser(description="Inspect stored decisions (read-only)")
    parser.add_argument("ticker")
    parser.add_argument("--db", required=True, help="Existing decision database path")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    if not args.ticker.strip():
        parser.error("A non-empty ticker is required.")
    if args.limit < 0:
        parser.error("limit must be a non-negative integer.")
    try:
        if not Path(args.db).is_file():
            parser.exit(1, "History failed: database does not exist.\n")
        context = build_decision_memory_context(
            DecisionStore(args.db, read_only=True), args.ticker, args.limit,
        )
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError):
        parser.exit(1, "History failed: unable to read decision history.\n")
    if not context.prior_decisions:
        print(f"No stored decisions for {context.ticker}.")
    for item in context.prior_decisions:
        print(f"{item.decision_timestamp} | {item.ticker} | {item.recommendation} | Confidence: {item.confidence_score}")
        print(f"Investment horizon: {item.investment_horizon or 'Not supplied'}")
        print(f"Reasoning: {item.reasoning_summary}")
        for label, statements in (("Major risks", item.major_risks),
                                  ("Thesis invalidation conditions", item.thesis_invalidation_conditions)):
            print(f"{label}:")
            for statement in statements:
                print(f"- {statement.text}")
        print("Missing data: " + ('; '.join(item.missing_data) or 'None'))
        print("Outcomes:" if item.outcomes else "Outcomes: None recorded.")
        for outcome in item.outcomes:
            print(f"- {outcome.evaluation_horizon}: stock return={outcome.stock_return}, "
                  f"benchmark return={outcome.benchmark_return}, excess return={outcome.excess_return}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "history":
        history_main(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description="V0.1 single-stock research (environment keys required)")
    parser.add_argument("ticker")
    parser.add_argument("--portfolio", help="Comma-separated TICKER:SHARES:AVERAGE_COST; empty for cash-only")
    parser.add_argument("--cash", type=float, default=0.0)
    parser.add_argument("--db", help="Decision history SQLite path")
    parser.add_argument("--use-memory", action="store_true", help="Read prior ticker history; requires an existing --db")
    parser.add_argument("--memory-limit", type=int, default=None, help="Prior decisions to load (default 5); requires --use-memory")
    parser.add_argument("--save-decision", action="store_true", help="Save validated decision; requires --db")
    parser.add_argument("--horizon", help="Optional investment horizon for a saved decision")
    args = parser.parse_args()
    contexts = []
    loaded_memory = []
    saved_decisions = []
    try:
        if not args.ticker.strip():
            raise ValueError("A non-empty ticker is required.")
        if args.memory_limit is not None and (args.memory_limit < 0 or not args.use_memory):
            raise ValueError("--memory-limit requires --use-memory and a non-negative value.")
        if (args.use_memory or args.save_decision) and not args.db:
            raise ValueError("--db is required with --use-memory or --save-decision.")
        if args.horizon is not None and not args.save_decision:
            raise ValueError("--horizon requires --save-decision.")
        if args.portfolio is None and args.cash != 0.0:
            raise ValueError("--cash requires --portfolio.")
        portfolio = parse_portfolio_input(args.portfolio, args.cash) if args.portfolio is not None else None
        options = {}
        if args.use_memory or args.save_decision:
            if args.use_memory and not Path(args.db).is_file():
                raise ValueError("Memory database must already exist.")
            store = DecisionStore(args.db, read_only=not args.save_decision)
            if args.save_decision:
                store.initialize()
            options = dict(
                decision_store=store, persist_decision=args.save_decision,
                decision_timestamp=utc_decision_timestamp() if args.save_decision else None,
                investment_horizon=args.horizon, use_decision_memory=args.use_memory,
                memory_limit=args.memory_limit if args.memory_limit is not None else 5,
                on_memory=loaded_memory.append, on_decision_saved=saved_decisions.append,
            )
        if portfolio is None:
            result = run_stock_research(args.ticker, **options)
        else:
            result = run_portfolio_aware_research(args.ticker, portfolio, on_context=contexts.append, **options)
    except (sqlite3.Error, OSError):
        parser.exit(1, "Research failed: decision database operation failed. No retry performed.\n")
    except (RuntimeError, ValueError) as error:
        parser.exit(1, f"Research failed: {error}\n")
    print(format_analysis(result))
    if args.use_memory:
        print("Historical memory used: YES")
        print(f"Prior decisions loaded: {len(loaded_memory[0].prior_decisions) if loaded_memory else 0}")
    for saved in saved_decisions:
        print(f"Decision saved: {saved.decision_id}")
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
