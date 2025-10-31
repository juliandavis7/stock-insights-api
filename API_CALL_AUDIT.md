# FMP API Call Audit - All Endpoints

## 🔍 Comprehensive Analysis of FMP API Usage

Updated: October 31, 2025

---

## 📊 Summary Table

| Endpoint | Current FMP Calls | Duplicates Found | Optimized Calls | Savings |
|----------|------------------|------------------|-----------------|---------|
| `/metrics` | ~~8~~ → 6 | ✅ Fixed | 6 | -25% |
| `/charts` | 3 | ✅ None | 3 | 0% |
| `/financials` | 3 | 🔴 **1 duplicate** | 2 | **-33%** |
| `/projections` (GET) | 1 | ✅ None | 1 | 0% |
| `/projections` (POST) | 1-2 | ✅ None | 1-2 | 0% |
| `/info` | 1 | ✅ None | 1 | 0% |

**Total Optimization Potential: 2 redundant calls eliminated across all endpoints**

---

## 1️⃣ `/metrics` Endpoint ✅ OPTIMIZED

**Status:** Already optimized (just completed)

### FMP API Calls (6 total):
1. `fetch_company_profile` - Company profile API
2. `fetch_current_year_data` - Income statement (limit=1)
3. `fetch_analyst_estimates` - Annual estimates API
4. `fetch_quarterly_income_statement` - Quarterly income API
5. `fetch_annual_income_statement` - Annual income API
6. `fetch_quarterly_analyst_estimates` - Quarterly estimates API

**Result:** ✅ No duplicates remaining

---

## 2️⃣ `/charts` Endpoint ✅ NO ISSUES

**Status:** No optimization needed

### FMP API Calls (3 total):
1. `fetch_estimates_data(ticker, mode)` - Quarterly analyst estimates API
2. `fetch_income_statement_data(ticker, mode)` - Quarterly income statement API
3. `fetch_cash_flow_data(ticker, mode)` - Quarterly cash flow API

### Analysis:
- Each call fetches different data sources
- No duplicates detected
- All three are necessary for chart display

**Result:** ✅ Already optimal

---

## 3️⃣ `/financials` Endpoint 🔴 NEEDS OPTIMIZATION

**Status:** DUPLICATE FOUND - Can reduce from 3 to 2 calls

### Current FMP API Calls (3 with 1 duplicate):

**Line 357 in api.py:**
```python
quarterly_data = fmp_service.fetch_quarterly_income_statement(ticker.upper())
```

**Lines 438-440 in api.py (inside estimates calculation):**
```python
# Get quarterly data and estimates from FMP
quarterly_data = fmp_service.fetch_quarterly_income_statement(ticker)  # ⚠️ DUPLICATE!
quarterly_estimates = fmp_service.fetch_quarterly_analyst_estimates(ticker)
```

### The Problem:
1. Line 357: Fetches `quarterly_data` for historical data aggregation
2. Line 439: Fetches `quarterly_data` AGAIN for estimates calculation
3. Line 440: Fetches `quarterly_estimates` (this is unique, not a duplicate)

### Why It's Redundant:
Both calls fetch the EXACT SAME quarterly income statement data. The data fetched on line 357 could be reused on line 439.

### Optimization:
```python
# Fetch once at line 357
quarterly_data = fmp_service.fetch_quarterly_income_statement(ticker.upper())

# ... historical data processing ...

# Reuse on line 439 instead of fetching again
# quarterly_data = fmp_service.fetch_quarterly_income_statement(ticker)  # ❌ Remove this
quarterly_estimates = fmp_service.fetch_quarterly_analyst_estimates(ticker)

# Use already-fetched quarterly_data
if quarterly_data and quarterly_estimates:
    # ... continue with existing logic ...
```

**Savings:** 1 API call per request = **33% reduction**

---

## 4️⃣ `/projections` (GET) Endpoint ✅ NO ISSUES

**Status:** No optimization needed

### FMP API Calls (1 total):
1. `fetch_quarterly_income_statement` - Called by `get_stock_current_data()` to get shares outstanding

### Analysis:
- Single API call
- No duplicates
- Necessary data fetch

**Result:** ✅ Already optimal

---

## 5️⃣ `/projections` (POST) Endpoint ✅ NO ISSUES

**Status:** No optimization needed (smart fallback logic already in place)

### FMP API Calls (1-2 total, conditional):

**First Call (always):**
1. `fetch_current_year_data` - Gets revenue, net_income, EPS (line 130 in projection_service.py)

**Second Call (conditional):**
2. `fetch_quarterly_income_statement` - Only if shares_outstanding not in current_data (line 155)

### Analysis:
- Uses smart fallback logic
- Only fetches quarterly data if needed
- No unnecessary duplicates
- Well-optimized already

**Result:** ✅ Already optimal

---

## 6️⃣ `/info` Endpoint ✅ NO ISSUES

**Status:** No optimization needed

### FMP API Calls (1 total, conditional):
1. `fetch_quarterly_income_statement` - To get shares outstanding (lines 585-590)
   - Only called if yfinance doesn't have the data
   - Smart fallback strategy

**Result:** ✅ Already optimal

---

## 🎯 Optimization Action Items

### Priority 1: Fix `/financials` Endpoint 🔴
**Impact:** 33% reduction in FMP calls for this endpoint

**Changes Needed:**
- File: `api.py`
- Lines: 357, 439
- Action: Remove duplicate fetch on line 439, reuse variable from line 357

**Estimated Time:** 5 minutes
**Complexity:** Low

---

## 📈 Overall Impact After All Optimizations

### Before All Optimizations:
- `/metrics`: 8 calls
- `/charts`: 3 calls
- `/financials`: 3 calls
- `/projections` (GET): 1 call
- `/projections` (POST): 1-2 calls

**Total potential calls per full workflow:** ~16-17 calls

### After All Optimizations:
- `/metrics`: 6 calls ✅
- `/charts`: 3 calls ✅
- `/financials`: 2 calls (pending)
- `/projections` (GET): 1 call ✅
- `/projections` (POST): 1-2 calls ✅

**Total optimized calls per full workflow:** ~13-14 calls

**Overall Savings: 3 API calls (~18% reduction) across all endpoints**

---

## 💰 Cost-Benefit Analysis

### FMP API Limit: 300 calls/minute

**Maximum Requests Per Minute (if all endpoints hit equally):**

| Scenario | Metrics | Charts | Financials | Total Load | Max Req/Min |
|----------|---------|--------|------------|------------|-------------|
| **Before** | 8 | 3 | 3 | 14 avg | ~21 req/min |
| **After** | 6 | 3 | 2 | 11 avg | ~27 req/min |

**Result: ~28% increase in throughput capacity! 🚀**

---

## ✅ Next Steps

1. **Immediate:** Fix `/financials` endpoint duplicate (5 min task)
2. **Testing:** Verify all endpoints still return correct data
3. **Monitoring:** Add logging to track actual FMP API usage
4. **Rate Limiting:** Implement SlowAPI with correct per-endpoint limits

---

## 📝 Notes

- All endpoints that were already optimal have good reason for their API calls
- The main issues were duplicates, not unnecessary calls
- Smart fallback logic is already in place in several services
- This audit focused on FMP API calls only (not yfinance calls)

