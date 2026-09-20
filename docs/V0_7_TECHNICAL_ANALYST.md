# V0.7D — Technical Analyst & Short-Term Signal Contract

> Current release status: active generation is `technical-analyst-v2` and
> `horizon-synthesis-v2` under `evidence-first-assembly-v1`. Historical v1
> consumption remains supported. Earlier step-specific status statements below
> are historical. G3 validated provider acceptance and one-shot compliance for one
> controlled NVDA/MEDIUM execution; it did not validate investment accuracy or
> long-term reliability. No retries/fallback/repair or semantic-entailment guarantee.
> Research-only V0.8A is ready for separately authorized release publication;
> portfolio-aware decision context remains future V0.8B work. See the
> [release checkpoint](V0_8A_RELEASE_CHECKPOINT.md).


## Objective

One Technical Analyst interprets existing deterministic evidence. It generates no market
facts, indicators or levels. `analyze_technical_snapshot(snapshot, catalog, horizon)` is
the explicit AI boundary, returning an immutable TechnicalSignal after validation.

## Architecture

HistoricalOHLCV → deterministic features → evidence catalog → Technical Analyst →
TechnicalSignal. The existing `openai_client.request_text` provides the centralized
model (`gpt-5.6-terra` at implementation), Responses structured output, timeout and
zero-retry behavior. No new client, secret path, specialist registry entry or framework
is introduced. Failure propagates; NEUTRAL is never an error fallback.

## Signal Vocabulary

BULLISH, NEUTRAL, BEARISH describe technical research, not Buy/Hold/Sell recommendations.
A deterministic BULLISH_STACK does not force BULLISH: the analyst considers conflicts,
momentum, volume and limitations. Fundamental recommendations remain independent.

## Horizons

- SHORT_TERM_1_TO_5_SESSIONS: approximately the next one to five completed trading sessions.
- SWING_1_TO_4_WEEKS: approximately the next one to four trading weeks.

A call chooses exactly one approved horizon. These are research scopes, not order
expirations, promised holding periods, price forecasts or resolved evaluation windows.
No technical outcome/evaluation integration is added.

## Confidence

Integer 0–100 measures evidence strength, not probability, expected return or win rate.
Values above 90 are rejected if any catalog item is unavailable or conflicting IDs are
reported. They are not clamped. The prompt additionally requires exceptional consistency;
validation cannot prove that consistency or detect every omitted conflict.

## Evidence Grounding

The supplied catalog must exactly match deterministic construction from the supplied
snapshot, preserving local T IDs, versions and provenance. The pre-call gate requires
an approved horizon, latest completed session/close and at least one available TREND or
MOMENTUM item. SMA200 is not required. Below this gate, zero OpenAI calls occur.

Every summary, thesis, confirmation, invalidation and risk statement contains text plus
available evidence IDs. Supporting IDs must be nonempty; conflicting IDs may be empty.
Unknown, duplicate and unavailable citations are rejected, as is supporting/conflicting
overlap. Named canonical feature labels must have their corresponding available citation.
Evidence ordering/IDs are unchanged from technical-evidence-v1.

## Trusted vs Model-Owned Fields

`LLMTechnicalAnalysisOutput` remains the public representation. The active v2 model
owns signal, confidence, interpretation, explicit evidence/role selections, conditions,
risks and missing-data impact text. Software assembles public citations and the exact
missing-ID inventory from the authoritative catalog. The draft schema excludes
identity/provenance fields.

Application code attaches TechnicalProvenance (symbol, as-of, latest session and source
methodologies), requested horizon, catalog version, model name and analyst methodology
`technical-analyst-v2`. The model cannot rewrite these. Only `catalog.to_packet()` and
the horizon are sent, never the full source dataset or fundamental/portfolio/history data.

## Confirmation

At least one cited confirmation condition describes a future observable development
that would strengthen the thesis, using available concepts. No arbitrary numeric levels
or execution fields are allowed.

## Invalidation

BULLISH and BEARISH require at least one cited invalidation condition; NEUTRAL may supply
one. Conditions describe thesis-changing developments, not stop orders. The prompt keeps
these future conditions separate from present interpretations.

## Missing Data

Every unavailable catalog ID must appear in `missing_evidence_ids`. A nonempty explanation
is required when missing items exist. Unavailable features cannot be cited as observed
facts. Partial snapshots can still yield any of the three signals if the minimum gate
passes; missing evidence is not mechanically classified as neutral.

## Hallucination Controls

Strict output shape and local validation reject invalid fields/enums/confidence, unknown
or unavailable citations and obvious opposite thesis wording. The prompt prohibits
outside market knowledge, indicator calculation and future events presented as facts.

A conservative **no-numeric-literals prose contract** keeps numbers in the existing
catalog. Canonical names such as `sma_20` and `momentum_5` are allowed with the required
citation; other digit-bearing prose is rejected. Thus invented RSI values, prices and
percentages fail rather than being approximately matched to unrelated catalog numbers.
Exact supplied numeric facts are not restated either: consumers inspect their citations.
Support/resistance, breakout, current-quote and execution phrases covered by the explicit
validator are rejected. This restriction can reject benign phrasing and is documented
as part of technical-analyst-v1, not a general financial-language classifier.

These checks do not prove natural-language entailment. Synonyms, numbers spelled as
words, subtle contradiction, uncited paraphrases and omitted conflicts can evade local
checks. Missing-ID coverage does not prove a good explanation of its impact. Conditions
are structurally separate but their future semantics remain partly prompt-enforced.
No perfect hallucination elimination or independently verified reasoning is claimed.

## Research vs Trade

TechnicalSignal is research, not an executable trade. There are no shares, allocation,
entry/stop/target orders or portfolio decisions. No persistence or automation occurs.

## Verification

Seven mocked tests added; all 379 tests pass. Coverage includes both horizons/all signals,
confidence edges, trusted provenance, insufficient-evidence zero-call gates, invalid IDs,
missing data, invented prices/indicators/levels, obvious thesis contradiction, required
conditions, malformed responses and API errors without fallback. The bounded strict
request is verified and no market-data calls are made. Optional manual OpenAI validation
was skipped; live structured-output compatibility was not independently tested this step.

## Limitations

No support/resistance engine, market-regime model, benchmark/relative-strength evidence,
technical signal persistence, outcome evaluation, portfolio synthesis, charts or trading.
RAW corporate-action discontinuities and provider-vintage uncertainty remain visible in
the evidence. V0.1–V0.6 and V0.7A–C contracts/calculations remain unchanged.

## Next Step

V0.7E — Technical Signal Persistence. Not implemented here.

## Step 6J — Prohibited-claim lexical boundary clarification

The sole `TECHNICAL_ANALYST_PROHIBITED_CLAIM` branch is `_parse.prose`:

```python
re.search(r'\b(support|resistance|breakout|buy|sell|order|allocation|stop.loss|take.profit|current quote)\b', text.lower())
```

It scans summary, thesis, every confirmation/invalidation/risk statement, and a
nonempty or required missing-data acknowledgement. There is no rationale field.
The same rule applies in every text field; condition semantics are not contextually
examined. Citations do not exempt prose. Case is normalized; word boundaries prevent
matching `sell` in `selling` or `support` in `supports`. Quotes, negation and benign
meanings do not exempt a match. The dots in `stop.loss`/`take.profit` match any single
non-newline character, including a space, hyphen, slash or letter. `current quote`
uses one literal space. No token normalization or financial-language parser exists.

This branch has no numeric/price/percentage test. A later, separate NUMERIC_PROSE
rule rejects all digits except exact cited catalog labels. Thus `sma_50` can pass,
while `SMA50`, `50-day`, quoted historical prices, decimals and percentages cannot.
`enter`, `exit`, `target` and bare `stop` are not in this regex. A dollar sign alone
is not a prohibited-claim match. First failing rule determines the reported reason.

The existing Hallucination Controls section explicitly permits conservative benign
rejections. This is not proof of a faulty implementation of that lexical contract.
The previous prompt's “No support/resistance levels” left benign uses of “support”
and “order” ambiguous, although the validator rejects them. Step 6J clarifies that
existing all-text restriction and provides descriptive/conditional alternatives.
No regex, schema, evidence rule, signal methodology or horizon policy changed.

### Offline phrase matrix

Synthetic phrases only; none is the historical live wording. PASS means local parser
acceptance, not proof of grounding or permission to issue a trade instruction.
All documented lexical expectations matched actual results. PC means
TECHNICAL_ANALYST_PROHIBITED_CLAIM; NP means TECHNICAL_ANALYST_NUMERIC_PROSE.

| Phrases | Expected / actual | Matching pattern | Interpretation |
| --- | --- | --- | --- |
| Momentum remains positive; price is above sma_50; volume is elevated relative to its recent average | PASS / PASS | None (canonical label cited) | Allowed evidence-based descriptions |
| Setup would weaken if momentum turns negative; confirmation would require continued strength; signal weakens if momentum deteriorates; wait for confirmation | PASS / PASS | None | Conditions expressible without prohibited terms |
| Short-term signal is bullish but conflicting evidence remains; selling pressure is elevated; evidence supports caution; momentum informs the interpretation | PASS / PASS | None | No substring false positive |
| Buy at $123; SELL at $123; sell price was $123 | PC / PC | buy / sell | Lexical rejection precedes numeric check |
| Set a limit order at $123; place a stop-loss at the recent low; take-profit is not specified; allocation is outside scope | PC / PC | order / stop.loss / take.profit / allocation | Execution wording rejected even when negated |
| Breakout above recent highs; resistance remains overhead; support is weakening | PC / PC | breakout / resistance / support | Unsupported concept restriction, even without digits |
| Evidence provides support for the thesis; order of indicators is unchanged; quoted “support” | PC / PC | support / order | Benign-language false positives relative to meaning, explicitly excluded by existing lexical contract |
| No buy instruction is supplied; current quote is unavailable | PC / PC | buy / current quote | Negation does not exempt phrases |
| STOP/LOSS is absent; stopXloss is absent | PC / PC | stop.loss | Existing single-character wildcard behavior; not a new semantic rule |
| Price above its 50-day average; volume relative to 20-day average; move above 20-day high; price above SMA50 | NP / NP | Digits, not PC regex | These are not valid prose forms under existing numeric contract |
| Enter at $123; place a stop at $123; target $123; exit position at $123; price was 123.45; momentum is 5% | NP / NP | Digits | Not evidence that the PC regex detects these commands |
| Enter now; exit the position; target the prior high; place a stop at the prior low | Local PASS | None | False negatives against research-only intent; documented lexical non-entailment limitation, not endorsed output |
| Price could test prior highs; downside risk below recent low | Local PASS | None | Grounding in specific supplied evidence is not proven by parser acceptance |
| current␠␠quote; stoploss; stop--loss | Local PASS | None | Known spacing/token limitations; no automatic normalization added |

Descriptive trend, momentum, volatility and moving-average relationships require
available evidence. Benchmark-relative strength and arbitrary high/low levels must
not be fabricated: this contract has no benchmark-relative-strength or support/
resistance engine. Execution/entry/stop/target instructions remain prohibited by the
research-only prompt even where the finite lexical detector misses synonyms.
Expanding or relaxing the detector is not undertaken here. Prompt relationship before
clarification: AMBIGUOUS at lexical granularity, not a requirement to produce banned
wording. Confirmation/invalidation descriptions and the no-execution intent are
compatible. The clarification makes benign-word exclusions explicit; it does not
claim exhaustive semantic enforcement or resolve the unretained live response.

## Step 6P — Canonical feature citations

The sole FEATURE_CITATION_MISSING branch is `_parse.prose`. It scans summary, thesis,
confirmation, invalidation and risk text after statement IDs are validated as nonempty,
unique, known and available. Availability means catalog value is not None. It lowercases
prose and searches canonical catalog labels literally, longest first. No aliases,
regex, stemming or whitespace/hyphen normalization are used. Remaining digits fail the
separate numeric rule. Matching still uses substrings rather than token boundaries.

Only the same statement's `evidence_ids` satisfy named-feature grounding. Top-level
supporting/conflicting IDs do not substitute. A statement may cite evidence assigned
to the global conflicting list. There is no condition-ID field in Technical statements.
Each recognized label requires every catalog entry with that exact label (one in the
trusted fixed catalog). Multiple explicitly named labels require their respective IDs.
Unavailable IDs fail CITATION_INVALID before prose matching; naming an unavailable
feature with other valid citations fails FEATURE_CITATION_MISSING. Missing-data
acknowledgement intentionally skips named-feature grounding so it can describe absent
features, while remaining subject to its other checks.

### Proven defect and narrow correction

Before Step 6P, detection checked the original lowercased text on every iteration,
although numeric scrubbing already removed longer labels. Thus `sma_200` with its
correct T006 citation was rejected for missing T004 (`sma_20`), and
`close_vs_sma_20_pct` with T007 incorrectly required T004. This contradicts the existing
canonical-label-to-corresponding-citation contract. Detection now checks the same
progressively scrubbed text, so a recognized longer label is not matched again as a
shorter nested label. Independently written `sma_200 and sma_20` still needs both IDs.
No alias expansion, indicator, evidence value, availability or generic citation rule
changed. This proves a matcher defect, not the unretained historical Step 6O cause.

### Complete fixed mapping

Aliases: none for every row. Valid location: the named statement's evidence_ids.
Missing behavior: unavailable IDs cannot be cited; acknowledge missing evidence instead.

| Canonical label / diagnostic feature_family | Catalog family | Required ID |
| --- | --- | --- |
| latest_close | PRICE | T001 |
| latest_high | PRICE | T002 |
| latest_low | PRICE | T003 |
| sma_20 | TREND | T004 |
| sma_50 | TREND | T005 |
| sma_200 | TREND | T006 |
| close_vs_sma_20_pct | TREND | T007 |
| close_vs_sma_50_pct | TREND | T008 |
| close_vs_sma_200_pct | TREND | T009 |
| trend_structure | TREND | T010 |
| rsi_14 | MOMENTUM | T011 |
| macd_line | MOMENTUM | T012 |
| macd_signal | MOMENTUM | T013 |
| macd_histogram | MOMENTUM | T014 |
| momentum_5 | MOMENTUM | T015 |
| momentum_20 | MOMENTUM | T016 |
| atr_14 | VOLATILITY | T017 |
| atr_pct | VOLATILITY | T018 |
| latest_volume | VOLUME | T019 |
| average_volume_20 | VOLUME | T020 |
| volume_ratio_20 | VOLUME | T021 |
| completed_bar_count | DATA_QUALITY | T022 |
| missing_session_count | DATA_QUALITY | T023 |

These IDs are documented deterministic catalog slots, not captured live response IDs.
MACD parameters remain the existing 12/26/9 calculation; the matched labels are its
three named outputs, not parameter text. Broad words trend, momentum, volume, average,
price, moving average and volatility have no feature-specific mapping. Neither RSI
nor MACD alone is an alias. Parser acceptance of these words with an unrelated valid
citation does not prove grounding. Digit-bearing variants SMA200, SMA-200, SMA 200,
RSI14, momentum20 and MACD 12/26/9 fail numeric prose, not feature matching. Case and
surrounding punctuation do not change a canonical label match. Embedded/plural forms
containing a literal canonical label can still match; semantic tokenization and
natural-language alias grounding remain limitations, not new rules in this step.

Offline tests cover every row: correct citation accepts; absent statement citations
fail CITATION_INVALID; unrelated available citations fail FEATURE_CITATION_MISSING;
correct conflicting-role evidence accepts when cited in the statement; top-level-only
citation does not suffice; citation without naming the feature accepts. Uppercase and
punctuation variants accept with correct IDs. Multi-label and unavailable-feature
cases preserve grounding. The former nested-label false positives are corrected;
no other observed matrix outcome deviates from the existing structural contract.

Prompt relationship before clarification: AMBIGUOUS about local feature matching,
although documentation already required corresponding citations. The prompt now
explicitly says to cite each named label in that statement and not substitute global
role lists; multi-feature and unavailable-feature handling are clarified. Schema is
unchanged: it specifies evidence_ids, while semantic validation checks their meaning.

Optional `feature_family` diagnostics use only the fixed canonical label vocabulary
above and only for FEATURE_CITATION_MISSING. They propagate through TechnicalValidationError,
TechnicalResearchError and HorizonPipelineError. No arbitrary ID, prose, prompt or
provider body is retained. Existing ValueError classification and dashboard presentation
remain unchanged. Historical feature identity cannot be reconstructed from the old code.


Step 6R aligns the prompt with the existing Confirmation section and parser: every valid
response, including NEUTRAL, requires a cited confirmation. BULLISH/BEARISH still require
invalidation; NEUTRAL may omit it. No Technical validator or schema changed.


## Step 6S — Completed contract audit

The prompt now explicitly states existing ID uniqueness, nonempty/disjoint supporting
roles, local available citations, nonblank statement text, signal/thesis consistency,
exact missing-ID coverage, missing-note requirement and optional risk list behavior.
No parser, schema, methodology or source contract changed. The release checkpoint's
Step 6S matrix inventories all 22 validation reasons and local/transport boundaries,
with fixture and diagnostic coverage. Lexical and entailment limitations above remain.

## Step 6V-A — Generation version reservation

The active generator remains `technical-analyst-v1`. Authoritative identifiers live
in `src/generation_contracts.py`; `technical-analyst-v2` is reserved for the approved
`evidence-first-assembly-v1` contract but is not generated or admitted/evaluated yet.
The existing `analyst_methodology_version` field will distinguish generation
contracts without rewriting historical records or changing investment methodology.
Storage preserves opaque version identities; eligibility remains a separate gate.
See the release checkpoint for consumer compatibility status.

## Step 6V-B — Inactive Technical v2 internal draft

`src/technical_draft.py` defines the frozen internal `TechnicalAnalysisDraft`,
`BoundStatementDraft`, `StatementPart`, and explicit `EvidenceRoleAssignment` types,
a strict bounded schema, and `validate_technical_draft`. It has no request function,
public renderer, persistence, or pipeline activation. **technical-analyst-v1 remains
ACTIVE; technical-analyst-v2 is NOT ACTIVE.**

TEXT preserves model prose. FEATURE explicitly selects an available catalog item to
be named by a future renderer. CITATION explicitly selects evidence without naming
it. Neither proves semantic entailment. All current catalog labels (including PRICE
and DATA_QUALITY labels) are already canonical references under the v1 contract and
are FEATURE-eligible when available. IDs/labels are resolved from the exact source
catalog, verified by existing snapshot preflight; no T006/sma_200 mapping is hardcoded.

Raw canonical labels inside TEXT reject, even when the item is selected elsewhere.
Adjacent TEXT across zero-width CITATION parts is checked together. No citation is
attached to repair prose. Repeated explicit selections remain in parts; the selection
accessor returns unique IDs in first-occurrence order. Role assignments are separate:
duplicate IDs (same or opposite role) reject, at least one SUPPORTING assignment is
required, and narrative/role coverage is intentionally independent.

Confirmation is always required; directional invalidation remains required; NEUTRAL
may omit invalidation. Risk notes use the same statement draft. Missing inventory is
software-derived in catalog order; the draft contains only the impact acknowledgement,
which must be nonblank when missing items exist. The missing-note exception permits
unavailable feature discussion without fabricated citations.

Internal resource limits are 128 parts per statement, 64 statements per condition/risk
list, 64 role assignments and 8192 characters per part/acknowledgement. These bound
response structure, not financial interpretation. Parser bounds match schema bounds.

Draft acceptance is NOT public TechnicalSignal acceptance. It verifies decoded shape,
explicit available selections, binding, role/condition requirements and confidence
constraints. Future 6V-C must revalidate and apply rendered numeric/prohibited-prose,
signal/thesis and all public-contract safeguards before returning any v2 signal.
Dataclass construction alone is not a validation certificate. No prompt, v1 schema,
v1 parser, admission or evaluation gate changes in this step. No live v2 execution or
reliability improvement is claimed.

## Step 6V-C — Offline v2 assembly and public validation

`assemble_technical_v2_offline(draft, snapshot, catalog, horizon, model=...)` in
`src/technical_assembly.py` is a no-IO internal entry point. It reconstructs and
revalidates the frozen draft against the supplied authoritative snapshot/catalog;
dataclass construction is not a validation certificate. Catalog tampering relative
to the snapshot rejects. The draft carries no historical catalog capability: the
caller must retain its original source pair; validation uses the supplied pair.

TEXT is concatenated exactly, FEATURE renders its selected item's exact catalog
label, and CITATION emits no prose. Explicit selected IDs normalize in first-use
order without deleting repeated prose. Roles serialize in assignment order with no
inference or narrative/role equality rule. Missing IDs derive in catalog order;
the model's impact acknowledgement is preserved separately.

The unchanged public `_parse` validates the entire assembled analysis: canonical
feature grounding, numeric/prohibited prose, signal/thesis consistency, confidence,
conditions, risks, available/unique/disjoint citations and missing data. These checks
remain defense in depth even where internal validation/assembly already guarantees
structure. Since v1 parsing trims outer whitespace, the assembler restores only the
exact already-validated input texts/acknowledgement into the frozen public objects;
no words, selections or analytical values are changed. V1 parser behavior is unchanged.

The returned existing TechnicalSignal shape carries `technical-analyst-v2`, explicit
caller-owned model identity, catalog provenance/version and requested horizon. The
approved version mapping identifies `evidence-first-assembly-v1`. No extra public
fields, database migration, provider call or persistence is introduced. Selection
and authoritative rendering prove neither semantic entailment nor analytical truth.

Bound sma_200 selection renders its catalog label and citation together; raw canonical
TEXT, unknown/unavailable selections and invalid rendered prose still reject without
repair. No historical Step 6T.1 response is recreated or claimed correct.

Normal generation/pipeline remains **technical-analyst-v1**. V2 is offline only;
evaluation and Horizon admission remain V2_COMPATIBILITY_PENDING and reject v2.
No active prompt/schema, Horizon, dashboard or persistence changes. No live reliability
improvement is claimed.

## Step 6V-F — Assembled-v2 consumer compatibility

Exact supported public artifact versions are now technical-analyst-v1 and
technical-analyst-v2 for Technical evaluation and Horizon admission. This supersedes
the earlier pending status: actual offline v2 assembly tests establish preserved
signal/horizon/confidence, provenance/evidence and evaluation semantics. Storage
round trips and read-only Technical rendering preserve the original version and text.
Normal generation remains v1. No v2 prompt/request is active; no historical rewrite,
methodology change or live reliability claim. See the checkpoint for activation wiring.

## Step 6V-G1 — Active evidence-first generation

Normal generation now uses **technical-analyst-v2**, superseding the earlier inactive
status above. One strict internal draft request → JSON decode → draft validation →
deterministic assembly → unchanged public validation → TechnicalSignal v2.
`src/generation_instructions.py` supplies the active prompt; the retained v1 prompt
and public schema are historical contract references, not a fallback path.

FEATURE explicitly selects an available catalog item; software renders its label
and reference. CITATION selects evidence without adding prose. TEXT is concatenated
unchanged and cannot independently type canonical feature labels. Software derives
missing inventory, native horizon and source metadata. Evidence roles and all
analytical meaning remain model-owned. No post-hoc citation repair or entailment
claim is made. Failed generation returns no partial signal and makes no retry.

Historical v1 storage/evaluation/admission remain supported. This activation is
verified only through mocks; live provider acceptance and model compliance are
unproven. See the release checkpoint for Step 6V-G1 validation and limitations.
