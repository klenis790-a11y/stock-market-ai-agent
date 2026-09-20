"""Normal production v2 request paths with providers blocked and responses mocked."""
import copy
import json
import unittest
from contextlib import ExitStack
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
import test_v07 as v07
import test_v08 as v08
from src import technical_analyst as ta, technical_pipeline as tp
from src import horizon_synthesis as hs, horizon_pipeline as hp, horizon_integration as hi
from src import technical_draft as td, horizon_draft as hd
from src.openai_client import request_text as REAL_REQUEST


def technical_output(catalog, signal='BULLISH'):
    available = [i for i in catalog.items if i.value is not None]
    item = next((i for i in available if i.label == 'sma_200'), available[0])
    statement = dict(parts=[dict(kind='FEATURE', value=item.evidence_id),
                           dict(kind='TEXT', value=' informs interpretation.')])
    return dict(signal=signal, confidence=60, summary=copy.deepcopy(statement),
        thesis=copy.deepcopy(statement), evidence_roles=[dict(evidence_id=item.evidence_id, role='SUPPORTING')],
        confirmation_conditions=[copy.deepcopy(statement)],
        invalidation_conditions=[] if signal == 'NEUTRAL' else [copy.deepcopy(statement)],
        risk_notes=[copy.deepcopy(statement)], missing_data_acknowledgement=
            'Missing evidence limits confidence.' if any(i.value is None for i in catalog.items) else '')


def horizon_output(packet, posture=None):
    fid = packet['fundamental']['catalog'][0]['evidence_id']
    tid = next(i['evidence_id'] for i in packet['technical']['catalog'] if i['value'] is not None)
    def statement(conditions=()):
        value = dict(parts=[dict(kind='TEXT', value='Evidence informs interpretation.'),
            dict(kind='CITATION', namespace='FUNDAMENTAL', evidence_id=fid),
            dict(kind='FEATURE', namespace='TECHNICAL', evidence_id=tid)])
        if conditions: value['condition_ids'] = list(conditions)
        else: value['classification'] = 'AI_INTERPRETATION'
        return value
    data = dict(timing_posture=posture or packet['allowed_postures'][0], synthesis_confidence=60,
        evidence_roles=[dict(namespace='FUNDAMENTAL', evidence_id=fid, role='SUPPORTING'),
                        dict(namespace='TECHNICAL', evidence_id=tid, role='CONFLICTING')],
        major_integrated_risks=[statement()], **{n:statement() for n in hs.NARRATIVES})
    data['invalidation_summary'] = statement(sorted(hs._invalidation_ids(packet['conditions']))[:1])
    if data['timing_posture'] == 'WAIT_FOR_CONFIRMATION':
        data['synthesis_summary'] = statement([next(iter(packet['conditions']))])
    return data


class V2ActivationTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket.connect', 'src.openai_client.request_text', 'sqlite3.connect'):
            guard = patch(target, side_effect=AssertionError('Unmocked external operation'))
            guard.start(); self.addCleanup(guard.stop)
        self.snapshot, self.catalog = v07.TechnicalAnalystTests().fixture(200)

    def technical_call(self, data, snapshot=None, catalog=None, horizon=ta.HORIZONS[0]):
        snapshot, catalog = snapshot or self.snapshot, catalog or self.catalog
        with patch('src.openai_client.request_text', return_value=json.dumps(data)) as request:
            try:
                return ta.analyze_technical_snapshot(snapshot, catalog, horizon)
            finally:
                request.assert_called_once()
                self.assertEqual(request.call_args.kwargs['text']['format']['schema'], td.SCHEMA)
                self.assertTrue(request.call_args.kwargs['require_completed'])

    def context(self):
        helper = v08.HorizonSynthesisTests(); helper.setUp(); self.addCleanup(helper.doCleanups)
        return helper.context

    def horizon_call(self, data, context):
        with patch('src.openai_client.request_text', return_value=json.dumps(data)) as request:
            try: return hs.synthesize_horizon(context)
            finally:
                request.assert_called_once()
                self.assertEqual(request.call_args.kwargs['text']['format']['schema'], hd.SCHEMA)
                self.assertTrue(request.call_args.kwargs['require_completed'])

    def test_technical_signals_horizons_and_bound_sma200(self):
        for signal in ('BULLISH','NEUTRAL','BEARISH'):
            for horizon in ta.HORIZONS:
                data=technical_output(self.catalog,signal)
                extra=next(i.evidence_id for i in self.catalog.items if i.label=='momentum_5')
                data['evidence_roles'].append(dict(evidence_id=extra,role='CONFLICTING'))
                result=self.technical_call(data,horizon=horizon)
                self.assertEqual(result.analyst_methodology_version,'technical-analyst-v2')
                self.assertEqual(result.horizon,horizon)
                self.assertEqual(result.analysis.signal,signal)
                self.assertEqual(result.analysis.confidence,60)
                selected=data['summary']['parts'][0]['value']
                self.assertEqual(result.analysis.summary.text,'sma_200 informs interpretation.')
                self.assertEqual(result.analysis.summary.evidence_ids,(selected,))
                self.assertEqual(result.analysis.conflicting_evidence_ids,(extra,))
                self.assertEqual(len(result.analysis.confirmation_conditions),1)
                self.assertEqual(len(result.analysis.invalidation_conditions),signal!='NEUTRAL')
                self.assertFalse(result.analysis.missing_evidence_ids)
        snapshot,catalog=v07.TechnicalAnalystTests().fixture()
        result=self.technical_call(technical_output(catalog),snapshot,catalog)
        self.assertEqual(result.analysis.missing_evidence_ids,tuple(i.evidence_id for i in catalog.items if i.value is None))

    def test_technical_failure_matrix_normal_path(self):
        cases=[('unknown',lambda x:x['summary']['parts'][0].update(value='UNKNOWN'),td.DraftReason.SELECTION.value),
            ('raw',lambda x:x['summary']['parts'].append(dict(kind='TEXT',value='sma_200')),td.DraftReason.UNBOUND.value),
            ('roles',lambda x:x['evidence_roles'].append(dict(evidence_id=x['evidence_roles'][0]['evidence_id'],role='CONFLICTING')),td.DraftReason.ROLE_DUPLICATE.value),
            ('confirmation',lambda x:x.update(confirmation_conditions=[]),td.DraftReason.CONDITIONS.value),
            ('invalidation',lambda x:x.update(invalidation_conditions=[]),td.DraftReason.CONDITIONS.value)]
        for name,mutate,reason in cases:
            data=technical_output(self.catalog);mutate(data)
            with self.subTest(name=name),self.assertRaises(ta.TechnicalGenerationError) as caught:self.technical_call(data)
            self.assertEqual(caught.exception.validation_reason,reason)
            self.assertEqual(caught.exception.substage,'DRAFT_VALIDATION')
        data=technical_output(self.catalog,'BEARISH');data['invalidation_conditions']=[]
        with self.assertRaises(ta.TechnicalGenerationError) as caught:self.technical_call(data)
        self.assertEqual(caught.exception.validation_reason,td.DraftReason.CONDITIONS.value)
        for text,reason in [('Buy now.','PROHIBITED_CLAIM'),('Evidence rose 12 percent.','NUMERIC_PROSE'),('The thesis is bearish.','SIGNAL_THESIS_CONFLICT')]:
            data=technical_output(self.catalog);data['summary']['parts']=[dict(kind='TEXT',value=text),dict(kind='CITATION',value=data['evidence_roles'][0]['evidence_id'])]
            with self.assertRaises(ta.TechnicalGenerationError) as caught:self.technical_call(data)
            self.assertEqual(caught.exception.substage,'PUBLIC_VALIDATION')
            self.assertEqual(caught.exception.validation_reason,'TECHNICAL_ANALYST_'+reason)
            self.assertNotIn(text,str(caught.exception)+repr(vars(caught.exception)))
        snapshot,catalog=v07.TechnicalAnalystTests().fixture()
        for unavailable in (False,True):
            data=technical_output(catalog)
            if unavailable:data['summary']['parts'][0]['value']=next(i.evidence_id for i in catalog.items if i.value is None)
            else:data['missing_data_acknowledgement']=''
            with self.assertRaises(ta.TechnicalGenerationError) as caught:self.technical_call(data,snapshot,catalog)
            self.assertEqual(caught.exception.validation_reason,(td.DraftReason.SELECTION if unavailable else td.DraftReason.MISSING_NOTE).value)

    def test_horizon_postures_identity_lineage_and_absence(self):
        context=self.context();packet=hs._packet(context)
        for posture in packet['allowed_postures']:
            data=horizon_output(packet,posture);view=self.horizon_call(data,context)
            self.assertEqual(view.methodology_version,'horizon-synthesis-v2')
            self.assertEqual(view.analysis['identity'],packet['identity'])
            self.assertEqual(view.analysis['acknowledged_limitations'],packet['limitations'])
            self.assertEqual(view.analysis['invalidation_summary']['classification'],'FORECAST')
            self.assertNotIn('classification',data['invalidation_summary'])
            self.assertNotIn('identity',data);self.assertNotIn('acknowledged_limitations',data)
            self.assertEqual(hs._validate(view.analysis,packet),view.analysis_json)
        contexts=[];original=hs._packet
        def capture(ctx):contexts.append(ctx);return original(ctx)
        with patch.object(hs,'_packet',side_effect=capture):
            v08.ContractConstructibilityAuditTests().exercise_source_invalidations()
        context=contexts[-1];packet=original(context)
        view=self.horizon_call(horizon_output(packet),context)
        self.assertFalse(view.analysis['invalidation_summary']['condition_ids'])
        self.assertIn('NO_SOURCE_INVALIDATION_CONDITION',view.analysis['acknowledged_limitations'])

    def test_horizon_failure_matrix_normal_path(self):
        context=self.context();packet=hs._packet(context)
        unavailable=next(i['evidence_id'] for i in packet['technical']['catalog'] if i['value'] is None)
        cases=[('unknown',lambda x:x['synthesis_summary']['parts'][1].update(evidence_id='UNKNOWN'),hd.Reason.EVIDENCE),
            ('unavailable',lambda x:x['synthesis_summary']['parts'][2].update(evidence_id=unavailable),hd.Reason.EVIDENCE),
            ('raw',lambda x:x['synthesis_summary']['parts'][0].update(value='sma_200'),hd.Reason.UNBOUND),
            ('roles',lambda x:x['evidence_roles'].append(dict(x['evidence_roles'][0],role='CONFLICTING')),hd.Reason.ROLE),
            ('condition',lambda x:x['invalidation_summary'].update(condition_ids=['FAKE']),hd.Reason.CONDITION),
            ('invalidation',lambda x:x.update(invalidation_summary=copy.deepcopy(x['agreement_explanation'])),hd.Reason.INVALIDATION),
            ('substitution',lambda x:x['invalidation_summary'].update(condition_ids=['T_CONFIRMATION:0']),hd.Reason.INVALIDATION),
            ('WAIT',lambda x:x.update(timing_posture='WAIT_FOR_CONFIRMATION'),hd.Reason.WAIT),
            ('namespace',lambda x:x['synthesis_summary']['parts'].pop(1),hd.Reason.GROUNDING)]
        for name,mutate,reason in cases:
            data=horizon_output(packet,'FAVORABLE_NOW');mutate(data)
            with self.subTest(name=name),self.assertRaises(hs.HorizonSynthesisError) as caught:self.horizon_call(data,context)
            self.assertEqual(caught.exception.draft_reason,reason.value)
            self.assertEqual(caught.exception.substage,'DRAFT_VALIDATION')
        for text,reason in [('Evidence rose 12 percent.','NUMERIC_PROSE'),('Buy now.','PROHIBITED_ACTION_LANGUAGE'),('Evidence could improve.','PREDICTIVE_TEXT_REQUIRES_FORECAST')]:
            data=horizon_output(packet);data['agreement_explanation']['parts'][0]['value']=text
            with self.assertRaises(hs.HorizonSynthesisError) as caught:self.horizon_call(data,context)
            self.assertEqual(caught.exception.semantic_reason,'HORIZON_SYNTHESIS_'+reason)
            self.assertEqual(caught.exception.substage,'PUBLIC_VALIDATION')
            self.assertNotIn(text,str(caught.exception)+repr(vars(caught.exception)))

    def test_combined_normal_v2_all_horizons(self):
        for horizon in ('SHORT','SWING','MEDIUM','LONG'):
            artifact=v08.FreshnessProvenanceTests()._pipeline('LONG' if horizon=='LONG' else 'MEDIUM')[0]
            events=[];signals=[];views=[]
            def request(**kwargs):
                name=kwargs['text']['format']['name'];events.append(name)
                if name=='technical_analysis_v2':return json.dumps(technical_output(self.catalog))
                self.assertEqual(name,'horizon_synthesis_v2')
                return json.dumps(horizon_output(json.loads(kwargs['input'])))
            def fundamental(*args,**kwargs):
                events.append('fundamental');self.assertFalse(kwargs['persist_decision'])
                self.assertEqual(kwargs['integration_run_id'],'run-1')
                kwargs['on_fundamental_artifact'](artifact)
                return artifact.analysis
            def analyst(*args):
                signal=ta.analyze_technical_snapshot(*args);signals.append(signal);return signal
            def synthesis(context):
                view=hs.synthesize_horizon(context);views.append(view);return view
            with patch.object(tp,'retrieve_historical_ohlcv',return_value=self.snapshot.historical_ohlcv) as retrieve, \
                 patch.object(tp,'analyze_technical_snapshot',side_effect=analyst) as a, \
                 patch.object(hp,'run_technical_research',wraps=tp.run_technical_research) as t, \
                 patch.object(hp,'run_stock_research',side_effect=fundamental) as f, \
                 patch.object(hp,'synthesize_horizon',side_effect=synthesis) as h, \
                 patch('src.openai_client.request_text',side_effect=request) as model, \
                 patch.object(hp,'uuid4',return_value=SimpleNamespace(hex='run-1')), \
                 patch.object(hp,'datetime') as clock:
                clock.now.return_value=v08.instant('2025-03-11T13:00:00+00:00')
                clock.fromisoformat.side_effect=datetime.fromisoformat
                result=hp.run_horizon_research('TEST',horizon,fundamental_horizon='LONG' if horizon=='LONG' else 'MEDIUM',
                    technical_as_of=self.snapshot.historical_ohlcv.requested_as_of,market_verified=True)
                for call in (retrieve,a,t,f,h):call.assert_called_once()
                self.assertEqual(model.call_count,2)
            self.assertEqual(events,['technical_analysis_v2','fundamental','horizon_synthesis_v2'])
            self.assertEqual(signals[0].analyst_methodology_version,'technical-analyst-v2')
            self.assertEqual(signals[0].horizon,hi.select_technical_horizon(horizon))
            self.assertEqual(result.view.methodology_version,'horizon-synthesis-v2')
            self.assertEqual(result.view.context.primary_authority,'TECHNICAL_PRIMARY' if horizon in ('SHORT','SWING') else 'FUNDAMENTAL_PRIMARY')
            self.assertEqual(result.view.context.integration_as_of,artifact.verified()['available_at'])
            hi.require_synthesis_ready(result.view.context)

    def test_diagnostic_boundaries_and_no_partial_outputs(self):
        for response,stage in [('SECRET','DRAFT_DECODING'),('', 'RESPONSE_EXTRACTION'),('{}','DRAFT_VALIDATION')]:
            with patch.object(tp,'retrieve_historical_ohlcv',return_value=self.snapshot.historical_ohlcv), \
                 patch('src.openai_client.request_text',return_value=response) as call, \
                 patch.object(hp,'run_stock_research') as fundamental:
                with self.assertRaises(hp.HorizonPipelineError) as caught:
                    hp.run_horizon_research('TEST','MEDIUM',fundamental_horizon='MEDIUM',technical_as_of=self.catalog.provenance.requested_as_of,market_verified=True)
                self.assertEqual(caught.exception.generation_substage,stage)
                self.assertNotIn('SECRET',str(caught.exception)+repr(vars(caught.exception)))
                call.assert_called_once();fundamental.assert_not_called()
        context=self.context()
        for response,stage in [('SECRET','DRAFT_DECODING'),('', 'RESPONSE_EXTRACTION'),('{}','DRAFT_VALIDATION')]:
            with patch('src.openai_client.request_text',return_value=response) as call:
                with self.assertRaises(hs.HorizonSynthesisError) as caught:hs.synthesize_horizon(context)
                self.assertEqual(caught.exception.substage,stage)
                self.assertNotIn('SECRET',str(caught.exception)+repr(vars(caught.exception)))
                call.assert_called_once()
        for detail in ('max_output_tokens','content_filter','not_completed','empty_output_text','SECRET'):
            error=RuntimeError('SECRET');error.synthesis_failure_type='RESPONSE_EXTRACTION';error.synthesis_response_detail=detail
            for invoke in (lambda:ta.analyze_technical_snapshot(self.snapshot,self.catalog,ta.HORIZONS[0]),lambda:hs.synthesize_horizon(context)):
                with patch('src.openai_client.request_text',side_effect=error) as call:
                    with self.assertRaises((ta.TechnicalGenerationError,hs.HorizonSynthesisError)) as caught:invoke()
                    self.assertEqual(caught.exception.response_detail,None if detail=='SECRET' else detail)
                    self.assertNotIn('SECRET',str(caught.exception)+repr(vars(caught.exception)))
                    call.assert_called_once()

    def test_horizon_diagnostics_through_combined_boundary(self):
        artifact=v08.FreshnessProvenanceTests()._pipeline('MEDIUM')[0]
        signal=self.technical_call(technical_output(self.catalog))
        run=tp.TechnicalRun(self.snapshot,self.catalog,signal)
        cases=[('SECRET','DRAFT_DECODING',None,None),
               ('{}','DRAFT_VALIDATION',hd.Reason.SHAPE.value,None),
               ('numeric','PUBLIC_VALIDATION',None,'HORIZON_SYNTHESIS_NUMERIC_PROSE')]
        for response,stage,draft_reason,semantic in cases:
            def request(**kwargs):
                if response!='numeric':return response
                data=horizon_output(json.loads(kwargs['input']))
                data['agreement_explanation']['parts'][0]['value']='Evidence rose 12 percent.'
                return json.dumps(data)
            def fundamental(*args,**kwargs):kwargs['on_fundamental_artifact'](artifact)
            with patch.object(hp,'run_technical_research',return_value=run), \
                 patch.object(hp,'run_stock_research',side_effect=fundamental), \
                 patch.object(hp,'datetime') as clock, \
                 patch.object(hp,'uuid4',return_value=SimpleNamespace(hex='run-1')), \
                 patch('src.openai_client.request_text',side_effect=request) as call:
                clock.now.return_value=v08.instant('2025-03-11T13:00:00+00:00')
                clock.fromisoformat.side_effect=datetime.fromisoformat
                with self.assertRaises(hp.HorizonPipelineError) as caught:
                    hp.run_horizon_research('TEST','MEDIUM',fundamental_horizon='MEDIUM',
                        technical_as_of=self.catalog.provenance.requested_as_of,market_verified=True)
                self.assertEqual(caught.exception.stage,'HORIZON_SYNTHESIS')
                self.assertEqual(caught.exception.substage,stage)
                self.assertEqual(caught.exception.draft_reason,draft_reason)
                self.assertEqual(caught.exception.semantic_reason,semantic)
                self.assertNotIn('SECRET',str(caught.exception)+repr(vars(caught.exception)))
                call.assert_called_once()

    def test_actual_request_helper_uses_single_mocked_sdk_call(self):
        from src import openai_client
        # The outer network guard remains in force. Only SDK transport is mocked.
        context=self.context()
        for data,invoke in [(technical_output(self.catalog),lambda:ta.analyze_technical_snapshot(self.snapshot,self.catalog,ta.HORIZONS[0])),
                            (horizon_output(hs._packet(context)),lambda:hs.synthesize_horizon(context))]:
            with patch.dict('os.environ',{'OPENAI_API_KEY':'unit-test-placeholder'}), \
                 patch.object(openai_client,'request_text',REAL_REQUEST), \
                 patch.object(openai_client,'OpenAI') as client:
                api=client.return_value.__enter__.return_value
                api.responses.create.return_value=SimpleNamespace(status='completed',output_text=json.dumps(data))
                result=invoke()
                self.assertIsNotNone(result)
                api.responses.create.assert_called_once()
                self.assertEqual(client.call_args.kwargs['max_retries'],0)
                self.assertFalse(api.responses.create.call_args.kwargs['store'])

    def test_assembly_and_preflight_revalidation_keep_fixed_reasons(self):
        for target,error,stage,reason in [
            ('src.technical_draft.validate_technical_draft',ta.TechnicalValidationError('TECHNICAL_ANALYST_CATALOG_MISMATCH'),'DRAFT_VALIDATION','TECHNICAL_ANALYST_CATALOG_MISMATCH'),
            ('src.technical_assembly.assemble_technical_v2_offline',td.TechnicalDraftError(td.DraftReason.SELECTION),'ASSEMBLY',td.DraftReason.SELECTION.value),
            ('src.technical_assembly.assemble_technical_v2_offline',RuntimeError('SECRET'),'ASSEMBLY',None)]:
            with patch(target,side_effect=error),self.assertRaises(ta.TechnicalGenerationError) as caught:
                self.technical_call(technical_output(self.catalog))
            self.assertEqual(caught.exception.substage,stage)
            self.assertEqual(caught.exception.validation_reason,reason)
            self.assertNotIn('SECRET',str(caught.exception)+repr(vars(caught.exception)))
        context=self.context();data=horizon_output(hs._packet(context))
        for target in ('src.horizon_draft.validate_horizon_draft','src.horizon_assembly.assemble_horizon_v2_offline'):
            with patch(target,side_effect=hi.SynthesisReadinessError(('SOURCE_UNAVAILABLE',))),self.assertRaises(hi.SynthesisReadinessError) as caught:
                self.horizon_call(data,context)
            self.assertEqual(caught.exception.reasons,('SOURCE_UNAVAILABLE',))
        for error,reason in [(hd.HorizonDraftError(hd.Reason.EVIDENCE),hd.Reason.EVIDENCE.value),(RuntimeError('SECRET'),None)]:
            with patch('src.horizon_assembly.assemble_horizon_v2_offline',side_effect=error),self.assertRaises(hs.HorizonSynthesisError) as caught:
                self.horizon_call(data,context)
            self.assertEqual(caught.exception.substage,'ASSEMBLY')
            self.assertEqual(caught.exception.draft_reason,reason)
            self.assertNotIn('SECRET',str(caught.exception)+repr(vars(caught.exception)))


    def test_condition_lineage_supplements_explicit_selection(self):
        context=self.context();packet=hs._packet(context)
        data=horizon_output(packet,'WAIT_FOR_CONFIRMATION')
        data['synthesis_summary']=dict(parts=[dict(kind='TEXT',value='Evidence informs interpretation.')],
            condition_ids=['F_INVALIDATION:0','T_CONFIRMATION:0'])
        # Both source namespaces are available through lineage, but that does not
        # replace the approved v2 requirement for an explicit analytical selection.
        with self.assertRaises(hs.HorizonSynthesisError) as caught:self.horizon_call(data,context)
        self.assertEqual(caught.exception.draft_reason,hd.Reason.GROUNDING.value)
        tid=next(i['evidence_id'] for i in packet['technical']['catalog'] if i['value'] is not None)
        data['synthesis_summary']['parts'].append(dict(kind='CITATION',namespace='TECHNICAL',evidence_id=tid))
        with patch('src.openai_client.request_text',return_value=json.dumps(data)) as request:
            view=hs.synthesize_horizon(context)
        request.assert_called_once()
        self.assertIn('at least one explicit FEATURE or CITATION selection',request.call_args.kwargs['instructions'])
        summary=view.analysis['synthesis_summary']
        self.assertEqual(summary['classification'],'FORECAST')
        self.assertTrue(summary['fundamental_evidence_ids'])
        self.assertIn(tid,summary['technical_evidence_ids'])
        self.assertNotIn('identity',data)
