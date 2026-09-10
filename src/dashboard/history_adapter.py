"""Read stored ticker history only; no initialization, memory generation or research."""
from pathlib import Path
import sqlite3

from src.decision_store import DecisionStore
from src.ui_contracts import DecisionHistoryPageData, UISectionAvailability


class HistoryReadError(RuntimeError):
    """Sanitized presentation error; never carries database contents."""


def load_history(database_path: str, ticker: str) -> DecisionHistoryPageData:
    """Reuse V0.3 lexical newest-first ordering and separately ordered outcomes.

    The existing store requires a ticker; no all-ticker SQL is duplicated here.
    Missing files are never created. Every connection uses SQLite read-only mode.
    """
    if not isinstance(database_path, str) or not database_path.strip():
        raise HistoryReadError('Enter an existing history database path.')
    if not isinstance(ticker, str) or not ticker.strip():
        raise HistoryReadError('Enter a ticker to inspect its stored decisions.')
    ticker = ticker.strip().upper()
    try:
        path = Path(database_path.strip()).expanduser()
        if not path.is_file():
            return DecisionHistoryPageData(availability={'history': UISectionAvailability(
                True, False, 'History database does not exist or is not a file. No database was created.')})
        store = DecisionStore(str(path), read_only=True)
        decisions = store.get_decisions_for_ticker(ticker)
        outcomes = [outcome for decision in decisions
                    for outcome in store.get_outcomes_for_decision(decision.decision_id)]
        return DecisionHistoryPageData(decisions=decisions, outcomes=outcomes,
            availability={'history': UISectionAvailability(
                True, bool(decisions), None if decisions else 'No stored decisions match this ticker.')})
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, AttributeError):
        raise HistoryReadError('Unable to read stored history. Check the database path, permissions and stored data format.') from None


def select_decision(data: DecisionHistoryPageData, decision_id: str):
    """Resolve selection only against loaded historical records, never current data."""
    return next((item for item in data.decisions if item.decision_id == decision_id), None)
