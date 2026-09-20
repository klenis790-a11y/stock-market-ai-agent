import copy
import json
import unittest
from dataclasses import asdict, fields, replace
from unittest.mock import patch
import test_technical_draft as fixtures
from src.technical_assembly import assemble_technical_v2_offline
from src import technical_draft as d
from src.technical_analyst import HORIZONS, TechnicalValidationError, _parse, _preflight


class TechnicalAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.helper=fixtures.TechnicalDraftTests()
        self.helper.setUp();self.addCleanup(self.helper.doCleanups)
        self.snapshot,self.catalog=self.helper.snapshot,self.helper.catalog
        self.ids=self.helper.ids
        guard=patch('sqlite3.connect',side_effect=AssertionError('No persistence'))
        guard.start();self.addCleanup(guard.stop)

    def assemble(self, data=None, snapshot=None, catalog=None, horizon=HORIZONS[0]):
        snapshot,catalog=snapshot or self.snapshot,catalog or self.catalog
        draft=d.validate_technical_draft(data or self.helper.output(),snapshot,catalog,horizon)
        return assemble_technical_v2_offline(draft,snapshot,catalog,horizon,model='offline-fixture')

    def test_render_order_sma_and_all_statement_locations(self):
        a,b=self.ids['sma_200'],self.ids['sma_20']
        statement=self.helper.statement(('TEXT','  '),('FEATURE',a),('TEXT',' and '),
            ('FEATURE',b),('CITATION',a),('TEXT',' then '),('FEATURE',a),('TEXT',' inform the view.\n'))
        expected='  sma_200 and sma_20 then sma_200 inform the view.\n'
        data=self.helper.output('BULLISH')
        data['summary']=statement;data['thesis']=statement
        for key in ('confirmation_conditions','invalidation_conditions','risk_notes'):
            data[key]=[statement,copy.deepcopy(statement)]
        out=self.assemble(data)
        for value in (out.analysis.summary,out.analysis.thesis,*out.analysis.confirmation_conditions,
                      *out.analysis.invalidation_conditions,*out.analysis.risk_notes):
            self.assertEqual(value.text,expected)
            self.assertEqual(value.evidence_ids,(a,b))
        items,available=_preflight(self.snapshot,self.catalog,HORIZONS[0])
        _parse(json.loads(json.dumps(asdict(out.analysis))),items,available)
        for parts,text,refs in [([('FEATURE',a)],'sma_200',(a,)),
                ([('TEXT','Interpretation.'),('CITATION',b)],'Interpretation.',(b,)),
                ([('FEATURE',a),('TEXT',' informs this view.'),('CITATION',b)],'sma_200 informs this view.',(a,b))]:
            data=self.helper.output();data['summary']=self.helper.statement(*parts)
            got=self.assemble(data).analysis.summary
            self.assertEqual((got.text,got.evidence_ids),(text,refs))

    def test_roles_signals_horizons_metadata_and_shape(self):
        for signal in ('BULLISH','BEARISH','NEUTRAL'):
            for horizon in HORIZONS:
                data=self.helper.output(signal)
                data['evidence_roles']=[dict(evidence_id=self.ids['sma_20'],role='CONFLICTING'),
                    dict(evidence_id=self.ids['momentum_5'],role='SUPPORTING'),
                    dict(evidence_id=self.ids['sma_50'],role='SUPPORTING')]
                out=self.assemble(data,horizon=horizon)
                self.assertEqual(out.analysis.supporting_evidence_ids,(self.ids['momentum_5'],self.ids['sma_50']))
                self.assertEqual(out.analysis.conflicting_evidence_ids,(self.ids['sma_20'],))
                self.assertEqual(out.analysis.signal,signal)
                self.assertEqual(out.analysis.confidence,data['confidence'])
                self.assertEqual(out.horizon,horizon)
                self.assertEqual(out.provenance,self.catalog.provenance)
                self.assertEqual(out.evidence_catalog_version,self.catalog.methodology_version)
                self.assertEqual(out.model,'offline-fixture')
                self.assertEqual(out.analyst_methodology_version,'technical-analyst-v2')
                self.assertEqual(len(out.analysis.invalidation_conditions),0 if signal=='NEUTRAL' else 1)
        from src.technical_analyst import SCHEMA
        self.assertEqual([f.name for f in fields(out.analysis)],list(SCHEMA['required']))

    def test_missing_inventory_and_exact_acknowledgement(self):
        snapshot,catalog=self.helper.helper.fixture(50)
        data=self.helper.output()
        generic=self.helper.statement(('TEXT','Interpretation.'),('CITATION',self.ids['momentum_5']))
        data.update(summary=generic,thesis=generic,confirmation_conditions=[generic],risk_notes=[generic],
                    missing_data_acknowledgement='  sma_200 is unavailable.\n')
        out=self.assemble(data,snapshot,catalog)
        self.assertEqual(out.analysis.missing_evidence_ids,d.missing_evidence_ids(catalog))
        self.assertEqual(out.analysis.missing_data_acknowledgement,data['missing_data_acknowledgement'])
        draft=d.validate_technical_draft(data,snapshot,catalog,HORIZONS[0])
        with self.assertRaises(d.TechnicalDraftError):
            assemble_technical_v2_offline(replace(draft,missing_data_acknowledgement=''),snapshot,catalog,HORIZONS[0],model='fixture')

    def test_assembly_revalidates_forged_drafts(self):
        draft=d.validate_technical_draft(self.helper.output('BULLISH'),self.snapshot,self.catalog,HORIZONS[0])
        badstatement=lambda kind,value:d.BoundStatementDraft((d.StatementPart(kind,value),))
        variants=[None,replace(draft,summary={}),replace(draft,summary=badstatement(d.StatementPartKind.FEATURE,'UNKNOWN')),
                  replace(draft,summary=badstatement(d.StatementPartKind.TEXT,'sma_200')),
                  replace(draft,evidence_roles=()),replace(draft,evidence_roles=draft.evidence_roles*2),
                  replace(draft,evidence_roles=(*draft.evidence_roles,d.EvidenceRoleAssignment(self.ids['momentum_5'],d.EvidenceRole.CONFLICTING))),
                  replace(draft,confirmation_conditions=()),replace(draft,invalidation_conditions=()),
                  replace(draft,signal='BEARISH',invalidation_conditions=()),replace(draft,confidence=101)]
        for bad in variants:
            with self.subTest(bad=type(bad)),self.assertRaises(d.TechnicalDraftError):
                assemble_technical_v2_offline(bad,self.snapshot,self.catalog,HORIZONS[0],model='fixture')
        snapshot,catalog=self.helper.helper.fixture(50)
        with self.assertRaises(d.TechnicalDraftError):
            assemble_technical_v2_offline(draft,snapshot,catalog,HORIZONS[0],model='fixture')
        item=self.catalog.items[0]
        forged=replace(self.catalog,items=(replace(item,value=item.value+1),*self.catalog.items[1:]))
        with self.assertRaises(TechnicalValidationError) as caught:
            assemble_technical_v2_offline(draft,self.snapshot,forged,HORIZONS[0],model='fixture')
        self.assertEqual(caught.exception.validation_reason,'TECHNICAL_ANALYST_CATALOG_MISMATCH')

    def test_public_prose_rejections_not_repaired(self):
        for text,reason in [('Buy now.','PROHIBITED_CLAIM'),('Evidence rose 12 percent.','NUMERIC_PROSE'),
                            ('The thesis is bearish.','SIGNAL_THESIS_CONFLICT')]:
            data=self.helper.output('BULLISH')
            data['summary']=self.helper.statement(('TEXT',text),('CITATION',self.ids['momentum_5']))
            draft=d.validate_technical_draft(data,self.snapshot,self.catalog,HORIZONS[0])
            with self.assertRaises(TechnicalValidationError) as caught:
                assemble_technical_v2_offline(draft,self.snapshot,self.catalog,HORIZONS[0],model='fixture')
            self.assertEqual(caught.exception.validation_reason,'TECHNICAL_ANALYST_'+reason)
            self.assertEqual(draft.summary.parts[0].value,text)
        # A FEATURE/Text boundary must not manufacture another grounded canonical label.
        data=self.helper.output()
        data['summary']=self.helper.statement(('FEATURE',self.ids['sma_20']),('TEXT','0 informs the view.'))
        with self.assertRaises(TechnicalValidationError) as caught:self.assemble(data)
        self.assertEqual(caught.exception.validation_reason,'TECHNICAL_ANALYST_FEATURE_CITATION_MISSING')

    def test_v2_active_and_consumers_accept_assembled_artifact(self):
        self.helper.test_normal_pipeline_uses_v2()
        from src.generation_contracts import ACTIVE_TECHNICAL_VERSION,ASSEMBLY_CONTRACT_BY_GENERATION
        self.assertEqual(ACTIVE_TECHNICAL_VERSION,'technical-analyst-v2')
        out=self.assemble()
        self.assertEqual(ASSEMBLY_CONTRACT_BY_GENERATION[out.analyst_methodology_version],'evidence-first-assembly-v1')
        from src.technical_signal_store import create_technical_signal_record
        record=create_technical_signal_record(out,self.catalog,created_at='2025-03-11T13:00:00Z')
        from src.technical_evaluation import _validate_source
        self.assertEqual(_validate_source(record),record.signal)
        from src.horizon_integration import admit_technical
        from datetime import datetime, timezone
        admission=admit_technical(record,record.symbol,datetime(2025,3,12,15,tzinfo=timezone.utc))
        self.assertEqual(admission.status,'ADMITTED')
