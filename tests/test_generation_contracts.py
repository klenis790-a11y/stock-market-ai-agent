"""Version-only characterization: reserved labels are not evidence-first outputs."""
import json
import tempfile
import unittest
from dataclasses import fields, replace
from unittest.mock import patch
import test_v07 as v07
import test_v08 as v08
from src import generation_contracts as versions
from src.horizon_integration import admit_technical, Admission
from src.technical_evaluation import _validate_source
from src.technical_signal_store import TechnicalSignalStore


class GenerationContractTests(unittest.TestCase):
    def setUp(self):
        guard = patch('socket.socket.connect', side_effect=AssertionError('No live calls'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_reserved_mapping_and_current_generators(self):
        from src.technical_analyst import ANALYST_VERSION
        from src.horizon_synthesis import VERSION
        self.assertEqual(ANALYST_VERSION, 'technical-analyst-v2')
        self.assertEqual(VERSION, 'horizon-synthesis-v2')
        self.assertEqual(dict(versions.ASSEMBLY_CONTRACT_BY_GENERATION), {
            'technical-analyst-v2': 'evidence-first-assembly-v1',
            'horizon-synthesis-v2': 'evidence-first-assembly-v1'})
        with self.assertRaises(TypeError):
            versions.ASSEMBLY_CONTRACT_BY_GENERATION['unknown'] = 'anything'
        record, signal, _ = v07.TechnicalSignalPersistenceTests().fixture()
        self.assertEqual(signal.analyst_methodology_version, versions.TECHNICAL_V1)
        self.assertEqual(record.signal['analyst_methodology_version'], versions.TECHNICAL_V1)
        helper = v08.HorizonSynthesisTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        view = helper.invoke(helper.output())
        self.assertEqual(view.methodology_version, versions.HORIZON_V1)
        # Representation only: this is NOT a generated or semantically certified v2 view.
        reserved = replace(view, methodology_version=versions.HORIZON_V2)
        self.assertEqual(fields(reserved), fields(view))
        self.assertEqual(reserved.analysis_json, view.analysis_json)
        self.assertEqual(view.methodology_version, versions.HORIZON_V1)

    def test_strict_consumers_reject_unknown_versions(self):
        record = v07.TechnicalEvaluationTests().record()
        self.assertEqual(_validate_source(record), record.signal)
        self.assertEqual(admit_technical(record, record.symbol, v08.instant()).status, Admission.ADMITTED)
        original = record.signal_json
        for version in ('technical-analyst-v3', 'technical-analyst-v999',
                        'technical-analyst-v1-extra', '', ' ', None, 2, []):
            with self.subTest(version=version):
                data = record.signal
                data['analyst_methodology_version'] = version
                if not isinstance(version, str) or not version.strip():
                    with self.assertRaises(ValueError):
                        replace(record, signal_json=json.dumps(data))
                    continue
                candidate = replace(record, signal_json=json.dumps(data))
                with self.assertRaises(ValueError):
                    _validate_source(candidate)
                admission = admit_technical(candidate, candidate.symbol, v08.instant())
                self.assertEqual(admission.status, Admission.REJECTED)
                self.assertIn('UNSUPPORTED_METHODOLOGY', admission.reasons)
        self.assertEqual(record.signal_json, original)

    def test_storage_preserves_opaque_version_labels(self):
        record = v07.TechnicalEvaluationTests().record()
        with tempfile.TemporaryDirectory() as directory:
            store = TechnicalSignalStore(directory + '/versions.db')
            store.initialize()
            for number, version in enumerate((versions.TECHNICAL_V1, versions.TECHNICAL_V2, 'historical-custom-v0')):
                # Storage envelope test, not proof of v2 generation compatibility.
                data = record.signal
                data['analyst_methodology_version'] = version
                candidate = replace(record, record_id=str(number), signal_json=json.dumps(data))
                store.save_technical_signal(candidate)
                loaded = store.get_technical_signal(candidate.record_id)
                self.assertEqual(loaded, candidate)
                self.assertEqual(loaded.signal['analyst_methodology_version'], version)
        self.assertEqual(record.signal['analyst_methodology_version'], versions.TECHNICAL_V1)
