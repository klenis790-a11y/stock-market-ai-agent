from dataclasses import asdict

from src.models import ResearchSnapshot


def build_evidence_package(snapshot: ResearchSnapshot) -> dict:
    data = asdict(snapshot)
    return {
        "ticker": snapshot.stock.ticker,
        "source": snapshot.source,
        "generated_at": snapshot.generated_at,
        "retrieved_facts": {
            name: data[name]
            for name in (
                "stock", "income_statements", "balance_sheets",
                "cash_flows", "earnings", "news",
                "earnings_call_transcript",
            )
        },
        "calculated_metrics": {
            name: data[name]
            for name in (
                "income_statement_metrics", "balance_sheet_metrics",
                "cash_flow_metrics", "earnings_metrics",
            )
        },
        "missing_data": data["missing_data"],
    }
