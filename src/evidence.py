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
    visit(evidence_package.get("missing_data"), "missing_data")
    return references


def _path_value(evidence: dict, path: str):
    value = evidence
    for part in path.split("."):
        if isinstance(value, dict):
            value = value[part]
        elif isinstance(value, list) and part.isascii() and part.isdigit():
            if str(int(part)) != part:
                raise ValueError("Invalid evidence path index.")
            value = value[int(part)]
        else:
            raise ValueError("Invalid evidence path.")
    return value


def build_evidence_catalog(evidence_package: dict) -> list[dict]:
    paths = [path for path in build_valid_evidence_references(evidence_package)
             if path.startswith(("retrieved_facts.", "calculated_metrics."))]
    return [
        {"evidence_id": f"E{index:03d}", "path": path,
         "value": _path_value(evidence_package, path)}
        for index, path in enumerate(paths, start=1)
    ]


def build_material_evidence_checklist(evidence_package: dict) -> dict[str, list[str]]:
    """Declare coverage of available financial evidence, without assigning judgment."""
    groups = {
        "valuation": ("retrieved_facts.stock", (
            "pe_ratio", "forward_pe", "price_to_sales", "ev_to_ebitda")),
        "growth_profitability": ("calculated_metrics.income_statement_metrics", (
            "revenue_growth", "net_income_growth", "operating_margin", "net_margin")),
        "cash_flow": ("calculated_metrics.cash_flow_metrics", (
            "free_cash_flow", "free_cash_flow_growth", "free_cash_flow_margin")),
        "balance_sheet": ("calculated_metrics.balance_sheet_metrics", (
            "debt_to_equity", "liabilities_to_assets", "cash_to_debt")),
        "earnings": ("calculated_metrics.earnings_metrics", (
            "latest_surprise_percentage", "average_surprise_percentage",
            "beats_last_4_quarters", "misses_last_4_quarters")),
    }
    ids_by_path = {
        entry["path"]: entry["evidence_id"]
        for entry in build_evidence_catalog(evidence_package)
    }
    return {
        category: [ids_by_path[f"{prefix}.{name}"] for name in names
                   if f"{prefix}.{name}" in ids_by_path]
        for category, (prefix, names) in groups.items()
    }


def resolve_evidence_id(evidence_id: str, catalog: list[dict], evidence_package: dict) -> dict:
    """Resolve an exact ID and verify its path/value against the original evidence."""
    matches = [entry for entry in catalog if entry["evidence_id"] == evidence_id]
    if len(matches) != 1:
        raise ValueError("Unknown or ambiguous evidence ID.")
    entry = matches[0]
    try:
        value = _path_value(evidence_package, entry["path"])
    except (KeyError, IndexError, ValueError, TypeError):
        raise ValueError("Evidence ID has an invalid original path.") from None
    if type(value) is not type(entry["value"]) or value != entry["value"]:
        raise ValueError("Evidence ID value does not match original evidence.")
    return dict(entry)


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
