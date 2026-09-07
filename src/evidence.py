from dataclasses import asdict

from src.models import ResearchSnapshot


def build_valid_evidence_references(evidence_package: dict) -> list[str]:
    """List populated leaf paths in evidence order, using dot-separated indices."""
    references = []

    def visit(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                # Dotted keys cannot be resolved as a single key by the validator.
                if isinstance(key, str) and key and "." not in key:
                    visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}.{index}")
        elif isinstance(value, (bool, int, float)) or (
            isinstance(value, str) and value.strip()
        ):
            references.append(path)

    for root in ("retrieved_facts", "calculated_metrics"):
        visit(evidence_package.get(root), root)
    # The existing prompt/validator intentionally support citing missing-data context.
    visit(evidence_package.get("missing_data"), "missing_data")
    return references


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
