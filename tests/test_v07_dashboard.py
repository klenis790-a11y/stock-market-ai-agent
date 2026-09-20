"""Technical dashboard actions with synthetic evidence, temporary DBs and zero live IO."""
from src import technical_pipeline as backend
import unittest
import tempfile
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from datetime import datetime, timezone

from src.dashboard import technical_adapter as adapter
import test_v07 as fixtures
from test_v07 import dt


class TechnicalDashboardTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=self.directory.name+'/technical.db'
        for name in ('socket.socket.connect','src.configuration.load_local_environment'):
            guard=patch(name,side_effect=AssertionError('Network prohibited') if name.startswith('socket') else None)
            guard.start();self.addCleanup(guard.stop)

    def bundle(self,horizon=None):
        helper=fixtures.TechnicalAnalystTests();snapshot,catalog=helper.fixture()
        signal=helper.run_output(helper.output(catalog),snapshot,catalog,horizon)
        return adapter.TechnicalRun(snapshot,catalog,signal)

    def button(self,app,label):
        return next(b for b in app.button if b.label==label)

    def input(self,app,key):
        return next(w for w in app.text_input if w.key==key)

    def app(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'dashboard.py')).run()
        app.sidebar.radio[0].set_value('technical_research').run()
        self.assertFalse(app.exception)
        return app

    def test_explicit_pipeline_single_asof_horizon_and_stages(self):
        bundle=self.bundle(adapter.HORIZONS[1]);data=bundle.snapshot.historical_ohlcv
        with patch.object(backend,'retrieve_historical_ohlcv',return_value=data) as retrieval, patch.object(
            backend,'analyze_technical_snapshot',return_value=bundle.signal) as analyst:
            result=adapter.run_technical_research(' test ',adapter.HORIZONS[1],data.requested_as_of,market_verified=True)
            retrieval.assert_called_once_with('TEST',data.requested_as_of,market='US_EQUITY_ETF_XNYS')
            analyst.assert_called_once()
            self.assertEqual(analyst.call_args.args[2],adapter.HORIZONS[1])
            self.assertEqual(result.catalog.provenance.requested_as_of,data.requested_as_of)
            self.assertEqual(result.signal,bundle.signal)
        with patch.object(backend,'retrieve_historical_ohlcv') as retrieval:
            for horizon,verified in (('invalid',True),(adapter.HORIZONS[0],False)):
                with self.assertRaises(adapter.TechnicalActionError):adapter.run_technical_research('TEST',horizon,data.requested_as_of,market_verified=verified)
            retrieval.assert_not_called()

    def test_page_load_rerun_horizon_and_failure_clear_bundle(self):
        bundle=self.bundle()
        with patch.object(adapter,'run_technical_research',return_value=bundle) as run, patch(
            'src.alpha_vantage_client.get_daily_raw') as av, patch('src.openai_client.request_text') as ai:
            app=self.app()
            app.selectbox[0].set_value(adapter.HORIZONS[1]).run()
            app.run();run.assert_not_called();av.assert_not_called();ai.assert_not_called()
            self.input(app,'tech_ticker').set_value('TEST')
            self.button(app,'Run Technical Research').click().run()
            self.assertFalse(app.exception);run.assert_called_once()
            self.assertIn('TEST',app.subheader[0].value)
            self.assertTrue(any('not a trade instruction' in c.value for c in app.caption))
            app.run();app.sidebar.radio[0].set_value('home').run()
            app.sidebar.radio[0].set_value('technical_research').run();run.assert_called_once()
            run.side_effect=adapter.TechnicalActionError('Technical analyst unavailable.')
            self.input(app,'tech_ticker').set_value('MSFT')
            self.button(app,'Run Technical Research').click().run()
            self.assertEqual(run.call_count,2);self.assertFalse(app.exception)
            self.assertNotIn('tech_run',app.session_state)
            self.assertFalse(any(b.label=='Save Technical Signal' for b in app.button))
            av.assert_not_called();ai.assert_not_called()

    def test_save_history_exact_duplicate_and_no_source_creation_on_read(self):
        bundle=self.bundle()
        with patch('src.openai_client.request_text',side_effect=AssertionError('No AI')),patch(
            'src.alpha_vantage_client.get_daily_raw',side_effect=AssertionError('No retrieval')):
            record=adapter.prepare_save(bundle,dt('2025-03-11T13:00:00Z'))
            self.assertFalse(Path(self.path).exists())
            with self.assertRaises(adapter.TechnicalActionError):adapter.load_history(self.path,'TEST')
            self.assertFalse(Path(self.path).exists())
            self.assertEqual(adapter.save_signal(record,self.path),record)
            self.assertEqual(adapter.save_signal(record,self.path),record)
            before=Path(self.path).read_bytes()
            self.assertEqual(adapter.load_history(self.path,' test '),[record])
            self.assertEqual(record.evidence_packet,adapter.load_history(self.path,'TEST')[0].evidence_packet)
            self.assertEqual(Path(self.path).read_bytes(),before)
            view=adapter.evaluation_view(self.path,record,dt('2025-03-11T13:01:00Z'),market_verified=True)
            self.assertTrue(view['can_enroll']);self.assertFalse(view['can_collect'])
            self.assertEqual(adapter.summary(self.path,[record])['total_enrolled'],0)

    def test_save_button_duplicate_and_historical_render_no_research(self):
        bundle=self.bundle()
        with patch.object(adapter,'run_technical_research',return_value=bundle) as run, patch.object(
            adapter,'now',return_value=dt('2025-03-11T13:00:00Z')):
            app=self.app();self.input(app,'tech_ticker').set_value('TEST')
            self.button(app,'Run Technical Research').click().run()
            self.input(app,'tech_db_path').set_value(self.path).run()
            self.button(app,'Save Technical Signal').click().run()
            self.assertFalse(app.exception)
            first=adapter.load_history(self.path,'TEST')[0]
            self.button(app,'Save Technical Signal').click().run()
            self.assertFalse(app.exception);self.assertEqual(adapter.load_history(self.path,'TEST'),[first])
            app.run();run.assert_called_once()
            self.assertFalse(any(b.label=='Collect Evaluation Observation' for b in app.button))

    def test_prospective_enrollment_status_and_no_automatic_collection(self):
        bundle=self.bundle();record=adapter.prepare_save(bundle,dt('2025-03-11T13:00:00Z'))
        adapter.save_signal(record,self.path)
        with patch('src.alpha_vantage_client.get_daily_adjusted') as provider:
            e=adapter.enroll(self.path,record.record_id,dt('2025-03-11T13:01:00Z'),market_verified=True)
            self.assertEqual(adapter.enroll(self.path,record.record_id,dt('2025-03-11T13:02:00Z'),market_verified=True),e)
            view=adapter.evaluation_view(self.path,record,dt('2025-03-11T14:00:00Z'),market_verified=True)
            self.assertFalse(view['can_collect']);self.assertEqual(view['target'].eligibility,'NOT_YET_ELIGIBLE')
            with self.assertRaises(adapter.TechnicalActionError):adapter.collect(self.path,e.enrollment_id,dt('2025-03-11T14:00:00Z'),market_verified=True)
            provider.assert_not_called()
        other=replace(record,record_id='late');adapter.save_signal(other,self.path)
        view=adapter.evaluation_view(self.path,other,dt('2025-06-01T00:00:00Z'),market_verified=True)
        self.assertFalse(view['can_enroll'])
        with self.assertRaises(adapter.TechnicalActionError):adapter.enroll(self.path,other.record_id,dt('2025-06-01T00:00:00Z'),market_verified=True)

    def test_collection_exact_backend_and_display_partial_neutral_denominators(self):
        from src.technical_evaluation import resolve_technical_target
        bundle=self.bundle();record=adapter.prepare_save(bundle,dt('2025-03-11T13:00:00Z'))
        adapter.save_signal(record,self.path)
        e=adapter.enroll(self.path,record.record_id,dt('2025-03-11T13:01:00Z'),market_verified=True)
        target=resolve_technical_target(e,dt('2025-06-01T00:00:00Z'))
        payload={'Meta Data':{'2. Symbol':'TEST'},'Time Series (Daily)':{
            target.reference.date.isoformat():{'5. adjusted close':'100'},target.target.date.isoformat():{'5. adjusted close':'105'}}}
        with patch('src.alpha_vantage_client.get_daily_adjusted',side_effect=[payload,RuntimeError('private body')]) as provider:
            view=adapter.evaluation_view(self.path,record,dt('2025-06-01T00:00:00Z'),market_verified=True)
            self.assertTrue(view['can_collect']);provider.assert_not_called()
            adapter.collect(self.path,e.enrollment_id,dt('2025-06-01T00:00:00Z'),market_verified=True)
            self.assertEqual(provider.call_count,2)
            view=adapter.evaluation_view(self.path,record,dt('2025-06-01T00:00:00Z'),market_verified=True)
            self.assertFalse(view['can_collect']);self.assertEqual(provider.call_count,2)
            rows=adapter.result_rows(view['result'])
            self.assertEqual(rows[0]['Value'],'5.00%');self.assertEqual(rows[1]['Value'],'Unavailable')
            self.assertIn('Not defined',rows[3]['Value'])
            summary=adapter.summary(self.path,[record])
            self.assertEqual(summary['evaluated_count'],1);self.assertEqual(summary['directional_count'],0)
            self.assertEqual(summary['benchmark_count'],0);self.assertEqual(provider.call_count,2)

    def test_classification_citations_and_directional_display(self):
        bundle=self.bundle();packet=bundle.catalog.to_packet()
        rows=adapter.evidence_rows(packet)
        self.assertEqual(rows[0]['Classification'],'RETRIEVED FACT')
        rsi=next(r for r in rows if r['Evidence']=='rsi_14')
        self.assertEqual(rsi['Classification'],'CALCULATED METRIC')
        missing=next(r for r in rows if r['Evidence']=='sma_200')
        self.assertEqual(missing['Value'],'Unavailable');self.assertNotEqual(missing['Availability'],'Available')
        refs=bundle.signal.analysis.supporting_evidence_ids
        self.assertEqual([r['ID'] for r in adapter.evidence_rows(packet,refs)],list(refs))
        from test_v07 import TechnicalEvaluationTests
        helper=TechnicalEvaluationTests()
        from src.technical_evaluation import prepare_technical_enrollment,evaluate_technical_signal
        for signal,end,expected in (('BULLISH',105,'True'),('BULLISH',95,'False'),('BEARISH',95,'True'),('BEARISH',105,'False')):
            record=helper.record(signal);e=prepare_technical_enrollment(record,dt('2025-03-11T13:01:00Z'),market='US_EQUITY_ETF_XNYS')
            result=evaluate_technical_signal(record,e,*helper.observations(e,end,104))
            self.assertEqual(adapter.result_rows(result)[3]['Value'],expected)

    def test_error_sanitization_stage_boundaries(self):
        bundle=self.bundle();data=bundle.snapshot.historical_ohlcv
        for stage,name in (('MARKET_DATA','retrieve_historical_ohlcv'),('FEATURES','build_technical_feature_snapshot'),
                           ('EVIDENCE','build_technical_evidence_catalog'),('TECHNICAL_ANALYST','analyze_technical_snapshot')):
            with patch.object(backend,'retrieve_historical_ohlcv',return_value=data),patch.object(backend,name,side_effect=RuntimeError('SECRET raw prompt provider body')), self.assertLogs('src.dashboard.technical_adapter',level='ERROR') as logs:
                with self.assertRaises(adapter.TechnicalActionError) as caught:adapter.run_technical_research('TEST',adapter.HORIZONS[0],data.requested_as_of,market_verified=True)
            self.assertIn('stage='+stage,logs.output[0]);self.assertNotIn('SECRET',logs.output[0]);self.assertNotIn('SECRET',str(caught.exception))
        record=adapter.prepare_save(bundle,dt('2025-03-11T13:00:00Z'))
        for stage,call in (('SAVE',lambda:adapter.save_signal(record,'')),
                           ('ENROLLMENT',lambda:adapter.enroll('',record.record_id,data.requested_as_of,market_verified=True)),
                           ('COLLECTION',lambda:adapter.collect('','id',data.requested_as_of,market_verified=True))):
            with self.assertLogs('src.dashboard.technical_adapter',level='ERROR') as logs:
                with self.assertRaises(adapter.TechnicalActionError):call()
            self.assertIn('stage='+stage,logs.output[0])
