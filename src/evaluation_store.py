"""Explicit additive evaluation storage. Legacy saving never initializes these tables."""
from contextlib import closing
from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3

from src.decision_store import DecisionStore
from src.evaluation_models import (EvaluationEnrollment, EvaluationObservation,
    EvaluationHorizon, EvaluationMethodology, EvaluationPrice, canonical_json)


def enrollment_from_json(payload):
    data = json.loads(payload)
    data['horizon'] = EvaluationHorizon(**data['horizon'])
    data['methodology'] = EvaluationMethodology(**data['methodology'])
    return EvaluationEnrollment(**data)


def observation_from_json(payload):
    data = json.loads(payload)
    for key in ('stock', 'benchmark'):
        if data[key] is not None:
            data[key] = EvaluationPrice(**data[key])
    return EvaluationObservation(**data)


class EvaluationStore(DecisionStore):
    """Append-only metadata with defensive revalidation at the persistence boundary.

    All dates are supplied; no calendar resolution or prospective certification.
    Reads of a legacy database return empty/None without creating tables.
    """
    def initialize(self):
        if self.read_only:
            raise ValueError('Evaluation initialization requires write mode.')
        super().initialize()
        with closing(self._connect()) as connection, connection:
            connection.execute('BEGIN')
            connection.execute('''CREATE TABLE IF NOT EXISTS evaluation_enrollments (
                enrollment_id TEXT PRIMARY KEY NOT NULL,
                decision_id TEXT NOT NULL REFERENCES decisions(decision_id),
                ticker TEXT NOT NULL,
                enrolled_at TEXT NOT NULL,
                horizon_length INTEGER NOT NULL,
                horizon_unit TEXT NOT NULL,
                methodology_version TEXT NOT NULL,
                methodology_hash TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(decision_id, horizon_length, horizon_unit, methodology_version)
            )''')
            connection.execute('''CREATE TABLE IF NOT EXISTS evaluation_observations (
                observation_id TEXT PRIMARY KEY NOT NULL,
                enrollment_id TEXT NOT NULL REFERENCES evaluation_enrollments(enrollment_id),
                point TEXT NOT NULL,
                effective_at TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                supersedes_id TEXT UNIQUE REFERENCES evaluation_observations(observation_id),
                input_hash TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(enrollment_id, input_hash)
            )''')
            connection.execute('''CREATE UNIQUE INDEX IF NOT EXISTS evaluation_root_point
                ON evaluation_observations(enrollment_id, point) WHERE supersedes_id IS NULL''')

    def save_enrollment(self, enrollment):
        if not isinstance(enrollment, EvaluationEnrollment):
            raise ValueError('EvaluationEnrollment required.')
        payload = canonical_json(asdict(enrollment))
        item = enrollment_from_json(payload)
        with closing(self._connect()) as connection, connection:
            parent = connection.execute('SELECT ticker FROM decisions WHERE decision_id = ?', (item.decision_id,)).fetchone()
            if parent is None:
                raise sqlite3.IntegrityError('Enrollment decision does not exist.')
            if parent[0] != item.ticker:
                raise ValueError('Enrollment ticker does not match decision.')
            conflict = connection.execute('''SELECT 1 FROM evaluation_enrollments
                WHERE methodology_version = ? AND methodology_hash != ?''',
                (item.methodology.version, item.methodology.digest)).fetchone()
            if conflict:
                raise ValueError('Methodology changes require a new version.')
            connection.execute('''INSERT INTO evaluation_enrollments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (item.enrollment_id, item.decision_id, item.ticker, item.enrolled_at,
                 item.horizon.length, item.horizon.unit, item.methodology.version, item.methodology.digest, payload))

    def save_observation(self, observation):
        if not isinstance(observation, EvaluationObservation):
            raise ValueError('EvaluationObservation required.')
        payload = canonical_json(asdict(observation))
        item = observation_from_json(payload)
        with closing(self._connect()) as connection, connection:
            row = connection.execute('SELECT payload FROM evaluation_enrollments WHERE enrollment_id = ?', (item.enrollment_id,)).fetchone()
            if row is None:
                raise sqlite3.IntegrityError('Observation enrollment does not exist.')
            enrollment = enrollment_from_json(row[0])
            if item.recorded_at < enrollment.enrolled_at:
                raise ValueError('Observation recording cannot precede enrollment.')
            for price, symbol in ((item.stock, enrollment.ticker), (item.benchmark, enrollment.methodology.benchmark_symbol)):
                if price is not None and (price.symbol != symbol or price.currency != enrollment.methodology.currency
                        or price.adjustment_policy != enrollment.methodology.adjustment_policy):
                    raise ValueError('Price identity or adjustment basis differs from enrollment.')
            if item.supersedes_id is not None:
                prior = connection.execute('SELECT payload FROM evaluation_observations WHERE observation_id = ?', (item.supersedes_id,)).fetchone()
                if prior is None:
                    raise sqlite3.IntegrityError('Revision predecessor does not exist.')
                prior = observation_from_json(prior[0])
                if (prior.enrollment_id, prior.point, prior.effective_at) != (item.enrollment_id, item.point, item.effective_at) or prior.recorded_at > item.recorded_at:
                    raise ValueError('Revision must preserve enrollment and observation point.')
            inputs = asdict(item)
            for key in ('observation_id', 'recorded_at', 'supersedes_id', 'revision_reason'):
                inputs.pop(key)
            digest = sha256(canonical_json(inputs).encode()).hexdigest()
            connection.execute('INSERT INTO evaluation_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (item.observation_id, item.enrollment_id, item.point, item.effective_at,
                 item.recorded_at, item.supersedes_id, digest, payload))

    def _read(self, table, sql, params, decode):
        with closing(self._connect()) as connection:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                return []
            return [decode(row[0]) for row in connection.execute(sql, params).fetchall()]

    def get_enrollment(self, enrollment_id):
        rows = self._read('evaluation_enrollments', 'SELECT payload FROM evaluation_enrollments WHERE enrollment_id = ?', (enrollment_id,), enrollment_from_json)
        return rows[0] if rows else None

    def get_enrollments_for_decision(self, decision_id):
        return self._read('evaluation_enrollments', 'SELECT payload FROM evaluation_enrollments WHERE decision_id = ? ORDER BY enrolled_at, enrollment_id', (decision_id,), enrollment_from_json)

    def get_enrollments_for_ticker(self, ticker):
        return self._read('evaluation_enrollments', 'SELECT payload FROM evaluation_enrollments WHERE ticker = ? ORDER BY enrolled_at, enrollment_id', (ticker.strip().upper(),), enrollment_from_json)

    def get_observations_for_enrollment(self, enrollment_id):
        return self._read('evaluation_observations', 'SELECT payload FROM evaluation_observations WHERE enrollment_id = ? ORDER BY recorded_at, observation_id', (enrollment_id,), observation_from_json)
