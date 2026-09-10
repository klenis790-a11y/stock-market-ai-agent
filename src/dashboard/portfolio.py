"""Portfolio structural shell."""
from src.ui_contracts import PortfolioPageData
from src.dashboard.components import header, sections


def render():
    header('Portfolio', 'Separate company attractiveness from portfolio suitability.')
    sections(PortfolioPageData(), [('Portfolio summary', True, 'No portfolio snapshot loaded.'), ('Holdings', True, 'No holdings supplied.'), ('Allocation', True, 'No backend-calculated weights loaded.'), ('Position recommendations', True, 'No portfolio-aware analysis loaded.'), ('Concentration / risk', True, 'No deterministic policy results loaded. Policy flags are not trade advice.')])
