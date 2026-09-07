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

    evidence_id: str
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
    material_evidence_review: list[MaterialEvidenceReview]
