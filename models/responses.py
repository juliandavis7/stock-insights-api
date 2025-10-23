"""Response models for the FastAPI application"""

from pydantic import BaseModel
from typing import Dict, Optional, Any, List


class MetricsResponse(BaseModel):
    """Model for stock metrics response"""
    ttm_pe: Optional[float]
    forward_pe: Optional[float]
    two_year_forward_pe: Optional[float]
    ttm_eps_growth: Optional[float]
    current_year_eps_growth: Optional[float]
    next_year_eps_growth: Optional[float]
    ttm_revenue_growth: Optional[float]
    current_year_revenue_growth: Optional[float]
    next_year_revenue_growth: Optional[float]
    gross_margin: Optional[float]
    net_margin: Optional[float]
    ttm_ps_ratio: Optional[float]
    forward_ps_ratio: Optional[float]
    # Stock info fields removed - use /info endpoint instead
    ticker: Optional[str]


class ProjectionResponse(BaseModel):
    """Model for the projection response"""
    success: bool
    ticker: str
    current_year: int
    base_data: Dict[str, float]
    projections: Dict[int, Dict[str, float]]
    summary: Dict[str, Any]
    error: Optional[str] = None


class ProjectionBaseDataResponse(BaseModel):
    """Model for projection base data response"""
    ticker: str
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
    ticker: str
    # Stock info fields removed - use /info endpoint instead
    historical: List[FinancialDataResponse]
    estimates: List[AnalystEstimateResponse]


class ErrorResponse(BaseModel):
    """Model for error responses"""
    success: bool = False
    error: str
    ticker: Optional[str] = None