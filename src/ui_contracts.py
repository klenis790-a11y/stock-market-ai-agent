"""Presentation-neutral containers, not application services or derived financial data.

Backend objects are referenced, not recalculated or reconstructed. Consumers must
not mutate them. Evidence IDs come only from backend catalogs; historical artifacts
must never be filled with current data. None means unavailable, never zero.
"""
from dataclasses import dataclass, field
from src.models import (
    ResearchSnapshot, InvestmentAnalysis, PortfolioSnapshot, PortfolioRiskAssessment,
    PortfolioAnalysisContext, SpecialistAnalysis, DecisionRecord, DecisionOutcome,
    DecisionMemoryContext,
)


@dataclass(frozen=True)
class UISectionAvailability:
    backend_supported: bool
    data_available: bool
    reason: str | None = None

    def __post_init__(self):
        if type(self.backend_supported) is not bool or type(self.data_available) is not bool:
            raise ValueError('Availability flags must be booleans.')
        if self.data_available and not self.backend_supported:
            raise ValueError('Unsupported sections cannot claim available data.')
        if not self.data_available and (not isinstance(self.reason, str) or not self.reason.strip()):
            raise ValueError('Unavailable sections require a reason.')


@dataclass(frozen=True)
class DashboardPage:
    key: str
    title: str

    def __post_init__(self):
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError('Page key is required.')
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError('Page title is required.')


DASHBOARD_PAGES = (
    DashboardPage('home', 'Command Center'),
    DashboardPage('research', 'Research'),
    DashboardPage('portfolio', 'Portfolio'),
    DashboardPage('agent_room', 'Agent Room'),
    DashboardPage('decision_history', 'Decision History'),
    DashboardPage('performance', 'Performance'),
)


@dataclass
class HomePageData:
    # Summary rendering only; no invented activity feed or freshness timestamp.
    portfolio: PortfolioSnapshot | None = None
    risk_assessment: PortfolioRiskAssessment | None = None
    current_analysis: InvestmentAnalysis | None = None
    recent_decisions: list[DecisionRecord] = field(default_factory=list)
    availability: dict[str, UISectionAvailability] = field(default_factory=dict)


@dataclass
class ResearchPageData:
    analysis: InvestmentAnalysis | None = None
    snapshot: ResearchSnapshot | None = None
    evidence_package: dict | None = None
    evidence_catalog: list[dict] | None = None
    portfolio_context: PortfolioAnalysisContext | None = None
    availability: dict[str, UISectionAvailability] = field(default_factory=dict)


@dataclass
class PortfolioPageData:
    snapshot: PortfolioSnapshot | None = None
    risk_assessment: PortfolioRiskAssessment | None = None
    analysis_context: PortfolioAnalysisContext | None = None
    analysis: InvestmentAnalysis | None = None
    availability: dict[str, UISectionAvailability] = field(default_factory=dict)


@dataclass
class AgentRoomPageData:
    # Ordered names/results are supplied by the application, never a fixed pair.
    registered_specialists: tuple[str, ...] = ()
    specialist_results: list[SpecialistAnalysis] = field(default_factory=list)
    synthesis: InvestmentAnalysis | None = None
    evidence_package: dict | None = None
    evidence_catalog: list[dict] | None = None
    availability: dict[str, UISectionAvailability] = field(default_factory=dict)


@dataclass
class DecisionHistoryPageData:
    decisions: list[DecisionRecord] = field(default_factory=list)
    outcomes: list[DecisionOutcome] = field(default_factory=list)
    # A backend-built historical view, NOT proof of memory used by an old run.
    memory_context: DecisionMemoryContext | None = None
    availability: dict[str, UISectionAvailability] = field(default_factory=dict)


@dataclass
class PerformancePageData:
    availability: UISectionAvailability = field(default_factory=lambda: UISectionAvailability(
        False, False, 'Performance analytics are not implemented; stored outcomes alone do not establish evaluated performance.'
    ))
