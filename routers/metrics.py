"""Metrics endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from models import MetricsResponse
from services.utils import get_metrics
from core.auth import verify_access
from services.validators import validate_ticker_or_raise
from services.supabase_service import supabase_service
from core.rate_limit import user_limiter, global_limiter, METRICS_USER_LIMIT, METRICS_GLOBAL_LIMIT
from core.deprecation import add_deprecation_headers

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/metrics", response_model=MetricsResponse)
@user_limiter.limit(METRICS_USER_LIMIT)
@global_limiter.limit(METRICS_GLOBAL_LIMIT)
def metrics(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_access)):
    """
    Get stock metrics from cached Supabase data.
    
    Args:
        ticker: Stock ticker symbol (e.g., META)
        
    Returns:
        MetricsResponse with data from search_metrics column
        
    Raises:
        404: If ticker not found in cache (cache miss)
        500: If Supabase connection error
    """
    try:
        stock_data = supabase_service.get_stock_data(ticker)
        
        if not stock_data:
            logger.info(f"Cache miss for ticker {ticker} in /metrics")
            raise HTTPException(status_code=404, detail=f"Metrics data not found for ticker {ticker}. Cache miss - data not yet scraped.")
        
        search_metrics = stock_data.get('search_metrics')
        
        if not search_metrics:
            logger.warning(f"No search_metrics data found for ticker {ticker}")
            raise HTTPException(status_code=404, detail=f"Metrics data not available for ticker {ticker}")
        
        # Map search_metrics to MetricsResponse format
        metrics_dict = dict(search_metrics) if isinstance(search_metrics, dict) else {}
        
        # Remove ticker if present (not needed in response)
        metrics_dict.pop('ticker', None)
        
        return JSONResponse(content=metrics_dict)
        
    except HTTPException:
        raise
    except Exception as e:
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

