"""Research structural shell."""
from src.ui_contracts import ResearchPageData
from src.dashboard.components import header, sections


def render():
    header('Research', 'Explore company research, reasoning and its supporting evidence.')
    sections(ResearchPageData(), [('Ticker / company', True, 'No company research loaded.'), ('Recommendation and confidence', True, 'No validated analysis loaded.'), ('Thesis and assessments', True, 'No fundamental, valuation or earnings assessments loaded.'), ('Specialist analysis', False, 'Same-run specialist capture is not connected.'), ('Evidence / provenance', False, 'Same-run evidence drill-down is not connected; no IDs are reconstructed.'), ('Risks', True, 'No current risk interpretations loaded.'), ('Scenarios and invalidation events', True, 'No forecasts or thesis-invalidation conditions loaded.')])
