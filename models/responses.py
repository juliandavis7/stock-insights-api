"""Response models for the FastAPI application"""

from pydantic import BaseModel
from typing import Dict, Optional, Any, List


class MetricsResponse(BaseModel):
    """Model for stock metrics response"""
    # Mandatory Metrics - PE Ratios
    ttm_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    two_year_forward_pe: Optional[float] = None
    # Mandatory Metrics - EPS Growth
    ttm_eps_growth: Optional[float] = None
    current_year_eps_growth: Optional[float] = None
    next_year_eps_growth: Optional[float] = None
    # Mandatory Metrics - Revenue Growth
    ttm_revenue_growth: Optional[float] = None
    current_year_revenue_growth: Optional[float] = None
    next_year_revenue_growth: Optional[float] = None
    # Mandatory Metrics - Margins
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    # Mandatory Metrics - P/S Ratios
    ttm_ps_ratio: Optional[float] = None
    forward_ps_ratio: Optional[float] = None
    # Advanced Metrics - EPS Growth
    last_year_eps_growth: Optional[float] = None
    ttm_vs_ntm_eps_growth: Optional[float] = None
    current_quarter_eps_growth_vs_previous_year: Optional[float] = None
    two_year_stack_exp_eps_growth: Optional[float] = None
    # Advanced Metrics - Revenue Growth
    last_year_revenue_growth: Optional[float] = None
    ttm_vs_ntm_revenue_growth: Optional[float] = None
    current_quarter_revenue_growth_vs_previous_year: Optional[float] = None
    two_year_stack_exp_revenue_growth: Optional[float] = None
    # Advanced Metrics - Valuation Ratios
    peg_ratio: Optional[float] = None
    return_on_equity: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_free_cash_flow: Optional[float] = None
    free_cash_flow_yield: Optional[float] = None
    # Advanced Metrics - Dividends
    dividend_yield: Optional[float] = None
    dividend_payout_ratio: Optional[float] = None


class ProjectionResponse(BaseModel):
    """Model for the projection response"""
    success: bool
    current_year: int
    base_data: Dict[str, float]
    projections: Dict[int, Dict[str, float]]
    summary: Dict[str, Any]
    error: Optional[str] = None


class ProjectionBaseDataResponse(BaseModel):
    """Model for projection base data response"""
    # Stock info fields removed - use /info endpoint instead
    revenue: Optional[int] = None
    net_income: Optional[int] = None
    eps: Optional[float] = None
    net_income_margin: Optional[int] = None
    data_year: int


class FinancialStatementResponse(BaseModel):
    """Model for financial statement response (mock FMP API response)"""
    date: str
    symbol: str
    reportedCurrency: str
    cik: str
    filingDate: str
    acceptedDate: str
    fiscalYear: str
    period: str
    revenue: int
    costOfRevenue: int
    grossProfit: int
    researchAndDevelopmentExpenses: int
    generalAndAdministrativeExpenses: int
    sellingAndMarketingExpenses: int
    sellingGeneralAndAdministrativeExpenses: int
    otherExpenses: int
    operatingExpenses: int
    costAndExpenses: int
    netInterestIncome: int
    interestIncome: int
    interestExpense: int
    depreciationAndAmortization: int
    ebitda: int
    ebit: int
    nonOperatingIncomeExcludingInterest: int
    operatingIncome: int
    totalOtherIncomeExpensesNet: int
    incomeBeforeTax: int
    incomeTaxExpense: int
    netIncomeFromContinuingOperations: int
    netIncomeFromDiscontinuedOperations: int
    otherAdjustmentsToNetIncome: int
    netIncome: int
    netIncomeDeductions: int
    bottomLineNetIncome: int
    eps: float
    epsDiluted: float
    weightedAverageShsOut: int
    weightedAverageShsOutDil: int


class AnalystEstimateResponse(BaseModel):
    """Model for analyst estimates data"""
    fiscalYear: str
    totalRevenue: Optional[int]
    netIncome: Optional[int]
    eps: Optional[float]
    dilutedEps: Optional[float]

class FinancialDataResponse(BaseModel):
    """Model for processed financial data response"""
    fiscalYear: str
    totalRevenue: Optional[int]
    costOfRevenue: Optional[int]
    grossProfit: Optional[int]
    sellingGeneralAndAdministrative: Optional[int]
    researchAndDevelopment: Optional[int]
    operatingExpenses: Optional[int]
    operatingIncome: Optional[int]
    netIncome: Optional[int]
    eps: Optional[float]
    dilutedEps: Optional[float]

class ComprehensiveFinancialResponse(BaseModel):
    """Model for comprehensive financial data including historical and analyst estimates"""
    # Stock info fields removed - use /info endpoint instead
    historical: List[FinancialDataResponse]
    estimates: List[AnalystEstimateResponse]


class IncomeStatementResponse(BaseModel):
    """Model for income statement data from scraped source"""
    years: List[int]
    metrics: Dict[str, List[Optional[Any]]]


class ErrorResponse(BaseModel):
    """Model for error responses"""
    success: bool = False
    error: str
    ticker: Optional[str] = None


class CheckoutResponse(BaseModel):
    """Response model for checkout creation."""
    checkout_url: str
    checkout_id: str
    status: str


class PortalResponse(BaseModel):
    """Response model for Stripe Customer Portal session."""
    portal_url: str


class SubscriptionsResponse(BaseModel):
    """Response model for user subscriptions."""
    subscriptions: List[Dict[str, Any]]
    count: int
    has_active_subscription: bool


class ScenarioData(BaseModel):
    """Model for a single scenario (bear_case, base_case, or bull_case)"""
    revenue_growth: list[float]
    net_income_growth: list[float]
    pe_low_est: list[float]
    pe_high_est: list[float]


class SavedProjectionData(BaseModel):
    """Model for saved projection data with all scenarios"""
    bear_case: ScenarioData
    base_case: ScenarioData
    bull_case: ScenarioData


class SavedProjectionGetResponse(BaseModel):
    """Response model for getting saved projections"""
    data: Optional[SavedProjectionData] = None
    updated_at: Optional[str] = None


class SavedProjectionPostResponse(BaseModel):
    """Response model for saving projections"""
    message: str


class SavedProjectionDeleteResponse(BaseModel):
    """Response model for deleting saved projections"""
    message: str

