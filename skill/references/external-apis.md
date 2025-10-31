# External APIs Reference

Integration details for FMP (Financial Modeling Prep) and yfinance APIs.

## FMP API (Financial Modeling Prep)

Primary data source for financial data with 300 calls/minute limit on Starter tier.

### Configuration

```python
# constants/constants.py
FMP_API_KEY = os.getenv("FMP_API_KEY")
FMP_SERVER = os.getenv("FMP_SERVER", "True").lower() == "true"  # Set to "false" for mocks
```

### Base URLs

```python
base_url_v3 = "https://financialmodelingprep.com/api/v3"
base_url_stable = "https://financialmodelingprep.com/stable"
analyst_estimates_url = "https://financialmodelingprep.com/stable/analyst-estimates"
```

### FMPService Class

Complete implementation in `services/fmp_service.py`:

```python
class FMPService:
    """Service for interacting with Financial Modeling Prep API."""
    
    # Stocks with cached mock data for development
    CACHED_STOCKS = [
        "AAPL", "META", "GOOG", "GOOGL", "AMZN", "CELH", "CRM", "ELF", 
        "FUBO", "NVDA", "SOFI", "ADBE", "PLTR", "TSLA", "PYPL", "AMD", 
        "NKE", "SHOP", "CAKE", "WYNN", "MSFT"
    ]
    
    def __init__(self, api_key: str = FMP_API_KEY):
        self.api_key = api_key
        self.base_url_v3 = "https://financialmodelingprep.com/api/v3"
        self.base_url_stable = "https://financialmodelingprep.com/stable"
        self.analyst_estimates_url = FMP_ANALYST_ESTIMATES_URL
        
        # Check if we should use mock data
        self.use_mock_data = os.getenv("FMP_SERVER", "True").lower() == "false"
```

### Key Methods

#### 1. fetch_company_profile()

Get company profile and current stock data.

```python
def fetch_company_profile(self, ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch company profile from FMP."""
    # Returns: price, mktCap, companyName, sector, industry, etc.
```

**API Endpoint:**
```
GET https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={key}
```

**Response Structure:**
```json
[{
  "symbol": "AAPL",
  "price": 185.50,
  "mktCap": 2856000000000,
  "companyName": "Apple Inc.",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "sharesOutstanding": 15408095000
}]
```

#### 2. fetch_quarterly_income_statement()

Get quarterly income statement data.

```python
def fetch_quarterly_income_statement(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
    """Fetch quarterly income statement from FMP."""
    # Returns: revenue, netIncome, eps, operatingIncome, etc.
```

**API Endpoint:**
```
GET https://financialmodelingprep.com/api/v3/income-statement/{ticker}?period=quarter&limit=40&apikey={key}
```

**Response Structure:**
```json
[{
  "date": "2024-09-28",
  "symbol": "AAPL",
  "revenue": 94930000000,
  "costOfRevenue": 51132000000,
  "grossProfit": 43798000000,
  "operatingIncome": 28972000000,
  "netIncome": 24072000000,
  "eps": 1.64,
  "epsDiluted": 1.64,
  "weightedAverageShsOut": 15343783000,
  "weightedAverageShsOutDil": 15408095000
}]
```

#### 3. fetch_quarterly_analyst_estimates()

Get quarterly analyst estimates.

```python
def fetch_quarterly_analyst_estimates(self, ticker: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
    """Fetch quarterly analyst estimates from FMP."""
    # Returns: estimatedRevenueAvg, estimatedEpsAvg, etc.
```

**API Endpoint:**
```
GET https://financialmodelingprep.com/stable/analyst-estimates?ticker={ticker}&period=quarter&limit={limit}&apikey={key}
```

**Response Structure:**
```json
[{
  "date": "2025-03-31",
  "symbol": "AAPL",
  "estimatedRevenueAvg": 92000000000,
  "estimatedRevenueLow": 90000000000,
  "estimatedRevenueHigh": 94000000000,
  "estimatedEpsAvg": 1.55,
  "estimatedEpsLow": 1.50,
  "estimatedEpsHigh": 1.60
}]
```

#### 4. fetch_annual_income_statement()

Get annual income statement data.

```python
def fetch_annual_income_statement(self, ticker: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
    """Fetch annual income statement from FMP."""
```

**API Endpoint:**
```
GET https://financialmodelingprep.com/api/v3/income-statement/{ticker}?limit={limit}&apikey={key}
```

#### 5. fetch_analyst_estimates()

Get annual analyst estimates.

```python
def fetch_analyst_estimates(self, ticker: str, period: str = "annual", page: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch analyst estimates from FMP."""
```

**API Endpoint:**
```
GET https://financialmodelingprep.com/stable/analyst-estimates?ticker={ticker}&period=annual&page={page}&limit={limit}&apikey={key}
```

#### 6. fetch_chart_data()

Get comprehensive chart data (revenue, EPS, margins, cash flow).

```python
def fetch_chart_data(self, ticker: str, mode: str = 'quarterly') -> Optional[Dict[str, Any]]:
    """Fetch comprehensive chart data combining multiple FMP endpoints."""
    # Combines: estimates, income statement, cash flow data
```

**Makes 3 FMP API calls:**
1. `fetch_estimates_data()` - Revenue and EPS
2. `fetch_income_statement_data()` - Margins and operating income
3. `fetch_cash_flow_data()` - Operating and free cash flow

### Mock Data Fallback

When `FMP_SERVER=false` or for cached stocks, returns data from `mocks/` directory:

```
mocks/
├── income-statement/{ticker}.json
├── analyst-estimates/
│   ├── annual/{ticker}.json
│   └── quarterly/{ticker}.json
├── cash-flow-statement/{ticker}.json
└── profile/{ticker}.json
```

**Usage:**
```python
# Use mock data for development
os.environ['FMP_SERVER'] = 'false'
fmp_service = FMPService()
data = fmp_service.fetch_quarterly_income_statement('AAPL')
# Returns data from mocks/income-statement/AAPL.json
```

### Rate Limit Management

**Starter Tier: 300 calls/minute**

Optimization strategies implemented:
1. **Reuse fetched data** within same request
2. **Batch related calls** in `fetch_all_data()`
3. **Eliminate duplicates** (6 calls per metrics request, down from 8)
4. **Use mock data** for development

Per-endpoint costs:
- `/metrics`: 6 calls
- `/financials`: 2 calls
- `/charts`: 3 calls
- `/projections` (GET): 1 call
- `/projections` (POST): 1-2 calls

### Error Handling

```python
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    # Check for FMP API errors
    if isinstance(data, dict) and 'Error Message' in data:
        logger.error(f"FMP API error: {data['Error Message']}")
        return None
    
    return data
    
except requests.exceptions.RequestException as e:
    logger.error(f"FMP API request failed: {e}")
    return None
```

### Caching Strategy

**Not yet implemented** - Recommended for production:

```python
from functools import lru_cache
from datetime import datetime, timedelta

# Cache company profile for 1 hour
@lru_cache(maxsize=100)
def fetch_company_profile_cached(ticker: str, cache_key: str):
    return fetch_company_profile(ticker)

# Generate cache key based on current hour
cache_key = f"{datetime.now().strftime('%Y%m%d%H')}"
profile = fetch_company_profile_cached('AAPL', cache_key)
```

---

## yfinance API

Supplementary data source for real-time stock prices and market data.

### YFinanceService Class

Implementation in `services/yfinance_service.py`:

```python
class YFinanceService:
    """Service for fetching stock data from yfinance."""
    
    def __init__(self):
        self.cache = {}  # Simple in-memory cache
```

### Key Methods

#### 1. get_current_price()

Get real-time stock price.

```python
def get_current_price(self, ticker: str) -> Optional[float]:
    """Get current stock price from yfinance."""
    stock = yf.Ticker(ticker)
    info = stock.info
    
    return (
        info.get('currentPrice') or 
        info.get('regularMarketPrice') or 
        info.get('previousClose')
    )
```

**Usage:**
```python
yfinance_service = YFinanceService()
price = yfinance_service.get_current_price('AAPL')
# Returns: 185.50
```

#### 2. get_market_cap()

Get market capitalization.

```python
def get_market_cap(self, ticker: str) -> Optional[int]:
    """Get market capitalization from yfinance."""
    stock = yf.Ticker(ticker)
    return stock.info.get('marketCap')
```

#### 3. get_shares_outstanding()

Get total shares outstanding.

```python
def get_shares_outstanding(self, ticker: str) -> Optional[int]:
    """Get shares outstanding from yfinance."""
    stock = yf.Ticker(ticker)
    return stock.info.get('sharesOutstanding')
```

#### 4. fetch_stock_info()

Get comprehensive stock information.

```python
def fetch_stock_info(self, ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch comprehensive stock info."""
    stock = yf.Ticker(ticker)
    info = stock.info
    
    return {
        'current_price': info.get('currentPrice'),
        'market_cap': info.get('marketCap'),
        'shares_outstanding': info.get('sharesOutstanding'),
        'trailing_pe': info.get('trailingPE'),
        'forward_pe': info.get('forwardPE'),
        'price_to_sales_ttm': info.get('priceToSalesTrailing12Months'),
        'gross_margins': info.get('grossMargins'),
        # ... more fields
    }
```

### Available Fields

yfinance provides extensive data in `stock.info`:

```python
{
    # Price & Valuation
    'currentPrice': 185.50,
    'previousClose': 184.25,
    'regularMarketPrice': 185.50,
    'marketCap': 2856000000000,
    'sharesOutstanding': 15408095000,
    
    # Valuation Ratios
    'trailingPE': 28.5,
    'forwardPE': 25.2,
    'priceToSalesTrailing12Months': 7.2,
    'priceToBook': 45.3,
    
    # Margins & Returns
    'grossMargins': 0.432,
    'profitMargins': 0.258,
    'operatingMargins': 0.315,
    'returnOnEquity': 1.475,
    
    # Growth & Estimates
    'revenueGrowth': 0.082,
    'earningsGrowth': 0.153,
    'targetMeanPrice': 195.00,
    
    # Company Info
    'longName': 'Apple Inc.',
    'sector': 'Technology',
    'industry': 'Consumer Electronics',
    'website': 'https://www.apple.com',
    
    # ... and many more fields
}
```

### When to Use FMP vs yfinance

**Use FMP for:**
- Historical financial statements
- Analyst estimates
- Detailed quarterly/annual data
- Comprehensive financials

**Use yfinance for:**
- Real-time stock prices
- Market cap (when FMP unavailable)
- Supplementary data
- Quick stock info lookups

### Integration Pattern

Typical pattern uses FMP as primary, yfinance as fallback:

```python
# Primary: Get from FMP
shares_outstanding = fmp_service.fetch_quarterly_income_statement(ticker)[0].get('weightedAverageShsOutDil')

# Fallback: If FMP doesn't have it, use yfinance
if not shares_outstanding:
    stock_info = yfinance_service.fetch_stock_info(ticker)
    shares_outstanding = stock_info.get('shares_outstanding')
```

### Error Handling

```python
try:
    stock = yf.Ticker(ticker)
    info = stock.info
    
    # yfinance returns empty dict on error
    if not info or 'regularMarketPrice' not in info:
        logger.warning(f"No data available for {ticker}")
        return None
    
    return info.get('currentPrice')
    
except Exception as e:
    logger.error(f"yfinance error for {ticker}: {e}")
    return None
```

---

## Data Flow Diagram

```
Frontend Request
    ↓
API Endpoint (auth required)
    ↓
FMPService / YFinanceService
    ↓
├─ Mock Data (if FMP_SERVER=false)
│   └─ mocks/*.json files
│
└─ Live APIs
    ├─ FMP API (primary)
    │   ├─ 300 calls/min limit
    │   ├─ Financial statements
    │   ├─ Analyst estimates
    │   └─ Company profiles
    │
    └─ yfinance (supplementary)
        ├─ Real-time prices
        ├─ Market cap
        └─ Stock info fallback
    ↓
Data Processing / Calculations
    ↓
Response to Frontend
```

---

## Best Practices

1. **Always check for None** - External APIs can fail
2. **Use timeouts** - Set reasonable timeouts (10s)
3. **Log API errors** - Help debug issues
4. **Implement fallbacks** - yfinance for FMP failures
5. **Respect rate limits** - Track FMP usage
6. **Use mock data in dev** - Avoid wasting API calls
7. **Cache expensive calls** - Implement caching for production
8. **Handle API errors gracefully** - Return meaningful errors to users

---

## Environment Configuration

```bash
# Required
FMP_API_KEY=your_fmp_api_key_here

# Optional - Use mock data instead of live API
FMP_SERVER=false

# For rate limiting
REDIS_URL=redis://localhost:6379
```

---

## Testing

```python
# Test with mock data
os.environ['FMP_SERVER'] = 'false'
fmp_service = FMPService()
data = fmp_service.fetch_quarterly_income_statement('AAPL')
assert data is not None

# Test with live API
os.environ['FMP_SERVER'] = 'true'
os.environ['FMP_API_KEY'] = 'your_key'
fmp_service = FMPService()
data = fmp_service.fetch_company_profile('AAPL')
assert 'price' in data[0]

# Test yfinance
yfinance_service = YFinanceService()
price = yfinance_service.get_current_price('AAPL')
assert price > 0
```

