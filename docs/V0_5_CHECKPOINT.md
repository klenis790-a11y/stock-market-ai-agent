# Stock Market AI Agent — V0.5 Checkpoint

Repository checkpoint: 2026-09-11. This document describes implemented code and offline tests, not a claim of investment performance. Earlier milestone documents describe their own historical scope.

## 1. Project Objective

An investment research and decision-support system: externally supplied data → deterministic calculations → evidence construction → AI interpretation and risk assessment → recommendation → optional preservation → later descriptive evaluation. Reliability is pursued through explicit validation and provenance, not assumed from a provider or model.

This is not a magical stock-price predictor. No live trading, order placement or brokerage connection exists.

## 2. Completed Versions

| Version | Purpose and implemented capabilities | Architectural boundary | Deliberately excluded |
| --- | --- | --- | --- |
| V0.1 — Single Stock Research Agent | Research one ticker using financial statements, quotes, earnings, news and available transcripts; calculate metrics and produce structured `InvestmentAnalysis`. | Python retrieves/calculates/validates; OpenAI interprets supplied evidence. | Trading, price prediction engine and independent AI data retrieval. |
| V0.2 — Portfolio Awareness | User holdings/cash, valuation, position gain/loss, concentration and deterministic policy checks; portfolio-aware backend analysis. | Portfolio facts remain separate from company evidence; policy flags are not orders. | Optimization, rebalancing, brokerage synchronization. |
| V0.3 — Decision History & Outcomes | Decision builders, append-only SQLite records, separate outcomes/returns, ticker history, optional historical memory and explicit persistence. | Decision-time beliefs and later observations are separate; memory is secondary to current evidence. | Automatic outcome collection, strategy adaptation and benchmark retrieval. |
| V0.4 — Specialist / Multi-Agent Analysis | Fundamental and Risk specialists, ordered registry-driven execution and final synthesis using the existing final report contract. | Specialists advise; synthesis owns the final recommendation. | Debate, voting, concurrency, specialist scoring and additional agents. |
| V0.5 — Dashboard Interface | Six Streamlit pages, explicit research/portfolio loading, same-run specialist inspection, explicit save, read-only history and descriptive outcome summaries. | Presentation consumes backend objects; only the performance adapter adds the scoped descriptive aggregates. | Automatic research on navigation, automatic saving, trading and backtesting. |

## 3. Current End-to-End Architecture

`src/research_pipeline.py:run_stock_research` builds evidence once through `build_stock_evidence`: Alpha Vantage → `normalizers.py` → `research_snapshot.py` plus `calculations.py` → `evidence.py` → analysis.

The default backend path remains single-agent `analyze_investment`. With `use_multi_agent=True`, `multi_agent.run_specialists` creates ordered results, then `synthesis.synthesize_investment_analysis` returns the same `InvestmentAnalysis` type. Failures propagate; no single-agent fallback or automatic retry is introduced.

Optional history retrieval occurs after current evidence and before analysis; optional persistence occurs after successful validation. The dashboard adapter explicitly selects multi-agent mode, disables automatic persistence and memory retrieval, and retains a successful result in session state. Its later Save Decision action uses the existing V0.3 helper without rerunning research.

The portfolio-aware backend builds current company evidence, reuses its target quote for portfolio valuation, builds deterministic portfolio context, and supplies that context separately to analysis or specialists/synthesis. The dashboard Portfolio page currently performs inspection only; loading holdings does not inject them into standalone Research.

Later outcomes must be supplied independently. The history store reads them separately; Performance joins them to parent decisions for descriptive summaries. This is not an automated outcome pipeline.

## 4. Data Integrity Model

- **RETRIEVED FACT:** normalized provider data, with source/period context where supplied. Vendor sentiment is an annotation, not an independently verified conclusion.
- **CALCULATED METRIC:** deterministic Python output such as growth, margins or leverage ratios.
- **AI INTERPRETATION:** assessments and `InterpretationStatement` objects, including current vulnerabilities.
- **FORECAST:** `ForecastStatement` scenarios and thesis-invalidation conditions; not established facts.

The evidence package separates retrieved facts, calculated metrics and missing data. Deterministic catalog IDs such as `E001` resolve to package paths/values. Statements carry `evidence_refs`; specialist subsets retain original IDs. Final validation checks IDs against current evidence and requires coverage of the material-evidence checklist.

IDs are package-local provenance references, not globally stable historical identifiers. Historical IDs cannot be resolved against a new research catalog. Statement type is represented by Python types and collection placement, not a UI-invented classification.

Normalizers use `None` for unavailable/non-finite numeric values. Calculations guard missing inputs and invalid denominators. Missing financial evidence is tracked explicitly; optional retrieval failures can degrade to missing evidence. Required retrieval failures stop research. Prompt rules prohibit filling gaps from memory or inventing evidence. Structural validation cannot prove that every cited claim is semantically supported; substantive review remains necessary.

## 5. AI Architecture

The only active specialists in `src/specialists.py` are:

- **Fundamental:** operating quality, growth, profitability, cash generation and financial strength.
- **Risk:** downside, leverage, vulnerability, uncertainty and, when supplied, separately attributed portfolio risk context.

Both receive deterministic evidence selections and return generic `SpecialistAnalysis`: identity, summary, findings, risks, scenarios, confidence and missing data. They have no final recommendation field. The registry associates names with builders/analyzers; the sequential orchestration loop supports future registered implementations without specialist-specific shared fields.

The Portfolio Manager is the final synthesis role, not proof that holdings were supplied. It receives full current evidence separately from ordered specialist interpretations and optional portfolio/memory context. It produces the existing `InvestmentAnalysis`, including valuation/earnings assessments without pretending dedicated valuation/earnings agents exist.

Recommendations remain Buy, Accumulate, Hold, Trim or Avoid. Confidence is 0–100, an AI assessment rather than a calibrated price-move probability. It is not averaged across specialists. Instructions prohibit voting, require material disagreement to be considered, ground qualitative valuation in supplied metrics, and distinguish current risks from future scenarios. Temporal rules distinguish fiscal periods, reported dates, transcript timing and retrieval time.

The standalone pipeline's optional `on_specialists_complete` callback exposes defensive copies of same-run ordered results before synthesis. Observer exceptions propagate; copies protect synthesis from observer mutations. The return type remains `InvestmentAnalysis`. The dashboard publishes specialist capture alongside the final result only after success. The portfolio-aware pipeline does not currently expose this same callback.

## 6. Portfolio Architecture

`PortfolioInput` holds ticker, shares, average cost and cash. Parsing and dataclass validation normalize tickers and reject invalid amounts/duplicate holdings. `portfolio_data.py` uses the existing quote client, once per required holding; a known target price, including unavailable `None`, is reused rather than retried.

`build_portfolio_snapshot` calculates cost basis, position value, unrealized gain/loss and its percentage, total positions value, total portfolio value, position/cash weights, largest position, top-three weight, HHI and effective position count. Stock weights use total value including cash; HHI sums stock weights squared, excluding cash as a position. Effective count is its reciprocal when defined; this cash-inclusive denominator matters when interpreting concentration.

Missing prices preserve known position information but prevent aggregate valuation and weights. Zero cost basis leaves gain/loss percentage unavailable. The UI does not invent an aggregate unrealized-gain/loss metric absent from the snapshot.

`PortfolioRiskPolicy` defaults to 25% maximum single-position weight, 60% maximum top-three weight and 5% minimum cash weight. `assess_portfolio_risk` returns strict threshold findings and evaluability/missing-price notes, not trades.

Portfolio-aware recommendation reasoning **is implemented** in the backend and distinguishes stock attractiveness from portfolio suitability. The current dashboard Portfolio view is inspection; its Research workflow is standalone. Neither interface calculates an optimized allocation.

## 7. Decision Memory Architecture

`decision_history.py` deep-copies validated analysis into `DecisionRecord`, preserves supplied IDs or generates ticker/timestamp/short-UUID IDs, and delegates saving to `DecisionStore`. SQLite stores scalar columns plus deterministic JSON for structured statements/reviews.

`DecisionRecord` preserves recommendation, confidence, assessments, reasoning, bull/bear/supporting/risk statements, forecasts, missing data and material reviews. It does not archive the full evidence catalog, a reference-price field, original portfolio snapshot, original memory input or specialist results.

`DecisionOutcome` is separate: decision ID, evaluation timestamp/horizon, supplied stock/benchmark prices and returns. Decisions use a primary key; outcomes use `(decision_id, evaluation_horizon)` and an enforced foreign key. Duplicate inserts fail. There are no store update/delete methods. Saving an outcome does not rewrite a decision.

Dashboard saving is explicit and uses the centralized UTC timestamp helper at save time. It saves the displayed successful analysis, not the editable ticker box. Repeated saves reuse the saved ID so the same database rejects duplicates. New research clears stale result/save state. It creates no outcome and retrieves no memory.

History inspection uses SQLite read-only connections and ticker queries. Missing files are not created. Stored timestamps sort lexically, requiring consistent caller formats; the models do not enforce an as-of chronology. Historical memory retrieval is optional in backend research, newest-first with a limit and linked outcomes. Memory cannot become current evidence or satisfy current evidence requirements.

This separation enables later comparison with what was actually preserved, without silently inserting future knowledge into the original thesis. It does not by itself establish a complete point-in-time dataset.

## 8. Performance / Evaluation Architecture

`dashboard/performance_adapter.py` reuses the read-only ticker-history adapter. It joins stored outcomes to their parent decisions and retains rows with at least one finite numeric return. Each decision/horizon row is an observation; stock-evaluated count includes only rows with valid stock returns.

Implemented summaries: independent sample counts and means for stock, benchmark and excess returns; strictly positive stock-return count/rate; strictly positive excess-return count/rate. Missing or non-finite values are excluded independently, never treated as zero. Benchmark-only rows can contribute to benchmark statistics without contributing to stock statistics.

Breakdowns use original recommendation, literal stored horizon and broad confidence buckets `[0,50)`, `[50,60)`, `[60,70)`, `[70,80)`, `[80,90)`, `[90,100]`. Confidence observations are not calibration claims. A native recommendation-count chart appears with at least five stock-return observations and two recommendation groups; this is a display threshold, not statistical sufficiency.

V0.3's outcome builder computes `(end/start)-1` only with both prices and a positive start; otherwise return is `None`. Excess return is the difference when both returns exist. Returns are decimal and unannualized. Performance consumes stored returns; it does not recompute them from prices or validate an entire outcome collection methodology.

Different metrics may have different denominators. Pooled horizons/benchmarks may not be comparable; repeated outcomes for one decision are not independent. Positive stock returns do not prove that an Avoid/Trim recommendation was correct, nor represent trading P&L. No win-rate strategy score, simulated portfolio, costs, risk-adjusted return, drawdown or statistical significance test exists. No claim that the system beats the market is supported by this checkpoint; local outcome sample size was not audited.

## 9. Dashboard Architecture

`dashboard.py` routes six pages through a persistent sidebar; `ui_contracts.py` composes backend dataclasses. Streamlit-native components use a dark theme without a separate frontend framework.

- **Home:** compact session portfolio/research/risk status and navigation. It may read the explicitly selected history source/ticker; it does not discover databases or refresh prices.
- **Research:** explicit standalone multi-agent run, structured results and evidence references, followed by optional Save Decision. Same-run full catalog resolution remains unavailable through the current pipeline return value.
- **Portfolio:** explicit holdings/cash loading, existing backend valuation and deterministic policy display. It does not execute AI portfolio research.
- **Agent Room:** ordered same-run specialist details and separate final synthesis; generic rendering, honest context flags, no fake dialogue or execution animation.
- **Decision History:** explicit database/ticker selection and read-only preserved records, with later outcomes separately displayed. Unknown historical artifacts remain unavailable.
- **Performance:** explicit or known history source/ticker, stored outcome tables and descriptive aggregates with denominators and cautionary copy.

Expensive provider work requires Run Research or Load Portfolio. Navigation/rerenders reuse session results; they may read selected SQLite history but never initiate provider work. Failed research clears stale results. UI errors are sanitized; Research diagnostics allow only safe internal messages and determinable stages. Session state is not durable decision history.

## 10. Testing Strategy

The checkpoint verification runs **319 tests** using:

```sh
.venv/bin/python -m unittest discover -s tests
```

`tests/test_v01.py` through `test_v05.py` cover deterministic financial calculations, normalization/missing values, citation and material-review validation, portfolio calculations/policy and quote reuse, decision/outcome separation, copying, SQLite round trips/duplicates/foreign keys, memory ordering and prompt boundaries, specialist/synthesis contracts, failure propagation and pipeline exclusivity.

V0.5 tests use Streamlit AppTest, mocked pipeline/provider boundaries and temporary SQLite databases. They exercise explicit submission, no rerun on navigation, same-run specialist capture, stale-result clearing, saving, read-only history, outcome aggregates, chart thresholds and UI provenance labels. Tests also block network connections in relevant suites. No live Alpha Vantage/OpenAI requests are part of checkpoint verification.

Prompt-text tests establish that instructions reach mocked requests, not that future model prose will always obey them. Offline mocks do not establish provider availability, financial accuracy or real investment performance. Manual/live acceptance is a separate activity; no new live run was performed for this document.

## 11. Current Technology Stack

Python 3.12; standard-library dataclasses, JSON, datetime, UUID, sqlite3, urllib and logging; Alpha Vantage HTTP API; OpenAI Responses API through pinned `openai==3.8.0`; `streamlit==1.63.0`; unittest/unittest.mock and Streamlit AppTest; Git; Markdown documentation.

The current client configures `gpt-5.6-terra`, a 120-second OpenAI timeout, `max_retries=0` and `store=False`. Alpha Vantage uses urllib with a 30-second timeout and request pacing. These are repository configuration facts, not independently verified provider availability guarantees. Local credentials stay in the environment/local ignored `.env`; dashboard bootstrap preserves existing environment values. No ORM or additional database service is used.

## 12. Key Engineering Decisions

- Keep formulas deterministic so ratios and portfolio facts are reproducible and testable.
- Build evidence once, retain canonical IDs in specialist subsets, and validate final citations against current evidence rather than agent agreement.
- Preserve unknowns explicitly so absent evidence cannot silently look like zero or certainty.
- Use structured responses and typed interpretation/forecast collections for inspectable output, while acknowledging semantic-validation limits.
- Run specialists sequentially with fatal failures to prevent silently incomplete synthesis; no retries or fallback analysis.
- Expose same-run results through an optional defensive-copy callback rather than rerunning analysis for UI visibility.
- Save only explicit accepted results; keep observations separate from beliefs to reduce hindsight contamination.
- Use small append-only SQLite tables and standard-library serialization before introducing database infrastructure.
- Keep historical pages read-only and separate from live research; preserve the backend's public return contract.
- Exclude trading and automatic adaptation so research quality can be examined before adding execution risk.

## 13. Known Limitations

Provider data is latest available, not necessarily real-time or complete; publication periods and retrieval timestamps differ. Quotas, network failures and provider availability can stop runs. Optional quote/news/transcript failures degrade, but mandatory retrieval failures remain fatal.

Comparative peer/historical valuation benchmarks and dedicated forward-estimate coverage are incomplete; neither valuation nor earnings has its own specialist. Exact IDs and strict schemas cannot prove every financial assertion or forecast is sound. No deterministic NLP classifier judges all prose.

Only Fundamental and Risk are active. No technical/chart analysis, concurrent agent debate, automated outcome collection, benchmark retrieval, trading or brokerage exists. Portfolio-aware backend analysis is implemented, but dashboard Research does not use the Portfolio page's holdings or automatically load memory.

The historical archive lacks full evidence/source/context snapshots. Timestamp sorting is lexical; no enforced historical cutoff or semantic horizon normalization exists. A delayed dashboard save timestamps preservation, not necessarily the earlier research execution. SQLite is local plaintext; authentication, deployment and access controls are outside the implemented dashboard scope.

Performance is ticker-scoped descriptive analytics over caller-supplied stored returns, not a backtest or a verified market-beating strategy. No audited production outcome dataset size or general accuracy claim is established here.

## 14. Future Backlog

**Near-term candidate:** stronger evaluation infrastructure: outcome provenance, disciplined observation timing, point-in-time archives, comparable horizons/benchmarks and larger legitimately collected samples. The next milestone is not yet finalized.

**Future options, not implemented:** structured OHLCV/time-series ingestion; deterministic technical features; a technical-analysis specialist; candlestick/volume analysis; short-term trading research; preservation of predictions/signals and evaluation of both positive and negative outcomes; backtesting with strict anti-look-ahead controls; expanded benchmark comparison; paper trading.

Robust chart research should primarily use structured market data, deterministic features and rigorous historical evaluation. Sending chart screenshots to an LLM is not a substitute; visual interpretation could later supplement that foundation.

Brokerage integration should follow extensive testing. Any eventual live trading should require deterministic risk controls and human approval. These are planning constraints, not existing execution capabilities.

## 15. Skills Demonstrated

| Skill | Repository evidence |
| --- | --- |
| Requirements and scope control | Staged contracts, narrow opt-in changes, documented unavailable states. |
| Python/API integration | Provider clients, normalization, deterministic calculations and error handling. |
| LLM/system design | Structured schemas, evidence selection, specialist registry, synthesis and prompt safeguards. |
| Data modeling and temporal integrity | Dataclasses, separate decision/outcome tables, copy isolation and foreign keys. |
| Testing and Git workflow | Versioned unittest suites, mocks, temporary databases and documented release checks. |
| Financial/risk analysis implementation | Reproducible margins, cash flow, leverage, portfolio weights and configured concentration limits. |
| UI/product architecture | Streamlit pages, thin adapters, explicit actions, session reuse and progressive disclosure. |

These demonstrate implementation and engineering judgment, not professional investment certification or proven trading skill.

## 16. Interview Talking Points

1. **Why not let the LLM calculate ratios?** Python formulas are reproducible and testable; the model can focus on interpreting supplied results.
2. **What does a citation prove?** The ID resolves to supplied evidence. It does not automatically prove the accompanying interpretation is correct.
3. **How do agents share evidence?** A current package is built once; deterministic selectors preserve original IDs while giving each role relevant inputs.
4. **Why separate specialist advice from synthesis?** Role-specific interpretation should not become a vote or a retrieved fact; final synthesis independently owns the recommendation.
5. **How does Agent Room avoid extra API calls?** An optional callback copies already-produced results into the successful session result without changing the final return contract.
6. **How is hindsight controlled?** Original records are append-only and outcomes separate; UI history never fills old gaps with current research. Full point-in-time enforcement remains future work.
7. **Why SQLite?** A local standard-library store supplies durable records, transactions, unique keys and foreign keys without an ORM or service.
8. **Why explicit saving?** A research result can be inspected before preservation; rerenders must not create duplicate historical decisions.
9. **Why is Performance deliberately modest?** Stored outcome means are descriptive and sample-dependent; they do not represent execution, costs, independent samples or a proven edge.
10. **What do tests miss?** Mocks verify contracts and failure behavior, not real provider uptime or semantic correctness of every live model claim.
11. **What is the portfolio/UI boundary?** Backend portfolio-aware analysis exists; the current standalone dashboard does not silently apply separately loaded holdings.
12. **What would precede technical trading features?** Structured time-series data, deterministic features, signal preservation and anti-look-ahead evaluation—not screenshot-only reasoning.

## 17. CURRENT PROJECT STATE

CURRENT VERSION: V0.5 COMPLETE

COMPLETED: V0.1 evidence-grounded single-stock research; V0.2 deterministic portfolio analysis and backend portfolio-aware research; V0.3 explicit history, separate outcomes and optional memory; V0.4 ordered specialist analysis and final synthesis; V0.5 six-page dashboard with explicit research/save and read-only history/outcome inspection.

NEXT: The next milestone has not yet been finalized and should be selected based on project priorities.

BACKLOG: Stronger evaluation and outcome provenance; technical time-series research; disciplined backtesting; possible paper trading and much later controlled brokerage/live execution.

DECISIONS: Preserve deterministic calculations, current-evidence authority, explicit unknowns, typed forecasts, generic specialist contracts, same-run capture, opt-in persistence, decision/outcome separation, truthful historical displays and no hidden provider calls or trading.
