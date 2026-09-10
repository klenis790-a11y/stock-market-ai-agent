# V0.5 dashboard contracts

The dashboard presents the engine. Direction: presentation → application/pipeline
interfaces → domain models. No Streamlit, rendering, new calculations or application
adapter is implemented in this step. Dark-mode-first, restrained, information-dense
presentation with progressive disclosure is the future design direction. Avoid
simulated agent conversations, decorative reasoning animations and implied live data.

Navigation is the immutable `DASHBOARD_PAGES` tuple in `src/ui_contracts.py`.
Page containers compose backend models; they do not replace or serialize them.
`UISectionAvailability` separates backend support from data availability and requires
an explanation for unavailable sections. An omitted availability entry means unknown,
not supported/ready. Application adapters must supply consistent objects and statuses;
these containers do not validate financial truth or perform retrieval. Empty lists
mean no supplied records/results, not proof that no historical records exist. None
means unavailable, not zero. Referenced backend objects must be treated as read-only.

## Capability map

| Destination / purpose | Existing suppliers and supported data | Partial/unavailable data; future work | Presentation boundary |
|---|---|---|---|
| Home / Command Center: overview and quick research entry | `PortfolioSnapshot`, `PortfolioRiskAssessment`, `InvestmentAnalysis`, `DecisionStore.get_decisions_for_ticker`: value, cash, position count, policy flags and current/stored recommendations | No global recent-activity query, durable run activity feed or default portfolio/session service. A future application adapter must retain actual run results; overview availability must reflect what it has. | Show summaries and links, not duplicate all page detail. Do not invent freshness, activity or advice from flags. |
| Research: company workspace with expandable evidence | `run_stock_research`, `run_portfolio_aware_research` return `InvestmentAnalysis`; `build_stock_evidence`, `build_research_snapshot`, `build_evidence_package`, `build_evidence_catalog`, `resolve_evidence_id` supply normalized facts, calculated metrics and provenance | Normal pipelines return only final analysis, not a combined snapshot/evidence/result bundle. A future backend/application capture interface is required for same-run drill-down. Do not rerun providers to reconstruct the original evidence. | Display assessments, recommendation/confidence, bull/bear, supporting evidence, risks, scenarios, invalidation, material reviews and missing data from existing objects. Evidence lives here, not in primary navigation. |
| Portfolio: holdings and portfolio suitability | `build_live_portfolio_snapshot`, `build_portfolio_snapshot`, `assess_portfolio_risk`, `build_portfolio_analysis_context`; existing models expose shares, cost, value, gain/loss, weights, cash and concentration | Portfolio pipeline callback exposes target context, not full holdings snapshot. No persistent portfolio exists. Future adapter must retain snapshot and policy results from the same workflow. | Never recompute weights or create risk labels. Missing prices imply unavailable totals/weights under existing rules. Company attractiveness differs from portfolio suitability. |
| Agent Room: actual specialist work and synthesis | `ACTIVE_SPECIALISTS`, `run_specialists` → `MultiAgentSynthesisContext.specialist_results`; `synthesize_investment_analysis` → `InvestmentAnalysis` | Normal pipeline does not expose intermediate results or execution events. No per-agent timing/status stream or stored specialist history. Future capture/events support is needed; do not rerun agents merely to populate UI. | Generic ordered results, no fundamental/risk-specific fields. Render summaries/findings/risks/scenarios/confidence/missing data and backend evidence. Registration does not prove execution or success. |
| Decision History: preserved beliefs and later observations | `DecisionStore.get_decision`, `get_decisions_for_ticker`, `get_outcomes_for_decision`, `build_decision_memory_context`; `DecisionRecord`, `DecisionOutcome` | Records preserve assessments, bull/bear, risks, scenarios, references and review prose. They do NOT archive decision-time quote, full evidence/catalog/transcript, portfolio snapshot/context or exact historical memory supplied to that run. `portfolio_assessment` is prose only. No all-ticker history query. Archiving absent artifacts would require later backend work. | Match outcomes by decision_id without rewriting decisions. Mark unarchived artifacts unavailable. Never resolve old IDs against a current catalog or label a newly built memory view as the original run's input. |
| Performance: reserved evaluation workspace | Stored `DecisionOutcome` has supplied-price stock/benchmark/excess returns for horizons; raw observations remain viewable in History | No aggregate analytics, benchmark retrieval, drawdown, win rate, confidence calibration or specialist contribution evaluation. PerformancePageData defaults to unsupported/unavailable. Future legitimate data and evaluation services required. | No charts/metrics manufactured from insufficient outcomes, no market-beating claim. No performance engine in V0.5 Step 1. |

## Evidence and temporal integrity

Preserve RETRIEVED FACT, CALCULATED METRIC, AI INTERPRETATION, FORECAST and
MISSING / UNAVAILABLE DATA as distinct meanings. Research holds the exact
backend-produced evidence package and catalog references. IDs and original path/value
resolution belong to `src/evidence.py`; the UI displays backend resolution results,
never generates IDs or reconstructs provenance. Specialist outputs remain interpretations,
not facts; portfolio context is separate from company evidence. Historical memory is
historical only and cannot fill missing current evidence. Source fiscal/trading/report
periods remain distinct from generation timestamps; “latest available” is not real-time.

## Information hierarchy and extensibility

Guide users through: conclusion → reasoning → supporting evidence → risks → portfolio
impact → prior beliefs → observed outcomes. Home stays concise. Research progressively
reveals evidence, Agent Room reveals actual structured specialist analyses. A future
registered specialist appears via the same generic name/result collection, without a
shared-model change. No fake conversations or inferred execution states are permitted.

The existing single-agent default and optional multi-agent mode remain backend choices.
No recommendation semantics, prompts, retrieval, persistence or shared domain models
change for UI convenience. Missing capabilities above are documented gaps, not work
implemented here. No UI framework or dependency has been added.
