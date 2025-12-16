"""Portfolio upload endpoint router."""
import logging
from typing import Dict, Optional
from fastapi import APIRouter, File, UploadFile, Query, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from models.portfolio import (
    PortfolioUploadResponse, 
    PortfolioResponse,
    HoldingCreateRequest,
    HoldingUpdateRequest,
    HoldingResponse,
    HoldingUpdateResponse
)
from services.portfolio_parser import (
    parse_portfolio_csv,
    finalize_portfolio_response
)
from services.portfolio_save_service import portfolio_save_service
from services.portfolio_calculator import (
    calculate_portfolio_values,
    calculate_portfolio_totals_and_percentages
)
from core.auth import verify_token
from core.rate_limit import user_limiter, global_limiter

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limit: 30 requests per minute (generous, max 1 FMP call per request)
PORTFOLIO_USER_LIMIT = "30/minute"
PORTFOLIO_GLOBAL_LIMIT = "200/minute"  # Global limit to protect FMP quota


@router.post("/portfolio/upload", response_model=PortfolioUploadResponse)
@user_limiter.limit(PORTFOLIO_USER_LIMIT)
@global_limiter.limit(PORTFOLIO_GLOBAL_LIMIT)
async def upload_portfolio(
    request: Request,
    file: UploadFile = File(...),
    user: Dict = Depends(verify_token)
):
    """
    Upload a CSV file containing portfolio holdings.
    
    Automatically detects CSV format from the following brokerages:
    - Fidelity: Symbol, Quantity, Current Value, Cost Basis Total, Type
    - Chase: Ticker, Quantity, Value, Cost
    - Generic: ticker, shares, cost_basis
    
    Column matching is robust and handles variations in column names (case-insensitive, 
    partial matches, etc.). This ensures the feature continues to work even if CSV formats 
    change slightly.
    
    Returns portfolio holdings with static data only. Dynamic values (market_value, 
    gain_loss_pct, percent_of_portfolio) should be calculated on the frontend based 
    on current stock prices.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV"
        )
    
    # Read file content
    try:
        content = await file.read()
        csv_content = content.decode('utf-8-sig')  # Handle BOM
    except UnicodeDecodeError:
        try:
            csv_content = content.decode('latin-1')
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Unable to decode CSV file. Please ensure it's UTF-8 encoded."
            )
    
    # Parse CSV (auto-detects format)
    try:
        parsed_data, needs_enrichment = parse_portfolio_csv(csv_content, format_hint="auto")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error parsing CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing CSV: {str(e)}"
        )
    
    holdings = parsed_data["holdings"]
    excluded = parsed_data["excluded_items"]
    detected_format = parsed_data["detected_format"]
    
    # No price fetching needed - frontend will calculate market_value, gain_loss_pct, etc.
    # based on current stock prices
    
    if not holdings:
        raise HTTPException(
            status_code=400,
            detail="No valid holdings found after processing CSV"
        )
    
    # Calculate final response (only static totals)
    result = finalize_portfolio_response(holdings, excluded, detected_format)
    
    # Save portfolio to Supabase
    try:
        user_id = user.get('sub')
        if user_id:
            portfolio_save_service.save_portfolio(user_id, result)
            logger.info(f"✅ Saved portfolio for user {user_id}")
    except Exception as e:
        # Log error but don't fail the request - saving is secondary
        logger.error(f"Error saving portfolio for user {user.get('sub')}: {e}", exc_info=True)
    
    return JSONResponse(content=result)


@router.get("/portfolio", response_model=PortfolioResponse)
@user_limiter.limit(PORTFOLIO_USER_LIMIT)
@global_limiter.limit(PORTFOLIO_GLOBAL_LIMIT)
async def get_portfolio(
    request: Request,
    refresh: bool = Query(False, description="Force refresh prices from yfinance (bypasses 1-hour cache)"),
    user: Dict = Depends(verify_token)
):
    """
    Retrieve saved portfolio and calculate dynamic values based on current stock prices.
    
    Prices are cached for 1 hour. Use ?refresh=true to force fresh prices.
    
    Returns portfolio holdings with:
    - Static data: ticker, name, shares, cost_basis (from saved portfolio)
    - Dynamic data: market_value, gain_loss_pct, percent_of_portfolio, current_price, pe_ratio
      (calculated from cached or fresh stock prices)
    
    Query Parameters:
    - refresh: If true, bypass cache and fetch fresh prices from yfinance
    
    Raises:
        404: If user has no saved portfolio
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        # Retrieve saved portfolio
        saved_portfolio = portfolio_save_service.get_portfolio(user_id)
        
        if not saved_portfolio:
            raise HTTPException(
                status_code=404,
                detail="No saved portfolio found. Please upload a portfolio CSV first."
            )
        
        holdings = saved_portfolio['holdings']
        excluded_items = saved_portfolio['excluded_items']
        detected_format = saved_portfolio['detected_format']
        
        # Fetch current prices (uses cache unless stale or refresh=true)
        try:
            enriched_holdings = await calculate_portfolio_values(holdings, force_refresh=refresh)
        except Exception as e:
            logger.error(f"Error fetching current prices: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching current prices: {str(e)}"
            )
        
        # Calculate totals and percentages
        result = calculate_portfolio_totals_and_percentages(enriched_holdings)
        
        # Add metadata
        result['detected_format'] = detected_format
        result['excluded_items'] = excluded_items
        result['prices_cached'] = not refresh  # Indicates if prices came from cache
        result['cache_ttl_minutes'] = 60
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving portfolio: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving portfolio: {str(e)}"
        )


@router.get("/portfolio/holdings", response_model=HoldingResponse)
@user_limiter.limit(PORTFOLIO_USER_LIMIT)
@global_limiter.limit(PORTFOLIO_GLOBAL_LIMIT)
async def get_holding(
    request: Request,
    ticker: str = Query(..., description="Stock ticker symbol"),
    user: Dict = Depends(verify_token)
):
    """
    Get a single holding from the user's portfolio.
    
    Returns:
        Holding data with ticker, name, shares, cost_basis
    
    Raises:
        404: If holding not found
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        holding = portfolio_save_service.get_holding(user_id, ticker)
        
        if not holding:
            raise HTTPException(
                status_code=404,
                detail=f"Holding with ticker {ticker} not found"
            )
        
        return JSONResponse(content={
            **holding,
            "message": "Holding retrieved successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving holding {ticker}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving holding: {str(e)}"
        )


@router.post("/portfolio/holdings", response_model=HoldingResponse)
@user_limiter.limit(PORTFOLIO_USER_LIMIT)
@global_limiter.limit(PORTFOLIO_GLOBAL_LIMIT)
async def add_holding(
    request: Request,
    ticker: str = Query(..., description="Stock ticker symbol"),
    holding_request: Optional[HoldingCreateRequest] = None,
    user: Dict = Depends(verify_token)
):
    """
    Add a new holding to the user's portfolio.
    
    Creates portfolio if it doesn't exist.
    Shares and cost_basis can be 0 initially (user can edit later).
    
    Ticker is required as query parameter. Optional body can include:
    - name: Company name (will fetch from yfinance if not provided)
    - shares: Number of shares (defaults to 0)
    - cost_basis: Cost basis (defaults to 0)
    
    Raises:
        400: If holding already exists or validation fails
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        # Get values from body if provided, otherwise use defaults
        shares = (holding_request.shares if holding_request and holding_request.shares is not None else 0.0)
        cost_basis = (holding_request.cost_basis if holding_request and holding_request.cost_basis is not None else 0.0)
        name = (holding_request.name if holding_request else None)
        
        # Validate input
        if shares < 0:
            raise HTTPException(status_code=400, detail="Shares cannot be negative")
        if cost_basis < 0:
            raise HTTPException(status_code=400, detail="Cost basis cannot be negative")
        
        # Optionally fetch company name if not provided
        if not name:
            try:
                from services.yfinance_service import YFinanceService
                yf_service = YFinanceService()
                stock_info = yf_service.fetch_stock_info(ticker)
                if stock_info:
                    name = stock_info.get('company_name')
            except Exception as e:
                logger.warning(f"Could not fetch company name for {ticker}: {e}")
        
        # Prepare holding data
        holding_data = {
            'ticker': ticker.upper(),
            'name': name,
            'shares': shares,
            'cost_basis': cost_basis
        }
        
        # Add holding
        try:
            created_holding = portfolio_save_service.add_holding(user_id, holding_data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        return JSONResponse(content={
            **created_holding,
            "message": "Holding added successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding holding: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error adding holding: {str(e)}"
        )


@router.put("/portfolio/holdings", response_model=HoldingUpdateResponse)
@user_limiter.limit(PORTFOLIO_USER_LIMIT)
@global_limiter.limit(PORTFOLIO_GLOBAL_LIMIT)
async def update_holding(
    request: Request,
    ticker: str = Query(..., description="Stock ticker symbol"),
    holding_request: HoldingUpdateRequest = ...,
    user: Dict = Depends(verify_token)
):
    """
    Update an existing holding in the user's portfolio.
    
    Returns:
    - updated_holding: The updated holding with calculated values (market_value, gain_loss_pct, current_price, pe_ratio)
    - holdings: All holdings with recalculated percent_of_portfolio
    - Portfolio totals (total_market_value, total_cost_basis, total_gain_loss_pct)
    
    Uses cached prices (1-hour TTL) for calculations.
    
    Raises:
        404: If holding not found
        400: If validation fails
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        # Build updates dict
        updates = {}
        if holding_request.shares is not None:
            if holding_request.shares < 0:
                raise HTTPException(status_code=400, detail="Shares cannot be negative")
            updates['shares'] = holding_request.shares
        
        if holding_request.cost_basis is not None:
            if holding_request.cost_basis < 0:
                raise HTTPException(status_code=400, detail="Cost basis cannot be negative")
            updates['cost_basis'] = holding_request.cost_basis
        
        if holding_request.name is not None:
            updates['name'] = holding_request.name
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields provided to update")
        
        # Update holding in database
        try:
            portfolio_save_service.update_holding(user_id, ticker, updates)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        
        # Fetch ALL holdings for user to recalculate percentages
        saved_portfolio = portfolio_save_service.get_portfolio(user_id)
        if not saved_portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        holdings = saved_portfolio['holdings']
        
        # Calculate dynamic values using cached prices
        try:
            enriched_holdings = await calculate_portfolio_values(holdings, force_refresh=False)
        except Exception as e:
            logger.error(f"Error calculating portfolio values: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error calculating portfolio values: {str(e)}"
            )
        
        # Calculate totals and percentages for ALL holdings
        result = calculate_portfolio_totals_and_percentages(enriched_holdings)
        
        # Find the updated holding in the enriched list
        ticker_upper = ticker.upper()
        updated_holding = next(
            (h for h in result['holdings'] if h['ticker'].upper() == ticker_upper),
            None
        )
        
        if not updated_holding:
            raise HTTPException(status_code=404, detail=f"Holding {ticker} not found after update")
        
        return JSONResponse(content={
            "updated_holding": updated_holding,
            "holdings": result['holdings'],
            "total_market_value": result['total_market_value'],
            "total_cost_basis": result['total_cost_basis'],
            "total_gain_loss_pct": result['total_gain_loss_pct'],
            "message": "Holding updated successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating holding: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error updating holding: {str(e)}"
        )


@router.delete("/portfolio/holdings")
@user_limiter.limit(PORTFOLIO_USER_LIMIT)
@global_limiter.limit(PORTFOLIO_GLOBAL_LIMIT)
async def delete_holding(
    request: Request,
    ticker: str = Query(..., description="Stock ticker symbol"),
    user: Dict = Depends(verify_token)
):
    """
    Delete a holding from the user's portfolio.
    
    Returns:
        Success message
    
    Raises:
        404: If holding not found
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        # Delete holding
        deleted = portfolio_save_service.delete_holding(user_id, ticker)
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Holding with ticker {ticker} not found"
            )
        
        return JSONResponse(content={
            "message": f"Holding {ticker} deleted successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting holding: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting holding: {str(e)}"
        )

