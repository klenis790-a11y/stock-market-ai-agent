# V0.7 — Technical & Short-Term Research System

## Status

V0.7 is **COMPLETE and release-ready**. All **412 tests pass**. Manual live
dashboard validation is **PASS**, based on the controlled test reported by the
user. The earlier browser-validation gap is resolved. This documentation update
makes no additional live calls and creates no commit or release tag.

### Controlled manual dashboard validation

The user tested AAPL with `SHORT_TERM_1_TO_5_SESSIONS` (1–5 trading sessions).
The initial attempt stopped correctly because XNYS compatibility had not been
confirmed: `stage=INPUT`, `exception=ValueError`. No automatic retry occurred.
This demonstrated the compatibility guard and explicit-run boundary.

After explicitly confirming XNYS compatibility, one controlled Technical Research
run completed successfully. The dashboard rendered AAPL, a BULLISH TechnicalSignal,
confidence 73/100, the selected horizon, explicit market `as_of` and latest completed
session. It displayed “Technical research signal — not a trade instruction” and
described confidence as evidence strength, not probability.

The user observed summary/thesis, deterministic features, stable Txxx evidence IDs,
RETRIEVED FACT and CALCULATED METRIC classifications, supporting evidence, a conflicting
evidence section, confirmation conditions, invalidation conditions with FORECAST
labeling, and applicable risk/missing-data presentation. Interpretation/condition
labels do not change the deterministic evidence catalog's no-forecast contract.

This validates execution and presentation only. The BULLISH signal is not evidence
of profitability or predictive skill. This smoke test does not establish validation
of live saving, enrollment, collection or future outcomes; no such actions are
performed by this sign-off update. All methodological limitations remain in force.

## Objective

Provide auditable technical research from completed daily market observations,
then preserve that research before measuring later outcomes. Indicators are
computed in Python; AI interprets a bounded evidence packet. Research, historical
beliefs and future observations remain separate.

## Architecture

```text
Ticker + explicit as_of
→ normalized completed daily OHLCV
→ deterministic technical features
→ technical research snapshot + stable evidence catalog
→ Technical Analyst
→ TechnicalSignal
→ explicit save: immutable signal record + evidence packet
→ explicit prospective evaluation enrollment
→ shared calendar resolution + explicit observation collection
→ derived technical evaluation result + dashboard presentation
```

## V0.7A through V0.7G

| Layer | Responsibility |
| --- | --- |
| A | Raw daily provider normalization, session validation, completed-bar filtering and provenance |
| B | Deterministic indicators and per-feature availability |
| C | Consistent research snapshot and stable, typed evidence packaging |
| D | Structured AI interpretation with citation and semantic validation |
| E | Explicit immutable signal/evidence persistence |
| F | Prospective enrollment, fixed session checkpoints and directional evaluation |
| G | Explicit dashboard actions, same-run state and historical presentation |

The review found no integration defect requiring source changes. Shared V0.6
calendar, observation collection and arithmetic helpers retain their fundamental
entry-point contracts. Technical evaluation uses separate source records and
linkage tables; it does not manufacture fundamental decisions.

## Data Integrity Model

- **RETRIEVED FACT:** provider raw OHLCV and, separately, provider-adjusted evaluation closes.
- **CALCULATED METRIC:** indicators, deterministic classifications, returns and aggregates.
- **AI INTERPRETATION:** the cited TechnicalSignal, including confidence and conditions.
- **FUTURE OBSERVATION:** later factual evaluation inputs, stored separately from the signal.

Persisting an AI interpretation makes it a historical record of belief; it does
not turn that interpretation into a verified market fact.

## Point-in-Time Guarantees

Construction requires timezone-aware `as_of`. The calendar decides whether a bar
has completed, even when the provider already supplies a later final daily bar.
At 10:17 AM New York time, that day's final daily bar is excluded. Provider dates
cannot replace calendar-selected evaluation dates. Features only consume the
normalized dataset; evidence verifies matching source state. Saved history is
read without fetching data, recalculating indicators or invoking AI.

These are completion and historical-record controls, not proof of the exact
provider publication state at an earlier instant. Historical provider vintages
are not independently archived. Caller-supplied timestamps require trust.

## Market Calendar

The existing `exchange_calendars==4.13.2` XNYS adapter supplies regular sessions,
holidays, observed holidays and actual early closes. Internal timestamps are UTC;
exchange interpretation uses `America/New_York`, including DST. Session arithmetic
counts valid sessions, not weekdays. Current adapter coverage is 1990–2050.
XNYS is a deliberate U.S. equity/ETF simplification, not global exchange coverage
or a guarantee about future emergency closures.

## Corporate Action Policy

Research uses **RAW OHLCV**, from Alpha Vantage `TIME_SERIES_DAILY`, with full
history requested. Raw open/high/low are never mixed with adjusted close.
**Raw historical indicators can be distorted by stock splits and other
corporate-action discontinuities. This is not solved in V0.7.**

Evaluation instead uses `TIME_SERIES_DAILY_ADJUSTED`, field `5. adjusted close`,
for both stock and VOO. These are provider-defined split/dividend adjustments;
ratios are described as **provider-adjusted returns**, not independently
constructed total-return indices, execution returns or investor realized returns.
Provider revisions may affect later retrievals; stored observations are not
silently refreshed.

## Technical Feature Methodology

`technical-features-v1` remains unchanged:

| Feature | Definition / availability |
| --- | --- |
| SMA20/50/200 | Arithmetic mean of latest N completed closes; requires N bars |
| Close versus SMA | `(close / SMA - 1) * 100`, percentage units |
| Trend stack | Strict close > SMA20 > SMA50 > SMA200 or strict inverse; otherwise MIXED; missing inputs unavailable |
| RSI14 | Initial mean of 14 gains/losses, then Wilder smoothing; needs 15 bars; flat = 50 |
| MACD12/26/9 | SMA-seeded EMAs; line at 26 bars, signal at 34; histogram = line minus signal |
| ATR14 | First 14 true ranges with prior closes averaged, then Wilder smoothing; needs 15 bars |
| ATR percent | ATR / latest close * 100 |
| Momentum5/20 | Latest close / close N sessions ago - 1; decimal return, N+1 bars |
| AverageVolume20 | Mean of latest 20 completed volumes |
| VolumeRatio20 | Latest volume / average; zero denominator remains unavailable |

Volatility is **not implemented**. Missing history and missing sessions retain
explicit availability reasons. Recursive indicators do not silently reseed across
gaps. Trend-stack labels are deterministic feature descriptions, not final signals.

## Evidence Architecture

`technical-evidence-v1` packages 23 fixed local slots, T001–T023, in deliberate
PRICE, TREND, MOMENTUM, VOLATILITY, VOLUME and DATA_QUALITY order. Unavailable values
keep their slots and reasons. Latest market values are RETRIEVED_FACT; indicators
are CALCULATED_METRIC. No forecast or AI interpretation is generated here.

The snapshot composes existing features rather than recalculating them. Source
consistency includes symbol, as-of, latest session and dataset provenance. Numeric
values and units remain explicit, including percentage versus decimal-return
conventions. IDs identify items within a versioned packet, not global facts.

Provenance layers remain distinct: `daily-ohlcv-normalization-v1`,
`technical-features-v1`, `technical-evidence-v1` and `technical-analyst-v1`.

## AI Architecture

The Technical Analyst uses the existing OpenAI client and strict structured output.
Application code attaches trusted source provenance, horizon and model identity.
It validates schema, confidence, evidence references and supported interpretation
constraints. Same-run evidence is checked before the call. Failures produce no
fallback signal. No specialist rerun or indicator calculation belongs here.

Prompt and deterministic checks prohibit invented support/resistance and execution
instructions; they do not constitute a general proof that all natural-language
reasoning is correct or free of outside knowledge. A prior synthetic live model
compatibility check is distinct from the subsequently successful, user-reported
live dashboard research validation recorded above.

## Signal Contract

Directions are exactly BULLISH, NEUTRAL and BEARISH. Horizons are exactly
`SHORT_TERM_1_TO_5_SESSIONS` and `SWING_1_TO_4_WEEKS`. Integer confidence 0–100 means
evidence-strength confidence, not probability of success. Cited summary/thesis,
supporting/conflicting references, conditions, risks and missing-data notes remain
part of the interpretation. No trade, quantity or execution contract is implied.

## Persistence Architecture

`technical-signal-record-v1` stores one SQLite row containing immutable serialized
signal and compact evidence packet, with identity and UTC record-creation time.
Ordered references, prose, values, units, availability reasons, methodology versions
and model identity survive round trips. The packet is what historical citations
refer to; current catalog code does not reinterpret it on read.

Saving is explicit. Reusing an existing record ID cannot overwrite it; separately
prepared later records may preserve identical content under new identities. One-row
insertion is atomic. No update API, outcome fields or automatic enrollment is added.
Application immutability is not protection against external SQLite modification.

Market `as_of`, latest session and record creation remain distinct. Signal generation
time is not separately preserved. Full raw historical bars are not persisted here.
Schema additions preserve legacy DecisionRecord, DecisionOutcome and V0.6 tables.

## Evaluation Architecture

Versions are `technical-signal-evaluation-v1` and
`technical-signal-horizon-map-v1`. The shorter horizon maps to **5 sessions**;
the swing horizon maps to **20 sessions**, counted after the reference session.
The calendar resolution version is `xnys-session-target-v1`.

Reference policy is NEXT_COMPLETED_REGULAR_CLOSE,
`next-completed-regular-close-v1`: first regular close strictly after record
creation, including the exact-close boundary. Enrollment must precede that
reference close, a stronger gate than merely preceding the target. It cannot move
the window forward to rescue a late enrollment. Caller timestamps remain trusted.

VOO is fixed under `voo-aligned-provider-adjusted-v1`; both symbols use
`alpha-vantage-adjusted-close-v1` and identical reference/target sessions. Source
record digests prevent accidental relinking to changed historical content.
Explicit `as_of` changes eligibility, not the historical target.

Collection retrieves exact dates and persists the reference/target observation
pair atomically. Required stock failure leaves no partial pair; supported benchmark
absence produces an intentional partial pair. Duplicate collection reuses stored
facts rather than silently refreshing them. Results are derived, never persisted.

BULLISH succeeds directionally only for positive stock return; BEARISH only for
negative stock return. Zero is unsuccessful for both; NEUTRAL has no binary
success metric. Benchmark outperformance is separate. No short-sale or trade P&L
is calculated. Technical result composition reuses the shared return structure;
its source identity and timestamp refer to the technical record, not a fabricated
fundamental DecisionRecord.

Aggregates exclude NEUTRAL from directional denominators and absent paired benchmark
comparisons from benchmark denominators. Stock-only results remain visible. Zero
samples are safe; pooled horizons are identified with separate horizon breakdowns.
Counts and averages are descriptive, not evidence of predictive skill.

## Dashboard Architecture

Technical Research adds explicit run, save, history load, enrollment and eligible
collection actions. Research holds one same-run bundle; a new submission clears
stale results. Rerendering does not repeat provider or AI calls. History reads
preserved records, and collection controls respect backend eligibility and policy
gates. Technical evaluation remains separate from legacy/fundamental Performance.

Failures at MARKET_DATA, FEATURES, EVIDENCE, TECHNICAL_ANALYST, SAVE, ENROLLMENT and
COLLECTION use sanitized UI messages. Internal diagnostics withhold raw details.
The page adds no charts, trading controls, price targets or support/resistance engine.

## Testing Strategy

The complete offline suite passes **412 tests**, including V0.1–V0.6 regressions.
This checkpoint adds no tests or source changes. Existing coverage includes real
local calendar cases, feature fixtures, stable evidence, response validation,
round trips, legacy databases, atomic pairs, duplicates, prospective enrollment,
directional/benchmark denominators and Streamlit AppTest/helper rerun behavior.
Unit tests use mocked providers and temporary databases: zero live Alpha Vantage
and zero live OpenAI requests. No user database is used for checkpoint writes.
Manual live dashboard research validation passed as reported above; no additional
live run or startup smoke is performed for this documentation update.

## Network / Side-Effect Boundaries

| Action | Permitted effects |
| --- | --- |
| Page render / eligibility / calculations | No provider or AI calls |
| Explicit research | Alpha Vantage retrieval, then one Technical Analyst call |
| Explicit save / history | Local SQLite only; no recalculation or AI |
| Explicit enrollment | Local validation/calendar and persistence only |
| Explicit eligible collection | Alpha Vantage only, then atomic observation persistence |

No scheduler, automatic save, backfill, enrollment or observation collection exists.
No new numerical, charting, ORM, database or provider dependency is introduced.

## Known Limitations

- Daily U.S. equity/ETF data and XNYS scope only; no intraday research.
- Raw technical series have unresolved corporate-action discontinuities.
- Provider history can revise; exact past publication/vintage is not archived.
- No volatility feature, deterministic support/resistance, market regime, sector or relative-strength context.
- No charts, portfolio-aware technical synthesis or automatic refresh.
- Natural-language confirmation/invalidation conditions are not machine evaluated.
- No MFE/MAE, transaction costs, slippage, trade simulation or execution evaluation.
- A single VOO benchmark and potentially small samples limit interpretation.
- Generation time is not separately recorded; save time differs from market as-of.
- Caller timestamps require trust; persistence is not a cryptographic audit ledger.
- Provider entitlement and availability remain external dependencies.
- The manual smoke validates research execution/presentation, not live persistence,
  evaluation collection, future outcomes or predictive skill.

## Professional Skills Demonstrated

Point-in-time market-data engineering; exchange-calendar handling; deterministic
quantitative calculations; stable evidence grounding; schema and semantic validation;
immutable historical records; prospective evaluation; no-look-ahead controls;
additive SQLite evolution; Streamlit state management; mocked API-boundary testing;
and disciplined ownership between data, interpretation, persistence and presentation.

## Important Design Decisions

Indicators belong in deterministic Python so their seeds, windows and missing-data
behavior are reproducible. AI receives bounded evidence so citations can be audited.
Signals are saved before outcomes so later results cannot rewrite the original view.

Broad 1–5-session and 1–4-week analysis horizons map to fixed 5/20-session endpoints
rather than outcome-selected dates. NEUTRAL has no invented directional-success
criterion. VOO is predeclared rather than selected after performance is known.
Raw research OHLCV and provider-adjusted evaluation closes serve different purposes
and retain separate policies. Research remains distinct from trade execution.

## What V0.7 Does NOT Claim

V0.7 is not a price predictor, a validated profitable strategy, evidence of
market-beating performance, a broker/trading system, a backtester or autonomous
trading. Its value is an auditable foundation for research and prospective measurement.

## Next Version

Potential next milestone: **V0.8 — Horizon-Aware Research Integration**.
A possible goal is to combine fundamental research, technical research, portfolio
context and differing horizons into controlled decision support. This is tentative;
V0.8 has not started and no V0.8 behavior is implemented here.
