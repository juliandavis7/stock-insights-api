# Rate Limiting Reference

Rate limiting implementation to protect FMP API budget (300 calls/minute).

## Overview

Rate limiting prevents exceeding the FMP API limit by restricting requests per endpoint based on their FMP API cost. Uses SlowAPI library with in-memory storage for single-instance deployments.

## FMP API Budget

**FMP Starter Tier: 300 calls/minute**

### Per-Endpoint Costs (After Optimization)

| Endpoint | FMP Calls | Recommended Limit | Max Throughput |
|----------|-----------|-------------------|----------------|
| `/metrics` | 6 | 15/min | 15 req × 6 = 90 calls |
| `/financials` | 2 | 50/min | 50 req × 2 = 100 calls |
| `/charts` | 3 | 30/min | 30 req × 3 = 90 calls |
| `/projections` (GET) | 1 | 100/min | 100 req × 1 = 100 calls |
| `/projections` (POST) | 1-2 | 75/min | 75 req × 1.5 = 112 calls |
| `/info` | 1 | 100/min | 100 req × 1 = 100 calls |
| `/health` | 0 | Unlimited | No FMP calls |

**Safety Buffer**: Reserve 20 calls → **280 usable calls/min**

## SlowAPI Implementation

### Installation

```bash
pip install slowapi
```

Add to `requirements.txt`:
```
slowapi>=0.1.9
```

### Rate Limiter Module

Create `middleware/rate_limiter.py`:

```python
"""Rate limiting configuration for API endpoints."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request, HTTPException
from slowapi.errors import RateLimitExceeded
import logging

logger = logging.getLogger(__name__)


def get_user_identifier(request: Request) -> str:
    """
    Extract user identifier for rate limiting.
    Uses JWT token if available, falls back to IP.
    """
    try:
        # Extract from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # Use portion of token as unique identifier
            token = auth_header[7:30]  # First 23 chars after "Bearer "
            return f"user:{token}"
    except Exception as e:
        logger.warning(f"Error extracting user identifier: {e}")
    
    # Fallback to IP address
    return f"ip:{get_remote_address(request)}"


# Initialize limiter with IN-MEMORY storage (no Redis needed for single instance)
limiter = Limiter(
    key_func=get_user_identifier,
    storage_uri="memory://",  # Simple in-memory storage
    default_limits=["100/minute"],  # Global default per user
    strategy="fixed-window"  # Can use "moving-window" for smoother limiting
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom error response for rate limit exceeded."""
    raise HTTPException(
        status_code=429,
        detail={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please slow down and try again.",
            "retry_after": 60
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": str(exc.detail.split()[0]) if exc.detail else "unknown"
        }
    )
```

### Integration in api.py

Add imports:
```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from fastapi import Request  # Make sure Request is imported
```

After `app = FastAPI()`:
```python
app = FastAPI()

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ... rest of middleware (CORS, etc.)
```

## Applying Rate Limits to Endpoints

### Pattern

Add two things to each endpoint:
1. `@limiter.limit("X/minute")` decorator
2. `request: Request` parameter

### Examples

```python
# Health check - no limit
@app.get("/health")
@limiter.exempt  # Exempt from rate limiting
def health_check(request: Request):
    return {"status": "ok"}


# Expensive endpoint - strict limit
@app.get("/metrics", response_model=MetricsResponse)
@limiter.limit("15/minute")  # 15 requests per minute
async def metrics(
    request: Request,  # ADD THIS - required by limiter
    ticker: str = Query(...),
    user: Dict = Depends(verify_token)
):
    # ... existing code unchanged ...


# Medium cost endpoint
@app.get("/charts")
@limiter.limit("30/minute")
async def get_chart_revenue(
    request: Request,
    ticker: str = Query(...),
    mode: str = Query("quarterly"),
    user: Dict = Depends(verify_token)
):
    # ... existing code ...


# Cheap endpoint - generous limit
@app.get("/info")
@limiter.limit("100/minute")
async def get_info(
    request: Request,
    ticker: str = Query(...),
    user: Dict = Depends(verify_token)
):
    # ... existing code ...
```

## Complete Rate Limit Table

| Endpoint | Decorator | Reasoning |
|----------|-----------|-----------|
| `/health` | `@limiter.exempt` | No FMP calls, health checks need high availability |
| `/metrics` | `@limiter.limit("15/minute")` | Most expensive (6 FMP calls), strictest limit |
| `/financials` | `@limiter.limit("50/minute")` | Cheap (2 FMP calls), generous limit |
| `/charts` | `@limiter.limit("30/minute")` | Medium cost (3 FMP calls), medium limit |
| `/projections` GET | `@limiter.limit("100/minute")` | Very cheap (1 FMP call), high limit |
| `/projections` POST | `@limiter.limit("75/minute")` | Cheap (1-2 FMP calls), high limit |
| `/info` | `@limiter.limit("100/minute")` | Very cheap (1 FMP call), high limit |

## Rate Limit Response

### Headers

SlowAPI automatically adds:
```http
X-RateLimit-Limit: 15
X-RateLimit-Remaining: 12
X-RateLimit-Reset: 1234567890
```

### 429 Error Response

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please slow down and try again.",
  "retry_after": 60
}
```

Headers:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 15
```

## Storage Options

### In-Memory (Default - Recommended for Single Instance)

```python
limiter = Limiter(
    key_func=get_user_identifier,
    storage_uri="memory://",  # In-memory storage
    default_limits=["100/minute"]
)
```

**Pros:**
- No external dependencies
- Easy to set up
- Fast performance
- Good for single server/container

**Cons:**
- Limits reset on restart
- Doesn't work across multiple instances
- Memory usage grows (cleaned up automatically)

### Redis (For Multiple Instances)

```python
limiter = Limiter(
    key_func=get_user_identifier,
    storage_uri="redis://localhost:6379",  # Redis storage
    default_limits=["100/minute"]
)
```

**Pros:**
- Works across multiple instances
- Persistent limits (survive restarts)
- Centralized tracking

**Cons:**
- Requires Redis server
- Additional infrastructure
- Slightly slower than in-memory

## User Identification Strategy

### Primary: JWT Token

```python
def get_user_identifier(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:30]  # First 23 chars
        return f"user:{token}"
    
    # Fallback to IP
    return f"ip:{get_remote_address(request)}"
```

**Benefits:**
- Rate limits apply per authenticated user
- Users can't bypass by changing IP
- Works with Clerk authentication

### Fallback: IP Address

For unauthenticated requests or if token extraction fails, uses client IP.

## Local Development

Disable rate limiting in local mode:

```python
import os

# In middleware/rate_limiter.py
if os.getenv('ENVIRONMENT') == 'local':
    limiter = Limiter(
        key_func=get_user_identifier,
        storage_uri="memory://",
        default_limits=[],  # No limits
        enabled=False  # Disable rate limiting
    )
```

Or set high limits:
```python
default_limits=["10000/minute"]  # Effectively unlimited for dev
```

## Testing Rate Limits

### Manual Testing

```bash
# Send 16 requests to /metrics (limit is 15/min)
for i in {1..16}; do
  curl -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/metrics?ticker=AAPL"
  echo "Request $i"
done

# Request 16 should return 429
```

### Python Test Script

```python
import requests
import time

BASE_URL = "http://localhost:8000"
TOKEN = "your_test_token"
headers = {"Authorization": f"Bearer {TOKEN}"}

# Test: Within limit (should work)
for i in range(15):
    response = requests.get(f"{BASE_URL}/metrics?ticker=AAPL", headers=headers)
    print(f"Request {i+1}: {response.status_code}")
    assert response.status_code == 200

# Test: Exceeds limit (should fail)
response = requests.get(f"{BASE_URL}/metrics?ticker=AAPL", headers=headers)
print(f"Request 16 (should be 429): {response.status_code}")
assert response.status_code == 429

# Test: After waiting (should work again)
time.sleep(60)
response = requests.get(f"{BASE_URL}/metrics?ticker=AAPL", headers=headers)
print(f"After wait (should be 200): {response.status_code}")
assert response.status_code == 200
```

## Monitoring Rate Limits

### Admin Endpoint (Optional)

```python
@app.get("/admin/rate-limit-status")
async def get_rate_limit_status(
    request: Request,
    user: Dict = Depends(verify_token)
):
    """Get current rate limit configuration."""
    return {
        "status": "Rate limiting active",
        "strategy": "fixed-window",
        "storage": "in-memory",
        "limits": {
            "metrics": "15/minute",
            "financials": "50/minute",
            "charts": "30/minute",
            "projections_get": "100/minute",
            "projections_post": "75/minute",
            "info": "100/minute",
            "global": "100/minute per user"
        },
        "fmp_api_budget": {
            "total": 300,
            "reserved": 20,
            "usable": 280
        }
    }
```

### Logging

Log rate limit hits:
```python
@app.middleware("http")
async def log_rate_limits(request: Request, call_next):
    response = await call_next(request)
    
    if response.status_code == 429:
        logger.warning(f"Rate limit exceeded: {request.url.path} by {get_user_identifier(request)}")
    
    return response
```

## Advanced: Custom Rate Limit Logic

### Different Limits per User Tier

```python
def get_rate_limit_for_user(user: Dict) -> str:
    """Dynamic rate limits based on user tier."""
    tier = user.get('tier', 'free')
    
    limits = {
        'free': "10/minute",
        'standard': "50/minute",
        'premium': "200/minute"
    }
    
    return limits.get(tier, "10/minute")

# Apply in endpoint
@app.get("/metrics")
async def metrics(request: Request, user: Dict = Depends(verify_token)):
    # Apply dynamic limit
    limit = get_rate_limit_for_user(user)
    limiter.limit(limit)(metrics)(request, user)
    # ... endpoint logic
```

### Per-Ticker Limits

Prevent abuse of specific tickers:
```python
from collections import defaultdict
import time

ticker_limits = defaultdict(list)

@app.middleware("http")
async def ticker_rate_limit(request: Request, call_next):
    ticker = request.query_params.get('ticker')
    
    if ticker:
        # Limit: 10 requests per ticker per minute
        now = time.time()
        ticker_limits[ticker] = [t for t in ticker_limits[ticker] if now - t < 60]
        
        if len(ticker_limits[ticker]) >= 10:
            raise HTTPException(status_code=429, detail="Too many requests for this ticker")
        
        ticker_limits[ticker].append(now)
    
    return await call_next(request)
```

## Troubleshooting

### Issue: Rate limit not working
**Solution**: Ensure `request: Request` parameter is added to endpoint and limiter middleware is registered

### Issue: All users share same limit
**Solution**: Check `get_user_identifier()` is properly extracting user token, not just using IP

### Issue: Limits reset on server restart
**Solution**: Expected with in-memory storage. Use Redis for persistence.

### Issue: 429 errors in production
**Solution**: Review limits are appropriate for your traffic. Monitor FMP API usage to adjust.

## Best Practices

1. **Test limits in staging** before production deployment
2. **Monitor 429 errors** to identify if limits too strict
3. **Log rate limit events** for analysis
4. **Use Redis in production** if running multiple instances
5. **Set different limits per endpoint** based on cost
6. **Include retry-after headers** to help clients
7. **Document limits** for API consumers
8. **Review limits quarterly** based on usage patterns

