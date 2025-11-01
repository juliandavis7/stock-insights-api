"""Metrics endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from models import MetricsResponse
from services.utils import get_metrics
from core.auth import verify_token
from services.validators import validate_ticker_or_raise
from core.rate_limit import user_limiter, global_limiter, METRICS_USER_LIMIT, METRICS_GLOBAL_LIMIT

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/metrics", response_model=MetricsResponse)
@user_limiter.limit(METRICS_USER_LIMIT)
@global_limiter.limit(METRICS_GLOBAL_LIMIT)
def metrics(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_token)):
    try:
        data = get_metrics(ticker)
        return JSONResponse(content=data)
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

