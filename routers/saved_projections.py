"""Saved projections endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Query, Depends, HTTPException
from fastapi.responses import JSONResponse

from models.requests import SavedProjectionRequest
from models.responses import (
    SavedProjectionGetResponse,
    SavedProjectionPostResponse,
    SavedProjectionDeleteResponse
)
from core.auth import verify_token
from services.projections_save_service import projections_save_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/saved-projections", response_model=SavedProjectionPostResponse)
def save_projections(
    ticker: str = Query(..., description="Stock ticker symbol"),
    request: SavedProjectionRequest = ...,
    user: Dict = Depends(verify_token)
):
    """
    Save user projection inputs for a ticker with scenarios.
    Upserts (insert or update) based on user_id + ticker.
    
    Request body format:
    {
        "bear_case": {
            "revenue_growth": [10.0, 10.0, 10.0, 10.0],
            "net_income_growth": [6.5, 32.1, 0.0, 0.0],
            "pe_low_est": [0.0, 0.0, 0.0, 0.0, 0.0],
            "pe_high_est": [0.0, 0.0, 0.0, 0.0, 0.0]
        },
        "base_case": {...},
        "bull_case": {...}
    }
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        request: SavedProjectionRequest with scenarios (bear_case, base_case, bull_case)
        
    Returns:
        SavedProjectionPostResponse with success message
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        # Convert Pydantic models to dict
        projection_data = {
            'bear_case': {
                'revenue_growth': request.bear_case.revenue_growth,
                'net_income_growth': request.bear_case.net_income_growth,
                'pe_low_est': request.bear_case.pe_low_est,
                'pe_high_est': request.bear_case.pe_high_est
            },
            'base_case': {
                'revenue_growth': request.base_case.revenue_growth,
                'net_income_growth': request.base_case.net_income_growth,
                'pe_low_est': request.base_case.pe_low_est,
                'pe_high_est': request.base_case.pe_high_est
            },
            'bull_case': {
                'revenue_growth': request.bull_case.revenue_growth,
                'net_income_growth': request.bull_case.net_income_growth,
                'pe_low_est': request.bull_case.pe_low_est,
                'pe_high_est': request.bull_case.pe_high_est
            }
        }
        
        projections_save_service.save_projection(user_id, ticker.upper(), projection_data)
        
        return JSONResponse(content={"message": "Projections saved successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving projections for ticker {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving projections: {str(e)}")


@router.put("/saved-projections", response_model=SavedProjectionPostResponse)
def update_projections(
    ticker: str = Query(..., description="Stock ticker symbol"),
    request: SavedProjectionRequest = ...,
    user: Dict = Depends(verify_token)
):
    """
    Update user projection inputs for a ticker with scenarios.
    Updates existing projections based on user_id + ticker.
    
    Request body format:
    {
        "bear_case": {
            "revenue_growth": [10.0, 10.0, 10.0, 10.0],
            "net_income_growth": [6.5, 32.1, 0.0, 0.0],
            "pe_low_est": [0.0, 0.0, 0.0, 0.0, 0.0],
            "pe_high_est": [0.0, 0.0, 0.0, 0.0, 0.0]
        },
        "base_case": {...},
        "bull_case": {...}
    }
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        request: SavedProjectionRequest with scenarios (bear_case, base_case, bull_case)
        
    Returns:
        SavedProjectionPostResponse with success message
        
    Raises:
        404: If projections not found for the ticker
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        # Check if projections exist first
        existing = projections_save_service.get_projection(user_id, ticker.upper())
        if not existing:
            raise HTTPException(status_code=404, detail=f"No saved projections found for ticker {ticker}")
        
        # Convert Pydantic models to dict
        projection_data = {
            'bear_case': {
                'revenue_growth': request.bear_case.revenue_growth,
                'net_income_growth': request.bear_case.net_income_growth,
                'pe_low_est': request.bear_case.pe_low_est,
                'pe_high_est': request.bear_case.pe_high_est
            },
            'base_case': {
                'revenue_growth': request.base_case.revenue_growth,
                'net_income_growth': request.base_case.net_income_growth,
                'pe_low_est': request.base_case.pe_low_est,
                'pe_high_est': request.base_case.pe_high_est
            },
            'bull_case': {
                'revenue_growth': request.bull_case.revenue_growth,
                'net_income_growth': request.bull_case.net_income_growth,
                'pe_low_est': request.bull_case.pe_low_est,
                'pe_high_est': request.bull_case.pe_high_est
            }
        }
        
        projections_save_service.save_projection(user_id, ticker.upper(), projection_data)
        
        return JSONResponse(content={"message": "Projections updated successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating projections for ticker {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating projections: {str(e)}")


@router.get("/saved-projections", response_model=SavedProjectionGetResponse)
def get_saved_projections(
    ticker: str = Query(..., description="Stock ticker symbol"),
    user: Dict = Depends(verify_token)
):
    """
    Retrieve saved projection inputs for a ticker.
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        
    Returns:
        SavedProjectionGetResponse with data or null if not found
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        result = projections_save_service.get_projection(user_id, ticker.upper())
        
        if result:
            return JSONResponse(content={
                "data": result['data'],
                "updated_at": result['updated_at']
            })
        
        return JSONResponse(content={"data": None})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving saved projections for ticker {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving projections: {str(e)}")


@router.delete("/saved-projections", response_model=SavedProjectionDeleteResponse)
def delete_saved_projections(
    ticker: str = Query(..., description="Stock ticker symbol"),
    user: Dict = Depends(verify_token)
):
    """
    Delete saved projection inputs for a ticker.
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        
    Returns:
        SavedProjectionDeleteResponse with success or not found message
    """
    try:
        user_id = user.get('sub')
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")
        
        deleted = projections_save_service.delete_projection(user_id, ticker.upper())
        
        if deleted:
            return JSONResponse(content={"message": "Projections deleted successfully"})
        
        return JSONResponse(content={"message": "No saved projections found"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting saved projections for ticker {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting projections: {str(e)}")

