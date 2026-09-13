# V0.7G — Technical Research Dashboard Integration

## Objective

Expose the existing technical research, preservation and prospective evaluation workflow
through one additional Streamlit page. No indicator, evidence, analyst or evaluation
methodology changes are introduced.

## User Workflow

1. Open **Technical Research** and confirm the selected ticker/VOO market scope.
2. Enter a ticker, choose an approved horizon, and press **Run Technical Research**.
3. Inspect the same-run signal, confidence, market as-of, latest completed session,
   features, evidence, confirmation/invalidation conditions, risks and missing data.
4. Supply an explicit **Decision database path** and press **Save Technical Signal**.
5. Load saved history by ticker and inspect the preserved record/evidence packet.
6. Explicitly enroll a supported, prospectively eligible saved signal.
7. After its target session completes, explicitly collect observations and inspect
   the derived result and technical summary.

Research horizons remain `SHORT_TERM_1_TO_5_SESSIONS` and `SWING_1_TO_4_WEEKS`, displayed
as “1–5 trading sessions” and “1–4 weeks.” No arbitrary horizon entry is available.

## Page Architecture

`src/dashboard/technical_research.py` renders the page.
`src/dashboard/technical_adapter.py` coordinates the existing backend builders and
provides save/read/evaluation actions and display rows. The adapter invokes historical
OHLCV retrieval → deterministic features → technical research snapshot → evidence catalog
→ Technical Analyst. The page does not calculate indicators or evaluation denominators.

The six existing pages retain their behavior. Technical evaluation summaries remain on
Technical Research, separate from fundamental Performance and legacy DecisionOutcome.
No new technical integration is added to Home, Agent Room or Portfolio.

## Session-State Safety

One `tech_run` bundle retains the matching snapshot (including features and source
OHLCV), catalog and signal. One aware UTC as-of is supplied at explicit submission;
provider retrieval time remains a separate factual timestamp owned by the backend.
Rerenders use that bundle without rebuilding or fetching anything.

A new submission clears the active run and its prepared/saved record state before work
begins. Failure leaves no previous signal masquerading as the new ticker. Editing an
input alone does not replace the successful result; its own ticker/horizon/as-of stay
visible. Fundamental session state uses separate keys.

The first save action prepares a stable record identity. Repeated saves of the same
prepared record return the existing equal record; conflicting identities fail safely.
New successful research clears that identity. No generation timestamp is invented.

## Explicit Network Actions

| Action | Alpha Vantage | OpenAI | Persistence |
| --- | --- | --- | --- |
| Run Technical Research | Existing raw daily retrieval | Existing Technical Analyst | None |
| Save Technical Signal | None | None | Explicit signal/evidence save |
| Load history / inspect evidence | None | None | Read-only |
| Inspect eligibility / results / summary | None | None | Read-only |
| Enroll for Evaluation | None | None | Explicit enrollment |
| Collect Evaluation Observation | Existing adjusted-close collector | None | Atomic factual pair |
| Navigate, change widgets, expand, rerender | None | None | Reads only where a history source is loaded |

Market confirmation is separate from the run form so saved-history actions do not
require a new research run. No automatic enrollment, collection, current-quote refresh,
background task, or retry is introduced.

## Research vs Trade

BULLISH/NEUTRAL/BEARISH remain AI INTERPRETATION and are labeled “Technical research
signal — not a trade instruction.” Confidence is evidence strength, not success
probability. Confirmation/invalidation remain conditional research statements, not orders.
There are no buy/sell buttons, allocation, position sizing, stops or broker controls.

## Historical Signal Integrity

Saving uses the exact same-run signal and evidence packet through V0.7E. History loads
TechnicalSignalRecord; no historical features/evidence/interpretation are reconstructed.
The view shows record ID, save time, market as-of, latest completed session, horizon,
signal, confidence and preserved prose. Citations resolve against that packet rather
than current research. Stable evidence IDs, numeric units, classifications and
unavailability reasons remain visible. Missing values display “Unavailable,” never zero.

No database path is assumed or scanned. The technical path control can initially reuse
an explicitly selected Decision History source. Save may create the selected SQLite
file; read operations require an existing file and never initialize tables. Existing
databases without technical tables show empty technical history.

## Evaluation UX

The UI calls the V0.7F prospective guard. Unsupported methods/timing or a passed reference
close produce an explanation and no enrollment action. There is no retrospective bypass.
The stricter pre-reference guard remains unchanged; passing the final target is not the
only reason enrollment may be unavailable.

Enrolled signals show the analysis horizon separately from the fixed 5/20-session
checkpoint, reference/target closes, backend eligibility and methodology. The benchmark
is VOO with `voo-aligned-provider-adjusted-v1`; evaluation prices use
`alpha-vantage-adjusted-close-v1`. RAW research inputs and provider-adjusted outcome
prices are explicitly distinguished. Record creation remains the conservative existence
anchor; the UI does not fabricate analysis-generation time.

Collection is offered only for confirmed market scope, backend ELIGIBLE status, and no
stored observations. The existing collector handles stock failure, intentional missing
benchmark facts, atomic persistence and duplicate protection. Once stored, facts are
read and results derived; rerendering does not recollect.

The summary uses V0.7F aggregate counts/means/medians/rates. It displays evaluated samples,
direction counts, directional and benchmark denominators, missing benchmark values,
horizon breakdowns and a descriptive-sample warning. Different pooled checkpoint lengths
are flagged. No predictive-skill or market-beating claim is made.

## Neutral Signal Semantics

NEUTRAL displays “Not defined under technical-signal-evaluation-v1” for directional
success. It is excluded from the directional denominator. BULLISH requires positive
stock provider-adjusted return; BEARISH requires negative return. Benchmark outperformance
is separate and unavailable without a valid pair. Neither measure represents trade P&L.

## Error Handling

Fixed safe messages reach the UI. Internal logs identify MARKET_DATA, FEATURES, EVIDENCE,
TECHNICAL_ANALYST, SAVE, HISTORY, ENROLLMENT, COLLECTION or EVALUATION and exception type.
They do not dump exception details, provider bodies, model responses, prompts or secrets.
Failures create no fallback signal; backend persistence/collection safety is unchanged.

## Verification

The full offline suite passes **412 tests**. Eight new dashboard tests cover explicit
pipeline/as-of propagation, zero-call page load and reruns, failed-run clearing, exact
save/history fidelity and duplicate saves, prospective guards, collection/results,
classification/citation display, directional/neutral semantics and safe stage errors.
Existing navigation tests were updated for the seventh page.

The local Streamlit server started and was stopped. Browser inspection was blocked by
automatic approval review citing the usage limit. Manual dashboard inspection, the live
technical research run, manual save and manual enrollment were skipped; no alternate
browser route or live request was attempted. Offline AppTest render checks passed.

## Limitations

No charts, support/resistance, price targets, portfolio synthesis, trade execution,
MFE/MAE, transaction costs or automatic retraining. Provider entitlement, revised history,
XNYS scope, current policy support and caller timing limitations remain those of V0.7A–F.
Manual live end-to-end validation remains pending.

## Next Step

V0.7 final integration/checkpoint. Implementation is complete pending that review and
manual smoke validation. V0.8 has not started.
