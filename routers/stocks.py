"""Stocks endpoint router for on-demand scraping."""
import logging
from typing import Dict
from datetime import datetime
from fastapi import APIRouter, Path, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from core.auth import verify_access
from services.validators import validate_ticker_or_raise
from services.scraper import (
    scrape_stock,
    get_cached_data,
    get_last_earnings_date,
    upsert_stock_data
)

logger = logging.getLogger(__name__)
router = APIRouter()


def is_cache_stale(cached_data: Dict, ticker: str) -> bool:
    """
    Check if cached data is stale based on earnings date.
    
    Args:
        cached_data: Cached stock data from Supabase
        ticker: Stock ticker symbol
        
    Returns:
        True if cache is stale, False otherwise
    """
    if not cached_data:
        return True
    
    # Get last earnings date
    last_earnings_date = get_last_earnings_date(ticker)
    
    # Parse cached updated_at timestamp
    cached_updated_at = None
    if cached_data.get('updated_at'):
        try:
            cached_updated_at = datetime.fromisoformat(cached_data['updated_at'].replace('Z', '+00:00'))
        except:
            try:
                cached_updated_at = datetime.fromisoformat(cached_data['updated_at'])
            except:
                logger.warning(f"Could not parse cached updated_at for {ticker}")
                return True  # If we can't parse, assume stale
    
    if not cached_updated_at:
        return True  # No timestamp, assume stale
    
    # Check if cache is stale based on earnings date
    if last_earnings_date and cached_updated_at:
        # Normalize timezones for comparison
        earnings_date_naive = (
            last_earnings_date.replace(tzinfo=None) 
            if last_earnings_date.tzinfo 
            else last_earnings_date
        )
        cached_date_naive = (
            cached_updated_at.replace(tzinfo=None) 
            if cached_updated_at.tzinfo 
            else cached_updated_at
        )
        
        if cached_date_naive < earnings_date_naive:
            return True  # Cache is stale
    elif cached_updated_at:
        # If we can't get earnings date, assume cache is valid if it's less than 90 days old
        cached_date_naive = (
            cached_updated_at.replace(tzinfo=None) 
            if cached_updated_at.tzinfo 
            else cached_updated_at
        )
        days_old = (datetime.now() - cached_date_naive).days
        if days_old > 90:
            return True  # Cache is old
    
    return False  # Cache is fresh


@router.get("/stock/{ticker}")
async def get_stock_data(
    request: Request,
    ticker: str = Path(..., description="Stock ticker symbol"),
    user: Dict = Depends(verify_access)
):
    """
    Get stock data for a ticker, scraping if cache is missing or stale.
    
    This endpoint:
    1. Checks Supabase cache
    2. If missing or stale → calls scrape_stock(ticker) → stores in Supabase
    3. Returns data to user
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        
    Returns:
        JSON with stock data including search metrics, income statement, and projections
    """
    try:
        # Validate ticker format
        ticker = ticker.upper()
        validate_ticker_or_raise(ticker)
        
        # Check cache
        logger.info(f"Checking cache for ticker: {ticker}")
        cached_data = get_cached_data(ticker)
        
        # Determine if we need to scrape
        should_scrape = False
        if not cached_data:
            logger.info(f"No cached data found for {ticker}, will scrape")
            should_scrape = True
        elif is_cache_stale(cached_data, ticker):
            logger.info(f"Cache is stale for {ticker}, will scrape")
            should_scrape = True
        else:
            logger.info(f"Using cached data for {ticker}")
        
        # Scrape if needed
        if should_scrape:
            try:
                logger.info(f"Scraping data for {ticker}...")
                result = await scrape_stock(ticker)
                
                # Store in Supabase (search_metrics parameter stores as 'metrics' in DB)
                upsert_stock_data(
                    ticker=ticker,
                    search_metrics=result.get('search'),  # stored as 'metrics' in consolidated stocks table
                    income_statement=result.get('income_statement'),
                    projections=result.get('projections')
                )
                
                logger.info(f"Successfully scraped and cached data for {ticker}")
            except Exception as e:
                logger.error(f"Error scraping {ticker}: {e}")
                # If scraping fails but we have cached data, return cached data
                if cached_data:
                    logger.warning(f"Returning stale cached data for {ticker} due to scraping error")
                    return JSONResponse(content={
                        "ticker": ticker,
                        "search": cached_data.get('metrics'),  # 'metrics' in consolidated table
                        "income_statement": cached_data.get('income_statement'),
                        "projections": cached_data.get('projections'),
                        "_from_cache": True,
                        "_scraping_error": str(e)
                    })
                else:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "error": f"Failed to scrape data for {ticker}: {str(e)}",
                            "ticker": ticker
                        }
                    )
        else:
            # Use cached data ('metrics' in consolidated table)
            result = {
                "search": cached_data.get('metrics'),  # 'metrics' in consolidated table
                "income_statement": cached_data.get('income_statement'),
                "projections": cached_data.get('projections')
            }
        
        # Return result
        return JSONResponse(content={
            "ticker": ticker,
            "search": result.get('search'),
            "income_statement": result.get('income_statement'),
            "projections": result.get('projections'),
            "_from_cache": not should_scrape
        })
    
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a ticker not found error
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['not found', 'invalid symbol', 'unknown symbol', 'invalid ticker']):
            logger.error(f"Ticker {ticker} not found: {e}")
            validate_ticker_or_raise(ticker)
        
        logger.error(f"Error fetching stock data for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Internal server error: {str(e)}",
                "ticker": ticker
            }
        )

