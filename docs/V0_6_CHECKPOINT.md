# V0.6 — Evaluation Infrastructure

## Objective

V0.6 is complete within its declared scope. Recommendations cannot be assessed responsibly
without predeclared evaluation rules and point-in-time-safe outcome measurement. This
version supplies those contracts and an explicit collection/evaluation workflow. It
measures observed outcomes of preserved research, not executed trades or market-beating
skill. A metadata-capture limitation still restricts which decisions can be evaluated.

## What Was Built

- Immutable enrollment, horizon, methodology and factual observation contracts.
- Additive SQLite persistence with foreign keys, duplicate protection and atomic collection.
- Offline market-session resolution, including holidays, early closes and DST.
- Explicit historical adjusted-close collection with exact-session validation.
- Pure deterministic return calculations and homogeneous-cohort aggregate helpers.
- Decision History enrollment/collection controls and a separate V0.6 Performance view.

## Architecture

```text
DecisionRecord
→ EvaluationEnrollment
→ ObservationTarget
→ Alpha Vantage factual observation
→ EvaluationObservation (reference + endpoint)
→ EvaluationResult
→ aggregate evaluation / dashboard
```

`DecisionRecord` preserves the original recommendation, confidence and reasoning.
`DecisionOutcome` remains the separate legacy V0.3 outcome mechanism; it is not converted
automatically into V0.6 data.

`EvaluationEnrollment` declares the horizon and complete methodology snapshot, retaining
availability-time provenance. `ObservationTarget` derives the reference and endpoint
sessions without prices or database writes.

`evaluation_collection` retrieves the two exact dates per symbol, normalizes provider
facts, then stores a pair of `EvaluationObservation` rows. `evaluation_engine` derives
`EvaluationResult` and aggregates without network or database access.

The dashboard adapter verifies stored point roles/dates against resolved targets before
producing display results. The pure engine still exposes
`horizon_resolution_verified=False`: arithmetic alone is not a calendar certification.
The workflow does not overwrite that flag or persist a new certification.

## Data Integrity Model

**RETRIEVED FACTS:** Alpha Vantage adjusted closes with symbol, endpoint/field provenance
and retrieval timestamps. Market observation timestamps are the calendar-selected
regular close, interpreting the provider's daily date; they are not vendor intraday
quote timestamps.

**CALCULATED METRICS:** stock and benchmark provider-adjusted returns, excess return,
means, medians and rates. Python computes end/start minus one without display rounding
inside arithmetic. Missing values remain unavailable, never zero.

**AI INTERPRETATION:** none is required for evaluation. The original recommendation and
confidence are preserved metadata. Confidence is not a probability and positive returns
are not automatically labeled a correct recommendation.

## Point-in-Time / No-Look-Ahead Controls

The horizon is declared before observations. Reference is the first regular-session
close strictly after verified analysis completion; equality at close advances to the
next session. This future evaluation anchor is never inserted into historical evidence.
Enrollment at/after the chosen reference cannot claim prospective eligibility.

The reference local session date plus 90 or 365 calendar days determines a nominal target.
The endpoint is the first XNYS session on/after that date. Weekends, holidays and early
closes use the installed calendar; UTC timestamps and America/New_York interpretation
handle DST without fixed offsets. Explicit aware `as_of` controls availability only.
Collection requires the endpoint close to have completed.

Provider bars cannot select a different date. Missing bars do not shift the horizon.
No observations or calculated results rewrite DecisionRecord or DecisionOutcome.

## Current Evaluation Policies

| Concept | Implemented value |
| --- | --- |
| Calendar | XNYS |
| Calendar dependency | exchange_calendars 4.13.2 |
| Explicit market scope | US_EQUITY_ETF_XNYS |
| Exchange timezone | America/New_York |
| Reference policy | NEXT_COMPLETED_REGULAR_CLOSE |
| Reference policy version | next-completed-regular-close-v1 |
| Resolution version | xnys-calendar-target-v1 |
| Active horizons | 90 and 365 calendar_days |
| Provider / endpoint | Alpha Vantage / TIME_SERIES_DAILY_ADJUSTED |
| Field | 5. adjusted close |
| Price policy | alpha-vantage-adjusted-close-v1 |
| Adjustment basis | alpha-vantage-provider-split-dividend-adjusted |
| Evaluation methodology | fundamental-provider-adjusted-v1 |
| Benchmark / currency | VOO / USD |
| Benchmark policy | voo-aligned-provider-adjusted-v1 |

Methodology snapshots include calendar/version and textual rules. The reference version
is a resolver constant associated with the current methodology, not an additional
independent enrollment column. Original default `fundamental-price-v1` and the earlier
`fundamental-price-v2` records remain unchanged. The collector accepts only the exact
current supported adjusted-price methodology; old versions are not relabeled or refreshed.

## Adjusted-Price Methodology

The provider's adjusted close incorporates provider-defined split and cash-dividend
adjustments. It avoids using raw split discontinuities and applies identical conventions
to stock and benchmark without a project corporate-action engine. Ratios are described
as **provider-adjusted returns**, not exact realized/execution returns, independently
constructed total shareholder returns or a verified total-return index.

One full historical series per distinct symbol supplies both dates. Suitable provider
entitlement is required. Provider revisions and different retrieval vintages can affect
comparability; there is no atomic provider-wide snapshot guarantee. A prior Step 5 live
validation checked AAPL/VOO field availability. This checkpoint made no live provider calls.

## Database Design

Legacy `decisions` and `outcomes` tables retain their existing behavior. V0.6 adds
`evaluation_enrollments` and `evaluation_observations`, initialized explicitly and
idempotently. Existing databases need no destructive migration.

Enrollment uniqueness covers decision, horizon and methodology version. A collection
has two rows, reference and endpoint, committed in one transaction. Failure on either
insert rolls back both. Required stock failure creates no rows; missing benchmark facts
are an intentional stock-only pair. Existing complete collections are returned without
new requests. Older partial collections/revisions require explicit review, not repair.
The underlying store supports explicit revision links; this collector never refreshes.

EvaluationResult is transient. Keeping source facts and methodology preserves the basis
for reproducible arithmetic without an additional table of potentially inconsistent
calculated values.

## Explicit Workflow

1. Preserve a decision using the existing explicit save workflow.
2. Select it in Decision History and explicitly enroll an approved horizon.
3. Inspect methodology, timing provenance and eligibility.
4. For an eligible supported enrollment, confirm market scope and click Collect Observation.
5. Derive results from the stored reference/endpoint pair.
6. Inspect the separate V0.6 Performance cohorts.

**Current metadata boundary:** `enroll_decision` does not possess verified analysis
completion time from the legacy DecisionRecord. It creates `legacy_time_unverified`
enrollments, which remain unresolved even if the save timestamp parses as UTC. This
applies to new dashboard enrollments through the current legacy save path as well as
old decisions. No production dashboard capture workflow currently fills this gap.
The complete collection path works for preexisting explicitly supplied enrollments
with trustworthy completion provenance and timely enrollment. Fixtures demonstrate
that path; they do not establish that arbitrary saved history is eligible. Future
capture work needs its own scope and cannot guess or retroactively invent metadata.

## Dashboard Integration

Decision History preserves historical details and adds explicit evaluation actions.
Collection is offered only for supported eligible enrollments without observations.
Page selection, eligibility display and reruns do not collect or auto-enroll.

Performance reads stored facts and uses the pure engine. V0.6 results and V0.3 legacy
outcomes are separate sections and never pooled. Cohorts separate horizon, methodology
digest and time provenance. Stock rates use stock-evaluable samples; benchmark means,
excess metrics and outperformance rates use paired stock/benchmark samples. Missing
benchmarks are excluded only from those denominators. Sample counts are displayed.

Home does not collect. Research does not auto-enroll or create outcomes. No background
scheduler, automatic backfill or OpenAI evaluation narrative exists.

## Testing

Checkpoint verification: **347 tests passed**, covering V0.1–V0.6. Tests use deterministic
fixtures, mocked providers and temporary SQLite files. Coverage includes horizon and
exact-close boundaries, weekends/holidays/half-days/DST, explicit as_of, unavailable
legacy timing, adjusted-price parsing, policy rejection, atomic rollback, duplicate
protection, partial benchmarks, denominator semantics and dashboard rerun safety.

The temporary-database workflow test covers preserved decision → enrollment → eligible
window → mocked collection → persisted facts → calculated result → aggregate. Legacy
records/outcomes remain unchanged. No live Alpha Vantage or OpenAI requests occurred.

Smoke test: the local Streamlit server started and was stopped. Offline AppTest renders
all six navigation destinations and the integrated evaluation sections without import
or session-state errors. Visual browser inspection was limited in this environment;
this is logical/render validation, not a pixel-level usability audit.

## Limitations

- Explicitly verified US equities/ETFs using XNYS-compatible regular sessions only; no
  global exchange discovery. Calendar coverage is fixed at 1990–2050; future emergency
  closures are not guaranteed. Package upgrades require provenance review.
- Provider entitlement, quotas, errors, missing dates and revised adjustment histories.
- Legacy/current dashboard saves lack verified completion metadata needed for collection.
- No automatic observation collection, backfill or repair of missing benchmark records.
- No statistical significance claims; repeated horizons and correlated decisions are
  not independent evidence of skill. Descriptive summaries do not prove an edge.
- No backtesting, transaction costs, slippage, trade/execution evaluation or technical
  signal evaluation. No broker integration or trading.

## Why V0.6 Matters

The project now has testable machinery for comparing preserved beliefs with later
observations under declared rules. This is a foundation for evaluating usefulness,
rather than treating persuasive research reports as evidence of predictive quality.
The metadata limitation and sample restrictions remain part of that honest assessment.

## Skills Demonstrated

Temporal data modeling; additive SQLite compatibility; deterministic analytics; API
integration and provider provenance; exchange-calendar/session logic; regression testing;
explicit UI workflow design; financial evaluation methodology; no-look-ahead controls;
and scope management.

## Interview Talking Points

- A decision and its later outcome have different temporal authority; never rewrite belief.
- Calendar policy selects dates before market data is inspected, preventing convenient substitutions.
- The first close after completion is a declared evaluation proxy, not an assumed execution fill.
- Stock-only outcomes remain useful, while benchmark denominators exclude missing pairs.
- Provider-adjusted prices avoid a homemade corporate-action engine without claiming exact total return.
- Two database rows are one logical collection, so their commit must be atomic.
- A parseable UTC save timestamp is not proof of analysis availability; unresolved is safer than guessed.
- Derived results and versioned facts avoid persisting redundant calculations.
- Explicit buttons and duplicate checks address Streamlit reruns without background automation.

## Next Version

**V0.7 — Technical & Short-Term Research System** is next, not implemented. Structured
OHLCV, deterministic features and explicit technical-signal horizons should build on
this evaluation foundation. Raw/adjusted data and completed-bar rules need deliberate
policies; screenshot-based interpretation is supplementary. Signals remain separate
from strategies, hypothetical trades and execution. Paper trading stays later.
