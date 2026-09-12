# V0.6 — Evaluation Infrastructure Design

Status: design proposal only, 2026-09-11. No production behavior, schema, dependencies or outcomes are changed by this step. Repository baseline includes tags `v0.5` and `v0.5.1`. Proposed names below are contracts for implementation planning, not existing modules or approved market-data integrations.

## 1. Repository findings and problem definition

Reviewed README, the V0.5 checkpoint, `src/models.py`, decision builders/store/memory, production pipelines, dashboard adapters/contracts and versioned tests. The source is authoritative where older milestone documentation describes a narrower scope.

Current capabilities:

- `DecisionRecord` preserves recommendation, 0–100 confidence, optional free-text investment horizon, assessments, reasoning, structured interpretations/forecasts, missing data and material reviews. Evidence **references and reviews** are preserved, not a complete evidence archive, source-price snapshot, portfolio snapshot or original memory input.
- `build_decision_record` copies collections and generates/preserves IDs. `save_analysis_decision` delegates to `DecisionStore`.
- SQLite `decisions` is keyed by decision ID. `decision_outcomes` is keyed by `(decision_id, evaluation_horizon)` with an enforced foreign key. There are insert/query methods, **no update/delete outcome API**. Existing rows cannot hold two methodologies for the same decision/horizon.
- `DecisionOutcome` stores evaluation timestamp/horizon, stock start/end prices and return, benchmark ticker/start/end prices/return, and excess return. It validates nonempty identifiers/text and finite nonnegative prices, but does not enforce chronology, return consistency, probability semantics or a price methodology. Returns themselves are not fully validated by this dataclass.
- `build_decision_outcome` computes unannualized decimal `(end/start)-1` when both prices exist and start is positive, otherwise `None`; excess is stock minus benchmark when both exist. Negative prices fail. A zero end price is permitted; missing/zero start prevents a return.
- Read-only ticker history sorts decisions lexically newest-first, then ID; outcomes lexically oldest-first, then horizon. No all-ticker store query or semantic horizon normalization exists.
- V0.5 Performance joins stored outcomes to decisions, keeps rows with at least one finite return, and aggregates each return field independently. It displays counts, means, positive/outperformance rates and recommendation/horizon/confidence groupings. A benchmark-only row can contribute to the benchmark mean without contributing to stock count. It is descriptive, not a rigorous evaluation cohort.
- Sources are explicit local paths; read-only SQLite uses URI `mode=ro`, missing files are not created. `.env`, local database extensions and SQLite sidecars are ignored. No historical daily-price or market-calendar service is currently implemented; the quote endpoint is not a historical observation archive.

V0.6 addresses reproducible, deterministic, temporally correct, benchmark-aware, horizon-aware and methodology-aware evaluation. It must answer what was believed, what happened, and how the result behaves under rules declared before inspecting outcomes. **V0.6 is not intended to prove that the system beats the market.**

## 2. Evaluation principles

1. Original beliefs are immutable: never rewrite a decision with later information.
2. Decisions and observed outcomes remain separate. Evaluation metadata is a third concern, not new decision-time evidence.
3. Python computes returns, calendar resolution and summaries; no LLM assigns numeric outcomes.
4. Missing/invalid observations stay unavailable, not zero, safe or successful.
5. Declare methodology, benchmark, horizons, eligibility and cohort before examining results. Preserve registration time.
6. Preserve all eligible decisions and both favorable/unfavorable results; display exclusions and overdue missing observations.
7. Observed prices, calculated returns and interpretations of decision quality have different provenance.
8. Evaluation introduces no trading, recommendation adaptation or confidence changes.
9. Reproduction uses stored inputs and pinned rules, never fresh prices masquerading as the original observations.

## 3. Decision time

Current `utc_decision_timestamp()` returns UTC `YYYYMMDDTHHMMSS.ffffffZ` using timezone-aware Python UTC. Precision is microseconds, but precision does not establish the event being timestamped: CLI captures before the research call; dashboard Save Decision captures save time; API callers can supply arbitrary nonempty strings. Old rows may be date-only, naive or inconsistent. Lexical ordering across mixed formats is not chronological normalization.

For prospective V0.6 evaluations define **decision availability time** as the instant the fully validated final analysis becomes available to its caller. This must be captured centrally in a future narrowly scoped integration, separately from save time and evidence-as-of time. Use aware UTC datetime internally and canonical RFC3339 `YYYY-MM-DDTHH:MM:SS.ffffffZ` in the new evaluation structures. Market timezone/session conversion is explicit and separate. Do not rewrite existing `DecisionRecord.decision_timestamp` strings.

A parser may recognize the existing compact UTC format and explicit-offset timestamps. Reject naive/date-only values for prospective intraday eligibility unless additional trustworthy provenance exists. Never invent midnight or assume a machine timezone. Preserve the original string, parsed value, provenance and time-quality status. Existing records with ambiguous event meaning remain `legacy_time_unverified`; a documented save-time proxy is a separate retrospective cohort, not a recovered original decision time.

Prospective registration occurs when a decision is explicitly accepted/saved, before its evaluation baseline session. A delayed save after that baseline cannot claim prospective enrollment. Record both analysis availability and enrollment timestamps. Clock precision does not guarantee clock accuracy; future integration tests must verify UTC conversion and event ordering.

## 4. Evaluation horizons

Initial recommendation: **90 calendar days and 365 calendar days**, labeled exactly as such, for a short/intermediate versus longer fundamental-research view. Do not equate these to every meaning of “3 months” or “12 months.” Decline a one-week horizon for the initial fundamental cohort; extra short horizons increase scope and selection freedom.

Use explicit horizon objects with stable ID, integer length and unit (`calendar_days` initially; reserved `trading_sessions` later). The nominal target is baseline session date plus 90/365 calendar days; resolve to the first eligible regular-session close on or after that date. This anchors the measured holding window to the actual baseline, not an unrelated research timestamp. Store nominal target and actual endpoint separately.

Calendar days simplify long-term comparisons but produce different session counts. Trading-session horizons make short-term windows precise but require an authoritative schedule. V0.7 may add 1, 5 and 20 trading-session horizons through the same unit contract; do not activate them in V0.6. Free-text legacy investment/evaluation horizons are not automatically mapped. Any explicit mapping is versioned and retrospective.

## 5. Outcome observation definition and ownership

| Concept | Existing location | Proposed treatment |
| --- | --- | --- |
| Original decision ID, timestamp, recommendation/confidence | DecisionRecord | Reference unchanged; retain original timestamp string. |
| Reliable availability/enrollment time and time-quality status | Absent | New evaluation enrollment metadata, not inferred decision facts. |
| Horizon label | DecisionOutcome free text | Keep legacy text; new horizon ID/unit/count frozen in enrollment. |
| Stock/benchmark start/end prices and returns | DecisionOutcome | Reuse numeric return semantics in new versioned observations; do not overwrite legacy rows. |
| Benchmark symbol | Optional DecisionOutcome field | Explicit frozen policy, plus instrument identity/currency provenance. |
| Nominal target, resolved session dates | Absent | Deterministically derive from pinned policy/schedule, persist resolution for audit. |
| Actual stock/benchmark price timestamps | Absent | Required provenance per supplied price; distinguish from observation ingestion time. |
| Source, retrieval timestamp, adjustment policy, calendar version | Absent | New observation metadata; source labels alone are not verification. |
| Methodology ID and rule snapshot | Absent | Immutable enrollment reference and snapshot. |
| Evaluation run-as-of time, eligibility/status/reason | Absent | Explicit audit state/derived report status; not a return. |
| Trade fills, costs, positions, MFE/MAE | Absent | Out of V0.6. |

An observation is a source-attributed measurement of a predefined instrument/window, not a judgment about an agent. Reference prices selected after decision availability are **evaluation baselines**, not prices the model knew. Keep them out of decision evidence and memory presented as decision-time facts.

## 6. Price observation policy

**Initial proposed scope:** USD US-listed instruments with a verified compatible regular-session calendar and supplied daily official close observations. This is an eligibility restriction, not a claim every stored ticker meets it.

Use the close of the **first full regular trading session whose open is strictly after decision availability and enrollment** as the baseline. During-session, at-open, after-close or pre-market decisions follow this same deterministic rule. Thus a during-session decision uses a later session's close; a before-open decision can use that day's close if both times precede the open. Exact equality with open moves to the next session. This deliberately conservative daily convention avoids guessing quote freshness or intraday fills. It is an observation proxy, **not a claim that execution at the closing price was achievable**.

The endpoint is the regular-session close on/after the nominal horizon date. Weekend/holiday resolution uses an explicit exchange schedule, not weekday arithmetic. A scheduled half-day uses its actual close. If the schedule is unavailable, resolution is unavailable. A missing expected price is a data gap: do not shift to a later available bar, forward-fill, use today's quote or drop the decision from denominators. Mark overdue/unavailable and allow an explicit later observation for the originally resolved session.

Initial return basis: **split-consistent price return, excluding cash dividends**, not total return. Require documented adjustment basis and comparability at both endpoints for stock and benchmark. Never mix raw and adjusted prices. Prefer a supplied, provenance-backed split-only series; if its semantics cannot be established, the result is ineligible for the rigorous cohort. Merger, delisting, symbol-identity discontinuity or unresolved corporate action becomes an explicit exception requiring an approved future policy, not silently surviving-symbol prices or an assumed zero.

Implementation gates: verify schedule provenance/coverage, session timezone, early closes, daily-close timestamp meaning, historical observation availability, licensing and split-only adjustment semantics before enabling a production import source. Current clients cannot supply this policy automatically. No new endpoint is authorized by this design. Retain raw supplied observation/provenance and adjustment vintage; reproducing an old report must not silently adopt provider revisions.

## 7. Benchmark policy

Propose one explicit initial default: **VOO as a comparison instrument**, confirmed and frozen in the methodology before observation. It is not the S&P 500 index itself and price return excluding dividends is not total index performance. No sector benchmark selector in the first cohort.

Stock and benchmark must use the same resolved baseline/end sessions, compatible currency and identical adjustment/return basis. Do not move one side to a different date to fill a gap. Record each price's actual timestamp and verify session alignment. Missing benchmark observations leave benchmark/excess return unavailable while preserving a valid stock return.

Keep raw stock and excess returns separate. Paired comparisons use only aligned pairs, with paired stock/benchmark means from the **same** observations. Benchmark outperformance is not recommendation correctness, risk-adjusted alpha or trading profit. Never infer a missing benchmark price from an index name/date.

## 8. Recommendation semantics

Preserve Buy, Accumulate, Hold, Trim and Avoid exactly. V0.6 reports observed stock/benchmark/excess returns and original recommendation without automatic “correct/incorrect,” winner/loser or success scores.

Buy/Accumulate describe favorable research/allocation judgments, not recorded fills. Hold is not a bet that prices are unchanged. Trim/Avoid are not short positions; avoided downside can be discussed as a separate descriptive lens but cannot be quantified as money saved without a declared counterfactual position and execution policy. Postpone categorical scoring until an explicit prospectively registered methodology defines the proposition being tested. Never negate Trim/Avoid returns to manufacture strategy P&L.

## 9. Confidence evaluation

Confidence currently measures evidential support on 0–100, not a probability. A score of 70 is not a 70% chance of success. Retain V0.5's broad continuous bands `[0,50)`, `[50,60)`, `[60,70)`, `[70,80)`, `[80,90)`, `[90,100]` for comparability.

Show “Observed outcome summary by confidence,” stratified by recommendation, horizon and methodology. Report counts, means/medians and missing paired samples. No Brier score, reliability probability plot, recalibration, learned weights or automatic confidence adjustment. There is no universal sample cutoff that makes a relationship meaningful; even large counts may be dependent or regime-specific.

## 10. Small rigorous metric set

V0.6 should retain simple means/rates and add medians plus **coverage accounting**, rather than trading statistics:

- Unique enrolled decisions; expected decision/horizon evaluations; not-yet-due, due, evaluated, missing/invalid and excluded counts with reasons.
- Valid stock count, mean/median stock price return and strictly-positive-return count/rate (zero is not positive).
- Valid aligned benchmark-pair count; paired mean stock return and mean benchmark return; mean/median excess return; strictly-positive excess count/rate.
- Breakdowns by original recommendation, registered horizon and confidence band within a methodology/benchmark/basis cohort.

Zero denominators yield unavailable metrics. Count only one accepted observation per enrollment/window/version. Never pool methodology versions, price bases or different horizons as one headline statistic. Show unique decisions alongside horizon observations to expose dependence. Preserve a separate legacy descriptive view rather than upgrading unverified outcomes to rigorous status.

These are decision-level statistics. Sharpe, Sortino, portfolio drawdown, CAGR and trading win/loss require an explicit portfolio/strategy/execution time series, financing and cost assumptions; none belongs in initial V0.6.

## 11. Sample-size honesty

Always show the denominator next to each metric and eligible/missing coverage, not just favorable completed cases. At 1 observation there is a case study; at 5, 20 or 100 there are larger descriptive samples, **not** automatic evidence of skill. Display a standing warning about limited/dependent samples, selection and market regimes. Do not declare statistical significance at any threshold. Chart thresholds are presentation choices only. Report cohort dates and distinct decision/instrument counts when available; no inference of independent observations from row count.

## 12. Outcome collection

| Approach | Benefit | Limitation | V0.6 recommendation |
| --- | --- | --- | --- |
| Manual supplied observations | Small, auditable, no new provider dependency | Entry errors and selection/provenance risk | Initial explicit entry/import with required metadata and validation. |
| Explicit user-triggered refresh/import | Reproducible action over all due enrollments | Requires validated historical source semantics | Support explicit batch validation/import of supplied observations; defer provider refresh until separately approved. |
| Scheduled collection | Convenience | Operational scheduling, retries and source lifecycle | Postpone. |

First workflow: register a fixed methodology/cohort/horizons → resolve due windows with supplied verified schedule → explicitly preview supplied prices/provenance → validate → confirm append-only persistence → deterministic report. Preview must not hide missing or unfavorable rows. Never import fabricated outcomes just to populate a UI. No background jobs, provider fetches or AI review is required.

Due status is computed from explicit `as_of` UTC time, not inferred from a future price. Missing attempts remain auditable as unavailable observations/reasons; a later valid append can resolve availability without deleting the earlier record. Prospective enrollment before baseline is mandatory for the prospective label. All existing already-observed history is retrospective unless registration provenance establishes otherwise.

## 13. Point-in-time safeguards

- Freeze cohort membership, benchmark, horizons and policy before baseline; do not cherry-pick evaluated survivors.
- Capture availability/enrollment separately from retrieval/save times; a future baseline is never inserted into old evidence.
- Resolve stock and benchmark sessions once from a pinned calendar; reject mismatched timestamps/window endpoints.
- Preserve immutable observation inputs and methodology snapshots; no automatic “latest adjusted price” replacement.
- Expose missing, delisted/unresolved and invalid observations in coverage, not just successful returns.
- Store prospective versus retrospective provenance. Applying new rules to old outcomes is a labeled reanalysis, not a prospectively tested method.
- Do not rewrite DecisionRecord, evidence IDs, confidence or recommendation. Current Research/session/portfolio data cannot fill historical gaps.
- Tests use frozen clocks and fixtures containing tempting future observations and confirm that they cannot alter earlier resolution or evidence.

This limits hindsight but cannot prove a human never viewed a price before manual entry. Report that limitation; prospective system registration and complete cohorts improve auditability rather than guaranteeing absence of bias.

## 14. Methodology versioning

Use a small immutable Python rule definition plus canonical JSON snapshot and content hash, identified by an explicit version such as `fundamental-price-v1`. Include benchmark policy, currency/universe, horizon unit/length, calendar identity/version, baseline/endpoint rules, adjustment basis, exclusions and aggregation rules. Store the snapshot/hash with enrollment; a version string alone cannot recover changed code.

Changing any material rule requires a new version, not mutation. Reanalysis remains separate and cannot silently replace earlier results. No plugin framework, dynamic discovery or general configuration service. Implementation code version may also be recorded for reproducibility.

## 15. Schema change analysis

**A — No change:** reuses existing rows but cannot preserve enrollment time, actual observation dates, source/basis or multiple methodologies. Suitable only for legacy descriptive metrics, not the V0.6 goal.

**B — Optional columns on DecisionOutcome:** small superficially, but leaves one-outcome-per-horizon primary key, ambiguous legacy defaults and an explicit deserializer (`DecisionOutcome(**dict(row))`) that would break on extra columns unless old readers change. It also cannot register an evaluation before an outcome exists cleanly.

**C — Recommended additive evaluation structures:** keep existing tables/models untouched. Propose two narrow new tables in the same explicitly selected SQLite file: an immutable **evaluation enrollment** (decision foreign key, availability/time provenance, enrollment time, methodology snapshot/hash, horizon and resolved target metadata) and append-only **evaluation observations** (enrollment foreign key, price/return payload, timestamps/source/basis, status/reason and revision/supersession provenance).

Exact DDL is deferred to contract implementation review. Enforce one enrollment per decision/horizon/methodology/cohort; observations have unique IDs and idempotency keys for the same supplied input. Accepted corrections append a linked revision with reason; conflicting unlinked valid observations fail rather than selecting the most favorable. Reports pin observation IDs and report-as-of time. No automatic overwrite or “latest wins” ambiguity.

Reuse V0.3's return helper as a numeric construction step where compatible, but do not automatically dual-write legacy `decision_outcomes`: its key cannot encode methodology revisions. Existing DecisionOutcome remains available unchanged for old workflows; the new rigorous report reads the new structures. Legacy observations can be referenced/imported only with honest missing-provenance labels, never fake metadata.

Future write-mode initialization creates only absent additive tables in a transaction; no destructive migration, backfill or read-mode initialization. Test opening old databases with both old code paths and new readers (new structures absent → unavailable). No migration library is necessary. This is the smallest safe option once prospective enrollment and methodology provenance are required.

## 16. Future V0.7 compatibility

Reserve horizon units and explicit timestamp/calendar contracts, not technical fields in InvestmentAnalysis. V0.7 can define a separate research-signal model with availability time, horizon, confirmation/invalidation, methodology and observation linkage; V0.6 need not implement its enum or table now. Later observations may include forward return, benchmark-relative return, MFE/MAE and condition occurrence based on a pinned intra-window path. Endpoints alone cannot establish MFE/MAE. No future metric is fabricated from current DecisionOutcome.

## 17. V0.7 Technical Research Requirements Preserved for Future Work

A. **Structured OHLCV pipeline:** normalized time-series data is primary.

B. **Market calendar and timestamps:** explicit timezone/session semantics for every bar, snapshot, signal and outcome; deterministic pre-market, regular session, after-hours, closed periods, weekends, holidays, half-days and missing bars. Do not hard-code weekdays as a market calendar.

C. **Corporate actions:** explicit split, dividend, merger and symbol-change policy with instrument continuity. Never mix raw/adjusted series silently.

D. **Data quality before indicators:** required bars, ordered/unique timestamps, valid OHLC relationships, sufficient history and missing-bar checks. Insufficient history is unavailable; never silently shorten windows.

E. **Deterministic features:** candidates include moving averages, trend, RSI, MACD, ATR/volatility, volume behavior, relative strength, momentum, gaps and support/resistance. Final feature set must remain deliberately small.

F. **Deterministic support/resistance:** Python derives candidate levels under explicit rules; the analyst interprets candidates, never invents numerical levels from visual intuition.

G. **Feature/version provenance:** preserve timeframe, parameters such as RSI(14)/SMA(50), feature methodology and calculation versions for reproduction.

H. **Provider abstraction:** normalized OHLCV contract independent of Alpha Vantage, Alpaca, Polygon/Massive or other vendors. Implement one source initially if justified; snapshot provenance includes provider, symbol/instrument, timeframe, data window, timestamps, adjustment policy and calculation version.

I. **Completed-bar / point-in-time rule:** initially use completed bars only. A 10:17 signal cannot use final OHLC from an hourly candle closing at 11:00; a midday daily signal cannot use the eventual daily close. Bar availability time matters, not just bar start label.

J. **TechnicalSnapshot:** structured deterministic technical evidence plus metadata.

K. **Technical evidence catalog:** reproducible references scoped to the snapshot; AI interprets evidence rather than creating facts.

L. **Technical specialist:** initially one dedicated Technical Analyst, not a collection of new agents.

M. **Signal contract:** short-term signals are conceptually separate from Buy/Accumulate/Hold/Trim/Avoid. Bullish/Neutral/Bearish is a candidate vocabulary, not finalized in V0.6.

N. **Explicit horizon:** every technical signal must declare its evaluation window, potentially 1, 5 or 20 trading sessions.

O. **Confirmation/invalidation:** explicit conditions supported by deterministic evidence where possible; preserve original conditions and temporal occurrence semantics.

P. **Research signal versus hypothetical trade:** technical evidence → research signal → signal evaluation is separate from signal → strategy → hypothetical trade → risk controls → execution. Measure signal, strategy and execution quality separately.

Q. **Predeclared outcomes:** define forward returns, benchmark/excess returns, MFE/MAE and confirmation/invalidation occurrence before inspecting results. Specify intrabar ambiguity and data requirements later, not ad hoc after an outcome.

R. **Positive and negative preservation:** retain winning, losing, neutral and unavailable signals/results, not selected successes.

S. **Learning from outcomes:** future evaluation/retrieval/analysis may examine successes and failures. This does not authorize autonomous retraining, self-modifying strategies or reinforcement learning from tiny samples.

T. **Charts for humans:** candlesticks, volume, moving averages and deterministic levels visualize the structured data.

U. **Visual interpretation is supplementary:** never design “screenshot → LLM → trade”; structured OHLCV and deterministic features remain primary.

V. **No execution in V0.7:** technical analysis, signal generation, preservation and evaluation only; no trade execution.

## 18. Future V0.7 implementation phases

Planning only: V0.7A Market Data Foundation → V0.7B Deterministic Technical Features → V0.7C Technical Snapshot & Evidence → V0.7D Technical Analyst & Signal Contract → V0.7E Signal Persistence → V0.7F Evaluation Integration → V0.7G Dashboard. Create none of these modules in V0.6 Step 1.

## 19. Proposed V0.6 implementation sequence

| Step | Objective / likely files (proposed) | Required tests | Boundary / non-goals |
| --- | --- | --- | --- |
| A — Contracts and registration | New `evaluation.py` or focused contracts module; prospective availability/enrollment integration points in pipelines/save adapter only after review | UTC parsing, legacy classification, immutable methodology, enrollment before baseline | Preserve InvestmentAnalysis and DecisionRecord; no collection or AI changes. |
| B — Window and price validation | Focused evaluation functions with injected session schedule; reuse decision-history return builder | Calendar fixtures, exact-open rule, half-day, missing prices, aligned benchmarks, corporate-action incompatibility | No provider integration, new indicators or weekday-only calendar approximation. |
| C — Additive persistence | Narrow evaluation store and explicit initialization over existing SQLite | Old DB compatibility, FKs, idempotency, append-only revisions, atomic writes, no read-mode creation | No destructive migration, legacy outcome overwrite or ORM. |
| D — Explicit observation workflow | Small CLI/application adapter for registration and supplied observation preview/confirmation | Missing/rejected inputs, overdue tracking, all cohort members retained, safe errors | No scheduled jobs, prices fetched automatically, arbitrary retrospective “prospective” enrollment or outcomes made by AI. |
| E — Reproducible reports | Domain evaluation aggregation; dashboard performance adapter consumes it | Cohort coverage, medians, paired denominators, grouping, version/as-of separation | Preserve legacy descriptive mode; no portfolio backtest or strategy scores. |
| F — Dashboard and final audit | Explicit evaluation controls and provenance/coverage displays, README/tests | UI read/write separation, no navigation-triggered writes/provider calls, full regressions and manual fixture audit | No V0.7 features or trading; production data-source/calendar capability gate must pass before prospective claims. |

Six steps, with implementation reviews before changing interfaces or schema. Most return arithmetic already exists; do not build a competing calculator.

## 20. Test plan

Extend a focused offline V0.6 suite while retaining V0.1–V0.5 regressions:

- Positive/negative/zero returns, zero start, missing endpoints, non-finite values, benchmark absence and arithmetic consistency.
- Nominal calendar targets, first eligible baseline session, exact-open boundary, weekend, supplied holiday/half-day, leap year, DST offset conversion and missing expected session/bar.
- Frozen UTC availability/enrollment/as-of times; reject naive ambiguity; preserve legacy strings and classify unknown provenance.
- Matching stock/benchmark effective windows and basis; reject mismatches without substituting prices.
- Original decision/legacy outcome byte/value equality before/after new observations; no writes from read-only reports.
- Duplicate enrollment/observation prevention, linked corrections, pinned revisions, methodology hash changes and older-database compatibility.
- Zero/one/five/twenty/hundred observation fixtures; no sufficiency claims, unavailable denominators, unique decision counts, pending/missing coverage, recommendation/confidence groups and paired medians/means.
- Adversarial future bars, changed horizons, benchmark switching and retrospective registration cannot enter a prospective cohort silently.
- No current research or memory used to fill gaps; zero live Alpha Vantage/OpenAI; mocks and temporary databases only.

Python `datetime`, `zoneinfo`, `calendar`, `unittest` and explicit finite session-schedule fixtures suffice for deterministic tests. A fixture can declare an invented holiday/half-day to test resolution logic without claiming it is an official exchange schedule. Production schedule truth requires separately verified data; do not confuse fixture coverage with a maintained calendar implementation.

## 21. Technology and dependency review

No new V0.6 dependency is recommended initially. Standard-library SQLite, JSON/hashlib, datetime/zoneinfo and statistics (mean/median) cover contracts, persistence and deterministic reporting. No ORM/migration framework or statistics package is needed.

A market-calendar library may later be appropriate, especially V0.7 intraday sessions; evaluate maintenance, coverage and version pinning before adoption. V0.6 initially accepts an explicit provenance-backed schedule, not a homegrown universal holiday engine. A new provider is not necessary for manual supplied observations, but any automated refresh remains blocked until historical price/adjustment/calendar semantics and access are verified. No dependency or API is added by this document.

## 22. Scope classification

| Category | Scope |
| --- | --- |
| CURRENT V0.6 (planned, not implemented by this step) | Evaluation infrastructure, frozen methodology/cohorts, benchmark-aware supplied outcomes, explicit observation/import, coverage and descriptive comparison. |
| NEXT V0.7 | OHLCV normalization, technical indicators/specialist, calendar-rich signal timestamps, structured chart visualization, supplementary chart interpretation, signal preservation/evaluation. |
| FUTURE BACKLOG | Paper trading, possible broker execution/Alpaca only after separate testing and controls; background schedulers only after explicit collection is reliable. Live trading would require separately approved deterministic risk controls and human approval. |
| NOT NECESSARY NOW | PostgreSQL, migration framework, statistics library, machine-learning price prediction, autonomous strategy optimization, automatic live trading. None is implicitly authorized or committed roadmap functionality. |

## 23. Verification and readiness

Design-only repository verification: existing baseline is 319 offline tests; run `.venv/bin/python -m unittest discover -s tests`, `git diff --check`, and `git status`. No live provider requests, database creation, schema change or production source edits belong to this step.

Ready to begin contract implementation under this design; **not** ready to claim prospective evaluation of legacy rows or launch automated historical collection. The remaining production capability checks concern trustworthy decision-availability capture, session schedule provenance, instrument continuity and price-adjustment semantics. Missing capabilities must remain unavailable until validated, not bypassed to populate reports.

### Step 3 implementation note

The pure `evaluation_engine` returns transient arithmetic results tied to explicitly selected reference/endpoint observation IDs. Step 2 lacks resolved calendar targets: results therefore expose `horizon_resolution_verified=False` and must not be presented as certified horizon evaluations. Stored methodology and horizon are retained without caller overrides. Step 3's explicit strict-positive-price requirement rejects zero endpoints as well as zero references; legacy DecisionOutcome's zero-end behavior is unchanged. Aggregate benchmark metrics use stock/benchmark pairs only, reject duplicate enrollment results and mixed horizon/methodology/time-provenance cohorts, and describe supplied results rather than full enrollment coverage. Calendar verification and reporting integration remain later work.

### Step 4 implementation — offline calendar and derived targets

This implementation supersedes the initial proposed calendar-dependency deferral above.
`exchange_calendars==4.13.2` is the sole calendar dependency, pinned in requirements;
its local **XNYS** schedule covers the project's explicitly verified US-listed equities
and ETFs using compatible regular sessions. No runtime calendar downloads occur.
The small `market_calendar` adapter has fixed 1990–2050 coverage, UTC-aware session
opens/closes and `America/New_York` interpretation. Out-of-range dates are unresolved.
Future emergency closures are not guaranteed by a published schedule. Upgrading the
calendar requires reviewing schedules and assigning compatible new provenance, not
silently recalculating an older enrollment with another package version.

The retry authorizes **NEXT_COMPLETED_REGULAR_CLOSE**, version
`next-completed-regular-close-v1`, under **fundamental-price-v2**. This differs from
v1's next-full-session rule; `close_methodology()` explicitly constructs the new
snapshot. Existing defaults and persisted v1 enrollments remain unchanged and are
unsupported by this resolver. Exact methodology snapshots, including calendar version,
are checked rather than replacing historical versions with current constants.

Reference is the first regular close strictly after preserved, verified analysis
completion: before/during a session uses its future close, equality at close advances
to the next session, and weekends/holidays advance to the next session. This is an
observation proxy, not an execution guarantee or information known at decision time.
It never updates a DecisionRecord. Legacy save/start timestamps do not establish
completion; missing verified availability remains unresolved. Enrollment at/after
that reference remains unresolved for prospective evaluation; the reference is not
shifted forward to disguise late registration.

Active horizons remain **90 and 365 calendar days** added to the reference's local
session date. The endpoint is the first session on/after that nominal date. Both stock
and VOO use this single window. Provider missing bars cannot move it. `as_of` is an
explicit aware datetime and only controls close availability/eligibility. Equality
with the actual close counts as completed; provider publication latency is a later
retrieval concern. Half-days use real early closes. DST uses timezone/calendar rules.
Session labels mean before open, open-inclusive/close-exclusive regular session,
after close, or non-session MARKET_CLOSED; they do not assert extended-hours venues
are operating at every such instant.

`ObservationTarget` is transient and retains the enrollment/methodology, reference,
nominal and actual target, resolution version and availability. Explicit caller-verified
market scope is required; ticker syntax is not an exchange classifier. Unsupported
assets/policies fail closed. No observations, tables, prices or return integrations
are created. Step 3's arithmetic results still do not certify resolved horizons;
linking retrieved observations to these exact targets belongs to the subsequent step.

Price basis remains **regular-session split-consistent price return excluding cash
dividends**, not total shareholder return. A provider's generic adjusted close is not
acceptable unless its documented semantics satisfy this exact split-only basis for
both symbols and dates; dividend-adjusted data must not be silently substituted.
Splits must be consistently reflected, while mergers/symbol history and total-return
reinvestment remain unsupported. Step 5 must validate provider capabilities before
retrieval is integrated. The calendar infrastructure can later support trading-session
horizons/completed intraday bars; no V0.7 horizons, indicators or signals are activated.

### Step 5 approved provider-adjusted observation policy

The explicitly approved replacement for new enrollments uses Alpha Vantage
`TIME_SERIES_DAILY_ADJUSTED`, field `5. adjusted close`, identically for stock and
benchmark. The prior split-only expectation is not available directly from this
provider. Its adjusted series incorporates provider-defined split and cash-dividend
adjustments. Ratios of these retrieved facts are **provider-adjusted returns**, not
raw price returns, independently verified total shareholder returns, realized returns,
or execution returns. No project corporate-action engine is introduced.

New methodology `fundamental-provider-adjusted-v1` uses price policy
`alpha-vantage-adjusted-close-v1` and benchmark policy `voo-aligned-provider-adjusted-v1`.
The reference-close rule remains `next-completed-regular-close-v1`; calendar selection
is unchanged. Earlier methodology snapshots/defaults/rows are retained. Collection
rejects them rather than interpreting their prices under this new convention.

Collection is explicit via `collect_evaluation_observations`; it requires a preserved,
matching enrollment and an eligible target before provider access. One `outputsize=full`
request per distinct symbol supplies both dates, avoiding the latest-100-row limit.
Only exact date keys and `5. adjusted close` are accepted, with symbol/shape and finite
positive numeric validation. Raw closes and adjacent dates are never substitutes.
The endpoint requires suitable Alpha Vantage entitlement; credentials alone do not
establish access. Existing client pacing/error handling is reused without retries.

Two existing observation rows represent reference and endpoint. Missing/invalid provider
inputs become None with safe missing-data reasons, independently for each symbol/date.
Observed timestamps are the selected calendar close (daily-session interpretation),
not a provider-supplied intraday quote time; actual retrieval and recording times are
separate UTC values. Endpoint/field provenance lives in existing source/price-type
strings, with methodology retained on enrollment. No schema changes are needed.

An existing complete pair is returned without retrieval. Partial prior persistence or
revisions require explicit review and are never silently repaired. Each insertion uses
the existing store transaction; a second-insert storage failure can leave the first row
persisted, raises to the caller, and blocks automatic recollection. Missing observations
are also immutable in this workflow. Provider revision vintages can differ across the
two symbol requests; there is no atomic provider-wide snapshot guarantee. No calculated
EvaluationResult is created/persisted here. V0.7's OHLCV adjustment, corporate-action,
and feature-reproducibility decisions remain separate.

Manual validation on 2026-09-12: one sequence, two successful requests (AAPL and VOO),
verified exact 2026-01-02 and 2026-04-02 adjusted-close fields after calendar eligibility.
No persistence, retries, or OpenAI calls. This validates field availability/shape under
the configured entitlement, not independent reconstruction of provider adjustments.

### Step 6 explicit dashboard workflow and atomic collection

Decision History now offers controlled 90/365-calendar-day enrollment for the selected
preserved decision. Duplicate supported enrollments are reused. Opening or selecting
history does not initialize evaluation tables; only explicit enrollment does. No
Research save action auto-enrolls. Legacy DecisionRecord timestamps do not reliably
identify completed analysis availability: enrollments created from these records retain
`legacy_time_unverified`, visibly unresolved. They cannot collect. This step does not
invent completion metadata, backfill timestamps, or relax prospective eligibility.
Supported preexisting enrollments with captured completion can use collection after
the user confirms compatible US stock/benchmark market scope. A later approved capture
workflow is needed to make new dashboard research prospectively enrollable.

Collection is button-only and persisted observations replace the action with factual
read views. The existing schema represents one logical evaluation window with TWO
rows (reference and endpoint), not one combined row. Step 6 replaces separate commits
with one atomic batch transaction using the existing store validation. A failure on
either insert rolls back both. Failed/missing required stock inputs create zero rows;
a missing benchmark intentionally creates a stock-only pair in the same transaction.
Older partial/revised records still require review, never an automatic repair. No
DecisionRecord or DecisionOutcome is changed, and no schema migration is introduced.

Performance has a separate V0.6 section. It checks resolved dates against stored point
roles, displays retrieved adjusted prices and derived provider-adjusted returns, and
uses Step 3 aggregates only within identical horizon/methodology/time-provenance
cohorts. Legacy outcomes remain independently readable and are never pooled into V0.6
metrics. Counts and unavailable values are explicit, benchmark denominators remain
paired, and no significance or trading-return claim is made. The pure engine's
`horizon_resolution_verified=False` contract is unchanged; workflow checks are not an
upgrade of historical arithmetic results to new persisted certifications. Read-only
rendering performs no collection, enrollment, OpenAI calls or database writes.
