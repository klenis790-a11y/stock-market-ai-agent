# V0.8A Step 3A — Freshness & Provenance Policy Design

## Status and authority

Design only. This document specifies the user-approved Technical V1 boundaries and
the prospective Fundamental provenance/currentness policy. It supplements the
[main design](V0_8A_HORIZON_SYNTHESIS_DESIGN.md); it supersedes its deferred-threshold
language for Technical freshness only. Step 2 runtime behavior remains unchanged.
Step 3B must implement and test these policies before claiming operational readiness.

Admission asks whether an artifact is structurally valid. Provenance identifies its
origin and methodology. Freshness assesses currentness for permitted use.
Applicability limits its role for the decision horizon. None repairs another:
recent invalid research remains invalid, and trusted historical research need not
be current. No confidence averaging or research conclusion changes are authorized.

## Technical freshness — technical-freshness-v1

Let S be the preserved latest completed signal session. Age is the number of XNYS
sessions **strictly after S** whose actual regular-session close is **at or before
integration_as_of**. S is excluded, so its completion corresponds to age zero.
Use the existing versioned USMarketCalendar, aware UTC timestamps and exchange-local
America/New_York semantics. Never subtract calendar days or count weekdays.

| Native Technical horizon | FRESH | AGING | STALE |
| --- | --- | --- | --- |
| SHORT_TERM_1_TO_5_SESSIONS | Age 0–2 | Age 3–5 | Age >5 |
| SWING_1_TO_4_WEEKS | Age 0–10 | Age 11–20 | Age >20 |

These are explicit V1 product/methodology choices, not empirically demonstrated
market laws. The native horizon selects the row, not the integration decision horizon.
A SHORT signal used as LONG context still ages under the SHORT rule.

At exactly age 5 or 20 the artifact remains AGING; it becomes STALE at the next
completed session. Thus “full horizon elapsed” means **beyond** the inclusive upper
boundary for this policy. This exact table takes precedence over informal wording.

### Temporal validation and exceptional cases

- Validate admission first. Preserve the signal's research-as-of, latest session,
  availability/record time and native horizon separately; do not infer generation time.
- Research-as-of and known artifact availability must not exceed integration_as_of.
  Future research, or integration before S closes, fails temporal admission; freshness
  is UNKNOWN/unusable, never a negative age clamped to zero.
- Missing S, unsupported native horizon, inconsistent session metadata, naive timestamps
  or unavailable calendar coverage cannot yield FRESH. Return UNKNOWN with a reason;
  retain the separate rejection/block when the condition violates admission.
- Validate S is an actual completed XNYS session consistent with the source contract.
  The existing admission checks must not be loosened by the age calculator.
- Weekends and exchange holidays add zero sessions. A half-day adds one only when its
  actual early close is reached; a normal unfinished session adds zero. At exact close,
  the session counts as completed. DST follows the calendar/timezone implementation.
- Preserve calendar identifier/version, S, integration_as_of, counted age and policy
  identifier in the future context. No provider availability or later outcome chooses S.

Future tests must cover both boundary sets (0/2/3/5/6 and 0/10/11/20/21), weekends,
observed holidays, half-day before/at/after close, DST, missing/future metadata and
calendar coverage failures. These are design requirements, not new tests in Step 3A.

### Freshness is not evaluation

Freshness decays within the declared research scope: an AGING signal may still be
inside that scope. V0.7 evaluation separately uses fixed 5/20-session checkpoints
from a future reference close after record creation. Freshness starts from the
signal's latest completed evidence session. Different anchors and purposes mean
an evaluation can remain pending after research has become stale. Do not change
evaluation horizons, enrollment rules or historical outcomes to align these clocks.

## Fundamental provenance — fundamental-provenance-v1

This policy governs both prospective source attestation and the limited operational
currentness rule below. It does not assert continuous event monitoring.

### What current code actually preserves

ResearchSnapshot has generated_at, provider source, normalized facts and metrics.
Statements preserve fiscal_date_ending; earnings may preserve reported_date;
news may preserve time_published. Stock data has a data timestamp and optional earnings/
guidance fields. Transcript segments preserve text/speaker information but not a
reliable standalone publication cutoff. Fiscal period end is not publication time.
Maximum observed news/earnings dates are not proof of exhaustive event coverage.

InvestmentAnalysis preserves interpretation but no verified native horizon or
methodology identifier. DecisionRecord has a save timestamp and optional native
horizon, not a complete same-run provenance packet. Step 2 caller reference strings
are attestations, not proof of current pipeline origin. Existing dashboard research
reports no accessible complete same-run catalog through its pipeline return value.

### Prospective trusted artifact contract

A future pipeline wrapper must emit an immutable artifact **after successful existing
research validation**, preserving the original conclusion rather than generating a
new recommendation. Required new metadata must be captured at generation time:

| Field/group | Requirement and capture source |
| --- | --- |
| artifact/schema version | Required prospective `fundamental-research-artifact-v1`; new wrapper constant, never backfilled |
| methodology manifest | Required stable identifier for the actual approved research path plus existing configuration/model identifiers; define the path manifest when the wrapper is implemented, not a guessed version for old records |
| symbol and original analysis | Required exact validated output, confidence, conditions, risks and references; no rewriting |
| native research horizon | Explicit caller-supplied scope retained; missing is unknown and blocks primary applicability until supplied, never default LONG |
| run identity | Required application-owned integration run/request identity, associated with explicitly requested generation/refresh |
| research_as_of / available_at | Required aware UTC evidence assessment time and validated research completion time, captured by orchestration; neither is a DB save time |
| retrieval interval / data_cutoff_as_of | Required application capture start/end for the actual evidence acquisition; cutoff is an acquisition boundary, not a claim of exhaustive event coverage |
| per-source coverage | Required status entries for financial statements, earnings, news and transcript/guidance; retain actual observed periods/dates if present, otherwise explicit unavailable/unknown |
| original evidence packet | Required exact same-run facts/metrics/catalog and ordered IDs; attach a prospective catalog-contract version and packet identity/digest without rebuilding historical IDs |
| provenance attestation | Required application-owned validated-run origin and known portfolio-independent path; no user string alone can confer trusted-current status |
| provider and model identity | Preserve actual provider/source and model/configuration used; no API keys, raw secrets or invented provider publication timestamps |

The smallest future pipeline change is to return a sidecar containing the already
created evidence and validated output, and capture run/configuration/timing metadata
at orchestration boundaries. It must not alter prompts, conclusions or minimum-evidence
rules merely to create this envelope. Binding packet identity to a run prevents
accidental cross-run mixing; it is not cryptographic proof against a malicious caller.
Existing in-memory portfolio-context absence can be attested by the actual call path;
removing portfolio prose after generation is insufficient.

No new schema is required by this design. The sidecar is prospective and transient;
legacy persistence behavior remains unchanged. Exact methodology manifests must reflect
the implementation inspected when the wrapper is built. An unsupported/missing manifest
fails current-artifact admission rather than being labeled current by default.

### Minimal provenance states

- CURRENT_SYSTEM_TRUSTED: generated through the approved prospective wrapper, validated,
  with supported manifest, exact evidence binding and required metadata.
- LEGACY_UNKNOWN: origin/methodology cannot be established under that contract.

A current schema-shaped dictionary or recent timestamp alone does not establish trust.
Corruption remains admission rejection, not another trust state. Legacy records remain
readable historical beliefs. Never stamp them with current versions, infer their cutoff,
or upgrade them from file dates, insertion order or the running application's version.

## Fundamental event currentness and operational freshness

An artifact cannot prove that no later earnings, guidance, filing, corporate action
or other material event occurred after its cutoff without authorized refresh or
sufficient deterministic event coverage. Even a fresh provider response may omit or
delay an event. Trusted provenance and universal event-currentness are distinct.

For V1, **require a trusted same-run or explicitly refreshed artifact bound to the
current integration request for primary Fundamental operational use**. “Refreshed”
means a new validated research/evidence artifact, not touching an old timestamp.
There is no automatic refresh. A new later request cannot reuse the prior request's
currentness qualification merely because little time passed.

Within that explicitly bounded run, Fundamental FRESH means **operationally current
under the captured acquisition policy**, not “no material event occurred.” Record a
mandatory limitation: event completeness and the interval after each provider response
are unverified. Sequential retrieval is not an atomic market snapshot. Integration
uses the completed run's explicit assessment timestamp; research/cutoff/availability
must all precede or equal it, with factual per-source timestamps retained. Historical
as-of requests cannot use later-retrieved facts as if their old publication state
were established. If this temporal binding cannot be established, block.

| Fundamental state | V1 assignment |
| --- | --- |
| FRESH | Admitted CURRENT_SYSTEM_TRUSTED artifact, same authorized run/refresh binding and successful evidence acquisition/validation, required cutoff metadata present; explicitly scoped operational meaning |
| UNKNOWN | Historical reuse without current coverage; legacy provenance; missing run/cutoff binding; or unresolved required acquisition coverage |
| AGING | Not assigned by V1; no approved elapsed-time decay model |
| STALE | Not inferred from age in V1; a future deterministic invalidating-event policy may establish it, but V1 does not invent such monitoring |

Unknown required coverage cannot be waived by a successful LLM output. Optional source
absence already accepted by specialist rules remains an explicit limitation; it is not
proof of complete events. Observed periods/news dates remain factual metadata only.
Thus full event-currentness can remain unknown even when limited same-run operational
freshness is FRESH. Consumers must carry both the qualification basis and limitation.

## Applicability, missing data and readiness implications

The main design's authority rules remain unchanged. Freshness is necessary, not
sufficient: primary native-horizon coverage, admission and required risk/evidence
checks must also pass. This document does not manufacture missing applicability facts.

| Decision horizon | Primary requirement | Secondary treatment |
| --- | --- | --- |
| SHORT / SWING | Admitted, native-compatible Technical artifact with FRESH or AGING status; AGING caution required | Fundamental may provide admitted contextual evidence; unknown provenance/currentness cannot establish current facts or veto/endorse a setup as current research |
| MEDIUM / LONG | Trusted, same-run/refreshed Fundamental artifact with operational FRESH qualification and verified native applicability | Admitted FRESH/AGING Technical research informs timing/context; stale/unknown Technical stays historical, not current timing evidence |

Missing/unusable primary research blocks and yields INSUFFICIENT_EVIDENCE. Primary
Fundamental UNKNOWN blocks MEDIUM/LONG; bullish Technical cannot replace it. Stale
Technical blocks SHORT/SWING even if Fundamental is favorable.

Secondary gaps do not automatically block. They can be non-blocking when existing
specialist validity holds and no required integration risk/applicability check depends
on them. If that dependency cannot be determined, retain the blocker. Do not add
feature counts or duplicate specialist minimum-evidence rules. A missing SMA200 in an
otherwise admitted secondary Technical artifact is not by itself a LONG blocker.
Legacy/unreliable secondary evidence must remain clearly segregated history or be
excluded, not silently treated as NEUTRAL. A degraded primary-only view must disclose
unassessable cross-layer agreement, never claim ALIGNED.

SYNTHESIS_READY means all deterministic gates passed, not a favorable recommendation.
BLOCKED contexts must never reach the future agent. These policies alone do not
resolve every native-horizon/material-risk ambiguity; unsupported cases remain blocked.
No timing posture, synthesis confidence or integrated recommendation is produced here.

## Dashboard and implementation boundary

The Fundamental dashboard currently lacks the complete integration sidecar. Exposing
it and wiring explicit run/refresh identity is later implementation work. Current
Step 2 records cannot be promoted through this design alone. Step 3B can implement
Technical age calculations and conservative UNKNOWN/BLOCKED Fundamental behavior;
trusted same-run qualification requires the prospective wrapper before activation.
No dashboard, provider, prompt, source model, test or database change occurs now.

## Historical integrity and future evaluation

Preserve source methodologies and each applied policy identifier alongside assessment
as-of, calendar version, source identity, age and reasons in future derived contexts.
A later version creates a new explicitly labeled assessment; it cannot overwrite old
policy decisions or pretend its rules existed when historical research was generated.
No persistence mechanism is added here.

Technical thresholds are testable product hypotheses. Future prospective evaluation
may compare predeclared alternatives on appropriate held-out/future observations,
with denominators and methodology versions explicit. Do not tune against outcomes
then describe the tuned rules as predeclared. No optimization, historical threshold
search or profitability claim is made in this task.

## Exclusions and implementation readiness

No LLM synthesis, prompts, live calls, refresh logic, dashboard work, schema, portfolio
actions, V0.8B, brokerage, trading, numerical research weights or automatic optimization.
The policy is ready for human review and scoped Step 3B implementation. Operational
Fundamental synthesis remains conditional on prospective provenance capture and
explicit applicability/risk checks; this is not a claim that those changes exist.

## Step 3B implementation

`technical_freshness` now implements the exact table using admitted records and
USMarketCalendar.completed_sessions, excluding the source session. Unknown admission,
time or calendar inputs remain UNKNOWN. Contexts retain age and calendar version.

`fundamental_provenance.py` supplies an immutable, transient sidecar. The existing
`run_stock_research` optionally accepts `integration_run_id` and
`on_fundamental_artifact`; without the callback its return/save behavior is unchanged.
The callback receives the validated same-run output, original evidence/catalog,
retrieval interval and completion time. It runs before optional legacy persistence;
callback failure propagates without retries. No automatic capture/save/refresh or
new network call is added. Explicit research still invokes the existing research APIs;
unit tests mock those boundaries.

Prospective manifest identifiers are `fundamental-single-agent-path-v1` and
`fundamental-multi-agent-path-v1`, describing the current existing analysis paths.
They preserve the actual OpenAI model, specialist names and memory-use flag. Both
paths in this orchestrator supply no portfolio context. The catalog transport is
`fundamental-evidence-path-catalog-v1`. These versions are not attached to legacy
records. Source dates remain observations, with explicit unavailable/unknown event
coverage. Acquisition cutoff is captured, not synthesized from fiscal periods.

A process-local origin capability binds the complete sidecar bytes and prevents
ordinary constructed/replaced objects from self-attesting. It is an application
boundary, not a security guarantee against hostile Python code. Run IDs are supplied
by the future application orchestrator and must be nonempty. To avoid introducing an
unapproved age window, current Fundamental qualification requires both matching run ID
and integration assessment time exactly equal to captured research completion.
Later assessment times remain UNKNOWN, even if the ID is reused. Explicit refresh
means another existing research call producing a new sidecar, never a retimestamp.

`horizon-readiness-v1` records applicability and SYNTHESIS_READY/BLOCKED. Primary
Technical compatibility requires exact SHORT/short-native or SWING/swing-native pairs.
Prospective Fundamental native scope must explicitly be MEDIUM or LONG and exactly
match a Fundamental-primary decision horizon. Free-form legacy scope text is retained
but not interpreted. Secondary roles follow the main design. No scope is rewritten.

Ready cases currently require both sources admitted and operationally current.
Unknown required-secondary risk coverage remains blocking; this does not declare
that secondary research must always exist in all future policies. Missing Technical
features accepted by the source contract are preserved as non-blocking entries, not
counted. Fundamental primary missing-data severity remains blocked where the source
provides only unstructured missing-data prose.

Unstructured Fundamental risks/bear cases or Technical risk notes/conflicting evidence
require an applicability decision not yet provided by the approved policy. They are
therefore conservatively blocked, not parsed for keywords or silently dismissed.
A ready case has no such unresolved claims, supported native scopes and valid run/time
binding. Conditional conflict helpers remain independently testable; assembled contexts
only use verified native scope differences after these gates. This deliberately
limits readiness rather than claiming all current research outputs are synthesis-ready.

No agent exists yet. A future agent must check readiness, use the exact immutable
context and preserve all warnings. Broader handling of unstructured risk relevance,
primary missing-data severity and safe omission of secondary research requires a
separate explicit policy decision. No dashboard or evaluation behavior changed.
