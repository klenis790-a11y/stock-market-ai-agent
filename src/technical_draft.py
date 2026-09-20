"""Technical v2 internal contract. No IO, rendering or public signal assembly.

A validated draft proves explicit selections and binding integrity, not entailment.
Callers must supply the source snapshot/catalog; existing preflight verifies identity.
Rendered-prose safeguards remain required at the public assembly boundary.
"""
from dataclasses import dataclass
from enum import StrEnum
from src.analysis import _object_schema
from src.generation_contracts import TECHNICAL_V2, EVIDENCE_FIRST_ASSEMBLY_VERSION
from src.technical_analyst import SIGNALS, FEATURE_FAMILIES, _preflight

VERSION = TECHNICAL_V2
ASSEMBLY_VERSION = EVIDENCE_FIRST_ASSEMBLY_VERSION
# Internal response resource bounds, not financial thresholds.
MAX_PARTS = 128
MAX_STATEMENTS = 64
MAX_TEXT = 8192
MAX_ROLES = 64


class StatementPartKind(StrEnum):
    TEXT = 'TEXT'
    FEATURE = 'FEATURE'
    CITATION = 'CITATION'


class EvidenceRole(StrEnum):
    SUPPORTING = 'SUPPORTING'
    CONFLICTING = 'CONFLICTING'


class DraftReason(StrEnum):
    SHAPE = 'TECHNICAL_DRAFT_SHAPE_INVALID'
    SELECTION = 'TECHNICAL_DRAFT_SELECTION_INVALID'
    UNBOUND = 'TECHNICAL_DRAFT_UNBOUND_FEATURE'
    GROUNDING = 'TECHNICAL_DRAFT_SELECTION_REQUIRED'
    TEXT = 'TECHNICAL_DRAFT_TEXT_REQUIRED'
    ROLE_DUPLICATE = 'TECHNICAL_DRAFT_ROLE_DUPLICATE'
    SUPPORTING = 'TECHNICAL_DRAFT_SUPPORTING_REQUIRED'
    CONDITIONS = 'TECHNICAL_DRAFT_CONDITIONS_REQUIRED'
    MISSING_NOTE = 'TECHNICAL_DRAFT_MISSING_NOTE_REQUIRED'
    CONFIDENCE = 'TECHNICAL_DRAFT_CONFIDENCE_CONFLICT'


class TechnicalDraftError(ValueError):
    def __init__(self, reason):
        self.reason = DraftReason(reason)
        super().__init__(self.reason.value)


@dataclass(frozen=True)
class StatementPart:
    kind: StatementPartKind
    value: str


@dataclass(frozen=True)
class BoundStatementDraft:
    parts: tuple[StatementPart, ...]

    @property
    def selected_evidence_ids(self):
        """First occurrence order; repeated explicit selections do not add citations."""
        return tuple(dict.fromkeys(p.value for p in self.parts if p.kind != StatementPartKind.TEXT))


@dataclass(frozen=True)
class EvidenceRoleAssignment:
    evidence_id: str
    role: EvidenceRole


@dataclass(frozen=True)
class TechnicalAnalysisDraft:
    signal: str
    confidence: int
    summary: BoundStatementDraft
    thesis: BoundStatementDraft
    evidence_roles: tuple[EvidenceRoleAssignment, ...]
    confirmation_conditions: tuple[BoundStatementDraft, ...]
    invalidation_conditions: tuple[BoundStatementDraft, ...]
    risk_notes: tuple[BoundStatementDraft, ...]
    missing_data_acknowledgement: str


def _array(items, maximum, minimum=0):
    return {'type': 'array', 'items': items, 'minItems': minimum, 'maxItems': maximum}


_TEXT = {'type': 'string', 'maxLength': MAX_TEXT}
_PART = _object_schema({'kind': {'type': 'string', 'enum': list(StatementPartKind)},
                        'value': {**_TEXT, 'minLength': 1}})
_STATEMENT = _object_schema({'parts': _array(_PART, MAX_PARTS, 1)})
_ROLE = _object_schema({'evidence_id': {**_TEXT, 'minLength': 1},
                        'role': {'type': 'string', 'enum': list(EvidenceRole)}})
SCHEMA = _object_schema({
    'signal': {'type': 'string', 'enum': list(SIGNALS)},
    'confidence': {'type': 'integer', 'minimum': 0, 'maximum': 100},
    'summary': _STATEMENT, 'thesis': _STATEMENT,
    'evidence_roles': _array(_ROLE, MAX_ROLES, 1),
    'confirmation_conditions': _array(_STATEMENT, MAX_STATEMENTS, 1),
    'invalidation_conditions': _array(_STATEMENT, MAX_STATEMENTS),
    'risk_notes': _array(_STATEMENT, MAX_STATEMENTS),
    'missing_data_acknowledgement': _TEXT,
})


def _fail(reason=DraftReason.SHAPE):
    raise TechnicalDraftError(reason)


def _object(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        _fail()


def _list(value, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail()


def missing_evidence_ids(catalog):
    """Inventory only, in authoritative catalog order; no impact interpretation."""
    return tuple(item.evidence_id for item in catalog.items if item.value is None)


def validate_technical_draft(data, snapshot, catalog, horizon):
    """Validate decoded JSON. Does not call a model or return TechnicalSignal.

    Dataclass construction alone is not validation. Future assembly must revalidate
    against the same authoritative catalog before producing a public artifact.
    """
    items, available = _preflight(snapshot, catalog, horizon)
    _object(data, SCHEMA['required'])
    if (not isinstance(data['signal'], str) or data['signal'] not in SIGNALS or
            type(data['confidence']) is not int or not 0 <= data['confidence'] <= 100):
        _fail()

    def selection(value):
        if not isinstance(value, str) or value not in available:
            _fail(DraftReason.SELECTION)
        return items[value]

    def statement(value):
        _object(value, ('parts',))
        _list(value['parts'], MAX_PARTS, 1)
        parts = []
        text_runs = ['']
        for raw in value['parts']:
            _object(raw, ('kind', 'value'))
            if (not isinstance(raw['kind'], str) or raw['kind'] not in StatementPartKind._value2member_map_ or
                    not isinstance(raw['value'], str) or not 1 <= len(raw['value']) <= MAX_TEXT):
                _fail()
            kind, text = StatementPartKind(raw['kind']), raw['value']
            if kind == StatementPartKind.TEXT:
                text_runs[-1] += text
            else:
                item = selection(text)
                if kind == StatementPartKind.FEATURE:
                    # All existing catalog labels are canonical prose references in v1,
                    # including PRICE/DATA_QUALITY. No analytical eligibility rule added.
                    if item.label not in FEATURE_FAMILIES:
                        _fail(DraftReason.SELECTION)
                    text_runs.append('')
            parts.append(StatementPart(kind, text))
        # CITATION emits no text; adjacent TEXT across citations must also be checked.
        if any(label.lower() in run.lower() for run in text_runs for label in FEATURE_FAMILIES):
            _fail(DraftReason.UNBOUND)
        result = BoundStatementDraft(tuple(parts))
        if not result.selected_evidence_ids:
            _fail(DraftReason.GROUNDING)
        if not any(p.kind == StatementPartKind.FEATURE or
                   (p.kind == StatementPartKind.TEXT and p.value.strip()) for p in parts):
            _fail(DraftReason.TEXT)
        return result

    _list(data['evidence_roles'], MAX_ROLES)
    roles, seen = [], set()
    for raw in data['evidence_roles']:
        _object(raw, ('evidence_id', 'role'))
        selection(raw['evidence_id'])
        if not isinstance(raw['role'], str) or raw['role'] not in EvidenceRole._value2member_map_:
            _fail()
        if raw['evidence_id'] in seen:
            _fail(DraftReason.ROLE_DUPLICATE)
        seen.add(raw['evidence_id'])
        roles.append(EvidenceRoleAssignment(raw['evidence_id'], EvidenceRole(raw['role'])))
    if not any(r.role == EvidenceRole.SUPPORTING for r in roles):
        _fail(DraftReason.SUPPORTING)
    missing = missing_evidence_ids(catalog)
    if data['confidence'] > 90 and (missing or any(r.role == EvidenceRole.CONFLICTING for r in roles)):
        _fail(DraftReason.CONFIDENCE)
    summary, thesis = statement(data['summary']), statement(data['thesis'])
    groups = {}
    for key in ('confirmation_conditions', 'invalidation_conditions', 'risk_notes'):
        _list(data[key], MAX_STATEMENTS)
        groups[key] = tuple(statement(v) for v in data[key])
    if not groups['confirmation_conditions'] or (data['signal'] != 'NEUTRAL' and not groups['invalidation_conditions']):
        _fail(DraftReason.CONDITIONS)
    note = data['missing_data_acknowledgement']
    if not isinstance(note, str) or len(note) > MAX_TEXT:
        _fail()
    if missing and not note.strip():
        _fail(DraftReason.MISSING_NOTE)
    if note and not note.strip():
        _fail(DraftReason.TEXT)
    return TechnicalAnalysisDraft(data['signal'], data['confidence'], summary, thesis,
        tuple(roles), groups['confirmation_conditions'], groups['invalidation_conditions'],
        groups['risk_notes'], note)
