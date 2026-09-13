# Stock Market AI Agent

**V0.1 — Single Stock Research Agent** is an AI-powered command-line research tool for one ticker. It organizes external financial evidence, calculates reproducible metrics, and produces an attributable investment research report.

## Scope and architecture

V0.1 retrieves company overview, latest available market quote, annual income statements, balance sheets, cash flow, quarterly earnings, ticker-relevant news, and an earnings-call transcript when available. Historical management guidance may inform analysis when present in the transcript; it is not automatically current guidance.

Ticker → Alpha Vantage retrieval → normalization → deterministic calculations → ResearchSnapshot → evidence package/catalog → OpenAI analysis → validated InvestmentAnalysis → CLI

| Information category | Responsibility |
| --- | --- |
| Retrieved facts | Alpha Vantage values, news and transcript evidence; supplied sentiment is a vendor annotation. |
| Calculated metrics | Python growth rates, margins, cash-flow and balance-sheet ratios, and earnings summaries. |
| AI interpretations | Evidence-based assessments, bull/bear reasoning and risks. |
| Forecasts | Separate scenario and thesis-invalidation structures, not established facts. |

Python owns retrieval, normalization, calculations, missing-data tracking, evidence IDs/provenance, the material-evidence checklist, and structural validation. OpenAI owns fundamental, valuation and earnings assessments, bull/bear reasoning, risks, scenarios, thesis invalidation, recommendation and confidence.

Deterministic IDs map to exact original evidence paths and values. Generated statements must cite supplied IDs. The schema requires one named review per available material checklist item, containing an observation and thesis relevance. Python rejects missing/extra review keys, invalid references and invalid recommendation/confidence values. It does not repair model output.

Validation establishes structure and provenance, **not factual or analytical correctness**. Human review remains necessary.

## Setup and usage

Use Python 3.12 and run commands from the repository root. For a new checkout:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Reuse an existing configured environment. Direct third-party runtime dependencies are the official OpenAI SDK, Streamlit and exchange_calendars, pinned in `requirements.txt`; pip resolves their required dependencies. Financial HTTP requests use the standard library; calendar calculations run offline.

Configure these environment variables privately:

- `ALPHA_VANTAGE_API_KEY`
- `OPENAI_API_KEY`

Never commit credentials. The project-root `.env` is Git-ignored. The CLI uses process environment variables; the dashboard loads supported credentials through its bootstrap helper. If using a trusted local `.env`, load it without shell tracing:

```sh
set +x
set -a
source .env
set +a
.venv/bin/python src/main.py AAPL
```

A run sends the retrieved research evidence, including available transcript content, to OpenAI. Provider access and usage charges apply. No credentials belong in report inputs.

The current centralized configuration in `src/openai_client.py` uses **gpt-5.6-terra**, default reasoning behavior, a **120-second SDK request timeout**, and no retries.

## Report and failure behavior

The CLI prints ticker, recommendation, confidence, fundamental/valuation/earnings assessments, bull/bear cases, supporting evidence, risks, scenarios, thesis-invalidation conditions, material evidence reviews, missing data and reasoning summary. Interpretation/forecast labels come from Python types. Statements display evidence IDs; the full transcript and catalog are not dumped.

Recommendations are Buy, Accumulate, Hold, Trim or Avoid. Confidence is an AI assessment of evidential support on a 0–100 scale, not a probability of price appreciation.

Each dataset is attempted at most once per run, in this order:

| Endpoint | Failure policy |
| --- | --- |
| OVERVIEW | Critical; unusable company identity also stops the run |
| GLOBAL_QUOTE | Non-critical |
| INCOME_STATEMENT | Critical |
| BALANCE_SHEET | Critical |
| CASH_FLOW | Critical |
| EARNINGS | Critical |
| NEWS_SENTIMENT | Non-critical |
| EARNINGS_CALL_TRANSCRIPT | Non-critical; skipped without a usable earnings date |

Critical retrieval errors stop before analysis. Non-critical retrieval errors are logged safely and become unavailable evidence with deterministic missing-data entries. Missing individual values remain missing. Analysis/API/validation failures stop without fabricating a recommendation.

Alpha Vantage requests are paced at a minimum **1.0-second interval** within the process. This does not enforce daily quotas. A complete standalone V0.1 run uses at most eight Alpha Vantage requests and one OpenAI analysis request. There are no automatic retries.

## Tests

Run the offline standard-library unittest suite:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests require no keys, do not load `.env`, block network connections and mock provider boundaries. They cover financial calculations, missing/zero inputs, period matching, ID provenance, exact material-review keys, recommendation/confidence validation and pipeline graceful degradation. Live integration and substantive report audits are separate, explicitly authorized activities.

## V0.1 acceptance result

The Step 54 single live AAPL acceptance run completed eight Alpha Vantage requests and one OpenAI request. It passed pipeline validation, material-evidence review, negative FCF treatment, balance-sheet treatment, factual precision, temporal attribution, forecast separation, balanced reasoning, and recommendation/confidence coherence.

Result: **Hold, confidence 63/100**. Acceptance status: **PASS WITH MINOR ISSUES**.

This is **one acceptance run**, not evidence of investment accuracy, repeatability across all inputs, or market-beating performance.

## Limitations and boundaries

- Quotes are the **latest available quote**, not assumed real-time. Trading date differs from retrieval time.
- Financial statements, earnings, news and transcript commentary can cover different periods. Historical guidance is not automatically current.
- Transcript segments have no dedicated date/quarter field; temporal context depends on supplied text. Request quarter selection maps the latest usable earnings date's calendar month to Q1–Q4, which may differ from company fiscal labels.
- Provider limits, entitlements, missing data, network errors and model output limits can prevent completion.
- Comparative valuation context is not supplied. Exact citations and complete reviews do not prove semantic support; wording, inference, timing and confidence can still require review.
- Available normalized transcript content is included in the analysis input; long evidence can increase cost and latency.
- Setup pins the direct SDK version, not an entire transitive dependency lockfile.

V0.1 intentionally excludes portfolio awareness, automated trading, backtesting, technical indicators, databases, UI frameworks and multi-agent systems. Future work is deferred: broader offline evaluations and separately scoped improvements based on observed limitations.

This project provides research and decision support, not personalized investment advice or guaranteed predictions. It does not execute trades.

## V0.2 portfolio CLI

Standalone research remains `.venv/bin/python src/main.py AAPL`.
For portfolio-aware research, use:

```sh
.venv/bin/python src/main.py AAPL --portfolio "AAPL:10:150,MSFT:5:300" --cash 5000
```

Holdings use comma-separated `TICKER:SHARES:AVERAGE_COST`; whitespace is accepted,
duplicate tickers and invalid or negative quantities are rejected. Cash defaults to
0; use `--portfolio "" --cash 5000` for cash-only input. The target need not be owned.
Portfolio mode adds the portfolio assessment, ownership, weights and policy notes.
No portfolios are saved. Stock research runs first; its target quote is reused for portfolio pricing,
including an unavailable price without retry. Other holdings are quoted once.
Existing pacing applies. V0.1 scope statements above
refer to standalone mode; V0.2 adds portfolio context without trading or persistence.

Python calculates position value, cost basis, unrealized gain/loss and decimal returns,
portfolio totals and weights, largest-position weight, top-three weight, HHI and effective
position count. Cash is included in the weight denominator but is not a stock position
in HHI; consequently effective position count can exceed the actual number of holdings.
Zero-share entries are retained. Any missing position price makes aggregate valuation,
weights and concentration unavailable; no partial valuation is treated as complete.

The deterministic policy defaults flag single-position weights above 25%, top-three
weight above 60%, and cash weight below 5%. Exact boundaries are not flagged. These
are configurable policy comparisons, not universal risk judgments or automatic actions.
Undefined inputs remain unknown; an empty portfolio with positive cash is supported.

OpenAI receives the separate deterministic portfolio context, including the target's
ownership, cost/gain context, allocation and policy flags. It explains stock attractiveness
versus portfolio suitability in `portfolio_assessment`; cost basis is not intrinsic value.
Stock citations and material reviews retain their existing validation. Portfolio prose
and policy consistency still require human review; structural checks do not prove them.
Portfolio context is sent to OpenAI along with stock research evidence.

A complete V0.2 run adds one quote request per non-target holding to the standalone
request budget, with exactly one analysis request. Quotes for different holdings may
cover different market dates; portfolio models do not retain quote dates or reconcile
currencies, so valuation assumes comparable currency units. V0.2 adds no broker access,
orders, portfolio persistence, optimization, backtesting, dashboards or price prediction.
The offline suite covers input parsing, valuation, concentration, policy boundaries,
quote reuse/degradation, CLI routing and mocked portfolio-aware analysis.

## V0.3 — Decision History & Memory

SQLite stores append-only `DecisionRecord` rows describing decision-time beliefs and
separate `DecisionOutcome` rows for later observations. Duplicate decision IDs and
outcome decision/horizon pairs are rejected; foreign keys prevent orphan outcomes.
Outcome returns use supplied prices only, are decimal and unannualized, and remain
unknown for missing prices or zero starting prices. No quality scoring is performed.

Existing standalone and portfolio commands remain unchanged without history flags.
Explicitly save a validated decision with:

```sh
.venv/bin/python src/main.py AAPL --db decisions.db --save-decision --horizon "12 months"
```

Save mode may initialize a database and uses a centralized UTC timestamp. Failed
analysis is never saved. Inspect an existing database without writes or provider calls:

```sh
.venv/bin/python -m src.main history AAPL --db decisions.db --limit 5
```

Opt into historical context for new research without saving another decision:

```sh
.venv/bin/python src/main.py AAPL --db decisions.db --use-memory --memory-limit 5
```

Memory requires an existing database. Add `--save-decision` to both read and save;
retrieval precedes analysis and saving, preventing a decision from seeing itself.
These options also work with `--portfolio`. `--memory-limit` requires `--use-memory`,
defaults to five, and accepts zero but not negative values. `--horizon` requires saving.
A database path alone enables neither reads nor writes. Memory-only access is read-only.

Memory contains prior recommendations/confidence, reasoning, risks, scenarios,
invalidation conditions, missing data and separate outcomes. It excludes full evidence
catalogs, transcripts and material reviews; old evidence IDs are omitted from AI memory
input to prevent collisions. Current verified evidence remains authoritative: memory
cannot fill missing current facts or satisfy current material-review requirements.
Historical claims must be attributed, and chronology must follow supplied source periods,
not retrieval time. No automatic evaluation, adaptation, outcome scheduling, benchmark
retrieval, embeddings or multi-agent functionality exists.

Limitations: API callers must use consistent sortable timestamps (store ordering is
lexical); timestamps and evaluation horizons are not semantically interpreted. No
historical as-of cutoff is enforced for caller-supplied outcomes. Historical evidence IDs
are stored without a full evidence archive and cannot independently reconstruct original
provenance. SQLite files contain sensitive research/portfolio context in plaintext;
keep them private and out of Git. Prompt boundaries and structural validation do not
prove semantic correctness; human review remains necessary. The Step 10B live recheck
validated with one prior decision, no additional saved decision, zero outcomes, and Hold
at 62/100; this single run is not evidence of general investment accuracy.

## V0.5 dashboard

Install the pinned dependencies with `.venv/bin/python -m pip install -r requirements.txt`.
From the repository root, launch:

```sh
.venv/bin/python -m streamlit run dashboard.py
```

The sidebar provides six workspaces:

- **Home:** compact overview of existing session results and explicitly selected history.
- **Research:** explicit live standalone multi-agent company analysis. Results remain in session state; navigation does not rerun research.
- **Portfolio:** explicit loading and inspection through the V0.2 portfolio backend, including deterministic risk flags.
- **Agent Room:** inspection of ordered specialist outputs and final synthesis from the same Research run; no extra AI calls.
- **Decision History:** read-only preserved decisions and separately attached outcomes from an explicit local database path and ticker.
- **Performance:** descriptive summaries of stored outcomes for the selected ticker, with sample counts and missing benchmark values preserved. Later `DecisionOutcome` observations are required; none are created automatically.

Research does not automatically save decisions or retrieve historical memory. After
reviewing a result, use **Save Decision** and choose a **Decision database path** to
persist it through V0.3. The save may initialize a local SQLite file; read-only pages
never create one. Database files (`*.db`, `*.sqlite`, `*.sqlite3`) and SQLite sidecars
are gitignored. Historical evidence catalogs, reference prices and original context
snapshots are not reconstructed from current data.

The dashboard loads supported credentials from the project-root local `.env`, preserving
existing environment values. Browsing does not require provider calls; explicit live
Research and portfolio-price loading require their configured credentials. There is
no live trading, automatic outcome capture, strategy adaptation or performance guarantee.
UI tests use Streamlit AppTest with mocked providers and temporary databases.

For a detailed architecture and project-status review through V0.5, see the [V0.5 checkpoint](docs/V0_5_CHECKPOINT.md).


## V0.6 — Evaluation Infrastructure: COMPLETE

Explicit methodology/horizon enrollment, offline XNYS targets, Alpha Vantage adjusted-close
observations, atomic persistence and deterministic provider-adjusted returns are implemented.
Decision History offers explicit enrollment/eligible collection; Performance separates
V0.6 cohorts from legacy outcomes. No automatic collection or trading is introduced.

Legacy/current dashboard saves lack verified analysis-completion metadata: enrolling
those records remains unresolved. Collection requires a supported enrollment with
trustworthy timing provenance; the dashboard does not guess or backfill it.
See the [V0.6 checkpoint](docs/V0_6_CHECKPOINT.md) for architecture, testing and limitations.

### Roadmap

- V0.1 Single Stock Research — COMPLETE
- V0.2 Portfolio Awareness — COMPLETE
- V0.3 Decision History & Memory — COMPLETE
- V0.4 Multi-Agent System — COMPLETE
- V0.5 Interface — COMPLETE
- V0.6 Evaluation Infrastructure — COMPLETE
- V0.7 Technical & Short-Term Research — implementation COMPLETE; final integration/checkpoint pending
- V0.7A Market Data Foundation — COMPLETE
- V0.7B Deterministic Technical Features — COMPLETE
- V0.7C Technical Snapshot & Evidence Catalog — COMPLETE
- V0.7D Technical Analyst & Short-Term Signal Contract — COMPLETE
- V0.7E Technical Signal Persistence — COMPLETE
- V0.7F Technical Signal Evaluation Integration — COMPLETE
- V0.7G Technical Research Dashboard Integration — COMPLETE
- Next: V0.7 final integration/checkpoint

Paper trading and execution remain later work. No backtested alpha or market-beating
performance is claimed.


V0.7A adds validated raw daily OHLCV, explicit as-of/completed-session filtering,
provenance and minimum-history checks. It does not add indicators or signals, and a
current provider response does not establish historical publication vintages.
See the [market-data foundation](docs/V0_7_MARKET_DATA_FOUNDATION.md).

V0.7B adds versioned deterministic SMA, RSI, MACD, ATR, momentum and volume features
with per-feature availability and source provenance. No technical signals or LLM
interpretation are added. See [technical features](docs/V0_7_TECHNICAL_FEATURES.md).

V0.7C packages matching raw market data and features into a bounded, versioned technical
evidence catalog with stable local IDs and explicit missing values. No Technical Analyst
or signals are implemented. See [technical evidence](docs/V0_7_TECHNICAL_EVIDENCE.md).

V0.7D adds an explicit evidence-only Technical Analyst through the existing OpenAI client.
Its cited BULLISH/NEUTRAL/BEARISH research signals have one declared horizon; they are
not trades; explicit endpoint evaluation is available through V0.7F. See [technical analyst](docs/V0_7_TECHNICAL_ANALYST.md).

V0.7E adds explicit immutable SQLite signal records with the compact historical evidence packet.
No automatic save or evaluation occurs. See [technical signal persistence](docs/V0_7_TECHNICAL_SIGNAL_PERSISTENCE.md).

V0.7F links explicitly enrolled technical signals to shared calendar/adjusted-price evaluation.
Predeclared 5/20-session checkpoints, VOO comparison, and directional summaries remain
separate from trades; the Technical Research page exposes this explicit workflow. See [technical evaluation](docs/V0_7_TECHNICAL_EVALUATION.md).

V0.7G adds **Technical Research** to the dashboard: explicit research, same-run features/evidence,
explicit signal save, preserved history, prospective enrollment and later observation collection.
No charts or trading controls are added. See [technical dashboard](docs/V0_7_TECHNICAL_DASHBOARD.md).
