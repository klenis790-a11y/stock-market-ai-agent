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

    def test_unknown_without_thresholds_at_any_age(self):
        for at in (instant(), instant('2030-01-01T00:00:00+00:00')):
            context = build_integration_context('TEST', 'SHORT', at, technical=self.technical)
            self.assertEqual(context.technical.status, Admission.ADMITTED)
            self.assertEqual(context.technical_freshness, Freshness.UNKNOWN)
            self.assertIsNone(context.freshness_policy_version)
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
        self.assertIn('MISSING_DATA_SEVERITY_POLICY_UNAVAILABLE', context.blocking_missing_data)

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
