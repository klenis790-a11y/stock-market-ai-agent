"""Append-only SQLite storage with separate decision-time and later-outcome tables."""
from contextlib import closing
from dataclasses import asdict
import json
import sqlite3
from pathlib import Path

from src.models import DecisionOutcome, DecisionRecord, InterpretationStatement, ForecastStatement, MaterialEvidenceReview


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

    def __init__(self, database_path: str, *, read_only: bool = False):
        self.database_path = database_path
        self.read_only = read_only

    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            connection = sqlite3.connect(Path(self.database_path).resolve().as_uri() + "?mode=ro", uri=True)
        else:
            connection = sqlite3.connect(self.database_path)
        connection.execute('PRAGMA foreign_keys = ON')
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
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

            connection.execute('''CREATE TABLE IF NOT EXISTS decision_outcomes (
                decision_id TEXT NOT NULL REFERENCES decisions(decision_id),
                evaluation_timestamp TEXT NOT NULL,
                evaluation_horizon TEXT NOT NULL,
                stock_start_price REAL,
                stock_end_price REAL,
                stock_return REAL,
                benchmark_ticker TEXT,
                benchmark_start_price REAL,
                benchmark_end_price REAL,
                benchmark_return REAL,
                excess_return REAL,
                PRIMARY KEY (decision_id, evaluation_horizon)
            )''')

    def save_decision(self, record: DecisionRecord) -> None:
        values = _serialize(record)
        with closing(self._connect()) as connection, connection:
            # Plain INSERT deliberately rejects duplicate primary keys (IntegrityError).
            connection.execute('''INSERT INTO decisions (
                decision_id, ticker, decision_timestamp, recommendation, confidence_score,
                investment_horizon, reasoning_summary, fundamental_assessment,
                valuation_assessment, earnings_assessment, portfolio_assessment,
                bull_case, bear_case, supporting_evidence, major_risks,
                thesis_invalidation_conditions, scenarios, missing_data, material_evidence_review
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', values)

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute('SELECT * FROM decisions WHERE decision_id = ?', (decision_id,)).fetchone()
            return _deserialize(row) if row is not None else None

    def get_decisions_for_ticker(self, ticker: str) -> list[DecisionRecord]:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError('A non-empty ticker is required.')
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute('''SELECT * FROM decisions WHERE ticker = ?
                ORDER BY decision_timestamp DESC, decision_id ASC''', (ticker.strip().upper(),)).fetchall()
            return [_deserialize(row) for row in rows]

    def save_outcome(self, outcome: DecisionOutcome) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute('''INSERT INTO decision_outcomes (
                decision_id, evaluation_timestamp, evaluation_horizon,
                stock_start_price, stock_end_price, stock_return, benchmark_ticker,
                benchmark_start_price, benchmark_end_price, benchmark_return, excess_return
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                outcome.decision_id, outcome.evaluation_timestamp, outcome.evaluation_horizon,
                outcome.stock_start_price, outcome.stock_end_price, outcome.stock_return,
                outcome.benchmark_ticker, outcome.benchmark_start_price, outcome.benchmark_end_price,
                outcome.benchmark_return, outcome.excess_return,
            ))

    def get_outcome(self, decision_id: str, evaluation_horizon: str) -> DecisionOutcome | None:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute('''SELECT * FROM decision_outcomes
                WHERE decision_id = ? AND evaluation_horizon = ?''',
                (decision_id, evaluation_horizon)).fetchone()
            return DecisionOutcome(**dict(row)) if row is not None else None

    def get_outcomes_for_decision(self, decision_id: str) -> list[DecisionOutcome]:
        """Lexical timestamp ascending, then horizon text for deterministic ties."""
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute('''SELECT * FROM decision_outcomes WHERE decision_id = ?
                ORDER BY evaluation_timestamp ASC, evaluation_horizon ASC''', (decision_id,)).fetchall()
            return [DecisionOutcome(**dict(row)) for row in rows]
