"""Prospective same-run metadata. No retrieval, interpretation or persistence."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json

from src.evaluation_models import canonical_json, utc_timestamp
from src.market_calendar import aware_utc
from src.evidence import build_evidence_catalog

POLICY_VERSION = 'fundamental-provenance-v1'
ARTIFACT_VERSION = 'fundamental-research-artifact-v1'
CATALOG_VERSION = 'fundamental-evidence-path-catalog-v1'
# Private capability: shape and arbitrary caller strings alone cannot attest origin.
_PIPELINE_ORIGIN = object()


@dataclass(frozen=True)
class CurrentFundamentalArtifact:
    analysis_json: str
    evidence_json: str
    provenance_json: str
    _origin: object

    @property
    def analysis(self):
        return json.loads(self.analysis_json)

    @property
    def evidence(self):
        return json.loads(self.evidence_json)

    @property
    def provenance(self):
        return json.loads(self.provenance_json)

    def verified(self):
        p = self.provenance
        if self._origin != (_PIPELINE_ORIGIN, sha256((self.analysis_json + self.evidence_json + self.provenance_json).encode()).hexdigest()):
            raise ValueError('Untrusted artifact origin.')
        if (p['artifact_version'] != ARTIFACT_VERSION or p['policy_version'] != POLICY_VERSION or
                p['evidence_catalog_version'] != CATALOG_VERSION or p['methodology_version'] not in
                ('fundamental-multi-agent-path-v1', 'fundamental-single-agent-path-v1')):
            raise ValueError('Unsupported artifact.')
        digest = sha256((self.analysis_json + '\n' + self.evidence_json).encode()).hexdigest()
        if digest != p['packet_digest']:
            raise ValueError('Artifact binding differs.')
        times = [utc_timestamp(p[k]) for k in ('retrieval_started_at', 'data_cutoff_as_of', 'available_at')]
        if times != sorted(times) or p['research_as_of'] != p['data_cutoff_as_of']:
            raise ValueError('Invalid provenance times.')
        generated = self.evidence.get('generated_at')
        if generated is not None and utc_timestamp(generated) > times[1]:
            raise ValueError('Evidence snapshot postdates acquisition cutoff.')
        return p


def _capture(analysis, evidence, *, run_id, native_horizon, started, cutoff, completed,
             multi_agent, specialists, model, memory_used):
    """Only invoked by the successful current research orchestration path.

    Python capabilities prevent accidental external attestation, not hostile Python
    process access. The same trust boundary already applies to source timestamps.
    """
    stamp = lambda v: utc_timestamp(aware_utc(v).isoformat())
    packet = dict(evidence)
    packet['catalog'] = build_evidence_catalog(evidence)
    analysis_json, evidence_json = canonical_json(asdict(analysis)), canonical_json(packet)
    facts = evidence['retrieved_facts']
    coverage = {}
    for name, field in [('income_statements', 'fiscal_date_ending'),
                        ('balance_sheets', 'fiscal_date_ending'), ('cash_flows', 'fiscal_date_ending'),
                        ('earnings', 'reported_date'), ('news', 'time_published'),
                        ('earnings_call_transcript', None)]:
        rows = facts.get(name, [])
        coverage[name] = {'status': 'OBSERVED' if rows else 'UNAVAILABLE',
                          'observed_dates': [r.get(field) for r in rows] if field else [],
                          'exhaustive_event_coverage': 'UNKNOWN'}
    p = dict(artifact_version=ARTIFACT_VERSION, policy_version=POLICY_VERSION,
             methodology_version=('fundamental-multi-agent-path-v1' if multi_agent else 'fundamental-single-agent-path-v1'),
             evidence_catalog_version=CATALOG_VERSION, run_id=run_id, native_horizon=native_horizon,
             retrieval_started_at=stamp(started), data_cutoff_as_of=stamp(cutoff),
             research_as_of=stamp(cutoff), available_at=stamp(completed),
             provider=evidence.get('source'), model=model, specialists=specialists,
             portfolio_context_supplied=False, memory_context_supplied=memory_used,
             event_currentness='UNKNOWN', coverage=coverage,
             packet_digest=sha256((analysis_json + '\n' + evidence_json).encode()).hexdigest())
    provenance_json = canonical_json(p)
    seal = (_PIPELINE_ORIGIN, sha256((analysis_json + evidence_json + provenance_json).encode()).hexdigest())
    artifact = CurrentFundamentalArtifact(analysis_json, evidence_json, provenance_json, seal)
    artifact.verified()
    return artifact
