# Portfolio API Documentation

## Overview

The Portfolio API allows users to upload CSV files containing their stock portfolio holdings and retrieve their saved portfolio with dynamically calculated values based on current stock prices.

**Key Features:**
- Supports two CSV formats: Chase brokerage export and generic format
- Automatically saves portfolios to database (one per user)
- Calculates dynamic values (market value, gain/loss, percentages) from current stock prices
- Uses yfinance for real-time price fetching
- Excludes cash equivalents automatically

---

## Endpoints

### 1. POST /portfolio/upload

Upload a CSV file containing portfolio holdings. The portfolio is automatically saved to the database.

**Authentication:** Required (Bearer token)

**Rate Limits:**
- Per user: 30 requests/minute
- Global: 200 requests/minute

#### Request

**Method:** `POST`

**URL:** `/portfolio/upload?format=auto`

**Query Parameters:**
- `format` (optional): `"chase"` | `"generic"` | `"auto"` (default: `"auto"`)
  - `"chase"`: Force Chase format detection
  - `"generic"`: Force generic format detection
  - `"auto"`: Auto-detect format based on CSV headers

**Headers:**
```
Authorization: Bearer <clerk_jwt_token>
Content-Type: multipart/form-data
```

**Body:**
- `file` (required): CSV file upload (form-data)

#### CSV Formats

##### Chase Format

Required columns: `Ticker`, `Quantity`, `Value`, `Cost`, `Description`

Example:
```csv
Asset Class,Description,Ticker,Quantity,Value,Cost,...
Equity,ADVANCED MICRO DEVICES INC COM,AMD,145,31605.65,17691.71,...
Equity,META PLATFORMS INC CLASS A COMMON STOCK,META,45.21538,30448.94,12616.51,...
```

**Notes:**
- Parser stops at "FOOTNOTES" row
- Cash equivalents (VMFXX, QACDS, QDERQ, etc.) are automatically excluded
- Uses `Value` column for market_value (not calculated)

##### Generic Format

Required columns: `ticker`, `shares`, `cost_basis`

Example:
```csv
ticker,shares,cost_basis
AMD,145.0,17691.71
META,45.21538,12616.51
GOOG,83.0,14491.21
AMZN,88.0,13633.08
```

**Notes:**
- Column names are case-insensitive
- Only requires ticker, shares, and cost_basis
- Market value will be calculated from current prices when retrieved via GET endpoint

#### Response

**Status:** `200 OK`

**Response Model:** `PortfolioUploadResponse`

```json
{
  "holdings": [
    {
      "ticker": "AMD",
      "name": "ADVANCED MICRO DEVICES INC COM",
      "shares": 145.0,
      "cost_basis": 17691.71
    },
    {
      "ticker": "META",
      "name": "META PLATFORMS INC CLASS A COMMON STOCK",
      "shares": 45.21538,
      "cost_basis": 12616.51
    }
  ],
  "total_cost_basis": 119025.9,
  "detected_format": "chase",
  "excluded_items": [
    {
      "ticker": "VMFXX",
      "reason": "cash_equivalent"
    },
    {
      "ticker": "QACDS",
      "reason": "cash_equivalent"
    }
  ]
}
```

**Response Fields:**
- `holdings`: Array of portfolio holdings (static data only)
  - `ticker`: Stock ticker symbol
  - `name`: Company name (from CSV or null for generic format)
  - `shares`: Number of shares owned
  - `cost_basis`: Total cost basis for the position
- `total_cost_basis`: Sum of all cost bases
- `detected_format`: `"chase"` or `"generic"`
- `excluded_items`: Array of excluded items (cash equivalents)

**Note:** This endpoint returns static data only. Dynamic values (`market_value`, `gain_loss_pct`, `percent_of_portfolio`) are calculated when retrieving via GET endpoint.

#### Error Responses

**400 Bad Request:**
```json
{
  "detail": "File must be a CSV"
}
```

```json
{
  "detail": "No valid holdings found in CSV"
}
```

```json
{
  "detail": "Unknown CSV format. Expected columns for Chase format: Ticker, Quantity, Value, Cost. Or generic format: ticker, shares, cost_basis."
}
```

**401 Unauthorized:**
```json
{
  "detail": "Missing authentication credentials"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error parsing CSV: <error message>"
}
```

---

### 2. GET /portfolio

Retrieve saved portfolio with dynamically calculated values based on current stock prices.

**Prices are cached for 1 hour.** Use `?refresh=true` to force fresh prices.

**Authentication:** Required (Bearer token)

**Rate Limits:**
- Per user: 30 requests/minute
- Global: 200 requests/minute

#### Request

**Method:** `GET`

**URL:** `/portfolio` or `/portfolio?refresh=true`

**Query Parameters:**
- `refresh` (optional): Boolean - If `true`, bypass cache and fetch fresh prices from yfinance. Default: `false`

**Headers:**
```
Authorization: Bearer <clerk_jwt_token>
```

#### Response

**Status:** `200 OK`

**Response Model:** `PortfolioResponse`

```json
{
  "holdings": [
    {
      "ticker": "AMD",
      "name": "ADVANCED MICRO DEVICES INC COM",
      "shares": 145.0,
      "cost_basis": 17691.71,
      "market_value": 30563.1,
      "gain_loss_pct": 72.75,
      "current_price": 210.78,
      "pe_ratio": 110.936844,
      "percent_of_portfolio": 15.41
    },
    {
      "ticker": "META",
      "name": "META PLATFORMS INC CLASS A COMMON STOCK",
      "shares": 45.21538,
      "cost_basis": 12616.51,
      "market_value": 29129.1,
      "gain_loss_pct": 130.88,
      "current_price": 644.23,
      "pe_ratio": 28.531,
      "percent_of_portfolio": 14.69
    }
  ],
  "total_market_value": 198292.6,
  "total_cost_basis": 119025.9,
  "total_gain_loss_pct": 66.6,
  "detected_format": "chase",
  "excluded_items": [
    {
      "ticker": "VMFXX",
      "reason": "cash_equivalent"
    }
  ],
  "prices_cached": true,
  "cache_ttl_minutes": 60
}
```

**Response Fields:**
- `holdings`: Array of portfolio holdings with all calculated values
  - `ticker`: Stock ticker symbol
  - `name`: Company name
  - `shares`: Number of shares owned
  - `cost_basis`: Total cost basis for the position
  - `market_value`: Current market value (shares × current_price)
  - `gain_loss_pct`: Gain/loss percentage ((market_value - cost_basis) / cost_basis × 100)
  - `current_price`: Current stock price (from cache or yfinance)
  - `pe_ratio`: P/E ratio (trailing PE or forward PE)
  - `percent_of_portfolio`: Percentage of total portfolio value
- `total_market_value`: Sum of all market values
- `total_cost_basis`: Sum of all cost bases
- `total_gain_loss_pct`: Overall portfolio gain/loss percentage
- `detected_format`: `"chase"` or `"generic"`
- `excluded_items`: Array of excluded items (cash equivalents)
- `prices_cached`: Boolean - `true` if prices came from cache, `false` if force refreshed
- `cache_ttl_minutes`: Cache time-to-live in minutes (60)

**Holdings are sorted by `percent_of_portfolio` descending.**

#### Error Responses

**401 Unauthorized:**
```json
{
  "detail": "Missing authentication credentials"
}
```

**404 Not Found:**
```json
{
  "detail": "No saved portfolio found. Please upload a portfolio CSV first."
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error fetching current prices: <error message>"
}
```

---

## Data Flow

### Upload Flow

```
1. User uploads CSV → POST /portfolio/upload
2. API parses CSV (detects format: chase or generic)
3. Extracts holdings (ticker, name, shares, cost_basis)
4. Excludes cash equivalents
5. Saves to Supabase (portfolios table)
6. Returns static data (no price fetching)
```

### Retrieve Flow

```
1. User requests portfolio → GET /portfolio
2. API retrieves saved portfolio from Supabase
3. Checks price_cache table for cached prices
   - If cache is fresh (< 1 hour old) → use cached prices
   - If cache is stale or missing → fetch from yfinance and update cache
4. Calculates dynamic values:
   - market_value = shares × current_price
   - gain_loss_pct = ((market_value - cost_basis) / cost_basis) × 100
   - percent_of_portfolio = (market_value / total_market_value) × 100
5. Returns enriched portfolio data with cache metadata
```

### Force Refresh Flow

```
1. User requests portfolio with refresh → GET /portfolio?refresh=true
2. API retrieves saved portfolio from Supabase
3. Bypasses cache → fetches fresh prices from yfinance for ALL tickers
4. Updates price_cache table with new prices
5. Calculates dynamic values and returns enriched portfolio
```

---

## Cash Equivalents

The following tickers are automatically excluded from portfolio visualization:

- `VMFXX` - Vanguard Federal Money Market
- `QACDS` - Chase Deposit Sweep
- `QDERQ` - Chase IRA Deposit Sweep
- `SPAXX` - Fidelity Government Money Market
- `FDRXX` - Fidelity Money Market
- `SWVXX` - Schwab Value Advantage Money

Excluded items are returned in the `excluded_items` array with reason `"cash_equivalent"`.

---

## Price Caching

**Prices are cached for 1 hour** to reduce API calls to yfinance.

### How it Works

1. **Cache Table:** Prices are stored in `price_cache` table (shared across all users)
2. **Cache TTL:** 1 hour - prices older than this are considered stale
3. **On GET /portfolio:**
   - Fresh cache (< 1 hour) → use cached prices (fast)
   - Stale/missing cache → fetch from yfinance and update cache
4. **Force Refresh:** Use `?refresh=true` to bypass cache and fetch fresh prices

### Benefits

- **Fast portfolio updates:** Adding/editing holdings uses cached prices
- **Shared cache:** Same AAPL price cached for all users
- **Reduced API calls:** ~95% fewer yfinance calls
- **Manual refresh:** Users can force refresh when needed

### Frontend Strategy

```javascript
// Normal load - uses cached prices (fast)
GET /portfolio

// After adding/editing a holding - uses cached prices
// percent_of_portfolio will still be recalculated correctly
GET /portfolio

// User clicks "Refresh Prices" button - forces fresh prices
GET /portfolio?refresh=true
```

---

## Price Data Source

**Current Implementation:** Uses yfinance exclusively for fetching current stock prices and P/E ratios.

- **Price:** Fetched via `yfinance_service.get_current_price()`
- **P/E Ratio:** Fetched via `yfinance_service.fetch_stock_info()` (trailing PE or forward PE)
- **Company Name:** Included in response when available

**Note:** If price cannot be fetched for a ticker, the holding will be included with `null` values for price-dependent fields (`market_value`, `gain_loss_pct`, `current_price`, `pe_ratio`, `percent_of_portfolio`).

---

## Database Schema

Portfolios are stored in the `portfolios` table:

- `id` (UUID, primary key)
- `user_id` (TEXT, unique, foreign key to users.clerk_user_id)
- `holdings` (JSONB) - Array of holdings with ticker, name, shares, cost_basis
- `excluded_items` (JSONB) - Array of excluded items
- `detected_format` (TEXT) - "chase" or "generic"
- `total_cost_basis` (NUMERIC)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)

**One portfolio per user:** Each user can have only one saved portfolio. Uploading a new CSV replaces the existing portfolio.

---

## Example Usage

### Upload Chase CSV

```bash
curl -X POST "https://api.example.com/portfolio/upload?format=auto" \
  -H "Authorization: Bearer <token>" \
  -F "file=@chase_portfolio.csv"
```

### Upload Generic CSV

```bash
curl -X POST "https://api.example.com/portfolio/upload?format=generic" \
  -H "Authorization: Bearer <token>" \
  -F "file=@my_portfolio.csv"
```

### Retrieve Portfolio

```bash
curl -X GET "https://api.example.com/portfolio" \
  -H "Authorization: Bearer <token>"
```

---

## Frontend Integration Notes

1. **Upload Flow:**
   - User uploads CSV via file input
   - Send to `POST /portfolio/upload` with form-data
   - Display static data (holdings, total_cost_basis)
   - Portfolio is automatically saved

2. **Display Flow:**
   - Call `GET /portfolio` to retrieve saved portfolio
   - Display holdings with all dynamic values
   - Holdings are pre-sorted by `percent_of_portfolio` descending
   - Handle `null` values gracefully (price fetch failures)

3. **Error Handling:**
   - 404: Prompt user to upload portfolio first
   - 400: Show CSV format error message
   - 500: Show generic error, suggest retry

4. **Refresh Strategy:**
   - Call `GET /portfolio` when user views portfolio page
   - Prices are fetched fresh each time (real-time)
   - Consider caching on frontend for short periods if needed

---

## Rate Limiting

Both endpoints share the same rate limits:
- **Per user:** 30 requests/minute
- **Global:** 200 requests/minute

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Limit per time window
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Time when limit resets

---

## Local Development

When `ENVIRONMENT=local`, authentication is bypassed:
- No token required
- Returns mock user: `{ sub: 'local-dev-user', email: 'dev@localhost' }`

Example:
```bash
ENVIRONMENT=local curl http://localhost:8080/portfolio
```

