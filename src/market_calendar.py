"""Offline XNYS regular sessions; no instrument discovery or market-data access."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
import exchange_calendars


def aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('An aware datetime is required.')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class MarketSession:
    date: date
    opens_at: datetime
    closes_at: datetime


class USMarketCalendar:
    """Fixed coverage avoids wall-clock-dependent defaults. Schedules are versioned,
    not a guarantee against future emergency closures. Outside coverage fails closed.
    """
    calendar_id = 'XNYS'
    version = exchange_calendars.__version__
    timezone = ZoneInfo('America/New_York')

    def __init__(self):
        self._calendar = exchange_calendars.get_calendar(
            self.calendar_id, start='1990-01-01', end='2050-12-31')

    def session_on_or_after(self, day: date) -> MarketSession:
        label = self._calendar.date_to_session(day.isoformat(), direction='next')
        return MarketSession(label.date(), self._calendar.session_open(label).to_pydatetime(),
                             self._calendar.session_close(label).to_pydatetime())

    def classify(self, instant: datetime) -> str:
        instant = aware_utc(instant)
        day = instant.astimezone(self.timezone).date()
        session = self.session_on_or_after(day)
        if session.date != day:
            return 'MARKET_CLOSED'
        if instant < session.opens_at:
            return 'PRE_MARKET'
        if instant < session.closes_at:
            return 'REGULAR_SESSION'
        return 'AFTER_HOURS'
