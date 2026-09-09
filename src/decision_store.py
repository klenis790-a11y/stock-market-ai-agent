"""Append-only SQLite storage of decision-time records, never later outcomes."""
from contextlib import closing
from dataclasses import asdict
import json
import sqlite3

from src.models import DecisionRecord, InterpretationStatement, ForecastStatement, MaterialEvidenceReview


SCALAR_FIELDS = (
    'decision_id', 'ticker', 'decision_timestamp', 'recommendation', 'confidence_score',
    'investment_horizon', 'reasoning_summary', 'fundamental_assessment',
    'valuation_assessment', 'earnings_assessment', 'portfolio_assessment',
)
INTERPRETATION_FIELDS = ('bull_case', 'bear_case', 'supporting_evidence', 'major_risks')
FORECAST_FIELDS = ('thesis_invalidation_conditions', 'scenarios')
JSON_FIELDS = (*INTERPRETATION_FIELDS, *FORECAST_FIELDS, 'missing_data', 'material_evidence_review')


def _serialize(record: DecisionRecord) -> tuple:
    data = asdict(record)
    return tuple(data[name] for name in SCALAR_FIELDS) + tuple(
        json.dumps(data[name], sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        for name in JSON_FIELDS
    )


def _deserialize(row: sqlite3.Row) -> DecisionRecord:
    data = {name: row[name] for name in SCALAR_FIELDS}
    for name in JSON_FIELDS:
        data[name] = json.loads(row[name])
    for name in INTERPRETATION_FIELDS:
        data[name] = [InterpretationStatement(**item) for item in data[name]]
    for name in FORECAST_FIELDS:
        data[name] = [ForecastStatement(**item) for item in data[name]]
    data['material_evidence_review'] = {
        key: MaterialEvidenceReview(**value) for key, value in data['material_evidence_review'].items()
    }
    return DecisionRecord(**data)


class DecisionStore:
    """Explicitly initialized file-backed store; each operation closes its connection.

    Timestamp ordering is lexical: callers must use a consistent, sortable timestamp
    representation for chronological history. Stored timestamps are not reinterpreted.
    """

    def __init__(self, database_path: str):
        self.database_path = database_path

    def initialize(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY NOT NULL,
                ticker TEXT NOT NULL,
                decision_timestamp TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                investment_horizon TEXT,
                reasoning_summary TEXT NOT NULL,
                fundamental_assessment TEXT NOT NULL,
                valuation_assessment TEXT NOT NULL,
                earnings_assessment TEXT NOT NULL,
                portfolio_assessment TEXT,
                bull_case TEXT NOT NULL,
                bear_case TEXT NOT NULL,
                supporting_evidence TEXT NOT NULL,
                major_risks TEXT NOT NULL,
                thesis_invalidation_conditions TEXT NOT NULL,
                scenarios TEXT NOT NULL,
                missing_data TEXT NOT NULL,
                material_evidence_review TEXT NOT NULL
            )''')

    def save_decision(self, record: DecisionRecord) -> None:
        values = _serialize(record)
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            # Plain INSERT deliberately rejects duplicate primary keys (IntegrityError).
            connection.execute('''INSERT INTO decisions (
                decision_id, ticker, decision_timestamp, recommendation, confidence_score,
                investment_horizon, reasoning_summary, fundamental_assessment,
                valuation_assessment, earnings_assessment, portfolio_assessment,
                bull_case, bear_case, supporting_evidence, major_risks,
                thesis_invalidation_conditions, scenarios, missing_data, material_evidence_review
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', values)

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute('SELECT * FROM decisions WHERE decision_id = ?', (decision_id,)).fetchone()
            return _deserialize(row) if row is not None else None

    def get_decisions_for_ticker(self, ticker: str) -> list[DecisionRecord]:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError('A non-empty ticker is required.')
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute('''SELECT * FROM decisions WHERE ticker = ?
                ORDER BY decision_timestamp DESC, decision_id ASC''', (ticker.strip().upper(),)).fetchall()
            return [_deserialize(row) for row in rows]
