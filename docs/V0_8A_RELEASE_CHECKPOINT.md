# V0.8A — Horizon-Aware Research Synthesis

> Current status: final release review **PASS WITH FIXES (documentation only)**.
> Active Technical/Horizon generation is v2 under `evidence-first-assembly-v1`.
> G3 completed one controlled live validation; 556 tests pass. Earlier step findings
> below are chronological historical records, superseded by the G3 and final review
> sections where applicable. Ready for separately authorized release publication;
> no commit, tag or push has been performed. Research-only; V0.8B remains future work.


## Objective and architecture

V0.8A combines independent Fundamental and Technical research for an explicit
research decision horizon. Deterministic admission, freshness, provenance,
applicability and readiness precede AI interpretation. It adds no portfolio actions.

Ticker + decision horizon → Technical horizon selection → Technical research →
Fundamental research → integration builder → require_synthesis_ready → Horizon
Synthesis → immutable IntegratedResearchView (inside CombinedResearchResult).

## Horizons, selection and authority

| Decision horizon | Technical native horizon | Primary authority |
| --- | --- | --- |
| SHORT (1–5 sessions) | SHORT_TERM_1_TO_5_SESSIONS | TECHNICAL_PRIMARY |
| SWING (1–4 weeks) | SWING_1_TO_4_WEEKS | TECHNICAL_PRIMARY |
| MEDIUM (approximately 1–6 months) | SWING_1_TO_4_WEEKS | FUNDAMENTAL_PRIMARY |
| LONG (6+ months) | SWING_1_TO_4_WEEKS | FUNDAMENTAL_PRIMARY |

`technical-horizon-selection-v1` selects native research, not analytical authority.
MEDIUM/LONG Technical input is still 1–4 week timing/context, not a longer forecast.
Fundamental native scope is a separate explicit input; unsupported scope fails closed.

`combined-research-sequencing-v1` requires TECHNICAL_THEN_FUNDAMENTAL. Execution
order does not rank investment authority. No numeric research weights are used.

## Freshness, timestamps and provenance

`technical-freshness-v1` counts completed XNYS sessions after the source session.
Short-native ages 0–2 are FRESH, 3–5 AGING, >5 STALE. Swing-native ages 0–10 are
FRESH, 11–20 AGING, >20 STALE. Weekends, holidays and actual half-day closes follow
the existing calendar. Freshness is separate from outcome evaluation checkpoints.

`fundamental-provenance-v1` preserves prospective pipeline identity, evidence,
methodologies, run identity, acquisition boundaries and completion time. Integration
as-of equals Fundamental available_at exactly. There is no elapsed-time grace period
or claim of continuous material-event coverage. Legacy provenance is never upgraded.
Technical native times stay intact; the existing transient availability envelope is
created without a store write. No backdating or shared completion time is fabricated.

## Risk, conflict and trust

`risk-applicability-v1` admits valid adverse/conflicting evidence as synthesis input.
Its existence alone is non-blocking. Independent evidence, missing-data, freshness,
provenance and temporal gates remain authoritative. It estimates no severity,
probability or financial impact and does not decide whether a thesis is invalidated.

Conflict vocabulary remains ALIGNED, TIMING_CONFLICT, THESIS_CONFLICT,
HORIZON_DIVERGENCE and INSUFFICIENT_EVIDENCE. It relates source conclusions, not risk
counts. Evidence namespaces and original conditions remain separate and immutable.

`require_synthesis_ready` recomputes from retained sources immediately before
synthesis; the synthesis entry point validates independently again. Frozen objects
and caller-set readiness flags are not proof. Forged states and unsupported policy
versions fail closed. Nested provenance is authoritative; selection/sequencing
versions are retained on the combined result without duplicating source manifests.

## Output and failure behavior

The existing strict Responses schema and semantic validators produce research-only
IntegratedResearchView. Timing postures are FAVORABLE_NOW, WAIT_FOR_CONFIRMATION,
UNFAVORABLE_NOW, NO_ACTION and UNRESOLVED. These are not portfolio instructions.
Synthesis confidence is independent 0–100 evidence strength, not profit probability
or an average of specialist confidence. Original recommendations/signals are retained.

INPUT, TECHNICAL_RESEARCH, FUNDAMENTAL_RESEARCH, INTEGRATION, READINESS and
HORIZON_SYNTHESIS failures stop downstream execution. No retry, refresh loop,
source rerun or fabricated fallback occurs. Readiness failure reasons survive.
No DecisionRecord/TechnicalSignalRecord save, evaluation enrollment/collection,
integrated-view persistence, holdings/cash access or brokerage/trading occurs.

## Dependency hardening and tests

`technical_pipeline.py` now owns the single shared non-rendering Technical action.
Both the dashboard adapter and horizon_pipeline call it. Backend stage errors contain
safe metadata; the dashboard retains its previous sanitized messages and stage logs.
No indicator, provider, model, timestamp or call-count behavior changed. No dependency
was added and no integrated dashboard feature was introduced.

Baseline: 477 tests. Final suite: 479 passing. Unit external calls are mocked;
zero live Alpha Vantage/OpenAI unit requests. All four horizons exercise realistic
nonempty risks, shared Technical features/evidence orchestration, one mocked analyst,
Fundamental provenance, trusted readiness and one mocked synthesis request. Additional
assertions cover source preservation, policy metadata, early-stage downstream call
counts, run mismatch and blocking missing data. Existing forged, invalid evidence,
staleness, time and dashboard regressions pass. No database access is permitted in
combined orchestration tests.

## Live validation

One authorized AAPL/MEDIUM attempt ran Technical then Fundamental with selected
SWING_1_TO_4_WEEKS research. Both source stages completed, the integration builder
returned, and orchestration readiness validation passed. The Horizon Synthesis
entry point was invoked once and failed before an additional OpenAI request.
Observed counters: 9 Alpha Vantage request-function invocations, 2 OpenAI
request_text invocations, 1 Horizon Synthesis invocation. No retry, persistence or
portfolio action occurred; no IntegratedResearchView was returned.

The retained safe error identifies HORIZON_SYNTHESIS only. It does not establish
the underlying exception or distinguish packet/schema preparation from repeated
readiness validation. The two OpenAI requests belonged to the completed source
research stages. This is an unresolved live integration failure, not a policy block
or demonstrated external API error. No second live run was made. Source-preservation
and final output checks remain supported by mocked tests, not a successful live view.

## Known limitations and deferred work

- Semantic validation cannot prove full natural-language entailment or all forecasts.
- Risk eligibility is not severity, likelihood, impact or thesis-invalidation analysis.
- Fundamental event currentness is bounded by prospective provenance, not continuous
  monitoring; required missing-data conditions may still block normal research.
- Technical research uses daily RAW OHLCV, with corporate-action discontinuities and
  provider-vintage limitations. MEDIUM/LONG Technical input remains shorter context.
- No portfolio-aware output, integrated persistence/history or evaluation exists.
- The process-bound Fundamental capability is not remote authentication/portable trust.

Possible later work includes V0.8B portfolio-aware decision context, dashboard exposure,
integrated-view persistence/history and prospective evaluation. None is implemented
or promised as the immediate next feature. No predictive accuracy, profitability,
market outperformance or trading capability is claimed.

## Release conclusion

NOT READY. The 479-test suite passes and the backend/dashboard dependency has been
corrected, but the single live run exposed an unresolved pre-request Horizon
Synthesis failure. This differs from an accepted independent readiness block.
Diagnose it with safe bounded stage/substage metadata and offline reproduction before
release sign-off. No policy or prompt was weakened. No commit, tag or push was made.

### Step 6B follow-up

Safe pre-request substage/type diagnostics are now preserved through the combined
pipeline. Offline realistic input reaches the mocked request, but the original live
payload was not retained and its exact trigger remains unknown. No root-cause fix
or live retry is claimed. Release remains NOT READY; see the synthesis-agent
diagnostic trace for coverage and required next-run diagnostic metadata.

### Step 6C — Single diagnostic attempt

One AAPL/MEDIUM attempt selected SWING_1_TO_4_WEEKS and stopped at
TECHNICAL_RESEARCH. Counters: Technical 1, Fundamental 0, Horizon Synthesis entry 0,
Horizon Synthesis OpenAI requests 0; total Alpha Vantage request-function calls 1
and OpenAI request-function calls 1. No retries, source reruns or persistence occurred.

Retained substage, error type and failure classification were null. This earlier
failure neither reproduces nor explains the original synthesis pre-request trigger.
No completed integration context existed for a sanitized synthesis reproduction
fixture. The evidence is insufficient to distinguish provider/API failure from
Technical validation failure. No production change or second live call was made.
Release remains NOT READY. Next work should preserve safe Technical stage/type
through the combined error boundary and diagnose offline before another authorization.

### Step 6D — Technical diagnostic propagation

Baseline 482 and final 484 tests pass offline. `horizon_pipeline` now catches
`TechnicalResearchError` before its generic catch, preserving `stage=TECHNICAL_RESEARCH`,
the backend stage as `substage`, its `exception_type` as `error_type`, and the fixed
classification `TechnicalResearchError`. Previously the generic catch discarded
these existing fields. No research behavior or dashboard translation changed.

| Shared Technical operation | Retained substage | Existing exception information |
| --- | --- | --- |
| normalize_symbol / aware_utc / horizon and market checks | INPUT | Underlying exception class; invalid horizon/market is ValueError |
| retrieve_historical_ohlcv | MARKET_DATA | Underlying exception class, commonly RuntimeError for retrieval failures |
| build_technical_feature_snapshot | FEATURES | Underlying validation/programming exception class |
| build_technical_research_snapshot / build_technical_evidence_catalog | EVIDENCE | Underlying validation/programming exception class |
| analyze_technical_snapshot | TECHNICAL_ANALYST | Underlying exception class; API RuntimeError and malformed JSON ValueError remain distinguishable at this level |

The backend wrapper carries no raw exception message, provider response body,
OpenAI output or prompt field. It uses `raise ... from None`; implicit Python
exception context can still exist in-process, but trace display is suppressed and
context is not serialized or exposed by the diagnostic contract. The Horizon wrapper
retains that suppression. The dashboard continues logging stage/type and displaying
its existing fixed sanitized message. Unexpected errors inside a wrapped operation
retain their class and stage; errors outside these wrappers still use the existing
generic combined error path without an invented diagnosis.

Mocked tests cover retrieval, features, both evidence builders, analyst API-style
failure, malformed analyst JSON through the real parser, and unexpected KeyError.
Each stops Fundamental and synthesis calls, without retries, source reruns, fallback
results or database access. Existing four-horizon success and dashboard tests pass.
No live requests were made. Step 6C never reached synthesis; its Technical trigger
and the original Step 6 synthesis trigger remain unknown. This is diagnostic
propagation hardening, not a root-cause fix or release-readiness claim.

### Step 6E — Single full-pipeline diagnostic

One authorized AAPL/MEDIUM attempt selected SWING_1_TO_4_WEEKS and stopped at
TECHNICAL_RESEARCH / TECHNICAL_ANALYST / ValueError, with fixed classification
TechnicalResearchError. Technical research and Technical Analyst were each invoked
once; Fundamental, integration, readiness and Horizon Synthesis were not reached.
Counters: Alpha Vantage request-function 1; OpenAI request-function 1; Horizon
Synthesis OpenAI requests 0. No retry, source rerun, persistence or portfolio/brokerage
access occurred. No production code was changed for this diagnostic step.

The safe metadata now identifies the Technical Analyst boundary, but not which
ValueError condition triggered. It does not establish an implementation, policy,
provider or API defect. Step 6C's earlier Technical-stage failure recurred at the
stage level only; an identical root cause cannot be claimed. The original Step 6
synthesis trigger was not reached. Next work is an offline Technical Analyst
validation diagnosis; no further live request is authorized by this step.

### Step 6F — Offline Technical Analyst validation diagnostics

Baseline 484; final 488 tests pass. No live requests. Step 6E established only
TECHNICAL_ANALYST / ValueError after one request; its exact validation condition
was not retained. The historical Technical trigger and original Step 6 synthesis
trigger remain unresolved. No valid-response rejection defect was proven; this
change adds diagnostics only. Release remains NOT READY.

`TechnicalValidationError` remains a ValueError subclass and contains only a fixed
`validation_reason`. Shared Technical orchestration retains the established public
exception classification `ValueError` and allowlists the reason. HorizonPipelineError
preserves it alongside TECHNICAL_RESEARCH / TECHNICAL_ANALYST. Dashboard messages
and stage/type logs remain unchanged. No response, prompt or arbitrary exception
message is copied into public diagnostic fields. Suppressed implicit Python exception
context may still exist in-process; it must not be serialized as diagnostic output.

Actual response path: trusted catalog preflight → JSON packet / strict schema request
→ `openai_client.request_text` Responses extraction → `json.loads` → `_parse` manual
shape and semantic checks → immutable TechnicalSignal. There is no separate runtime
JSON-schema library or validating dataclass constructor. The response has no horizon
field: the requested, preflight-validated native horizon is attached by Python.

All reason suffixes below have the prefix `TECHNICAL_ANALYST_`. Before Step 6F these
branches raised plain ValueError without codes; the backend retained only the class.
Existing V0.7 tests covered the main rejection families; Step 6F exercises every
explicit branch, including array/text shapes, through targeted offline tests.

| Function / phase | Existing rule / new reason suffix |
| --- | --- |
| `_preflight`, before request | Unsupported horizon: HORIZON_INVALID; wrong input types: INPUT_INVALID; catalog differs from reconstructed snapshot: CATALOG_MISMATCH; duplicate catalog IDs: CATALOG_DUPLICATE_IDS; insufficient temporal/price/trend evidence: INSUFFICIENT_EVIDENCE |
| `analyze_technical_snapshot`, after extraction | `json.loads` TypeError/ValueError: INVALID_JSON |
| `_parse`, initial shape | Exact top-level fields: SCHEMA_INVALID; signal enum/exact integer confidence range: SIGNAL_CONFIDENCE_INVALID |
| `_parse.ids`, references | Non-list/non-string IDs: CITATION_SHAPE_INVALID; duplicate, unknown, unavailable or required-empty refs: CITATION_INVALID |
| `_parse`, cross-field | Supporting/conflicting overlap: CITATION_OVERLAP; incomplete missing IDs: MISSING_ACK_INCOMPLETE; confidence above 90 with missing/conflicting evidence: CONFIDENCE_EVIDENCE_CONFLICT |
| `_parse.prose`, semantics | Blank/non-string text: TEXT_INVALID; prohibited execution/level/quote terms: PROHIBITED_CLAIM; named feature without citation: FEATURE_CITATION_MISSING; numeric prose after removing feature labels: NUMERIC_PROSE |
| `_parse.statement`, shape | Exact statement keys: STATEMENT_INVALID |
| `_parse`, semantics | Opposite directional thesis: SIGNAL_THESIS_CONFLICT |
| `_parse`, conditions/risks | Non-array: STATEMENT_ARRAY_INVALID; missing confirmation or directional invalidation: CONDITIONS_REQUIRED |
| `_parse`, missing-data note | Non-string note: MISSING_NOTE_INVALID; nonempty note also passes prose checks |

The shared client rejects empty extracted output with RuntimeError, and translates
API failures to RuntimeError. These are not newly labeled as validation failures.
An empty string returned by a mocked request reaches INVALID_JSON; that differs from
actual client extraction. Extraction can also raise AttributeError for an unexpected
non-string response attribute. Unexpected errors retain existing type/stage behavior,
without an invented validation code. Pre-request JSON serialization/catalog-builder
errors are likewise not mistaken for one of the known response validation rules.

The matrix covers unknown supporting and conflicting IDs, duplicates, missing
acknowledgement, prohibited/numeric text, contradictory thesis and condition failures.
Each response rejection makes one mocked request and no Fundamental/synthesis call,
retry, rerun, fallback or persistence. Rich valid responses cover all three signals,
multiple citations, conflicts, Unicode prose, conditions/risks and confidence 0/90/100
(with complete, conflict-free evidence for 100). All four combined horizon regressions
and dashboard sanitization remain passing. No policy, prompt, schema, validator
predicate, source artifact, provider behavior or successful output was changed.

### Step 6G / 6H — Post-response semantic boundary

Step 6G's single authorized AAPL/MEDIUM run completed Technical and Fundamental
research, integration and readiness. Both sources were ADMITTED/FRESH; Fundamental
provenance was CURRENT_SYSTEM_TRUSTED, blockers were empty and integration time
matched Fundamental availability. Horizon Synthesis made one request and rejected
the response with SEMANTIC_VALIDATION. No IntegratedResearchView was returned.
The exact semantic rule was not retained. The request counter observed two OpenAI
request-function invocations but missed Fundamental's imported alias; no corrected
historical total is asserted.

Step 6H adds nine allowlisted semantic reason codes and propagates them through
HorizonSynthesisError to HorizonPipelineError. See the synthesis-agent document for
the full rule inventory and phase boundaries. Baseline 488; final 492 tests pass,
including all nine semantic branches through the combined boundary, valid edge cases,
separate structural/evidence failures and four-horizon regressions. No live calls,
raw response retention, validation weakening, policy change, retry or persistence.
No valid-response implementation defect was proven; diagnostic hardening is the only
production change. Historical Step 6 pre-request and Step 6C/6E Technical causes
remain unexplained and were not reproduced in Step 6G. The precise Step 6G semantic
cause also remains unknown. V0.8A remains NOT READY pending human review; any future
live diagnosis requires separate authorization.

### Step 6I / 6J — Technical prohibited-claim diagnosis

Step 6I stopped at TECHNICAL_RESEARCH / TECHNICAL_ANALYST / ValueError with exact
reason TECHNICAL_ANALYST_PROHIBITED_CLAIM. Technical research and Analyst ran once;
Fundamental, integration and synthesis were not reached. The precise triggering
wording was not retained; correctness of that historical rejection is unknown.

Step 6J baseline 492 and final 495 tests pass offline. The V0.7 Technical Analyst
document now records the exact single lexical branch, all scanned fields, phrase
matrix, numeric-rule distinction and known false-positive/false-negative limitations.
Benign “support”/“order” rejections are reproducible but already explicitly documented
in technical-analyst-v1. No validator implementation defect under that contract was
proven. Prompt wording was ambiguous about benign uses; a small clarification states
the existing all-text exclusions and gives descriptive alternatives. Only that prompt
clarification, tests and documentation changed. No validator, schema, methodology,
policy, provider behavior, retry or persistence change; no live validation occurred.
Historical triggers remain unexplained. V0.8A remains NOT READY pending review.

### Step 6K / 6L — Condition/FORECAST classification

Step 6K completed Technical research after the Step 6J clarification, Fundamental
research, integration and readiness, then received a Horizon Synthesis response.
Validation rejected it with HORIZON_SYNTHESIS_CONDITION_REQUIRES_FORECAST. This
establishes a condition-bearing statement lacked FORECAST classification, not its
wording or the historical rejection's correctness. No integrated view was returned.

Step 6L baseline 495; final 498 tests pass offline. Existing documentation requires
FORECAST for all generated condition-bearing statements; original conditions remain
separately preserved in the context. No implementation defect was proven. The prompt
was ambiguous about descriptive attribution with condition IDs, so it now explicitly
states the existing structural rule and preservation distinction. Schema, validators,
methodology and all nine diagnostics are unchanged. Matrix tests cover descriptive,
conditional and current-state text, every condition prefix and statement field;
all four combined horizon regressions pass. No live calls, raw response retention,
retries, persistence or new dependencies. Historical causes remain unresolved;
V0.8A remains NOT READY pending human review.

### Step 6M / 6N — Evidence-role overlap

Step 6M completed Technical, Fundamental, integration and readiness, then received
Horizon Synthesis output rejected with HORIZON_SYNTHESIS_EVIDENCE_ROLE_OVERLAP.
The old diagnostic identifies neither namespace nor IDs; no raw response was retained.
Step 6N baseline 498; final 500 tests pass offline. The existing rule is disjoint
top-level supporting/conflicting lists per namespace, separate from reusable statement
citations. No validator defect or methodology gap in that implemented scope was proven.
The prompt was ambiguous about scope and now explicitly describes the existing rule.
A fixed FUNDAMENTAL/TECHNICAL diagnostic namespace is propagated without IDs or prose.
No schema, validation predicate, policy or source behavior changed. All semantic and
four-horizon regressions pass; no live calls, persistence, retries or new dependencies.
Historical overlapping IDs remain unknown. V0.8A remains NOT READY pending review.

### Step 6O / 6P — Technical feature citation mapping

Step 6O stopped at Technical Analyst with TECHNICAL_ANALYST_FEATURE_CITATION_MISSING;
Fundamental and synthesis were not reached. Its exact feature/wording was not retained.
Step 6P baseline 500; final 504 tests pass offline. A real matcher defect was reproduced:
correctly cited sma_200 was also treated as sma_20, and close-versus-SMA labels required
nested SMA citations. The matcher now consumes longer recognized labels before testing
shorter labels, matching the existing canonical-label contract without weakening
independent citation requirements. This is not proof of the historical live cause.

The prompt now clarifies statement-local matching citations, multi-feature statements
and unavailable features. Fixed canonical-label feature_family diagnostics propagate
safely without raw IDs or output. All 23 labels, missing/unrelated/conflicting citations,
case variants and broad-term limitations are documented/tested. No live calls, new
indicators, schema/methodology changes, persistence, retries or dependencies. Existing
Technical reason-code and four-horizon regressions pass. V0.8A remains NOT READY pending
review; the historical failures remain unresolved beyond their retained diagnostics.

### Step 6Q — Consolidated offline audit STOPPED

Baseline 504 tests passed. The constructibility review reproduced a release-blocking
cross-stage contract inconsistency, so the requested stop condition applies. No
production code, prompt, schema, policy or diagnostic contract was changed. Step 6P's
nested-feature correction and statement-local prompt clarification remain preserved.

`ContractConstructibilityAuditTests.test_ready_neutral_without_source_invalidations_has_no_valid_synthesis`
uses synthetic data, the real Fundamental response validator, the normal prospective
research capture, the real Technical parser and the authoritative integration builder
and readiness revalidation. Fundamental's schema/parser accepts an empty
`thesis_invalidation_conditions`; Technical explicitly permits empty invalidation for
NEUTRAL while requiring confirmation. Both admissions/currentness gates pass, leaving
only T_CONFIRMATION entries in the synthesis condition catalog.

No output can satisfy `_validate.statement(..., invalidation=True)` for this context:

- Empty condition_ids produces HORIZON_SYNTHESIS_INVALIDATION_REFERENCE_REQUIRED.
- Any existing confirmation ID produces the same reason.
- Inventing an invalidation ID produces INVALID_EVIDENCE_REFERENCE.
- Changing posture cannot fix the contradiction; every permitted posture is tested.

This proves an input/output constructibility defect, not a historical live cause.
The Fundamental prompt asks for concrete invalidations but its schema/parser does
not require a nonempty list. Existing contracts do not determine whether absent
invalidations should block readiness or be represented explicitly in synthesis.
Choosing that behavior requires human contract/methodology review; neither validation
weakening nor fabricated conditions is an acceptable automatic fix.

#### Partial contract inventory and outstanding work

The audit inspected the 22 Technical reason-code families and the nine Horizon semantic
families plus shape, identity, enum, evidence, pre-request and readiness boundaries.
The earlier per-family regression matrices remain passing. A complete rule-by-rule
ALIGNED certification and the remaining cross-rule audit were not completed after the
stop condition; passing existing tests is not a completeness claim.

| Stage / rule | Status | Evidence / action |
| --- | --- | --- |
| Readiness plus mandatory synthesis invalidation | METHODOLOGY_GAP | Proven impossible ready input above; decide absent-invalidation contract before implementation |
| Technical CONDITIONS_REQUIRED | PROMPT_AMBIGUITY | Prompt says confirmation "when evidence permits"; parser requires it unconditionally, including NEUTRAL. Clarification pending resumed audit |
| Horizon summary citations | PROMPT_AMBIGUITY | "Cite every statement" does not explicitly require both namespaces in synthesis_summary; parser does. Clarification pending |
| Horizon LIMITATIONS_MISMATCH | PROMPT_AMBIGUITY | Prompt says every token exactly; validator also requires identical order. Clarification pending |
| Horizon INVALIDATION_REFERENCE_REQUIRED | PROMPT_AMBIGUITY | Explicitly communicate nonempty, invalidation-only IDs once absent-source behavior is decided |
| Technical lexical prose / feature detection | KNOWN_LIMITATION | Benign lexical exclusions, synonym gaps and lack of entailment remain documented; Step 6P nested-label defect is corrected |
| Horizon lexical action / predictive text checks | KNOWN_LIMITATION | Finite lexical vocabulary, conservative rejections and semantic false negatives; not an entailment checker |
| Nonsemantic schema/evidence diagnostics | KNOWN_LIMITATION | Multiple predicates share fixed SCHEMA_VALIDATION / INVALID_EVIDENCE_REFERENCE classifications; exact predicate is not always retained |
| Unexpected local exceptions | KNOWN_LIMITATION | Stage/type or generic stage fallback is not an exact deterministic reason; no new propagation change made |

No new schema ambiguity or validator correction was resolved in Step 6Q. Prompt
completeness, all remaining documentation gaps and full accumulated-diff release
certification remain pending. Historical raw responses are unnecessary to reproduce
this blocker and were neither obtained nor retained.

Final suite: 505 PASS, including one new characterization test. All live Alpha Vantage
and OpenAI calls in Step 6Q: zero. Existing four-horizon combined regressions and safe
diagnostic matrices pass. No persistence, portfolio/brokerage behavior, retries, new
dependencies, commits, tags or pushes. V0.8A is not release-signed-off and another paid
live diagnostic is not recommended until this contract decision and the audit are complete.


### Step 6R — Source-available invalidation decision implemented

The human-approved `source-available-invalidation-v1` resolves the Step 6Q blocker.
Fundamental's parser permits an empty invalidation list; Technical permits it for
NEUTRAL only (directional invalidations and all-signal confirmation remain mandatory).
Packet condition IDs are derived from source arrays, not model assertions. Synthesis
now requires a nonempty invalidation-only reference set if source invalidations exist,
and permits an empty set only when none exist. Unknown IDs and confirmation substitution
remain rejected. No readiness or source-level rule changed.

Absence is represented using the existing limitations mechanism: packet construction
appends NO_SOURCE_INVALIDATION_CONDITION, and exact ordered acknowledgement is required.
No fake condition, new output-schema field, historical artifact mutation or source
missing-data rewrite occurs. The packet and immutable view retain the policy version.

The previous characterization now returns a valid IntegratedResearchView through real
source parsing, prospective capture, authoritative integration and readiness. Tests cover
both/F-only/T-only/neither availability, omitted/unknown/substituted references, missing
absence acknowledgement, immutable version metadata, both authority modes and all five
postures where allowed. Sources remain unchanged. Existing condition/FORECAST, predictive
text, role exclusivity, missing-data, confidence and safe diagnostic matrices pass.

Three Step 6Q prompt ambiguities are clarified from existing documented contracts:
Technical confirmation is mandatory, synthesis_summary cites both namespaces, and
acknowledged_limitations preserves exact ordering. The invalidation prompt describes the
new approved conditional rule explicitly. Neither Technical validation nor unrelated
Horizon validation was changed.

Constructibility review resumed: mandatory statements can cite available evidence in
both namespaces; WAIT can use the mandatory Technical confirmation with FORECAST;
invalidation references can use available source conditions with their evidence or the
new absence representation; role exclusivity does not restrict narrative citation reuse;
missing tokens remain outside numeric-prose validation. No further impossible combination
was found in the reviewed contracts and offline matrices. This is not proof of arbitrary
natural-language entailment or completion of every Step 6Q audit/documentation item.

Accumulated production review: the shared backend extraction remains intact; backend
orchestration does not import dashboard code. No temporary live harness, request counter,
raw response/prompt persistence, secret literal, network-on-import change, retry/fallback,
duplicate temporary service layer or new persistence action was found in the accumulated
changes. Existing dashboard save/evaluation actions are not invoked by the combined path.
No dead-code issue requiring unrelated refactoring was identified. Earlier release status
paragraphs are historical; current status remains NOT RELEASE-SIGNED-OFF.

Baseline 505; final 508 tests PASS (three additional methods, former blocker test updated).
Zero live Alpha Vantage/OpenAI requests; no manual run, dependency, portfolio, brokerage,
dashboard feature, commit/tag/push. Known lexical limitations, coarse nonsemantic error
classifications and historically unretained live triggers remain. Human review is required
before any separately authorized live validation or final release decision.


## Step 6S — Completed consolidated offline contract audit

Outcome: PASS for the bounded offline contract audit. No live execution or investment
accuracy is claimed. Baseline 508 tests passed; final count is recorded below.
The matrices below supersede the incomplete Step 6Q certification. No validator,
schema, methodology, model or readiness predicate changed in Step 6S.

### Counting, interpretation and fixture key

Counts are grouped rejection paths, not a claim that each operand of a compound
predicate is a separate rule. Technical has 22 fixed reason families plus two local/
transport boundary groups (24 rows). Horizon has 24 explicit output rejection branches
plus seven preflight/transport groups (31 rows). Repeated calls to a shared ID/statement
validator are listed once; both condition-evidence subset branches are listed separately.
Technical error-constructor rejection of an unknown programmer-supplied reason is not a
model-output path. Post-validation dataclass/time/JSON construction has no additional
explicit rejection rule; unexpected runtime failures remain generic rather than invented
semantic diagnoses.

Prompt/Schema columns distinguish explicit communication from representation. Partial
schema means the shape represents a valid output but semantic relationships are enforced
by code, not JSON Schema. This is not SCHEMA_AMBIGUITY. N/A is used only where the model
cannot repair an application/transport input. All rows have a constructible valid baseline;
invalid coverage references actual regression tests, not prompt-string checks alone.
KNOWN_LIMITATION is non-blocking and does not mean acceptance proves semantic truth.
No row has a release blocker after the Step 6R resolution.

Fixture keys (all in tests/test_v08.py unless stated):

- Tneg/Tvalid/Tpre: TechnicalValidationDiagnosticTests response_failure_matrix,
  valid_rich_response_shapes, preflight_codes_and_client_errors respectively.
- Tfeature: TechnicalFeatureCitationTests, all 23 canonical labels and multi-label cases.
- Tlex: TechnicalProhibitedClaimTests; V07: tests/test_v07.py TechnicalAnalystTests and
  TechnicalEvidenceTests (typed inputs, versions, units, finite/available evidence).
- Hsem/Hshape/Hedges: HorizonSemanticDiagnosticTests every_semantic_reason,
  other_classifications + remaining_structural_and_evidence_branches, valid_edges.
- Hbase: HorizonSynthesisTests (valid baseline, identity, JSON, real mocked Responses,
  no retry, all horizons and parser-only conflict echoes).
- Hpre: CombinedPipelineTests pre_request_substages + pipeline_preserves_typed diagnostic.
- Hconditions/Hroles: HorizonConditionForecastTests / HorizonEvidenceRoleTests.
- R: ContractConstructibilityAuditTests source availability matrix and absence cases.
- S36/Sextract/Sinteraction: CompletedContractAuditTests all_ready_direction_horizon_posture,
  response_extraction_detail, clarified_horizon_cross_rule respectively.

For every Technical fixed reason, safe transport is TechnicalValidationError →
TechnicalResearchError (ValueError classification) → HorizonPipelineError. Tneg verifies
real parser transport; Tpre isolates zero-call guards; the same typed catch transports
preflight codes. Feature failure additionally retains fixed feature_family. All Horizon
semantic suffixes below have HORIZON_SYNTHESIS_ prefix and retain SEMANTIC_VALIDATION;
Hsem verifies combined transport. Other output classifications use the fixed name shown
and Hpre/typed-boundary tests verify the shared wrapper. Overlap retains only a fixed
namespace, never IDs. Readiness retains reason codes. New response_detail preserves only
max_output_tokens/content_filter/not_completed/empty_output_text from the existing client.

### Technical matrix

Technical fixed reason suffixes below have TECHNICAL_ANALYST_ prefix. Unless otherwise
specified, the diagnostic is that exact reason plus stage/substage/type; no raw text.

| Rule / diagnostic | Validator | Trigger | Prompt | Schema | Evidence/condition contract | Valid + invalid coverage | Status | Release blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HORIZON_INVALID | _preflight | Native horizon outside the two allowed values | Yes | N/A | Requested native scope | Tpre | ALIGNED | No |
| INPUT_INVALID | _preflight | Snapshot/catalog wrong types | N/A: application input | N/A | Typed source objects | Tpre | ALIGNED | No |
| CATALOG_MISMATCH | _preflight | Catalog differs from reconstruction | N/A: application input | N/A | Exact trusted catalog | Tpre | ALIGNED | No |
| CATALOG_DUPLICATE_IDS | _preflight | Duplicate catalog IDs after equality gate | N/A: application input | N/A | Catalog uniqueness | Tpre (isolated defensive branch) | ALIGNED | No |
| INSUFFICIENT_EVIDENCE | _preflight | Absent symbol/session/timezone/latest close or available TREND/MOMENTUM | N/A: zero-call input gate | N/A | Minimum available evidence | Tpre / V07 | ALIGNED | No |
| INVALID_JSON | analyze_technical_snapshot | JSON decoding TypeError/ValueError | Yes: strict output | Yes: JSON object | None | Tneg | ALIGNED | No |
| SCHEMA_INVALID | _parse | Non-object or missing/extra top-level keys | Yes: strict schema | Yes | Model-owned fields only | Tneg | ALIGNED | No |
| SIGNAL_CONFIDENCE_INVALID | _parse | Unknown signal; confidence not exact int or outside 0–100 | Yes | Yes | Independent evidence strength | Tneg / Tvalid | ALIGNED | No |
| CITATION_SHAPE_INVALID | _parse.ids | Non-list or non-string element | Yes + schema | Yes | Exact ID arrays | Tneg | ALIGNED | No |
| CITATION_INVALID | _parse.ids | Duplicate, unknown, unavailable ID or empty required supporting/statement list | Yes, clarified | Partial: arrays express valid values | Available vs missing catalog sets | Tneg / Tfeature / V07 | ALIGNED | No |
| CITATION_OVERLAP | _parse | Global supporting/conflicting intersection | Yes, clarified | Partial: separate arrays | Disjoint roles, reusable local citations | Tneg / Tfeature | ALIGNED | No |
| MISSING_ACK_INCOMPLETE | _parse | Missing-ID set is not exactly all unavailable IDs | Yes, clarified | Partial: array | Unavailable catalog entries | Tneg / Tfeature | ALIGNED | No |
| CONFIDENCE_EVIDENCE_CONFLICT | _parse | Confidence above 90 with missing or conflicting evidence | Yes | Partial: range only | Missing/conflicting sets | Tneg / Tvalid | ALIGNED | No |
| TEXT_INVALID | _parse.prose | Non-string/blank text; includes required/nonempty missing note | Yes, clarified | Partial: minLength, no whitespace test | Missing note required only if missing | Tneg / V07 | ALIGNED | No |
| PROHIBITED_CLAIM | _parse.prose | Existing word-boundary support/resistance/breakout/buy/sell/order/allocation/stop.loss/take.profit/current quote regex | Yes: lexical exclusions | Partial: string | Research-only conservative prose | Tlex | KNOWN_LIMITATION | No |
| FEATURE_CITATION_MISSING | _parse.prose | Canonical label lacks corresponding available statement citation | Yes | Partial: statement refs | 23 canonical labels; progressive scrubbing | Tfeature | KNOWN_LIMITATION | No |
| NUMERIC_PROSE | _parse.prose | Digits remain after canonical-label scrubbing | Yes | Partial: string | Values stay in catalog | Tlex / Tfeature | KNOWN_LIMITATION | No |
| STATEMENT_INVALID | _parse.statement | Non-object or keys other than text/evidence_ids | Yes + schema | Yes | Statement-local grounding | Tneg | ALIGNED | No |
| SIGNAL_THESIS_CONFLICT | _parse | Opposite setup/thesis/outlook wording in summary/thesis for directional signal | Yes, clarified | Partial: text | Independent signal consistency | Tneg / V07 | KNOWN_LIMITATION | No |
| STATEMENT_ARRAY_INVALID | _parse | Conditions/risk collection not a list | Yes + schema | Yes | Conditions and risks separate | Tneg | ALIGNED | No |
| CONDITIONS_REQUIRED | _parse | No confirmation; or directional signal without invalidation | Yes, Step 6R | Partial: arrays | NEUTRAL can omit invalidation | Tneg / R / V07 | ALIGNED | No |
| MISSING_NOTE_INVALID | _parse | Missing-data acknowledgement not string | Yes + schema | Yes | Source missing-data explanation | Tneg | ALIGNED | No |
| Request/extraction RuntimeError | request_text → step | Missing configuration/API failure/empty client output; unexpected response type may be AttributeError | N/A: transport | N/A | No generated validation reason exists | Tpre / V07 / combined stage tests | KNOWN_LIMITATION | No |
| Local catalog/serialization exception | _preflight / analyze_technical_snapshot | Reconstruction model validation; malformed input/serialization failure before request | N/A: application input | N/A | Source type/version/units/finite values | V07 evidence tests / combined stage tests | KNOWN_LIMITATION | No |

Technical totals: 18 ALIGNED; 6 KNOWN_LIMITATION (four lexical/semantic families and
two generic boundary groups); zero remaining PROMPT_AMBIGUITY, SCHEMA_AMBIGUITY,
VALIDATOR_DEFECT, DOCUMENTATION_GAP or METHODOLOGY_GAP within this audited scope.
The lexical rules are accurately communicated but intentionally not labeled complete
semantic grounding. Their known false positives/negatives are in the Technical document.
The Step 6P nested-label defect remains corrected, not an unresolved defect.

### Horizon matrix

Semantic reason names omit the HORIZON_SYNTHESIS_ prefix. Other names are existing
fixed classifications; sharing a classification does not discard a more specific
internally available reason. Those branches never had a finer fixed reason.

| Rule / diagnostic | Validator | Trigger | Prompt | Schema | Evidence/condition contract | Valid + invalid coverage | Status | Release blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SCHEMA_VALIDATION: top-level | _validate | Non-object or wrong exact keys | Yes | Yes | Output ownership | Hshape | ALIGNED | No |
| IDENTITY_MISMATCH | _validate | Identity differs in any field | Yes | Yes: singleton enums | Ticker/horizon/authority/conflict/source conclusions | Hshape / Hbase | ALIGNED | No |
| INVALID_ENUM: posture | _validate | Unknown posture | Yes | Yes | Fixed postures | Hshape | ALIGNED | No |
| POSTURE_NOT_ALLOWED | _validate | Known posture outside authoritative allowed_postures | Yes | Yes: packet enum | Approved direction/horizon matrix | Hsem / S36 | ALIGNED | No |
| SCHEMA_VALIDATION: confidence | _validate | Not exact integer in 0–100 | Yes | Yes | Independent synthesis confidence | Hshape / Hedges | ALIGNED | No |
| SCHEMA_VALIDATION: ID shape | _validate.ids | Not list of strings | Yes + schema | Yes | Separate namespaces | Hshape | ALIGNED | No |
| INVALID_EVIDENCE_REFERENCE: ID membership | _validate.ids | Duplicate/unknown IDs or unavailable Technical ID | Yes, clarified | Partial: arrays | Exact F/T/condition catalogs | Hshape / Hroles | ALIGNED | No |
| EVIDENCE_ROLE_OVERLAP | _validate | Top-level support/conflict intersection within F or T | Yes | Partial: four arrays | Per-namespace role exclusivity | Hsem / Hroles | ALIGNED | No |
| LIMITATIONS_MISMATCH | _validate | Acknowledged list differs from ordered expected limitations | Yes, Step 6R | Partial: array | Warnings/missing tokens + conditional absence token | Hsem / R / Sinteraction | ALIGNED | No |
| SCHEMA_VALIDATION: statement shape | _validate.statement | Non-object/wrong exact statement keys | Yes + schema | Yes | Narratives and risk items | Hshape | ALIGNED | No |
| INVALID_ENUM: category | _validate.statement | Category other than AI_INTERPRETATION/FORECAST | Yes | Yes | Source data categories remain separate | Hshape / Hconditions | ALIGNED | No |
| INVALID_EVIDENCE_REFERENCE: empty statement refs | _validate.statement | Neither F nor T evidence cited | Yes, clarified | Partial: separate arrays | Condition reference alone insufficient | Hshape | ALIGNED | No |
| INVALIDATION_REFERENCE_REQUIRED | _validate.statement | Source invalidation available but none cited, or any non-invalidation condition in invalidation_summary | Yes, Step 6R | Partial: condition_ids | source-available-invalidation-v1 | Hsem / R | ALIGNED | No |
| CONDITION_REQUIRES_FORECAST | _validate.statement | Nonempty condition_ids outside FORECAST | Yes | Partial: category enum | Structural, irrespective of tense | Hsem / Hconditions / Sinteraction | ALIGNED | No |
| INVALID_EVIDENCE_REFERENCE: Fundamental condition | _validate.statement | Condition evidence_refs not subset of statement F refs | Yes, clarified | Partial: F refs | Original source condition grounding | Hshape / Hconditions | ALIGNED | No |
| INVALID_EVIDENCE_REFERENCE: Technical condition | _validate.statement | Condition evidence_ids not subset of statement T refs | Yes, clarified | Partial: T refs | Original source condition grounding | Hshape / Hconditions | ALIGNED | No |
| SCHEMA_VALIDATION: text | _validate.statement | Non-string or blank text | Yes, clarified | Partial: string | Narratives/risks | Hshape | ALIGNED | No |
| INVALID_EVIDENCE_REFERENCE: feature label | _validate.statement | Named canonical Technical label lacks own T citation | Yes, clarified | Partial: refs | Longest-first label matching | Hshape / Tfeature / Sinteraction | KNOWN_LIMITATION | No |
| NUMERIC_PROSE | _validate.statement | Digits after canonical-label scrubbing | Yes | Partial: string | No numeric restatement | Hsem / Sinteraction | KNOWN_LIMITATION | No |
| PROHIBITED_ACTION_LANGUAGE | _validate.statement | Existing action/position/portfolio/level lexical regex | Yes, clarified | Partial: string | Research-only prose, not identity | Hsem / Sinteraction | KNOWN_LIMITATION | No |
| PREDICTIVE_TEXT_REQUIRES_FORECAST | _validate.statement | will/expect/forecast/predict/would/could outside FORECAST | Yes, clarified | Partial: enum | Lexical future classification | Hsem / Hconditions / Sinteraction | KNOWN_LIMITATION | No |
| SCHEMA_VALIDATION: risks | _validate | major_integrated_risks not list | Yes + schema | Yes | Same statement contract per risk | Hshape | ALIGNED | No |
| WAIT_CONDITION_REQUIRED | _validate | WAIT but synthesis_summary has no condition IDs | Yes, clarified | Partial: arrays | Original confirmation or invalidation; FORECAST | Hsem / R / Sinteraction | ALIGNED | No |
| INVALID_EVIDENCE_REFERENCE: summary grounding | _validate | Summary lacks either F or T refs | Yes, Step 6R | Partial: arrays | Cross-source grounding | Hshape / Hbase | ALIGNED | No |
| Readiness reasons | require_synthesis_ready | Invalid type/reasons, unavailable retained sources, invalid policy input, recomputation mismatch or policy-blocked context | N/A: authoritative preflight | N/A | Admission/time/provenance/missing-data/risk policy | ReadinessIntegrityTests / FreshnessProvenanceTests | ALIGNED | No |
| Packet failure | _packet / synthesize_horizon | Catalog resolution/duplicate IDs or incompatible source/posture shape | N/A: application input | N/A | Trusted catalogs and source structures | Hpre / V07 evidence tests | ALIGNED | No |
| INPUT_SERIALIZATION | synthesize_horizon | canonical_json rejects unsupported/nonfinite packet values | N/A: application input | N/A | Deterministic packet | Hpre | ALIGNED | No |
| SCHEMA_CONSTRUCTION | synthesize_horizon | Local schema assembly failure | N/A: application input | N/A | Identity/postures | Hpre | ALIGNED | No |
| API_REQUEST | synthesize_horizon / request_text | Request RuntimeError without extraction classification | N/A: transport | N/A | No output to validate | Hbase | KNOWN_LIMITATION | No |
| RESPONSE_EXTRACTION | request_text / synthesize_horizon | Incomplete response, absent/blank/non-string output | N/A: transport | N/A | Completed Responses output | Hbase / Sextract | ALIGNED | No |
| INVALID_JSON | synthesize_horizon | Response JSON decoding failure | Yes: strict structured output | Yes | No repair/code-fence fallback | Hbase | ALIGNED | No |

Horizon totals: 26 ALIGNED; 5 KNOWN_LIMITATION (four lexical/semantic branches and the
coarse API boundary); zero remaining ambiguity, defect, documentation or methodology
statuses in this scope. Schema/reference classifications are intentionally shared;
they identify a family, not always a field. Generic unexpected exceptions remain generic.

Readiness's grouped row explicitly includes INVALID_CONTEXT_TYPE, INVALID_BLOCKING_REASONS,
REQUIRED_POLICY_SOURCES_UNAVAILABLE, INVALID_POLICY_INPUTS,
CONTEXT_DIFFERS_FROM_POLICY_RECOMPUTATION and POLICY_CONTEXT_BLOCKED, plus the authoritative
builder's existing admission/freshness/provenance/applicability/missing-data reason codes.
The builder is reused, not replaced by an LLM validator. Existing integrity, temporal,
version, forged-context and missing-data tests exercise these independent policy gates.
Packet failures include both resolve_evidence_id failures and duplicate catalog IDs;
pre-request wrapping retains PACKET_CONSTRUCTION and safe classification/type. Guards
normally prevented by upstream integrity are defense-in-depth, tested by controlled
injection without treating forged packets as publicly trusted inputs.

### Prompt and diagnostic changes

Technical clarification: unique exact IDs, nonempty/disjoint support lists, nonblank
statements, local evidence, signal/thesis consistency, exact missing-ID set and required
missing note, optional risk list. Horizon clarification: unique IDs/nonblank text,
all original condition evidence in the same statement, feature-matching Technical refs,
WAIT condition in summary, and the existing lexical action/predictive vocabulary even
in negated/descriptive prose. Identity and limitation tokens are not narrative prose.
These rules already existed in code/docs. Valid examples remain possible; no validator
or schema was broadened or relaxed.

The only propagation defect found in Step 6S was loss of the client's existing fixed
synthesis_response_detail. The optional response_detail field now survives the two
Horizon boundaries and is allowlisted only for RESPONSE_EXTRACTION. Real request helper
plus fake SDK tests cover all four values and withhold an arbitrary SECRET detail.
The successful request/response path is unchanged. Technical non-completed extraction
has no existing fixed detail because its request does not enable require_completed;
that existing difference is documented, not silently changed. No raw exception strings,
responses, evidence IDs, prompts or credentials are added to diagnostic output.

### Constructibility and interactions

S36 executes 36 combinations: four decision horizons × three Fundamental directions ×
three Technical signals, and every posture permitted in each authoritative packet.
Sources pass actual parsers, prospective capture, integration and readiness; no forged
context is sent to synthesis. R additionally covers F-only/T-only/both/neither
invalidation and both authority modes. The neutral/empty case produces a valid immutable
view with the required absence token. Every request is mocked; one request per invocation.

Technical V07/Tvalid/Tfeature/Tlex cover all signals and both native horizons, cited
confirmation/invalidation/risk, conflicts, missing evidence, all labels and overlapping
canonical names. Unsupported source combinations (directional signal with no invalidation,
or any signal without confirmation) still reject; they are not impossible ready inputs.

Horizon interactions cover WAIT + original condition + FORECAST + globally conflicting
Technical evidence; invalidation + source evidence + FORECAST; all postures; nonnumeric
forecasts; numeric/action rejection despite otherwise valid citations; predictive versus
current-state classification; exact ordered limitations; narrative citation reuse across
both namespaces; source divergence and both authority modes. Missing data remains in
limitations, outside numeric prose scanning. Source conclusions stay in identity/context,
so lexical prohibitions do not force rewriting the source recommendation. All existing
nine-reason and combined four-horizon matrices pass. THESIS_CONFLICT and
INSUFFICIENT_EVIDENCE echo checks remain parser-level where no legitimate ready builder
case is produced; the audit does not claim readiness for blocked or unclassified cases.

No further constructibility contradiction was found. This establishes tested structural
constructibility, not universal semantic entailment for arbitrary generated prose.

### Policy inventory (no duplicate metadata introduced)

| Policy | Authoritative location | Packet / immutable result | Verification |
| --- | --- | --- | --- |
| technical-horizon-selection-v1 | horizon_integration.TECHNICAL_HORIZON_SELECTION_VERSION | CombinedResearchResult.technical_horizon_selection_version; selected native horizon in context/packet | Four-horizon selection and combined tests |
| combined-research-sequencing-v1 | horizon_integration.COMBINED_RESEARCH_SEQUENCING_VERSION | CombinedResearchResult.sequencing_version; orchestration guard | Sequence/fail-fast combined tests |
| technical-freshness-v1 | IntegrationContext / TechnicalFreshness policy defaults | Packet policy_versions.freshness; view.context.freshness_policy_version | Age/native-horizon/boundary tests |
| fundamental-provenance-v1 | fundamental_provenance.POLICY_VERSION and context qualified policy | Packet policy_versions.fundamental; immutable source sidecar/context | Origin/run/time/integrity tests |
| risk-applicability-v1 | horizon_integration.RISK_APPLICABILITY_VERSION | Immutable view.context.risk_applicability_version; eligibility already checked, not duplicated in model-owned output | Risk and forged-version tests |
| source-available-invalidation-v1 | horizon_synthesis.INVALIDATION_POLICY_VERSION | Packet policy_versions.invalidation; frozen view.invalidation_policy_version | R availability, acknowledgement and immutability tests |

All six are documented in current design/policy/agent/combined documents. No policy version
or source artifact is rewritten by Step 6S. Not every application policy must be echoed
by the LLM: returned composition is the authoritative retained provenance.

### Accumulated production diff review

Reviewed every changed production file: dashboard/technical_adapter.py, horizon_pipeline.py,
horizon_synthesis.py, technical_analyst.py and the untracked technical_pipeline.py, plus
all accumulated test/doc changes. TechnicalRun and orchestration moved to the shared
backend; dashboard is a consumer and keeps its sanitized UI contract. Re-export of
TechnicalRun in the adapter preserves compatibility, not a duplicate implementation.
TechnicalValidationError and HorizonSynthesisError carry bounded diagnostic metadata.
Prior behavioral changes are the proven nested-label correction, approved source-available
invalidation policy, and documented prompt clarifications. No accidental model, indicator,
horizon, confidence, authority or freshness change was found.

No temporary live harness/counter, debugging branch/print, raw-output/prompt persistence,
secret literal, environment-value logging, new network-on-import call, hidden retry,
source rerun, fallback result, evaluation/portfolio/brokerage action, duplicate service
abstraction, dead hardening code or stale hardening TODO was found in accumulated
production additions. In-memory create_technical_signal_record is not a database save.
run_stock_research is explicitly called with persist_decision=False and no store/portfolio
context. Existing dashboard saves/evaluation remain explicit separate user actions.
OpenAI stays lazy, store=False, max_retries=0; credentials are used only by the existing
client authentication path, not research packets. Raw exception context can exist in
process and must not be serialized; public metadata/log calls do not dump it.
Historical doc sections are dated records, not current release claims. Current checkpoint
status is offline-audit PASS, not live execution validated and not release-signed-off.

### Resolved blockers, limitations and historical failures

Resolved: Step 6P nested-label false rejection; Step 6Q absent-source invalidation
constructibility contradiction through the human-approved Step 6R policy. Remaining
prompt ambiguities identified in this audit are clarified. No release-blocking contract
issue remains identified by this review.

Non-blocking: finite lexical matching (benign rejections and synonym/spelled-number gaps),
no full entailment/forecast-truth proof, coarse schema/reference/API diagnostics, generic
unexpected exceptions, provenance/currentness bounds, provider vintage and RAW-price
limitations. These are documented limits, not evidence of predictive quality.

Historical unresolved: Step 6 pre-request synthesis cause; Step 6C/6E Technical causes;
Step 6G exact semantic rule; Step 6I prohibited wording; Step 6K condition wording;
Step 6M overlapping namespace/IDs; Step 6O named feature. Fixed historical reason codes
identify rules only. Neither Step 6P nor this audit proves their exact causes.

This audit supports human review before ONE separately authorized controlled live
validation. It does not authorize that run or claim release sign-off. Step 6S makes zero
live provider/OpenAI requests, creates no persistence/portfolio/trading behavior or new
dependency, and performs no commit/tag/push.

Final Step 6S validation: **512 tests PASS** from a 508-test baseline, four new test
methods with matrix cases; `git diff --check` PASS. All unit/manual live Alpha Vantage
and OpenAI calls: zero. Existing accumulated working-tree changes remain uncommitted.

## Step 6V-A — Approved version foundation; v2 generation inactive

Human approval reserves `evidence-first-assembly-v1`, `technical-analyst-v2` and
`horizon-synthesis-v2`. `src/generation_contracts.py` defines the exact identifiers
and immutable v2-to-assembly mapping. These are generation/assembly contracts, not
new investment methodologies. The mapping is not a consumer acceptance allowlist.

ACTIVE TECHNICAL GENERATION = `technical-analyst-v1`.
ACTIVE HORIZON GENERATION = `horizon-synthesis-v1`.
No prompt, schema, validator semantics, bound parts or evidence-first assembly is
activated. Current module aliases and public default version fields remain v1.
Admission/evaluation use the explicit historical v1 constant, not the active
version selector: a later activation must not silently expand their eligibility.

| Consumer | Status | Basis / remaining work |
| --- | --- | --- |
| Technical generator | V1_ONLY | Actual mocked request still returns v1 |
| Horizon generator | V1_ONLY | Actual mocked request still returns v1 |
| Technical storage | V1_V2_COMPATIBLE (storage envelope only) | Preserves nonempty version strings opaquely, including unknown historical labels; never interprets or upgrades them |
| Technical evaluation | V2_COMPATIBILITY_PENDING | Consumes preserved signal/direction, horizon, provenance and evidence; explicit v1 gate remains until real v2 assembled artifacts pass compatibility regressions |
| Horizon Technical admission/readiness | V2_COMPATIBILITY_PENDING | Revalidates source shape/provenance/versions; explicit v1 gate unchanged |
| IntegratedResearchView representation | V1_V2_COMPATIBLE (representation only) | Existing methodology_version field represents either identity without changing analysis_json or public shape; constructor is not a version admission gate |
| Dashboard / evaluation downstream consumers | V2_COMPATIBILITY_PENDING | Existing public shape planned unchanged; real v2 artifact regression required before certification |

Storage's acceptance of an opaque unknown label is not research/evaluation
acceptance. Empty/non-string version fields reject at storage shape validation;
unknown and malformed nonempty strings reject at strict admission/evaluation.
There is no Horizon-result ingestion/version-validation boundary to broaden in
this step. The Horizon producer remains v1; its frozen result constructor must not
be misrepresented as validating an arbitrary version or its semantics.

No historical artifact mutation, reinterpretation, database migration or public
shape change. All six existing V0.8A policy versions remain unchanged. Tests that
substitute a reserved label characterize storage/representation only and do not
claim to generate a valid evidence-first v2 artifact.

Step 6T.1 consumed the final live authorization and failed closed at Technical
Analyst with FEATURE_CITATION_MISSING, feature_family sma_200. This version-only
foundation does not address that reliability failure or authorize another run.
V0.8A remains not release-ready. No live calls, retries, extra model passes, new
providers/dependencies, dashboard features, portfolio or brokerage behavior added.

Validation: starting suite **512 PASS**, final suite **515 PASS**, three new focused
version tests; `git diff --check` PASS. Mocked generator tests confirm both active
v1 identities; network-guarded version tests cover reserved mappings, strict
consumer rejection and exact storage round trips. Unit/manual live provider calls:
zero. Prior accumulated changes preserved; no commit, tag or push.

## Step 6V-B — Technical internal draft only

Implemented inactive `technical-analyst-v2` internal frozen types, strict bounded
schema and source-catalog validation in `src/technical_draft.py`, under approved
`evidence-first-assembly-v1`. TEXT/FEATURE/CITATION selections and explicit thesis
roles are validated without inferring semantic support or repairing prose. Canonical
labels in TEXT reject; sma_200 binding uses the actual catalog ID. Repeated selection
normalization is separate from prohibited duplicate role assignments. Missing inventory
remains software-owned; condition requirements and role/narrative independence remain.

Active Technical and Horizon generation remain v1. No active prompts/schemas/parsers,
pipelines, admission, evaluation, dashboard, storage or database changes. Public v2
assembly and its full rendered-prose validation belong to 6V-C; a draft is not a public
signal or evidence of entailment. No Horizon v2, live call, retry, fallback or extra
model pass. No live reliability improvement or release readiness claimed.

Validation: **515 PASS** before edits; **522 PASS** after edits (seven new matrix
methods). Network-guarded internal tests and mocked v1 pipeline regression pass;
all prior v1 rejection/combined regressions pass. `git diff --check` PASS. Live
Alpha Vantage/OpenAI calls: zero. Accumulated changes preserved; no commit/tag/push.

## Step 6V-C — Offline Technical deterministic assembly

Added only the offline `src/technical_assembly.py` entry point plus assembly tests
and documentation. Draft revalidation → deterministic assembly → unchanged public
validation → existing TechnicalSignal shape labeled technical-analyst-v2. Explicit
bindings supply canonical labels/citations, role assignments supply roles, and the
catalog supplies missing inventory/provenance. TEXT and acknowledgement are preserved
exactly, including outer whitespace; no post-hoc citation repair or analytical rewrite.
All public safeguards remain active. This guarantees selection identity, not entailment.

Normal Technical generation stays v1; Horizon/evaluation/admission/dashboard/storage
behavior is unchanged. Tests create in-memory v2 records only to verify existing strict
consumers still reject them; no v2 signal is persisted. No live calls, retries, repair
passes, new dependencies or activation. V0.8A remains not release-ready; live reliability
has not been established by offline assembly.

Validation: starting **522 PASS**, final **528 PASS**; six new offline matrix tests.
Exact whitespace, repeated selections, every statement location, signals/horizons,
metadata, missing inventory, forged drafts/catalogs and public prose rejections pass.
Normal v1 pipeline and pending v2 consumer gates pass. `git diff --check` PASS;
zero live Alpha Vantage/OpenAI calls. Accumulated changes preserved; no commit/tag/push.

## Step 6V-D — Horizon internal draft only

Added inactive horizon-synthesis-v2 types/schema/validation in horizon_draft.py.
The public draft entry revalidates readiness and rebuilds the packet. Model output
excludes authoritative identity/limitations/policies/source conclusions. Explicit
namespaced selections, Technical FEATURE binding, unique namespaced role assignments
and condition-bound statements preserve the approved ownership split. Condition-bound
drafts cannot independently specify a conflicting category; FORECAST assembly belongs
to 6V-E. Source-condition lineage is validated but not publicly assembled here.

Tests retain v1 WAIT's confirmation-or-invalidation rule, explicit both-namespace
summary grounding and source-available invalidation (including a real ready no-source-
invalidation context). Unknown/unavailable selections, duplicate roles, invalid conditions,
unbound labels and malformed drafts reject. Same textual IDs in separate namespaces
remain distinct. No semantic errors are repaired; no entailment guarantee is claimed.

Active Horizon/Technical generators remain v1. No public v2 view, v2 request, Technical
change, admission/evaluation expansion, dashboard/persistence/database change, dependency,
retry or fallback. Live calls: zero. V0.8A remains not release-ready and no live reliability
improvement is claimed. Public rendering/validation remains mandatory in 6V-E.

Validation: starting **528 PASS**, final **535 PASS**; seven new offline matrix tests.
Network/model/DB guards protect draft tests; existing mocked v1 generation and combined
regressions remain passing. `git diff --check` PASS. Accumulated working tree preserved;
no commit/tag/push and zero live Alpha Vantage/OpenAI calls.

## Step 6V-E — Offline Horizon deterministic assembly

Added horizon_assembly.py: frozen-draft and readiness revalidation → deterministic
assembly → unchanged public Horizon validation → offline horizon-synthesis-v2 view.
Identity/ordered limitations are copied authoritatively; explicit roles remain model-
owned; Technical bindings render labels/citations together. Source-condition dependencies
are retained separately from explicit analytical selections until public serialization.
Condition-bound FORECAST is deterministic; unconditioned predictive prose still rejects
under the existing validator unless classified correctly. No post-hoc repair or entailment
claim. Source-available invalidation and WAIT confirmation-or-invalidation are unchanged.

Inactive horizon_draft summary grounding now includes valid selected-condition lineage,
as permitted by the public contract and Step 6V-E. No source-conclusion-based inference.
No active v1 schema/validator/pipeline, Technical, admission, evaluation, dashboard,
persistence, database or dependency changes. Both production generators remain v1.
Public shape and source/provenance context are preserved; compatibility remains pending.
No live calls, retries, repair passes or fallback; no release/live reliability claim.

Validation: starting **535 PASS**, final **541 PASS**; six new offline assembly matrix
tests. Authoritative echoes, exact text, namespaced roles, condition lineage/FORECAST,
source invalidation absence, malformed drafts and public prose rejection pass. Mocked
combined SHORT/SWING/MEDIUM/LONG remain v1 with existing call-count/source-preservation
checks. `git diff --check` PASS. Zero live Alpha Vantage/OpenAI calls; no commit/tag/push.

## Step 6V-F — Offline v2 compatibility and activation readiness

This section supersedes earlier V2_COMPATIBILITY_PENDING statuses where explicitly
listed below. Both ACTIVE generator identifiers remain v1. The only production
eligibility change is the exact tuple `SUPPORTED_TECHNICAL_ARTIFACT_VERSIONS`:
`technical-analyst-v1`, `technical-analyst-v2`. Admission and evaluation use that
explicit set independently of the architecture mapping and active generation.
No other policy predicate, public shape, prompt or schema is changed.

| Consumer | Status | Evidence / scope |
| --- | --- | --- |
| Normal Technical generator/pipeline | V1_ONLY | Existing mocked request/pipeline regressions still emit v1 |
| Normal Horizon generator/pipeline | V1_ONLY | Existing v1 request/combined regressions retained |
| Technical storage and explicit save envelope | V1_V2_COMPATIBLE | Actual assembled v2 and v1 exact temporary SQLite round trips; opaque labels preserved |
| Technical evaluation | V1_V2_COMPATIBLE | Actual v2 versus v1, all signals/both native horizons: identical 5/20 session methodology, VOO benchmark, returns and directional/outperformance results |
| Horizon Technical admission/readiness | V1_V2_COMPATIBLE | Actual assembled Technical v2 passes source/provenance/evidence/freshness/risk checks through full ready-context chain |
| Technical read-only dashboard | V1_V2_COMPATIBLE | Existing show_interpretation renders actual v1/v2 public objects with original text and exact version displayed; no feature change |
| IntegratedResearchView/analysis accessor and CombinedResearchResult envelope | V1_V2_COMPATIBLE | Assembled v2 validates against unchanged public schema, preserves context/source conclusions and round-trip analysis JSON |
| Horizon dashboard/persistence/evaluation consumers | V2_COMPATIBILITY_PENDING (not implemented) | No such downstream consumer exists to certify; no new feature added |

Technical evaluation consumes signal/confidence, preserved native horizon, record time,
source metadata and evidence digest. It does not interpret generation prose/conditions
or assume v1 prompt mechanics. v2 assembly preserves those public semantics. Evaluation
methodology technical-signal-evaluation-v1, 5/20 XNYS-session mapping, VOO benchmark and
provider-adjusted return policy are unchanged. Existing outcome records are not rewritten.

New full-chain fixtures cover four horizons × three Fundamental directions × three
Technical signals, and every permitted posture: real deterministic Technical draft →
v2 assembly → record/admission → prospective Fundamental artifact/context/readiness →
Horizon draft → v2 assembly/public validation. All evidence and drafts are synthetic;
Fundamental research boundaries are mocked, never live. Source conclusions, authority,
conflict and all six prior policies remain preserved; v2 mapping is evidence-first-
assembly-v1. Existing special conflict/admission tests cover THESIS_CONFLICT and
INSUFFICIENT_EVIDENCE where no ordinary ready matrix input should be invented.

Unknown/empty/malformed Technical versions still reject at strict consumers. Opaque
storage may preserve unknown nonempty historical labels but cannot certify eligibility.
There is no strict Horizon-view ingestion boundary today: the frozen representation
is not a certificate and accepts an arbitrary explicit version by construction. Neither
assembly entry permits caller-selected generation versions; they emit fixed v2. No new
Horizon ingestion API or artificial version gate was added merely to claim coverage.
Future Horizon consumers must explicitly validate versions at their trust boundary.

### Activation review — no activation in this step

ACTIVATION_WIRING_ONLY: author the model-facing v2 instructions from the approved draft
contracts; build bounded request/schema packets; decode responses into draft validation;
call deterministic/public assembly with original source context and actual model identity;
propagate fixed TechnicalDraftError/HorizonDraftError reasons safely through existing
pipeline errors; explicitly select v2 generation after review and update mocked request
regressions. Preserve one request, no retries/repairs/fallback, and readiness immediately
before the Horizon request. Reserved constants alone do not perform this wiring.

ARCHITECTURE_GAP: none identified in reviewed offline scope. Real provider structured-
output acceptance and one-shot model compliance remain unproven. No live validation is
authorized here. Historical lexical/entailment limitations remain. No new agent, provider,
database schema, dependency, portfolio/trading behavior or migration. All historical v1
artifacts stay immutable; no retroactive evidence-first label. V0.8A is not release-ready.

Validation: baseline **541 PASS**, final **545 PASS**; four new compatibility matrix
methods plus updated earlier pending-version expectations. Full historical hardening,
v1, v2 draft/assembly and combined regressions pass. `git diff --check` PASS. All
unit/manual live Alpha Vantage/OpenAI calls: zero. Temporary SQLite storage only;
no user database writes. No commit/tag/push; accumulated changes preserved.

## Step 6V-G1 — Active v2 generation, verified offline

**ACTIVE Technical: `technical-analyst-v2`. ACTIVE Horizon: `horizon-synthesis-v2`.**
This supersedes the inactive/activation-pending status in historical 6V-A–6V-F
entries above. Both use `evidence-first-assembly-v1`; historical v1 identifiers and
consumption remain supported, with no artifact rewriting or implicit upgrades.

The normal Technical and Horizon entry points now make one strict internal-draft
request, decode JSON, validate the draft, call the existing deterministic assembler,
and run retained public validation before returning the existing public artifact.
Model-facing instructions are in `src/generation_instructions.py`; schemas remain
the approved draft schemas. Horizon revalidates readiness immediately before its
request. There is no version fallback, retry, repair request or second model pass.
Assembler function names retain their `_offline` suffix for compatibility: these
functions contain no provider/storage IO and now also serve normal generation.

Technical FEATURE labels/references and missing inventory are software-owned.
Horizon identity, exact ordered limitations and source-condition lineage are
software-owned. Explicit condition selection mechanically produces FORECAST;
unconditioned predictive prose still requires the model's valid classification.
The model still owns signal/posture, confidence, interpretation, evidence relevance
and supporting/conflicting roles. Neither explicit selection nor inherited source
lineage proves entailment or investment correctness. Public safeguards are retained.

Safe errors distinguish OPENAI_REQUEST, RESPONSE_EXTRACTION, DRAFT_DECODING,
DRAFT_VALIDATION, ASSEMBLY and PUBLIC_VALIDATION. Technical pipeline diagnostics
retain the logical TECHNICAL_ANALYST stage plus `generation_substage`, fixed
`validation_reason` and the existing canonical feature family where applicable.
Horizon retains fixed `draft_reason` or public semantic reason through the combined
boundary. Extraction details remain restricted to max_output_tokens, content_filter,
not_completed and empty_output_text. No failed raw text, prompts, IDs or provider
payloads are retained by these diagnostic objects.

Offline evidence: normal Technical requests cover BULLISH/NEUTRAL/BEARISH, both
native horizons, bound sma_200 rendering, roles, conditions and missing inventory.
Normal Horizon requests cover permitted postures, source invalidation present/absent,
identity, limitations, lineage and public validation. Failure matrices exercise draft
and public safeguards with one request maximum and no returned partial artifacts.
All four combined horizons use the actual v2 Technical and Horizon request paths,
mocked provider/model responses and the mocked Fundamental boundary: one Technical
research, one Technical Analyst, one Fundamental research and one Horizon Synthesis,
in that order. Authority, native horizon and prospective readiness remain intact.
SDK transport tests also verify max_retries=0 and store=False with the real request
helper and mocked SDK. A network guard rejects accidental external connections.

Historical v1 response matrices now use an explicitly test-only request harness,
`tests/historical_generation.py`, invoking the retained v1 public validators. This
harness is not imported by production and cannot provide a runtime fallback. Active
v2 tests are separate and invoke normal entry points. Existing historical admission,
evaluation, storage and dashboard regressions remain in the full suite. Downstream
Technical acceptance remains exactly v1/v2, not a version wildcard. All six existing
horizon/sequence/freshness/provenance/risk/invalidation policies remain unchanged.

Validation: baseline **545 PASS**; final **554 PASS**, nine new activation test
methods containing the success/failure matrices, plus updated active-version tests.
Zero live Alpha Vantage/OpenAI calls; no manual ticker run or validation attempt.
No database migration, public shape change, dependency, dashboard feature, portfolio
or brokerage work. No commit/tag/push; earlier uncommitted work is preserved.

Remaining classifications: **OFFLINE_DEFECT: none identified; ARCHITECTURE_GAP:
none identified; PROVIDER_UNPROVEN; MODEL_COMPLIANCE_UNPROVEN.** Ready for **FINAL
OFFLINE REVIEW**, not release sign-off. Provider acceptance of v2 structured output
and one-shot model compliance have not been validated live. No live validation is
authorized by this step; any future live attempt requires separate authorization.

## Step 6V-G2 — Final offline release review

**PASS after two narrow offline corrections.** Active Technical/Horizon generators
remain `technical-analyst-v2` / `horizon-synthesis-v2`, mapped to
`evidence-first-assembly-v1`. Ready for one separately authorized controlled live
validation; **not release-ready**. No live attempt was authorized or consumed here.

### Complete accumulated inventory and classification

Initial state: 14 modified tracked paths and 16 untracked paths; initial
`git diff --check` PASS. Earlier uncommitted changes were preserved. The inventory
below includes every accumulated production change, including untracked source.
M/U describe initial tracked modification/untracked status, not release eligibility.

| Production file | Initial status | Classification and reason |
| --- | --- | --- |
| src/dashboard/technical_adapter.py | M | REQUIRED: delegate Technical research to shared backend while retaining sanitized UI boundary |
| src/horizon_integration.py | M | REQUIRED: exact approved Technical v1/v2 admission set; all other predicates unchanged |
| src/horizon_pipeline.py | M | REQUIRED: shared backend dependency and fixed error propagation; Technical-first one-shot orchestration |
| src/horizon_synthesis.py | M | REQUIRED: active v2 request, public validators, approved source-available invalidation, safe diagnostics |
| src/technical_analyst.py | M | REQUIRED: active v2 request, retained public parser, fixed reasons and corrected nested-label matcher |
| src/technical_evaluation.py | M | REQUIRED: exact approved v1/v2 source eligibility; evaluation methodology unchanged |
| src/generation_contracts.py | U | REQUIRED: authoritative versions, exact acceptance tuple, immutable v2 architecture mapping |
| src/generation_instructions.py | U | REQUIRED: active model-facing draft/ownership instructions; G2 clarification described below |
| src/technical_pipeline.py | U | REQUIRED: shared backend retrieval/features/catalog/analyst orchestration and safe errors |
| src/technical_draft.py | U | REQUIRED: strict bound selections/roles, conditions, missing impact and internal validation |
| src/technical_assembly.py | U | REQUIRED: exact labels/text/refs/roles/missing inventory, source metadata, final public validation |
| src/horizon_draft.py | U | REQUIRED: explicit namespace/condition/role selections and internal validation |
| src/horizon_assembly.py | U | REQUIRED: identity/limitations/lineage/classification assembly and final public validation |
| src/research_pipeline.py | Clean at start; modified in G2 | SAFE SUPPORTING CHANGE: withhold arbitrary optional-source error text without changing retrieval behavior |

Initial modified tracked test files (TEST-ONLY): tests/test_v07.py,
tests/test_v07_dashboard.py, tests/test_v08.py. Initial untracked test files
(TEST-ONLY): tests/historical_generation.py, tests/test_generation_contracts.py,
tests/test_technical_draft.py, tests/test_technical_assembly.py,
tests/test_horizon_draft.py, tests/test_horizon_assembly.py,
tests/test_v2_compatibility.py, tests/test_v2_activation.py. G2 additionally modifies
tracked tests/test_v05.py for the optional-warning regression.

Initial modified tracked documentation (DOCUMENTATION): README.md,
docs/V0_7_TECHNICAL_ANALYST.md, docs/V0_8A_COMBINED_RESEARCH.md,
docs/V0_8A_HORIZON_SYNTHESIS_AGENT.md, docs/V0_8A_HORIZON_SYNTHESIS_DESIGN.md.
Initial untracked documentation: this release checkpoint. G2 also updates
tracked docs/V0_8A_FRESHNESS_PROVENANCE_POLICY.md with current-status context.

SAFE SUPPORTING historical code: retained v1 prompt/schema references are used by
historical response tests; the public parsers remain active v2 assembly safeguards.
They are not runtime fallback generators. tests/historical_generation.py is explicitly
test-only and has no production import. No unexplained, suspicious or dead executable
production branch was found. No live harness, counters, debug prints, marker logic,
/tmp results, hardcoded live ticker/date, disabled validator or repair loop exists
in the reviewed accumulated production changes. Existing ignored .env, .venv,
decisions.db and Python caches were classified as local configuration/environment,
user database and generated caches; none was deleted, normalized or committed.
Credentials/database contents were not printed or used for research.

### Findings and corrections

1. **OFFLINE_DEFECT (resolved): Horizon prompt/validator mismatch.** G1 instructions
   allowed every statement to ground itself through explicit selection *and/or*
   condition lineage. The approved v2 validator still requires at least one explicit
   analytical FEATURE/CITATION selection per statement. The instruction now states
   that requirement even for condition-bound statements. Source lineage can still
   supply the other summary namespace and must still be inherited during assembly.
   No schema, validator, public behavior or methodology changed. A normal-path test
   rejects lineage-only selection with HORIZON_DRAFT_GROUNDING_REQUIRED, then accepts
   explicit Technical selection plus Fundamental condition lineage and FORECAST.

2. **OFFLINE_DEFECT (resolved): optional Fundamental warning exposed provider text.**
   The pre-existing `_retrieve_optional` warning formatted the RuntimeError message.
   Alpha Vantage secret redaction does not make arbitrary provider body text approved
   diagnostics. The warning now contains fixed text and `detail=withheld`; the existing
   client already logs fixed operation/function/classification. All three optional
   source paths retain their existing empty/missing result behavior and one request.
   Mocked provider-body tests verify no body/secret appears in either log. No provider
   client or Fundamental analysis/methodology was changed.

3. **DOCUMENTATION_ONLY (resolved): stale present-tense status.** Current-status notes
   distinguish the active v2 implementation from historical design/step entries.
   Initial Horizon identity-echo prose, Technical missing-inventory ownership, old
   backend-to-dashboard dependency, obsolete risk-block descriptions and old live
   status were corrected narrowly. Historical findings and version IDs are preserved.

### Execution, ownership and policy review

Each normal Technical/Horizon path makes exactly one strict draft request, then
local draft validation, deterministic assembly and retained public validation.
Horizon recomputes readiness immediately before the request. No fallback, retry,
repair pass, second validation model or partially returned artifact exists. Software
renders only explicit selections or mandated source lineage, never infers semantic
relevance or analytical roles. Signal/posture, confidence and interpretation stay
model-owned. Both-namespace summary grounding and source invalidation are retained.

The combined path remains Technical research → Technical Analyst → Fundamental
research → prospective artifact → exact Fundamental available_at as integration_as_of
→ integration/readiness → Horizon synthesis. One call per logical stage, no hidden
reruns; no source timestamp repair. No DecisionStore is supplied and persistence is
explicitly disabled. Technical record construction is an in-memory envelope, not a
save. No automatic signal/view/DecisionRecord/evaluation/portfolio/brokerage writes.
Existing optional Fundamental missing-source handling is not fallback generation.

All seven policies remain as approved: technical-horizon-selection-v1,
combined-research-sequencing-v1, technical-freshness-v1, fundamental-provenance-v1,
risk-applicability-v1, source-available-invalidation-v1, evidence-first-assembly-v1.
No authority/conflict, freshness, provenance, risk, confidence or 5/20-session VOO
provider-adjusted evaluation changes were introduced by activation or this review.

Accumulated behavioral changes are explained: Step 6P progressive label scrubbing
corrects the nested sma_200/sma_20 false rejection; Step 6R conditions invalidation
requirements on authoritative source availability; Step 6V-F explicitly admits
approved v2 public semantics. V2 adds bound-draft validation and assembles copy-only
fields while keeping every applicable public semantic safeguard. No validator was
removed, and G2 changes no validation behavior. No safeguard weakening identified.

### Error, imports, compatibility and coverage

Technical/Horizon safe stage/reason propagation and four-value response_detail
allowlists were inspected and exercised. No raw generated output, prompt, failed
citation ID or arbitrary provider body is retained in v2 error diagnostics. Unexpected
exceptions fail closed with generic fixed classifications; no catch resumes generation.
The optional warning correction closes the reachable pre-existing logging exception.

No external dependency changes. Backend does not import dashboard or Streamlit.
Fresh-process imports succeeded in three orders with socket, HTTP, OpenAI construction
and SQLite access blocked and environment equality checked. Deferred local imports
link generators to draft/assembly modules without import-time cyclic initialization;
there is module-level coupling, not a claim of a completely acyclic dependency graph.
No network, database or environment mutation occurred on those imports.

Historical v1 admission, evaluation, immutable storage round trips and read-only
dashboard display remain covered. No migration, rewriting or retroactive evidence-first
mapping. Storage deliberately preserves opaque nonempty unknown labels; strict
admission/evaluation reject unsupported versions. IntegratedResearchView has no separate
public ingestion/version-certification API; a manually constructed view is not trusted
readiness. Neither assembler accepts a caller-chosen output version.

Coverage reviewed: all Technical signals/native horizons; sma_200 and nested matcher;
selection/role/condition/missing-data/prose failures; four active combined horizons;
Horizon conditions, WAIT, source absence, namespace grounding, all permitted posture
branches in the offline 36-combination matrix; safe errors and call counts; v1/v2
storage/evaluation/admission; exact unknown-version rejection. Two narrow tests were
added for the concrete G2 findings. No other release-critical coverage gap identified.
Lexical false positives/negatives and lack of semantic entailment remain documented
non-blocking limitations; this audit does not establish analytical accuracy.

### Final validation and live-readiness decision

Baseline **554 PASS**. Final **556 PASS**, two tests added. Final full suite ran with
external socket operations blocked and SQLite restricted to temporary/in-memory
storage: **0 unmocked network attempts, 0 non-temporary DB attempts** (969 permitted
temporary/in-memory connection calls). Live Alpha Vantage/OpenAI calls: **0/0**.
Final `git diff --check` PASS. No commit/tag/push; all accumulated changes preserved.

Remaining substantive classifications: **PROVIDER_UNPROVEN** and
**MODEL_COMPLIANCE_UNPROVEN** only. No unresolved offline, architecture or methodology
blocker. The code supports one separately authorized controlled run with one ticker,
one decision horizon, one Technical request, one Fundamental execution and one Horizon
request; fail closed, no retry/rerun/persistence/portfolio/brokerage. No new live harness
was created. Any future temporary harness must use a fresh attempt guard and retain
current fixed v2 draft/public diagnostics; historical consumed markers/results cannot
be reused. That operational preparation is not another architecture change.

**Recommend ONE separately authorized controlled live validation.** Require pre/post
full suite and diff checks, safe diagnostics and no side effects. This is readiness
for authorization, not authorization itself. V0.8A remains **not release-ready** until
provider/model execution evidence and final human release review support sign-off.


## Step 6V-G3 — Controlled live execution validated

Verified against the preserved external `/private/tmp/v08a_6vg3_result.json` and
consumed `/private/tmp/v08a_6vg3_started` marker. Neither artifact was modified.
This is a historical execution-validation record, **not a current investment
recommendation**. No investment accuracy or long-term reliability is established.

| Field | Observed result |
| --- | --- |
| Target | NVDA / MEDIUM |
| Technical | technical-analyst-v2; BULLISH; confidence 71; SWING_1_TO_4_WEEKS |
| Fundamental | Accumulate; confidence 66; fundamental-provenance-v1 |
| Integration | FUNDAMENTAL_PRIMARY; ALIGNED; SYNTHESIS_READY; no blockers |
| Horizon | horizon-synthesis-v2; FAVORABLE_NOW; synthesis confidence 74 |
| Logical stages | Technical Research 1; Technical Analyst 1; Fundamental Research 1; Horizon Synthesis 1 |
| OpenAI requests | Technical 1; Fundamental 1; Horizon 1; total 3 |
| Alpha Vantage request-function calls | 9 |
| Attempts / retries / reruns / fallback / repair | 1 / 0 / 0 / 0 / 0 |
| Persistence / portfolio / brokerage / database attempts | 0 / 0 / 0 / 0 |
| Pre/post tests and diff check | 556 PASS; diff check PASS |
| Repository changes caused by validation | None |

Integration timestamp and Fundamental available_at both equal
`2026-09-20T04:02:34.842378Z`. Both sources were admitted; Technical was FRESH and
Fundamental CURRENT_SYSTEM_TRUSTED. Exact identity, ordered limitations and disjoint
roles passed. Invalidation references were F_INVALIDATION:1 and T_INVALIDATION:0.
Limitations remained PROVIDER_PUBLICATION_VINTAGE_UNVERIFIED and
FUNDAMENTAL_MATERIAL_EVENT_COVERAGE_UNKNOWN. Provider acceptance and Technical/Horizon
one-shot compliance are proven **for this attempt only**. The attempt remains consumed.

## Final V0.8A release review

**PASS WITH FIXES — documentation only.** Starting and final suites: **556 PASS**.
No production/test changes, new tests, methodology changes or architecture changes.
No live provider calls, database migration, feature work, commit, tag or push.

The complete accumulated inventory is the G2 file-classification table above:
13 REQUIRED PRODUCTION files, one SAFE SUPPORTING production file, 12 TEST-ONLY
files and seven DOCUMENTATION files. All 33 modified/untracked files are accounted
for. None is suspicious, unrelated or unexplained dead code. Historical v1 helpers
are intentional test/compatibility support, not production fallback. The original
17 tracked modifications and 16 untracked files remain preserved.

All repository file hashes matched the preserved G3 pre-run snapshot before review
edits. The G2 complete production audit therefore applies to the exact live-validated
code. Final review reconfirmed active versions, request/readiness boundaries and
preserved diagnostics. Technical and Horizon each use one request followed by draft
validation, deterministic assembly and unchanged public safeguards. The model owns
meaning, relevance, roles and conditions; software resolves only authoritative
structure and source lineage. No prose-based citation repair or semantic inference.

Technical-first sequencing, one execution per stage, Fundamental availability-based
integration timestamp, horizon/authority mappings, XNYS freshness thresholds,
prospective provenance, fail-closed readiness, risk applicability and all seven
approved policies remain intact. Unknown IDs/versions reject at strict boundaries.
Condition-bound FORECAST, source-available invalidation and namespace-local role
exclusivity remain enforced. No public validator was removed or weakened.

Historical v1 storage, evaluation, admission and display remain supported without
rewriting or retroactive evidence-first labels. No automatic persistence, evaluation,
portfolio or brokerage operation is introduced. No new dependency, backend/UI
inversion, startup-breaking cycle or import-time provider/database operation exists.
Deferred assembly imports are intentional; fresh-process coverage from G2 remains
applicable to unchanged code. No live instrumentation is in production or the repo.

Documentation-only release issues resolved: stale current claims of inactive/offline-
only/unvalidated v2 and pending provider acceptance were replaced in README and
current document status sections. Historical failures and chronological step statuses
remain explicitly historical. The G3 record above supplies bounded live evidence.

No release-critical test gap or remaining offline, architecture, methodology,
historical-compatibility or release-hygiene blocker was found. Lexical false positives/
negatives and unproven semantic entailment remain documented limitations. Final tests
ran with external sockets blocked and SQLite restricted to temporary/in-memory test
storage; no live calls or real-user-database access occurred. Final diff check PASS.
Production/test hashes and the user database remained unchanged; the G3 marker remains.
The first extra guarded run incorrectly treated temporary read-only SQLite file URIs
as non-temporary paths (32 failures, four errors). Correcting only the external guard
to decode file URIs restored 556 PASS: zero network attempts, zero non-temporary DB
attempts and 969 temporary/in-memory connections. No repository code/test fix was needed.

**Release-ready for a subsequent explicitly authorized commit/tag/push step.** This
review authorizes none of those operations and no further live attempt. V0.8A remains
research-only; portfolio-aware decision context belongs to future V0.8B.
