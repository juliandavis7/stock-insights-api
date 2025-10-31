# Pydantic Models Reference

Complete reference of all request and response models used in the API.

## Request Models

### ProjectionRequest

Used by: `POST /projections`

```python
from pydantic import BaseModel, Field, validator
from typing import Dict, Optional
from datetime import datetime


class ProjectionRequest(BaseModel):
    """Model for the complete projection request"""
    projections: Dict[int, YearProjection] = Field(..., description="Projections by year")
    
    @validator('projections')
    def validate_projection_years(cls, v):
        current_year = datetime.now().year
        valid_years = set(range(current_year + 1, current_year + 5))
        
        for year in v.keys():
            if year not in valid_years:
                raise ValueError(f"Invalid year {year}. Must be between {current_year + 1} and {current_year + 4}")
        
        if not v:
            raise ValueError("At least one projection year must be provided")
        
        return v
```

**Example:**
```json
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

### YearProjection

Used by: `ProjectionRequest`

```python
class YearProjection(BaseModel):
    """Model for a single year's projection inputs"""
    revenue_growth: float = Field(..., ge=-0.5, le=1.0, description="Revenue growth rate (decimal, e.g., 0.15 for 15%)")
    net_income_growth: float = Field(..., ge=-1.0, le=2.0, description="Net income growth rate (decimal)")
    net_income_margin: Optional[float] = Field(None, ge=0.0, le=0.5, description="Expected net income margin (decimal)")
    pe_low: float = Field(..., gt=0, le=100, description="Low PE ratio estimate")
    pe_high: float = Field(..., gt=0, le=200, description="High PE ratio estimate")
    
    @validator('pe_high')
    def pe_high_must_be_greater_than_low(cls, v, values):
        if 'pe_low' in values and v < values['pe_low']:
            raise ValueError('pe_high must be greater than or equal to pe_low')
        return v
```

**Field Constraints:**
- `revenue_growth`: -50% to 100% (-0.5 to 1.0)
- `net_income_growth`: -100% to 200% (-1.0 to 2.0)
- `net_income_margin`: 0% to 50% (0.0 to 0.5)
- `pe_low`: 0 to 100
- `pe_high`: 0 to 200, must be >= pe_low

---

## Response Models

### MetricsResponse

Used by: `GET /metrics`

```python
class MetricsResponse(BaseModel):
    """Model for stock metrics response"""
    ttm_pe: Optional[float]                      # Trailing twelve months P/E ratio
    forward_pe: Optional[float]                  # Forward P/E ratio (next year)
    two_year_forward_pe: Optional[float]         # 2-year forward P/E ratio
    ttm_eps_growth: Optional[float]              # TTM EPS growth percentage
    current_year_eps_growth: Optional[float]     # Current year EPS growth percentage
    next_year_eps_growth: Optional[float]        # Next year EPS growth percentage
    ttm_revenue_growth: Optional[float]          # TTM revenue growth percentage
    current_year_revenue_growth: Optional[float] # Current year revenue growth percentage
    next_year_revenue_growth: Optional[float]    # Next year revenue growth percentage
    gross_margin: Optional[float]                # Gross profit margin percentage
    net_margin: Optional[float]                  # Net profit margin percentage
    ttm_ps_ratio: Optional[float]                # Trailing P/S ratio
    forward_ps_ratio: Optional[float]            # Forward P/S ratio
    ticker: Optional[str]                        # Stock ticker symbol
```

**Example:**
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

### ProjectionResponse

Used by: `POST /projections`

```python
class ProjectionResponse(BaseModel):
    """Model for the projection response"""
    success: bool
    ticker: str
    current_year: int
    base_data: Dict[str, float]               # Current stock price, shares, revenue, net income
    projections: Dict[int, Dict[str, float]]  # Year -> calculated metrics
    summary: Dict[str, Any]                   # CAGR, annualized returns
    error: Optional[str] = None
```

**base_data fields:**
- `current_stock_price`: Current stock price
- `shares_outstanding`: Total shares outstanding
- `current_revenue`: Current year revenue
- `current_net_income`: Current year net income

**projections[year] fields:**
- `revenue`: Projected revenue
- `net_income`: Projected net income
- `eps`: Projected earnings per share
- `stock_price_low`: Low stock price estimate
- `stock_price_high`: High stock price estimate
- `upside_low`: Upside % from current price (low)
- `upside_high`: Upside % from current price (high)

**summary fields:**
- `revenue_cagr`: Revenue compound annual growth rate %
- `net_income_cagr`: Net income CAGR %
- `eps_cagr`: EPS CAGR %

**Example:**
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

### ProjectionBaseDataResponse

Used by: `GET /projections`

```python
class ProjectionBaseDataResponse(BaseModel):
    """Model for projection base data response"""
    ticker: str
    revenue: Optional[int] = None             # Current year revenue
    net_income: Optional[int] = None          # Current year net income
    eps: Optional[float] = None               # Current year EPS
    net_income_margin: Optional[int] = None   # Net income margin percentage
    data_year: int                            # Year of the data
```

**Example:**
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

### ComprehensiveFinancialResponse

Used by: `GET /financials`

```python
class ComprehensiveFinancialResponse(BaseModel):
    """Model for comprehensive financial data including historical and analyst estimates"""
    ticker: str
    historical: List[FinancialDataResponse]    # Historical annual data
    estimates: List[AnalystEstimateResponse]   # Future estimates (2025-2027)
```

**Example:**
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

### FinancialDataResponse

Used by: `ComprehensiveFinancialResponse.historical`

```python
class FinancialDataResponse(BaseModel):
    """Model for processed financial data response"""
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
```

### AnalystEstimateResponse

Used by: `ComprehensiveFinancialResponse.estimates`

```python
class AnalystEstimateResponse(BaseModel):
    """Model for analyst estimates data"""
    fiscalYear: str
    totalRevenue: Optional[int]
    netIncome: Optional[int]
    eps: Optional[float]
    dilutedEps: Optional[float]
```

### FinancialStatementResponse

Used by: `GET /mock-income-statement` (development only)

```python
class FinancialStatementResponse(BaseModel):
    """Model for financial statement response (mock FMP API response)"""
    date: str
    symbol: str
    reportedCurrency: str
    cik: str
    filingDate: str
    acceptedDate: str
    fiscalYear: str
    period: str
    revenue: int
    costOfRevenue: int
    grossProfit: int
    researchAndDevelopmentExpenses: int
    generalAndAdministrativeExpenses: int
    sellingAndMarketingExpenses: int
    sellingGeneralAndAdministrativeExpenses: int
    otherExpenses: int
    operatingExpenses: int
    costAndExpenses: int
    netInterestIncome: int
    interestIncome: int
    interestExpense: int
    depreciationAndAmortization: int
    ebitda: int
    ebit: int
    nonOperatingIncomeExcludingInterest: int
    operatingIncome: int
    totalOtherIncomeExpensesNet: int
    incomeBeforeTax: int
    incomeTaxExpense: int
    netIncomeFromContinuingOperations: int
    netIncomeFromDiscontinuedOperations: int
    otherAdjustmentsToNetIncome: int
    netIncome: int
    netIncomeDeductions: int
    bottomLineNetIncome: int
    eps: float
    epsDiluted: float
    weightedAverageShsOut: int
    weightedAverageShsOutDil: int
```

### ErrorResponse

Used by: Error handling

```python
class ErrorResponse(BaseModel):
    """Model for error responses"""
    success: bool = False
    error: str
    ticker: Optional[str] = None
```

**Example:**
```json
{
  "success": false,
  "error": "Invalid ticker symbol",
  "ticker": "INVALID"
}
```

---

## Model Usage by Endpoint

| Endpoint | Request Model | Response Model |
|----------|---------------|----------------|
| `GET /health` | None | `Dict` |
| `GET /metrics` | None | `MetricsResponse` |
| `GET /financials` | None | `ComprehensiveFinancialResponse` |
| `GET /charts` | None | `Dict` (not using Pydantic model) |
| `GET /projections` | None | `ProjectionBaseDataResponse` |
| `POST /projections` | `ProjectionRequest` | `ProjectionResponse` |
| `GET /info` | None | `Dict` (not using Pydantic model) |
| `GET /mock-income-statement` | None | `List[FinancialStatementResponse]` |

---

## Common Patterns

### Optional Fields

Most response fields are `Optional` to handle cases where data is unavailable:

```python
class MetricsResponse(BaseModel):
    ttm_pe: Optional[float]  # May be None if data unavailable
    forward_pe: Optional[float]
    # ...
```

### Field Validation

Use Pydantic validators for business logic:

```python
@validator('pe_high')
def pe_high_must_be_greater_than_low(cls, v, values):
    if 'pe_low' in values and v < values['pe_low']:
        raise ValueError('pe_high must be greater than or equal to pe_low')
    return v
```

### Field Constraints

Use `Field` with constraints:

```python
revenue_growth: float = Field(..., ge=-0.5, le=1.0)  # Between -50% and 100%
pe_low: float = Field(..., gt=0, le=100)             # Greater than 0, up to 100
```

### Nested Models

Models can contain other models:

```python
class ComprehensiveFinancialResponse(BaseModel):
    ticker: str
    historical: List[FinancialDataResponse]  # List of nested model
    estimates: List[AnalystEstimateResponse]  # List of nested model
```

---

## Adding New Models

### Steps

1. **Create model class** in appropriate file:
   - Requests: `models/requests.py`
   - Responses: `models/responses.py`

2. **Add validators** for business logic constraints

3. **Export in** `models/__init__.py`:
```python
from models.requests import ProjectionRequest, YearProjection
from models.responses import MetricsResponse, ProjectionResponse
```

4. **Use in endpoint**:
```python
@app.post("/endpoint", response_model=YourResponseModel)
def endpoint(request: YourRequestModel):
    # ...
```

### Best Practices

- Use `Optional` for fields that may be missing
- Add field descriptions with `Field(..., description="...")`
- Use validators for complex validation logic
- Keep models focused and single-purpose
- Document field meanings in docstrings
- Use type hints for all fields

---

## Validation Examples

### Automatic Validation

Pydantic automatically validates:
```python
# This will fail validation
invalid_request = {
    "projections": {
        "2026": {
            "revenue_growth": 2.0,  # Invalid: exceeds 1.0 max
            "pe_low": 50.0,
            "pe_high": 40.0  # Invalid: pe_high < pe_low
        }
    }
}

# Returns 422 Unprocessable Entity with error details
```

### Custom Validation

Add custom validators:
```python
@validator('projections')
def validate_projection_years(cls, v):
    current_year = datetime.now().year
    valid_years = set(range(current_year + 1, current_year + 5))
    
    for year in v.keys():
        if year not in valid_years:
            raise ValueError(f"Invalid year {year}")
    
    return v
```

---

## Testing Models

```python
from models import ProjectionRequest, YearProjection

# Valid model
request = ProjectionRequest(projections={
    2026: YearProjection(
        revenue_growth=0.12,
        net_income_growth=0.15,
        net_income_margin=0.25,
        pe_low=25.0,
        pe_high=35.0
    )
})

# Access fields
assert request.projections[2026].revenue_growth == 0.12

# Convert to dict
request_dict = request.dict()

# Convert to JSON
request_json = request.json()
```

