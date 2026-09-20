# V0.8A — Horizon Synthesis Contract & Decision Matrix

> Current release status: active generation is `technical-analyst-v2` and
> `horizon-synthesis-v2` under `evidence-first-assembly-v1`. Historical v1
> consumption remains supported. Earlier step-specific status statements below
> are historical. G3 validated provider acceptance and one-shot compliance for one
> controlled NVDA/MEDIUM execution; it did not validate investment accuracy or
> long-term reliability. No retries/fallback/repair or semantic-entailment guarantee.
> Research-only V0.8A is ready for separately authorized release publication;
> portfolio-aware decision context remains future V0.8B work. See the
> [release checkpoint](V0_8A_RELEASE_CHECKPOINT.md).


## Historical design status and authority

Step 1: design only, ready for human review. This is the authoritative V0.8A design
baseline for later implementation, subject to explicit versioned design amendments.
No production contracts, schema, thresholds, prompts or behavior are implemented.
V0.7 remains complete. Exact freshness and evidence-applicability policies require a
later deterministic policy step before an operational synthesis implementation.

## Purpose and architectural boundaries

```text
Immutable Fundamental research + immutable Technical research
+ explicit decision horizon
→ deterministic validation, freshness, authority and conflict context
→ Horizon Synthesis Agent, constrained by that context
→ IntegratedResearchView
```

Fundamental and Technical research retain independent conclusions, confidence,
evidence, risks, native horizons and methodologies. Neither layer nor synthesis may
rewrite, regenerate or reinterpret a stored source conclusion. Packaging must take
an immutable snapshot even where existing Python source models are mutable.

The V0.8A AI is named **Horizon Synthesis Agent**. It interprets research for a
horizon; it is not the existing fundamental Portfolio Manager synthesis component.
V0.8B's future Portfolio Decision Agent / Portfolio Manager will consume the view
plus position, weight, average cost, cash, concentration and deterministic portfolio
risk context. None of those inputs is required or used by V0.8A.

V0.8A emits no BUY/ACCUMULATE/HOLD/TRIM/AVOID action, ENTER, HOLD_POSITION or REDUCE
instruction. Existing fundamental recommendations remain visible as attributed
inputs. Their portfolio-specific application belongs to V0.8B.

## Existing-contract findings and input admission

The repository stores fundamental recommendations as `Buy`, `Accumulate`, `Hold`,
`Trim`, `Avoid`, not uppercase enum strings. Preserve the original spelling and
value exactly. Uppercase names in conceptual descriptions are vocabulary labels,
not a migration instruction. Fundamental confidence may be a numeric float; do not
round it to match technical integer confidence.

`InvestmentAnalysis` has no native horizon or verified market-as-of field.
`DecisionRecord.investment_horizon` is optional, and a save timestamp does not prove
research completion or evidence availability. Do not assign every legacy input
LONG or invent an as-of. TechnicalSignal supplies its native horizon and market
provenance but does not separately preserve generation time. Keep unknowns explicit.

Existing fundamental synthesis can include portfolio context. Removing its
`portfolio_assessment` field does not prove the recommendation was independent of
holdings. An admitted V0.8A fundamental input must have verified portfolio-independent
origin. Unknown or portfolio-conditioned origin is blocking for that input; do not
reverse-engineer a new recommendation or rerun research implicitly. A later source
adapter must establish this provenance without altering existing business logic.

Both admitted inputs must identify the same normalized ticker using existing project
rules. Reject ticker mismatch, invalid decision horizon, corrupted enums, malformed
required timestamps or packet/reference mismatch before AI invocation. Do not fuzzy
match tickers or choose the newest convenient source. A valid request with absent
or inadmissible research can instead produce a deterministic UNRESOLVED status with
reasons. Invalid caller input is an error, not a fabricated integrated view.

## Research horizons versus decision horizon

| Decision horizon | Meaning | Primary authority | Secondary responsibility |
| --- | --- | --- | --- |
| SHORT | 1–5 trading sessions | Technical | Fundamental major risks, thesis and event context |
| SWING | 1–4 weeks | Technical | Fundamental thesis, catalysts and context |
| MEDIUM | Approximately 1–6 months | Fundamental | Technical timing, setup and caution |
| LONG | 6+ months | Fundamental | Technical timing/context only |

These labels describe research scope, not exact evaluation checkpoints or holding
instructions. The approximate six-month boundary is resolved by the caller's explicit
MEDIUM or LONG selection, not inferred from elapsed time. No evaluation mapping is
introduced. Preserve Technical native `SHORT_TERM_1_TO_5_SESSIONS` or
`SWING_1_TO_4_WEEKS` and the original Fundamental horizon separately.

Different native and decision horizons are expected. A SHORT technical view can
inform LONG timing without becoming a long-term technical forecast. A SWING technical
view does not automatically prove a SHORT setup: a later deterministic applicability
policy must establish coverage of the selected primary horizon. Unknown primary
coverage blocks; secondary horizon mismatch can remain contextual with a warning.
Authority is responsibility, never a numeric weight or confidence vote. Secondary
research can change caution, timing, conflict and interpretation confidence; it
cannot independently reverse the primary thesis. Verified blocking risks may halt
synthesis without rewriting either conclusion.

## Step 5A — Technical generation selection

`technical-horizon-selection-v1` is the approved generation-selection policy,
implemented by `select_technical_horizon(decision_horizon)` in `horizon_integration.py`.

| Explicit decision horizon | Technical native horizon to generate |
| --- | --- |
| SHORT | SHORT_TERM_1_TO_5_SESSIONS |
| SWING | SWING_1_TO_4_WEEKS |
| MEDIUM | SWING_1_TO_4_WEEKS |
| LONG | SWING_1_TO_4_WEEKS |

MEDIUM/LONG use the existing 1–4 week research scope to supply current timing/setup
and context around the Fundamental primary thesis. This is an explicit product
choice, not a claim that SWING Technical research predicts medium/long outcomes.
The decision horizon stays MEDIUM/LONG; Technical is never relabeled as that horizon.

Generation selection chooses what to generate. Applicability determines whether
supplied research can participate and in what role. Authority assigns primary
responsibility. Freshness assesses the artifact under its own native horizon.
These remain separate policies: SHORT/SWING stay Technical-primary; MEDIUM/LONG
stay Fundamental-primary. Existing applicability, conflict classification and
readiness gates are unchanged, including support for other admissible supplied
native horizons as context. Selection neither certifies readiness nor adds weights.

`technical-freshness-v1` remains unchanged: short-native ages 0–2 are FRESH, 3–5
AGING, >5 STALE; swing-native ages 0–10 are FRESH, 11–20 AGING, >20 STALE, counted
in completed XNYS sessions. MEDIUM/LONG selection uses that same swing-native rule,
without a longer freshness window or new thresholds.

Unsupported decision horizons fail closed using existing exact DecisionHorizon
parsing; there is no default or string inference. The exported
`TECHNICAL_HORIZON_SELECTION_VERSION` lets future orchestration retain the policy
used alongside both horizons. Any mapping change requires a new version, never
retroactive reinterpretation. Step 5 combined orchestration is not implemented.

## Fundamental direction normalization

For conflict analysis only, propose the future identifier
`fundamental-direction-normalization-v1`:

| Exact stored recommendation | Derived direction |
| --- | --- |
| Buy / Accumulate | FAVORABLE |
| Hold | NEUTRAL |
| Trim / Avoid | UNFAVORABLE |

Keep recommendation and derived direction side by side. Reject unknown values;
never silently coerce STRONG_BUY or infer direction from prose. This coarse mapping
loses distinctions intentionally and cannot generate a recommendation. It is valid
only after portfolio-independent source admission.

## Freshness and missing-data gates

Freshness is deterministic, assessed against an explicit synthesis assessment-as-of,
not chosen by AI or a hidden wall clock. Source research-as-of, retrieval time,
creation/save time and synthesis completion time remain distinct. Future-relative
inputs cannot be used as already-known evidence. Verified temporal provenance is
required to establish availability; a timestamp alone is not proof of provider vintage.

| State | Definition | Primary input behavior | Secondary input behavior |
| --- | --- | --- | --- |
| FRESH | Meets the approved source-specific currentness policy | Normal use | Normal contextual use |
| AGING | Still admissible, but policy identifies reduced currentness | Allowed with explicit caution | Allowed with explicit caution |
| STALE | Outside policy's admissible currentness for intended use | Block normal synthesis; UNRESOLVED | Exclude from current directional/timing claims; retain historical context and warning |
| UNKNOWN | Required timing or freshness-policy facts unavailable | Block until resolved | Exclude from current claims; warn or block if a required risk check depends on it |

No day/session thresholds, numerical penalties or freshness formula are defined
here. Technical and Fundamental policies may differ and may consider source/event
coverage as well as elapsed time. Until the later policy is approved, freshness must
not default to FRESH. AGING may still block if a separate mandatory evidence check
fails. Stale secondary evidence cannot overturn a fresh primary conclusion.

**Blocking missing data** means required reliable synthesis cannot be formed for
the selected horizon. Examples: unavailable primary research; unverified primary
horizon/timing; missing primary core financial evidence for LONG; missing primary
technical evidence for SHORT; unresolved required event-risk coverage; absent cited
packet values; unknown portfolio independence of a required fundamental source.
Blocking gates yield INSUFFICIENT_EVIDENCE and UNRESOLVED with no AI synthesis call.

**Non-blocking missing data** means a defensible but explicitly limited view remains.
Examples: unavailable SMA200 for LONG where valid Fundamental research is primary
and admitted Technical evidence still supports limited timing context; an optional
secondary detail; missing secondary research when no mandatory cross-check depends
on it. No input is silently treated as neutral or zero.

A degraded primary-only view is permitted only when deterministic policy explicitly
marks the missing secondary input non-blocking. It must say it is one-sided, use
INSUFFICIENT_EVIDENCE for unassessable cross-layer agreement, and never claim ALIGNED.
It can have a constrained posture rather than UNRESOLVED if the primary interpretation
is reliable. Complete absence of both inputs always blocks. Later policy must define
required evidence by source/horizon; Step 1 does not invent indicator counts or thresholds.

## Deterministic conflict taxonomy

The classification is assigned before AI, with rule identifier, source references,
reason and applicable horizon metadata. AI may explain it but cannot select or replace it.

| Class | Precise meaning | Example |
| --- | --- | --- |
| ALIGNED | Admissible conclusions are materially compatible for the selected horizon; no opposing applicable claim | FAVORABLE + BULLISH; or two neutral views with adequate evidence |
| TIMING_CONFLICT | Favorable primary Fundamental thesis remains intact, but admitted secondary Technical context opposes immediate timing | LONG Accumulate + BEARISH |
| THESIS_CONFLICT | Opposing claims apply to the same relevant decision scope and cannot be explained solely by timing or different native scopes | BULLISH SHORT setup opposed by a supplied, structured, horizon-relevant fundamental risk constraint |
| HORIZON_DIVERGENCE | Apparent disagreement is explained by verified different scopes without a contradictory claim at the same relevant scope | Unfavorable long-term fundamentals alongside bullish short-term setup |
| INSUFFICIENT_EVIDENCE | Required reliability or applicability cannot be established; includes inability to assess cross-layer agreement | Stale primary; missing packet; unresolvable scope ambiguity |

Classification precedence for future deterministic rules:

1. Admission/blocking failure or insufficient classification metadata → INSUFFICIENT_EVIDENCE.
2. Verified opposing same-scope material claims → THESIS_CONFLICT.
3. Fundamental-primary favorable thesis plus contrary eligible Technical timing, without a same-scope thesis contradiction → TIMING_CONFLICT.
4. Otherwise, opposing directions with verified distinct native applicability → HORIZON_DIVERGENCE.
5. Otherwise, compatible directions and no applicable opposition → ALIGNED.
6. Ambiguity not resolved by these inputs → INSUFFICIENT_EVIDENCE, never an AI tie-break.

Direction pairs alone do not prove materiality, catalyst relevance or horizon
coverage. Later Python policy must operate on approved structured applicability/risk
metadata with evidence references; it must not infer arbitrary prose meaning or ask
the synthesis LLM to supply its own gates. If such metadata does not exist, report
the ambiguity. Different horizons alone do not imply conflict. Neutral is absence
of directional commitment, not evidence of opposition. Preserve subsidiary cautions
and reasons even when one higher-precedence classification is selected.

## Research timing posture

| Posture | Meaning |
| --- | --- |
| FAVORABLE_NOW | Current admitted setup/alignment supports the decision horizon; no order implied |
| WAIT_FOR_CONFIRMATION | Potentially constructive thesis/setup, but supplied conditions or timing caution prevent treating it as favorable now |
| UNFAVORABLE_NOW | Current setup is unfavorable for the selected horizon; another horizon may remain constructive |
| NO_ACTION | Reliable evidence is understood and supplies no compelling current research timing stance |
| UNRESOLVED | Reliable interpretation cannot responsibly be formed |

WAIT_FOR_CONFIRMATION must cite an existing condition or documented timing concern;
it must not invent a trigger or level. NO_ACTION is an informed stance, not a synonym
for missing data, stale primary evidence or a failed model call. No posture is an
instruction based on ownership. A valid NEUTRAL input does not force UNRESOLVED.

## Decision matrix: interpretation guardrails

All 36 pairs below assume admitted, sufficiently fresh, applicable evidence and no
blocking concern. The conflict code is a default subject to the deterministic
precedence above, **not an LLM choice**. Postures are permitted ranges, not mandatory
lookup outputs. AI reasons within the deterministically narrowed range, cites supplied
evidence and retains disagreement. Blocking gates override every cell to UNRESOLVED.

Codes: A = ALIGNED; T = TIMING_CONFLICT; H = HORIZON_DIVERGENCE.
H becomes THESIS_CONFLICT only with verified opposing same-scope claims; ambiguous
scope becomes INSUFFICIENT_EVIDENCE. FAV = FAVORABLE_NOW; WAIT = WAIT_FOR_CONFIRMATION;
UNFAV = UNFAVORABLE_NOW; NONE = NO_ACTION. WAIT requires supplied support as above.

### SHORT — Technical primary

Fundamental influence is risk/event/thesis context. Unfavorable fundamentals alone
cannot erase an admissible short setup; favorable fundamentals cannot reverse a
bearish short setup. A verified blocking event concern may stop synthesis.

| Fundamental | Technical | Default conflict | Allowed interpretation / posture range |
| --- | --- | --- | --- |
| FAVORABLE | BULLISH | A | Constructive short setup with thesis context; FAV, WAIT |
| FAVORABLE | NEUTRAL | A | Favorable thesis supplies no short trigger; NONE, WAIT |
| FAVORABLE | BEARISH | H | Weak short setup despite favorable other-horizon thesis; UNFAV, WAIT |
| NEUTRAL | BULLISH | A | Constructive short setup, no fundamental endorsement implied; FAV, WAIT |
| NEUTRAL | NEUTRAL | A | No compelling short stance; NONE |
| NEUTRAL | BEARISH | A | Unfavorable short setup; UNFAV, NONE |
| UNFAVORABLE | BULLISH | H | Constructive short setup with explicit thesis risk; FAV, WAIT |
| UNFAVORABLE | NEUTRAL | A | No positive short setup, unfavorable context retained; NONE, UNFAV |
| UNFAVORABLE | BEARISH | A | Unfavorable short setup and context; UNFAV, NONE |

Prohibited in every SHORT cell: promote Fundamental confidence into an overriding
vote, erase thesis risks, interpret technical bearishness as a short-sale instruction,
or manufacture a favorable technical signal from a Fundamental recommendation.

### SWING — Technical primary

Fundamental catalysts/thesis may meaningfully qualify the swing interpretation,
but cannot create a missing technical setup. Supplied catalyst relevance must be
validated; the agent cannot introduce outside news or infer event timing.

| Fundamental | Technical | Default conflict | Allowed interpretation / posture range |
| --- | --- | --- | --- |
| FAVORABLE | BULLISH | A | Constructive swing setup with thesis support; FAV, WAIT |
| FAVORABLE | NEUTRAL | A | Thesis constructive, swing confirmation absent; NONE, WAIT |
| FAVORABLE | BEARISH | H | Unfavorable swing setup despite thesis; UNFAV, WAIT |
| NEUTRAL | BULLISH | A | Constructive swing setup without thesis upgrade; FAV, WAIT |
| NEUTRAL | NEUTRAL | A | No compelling swing stance; NONE |
| NEUTRAL | BEARISH | A | Weak swing setup; UNFAV, NONE |
| UNFAVORABLE | BULLISH | H | Setup may remain valid; explicitly retain unfavorable thesis; FAV, WAIT |
| UNFAVORABLE | NEUTRAL | A | No affirmative swing setup; NONE, UNFAV |
| UNFAVORABLE | BEARISH | A | Unfavorable swing interpretation; UNFAV, NONE |

Prohibited in every SWING cell: rewrite unfavorable fundamentals as favorable because
price strength exists, promote long-term valuation alone into swing timing, or treat
horizon divergence as proof that either source was wrong.

### MEDIUM — Fundamental primary

Technical context can materially narrow present timing posture and add caution,
more than for LONG, without numeric weighting or rewriting the primary thesis.

| Fundamental | Technical | Default conflict | Allowed interpretation / posture range |
| --- | --- | --- | --- |
| FAVORABLE | BULLISH | A | Favorable medium thesis and current setup; FAV, WAIT |
| FAVORABLE | NEUTRAL | A | Favorable thesis, no technical timing endorsement; FAV, WAIT, NONE |
| FAVORABLE | BEARISH | T | Thesis favorable; current setup cautions; WAIT, UNFAV |
| NEUTRAL | BULLISH | A | Timing strength does not upgrade neutral thesis; NONE, WAIT |
| NEUTRAL | NEUTRAL | A | No compelling medium stance; NONE |
| NEUTRAL | BEARISH | A | Neutral thesis with timing caution; NONE, UNFAV |
| UNFAVORABLE | BULLISH | H | Strength does not repair medium thesis; UNFAV, NONE |
| UNFAVORABLE | NEUTRAL | A | Unfavorable thesis without timing offset; UNFAV, NONE |
| UNFAVORABLE | BEARISH | A | Unfavorable thesis and setup; UNFAV, NONE |

Prohibited in every MEDIUM cell: bullish Technical alone upgrades the Fundamental
thesis, bearish Technical alone replaces it with Avoid, or timing posture is
presented as a changed primary recommendation.

### LONG — Fundamental primary

Technical contributes timing/context only. Short weakness can justify patience or
an unfavorable-now posture while the long-term thesis remains explicitly favorable.

| Fundamental | Technical | Default conflict | Allowed interpretation / posture range |
| --- | --- | --- | --- |
| FAVORABLE | BULLISH | A | Favorable long thesis with supportive present context; FAV, WAIT |
| FAVORABLE | NEUTRAL | A | Favorable thesis, limited timing information; FAV, WAIT, NONE |
| FAVORABLE | BEARISH | T | Favorable long thesis; timing caution retained; WAIT, UNFAV |
| NEUTRAL | BULLISH | A | Short strength does not establish favorable long thesis; NONE, WAIT |
| NEUTRAL | NEUTRAL | A | Sufficient evidence, no compelling long stance; NONE |
| NEUTRAL | BEARISH | A | Neutral long thesis with near-term caution; NONE, UNFAV |
| UNFAVORABLE | BULLISH | H | Short strength does not repair unfavorable long thesis; UNFAV, NONE |
| UNFAVORABLE | NEUTRAL | A | Unfavorable long thesis retained; UNFAV, NONE |
| UNFAVORABLE | BEARISH | A | Unfavorable thesis with compatible timing context; UNFAV, NONE |

Prohibited in every LONG cell: Accumulate + BEARISH becomes Avoid solely from
Technical; unfavorable fundamentals become favorable solely from BULLISH; immediate
price movement is represented as a long-term forecast. UNFAVORABLE + BULLISH is
THESIS_CONFLICT only if applicable same-scope evidence establishes more than different
horizons. Default H must not hide a verified same-scope contradiction.

## Conceptual IntegratedResearchView contract

Prefer composition of immutable admitted source packets and deterministic context,
not duplicated free-text copies that can diverge. The following are conceptual fields,
not Python definitions or a persistence schema.

| Group | Requiredness and ownership |
| --- | --- |
| Identity | Required normalized ticker, selected decision_horizon; trusted application fields |
| Source references | Required slots for Fundamental and Technical; each contains immutable packet identity/version or explicit absence/rejection reason |
| Source conclusions | Exact original recommendation/signal, native horizon, confidence; copied, never AI-owned; unknown native metadata explicitly nullable |
| Source time/provenance | Original as-of/retrieval/save times where known, technical latest session, provider/data/adjustment metadata and evidence packet identity; copied |
| Deterministic context | Required primary_authority, freshness for each slot, conflict classification, rule reasons/IDs, allowed posture set, blocking/non-blocking missing data, applicability status |
| Integrated interpretation | Cited synthesis_summary / integrated_research_view narrative, timing_posture and independent synthesis_confidence; AI-generated only for admissible requests |
| Citations | Supporting/conflicting Fundamental and Technical reference lists; AI selections validated against supplied qualified packet IDs |
| Invalidation | Separate immutable Fundamental and Technical condition lists; generated integrated_invalidation_summary may only summarize them with references |
| Risks/missing data | Original source lists plus deterministic admission warnings preserved; AI may summarize with attribution but not remove blockers |
| Versions | Required design/context/normalization/freshness/matrix versions for future execution plus original source methodology versions, unknowns explicit |
| Timing | Explicit assessment_as_of and application-owned synthesis_timestamp in aware UTC; completion time must not be used to recalculate input eligibility |

For a blocked valid request, emit only a deterministic unresolved envelope/context:
UNRESOLVED posture, blocking reasons, preserved available input metadata, no fabricated
AI narrative and synthesis_confidence unavailable. A failed LLM call is an explicit
failure, not NO_ACTION, confidence=0 or a fallback recommendation. For a successful
view, confidence conceptually remains integer 0–100 with the semantics below.

Required source packets must contain enough original evidence to resolve every cited
ID. IDs are qualified by source and immutable packet identity: Fundamental F-local
IDs and Technical Txxx IDs must not collide or be rebound by a future catalog. Preserve
original ordered lists, numeric units and RETRIEVED_FACT / CALCULATED_METRIC /
AI_INTERPRETATION / FORECAST distinctions. Do not relabel source forecasts as facts.
A legacy record with only unresolved references is not an auditable complete packet.
No full OHLCV retrieval, reconstruction or current quote substitution occurs here.

Proposed future integration identifiers should be separate from source versions:
`horizon-synthesis-context-v1`, `horizon-decision-matrix-v1` and
`horizon-synthesis-v1`, alongside the proposed direction normalization identifier.
They are design proposals, not existing supported runtime policies. Freshness gets
its own identifier when approved; missing policy must not masquerade as implemented v1.
Historical source identifiers are never overwritten with current constants.

## Invalidation and confidence rules

Preserve each supplied condition and its evidence references unchanged. An integrated
summary can describe overlapping or conflicting implications but cannot add a
financial fact, numerical level, unsupported trigger or new condition. If a source
has no condition, record absence; do not invent one. Natural-language conditions
are not machine-evaluated by this design. Unknown trigger status is not “not triggered.”

Specialist confidences remain independent, with their original numeric precision.
Never average them, weight them or use them as votes. `synthesis_confidence` means
confidence that the combined interpretation is justified by current available
evidence for the selected decision horizon. It is neither profit probability,
backtested accuracy, expected return nor evidence of predictive skill.

Completeness, freshness, agreement, authority clarity, missing data and unresolved
invalidation concerns may inform the separate judgment. There is no formula, numerical
penalty, cap or scoring algorithm in Step 1. Authority constraints and blockers hold
regardless of confidence; high confidence cannot authorize a prohibited posture.

## Future validation and test requirements

Before an LLM call, deterministic Python must validate admission, source identity,
temporal availability, native coverage, freshness, missing-data severity, authority,
normalized direction, conflict and allowed posture range. Post-call validation must
reject out-of-range postures, invented citations, changed trusted fields and unsupported
conditions. Schema checks alone cannot prove all semantic correctness: subsequent
implementation needs explicit structured claim/citation constraints and adversarial
tests, not an assertion that arbitrary prose can be perfectly checked.

Required future tests include:

- Ticker mismatch, unsupported decision horizon, bad enums and corrupted packet rejection.
- Native horizon preservation, including missing legacy values and legitimate cross-horizon context.
- Exact four-horizon authority assignment and five-recommendation normalization; original spelling retained.
- All 36 matrix cells, deterministic precedence, reordered packet stability and ambiguous scope refusal.
- Stale primary blocks; stale secondary cannot drive current claims; UNKNOWN behavior follows role and risk requirements.
- No freshness defaults or invented thresholds; future-relative source exclusion and caller time validation.
- Blocking/non-blocking missing-data behavior, absent source slots and honest primary-only degraded views.
- No confidence averaging; exact source confidence preserved; unavailable synthesis confidence on blockers.
- Qualified evidence IDs, packet values, units and classifications preserved; invented IDs rejected.
- Invalidation lists/ordering preserved; unsupported new trigger/level rejected; unknown trigger status explicit.
- Disagreement retained; secondary cannot arbitrarily override primary; numeric confidence cannot bypass authority.
- NO_ACTION distinct from UNRESOLVED and model failure; WAIT cites supplied conditions/concerns.
- Portfolio fields not needed or consumed; portfolio-conditioned source origin rejected, not silently sanitized.
- No trading/brokerage instruction or fallback action; no mutation of either source.
- Source and synthesis methodology provenance and timestamps preserved independently.
- Deterministic context created before AI, AI cannot change context, and output lies within the narrowed matrix range.
- No provider calls or implicit research regeneration; all future unit tests use mocked AI and immutable fixtures.

## Scope exclusions and next-step gate

No V0.8B action design, position/trade sizing, broker, orders, stops, price targets,
options, intraday execution, paper trading, prediction model, numerical layer weights,
autonomous strategy adaptation, optimization, provider, database schema, dependencies,
UI implementation or LLM implementation is introduced. No OpenAI or Alpha Vantage
calls are required for this design.

Ready for human design review. Step 2 may implement the approved conceptual contracts
and deterministic policy scaffolding after review, but operational synthesis must
wait for explicit freshness thresholds, horizon applicability/material-risk rules,
source provenance admission and ambiguity handling to be approved and tested. These
are deliberate policy dependencies, not permission to invent defaults during coding.

## Step 2 implementation clarification

`src/horizon_integration.py` implements `horizon-synthesis-context-v1`,
`fundamental-direction-normalization-v1`, `horizon-research-admission-v1` and
`horizon-conflict-foundation-v1`. It does not implement the synthesis agent or the
full matrix posture contract. Decision horizons and authority are enums; original
repository title-case Fundamental recommendations remain exact.

Admission and participation are separate. A structurally admitted artifact can
still be unusable due to STALE or UNKNOWN freshness. The pure participation helper
represents all four states; it does not certify externally asserted freshness.
The assembled context always uses UNKNOWN with no freshness policy version: no
threshold policy exists. There is deliberately no caller override that can mark a
context FRESH. Authority records the declared responsibility, while
`usable_primary_authority` is unavailable until policy gates can be satisfied.

The Fundamental source envelope requires a DecisionRecord, its original evidence
package and original catalog, explicit research-as-of/availability, and references
to caller verification of timing and portfolio-independent origin. These references
are trusted caller attestations, not independent authentication. No current dashboard
adapter supplies them automatically. Bare legacy records do not pass admission;
save timestamps alone are insufficient. Native horizons are preserved as original
text, not guessed or reclassified. Fundamental methodology is explicitly unknown
where the legacy contract has no identifier. The admission version identifies the
adapter checks, not a retroactive research methodology.

The Technical adapter accepts TechnicalSignalRecord, reuses its historical structural
validation, checks supported source versions and verifies calendar/timestamp consistency
without rerunning features, evidence or analysis. Transient signals must first have a
trustworthy availability envelope; no automatic save is introduced. Both source packets
are copied as immutable JSON, with detached accessors. Fundamental E IDs and Technical
T IDs remain in separate named source packets. Original conditions, references, missing
data and provenance are retained, including classification paths in fundamental evidence.

Conditional conflict helpers implement the Step 1 precedence on explicit validated
scope facts. They cannot infer scope/materiality from prose. Operational contexts use
INSUFFICIENT_EVIDENCE until freshness, applicability and missing-data severity policies
exist. The helpers' `evidence_ready`/scope arguments are policy-test inputs, not an
admission bypass in the builder. Same-scope opposition, distinct-scope divergence and
timing conflict are independently testable without producing recommendations.

Missing primary research is explicitly blocking. Missing secondary research is
reported without asserting it is safe to omit: the required-cross-check policy remains
unresolved and blocks authorization. Missing features in admitted secondary Technical
research are recorded as non-blocking feature absences for a Fundamental-primary
horizon; that does not waive the separate missing-data/risk-policy gate. Primary
Technical missing features retain unresolved-severity warnings. Core Fundamental
missing-data prose is never heuristically classified by keyword or feature count.

Consequently Step 2 builds inspectable, immutable **blocked contexts**, not
LLM-ready operational views. The next step must approve source applicability,
freshness and missing-data requirements before enabling synthesis. No schema,
dashboard, provider, LLM, existing research or evaluation behavior changes here.


## Step 3A policy authority

[Freshness & Provenance Policy](V0_8A_FRESHNESS_PROVENANCE_POLICY.md) defines the
approved `technical-freshness-v1` boundaries and prospective
`fundamental-provenance-v1` contract. It supersedes earlier deferred Technical
threshold language in this document. The Step 2 clarification above describes
existing implementation, not the newly approved prospective behavior.
Fundamental operational FRESH is limited to trusted same-run/refreshed acquisition,
not proof of absence of material events. Historical event currentness remains unknown;
no calendar-age shortcut or legacy version backfill is authorized. Step 3 implementation
and prospective pipeline/dashboard wiring are not completed by this design update.

## Step 3B runtime clarification

The [policy document's implementation section](V0_8A_FRESHNESS_PROVENANCE_POLICY.md#step-3b-implementation)
now describes approved freshness, prospective capture and conservative readiness.
It supersedes Step 2's universal UNKNOWN placeholder behavior. Legacy Fundamental
freshness stays UNKNOWN; supported same-run provenance can qualify operationally.
No Horizon Synthesis Agent or AI output fields are implemented. Unresolved risk,
native applicability and missing-data dependencies remain explicit blockers.

## Step 3C — readiness integrity boundary

Readiness is derived metadata, not caller authority. Frozen dataclasses can still
be constructed or replaced. Every future synthesis consumer must call
`require_synthesis_ready(context)` immediately before OpenAI and use its returned,
recomputed context. Checking a readiness string alone is prohibited.

The normal builder retains the immutable current Fundamental sidecar (including its
existing process-bound provenance capability), immutable TechnicalSignalRecord and
integration run ID. The boundary validator reruns the same builder with these sources,
the selected horizon and explicit assessment timestamp, using the real supported
calendar rather than a caller-injected calendar. It compares the complete derived
context, including versions, admissions, freshness, authority, applicability, conflict,
missing data and warnings. Any mismatch or recomputed blocker raises
SynthesisReadinessError with deterministic reasons. Original blocker reasons are
retained alongside recomputed reasons. No fallback or regeneration occurs.

The validator returns a newly recomputed context for valid ready inputs. No identity
flag or hash is accepted as proof of readiness. Existing Fundamental provenance
verification remains a prerequisite, not a substitute for policy recomputation.
Legacy mutable envelopes are not retained as trusted sources; their detached historical
metadata remains visible, and they cannot qualify current synthesis. No historical
records or Step 3B readiness policies change.

## Step 4 implementation

The [Horizon Synthesis Agent](V0_8A_HORIZON_SYNTHESIS_AGENT.md) now implements one
guarded structured interpretation call and an immutable IntegratedResearchView.
Step 4 explicitly allows UNRESOLVED for residual interpretation ambiguity in ready
contexts, in addition to each matrix row's ranges. It never admits blocked contexts.
All original conclusions/conditions/provenance remain in the validated source context.
No existing readiness policy or portfolio boundary is weakened.

## Step 5B — Combined research sequencing

`combined-research-sequencing-v1` selects `TECHNICAL_THEN_FUNDAMENTAL` for new
combined runs. Machine-readable exports in `horizon_integration.py` are
`COMBINED_RESEARCH_SEQUENCING_VERSION`, `COMBINED_RESEARCH_SEQUENCE` and the
`ResearchSequence` enum (unsupported sequence values fail closed). These declarations
do not execute research or accept alternate policy versions.

The future orchestrator accepts an explicit decision horizon, calls the existing
`select_technical_horizon`, completes Technical research with its real timestamps,
then completes Fundamental research and captures its trusted prospective sidecar.
It uses `integration_as_of = fundamental.available_at`, builds the context, and calls
`require_synthesis_ready` before Horizon Synthesis. Preserve the sequencing and
selection versions independently in eventual combined-run provenance.

Execution order is not analytical authority: SHORT/SWING remain Technical-primary;
MEDIUM/LONG remain Fundamental-primary. Selection, applicability and conflict policy
are unchanged. Technical freshness is evaluated under its native horizon at integration
time. AGING, STALE or UNKNOWN are handled by existing gates, never by an automatic
refresh loop. A blocked run is a valid outcome.

Technical failure stops before Fundamental. Fundamental failure stops before
integration/synthesis. Integration/readiness failure stops before synthesis; synthesis
failure never regenerates either input. No automatic retry or fallback is approved.
No source timestamps are backdated, synchronized or overwritten. Run identity is
separate from timestamps; this step does not redesign identity or grant a new
Fundamental time-validity window. Future ordering/currentness changes require a new
policy version, not reinterpretation of historical results.

This step implements policy representation only. Step 5 combined orchestration is
not implemented. Existing provenance, material-event coverage limitations and all
readiness gates remain in force; ordering alone does not guarantee readiness.

## Step 6A — Risk applicability

`risk-applicability-v1` supersedes the earlier blanket unresolved-risk blockers.
For otherwise qualified research, the existence of Fundamental major_risks or
bear_case and Technical risk_notes or valid conflicting_evidence_ids is non-blocking.
These are original synthesis inputs, preserved with source confidence, conclusions,
conditions and evidence. Both primary and secondary sources retain adverse evidence.

Admission, provenance, exact run/completion currentness, native-horizon freshness,
temporal integrity, methodology and missing-data requirements remain unchanged.
Invalid Technical conflicting IDs fail existing catalog-reference validation.
Fundamental risk statements carry existing evidence_refs; trusted current artifacts
retain the pipeline-validated packet and origin binding. No references or semantic
severity are invented. Legacy artifacts receive no new provenance qualification.

Risk applicability is separate from authority, cross-source conflict classification
and missing-data severity. The deterministic layer neither ranks risk probability/
impact nor decides whether a risk changes the investment thesis. Existing Horizon
Synthesis interprets the admitted packet; its prompt/schema already transport both
risk collections and are unchanged. Presence of risk alone implies neither ALIGNED
nor THESIS_CONFLICT. All other blocking conditions still stop synthesis.

IntegrationContext retains `risk_applicability_version`; authoritative readiness
recomputation compares it, rejecting unsupported or inconsistent versions. Historical
contexts are not relabeled. Future policy changes require a new version. No source
records, persistence, dashboard or dependency direction are changed in this step.
No live validation was performed. Step 6 release review remains pending.


## Step 6R — Source-available invalidation

`source-available-invalidation-v1` supersedes the unconditional generated invalidation
reference requirement. `_packet` derives availability exclusively from retained admitted
F_INVALIDATION and T_INVALIDATION conditions. When either source provides invalidations,
`invalidation_summary.condition_ids` must contain at least one valid invalidation ID.
Confirmation IDs never substitute, and unknown IDs remain rejected. When neither source
provides invalidations, that collection may be empty; no source condition is invented.
Absence alone does not change admission or readiness. All independent gates remain intact.

The packet appends `NO_SOURCE_INVALIDATION_CONDITION` to its existing limitations list
only when no invalidations exist. The existing exact ordered `acknowledged_limitations`
contract requires this token in accepted output. It is not a condition or a new source
missing-data assertion. Sources and context remain unchanged. The version is supplied
in packet policy_versions.invalidation and retained as IntegratedResearchView's frozen
invalidation_policy_version. No output-schema field was added.

The prompt explicitly describes both availability cases, confirmation non-substitution,
summary grounding in both namespaces and exact limitation ordering. Conditions still
require FORECAST; empty references do not exempt predictive prose from FORECAST rules.
Original condition text, evidence and conclusions remain preserved in the context.
No live validation occurred; V0.8A is not release-signed-off.
