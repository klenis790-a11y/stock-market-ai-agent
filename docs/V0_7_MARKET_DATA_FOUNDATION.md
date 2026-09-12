# V0.7A — Market Data Foundation

## Objective

Technical indicators need reproducible, validated historical bars before they can be
trusted. V0.7A constructs immutable daily OHLCV datasets and enforces calendar completion
at an explicit as-of time. It introduces no indicators, signals or AI interpretation.

## Supported Scope

Daily (`1d`) US-listed equities/ETFs explicitly confirmed compatible with XNYS; Alpha
Vantage is the only implemented provider. Callers must supply `US_EQUITY_ETF_XNYS` scope.
Ticker syntax does not prove exchange membership. Symbol normalization follows the
existing nonempty, strip, uppercase convention without global symbol mapping.

The existing `exchange_calendars==4.13.2` adapter supplies regular sessions offline,
with fixed 1990–2050 coverage. No intraday, extended-hours evaluation or new dependency.

## Normalized OHLCV Contract

`MarketBar` is frozen: symbol, session date, open, high, low, close and volume.
Prices use finite positive floats consistent with existing numeric models; volume is
an exact nonnegative Python integer. Parsing uses Decimal to reject fractional or
non-finite volumes without losing integer precision. Zero volume is allowed; missing
volume is not zero. Float prices are not intended for exact monetary settlement.

`HistoricalOHLCV` contains a tuple of chronologically ordered bars, normalized symbol,
UTC as-of/retrieval times, timeframe, provider/function, RAW adjustment mode, calendar
name/version/timezone, normalization version and an explicit availability limitation.
First/last included dates are derived. Expected latest completed session and missing
sessions expose stale/missing history. It contains no raw JSON, credentials or mutable
provider aliases. Models do not perform retrieval; the builder owns calendar validation.

## Point-in-Time Rule

`build_historical_ohlcv(symbol, payload, as_of, retrieved_at=..., market=...)` is pure.
It never reads a clock. `retrieve_historical_ohlcv` is the separate explicit IO operation;
it obtains one response and records the actual UTC retrieval timestamp.

At Monday **10:17 AM New York time**, the eventual Monday daily bar is discarded even
if present in the supplied response. Inclusion requires actual regular-session close
at or before both `as_of` and `retrieved_at`. Equality at close counts as completed;
this is a calendar boundary, not a guarantee of instant provider publication.

**Important limit:** a current historical response cannot prove what the provider
published at a past instant or whether it subsequently revised a bar. The dataset's
`availability_basis` explicitly marks historical publication/vintage as unverified.
Completed-bar filtering prevents unfinished-bar leakage; it does not certify archived
point-in-time vintages. Same response vintage, timestamps and methodology produce the
same dataset. Reproduction after a provider revision requires retaining the original
normalized dataset externally; automatic persistence is outside this step.

## Calendar Handling

XNYS determines weekends, holidays (including observed holidays), early closes and DST.
A half-day bar is excluded at 12:30 PM when the actual close is 1 PM; it is eligible at
that close. No fixed UTC offset, weekday approximation or hard-coded 4 PM rule is used.
All provider date keys must be canonical YYYY-MM-DD and actual XNYS sessions, including
rows later filtered as unfinished. Out-of-range dates fail closed. Future emergency
closures remain subject to calendar-version limitations.

Missing sessions between the first retained bar and the latest expected completed
session are exposed, never synthesized. Listing inception and data before the first
returned bar cannot be established from this response alone. An empty supplied series
is an error; a nonempty series containing no completed bars yields an empty dataset
whose minimum-history check fails.

## Corporate-Action / Adjustment Policy

**RAW as-traded daily OHLCV** is the only supported mode. The selected endpoint is
`TIME_SERIES_DAILY`, `outputsize=full`; fields are `1. open`, `2. high`, `3. low`,
`4. close`, `5. volume`. Full history avoids the compact latest-100-row limit and uses
one request per explicit operation. This requires appropriate provider entitlement.
[Alpha Vantage daily API documentation](https://www.alphavantage.co/documentation/#daily)

No adjusted-close field enters these bars. A separate adjusted close does not create
adjusted open/high/low values. Split/dividend events are not supplied by this selected
endpoint and are not fabricated. Raw bars can have corporate-action discontinuities;
future feature work must address their effect explicitly. V0.7A does not construct
adjusted series, infer splits, or claim total/investor returns.

## Validation

Each retained bar requires all OHLCV fields. Prices must be finite and strictly positive;
high must cover open/close/low and low must not exceed open/close/high. Volume must be
finite, integral and nonnegative. No repair, coercion of missing values or rounding of
fractional volume occurs. Uncompleted rows are date-validated but their provisional
OHLCV values are excluded before numeric validation.

Unexpected provider shapes, missing identity/timezone metadata, informational/error
payloads and non-session dates fail with errors. Provider metadata must match the
requested normalized symbol and US/Eastern or America/New_York timezone. Existing
HTTP error handling and pacing are reused without retries. V0.7 raw requests opt into
strict JSON decoding so duplicate date keys cannot silently disappear in a dict;
normalized duplicate dates and noncanonical aliases are also rejected. Existing client
callers retain their previous decoding behavior.

`require_minimum_history(dataset, n)` requires a positive integer count, at least n
completed bars and no missing sessions in that trailing window through the expected
latest close. 199 bars cannot satisfy 200. It never shortens a lookback or substitutes
calendar days. It validates sufficiency, not an indicator or corporate-action policy.

## Provenance

Provider/function, symbol, timeframe, RAW mode, XNYS name/version, exchange timezone,
requested UTC as-of, actual UTC retrieval time and first/last included sessions travel
with the dataset. Methodology `daily-ohlcv-normalization-v1` identifies strict daily
parsing, raw prices, chronological ordering and completed-session filtering. It is a
project methodology identifier, not a provider software version. No API keys are stored.

## Data Integrity

- **RETRIEVED FACTS:** vendor raw OHLCV, under the response's retrieval vintage.
- **CALCULATED/TRANSFORMED:** numeric normalization, ordering, session validation,
  completed-bar filtering and missing-session detection.
- **AI INTERPRETATION:** none. No prompts, recommendations or OpenAI calls.

## V0.6 Separation

V0.6 continues using `TIME_SERIES_DAILY_ADJUSTED` and `5. adjusted close` under
`alpha-vantage-adjusted-close-v1` for provider-adjusted evaluation returns. V0.7A's raw
policy neither replaces that policy nor rewrites any enrollment/observation. Calendar
helpers are additive; existing reference-target resolution is unchanged. No database
schema, dashboard or legacy model changes were needed.

## Verification

359 offline tests pass (12 added for V0.7A). Fixtures cover calendar boundaries,
unfinished daily bars, UTC/naive times, malformed OHLCV, duplicates, provider errors,
ordering/reproducibility, immutability, volume precision, missing sessions and 200/199
history sufficiency. Network connections are blocked in the new test class. V0.1–V0.6
regressions pass.

One authorized live validation on 2026-09-12 used AAPL, one full raw daily request,
no retry/persistence/OpenAI. It normalized 6,756 bars from 1999-11-01 to 2026-09-11,
with no missing sessions in that returned window. This validates that response, not
universal provider quality or historical availability at prior as-of timestamps.

## Limitations

No intraday, indicators, signals, charts, persistence, broker integration or automatic
refresh. Historical provider revisions/publication latency are not independently
verified. Corporate-action metadata is unavailable in this mode. XNYS compatibility
must be supplied explicitly; global calendars and symbol histories are unsupported.
No API request is made to fill gaps or repair insufficient history.

## Next Step

**V0.7B — Deterministic Technical Features** is next. It must consume normalized data,
respect history sufficiency and RAW corporate-action limitations, and remain separate
from future signal interpretation. No V0.7B functionality is implemented here.
