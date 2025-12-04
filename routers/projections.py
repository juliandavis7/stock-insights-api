"""Projections endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from models import ProjectionRequest, ProjectionResponse, ProjectionBaseDataResponse
from services.utils import calculate_financial_projections
from core.auth import verify_access
from services.validators import validate_ticker_or_raise, validate_projection_inputs
from services.projection_service import ProjectionService
from services.supabase_service import supabase_service
from constants.constants import FMP_API_KEY
from core.rate_limit import user_limiter, global_limiter, PROJECTIONS_USER_LIMIT, PROJECTIONS_GLOBAL_LIMIT
from core.deprecation import add_deprecation_headers

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/projections", response_model=ProjectionResponse)
@user_limiter.limit(PROJECTIONS_USER_LIMIT)
@global_limiter.limit(PROJECTIONS_GLOBAL_LIMIT)
async def create_financial_projections(
    request: Request,
    request_body: ProjectionRequest,
    ticker: str = Query(..., description="Stock ticker symbol (e.g., AAPL)", regex="^[A-Z]{1,5}$"),
    user: Dict = Depends(verify_access)
):
    """
    Calculate financial projections for a stock based on user assumptions.
    
    Args:
        ticker: Stock ticker symbol as query parameter
        request: Projection inputs in request body
    
    Returns:
        Financial projections including revenue, net income, EPS, stock price ranges, and CAGR
    """
    # Convert Pydantic models to dictionary format expected by utils
    projection_inputs = {}
    for year, projection in request_body.projections.items():
        projection_inputs[year] = {
            'revenue_growth': projection.revenue_growth,
            'net_income_growth': projection.net_income_growth,
            'net_income_margin': projection.net_income_margin,
            'pe_low': projection.pe_low,
            'pe_high': projection.pe_high
        }
    
    # Validate inputs using utility function
    validation_errors = validate_projection_inputs(projection_inputs)
    if validation_errors:
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "Validation failed",
                "details": validation_errors
            }
        )
    
    # Calculate projections
    try:
        result = calculate_financial_projections(
            ticker=ticker.upper(),
            api_key=FMP_API_KEY,
            projection_inputs=projection_inputs
        )
        
        if not result.get('success', True):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": result.get('error', 'Unknown error occurred'),
                    "ticker": ticker
                }
            )
        
        # Remove ticker if present (not needed in response, already in query param)
        result.pop('ticker', None)
        response_data = ProjectionResponse(**result)
        return JSONResponse(content=response_data.dict())
    
    except ValueError as e:
        # ValueError raised by FMPService when ticker not found in mocks
        logger.error(f"❌ API: Ticker {ticker} not found: {e}")
        validate_ticker_or_raise(ticker)
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a ticker not found error from FMP API
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['not found', 'invalid symbol', 'unknown symbol', 'invalid ticker']):
            logger.error(f"❌ API: Ticker {ticker} not found in FMP API: {e}")
            validate_ticker_or_raise(ticker)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Internal server error: {str(e)}",
                "ticker": ticker
            }
        )


@router.get("/projections", response_model=ProjectionBaseDataResponse)
@user_limiter.limit(PROJECTIONS_USER_LIMIT)
@global_limiter.limit(PROJECTIONS_GLOBAL_LIMIT)
def get_projection_base_data(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_access)):
    """
    Get projections data from cached Supabase data.
    
    Args:
        ticker: Stock ticker symbol (e.g., META)
        
    Returns:
        ProjectionBaseDataResponse with data from projections column
        
    Raises:
        404: If ticker not found in cache (cache miss)
        500: If Supabase connection error
    """
    try:
        stock_data = supabase_service.get_stock_data(ticker)
        
        if not stock_data:
            logger.info(f"Cache miss for ticker {ticker} in /projections")
            raise HTTPException(status_code=404, detail=f"Projections data not found for ticker {ticker}. Cache miss - data not yet scraped.")
        
        projections = stock_data.get('projections')
        
        if not projections:
            logger.warning(f"No projections data found for ticker {ticker}")
            raise HTTPException(status_code=404, detail=f"Projections data not available for ticker {ticker}")
        
        # Map projections to ProjectionBaseDataResponse format
        projections_dict = dict(projections) if isinstance(projections, dict) else {}
        
        # Remove ticker if present (not needed in response)
        projections_dict.pop('ticker', None)
        
        return JSONResponse(content=projections_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /projections endpoint for {ticker}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error fetching projections data: {str(e)}")


@router.get("/v1/projections", response_model=ProjectionBaseDataResponse, deprecated=True)
@user_limiter.limit(PROJECTIONS_USER_LIMIT)
@global_limiter.limit(PROJECTIONS_GLOBAL_LIMIT)
def get_projection_base_data_v1(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_access)):
    """
    [DEPRECATED] Get base data for financial projections including current stock metrics.
    
    This endpoint is deprecated. Use /projections instead, which uses cached Supabase data.
    
    Args:
        ticker: Stock ticker symbol (e.g., CELH, AAPL)
        
    Returns:
        Base data including price, market cap, shares outstanding, and financial metrics
    """
    try:
        projection_service = ProjectionService()
        data = projection_service.get_stock_current_data(ticker.upper(), FMP_API_KEY)
        
        if not data:
            logger.error(f"❌ API: Unable to fetch projection data for ticker {ticker}")
            validate_ticker_or_raise(ticker)
        
        # Calculate net income margin if we have both net income and revenue
        net_income_margin = None
        if data.get('net_income') and data.get('revenue') and data['revenue'] > 0:
            net_income_margin = int(round((data['net_income'] / data['revenue']) * 100))
        
        response_data = ProjectionBaseDataResponse(
            # Stock info fields removed - use /info endpoint instead
            revenue=data.get('revenue'),
            net_income=data.get('net_income'),
            eps=data.get('current_year_eps'),
            net_income_margin=net_income_margin,
            data_year=data['data_year']
        )
        response = JSONResponse(content=response_data.dict())
        return add_deprecation_headers(response, "/projections")
    
    except ValueError as e:
        # ValueError raised by FMPService when ticker not found in mocks
        logger.error(f"❌ API: Ticker {ticker} not found: {e}")
        validate_ticker_or_raise(ticker)
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a ticker not found error from FMP API
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['not found', 'invalid symbol', 'unknown symbol', 'invalid ticker']):
            logger.error(f"❌ API: Ticker {ticker} not found in FMP API: {e}")
            validate_ticker_or_raise(ticker)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Internal server error: {str(e)}",
                "ticker": ticker.upper()
            }
        )

