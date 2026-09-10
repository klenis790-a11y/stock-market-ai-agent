"""Agent Room structural shell."""
from src.ui_contracts import AgentRoomPageData
from src.dashboard.components import header, sections


def render():
    header('Agent Room', 'Inspect actual specialist interpretations and final synthesis.')
    sections(AgentRoomPageData(), [('Active agents', False, 'Registry display is not connected; no executed agents are implied.'), ('Agent status', False, 'Execution status telemetry is not available.'), ('Specialist conclusions', False, 'Specialist result capture is not connected.'), ('Bull / bear disagreement', False, 'No specialist results loaded; no conversations or disagreement are invented.'), ('Risk observations', False, 'No specialist risk observations loaded.'), ('Synthesis', True, 'No final synthesis loaded.')])
