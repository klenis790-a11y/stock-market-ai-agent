"""Deterministic Technical v2 assembly used by generation and offline tests; no IO."""
from dataclasses import replace
from src.generation_contracts import TECHNICAL_V2
from src.technical_analyst import TechnicalSignal, _parse, _preflight
from src.technical_draft import (TechnicalAnalysisDraft, BoundStatementDraft, StatementPart,
    StatementPartKind, EvidenceRoleAssignment, EvidenceRole, TechnicalDraftError,
    DraftReason, validate_technical_draft, missing_evidence_ids)


def _draft_data(draft):
    """Re-enter validation; frozen dataclasses alone are not trusted certificates."""
    def require(condition):
        if not condition:
            raise TechnicalDraftError(DraftReason.SHAPE)

    def statement(value):
        require(type(value) is BoundStatementDraft and type(value.parts) is tuple)
        parts = []
        for part in value.parts:
            require(type(part) is StatementPart and type(part.kind) is StatementPartKind)
            parts.append(dict(kind=part.kind.value, value=part.value))
        return dict(parts=parts)

    require(type(draft) is TechnicalAnalysisDraft)
    require(type(draft.evidence_roles) is tuple)
    roles = []
    for assignment in draft.evidence_roles:
        require(type(assignment) is EvidenceRoleAssignment and type(assignment.role) is EvidenceRole)
        roles.append(dict(evidence_id=assignment.evidence_id, role=assignment.role.value))
    data = dict(signal=draft.signal, confidence=draft.confidence,
        summary=statement(draft.summary), thesis=statement(draft.thesis),
        evidence_roles=roles, missing_data_acknowledgement=draft.missing_data_acknowledgement)
    for key in ('confirmation_conditions', 'invalidation_conditions', 'risk_notes'):
        values = getattr(draft, key)
        require(type(values) is tuple)
        data[key] = [statement(value) for value in values]
    return data


def _statement_data(statement, items):
    """Only called with a freshly validated draft and its authoritative catalog."""
    text = []
    for part in statement.parts:
        if part.kind == StatementPartKind.TEXT:
            text.append(part.value)
        elif part.kind == StatementPartKind.FEATURE:
            text.append(items[part.value].label)
        # CITATION contributes only an explicit selection, never text.
    return dict(text=''.join(text), evidence_ids=list(statement.selected_evidence_ids))


def assemble_technical_v2_offline(draft, snapshot, catalog, horizon, *, model):
    """Revalidate, assemble and publicly validate a v2 signal without IO.

    model is explicit caller-owned execution metadata, not supplied by the draft.
    Selection validity and reference identity do not establish semantic entailment.
    """
    if not isinstance(model, str) or not model.strip():
        raise ValueError('Model identity required.')
    checked = validate_technical_draft(_draft_data(draft), snapshot, catalog, horizon)
    items, available = _preflight(snapshot, catalog, horizon)
    data = dict(signal=checked.signal, confidence=checked.confidence,
        summary=_statement_data(checked.summary, items),
        thesis=_statement_data(checked.thesis, items),
        supporting_evidence_ids=[r.evidence_id for r in checked.evidence_roles if r.role == EvidenceRole.SUPPORTING],
        conflicting_evidence_ids=[r.evidence_id for r in checked.evidence_roles if r.role == EvidenceRole.CONFLICTING],
        missing_evidence_ids=list(missing_evidence_ids(catalog)),
        missing_data_acknowledgement=checked.missing_data_acknowledgement)
    groups = ('confirmation_conditions', 'invalidation_conditions', 'risk_notes')
    for key in groups:
        data[key] = [_statement_data(value, items) for value in getattr(checked, key)]
    analysis = _parse(data, items, available)  # All existing public safeguards unchanged.
    # v1 parsing trims outer whitespace. Preserve the exact validated v2 prose,
    # including whitespace, without altering any citation or analytical value.
    analysis = replace(analysis,
        summary=replace(analysis.summary, text=data['summary']['text']),
        thesis=replace(analysis.thesis, text=data['thesis']['text']),
        missing_data_acknowledgement=data['missing_data_acknowledgement'],
        **{key: tuple(replace(value, text=raw['text']) for value, raw in
                      zip(getattr(analysis, key), data[key])) for key in groups})
    return TechnicalSignal(catalog.provenance, horizon, analysis,
                           catalog.methodology_version, model, TECHNICAL_V2)
