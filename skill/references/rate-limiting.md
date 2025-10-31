# Rate Limiting Implementation

## Overview

The Stock Insights API implements rate limiting using `slowapi` with in-memory storage (no Redis required). This protects the FMP API quota (300 calls/minute) and prevents abuse.

## Architecture

- **Library**: slowapi (>= 0.1.9)
- **Storage**: In-memory (suitable for single-server deployments)
- **Key Function**: IP-based rate limiting via `get_remote_address()`
- **Headers**: Rate limit information included in response headers

## Rate Limits

All environments use the same rate limits to protect the FMP API quota (300 calls/minute).

| Endpoint | Rate Limit | FMP Calls per Request | Total FMP Calls/min |
|----------|------------|----------------------|---------------------|
| `/health` | 200/min | 0 | 0 |
| `/metrics` | 8/min | ~6 | 48 |
| `/charts` | 15/min | ~3 | 45 |
| `/financials` | 20/min | ~2 | 40 |
| `/projections` (GET) | 20/min | ~2 | 40 |
| `/projections` (POST) | 20/min | ~2 | 40 |
| `/info` | 30/min | ~1 | 30 |
| `/mock-income-statement` | 50/min | 0 | 0 |
| Default | 100/min | varies | - |

**Total Conservative Budget**: ~243 FMP calls/minute (under the 300 limit)

## Response Headers

When rate limiting is active, responses include:

```
X-RateLimit-Limit: 8
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1698765432
```

## Rate Limit Exceeded Response

When a rate limit is exceeded, the API returns:

**Status Code**: 429 Too Many Requests

**Response Body**:
```json
{
  "error": "Rate limit exceeded",
  "detail": "8 per 1 minute",
  "message": "Too many requests. Please try again later."
}
```

**Headers**:
```
Retry-After: 60
```

## Implementation Details

### Initialization (api.py)

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri="memory://",
    headers_enabled=True
)

app.state.limiter = limiter
```

### Endpoint Decoration

```python
@app.get("/metrics")
@limiter.limit(METRICS_LIMIT)
def metrics(request: Request, ticker: str, user: Dict = Depends(verify_token)):
    # ... endpoint logic
```

**Note**: All endpoints must accept `request: Request` as the first parameter for slowapi to work.

### Custom Error Handler

```python
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"Rate limit exceeded for {get_remote_address(request)}")
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", ...},
        headers={"Retry-After": "60"}
    )
```

## Configuration

Rate limits are consistent across all environments to protect the FMP API quota. They can be adjusted in `api.py`:

```python
# /metrics: 6 FMP calls × 8 = 48 calls/min
METRICS_LIMIT = "8/minute"
# /charts: 3 FMP calls × 15 = 45 calls/min
CHARTS_LIMIT = "15/minute"
# ... etc
```

## Testing

### Manual Testing

Use the provided test script:

```bash
python3 scripts/test_rate_limit.py
```

### Testing with curl

```bash
# Test health endpoint
for i in {1..10}; do 
  curl -i http://localhost:8000/health
  echo "---"
done
```

### Testing Authenticated Endpoints

```bash
# Get a token first
TOKEN="your_jwt_token_here"

# Test rate limiting
for i in {1..10}; do 
  curl -i -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/metrics?ticker=AAPL"
  echo "---"
done
```

## Monitoring

Rate limit events are logged with warnings:

```
⚠️  Rate limit exceeded for 127.0.0.1 on endpoint /metrics
```

Monitor these logs to:
- Identify users hitting limits
- Adjust limits based on usage patterns
- Detect potential abuse

## Scaling Considerations

### Single Server (Current Setup)
✅ In-memory storage works perfectly
✅ No external dependencies
✅ Fast and simple

### Multiple Workers

If running with multiple uvicorn workers:

```bash
uvicorn api:app --workers 4
```

Each worker has its own rate limiter. Effective limit = `limit × workers`.

**Solutions**:
1. Divide limits by worker count in configuration
2. Use single worker: `uvicorn api:app --workers 1`
3. Upgrade to Redis storage for shared state (future)

### Multiple Servers

For multi-server deployments (e.g., load-balanced), you'll need Redis:

```python
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"
)
```

## Advanced: Per-User Rate Limiting

To rate limit by authenticated user instead of IP:

```python
def get_user_key(request: Request) -> str:
    """Extract user ID from JWT token"""
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_id = decoded.get("sub") or decoded.get("user_id")
            if user_id:
                return f"user:{user_id}"
    except:
        pass
    return get_remote_address(request)

limiter = Limiter(key_func=get_user_key, ...)
```

## Troubleshooting

### Issue: Rate limits not working

**Check**:
1. slowapi is installed: `pip3 install slowapi>=0.1.9`
2. `request: Request` is first parameter in endpoints
3. Limiter is added to app state: `app.state.limiter = limiter`
4. Environment variable is set correctly

### Issue: Limits too restrictive for your use case

**Solution**: Adjust limits in `api.py` based on your needs:
```python
# Increase if needed (but stay under 300 FMP calls/minute total)
METRICS_LIMIT = "15/minute"  # Was 8/minute
```

### Issue: Rate limit headers not appearing

**Check**: `headers_enabled=True` in limiter initialization

## FMP API Budget Management

With 300 FMP calls/minute available:

- Conservative allocation: ~240 calls/minute
- Buffer for spikes: 60 calls/minute
- Per-endpoint limits ensure no single endpoint exhausts quota
- Most expensive endpoint (`/metrics`) limited to 48 calls/minute

## Future Enhancements

1. **Redis Integration**: For multi-server deployments
2. **User-based Limits**: Rate limit by authenticated user
3. **Tiered Limits**: Different limits for different user tiers
4. **Dynamic Limits**: Adjust based on FMP quota remaining
5. **Rate Limit Analytics**: Track usage patterns per endpoint

## References

- slowapi documentation: https://slowapi.readthedocs.io/
- FMP API limits: 300 calls/minute (Starter tier)
- FastAPI integration: https://github.com/laurentS/slowapi
