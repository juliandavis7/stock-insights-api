"""Services package for API interactions and business logic orchestration."""

# Lazy imports to avoid importing FastAPI and other heavy dependencies
# when only scraper.py is needed (e.g., in job context)
def __getattr__(name):
    """Lazy import for services to avoid eager FastAPI dependency."""
    if name == "FMPService":
        from .fmp_service import FMPService
        return FMPService
    elif name == "YFinanceService":
        from .yfinance_service import YFinanceService
        return YFinanceService
    elif name == "MetricsService":
        from .metrics_service import MetricsService
        return MetricsService
    elif name == "ProjectionService":
        from .projection_service import ProjectionService
        return ProjectionService
    elif name == "SupabaseService":
        from .supabase_service import SupabaseService
        return SupabaseService
    elif name == "StripeService":
        from .stripe_service import StripeService
        return StripeService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "FMPService",
    "YFinanceService", 
    "MetricsService",
    "ProjectionService",
    "SupabaseService",
    "StripeService"
]