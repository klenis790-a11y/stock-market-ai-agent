import historical_generation
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
    participation, primary_authority, select_technical_horizon,
    TECHNICAL_HORIZON_SELECTION_VERSION,
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

    def test_generation_selection_mapping_and_version(self):
        from src.technical_analyst import HORIZONS
        self.assertEqual(TECHNICAL_HORIZON_SELECTION_VERSION, 'technical-horizon-selection-v1')
        for horizon, native in [(DecisionHorizon.SHORT, 'SHORT_TERM_1_TO_5_SESSIONS'),
                                (DecisionHorizon.SWING, 'SWING_1_TO_4_WEEKS'),
                                (DecisionHorizon.MEDIUM, 'SWING_1_TO_4_WEEKS'),
                                (DecisionHorizon.LONG, 'SWING_1_TO_4_WEEKS')]:
            original = horizon.value
            authority = primary_authority(horizon)
            before = build_integration_context('TEST', horizon, instant(), technical=self.technical)
            self.assertEqual(select_technical_horizon(horizon), native)
            self.assertEqual(select_technical_horizon(original), native)
            self.assertIn(native, HORIZONS)
            self.assertNotEqual(native, original)
            self.assertEqual(horizon.value, original)
            self.assertEqual(primary_authority(horizon), authority)
            self.assertEqual(build_integration_context('TEST', horizon, instant(),
                             technical=self.technical), before)
            self.assertEqual(before.decision_horizon, horizon)

    def test_generation_selection_invalid_inputs_fail_closed(self):
        for bad in ('', 'short', ' LONG ', 'YEAR', 'SWING_1_TO_4_WEEKS', None, 20):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                select_technical_horizon(bad)

    def test_combined_sequence_policy_and_independent_authority(self):
        from src.horizon_integration import (ResearchSequence, COMBINED_RESEARCH_SEQUENCE,
                                            COMBINED_RESEARCH_SEQUENCING_VERSION)
        self.assertEqual(COMBINED_RESEARCH_SEQUENCING_VERSION, 'combined-research-sequencing-v1')
        self.assertEqual(COMBINED_RESEARCH_SEQUENCE, 'TECHNICAL_THEN_FUNDAMENTAL')
        self.assertEqual(ResearchSequence(COMBINED_RESEARCH_SEQUENCE), COMBINED_RESEARCH_SEQUENCE)
        for bad in ('FUNDAMENTAL_THEN_TECHNICAL', '', None):
            with self.assertRaises(ValueError):
                ResearchSequence(bad)
        for horizon, expected in [('SHORT', 'TECHNICAL_PRIMARY'), ('SWING', 'TECHNICAL_PRIMARY'),
                                  ('MEDIUM', 'FUNDAMENTAL_PRIMARY'), ('LONG', 'FUNDAMENTAL_PRIMARY')]:
            self.assertEqual(primary_authority(horizon), expected)
        self.assertEqual(TECHNICAL_HORIZON_SELECTION_VERSION, 'technical-horizon-selection-v1')

    def test_selected_native_horizon_keeps_existing_freshness(self):
        from src.horizon_integration import technical_freshness
        from src.market_calendar import USMarketCalendar
        original = asdict(self.technical)
        cal = USMarketCalendar()
        session = datetime.fromisoformat(self.technical.signal['provenance']['latest_completed_session']).date()
        for horizon in DecisionHorizon:
            signal = self.technical.signal
            signal['horizon'] = select_technical_horizon(horizon)
            record = replace(self.technical, signal_json=json.dumps(signal))
            cases = ((2, 'FRESH'), (3, 'AGING'), (5, 'AGING'), (6, 'STALE')) if horizon == DecisionHorizon.SHORT else (
                (10, 'FRESH'), (11, 'AGING'), (20, 'AGING'), (21, 'STALE'))
            for age, expected in cases:
                result = technical_freshness(record, cal.advance_sessions(session, age).closes_at)
                self.assertEqual(result.state, expected)
                self.assertEqual(result.policy_version, 'technical-freshness-v1')
            self.assertEqual(record.signal['horizon'], select_technical_horizon(horizon))
        self.assertEqual(asdict(self.technical), original)

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

    def _pipeline(self, horizon='LONG', fail=False, risks=False, missing=False, rich=False):
        from src.models import InvestmentAnalysis
        from src.research_pipeline import run_stock_research
        source = fundamental()
        allowed = InvestmentAnalysis.__dataclass_fields__
        values = {k:v for k,v in asdict(source.record).items() if k in allowed}
        # Original typed interpretation objects are preserved by the mocked existing analyzer.
        values = {k:getattr(source.record,k) for k in values}
        values['portfolio_assessment'] = 'Portfolio context not supplied.'
        if missing:
            values['missing_data'] = ['Required coverage unavailable']
        if risks:
            values['major_risks'] = [InterpretationStatement('Observed uncertainty', ['E001'])]
            values['bear_case'] = [InterpretationStatement('Adverse thesis evidence', ['E001'])]
        analysis = InvestmentAnalysis(**values)
        packet = json.loads(source.evidence_json)
        packet['source'] = 'Alpha Vantage'
        if rich:
            packet['retrieved_facts']['second_value'] = 7.5
            for field in ('major_risks', 'bear_case'):
                values = getattr(analysis, field)
                values[0].evidence_refs.append('E002')
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

    def test_valid_technical_risk_is_preserved_without_existence_block(self):
        artifact = self._pipeline()[0]
        result = build_integration_context('TEST','LONG',instant(), fundamental=artifact,
                                          technical=self.record,integration_run_id='run-1')
        self.assertEqual(result.readiness, 'SYNTHESIS_READY')
        self.assertNotIn('TECHNICAL_RISK_APPLICABILITY_UNRESOLVED', result.blocking_missing_data)
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


class ReadinessIntegrityTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No live network'))
        guard.start()
        self.addCleanup(guard.stop)
        helper = FreshnessProvenanceTests()
        helper.record, _, _ = fixtures.TechnicalSignalPersistenceTests().fixture('BULLISH')
        self.artifact = helper._pipeline()[0]
        signal = helper.record.signal
        signal['analysis']['risk_notes'] = []
        self.record = replace(helper.record, signal_json=json.dumps(signal))
        self.context = build_integration_context('TEST','LONG',instant(),fundamental=self.artifact,
                                                technical=self.record,integration_run_id='run-1')

    def require(self, context):
        from src.horizon_integration import require_synthesis_ready
        return require_synthesis_ready(context)

    def test_reported_replace_bypass_permanent_regression(self):
        from src.horizon_integration import SynthesisReadinessError
        blocked = build_integration_context('TEST','LONG',instant())
        forged = replace(blocked, readiness='SYNTHESIS_READY', blocking_missing_data=())
        with self.assertRaises(SynthesisReadinessError):
            self.require(forged)
        with self.assertRaises(SynthesisReadinessError) as caught:
            self.require(blocked)
        self.assertTrue(set(blocked.blocking_missing_data) <= set(caught.exception.reasons))

    def test_technical_first_sequence_satisfies_existing_time_contract(self):
        original = (self.artifact.provenance_json, asdict(self.record))
        p = self.artifact.verified()
        retrieved = instant(self.record.signal['provenance']['retrieved_at'].replace('Z', '+00:00'))
        created = instant(self.record.created_at.replace('Z', '+00:00'))
        available = instant(p['available_at'].replace('Z', '+00:00'))
        self.assertLessEqual(retrieved, created)
        self.assertLessEqual(created, instant(p['retrieval_started_at'].replace('Z', '+00:00')))
        self.assertLessEqual(created, available)
        self.assertEqual(self.context.integration_as_of, p['available_at'])
        self.assertEqual(self.require(self.context), self.context)
        self.assertEqual(self.context.fundamental_freshness, Freshness.FRESH)
        self.assertEqual((self.artifact.provenance_json, asdict(self.record)), original)

    def test_reverse_sequence_cannot_repair_time_by_advancing_integration(self):
        from src.horizon_integration import SynthesisReadinessError
        # A separate fixture represents actual later Technical completion. Neither
        # assessment below retimestamps it or the Fundamental sidecar.
        late = replace(self.record, created_at=(instant() + timedelta(seconds=1)).isoformat())
        original = (self.artifact.provenance_json, asdict(late))
        for at in (instant(), instant() + timedelta(seconds=1)):
            context = build_integration_context('TEST', 'LONG', at,
                fundamental=self.artifact, technical=late, integration_run_id='run-1')
            with self.assertRaises(SynthesisReadinessError):
                self.require(context)
            if at == instant():
                self.assertIn('INVALID_TEMPORAL_ORDER', context.technical.reasons)
            else:
                self.assertEqual(context.fundamental_freshness, Freshness.UNKNOWN)
                self.assertIn('PRIMARY_RESEARCH_UNKNOWN', context.blocking_missing_data)
        self.assertEqual((self.artifact.provenance_json, asdict(late)), original)

    def test_legitimate_ready_recomputes_and_preserves_sources(self):
        self.assertEqual(self.require(self.context), self.context)
        self.assertEqual(self.require(self.context), self.require(self.context))
        self.assertIs(self.context.fundamental_source, self.artifact)
        self.assertEqual(self.context.technical_source, self.record)
        self.assertEqual(self.context.integration_run_id, 'run-1')
        self.assertTrue(self.context.non_blocking_missing_data)
        self.assertEqual(self.context.fundamental.source, self.artifact.analysis)
        self.assertEqual(self.context.technical.source, self.record.signal)

    def test_direct_constructor_inconsistent_state_rejected(self):
        from dataclasses import fields
        from src.horizon_integration import IntegrationContext, SynthesisReadinessError
        data = {f.name:getattr(self.context,f.name) for f in fields(self.context)}
        data['technical_freshness'] = Freshness.STALE
        with self.assertRaises(SynthesisReadinessError):
            self.require(IntegrationContext(**data))

    def test_derived_fields_cannot_override_policy(self):
        from src.horizon_integration import SynthesisReadinessError, ConflictAssessment
        changes = [dict(readiness='BLOCKED'),dict(blocking_missing_data=('invented-block',)),
                   dict(fundamental=replace(self.context.fundamental,status=Admission.REJECTED)),
                   dict(technical_freshness=Freshness.STALE),dict(fundamental_freshness=Freshness.UNKNOWN),
                   dict(primary_authority=Authority.TECHNICAL_PRIMARY),dict(decision_horizon='SHORT'),
                   dict(conflict=ConflictAssessment(Conflict.THESIS_CONFLICT,'invented')),
                   dict(non_blocking_missing_data=()),dict(warnings=()),dict(technical_session_age=999)]
        for change in changes:
            with self.subTest(change=tuple(change)):
                with self.assertRaises(SynthesisReadinessError):
                    self.require(replace(self.context,**change))

    def test_versions_fail_closed(self):
        from src.horizon_integration import SynthesisReadinessError
        for name in ('methodology_version','admission_version','normalization_version',
                     'freshness_policy_version','integration_policy_version','fundamental_policy_version',
                     'calendar_version'):
            with self.subTest(name=name), self.assertRaises(SynthesisReadinessError):
                self.require(replace(self.context,**{name:'unsupported'}))

    def test_run_completion_ticker_and_provenance_binding(self):
        from src.horizon_integration import SynthesisReadinessError
        p = self.artifact.provenance
        p['run_id'] = 'altered'
        bad = replace(self.artifact,provenance_json=json.dumps(p))
        for change in (dict(integration_run_id='other'),dict(integration_run_id=None),
                       dict(integration_as_of='2025-03-12T15:00:01+00:00'),
                       dict(integration_as_of='2025-03-01T15:00:00+00:00'),dict(ticker='AAPL'),
                       dict(fundamental_source=bad),dict(fundamental_source=None)):
            with self.subTest(change=tuple(change)), self.assertRaises(SynthesisReadinessError):
                self.require(replace(self.context,**change))

    def test_stale_primary_forgery_recomputed(self):
        from src.horizon_integration import SynthesisReadinessError
        context = build_integration_context('TEST','SHORT',instant('2025-04-01T15:00:00+00:00'),
                    fundamental=self.artifact,technical=self.record,integration_run_id='run-1')
        forged = replace(context,readiness='SYNTHESIS_READY',blocking_missing_data=(),
                         technical_freshness=Freshness.FRESH)
        with self.assertRaises(SynthesisReadinessError) as caught:
            self.require(forged)
        self.assertIn('PRIMARY_RESEARCH_STALE',caught.exception.reasons)

    def test_legacy_no_capability_and_no_external_side_effects(self):
        from src.horizon_integration import SynthesisReadinessError
        legacy = build_integration_context('TEST','LONG',instant(),fundamental=fundamental(),technical=self.record)
        self.assertIsNone(legacy.fundamental_source)
        with self.assertRaises(SynthesisReadinessError):
            self.require(replace(legacy,readiness='SYNTHESIS_READY',blocking_missing_data=()))
        with patch('src.openai_client.request_text',side_effect=AssertionError('No AI')), \
             patch('src.research_pipeline.run_stock_research',side_effect=AssertionError('No research')), \
             patch('sqlite3.connect',side_effect=AssertionError('No DB')):
            self.assertEqual(self.require(self.context),self.context)


class HorizonSynthesisTests(unittest.TestCase):
    def setUp(self):
        helper = ReadinessIntegrityTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.context = helper.context

    def output(self, context=None, posture='FAVORABLE_NOW'):
        from src.horizon_synthesis import _packet
        p = _packet(context or self.context)
        fid = p['fundamental']['catalog'][0]['evidence_id']
        tid = p['technical']['analysis']['supporting_evidence_ids'][0]
        statement = lambda text: dict(text=text,classification='AI_INTERPRETATION',
            fundamental_evidence_ids=[fid],technical_evidence_ids=[tid],condition_ids=[])
        data = dict(identity=p['identity'],timing_posture=posture,synthesis_confidence=67,
            synthesis_summary=statement('The supplied thesis and timing evidence inform different research horizons.'),
            agreement_explanation=statement('The independent research conclusions remain preserved.'),
            horizon_interpretation=statement('Primary authority governs the selected horizon.'),
            invalidation_summary=statement('The supplied invalidation condition remains conditional.'),
            major_integrated_risks=[],supporting_fundamental_evidence_ids=[fid],conflicting_fundamental_evidence_ids=[],
            supporting_technical_evidence_ids=[tid],conflicting_technical_evidence_ids=[],
            acknowledged_limitations=p['limitations'])
        data['invalidation_summary']['classification']='FORECAST'
        data['invalidation_summary']['condition_ids']=['F_INVALIDATION:0']
        if posture == 'WAIT_FOR_CONFIRMATION':
            data['synthesis_summary']['classification']='FORECAST'
            data['synthesis_summary']['condition_ids']=['T_CONFIRMATION:0']
        return data

    def invoke(self, data, context=None):
        from historical_generation import synthesize_horizon
        with patch('src.openai_client.request_text',return_value=json.dumps(data)) as request:
            result = synthesize_horizon(context or self.context)
            request.assert_called_once()
            self.assertTrue(request.call_args.kwargs['require_completed'])
            self.assertTrue(request.call_args.kwargs['text']['format']['strict'])
            self.assertNotIn('portfolio_assessment',request.call_args.kwargs['input'])
        return result

    def test_valid_output_retains_original_context_and_confidence(self):
        result=self.invoke(self.output())
        self.assertEqual(result.context,self.context)
        self.assertEqual(result.analysis['synthesis_confidence'],67)
        self.assertEqual(result.context.fundamental.confidence,72.5)
        self.assertEqual(result.context.technical.source,self.context.technical.source)
        self.assertTrue(result.synthesized_at.endswith('Z'))
        self.assertEqual(result.methodology_version,'horizon-synthesis-v1')

    def test_blocked_and_forged_zero_calls(self):
        from historical_generation import synthesize_horizon
        from src.horizon_integration import SynthesisReadinessError
        blocked=build_integration_context('TEST','LONG',instant())
        with patch('src.openai_client.request_text') as request:
            for context in (blocked,replace(blocked,readiness='SYNTHESIS_READY',blocking_missing_data=())):
                with self.assertRaises(SynthesisReadinessError): synthesize_horizon(context)
            request.assert_not_called()

    def test_identity_changes_rejected(self):
        from src.horizon_synthesis import HorizonSynthesisError
        for key in self.output()['identity']:
            data=self.output(); data['identity'][key]='CHANGED'
            with self.subTest(key=key),self.assertRaises(HorizonSynthesisError) as caught:
                self.invoke(data)
            self.assertEqual(caught.exception.synthesis_failure_type,'IDENTITY_MISMATCH')

    def test_postures_and_matrix_guardrail(self):
        from src.horizon_synthesis import _validate,_packet,HorizonSynthesisError
        for posture in ('FAVORABLE_NOW','WAIT_FOR_CONFIRMATION','UNRESOLVED'):
            self.invoke(self.output(posture=posture))
        # Parser units use approved matrix variations; forged contexts are never sent to IO.
        for direction, signal, posture in [('NEUTRAL','NEUTRAL','NO_ACTION'),('UNFAVORABLE','BEARISH','UNFAVORABLE_NOW')]:
            context=replace(self.context,fundamental=replace(self.context.fundamental,direction=FundamentalDirection(direction)),
                            technical=replace(self.context.technical,recommendation=signal))
            _validate(self.output(context,posture),_packet(context))
        for posture in ('BUY','SELL','ENTER','HOLD_POSITION','NO_ACTION'):
            with self.subTest(posture=posture),self.assertRaises(HorizonSynthesisError):
                self.invoke(self.output(posture=posture))

    def test_schema_confidence_and_fake_evidence(self):
        from src.horizon_synthesis import HorizonSynthesisError
        for value in (-1,101,True,'70',None):
            data=self.output();data['synthesis_confidence']=value
            with self.assertRaises(HorizonSynthesisError):self.invoke(data)
        for field in ('supporting_fundamental_evidence_ids','supporting_technical_evidence_ids'):
            data=self.output();data[field]=['FAKE999']
            with self.assertRaises(HorizonSynthesisError) as caught:self.invoke(data)
            self.assertEqual(caught.exception.synthesis_failure_type,'INVALID_EVIDENCE_REFERENCE')
        for change in ('missing','extra'):
            data=self.output()
            if change=='missing':del data['synthesis_summary']
            else:data['position_size']=1
            with self.assertRaises(HorizonSynthesisError):self.invoke(data)

    def test_conditions_numbers_limitations_and_forecasts(self):
        from src.horizon_synthesis import HorizonSynthesisError
        mutations=[('invalidation_summary','text','Stop-loss at 100.'),
                   ('invalidation_summary','condition_ids',['F_INVALIDATION:999']),
                   ('invalidation_summary','classification','RETRIEVED_FACT'),
                   ('synthesis_summary','text','The price will rise.'),
                   ('synthesis_summary','technical_evidence_ids',['E001'])]
        for field,key,value in mutations:
            data=self.output();data[field][key]=value
            with self.subTest(field=field,key=key),self.assertRaises(HorizonSynthesisError):self.invoke(data)
        data=self.output();data['acknowledged_limitations']=[]
        with self.assertRaises(HorizonSynthesisError):self.invoke(data)
        data=self.output(posture='WAIT_FOR_CONFIRMATION');data['synthesis_summary']['condition_ids']=[]
        with self.assertRaises(HorizonSynthesisError):self.invoke(data)

    def test_json_extraction_and_api_failures_no_retry(self):
        from src.horizon_synthesis import HorizonSynthesisError
        from historical_generation import synthesize_horizon
        for response,kind in [('{broken','INVALID_JSON'),('```json\n{}\n```','INVALID_JSON'),('', 'RESPONSE_EXTRACTION'),(None,'RESPONSE_EXTRACTION')]:
            with patch('src.openai_client.request_text',return_value=response) as request:
                with self.assertRaises(HorizonSynthesisError) as caught:synthesize_horizon(self.context)
                self.assertEqual(caught.exception.synthesis_failure_type,kind)
                request.assert_called_once()
        with patch('src.openai_client.request_text',side_effect=RuntimeError('secret provider detail')) as request:
            with self.assertRaises(HorizonSynthesisError) as caught:synthesize_horizon(self.context)
            self.assertNotIn('secret',str(caught.exception))
            request.assert_called_once()

    def test_actual_responses_object_extraction(self):
        from types import SimpleNamespace
        from src.horizon_synthesis import HorizonSynthesisError
        from historical_generation import synthesize_horizon
        with patch.dict('os.environ',{'OPENAI_API_KEY':'unit-test-placeholder'}), patch('src.openai_client.OpenAI') as client:
            api=client.return_value.__enter__.return_value
            api.responses.create.return_value=SimpleNamespace(status='completed',output_text=json.dumps(self.output()))
            result=synthesize_horizon(self.context)
            self.assertEqual(result.analysis['identity']['ticker'],'TEST')
            api.responses.create.assert_called_once()
            self.assertEqual(client.call_args.kwargs['max_retries'],0)
            api.responses.create.return_value=SimpleNamespace(status='incomplete',output_text='{}',incomplete_details=None)
            with self.assertRaises(HorizonSynthesisError) as caught:synthesize_horizon(self.context)
            self.assertEqual(caught.exception.synthesis_failure_type,'RESPONSE_EXTRACTION')

    def test_no_rerun_or_persistence(self):
        with patch('src.research_pipeline.run_stock_research',side_effect=AssertionError('No research')), \
             patch('src.multi_agent.run_specialists',side_effect=AssertionError('No specialists')), \
             patch('sqlite3.connect',side_effect=AssertionError('No DB')):
            self.invoke(self.output())

    def test_four_horizons_through_authoritative_builder(self):
        for horizon in ('SHORT','SWING','MEDIUM','LONG'):
            helper=FreshnessProvenanceTests()
            artifact=helper._pipeline('MEDIUM' if horizon=='MEDIUM' else 'LONG')[0]
            record=self.context.technical_source
            if horizon=='SWING':
                signal=record.signal;signal['horizon']='SWING_1_TO_4_WEEKS'
                record=replace(record,signal_json=json.dumps(signal))
            context=build_integration_context('TEST',horizon,instant(),fundamental=artifact,
                        technical=record,integration_run_id='run-1')
            result=self.invoke(self.output(context),context)
            self.assertEqual(result.context.decision_horizon,horizon)
            self.assertEqual(result.context.primary_authority,primary_authority(horizon))

    def test_conflict_echo_validation_without_bypassing_readiness(self):
        from src.horizon_synthesis import _packet,_validate,HorizonSynthesisError
        from src.horizon_integration import ConflictAssessment
        # Parser-level contract coverage only: THESIS_CONFLICT is not currently
        # emitted by ready Step 3B contexts. The public builder gate is never patched.
        for conflict in Conflict:
            context=replace(self.context,conflict=ConflictAssessment(conflict,'parser-fixture'))
            packet=_packet(context)
            data=self.output(context)
            _validate(data,packet)
            data['identity']['conflict_classification']='ALTERED'
            with self.assertRaises(HorizonSynthesisError):_validate(data,packet)


class CombinedPipelineTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No live network'))
        guard.start()
        self.addCleanup(guard.stop)

    def exercise(self, horizon='LONG', failure=None, forged=False, risks=False, rich=False, response_mutator=None, expected_semantic=None, expected_namespace=None):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from src import horizon_pipeline as pipeline
        from src import horizon_integration as policy
        native = select_technical_horizon(horizon)
        record, signal, catalog = fixtures.TechnicalSignalPersistenceTests().fixture('BULLISH', native)
        if risks:
            signal = replace(signal, analysis=replace(signal.analysis,
                conflicting_evidence_ids=signal.analysis.supporting_evidence_ids[:1]))
        else:
            signal = replace(signal, analysis=replace(signal.analysis, risk_notes=()))
        if rich:
            available = tuple(item['evidence_id'] for item in catalog.to_packet()['items'] if item['value'] is not None)[:2]
            signal = replace(signal, analysis=replace(signal.analysis, risk_notes=tuple(
                replace(note, evidence_ids=available) for note in signal.analysis.risk_notes)))
        before = asdict(signal)
        helper = FreshnessProvenanceTests()
        artifact = helper._pipeline('MEDIUM' if horizon == 'MEDIUM' else 'LONG', risks=risks, missing=failure == 'MISSING', rich=rich)[0]
        events = []
        def technical(*args, **kwargs):
            events.append('technical')
            self.assertEqual(args[1], native)
            if failure == 'TECHNICAL_RESEARCH': raise ValueError('secret provider payload')
            from src import technical_pipeline as backend
            snapshot, _ = fixtures.TechnicalAnalystTests().fixture()
            with patch.object(backend, 'retrieve_historical_ohlcv', return_value=snapshot.historical_ohlcv) as retrieval, \
                 patch.object(backend, 'analyze_technical_snapshot', return_value=signal) as analyst:
                result = backend.run_technical_research(*args, **kwargs)
                retrieval.assert_called_once()
                analyst.assert_called_once()
                self.assertEqual(analyst.call_args.args[2], native)
                return result
        def fundamental_run(*args, **kwargs):
            events.append('fundamental')
            self.assertFalse(kwargs['persist_decision'])
            self.assertEqual(kwargs['integration_run_id'], 'run-other' if failure == 'PROVENANCE' else 'run-1')
            if failure == 'FUNDAMENTAL_RESEARCH': raise ValueError('secret provider payload')
            kwargs['on_fundamental_artifact'](artifact)
            return artifact.analysis
        actual_builder = policy.build_integration_context
        built = []
        def builder(*args, **kwargs):
            if failure == 'INTEGRATION': raise ValueError('secret')
            result = actual_builder(*args, **kwargs)
            if forged and not built:
                built.append(result)
                return replace(result, fundamental=replace(result.fundamental,status=Admission.REJECTED))
            return result
        def synthesis(context):
            events.append('synthesis')
            if failure == 'HORIZON_SYNTHESIS': raise ValueError('secret model payload')
            from historical_generation import synthesize_horizon
            if risks:
                from src.horizon_synthesis import _packet
                packet = _packet(context)
                self.assertEqual(context.fundamental.source['major_risks'], artifact.analysis['major_risks'])
                self.assertEqual(context.fundamental.source['bear_case'], artifact.analysis['bear_case'])
                self.assertEqual(context.technical.source['analysis']['risk_notes'], json.loads(json.dumps(asdict(signal.analysis)))['risk_notes'])
                self.assertEqual(context.risk_applicability_version, 'risk-applicability-v1')
            data = HorizonSynthesisTests().output(context)
            if response_mutator is not None:
                response_mutator(data)
            with patch('src.openai_client.request_text', return_value=json.dumps(data)) as request:
                try:
                    result = synthesize_horizon(context)
                finally:
                    if expected_semantic:
                        request.assert_called_once()
                request.assert_called_once()
                if rich:
                    supplied = json.loads(request.call_args.kwargs['input'])
                    self.assertEqual(len(supplied['fundamental']['analysis']['major_risks'][0]['evidence_refs']), 2)
                    self.assertEqual(len(supplied['technical']['analysis']['risk_notes'][0]['evidence_ids']), 2)
            return result
        with ExitStack() as stack:
            stack.enter_context(patch('sqlite3.connect', side_effect=AssertionError('No persistence')))
            stack.enter_context(patch.object(pipeline, 'uuid4', return_value=SimpleNamespace(hex='run-other' if failure == 'PROVENANCE' else 'run-1')))
            clock = stack.enter_context(patch.object(pipeline, 'datetime'))
            clock.now.return_value = (instant() + timedelta(seconds=1) if failure == 'READINESS'
                                      else instant('2025-03-11T13:00:00+00:00'))
            clock.fromisoformat.side_effect = datetime.fromisoformat
            t = stack.enter_context(patch.object(pipeline,'run_technical_research',side_effect=technical))
            f = stack.enter_context(patch.object(pipeline,'run_stock_research',side_effect=fundamental_run))
            s = stack.enter_context(patch.object(pipeline,'synthesize_horizon',side_effect=synthesis))
            select = stack.enter_context(patch.object(policy,'select_technical_horizon',wraps=select_technical_horizon))
            build_call = stack.enter_context(patch.object(policy,'build_integration_context',side_effect=builder))
            require = stack.enter_context(patch.object(policy,'require_synthesis_ready',wraps=policy.require_synthesis_ready))
            if failure or forged or expected_semantic:
                with self.assertRaises(pipeline.HorizonPipelineError) as caught:
                    pipeline.run_horizon_research('TEST', horizon, fundamental_horizon='MEDIUM' if horizon == 'MEDIUM' else 'LONG',
                        technical_as_of=instant('2025-03-11T13:00:00+00:00'), market_verified=True)
                if expected_semantic:
                    self.assertEqual(caught.exception.failure_type, 'SEMANTIC_VALIDATION')
                    self.assertEqual(caught.exception.semantic_reason, expected_semantic)
                    if expected_namespace is not None:
                        self.assertEqual(caught.exception.evidence_namespace, expected_namespace)
                    self.assertEqual(caught.exception.error_type, 'HorizonSynthesisError')
                    self.assertNotIn('SECRET', str(caught.exception) + repr(vars(caught.exception)))
                    self.assertEqual(events, ['technical','fundamental','synthesis'])
                    s.assert_called_once()
                self.assertEqual(caught.exception.stage, 'HORIZON_SYNTHESIS' if expected_semantic else 'READINESS' if forged or failure in ('MISSING', 'PROVENANCE') else failure)
                self.assertNotIn('secret',str(caught.exception))
                if forged: self.assertTrue(caught.exception.reasons)
                if failure != 'HORIZON_SYNTHESIS' and not expected_semantic: s.assert_not_called()
            else:
                result = pipeline.run_horizon_research('TEST',horizon,
                    fundamental_horizon='MEDIUM' if horizon == 'MEDIUM' else 'LONG',
                    technical_as_of=instant('2025-03-11T13:00:00+00:00'),market_verified=True)
                self.assertEqual(events, ['technical','fundamental','synthesis'])
                self.assertEqual(result.view.context.primary_authority, primary_authority(horizon))
                self.assertEqual(result.view.context.fundamental.source, artifact.analysis)
                self.assertEqual(result.view.context.technical.source['analysis'], json.loads(json.dumps(asdict(signal.analysis))))
                self.assertEqual(result.view.context.freshness_policy_version, 'technical-freshness-v1')
                self.assertEqual(result.view.context.fundamental_policy_version, 'fundamental-provenance-v1')
                self.assertEqual(result.view.context.decision_horizon,horizon)
                self.assertEqual(result.view.context.technical.native_horizon,native)
                self.assertEqual(result.view.context.integration_as_of,artifact.provenance['available_at'])
                self.assertEqual(result.view.context.fundamental_source,artifact)
                self.assertEqual(result.technical_horizon_selection_version,'technical-horizon-selection-v1')
                self.assertEqual(result.sequencing_version,'combined-research-sequencing-v1')
                require.assert_called_once()
                s.assert_called_once()
            select.assert_called_once()
            t.assert_called_once()
            if failure in ('TECHNICAL_RESEARCH', 'FUNDAMENTAL_RESEARCH'):
                build_call.assert_not_called()
                require.assert_not_called()
            if failure == 'TECHNICAL_RESEARCH': f.assert_not_called()
            else: f.assert_called_once()
        self.assertEqual(asdict(signal),before)

    def test_all_horizons_success_and_source_preservation(self):
        for horizon in DecisionHorizon:
            with self.subTest(horizon=horizon): self.exercise(horizon)

    def test_fail_fast_stages_no_retries_or_leaks(self):
        for stage in ('TECHNICAL_RESEARCH','FUNDAMENTAL_RESEARCH','INTEGRATION','READINESS','HORIZON_SYNTHESIS'):
            with self.subTest(stage=stage): self.exercise(failure=stage)

    def test_forged_context_rejected_before_synthesis(self):
        self.exercise(forged=True)

    def test_bad_input_makes_no_research_calls(self):
        from src.horizon_pipeline import run_horizon_research, HorizonPipelineError
        with patch('src.horizon_pipeline.run_technical_research') as technical:
            with self.assertRaises(HorizonPipelineError) as caught:
                run_horizon_research('TEST','INVALID',fundamental_horizon='LONG',technical_as_of=instant(),market_verified=True)
            self.assertEqual(caught.exception.stage,'INPUT')
            technical.assert_not_called()

    def test_risks_reach_synthesis_for_all_horizons(self):
        for horizon in DecisionHorizon:
            with self.subTest(horizon=horizon): self.exercise(horizon, risks=True)

    def test_risks_do_not_override_temporal_or_forged_readiness(self):
        self.exercise(risks=True, failure='READINESS')
        self.exercise(risks=True, forged=True)

    def test_unknown_technical_conflicting_id_fails_admission(self):
        record, _, _ = fixtures.TechnicalSignalPersistenceTests().fixture('BULLISH')
        original = asdict(record)
        signal = record.signal
        signal['analysis']['conflicting_evidence_ids'] = ['T_NONEXISTENT']
        corrupted = replace(record)
        object.__setattr__(corrupted, 'signal_json', json.dumps(signal))
        self.assertEqual(admit_technical(corrupted, 'TEST', instant()).status, Admission.REJECTED)
        self.assertEqual(asdict(record), original)

    def test_unsupported_risk_version_fails_boundary(self):
        from src.horizon_integration import require_synthesis_ready, SynthesisReadinessError
        helper = ReadinessIntegrityTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        with self.assertRaises(SynthesisReadinessError):
            require_synthesis_ready(replace(helper.context, risk_applicability_version='risk-applicability-v999'))

    def test_combined_missing_data_remains_blocking_with_risks(self):
        self.exercise(failure='MISSING', risks=True)

    def test_combined_run_provenance_mismatch_blocks_with_risks(self):
        self.exercise(failure='PROVENANCE', risks=True)

    def test_rich_medium_packet_reaches_mocked_request(self):
        self.exercise('MEDIUM', risks=True, rich=True)

    def test_pre_request_substages_keep_safe_cause_and_zero_requests(self):
        from src import horizon_synthesis as synthesis
        helper = ReadinessIntegrityTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        for function, substage, error in [('_packet', 'PACKET_CONSTRUCTION', KeyError('SECRET raw body')),
                                         ('canonical_json', 'INPUT_SERIALIZATION', TypeError('SECRET prompt')),
                                         ('_schema', 'SCHEMA_CONSTRUCTION', ValueError('SECRET key'))]:
            with patch.object(synthesis, function, side_effect=error), patch.object(synthesis.openai_client, 'request_text') as request:
                with self.assertRaises(synthesis.HorizonSynthesisError) as caught:
                    historical_generation.synthesize_horizon(helper.context)
                self.assertEqual(caught.exception.substage, substage)
                self.assertEqual(caught.exception.error_type, type(error).__name__)
                self.assertNotIn('SECRET', str(caught.exception))
                request.assert_not_called()

    def test_pipeline_preserves_typed_synthesis_diagnostic(self):
        from src import horizon_pipeline as pipeline
        from src.horizon_synthesis import HorizonSynthesisError
        # Exercise existing complete fixtures; typed diagnostic is produced at the
        # same synthesis boundary as local packet preparation.
        def fail(context):
            raise HorizonSynthesisError('PRE_REQUEST', substage='PACKET_CONSTRUCTION', error_type='KeyError')
        with patch('historical_generation.synthesize_horizon', side_effect=fail):
            # exercise's synthesis wrapper uses the real imported entry at runtime.
            with self.assertRaises(pipeline.HorizonPipelineError) as caught:
                self.exercise('MEDIUM', risks=True)
        self.assertEqual(caught.exception.substage, 'PACKET_CONSTRUCTION')
        self.assertEqual(caught.exception.error_type, 'KeyError')
        self.assertEqual(caught.exception.failure_type, 'PRE_REQUEST')

    def test_technical_stage_diagnostics_survive_combined_boundary(self):
        from contextlib import ExitStack
        from src import technical_pipeline as backend, horizon_pipeline as pipeline
        snapshot, _ = fixtures.TechnicalAnalystTests().fixture()
        cases = [('retrieve_historical_ohlcv', 'MARKET_DATA', RuntimeError),
                 ('build_technical_feature_snapshot', 'FEATURES', ValueError),
                 ('build_technical_research_snapshot', 'EVIDENCE', TypeError),
                 ('build_technical_evidence_catalog', 'EVIDENCE', ValueError),
                 ('analyze_technical_snapshot', 'TECHNICAL_ANALYST', RuntimeError),
                 ('analyze_technical_snapshot', 'TECHNICAL_ANALYST', KeyError)]
        for function, substage, error_type in cases:
            with self.subTest(function=function, error=error_type), ExitStack() as stack:
                stack.enter_context(patch('sqlite3.connect', side_effect=AssertionError('No persistence')))
                stack.enter_context(patch.object(backend, 'retrieve_historical_ohlcv', return_value=snapshot.historical_ohlcv))
                failing = stack.enter_context(patch.object(backend, function, side_effect=error_type('SECRET raw provider prompt')))
                technical = stack.enter_context(patch.object(pipeline, 'run_technical_research', wraps=backend.run_technical_research))
                fundamental = stack.enter_context(patch.object(pipeline, 'run_stock_research'))
                synthesis = stack.enter_context(patch.object(pipeline, 'synthesize_horizon'))
                builder = stack.enter_context(patch.object(pipeline.policy, 'build_integration_context'))
                with self.assertRaises(pipeline.HorizonPipelineError) as caught:
                    pipeline.run_horizon_research('TEST', 'MEDIUM', fundamental_horizon='MEDIUM',
                        technical_as_of=snapshot.historical_ohlcv.requested_as_of, market_verified=True)
                error = caught.exception
                self.assertEqual((error.stage, error.substage, error.error_type, error.failure_type),
                                 ('TECHNICAL_RESEARCH', substage, error_type.__name__, 'TechnicalResearchError'))
                self.assertNotIn('SECRET', str(error) + repr(vars(error)))
                self.assertTrue(error.__suppress_context__)
                technical.assert_called_once()
                failing.assert_called_once()
                fundamental.assert_not_called()
                builder.assert_not_called()
                synthesis.assert_not_called()

    def test_malformed_technical_response_preserves_safe_type(self):
        from src import technical_pipeline as backend, horizon_pipeline as pipeline
        snapshot, _ = fixtures.TechnicalAnalystTests().fixture()
        with patch.object(backend, 'retrieve_historical_ohlcv', return_value=snapshot.historical_ohlcv), \
             patch('src.openai_client.request_text', return_value='SECRET not JSON') as request, \
             patch.object(pipeline, 'run_stock_research') as fundamental, \
             patch.object(pipeline, 'synthesize_horizon') as synthesis:
            with self.assertRaises(pipeline.HorizonPipelineError) as caught:
                pipeline.run_horizon_research('TEST', 'MEDIUM', fundamental_horizon='MEDIUM',
                    technical_as_of=snapshot.historical_ohlcv.requested_as_of, market_verified=True)
            self.assertEqual(caught.exception.stage, 'TECHNICAL_RESEARCH')
            self.assertEqual(caught.exception.substage, 'TECHNICAL_ANALYST')
            self.assertEqual(caught.exception.error_type, 'TechnicalGenerationError')
            self.assertNotIn('SECRET', str(caught.exception) + repr(vars(caught.exception)))
            request.assert_called_once()
            fundamental.assert_not_called()
            synthesis.assert_not_called()


class TechnicalValidationDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch('socket.socket.connect', side_effect=AssertionError('No network'))
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_response_failure_matrix_through_combined_pipeline(self):
        from copy import deepcopy
        from src import technical_pipeline as backend, horizon_pipeline as pipeline
        helper = fixtures.TechnicalAnalystTests()
        snapshot, catalog = helper.fixture()
        valid = helper.output(catalog, 'BULLISH')
        cases = [('', 'INVALID_JSON'), ('SECRET not JSON', 'INVALID_JSON'),
                 ('null', 'SCHEMA_INVALID'), ('{}', 'SCHEMA_INVALID')]
        def change(code, field, value):
            data = deepcopy(valid)
            data[field] = value
            cases.append((json.dumps(data), code))
        change('SIGNAL_CONFIDENCE_INVALID', 'signal', 'BUY')
        for confidence in (-1, 101, True, 0.5):
            change('SIGNAL_CONFIDENCE_INVALID', 'confidence', confidence)
        change('CITATION_SHAPE_INVALID', 'supporting_evidence_ids', [None])
        for field in ('supporting_evidence_ids', 'conflicting_evidence_ids'):
            change('CITATION_INVALID', field, ['SECRET_UNKNOWN'])
        change('CITATION_INVALID', 'supporting_evidence_ids', [])
        change('CITATION_INVALID', 'supporting_evidence_ids', valid['supporting_evidence_ids'] * 2)
        change('CITATION_OVERLAP', 'conflicting_evidence_ids', valid['supporting_evidence_ids'])
        change('MISSING_ACK_INCOMPLETE', 'missing_evidence_ids', [])
        change('CONFIDENCE_EVIDENCE_CONFLICT', 'confidence', 91)
        change('STATEMENT_INVALID', 'summary', {'text': 'SECRET'})
        for code, text in [('TEXT_INVALID', ''), ('PROHIBITED_CLAIM', 'Buy now.'),
                           ('FEATURE_CITATION_MISSING', 'sma_200 is uncertain.'),
                           ('NUMERIC_PROSE', 'Momentum is 123.'),
                           ('SIGNAL_THESIS_CONFLICT', 'The thesis is bearish.')]:
            change(code, 'summary', {'text': text, 'evidence_ids': valid['supporting_evidence_ids']})
        change('STATEMENT_ARRAY_INVALID', 'risk_notes', None)
        for field in ('confirmation_conditions', 'invalidation_conditions'):
            change('CONDITIONS_REQUIRED', field, [])
        change('MISSING_NOTE_INVALID', 'missing_data_acknowledgement', None)
        # Response horizons are not model-owned: an extra horizon is a schema error.
        change('SCHEMA_INVALID', 'horizon', 'SHORT_TERM_1_TO_5_SESSIONS')
        before = asdict(snapshot), asdict(catalog)
        for response, code in cases:
            with self.subTest(code=code, response=response), \
                 patch('sqlite3.connect', side_effect=AssertionError('No persistence')), \
                 patch.object(backend, 'retrieve_historical_ohlcv', return_value=snapshot.historical_ohlcv) as retrieve, \
                 patch.object(pipeline, 'run_technical_research', wraps=backend.run_technical_research) as technical, \
                 patch.object(backend, 'analyze_technical_snapshot', historical_generation.analyze_technical_snapshot), \
                 patch('src.openai_client.request_text', return_value=response) as request, \
                 patch.object(pipeline, 'run_stock_research') as fundamental, \
                 patch.object(pipeline, 'synthesize_horizon') as synthesis:
                with self.assertRaises(pipeline.HorizonPipelineError) as caught:
                    pipeline.run_horizon_research('TEST', 'MEDIUM', fundamental_horizon='MEDIUM',
                        technical_as_of=snapshot.historical_ohlcv.requested_as_of, market_verified=True)
                error = caught.exception
                self.assertEqual((error.stage, error.substage, error.error_type),
                                 ('TECHNICAL_RESEARCH', 'TECHNICAL_ANALYST', 'ValueError'))
                self.assertEqual(error.validation_reason, 'TECHNICAL_ANALYST_' + code)
                self.assertNotIn('SECRET', str(error) + repr(vars(error)))
                self.assertEqual(error.__context__.validation_reason, error.validation_reason)
                self.assertTrue(error.__suppress_context__)
                request.assert_called_once()
                retrieve.assert_called_once()
                technical.assert_called_once()
                fundamental.assert_not_called()
                synthesis.assert_not_called()
        self.assertEqual(before, (asdict(snapshot), asdict(catalog)))

    def test_valid_rich_response_shapes_unchanged(self):
        from copy import deepcopy
        helper = fixtures.TechnicalAnalystTests()
        snapshot, catalog = helper.fixture(200)
        available = [i.evidence_id for i in catalog.items if i.value is not None]
        for signal in ('BULLISH', 'NEUTRAL', 'BEARISH'):
            for confidence in (0, 90, 100):
                data = helper.output(catalog, signal)
                data['confidence'] = confidence
                refs = list(dict.fromkeys(data['supporting_evidence_ids'] + available[:2]))
                data['supporting_evidence_ids'] = refs
                data['summary'] = {'text': 'Mixed evidence — caution; “conditional” remains uncertain.', 'evidence_ids': refs}
                data['conflicting_evidence_ids'] = [] if confidence == 100 else [next(i for i in available if i not in refs)]
                original = deepcopy(data)
                result = helper.run_output(data, snapshot, catalog, 'SWING_1_TO_4_WEEKS')
                self.assertEqual(data, original)
                self.assertEqual(result.analysis.signal, signal)
                self.assertEqual(result.analysis.confidence, confidence)
                self.assertEqual(result.analysis.summary.evidence_ids, tuple(refs))
                self.assertEqual(result.analysis.conflicting_evidence_ids, tuple(data['conflicting_evidence_ids']))
                for field in ('confirmation_conditions', 'invalidation_conditions', 'risk_notes'):
                    self.assertTrue(getattr(result.analysis, field))

    def test_preflight_codes_and_client_errors_remain_distinct(self):
        from src import technical_analyst as analyst, technical_pipeline as backend
        helper = fixtures.TechnicalAnalystTests()
        snapshot, catalog = helper.fixture()
        tiny, tiny_catalog = helper.fixture(1)
        cases = [(snapshot, catalog, 'UNKNOWN', 'HORIZON_INVALID'),
                 (None, catalog, analyst.HORIZONS[0], 'INPUT_INVALID'),
                 (snapshot, replace(catalog, methodology_version='future'), analyst.HORIZONS[0], 'CATALOG_MISMATCH'),
                 (tiny, tiny_catalog, analyst.HORIZONS[0], 'INSUFFICIENT_EVIDENCE')]
        with patch('src.openai_client.request_text') as request:
            for s, c, h, code in cases:
                with self.assertRaises(backend.TechnicalResearchError) as caught:
                    backend.step('TECHNICAL_ANALYST', historical_generation.analyze_technical_snapshot, s, c, h)
                self.assertEqual(caught.exception.validation_reason, 'TECHNICAL_ANALYST_' + code)
            request.assert_not_called()
        # Duplicate IDs are normally rejected earlier by trusted-catalog equality.
        duplicate = replace(catalog, items=catalog.items + (catalog.items[0],))
        with patch.object(analyst, 'build_technical_evidence_catalog', return_value=duplicate), \
             patch('src.openai_client.request_text') as request:
            with self.assertRaises(analyst.TechnicalValidationError) as caught:
                analyst.analyze_technical_snapshot(snapshot, duplicate, analyst.HORIZONS[0])
            self.assertEqual(caught.exception.validation_reason, 'TECHNICAL_ANALYST_CATALOG_DUPLICATE_IDS')
            request.assert_not_called()
        for message in ('OpenAI returned no text.', 'SECRET API body'):
            with patch('src.openai_client.request_text', side_effect=RuntimeError(message)) as request:
                with self.assertRaises(backend.TechnicalResearchError) as caught:
                    backend.step('TECHNICAL_ANALYST', historical_generation.analyze_technical_snapshot, snapshot, catalog, analyst.HORIZONS[0])
                self.assertIsNone(caught.exception.validation_reason)
                self.assertEqual(caught.exception.exception_type, 'RuntimeError')
                self.assertNotIn(message, str(caught.exception) + repr(vars(caught.exception)))
                request.assert_called_once()
        self.assertIsNone(backend.TechnicalResearchError('TECHNICAL_ANALYST', 'ValueError', 'SECRET').validation_reason)

    def test_dashboard_keeps_existing_sanitized_presentation(self):
        from src.dashboard import technical_adapter as adapter
        from src import technical_pipeline as backend
        from src.technical_analyst import TechnicalValidationError
        snapshot, _ = fixtures.TechnicalAnalystTests().fixture()
        with patch.object(backend, 'retrieve_historical_ohlcv', return_value=snapshot.historical_ohlcv), \
             patch.object(backend, 'analyze_technical_snapshot', side_effect=TechnicalValidationError('TECHNICAL_ANALYST_CITATION_INVALID')), \
             self.assertLogs('src.dashboard.technical_adapter', level='ERROR') as logs:
            with self.assertRaises(adapter.TechnicalActionError) as caught:
                adapter.run_technical_research('TEST', 'SWING_1_TO_4_WEEKS', snapshot.historical_ohlcv.requested_as_of, market_verified=True)
        self.assertEqual(str(caught.exception), 'Technical technical analyst unavailable. Check inputs, source and server configuration; no automatic retry occurs.')
        self.assertIn('exception=ValueError', logs.output[0])
        self.assertNotIn('CITATION_INVALID', logs.output[0] + str(caught.exception))


class HorizonSemanticDiagnosticTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No live network'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_every_semantic_reason_through_real_combined_boundary(self):
        from src.horizon_synthesis import SEMANTIC_REASONS
        def top(key, value):
            return lambda data: data.__setitem__(key, value)
        def statement(field, key, value):
            return lambda data: data[field].__setitem__(key, value)
        cases = [
            ('POSTURE_NOT_ALLOWED', top('timing_posture', 'NO_ACTION')),
            ('LIMITATIONS_MISMATCH', top('acknowledged_limitations', ['SECRET'])),
            ('INVALIDATION_REFERENCE_REQUIRED', statement('invalidation_summary', 'condition_ids', [])),
            ('INVALIDATION_REFERENCE_REQUIRED', statement('invalidation_summary', 'condition_ids', ['T_CONFIRMATION:0'])),
            ('CONDITION_REQUIRES_FORECAST', statement('invalidation_summary', 'classification', 'AI_INTERPRETATION')),
            ('NUMERIC_PROSE', statement('synthesis_summary', 'text', 'SECRET observed 123.')),
            ('PROHIBITED_ACTION_LANGUAGE', statement('synthesis_summary', 'text', 'SECRET portfolio allocation.')),
            ('PREDICTIVE_TEXT_REQUIRES_FORECAST', statement('synthesis_summary', 'text', 'The evidence could strengthen.')),
            ('WAIT_CONDITION_REQUIRED', top('timing_posture', 'WAIT_FOR_CONFIRMATION')),
        ]
        for namespace in ('fundamental', 'technical'):
            def overlap(data, namespace=namespace):
                data[f'conflicting_{namespace}_evidence_ids'] = data[f'supporting_{namespace}_evidence_ids'][:]
            cases.append(('EVIDENCE_ROLE_OVERLAP', overlap))
        covered = set()
        for reason, mutate in cases:
            reason = 'HORIZON_SYNTHESIS_' + reason
            covered.add(reason)
            with self.subTest(reason=reason):
                CombinedPipelineTests().exercise('MEDIUM', risks=True, rich=True,
                    response_mutator=mutate, expected_semantic=reason)
        self.assertEqual(covered, SEMANTIC_REASONS)

    def test_valid_edges_preserve_frozen_view_and_namespaces(self):
        from copy import deepcopy
        from dataclasses import FrozenInstanceError
        from src.horizon_synthesis import _packet, _validate, HorizonSynthesisError
        helper = HorizonSynthesisTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        original = helper.context
        for posture in ('FAVORABLE_NOW', 'WAIT_FOR_CONFIRMATION', 'UNRESOLVED'):
            for confidence in (0, 100):
                data = helper.output(posture=posture)
                data['synthesis_confidence'] = confidence
                before = deepcopy(data)
                view = helper.invoke(data)
                self.assertEqual(data, before)
                self.assertEqual(view.context, original)
                self.assertEqual(view.analysis, data)
                with self.assertRaises(FrozenInstanceError):
                    view.analysis_json = '{}'
        # Packet parser coverage of the existing matrix, never bypass the IO readiness gate.
        for direction, signal, posture in [('NEUTRAL', 'NEUTRAL', 'NO_ACTION'),
                                           ('UNFAVORABLE', 'BEARISH', 'UNFAVORABLE_NOW')]:
            context = replace(original, fundamental=replace(original.fundamental, direction=FundamentalDirection(direction)),
                              technical=replace(original.technical, recommendation=signal))
            packet = _packet(context)
            data = helper.output(context, posture)
            packet['limitations'] = []
            data['acknowledged_limitations'] = []
            self.assertEqual(json.loads(_validate(data, packet)), data)
        def rich(data):
            data['synthesis_summary']['fundamental_evidence_ids'] = ['E001', 'E002']
            data['synthesis_summary']['technical_evidence_ids'] = ['T001', 'T002']
            data['conflicting_fundamental_evidence_ids'] = ['E002']
            data['conflicting_technical_evidence_ids'] = ['T001', 'T002']
            data['major_integrated_risks'] = [deepcopy(data['agreement_explanation'])]
        CombinedPipelineTests().exercise('MEDIUM', risks=True, rich=True, response_mutator=rich)
        self.assertIsNone(HorizonSynthesisError('SEMANTIC_VALIDATION', semantic_reason='SECRET').semantic_reason)

    def test_other_classifications_are_not_relabeled_semantic(self):
        from src.horizon_synthesis import HorizonSynthesisError
        helper = HorizonSynthesisTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        for field in helper.output()['identity']:
            data = helper.output()
            data['identity'][field] = 'CHANGED'
            with self.assertRaises(HorizonSynthesisError) as caught:
                helper.invoke(data)
            self.assertEqual(caught.exception.synthesis_failure_type, 'IDENTITY_MISMATCH')
            self.assertIsNone(caught.exception.semantic_reason)
        for field, value, kind in [
            ('synthesis_confidence', 101, 'SCHEMA_VALIDATION'),
            ('timing_posture', 'BUY', 'INVALID_ENUM'),
            ('supporting_fundamental_evidence_ids', ['SECRET'], 'INVALID_EVIDENCE_REFERENCE'),
            ('conflicting_technical_evidence_ids', ['SECRET'], 'INVALID_EVIDENCE_REFERENCE')]:
            data = helper.output()
            data[field] = value
            with self.assertRaises(HorizonSynthesisError) as caught:
                helper.invoke(data)
            self.assertEqual(caught.exception.synthesis_failure_type, kind)
            self.assertIsNone(caught.exception.semantic_reason)

    def test_remaining_structural_and_evidence_branches_fail_closed(self):
        from src.horizon_synthesis import HorizonSynthesisError, _packet
        from historical_generation import synthesize_horizon
        helper = HorizonSynthesisTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        packet = _packet(helper.context)
        cases = []
        def top(kind, key, value):
            data = helper.output(); data[key] = value; cases.append((data, kind))
        def statement(kind, key, value):
            data = helper.output(); data['agreement_explanation'][key] = value; cases.append((data, kind))
        cases.append(({}, 'SCHEMA_VALIDATION'))
        top('SCHEMA_VALIDATION', 'supporting_fundamental_evidence_ids', [None])
        top('INVALID_EVIDENCE_REFERENCE', 'supporting_fundamental_evidence_ids', ['E001', 'E001'])
        top('SCHEMA_VALIDATION', 'synthesis_summary', {})
        statement('INVALID_ENUM', 'classification', 'RETRIEVED_FACT')
        statement('INVALID_EVIDENCE_REFERENCE', 'condition_ids', ['SECRET'])
        statement('SCHEMA_VALIDATION', 'text', '')
        top('SCHEMA_VALIDATION', 'major_integrated_risks', None)
        data = helper.output()
        data['agreement_explanation']['fundamental_evidence_ids'] = []
        data['agreement_explanation']['technical_evidence_ids'] = []
        cases.append((data, 'INVALID_EVIDENCE_REFERENCE'))
        data = helper.output()
        data['synthesis_summary']['fundamental_evidence_ids'] = []
        cases.append((data, 'INVALID_EVIDENCE_REFERENCE'))
        for condition in ('F_INVALIDATION:0', 'T_CONFIRMATION:0'):
            data = helper.output()
            stmt = data['agreement_explanation']
            stmt['condition_ids'] = [condition]; stmt['classification'] = 'FORECAST'
            stmt['fundamental_evidence_ids' if condition.startswith('F_') else 'technical_evidence_ids'] = []
            cases.append((data, 'INVALID_EVIDENCE_REFERENCE'))
        # Valid known feature name without its own reference is rejected.
        cited = helper.output()['agreement_explanation']['technical_evidence_ids']
        row = next(row for row in packet['technical']['catalog'] if row['evidence_id'] not in cited)
        statement('INVALID_EVIDENCE_REFERENCE', 'text', row['label'])
        for data, kind in cases:
            with self.subTest(kind=kind), \
                 patch('src.openai_client.request_text', return_value=json.dumps(data)) as request, \
                 patch('sqlite3.connect', side_effect=AssertionError('No persistence')):
                with self.assertRaises(HorizonSynthesisError) as caught:
                    synthesize_horizon(helper.context)
                self.assertEqual(caught.exception.synthesis_failure_type, kind)
                self.assertIsNone(caught.exception.semantic_reason)
                request.assert_called_once()


class TechnicalProhibitedClaimTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No network'))
        guard.start(); self.addCleanup(guard.stop)
        self.helper = fixtures.TechnicalAnalystTests()
        self.snapshot, self.catalog = self.helper.fixture(200)

    def parse_text(self, text, field='summary'):
        from src.technical_analyst import _preflight, _parse, HORIZONS
        data = self.helper.output(self.catalog)
        if field == 'missing_data_acknowledgement':
            data[field] = text
        else:
            item = data[field][0] if isinstance(data[field], list) else data[field]
            item['text'] = text
            item['evidence_ids'] = [i.evidence_id for i in self.catalog.items if i.value is not None]
        items, available = _preflight(self.snapshot, self.catalog, HORIZONS[0])
        return _parse(data, items, available)

    def test_phrase_matrix_existing_lexical_and_numeric_contract(self):
        from src.technical_analyst import TechnicalValidationError
        accepted = [
            'Momentum remains positive.', 'Price is above sma_50.',
            'Volume is elevated relative to its recent average.',
            'The setup would weaken if momentum turns negative.',
            'Confirmation would require continued strength in trend evidence.',
            'The short-term signal is bullish but conflicting evidence remains.',
            'The signal weakens if momentum deteriorates.', 'Wait for confirmation.',
            'Selling pressure is elevated.', 'The evidence supports caution.',
            'Momentum informs the interpretation.',
        ]
        prohibited = [
            'Buy at $123.', 'SELL at $123.', 'Set a limit order at $123.',
            'Place a stop-loss at the recent low.', 'Take-profit is not specified.',
            'A breakout above recent highs would strengthen the setup.',
            'Resistance remains overhead.', 'Support is weakening.',
            'The evidence provides support for the thesis.', 'No buy instruction is supplied.',
            'The current quote is unavailable.', 'The order of indicators is unchanged.',
            '"support"', 'STOP/LOSS is absent.', 'stopXloss is absent.',
            'allocation is outside scope.',
        ]
        numeric = [
            'Price is above its 50-day moving average.',
            'Volume is elevated relative to the 20-day average.',
            'A move above the 20-day high would confirm momentum.',
            'Enter at $123.', 'Sell price was $123.', 'Place a stop at $123.',
            'Target $123.', 'Exit the position at $123.', 'Price was 123.45.',
            'Momentum is 5%.', 'Price is above SMA50.',
        ]
        # Sell is caught before digits: explicit first-failure ordering.
        numeric.remove('Sell price was $123.')
        prohibited.append('Sell price was $123.')
        for text in accepted:
            with self.subTest(text=text): self.parse_text(text)
        for suffix, texts in [('PROHIBITED_CLAIM', prohibited), ('NUMERIC_PROSE', numeric)]:
            for text in texts:
                with self.subTest(text=text), self.assertRaises(TechnicalValidationError) as caught:
                    self.parse_text(text)
                self.assertEqual(caught.exception.validation_reason, 'TECHNICAL_ANALYST_' + suffix)
        # Characterize documented lexical limitations; acceptance is NOT contract approval.
        for text in ['Enter now.', 'Exit the position.', 'Target the prior high.',
                     'Place a stop at the prior low.', 'Price could test prior highs.',
                     'Downside risk increases below the recent low.', 'current  quote',
                     'stoploss', 'stop--loss']:
            with self.subTest(known_lexical_limit=text): self.parse_text(text)

    def test_identical_rule_in_every_actual_text_field(self):
        from src.technical_analyst import TechnicalValidationError
        for field in ('summary', 'thesis', 'confirmation_conditions', 'invalidation_conditions',
                      'risk_notes', 'missing_data_acknowledgement'):
            with self.subTest(field=field):
                self.parse_text('Momentum informs the interpretation.', field)
                with self.assertRaises(TechnicalValidationError) as caught:
                    self.parse_text('The evidence provides support.', field)
                self.assertEqual(caught.exception.validation_reason, 'TECHNICAL_ANALYST_PROHIBITED_CLAIM')

    def test_prompt_clarification_and_valid_request_regression(self):
        from src.technical_analyst import INSTRUCTIONS, HORIZONS
        self.assertIn('even in negated, quoted or benign descriptive prose', INSTRUCTIONS)
        self.assertIn('including missing-data acknowledgement', INSTRUCTIONS)
        for signal in ('BULLISH', 'NEUTRAL', 'BEARISH'):
            for horizon in HORIZONS:
                data = self.helper.output(self.catalog, signal)
                result = self.helper.run_output(data, self.snapshot, self.catalog, horizon)
                self.assertEqual(result.analysis.signal, signal)
                self.assertEqual(result.horizon, horizon)


class HorizonConditionForecastTests(unittest.TestCase):
    def setUp(self):
        self.helper = HorizonSynthesisTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)

    def test_condition_reference_matrix_and_source_preservation(self):
        from src.horizon_synthesis import _packet, HorizonSynthesisError
        context = self.helper.context
        packet = _packet(context)
        before = (context.fundamental.source, context.technical.source)
        texts = [
            'The Technical Analyst identified continued momentum as confirmation.',
            'The source invalidation condition remains a deterioration in trend.',
            'The analyst has identified a confirmation condition.',
            'If momentum continues, the setup strengthens.',
            'Confirmation requires continued positive momentum.',
            'The source thesis would weaken if momentum turns negative.',
            'The condition has already occurred.', 'The condition may occur.',
            'Watch for the condition.',
        ]
        for condition_id, condition in packet['conditions'].items():
            for text in texts:
                data = self.helper.output()
                stmt = data['agreement_explanation']
                stmt['text'] = text
                stmt['condition_ids'] = [condition_id]
                field = 'fundamental_evidence_ids' if condition_id.startswith('F_') else 'technical_evidence_ids'
                stmt[field] = condition['evidence_refs' if condition_id.startswith('F_') else 'evidence_ids']
                with self.subTest(condition=condition_id, text=text):
                    with self.assertRaises(HorizonSynthesisError) as caught:
                        self.helper.invoke(data)
                    self.assertEqual(caught.exception.semantic_reason, 'HORIZON_SYNTHESIS_CONDITION_REQUIRES_FORECAST')
                    stmt['classification'] = 'FORECAST'
                    view = self.helper.invoke(data)
                    self.assertEqual(view.context, context)
        self.assertEqual(before, (context.fundamental.source, context.technical.source))

    def test_all_statement_fields_require_forecast_for_conditions(self):
        from src.horizon_synthesis import NARRATIVES, HorizonSynthesisError
        for field in (*NARRATIVES, 'major_integrated_risks'):
            data = self.helper.output()
            statement = dict(data['invalidation_summary'])
            statement['classification'] = 'AI_INTERPRETATION'
            data[field] = [statement] if field == 'major_integrated_risks' else statement
            with self.subTest(field=field), self.assertRaises(HorizonSynthesisError) as caught:
                self.helper.invoke(data)
            self.assertEqual(caught.exception.semantic_reason, 'HORIZON_SYNTHESIS_CONDITION_REQUIRES_FORECAST')
            statement['classification'] = 'FORECAST'
            self.helper.invoke(data)

    def test_current_state_and_separate_predictive_rule(self):
        from src.horizon_synthesis import INSTRUCTIONS, HorizonSynthesisError
        self.assertIn('EVERY statement with nonempty condition_ids', INSTRUCTIONS)
        self.assertIn('including descriptive attribution', INSTRUCTIONS)
        for text in ['Momentum is positive.', 'The Technical signal is bullish.',
                     'The source contains a confirmation condition.']:
            data = self.helper.output()
            data['agreement_explanation']['text'] = text
            result = self.helper.invoke(data)
            self.assertEqual(result.analysis['agreement_explanation']['classification'], 'AI_INTERPRETATION')
        data = self.helper.output()
        data['agreement_explanation']['text'] = 'The thesis would weaken if momentum turns negative.'
        with self.assertRaises(HorizonSynthesisError) as caught:
            self.helper.invoke(data)
        self.assertEqual(caught.exception.semantic_reason, 'HORIZON_SYNTHESIS_PREDICTIVE_TEXT_REQUIRES_FORECAST')
        # Characterize existing lexical limits, not semantic endorsement of the claims.
        for text in ['If momentum continues, the setup strengthens.', 'The condition may occur.',
                     'The condition has already occurred.']:
            data = self.helper.output(); data['agreement_explanation']['text'] = text
            self.helper.invoke(data)


class HorizonEvidenceRoleTests(unittest.TestCase):
    def setUp(self):
        self.helper = HorizonSynthesisTests(); self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)

    def test_role_matrix_and_safe_namespace_propagation(self):
        from src.horizon_synthesis import HorizonSynthesisError
        for namespace in ('fundamental', 'technical'):
            support = f'supporting_{namespace}_evidence_ids'
            conflict = f'conflicting_{namespace}_evidence_ids'
            data = self.helper.output()
            # A global conflicting ID can still ground multiple statement citations.
            data[conflict] = data[support][:]; data[support] = []
            self.helper.invoke(data)
            def overlap(data, support=support, conflict=conflict):
                data[conflict] = data[support][:]
            CombinedPipelineTests().exercise('MEDIUM', risks=True, rich=True,
                response_mutator=overlap, expected_semantic='HORIZON_SYNTHESIS_EVIDENCE_ROLE_OVERLAP',
                expected_namespace=namespace.upper())
            for value in (['UNKNOWN'], self.helper.output()[support] * 2):
                data = self.helper.output(); data[conflict] = value
                with self.assertRaises(HorizonSynthesisError) as caught:
                    self.helper.invoke(data)
                self.assertEqual(caught.exception.synthesis_failure_type, 'INVALID_EVIDENCE_REFERENCE')
                self.assertIsNone(caught.exception.evidence_namespace)
        self.assertIsNone(HorizonSynthesisError('SEMANTIC_VALIDATION',
            semantic_reason='HORIZON_SYNTHESIS_EVIDENCE_ROLE_OVERLAP', evidence_namespace='SECRET').evidence_namespace)

    def test_namespace_identity_and_role_scope_parser_contract(self):
        from copy import deepcopy
        from src.horizon_synthesis import _packet, _validate
        packet = _packet(self.helper.context)
        data = self.helper.output()
        # Parser-only hypothetical catalog collision; no forged context crosses readiness.
        fid = data['supporting_fundamental_evidence_ids'][0]
        tid = data['supporting_technical_evidence_ids'][0]
        for row in packet['technical']['catalog']:
            if row['evidence_id'] == tid: row['evidence_id'] = fid
        for value in packet['conditions'].values():
            if 'evidence_ids' in value:
                value['evidence_ids'] = [fid if x == tid else x for x in value['evidence_ids']]
        for field in ('synthesis_summary','agreement_explanation','horizon_interpretation','invalidation_summary'):
            data[field]['technical_evidence_ids'] = [fid]
        data['supporting_technical_evidence_ids'] = []
        data['conflicting_technical_evidence_ids'] = [fid]
        original = deepcopy(data)
        self.assertEqual(json.loads(_validate(data, packet)), original)
        # Role fields do not exist inside statements; adding them is a schema error.
        from src.horizon_synthesis import HorizonSynthesisError
        data['agreement_explanation']['supporting_evidence_ids'] = [fid]
        with self.assertRaises(HorizonSynthesisError) as caught: _validate(data, packet)
        self.assertEqual(caught.exception.synthesis_failure_type, 'SCHEMA_VALIDATION')


class TechnicalFeatureCitationTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No network'))
        guard.start(); self.addCleanup(guard.stop)
        self.helper = fixtures.TechnicalAnalystTests()
        self.snapshot, self.catalog = self.helper.fixture(200)

    def output(self, text, refs):
        data = self.helper.output(self.catalog)
        data['summary'] = dict(text=text, evidence_ids=refs)
        return data

    def test_every_catalog_label_statement_grounding(self):
        from src.technical_analyst import FEATURE_FAMILIES, TechnicalValidationError
        self.assertEqual(FEATURE_FAMILIES, {i.label for i in self.catalog.items})
        for item in self.catalog.items:
            unrelated = next(i.evidence_id for i in self.catalog.items if i.evidence_id != item.evidence_id)
            for text in (item.label+' informs the interpretation.', '('+item.label.upper()+').'):
                with self.subTest(label=item.label, text=text):
                    self.helper.run_output(self.output(text, [item.evidence_id]), self.snapshot, self.catalog)
                    with self.assertRaises(TechnicalValidationError) as caught:
                        self.helper.run_output(self.output(text, [unrelated]), self.snapshot, self.catalog)
                    self.assertEqual(caught.exception.validation_reason, 'TECHNICAL_ANALYST_FEATURE_CITATION_MISSING')
                    self.assertEqual(caught.exception.feature_family, item.label)
            with self.assertRaises(TechnicalValidationError) as caught:
                self.helper.run_output(self.output(item.label, []), self.snapshot, self.catalog)
            self.assertEqual(caught.exception.validation_reason, 'TECHNICAL_ANALYST_CITATION_INVALID')
            data = self.output(item.label, [item.evidence_id])
            data['supporting_evidence_ids'] = [unrelated]
            data['conflicting_evidence_ids'] = [item.evidence_id]
            self.helper.run_output(data, self.snapshot, self.catalog)
            data['summary']['evidence_ids'] = [unrelated]
            with self.assertRaises(TechnicalValidationError): self.helper.run_output(data, self.snapshot, self.catalog)
            self.helper.run_output(self.output('The evidence is mixed.', [item.evidence_id]), self.snapshot, self.catalog)

    def test_longer_label_regression_multiple_features_and_missing_data(self):
        from src.technical_analyst import TechnicalValidationError
        ids = {i.label:i.evidence_id for i in self.catalog.items}
        for label in ('sma_200','close_vs_sma_20_pct','close_vs_sma_50_pct','close_vs_sma_200_pct'):
            self.helper.run_output(self.output(label+' informs the thesis.', [ids[label]]), self.snapshot, self.catalog)
        text = 'sma_200 and sma_20 inform the thesis.'
        self.helper.run_output(self.output(text, [ids['sma_200'],ids['sma_20']]), self.snapshot, self.catalog)
        with self.assertRaises(TechnicalValidationError) as caught:
            self.helper.run_output(self.output(text, [ids['sma_200']]), self.snapshot, self.catalog)
        self.assertEqual(caught.exception.feature_family, 'sma_20')
        snapshot, catalog = self.helper.fixture(50)
        data = self.helper.output(catalog)
        data['summary']['text'] = 'sma_200 informs this view.'
        with self.assertRaises(TechnicalValidationError) as caught: self.helper.run_output(data, snapshot, catalog)
        self.assertEqual(caught.exception.feature_family, 'sma_200')
        data['summary']['evidence_ids'] = [ids['sma_200']]
        with self.assertRaises(TechnicalValidationError) as caught: self.helper.run_output(data, snapshot, catalog)
        self.assertEqual(caught.exception.validation_reason, 'TECHNICAL_ANALYST_CITATION_INVALID')
        data = self.helper.output(catalog)
        data['missing_data_acknowledgement'] = 'sma_200 is unavailable.'
        self.helper.run_output(data, snapshot, catalog)

    def test_feature_family_reaches_combined_error_safely(self):
        from src import technical_pipeline as backend, horizon_pipeline as pipeline
        ids = {i.label:i.evidence_id for i in self.catalog.items}
        data = self.output('sma_200 informs the view.', [ids['momentum_5']])
        with patch.object(backend,'retrieve_historical_ohlcv',return_value=self.snapshot.historical_ohlcv), \
             patch.object(backend, 'analyze_technical_snapshot', historical_generation.analyze_technical_snapshot), \
             patch('src.openai_client.request_text',return_value=json.dumps(data)) as request, \
             patch.object(pipeline,'run_stock_research') as fundamental, \
             patch.object(pipeline,'synthesize_horizon') as synthesis, \
             patch('sqlite3.connect',side_effect=AssertionError('No DB')):
            with self.assertRaises(pipeline.HorizonPipelineError) as caught:
                pipeline.run_horizon_research('TEST','MEDIUM',fundamental_horizon='MEDIUM',
                    technical_as_of=self.snapshot.historical_ohlcv.requested_as_of,market_verified=True)
            self.assertEqual(caught.exception.feature_family,'sma_200')
            self.assertEqual(caught.exception.substage,'TECHNICAL_ANALYST')
            self.assertEqual(caught.exception.error_type,'ValueError')
            request.assert_called_once(); fundamental.assert_not_called(); synthesis.assert_not_called()
        self.assertIsNone(backend.TechnicalResearchError('TECHNICAL_ANALYST','ValueError',
            'TECHNICAL_ANALYST_FEATURE_CITATION_MISSING', 'SECRET').feature_family)

    def test_broad_words_alias_limits_and_unchanged_numeric_rule(self):
        from src.technical_analyst import TechnicalValidationError
        ref = self.catalog.items[0].evidence_id
        for text in ('trend remains constructive','momentum is improving','volume is elevated',
                     'volatility increased','price remains above the moving average',
                     'longer-term trend','short-term momentum','volume confirmation',
                     'momentum evidence','trend evidence','RSI is elevated','MACD is rising'):
            self.helper.run_output(self.output(text,[ref]), self.snapshot,self.catalog)
        for text in ('SMA200','SMA-200','SMA 200','momentum20','RSI14','MACD 12/26/9'):
            with self.assertRaises(TechnicalValidationError) as caught:
                self.helper.run_output(self.output(text,[ref]),self.snapshot,self.catalog)
            self.assertEqual(caught.exception.validation_reason,'TECHNICAL_ANALYST_NUMERIC_PROSE')


class ContractConstructibilityAuditTests(unittest.TestCase):
    def exercise_source_invalidations(self, fundamental_present=False, technical_present=False, horizon='MEDIUM', recommendation='Accumulate', technical_signal='NEUTRAL'):
        """Real source parsers, prospective capture and readiness; no caller-set readiness."""
        from src.analysis import _validate_analysis, build_analysis_schema
        from src.research_pipeline import run_stock_research
        from src.technical_signal_store import create_technical_signal_record
        from src.horizon_integration import require_synthesis_ready
        from src.horizon_synthesis import _packet, _validate, HorizonSynthesisError
        from historical_generation import synthesize_horizon
        with patch('socket.socket.connect', side_effect=AssertionError('No live network')), \
             patch('sqlite3.connect', side_effect=AssertionError('No persistence')):
            source = fundamental()
            packet = json.loads(source.evidence_json)
            packet['missing_data'] = []
            raw = asdict(source.record)
            raw.update(recommendation=recommendation, portfolio_assessment='No portfolio context.',
                       material_evidence_review={}, thesis_invalidation_conditions=(raw['thesis_invalidation_conditions'] if fundamental_present else []))
            raw = {key: raw[key] for key in build_analysis_schema(packet)['required']}
            # Real source parser accepts the empty list; no invented provenance capability.
            analysis = _validate_analysis(raw, packet)
            captured = []
            with patch('src.research_pipeline.build_stock_evidence', return_value=packet) as retrieval, \
                 patch('src.research_pipeline.analyze_investment', return_value=analysis) as fundamental_call, \
                 patch('src.research_pipeline.datetime') as clock:
                clock.now.side_effect = [instant('2025-03-12T14:00:00+00:00'),
                                        instant('2025-03-12T14:30:00+00:00'), instant()]
                run_stock_research('TEST', persist_decision=False, investment_horizon='LONG' if horizon == 'LONG' else 'MEDIUM',
                                   integration_run_id='run-1', on_fundamental_artifact=captured.append)
                retrieval.assert_called_once()
                fundamental_call.assert_called_once()
            helper = fixtures.TechnicalAnalystTests()
            snapshot, catalog = helper.fixture()
            technical_output = helper.output(catalog, technical_signal)
            if not technical_present:
                technical_output['invalidation_conditions'] = []
            signal = helper.run_output(technical_output, snapshot, catalog, select_technical_horizon(horizon))
            record = create_technical_signal_record(signal, catalog,
                created_at='2025-03-11T13:00:00Z', record_id='offline-no-invalidation')
            context = build_integration_context('TEST', horizon, instant(),
                fundamental=captured[0], technical=record, integration_run_id='run-1')
            validated = require_synthesis_ready(context)
            self.assertEqual(validated.readiness, 'SYNTHESIS_READY')
            self.assertEqual(validated.blocking_missing_data, ())
            synthesis_packet = _packet(validated)
            self.assertTrue(synthesis_packet['conditions'])  # Confirmation still exists.
            available = [key for key in synthesis_packet['conditions'] if 'INVALIDATION:' in key]
            self.assertEqual(len(available), int(fundamental_present) + int(technical_present))
            self.assertEqual(synthesis_packet['policy_versions']['invalidation'], 'source-available-invalidation-v1')
            self.assertEqual('NO_SOURCE_INVALIDATION_CONDITION' in synthesis_packet['limitations'], not available)
            before = (captured[0].analysis_json, record.signal_json)
            for posture in synthesis_packet['allowed_postures']:
                data = HorizonSynthesisTests().output(context, posture)
                data['invalidation_summary']['condition_ids'] = available[:1]
                data['invalidation_summary']['text'] = 'Source invalidation availability is retained.'
                if not available:
                    data['invalidation_summary']['classification'] = 'AI_INTERPRETATION'
                if available and available[0].startswith('T_'):
                    data['invalidation_summary']['technical_evidence_ids'] = synthesis_packet['conditions'][available[0]]['evidence_ids']
                with patch('src.openai_client.request_text', return_value=json.dumps(data)) as request:
                    view = synthesize_horizon(context)
                    request.assert_called_once()
                self.assertEqual(view.invalidation_policy_version, 'source-available-invalidation-v1')
                self.assertEqual(view.context, validated)
                self.assertEqual(view.context.primary_authority, primary_authority(horizon))
                with self.assertRaises(FrozenInstanceError):
                    view.invalidation_policy_version = 'modified'
                self.assertEqual(before, (captured[0].analysis_json, record.signal_json))
                if available:
                    data['invalidation_summary']['condition_ids'] = []
                    with self.assertRaises(HorizonSynthesisError) as caught:
                        _validate(data, synthesis_packet)
                    self.assertEqual(caught.exception.semantic_reason,
                        'HORIZON_SYNTHESIS_INVALIDATION_REFERENCE_REQUIRED')
                else:
                    data['acknowledged_limitations'] = synthesis_packet['limitations'][:-1]
                    with self.assertRaises(HorizonSynthesisError) as caught:
                        _validate(data, synthesis_packet)
                    self.assertEqual(caught.exception.semantic_reason, 'HORIZON_SYNTHESIS_LIMITATIONS_MISMATCH')
                    data['acknowledged_limitations'] = synthesis_packet['limitations']
                data['invalidation_summary']['condition_ids'] = ['T_CONFIRMATION:0']
                with self.assertRaises(HorizonSynthesisError) as caught:
                    _validate(data, synthesis_packet)
                self.assertEqual(caught.exception.semantic_reason,
                    'HORIZON_SYNTHESIS_INVALIDATION_REFERENCE_REQUIRED')
                data['invalidation_summary']['condition_ids'] = ['F_INVALIDATION:999']
                with self.assertRaises(HorizonSynthesisError) as caught:
                    _validate(data, synthesis_packet)
                self.assertEqual(caught.exception.synthesis_failure_type, 'INVALID_EVIDENCE_REFERENCE')

    def test_ready_zero_invalidations_now_constructible(self):
        self.exercise_source_invalidations()

    def test_source_available_invalidation_combinations(self):
        for fundamental_present, technical_present in ((True, True), (True, False), (False, True)):
            with self.subTest(fundamental=fundamental_present, technical=technical_present):
                self.exercise_source_invalidations(fundamental_present, technical_present)

    def test_absence_across_authorities_and_permitted_postures(self):
        for horizon in ('SHORT', 'SWING', 'MEDIUM', 'LONG'):
            for recommendation in ('Accumulate', 'Avoid'):
                with self.subTest(horizon=horizon, recommendation=recommendation):
                    self.exercise_source_invalidations(horizon=horizon, recommendation=recommendation)

    def test_prompt_contract_clarifications(self):
        from src.horizon_synthesis import INSTRUCTIONS
        from src.technical_analyst import INSTRUCTIONS as technical_prompt
        for phrase in ('source-available-invalidation-v1', 'NO_SOURCE_INVALIDATION_CONDITION',
                       'EACH namespace', 'including its ordering', 'confirmation IDs'):
            self.assertIn(phrase, INSTRUCTIONS)
        self.assertIn('at least one cited confirmation condition, including NEUTRAL', technical_prompt)


class CompletedContractAuditTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No live network'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_all_ready_direction_horizon_posture_combinations(self):
        helper = ContractConstructibilityAuditTests()
        for horizon in DecisionHorizon:
            for recommendation in ('Accumulate', 'Hold', 'Avoid'):
                for signal in ('BULLISH', 'NEUTRAL', 'BEARISH'):
                    with self.subTest(horizon=horizon, recommendation=recommendation, signal=signal):
                        helper.exercise_source_invalidations(True, True, horizon, recommendation, signal)

    def test_response_extraction_detail_survives_real_client_and_combined_boundary(self):
        from types import SimpleNamespace
        from src import openai_client, horizon_synthesis, horizon_pipeline
        real_request = openai_client.request_text
        real_synthesis = historical_generation.synthesize_horizon
        cases = [('incomplete', 'max_output_tokens', '{}', 'max_output_tokens'),
                 ('incomplete', 'content_filter', '{}', 'content_filter'),
                 ('incomplete', 'SECRET', '{}', 'not_completed'),
                 ('completed', None, '', 'empty_output_text')]
        def synthesis(context):
            # Restore only the real request helper, whose SDK transport is mocked below.
            with patch.object(openai_client, 'request_text', real_request):
                return real_synthesis(context)
        for status, reason, output, expected in cases:
            with self.subTest(detail=expected), \
                 patch.dict('os.environ', {'OPENAI_API_KEY': 'unit-test-placeholder'}), \
                 patch.object(openai_client, 'OpenAI') as client, \
                 patch.object(historical_generation, 'synthesize_horizon', side_effect=synthesis) as entry:
                api = client.return_value.__enter__.return_value
                api.responses.create.return_value = SimpleNamespace(status=status, output_text=output,
                    incomplete_details=SimpleNamespace(reason=reason))
                with self.assertRaises(horizon_pipeline.HorizonPipelineError) as caught:
                    CombinedPipelineTests().exercise('MEDIUM', risks=True)
                error = caught.exception
                self.assertEqual(error.stage, 'HORIZON_SYNTHESIS')
                self.assertEqual(error.failure_type, 'RESPONSE_EXTRACTION')
                self.assertEqual(error.response_detail, expected)
                self.assertNotIn('SECRET', str(error) + repr(vars(error)))
                entry.assert_called_once()
                api.responses.create.assert_called_once()
                self.assertEqual(client.call_args.kwargs['max_retries'], 0)
                self.assertFalse(api.responses.create.call_args.kwargs['store'])
        self.assertIsNone(horizon_synthesis.HorizonSynthesisError('RESPONSE_EXTRACTION',
            response_detail='SECRET').response_detail)

    def test_clarified_horizon_cross_rule_contract(self):
        from copy import deepcopy
        from src.horizon_synthesis import _packet, _validate, HorizonSynthesisError
        helper = HorizonSynthesisTests(); helper.setUp(); self.addCleanup(helper.doCleanups)
        packet = _packet(helper.context)
        data = helper.output(posture='WAIT_FOR_CONFIRMATION')
        condition = packet['conditions']['T_CONFIRMATION:0']
        data['synthesis_summary']['technical_evidence_ids'] = condition['evidence_ids']
        data['supporting_technical_evidence_ids'] = []
        data['conflicting_technical_evidence_ids'] = condition['evidence_ids']
        data['synthesis_summary']['text'] = 'The evidence could strengthen.'
        self.assertEqual(json.loads(_validate(data, packet)), data)
        for change, code in [
            (lambda d: d['synthesis_summary'].__setitem__('classification', 'AI_INTERPRETATION'), 'CONDITION_REQUIRES_FORECAST'),
            (lambda d: d['synthesis_summary'].__setitem__('condition_ids', []), 'WAIT_CONDITION_REQUIRED'),
            (lambda d: d.__setitem__('acknowledged_limitations', list(reversed(packet['limitations']))), 'LIMITATIONS_MISMATCH'),
            (lambda d: d['synthesis_summary'].__setitem__('text', 'The evidence could improve 20%.'), 'NUMERIC_PROSE'),
            (lambda d: d['synthesis_summary'].__setitem__('text', 'No portfolio action is proposed.'), 'PROHIBITED_ACTION_LANGUAGE')]:
            invalid = deepcopy(data); change(invalid)
            with self.assertRaises(HorizonSynthesisError) as caught:
                _validate(invalid, packet)
            self.assertEqual(caught.exception.semantic_reason, 'HORIZON_SYNTHESIS_' + code)

    def test_prompt_instructions_for_nonobvious_rules(self):
        from src.technical_analyst import INSTRUCTIONS as technical
        from src.horizon_synthesis import INSTRUCTIONS as horizon
        for phrase in ('unique exact catalog IDs', 'nonempty and disjoint', 'All statement text must be nonblank',
                       'exactly all unavailable IDs', 'risk_notes may'):
            self.assertIn(phrase, technical)
        for phrase in ('unique exact IDs', 'ALL of its original evidence_refs', 'matching available Technical',
                       'synthesis_summary itself', 'quoted, negated', 'will, expect, forecast, predict, would or could'):
            self.assertIn(phrase, horizon)
