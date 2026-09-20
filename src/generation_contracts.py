"""Exact generation-contract identities; active generators use explicit v2 wiring.

These identify output/assembly contracts, not new investment methodologies.
Consumer acceptance remains explicit at each boundary.
"""
from types import MappingProxyType

EVIDENCE_FIRST_ASSEMBLY_VERSION = 'evidence-first-assembly-v1'
TECHNICAL_V1 = 'technical-analyst-v1'
TECHNICAL_V2 = 'technical-analyst-v2'
HORIZON_V1 = 'horizon-synthesis-v1'
HORIZON_V2 = 'horizon-synthesis-v2'

ACTIVE_TECHNICAL_VERSION = TECHNICAL_V2
ACTIVE_HORIZON_VERSION = HORIZON_V2

# Architecture contract mapping, NOT an admission/evaluation allowlist.
ASSEMBLY_CONTRACT_BY_GENERATION = MappingProxyType({
    TECHNICAL_V2: EVIDENCE_FIRST_ASSEMBLY_VERSION,
    HORIZON_V2: EVIDENCE_FIRST_ASSEMBLY_VERSION,
})

# Explicit public-semantics compatibility, proven with assembled v2 artifacts.
# Independent of active generation and the architecture mapping above.
SUPPORTED_TECHNICAL_ARTIFACT_VERSIONS = (TECHNICAL_V1, TECHNICAL_V2)
