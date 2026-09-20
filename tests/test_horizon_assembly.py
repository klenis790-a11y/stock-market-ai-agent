import copy
import unittest
from dataclasses import replace, FrozenInstanceError
from unittest.mock import patch
import test_horizon_draft as fixtures
import test_v08 as v08
from src import horizon_draft as d, horizon_synthesis as h
from src.horizon_assembly import assemble_horizon_v2_offline, _statement_data


class HorizonAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.helper=fixtures.HorizonDraftTests();self.helper.setUp();self.addCleanup(self.helper.doCleanups)
        self.context=self.helper.context;self.packet=self.helper.packet

    def assemble(self,data=None,context=None):
        context=context or self.context
        draft=d.validate_horizon_draft(data or self.helper.output(),context)
        return assemble_horizon_v2_offline(draft,context,model='offline-fixture')

    def test_exact_text_roles_identity_limits_shape_and_version(self):
        data=self.helper.output();available=[r for r in self.packet['technical']['catalog'] if r['value'] is not None]
        a,b=available[:2]
        parts=[dict(kind='TEXT',value='  '),dict(kind='FEATURE',namespace='TECHNICAL',evidence_id=a['evidence_id']),
            dict(kind='TEXT',value=' and '),dict(kind='FEATURE',namespace='TECHNICAL',evidence_id=b['evidence_id']),
            dict(kind='TEXT',value=' inform interpretation.\n'),dict(kind='CITATION',namespace='TECHNICAL',evidence_id=a['evidence_id']),
            dict(kind='CITATION',namespace='FUNDAMENTAL',evidence_id=self.helper.fid)]
        for key in h.NARRATIVES:data[key]['parts']=copy.deepcopy(parts)
        data['major_integrated_risks']=[copy.deepcopy(data['agreement_explanation'])]
        data['evidence_roles']=[dict(namespace='FUNDAMENTAL',evidence_id=self.helper.fid,role='SUPPORTING'),
            dict(namespace='TECHNICAL',evidence_id=a['evidence_id'],role='CONFLICTING')]
        before=copy.deepcopy(data);view=self.assemble(data);out=view.analysis
        self.assertEqual(data,before)
        self.assertEqual(set(out),set(h._schema(self.packet)['required']))
        self.assertEqual(out['identity'],self.packet['identity'])
        self.assertEqual(out['acknowledged_limitations'],self.packet['limitations'])
        self.assertEqual(out['synthesis_confidence'],data['synthesis_confidence'])
        self.assertEqual(out['timing_posture'],data['timing_posture'])
        for statement in [*(out[k] for k in h.NARRATIVES),*out['major_integrated_risks']]:
            self.assertEqual(statement['text'],'  '+a['label']+' and '+b['label']+' inform interpretation.\n')
            self.assertEqual(statement['technical_evidence_ids'][:2],[a['evidence_id'],b['evidence_id']])
        self.assertEqual(out['supporting_fundamental_evidence_ids'],[self.helper.fid])
        self.assertEqual(out['conflicting_technical_evidence_ids'],[a['evidence_id']])
        self.assertEqual(out['supporting_technical_evidence_ids'],[])
        self.assertEqual(view.context,self.context)
        self.assertEqual(view.methodology_version,'horizon-synthesis-v2')
        self.assertEqual(view.invalidation_policy_version,'source-available-invalidation-v1')
        self.assertEqual(view.model,'offline-fixture')
        self.assertEqual(h._validate(out,self.packet),view.analysis_json)
        with self.assertRaises(FrozenInstanceError):view.model='changed'
        out['identity']['ticker']='changed';self.assertNotEqual(view.analysis['identity']['ticker'],'changed')

    def test_condition_lineage_wait_and_classification(self):
        for condition in ('F_INVALIDATION:0','T_CONFIRMATION:0'):
            data=self.helper.output();data['timing_posture']='WAIT_FOR_CONFIRMATION'
            data['synthesis_summary']=self.helper.statement([condition])
            if condition.startswith('F_'):
                # F summary grounding comes only from explicit condition lineage.
                data['synthesis_summary']['parts']=[p for p in data['synthesis_summary']['parts'] if p.get('namespace')!='FUNDAMENTAL']
            draft=d.validate_horizon_draft(data,self.context)
            self.assertIsNone(draft.synthesis_summary.classification)
            out=assemble_horizon_v2_offline(draft,self.context,model='fixture').analysis
            statement=out['synthesis_summary']
            self.assertEqual(statement['classification'],'FORECAST')
            self.assertEqual(statement['condition_ids'],[condition])
            source=self.packet['conditions'][condition]
            key='fundamental_evidence_ids' if condition.startswith('F_') else 'technical_evidence_ids'
            dependencies=source['evidence_refs' if condition.startswith('F_') else 'evidence_ids']
            self.assertTrue(set(dependencies)<=set(statement[key]))
        data=self.helper.output();data['agreement_explanation']['classification']='FORECAST'
        self.assertEqual(self.assemble(data).analysis['agreement_explanation']['classification'],'FORECAST')

    def test_public_prose_rejections_without_repair(self):
        for text,reason in [('Evidence rose 12 percent.','NUMERIC_PROSE'),('Buy now.','PROHIBITED_ACTION_LANGUAGE'),
                            ('Evidence could improve.','PREDICTIVE_TEXT_REQUIRES_FORECAST')]:
            data=self.helper.output();data['synthesis_summary']['parts'][0]['value']=text
            draft=d.validate_horizon_draft(data,self.context)
            with self.assertRaises(h.HorizonSynthesisError) as caught:
                assemble_horizon_v2_offline(draft,self.context,model='fixture')
            self.assertEqual(caught.exception.semantic_reason,'HORIZON_SYNTHESIS_'+reason)
            self.assertEqual(draft.synthesis_summary.parts[0].text,text)
        data=self.helper.output();data['synthesis_summary']['parts'][0]['value']='Evidence could improve.'
        data['synthesis_summary']['classification']='FORECAST';self.assemble(data)

    def test_revalidation_rejects_forged_drafts_and_context(self):
        draft=d.validate_horizon_draft(self.helper.output(),self.context)
        unknown=d.EvidenceSelection(d.Namespace.TECHNICAL,'FAKE')
        invalidpart=d.HorizonPart(d.PartKind.CITATION,selection=unknown)
        role=d.HorizonRole(unknown,d.Role.SUPPORTING)
        wrong=d.HorizonStatementDraft((invalidpart,),(), 'AI_INTERPRETATION')
        variants=[None,replace(draft,synthesis_summary=wrong),replace(draft,evidence_roles=(role,)),
                  replace(draft,invalidation_summary=replace(draft.invalidation_summary,condition_ids=(),classification='AI_INTERPRETATION')),
                  replace(draft,invalidation_summary=replace(draft.invalidation_summary,condition_ids=('T_CONFIRMATION:0',))),
                  replace(draft,timing_posture='WAIT_FOR_CONFIRMATION'),
                  replace(draft,invalidation_summary=replace(draft.invalidation_summary,classification='AI_INTERPRETATION'))]
        validrole=d.HorizonRole(d.EvidenceSelection(d.Namespace.TECHNICAL,self.helper.tid),d.Role.SUPPORTING)
        variants.append(replace(draft,evidence_roles=(validrole,replace(validrole,role=d.Role.CONFLICTING))))
        variants.append(replace(draft,invalidation_summary=replace(draft.invalidation_summary,condition_ids=('FAKE',))))
        variants.append(replace(draft,synthesis_summary=replace(draft.synthesis_summary,
            parts=tuple(p for p in draft.synthesis_summary.parts if p.selection is None or p.selection.namespace!=d.Namespace.FUNDAMENTAL))))
        variants.append(replace(draft,synthesis_summary=replace(draft.synthesis_summary,
            parts=(d.HorizonPart(d.PartKind.CITATION,selection=d.EvidenceSelection('INVALID',self.helper.tid)),))))

        for bad in variants:
            with self.assertRaises(d.HorizonDraftError):assemble_horizon_v2_offline(bad,self.context,model='fixture')
        from src.horizon_integration import SynthesisReadinessError
        with self.assertRaises(SynthesisReadinessError):
            assemble_horizon_v2_offline(draft,replace(self.context,primary_authority='FORGED'),model='fixture')
        unavailable=next(r['evidence_id'] for r in self.packet['technical']['catalog'] if r['value'] is None)
        for part in (d.HorizonPart(d.PartKind.FEATURE,selection=d.EvidenceSelection(d.Namespace.TECHNICAL,unavailable)),
                     d.HorizonPart(d.PartKind.TEXT,text=self.helper.label)):
            bad=replace(draft,synthesis_summary=replace(draft.synthesis_summary,parts=(*draft.synthesis_summary.parts,part)))
            with self.assertRaises(d.HorizonDraftError):assemble_horizon_v2_offline(bad,self.context,model='fixture')

    def test_absent_invalidations_and_namespace_serialization(self):
        contexts=[];original=h._packet
        def capture(context):contexts.append(context);return original(context)
        with patch.object(h,'_packet',side_effect=capture):
            v08.ContractConstructibilityAuditTests().exercise_source_invalidations()
        context=contexts[-1];packet=original(context)
        data=self.helper.output();data['timing_posture']=packet['allowed_postures'][0]
        data['invalidation_summary']=self.helper.statement()
        view=self.assemble(data,context)
        self.assertEqual(view.analysis['invalidation_summary']['condition_ids'],[])
        self.assertEqual(view.analysis['acknowledged_limitations'],packet['limitations'])
        self.assertIn('NO_SOURCE_INVALIDATION_CONDITION',view.analysis['acknowledged_limitations'])
        draft=d.validate_horizon_draft(data,context)
        for ref in ('FAKE','T_CONFIRMATION:0'):
            bad=replace(draft,invalidation_summary=replace(draft.invalidation_summary,condition_ids=(ref,),classification=None))
            with self.assertRaises(d.HorizonDraftError):assemble_horizon_v2_offline(bad,context,model='fixture')
        # Serialization unit: identical strings across namespaces remain independent.
        statement=d.HorizonStatementDraft((d.HorizonPart(d.PartKind.TEXT,text='Interpretation.'),
            d.HorizonPart(d.PartKind.CITATION,selection=d.EvidenceSelection(d.Namespace.FUNDAMENTAL,'SAME')),
            d.HorizonPart(d.PartKind.CITATION,selection=d.EvidenceSelection(d.Namespace.TECHNICAL,'SAME'))),(),'AI_INTERPRETATION')
        out=_statement_data(statement,self.packet)
        self.assertEqual(out['fundamental_evidence_ids'],['SAME'])
        self.assertEqual(out['technical_evidence_ids'],['SAME'])

    def test_v2_active_and_historical_combined_regression(self):
        self.helper.test_active_v2_generation()
        # Existing real orchestration fixture asserts one call per stage and source preservation.
        for horizon in ('SHORT','SWING','MEDIUM','LONG'):
            v08.CombinedPipelineTests().exercise(horizon)
        from src.generation_contracts import ACTIVE_TECHNICAL_VERSION,ACTIVE_HORIZON_VERSION
        self.assertEqual(ACTIVE_TECHNICAL_VERSION,'technical-analyst-v2')
        self.assertEqual(ACTIVE_HORIZON_VERSION,'horizon-synthesis-v2')
