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

Reuse an existing configured environment. The only direct third-party runtime dependency is the official OpenAI SDK, pinned in `requirements.txt`; pip resolves its required dependencies. Financial requests and tests use the standard library.

Configure these environment variables privately:

- `ALPHA_VANTAGE_API_KEY`
- `OPENAI_API_KEY`

Never commit credentials. The project-root `.env` is Git-ignored and is not automatically loaded by Python. If using a trusted local `.env`, load it without shell tracing:

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

Alpha Vantage requests are paced at a minimum **1.0-second interval** within the process. This does not enforce daily quotas. A complete run uses at most eight Alpha Vantage requests and one OpenAI analysis request. There are no automatic retries.

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
