"""Metrics endpoint router."""
import logging
from typing import Dict
from collections import OrderedDict
from fastapi import APIRouter, Query, Depends, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from models import MetricsResponse
from services.utils import get_metrics
from core.auth import verify_access
from services.validators import validate_ticker_or_raise
from services.supabase_service import supabase_service
from services.scraping_utils import ensure_data_scraped, scrape_remaining_pages_background
from core.rate_limit import user_limiter, global_limiter, METRICS_USER_LIMIT, METRICS_GLOBAL_LIMIT
from core.deprecation import add_deprecation_headers

# Define the order of metrics to match UI display
METRICS_ORDER = [
    # Mandatory Metrics - PE Ratios
    "ttm_pe",
    "forward_pe",
    "two_year_forward_pe",
    # Mandatory Metrics - EPS Growth
    "ttm_eps_growth",
    "current_year_eps_growth",
    "next_year_eps_growth",
    # Mandatory Metrics - Revenue Growth
    "ttm_revenue_growth",
    "current_year_revenue_growth",
    "next_year_revenue_growth",
    # Mandatory Metrics - Margins
    "gross_margin",
    "net_margin",
    # Mandatory Metrics - P/S Ratios
    "ttm_ps_ratio",
    "forward_ps_ratio",
    # Advanced Metrics - EPS Growth
    "last_year_eps_growth",
    "ttm_vs_ntm_eps_growth",
    "current_quarter_eps_growth_vs_previous_year",
    "two_year_stack_exp_eps_growth",
    # Advanced Metrics - Revenue Growth
    "last_year_revenue_growth",
    "ttm_vs_ntm_revenue_growth",
    "current_quarter_revenue_growth_vs_previous_year",
    "two_year_stack_exp_revenue_growth",
    # Advanced Metrics - Valuation Ratios
    "peg_ratio",
    "return_on_equity",
    "price_to_book",
    "price_to_free_cash_flow",
    "free_cash_flow_yield",
    # Advanced Metrics - Dividends
    "dividend_yield",
    "dividend_payout_ratio",
]


def order_metrics(metrics_dict: Dict) -> OrderedDict:
    """
    Order metrics dictionary according to METRICS_ORDER.
    
    Args:
        metrics_dict: Dictionary of metrics (may be unordered)
        
    Returns:
        OrderedDict with metrics in the specified order
    """
    ordered_metrics = OrderedDict()
    
    # Add metrics in the specified order
    for metric_key in METRICS_ORDER:
        if metric_key in metrics_dict:
            ordered_metrics[metric_key] = metrics_dict[metric_key]
    
    # Add any remaining metrics that weren't in the order list (shouldn't happen, but for safety)
    for key, value in metrics_dict.items():
        if key not in ordered_metrics and key != 'ticker':
            ordered_metrics[key] = value
    
    return ordered_metrics


logger = logging.getLogger(__name__)
router = APIRouter()




@router.get("/metrics", response_model=MetricsResponse)
@user_limiter.limit(METRICS_USER_LIMIT)
@global_limiter.limit(METRICS_GLOBAL_LIMIT)
async def metrics(
    request: Request,
    ticker: str = Query(..., description="Stock ticker symbol"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: Dict = Depends(verify_access)
):
    """
    Get stock metrics from cached Supabase data.
    If data is not found, automatically scrapes with priority='search' and returns the data.
    
    Args:
        ticker: Stock ticker symbol (e.g., META)
        
    Returns:
        MetricsResponse with data from metrics column
        
    Raises:
        500: If scraping or Supabase connection error
    """
    try:
        # Normalize ticker format
        ticker = ticker.upper()
        
        # Ensure data is scraped using common utility
        metrics_dict, was_scraped = await ensure_data_scraped(
            ticker=ticker,
            priority_page='search',
            data_key='metrics',  # Changed from 'search_metrics' to 'metrics' in consolidated table
            remaining_pages=['income_statement', 'projections']
        )
        
        # Queue remaining pages as background task if we just scraped
        if was_scraped:
            remaining_pages = ['income_statement', 'projections']
            logger.info(f"Queueing background task to scrape remaining pages for {ticker}: {', '.join(remaining_pages)}")
            background_tasks.add_task(scrape_remaining_pages_background, ticker, remaining_pages)
        
        # Remove ticker if present (not needed in response)
        metrics_dict.pop('ticker', None)
        
        # Order metrics according to UI display order
        ordered_metrics = order_metrics(metrics_dict)
        
        return JSONResponse(content=ordered_metrics)
        
    except HTTPException:
        raise
    except ValueError as e:
        # Handle validation errors from scraper (e.g., invalid ticker)
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['not found', 'invalid', 'could not extract', 'not available']):
            logger.error(f"Ticker {ticker} validation error: {e}")
            validate_ticker_or_raise(ticker)
        raise HTTPException(status_code=400, detail=f"Error fetching metrics data: {str(e)}")
    except Exception as e:
        # Check if it's a ticker not found error
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['not found', 'invalid symbol', 'unknown symbol', 'invalid ticker', 'could not extract']):
            logger.error(f"Ticker {ticker} not found: {e}")
            validate_ticker_or_raise(ticker)
        
        logger.error(f"Error in /metrics endpoint for {ticker}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error fetching metrics data: {str(e)}")


@router.get("/v1/metrics", response_model=MetricsResponse, deprecated=True)
@user_limiter.limit(METRICS_USER_LIMIT)
@global_limiter.limit(METRICS_GLOBAL_LIMIT)
def metrics_v1(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_access)):
    """
    [DEPRECATED] Get stock metrics using FMP service.
    
    This endpoint is deprecated. Use /metrics instead, which uses cached Supabase data.
    
    Args:
        ticker: Stock ticker symbol (e.g., META)
        
    Returns:
        MetricsResponse with calculated metrics from FMP
    """
    try:
        data = get_metrics(ticker)
        # Remove ticker field (not needed in response, already in query param)
        data.pop('ticker', None)
        response = JSONResponse(content=data)
        return add_deprecation_headers(response, "/metrics")
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
        
        logging.error(f"❌ API: Error in metrics endpoint for {ticker}: {e}")
        import traceback
        logging.error(f"❌ API: Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error calculating metrics: {str(e)}")

