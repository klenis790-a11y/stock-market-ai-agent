"""Decision History structural shell."""
from src.ui_contracts import DecisionHistoryPageData
from src.dashboard.components import header, sections


def render():
    header('Decision History', 'Inspect preserved decisions separately from later observed outcomes.')
    sections(DecisionHistoryPageData(), [('Prior recommendations', True, 'No history source loaded. This does not mean the database is empty.'), ('Decision details', True, 'Date, ticker, decision, confidence and thesis summary will use preserved records only.'), ('Later outcomes', True, 'No stored outcomes loaded; none will be fabricated.'), ('Historical evidence', False, 'Full historical evidence and portfolio snapshots are not archived. Current data will not substitute.')])
