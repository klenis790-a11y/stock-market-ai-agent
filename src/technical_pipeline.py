"""Explicit Technical application pipeline, shared by backend and dashboard."""
from dataclasses import dataclass
from src.historical_market_data import retrieve_historical_ohlcv
from src.technical_features import build_technical_feature_snapshot
from src.technical_evidence import build_technical_research_snapshot, build_technical_evidence_catalog
from src.technical_analyst import analyze_technical_snapshot, HORIZONS, TechnicalValidationError, TechnicalGenerationError, VALIDATION_REASONS, FEATURE_FAMILIES
from src.market_data_models import normalize_symbol
from src.market_calendar import aware_utc
from src.observation_resolution import SUPPORTED_MARKET

class TechnicalResearchError(RuntimeError):
    def __init__(self, stage, exception_type, validation_reason=None, feature_family=None, generation_substage=None, response_detail=None):
        from src.technical_draft import DraftReason
        self.generation_substage = generation_substage if generation_substage in TechnicalGenerationError.STAGES else None
        self.response_detail = response_detail if response_detail in ("max_output_tokens", "content_filter", "not_completed", "empty_output_text") else None
        self.feature_family = feature_family if (validation_reason == "TECHNICAL_ANALYST_FEATURE_CITATION_MISSING" and feature_family in FEATURE_FAMILIES) else None
        self.validation_reason = validation_reason if validation_reason in (*VALIDATION_REASONS, *(r.value for r in DraftReason)) else None
        self.stage = stage
        self.exception_type = exception_type
        super().__init__(f'Technical research failed at {stage}.')


def step(stage, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except TechnicalGenerationError as error:
        raise TechnicalResearchError(stage, "TechnicalGenerationError", error.validation_reason, getattr(error, "feature_family", None), error.substage, error.response_detail) from None
    except TechnicalValidationError as error:
        raise TechnicalResearchError(stage, "ValueError", error.validation_reason, error.feature_family) from None
    except Exception as error:
        raise TechnicalResearchError(stage, type(error).__name__) from None


@dataclass(frozen=True)
class TechnicalRun:
    snapshot: object
    catalog: object
    signal: object


def run_technical_research(ticker, horizon, as_of, *, market_verified):
    ticker = step('INPUT', normalize_symbol, ticker)
    as_of = step('INPUT', aware_utc, as_of)
    if horizon not in HORIZONS or not market_verified:
        raise TechnicalResearchError('INPUT', 'ValueError')
    data = step('MARKET_DATA', retrieve_historical_ohlcv, ticker, as_of, market=SUPPORTED_MARKET)
    features = step('FEATURES', build_technical_feature_snapshot, data)
    snapshot = step('EVIDENCE', build_technical_research_snapshot, data, features)
    catalog = step('EVIDENCE', build_technical_evidence_catalog, snapshot)
    signal = step('TECHNICAL_ANALYST', analyze_technical_snapshot, snapshot, catalog, horizon)
    return TechnicalRun(snapshot, catalog, signal)
