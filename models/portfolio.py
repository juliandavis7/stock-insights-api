"""Portfolio upload models."""
from pydantic import BaseModel
from typing import List, Optional


class PortfolioHolding(BaseModel):
    ticker: str
    name: Optional[str] = None
    shares: float
    cost_basis: float
    # market_value, gain_loss_pct, percent_of_portfolio, current_price, pe_ratio
    # are calculated dynamically on the frontend based on current stock prices


class PortfolioHoldingEnriched(BaseModel):
    """Portfolio holding with all dynamic values calculated."""
    ticker: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    country_code: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    shares: float
    cost_basis: float
    market_value: Optional[float] = None
    gain_loss_pct: Optional[float] = None
    percent_of_portfolio: Optional[float] = None
    current_price: Optional[float] = None
    pe_ratio: Optional[float] = None


class ExcludedItem(BaseModel):
    ticker: str
    reason: str


class PortfolioUploadResponse(BaseModel):
    holdings: List[PortfolioHolding]
    total_cost_basis: float  # Only static cost basis total
    detected_format: str
    excluded_items: List[ExcludedItem]


class PortfolioResponse(BaseModel):
    """Portfolio response with all dynamic values calculated."""
    holdings: List[PortfolioHoldingEnriched]
    total_market_value: Optional[float] = None
    total_cost_basis: float
    total_gain_loss_pct: Optional[float] = None
    detected_format: str
    excluded_items: List[ExcludedItem]


class HoldingCreateRequest(BaseModel):
    """Request model for creating a new holding.
    
    Note: ticker is passed as query parameter, not in body.
    """
    name: Optional[str] = None  # Optional, will fetch from yfinance if not provided
    shares: Optional[float] = 0.0  # Can be 0 initially
    cost_basis: Optional[float] = 0.0  # Can be 0 initially


class HoldingUpdateRequest(BaseModel):
    """Request model for updating an existing holding."""
    shares: Optional[float] = None
    cost_basis: Optional[float] = None
    name: Optional[str] = None  # Optional, for updating company name


class HoldingResponse(BaseModel):
    """Response model for individual holding operations."""
    ticker: str
    name: Optional[str] = None
    shares: float
    cost_basis: float
    message: str


class HoldingUpdateResponse(BaseModel):
    """Response model for PUT /portfolio/holdings.
    
    Returns the updated holding with calculated values,
    plus all holdings with recalculated percent_of_portfolio.
    """
    # The updated holding with all calculated fields
    updated_holding: PortfolioHoldingEnriched
    # All holdings with recalculated percent_of_portfolio
    holdings: List[PortfolioHoldingEnriched]
    # Portfolio totals
    total_market_value: Optional[float] = None
    total_cost_basis: float
    total_gain_loss_pct: Optional[float] = None
    message: str

