"""Home structural shell."""
from src.ui_contracts import HomePageData
from src.dashboard.components import header, sections


def render():
    header('Home', 'Command center for research, portfolio context and recorded activity.')
    sections(HomePageData(), [('Portfolio snapshot', True, 'No portfolio snapshot loaded.'), ('Latest recommendation', True, 'No analysis loaded.'), ('Recent research', True, 'No stored decisions loaded.'), ('Agent activity', False, 'Execution activity telemetry is not available.'), ('Portfolio alerts', True, 'No deterministic portfolio policy results loaded.'), ('Quick research', False, 'Research execution is not connected in this shell.')])
