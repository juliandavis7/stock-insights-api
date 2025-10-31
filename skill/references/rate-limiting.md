# Rate Limiting Implementation

## Overview

The Stock Insights API implements **dual rate limiting** using `slowapi` with in-memory storage (no Redis required). This provides both per-user fairness and server-wide FMP API quota protection.

## Dual Rate Limiting Architecture

### Two-Tier System

1. **Per-User Limits** (JWT-based)
   - Each authenticated user gets their own independent rate limit quota
   - Prevents any single user from monopolizing resources
   - Fair distribution among all users
   - Falls back to IP-based limiting if JWT is unavailable

2. **Global Limits** (Server-wide)
   - Protects the FMP API quota (300 calls/minute)
   - Applies across all users collectively
   - Prevents server from exceeding external API limits
   - Critical for production stability and cost control

### How It Works

Both limiters are checked in sequence:
1. **First**: Per-user limit is checked (is this user over their quota?)
2. **Second**: Global limit is checked (is the server over its quota?)
3. **Result**: Whichever limit is hit first blocks the request

This ensures fair distribution while protecting the FMP quota.

## Technical Implementation

### Module Structure

Rate limiting is centralized in `rate_limit.py`:
- Key extraction functions (`get_user_from_jwt`, `get_global_key`)
- Limiter initialization (`user_limiter`, `global_limiter`)
- Rate limit configuration constants
- Custom exception handler

### Library & Storage

- **Library**: slowapi (>= 0.1.9)
- **Storage**: In-memory (suitable for single-server deployments)
- **Key Function**: JWT-based with IP fallback
- **Headers**: Rate limit information included in response headers

### JWT-Based User Identification

The rate limiter extracts user IDs from JWT tokens:

```python
def get_user_from_jwt(request: Request) -> str:
    # Extract JWT from Authorization header
    # Decode to get user ID (sub claim)
    # Return "user:{user_id}" for rate limiting
    # Fallback to "ip:{ip_address}" if JWT unavailable
```

**Key Features**:
- No signature verification (already done by `verify_token` dependency)
- Extracts `sub` or `user_id` claim
- Graceful fallback to IP-based limiting
- Visible logging for debugging

## Rate Limits Configuration

All rate limits are defined in `rate_limit.py` for easy configuration.

### Endpoint Limits

| Endpoint | Per-User Limit | Global Limit | FMP Calls/Request | Global FMP Budget |
|----------|----------------|--------------|-------------------|-------------------|
| `/health` | 200/min | None | 0 | 0 |
| `/metrics` | 8/min | 48/min | 6 | 288/min |
| `/charts` | 15/min | 90/min | 3 | 270/min |
| `/financials` | 20/min | 140/min | 2 | 280/min |
| `/projections` (GET) | 20/min | 140/min | 2 | 280/min |
| `/projections` (POST) | 20/min | 140/min | 2 | 280/min |
| `/info` | 30/min | 280/min | 1 | 280/min |
| `/mock-income-statement` | 50/min | None | 0 | 0 |

### Design Philosophy

- **Per-user limits**: Generous enough for single users to use endpoints fully
- **Global limits**: Protect FMP quota (stay under 300 calls/minute)
- **Conservative allocation**: ~270-290 FMP calls/min per endpoint
- **Buffer for spikes**: Leaves ~10-30 calls/min buffer per endpoint

**Note**: Only one endpoint is typically hit at a time per user, so global limits protect against multiple concurrent users exhausting the FMP quota.

## Response Headers

When rate limiting is active, successful responses include:

```
X-RateLimit-Limit: 8          # Per-user limit for this endpoint
X-RateLimit-Remaining: 5      # Requests remaining for this user
X-RateLimit-Reset: 1698765432 # Unix timestamp when limit resets
```

**Note**: Global limit headers are not shown (to avoid confusion), but global limits are still enforced.

## Rate Limit Exceeded Response

When either limit is exceeded, the API returns:

**Status Code**: `429 Too Many Requests`

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

The `detail` field indicates which limit was hit:
- `"8 per 1 minute"` = per-user limit (8 requests/min for /metrics)
- `"48 per 1 minute"` = global limit (48 requests/min for /metrics)

## Implementation in api.py

### Import Configuration

```python
from rate_limit import (
    user_limiter,
    global_limiter,
    rate_limit_exceeded_handler,
    METRICS_USER_LIMIT,
    METRICS_GLOBAL_LIMIT,
    # ... other constants
)
```

### App Initialization

```python
app = FastAPI()

# Add rate limiters to app state (required by slowapi)
app.state.limiter = user_limiter
app.state.global_limiter = global_limiter

# Add SlowAPI middleware
app.add_middleware(SlowAPIMiddleware)

# Register custom exception handler
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return await rate_limit_exceeded_handler(request, exc)
```

### Endpoint Decoration

**Important**: Decorator order matters! Per-user limit should be checked first (closer to function).

```python
@app.get("/metrics")
@user_limiter.limit(METRICS_USER_LIMIT)      # Check per-user first
@global_limiter.limit(METRICS_GLOBAL_LIMIT)  # Then check global
def metrics(request: Request, ticker: str, user: Dict = Depends(verify_token)):
    # ... endpoint logic
```

**Requirements**:
- All endpoints must accept `request: Request` as the first parameter
- All endpoints must return `JSONResponse` objects (not plain dicts/Pydantic models)
- Decorators must be in correct order: `@user_limiter` then `@global_limiter`

## Testing

### Test Suite

Comprehensive test scripts are available in `scripts/ratelimit/`:

| Script | Purpose | JWT Tokens Needed |
|--------|---------|-------------------|
| `test_per_user_limit.py` | Tests independent per-user quotas | 1-2 tokens |
| `test_global_limit.py` | Tests server-wide global limits | 1 token |
| `test_dual_limits.py` | Tests both limits working together | 2-3 tokens |

### Running Tests

```bash
# Setup: Add JWT tokens to .env
JWT_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
JWT_TOKEN_2=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...  # For multi-user tests

# Start API in production mode (JWT required)
uvicorn api:app --reload

# Run tests
python3 scripts/ratelimit/test_per_user_limit.py
python3 scripts/ratelimit/test_global_limit.py
python3 scripts/ratelimit/test_dual_limits.py
```

See `scripts/ratelimit/README.md` for detailed test documentation.

### Manual Testing with curl

```bash
# Get JWT token
TOKEN="your_jwt_token_here"

# Test per-user rate limiting
for i in {1..10}; do 
  curl -i -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/metrics?ticker=AAPL"
  echo "---"
done

# Expected: 8 success, then 429 errors
```

## Monitoring

### Log Messages

Rate limit events are logged for monitoring:

```
✅ Rate limiting by user: user_abc123        # JWT extraction succeeded
🔍 Rate limiting by IP: 192.168.1.1          # Fallback to IP
⚠️  Rate limit exceeded for 192.168.1.1 on endpoint /metrics  # Limit hit
```

### What to Monitor

- **Frequency of rate limit hits**: Indicates if limits are too restrictive
- **Which endpoints hit limits most**: May need adjustment
- **JWT extraction failures**: Authentication or token issues
- **Global limit hits**: May indicate heavy concurrent usage

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

⚠️ **Issue**: Each worker has its own in-memory rate limiter. Effective limit = `limit × workers`.

**Solutions**:
1. **Recommended**: Use single worker: `uvicorn api:app --workers 1`
2. Divide limits by worker count in `rate_limit.py`
3. Upgrade to Redis storage for shared state (see below)

### Multiple Servers (Future)

For multi-server deployments (e.g., load-balanced), upgrade to Redis:

```python
# In rate_limit.py
user_limiter = Limiter(
    key_func=get_user_from_jwt,
    storage_uri="redis://localhost:6379",  # Shared state
    ...
)
```

This ensures all servers share the same rate limit counters.

## Troubleshooting

### Rate Limits Not Working

**Symptoms**: All requests succeed, no limits enforced

**Check**:
1. ✅ slowapi installed: `pip3 install slowapi>=0.1.9`
2. ✅ `request: Request` is first parameter in all endpoints
3. ✅ Endpoints return `JSONResponse` objects (not plain dicts)
4. ✅ Limiter added to app state: `app.state.limiter = user_limiter`
5. ✅ SlowAPI middleware added: `app.add_middleware(SlowAPIMiddleware)`
6. ✅ Decorator order correct: `@user_limiter` before `@global_limiter`

### Per-User Limiting Not Working

**Symptoms**: All users share same quota, hitting limits together

**Check**:
1. ✅ JWT token is being sent: `Authorization: Bearer <token>`
2. ✅ JWT extraction logs visible: Look for `✅ Rate limiting by user:` messages
3. ✅ Not all requests falling back to IP: Check for `🔍 Rate limiting by IP:` messages
4. ✅ Running in production mode: `ENVIRONMENT` should not be `local` (unless testing)

**Debug**: Check server logs for JWT extraction messages.

### Rate Limit Headers Not Appearing

**Symptoms**: No `X-RateLimit-*` headers in responses

**Check**:
1. ✅ `headers_enabled=True` in `user_limiter` initialization
2. ✅ Endpoints return `JSONResponse` objects
3. ✅ SlowAPI middleware is added

**Note**: Global limiter has `headers_enabled=False` by design (to avoid confusion).

### Getting 500 Errors

**Symptoms**: Server returns 500 instead of 429 when rate limited

**Cause**: Endpoints returning plain dicts or Pydantic models instead of `JSONResponse`.

**Fix**: Ensure all endpoints return `JSONResponse`:
```python
return JSONResponse(content={"data": "value"})  # ✅ Correct
return {"data": "value"}  # ❌ Will cause 500 error
```

## Configuration Changes

To adjust rate limits, edit `rate_limit.py`:

```python
# Increase per-user limit for /metrics
METRICS_USER_LIMIT = "12/minute"  # Was 8/minute

# Increase global limit for /metrics
METRICS_GLOBAL_LIMIT = "72/minute"  # Was 48/minute (72 × 6 = 432 FMP calls)
```

**Important**: Ensure global limits don't exceed FMP quota (300 calls/minute).

## FMP API Budget Management

With 300 FMP calls/minute available:

- **Conservative allocation**: 270-290 calls/minute per endpoint
- **Buffer for safety**: 10-30 calls/minute buffer
- **Most expensive endpoint**: `/metrics` (6 FMP calls) limited to 288 calls/min
- **Protection**: Global limits ensure no endpoint exceeds quota

### Budget Formula

```
Global Limit = FMP_QUOTA / FMP_CALLS_PER_REQUEST
```

Example for `/metrics`:
```
48 requests/min = 300 calls/min ÷ 6 calls/request
(with safety margin: 288 instead of 300)
```

## Architecture Benefits

### Why Dual Rate Limiting?

| Without Per-User | Without Global | With Both |
|-----------------|----------------|-----------|
| One user monopolizes | Many users exhaust quota | Fair + Protected |
| Unfair to others | FMP billing overages | Best of both worlds |
| Corporate users blocked together | No server protection | Production-ready |

### Key Advantages

1. **Fair Distribution**: Each user gets their own quota
2. **Quota Protection**: Server-wide cap prevents FMP overages
3. **Cost Control**: No unexpected FMP charges
4. **User Experience**: Clear error messages, retry headers
5. **Debugging**: Visible logging for troubleshooting
6. **Maintainability**: Centralized configuration in `rate_limit.py`

## Future Enhancements

1. **Redis Integration**: For multi-server deployments
2. **Tiered Limits**: Different limits for different user subscription tiers
3. **Dynamic Limits**: Adjust based on FMP quota remaining
4. **Rate Limit Analytics**: Track usage patterns per endpoint/user
5. **Burst Allowance**: Allow short bursts above limit
6. **Admin Bypass**: Exclude admin users from rate limits

## References

- **slowapi Documentation**: https://slowapi.readthedocs.io/
- **FMP API Limits**: 300 calls/minute (Starter tier)
- **FastAPI Integration**: https://github.com/laurentS/slowapi
- **Rate Limit Module**: `rate_limit.py`
- **Test Suite**: `scripts/ratelimit/`
