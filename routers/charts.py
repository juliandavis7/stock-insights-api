"""Charts endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from core.auth import verify_token
from services.validators import validate_ticker_or_raise
from services.utils import fetch_enhanced_chart_data
from core.rate_limit import user_limiter, global_limiter, CHARTS_USER_LIMIT, CHARTS_GLOBAL_LIMIT

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/charts")
@user_limiter.limit(CHARTS_USER_LIMIT)
@global_limiter.limit(CHARTS_GLOBAL_LIMIT)
def get_chart_revenue(
    request: Request,
    ticker: str = Query(..., description="Stock ticker symbol"),
    mode: str = Query("quarterly", description="Mode: 'quarterly' for quarterly data or 'ttm' for trailing twelve months"),
    user: Dict = Depends(verify_token)
):
    """
    Get quarterly revenue and EPS chart data for a ticker, including current price and market cap.
    Returns chart data with quarterly data plus current stock info.
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        mode: Data mode - "quarterly" for quarterly data or "ttm" for trailing twelve months data
        
    Returns:
        Chart data with ticker, quarters, revenue, eps, price, and market_cap
    """
    try:
        chart_data = fetch_enhanced_chart_data(ticker.upper(), mode=mode)
        
        if chart_data is None:
            logger.error(f"❌ API: Unable to fetch chart data for ticker {ticker}")
            validate_ticker_or_raise(ticker)
        
        # Stock info removed - use /info endpoint instead
        
        # Return the chart data without redundant stock info
        return JSONResponse(content={
            'ticker': chart_data['ticker'],
            'quarters': chart_data['quarters'],
            'revenue': chart_data['revenue'],
            'eps': chart_data['eps'],
            'gross_margin': chart_data['gross_margin'],
            'net_margin': chart_data['net_margin'],
            'operating_income': chart_data['operating_income'],
            'operating_cash_flow': chart_data['operating_cash_flow'],
            'free_cash_flow': chart_data['free_cash_flow']
            # Stock info fields removed - use /info endpoint instead
        })
    
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

