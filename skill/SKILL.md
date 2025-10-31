---
name: stock-api
description: Stock analysis API backend. FastAPI with Clerk auth, FMP & yfinance integration, optimized for 300 FMP calls/min. Use for API endpoints, authentication, external API integration, financial calculations.
---

# Stock Insights API

FastAPI backend providing stock analysis metrics, financial projections, and comprehensive financial data.

## Tech Stack

- **Framework**: FastAPI 0.104+
- **Authentication**: Clerk JWT tokens (JWKS validation)
- **External APIs**: 
  - Financial Modeling Prep (FMP) - Primary data source
  - yfinance - Supplementary stock data
- **Data Processing**: Pandas, custom calculators
- **Environment**: Python 3.9+

## Project Structure

```
stock-insights-api/
├── api.py                      # Main FastAPI application
├── auth.py                     # Clerk JWT authentication
├── util.py                     # Utility functions
├── models/                     # Pydantic request/response models
│   ├── requests.py
│   └── responses.py
├── services/                   # Business logic services
│   ├── fmp_service.py         # FMP API integration
│   ├── fmp_data_fetcher.py    # Optimized data fetching
│   ├── yfinance_service.py    # yfinance integration
│   ├── metrics_service.py     # Metrics orchestration
│   ├── metrics_calculator.py  # Financial calculations
│   ├── projection_service.py  # Projection calculations
│   └── validators/            # Data validation
├── constants/                  # Configuration constants
│   └── constants.py
└── mocks/                      # Mock data for development
    ├── income-statement/
    ├── analyst-estimates/
    ├── cash-flow-statement/
    └── profile/
```

## Key Files

- `api.py` - FastAPI app, all endpoint definitions, CORS setup
- `auth.py` - ClerkAuthValidator class, verify_token dependency
- `models/responses.py` - MetricsResponse, ProjectionResponse, FinancialDataResponse
- `models/requests.py` - ProjectionRequest, YearProjection with validation
- `services/fmp_service.py` - FMP API client, mock data fallback
- `services/metrics_calculator.py` - Financial metric calculations (PE, growth, margins)
- `util.py` - Helper functions for metrics and projections
- `constants/constants.py` - FMP API key, field names, calculation constants

## Common Tasks

### Adding a New API Endpoint

Add endpoint to `api.py` with proper auth and response model. Include authentication via `user: Dict = Depends(verify_token)` dependency. Define Pydantic response model in `models/responses.py`. See **references/endpoints.md** for existing endpoint patterns.

### Working with Authentication

All protected endpoints use Clerk JWT validation. Add `user: Dict = Depends(verify_token)` parameter to endpoint. Local development bypasses auth with `ENVIRONMENT=local`. See **references/auth.md** for complete implementation and error handling.

### Implementing Rate Limiting

Rate limits protect FMP API budget (300 calls/min). Use SlowAPI with per-endpoint limits based on FMP call cost. Example: `@limiter.limit("15/minute")` for expensive endpoints. See **references/rate-limiting.md** for recommended limits and implementation.

### Integrating External APIs

FMP API is primary data source with mock fallback. Use `FMPService` class for all FMP calls. yfinance supplements with real-time prices. Cache expensive calls and reuse fetched data. See **references/external-apis.md** for API details and optimization strategies.

### Optimizing API Calls

Each endpoint makes specific number of FMP calls. `/metrics`: 6 calls, `/financials`: 2 calls, `/charts`: 3 calls. Avoid duplicate fetches by reusing data. Use `fetch_all_data()` pattern for batching. See **references/endpoints.md** for per-endpoint costs.

### Working with Financial Calculations

Metrics calculator provides PE ratios, growth rates, margins. Use `MetricsCalculator` class for consistent calculations. Projection service handles multi-year financial projections. See service classes for calculation logic.

### Adding Request/Response Models

Define Pydantic models in `models/` directory. Use validators for business logic constraints. Include Optional fields with defaults. Document fields with descriptions. See **references/models.md** for all existing models.

## Environment Variables

Required:
- `FMP_API_KEY` - Financial Modeling Prep API key
- `VITE_CLERK_PUBLISHABLE_KEY` or `CLERK_PUBLISHABLE_KEY` - Clerk public key

Optional:
- `ENVIRONMENT` - Set to "local" to bypass authentication
- `FMP_SERVER` - Set to "false" to use mock data instead of live FMP API

## Running the API

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export FMP_API_KEY="your_key_here"
export CLERK_PUBLISHABLE_KEY="your_key_here"

# Run development server
uvicorn api:app --reload

# Run with local auth bypass
ENVIRONMENT=local uvicorn api:app --reload
```

## API Endpoints

All endpoints require authentication except `/health`.

- **GET /health** - Health check (no auth)
- **GET /metrics** - Stock metrics (PE, growth, margins)
- **GET /financials** - Historical + analyst estimates
- **GET /charts** - Chart data (revenue, EPS, margins, cash flow)
- **GET /projections** - Base data for projections
- **POST /projections** - Calculate financial projections
- **GET /info** - Stock price, market cap, shares

See **references/endpoints.md** for complete endpoint documentation with examples.

## FMP API Budget Management

FMP Starter tier: 300 calls/minute

Per-endpoint costs (after optimization):
- `/metrics`: 6 FMP calls
- `/financials`: 2 FMP calls  
- `/charts`: 3 FMP calls
- `/projections` (GET): 1 FMP call
- `/projections` (POST): 1-2 FMP calls
- `/info`: 1 FMP call

Optimization strategies:
1. Reuse fetched data within same request
2. Implement response caching (5-10 min TTL)
3. Apply rate limits based on endpoint cost
4. Use mock data for development

## Authentication Flow

1. Frontend sends request with `Authorization: Bearer <jwt_token>` header
2. `verify_token()` dependency extracts and validates JWT
3. Clerk JWKS public keys validate token signature
4. Decoded payload contains user info (`sub`, `email`)
5. Invalid/expired tokens return 401 error

Local development mode (`ENVIRONMENT=local`) bypasses auth and returns mock user.

## Error Handling

All endpoints use try/except with HTTPException. Return structured error responses with status codes. Log errors with context for debugging. See endpoint implementations for patterns.

## Testing

Mock data available for 21 tickers in `mocks/` directory. Set `FMP_SERVER=false` to use mocks. Test authentication with valid Clerk JWT or local mode. Verify rate limiting with load testing tools.

## Additional Resources

- **references/endpoints.md** - Complete API endpoint documentation
- **references/auth.md** - Authentication implementation details  
- **references/rate-limiting.md** - Rate limiting setup and limits
- **references/models.md** - All Pydantic models
- **references/external-apis.md** - FMP & yfinance integration
- **references/database.md** - Database information (if applicable)

