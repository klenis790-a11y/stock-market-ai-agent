from dataclasses import dataclass, field


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
