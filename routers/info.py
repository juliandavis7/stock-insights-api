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
        current_price = None
        market_cap = None
        shares_outstanding = None
        
        # Try yfinance first
        current_price = yfinance_service.get_current_price(ticker.upper())
        market_cap = yfinance_service.get_market_cap(ticker.upper())
        shares_outstanding = yfinance_service.get_shares_outstanding(ticker.upper())
        if shares_outstanding:
            logger.info(f"Using shares from yfinance for {ticker}: {shares_outstanding:,.0f}")
        
        # If yfinance failed to get price or market cap, try FMP as fallback
        if current_price is None or market_cap is None or shares_outstanding is None:
            logger.info(f"⚠️ yfinance data incomplete for {ticker}, trying FMP fallback...")
            try:
                fmp_service = FMPService()
                profile = fmp_service.fetch_company_profile(ticker.upper())
                
                if profile:
                    # FMP profile returns: price, marketCap (camelCase), sharesOutstanding
                    if current_price is None:
                        current_price = profile.get('price')
                        if current_price:
                            logger.info(f"✓ Got price from FMP for {ticker}: {current_price}")
                    
                    if market_cap is None:
                        # FMP API returns 'marketCap' (camelCase), not 'mktCap'
                        market_cap = profile.get('marketCap') or profile.get('mktCap')
                        if market_cap:
                            logger.info(f"✓ Got market cap from FMP for {ticker}: {market_cap}")
                    
                    # FMP profile may have shares outstanding
                    if shares_outstanding is None:
                        shares_outstanding = profile.get('sharesOutstanding')
                        if shares_outstanding:
                            logger.info(f"✓ Got shares outstanding from FMP for {ticker}: {shares_outstanding}")
                        else:
                            # Calculate shares outstanding from market cap and price if not available
                            if market_cap and current_price:
                                try:
                                    calculated_shares = market_cap / current_price
                                    shares_outstanding = calculated_shares
                                    logger.info(f"✓ Calculated shares outstanding for {ticker}: {calculated_shares:,.0f} (Market Cap / Price = {market_cap:,.0f} / {current_price:.2f})")
                                except (TypeError, ZeroDivisionError) as e:
                                    logger.warning(f"Could not calculate shares outstanding for {ticker}: {e}")
            except Exception as e:
                logger.warning(f"FMP fallback failed for {ticker}: {e}")
        
        # If price is still None but we have other data, try to get price from yfinance stock info
        if current_price is None:
            logger.warning(f"⚠️ API: Price not available for {ticker}, trying yfinance stock_info")
            stock_info = yfinance_service.fetch_stock_info(ticker.upper())
            if stock_info and stock_info.get('current_price'):
                current_price = stock_info.get('current_price')
                logger.info(f"✓ Got price from stock_info for {ticker}: {current_price}")
        
        # Calculate shares outstanding from market cap and price if we still don't have it
        if shares_outstanding is None and market_cap and current_price:
            try:
                calculated_shares = market_cap / current_price
                shares_outstanding = calculated_shares
                logger.info(f"✓ Calculated shares outstanding for {ticker}: {calculated_shares:,.0f} (Market Cap / Price = {market_cap:,.0f} / {current_price:.2f})")
            except (TypeError, ZeroDivisionError) as e:
                logger.warning(f"Could not calculate shares outstanding for {ticker}: {e}")
        
        # Only fail if we can't get ANY data (all are None)
        if current_price is None and market_cap is None and shares_outstanding is None:
            logger.error(f"❌ API: Unable to fetch any data for ticker {ticker}")
            validate_ticker_or_raise(ticker)
        
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

