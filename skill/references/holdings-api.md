# Holdings CRUD API Documentation

## Overview

The Holdings API allows users to manage individual portfolio holdings through CRUD operations. Users can add, retrieve, update, and delete individual holdings without needing to upload a CSV file.

**Key Features:**
- Add holdings with optional shares/cost_basis (can be 0 initially)
- Get individual holdings
- Update shares, cost_basis, or company name
- Delete holdings
- Automatic company name fetching from yfinance
- Portfolio auto-creation if it doesn't exist

---

## Endpoints

### 1. GET /portfolio/holdings

Get a single holding from the user's portfolio.

**Authentication:** Required (Bearer token)

**Rate Limits:**
- Per user: 30 requests/minute
- Global: 200 requests/minute

#### Request

**Method:** `GET`

**URL:** `/portfolio/holdings?ticker=AAPL`

**Query Parameters:**
- `ticker` (required): Stock ticker symbol (e.g., "AAPL", "MSFT")

**Headers:**
```
Authorization: Bearer <clerk_jwt_token>
```

#### Response

**Status:** `200 OK`

**Response Model:** `HoldingResponse`

```json
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "shares": 100.0,
  "cost_basis": 15000.0,
  "message": "Holding retrieved successfully"
}
```

**Response Fields:**
- `ticker`: Stock ticker symbol
- `name`: Company name (or null if not available)
- `shares`: Number of shares owned
- `cost_basis`: Total cost basis for the position
- `message`: Success message

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
  "detail": "Holding with ticker AAPL not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error retrieving holding: <error message>"
}
```

---

### 2. POST /portfolio/holdings

Add a new holding to the user's portfolio.

**Authentication:** Required (Bearer token)

**Rate Limits:**
- Per user: 30 requests/minute
- Global: 200 requests/minute

#### Request

**Method:** `POST`

**URL:** `/portfolio/holdings?ticker=AAPL`

**Query Parameters:**
- `ticker` (required): Stock ticker symbol (e.g., "AAPL", "MSFT")

**Headers:**
```
Authorization: Bearer <clerk_jwt_token>
Content-Type: application/json
```

**Body (optional):**
```json
{
  "name": "Apple Inc.",     // Optional - will fetch from yfinance if not provided
  "shares": 0.0,            // Optional - defaults to 0 (can be 0 initially)
  "cost_basis": 0.0         // Optional - defaults to 0 (can be 0 initially)
}
```

**Note:** Body can be empty `{}` or omitted entirely. Shares and cost_basis can be 0 initially - user can edit them later.

#### Response

**Status:** `200 OK`

**Response Model:** `HoldingResponse`

```json
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "shares": 0.0,
  "cost_basis": 0.0,
  "message": "Holding added successfully"
}
```

**Response Fields:**
- `ticker`: Stock ticker symbol (uppercase)
- `name`: Company name (fetched from yfinance if not provided)
- `shares`: Number of shares (defaults to 0 if not provided)
- `cost_basis`: Total cost basis (defaults to 0 if not provided)
- `message`: Success message

#### Error Responses

**400 Bad Request:**
```json
{
  "detail": "Holding with ticker AAPL already exists. Use PUT to update."
}
```

```json
{
  "detail": "Shares cannot be negative"
}
```

```json
{
  "detail": "Cost basis cannot be negative"
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
  "detail": "Error adding holding: <error message>"
}
```

#### Example Usage

**Minimal request (just ticker):**
```bash
curl -X POST "https://api.example.com/portfolio/holdings?ticker=AAPL" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{}"
```

**With shares and cost_basis:**
```bash
curl -X POST "https://api.example.com/portfolio/holdings?ticker=AAPL" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shares": 100,
    "cost_basis": 15000
  }'
```

---

### 3. PUT /portfolio/holdings

Update an existing holding in the user's portfolio.

**Returns calculated values for the updated holding and recalculates `percent_of_portfolio` for ALL holdings.**

Uses cached prices (1-hour TTL) for calculations - no need to call `GET /portfolio` afterward.

**Authentication:** Required (Bearer token)

**Rate Limits:**
- Per user: 30 requests/minute
- Global: 200 requests/minute

#### Request

**Method:** `PUT`

**URL:** `/portfolio/holdings?ticker=AAPL`

**Query Parameters:**
- `ticker` (required): Stock ticker symbol to update

**Headers:**
```
Authorization: Bearer <clerk_jwt_token>
Content-Type: application/json
```

**Body (all fields optional):**
```json
{
  "shares": 150.0,          // Optional - update shares
  "cost_basis": 22500.0,    // Optional - update cost basis
  "name": "Apple Inc."      // Optional - update company name
}
```

**Note:** At least one field must be provided.

#### Response

**Status:** `200 OK`

**Response Model:** `HoldingUpdateResponse`

```json
{
  "updated_holding": {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "shares": 150.0,
    "cost_basis": 22500.0,
    "market_value": 37500.0,
    "gain_loss_pct": 66.67,
    "current_price": 250.0,
    "pe_ratio": 28.5,
    "percent_of_portfolio": 25.0
  },
  "holdings": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "shares": 150.0,
      "cost_basis": 22500.0,
      "market_value": 37500.0,
      "gain_loss_pct": 66.67,
      "current_price": 250.0,
      "pe_ratio": 28.5,
      "percent_of_portfolio": 25.0
    },
    {
      "ticker": "MSFT",
      "name": "Microsoft Corporation",
      "shares": 100.0,
      "cost_basis": 30000.0,
      "market_value": 45000.0,
      "gain_loss_pct": 50.0,
      "current_price": 450.0,
      "pe_ratio": 35.2,
      "percent_of_portfolio": 30.0
    }
  ],
  "total_market_value": 150000.0,
  "total_cost_basis": 100000.0,
  "total_gain_loss_pct": 50.0,
  "message": "Holding updated successfully"
}
```

**Response Fields:**
- `updated_holding`: The updated holding with all calculated fields:
  - `ticker`: Stock ticker symbol
  - `name`: Company name
  - `shares`: Updated number of shares
  - `cost_basis`: Updated cost basis
  - `market_value`: shares × current_price
  - `gain_loss_pct`: ((market_value - cost_basis) / cost_basis) × 100
  - `current_price`: Current stock price (from cache)
  - `pe_ratio`: P/E ratio (from cache)
  - `percent_of_portfolio`: Percentage of total portfolio value
- `holdings`: ALL holdings with recalculated `percent_of_portfolio` (sorted by percent descending)
- `total_market_value`: Sum of all market values
- `total_cost_basis`: Sum of all cost bases
- `total_gain_loss_pct`: Overall portfolio gain/loss percentage
- `message`: Success message

**Note:** Prices come from cache (1-hour TTL). Use `GET /portfolio?refresh=true` if you need fresh prices.

#### Error Responses

**400 Bad Request:**
```json
{
  "detail": "No fields provided to update"
}
```

```json
{
  "detail": "Shares cannot be negative"
}
```

```json
{
  "detail": "Cost basis cannot be negative"
}
```

**401 Unauthorized:**
```json
{
  "detail": "Missing authentication credentials"
}
```

**404 Not Found:**
```json
{
  "detail": "Holding with ticker AAPL not found."
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error updating holding: <error message>"
}
```

#### Example Usage

**Update shares only:**
```bash
curl -X PUT "https://api.example.com/portfolio/holdings?ticker=AAPL" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shares": 150
  }'
```

**Update shares and cost_basis:**
```bash
curl -X PUT "https://api.example.com/portfolio/holdings?ticker=AAPL" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "shares": 150,
    "cost_basis": 22500
  }'
```

---

### 4. DELETE /portfolio/holdings

Delete a holding from the user's portfolio.

**Authentication:** Required (Bearer token)

**Rate Limits:**
- Per user: 30 requests/minute
- Global: 200 requests/minute

#### Request

**Method:** `DELETE`

**URL:** `/portfolio/holdings?ticker=AAPL`

**Query Parameters:**
- `ticker` (required): Stock ticker symbol to delete

**Headers:**
```
Authorization: Bearer <clerk_jwt_token>
```

#### Response

**Status:** `200 OK`

```json
{
  "message": "Holding AAPL deleted successfully"
}
```

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
  "detail": "Holding with ticker AAPL not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error deleting holding: <error message>"
}
```

#### Example Usage

```bash
curl -X DELETE "https://api.example.com/portfolio/holdings?ticker=AAPL" \
  -H "Authorization: Bearer <token>"
```

---

## Data Models

### HoldingCreateRequest

Request body for creating a holding (all fields optional since ticker is in query param):

```typescript
{
  name?: string;        // Optional - will fetch from yfinance if not provided
  shares?: number;      // Optional - defaults to 0
  cost_basis?: number;  // Optional - defaults to 0
}
```

### HoldingUpdateRequest

Request body for updating a holding (all fields optional):

```typescript
{
  shares?: number;      // Optional - update shares
  cost_basis?: number;  // Optional - update cost basis
  name?: string;        // Optional - update company name
}
```

### HoldingResponse

Response model for GET and POST holding operations:

```typescript
{
  ticker: string;      // Stock ticker symbol
  name: string | null; // Company name (or null)
  shares: number;      // Number of shares
  cost_basis: number;  // Total cost basis
  message: string;     // Success message
}
```

### HoldingUpdateResponse

Response model for PUT /portfolio/holdings:

```typescript
{
  // The updated holding with all calculated fields
  updated_holding: {
    ticker: string;
    name: string | null;
    shares: number;
    cost_basis: number;
    market_value: number | null;      // shares × current_price
    gain_loss_pct: number | null;     // ((market_value - cost_basis) / cost_basis) × 100
    current_price: number | null;     // From price cache
    pe_ratio: number | null;          // From price cache
    percent_of_portfolio: number | null; // (market_value / total_market_value) × 100
  };
  
  // ALL holdings with recalculated percentages
  holdings: Array<{
    ticker: string;
    name: string | null;
    shares: number;
    cost_basis: number;
    market_value: number | null;
    gain_loss_pct: number | null;
    current_price: number | null;
    pe_ratio: number | null;
    percent_of_portfolio: number | null;
  }>;
  
  // Portfolio totals
  total_market_value: number | null;
  total_cost_basis: number;
  total_gain_loss_pct: number | null;
  message: string;
}
```

---

## Workflow Examples

### Adding a Holding

1. **Add holding with just ticker:**
   ```
   POST /portfolio/holdings?ticker=AAPL
   Body: {}
   ```
   - Creates holding with shares=0, cost_basis=0
   - Fetches company name from yfinance

2. **Edit to add shares and cost_basis:**
   ```
   PUT /portfolio/holdings?ticker=AAPL
   Body: {
     "shares": 100,
     "cost_basis": 15000
   }
   ```

3. **Refresh portfolio to see dynamic values:**
   ```
   GET /portfolio
   ```
   - Returns portfolio with market_value, gain_loss_pct, etc. calculated

### Complete CRUD Flow

```javascript
// 1. Add holding
POST /portfolio/holdings?ticker=AAPL
→ Returns: { ticker: "AAPL", shares: 0, cost_basis: 0, ... }

// 2. Update with shares/cost_basis - now returns ALL data!
PUT /portfolio/holdings?ticker=AAPL
Body: { shares: 100, cost_basis: 15000 }
→ Returns: {
     updated_holding: { ticker: "AAPL", shares: 100, market_value: 25000, ... },
     holdings: [ ... all holdings with recalculated percentages ... ],
     total_market_value: 150000,
     total_cost_basis: 100000,
     total_gain_loss_pct: 50.0,
     message: "..."
   }
// No need to call GET /portfolio - all data is in the response!

// 3. Get single holding (static data only)
GET /portfolio/holdings?ticker=AAPL
→ Returns: { ticker: "AAPL", shares: 100, cost_basis: 15000, ... }

// 4. Get full portfolio with dynamic values (if needed)
GET /portfolio
→ Returns: Full portfolio with market_value, gain_loss_pct, etc.

// 5. Delete holding
DELETE /portfolio/holdings?ticker=AAPL
→ Returns: { message: "Holding AAPL deleted successfully" }
```

---

## Frontend Integration Notes

### 1. Adding Holdings

**Initial Add (Empty):**
- User searches/selects ticker
- Call `POST /portfolio/holdings?ticker=AAPL` with empty body
- Holding created with shares=0, cost_basis=0
- Show success message

**Adding Shares/Cost Basis:**
- User enters shares and cost_basis in form
- Call `PUT /portfolio/holdings?ticker=AAPL` with shares/cost_basis
- After success, call `GET /portfolio` to refresh with dynamic values

### 2. Editing Holdings

**Update Flow:**
- User edits shares/cost_basis in form
- Call `PUT /portfolio/holdings?ticker=AAPL` with updates
- Response includes:
  - `updated_holding` with market_value, gain_loss_pct, current_price, pe_ratio, percent_of_portfolio
  - `holdings` array with ALL holdings and recalculated percent_of_portfolio
  - Portfolio totals
- **No need to call `GET /portfolio`** - all data is in the PUT response!

**Example:**
```javascript
const response = await updateHolding('AAPL', { shares: 100, cost_basis: 15000 });
// response.updated_holding has all calculated values
// response.holdings has all holdings with recalculated percentages
// Use response.holdings to update your portfolio table
```

**Note:** Prices come from cache (1-hour TTL). Use `GET /portfolio?refresh=true` if you need fresh prices.

### 3. Deleting Holdings

**Delete Flow:**
- User clicks delete on a holding
- Call `DELETE /portfolio/holdings?ticker=AAPL`
- After success, call `GET /portfolio` to refresh portfolio
- Remove holding from UI

### 4. Error Handling

- **400 (Already Exists):** Show message "Holding already exists. Use edit instead."
- **404 (Not Found):** Show message "Holding not found."
- **422 (Validation Error):** Show validation error message
- **500 (Server Error):** Show generic error, suggest retry

### 5. State Management

**Recommended Flow for PUT:**
```javascript
// PUT now returns all the data you need!
const response = await updateHolding(ticker, { shares: 100, cost_basis: 15000 });

// Use the response directly - no need for GET /portfolio
setPortfolio({
  holdings: response.holdings,
  total_market_value: response.total_market_value,
  total_cost_basis: response.total_cost_basis,
  total_gain_loss_pct: response.total_gain_loss_pct
});

// If you need fresh prices (not cached), use GET with refresh
const freshPortfolio = await getPortfolio({ refresh: true });
```

**Recommended Flow for POST/DELETE:**
```javascript
// After adding or deleting, fetch portfolio to get calculated values
await addHolding(ticker);  // or deleteHolding(ticker)
const portfolio = await getPortfolio();  // Get updated portfolio with calculations
```

### 6. Price Caching

**Prices are cached for 1 hour** to optimize performance:

- `GET /portfolio` → Uses cached prices (fast)
- `GET /portfolio?refresh=true` → Forces fresh prices from yfinance

**When to use refresh:**
- User explicitly clicks "Refresh Prices" button
- After market opens (to get fresh prices)
- If prices seem stale

**When NOT to use refresh:**
- After adding/editing holdings (cached prices are fine)
- Frequent portfolio loads (would hit yfinance rate limits)

---

## Rate Limiting

All endpoints share the same rate limits:
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
ENVIRONMENT=local curl "http://localhost:8080/portfolio/holdings?ticker=AAPL"
```

---

## Notes

1. **Portfolio Auto-Creation:** If user has no portfolio, it's automatically created when adding first holding
2. **Company Name Fetching:** If name not provided, API attempts to fetch from yfinance
3. **Zero Values:** Holdings can be created with shares=0 and cost_basis=0 (user can edit later)
4. **Ticker Format:** Tickers are automatically uppercased (AAPL, not aapl)
5. **Portfolio Refresh:** After any update, call `GET /portfolio` to recalculate dynamic values
6. **Unique Constraint:** Only one holding per ticker per user (enforced by database)

