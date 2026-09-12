"""Bounded technical evidence packaging; no calculation, retrieval, prompts or signals."""
from dataclasses import dataclass, asdict, replace
from datetime import date, datetime
from math import isfinite
from src.market_data_models import HistoricalOHLCV, METHODOLOGY_VERSION as DATA_VERSION
from src.technical_features import TechnicalFeatureSnapshot, PARAMETERS, METHODOLOGY_VERSION as FEATURE_VERSION

CATALOG_VERSION = 'technical-evidence-v1'
# Fixed slots retain their IDs even when values are unavailable or feature tuple order changes.
FEATURES = (
    ('TREND', 'sma_20', 'price'), ('TREND', 'sma_50', 'price'), ('TREND', 'sma_200', 'price'),
    ('TREND', 'close_vs_sma_20_pct', 'percent'), ('TREND', 'close_vs_sma_50_pct', 'percent'),
    ('TREND', 'close_vs_sma_200_pct', 'percent'), ('TREND', 'trend_structure', 'ordering'),
    ('MOMENTUM', 'rsi_14', '0-100'), ('MOMENTUM', 'macd_line', 'price'),
    ('MOMENTUM', 'macd_signal', 'price'), ('MOMENTUM', 'macd_histogram', 'price'),
    ('MOMENTUM', 'momentum_5', 'decimal_return'), ('MOMENTUM', 'momentum_20', 'decimal_return'),
    ('VOLATILITY', 'atr_14', 'price'), ('VOLATILITY', 'atr_pct', 'percent'),
    ('VOLUME', 'average_volume_20', 'shares'), ('VOLUME', 'volume_ratio_20', 'ratio'))


@dataclass(frozen=True)
class TechnicalResearchSnapshot:
    technical_features: TechnicalFeatureSnapshot

    @property
    def historical_ohlcv(self):
        return self.technical_features.source_dataset

    def __post_init__(self):
        features = self.technical_features
        if not isinstance(features, TechnicalFeatureSnapshot):
            raise ValueError('TechnicalFeatureSnapshot required.')
        data = features.source_dataset
        if not isinstance(data, HistoricalOHLCV):
            raise ValueError('HistoricalOHLCV required.')
        replace(data, bars=tuple(replace(bar) for bar in data.bars))
        if (data.methodology_version != DATA_VERSION or features.methodology_version != FEATURE_VERSION
                or features.indicator_parameters != PARAMETERS or data.adjustment_mode != 'RAW'):
            raise ValueError('Unsupported source methodology or parameters.')
        if not isinstance(features.features, tuple):
            raise ValueError('Immutable feature collection required.')
        expected = {name: unit for _, name, unit in FEATURES}
        if len(features.features) != len(expected) or {f.name for f in features.features} != set(expected):
            raise ValueError('Missing, duplicate or unexpected feature names.')
        for feature in features.features:
            replace(feature)  # Validate availability and finite values, without recalculation.
            if feature.unit != expected[feature.name]:
                raise ValueError('Feature unit differs from declared methodology.')
            if feature.value is not None:
                if feature.name == 'trend_structure':
                    if feature.value not in ('BULLISH_STACK', 'BEARISH_STACK', 'MIXED'):
                        raise ValueError('Unknown deterministic ordering.')
                elif type(feature.value) not in (int, float):
                    raise ValueError('Numeric feature required.')


def build_technical_research_snapshot(historical_ohlcv, technical_features):
    snapshot = TechnicalResearchSnapshot(technical_features)
    # Full equality also detects changed bar values, retrieval vintage and gap metadata.
    if historical_ohlcv != snapshot.historical_ohlcv:
        raise ValueError('Market data and features must refer to the exact same source dataset.')
    return snapshot


@dataclass(frozen=True)
class TechnicalEvidenceItem:
    evidence_id: str
    category: str
    label: str
    value: float | int | str | None
    unit: str
    classification: str
    source_path: str
    unavailable_reason: str | None = None

    def __post_init__(self):
        if self.category not in ('PRICE', 'TREND', 'MOMENTUM', 'VOLATILITY', 'VOLUME', 'DATA_QUALITY'):
            raise ValueError('Unknown evidence category.')
        if self.classification not in ('RETRIEVED_FACT', 'CALCULATED_METRIC'):
            raise ValueError('Unsupported evidence classification.')
        if (self.value is None) != (self.unavailable_reason is not None):
            raise ValueError('Missing evidence requires its reason.')
        if self.value is not None and not isinstance(self.value, str):
            if type(self.value) not in (int, float) or not isfinite(self.value):
                raise ValueError('Evidence must be finite.')


@dataclass(frozen=True)
class TechnicalProvenance:
    symbol: str
    requested_as_of: datetime
    latest_completed_session: date | None
    first_included_session: date | None
    expected_last_session: date | None
    retrieved_at: datetime
    provider: str
    provider_function: str
    adjustment_mode: str
    timeframe: str
    calendar: str
    calendar_version: str
    exchange_timezone: str
    market_data_methodology: str
    feature_methodology: str
    indicator_parameters: tuple
    availability_basis: str


@dataclass(frozen=True)
class TechnicalEvidenceCatalog:
    provenance: TechnicalProvenance
    items: tuple[TechnicalEvidenceItem, ...]
    methodology_version: str = CATALOG_VERSION

    def resolve(self, evidence_id):
        for item in self.items:
            if item.evidence_id == evidence_id:
                return item
        raise ValueError('Unknown technical evidence ID for this catalog.')

    def to_packet(self):
        """JSON-ready bounded values only: never serialize the full source history."""
        packet = asdict(self)
        for key, value in packet['provenance'].items():
            if isinstance(value, (date, datetime)):
                packet['provenance'][key] = value.isoformat()
        return packet


def build_technical_evidence_catalog(snapshot):
    if not isinstance(snapshot, TechnicalResearchSnapshot):
        raise ValueError('TechnicalResearchSnapshot required.')
    replace(snapshot)
    data, features = snapshot.historical_ohlcv, snapshot.technical_features
    latest = data.bars[-1] if data.bars else None
    items = []
    def add(category, name, value, unit, classification, path, reason=None):
        items.append(TechnicalEvidenceItem(f'T{len(items)+1:03d}', category, name, value,
                                           unit, classification, path, reason))
    for name in ('close', 'high', 'low'):
        add('PRICE', 'latest_' + name, getattr(latest, name) if latest else None, 'price',
            'RETRIEVED_FACT', 'historical_ohlcv.bars[-1].' + name,
            None if latest else 'NO_COMPLETED_BARS')
    for category, name, unit in FEATURES:
        if name == 'average_volume_20':
            add('VOLUME', 'latest_volume', latest.volume if latest else None, 'shares',
                'RETRIEVED_FACT', 'historical_ohlcv.bars[-1].volume',
                None if latest else 'NO_COMPLETED_BARS')
        feature = features.feature(name)
        add(category, name, feature.value, feature.unit, 'CALCULATED_METRIC',
            'technical_features.' + name, feature.unavailable_reason)
    add('DATA_QUALITY', 'completed_bar_count', len(data.bars), 'observations',
        'CALCULATED_METRIC', 'historical_ohlcv.bars.length')
    add('DATA_QUALITY', 'missing_session_count', len(data.missing_sessions), 'sessions',
        'CALCULATED_METRIC', 'historical_ohlcv.missing_sessions.length')
    provenance = TechnicalProvenance(data.symbol, data.requested_as_of, data.effective_last_session,
        data.data_window_start, data.expected_last_session, data.retrieved_at, data.provider,
        data.provider_function, data.adjustment_mode, data.timeframe, data.exchange_calendar,
        data.calendar_version, data.exchange_timezone, data.methodology_version,
        features.methodology_version, features.indicator_parameters, data.availability_basis)
    return TechnicalEvidenceCatalog(provenance, tuple(items))
