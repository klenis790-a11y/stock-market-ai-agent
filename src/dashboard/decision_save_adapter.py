"""Explicit dashboard persistence through the existing V0.3 save helper only."""
from pathlib import Path
import sqlite3

from src.decision_history import save_analysis_decision, utc_decision_timestamp
from src.decision_store import DecisionStore
from src.models import InvestmentAnalysis


class DecisionSaveError(RuntimeError):
    """Safe user-facing persistence error."""


def save_research_decision(data, database_path, *, decision_id=None, decision_timestamp=None):
    """Save the successful session analysis, never the editable ticker input.

    Repeated saves can reuse the returned ID; SQLite retains duplicate protection.
    No provider, memory or outcome work occurs here.
    """
    if data is None or not isinstance(data.analysis, InvestmentAnalysis):
        raise DecisionSaveError('A successful research result is required before saving.')
    if not isinstance(database_path, str) or not database_path.strip():
        raise DecisionSaveError('Enter a local decision database path before saving.')
    if '://' in database_path or database_path.strip() == ':memory:':
        raise DecisionSaveError('Choose a local database file path.')
    try:
        store = DecisionStore(str(Path(database_path.strip()).expanduser()))
        store.initialize()
        return save_analysis_decision(data.analysis, store,
            decision_timestamp if decision_timestamp is not None else utc_decision_timestamp(),
            decision_id=decision_id)
    except sqlite3.IntegrityError:
        raise DecisionSaveError('This decision could not be inserted. It may already be saved in this database.') from None
    except (OSError, sqlite3.Error, ValueError, TypeError, RuntimeError):
        raise DecisionSaveError('Decision could not be saved. Check the local database path and permissions.') from None
