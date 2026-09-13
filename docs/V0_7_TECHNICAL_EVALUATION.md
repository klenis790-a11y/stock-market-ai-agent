# V0.7F — Technical Signal Evaluation Integration

## Objective

Measure preserved technical research under prospectively declared endpoint rules. Signals,
market evidence, enrollment, later observations and calculated results remain separate.
Directional success is a defined descriptive measure, not trading accuracy or proof of skill.

## Architecture

TechnicalSignalRecord → explicit TechnicalEvaluationEnrollment → shared V0.6 calendar
resolution → shared V0.6 adjusted-close collection → EvaluationObservation pair →
TechnicalSignalEvaluationResult → descriptive aggregates.

`technical_evaluation.py` is the source-specific adapter. `technical_evaluation_store.py`
provides additive linkage and factual observation storage. Existing V0.6 entry points
retain their fundamental decision validation and policy restrictions. Small internal
kernels extracted from the resolver, collector and return engine are shared; there is
no technical price collector, duplicate return formula, or second market calendar.

The result composes the existing transient `EvaluationResult`. Within this wrapper its
`recommendation` field carries the original BULLISH/NEUTRAL/BEARISH source label and its
`decision_timestamp` carries the declared record-existence anchor. It is not a
fundamental recommendation or a synthetic DecisionRecord. Technical callers use the
wrapper's `signal`, `directional_success`, and `benchmark_outperformance` properties.
Original confidence remains integer evidence strength, not a probability.

## Analysis Horizon vs Evaluation Horizon

| Preserved analysis horizon | Predeclared evaluation checkpoint |
| --- | --- |
| SHORT_TERM_1_TO_5_SESSIONS | 5 trading_sessions |
| SWING_1_TO_4_WEEKS | 20 trading_sessions |

`technical-signal-horizon-map-v1` fixes this mapping. The reference session is excluded:
N means the Nth XNYS session strictly after the reference. Holidays and weekends are
not sessions; an early-close session counts once. There is no best-of-window selection.
The new calendar adapter method uses exchange_calendars session arithmetic.

## Prospective Enrollment

Explicit `enroll_technical_signal(store, record_id, enrolled_at, market=...)` requires a
saved source and an aware caller-supplied application timestamp. Saving a technical
signal does not initialize evaluation or enroll it. New enrollment validates the symbol,
approved source versions, RAW daily provenance, XNYS calendar/version, source timestamps,
and latest completed session as of the preserved market timestamp. Missing/stale session
metadata or retrieval preceding that session's close is rejected, never repaired.

**Timing boundary:** the current TechnicalSignal lacks a generated-at field. V0.7F
therefore declares `preserved_record_creation` timing provenance. Record creation is a
conservative timestamp at which the signal is recorded as existing; it is not renamed
as analyst completion. The reference is the first completed regular-session close
strictly after that record timestamp (NEXT_COMPLETED_REGULAR_CLOSE). Equality at close
advances to the next session. No save-time price or current quote is used.

The source market as-of, provider retrieval time and record creation time remain
separate. Both source timestamps must precede or equal creation; enrollment cannot
precede creation. As with existing persistence, event timestamps must come from a
trustworthy caller. This is not cryptographic proof of real-world creation time, and
caller-supplied timestamps cannot prevent deliberate backdating outside the application.
Delayed saves shift the declared evaluation anchor; this does not measure performance
since the unknown original generation time. No maximum source-age rule is invented.

V0.6's stronger prospective guard is retained: enrollment must occur **before the
reference close**, not merely before the endpoint. Consequently completed-target
retrospective enrollment is blocked, as is enrollment after the reference but before
the endpoint. The window is never moved to accommodate a late enrollment. As-of affects
eligibility only; collection requires the endpoint close to have completed.

## Versions and Database Design

- Technical methodology: `technical-signal-evaluation-v1`.
- Horizon mapping: `technical-signal-horizon-map-v1`.
- Reference policy: `next-completed-regular-close-v1`.
- Technical session resolution: `xnys-session-target-v1`.
- Time provenance: `preserved_record_creation`.
- Calendar: XNYS, America/New_York, installed exchange_calendars version (currently 4.13.2).

Each enrollment stores the complete `EvaluationMethodology`, source identity/digest,
analysis and evaluation horizons, enrollment and record timestamps, explicit supported
market, and policy versions. Unsupported versions fail closed; they are not relabeled.
A digest pins the complete saved record, including evidence JSON, without recalculating
features or rerunning the Analyst. IDs deterministically hash record ID plus methodology.

V0.6 enrollment foreign keys require DecisionRecord; its observation foreign keys in
turn require those fundamental enrollments. Reusing those tables would require fake
decisions or a destructive FK change. Two additive technical tables avoid that:
`technical_evaluation_enrollments` references `technical_signals`, and
`technical_evaluation_observations` references technical enrollments. Legacy table SQL
and contents are unchanged. Initialization is explicit and idempotent.

One enrollment/linkage row inserts atomically, with a unique source/methodology pair.
The shared V0.6 batch transaction stores reference and endpoint together, or neither.
Technical observations are unique per enrollment/point; revisions/overwrites are not
accepted. An existing pair is returned without provider calls. Existing partial or
mismatched data requires explicit review, not repair. No result table is added.

## Price Policy

Research still consumes RAW daily OHLCV. Evaluation uses Alpha Vantage
TIME_SERIES_DAILY_ADJUSTED, `5. adjusted close`, under
`alpha-vantage-adjusted-close-v1` and
`alpha-vantage-provider-split-dividend-adjusted` semantics for both instruments.
These are **provider-adjusted returns**, not execution returns or an independently
constructed total-return index. V0.6 policies and V0.7 technical inputs are unchanged.

One full series per distinct symbol supplies both exact calendar-selected dates.
Provider availability cannot select adjacent sessions. Provider revisions may affect
later retrieval vintages, but stored observations are not silently refreshed.

## Benchmark

The actual existing benchmark is **VOO**, currency USD, with policy
`voo-aligned-provider-adjusted-v1`. It is fixed rather than inferred from the signal.
Stock and benchmark share one reference and endpoint window and adjustment policy.

## Directional Semantics

- BULLISH: stock provider-adjusted return > 0 is directionally favorable.
- BEARISH: stock provider-adjusted return < 0 is directionally favorable.
- Zero return: false for either directional signal.
- NEUTRAL: directional success is always unavailable (`None`), including zero returns.
- Missing stock return: directional success is unavailable for every signal.

No neutral band, probability calibration, short-sale P&L, or single accuracy score is
introduced. Confirmation/invalidation prose stays in the original evidence archive.

## Benchmark Semantics

Stock return, benchmark return, and excess return use unchanged V0.6 arithmetic.
Benchmark outperformance means excess return > 0, independent of signal direction.
A bullish +2% result versus benchmark +4% is directionally favorable but underperforms.
A bearish -1% result versus benchmark -5% is directionally favorable with positive
excess return; this is not automatically an economically useful short strategy.

## Partial Results

Required stock retrieval failure creates no rows. Benchmark failure may intentionally
produce a stock-only pair committed once. The shared pure engine can also represent
supplied missing-stock or entirely unavailable observations without claiming evaluation.
Stock-only directional results remain usable; missing benchmark/excess stay None.
The adapter checks observation points, exact calendar timestamps, provider/field and
source digest before calculation. Calendar verification is marked separately from
arithmetic completeness. Results are derived on read, never stored.

## Aggregate Metrics

Call `get_technical_result` for **every** enrollment, including ones without observations,
then `aggregate_technical_evaluations`. Counts describe supplied enrollments, not an
implicit database-wide scan. Duplicate enrollment results are rejected.

- Total enrolled: all supplied unique enrollments; evaluated: stock return available.
- Stock mean/median and positive-return rates: stock-evaluable denominator.
- Benchmark means, excess metrics and outperformance rates: paired stock/benchmark denominator.
- Directional rate: favorable BULLISH/BEARISH results divided by stock-evaluable
  BULLISH/BEARISH results. NEUTRAL and missing-stock results are excluded.
- Signal and analysis-horizon breakdowns contain the same metrics and exact counts.
- No eligible values yields None for averages/rates rather than an apparent 0% result.

Overall metrics can pool the two **predeclared** checkpoint lengths; `pooled_horizons`
explicitly marks that case, with mandatory horizon breakdowns. Such a pooled mean is
not a return for one common holding period. This technical descriptive summary does
not change V0.6's homogeneous-cohort aggregate entry point. Every summary includes a
sample limitation; confidence calibration and statistical significance are not claimed.

## Point-in-Time Integrity

Original signal/evidence is read from persistence without provider or AI calls. Enrollment
pins its digest and methodology. The calendar selects dates before provider access;
completed-session checks use explicit as-of and actual early closes/DST. Provider dates
cannot modify the window. Later observations and computed metrics never write back to
TechnicalSignalRecord, DecisionRecord, DecisionOutcome, or fundamental evaluation rows.

## What Is NOT Evaluated Yet

No invalidation-first outcome, support/resistance breaks, MFE/MAE, hypothetical trade
P&L, transaction costs, stops or position sizing. MFE/MAE require path observations;
natural-language invalidation requires a future machine-readable condition contract.
No confidence-band/calibration analysis, automatic refresh, scheduler or dashboard.

## Verification and Limitations

404 offline tests pass, including 13 new integration tests with synthetic preserved
records, mocked adjusted series and temporary SQLite databases. Coverage includes
session counting, partial results, denominators, duplicates, rollback, unchanged legacy
rows, source/window tampering, unsupported methods and zero provider calls before
eligibility. No live OpenAI or Alpha Vantage calls occur in the suite.

Manual live collection was skipped: no established prospectively enrolled eligible
record was supplied; no backdated live fixture was created to force eligibility.
The fully mocked integration covers the same shared collector and persistence path.

Limitations include small/correlated samples, one benchmark, provider entitlements and
revised histories, caller-supplied timing, delayed saves/old evidence, XNYS-only market
scope and fixed calendar coverage, endpoint-only evaluation, and non-machine-readable
invalidation. The market assertion must be verified by the caller; ticker syntax alone
does not establish a US equity/ETF. No strategy-quality or market-beating claim follows.

## Next Step

V0.7G — Technical Research Dashboard Integration. V0.7 remains IN PROGRESS; no technical
evaluation controls or charts are added by V0.7F.
