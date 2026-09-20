"""ATS-3 atomic same-type swing comparisons; no projection or interpretation.

Consumes an ATS-1 eligible pivot snapshot and builds ATS-2 confirmation-session
contexts once. Released float observations are converted through their canonical
string representation for unrounded Decimal comparison arithmetic; ATR itself is
never recalculated here.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from enum import Enum
from hashlib import sha256
import json

from src.market_calendar import USMarketCalendar, aware_utc
from src.structural_pivots import ConfirmedPivot, PivotSnapshot, PivotType, METHODOLOGY_VERSION
from src.historical_feature_context import HistoricalFeatureContext, build_historical_feature_index

EQUALITY_MULTIPLIER = Decimal('0.25')


class SwingClassification(str, Enum):
    HH = 'HH'
    EH = 'EH'
    LH = 'LH'
    HL = 'HL'
    EL = 'EL'
    LL = 'LL'


@dataclass(frozen=True)
class SwingComparison:
    previous: ConfirmedPivot
    later: ConfirmedPivot
    atr_context: HistoricalFeatureContext
    difference: Decimal
    tolerance: Decimal | None
    classification: SwingClassification | None
    unavailable_reason: str | None
    logical_id: str
    state_id: str
    available_at: datetime
    computed_at: datetime
    limitations: tuple[str, ...]
    methodology_version: str = METHODOLOGY_VERSION
    equality_multiplier: Decimal = EQUALITY_MULTIPLIER


@dataclass(frozen=True)
class SwingStructureSnapshot:
    pivot_snapshot: PivotSnapshot
    comparisons: tuple[SwingComparison, ...]
    computed_at: datetime
    methodology_version: str = METHODOLOGY_VERSION


def _comparison_values(previous, later, atr, side):
    """Exact decimal operations on the supplied canonical numeric observations."""
    numbers = [Decimal(str(previous)), Decimal(str(later))]
    if atr is not None:
        numbers.append(Decimal(str(atr)))
    if not all(n.is_finite() for n in numbers):
        raise ValueError('Finite comparison dependencies required.')
    with localcontext() as context:
        # Derive sufficient precision from operands, independent of ambient Decimal
        # settings. This is arithmetic capacity, not a methodological threshold.
        context.prec = sum(len(n.as_tuple().digits) + abs(n.as_tuple().exponent)
                           for n in numbers) + 4
        difference = numbers[1] - numbers[0]
        if atr is None or numbers[2] <= 0:
            return difference, None, None
        tolerance = EQUALITY_MULTIPLIER * numbers[2]
        if abs(difference) <= tolerance:
            label = 'EH' if side == PivotType.HIGH else 'EL'
        elif difference > tolerance:
            label = 'HH' if side == PivotType.HIGH else 'HL'
        else:
            label = 'LH' if side == PivotType.HIGH else 'LL'
        return difference, tolerance, SwingClassification(label)


def _canonical_numeric_identity(value):
    """Exact, context-independent decimal text for hashing only."""
    if not value.is_finite():
        raise ValueError('Finite identity value required.')
    if value.is_zero():
        return '0'
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _identity(values):
    return sha256(json.dumps(values, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def build_swing_structure(snapshot, *, computed_at, calendar=None):
    """Consume the complete eligible ATS-1 population; never seek older pivots.

    First same-type pivots have no comparison. Missing ATR preserves the pair as
    an explicitly unavailable comparison, without skipping it in the sequence.
    The input is an in-memory ATS-1 result, not an untrusted deserialization API.
    """
    if not isinstance(snapshot, PivotSnapshot) or snapshot.methodology_version != METHODOLOGY_VERSION:
        raise ValueError('Approved ATS-1 pivot snapshot required.')
    computed = aware_utc(computed_at)
    if computed < snapshot.computed_at:
        raise ValueError('Comparison materialization precedes pivot snapshot.')
    calendar = calendar or USMarketCalendar()
    ordered = sorted(snapshot.pivots, key=lambda p: (p.event_session, p.pivot_type.value, p.logical_id))
    seen = set()
    for p in ordered:
        key = (p.event_session, p.pivot_type)
        if (not isinstance(p, ConfirmedPivot) or p.pivot_type not in (PivotType.HIGH, PivotType.LOW)
                or p.symbol != snapshot.source_dataset.symbol or p.timeframe != 'DAILY'
                or p.methodology_version != METHODOLOGY_VERSION
                or not snapshot.window_start <= p.event_session <= snapshot.anchor_session
                or p.market_as_of != snapshot.market_as_of
                or p.knowledge_as_of != snapshot.knowledge_as_of
                or p.source_retrieved_at != snapshot.source_dataset.retrieved_at
                or p.confirmed_at > snapshot.market_as_of or p.available_at > computed
                or key in seen):
            raise ValueError('Inconsistent or duplicate eligible pivot dependency.')
        seen.add(key)
        expected = calendar.advance_sessions(p.event_session, 2)
        if p.right_sessions != (calendar.advance_sessions(p.event_session, 1).date, expected.date) or p.confirmed_at != expected.closes_at:
            raise ValueError('Pivot confirmation differs from the ATS-1 calendar rule.')
    previous, pairs = {}, []
    for p in ordered:
        if p.pivot_type in previous:
            pairs.append((previous[p.pivot_type], p))
        previous[p.pivot_type] = p
    contexts = build_historical_feature_index(snapshot.source_dataset,
        [later.right_sessions[-1] for _, later in pairs], market_as_of=snapshot.market_as_of,
        knowledge_as_of=snapshot.knowledge_as_of, computed_at=computed, calendar=calendar)
    result = []
    for earlier, later in pairs:
        context = contexts.resolve(later.right_sessions[-1])
        atr = context.atr_14.feature
        difference, tolerance, classification = _comparison_values(
            earlier.price, later.price, atr.value, later.pivot_type)
        reason = atr.unavailable_reason if atr.value is None else (
            'NON_POSITIVE_ATR' if atr.value <= 0 else None)
        key = [later.symbol, later.timeframe, METHODOLOGY_VERSION, later.pivot_type.value,
               earlier.logical_id, later.logical_id]
        logical = 'SWING:' + _identity(key)
        state = 'SWING_STATE:' + _identity([key, earlier.state_id, later.state_id,
            context.atr_14.state_id, _canonical_numeric_identity(EQUALITY_MULTIPLIER),
            _canonical_numeric_identity(difference),
            _canonical_numeric_identity(tolerance) if tolerance is not None else None,
            classification, reason])
        limits = tuple(sorted(set(snapshot.limitations + earlier.limitations + later.limitations + context.limitations)))
        result.append(SwingComparison(earlier, later, context, difference, tolerance,
            classification, reason, logical, state,
            max(computed, earlier.available_at, later.available_at, context.available_at),
            computed, limits))
    # Pairs already follow later event session, HIGH before LOW, then logical ID.
    return SwingStructureSnapshot(snapshot, tuple(result), computed)
