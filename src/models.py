from dataclasses import dataclass, field


@dataclass
class IncomeStatementPeriod:
    fiscal_date_ending: str
    total_revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None


@dataclass
class BalanceSheetPeriod:
    fiscal_date_ending: str
    cash_and_cash_equivalents: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    long_term_debt: float | None = None
    total_debt: float | None = None
    shareholder_equity: float | None = None


@dataclass
class CashFlowPeriod:
    fiscal_date_ending: str
    operating_cash_flow: float | None = None
    capital_expenditures: float | None = None


@dataclass
class EarningsPeriod:
    fiscal_date_ending: str
    reported_date: str | None = None
    reported_eps: float | None = None
    estimated_eps: float | None = None
    surprise: float | None = None
    surprise_percentage: float | None = None


@dataclass
class EarningsCallTranscriptSegment:
    content: str
    speaker: str | None = None
    title: str | None = None
    sentiment: float | None = None  # Vendor-supplied annotation, not our analysis.


@dataclass
class NewsItem:
    title: str
    source: str | None = None
    time_published: str | None = None
    url: str | None = None
    ticker_relevance_score: float | None = None


@dataclass
class StockResearchData:
    ticker: str
    company_name: str
    data_source: str
    data_timestamp: str
    current_price: float | None = None
    market_cap: float | None = None
    revenue: float | None = None
    net_income: float | None = None
    eps: float | None = None
    free_cash_flow: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    price_to_sales: float | None = None
    ev_to_ebitda: float | None = None
    latest_earnings_date: str | None = None
    latest_earnings_revenue: float | None = None
    latest_earnings_eps: float | None = None
    guidance: str | None = None
    recent_news: list[str] = field(default_factory=list)
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None  # Decimal: 1.23% is 0.0123.
    latest_trading_day: str | None = None


@dataclass
class ResearchSnapshot:
    stock: StockResearchData
    income_statements: list[IncomeStatementPeriod]
    balance_sheets: list[BalanceSheetPeriod]
    cash_flows: list[CashFlowPeriod]
    earnings: list[EarningsPeriod]
    news: list[NewsItem]
    earnings_call_transcript: list[EarningsCallTranscriptSegment]
    income_statement_metrics: dict[str, float | None]
    balance_sheet_metrics: dict[str, float | None]
    cash_flow_metrics: dict[str, float | None]
    earnings_metrics: dict[str, float | int | None]
    missing_data: list[str]
    source: str
    generated_at: str


@dataclass
class InterpretationStatement:
    """AI judgment about current/historical evidence, cited by exact evidence IDs."""

    text: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class ForecastStatement:
    """Forward-looking scenario or condition, based on cited evidence IDs."""

    text: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class MaterialEvidenceReview:
    """Generated review of one material evidence item; provenance stays in the catalog."""

    observation: str
    thesis_relevance: str


@dataclass
class InvestmentAnalysis:
    """Report contract; recommendation: Buy, Accumulate, Hold, Trim, or Avoid.

    confidence_score is confidence in the recommendation given available evidence,
    on a 0-100 scale, not a price-move probability. No scoring is performed here.
    """

    ticker: str
    recommendation: str
    confidence_score: float
    fundamental_assessment: str
    valuation_assessment: str
    earnings_assessment: str
    bull_case: list[InterpretationStatement]
    bear_case: list[InterpretationStatement]
    supporting_evidence: list[InterpretationStatement]
    major_risks: list[InterpretationStatement]
    thesis_invalidation_conditions: list[ForecastStatement]
    scenarios: list[ForecastStatement]
    missing_data: list[str]
    reasoning_summary: str
    material_evidence_review: dict[str, MaterialEvidenceReview]
    portfolio_assessment: str = "Portfolio context not supplied."


def _validate_portfolio_amount(value: float, name: str) -> None:
    # NaN/infinity and booleans are not usable user-supplied quantities.
    from math import isfinite

    if type(value) not in (int, float) or not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number.")


@dataclass
class PortfolioPositionInput:
    """User-supplied long-only holding. Zero-share positions are retained.

    Validation occurs at construction; no prices or metrics are inferred.
    """

    ticker: str
    shares: float
    average_cost: float

    def __post_init__(self):
        if not isinstance(self.ticker, str) or not self.ticker.strip():
            raise ValueError("A non-empty portfolio ticker is required.")
        self.ticker = self.ticker.strip().upper()
        _validate_portfolio_amount(self.shares, "shares")
        _validate_portfolio_amount(self.average_cost, "average_cost")


@dataclass
class PortfolioInput:
    """User-supplied holdings and cash; duplicate normalized tickers are rejected.

    Separate lots are never merged. An empty positions list permits cash-only input.
    """

    positions: list[PortfolioPositionInput]
    cash: float

    def __post_init__(self):
        _validate_portfolio_amount(self.cash, "cash")
        if not isinstance(self.positions, list) or not all(
            isinstance(position, PortfolioPositionInput) for position in self.positions
        ):
            raise ValueError("positions must be a list of PortfolioPositionInput objects.")
        tickers = [position.ticker.strip().upper() for position in self.positions]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Duplicate portfolio tickers are not allowed.")


@dataclass
class PortfolioPosition:
    """Output contract: copied inputs, retrieved latest available price, and metrics.

    All fields after current_price are deterministic calculated metrics, not AI
    interpretations. Ratios/percent changes use decimals (0.10 means 10%). None
    represents unavailable results; construction performs no calculations.
    """

    ticker: str
    shares: float
    average_cost: float
    current_price: float | None
    cost_basis: float
    position_value: float | None
    unrealized_gain_loss: float | None
    unrealized_gain_loss_percent: float | None
    portfolio_weight: float | None


@dataclass
class PortfolioSnapshot:
    """Copied user cash and positions with deterministic totals/concentration.

    Intended future flow: PortfolioInput -> retrieve latest available prices ->
    deterministic calculations -> PortfolioSnapshot + existing ResearchSnapshot
    -> portfolio-aware analysis. No retrieval, AI interpretation, or forecast is
    implemented here. Weights are decimal fractions; unavailable metrics are None.
    """

    positions: list[PortfolioPosition]
    cash: float
    total_positions_value: float | None
    total_portfolio_value: float | None
    cash_weight: float | None
    largest_position_ticker: str | None
    largest_position_weight: float | None

    # Stock weights include cash in the denominator; cash is not a position.
    top_3_weight: float | None
    position_count: int
    effective_position_count: float | None
    herfindahl_index: float | None


@dataclass
class PortfolioRiskPolicy:
    """Configured portfolio limits, not investment recommendations."""

    max_single_position_weight: float = 0.25
    max_top_3_weight: float = 0.60
    minimum_cash_weight: float = 0.05

    def __post_init__(self):
        for name in ('max_single_position_weight', 'max_top_3_weight', 'minimum_cash_weight'):
            value = getattr(self, name)
            _validate_portfolio_amount(value, name)
            if value > 1:
                raise ValueError(f"{name} must be between 0 and 1.")


@dataclass
class PortfolioRiskAssessment:
    """Deterministic policy outputs only; no investment judgment or action."""

    oversized_positions: list[str]
    largest_position_over_limit: bool | None
    top_3_concentration_over_limit: bool | None
    minimum_cash_below_target: bool | None
    concentration_policy_evaluable: bool
    notes: list[str]


@dataclass
class PortfolioAnalysisContext:
    """Deterministic portfolio inputs, kept separate from stock evidence IDs."""

    target_ticker: str
    owns_target: bool
    target_shares: float
    target_average_cost: float | None
    target_current_price: float | None
    target_position_value: float | None
    target_unrealized_gain_loss: float | None
    target_unrealized_gain_loss_percent: float | None
    target_portfolio_weight: float | None
    cash_weight: float | None
    largest_position_ticker: str | None
    largest_position_weight: float | None
    top_3_weight: float | None
    herfindahl_index: float | None
    effective_position_count: float | None
    portfolio_risk_assessment: PortfolioRiskAssessment
