"""Explicit transient combined research; policies and engines remain authoritative."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from src import horizon_integration as policy
from src.technical_pipeline import run_technical_research, TechnicalResearchError
from src.research_pipeline import run_stock_research
from src.technical_signal_store import create_technical_signal_record
from src.horizon_synthesis import synthesize_horizon, IntegratedResearchView, HorizonSynthesisError
from src.market_calendar import aware_utc
from src.market_data_models import normalize_symbol


class HorizonPipelineError(RuntimeError):
    def __init__(self, stage, reasons=(), *, substage=None, error_type=None, failure_type=None, validation_reason=None, semantic_reason=None, evidence_namespace=None, feature_family=None, response_detail=None, generation_substage=None, draft_reason=None):
        self.generation_substage = generation_substage
        self.draft_reason = draft_reason
        self.response_detail = response_detail
        self.feature_family = feature_family
        self.evidence_namespace = evidence_namespace
        self.semantic_reason = semantic_reason
        self.validation_reason = validation_reason
        self.substage = substage
        self.error_type = error_type
        self.failure_type = failure_type
        self.stage = stage
        self.reasons = tuple(reasons)
        super().__init__(f'Combined research failed at {stage}; no automatic retry.')


@dataclass(frozen=True)
class CombinedResearchResult:
    view: IntegratedResearchView
    technical_horizon_selection_version: str
    sequencing_version: str


def run_horizon_research(ticker, decision_horizon, *, fundamental_horizon,
                         technical_as_of, market_verified):
    """One Technical-first attempt; no saves, refreshes or inferred native scopes.

    Fundamental native scope is explicit because selection policy only selects the
    Technical scope. The returned view retains immutable source packets/sidecar.
    """
    stage = 'INPUT'
    try:
        ticker = normalize_symbol(ticker)
        horizon = policy.DecisionHorizon(decision_horizon)
        native = policy.select_technical_horizon(horizon)
        at = aware_utc(technical_as_of)
        if fundamental_horizon not in ('MEDIUM', 'LONG') or market_verified is not True:
            raise ValueError('Explicit Fundamental scope and confirmed market required.')
        if (policy.COMBINED_RESEARCH_SEQUENCING_VERSION != 'combined-research-sequencing-v1'
                or policy.COMBINED_RESEARCH_SEQUENCE != policy.ResearchSequence.TECHNICAL_THEN_FUNDAMENTAL
                or policy.TECHNICAL_HORIZON_SELECTION_VERSION != 'technical-horizon-selection-v1'):
            raise ValueError('Unsupported orchestration policy.')
        run_id = uuid4().hex
        stage = 'TECHNICAL_RESEARCH'
        technical = run_technical_research(ticker, native, at, market_verified=market_verified)
        # Existing immutable availability envelope, constructed in memory only.
        record = create_technical_signal_record(technical.signal, technical.catalog,
                                               created_at=datetime.now(timezone.utc))
        stage = 'FUNDAMENTAL_RESEARCH'
        captured = []
        run_stock_research(ticker, investment_horizon=fundamental_horizon,
                           persist_decision=False, integration_run_id=run_id,
                           on_fundamental_artifact=captured.append)
        stage = 'INTEGRATION'
        if len(captured) != 1:
            raise ValueError('Missing unique prospective artifact.')
        artifact = captured[0]
        provenance = artifact.verified()
        integration_time = datetime.fromisoformat(provenance['available_at'].replace('Z', '+00:00'))
        context = policy.build_integration_context(ticker, horizon, integration_time,
                    fundamental=artifact, technical=record, integration_run_id=run_id)
        stage = 'READINESS'
        validated = policy.require_synthesis_ready(context)
        stage = 'HORIZON_SYNTHESIS'
        view = synthesize_horizon(validated)
        return CombinedResearchResult(view, policy.TECHNICAL_HORIZON_SELECTION_VERSION,
                                      policy.COMBINED_RESEARCH_SEQUENCING_VERSION)
    except TechnicalResearchError as error:
        raise HorizonPipelineError(stage, substage=error.stage, error_type=error.exception_type,
                                   failure_type='TechnicalResearchError', validation_reason=error.validation_reason, feature_family=error.feature_family, generation_substage=error.generation_substage, response_detail=error.response_detail) from None
    except policy.SynthesisReadinessError as error:
        raise HorizonPipelineError(stage, error.reasons, substage='READINESS_VALIDATION', error_type='SynthesisReadinessError') from None
    except HorizonSynthesisError as error:
        raise HorizonPipelineError(stage, substage=error.substage, error_type=error.error_type or 'HorizonSynthesisError', failure_type=error.synthesis_failure_type, semantic_reason=error.semantic_reason, evidence_namespace=error.evidence_namespace, response_detail=error.response_detail, draft_reason=error.draft_reason) from None
    except Exception:
        raise HorizonPipelineError(stage) from None
