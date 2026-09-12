# V0.7D — Technical Analyst & Short-Term Signal Contract

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

`LLMTechnicalAnalysisOutput` owns signal, integer confidence, cited summary/thesis,
supporting/conflicting IDs, cited conditions/risks, missing IDs and missing-data text.
The strict schema rejects unexpected identity/provenance fields.

Application code attaches TechnicalProvenance (symbol, as-of, latest session and source
methodologies), requested horizon, catalog version, model name and analyst methodology
`technical-analyst-v1`. The model cannot rewrite these. Only `catalog.to_packet()` and
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
