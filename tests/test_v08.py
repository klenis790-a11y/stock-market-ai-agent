"""Offline admission and policy contracts; no synthesis, market retrieval or persistence."""
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timezone, timedelta
import json
import unittest
from unittest.mock import patch

import test_v07 as fixtures
from src.horizon_integration import (
    Admission, Authority, Conflict, DecisionHorizon, Freshness, FundamentalDirection,
    FundamentalArtifact, ScopeRelation, admit_fundamental, admit_technical,
    build_integration_context, classify_conflict, normalize_fundamental,
    participation, primary_authority,
)
from src.models import DecisionRecord, InterpretationStatement, ForecastStatement, MaterialEvidenceReview


def instant(value='2025-03-12T15:00:00+00:00'):
    return datetime.fromisoformat(value)


def fundamental():
    statement = InterpretationStatement('Preserved thesis', ['E001'])
    record = DecisionRecord('fund-1', 'TEST', '2025-03-11T14:00:00+00:00',
        'Accumulate', 72.5, 'long-term', 'Original reasoning', 'Original fundamentals',
        'Original valuation', 'Original earnings', None, [statement], [], [statement], [],
        [ForecastStatement('Original invalidation', ['E001'])], [], [],
        {'E001': MaterialEvidenceReview('Observed', 'Relevant')})
    evidence = {'ticker': 'TEST', 'retrieved_facts': {'value': 42}, 'calculated_metrics': {},
                'catalog': [{'evidence_id': 'E001', 'path': 'retrieved_facts.value', 'value': 42}]}
    return FundamentalArtifact(record, json.dumps(evidence),
        instant('2025-03-11T12:00:00+00:00'), instant('2025-03-11T13:00:00+00:00'),
        'fixture:verified-no-portfolio-run', 'fixture:verified-completion')


class HorizonIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.technical, _, _ = fixtures.TechnicalSignalPersistenceTests().fixture('BULLISH')

    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_horizons_and_authority(self):
        for horizon in DecisionHorizon:
            expected = Authority.TECHNICAL_PRIMARY if horizon in ('SHORT', 'SWING') else Authority.FUNDAMENTAL_PRIMARY
            self.assertEqual(primary_authority(horizon), expected)
        for bad in ('', 'long', 'YEAR', None):
            with self.assertRaises(ValueError):
                primary_authority(bad)

    def test_exact_normalization_and_no_rewrite(self):
        for name, expected in [('Buy', 'FAVORABLE'), ('Accumulate', 'FAVORABLE'),
                               ('Hold', 'NEUTRAL'), ('Trim', 'UNFAVORABLE'), ('Avoid', 'UNFAVORABLE')]:
            self.assertEqual(normalize_fundamental(name), expected)
        for bad in ('STRONG_BUY', 'BUY', '', None):
            with self.assertRaises(ValueError):
                normalize_fundamental(bad)
        source = fundamental()
        result = admit_fundamental(source, 'TEST', instant())
        self.assertEqual(result.recommendation, 'Accumulate')
        self.assertEqual(source.record.recommendation, 'Accumulate')
        self.assertEqual(result.confidence, 72.5)

    def test_admitted_fundamental_preserves_packet(self):
        source = fundamental()
        result = admit_fundamental(source, 'TEST', instant())
        self.assertEqual(result.status, Admission.ADMITTED, result.reasons)
        self.assertEqual(result.source, asdict(source.record))
        self.assertEqual(result.evidence, json.loads(source.evidence_json))
        self.assertEqual(result.native_horizon, 'long-term')
        self.assertIn('source_methodology', json.loads(result.metadata_json))

    def test_technical_admission_and_preservation(self):
        result = admit_technical(self.technical, 'TEST', instant())
        self.assertEqual(result.status, Admission.ADMITTED, result.reasons)
        self.assertEqual(result.source, self.technical.signal)
        self.assertEqual(result.evidence, self.technical.evidence_packet)
        self.assertEqual(result.native_horizon, self.technical.signal['horizon'])
        self.assertEqual(result.latest_completed_session, self.technical.signal['provenance']['latest_completed_session'])

    def test_ticker_mismatch_fails_context(self):
        for kwargs in ({'fundamental': fundamental()}, {'technical': self.technical}):
            with self.assertRaisesRegex(ValueError, 'ticker mismatch'):
                build_integration_context('AAPL', 'LONG', instant(), **kwargs)

    def test_missing_and_wrong_type(self):
        for value in (None, object(), self.technical):
            result = admit_fundamental(value, 'TEST', instant())
            self.assertEqual(result.status, Admission.REJECTED)
        self.assertEqual(admit_technical(fundamental(), 'TEST', instant()).status, Admission.REJECTED)

    def test_no_fabricated_fundamental_provenance(self):
        for change, reason in [({'research_as_of': None}, 'INVALID_TIMESTAMP'),
                               ({'origin_reference': None}, 'UNVERIFIED_PORTFOLIO_INDEPENDENCE'),
                               ({'timing_reference': None}, 'MISSING_TIMING_PROVENANCE')]:
            result = admit_fundamental(replace(fundamental(), **change), 'TEST', instant())
            self.assertEqual(result.status, Admission.REJECTED)
            self.assertIn(reason, result.reasons)

    def test_invalid_fundamental_not_repaired(self):
        for field, value in [('recommendation', 'STRONG_BUY'), ('confidence_score', 101),
                             ('confidence_score', float('nan')), ('investment_horizon', None)]:
            source = fundamental()
            setattr(source.record, field, value)
            result = admit_fundamental(source, 'TEST', instant())
            self.assertEqual(result.status, Admission.REJECTED)
            self.assertEqual(getattr(source.record, field), value) if field != 'confidence_score' else None

    def test_evidence_mismatch_rejected(self):
        source = fundamental()
        source.record.supporting_evidence[0].evidence_refs = ['E999']
        self.assertEqual(admit_fundamental(source, 'TEST', instant()).status, Admission.REJECTED)
        source = fundamental()
        packet = json.loads(source.evidence_json)
        packet['catalog'][0]['value'] = 123
        result = admit_fundamental(replace(source, evidence_json=json.dumps(packet)), 'TEST', instant())
        self.assertIn('INVALID_EVIDENCE_OR_SOURCE', result.reasons)

    def test_unsupported_technical_version(self):
        signal = self.technical.signal
        signal['analyst_methodology_version'] = 'future-version'
        record = replace(self.technical, signal_json=json.dumps(signal))
        result = admit_technical(record, 'TEST', instant())
        self.assertEqual(result.status, Admission.REJECTED)
        self.assertIn('UNSUPPORTED_METHODOLOGY', result.reasons)
        self.assertEqual(result.source['analyst_methodology_version'], 'future-version')

    def test_invalid_technical_signal_horizon_confidence(self):
        for key, value in [('signal', 'BUY'), ('confidence', -1), ('confidence', '70')]:
            signal = self.technical.signal
            signal['analysis'][key] = value
            # Corruption bypassing frozen constructor is still caught at admission.
            record = replace(self.technical)
            object.__setattr__(record, 'signal_json', json.dumps(signal))
            self.assertEqual(admit_technical(record, 'TEST', instant()).status, Admission.REJECTED)
        signal = self.technical.signal
        signal['horizon'] = 'LONG'
        record = replace(self.technical)
        object.__setattr__(record, 'signal_json', json.dumps(signal))
        self.assertEqual(admit_technical(record, 'TEST', instant()).status, Admission.REJECTED)

    def test_freshness_is_separate_from_admission(self):
        admitted = admit_technical(self.technical, 'TEST', instant())
        for state in Freshness:
            result = participation(admitted.status, state)
            self.assertEqual(result.freshness, state)
            self.assertEqual(result.usable, state in (Freshness.FRESH, Freshness.AGING))
            self.assertEqual(admitted.status, Admission.ADMITTED)
            self.assertFalse(participation(Admission.REJECTED, state).usable)
        self.assertEqual(participation(Admission.ADMITTED, 'AGING').reasons, ('AGING_CAUTION',))
        with self.assertRaises(ValueError):
            participation(Admission.ADMITTED, 'RECENT')

    def test_approved_thresholds_replace_unknown_placeholder(self):
        for at, expected in ((instant(), Freshness.FRESH), (instant('2030-01-01T00:00:00+00:00'), Freshness.STALE)):
            context = build_integration_context('TEST', 'SHORT', at, technical=self.technical)
            self.assertEqual(context.technical.status, Admission.ADMITTED)
            self.assertEqual(context.technical_freshness, expected)
            self.assertEqual(context.freshness_policy_version, 'technical-freshness-v1')
            self.assertIsNone(context.usable_primary_authority)

    def test_utc_naive_and_future(self):
        source = fundamental()
        context = build_integration_context('test', 'LONG', instant().astimezone(timezone(timedelta(hours=-4))), fundamental=source)
        self.assertTrue(context.integration_as_of.endswith('Z'))
        with self.assertRaises(ValueError):
            build_integration_context('TEST', 'LONG', datetime(2025, 3, 12))
        result = admit_fundamental(replace(source, research_as_of=datetime(2025, 3, 11)), 'TEST', instant())
        self.assertIn('INVALID_TIMESTAMP', result.reasons)
        self.assertIn('INVALID_TEMPORAL_ORDER', admit_fundamental(source, 'TEST', instant('2025-03-10T00:00:00+00:00')).reasons)
        self.assertIn('INVALID_TEMPORAL_ORDER', admit_technical(self.technical, 'TEST', instant('2025-03-10T00:00:00+00:00')).reasons)

    def test_incomplete_technical_session_rejected(self):
        signal, packet = self.technical.signal, self.technical.evidence_packet
        for value in (signal, packet):
            value['provenance']['latest_completed_session'] = '2025-03-12'
        record = replace(self.technical, signal_json=json.dumps(signal), evidence_json=json.dumps(packet))
        self.assertIn('INVALID_COMPLETED_SESSION', admit_technical(record, 'TEST', instant()).reasons)

    def test_conditional_conflict_rules(self):
        cases = [('LONG', 'FAVORABLE', 'BULLISH', 'COMPATIBLE', Conflict.ALIGNED),
                 ('LONG', 'FAVORABLE', 'BEARISH', 'DISTINCT', Conflict.TIMING_CONFLICT),
                 ('LONG', 'UNFAVORABLE', 'BULLISH', 'DISTINCT', Conflict.HORIZON_DIVERGENCE),
                 ('SWING', 'UNFAVORABLE', 'BULLISH', 'OPPOSING_SAME_SCOPE', Conflict.THESIS_CONFLICT),
                 ('SWING', 'UNFAVORABLE', 'BULLISH', 'COMPATIBLE', Conflict.INSUFFICIENT_EVIDENCE)]
        for horizon, f, t, scope, expected in cases:
            self.assertEqual(classify_conflict(horizon, f, t, scope=scope, evidence_ready=True).classification, expected)
        self.assertEqual(classify_conflict('LONG', 'FAVORABLE', 'BULLISH').classification, Conflict.INSUFFICIENT_EVIDENCE)

    def test_blocking_primary_and_missing_feature_inventory(self):
        context = build_integration_context('TEST', 'LONG', instant(), technical=self.technical)
        self.assertIn('FUNDAMENTAL:MISSING_RESEARCH', context.blocking_missing_data)
        context = build_integration_context('TEST', 'SHORT', instant(), fundamental=fundamental())
        self.assertIn('TECHNICAL:MISSING_RESEARCH', context.blocking_missing_data)
        context = build_integration_context('TEST', 'LONG', instant(), fundamental=fundamental(), technical=self.technical)
        expected = tuple('TECHNICAL:' + eid for eid in self.technical.signal['analysis']['missing_evidence_ids'])
        self.assertEqual(context.non_blocking_missing_data, expected)
        self.assertIn('PRIMARY_RESEARCH_UNKNOWN', context.blocking_missing_data)

    def test_context_deep_snapshot_and_namespaces(self):
        source = fundamental()
        before = asdict(source.record)
        context = build_integration_context('TEST', 'LONG', instant(), fundamental=source, technical=self.technical)
        self.assertEqual(asdict(source.record), before)
        with self.assertRaises(FrozenInstanceError):
            context.ticker = 'AAPL'
        source.record.reasoning_summary = 'Changed later'
        detached = context.technical.source
        detached['analysis']['signal'] = 'BEARISH'
        self.assertEqual(context.fundamental.source['reasoning_summary'], 'Original reasoning')
        self.assertEqual(context.technical.source['analysis']['signal'], 'BULLISH')
        self.assertEqual(context.fundamental.namespace, 'FUNDAMENTAL')
        self.assertEqual(context.technical.namespace, 'TECHNICAL')
        self.assertEqual(context.technical.source['analysis']['confirmation_conditions'], self.technical.signal['analysis']['confirmation_conditions'])
        self.assertEqual(context.fundamental.source['thesis_invalidation_conditions'], before['thesis_invalidation_conditions'])

    def test_scope_and_determinism(self):
        with patch('src.openai_client.request_text', side_effect=AssertionError('No AI')), \
             patch('src.alpha_vantage_client.get_daily_raw', side_effect=AssertionError('No provider')), \
             patch('sqlite3.connect', side_effect=AssertionError('No DB')):
            args = dict(fundamental=fundamental(), technical=self.technical)
            first = build_integration_context('TEST', 'LONG', instant(), **args)
            self.assertEqual(first, build_integration_context('TEST', 'LONG', instant(), **args))
        fields = asdict(first)
        for prohibited in ('synthesis_summary', 'synthesis_confidence', 'timing_posture', 'portfolio', 'position', 'weights'):
            self.assertNotIn(prohibited, fields)
        self.assertEqual(first.conflict.classification, Conflict.INSUFFICIENT_EVIDENCE)

    def test_fundamental_packet_cannot_postdate_availability(self):
        source = fundamental()
        packet = json.loads(source.evidence_json)
        packet['generated_at'] = '2026-01-01T00:00:00+00:00'
        result = admit_fundamental(replace(source, evidence_json=json.dumps(packet)), 'TEST', instant())
        self.assertIn('INVALID_TEMPORAL_ORDER', result.reasons)

    def test_technical_parameters_and_window_validation(self):
        for key, value, reason in [('indicator_parameters', [], 'UNSUPPORTED_METHODOLOGY'),
                                   ('first_included_session', '2026-01-01', 'INVALID_COMPLETED_SESSION')]:
            signal, packet = self.technical.signal, self.technical.evidence_packet
            for target in (signal, packet):
                target['provenance'][key] = value
            record = replace(self.technical, signal_json=json.dumps(signal), evidence_json=json.dumps(packet))
            self.assertIn(reason, admit_technical(record, 'TEST', instant()).reasons)


class FreshnessProvenanceTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No live network'))
        guard.start()
        self.addCleanup(guard.stop)
        self.record, _, _ = fixtures.TechnicalSignalPersistenceTests().fixture('BULLISH')

    def test_all_technical_age_boundaries(self):
        from src.horizon_integration import technical_freshness
        from src.market_calendar import USMarketCalendar
        cal = USMarketCalendar()
        session = datetime.fromisoformat(self.record.signal['provenance']['latest_completed_session']).date()
        for native, cases in [('SHORT_TERM_1_TO_5_SESSIONS', [(0,'FRESH'),(2,'FRESH'),(3,'AGING'),(5,'AGING'),(6,'STALE')]),
                              ('SWING_1_TO_4_WEEKS', [(0,'FRESH'),(10,'FRESH'),(11,'AGING'),(20,'AGING'),(21,'STALE')])]:
            signal = self.record.signal
            signal['horizon'] = native
            record = replace(self.record, signal_json=json.dumps(signal))
            for age, state in cases:
                at = instant('2025-03-11T14:00:00+00:00') if age == 0 else cal.advance_sessions(session, age).closes_at
                result = technical_freshness(record, at, calendar=cal)
                self.assertEqual((result.state, result.completed_session_age), (state, age))
                self.assertEqual(result.policy_version, 'technical-freshness-v1')

    def _dated_record(self, session):
        from src.market_calendar import USMarketCalendar
        close = USMarketCalendar().session_on_or_after(datetime.fromisoformat(session).date()).closes_at
        signal, packet = self.record.signal, self.record.evidence_packet
        for item in (signal, packet):
            p = item['provenance']
            p.update(latest_completed_session=session, first_included_session=session,
                     expected_last_session=session, requested_as_of=close.isoformat(), retrieved_at=close.isoformat())
        return replace(self.record, created_at=close.isoformat(), signal_json=json.dumps(signal), evidence_json=json.dumps(packet))

    def test_weekend_holiday_halfday_and_exact_close(self):
        from src.horizon_integration import technical_freshness
        record = self._dated_record('2025-07-02')
        for at, age in [('2025-07-03T12:59:00-04:00',0), ('2025-07-03T13:00:00-04:00',1),
                        ('2025-07-04T18:00:00-04:00',1), ('2025-07-05T18:00:00-04:00',1),
                        ('2025-07-06T18:00:00-04:00',1), ('2025-07-07T16:00:00-04:00',2)]:
            self.assertEqual(technical_freshness(record, instant(at)).completed_session_age, age)

    def test_unknown_future_missing_and_unsupported(self):
        from src.horizon_integration import technical_freshness
        for at in (datetime(2025,3,1), instant('2025-03-01T00:00:00+00:00')):
            self.assertEqual(technical_freshness(self.record, at).state, Freshness.UNKNOWN)
        for key, value in [('horizon','UNSUPPORTED'), ('latest_completed_session',None)]:
            signal, packet = self.record.signal, self.record.evidence_packet
            if key == 'horizon': signal[key] = value
            else:
                signal['provenance'][key] = value
                packet['provenance'][key] = value
            corrupted = replace(self.record)
            object.__setattr__(corrupted, 'signal_json', json.dumps(signal))
            object.__setattr__(corrupted, 'evidence_json', json.dumps(packet))
            self.assertEqual(technical_freshness(corrupted, instant()).state, Freshness.UNKNOWN)

    def _pipeline(self, horizon='LONG', fail=False):
        from src.models import InvestmentAnalysis
        from src.research_pipeline import run_stock_research
        source = fundamental()
        allowed = InvestmentAnalysis.__dataclass_fields__
        values = {k:v for k,v in asdict(source.record).items() if k in allowed}
        # Original typed interpretation objects are preserved by the mocked existing analyzer.
        values = {k:getattr(source.record,k) for k in values}
        values['portfolio_assessment'] = 'Portfolio context not supplied.'
        analysis = InvestmentAnalysis(**values)
        packet = json.loads(source.evidence_json)
        packet['source'] = 'Alpha Vantage'
        captured = []
        with patch('src.research_pipeline.build_stock_evidence', return_value=packet) as retrieval, \
             patch('src.research_pipeline.analyze_investment', side_effect=ValueError('failed') if fail else None, return_value=analysis) as analyst, \
             patch('src.research_pipeline.datetime') as clock:
            clock.now.side_effect = [instant('2025-03-12T14:00:00+00:00'),
                                    instant('2025-03-12T14:30:00+00:00'), instant()]
            if fail:
                with self.assertRaises(ValueError):
                    run_stock_research('TEST', persist_decision=False, investment_horizon=horizon,
                        integration_run_id='run-1', on_fundamental_artifact=captured.append)
            else:
                result = run_stock_research('TEST', persist_decision=False, investment_horizon=horizon,
                    integration_run_id='run-1', on_fundamental_artifact=captured.append)
                self.assertIs(result, analysis)
            retrieval.assert_called_once()
            analyst.assert_called_once()
        return captured

    def test_pipeline_prospective_capture_and_cutoffs(self):
        artifact = self._pipeline()[0]
        p = artifact.verified()
        self.assertEqual(p['policy_version'], 'fundamental-provenance-v1')
        self.assertEqual(p['methodology_version'], 'fundamental-single-agent-path-v1')
        self.assertEqual(p['data_cutoff_as_of'], '2025-03-12T14:30:00.000000Z')
        self.assertEqual(p['coverage']['earnings']['status'], 'UNAVAILABLE')
        self.assertEqual(p['coverage']['earnings']['observed_dates'], [])
        self.assertEqual(p['event_currentness'], 'UNKNOWN')
        self.assertEqual(artifact.analysis['recommendation'], 'Accumulate')
        self.assertEqual(artifact.evidence['catalog'][0]['evidence_id'], 'E001')
        self.assertEqual(self._pipeline(fail=True), [])

    def test_ready_same_run_and_historical_unknown(self):
        artifact = self._pipeline()[0]
        clean_signal = self.record.signal
        clean_signal['analysis']['risk_notes'] = []
        self.record = replace(self.record, signal_json=json.dumps(clean_signal))
        context = build_integration_context('TEST','LONG',instant(),fundamental=artifact,
                                             technical=self.record,integration_run_id='run-1')
        self.assertEqual(context.readiness, 'SYNTHESIS_READY')
        self.assertEqual(context.fundamental_freshness, Freshness.FRESH)
        self.assertEqual(context.fundamental_provenance_status, 'CURRENT_SYSTEM_TRUSTED')
        self.assertEqual(context.technical_applicability, 'CONTEXT_ONLY')
        self.assertEqual(context.conflict.classification, Conflict.ALIGNED)
        self.assertTrue(context.non_blocking_missing_data)  # Missing long SMA does not block.
        for run, at in [('other',instant()), ('run-1',instant()+timedelta(seconds=1))]:
            later = build_integration_context('TEST','LONG',at,fundamental=artifact,
                                              technical=self.record,integration_run_id=run)
            self.assertEqual(later.fundamental_freshness, Freshness.UNKNOWN)
            self.assertEqual(later.readiness, 'BLOCKED')

    def test_legacy_and_malformed_provenance_not_upgraded(self):
        context = build_integration_context('TEST','LONG',instant(),fundamental=fundamental(),technical=self.record)
        self.assertEqual(context.fundamental_provenance_status, 'LEGACY_UNKNOWN')
        self.assertEqual(context.readiness, 'BLOCKED')
        artifact = self._pipeline()[0]
        p = artifact.provenance
        p['run_id'] = 'forged'
        malformed = replace(artifact, provenance_json=json.dumps(p))
        context = build_integration_context('TEST','LONG',instant(),fundamental=malformed,technical=self.record)
        self.assertIn('FUNDAMENTAL:INVALID_PROVENANCE', context.blocking_missing_data)

    def test_roles_stale_primary_and_native_mismatch(self):
        artifact = self._pipeline()[0]
        for h, role in [('SHORT','CONTEXT_ONLY'),('SWING','SECONDARY'),('MEDIUM','UNKNOWN'),('LONG','PRIMARY')]:
            result = build_integration_context('TEST',h,instant(),fundamental=artifact,
                                              technical=self.record,integration_run_id='run-1')
            self.assertEqual(result.fundamental_applicability, role)
        result = build_integration_context('TEST','SHORT',instant('2025-04-01T00:00:00+00:00'), technical=self.record)
        self.assertEqual(result.technical.status, Admission.ADMITTED)
        self.assertIn('PRIMARY_RESEARCH_STALE',result.blocking_missing_data)
        self.assertEqual(result.conflict.classification,Conflict.INSUFFICIENT_EVIDENCE)

    def test_no_callback_no_capture_and_invalid_request_preflight(self):
        from src.research_pipeline import run_stock_research
        with patch('src.research_pipeline.build_stock_evidence') as retrieval:
            with self.assertRaises(ValueError):
                run_stock_research('TEST',on_fundamental_artifact=lambda _:None)
            retrieval.assert_not_called()
        with patch('src.fundamental_provenance._capture') as capture, \
             patch('src.research_pipeline.build_stock_evidence',return_value={}), \
             patch('src.research_pipeline.analyze_investment',return_value='unchanged'):
            self.assertEqual(run_stock_research('TEST'), 'unchanged')
            capture.assert_not_called()

    def test_risk_ambiguity_is_not_silently_waived(self):
        artifact = self._pipeline()[0]
        result = build_integration_context('TEST','LONG',instant(), fundamental=artifact,
                                          technical=self.record,integration_run_id='run-1')
        self.assertEqual(result.readiness, 'BLOCKED')
        self.assertIn('TECHNICAL_RISK_APPLICABILITY_UNRESOLVED', result.blocking_missing_data)
        self.assertEqual(result.technical.source, self.record.signal)

    def test_current_artifact_immutable_and_temporally_bound(self):
        artifact = self._pipeline()[0]
        original = artifact.analysis
        detached = artifact.analysis
        detached['recommendation'] = 'Avoid'
        self.assertEqual(artifact.analysis, original)
        with self.assertRaises(FrozenInstanceError):
            artifact.analysis_json = '{}'
        result = build_integration_context('TEST','LONG',instant('2025-03-12T14:59:59+00:00'),
                                          fundamental=artifact,technical=self.record,integration_run_id='run-1')
        self.assertIn('FUNDAMENTAL:INVALID_TEMPORAL_ORDER',result.blocking_missing_data)

    def test_multi_agent_capture_keeps_same_run_path(self):
        from types import SimpleNamespace
        from src.models import InvestmentAnalysis
        from src.research_pipeline import run_stock_research
        seed = self._pipeline()[0]
        result = InvestmentAnalysis(**seed.analysis)
        captured = []
        context = SimpleNamespace(specialist_results=[SimpleNamespace(specialist_name='fundamental'),
                                                      SimpleNamespace(specialist_name='risk')])
        with patch('src.research_pipeline.build_stock_evidence',return_value=seed.evidence), \
             patch('src.research_pipeline.run_specialists',return_value=context) as specialists, \
             patch('src.research_pipeline.synthesize_investment_analysis',return_value=result) as synthesis, \
             patch('src.research_pipeline.analyze_investment') as single:
            returned = run_stock_research('TEST',use_multi_agent=True,persist_decision=False,
                investment_horizon='LONG',integration_run_id='multi-run',on_fundamental_artifact=captured.append)
        self.assertIs(returned,result)
        specialists.assert_called_once()
        synthesis.assert_called_once()
        single.assert_not_called()
        self.assertEqual(captured[0].verified()['specialists'],['fundamental','risk'])
        self.assertEqual(captured[0].provenance['methodology_version'],'fundamental-multi-agent-path-v1')
