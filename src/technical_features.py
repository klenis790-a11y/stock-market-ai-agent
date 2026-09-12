"""Versioned arithmetic over validated V0.7A bars only; no IO or interpretation."""
from dataclasses import dataclass, replace
from math import isfinite
from statistics import mean
from src.market_data_models import HistoricalOHLCV, require_minimum_history

METHODOLOGY_VERSION = 'technical-features-v1'
PARAMETERS = (('SMA', (20, 50, 200)), ('RSI_WILDER', (14,)),
              ('MACD_SMA_SEEDED_EMA', (12, 26, 9)), ('ATR_WILDER', (14,)),
              ('MOMENTUM', (5, 20)), ('VOLUME_AVERAGE', (20,)))


@dataclass(frozen=True)
class FeatureValue:
    name: str
    value: float | str | None
    unit: str
    unavailable_reason: str | None = None

    def __post_init__(self):
        if (self.value is None) != (self.unavailable_reason is not None):
            raise ValueError('Unavailable features require an explicit reason.')
        if self.value is not None and not isinstance(self.value, str):
            if type(self.value) not in (int, float) or not isfinite(self.value):
                raise ValueError('Non-finite technical calculation.')


@dataclass(frozen=True)
class TechnicalFeatureSnapshot:
    source_dataset: HistoricalOHLCV
    features: tuple[FeatureValue, ...]
    methodology_version: str = METHODOLOGY_VERSION
    indicator_parameters: tuple = PARAMETERS

    def feature(self, name):
        return next(item for item in self.features if item.name == name)

    @property
    def symbol(self):
        return self.source_dataset.symbol

    @property
    def as_of(self):
        return self.source_dataset.requested_as_of

    @property
    def latest_session(self):
        return self.source_dataset.effective_last_session

    @property
    def latest_close(self):
        return self.source_dataset.bars[-1].close if self.source_dataset.bars else None


def _wilder(values, period):
    average = mean(values[:period])
    for value in values[period:]:
        average = average * ((period - 1) / period) + value / period
    return average


def _ema(values, period):
    average = mean(values[:period])
    result = [average]
    alpha = 2 / (period + 1)
    for value in values[period:]:
        average = alpha * value + (1 - alpha) * average
        result.append(average)
    return result


def build_technical_feature_snapshot(dataset):
    """SMA-seeded recursive indicators use the full supplied history, never reseed
    after gaps. Missing history is per-feature; unexpected calculation errors propagate.
    Caller must supply V0.7A-validated bars; no new calendar or provider queries occur.
    """
    if not isinstance(dataset, HistoricalOHLCV):
        raise ValueError('HistoricalOHLCV is required.')
    replace(dataset, bars=tuple(replace(bar) for bar in dataset.bars))
    bars = dataset.bars
    closes = [bar.close for bar in bars]
    latest = closes[-1] if closes else None
    result = []

    def history(n, recursive=False):
        if len(bars) < n:
            return 'UNAVAILABLE_DUE_TO_HISTORY'
        # Use the existing gap/sufficiency contract. No generic calculation exception catch.
        required = len(bars) if recursive else n
        try:
            require_minimum_history(dataset, required)
        except ValueError:
            return 'UNAVAILABLE_DUE_TO_MISSING_SESSIONS'
        return None

    def add(name, value, unit, reason=None):
        result.append(FeatureValue(name, value, unit, reason))

    smas = []
    for n in (20, 50, 200):
        reason = history(n)
        sma = mean(closes[-n:]) if reason is None else None
        smas.append(sma)
        add(f'sma_{n}', sma, 'price', reason)
        add(f'close_vs_sma_{n}_pct', (latest / sma - 1) * 100 if sma is not None else None,
            'percent', reason)
    if all(s is not None for s in smas):
        stack = ('BULLISH_STACK' if latest > smas[0] > smas[1] > smas[2] else
                 'BEARISH_STACK' if latest < smas[0] < smas[1] < smas[2] else 'MIXED')
        add('trend_structure', stack, 'ordering')
    else:
        add('trend_structure', None, 'ordering', history(200))

    reason = history(15, recursive=True)
    rsi = atr = None
    if reason is None:
        changes = [b - a for a, b in zip(closes, closes[1:])]
        gain = _wilder([max(c, 0) for c in changes], 14)
        loss = _wilder([max(-c, 0) for c in changes], 14)
        rsi = 50.0 if gain == loss == 0 else 100.0 if loss == 0 else 100 * (gain / (gain + loss))
        ranges = [max(bar.high - bar.low, abs(bar.high - previous.close),
                      abs(bar.low - previous.close)) for previous, bar in zip(bars, bars[1:])]
        atr = _wilder(ranges, 14)
    add('rsi_14', rsi, '0-100', reason)
    add('atr_14', atr, 'price', reason)
    add('atr_pct', atr / latest * 100 if atr is not None else None, 'percent', reason)

    reason = history(26, recursive=True)
    lines = []
    if reason is None:
        fast, slow = _ema(closes, 12), _ema(closes, 26)
        lines = [f - s for f, s in zip(fast[14:], slow)]
    add('macd_line', lines[-1] if lines else None, 'price', reason)
    signal_reason = history(34, recursive=True)
    signal = _ema(lines, 9)[-1] if signal_reason is None else None
    add('macd_signal', signal, 'price', signal_reason)
    add('macd_histogram', lines[-1] - signal if signal is not None else None, 'price', signal_reason)

    for n in (5, 20):
        reason = history(n + 1)
        add(f'momentum_{n}', latest / closes[-n-1] - 1 if reason is None else None,
            'decimal_return', reason)
    reason = history(20)
    average = mean([bar.volume for bar in bars[-20:]]) if reason is None else None
    add('average_volume_20', average, 'shares', reason)
    ratio_reason = reason or ('UNAVAILABLE_ZERO_DENOMINATOR' if average == 0 else None)
    add('volume_ratio_20', bars[-1].volume / average if ratio_reason is None else None,
        'ratio', ratio_reason)
    return TechnicalFeatureSnapshot(dataset, tuple(result))
