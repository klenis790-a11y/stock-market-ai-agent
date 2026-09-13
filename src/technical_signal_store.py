"""Explicit append-only technical belief storage; no research or outcome computation."""
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date, datetime
import json
import sqlite3
from uuid import uuid4

from src.decision_store import DecisionStore
from src.evaluation_models import utc_timestamp
from src.technical_analyst import HORIZONS, SIGNALS
from src.technical_evidence import TechnicalEvidenceItem

RECORD_VERSION = 'technical-signal-record-v1'


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False, default=lambda v: v.isoformat() if isinstance(v, (date, datetime)) else _invalid())


def _invalid():
    raise ValueError('Unsupported historical value.')


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Required historical text is missing.')


def _validate(signal, packet):
    """Validate storage shape, not current analyst prose rules or recalculated evidence.

    Nonempty methodology identifiers are preserved opaquely, including future versions;
    loading never converts historical JSON into current runtime analyst semantics.
    """
    if signal['provenance'] != packet['provenance'] or signal['evidence_catalog_version'] != packet['methodology_version']:
        raise ValueError('Signal and evidence provenance differ.')
    p = signal['provenance']
    for key in ('symbol', 'provider', 'provider_function', 'adjustment_mode', 'timeframe',
                'calendar', 'calendar_version', 'market_data_methodology', 'feature_methodology'):
        _text(p[key])
    for key in ('requested_as_of', 'retrieved_at'):
        utc_timestamp(p[key])
    for key in ('latest_completed_session', 'first_included_session', 'expected_last_session'):
        if p[key] is not None:
            date.fromisoformat(p[key])
    for key in ('evidence_catalog_version', 'analyst_methodology_version', 'model'):
        _text(signal[key])
    if signal['horizon'] not in HORIZONS or signal['analysis']['signal'] not in SIGNALS:
        raise ValueError('Unknown historical signal or horizon.')
    a = signal['analysis']
    if type(a['confidence']) is not int or not 0 <= a['confidence'] <= 100:
        raise ValueError('Invalid historical confidence.')
    if not isinstance(packet['items'], list) or not packet['items']:
        raise ValueError('Evidence packet required.')
    items = {}
    for raw in packet['items']:
        item = TechnicalEvidenceItem(**raw)
        _text(item.evidence_id)
        if item.evidence_id in items:
            raise ValueError('Duplicate evidence ID.')
        items[item.evidence_id] = item
    def ids(values, missing=False):
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError('Ordered evidence IDs required.')
        if len(set(values)) != len(values) or any(v not in items for v in values):
            raise ValueError('Invalid evidence reference.')
        if any((items[v].value is None) != missing for v in values):
            raise ValueError('Evidence availability mismatch.')
    for key in ('supporting_evidence_ids', 'conflicting_evidence_ids'):
        ids(a[key])
    ids(a['missing_evidence_ids'], True)
    if set(a['missing_evidence_ids']) != {k for k,v in items.items() if v.value is None}:
        raise ValueError('Missing evidence inventory differs.')
    if not isinstance(a['missing_data_acknowledgement'], str):
        raise ValueError('Missing-data notes must be text.')
    statements = [a['summary'], a['thesis']]
    for key in ('confirmation_conditions', 'invalidation_conditions', 'risk_notes'):
        if not isinstance(a[key], list):
            raise ValueError('Ordered statements required.')
        statements.extend(a[key])
    for statement in statements:
        _text(statement['text'])
        ids(statement['evidence_ids'])


@dataclass(frozen=True)
class TechnicalSignalRecord:
    """Immutable JSON source of truth; accessors return detached historical dictionaries."""
    record_id: str
    created_at: str
    signal_json: str
    evidence_json: str
    record_version: str = RECORD_VERSION

    def __post_init__(self):
        try:
            _text(self.record_id)
            if self.record_version != RECORD_VERSION:
                raise ValueError('Unsupported technical signal record version.')
            object.__setattr__(self, 'created_at', utc_timestamp(self.created_at))
            _validate(self.signal, self.evidence_packet)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise ValueError('Invalid technical signal record: ' + str(exc)) from exc

    @property
    def signal(self):
        return json.loads(self.signal_json)

    @property
    def evidence_packet(self):
        return json.loads(self.evidence_json)

    @property
    def symbol(self):
        return self.signal['provenance']['symbol']


def create_technical_signal_record(signal, catalog, *, created_at, record_id=None):
    """Prepare once and reuse its ID for retries. Does not save or infer generation time."""
    timestamp = utc_timestamp(created_at.isoformat() if isinstance(created_at, datetime) else created_at)
    identity = record_id or f'{signal.provenance.symbol}-{timestamp}-{uuid4().hex}'
    return TechnicalSignalRecord(identity, timestamp, _json(asdict(signal)), _json(catalog.to_packet()))


class TechnicalSignalStore(DecisionStore):
    """One-row INSERT is the transaction boundary. No update or outcome API is added."""
    def initialize(self):
        with closing(self._connect()) as connection, connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS technical_signals (
                record_id TEXT PRIMARY KEY NOT NULL, symbol TEXT NOT NULL,
                created_at TEXT NOT NULL, record_version TEXT NOT NULL,
                signal_json TEXT NOT NULL, evidence_json TEXT NOT NULL)''')

    def save_technical_signal(self, record):
        checked = TechnicalSignalRecord(**asdict(record))
        with closing(self._connect()) as connection, connection:
            connection.execute('INSERT INTO technical_signals VALUES (?, ?, ?, ?, ?, ?)',
                (checked.record_id, checked.symbol, checked.created_at, checked.record_version,
                 checked.signal_json, checked.evidence_json))

    def _read(self, clause='', parameters=()):
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute('SELECT * FROM technical_signals ' + clause +
                                      ' ORDER BY created_at DESC, record_id', parameters).fetchall()
        records = []
        for row in rows:
            data = dict(row)
            symbol = data.pop('symbol')
            record = TechnicalSignalRecord(**data)
            if record.symbol != symbol:
                raise ValueError('Corrupt indexed symbol.')
            records.append(record)
        return records

    def get_technical_signal(self, record_id):
        records = self._read('WHERE record_id = ?', (record_id,))
        return records[0] if records else None

    def list_technical_signals(self, symbol=None):
        return self._read('WHERE symbol = ?', (symbol.strip().upper(),)) if symbol is not None else self._read()
