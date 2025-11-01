"""Info endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from core.auth import verify_access
from services.validators import validate_ticker_or_raise
from services.yfinance_service import YFinanceService
from services.fmp_service import FMPService
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
        fmp_service = FMPService()
        
        # Get current price
        current_price = yfinance_service.get_current_price(ticker.upper())
        if current_price is None:
            logger.error(f"❌ API: Unable to fetch price data for ticker {ticker}")
            validate_ticker_or_raise(ticker)
        
        # Get market cap
        market_cap = yfinance_service.get_market_cap(ticker.upper())
        
        # Get shares outstanding from FMP quarterly income statement (use diluted shares)
        shares_outstanding = None
        try:
            quarterly_data = fmp_service.fetch_quarterly_income_statement(ticker.upper())
            if quarterly_data and len(quarterly_data) > 0:
                shares_outstanding = quarterly_data[0].get('weightedAverageShsOutDil')
                # Fallback to basic shares if diluted not available
                if not shares_outstanding:
                    shares_outstanding = quarterly_data[0].get('weightedAverageShsOut')
                
                if shares_outstanding:
                    logger.info(f"Using diluted shares from FMP for {ticker}: {shares_outstanding:,.0f}")
        except ValueError as ve:
            # ValueError from FMPService for missing ticker in mocks
            logger.error(f"❌ API: Ticker {ticker} not found: {ve}")
            validate_ticker_or_raise(ticker)
        except Exception as e:
            logger.error(f"Error fetching shares from FMP for {ticker}: {e}")
        
        # Fallback to yfinance if FMP data not available
        if not shares_outstanding:
            shares_outstanding = yfinance_service.get_shares_outstanding(ticker.upper())
            if shares_outstanding:
                logger.warning(f"Using yfinance shares for {ticker} (FMP data unavailable): {shares_outstanding:,.0f}")
        
        return JSONResponse(content={
            "ticker": ticker.upper(),
            "price": current_price,
            "market_cap": int(market_cap) if market_cap else None,
            "shares_outstanding": int(shares_outstanding) if shares_outstanding else None
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

