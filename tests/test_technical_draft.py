import copy
import json
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch
import test_v07 as fixtures
from src import technical_draft as draft
from src.technical_analyst import HORIZONS


class TechnicalDraftTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch('socket.socket.connect', side_effect=AssertionError('No network'))
        self.guard.start(); self.addCleanup(self.guard.stop)
        self.ai = patch('src.openai_client.request_text', side_effect=AssertionError('No model'))
        self.ai.start(); self.addCleanup(self.ai.stop)
        self.helper = fixtures.TechnicalAnalystTests()
        self.snapshot, self.catalog = self.helper.fixture(200)
        self.ids = {i.label:i.evidence_id for i in self.catalog.items}

    def statement(self, *parts):
        return {'parts': [dict(kind=k, value=v) for k,v in parts]}

    def output(self, signal='NEUTRAL'):
        statement = self.statement(('FEATURE', self.ids['sma_200']), ('TEXT', ' informs this interpretation.'))
        return dict(signal=signal, confidence=60, summary=copy.deepcopy(statement),
            thesis=copy.deepcopy(statement), evidence_roles=[dict(evidence_id=self.ids['momentum_5'], role='SUPPORTING')],
            confirmation_conditions=[copy.deepcopy(statement)],
            invalidation_conditions=[] if signal=='NEUTRAL' else [copy.deepcopy(statement)],
            risk_notes=[copy.deepcopy(statement)], missing_data_acknowledgement='')

    def validate(self, data, snapshot=None, catalog=None):
        return draft.validate_technical_draft(data, snapshot or self.snapshot, catalog or self.catalog, HORIZONS[0])

    def rejects(self, data, reason, **kwargs):
        with self.assertRaises(draft.TechnicalDraftError) as caught:
            self.validate(data, **kwargs)
        self.assertEqual(caught.exception.reason, reason)
        self.assertEqual(str(caught.exception), reason.value)

    def test_valid_parts_and_normalized_explicit_selections(self):
        a,b = self.ids['sma_200'],self.ids['sma_20']
        cases = [([('TEXT','Evidence informs this view.'),('CITATION',a)], (a,)),
                 ([('FEATURE',a),('TEXT',' informs this view.')], (a,)),
                 ([('FEATURE',a),('TEXT',' and '),('FEATURE',b)], (a,b)),
                 ([('FEATURE',a),('CITATION',b),('CITATION',a),('FEATURE',a)], (a,b))]
        for parts, expected in cases:
            data=self.output();data['summary']=self.statement(*parts)
            result=self.validate(data)
            self.assertEqual(result.summary.selected_evidence_ids,expected)
            self.assertEqual(len(result.summary.parts),len(parts))
            with self.assertRaises(FrozenInstanceError): result.signal='BULLISH'
        for item in self.catalog.items:
            if item.value is not None:
                data=self.output();data['summary']=self.statement(('FEATURE',item.evidence_id))
                self.validate(data)

    def test_roles_are_explicit_and_independent(self):
        data=self.output()
        data['evidence_roles'].append(dict(evidence_id=self.ids['sma_20'],role='CONFLICTING'))
        result=self.validate(data)
        self.assertNotIn(self.ids['sma_200'], [r.evidence_id for r in result.evidence_roles])
        self.assertNotIn(self.ids['momentum_5'], result.summary.selected_evidence_ids)
        for role in ('SUPPORTING','CONFLICTING'):
            changed=copy.deepcopy(data)
            changed['evidence_roles'].append(dict(evidence_id=self.ids['momentum_5'],role=role))
            self.rejects(changed,draft.DraftReason.ROLE_DUPLICATE)
        for roles in ([], [dict(evidence_id=self.ids['sma_20'],role='CONFLICTING')]):
            changed=self.output();changed['evidence_roles']=roles
            self.rejects(changed,draft.DraftReason.SUPPORTING)

    def test_selection_failures_and_missing_inventory(self):
        snapshot,catalog=self.helper.fixture(50)
        missing=draft.missing_evidence_ids(catalog)
        self.assertEqual(missing,tuple(i.evidence_id for i in catalog.items if i.value is None))
        for kind in ('FEATURE','CITATION'):
            for selected in ('FABRICATED',self.ids['sma_200']):
                data=self.output();data['summary']=self.statement((kind,selected))
                self.rejects(data,draft.DraftReason.SELECTION,snapshot=snapshot,catalog=catalog)
        data=self.output();data['evidence_roles'][0]['evidence_id']='FABRICATED'
        self.rejects(data,draft.DraftReason.SELECTION)
        data['evidence_roles'][0]['evidence_id']=self.ids['sma_200']
        self.rejects(data,draft.DraftReason.SELECTION,snapshot=snapshot,catalog=catalog)
        data=self.output()
        generic=self.statement(('TEXT','The interpretation is conditional.'),('CITATION',self.ids['momentum_5']))
        for key in ('summary','thesis'):data[key]=generic
        data['confirmation_conditions']=[generic];data['risk_notes']=[generic]
        self.rejects(data,draft.DraftReason.MISSING_NOTE,snapshot=snapshot,catalog=catalog)
        data['missing_data_acknowledgement']='sma_200 is unavailable.'
        self.validate(data,snapshot,catalog)
        self.assertNotIn('missing_evidence_ids',draft.SCHEMA['properties'])

    def test_sma_200_binding_and_unbound_text(self):
        selected=next(i for i in self.catalog.items if i.label=='sma_200')
        result=self.validate(self.output())
        self.assertEqual(result.summary.selected_evidence_ids,(selected.evidence_id,))
        self.assertNotIn('sma_200',json.dumps(self.output()))
        for parts in ([('TEXT','sma_200 informs this view.'),('CITATION',selected.evidence_id)],
                      [('TEXT','SMA_200'),('FEATURE',selected.evidence_id)],
                      [('TEXT','sma_'),('CITATION',selected.evidence_id),('TEXT','200')]):
            data=self.output();data['summary']=self.statement(*parts)
            self.rejects(data,draft.DraftReason.UNBOUND)
        data=self.output();data['summary']=self.statement(('TEXT','Uncited interpretation.'))
        self.rejects(data,draft.DraftReason.GROUNDING)
        data['summary']=self.statement(('CITATION',selected.evidence_id))
        self.rejects(data,draft.DraftReason.TEXT)

    def test_condition_signal_horizon_and_confidence_matrix(self):
        for signal in ('BULLISH','NEUTRAL','BEARISH'):
            for horizon in HORIZONS:
                draft.validate_technical_draft(self.output(signal),self.snapshot,self.catalog,horizon)
            data=self.output(signal);data['confirmation_conditions']=[]
            self.rejects(data,draft.DraftReason.CONDITIONS)
            if signal!='NEUTRAL':
                data=self.output(signal);data['invalidation_conditions']=[]
                self.rejects(data,draft.DraftReason.CONDITIONS)
        for confidence in (0,100):
            data=self.output();data['confidence']=confidence;self.validate(data)
        data=self.output();data['confidence']=91
        data['evidence_roles'].append(dict(evidence_id=self.ids['sma_20'],role='CONFLICTING'))
        self.rejects(data,draft.DraftReason.CONFIDENCE)

    def test_shape_bounds_and_metadata_exclusion(self):
        mutations=[lambda d:d['summary']['parts'][0].update(kind='UNKNOWN'),
                   lambda d:d['summary']['parts'][0].update(value=12),
                   lambda d:d['evidence_roles'][0].update(role='NEUTRAL'),
                   lambda d:d.update(confidence=True),
                   lambda d:d.update(native_horizon=HORIZONS[0]),
                   lambda d:d.update(missing_evidence_ids=[]),
                   lambda d:d['summary'].update(parts=[]),
                   lambda d:d['summary'].update(parts=[dict(kind='TEXT',value='x')]*(draft.MAX_PARTS+1))]
        for mutate in mutations:
            data=self.output();mutate(data);self.rejects(data,draft.DraftReason.SHAPE)
        def check(schema):
            if schema.get('type')=='object':
                self.assertFalse(schema['additionalProperties'])
                self.assertEqual(set(schema['required']),set(schema['properties']))
                for child in schema['properties'].values():check(child)
            if schema.get('type')=='array':
                self.assertIn('maxItems',schema);check(schema['items'])
        check(draft.SCHEMA)
        json.dumps(draft.SCHEMA,allow_nan=False)

    def test_normal_pipeline_uses_v2(self):
        from src import technical_pipeline as pipeline
        from src.technical_analyst import SCHEMA, ANALYST_VERSION
        from dataclasses import fields
        data=self.output()
        with patch.object(pipeline,'retrieve_historical_ohlcv',return_value=self.snapshot.historical_ohlcv), \
             patch('src.openai_client.request_text',return_value=json.dumps(data)) as request:
            result=pipeline.run_technical_research('TEST',HORIZONS[0],self.catalog.provenance.requested_as_of,market_verified=True)
        self.assertEqual(result.signal.analyst_methodology_version,'technical-analyst-v2')
        self.assertEqual(ANALYST_VERSION,'technical-analyst-v2')
        self.assertEqual(request.call_args.kwargs['text']['format']['schema'],draft.SCHEMA)
        self.assertIn('missing_evidence_ids',SCHEMA['properties'])
        self.assertNotIn('evidence_roles',SCHEMA['properties'])
        self.assertEqual([f.name for f in fields(result.signal.analysis)],list(SCHEMA['required']))
        request.assert_called_once()
