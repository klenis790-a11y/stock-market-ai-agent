"""Immutable evaluation metadata only: no price retrieval, calendar resolution or returns."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be non-empty.')
    return value.strip()


def utc_timestamp(value):
    """Accept explicit offsets and legacy compact UTC; never infer a naive timezone."""
    value = text(value, 'timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        parsed = datetime.strptime(value, '%Y%m%dT%H%M%S.%fZ').replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Timestamp requires an explicit timezone.')
    return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class EvaluationHorizon:
    length: int
    unit: str = 'calendar_days'

    def __post_init__(self):
        if type(self.length) is not int or self.length <= 0:
            raise ValueError('Horizon length must be a positive integer.')
        if self.unit not in ('calendar_days', 'trading_sessions'):
            raise ValueError('Unknown horizon unit.')


# Activation policy is separate from the extensible horizon contract.
ACTIVE_HORIZONS = (EvaluationHorizon(90), EvaluationHorizon(365))


@dataclass(frozen=True)
class EvaluationMethodology:
    version: str = 'fundamental-price-v1'
    price_policy_version: str = 'next-full-session-close-v1'
    benchmark_policy_version: str = 'voo-aligned-price-v1'
    benchmark_symbol: str = 'VOO'
    currency: str = 'USD'
    adjustment_policy: str = 'split-consistent-excluding-cash-dividends'
    calendar_id: str = 'unresolved'
    calendar_version: str = 'unresolved'
    baseline_rule: str = 'first regular session opening strictly after availability and enrollment'
    endpoint_rule: str = 'first regular session close on or after baseline date plus horizon'
    missing_rule: str = 'unavailable; no forward-fill or substituted session'

    def __post_init__(self):
        for name, value in asdict(self).items():
            text(value, name)
        object.__setattr__(self, 'benchmark_symbol', self.benchmark_symbol.strip().upper())

    @property
    def snapshot(self):
        return canonical_json(asdict(self))

    @property
    def digest(self):
        return sha256(self.snapshot.encode()).hexdigest()


@dataclass(frozen=True)
class EvaluationEnrollment:
    enrollment_id: str
    decision_id: str
    ticker: str
    enrolled_at: str
    horizon: EvaluationHorizon
    methodology: EvaluationMethodology
    decision_available_at: str | None = None
    time_provenance: str = 'legacy_time_unverified'

    def __post_init__(self):
        for name in ('enrollment_id', 'decision_id', 'ticker', 'time_provenance'):
            text(getattr(self, name), name)
        if not isinstance(self.horizon, EvaluationHorizon) or not isinstance(self.methodology, EvaluationMethodology):
            raise ValueError('Typed horizon and methodology are required.')
        object.__setattr__(self, 'ticker', self.ticker.strip().upper())
        object.__setattr__(self, 'enrolled_at', utc_timestamp(self.enrolled_at))
        if self.decision_available_at is not None:
            object.__setattr__(self, 'decision_available_at', utc_timestamp(self.decision_available_at))
            if self.decision_available_at > self.enrolled_at:
                raise ValueError('Availability cannot follow enrollment.')
        if self.time_provenance not in ('legacy_time_unverified', 'captured_analysis_completion'):
            raise ValueError('Unknown decision-time provenance.')
        if self.time_provenance == 'captured_analysis_completion' and self.decision_available_at is None:
            raise ValueError('Captured completion requires an availability timestamp.')
        # Enrollment is not a claim of prospective/calendar eligibility.


@dataclass(frozen=True)
class EvaluationPrice:
    symbol: str
    price: float
    observed_at: str
    retrieved_at: str
    source: str
    price_type: str
    adjustment_policy: str
    currency: str

    def __post_init__(self):
        for name in ('symbol', 'source', 'price_type', 'adjustment_policy', 'currency'):
            text(getattr(self, name), name)
        object.__setattr__(self, 'symbol', self.symbol.strip().upper())
        if type(self.price) not in (int, float) or not isfinite(self.price) or self.price < 0:
            raise ValueError('Price must be finite and nonnegative.')
        for name in ('observed_at', 'retrieved_at'):
            object.__setattr__(self, name, utc_timestamp(getattr(self, name)))
        if self.observed_at > self.retrieved_at:
            raise ValueError('Observation cannot follow retrieval.')


@dataclass(frozen=True)
class EvaluationObservation:
    observation_id: str
    enrollment_id: str
    point: str
    effective_at: str
    recorded_at: str
    stock: EvaluationPrice | None = None
    benchmark: EvaluationPrice | None = None
    missing_reason: str | None = None
    supersedes_id: str | None = None
    revision_reason: str | None = None

    def __post_init__(self):
        for name in ('observation_id', 'enrollment_id'):
            text(getattr(self, name), name)
        if self.point not in ('reference', 'endpoint'):
            raise ValueError('Observation point must be reference or endpoint.')
        for name in ('effective_at', 'recorded_at'):
            object.__setattr__(self, name, utc_timestamp(getattr(self, name)))
        if self.effective_at > self.recorded_at:
            raise ValueError('Future observation points cannot be recorded.')
        for price in (self.stock, self.benchmark):
            if price is not None:
                if not isinstance(price, EvaluationPrice):
                    raise ValueError('Typed price provenance is required.')
                if price.observed_at != self.effective_at or price.retrieved_at > self.recorded_at:
                    raise ValueError('Price observation timestamps do not match the effective point.')
        if self.stock is None or self.benchmark is None:
            text(self.missing_reason, 'missing_reason')
        if self.supersedes_id is not None:
            text(self.supersedes_id, 'supersedes_id')
            text(self.revision_reason, 'revision_reason')
        elif self.revision_reason is not None:
            raise ValueError('Revision reason requires a predecessor.')
