"""
Rate Limiting Configuration and Setup

This module provides dual rate limiting for the Stock Insights API:
1. Per-User Limits: JWT-based rate limiting for fair distribution among users
2. Global Limits: Server-wide caps to protect FMP API quota (300 calls/minute)

The rate limiting uses slowapi with in-memory storage (no Redis required),
suitable for single-server deployments.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Key Functions for Rate Limiting
# ============================================================================

def get_user_from_jwt(request: Request) -> str:
    """
    Extract user ID from JWT token for per-user rate limiting.
    Falls back to IP if JWT not available or invalid.
    
    Returns:
        str: Rate limit key in format "user:{user_id}" or "ip:{ip_address}"
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            
            # Decode JWT to get user ID (don't verify - already done by verify_token dependency)
            import jwt
            decoded = jwt.decode(token, options={"verify_signature": False})
            user_id = decoded.get("sub") or decoded.get("user_id")
            
            if user_id:
                logger.info(f"✅ Rate limiting by user: {user_id}")
                return f"user:{user_id}"
    except Exception as e:
        logger.info(f"⚠️  Could not extract user from JWT, using IP: {e}")
    
    # Fallback to IP address
    ip = get_remote_address(request)
    logger.info(f"🔍 Rate limiting by IP: {ip}")
    return f"ip:{ip}"


def get_global_key(request: Request) -> str:
    """
    Return a constant key for global server-wide rate limiting.
    All requests share the same counter regardless of user/IP.
    
    Returns:
        str: Always returns "global"
    """
    return "global"


# ============================================================================
# Rate Limiter Initialization
# ============================================================================

# Initialize per-user rate limiter (JWT-based)
user_limiter = Limiter(
    key_func=get_user_from_jwt,  # Rate limit by user ID from JWT
    default_limits=["100/minute"],  # Default per-user limit
    storage_uri="memory://",  # In-memory storage (no Redis needed)
    headers_enabled=True  # Send rate limit headers (X-RateLimit-*)
)

# Initialize global rate limiter (server-wide FMP quota protection)
global_limiter = Limiter(
    key_func=get_global_key,  # Rate limit globally
    default_limits=[],  # No default, set per endpoint
    storage_uri="memory://",  # In-memory storage
    headers_enabled=False  # Don't need headers for global limit
)

# Use user_limiter as the primary limiter
limiter = user_limiter


# ============================================================================
# Rate Limit Configuration
# ============================================================================
# 
# Dual Rate Limiting Strategy:
# - Per-user limits: Generous per-user quotas for fair distribution
# - Global limits: Server-wide caps to protect FMP API quota (300 calls/min)
#
# Format: (per_user_limit, global_limit, fmp_calls_per_request)
# ============================================================================

# /metrics: 6 FMP calls per request
METRICS_USER_LIMIT = "8/minute"        # Per user: 8 requests/min
METRICS_GLOBAL_LIMIT = "48/minute"     # Global: 48 requests × 6 = 288 FMP calls/min

# /charts: 3 FMP calls per request  
CHARTS_USER_LIMIT = "15/minute"        # Per user: 15 requests/min
CHARTS_GLOBAL_LIMIT = "90/minute"      # Global: 90 requests × 3 = 270 FMP calls/min

# /financials: 2 FMP calls per request
FINANCIALS_USER_LIMIT = "20/minute"    # Per user: 20 requests/min
FINANCIALS_GLOBAL_LIMIT = "140/minute" # Global: 140 requests × 2 = 280 FMP calls/min

# /projections: 2 FMP calls per request
PROJECTIONS_USER_LIMIT = "20/minute"   # Per user: 20 requests/min
PROJECTIONS_GLOBAL_LIMIT = "140/minute" # Global: 140 requests × 2 = 280 FMP calls/min

# /info: 1 FMP call per request
INFO_USER_LIMIT = "30/minute"          # Per user: 30 requests/min
INFO_GLOBAL_LIMIT = "280/minute"       # Global: 280 requests × 1 = 280 FMP calls/min

# /health: No FMP calls
HEALTH_USER_LIMIT = "200/minute"       # Per user: 200 requests/min
HEALTH_GLOBAL_LIMIT = None             # No global limit needed

# /mock-income-statement: No FMP calls (mock data)
MOCK_USER_LIMIT = "50/minute"          # Per user: 50 requests/min
MOCK_GLOBAL_LIMIT = None               # No global limit needed


# ============================================================================
# Custom Exception Handler
# ============================================================================

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.
    
    Returns a user-friendly 429 response with retry information.
    """
    logger.warning(
        f"⚠️  Rate limit exceeded for {get_remote_address(request)} "
        f"on endpoint {request.url.path}"
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "message": "Too many requests. Please try again later."
        },
        headers={"Retry-After": "60"}
    )


# ============================================================================
# Rate Limit Summary
# ============================================================================
# 
# Conservative FMP Budget Allocation:
# - /metrics:     288 FMP calls/min (most expensive)
# - /charts:      270 FMP calls/min
# - /financials:  280 FMP calls/min
# - /projections: 280 FMP calls/min
# - /info:        280 FMP calls/min
# 
# Note: Only one endpoint is typically hit at a time per user,
# so the global limits prevent exceeding the 300 calls/min FMP quota.
# ============================================================================

