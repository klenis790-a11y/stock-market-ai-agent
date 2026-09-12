# V0.7E — Technical Signal Persistence

## Objective
Preserve technical research beliefs before measuring later outcomes. Saving never changes the interpretation or retrieves data.

## Architecture
TechnicalSignal → explicit record preparation → explicit save → TechnicalSignalRecord → future evaluation.

## Historical Integrity
Original beliefs and their evidence stay unchanged. Future outcomes belong in separate structures; this step adds none.

## Persisted Fields
The record preserves the complete structured signal: exact signal vocabulary, horizon, integer confidence, summary, thesis, ordered supporting/conflicting references, cited confirmation/invalidation conditions, risks, missing evidence IDs and acknowledgement, model identifier and methodology provenance. Confidence is not a probability.

## Evidence Auditability
Catalog-local IDs alone cannot reconstruct evidence because source bars and catalogs were not persisted. Each record therefore embeds the compact catalog packet supplied alongside the signal: ordered IDs, labels, numeric values, units, classifications, source paths, unavailable reasons and complete provenance. No raw provider JSON or OHLCV history is saved. Callers must supply the actual catalog used for analysis; matching provenance/version and reference availability are validated, but these checks do not cryptographically authenticate its origin. T001 remains interpretable from the saved packet without current evidence code.

## Timestamp Semantics
Market `requested_as_of`, latest completed session, provider retrieval timestamp, and record `created_at` are separate. Record creation is normalized to UTC with microseconds; source timestamps retain their original aware representation. Current TechnicalSignal has no generation timestamp: save time must not be presented as generation time. No historical timestamp is reconstructed.

## Database Design
`TechnicalSignalStore` reuses the existing SQLite connection conventions. Explicit initialization adds only `technical_signals` using CREATE TABLE IF NOT EXISTS. One row contains indexed identity/symbol/save time, record version and deterministic signal/evidence JSON. A single INSERT commits both packets atomically. Existing decision/evaluation tables are untouched; results are not persisted here.

## Immutability
Frozen record objects hold immutable JSON strings. Accessors return detached historical dictionaries, not current runtime TechnicalSignal objects. There is no technical update API or overwrite operation. This is application append-only storage, not protection against someone directly editing SQLite.

## Duplicate Behavior
Prepare a record once with `create_technical_signal_record`, then reuse it for retries. IDs contain symbol, canonical save timestamp and a UUID suffix unless explicitly supplied. The same ID raises SQLite IntegrityError without overwriting. Preparing a new record intentionally creates a new identity even for identical content; callers must retain the prepared record to distinguish retries from new saves. New separately generated views are permitted.

## Serialization and Versions
`technical-signal-record-v1` identifies storage format, separately from analyst, evidence, feature and market-data methods. JSON preserves list order, values and prose. Reads reject malformed JSON, unknown record versions, unknown signal/horizon, invalid confidence/timestamps and broken references. Nonempty research methodology identifiers are preserved opaquely rather than interpreted using current methods. No analysis, feature calculations or catalog building occurs during save/read.

## Data Integrity
Historical signal and packet preservation records what was supplied at save time. Embedded OHLCV evidence retains RETRIEVED_FACT classification; indicator evidence retains CALCULATED_METRIC classification. AI INTERPRETATION remains the preserved analyst output. No calculations or future outcomes are introduced by persistence.

## V0.6 Separation
Saving creates no DecisionRecord, DecisionOutcome, EvaluationEnrollment or EvaluationObservation. There is no automatic evaluation enrollment.

## Verification
The offline suite includes vocabulary/horizon round trips, evidence fidelity and unavailability, duplicates, detached reads, corrupted records, additive initialization, atomic insertion failure and legacy-table separation. All 384 tests pass (five persistence tests added). Unit tests make no live provider requests. One separate controlled live compatibility check passed with the configured gpt-5.6-terra model using synthetic evidence: valid BULLISH output and validated citations, no Alpha Vantage call and no persistence.

## Limitations
No evaluation, automatic saving, dashboard, trade execution or portfolio synthesis. SQLite itself is not tamper-proof. Exact generation time is unavailable in the current signal contract. Source publication/vintage limitations remain preserved in provenance.

## Next Step
V0.7F — Technical Signal Evaluation Integration. V0.7 remains in progress.
