"""Horizon v2 draft validation. No model IO or public view assembly.

Explicit selection is not semantic entailment. Public rendered-prose validation
and source-lineage assembly remain mandatory in the assembly boundary.
"""
from dataclasses import dataclass
from enum import StrEnum
from src.generation_contracts import HORIZON_V2, EVIDENCE_FIRST_ASSEMBLY_VERSION
from src.horizon_integration import require_synthesis_ready
from src.horizon_synthesis import _packet, _invalidation_ids, _object, NARRATIVES, POSTURES

VERSION = HORIZON_V2
ASSEMBLY_VERSION = EVIDENCE_FIRST_ASSEMBLY_VERSION
MAX_PARTS, MAX_ITEMS, MAX_TEXT = 128, 128, 8192


class Namespace(StrEnum):
    FUNDAMENTAL = 'FUNDAMENTAL'
    TECHNICAL = 'TECHNICAL'


class PartKind(StrEnum):
    TEXT = 'TEXT'
    FEATURE = 'FEATURE'
    CITATION = 'CITATION'


class Role(StrEnum):
    SUPPORTING = 'SUPPORTING'
    CONFLICTING = 'CONFLICTING'


class Reason(StrEnum):
    SHAPE = 'HORIZON_DRAFT_SHAPE_INVALID'
    POSTURE = 'HORIZON_DRAFT_POSTURE_INVALID'
    EVIDENCE = 'HORIZON_DRAFT_EVIDENCE_INVALID'
    UNBOUND = 'HORIZON_DRAFT_UNBOUND_FEATURE'
    GROUNDING = 'HORIZON_DRAFT_GROUNDING_REQUIRED'
    ROLE = 'HORIZON_DRAFT_ROLE_DUPLICATE'
    CONDITION = 'HORIZON_DRAFT_CONDITION_INVALID'
    INVALIDATION = 'HORIZON_DRAFT_INVALIDATION_REQUIRED'
    WAIT = 'HORIZON_DRAFT_WAIT_CONDITION_REQUIRED'


class HorizonDraftError(ValueError):
    def __init__(self, reason):
        self.reason = Reason(reason)
        super().__init__(self.reason.value)


@dataclass(frozen=True)
class EvidenceSelection:
    namespace: Namespace
    evidence_id: str


@dataclass(frozen=True)
class HorizonPart:
    kind: PartKind
    text: str | None = None
    selection: EvidenceSelection | None = None


@dataclass(frozen=True)
class HorizonRole:
    selection: EvidenceSelection
    role: Role


@dataclass(frozen=True)
class HorizonStatementDraft:
    parts: tuple[HorizonPart, ...]
    condition_ids: tuple[str, ...]
    classification: str | None  # None means condition-bound; assembly must use FORECAST.

    @property
    def selected_evidence(self):
        return tuple(dict.fromkeys(p.selection for p in self.parts if p.selection is not None))


@dataclass(frozen=True)
class HorizonSynthesisDraft:
    timing_posture: str
    synthesis_confidence: int
    synthesis_summary: HorizonStatementDraft
    agreement_explanation: HorizonStatementDraft
    horizon_interpretation: HorizonStatementDraft
    invalidation_summary: HorizonStatementDraft
    major_integrated_risks: tuple[HorizonStatementDraft, ...]
    evidence_roles: tuple[HorizonRole, ...]


def _array(item, minimum=0):
    return {'type':'array', 'items':item, 'minItems':minimum, 'maxItems':MAX_ITEMS}


_STRING = {'type':'string', 'minLength':1, 'maxLength':MAX_TEXT}
_SELECTION = {'namespace':{'type':'string','enum':list(Namespace)}, 'evidence_id':_STRING}
_PART = {'anyOf':[
    _object({'kind':{'type':'string','enum':['TEXT']}, 'value':_STRING}),
    _object({'kind':{'type':'string','enum':['FEATURE']},
             'namespace':{'type':'string','enum':['TECHNICAL']}, 'evidence_id':_STRING}),
    _object({'kind':{'type':'string','enum':['CITATION']}, **_SELECTION})]}
_PARTS = {'type':'array','items':_PART,'minItems':1,'maxItems':MAX_PARTS}
_STATEMENT = {'anyOf':[
    _object({'parts':_PARTS, 'condition_ids':_array(_STRING,1)}),
    _object({'parts':_PARTS, 'classification':{'type':'string','enum':['AI_INTERPRETATION','FORECAST']}})]}
SCHEMA = _object({'timing_posture':{'type':'string','enum':list(POSTURES)},
    'synthesis_confidence':{'type':'integer','minimum':0,'maximum':100},
    **{key:_STATEMENT for key in NARRATIVES}, 'major_integrated_risks':_array(_STATEMENT),
    'evidence_roles':_array(_object({**_SELECTION,'role':{'type':'string','enum':list(Role)}}))})


def _fail(reason=Reason.SHAPE):
    raise HorizonDraftError(reason)


def _shape(value, keys):
    if not isinstance(value,dict) or set(value)!=set(keys): _fail()


def _list(value, minimum=0, maximum=MAX_ITEMS):
    if not isinstance(value,list) or not minimum<=len(value)<=maximum: _fail()


def _string(value):
    if not isinstance(value,str) or not 1<=len(value)<=MAX_TEXT: _fail()


def validate_horizon_draft(data, context):
    """Recompute readiness and authoritative packet; never trust model metadata."""
    return _validate_packet(data, _packet(require_synthesis_ready(context)))


def _validate_packet(data, packet):
    """Internal parser; packet must come from readiness revalidation above."""
    _shape(data,SCHEMA['required'])
    if not isinstance(data['timing_posture'],str) or data['timing_posture'] not in packet['allowed_postures']:
        _fail(Reason.POSTURE)
    if type(data['synthesis_confidence']) is not int or not 0<=data['synthesis_confidence']<=100: _fail()
    fids={r['evidence_id'] for r in packet['fundamental']['catalog']}
    technical={r['evidence_id']:r for r in packet['technical']['catalog']}
    tids={key for key,row in technical.items() if row['value'] is not None}
    labels=[row['label'] for row in technical.values()]
    conditions=packet['conditions']

    def selection(raw):
        ns=raw['namespace'];key=raw['evidence_id']
        if not isinstance(ns,str) or ns not in Namespace._value2member_map_: _fail(Reason.EVIDENCE)
        if not isinstance(key,str) or key not in (fids if ns=='FUNDAMENTAL' else tids): _fail(Reason.EVIDENCE)
        _string(key)
        return EvidenceSelection(Namespace(ns),key)

    def statement(raw, invalidation=False):
        if not isinstance(raw,dict): _fail()
        bound='condition_ids' in raw
        _shape(raw,('parts','condition_ids') if bound else ('parts','classification'))
        refs=()
        classification=None
        if bound:
            _list(raw['condition_ids'],1)
            seen=set()
            for key in raw['condition_ids']:
                if not isinstance(key,str) or key not in conditions or key in seen: _fail(Reason.CONDITION)
                _string(key);seen.add(key)
                source=conditions[key]
                dependencies=source['evidence_refs'] if key.startswith('F_') else source['evidence_ids']
                allowed=fids if key.startswith('F_') else tids
                if not set(dependencies)<=allowed: _fail(Reason.EVIDENCE)
            refs=tuple(raw['condition_ids'])
        else:
            classification=raw['classification']
            if not isinstance(classification,str) or classification not in ('AI_INTERPRETATION','FORECAST'): _fail()
        available=_invalidation_ids(conditions)
        if invalidation and ((available and not refs) or not set(refs)<=available): _fail(Reason.INVALIDATION)
        _list(raw['parts'],1,MAX_PARTS)
        parts=[];runs=[''];has_text=False
        for part in raw['parts']:
            if not isinstance(part,dict): _fail()
            kind=part.get('kind')
            if not isinstance(kind,str) or kind not in PartKind._value2member_map_: _fail()
            if kind=='TEXT':
                _shape(part,('kind','value'));_string(part['value'])
                runs[-1]+=part['value'];has_text=has_text or bool(part['value'].strip())
                parts.append(HorizonPart(PartKind.TEXT,text=part['value']))
            else:
                _shape(part,('kind','namespace','evidence_id'))
                selected=selection(part)
                if kind=='FEATURE':
                    if selected.namespace!=Namespace.TECHNICAL: _fail(Reason.EVIDENCE)
                    # v1 recognizes every supplied Technical catalog label as canonical.
                    if not isinstance(technical[selected.evidence_id]['label'],str) or not technical[selected.evidence_id]['label']:
                        _fail(Reason.EVIDENCE)
                    runs.append('');has_text=True
                parts.append(HorizonPart(PartKind(kind),selection=selected))
        if any(label.lower() in run.lower() for run in runs for label in labels): _fail(Reason.UNBOUND)
        result=HorizonStatementDraft(tuple(parts),refs,classification)
        if not has_text: _fail()
        if not result.selected_evidence: _fail(Reason.GROUNDING)
        return result

    _list(data['evidence_roles'])
    roles=[];seen=set()
    for raw in data['evidence_roles']:
        _shape(raw,('namespace','evidence_id','role'))
        selected=selection(raw)
        if not isinstance(raw['role'],str) or raw['role'] not in Role._value2member_map_: _fail()
        if selected in seen: _fail(Reason.ROLE)
        seen.add(selected);roles.append(HorizonRole(selected,Role(raw['role'])))
    narratives={key:statement(data[key],key=='invalidation_summary') for key in NARRATIVES}
    summary=narratives['synthesis_summary']
    # Public grounding also permits mandated lineage of explicitly selected conditions.
    summary_namespaces={s.namespace for s in summary.selected_evidence}
    for ref in summary.condition_ids:
        source=conditions[ref]
        ns=Namespace.FUNDAMENTAL if ref.startswith('F_') else Namespace.TECHNICAL
        if source['evidence_refs' if ns==Namespace.FUNDAMENTAL else 'evidence_ids']:
            summary_namespaces.add(ns)
    if summary_namespaces!=set(Namespace): _fail(Reason.GROUNDING)
    # Existing policy allows a confirmation OR invalidation source condition for WAIT.
    if data['timing_posture']=='WAIT_FOR_CONFIRMATION' and not summary.condition_ids: _fail(Reason.WAIT)
    _list(data['major_integrated_risks'])
    risks=tuple(statement(raw) for raw in data['major_integrated_risks'])
    return HorizonSynthesisDraft(data['timing_posture'],data['synthesis_confidence'],
        **narratives,major_integrated_risks=risks,evidence_roles=tuple(roles))
