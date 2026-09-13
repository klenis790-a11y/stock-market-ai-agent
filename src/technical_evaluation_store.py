"""Additive technical-source linkage. Legacy fundamental foreign keys stay intact."""
from contextlib import closing
from dataclasses import asdict
from datetime import datetime
import json
import sqlite3

from src.evaluation_models import EvaluationHorizon, EvaluationMethodology, canonical_json
from src.evaluation_store import EvaluationStore, observation_from_json
from src.technical_signal_store import TechnicalSignalStore
from src.technical_evaluation import (TechnicalEvaluationEnrollment, prepare_technical_enrollment,
                                      evaluate_technical_signal)


def technical_enrollment_from_json(payload):
    data = json.loads(payload)
    data['horizon'] = EvaluationHorizon(**data['horizon'])
    data['methodology'] = EvaluationMethodology(**data['methodology'])
    return TechnicalEvaluationEnrollment(**data)


class TechnicalEvaluationStore(EvaluationStore):
    """Reuse V0.6 connection and atomic observation-batch machinery, not its IDs.

    Technical source FKs require separate tables. There are no shadow decisions,
    edits, revisions, or calculated-result rows. Reads never initialize schema.
    """
    def initialize(self):
        if self.read_only:
            raise ValueError('Technical evaluation initialization requires write mode.')
        TechnicalSignalStore.initialize(self)
        with closing(self._connect()) as connection, connection:
            connection.execute('BEGIN')
            connection.execute('''CREATE TABLE IF NOT EXISTS technical_evaluation_enrollments (
                enrollment_id TEXT PRIMARY KEY NOT NULL,
                signal_record_id TEXT NOT NULL REFERENCES technical_signals(record_id),
                methodology_version TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(signal_record_id, methodology_version))''')
            connection.execute('''CREATE TABLE IF NOT EXISTS technical_evaluation_observations (
                observation_id TEXT PRIMARY KEY NOT NULL,
                enrollment_id TEXT NOT NULL REFERENCES technical_evaluation_enrollments(enrollment_id),
                point TEXT NOT NULL CHECK(point IN ('reference','endpoint')),
                payload TEXT NOT NULL,
                UNIQUE(enrollment_id, point))''')

    def get_signal_record(self, record_id):
        return TechnicalSignalStore(self.database_path, read_only=True).get_technical_signal(record_id)

    def save_enrollment(self, enrollment):
        if self.read_only:
            raise ValueError('Enrollment requires write mode.')
        item = technical_enrollment_from_json(canonical_json(asdict(enrollment)))
        record = self.get_signal_record(item.signal_record_id)
        if record is None:
            raise ValueError('Technical signal does not exist.')
        expected = prepare_technical_enrollment(record,
            datetime.fromisoformat(item.enrolled_at.replace('Z', '+00:00')), market=item.market)
        if item != expected:
            raise ValueError('Enrollment must match the declared technical policy/source.')
        with closing(self._connect()) as connection, connection:
            connection.execute('INSERT INTO technical_evaluation_enrollments VALUES (?, ?, ?, ?)',
                (item.enrollment_id, item.signal_record_id, item.methodology.version, canonical_json(asdict(item))))

    def get_enrollment(self, enrollment_id):
        rows = self._read('technical_evaluation_enrollments',
            'SELECT payload FROM technical_evaluation_enrollments WHERE enrollment_id = ?',
            (enrollment_id,), technical_enrollment_from_json)
        return rows[0] if rows else None

    def get_enrollments_for_signal(self, record_id):
        return self._read('technical_evaluation_enrollments',
            'SELECT payload FROM technical_evaluation_enrollments WHERE signal_record_id = ? ORDER BY enrollment_id',
            (record_id,), technical_enrollment_from_json)

    def list_enrollments(self):
        return self._read('technical_evaluation_enrollments',
            'SELECT payload FROM technical_evaluation_enrollments ORDER BY enrollment_id', (), technical_enrollment_from_json)

    def get_observations_for_enrollment(self, enrollment_id):
        return self._read('technical_evaluation_observations',
            'SELECT payload FROM technical_evaluation_observations WHERE enrollment_id = ? ORDER BY point',
            (enrollment_id,), observation_from_json)

    def save_observations(self, observations):
        observations = tuple(observations)
        if (len(observations) != 2 or {o.point for o in observations} != {'reference', 'endpoint'}
                or len({o.enrollment_id for o in observations}) != 1):
            raise ValueError('Technical collection requires one atomic reference/endpoint pair.')
        super().save_observations(observations)

    def _insert_observation(self, connection, item, payload):
        row = connection.execute('SELECT payload FROM technical_evaluation_enrollments WHERE enrollment_id = ?',
                                 (item.enrollment_id,)).fetchone()
        if row is None:
            raise sqlite3.IntegrityError('Technical enrollment does not exist.')
        enrollment = technical_enrollment_from_json(row[0])
        record = self.get_signal_record(enrollment.signal_record_id)
        # Shared engine checks prices and temporal provenance; technical adapter also
        # checks immutable exact calendar points and the preserved source digest.
        evaluate_technical_signal(record, enrollment,
            item if item.point == 'reference' else None, item if item.point == 'endpoint' else None)
        connection.execute('INSERT INTO technical_evaluation_observations VALUES (?, ?, ?, ?)',
            (item.observation_id, item.enrollment_id, item.point, payload))
