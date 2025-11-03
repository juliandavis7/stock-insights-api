"""Middleware configuration for the Stock Insights API."""
import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from core.rate_limit import user_limiter, global_limiter, rate_limit_exceeded_handler


def setup_middleware(app: FastAPI):
    """Configure all middleware for the FastAPI application."""
    
    # Add rate limiters to app state (required by slowapi)
    app.state.limiter = user_limiter
    app.state.global_limiter = global_limiter
    
    # Add SlowAPI middleware for rate limiting
    app.add_middleware(SlowAPIMiddleware)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173", 
            "http://127.0.0.1:5173"  # React frontend local
        ],
        allow_origin_regex=r"https://stock-insights-.*\.vercel\.app",  # All Vercel preview deployments
        allow_credentials=True,
        allow_methods=["GET", "POST"],  # Only allow necessary methods
        allow_headers=["Content-Type", "Authorization"],  # Restrict headers
    )
    
    # Add custom rate limit exception handler
    @app.exception_handler(RateLimitExceeded)
    async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return await rate_limit_exceeded_handler(request, exc)
    
    # Add startup event
    @app.on_event("startup")
    async def startup_event():
        environment = os.getenv('ENVIRONMENT', 'production').lower()
        logging.info("🚀 Stock Insights API started with enhanced logging")
        logging.info("📊 Debug logs will be visible for current year growth calculations")
        if environment == 'dev':
            logging.warning("⚠️  Running in DEV mode")
        else:
            logging.info(f"🔒 Running in {environment.upper()} mode")

