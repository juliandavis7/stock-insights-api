# API Endpoints Reference

Complete documentation of all API endpoints with request/response examples.

## Endpoint Summary

| Endpoint | Method | Auth | FMP Calls | Rate Limit (Recommended) | Purpose |
|----------|--------|------|-----------|--------------------------|---------|
| `/health` | GET | No | 0 | Unlimited | Health check |
| `/metrics` | GET | Yes | 6 | 15/min | Stock metrics |
| `/financials` | GET | Yes | 2 | 50/min | Financial data |
| `/charts` | GET | Yes | 3 | 30/min | Chart data |
| `/projections` | GET | Yes | 1 | 100/min | Base projection data |
| `/projections` | POST | Yes | 1-2 | 75/min | Calculate projections |
| `/info` | GET | Yes | 1 | 100/min | Stock info |
| `/mock-income-statement` | GET | Yes | 0 | N/A | Mock data (dev only) |

---

## GET /health

Health check endpoint (no authentication required).

### Request
```http
GET /health HTTP/1.1
```

### Response
```json
{
  "status": "ok"
}
```

### Response Model
```python
# Returns dict with status field
{"status": str}
```

---

## GET /metrics

Get comprehensive stock metrics including PE ratios, growth rates, and margins.

### Request
```http
GET /metrics?ticker=AAPL HTTP/1.1
Authorization: Bearer <jwt_token>
```

### Query Parameters
- `ticker` (required) - Stock ticker symbol (e.g., AAPL, MSFT, GOOGL)

### Response Model
```python
class MetricsResponse(BaseModel):
    ttm_pe: Optional[float]                      # Trailing 12-month P/E ratio
    forward_pe: Optional[float]                  # Forward P/E ratio (next year)
    two_year_forward_pe: Optional[float]         # 2-year forward P/E ratio
    ttm_eps_growth: Optional[float]              # TTM EPS growth %
    current_year_eps_growth: Optional[float]     # Current year EPS growth %
    next_year_eps_growth: Optional[float]        # Next year EPS growth %
    ttm_revenue_growth: Optional[float]          # TTM revenue growth %
    current_year_revenue_growth: Optional[float] # Current year revenue growth %
    next_year_revenue_growth: Optional[float]    # Next year revenue growth %
    gross_margin: Optional[float]                # Gross profit margin %
    net_margin: Optional[float]                  # Net profit margin %
    ttm_ps_ratio: Optional[float]                # Trailing P/S ratio
    forward_ps_ratio: Optional[float]            # Forward P/S ratio
    ticker: Optional[str]                        # Stock ticker
```

### Example Response
```json
{
  "ttm_pe": 28.5,
  "forward_pe": 25.2,
  "two_year_forward_pe": 22.8,
  "ttm_eps_growth": 15.3,
  "current_year_eps_growth": 12.5,
  "next_year_eps_growth": 10.8,
  "ttm_revenue_growth": 8.2,
  "current_year_revenue_growth": 9.5,
  "next_year_revenue_growth": 11.2,
  "gross_margin": 43.2,
  "net_margin": 25.8,
  "ttm_ps_ratio": 7.2,
  "forward_ps_ratio": 6.5,
  "ticker": "AAPL"
}
```

### FMP API Calls: 6
1. Company profile
2. Current year income data
3. Annual analyst estimates
4. Quarterly income statement
5. Annual income statement
6. Quarterly analyst estimates

---

## GET /financials

Get comprehensive financial data including historical financials and analyst estimates.

### Request
```http
GET /financials?ticker=AAPL HTTP/1.1
Authorization: Bearer <jwt_token>
```

### Query Parameters
- `ticker` (required) - Stock ticker symbol

### Response Model
```python
class ComprehensiveFinancialResponse(BaseModel):
    ticker: str
    historical: List[FinancialDataResponse]  # Historical annual data
    estimates: List[AnalystEstimateResponse]  # Future estimates (2025-2027)

class FinancialDataResponse(BaseModel):
    fiscalYear: str
    totalRevenue: Optional[int]
    costOfRevenue: Optional[int]
    grossProfit: Optional[int]
    sellingGeneralAndAdministrative: Optional[int]
    researchAndDevelopment: Optional[int]
    operatingExpenses: Optional[int]
    operatingIncome: Optional[int]
    netIncome: Optional[int]
    eps: Optional[float]
    dilutedEps: Optional[float]

class AnalystEstimateResponse(BaseModel):
    fiscalYear: str
    totalRevenue: Optional[int]
    netIncome: Optional[int]
    eps: Optional[float]
    dilutedEps: Optional[float]
```

### Example Response
```json
{
  "ticker": "AAPL",
  "historical": [
    {
      "fiscalYear": "2024",
      "totalRevenue": 391035000000,
      "costOfRevenue": 210352000000,
      "grossProfit": 180683000000,
      "sellingGeneralAndAdministrative": 26097000000,
      "researchAndDevelopment": 31370000000,
      "operatingExpenses": 57467000000,
      "operatingIncome": 123216000000,
      "netIncome": 93736000000,
      "eps": 6.11,
      "dilutedEps": 6.08
    }
  ],
  "estimates": [
    {
      "fiscalYear": "2025",
      "totalRevenue": 420000000000,
      "netIncome": 98000000000,
      "eps": 6.45,
      "dilutedEps": 6.39
    }
  ]
}
```

### FMP API Calls: 2
1. Quarterly income statement
2. Quarterly analyst estimates

---

## GET /charts

Get chart data including revenue, EPS, margins, and cash flow metrics.

### Request
```http
GET /charts?ticker=AAPL&mode=quarterly HTTP/1.1
Authorization: Bearer <jwt_token>
```

### Query Parameters
- `ticker` (required) - Stock ticker symbol
- `mode` (optional) - Data mode: "quarterly" (default) or "ttm" (trailing twelve months)

### Response Structure
```python
{
    "ticker": str,
    "quarters": List[str],              # Quarter labels (e.g., "2024 Q1")
    "revenue": List[int],               # Revenue values
    "eps": List[float],                 # EPS values
    "gross_margin": List[Optional[float]],      # Gross margin %
    "net_margin": List[Optional[float]],        # Net margin %
    "operating_income": List[Optional[int]],    # Operating income
    "operating_cash_flow": List[Optional[int]], # Operating cash flow
    "free_cash_flow": List[Optional[int]]       # Free cash flow
}
```

### Example Response
```json
{
  "ticker": "AAPL",
  "quarters": ["2024 Q3", "2024 Q2", "2024 Q1", "2023 Q4"],
  "revenue": [94930000000, 85780000000, 90753000000, 119575000000],
  "eps": [1.64, 1.53, 1.52, 2.18],
  "gross_margin": [46.2, 45.9, 46.6, 45.9],
  "net_margin": [25.3, 24.8, 25.0, 25.3],
  "operating_income": [28972000000, 26274000000, 27421000000, 40323000000],
  "operating_cash_flow": [30740000000, 26690000000, 22892000000, 34327000000],
  "free_cash_flow": [28123000000, 24521000000, 20145000000, 31892000000]
}
```

### FMP API Calls: 3
1. Quarterly analyst estimates (for revenue/EPS)
2. Quarterly income statement (for margins/operating income)
3. Quarterly cash flow statement (for cash flows)

---

## GET /projections

Get base data for financial projections (current financials to project from).

### Request
```http
GET /projections?ticker=AAPL HTTP/1.1
Authorization: Bearer <jwt_token>
```

### Query Parameters
- `ticker` (required) - Stock ticker symbol

### Response Model
```python
class ProjectionBaseDataResponse(BaseModel):
    ticker: str
    revenue: Optional[int]              # Current year revenue
    net_income: Optional[int]           # Current year net income
    eps: Optional[float]                # Current year EPS
    net_income_margin: Optional[int]    # Net income margin %
    data_year: int                      # Year of the data
```

### Example Response
```json
{
  "ticker": "AAPL",
  "revenue": 391035000000,
  "net_income": 93736000000,
  "eps": 6.08,
  "net_income_margin": 24,
  "data_year": 2024
}
```

### FMP API Calls: 1
1. Quarterly income statement (for shares outstanding and financial data)

---

## POST /projections

Calculate multi-year financial projections based on growth assumptions.

### Request
```http
POST /projections?ticker=AAPL HTTP/1.1
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "projections": {
    "2026": {
      "revenue_growth": 0.12,
      "net_income_growth": 0.15,
      "net_income_margin": 0.25,
      "pe_low": 25.0,
      "pe_high": 35.0
    },
    "2027": {
      "revenue_growth": 0.10,
      "net_income_growth": 0.12,
      "net_income_margin": 0.26,
      "pe_low": 24.0,
      "pe_high": 33.0
    }
  }
}
```

### Query Parameters
- `ticker` (required) - Stock ticker symbol (must be uppercase, 1-5 chars)

### Request Model
```python
class ProjectionRequest(BaseModel):
    projections: Dict[int, YearProjection]

class YearProjection(BaseModel):
    revenue_growth: float          # Revenue growth rate (decimal, -0.5 to 1.0)
    net_income_growth: float       # Net income growth rate (decimal, -1.0 to 2.0)
    net_income_margin: Optional[float]  # Net income margin (decimal, 0.0 to 0.5)
    pe_low: float                  # Low P/E ratio estimate (0 to 100)
    pe_high: float                 # High P/E ratio estimate (0 to 200, >= pe_low)
```

### Response Model
```python
class ProjectionResponse(BaseModel):
    success: bool
    ticker: str
    current_year: int
    base_data: Dict[str, float]    # Current stock price, shares, revenue, net income
    projections: Dict[int, Dict[str, float]]  # Year -> calculated metrics
    summary: Dict[str, Any]        # CAGR, annualized returns
    error: Optional[str]
```

### Example Response
```json
{
  "success": true,
  "ticker": "AAPL",
  "current_year": 2025,
  "base_data": {
    "current_stock_price": 185.50,
    "shares_outstanding": 15408095000,
    "current_revenue": 391035000000,
    "current_net_income": 93736000000
  },
  "projections": {
    "2026": {
      "revenue": 438000000000,
      "net_income": 107800000000,
      "eps": 6.99,
      "stock_price_low": 174.75,
      "stock_price_high": 244.65,
      "upside_low": -5.8,
      "upside_high": 31.9
    }
  },
  "summary": {
    "revenue_cagr": 11.5,
    "net_income_cagr": 14.2,
    "eps_cagr": 14.2
  }
}
```

### FMP API Calls: 1-2
1. Current year data (always)
2. Quarterly income statement (only if shares outstanding not in current data)

---

## GET /info

Get basic stock information including current price, market cap, and shares outstanding.

### Request
```http
GET /info?ticker=AAPL HTTP/1.1
Authorization: Bearer <jwt_token>
```

### Query Parameters
- `ticker` (required) - Stock ticker symbol

### Response Structure
```python
{
    "ticker": str,
    "price": float,                    # Current stock price
    "market_cap": Optional[int],       # Market capitalization
    "shares_outstanding": Optional[int] # Total shares outstanding
}
```

### Example Response
```json
{
  "ticker": "AAPL",
  "price": 185.50,
  "market_cap": 2856000000000,
  "shares_outstanding": 15408095000
}
```

### FMP API Calls: 1
1. Quarterly income statement (for shares outstanding, if yfinance doesn't have it)

---

## Common Error Responses

### 401 Unauthorized
```json
{
  "detail": "Missing authentication credentials"
}
```

### 404 Not Found
```json
{
  "detail": "No data found for ticker INVALID"
}
```

### 429 Too Many Requests (Rate Limited)
```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please slow down and try again.",
  "retry_after": 60
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error: <error message>"
}
```

---

## Implementation Notes

### Authentication
All endpoints except `/health` require authentication. Add to endpoint:
```python
user: Dict = Depends(verify_token)
```

### Rate Limiting (Recommended)
Apply limits based on FMP API cost:
```python
@limiter.limit("15/minute")  # For expensive endpoints like /metrics
async def metrics(request: Request, ticker: str, user: Dict = Depends(verify_token)):
    # ...
```

### Error Handling Pattern
```python
try:
    data = get_metrics(ticker)
    return data
except Exception as e:
    logging.error(f"Error in endpoint for {ticker}: {e}")
    raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
```

### CORS Configuration
Frontend origins are configured in `api.py`:
- Local: `http://localhost:5173`
- Production: Vercel preview deployments via regex pattern

