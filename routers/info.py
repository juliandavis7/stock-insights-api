"""Info endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from core.auth import verify_access
from services.validators import validate_ticker_or_raise
from services.yfinance_service import YFinanceService
from core.rate_limit import user_limiter, global_limiter, INFO_USER_LIMIT, INFO_GLOBAL_LIMIT

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/info")
@user_limiter.limit(INFO_USER_LIMIT)
@global_limiter.limit(INFO_GLOBAL_LIMIT)
def get_info(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_access)):
    """
    Get basic stock information including price, market cap, and shares outstanding.
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        
    Returns:
        JSON with ticker, price, market_cap, and shares_outstanding
    """
    try:
        yfinance_service = YFinanceService()
        
        # Get current price
        current_price = yfinance_service.get_current_price(ticker.upper())
        if current_price is None:
            logger.error(f"❌ API: Unable to fetch price data for ticker {ticker}")
            validate_ticker_or_raise(ticker)
        
        # Get market cap
        market_cap = yfinance_service.get_market_cap(ticker.upper())
        
        # Get shares outstanding from yfinance
        shares_outstanding = yfinance_service.get_shares_outstanding(ticker.upper())
        if shares_outstanding:
            logger.info(f"Using shares from yfinance for {ticker}: {shares_outstanding:,.0f}")
        
        return JSONResponse(content={
            "ticker": ticker.upper(),
            "price": current_price,
            "market_cap": int(market_cap) if market_cap else None,
            "shares_outstanding": int(shares_outstanding) if shares_outstanding else None
        })
    
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a ticker not found error
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['not found', 'invalid symbol', 'unknown symbol', 'invalid ticker']):
            logger.error(f"❌ API: Ticker {ticker} not found: {e}")
            validate_ticker_or_raise(ticker)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Internal server error: {str(e)}",
                "ticker": ticker.upper()
            }
        )

