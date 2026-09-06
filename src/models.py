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


@dataclass
class ResearchSnapshot:
    stock: StockResearchData
    income_statements: list[IncomeStatementPeriod]
    balance_sheets: list[BalanceSheetPeriod]
    cash_flows: list[CashFlowPeriod]
    earnings: list[EarningsPeriod]
    income_statement_metrics: dict[str, float | None]
    balance_sheet_metrics: dict[str, float | None]
    cash_flow_metrics: dict[str, float | None]
    earnings_metrics: dict[str, float | int | None]
    missing_data: list[str]
    source: str
    generated_at: str
