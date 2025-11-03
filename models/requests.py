"""Request models for the FastAPI application"""

from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, Literal
from datetime import datetime


class CreateUserRequest(BaseModel):
    """Request body for creating a user."""
    pass  # No body needed - we get everything from JWT


class UpdateSubscriptionStatusRequest(BaseModel):
    """Request body for updating a user's subscription status."""
    subscription_status: Literal['trial', 'active', 'expired'] = Field(
        ..., 
        description="New subscription status: 'trial', 'active', or 'expired'"
    )


class CreateCheckoutRequest(BaseModel):
    """Request model for creating a Polar checkout session."""
    product_id: str = Field(..., description="Polar product ID from dashboard")
    success_url: Optional[str] = Field(None, description="URL to redirect after successful payment")
    cancel_url: Optional[str] = Field(None, description="URL to redirect if user cancels")


class YearProjection(BaseModel):
    """Model for a single year's projection inputs"""
    revenue_growth: float = Field(..., ge=-0.5, le=1.0, description="Revenue growth rate (decimal, e.g., 0.15 for 15%)")
    net_income_growth: float = Field(..., ge=-1.0, le=2.0, description="Net income growth rate (decimal)")
    net_income_margin: Optional[float] = Field(None, ge=0.0, le=0.5, description="Expected net income margin (decimal)")
    pe_low: float = Field(..., gt=0, le=100, description="Low PE ratio estimate")
    pe_high: float = Field(..., gt=0, le=200, description="High PE ratio estimate")
    
    @validator('pe_high')
    def pe_high_must_be_greater_than_low(cls, v, values):
        if 'pe_low' in values and v < values['pe_low']:
            raise ValueError('pe_high must be greater than or equal to pe_low')
        return v


class ProjectionRequest(BaseModel):
    """Model for the complete projection request"""
    projections: Dict[int, YearProjection] = Field(..., description="Projections by year")
    
    @validator('projections')
    def validate_projection_years(cls, v):
        current_year = datetime.now().year
        valid_years = set(range(current_year + 1, current_year + 5))
        
        for year in v.keys():
            if year not in valid_years:
                raise ValueError(f"Invalid year {year}. Must be between {current_year + 1} and {current_year + 4}")
        
        if not v:
            raise ValueError("At least one projection year must be provided")
        
        return v