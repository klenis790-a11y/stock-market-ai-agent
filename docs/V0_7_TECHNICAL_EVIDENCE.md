# V0.7C — Technical Snapshot & Evidence Catalog

## Objective

A future Technical Analyst should receive a bounded, attributable evidence packet rather
than raw provider JSON or an entire historical series. V0.7C packages existing facts
and features without recalculating indicators or generating analysis.

## Architecture

HistoricalOHLCV → TechnicalFeatureSnapshot → TechnicalResearchSnapshot →
TechnicalEvidenceCatalog → future Technical Analyst.

`build_technical_research_snapshot(data, features)` validates source compatibility.
`build_technical_evidence_catalog(snapshot)` constructs immutable evidence and shared
provenance. `catalog.to_packet()` exports JSON-compatible data without source bars.
No prompt, provider call, model call, database write or dashboard integration is added.

## Technical Research Snapshot

The frozen research snapshot composes the existing feature snapshot, whose source is
already the immutable HistoricalOHLCV. It does not maintain a second copy of feature
values. Full source-dataset equality is required, including symbol, as-of, latest bar,
bar contents, retrieval timestamp, gaps and provenance. Merely matching a ticker is
insufficient. Approved feature names, units, initialization parameters and methodology
versions are checked; missing, duplicate and unexpected feature names are rejected.
Feature numeric values are validated but not recomputed: upstream calculations remain
the source of truth. Structural validation does not prove correctness of fabricated
feature values supplied by an untrusted caller.

## Evidence Catalog

Version `technical-evidence-v1` defines 23 fixed slots with IDs T001 through T023.
Ordering is explicit, independent of feature tuple/dictionary construction order:

1. PRICE: latest completed close, high, low.
2. TREND: SMA20/50/200; corresponding close-distance percentages; trend structure.
3. MOMENTUM: RSI14; MACD line, signal, histogram; momentum5/20.
4. VOLATILITY: ATR14 and ATR percentage.
5. VOLUME: latest completed volume, average volume20, volume ratio20.
6. DATA_QUALITY: completed-bar count and missing-session count.

Unavailable entries retain their slots. Each item has an ID, category, label, numeric
or categorical value, unit, classification, source path and exact unavailable reason.
IDs are **catalog-local**, not globally unique across companies or dates. Consumers
must carry packet provenance and version with citations. `resolve(id)` rejects IDs
absent from that catalog. This borrows the fundamental catalog's local-reference idea
without altering E-prefixed fundamental evidence or its citation validation.

Numeric values remain numeric. `percent` retains V0.7B values such as 5 for 5%; momentum
uses `decimal_return`, such as 0.05 for 5%. Ratios, price units, shares and RSI's 0–100
scale are preserved. No prose replaces numeric values. Trend ordering strings remain
deterministic classifications, not a final directional signal.

## Evidence Classification

Latest close/high/low/volume are RETRIEVED_FACT. Indicators, ordering and data-quality
counts are CALCULATED_METRIC. There is NO AI_INTERPRETATION and NO FORECAST. No confidence,
price target, expected return or recommendation is generated. A BULLISH_STACK value
continues to describe V0.7B's exact numeric ordering only.

## Point-in-Time Integrity

Packet provenance preserves requested UTC as-of, latest completed session, expected last
session, first included session and actual retrieval timestamp. Stale sessions, changed
as-ofs or different datasets cannot be merged. The layer consumes V0.7A completed bars;
it does not fetch fresh bars, change timestamps, or revise historical source values.

Historical provider publication/vintage remains unverified as explicitly stated in
V0.7A's availability metadata. Calendar completion is not proof of what a provider had
published at a historical instant. Missing-session counts and expected latest session
help expose gaps/staleness; the packet does not invent missing price context.

## Provenance

The shared immutable provenance includes provider, endpoint, RAW adjustment mode,
timeframe, calendar/name/version/timezone, all relevant source times, feature parameters
and availability basis. Methodology layers remain distinct:

- `daily-ohlcv-normalization-v1`: V0.7A source construction.
- `technical-features-v1`: V0.7B calculations and initialization.
- `technical-evidence-v1`: V0.7C fixed evidence selection/order/packaging.

Per-item source paths identify the source field; the catalog carries shared timing and
methodology once. `to_packet()` is the intended bounded export, not recursive serialization
of TechnicalResearchSnapshot (which composes the full source internally). No secrets
or provider response objects are included.

## Missing Data

The exact V0.7B unavailable reason travels with each feature. None is not guessed to mean
insufficient history and never becomes zero. A 50-bar input retains available shorter
features and a missing SMA200 slot. Missing sessions and zero volume denominators retain
their distinct reasons. Empty price history produces NO_COMPLETED_BARS for price/volume
facts, with no fictitious latest session. No optional range calculation was added.

## V0.6 Separation

V0.6 enrollment, observation, provider-adjusted return and Performance contracts are
unchanged. V0.7 technical evidence preserves RAW provenance and never imports V0.6
adjusted-close interpretation. Technical evidence is not an evaluation outcome.

## Verification

Five offline tests added; 372 total tests pass across V0.1–V0.7C. Tests cover source
mismatch/staleness, fixed IDs/category order, reordered features, numeric units, missing
history, bounded JSON export, provenance, immutability, non-finite rejection, empty data
and no recalculation/network behavior. No live Alpha Vantage or OpenAI requests occur.

## Limitations

No Technical Analyst, directional signal, confidence, support/resistance, forecast,
chart, persistence or trading. Raw corporate-action discontinuities and provider-vintage
limitations remain. IDs alone do not authenticate source data or prove semantic support
for a future claim. V0.7D must bind citations to the supplied packet and interpret its
availability/provenance honestly.

## Next Step

V0.7D — Technical Analyst & Short-Term Signal Contract. It is not implemented here.
