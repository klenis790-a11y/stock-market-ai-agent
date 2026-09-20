# V0.8A Step 5 — Combined backend research

> Current release status: active generation is `technical-analyst-v2` and
> `horizon-synthesis-v2` under `evidence-first-assembly-v1`. Historical v1
> consumption remains supported. Earlier step-specific status statements below
> are historical. G3 validated provider acceptance and one-shot compliance for one
> controlled NVDA/MEDIUM execution; it did not validate investment accuracy or
> long-term reliability. No retries/fallback/repair or semantic-entailment guarantee.
> Research-only V0.8A is ready for separately authorized release publication;
> portfolio-aware decision context remains future V0.8B work. See the
> [release checkpoint](V0_8A_RELEASE_CHECKPOINT.md).


`horizon_pipeline.run_horizon_research` accepts ticker, explicit decision horizon,
explicit Fundamental native scope (MEDIUM or LONG), Technical as-of and explicit
XNYS market confirmation. It returns frozen `CombinedResearchResult`, containing
the existing immutable `IntegratedResearchView` and selection/sequencing versions.
Original research and evidence are retained through the view's validated context.
No competing synthesis contract is introduced.

## Ownership and order

The authoritative `select_technical_horizon` supplies the native scope under
`technical-horizon-selection-v1`. `combined-research-sequencing-v1` requires
Technical then Fundamental. Unsupported runtime policy versions fail before IO.
Technical orchestration is shared through `src.technical_pipeline`; the dashboard
adapter calls the backend, and the backend does not import dashboard code.
Its retrieval/features/evidence/analyst sequence is not copied. The existing
`run_stock_research` then runs once with persistence disabled and a prospective
sidecar callback. Default existing single-agent Fundamental behavior is preserved.
Active v2 generation uses evidence-first drafts and deterministic assembly; indicator
calculations and approved public semantic safeguards remain unchanged.

Execution order does not change authority. MEDIUM/LONG stay Fundamental-primary;
the selected SWING Technical scope remains 1–4 week timing/context. Fundamental
native scope is separately required rather than inferred from the Technical mapping.
An incompatible Fundamental primary scope is blocked by the integration policy.

## Time and provenance

A new run identity is passed unchanged to the Fundamental callback and builder.
Technical output is wrapped using the existing record factory with actual current
completion/availability time **in memory only**; no store is instantiated. This
adds an availability envelope, not a fabricated historical generation timestamp.
Technical market as-of, retrieval time and latest session are unchanged.
Fundamental's verified sidecar supplies the exact integration timestamp. No common
source timestamp is invented. The builder evaluates native-horizon freshness there.

`require_synthesis_ready` immediately precedes synthesis and its recomputed context
is used. The synthesis entry point independently validates again. Readiness labels
and empty reasons alone cannot authorize a call. Sources and derived policies are
not edited to pass. Selection and sequencing versions reside on the combined result;
the unchanged context retains its existing source and readiness policy versions.

## Failures and boundaries

`HorizonPipelineError.stage` distinguishes INPUT, TECHNICAL_RESEARCH,
FUNDAMENTAL_RESEARCH, INTEGRATION, READINESS and HORIZON_SYNTHESIS. Readiness reasons
are retained as an immutable tuple. Messages contain fixed stage text, no provider
body or model output. Other exceptions remain classified by stage without copying
potentially sensitive details. Missing/malformed sidecars fail integration.

Each failure stops downstream work. No automatic retry, refresh, fallback,
specialist rerun, persistence, evaluation enrollment, portfolio context or trading
behavior is introduced. A Technical artifact that becomes stale while Fundamental
runs remains stale and blocks according to existing policy.

## Validation and limitations

Mocked tests exercise all four horizons, the actual synthesis validator with mocked
OpenAI output, source preservation, order/counts, failure stages, forged context
rejection and zero database/network access. Existing calendar, temporal/provenance
and synthesis regressions remain authoritative.

All four combined horizon paths have offline regression coverage. G3 also completed
one controlled live NVDA/MEDIUM v2 execution. This proves execution and compliance
for that attempt, not investment quality or long-term reliability. Full natural-language
entailment remains outside validation. Combined output is transient.

## Step 6 review update

Technical orchestration now lives in `src/technical_pipeline.py`, shared directly by
the horizon pipeline and the dashboard adapter. The adapter preserves its sanitized
UI error contract. Earlier dependency and risk-block descriptions above record Step 5;
`risk-applicability-v1` supersedes existence-only risk blocking. See the
[release checkpoint](V0_8A_RELEASE_CHECKPOINT.md) for historical live failures and
the final review and successful G3 validation record. No further live run is authorized.
