# Stock Market AI Agent

V0.1 — Single Stock Research Agent builds an attributable research report for one ticker. It combines company facts, financial statements, earnings, ticker-relevant news, and earnings-call transcript evidence with deterministic calculations and evidence-grounded OpenAI analysis.

## Architecture and data integrity

Alpha Vantage → retrieval → normalization → deterministic calculations → ResearchSnapshot → evidence package → OpenAI analysis → InvestmentAnalysis → CLI

- **RETRIEVED FACT:** API-provided values and transcript/news evidence. Vendor sentiment annotations remain vendor-supplied annotations.
- **CALCULATED METRIC:** Deterministic Python calculations stored separately from retrieved facts.
- **AI INTERPRETATION:** Model assessments of supplied evidence, with validated evidence paths.
- **FORECAST:** Explicitly labeled forward-looking claims, never treated as facts.

Missing values remain missing and known gaps are carried into the report. Reference validation checks that paths exist; it does not prove the correctness of an interpretation. Recommendations are research/decision-support output, not guaranteed predictions. Confidence is an AI assessment, not an expected-return probability. No automatic trading exists.

## Setup and usage

Use Python 3.12. For a new checkout, create a virtual environment and install dependencies:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Reuse the existing `.venv` when already configured. `requirements.txt` pins the direct OpenAI SDK dependency; its transitive dependencies are resolved by pip.

Configure these environment variables privately, optionally in the Git-ignored project-root `.env`:

- `ALPHA_VANTAGE_API_KEY`
- `OPENAI_API_KEY`

Python does not automatically load `.env`. In a shell without command tracing, load your trusted local file and run:

```sh
set +x
set -a
source .env
set +a
.venv/bin/python src/main.py AAPL
```

Never commit credentials. The CLI prints assessments, typed statements, evidence references, risks, invalidation conditions, and missing data; it does not dump the raw transcript.

## Sources and request budget

Alpha Vantage supplies financial and news evidence. OpenAI supplies structured analysis using the centralized model configuration in `src/openai_client.py`.

A complete run requests each endpoint at most once, in this order:

1. `OVERVIEW`
2. `GLOBAL_QUOTE`
3. `INCOME_STATEMENT`
4. `BALANCE_SHEET`
5. `CASH_FLOW`
6. `EARNINGS`
7. `NEWS_SENTIMENT`
8. `EARNINGS_CALL_TRANSCRIPT`

The transcript request is skipped if no usable earnings date exists. The pipeline maps the latest usable earnings date's month to Q1–Q4; this calendar-month convention may differ from a company's fiscal-quarter labels. Successful complete runs then make one OpenAI analysis request. No automatic request retries are configured.

Quote data are the **latest available quote**, not assumed real-time. Alpha Vantage API request limits or access restrictions can prevent a complete run. Critical retrieval failures stop before analysis; missing optional evidence is reported where supported. The first live integrated attempt stopped at `GLOBAL_QUOTE`, after two Alpha Vantage requests and before any OpenAI request.

## Verification and scope

Run deterministic and mocked tests before live integration testing, using `.venv/bin/python`. Stabilization checks cover imports/syntax, ticker normalization, quarter selection, evidence separation, missing data, evidence-reference and analysis validation, CLI formatting, critical failures, and per-run request counts. The audit runs locally with network connections blocked; live tests are separate and explicitly authorized.

V0.1 has no portfolio awareness, automatic trading, backtesting, database, UI framework, technical indicators, or multi-agent system.
