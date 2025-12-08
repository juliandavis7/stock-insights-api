"""Common utilities for automatic scraping in API endpoints."""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
import asyncio

from services.scraper import scrape_stock_metrics, upsert_stock_data
from services.supabase_service import supabase_service

logger = logging.getLogger(__name__)


async def scrape_remaining_pages_background(ticker: str, pages: list):
    """
    Background task to scrape remaining pages after priority page is fetched.
    
    Args:
        ticker: Stock ticker symbol
        pages: List of page names to scrape (e.g., ['income_statement', 'projections'])
    """
    try:
        logger.info(f"Background task: Scraping remaining pages for {ticker}: {', '.join(pages)}")
        result, _ = await scrape_stock_metrics(ticker, pages=pages, use_cache=False)
        
        # Store scraped data in Supabase
        upsert_stock_data(
            ticker=ticker,
            search_metrics=result.get('search'),
            income_statement=result.get('income_statement'),
            projections=result.get('projections')
        )
        
        logger.info(f"Background task: Successfully scraped and cached remaining pages for {ticker}")
    except Exception as e:
        logger.error(f"Background task: Error scraping remaining pages for {ticker}: {e}", exc_info=True)


async def ensure_data_scraped(
    ticker: str,
    priority_page: str,
    data_key: str,
    remaining_pages: list
) -> Tuple[Optional[Dict], bool]:
    """
    Ensure data is scraped for a given ticker and priority page.
    Checks cache first, then scrapes if needed.
    
    Args:
        ticker: Stock ticker symbol (normalized to uppercase)
        priority_page: Page to scrape with priority (e.g., 'search', 'income_statement', 'projections')
        data_key: Key in stock_data dict (e.g., 'search_metrics', 'income_statement', 'projections')
        remaining_pages: List of pages to scrape in background (e.g., ['income_statement', 'projections'])
    
    Returns:
        Tuple of (data_dict, was_scraped)
        - data_dict: The requested data dictionary or None if not found
        - was_scraped: True if scraping was performed, False if data was cached
    """
    ticker = ticker.upper()
    
    stock_data = supabase_service.get_stock_data(ticker)
    
    # Check if we need to scrape
    should_scrape = False
    if not stock_data:
        logger.info(f"Cache miss for ticker {ticker} in {priority_page} endpoint - will scrape")
        should_scrape = True
    else:
        requested_data = stock_data.get(data_key)
        if not requested_data:
            # Check if ticker was recently updated (might be scraping in background)
            if stock_data.get('updated_at'):
                try:
                    updated_at = datetime.fromisoformat(stock_data['updated_at'].replace('Z', '+00:00'))
                    age_seconds = (datetime.now(updated_at.tzinfo) - updated_at).total_seconds()
                    
                    # If updated within last 60 seconds, poll briefly before scraping
                    if age_seconds < 60:
                        logger.info(f"Ticker {ticker} recently updated ({age_seconds:.0f}s ago), polling for {data_key}...")
                        
                        # Poll every 2 seconds, up to 20 seconds
                        for attempt in range(10):
                            await asyncio.sleep(2)
                            stock_data = supabase_service.get_stock_data(ticker)
                            if stock_data and stock_data.get(data_key):
                                logger.info(f"✓ Found {data_key} after {attempt * 2}s")
                                requested_data = stock_data.get(data_key)
                                return (dict(requested_data) if isinstance(requested_data, dict) else {}, False)
                        
                        logger.info(f"Polling timeout for {ticker}, scraping synchronously")
                except Exception as e:
                    logger.warning(f"Error checking updated_at timestamp: {e}")
            
            logger.info(f"No {data_key} data found for ticker {ticker} - will scrape")
            should_scrape = True
        else:
            # Data exists, return it
            return (dict(requested_data) if isinstance(requested_data, dict) else {}, False)
    
    # Scrape if needed
    if should_scrape:
        logger.info(f"Scraping {priority_page} page for ticker {ticker}...")
        result, _ = await scrape_stock_metrics(
            ticker=ticker,
            pages=[priority_page],
            use_cache=False
        )
        
        # Extract priority data
        priority_data = None
        if priority_page == 'search':
            priority_data = result.get('search')
            upsert_stock_data(ticker=ticker, search_metrics=priority_data)
        elif priority_page == 'income_statement':
            priority_data = result.get('income_statement')
            upsert_stock_data(ticker=ticker, income_statement=priority_data)
        elif priority_page == 'projections':
            priority_data = result.get('projections')
            upsert_stock_data(ticker=ticker, projections=priority_data)
        
        logger.info(f"Successfully scraped and cached {priority_page} data for {ticker}")
        
        # Return scraped data
        if priority_data:
            return (dict(priority_data) if isinstance(priority_data, dict) else {}, True)
        else:
            logger.error(f"Scraping completed but no {data_key} data returned for {ticker}")
            return ({}, True)
    
    # Should not reach here, but return empty dict if somehow we do
    logger.warning(f"Unexpected code path in ensure_data_scraped for {ticker}")
    return ({}, False)

