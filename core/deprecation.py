"""Deprecation utilities for API endpoints."""
from fastapi.responses import JSONResponse
from typing import Any, Dict


def add_deprecation_headers(response: JSONResponse, replacement_endpoint: str) -> JSONResponse:
    """
    Add deprecation headers to a response.
    
    Args:
        response: The JSONResponse to add headers to
        replacement_endpoint: The new endpoint path to use instead (e.g., "/metrics")
    
    Returns:
        JSONResponse with deprecation headers added
    """
    response.headers["Deprecation"] = "true"
    response.headers["Warning"] = f'299 - "This endpoint is deprecated. Use {replacement_endpoint} instead."'
    return response

