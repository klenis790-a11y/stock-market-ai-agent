import copy
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch
import test_v08 as fixtures
from src import horizon_draft as d
from src import horizon_synthesis as h


class HorizonDraftTests(unittest.TestCase):
    def setUp(self):
        self.helper=fixtures.HorizonSynthesisTests()
        self.helper.setUp();self.addCleanup(self.helper.doCleanups)
        self.context=self.helper.context
        self.packet=h._packet(self.context)
        self.fid=self.packet['fundamental']['catalog'][0]['evidence_id']
        self.tid=next(r['evidence_id'] for r in self.packet['technical']['catalog'] if r['value'] is not None)
        self.label=next(r['label'] for r in self.packet['technical']['catalog'] if r['evidence_id']==self.tid)
        for path in ('socket.socket.connect','src.openai_client.request_text','sqlite3.connect'):
            guard=patch(path,side_effect=AssertionError('No external side effects'))
            guard.start();self.addCleanup(guard.stop)

    def statement(self, conditions=None):
        out=dict(parts=[dict(kind='TEXT',value='Evidence informs interpretation.'),
            dict(kind='CITATION',namespace='FUNDAMENTAL',evidence_id=self.fid),
            dict(kind='CITATION',namespace='TECHNICAL',evidence_id=self.tid)])
        if conditions:out['condition_ids']=conditions
        else:out['classification']='AI_INTERPRETATION'
        return out

    def output(self):
        out=dict(timing_posture='FAVORABLE_NOW',synthesis_confidence=60,
                 evidence_roles=[],major_integrated_risks=[self.statement()])
        out.update({key:self.statement() for key in h.NARRATIVES})
        out['invalidation_summary']=self.statement(['F_INVALIDATION:0'])
        return out

    def reject(self,data,reason):
        with self.assertRaises(d.HorizonDraftError) as caught:d.validate_horizon_draft(data,self.context)
        self.assertEqual(caught.exception.reason,reason)
        self.assertEqual(str(caught.exception),reason.value)

    def test_valid_selection_and_condition_variants(self):
        data=self.output()
        available=[r for r in self.packet['technical']['catalog'] if r['value'] is not None]
        data['synthesis_summary']['parts'] += [dict(kind='FEATURE',namespace='TECHNICAL',evidence_id=r['evidence_id']) for r in available[:2]]
        data['agreement_explanation']['classification']='FORECAST'
        result=d.validate_horizon_draft(data,self.context)
        self.assertIsNone(result.invalidation_summary.classification)
        self.assertEqual(result.invalidation_summary.condition_ids,('F_INVALIDATION:0',))
        self.assertEqual(result.agreement_explanation.classification,'FORECAST')
        self.assertEqual(len(result.major_integrated_risks),1)
        with self.assertRaises(FrozenInstanceError):result.timing_posture='NO_ACTION'
        for ref in ('T_CONFIRMATION:0','F_INVALIDATION:0'):
            data=self.output();data['timing_posture']='WAIT_FOR_CONFIRMATION'
            data['synthesis_summary']=self.statement([ref])
            d.validate_horizon_draft(data,self.context)
        data=self.output();data['timing_posture']='WAIT_FOR_CONFIRMATION'
        self.reject(data,d.Reason.WAIT)
        for namespace,key in [('FUNDAMENTAL',self.fid),('TECHNICAL',self.tid)]:
            single=self.output()
            single['agreement_explanation']['parts']=[dict(kind='TEXT',value='Interpretation.'),
                dict(kind='CITATION',namespace=namespace,evidence_id=key)]
            d.validate_horizon_draft(single,self.context)
        for confidence in (0,100):
            edge=self.output();edge['synthesis_confidence']=confidence
            d.validate_horizon_draft(edge,self.context)


    def test_namespace_roles_and_literal_collision(self):
        data=self.output()
        data['evidence_roles']=[dict(namespace='FUNDAMENTAL',evidence_id=self.fid,role='SUPPORTING'),
            dict(namespace='TECHNICAL',evidence_id=self.tid,role='CONFLICTING')]
        d.validate_horizon_draft(data,self.context)
        for role in ('SUPPORTING','CONFLICTING'):
            bad=copy.deepcopy(data)
            bad['evidence_roles'].append(dict(namespace='FUNDAMENTAL',evidence_id=self.fid,role=role))
            self.reject(bad,d.Reason.ROLE)
        # Parser-level namespace characterization, not a forged ready context.
        packet=copy.deepcopy(self.packet)
        packet['fundamental']['catalog'].append(dict(evidence_id=self.tid))
        data['evidence_roles'][0]['evidence_id']=self.tid
        got=d._validate_packet(data,packet)
        self.assertEqual(len(got.evidence_roles),2)
        self.assertNotEqual(got.evidence_roles[0].selection,got.evidence_roles[1].selection)
        # Roles need not cover narratives, and may reference other valid evidence.
        extra=next(r['evidence_id'] for r in self.packet['technical']['catalog'] if r['value'] is not None and r['evidence_id']!=self.tid)
        data=self.output();data['evidence_roles']=[dict(namespace='TECHNICAL',evidence_id=extra,role='SUPPORTING')]
        d.validate_horizon_draft(data,self.context)

    def test_evidence_binding_rejections(self):
        unavailable=next(r['evidence_id'] for r in self.packet['technical']['catalog'] if r['value'] is None)
        for ns,key,kind in [('OTHER',self.tid,'CITATION'),('FUNDAMENTAL','UNKNOWN','CITATION'),
                ('TECHNICAL','UNKNOWN','FEATURE'),('TECHNICAL','UNKNOWN','CITATION'),
                ('TECHNICAL',unavailable,'FEATURE'),('TECHNICAL',unavailable,'CITATION'),
                ('FUNDAMENTAL',self.fid,'FEATURE')]:
            data=self.output();data['synthesis_summary']['parts'].append(dict(kind=kind,namespace=ns,evidence_id=key))
            self.reject(data,d.Reason.EVIDENCE)
        for key in ('FABRICATED',unavailable):
            bad=self.output();bad['evidence_roles']=[dict(namespace='TECHNICAL',evidence_id=key,role='SUPPORTING')]
            self.reject(bad,d.Reason.EVIDENCE)
        data=self.output();data['synthesis_summary']['parts'][0]['value']=self.label.upper()
        self.reject(data,d.Reason.UNBOUND)
        data=self.output();data['synthesis_summary']['parts']=[dict(kind='TEXT',value='Interpretation.'),dict(kind='CITATION',namespace='TECHNICAL',evidence_id=self.tid)]
        self.reject(data,d.Reason.GROUNDING)
        data=self.output();data['major_integrated_risks'][0]['parts']=[dict(kind='TEXT',value='Interpretation.')]
        self.reject(data,d.Reason.GROUNDING)

    def test_condition_and_invalidation_rejections(self):
        for conditions,reason in [(['FAKE'],d.Reason.CONDITION),(['F_INVALIDATION:999'],d.Reason.CONDITION),
                (['T_CONFIRMATION:0'],d.Reason.INVALIDATION),(['F_INVALIDATION:0']*2,d.Reason.CONDITION)]:
            data=self.output();data['invalidation_summary']=self.statement(conditions)
            self.reject(data,reason)
        data=self.output();data['invalidation_summary']=self.statement()
        self.reject(data,d.Reason.INVALIDATION)
        data=self.output();data['invalidation_summary']['classification']='AI_INTERPRETATION'
        self.reject(data,d.Reason.SHAPE)
        data=self.output();data['invalidation_summary']['condition_ids']=[]
        self.reject(data,d.Reason.SHAPE)

    def test_absent_invalidations_from_real_ready_sources(self):
        contexts=[]
        original=h._packet
        def capture(context):
            contexts.append(context)
            return original(context)
        with patch.object(h,'_packet',side_effect=capture):
            fixtures.ContractConstructibilityAuditTests().exercise_source_invalidations()
        context=contexts[-1];packet=original(context)
        self.assertFalse(h._invalidation_ids(packet['conditions']))
        data=self.output()
        data['timing_posture']=packet['allowed_postures'][0]
        data['invalidation_summary']=self.statement()
        d.validate_horizon_draft(data,context)
        self.assertIn('NO_SOURCE_INVALIDATION_CONDITION',packet['limitations'])
        self.assertNotIn('acknowledged_limitations',data)
        for ref,reason in [('F_INVALIDATION:0',d.Reason.CONDITION),('T_CONFIRMATION:0',d.Reason.INVALIDATION)]:
            bad=copy.deepcopy(data);bad['invalidation_summary']=self.statement([ref])
            with self.assertRaises(d.HorizonDraftError) as caught:d.validate_horizon_draft(bad,context)
            self.assertEqual(caught.exception.reason,reason)

    def test_schema_shape_metadata_and_readiness(self):
        mutations=[lambda x:x.update(identity={}),lambda x:x.update(acknowledged_limitations=[]),
            lambda x:x.update(synthesis_confidence=True),
            lambda x:x['synthesis_summary']['parts'][0].update(kind='OTHER'),
            lambda x:x['synthesis_summary'].update(classification='RETRIEVED_FACT'),
            lambda x:x.update(evidence_roles=[dict(namespace='TECHNICAL',evidence_id=self.tid,role='OTHER')]),
            lambda x:x['major_integrated_risks'][0].update(parts=[dict(kind='TEXT',value='   '),dict(kind='CITATION',namespace='TECHNICAL',evidence_id=self.tid)])]
        for mutate in mutations:
            data=self.output();mutate(data);self.reject(data,d.Reason.SHAPE)
        data=self.output();data['timing_posture']='BUY';self.reject(data,d.Reason.POSTURE)
        from src.horizon_integration import SynthesisReadinessError
        with self.assertRaises(SynthesisReadinessError):
            d.validate_horizon_draft(self.output(),replace(self.context,primary_authority='FORGED'))
        def inspect(schema):
            if schema.get('type')=='object':
                self.assertFalse(schema['additionalProperties'])
                self.assertEqual(set(schema['required']),set(schema['properties']))
                for child in schema['properties'].values():inspect(child)
            if schema.get('type')=='array':inspect(schema['items'])
            for child in schema.get('anyOf',[]):inspect(child)
        inspect(d.SCHEMA);json.dumps(d.SCHEMA,allow_nan=False)

    def test_active_v2_generation(self):
        from src.generation_contracts import ACTIVE_HORIZON_VERSION
        with patch('src.openai_client.request_text',return_value=json.dumps(self.output())) as call:
            view=h.synthesize_horizon(self.context)
        self.assertEqual(view.methodology_version,'horizon-synthesis-v2')
        self.assertEqual(ACTIVE_HORIZON_VERSION,'horizon-synthesis-v2')
        self.assertEqual(call.call_args.kwargs['text']['format']['schema'],d.SCHEMA)
        self.assertNotIn('identity',call.call_args.kwargs['text']['format']['schema']['required'])
        self.assertIn('acknowledged_limitations',view.analysis)
        call.assert_called_once()
