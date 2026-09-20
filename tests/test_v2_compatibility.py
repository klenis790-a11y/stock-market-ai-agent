"""Assembled v2 public semantics, not relabeled v1, through existing consumers."""
import json
import tempfile
import unittest
from dataclasses import replace, asdict
from unittest.mock import patch, MagicMock
import test_v07 as v07
import test_v08 as v08
from src import technical_draft as td, horizon_draft as hd, horizon_synthesis as hs
from src.technical_assembly import assemble_technical_v2_offline
from src.horizon_assembly import assemble_horizon_v2_offline
from src.technical_signal_store import create_technical_signal_record, TechnicalSignalStore
from src import horizon_integration as integration
from src.technical_evaluation import prepare_technical_enrollment, evaluate_technical_signal, _validate_source
from src.observation_resolution import SUPPORTED_MARKET


class V2CompatibilityTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket.connect','src.openai_client.request_text'):
            guard=patch(name,side_effect=AssertionError('No live IO'))
            guard.start();self.addCleanup(guard.stop)
        self.helper=v07.TechnicalAnalystTests()
        self.snapshot,self.catalog=self.helper.fixture(200)

    def technical(self,signal='NEUTRAL',horizon='SHORT_TERM_1_TO_5_SESSIONS'):
        selected=next(i.evidence_id for i in self.catalog.items if i.label=='sma_200')
        statement=dict(parts=[dict(kind='FEATURE',value=selected),dict(kind='TEXT',value=' informs interpretation.')])
        data=dict(signal=signal,confidence=60,summary=statement,thesis=statement,
            evidence_roles=[dict(evidence_id=selected,role='SUPPORTING')],
            confirmation_conditions=[statement],invalidation_conditions=[] if signal=='NEUTRAL' else [statement],
            risk_notes=[statement],missing_data_acknowledgement='')
        draft=td.validate_technical_draft(data,self.snapshot,self.catalog,horizon)
        result=assemble_technical_v2_offline(draft,self.snapshot,self.catalog,horizon,model='fixture')
        return create_technical_signal_record(result,self.catalog,created_at='2025-03-11T13:00:00Z'),result

    def test_all_horizons_directions_signals_and_allowed_postures(self):
        from src.horizon_pipeline import CombinedResearchResult
        for horizon in ('SHORT','SWING','MEDIUM','LONG'):
            for recommendation in ('Accumulate','Hold','Avoid'):
                original=v08.fundamental()
                source=replace(original,record=replace(original.record,recommendation=recommendation))
                with patch.object(v08,'fundamental',return_value=source):
                    artifact=v08.FreshnessProvenanceTests()._pipeline('LONG' if horizon=='LONG' else 'MEDIUM')[0]
                for signal in ('BULLISH','NEUTRAL','BEARISH'):
                    record,_=self.technical(signal,integration.select_technical_horizon(horizon))
                    before=record.signal_json
                    context=integration.build_integration_context('TEST',horizon,v08.instant(),
                        fundamental=artifact,technical=record,integration_run_id='run-1')
                    integration.require_synthesis_ready(context)
                    self.assertEqual(context.technical.status,'ADMITTED')
                    self.assertEqual(context.primary_authority,'TECHNICAL_PRIMARY' if horizon in ('SHORT','SWING') else 'FUNDAMENTAL_PRIMARY')
                    self.assertEqual(context.risk_applicability_version,'risk-applicability-v1')
                    self.assertEqual(context.freshness_policy_version,'technical-freshness-v1')
                    self.assertEqual(context.fundamental_policy_version,'fundamental-provenance-v1')
                    packet=hs._packet(context)
                    fid=packet['fundamental']['catalog'][0]['evidence_id']
                    tid=record.signal['analysis']['supporting_evidence_ids'][0]
                    def statement(conditions=()):
                        value=dict(parts=[dict(kind='TEXT',value='The evidence informs interpretation.'),
                            dict(kind='CITATION',namespace='FUNDAMENTAL',evidence_id=fid),
                            dict(kind='CITATION',namespace='TECHNICAL',evidence_id=tid)])
                        value.update(condition_ids=list(conditions)) if conditions else value.update(classification='AI_INTERPRETATION')
                        return value
                    invalidations=sorted(hs._invalidation_ids(packet['conditions']))
                    for posture in packet['allowed_postures']:
                        data=dict(timing_posture=posture,synthesis_confidence=60,evidence_roles=[],major_integrated_risks=[statement()],
                                  **{key:statement() for key in hs.NARRATIVES})
                        data['invalidation_summary']=statement(invalidations[:1])
                        if posture=='WAIT_FOR_CONFIRMATION':data['synthesis_summary']=statement(['T_CONFIRMATION:0'])
                        draft=hd.validate_horizon_draft(data,context)
                        view=assemble_horizon_v2_offline(draft,context,model='fixture')
                        self.assertEqual(view.methodology_version,'horizon-synthesis-v2')
                        self.assertEqual(view.analysis['identity']['conflict_classification'],context.conflict.classification)
                        self.assertEqual(view.analysis['identity']['fundamental_recommendation'],recommendation)
                        self.assertEqual(view.analysis['identity']['technical_signal'],signal)
                        self.assertEqual(view.context,context)
                        self.assertEqual(view.invalidation_policy_version,'source-available-invalidation-v1')
                        wrapped=CombinedResearchResult(view,integration.TECHNICAL_HORIZON_SELECTION_VERSION,integration.COMBINED_RESEARCH_SEQUENCING_VERSION)
                        self.assertEqual(wrapped.technical_horizon_selection_version,'technical-horizon-selection-v1')
                        self.assertEqual(wrapped.sequencing_version,'combined-research-sequencing-v1')
                        self.assertEqual(hs._validate(view.analysis,packet),view.analysis_json)
                    self.assertEqual(record.signal_json,before)

    def test_evaluation_v1_v2_same_methodology_and_results(self):
        helper=v07.TechnicalEvaluationTests()
        for signal in ('BULLISH','NEUTRAL','BEARISH'):
            for horizon,length in (('SHORT_TERM_1_TO_5_SESSIONS',5),('SWING_1_TO_4_WEEKS',20)):
                v2,_=self.technical(signal,horizon)
                v1=helper.record(signal,horizon)
                results=[];targets=[]
                for record in (v1,v2):
                    enrolled=prepare_technical_enrollment(record,v07.dt('2025-03-11T13:01:00Z'),market=SUPPORTED_MARKET)
                    self.assertEqual(enrolled.horizon.length,length)
                    self.assertEqual(enrolled.methodology.version,'technical-signal-evaluation-v1')
                    self.assertEqual(enrolled.methodology.benchmark_symbol,'VOO')
                    results.append(evaluate_technical_signal(record,enrolled,*helper.observations(enrolled,105,104)))
                    targets.append(enrolled.methodology)
                self.assertEqual(targets[0],targets[1])
                for field in ('stock_return','excess_return','confidence_score','recommendation','completeness'):
                    self.assertEqual(getattr(results[0].evaluation,field),getattr(results[1].evaluation,field))
                self.assertEqual(results[0].directional_success,results[1].directional_success)
                self.assertEqual(results[0].benchmark_outperformance,results[1].benchmark_outperformance)

    def test_storage_dashboard_v1_and_real_v2(self):
        from src.dashboard import technical_research as page
        records=[v07.TechnicalEvaluationTests().record(),self.technical()[0]]
        with tempfile.TemporaryDirectory() as directory:
            store=TechnicalSignalStore(directory+'/versions.db');store.initialize()
            for record in records:
                before=(record.signal_json,record.evidence_json)
                store.save_technical_signal(record)
                loaded=store.get_technical_signal(record.record_id)
                self.assertEqual(loaded,record)
                self.assertEqual((loaded.signal_json,loaded.evidence_json),before)
                with patch.object(page,'st',MagicMock()) as ui:
                    page.show_interpretation(loaded.signal,loaded.evidence_packet)
                    texts=[str(c) for c in ui.mock_calls]
                    self.assertTrue(any(loaded.signal['analyst_methodology_version'] in text for text in texts))
                    ui.table.assert_called()
                    ui.write.assert_any_call(loaded.signal['analysis']['summary']['text'])

    def test_unknown_versions_and_policy_guards(self):
        record,_=self.technical()
        for version in ('technical-analyst-v3','horizon-synthesis-v3','unknown','technical-analyst-v2-extra','',None,[],3):
            signal=record.signal;signal['analyst_methodology_version']=version
            if not isinstance(version,str) or not version:
                with self.assertRaises(ValueError):replace(record,signal_json=json.dumps(signal))
                continue
            bad=replace(record,signal_json=json.dumps(signal))
            with self.assertRaises(ValueError):_validate_source(bad)
            self.assertIn('UNSUPPORTED_METHODOLOGY',integration.admit_technical(bad,'TEST',v08.instant()).reasons)
        signal=record.signal;signal['provenance']['feature_methodology']='unsupported'
        evidence=record.evidence_packet;evidence['provenance']['feature_methodology']='unsupported'
        bad=replace(record,signal_json=json.dumps(signal),evidence_json=json.dumps(evidence))
        with self.assertRaises(ValueError):_validate_source(bad)
        self.assertIn('UNSUPPORTED_METHODOLOGY',integration.admit_technical(bad,'TEST',v08.instant()).reasons)
        from src.generation_contracts import ASSEMBLY_CONTRACT_BY_GENERATION,ACTIVE_TECHNICAL_VERSION,ACTIVE_HORIZON_VERSION
        self.assertNotIn('technical-analyst-v1',ASSEMBLY_CONTRACT_BY_GENERATION)
        self.assertNotIn('horizon-synthesis-v1',ASSEMBLY_CONTRACT_BY_GENERATION)
        self.assertEqual(set(ASSEMBLY_CONTRACT_BY_GENERATION.values()),{'evidence-first-assembly-v1'})
        self.assertEqual((ACTIVE_TECHNICAL_VERSION,ACTIVE_HORIZON_VERSION),('technical-analyst-v2','horizon-synthesis-v2'))
