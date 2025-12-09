"""Main application factory for Stock Insights API."""
from fastapi import FastAPI

from core.config import setup_logging
from core.middleware import setup_middleware
from routers import health, metrics, projections, financials, info, charts, users, webhooks, payments, stocks, saved_projections


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Setup logging
    setup_logging()
    
    # Initialize FastAPI app
    app = FastAPI(
        title="Stock Insights API",
        description="API for stock market insights and projections",
        version="1.0.0"
    )
    
    # Setup middleware (CORS, rate limiting, etc.)
    setup_middleware(app)
    
    # Register routers
    app.include_router(health.router, tags=["health"])
    app.include_router(metrics.router, tags=["metrics"])
    app.include_router(projections.router, tags=["projections"])
    app.include_router(financials.router, tags=["financials"])
    app.include_router(info.router, tags=["info"])
    app.include_router(charts.router, tags=["charts"])
    app.include_router(users.router, tags=["users"])
    app.include_router(webhooks.router, tags=["webhooks"])
    app.include_router(payments.router, tags=["payments"])
    app.include_router(stocks.router, tags=["stocks"])
    app.include_router(saved_projections.router, tags=["saved-projections"])
    
    return app


# Create the app instance
app = create_app()

