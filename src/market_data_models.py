"""Immutable daily market facts and dataset provenance; no indicators or provider JSON."""
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from src.market_calendar import aware_utc

METHODOLOGY_VERSION = 'daily-ohlcv-normalization-v1'


def normalize_symbol(symbol):
    """Same nonempty/strip/uppercase convention as the production research pipeline."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError('A non-empty symbol is required.')
    return symbol.strip().upper()


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    session_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __post_init__(self):
        object.__setattr__(self, 'symbol', normalize_symbol(self.symbol))
        if type(self.session_date) is not date:
            raise ValueError('Session must be a date, not a timestamp.')
        for value in (self.open, self.high, self.low, self.close):
            if type(value) not in (float, int) or not isfinite(value) or value <= 0:
                raise ValueError('OHLC prices must be finite and positive.')
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError('Volume must be a nonnegative integer.')
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close, self.high):
            raise ValueError('Invalid OHLC relationships.')


@dataclass(frozen=True)
class HistoricalOHLCV:
    symbol: str
    bars: tuple[MarketBar, ...]
    requested_as_of: datetime
    retrieved_at: datetime
    calendar_version: str
    expected_last_session: date | None
    missing_sessions: tuple[date, ...]
    timeframe: str = '1d'
    provider: str = 'Alpha Vantage'
    provider_function: str = 'TIME_SERIES_DAILY'
    adjustment_mode: str = 'RAW'
    exchange_calendar: str = 'XNYS'
    exchange_timezone: str = 'America/New_York'
    methodology_version: str = METHODOLOGY_VERSION
    availability_basis: str = 'calendar-completed; historical provider publication/vintage unverified'

    def __post_init__(self):
        object.__setattr__(self, 'symbol', normalize_symbol(self.symbol))
        object.__setattr__(self, 'requested_as_of', aware_utc(self.requested_as_of))
        object.__setattr__(self, 'retrieved_at', aware_utc(self.retrieved_at))
        object.__setattr__(self, 'bars', tuple(self.bars))
        object.__setattr__(self, 'missing_sessions', tuple(self.missing_sessions))
        if self.timeframe != '1d' or self.adjustment_mode != 'RAW':
            raise ValueError('Only raw daily datasets are supported.')
        if any(not isinstance(b, MarketBar) or b.symbol != self.symbol for b in self.bars):
            raise ValueError('Bar identity differs from dataset.')
        dates = [b.session_date for b in self.bars]
        if dates != sorted(set(dates)):
            raise ValueError('Bars must be unique and chronological.')

    @property
    def data_window_start(self):
        return self.bars[0].session_date if self.bars else None

    @property
    def effective_last_session(self):
        return self.bars[-1].session_date if self.bars else None

    @property
    def data_window_end(self):
        return self.effective_last_session


def require_minimum_history(dataset: HistoricalOHLCV, bars_required: int) -> HistoricalOHLCV:
    """Require completed observations without gaps in the requested trailing window."""
    if type(bars_required) is not int or bars_required <= 0:
        raise ValueError('Required history must be a positive integer.')
    if len(dataset.bars) < bars_required:
        raise ValueError(f'Insufficient history: require {bars_required}, available {len(dataset.bars)}.')
    start = dataset.bars[-bars_required].session_date
    if any(day >= start for day in dataset.missing_sessions):
        raise ValueError('Insufficient history: required trailing window has missing sessions.')
    return dataset
