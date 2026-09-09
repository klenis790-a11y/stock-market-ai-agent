"""Evidence preparation and ordered implementation-phase specialist registration.

Fundamental will focus on company fundamentals, not portfolio allocation.
Risk may interpret company risk and optional deterministic portfolio policy.
Future activation changes do not require changing shared data contracts.
"""

from copy import deepcopy

from src.evidence import build_evidence_catalog
from src.models import SpecialistContext, PortfolioAnalysisContext, DecisionMemoryContext


# Canonical normalized fields only. Period dates and metric inputs retain timing
# context; sector is not currently supplied by StockResearchData and is not inferred.
_FUNDAMENTAL_FIELDS = {
    'retrieved_facts.stock': {
        'ticker', 'company_name', 'revenue', 'net_income', 'free_cash_flow',
        'data_source', 'data_timestamp',
    },
    'retrieved_facts.income_statements': {
        'fiscal_date_ending', 'total_revenue', 'operating_income', 'net_income',
    },
    'retrieved_facts.balance_sheets': {
        'fiscal_date_ending', 'cash_and_cash_equivalents', 'total_assets',
        'total_liabilities', 'long_term_debt', 'total_debt', 'shareholder_equity',
    },
    'retrieved_facts.cash_flows': {
        'fiscal_date_ending', 'operating_cash_flow', 'capital_expenditures',
    },
    'calculated_metrics.income_statement_metrics': {
        'revenue_growth', 'net_income_growth', 'operating_margin', 'net_margin',
    },
    'calculated_metrics.balance_sheet_metrics': {
        'debt_to_equity', 'liabilities_to_assets', 'cash_to_debt',
    },
    'calculated_metrics.cash_flow_metrics': {
        'free_cash_flow', 'free_cash_flow_growth', 'free_cash_flow_margin',
    },
}


def select_fundamental_evidence(evidence: dict) -> dict:
    """Select entries from the FULL canonical catalog, never renumber a subset.

    Input is build_evidence_package output, not raw provider data. The returned
    EVIDENCE_CATALOG retains original IDs, paths, values and order; resolve IDs
    against the original package using resolve_evidence_id. Do not rebuild a
    catalog from this selected view. Existing missing_data is preserved verbatim
    (including broader package limitations); absent/None leaves get no new IDs.
    No calculations, interpretations, or historical substitutions occur here.
    """
    return _select_evidence(evidence, _FUNDAMENTAL_FIELDS)


def _select_evidence(evidence: dict, fields_by_path: dict) -> dict:
    """Filter canonical entries without changing identity, values or ordering."""
    selected = []
    for entry in build_evidence_catalog(evidence):
        parts = entry['path'].split('.')
        prefix = '.'.join(parts[:2])
        fields = fields_by_path.get(prefix, set())
        indexed = prefix in {
            'retrieved_facts.income_statements',
            'retrieved_facts.balance_sheets', 'retrieved_facts.cash_flows',
            'retrieved_facts.earnings',
        }
        expected_length = 4 if indexed else 3
        if (len(parts) == expected_length and parts[-1] in fields
                and (not indexed or parts[2].isdigit())):
            selected.append(entry)
    return deepcopy({
        **{name: evidence[name] for name in ('ticker', 'source', 'generated_at')
           if name in evidence},
        'EVIDENCE_CATALOG': selected,
        'missing_data': evidence['missing_data'],
    })


def build_fundamental_context(
    evidence: dict,
    portfolio_context: PortfolioAnalysisContext | None = None,
    decision_memory: DecisionMemoryContext | None = None,
) -> SpecialistContext:
    """Keep optional portfolio/history context separate from current stock evidence."""
    return SpecialistContext(
        ticker=evidence['ticker'], specialist_name='fundamental',
        research_evidence=select_fundamental_evidence(evidence),
        portfolio_context=portfolio_context, decision_memory=decision_memory,
    )


# Risk shares financial facts with Fundamental, retaining the same original IDs.
# Dates and raw metric inputs preserve context, not additional risk calculations.
_RISK_FIELDS = {
    'retrieved_facts.stock': {
        'ticker', 'company_name', 'data_source', 'data_timestamp', 'free_cash_flow',
    },
    'retrieved_facts.balance_sheets': set(_FUNDAMENTAL_FIELDS['retrieved_facts.balance_sheets']),
    'retrieved_facts.cash_flows': set(_FUNDAMENTAL_FIELDS['retrieved_facts.cash_flows']),
    'retrieved_facts.income_statements': {
        'fiscal_date_ending', 'total_revenue', 'net_income',
    },
    'retrieved_facts.earnings': {
        'fiscal_date_ending', 'reported_date', 'reported_eps', 'estimated_eps',
        'surprise', 'surprise_percentage',
    },
    'calculated_metrics.balance_sheet_metrics': {
        'debt_to_equity', 'liabilities_to_assets', 'cash_to_debt',
    },
    'calculated_metrics.cash_flow_metrics': {'free_cash_flow', 'free_cash_flow_growth'},
    'calculated_metrics.income_statement_metrics': {'revenue_growth', 'net_income_growth'},
    'calculated_metrics.earnings_metrics': {
        'latest_surprise_percentage', 'average_surprise_percentage',
        'beats_last_4_quarters', 'misses_last_4_quarters',
    },
}


def select_risk_evidence(evidence: dict) -> dict:
    """Current company evidence only, using the existing selected-catalog convention.

    Preserve original IDs/path/value and missing_data verbatim. Missing values are
    not fabricated or replaced; no risk scores or policy judgments are calculated.
    Portfolio policy and historical memory are never added to this evidence view.
    """
    return _select_evidence(evidence, _RISK_FIELDS)


def build_risk_context(
    evidence: dict,
    portfolio_context: PortfolioAnalysisContext | None = None,
    decision_memory: DecisionMemoryContext | None = None,
) -> SpecialistContext:
    """Attach portfolio policy and historical memory separately, without adapting either."""
    return SpecialistContext(
        ticker=evidence['ticker'], specialist_name='risk',
        research_evidence=select_risk_evidence(evidence),
        portfolio_context=portfolio_context, decision_memory=decision_memory,
    )


# One ordered activation boundary; shared models do not restrict specialist names.
from src.fundamental_analysis import analyze_fundamental_specialist
from src.risk_analysis import analyze_risk_specialist

ACTIVE_SPECIALISTS = {
    'fundamental': (build_fundamental_context, analyze_fundamental_specialist),
    'risk': (build_risk_context, analyze_risk_specialist),
}
