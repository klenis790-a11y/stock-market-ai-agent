"""Deterministic Horizon v2 assembly used by generation and offline tests; no IO."""
from datetime import datetime, timezone
from dataclasses import dataclass
from src.evaluation_models import utc_timestamp
from src.generation_contracts import HORIZON_V2
from src.horizon_integration import require_synthesis_ready
from src.horizon_synthesis import _packet, _validate, NARRATIVES, REFERENCES, IntegratedResearchView
from src.horizon_draft import (HorizonSynthesisDraft, HorizonStatementDraft, HorizonPart,
    HorizonRole, EvidenceSelection, Namespace, PartKind, Role, HorizonDraftError, Reason,
    _validate_packet)


def _draft_data(draft):
    def require(condition):
        if not condition: raise HorizonDraftError(Reason.SHAPE)

    def selection(value):
        require(type(value) is EvidenceSelection and type(value.namespace) is Namespace)
        return dict(namespace=value.namespace.value, evidence_id=value.evidence_id)

    def statement(value):
        require(type(value) is HorizonStatementDraft and type(value.parts) is tuple
                and type(value.condition_ids) is tuple)
        parts=[]
        for part in value.parts:
            require(type(part) is HorizonPart and type(part.kind) is PartKind)
            if part.kind==PartKind.TEXT:
                require(part.selection is None)
                parts.append(dict(kind='TEXT',value=part.text))
            else:
                require(part.text is None)
                parts.append(dict(kind=part.kind.value,**selection(part.selection)))
        if value.condition_ids:
            require(value.classification is None)
            return dict(parts=parts,condition_ids=list(value.condition_ids))
        return dict(parts=parts,classification=value.classification)

    require(type(draft) is HorizonSynthesisDraft)
    require(type(draft.evidence_roles) is tuple and type(draft.major_integrated_risks) is tuple)
    roles=[]
    for item in draft.evidence_roles:
        require(type(item) is HorizonRole and type(item.role) is Role)
        roles.append(dict(**selection(item.selection),role=item.role.value))
    return dict(timing_posture=draft.timing_posture,synthesis_confidence=draft.synthesis_confidence,
        **{key:statement(getattr(draft,key)) for key in NARRATIVES},
        major_integrated_risks=[statement(v) for v in draft.major_integrated_risks],evidence_roles=roles)


@dataclass(frozen=True)
class _StatementReferences:
    explicit: tuple[EvidenceSelection, ...]
    inherited: tuple[EvidenceSelection, ...]

    def ids(self, namespace):
        return list(dict.fromkeys(s.evidence_id for s in (*self.explicit,*self.inherited)
                                  if s.namespace==namespace))


def _statement_data(statement, packet):
    """Freshly validated selections only; lineage is separate until serialization."""
    technical={row['evidence_id']:row for row in packet['technical']['catalog']}
    text=[]
    for part in statement.parts:
        if part.kind==PartKind.TEXT: text.append(part.text)
        elif part.kind==PartKind.FEATURE: text.append(technical[part.selection.evidence_id]['label'])
    inherited=[]
    for ref in statement.condition_ids:
        source=packet['conditions'][ref]
        namespace=Namespace.FUNDAMENTAL if ref.startswith('F_') else Namespace.TECHNICAL
        key='evidence_refs' if namespace==Namespace.FUNDAMENTAL else 'evidence_ids'
        inherited.extend(EvidenceSelection(namespace,item) for item in source[key])
    refs=_StatementReferences(statement.selected_evidence,tuple(inherited))
    return dict(text=''.join(text),classification='FORECAST' if statement.condition_ids else statement.classification,
        fundamental_evidence_ids=refs.ids(Namespace.FUNDAMENTAL),
        technical_evidence_ids=refs.ids(Namespace.TECHNICAL),condition_ids=list(statement.condition_ids))


def assemble_horizon_v2_offline(draft, context, *, model):
    """Return an offline validated v2 view; no inference, repair, requests or saves.

    Caller supplies the original authoritative source context and model metadata.
    Frozen draft construction is not certification; readiness and draft are rechecked.
    """
    if not isinstance(model,str) or not model.strip(): raise ValueError('Model identity required.')
    ready=require_synthesis_ready(context)
    packet=_packet(ready)
    checked=_validate_packet(_draft_data(draft),packet)
    data=dict(identity=dict(packet['identity']),acknowledged_limitations=list(packet['limitations']),
        timing_posture=checked.timing_posture,synthesis_confidence=checked.synthesis_confidence,
        **{key:_statement_data(getattr(checked,key),packet) for key in NARRATIVES},
        major_integrated_risks=[_statement_data(v,packet) for v in checked.major_integrated_risks],
        **{key:[] for key in REFERENCES})
    for assignment in checked.evidence_roles:
        key=f'{assignment.role.value.lower()}_{assignment.selection.namespace.value.lower()}_evidence_ids'
        data[key].append(assignment.selection.evidence_id)
    analysis_json=_validate(data,packet)  # Unchanged public shape and all semantic safeguards.
    return IntegratedResearchView(ready,analysis_json,utc_timestamp(datetime.now(timezone.utc).isoformat()),
                                  model,methodology_version=HORIZON_V2)
