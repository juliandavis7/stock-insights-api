"""
Core scraping logic for stock data.

This module handles scraping a single stock and returning the data.
Job-specific logic (looping through stocks, checking cache) stays in job/job.py.
"""

import os
import re
import time
import traceback
from datetime import datetime

from dotenv import load_dotenv
from playwright.async_api import async_playwright
import yfinance as yf

from core.supabase_client import get_supabase_client
from job.validation import validate_stock_data

# Load environment variables
load_dotenv()

# Base URL for the stock data website
BASE_URL = os.getenv("BASE_URL", "").rstrip('/')


def get_last_earnings_date(ticker):
    """
    Get the most recent earnings date for a stock using yfinance.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        datetime object representing the last earnings date, or None if not available
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Try multiple methods to get earnings date
        # Method 1: Try calendar (can be DataFrame or dict)
        try:
            calendar = stock.calendar
            if calendar is not None:
                # Check if calendar is a DataFrame
                if hasattr(calendar, 'empty') and not calendar.empty:
                    # Calendar is a DataFrame, check for earnings dates
                    if 'Earnings Date' in calendar.columns:
                        earnings_dates = calendar['Earnings Date'].dropna()
                        if len(earnings_dates) > 0:
                            # Get the most recent earnings date
                            last_date = earnings_dates.iloc[0]
                            if isinstance(last_date, str):
                                # Parse string date
                                return datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                            elif hasattr(last_date, 'to_pydatetime'):
                                return last_date.to_pydatetime()
                # Check if calendar is a dict
                elif isinstance(calendar, dict):
                    # Look for earnings date in dict
                    if 'Earnings Date' in calendar:
                        earnings_date = calendar['Earnings Date']
                        if earnings_date:
                            if isinstance(earnings_date, list) and len(earnings_date) > 0:
                                earnings_date = earnings_date[0]
                            if isinstance(earnings_date, str):
                                try:
                                    return datetime.fromisoformat(earnings_date.replace('Z', '+00:00'))
                                except:
                                    pass
        except Exception as e:
            print(f"⚠️ Could not get earnings date from calendar: {e}")
        
        # Method 2: Try info dict
        try:
            info = stock.info
            if info:
                # Check for various earnings date fields
                earnings_fields = [
                    'mostRecentQuarter',
                    'earningsQuarterlyGrowth',
                    'earningsDate',
                    'exDividendDate'
                ]
                for field in earnings_fields:
                    if field in info and info[field]:
                        date_value = info[field]
                        if isinstance(date_value, (int, float)):
                            # Unix timestamp
                            return datetime.fromtimestamp(date_value)
                        elif isinstance(date_value, str):
                            try:
                                return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                            except:
                                pass
        except Exception as e:
            print(f"⚠️ Could not get earnings date from info: {e}")
        
        print(f"⚠️ Could not determine last earnings date for {ticker}")
        return None
    except Exception as e:
        print(f"⚠️ Error fetching earnings date for {ticker}: {e}")
        return None


def get_cached_data(ticker):
    """
    Get cached stock data from Supabase.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary with cached data or None if not found
    """
    try:
        supabase = get_supabase_client()
        result = supabase.table('stock_data').select('*').eq('ticker', ticker).single().execute()
        
        if result.data:
            return result.data
        return None
    except Exception as e:
        # If no row found, supabase-py raises an exception with code PGRST116
        # This is expected when there's no cached data - handle silently
        error_str = str(e)
        if ('PGRST116' in error_str or 
            'Cannot coerce the result to a single JSON object' in error_str or
            'No rows' in error_str or 
            'not found' in error_str.lower() or
            'contains 0 rows' in error_str.lower()):
            return None
        # Only print error for unexpected errors
        print(f"⚠️ Error fetching cached data for {ticker}: {e}")
        return None


def upsert_stock_data(ticker, search_metrics=None, income_statement=None, projections=None):
    """
    Upsert stock data into Supabase.
    
    Args:
        ticker: Stock ticker symbol
        search_metrics: Search page metrics (dict or None)
        income_statement: Income statement data (dict or None)
        projections: Projections data (dict or None)
    """
    try:
        supabase = get_supabase_client()
        
        data = {
            'ticker': ticker,
            'updated_at': datetime.now().isoformat()
        }
        
        if search_metrics is not None:
            data['search_metrics'] = search_metrics
        if income_statement is not None:
            data['income_statement'] = income_statement
        if projections is not None:
            data['projections'] = projections
        
        result = supabase.table('stock_data').upsert(data).execute()
        print(f"✅ Successfully cached data for {ticker}")
        return result
    except Exception as e:
        print(f"⚠️ Error caching data for {ticker}: {e}")
        # Don't raise - caching failure shouldn't break the script


async def authenticate(page):
    """Authenticate with the stock data website if credentials are provided."""
    username = os.getenv("STOCK_USER")
    password = os.getenv("STOCK_PASS")
    
    if not username or not password:
        print("No authentication credentials found (STOCK_USER, STOCK_PASS). Proceeding without auth...")
        return False
    
    print("Authentication credentials found. Attempting to login...")
    
    try:
        # Try to navigate to login page - common paths
        login_paths = [
            f"{BASE_URL}/login",
            f"{BASE_URL}/login/",
            f"{BASE_URL}/member-login",
            f"{BASE_URL}/member-login/",
        ]
        
        # First, check if we're already logged in by checking current page
        current_url = page.url
        body_text = await page.inner_text('body')
        
        # If we see login-related text, we need to authenticate
        needs_login = any(keyword in body_text.lower() for keyword in ['login', 'sign in', 'member login', 'password'])
        
        if not needs_login and 'login' not in current_url.lower():
            print("Already authenticated or no login required.")
            return True
        
        # Try to find login form on current page first
        login_form = await page.query_selector('form[action*="login" i], form[id*="login" i], form[class*="login" i]')
        
        if not login_form:
            # Navigate to login page
            login_success = False
            for login_path in login_paths:
                try:
                    print(f"Trying login path: {login_path}")
                    await page.goto(login_path, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    # Check if login form exists
                    login_form = await page.query_selector('form, input[type="password"]')
                    if login_form:
                        login_success = True
                        break
                except:
                    continue
            
            if not login_form:
                print("Could not find login page. Proceeding without authentication...")
                return False
        
        # Find username/email input
        username_selectors = [
            'input[name="username"]',
            'input[name="email"]',
            'input[name="user"]',
            'input[type="email"]',
            'input[id*="user" i]',
            'input[id*="email" i]',
            'input[placeholder*="user" i]',
            'input[placeholder*="email" i]',
        ]
        
        username_input = None
        for selector in username_selectors:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    username_input = elem
                    break
            except:
                continue
        
        # Find password input
        password_input = await page.query_selector('input[type="password"]')
        
        if not username_input or not password_input:
            print("Could not find login form fields. Proceeding without authentication...")
            return False
        
        # Fill in credentials
        print("Filling in credentials...")
        await username_input.click()
        await username_input.fill(username)
        await page.wait_for_timeout(500)
        
        await password_input.click()
        await password_input.fill(password)
        await page.wait_for_timeout(500)
        
        # Find and click submit button
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Login")',
            'button:has-text("Sign in")',
            'button:has-text("Log in")',
            'form button',
        ]
        
        submitted = False
        for selector in submit_selectors:
            try:
                submit_btn = await page.query_selector(selector)
                if submit_btn and await submit_btn.is_visible():
                    await submit_btn.click()
                    submitted = True
                    break
            except:
                continue
        
        if not submitted:
            # Try pressing Enter on password field
            await password_input.press("Enter")
        
        # Wait for navigation or authentication to complete
        print("Waiting for authentication...")
        await page.wait_for_timeout(3000)
        
        # Check if we're redirected or if login was successful
        current_url = page.url
        body_text = await page.inner_text('body')
        
        # If we're no longer on login page or don't see login form, assume success
        if 'login' not in current_url.lower() or 'password' not in body_text.lower():
            print("Authentication successful!")
            return True
        else:
            print("Authentication may have failed. Proceeding anyway...")
            return False
            
    except Exception as e:
        print(f"Authentication error: {e}. Proceeding without authentication...")
        return False


def parse_number(value_str):
    """Parse a number string, handling commas, percentages, and other formatting."""
    if not value_str or value_str == "N/A" or value_str == "-":
        return None
    
    # Remove commas and whitespace
    cleaned = value_str.replace(",", "").replace(" ", "").strip()
    
    # Handle Infinity values (case-insensitive, check before processing)
    cleaned_lower = cleaned.lower()
    if cleaned_lower in ['infinity', 'inf', '-infinity', '-inf']:
        if cleaned_lower.startswith('-'):
            return float('-inf')
        else:
            return float('inf')
    
    # Handle percentages
    if "%" in cleaned:
        cleaned = cleaned.replace("%", "")
        # Check again for infinity after removing %
        cleaned_lower = cleaned.lower()
        if cleaned_lower in ['infinity', 'inf', '-infinity', '-inf']:
            if cleaned_lower.startswith('-'):
                return float('-inf')
            else:
                return float('inf')
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    # Handle currency symbols (preserve negative sign)
    # Check for negative before removing $
    is_negative = cleaned.startswith('-')
    if "$" in cleaned:
        cleaned = cleaned.replace("$", "")
    # Restore negative sign if it was removed
    if is_negative and not cleaned.startswith('-'):
        cleaned = '-' + cleaned
    
    # Handle multipliers (B for billions, M for millions, K for thousands)
    multiplier = 1
    if cleaned.endswith("B"):
        multiplier = 1e9
        cleaned = cleaned[:-1]
    elif cleaned.endswith("M"):
        multiplier = 1e6
        cleaned = cleaned[:-1]
    elif cleaned.endswith("K"):
        multiplier = 1e3
        cleaned = cleaned[:-1]
    
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


async def extract_metrics_from_dom_structure(page, metric_patterns, metrics):
    """
    Extract metrics using DOM structure (div.list > div.stock_name + a.stock_number).
    This handles cases where metric labels and values are in separate DOM elements.
    """
    
    try:
        # Find all div.list containers
        list_containers = await page.query_selector_all('div.list')
        print(f"Found {len(list_containers)} div.list containers for DOM extraction")
        
        for container in list_containers:
            try:
                # Get metric label from stock_name
                stock_name_elem = await container.query_selector('div.stock_name')
                if not stock_name_elem:
                    continue
                
                metric_label = (await stock_name_elem.inner_text()).strip()
                metric_label_lower = metric_label.lower()
                
                # Get value from stock_number (try both a and div)
                stock_number_elem = await container.query_selector('a.stock_number')
                if not stock_number_elem:
                    stock_number_elem = await container.query_selector('div.stock_number')
                
                if not stock_number_elem:
                    continue
                
                # Try inner_text first, then title attribute
                value_text = (await stock_number_elem.inner_text()).strip()
                if not value_text:
                    value_text = (await stock_number_elem.get_attribute('title') or '').strip()
                
                if not value_text:
                    continue
                
                # Extract numeric value (remove %, spaces, handle negative signs)
                # Keep negative sign, remove %, spaces, commas
                # Preserve negative sign by checking before cleaning
                is_negative = value_text.strip().startswith('-')
                value_str = re.sub(r'[%\s,]', '', value_text)
                # Ensure negative sign is preserved if it was removed
                if is_negative and not value_str.startswith('-'):
                    value_str = '-' + value_str
                value = parse_number(value_str)
                
                if value is None:
                    continue
                
                # Match metric label to metric_key
                for metric_key, patterns in metric_patterns.items():
                    if metric_key in metrics:
                        continue
                    
                    # Check if label matches any pattern for this metric
                    for pattern in patterns:
                        # Extract label part of pattern (everything before the capture group)
                        if r'([\d,]+\.?\d*)' in pattern or r'([+-]?[\d,]+\.?\d*)' in pattern:
                            # Split on capture group
                            label_part = pattern.split(r'([+-]?[\d,]+\.?\d*)')[0] if r'([+-]?[\d,]+\.?\d*)' in pattern else pattern.split(r'([\d,]+\.?\d*)')[0]
                        else:
                            label_part = pattern
                        
                        # Clean up pattern for matching - remove regex anchors and quantifiers
                        label_part = label_part.rstrip(r'[\s\n:]*%?').rstrip()
                        # Remove regex special chars but keep word boundaries and spaces
                        label_part_clean = label_part.replace('^', '').replace('$', '').replace(r'\s+', ' ').replace(r'\s*', ' ').replace(r'\s', ' ')
                        
                        # Try matching the label (case-insensitive)
                        if re.search(label_part_clean, metric_label_lower, re.IGNORECASE):
                            metrics[metric_key] = value
                            break
            except Exception as e:
                continue
    except Exception as e:
        print(f"⚠️ DOM extraction error: {e}")


async def scrape_search_metrics(page, ticker):
    """Scrape metrics from the search page for a given ticker."""
    # Navigate to the search page
    print(f"Navigating to search page...")
    search_url = f"{BASE_URL}/search-stock/"
    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        # If domcontentloaded times out, try with just load
        print(f"domcontentloaded timeout, trying load...")
        try:
            await page.goto(search_url, wait_until="load", timeout=60000)
        except:
            # Last resort: just navigate and wait manually
            print(f"Using fallback navigation...")
            await page.goto(search_url, timeout=60000)
    
    # Wait for React to hydrate and any dynamic content
    await page.wait_for_timeout(5000)
    
    # Check if page loaded correctly
    page_title = await page.title()
    current_url = page.url
    print(f"Page loaded: {page_title} at {current_url}")
    
    # Try multiple strategies to find the search input
    search_input = None
    
    # Strategy 1: Try common input selectors
    search_selectors = [
        'input[type="text"]',
        'input[type="search"]',
        'input[placeholder*="search" i]',
        'input[placeholder*="ticker" i]',
        'input[placeholder*="stock" i]',
        'input[placeholder*="symbol" i]',
        'input[id*="search" i]',
        'input[name*="search" i]',
        'input[class*="search" i]',
        'input[aria-label*="search" i]',
        'input[aria-label*="ticker" i]',
    ]
    
    # Find search input using multiple strategies
    for selector in search_selectors:
        try:
            elements = await page.query_selector_all(selector)
            for elem in elements:
                try:
                    if await elem.is_visible():
                        placeholder = await elem.get_attribute('placeholder') or ''
                        input_id = await elem.get_attribute('id') or ''
                        input_name = await elem.get_attribute('name') or ''
                        aria_label = await elem.get_attribute('aria-label') or ''
                        attrs = (placeholder + input_id + input_name + aria_label).lower()
                        if any(keyword in attrs for keyword in ['search', 'ticker', 'stock', 'symbol']):
                            search_input = elem
                            break
                except:
                    continue
            if search_input:
                break
        except:
            continue
    
    # Strategy 2: Get all inputs and check them
    if not search_input:
        all_inputs = await page.query_selector_all('input')
        for inp in all_inputs:
            try:
                if await inp.is_visible():
                    input_type = await inp.get_attribute('type') or ''
                    if input_type not in ['hidden', 'submit', 'button', 'checkbox', 'radio']:
                        search_input = inp
                        break
            except:
                continue
    
    # Strategy 3: Try to find search via buttons or links
    if not search_input:
        search_buttons = await page.query_selector_all('button, a, [role="button"]')
        for btn in search_buttons:
            try:
                btn_text = await btn.inner_text()
                if btn_text and any(keyword in btn_text.lower() for keyword in ['search', 'go', 'find']):
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    all_inputs = await page.query_selector_all('input')
                    for inp in all_inputs:
                        if await inp.is_visible():
                            search_input = inp
                            break
                    if search_input:
                        break
            except:
                continue
    
    # Strategy 4: Check if URL-based navigation works
    if not search_input:
        try:
            direct_url = f"{BASE_URL}/search-stock/{ticker}"
            await page.goto(direct_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            body_text = await page.inner_text('body')
            if 'mandatory' in body_text.lower() or 'metric' in body_text.lower():
                search_input = "SKIP"  # Skip search, we're already on results page
        except:
            pass
    
    if not search_input:
        raise Exception("Could not find search input field on the page. The page structure may have changed or require authentication.")
    
    # Type the ticker into the search field (skip if direct URL worked)
    if search_input != "SKIP":
        print(f"Searching for ticker: {ticker}")
        await search_input.click()
        await search_input.fill("")
        await search_input.type(ticker, delay=100)
        await page.wait_for_timeout(1000)
        
        # Press Enter to submit
        await search_input.press("Enter")
        
        # Wait for navigation or content update
        await page.wait_for_timeout(3000)
    else:
        print(f"Already on results page for ticker: {ticker}")
    
    # Wait for metrics to appear - try multiple indicators
    print("Waiting for metrics to load...")
    metrics_loaded = False
    wait_selectors = [
        'text=MANDATORY METRICS',
        'text=Mandatory Metrics',
        'text=ADVANCED METRICS',
        'text=Advanced Metrics',
        '[class*="metric" i]',
        '[class*="mandatory" i]',
        '[class*="advanced" i]',
    ]
    
    for selector in wait_selectors:
        try:
            await page.wait_for_selector(selector, timeout=5000)
            metrics_loaded = True
            break
        except:
            continue
    
    if not metrics_loaded:
        # Check if ticker was not found
        body_text = await page.inner_text('body')
        if any(phrase in body_text.lower() for phrase in ['not found', 'no results', 'invalid', 'error']):
            raise Exception(f"Ticker {ticker} not found on {BASE_URL}")
        # Wait a bit more for dynamic content
        await page.wait_for_timeout(3000)
    
    # Extract metrics from the page
    metrics = {}
    
    # Get the full page text
    body_text = await page.inner_text('body')
    
    # Define metric patterns with their possible labels
    # Mandatory Metrics + Advanced Metrics
    metric_patterns = {
        # Mandatory Metrics - PE Ratios
        "ttm_pe": [r'ttm pe[\s:]*([\d,]+\.?\d*)', r'pe \(ttm\)[\s:]*([\d,]+\.?\d*)', r'trailing pe[\s:]*([\d,]+\.?\d*)'],
        "forward_pe": [r'forward pe[\s:]*([\d,]+\.?\d*)', r'forward p/e[\s:]*([\d,]+\.?\d*)'],
        "two_year_forward_pe": [r'2[-\s]?year forward pe[\s:]*([\d,]+\.?\d*)', r'two year forward pe[\s:]*([\d,]+\.?\d*)'],
        
        # Mandatory Metrics - EPS Growth
        "ttm_eps_growth": [r'ttm eps growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'eps growth \(ttm\)[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        "current_year_eps_growth": [
            r'current\s+yr\s+exp\s+eps\s+growth[\s:]*([+-]?[\d,]+\.?\d*)%?',  # "Current yr exp EPS growth"
            r'current\s+year\s+exp\s+eps\s+growth[\s:]*([+-]?[\d,]+\.?\d*)%?',  # "Current year exp EPS growth"
            r'current\s+y[ear]*[.\s]*exp\s+eps\s+growth[\s:]*([+-]?[\d,]+\.?\d*)%?',  # "Current y exp EPS growth" (fallback)
            r'current\s+year\s+eps\s+growth[\s:]*([+-]?[\d,]+\.?\d*)%?',  # "Current year EPS growth"
            r'cy\s+eps\s+growth[\s:]*([+-]?[\d,]+\.?\d*)%?',  # "CY EPS growth"
        ],
        "next_year_eps_growth": [r'next year eps growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'ny eps growth[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        
        # Mandatory Metrics - Revenue Growth
        "ttm_revenue_growth": [r'ttm rev growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'ttm revenue growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'revenue growth \(ttm\)[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        "current_year_revenue_growth": [r'current y[ear]*[.\s]*exp rev growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'current year revenue growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'cy revenue growth[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        "next_year_revenue_growth": [r'next year rev growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'next year revenue growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'ny revenue growth[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        
        # Mandatory Metrics - Margins
        "gross_margin": [r'gross margin[\s:]*([\d,]+\.?\d*)%?'],
        "net_margin": [r'net margin[\s:]*([\d,]+\.?\d*)%?', r'profit margin[\s:]*([\d,]+\.?\d*)%?'],
        
        # Mandatory Metrics - P/S Ratios
        "ttm_ps_ratio": [r'ttm p/s ratio[\s:]*([\d,]+\.?\d*)', r'ttm ps[\s:]*([\d,]+\.?\d*)', r'price to sales \(ttm\)[\s:]*([\d,]+\.?\d*)', r'p/s \(ttm\)[\s:]*([\d,]+\.?\d*)'],
        "forward_ps_ratio": [r'forward p/s ratio[\s:]*([\d,]+\.?\d*)', r'forward ps[\s:]*([\d,]+\.?\d*)', r'forward p/s[\s:]*([\d,]+\.?\d*)'],
        
        # Advanced Metrics - EPS Growth
        "last_year_eps_growth": [r'last year eps growth[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        "ttm_vs_ntm_eps_growth": [r'ttm vs ntm eps growth[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        "current_quarter_eps_growth_vs_previous_year": [r'current quarter eps growth vs previous year[\s:]*([+-]?[\d,]+\.?\d*|-?infinity|-?inf)%?', r'current q[tr]* eps growth vs previous year[\s:]*([+-]?[\d,]+\.?\d*|-?infinity|-?inf)%?'],
        "two_year_stack_exp_eps_growth": [r'2[-\s]?year stack exp eps growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'two year stack exp eps growth[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        
        # Advanced Metrics - Revenue Growth
        "last_year_revenue_growth": [r'last year rev growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'last year revenue growth[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        "ttm_vs_ntm_revenue_growth": [r'ttm vs ntm rev growth[\s:]*([+-]?[\d,]+\.?\d*)%?', r'ttm vs ntm revenue growth[\s:]*([+-]?[\d,]+\.?\d*)%?'],
        "current_quarter_revenue_growth_vs_previous_year": [r'current quarter rev growth vs previous year[\s:]*([+-]?[\d,]+\.?\d*|-?infinity|-?inf)%?', r'current quarter revenue growth vs previous year[\s:]*([+-]?[\d,]+\.?\d*|-?infinity|-?inf)%?', r'current q[tr]* rev growth vs previous year[\s:]*([+-]?[\d,]+\.?\d*|-?infinity|-?inf)%?'],
        "two_year_stack_exp_revenue_growth": [r'2[-\s]?year stack exp rev growth[\s:]*([\d,]+\.?\d*)%?', r'two year stack exp rev growth[\s:]*([\d,]+\.?\d*)%?', r'2[-\s]?year stack exp revenue growth[\s:]*([\d,]+\.?\d*)%?'],
        
        # Advanced Metrics - Valuation Ratios
        "peg_ratio": [r'peg ratio[\s:]*([\d,]+\.?\d*)'],
        "return_on_equity": [r'return on equity[\s:]*([\d,]+\.?\d*)%?', r'roe[\s:]*([\d,]+\.?\d*)%?'],
        "price_to_book": [r'price to book[\s:]*([\d,]+\.?\d*)', r'p/b[\s:]*([\d,]+\.?\d*)', r'pb ratio[\s:]*([\d,]+\.?\d*)'],
        "price_to_free_cash_flow": [r'price to free cash flow[\s:]*([\d,]+\.?\d*)', r'p/fcf[\s:]*([\d,]+\.?\d*)'],
        "free_cash_flow_yield": [r'free cash flow yield[\s:]*([\d,]+\.?\d*)%?', r'fcf yield[\s:]*([\d,]+\.?\d*)%?'],
        
        # Advanced Metrics - Dividends
        "dividend_yield": [r'dividend yield[\s:]*([\d,]+\.?\d*)%?'],
        "dividend_payout_ratio": [r'dividend payout ratio[\s:]*([\d,]+\.?\d*)%?'],
    }
    
    # Extract metrics using DOM structure first (more reliable for structured layouts)
    print("Extracting metrics from DOM structure...")
    await extract_metrics_from_dom_structure(page, metric_patterns, metrics)
    
    # Extract metrics using regex patterns from full body text
    for metric_key, patterns in metric_patterns.items():
        if metric_key in metrics:
            continue
        
        for pattern in patterns:
            matches = re.findall(pattern, body_text, re.IGNORECASE)
            if matches:
                value_str = matches[0]
                value = parse_number(value_str)
                if value is not None:
                    metrics[metric_key] = value
                    break
    
    if len(metrics) == 0:
        raise Exception(f"Could not extract metrics for {ticker}. The page structure may have changed or the ticker may not be available.")
    
    return metrics


async def find_and_use_search_input(page, ticker):
    """Helper function to find search input and enter ticker."""
    search_input = None
    
    # Strategy 0: Try direct selector first (we know it exists from search page)
    try:
        search_input = await page.query_selector('#symbolInput')
        if search_input and await search_input.is_visible():
            print("  Found search input via direct selector: #symbolInput")
    except:
        pass
    
    # Strategy 1: Try common input selectors
    if not search_input:
        search_selectors = [
            'input[type="text"]',
            'input[type="search"]',
            'input[placeholder*="search" i]',
            'input[placeholder*="ticker" i]',
            'input[placeholder*="stock" i]',
            'input[placeholder*="symbol" i]',
            'input[id*="search" i]',
            'input[name*="search" i]',
            'input[class*="search" i]',
            'input[aria-label*="search" i]',
            'input[aria-label*="ticker" i]',
        ]
        
        print("Looking for search input...")
        for selector in search_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    try:
                        is_visible = await elem.is_visible()
                        if is_visible:
                            placeholder = await elem.get_attribute('placeholder') or ''
                            input_id = await elem.get_attribute('id') or ''
                            input_name = await elem.get_attribute('name') or ''
                            aria_label = await elem.get_attribute('aria-label') or ''
                            
                            # Check if it looks like a search input
                            attrs = (placeholder + input_id + input_name + aria_label).lower()
                            if any(keyword in attrs for keyword in ['search', 'ticker', 'stock', 'symbol']):
                                print(f"  Found search input: placeholder='{placeholder}', id='{input_id}', name='{input_name}'")
                                search_input = elem
                                break
                    except:
                        continue
                if search_input:
                    break
            except:
                continue
    
    # Strategy 2: Get all inputs and check them
    if not search_input:
        print("Trying to find any visible input...")
        all_inputs = await page.query_selector_all('input')
        print(f"  Found {len(all_inputs)} total input elements")
        for inp in all_inputs:
            try:
                if await inp.is_visible():
                    placeholder = await inp.get_attribute('placeholder') or ''
                    input_type = await inp.get_attribute('type') or ''
                    # Skip hidden, submit, button inputs
                    if input_type in ['hidden', 'submit', 'button', 'checkbox', 'radio']:
                        continue
                    print(f"  Found visible input: type='{input_type}', placeholder='{placeholder}'")
                    search_input = inp
                    break
            except:
                continue
    
    if not search_input:
        raise Exception("Could not find search input field on the page")
    
    # Type the ticker into the search field
    print(f"Searching for ticker: {ticker}")
    await search_input.click()
    await search_input.fill("")
    await search_input.type(ticker, delay=100)
    await page.wait_for_timeout(1000)
    
    # Press Enter to submit
    await search_input.press("Enter")
    
    # Wait for navigation or content update
    await page.wait_for_timeout(3000)
    
    return True


async def extract_from_div_structure(page, container, years, ticker):
    """Extract income statement data from div-based financial structure."""
    print("Extracting from div-based financial structure...")
    
    # Find all financial rows
    rows = await container.query_selector_all('.financial-row')
    print(f"Found {len(rows)} financial rows")
    
    if len(rows) == 0:
        return None
    
    # Extract years from header row or first row
    year_columns = []
    header_row = rows[0] if rows else None
    if header_row:
        cells = await header_row.query_selector_all('.financial-cell')
        # Skip the first cell (METRIC label), start from index 1
        for i in range(1, len(cells)):
            cell_text = await cells[i].inner_text()
            year_match = re.search(r'\b(20\d{2})\b', cell_text)
            if year_match:
                # Map to value_cells index (i-1 because we skip metric cell)
                year_columns.append((i-1, year_match.group(1)))
                print(f"  Found year {year_match.group(1)} at header index {i}, value cell index {i-1}")
    
    if not year_columns:
        # Use years from parameter - map to value cell indices (starting from 0)
        sorted_years = sorted([int(y) for y in years])[:6]
        year_columns = [(i, str(year)) for i, year in enumerate(sorted_years)]
        print(f"  Using fallback year mapping: {year_columns}")
    
    print(f"Year columns (value_cell_index, year): {year_columns}")
    
    income_data_by_year = {}
    
    # Process each row
    for row_idx, row in enumerate(rows):
        # Get metric name from first cell
        metric_cell = await row.query_selector('.financial-cell.metric')
        if not metric_cell:
            continue
        
        row_label = await metric_cell.inner_text()
        row_label_lower = row_label.lower().strip()
        
        # Skip header rows
        if 'metric' in row_label_lower or row_label_lower == '':
            continue
        
        # Debug logging for R&D row
        if 'r&d' in row_label_lower or 'rd' in row_label_lower or ('research' in row_label_lower and 'development' in row_label_lower):
            print(f"  🔍 Found R&D row at index {row_idx}: '{row_label}'")
        
        # Get all value cells (excluding the metric cell)
        value_cells = await row.query_selector_all('.financial-cell:not(.metric)')
        
        # Extract values for each year
        for col_idx, year in year_columns:
            if col_idx < len(value_cells):
                cell = value_cells[col_idx]
                cell_text = await cell.inner_text()
                original_cell_text = cell_text
                
                # Remove percentage spans if they exist
                percentage_spans = await cell.query_selector_all('.percentage')
                for span in percentage_spans:
                    span_text = await span.inner_text()
                    if span_text:
                        # Remove percentage from cell text
                        cell_text = cell_text.replace(span_text, '').strip()
                
                # Remove percentage changes in parentheses
                cell_text = re.sub(r'\s*\([^)]*\)', '', cell_text).strip()
                
                # Parse value (including negative values)
                value = parse_number(cell_text)
                
                # Store value (including 0 and negative values)
                if value is not None:
                    if year not in income_data_by_year:
                        income_data_by_year[year] = {}
                    
                    # Map row labels to metric names (improved matching)
                    metric_name = None
                    if 'total revenue' in row_label_lower and 'cost' not in row_label_lower:
                        metric_name = 'total_revenue'
                    elif 'cost of revenue' in row_label_lower or ('cost' in row_label_lower and 'revenue' in row_label_lower):
                        metric_name = 'cost_of_revenue'
                    elif 'gross profit' in row_label_lower:
                        metric_name = 'gross_profit'
                    elif 'sg&a' in row_label_lower or 'sga' in row_label_lower or ('selling' in row_label_lower and 'general' in row_label_lower and 'administrative' in row_label_lower):
                        metric_name = 'sga'
                    elif 'r&d' in row_label_lower or 'rd' in row_label_lower or ('research' in row_label_lower and 'development' in row_label_lower):
                        metric_name = 'rnd'
                    elif 'total opex' in row_label_lower or 'total operating expenses' in row_label_lower:
                        metric_name = 'total_opex'
                    elif 'operating income' in row_label_lower:
                        metric_name = 'operating_income'
                    elif 'net income' in row_label_lower:
                        metric_name = 'net_income'
                    elif 'basic eps' in row_label_lower:
                        metric_name = 'basic_eps'
                    elif 'diluted eps' in row_label_lower or 'dilluted eps' in row_label_lower:
                        metric_name = 'diluted_eps'
                    
                    if metric_name:
                        income_data_by_year[year][metric_name] = value
    
    if income_data_by_year:
        return convert_to_requested_format({'data_by_year': income_data_by_year}, ticker, years)
    
    return None


async def scrape_income_statement_metrics(page, ticker):
    """Scrape income statement metrics from the income statement page."""
    print(f"Navigating to income statement page...")
    
    # Navigate to income statement page (without ticker in URL)
    income_statement_url = f"{BASE_URL}/income-statement/"
    try:
        await page.goto(income_statement_url, wait_until="domcontentloaded", timeout=60000)
        print(f"✅ Successfully navigated to income statement page")
    except Exception as e:
        print(f"⚠️ Navigation issue (domcontentloaded), trying load... Error: {e}")
        try:
            await page.goto(income_statement_url, wait_until="load", timeout=60000)
            print(f"✅ Successfully navigated using load strategy")
        except Exception as e2:
            print(f"⚠️ Navigation issue (load), trying basic navigation... Error: {e2}")
            await page.goto(income_statement_url, timeout=60000)
            print(f"✅ Successfully navigated using basic strategy")
    
    # Wait for React to hydrate
    await page.wait_for_timeout(5000)
    
    # Check current URL
    current_url = page.url
    print(f"Current URL: {current_url}")
    
    # Find search input and enter ticker
    try:
        await find_and_use_search_input(page, ticker)
    except Exception as e:
        print(f"❌ Error finding/using search input: {e}")
        raise
    
    # Wait for table to appear after search
    try:
        await page.wait_for_selector('table, [class*="table"], [class*="income"]', timeout=10000)
    except:
        await page.wait_for_timeout(3000)
    
    # Extract income statement data
    income_statement = None  # Will be set by parser or table extraction
    
    # Get page text and extract years
    body_text = await page.inner_text('body')
    year_pattern = r'\b(20\d{2})\b'
    years = sorted(set(re.findall(year_pattern, body_text)))
    
    # Extract metrics from table
    # Based on screenshot, we need: TOTAL REVENUE, COST OF REVENUE, GROSS PROFIT, SG&A, R&D, TOTAL OPEX, OPERATING INCOME, NET INCOME, BASIC EPS, DILUTED EPS
    
    metric_labels = {
        "total_revenue": [r'total revenue[\s:]*\$?([\d,]+)', r'revenue[\s:]*\$?([\d,]+)'],
        "cost_of_revenue": [r'cost of revenue[\s:]*\$?([\d,]+)'],
        "gross_profit": [r'gross profit[\s:]*\$?([\d,]+)'],
        "sga": [r'sg&a[\s:]*\$?([\d,]+)', r'selling.*general.*administrative[\s:]*\$?([\d,]+)'],
        "rd": [r'r&d[\s:]*\$?([\d,]+)', r'research.*development[\s:]*\$?([\d,]+)'],
        "total_opex": [r'total opex[\s:]*\$?([\d,]+)', r'total operating expenses[\s:]*\$?([\d,]+)'],
        "operating_income": [r'operating income[\s:]*\$?([\d,]+)'],
        "net_income": [r'net income[\s:]*\$?([\d,]+)'],
        "basic_eps": [r'basic eps[\s:]*\$?([\d,]+\.?\d*)'],
        "diluted_eps": [r'diluted eps[\s:]*\$?([\d,]+\.?\d*)', r'diluted eps[\s:]*\$?([\d,]+\.?\d*)'],
    }
    
    # Try to extract table data
    try:
        # First, try div-based financial structure (from screenshot)
        financial_container = await page.query_selector('.financials-container, #financial-divs')
        if financial_container:
            income_statement = await extract_from_div_structure(page, financial_container, years, ticker)
            if income_statement and income_statement.get('metrics'):
                return income_statement
        
        # Find all tables
        tables = await page.query_selector_all('table')
        if len(tables) == 0:
            # Try alternative selectors
            tables = await page.query_selector_all('[role="table"], [class*="table"], [class*="grid"], [class*="data"]')
        
        for idx, table in enumerate(tables):
            table_text = await table.inner_text()
            # Check if this looks like the income statement table
            has_revenue = 'revenue' in table_text.lower()
            has_income = 'income' in table_text.lower()
            has_eps = 'eps' in table_text.lower()
            
            if has_revenue and (has_income or has_eps):
                # Extract rows
                rows = await table.query_selector_all('tr')
                
                # Find header row to get year columns
                year_columns = []
                for row_idx, row in enumerate(rows[:10]):
                    cells = await row.query_selector_all('th, td')
                    if len(cells) > 1:
                        first_cell = await cells[0].inner_text()
                        first_cell_lower = first_cell.lower().strip()
                        if 'metric' in first_cell_lower or first_cell.strip() == '':
                            # Extract years from header cells
                            for i in range(1, min(len(cells), 8)):
                                cell_text = await cells[i].inner_text()
                                year_match = re.search(r'\b(20\d{2})\b', cell_text)
                                if year_match:
                                    year_columns.append((i, year_match.group(1)))
                            if year_columns:
                                break
                
                if not year_columns:
                    # Fallback: try to find years in any row
                    for row_idx, row in enumerate(rows[:5]):
                        cells = await row.query_selector_all('th, td')
                        for i, cell in enumerate(cells):
                            cell_text = await cell.inner_text()
                            year_match = re.search(r'\b(20\d{2})\b', cell_text)
                            if year_match and year_match.group(1) not in [y[1] for y in year_columns]:
                                year_columns.append((i, year_match.group(1)))
                        if year_columns:
                            break
                
                if not year_columns:
                    # Use years found in body text
                    sorted_years = sorted([int(y) for y in years])[:6]
                    year_columns = [(i+1, str(year)) for i, year in enumerate(sorted_years)]
                
                income_data_by_year = {}
                
                # Extract data from each row
                for row_idx, row in enumerate(rows):
                    cells = await row.query_selector_all('td, th')
                    if len(cells) < 2:
                        continue
                    
                    # Get row label (first cell)
                    row_label = await cells[0].inner_text()
                    row_label_lower = row_label.lower().strip()
                    
                    # Skip header rows
                    if 'metric' in row_label_lower or row_label_lower == '':
                        continue
                    
                    # Extract values for each year column
                    for col_idx, year in year_columns:
                        if col_idx < len(cells):
                            cell_text = await cells[col_idx].inner_text()
                            original_cell_text = cell_text
                            # Remove percentage changes in parentheses (e.g., "123.45 (5.6%)")
                            cell_text = re.sub(r'\s*\([^)]*\)', '', cell_text).strip()
                            value = parse_number(cell_text)
                            
                            # Store value if it's not None (including 0 and negative values)
                            # Only skip if value is None (couldn't parse)
                            if value is not None:
                                if year not in income_data_by_year:
                                    income_data_by_year[year] = {}
                                
                                # Map row labels to metric names (improved matching)
                                metric_name = None
                                if 'total revenue' in row_label_lower and 'cost' not in row_label_lower:
                                    metric_name = 'total_revenue'
                                elif 'cost of revenue' in row_label_lower or ('cost' in row_label_lower and 'revenue' in row_label_lower):
                                    metric_name = 'cost_of_revenue'
                                elif 'gross profit' in row_label_lower:
                                    metric_name = 'gross_profit'
                                elif 'sg&a' in row_label_lower or 'sga' in row_label_lower or ('selling' in row_label_lower and 'general' in row_label_lower and 'administrative' in row_label_lower):
                                    metric_name = 'sga'
                                elif 'r&d' in row_label_lower or 'rd' in row_label_lower or ('research' in row_label_lower and 'development' in row_label_lower):
                                    metric_name = 'rnd'
                                elif 'total opex' in row_label_lower or 'total operating expenses' in row_label_lower:
                                    metric_name = 'total_opex'
                                elif 'operating income' in row_label_lower:
                                    metric_name = 'operating_income'
                                elif 'net income' in row_label_lower:
                                    metric_name = 'net_income'
                                elif 'basic eps' in row_label_lower:
                                    metric_name = 'basic_eps'
                                elif 'diluted eps' in row_label_lower or 'dilluted eps' in row_label_lower:
                                    metric_name = 'diluted_eps'
                                
                                if metric_name:
                                    income_data_by_year[year][metric_name] = value
                
                if income_data_by_year:
                    income_statement = {'data_by_year': income_data_by_year}
                    print(f"✅ Successfully extracted income statement data for {len(income_data_by_year)} years")
                    print(f"   Years: {list(income_data_by_year.keys())}")
                    break
                else:
                    print(f"⚠️ No data extracted from table {idx + 1}")
    except Exception as e:
        print(f"❌ Error extracting table data: {e}")
        print("Full traceback:")
        traceback.print_exc()
    
    # Fallback: Try regex extraction from body text if table extraction failed
    if income_statement is None or 'data_by_year' not in income_statement or not income_statement.get('data_by_year'):
        print("\n⚠️ Table extraction failed, attempting fallback regex extraction from body text...")
        print(f"   Body text contains 'revenue': {'revenue' in body_text.lower()}")
        print(f"   Body text contains 'income': {'income' in body_text.lower()}")
        print(f"   Body text contains 'eps': {'eps' in body_text.lower()}")
        
        # Parse data from body text
        parsed_data = parse_income_statement_from_text(body_text, years)
        if parsed_data:
            income_statement = parsed_data
            print(f"✅ Successfully parsed income statement from text")
        else:
            print(f"⚠️ Failed to parse income statement from text")
            income_statement = {"years": [int(y) for y in years], "metrics": {}}
    else:
        # Convert data_by_year format to requested format
        print(f"\n✅ Income statement extraction successful! Converting format...")
        income_statement = convert_to_requested_format(income_statement, ticker, years)
    
    return income_statement


def convert_to_requested_format(data_by_year_dict, ticker, years):
    """Convert data_by_year format to the requested format."""
    years_int = [int(y) for y in sorted(years)]
    
    result = {
        "years": years_int,
        "metrics": {}
    }
    
    # Initialize all metrics with None arrays
    metric_keys = [
        "total_revenue", "cost_of_revenue", "gross_profit", "sga", "rnd",
        "total_opex", "operating_income", "net_income", "basic_eps", "diluted_eps"
    ]
    
    for metric_key in metric_keys:
        result["metrics"][metric_key] = []
        for year in years_int:
            year_str = str(year)
            if year_str in data_by_year_dict.get('data_by_year', {}):
                value = data_by_year_dict['data_by_year'][year_str].get(metric_key)
                # Format values: integers for non-EPS, decimals rounded to hundredth for EPS
                # Keep 0 values as 0 (don't convert to None) - they might be valid projections
                if value is not None:
                    if 'eps' in metric_key:
                        value = round(value, 2)
                    else:
                        # Convert to int, preserving 0 values
                        value = int(value)
                result["metrics"][metric_key].append(value)
            else:
                result["metrics"][metric_key].append(None)
    
    return result


def parse_income_statement_from_text(body_text, years):
    """
    Parse income statement data from page text when table extraction fails.
    
    Expected format in text:
    METRIC
    2021  2022  2023  2024  2025  2026
    TOTAL REVENUE
    $21,252  $26,492  24.7%  $31,352  18.3%  ...
    """
    if not years or len(years) == 0:
        print("⚠️ No years found for parsing")
        return None
    
    # Normalize years to integers
    years_int = [int(y) for y in sorted(years)]
    
    result = {
        "years": years_int,
        "metrics": {}
    }
    
    # Define metric patterns and their keys (order matters - more specific first)
    # Note: "revenue" must come after "total revenue" and "cost of revenue"
    metric_patterns = {
        "total_revenue": [r'^total revenue$', r'^total revenue\s'],
        "cost_of_revenue": [r'^cost of revenue$', r'^cost of revenue\s'],
        "gross_profit": [r'^gross profit$', r'^gross profit\s'],
        "sga": [r'^sg&a$', r'^sga$', r'^sg\s*&\s*a$', r'^selling.*general.*administrative'],
        "rnd": [r'^r&d$', r'^rd$', r'^r\s*&\s*d$', r'^research.*development'],
        "total_opex": [r'^total opex$', r'^total operating expenses$'],
        "operating_income": [r'^operating income$', r'^operating income\s'],
        "net_income": [r'^net income$', r'^net income\s'],
        "basic_eps": [r'^basic eps$', r'^basic eps\s', r'basic eps'],
        "diluted_eps": [r'^dilluted eps$', r'^dilluted eps\s', r'dilluted eps', r'\bdilluted\s+eps\b', r'^diluted eps$', r'^diluted eps\s', r'diluted eps'],
    }
    
    # Split text into lines for easier parsing
    lines = [line.strip() for line in body_text.split('\n') if line.strip()]
    
    print(f"Parsing {len(lines)} lines of text...")
    
    # Find metric rows and extract values
    for metric_key, patterns in metric_patterns.items():
        metric_values = []
        metric_found = False
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            
            # Check if this line matches a metric name
            # Try each pattern
            for pattern in patterns:
                match_found = False
                
                # Strategy 1: Full regex match (case-insensitive)
                try:
                    if re.search(pattern, line_lower, re.IGNORECASE):
                        match_found = True
                except:
                    pass
                
                # Strategy 2: Regex match without anchors
                if not match_found:
                    try:
                        pattern_no_anchors = pattern.replace('^', '').replace('$', '')
                        if re.match(pattern_no_anchors, line_lower, re.IGNORECASE):
                            match_found = True
                    except:
                        pass
                
                # Strategy 3: Simple string match (for cases like "DILUTED EPS")
                if not match_found:
                    # Extract base text from pattern - remove regex special chars
                    pattern_base = pattern.replace('^', '').replace('$', '').replace(r'\s+', ' ').replace(r'\s*', ' ').replace(r'\b', '').replace('(', '').replace(')', '').strip()
                    # Remove remaining regex special chars but keep spaces
                    pattern_base = re.sub(r'[\\\[\](){}.*+?^$|]', '', pattern_base).strip()
                    if pattern_base and pattern_base.lower() in line_lower:
                        match_found = True
                
                # Strategy 4: Word boundary match with cleaned pattern
                if not match_found:
                    try:
                        # Clean pattern for word boundary search
                        pattern_clean = pattern.replace('^', '').replace('$', '').replace(r'\s+', r'\s+').replace(r'\s*', r'\s*')
                        # Escape special regex chars but keep word boundaries
                        pattern_escaped = re.escape(pattern_clean).replace(r'\s\+', r'\s+').replace(r'\s\*', r'\s*')
                        if re.search(r'\b' + pattern_escaped + r'\b', line_lower, re.IGNORECASE):
                            match_found = True
                    except:
                        pass
                
                if match_found:
                    metric_found = True
                    print(f"Found metric '{metric_key}' at line {i}: '{line_stripped[:60]}' (matched pattern: {pattern})")
                    
                    # Look ahead for values - collect next many lines
                    # Values appear after the metric name, spanning multiple lines
                    # Each metric has up to 6 years, so we need to check many lines ahead
                    # Format: value, value, percentage, value, percentage, value, percentage...
                    # Start from the line AFTER the metric name (i+1) to avoid matching the metric name itself
                    search_start = i + 1
                    search_end = min(len(lines), i + 25)  # Check up to 25 lines ahead (enough for 6 years + percentages + next metric)
                    search_lines = lines[search_start:search_end]
                    combined_text = ' '.join(search_lines)
                    
                    # Extract all dollar amounts from this section
                    # Pattern: optional minus, $ followed by digits, commas, optional decimal
                    # Use finditer to capture both value and sign
                    values = []
                    for match in re.finditer(r'(-?)\$([\d,]+\.?\d*)', combined_text):
                        is_negative = match.group(1) == '-'
                        value_str = match.group(2).replace(',', '')
                        try:
                            value = float(value_str)
                            if is_negative:
                                value = -value
                            values.append(value)
                        except:
                            continue
                            
                        print(f"  Found {len(values)} dollar amounts")
                        
                        # Filter out values that are too small (likely percentages or errors) unless it's EPS
                        if 'eps' not in metric_key:
                            # For non-EPS metrics, filter out values < 0.1 (likely percentages)
                            # But keep 0 values as they might be valid (will convert to None later)
                            original_count = len(values)
                            values = [v for v in values if v >= 0.1 or v == 0]
                            if original_count != len(values):
                                print(f"  Filtered out {original_count - len(values)} small values")
                        
                        # The values are in order: value1, value2, value3, value4, value5, value6
                        # Take first N values where N = number of years
                        if len(values) >= len(years_int):
                            metric_values = values[:len(years_int)]
                        elif len(values) > 0:
                            # Pad with None if we have fewer values than years
                            metric_values = values + [None] * (len(years_int) - len(values))
                        else:
                            metric_values = [None] * len(years_int)
                        
                        # Keep 0 values as 0 (they might be valid projections or actual zeros)
                        # Don't convert zeros to None - preserve them
                        
                        non_null_count = len([v for v in metric_values if v is not None])
                        print(f"  Extracted {non_null_count} values: {metric_values}")
                        break
            
            if metric_found:
                break
        
        if metric_values and len(metric_values) == len(years_int):
            # Format values: integers for non-EPS, decimals rounded to hundredth for EPS
            if 'eps' in metric_key:
                metric_values = [round(v, 2) if v is not None else None for v in metric_values]
            else:
                metric_values = [int(v) if v is not None else None for v in metric_values]
            result["metrics"][metric_key] = metric_values
        else:
            # If metric not found, try searching entire text as fallback (for diluted_eps which might be formatted differently)
            if not metric_found and metric_key == 'diluted_eps':
                # Search entire body text for diluted eps values (checking both "dilluted" and "diluted" spellings)
                full_text_lower = body_text.lower()
                
                # Strategy 1: Look for "dilluted eps" (misspelled) or "diluted eps" text
                diluted_eps_pos = -1
                if 'dilluted eps' in full_text_lower:
                    diluted_eps_pos = full_text_lower.find('dilluted eps')
                elif 'diluted eps' in full_text_lower:
                    diluted_eps_pos = full_text_lower.find('diluted eps')
                
                if diluted_eps_pos >= 0:
                    # Extract text around diluted eps
                    search_text = body_text[max(0, diluted_eps_pos-100):min(len(body_text), diluted_eps_pos+500)]
                    # Extract dollar amounts with negative support
                    values = []
                    for match in re.finditer(r'(-?)\$([\d,]+\.?\d*)', search_text):
                        is_negative = match.group(1) == '-'
                        value_str = match.group(2).replace(',', '')
                        try:
                            value = float(value_str)
                            if is_negative:
                                value = -value
                            # EPS values are typically small (< 100 in absolute value)
                            if abs(value) <= 100:
                                values.append(value)
                        except:
                            continue
                    
                    if values and len(values) >= len(years_int):
                            metric_values = values[:len(years_int)]
                            # Format values: integers for non-EPS, decimals rounded to hundredth for EPS
                            if 'eps' in metric_key:
                                metric_values = [round(v, 2) if v is not None else None for v in metric_values]
                            else:
                                metric_values = [int(v) if v is not None else None for v in metric_values]
                            result["metrics"][metric_key] = metric_values
                            print(f"  ✅ Found {len(metric_values)} values for '{metric_key}' via fallback search: {metric_values}")
                            continue
                
                # Strategy 2: Diluted EPS might be the same as Basic EPS (common for some companies)
                if 'basic_eps' in result["metrics"] and result["metrics"]["basic_eps"]:
                    basic_values = result["metrics"]["basic_eps"]
                    # Use basic EPS values as diluted EPS (they're often the same or very close)
                    # Format as decimals rounded to hundredth for EPS
                    basic_values = [round(v, 2) if v is not None else None for v in basic_values]
                    result["metrics"][metric_key] = basic_values
                    continue
            
            # Initialize with None values if not found
            result["metrics"][metric_key] = [None] * len(years_int)
            if not metric_found:
                print(f"⚠️ Could not find metric '{metric_key}'")
            else:
                print(f"⚠️ Could not extract correct number of values for '{metric_key}' (got {len(metric_values) if metric_values else 0}, expected {len(years_int)})")
    
    # Check if we got any data
    if any(v != [None] * len(years_int) for v in result["metrics"].values()):
        return result
    else:
        print("⚠️ No metric data extracted from text")
        return None


async def scrape_projections_metrics(page, ticker):
    """Scrape projections metrics from the projections page."""
    print(f"Navigating to projections page...")
    
    # Navigate to projections page (without ticker in URL)
    projections_url = f"{BASE_URL}/projections/"
    try:
        await page.goto(projections_url, wait_until="domcontentloaded", timeout=60000)
        print(f"✅ Successfully navigated to projections page")
    except Exception as e:
        print(f"⚠️ Navigation issue (domcontentloaded), trying load... Error: {e}")
        try:
            await page.goto(projections_url, wait_until="load", timeout=60000)
            print(f"✅ Successfully navigated using load strategy")
        except Exception as e2:
            print(f"⚠️ Navigation issue (load), trying basic navigation... Error: {e2}")
            await page.goto(projections_url, timeout=60000)
            print(f"✅ Successfully navigated using basic strategy")
    
    # Wait for React to hydrate
    await page.wait_for_timeout(5000)
    
    # Check current URL
    current_url = page.url
    print(f"Current URL: {current_url}")
    
    # Find search input and enter ticker
    try:
        await find_and_use_search_input(page, ticker)
    except Exception as e:
        print(f"❌ Error finding/using search input: {e}")
        raise
    
    # Wait for projections data to load
    print("Waiting for projections data to load...")
    await page.wait_for_timeout(3000)
    
    # Extract projections data
    projections = {}
    
    # Get page text
    print("Extracting page content...")
    body_text = await page.inner_text('body')
    print(f"Page text length: {len(body_text)} characters")
    
    # Parse projections from text
    # The page has a table with years 2025-2029, we need to find the year with actual data (not $0)
    # Based on the image, data is in the first year column (2025) with values like:
    # REVENUE: $40,195,000,000
    # NET INCOME: $7,885,514,000
    # EPS: $8.20
    # NET INC. MARGINS: 20%
    
    # Find all years in the text
    year_pattern = r'\b(20\d{2})\b'
    years = sorted(set(re.findall(year_pattern, body_text)))
    print(f"Found years in text: {years}")
    
    # Split text by lines for easier parsing
    lines = body_text.split('\n')
    
    # Extract revenue - look for large dollar amounts in billions format: $40,195,000,000
    revenue = None
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if line_lower == 'revenue' or (line_lower.startswith('revenue') and 'growth' not in line_lower):
            # Look for dollar amounts in this line and next few lines
            search_text = ' '.join(lines[i:min(len(lines), i+3)])
            # Find all dollar amounts with commas
            dollar_matches = re.findall(r'\$([\d,]+)', search_text)
            for dollar_match in dollar_matches:
                dollar_str = dollar_match.replace(',', '')
                try:
                    dollar_value = int(dollar_str)
                    # Look for values that are billions (at least 1 billion, less than 1 trillion)
                    if 1_000_000_000 <= dollar_value <= 1_000_000_000_000:
                        revenue = dollar_value
                        break
                except:
                    continue
            if revenue:
                break
    
    # Extract net income - look for large dollar amounts (billions), including negative values
    net_income = None
    # Look for NET INCOME row with values like $7,885,514,000 or -$35,976,690
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if 'net income' in line_lower and 'growth' not in line_lower:
            # Look for dollar amounts in this line and next few lines
            search_text = ' '.join(lines[i:min(len(lines), i+3)])
            # Find all dollar amounts with commas, including negative values
            for match in re.finditer(r'(-?)\$([\d,]+)', search_text):
                is_negative = match.group(1) == '-'
                dollar_str = match.group(2).replace(',', '')
                try:
                    dollar_value = int(dollar_str)
                    if is_negative:
                        dollar_value = -dollar_value
                    # Look for values that are millions or billions (absolute value)
                    abs_value = abs(dollar_value)
                    if 1_000_000 <= abs_value <= 1_000_000_000_000:
                        net_income = dollar_value
                        break
                except:
                    continue
            if net_income is not None:
                break
    
    # Extract EPS - look for values like $8.20 or $-0.10 (including negative values)
    eps = None
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if line_lower == 'eps' or (line_lower.startswith('eps') and len(line_lower) < 10):
            # Look for dollar amounts with decimals in this line and next few lines
            search_text = ' '.join(lines[i:min(len(lines), i+3)])
            print(f"Searching for EPS in: {search_text[:200]}")
            # Find dollar amounts with decimals (EPS format: $8.20, $-0.10, or -$0.10)
            # Pattern 1: minus before $: -$0.10
            # Pattern 2: minus after $: $-0.10
            # Pattern 3: positive: $8.20
            for match in re.finditer(r'(-?)\$(-?)([\d,]*\.\d{1,2})', search_text):
                is_negative_before = match.group(1) == '-'
                is_negative_after = match.group(2) == '-'
                eps_str = match.group(3).replace(',', '')
                try:
                    eps_value = float(eps_str)
                    # If minus appears before $ OR after $, make it negative
                    if is_negative_before or is_negative_after:
                        eps_value = -eps_value
                    # Accept non-zero values (including negative)
                    if eps_value != 0:
                        eps = round(eps_value, 2)
                        print(f"Found EPS: {eps}")
                        break
                except:
                    continue
            if eps is not None:
                break
    
    # Extract net income margin - look for percentage values like 20% or -0%
    net_income_margin = None
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if 'net inc' in line_lower and 'margins' in line_lower:
            # Look for percentage values in this line and next few lines
            search_text = ' '.join(lines[i:min(len(lines), i+3)])
            # Find percentage values (format: 20% or -0%)
            for match in re.finditer(r'(-?)(\d+)\s*%', search_text):
                is_negative = match.group(1) == '-'
                margin_str = match.group(2)
                try:
                    margin_value = int(margin_str)
                    if is_negative:
                        margin_value = -margin_value
                    if -100 <= margin_value <= 100:
                        net_income_margin = margin_value
                        break
                except:
                    continue
            if net_income_margin is not None:
                break
    
    # Always use the first year found (should be 2025) - this is the year with actual data
    # Other years (2026-2029) show $0 or "ENTER VALUES"
    data_year = None
    if years:
        data_year = int(years[0])  # Use first year (2025), not last year (2029)
        print(f"Using first year found as data year: {data_year}")
    else:
        print("⚠️ Could not find data year")
    
    # Assign values to projections dict
    projections["revenue"] = revenue
    projections["net_income"] = net_income
    projections["eps"] = eps
    projections["net_income_margin"] = net_income_margin
    projections["data_year"] = data_year
    
    return projections


async def scrape_stock(ticker: str):
    """
    Scrape stock data for a given ticker.
    
    This function scrapes all pages without checking cache (cache checking is handled by the caller).
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary containing scraped data with keys: 'search', 'income_statement', 'projections'
    """
    result, _ = await scrape_stock_metrics(ticker, pages=None, use_cache=False)
    return result


async def scrape_stock_metrics(ticker, pages=None, use_cache=True, page=None, browser=None):
    """
    Scrape stock metrics from the stock data website for a given ticker.
    
    Args:
        ticker: Stock ticker symbol
        pages: List of pages to scrape. Options: 'search', 'income_statement', 'projections'
               If None or empty, scrapes all pages.
        use_cache: Whether to check Supabase cache before scraping (default: True)
        page: Optional Playwright page object (if provided, will reuse existing browser session)
        browser: Optional Playwright browser object (required if page is provided, for cleanup)
    
    Returns:
        Tuple of (result_dict, duration)
    """
    start_time = time.time()
    should_close_browser = False
    
    # Default to all pages if none specified
    if pages is None or len(pages) == 0:
        pages = ['search', 'income_statement', 'projections']
    
    # Normalize page names
    pages = [p.lower().strip() for p in pages]
    
    # Validate page names
    valid_pages = ['search', 'income_statement', 'projections']
    invalid_pages = [p for p in pages if p not in valid_pages]
    if invalid_pages:
        raise ValueError(f"Invalid page names: {invalid_pages}. Valid options: {valid_pages}")
    
    print(f"Scraping pages: {', '.join(pages)}")
    
    # Check cache if enabled
    if use_cache:
        try:
            cached_data = get_cached_data(ticker)
            
            if cached_data:
                # Get last earnings date from yfinance
                last_earnings_date = get_last_earnings_date(ticker)
                
                # Parse cached updated_at timestamp
                cached_updated_at = None
                if cached_data.get('updated_at'):
                    try:
                        cached_updated_at = datetime.fromisoformat(cached_data['updated_at'].replace('Z', '+00:00'))
                    except:
                        try:
                            cached_updated_at = datetime.fromisoformat(cached_data['updated_at'])
                        except:
                            print(f"⚠️ Could not parse cached updated_at: {cached_data['updated_at']}")
                
                # Check if cache is still valid
                cache_valid = True
                if last_earnings_date and cached_updated_at:
                    # Normalize timezones for comparison
                    earnings_date_naive = last_earnings_date.replace(tzinfo=None) if last_earnings_date.tzinfo else last_earnings_date
                    cached_date_naive = cached_updated_at.replace(tzinfo=None) if cached_updated_at.tzinfo else cached_updated_at
                    
                    if cached_date_naive < earnings_date_naive:
                        cache_valid = False
                        print(f"📅 Cache is stale (updated: {cached_date_naive}, last earnings: {earnings_date_naive})")
                    else:
                        print(f"✅ Cache is valid (updated: {cached_date_naive}, last earnings: {earnings_date_naive})")
                elif cached_updated_at:
                    # If we can't get earnings date, assume cache is valid if it's less than 90 days old
                    cached_date_naive = cached_updated_at.replace(tzinfo=None) if cached_updated_at.tzinfo else cached_updated_at
                    days_old = (datetime.now() - cached_date_naive).days
                    if days_old > 90:
                        cache_valid = False
                        print(f"📅 Cache is old ({days_old} days), refreshing...")
                    else:
                        print(f"✅ Using cached data ({days_old} days old)")
                
                if cache_valid:
                    # Build result from cached data
                    result = {}
                    if 'search' in pages and cached_data.get('search_metrics'):
                        result['search'] = cached_data['search_metrics']
                    if 'income_statement' in pages and cached_data.get('income_statement'):
                        result['income_statement'] = cached_data['income_statement']
                    if 'projections' in pages and cached_data.get('projections'):
                        result['projections'] = cached_data['projections']
                    
                    # Only return cached data if we have all requested pages
                    if len(result) == len(pages):
                        end_time = time.time()
                        duration = end_time - start_time
                        print(f"✅ Returning cached data for {ticker}")
                        return result, duration
                    else:
                        print(f"⚠️ Cache missing some requested pages, scraping...")
                else:
                    print(f"🔄 Cache is stale, scraping fresh data...")
            else:
                print(f"📭 No cached data found for {ticker}, scraping...")
        except Exception as e:
            print(f"⚠️ Error checking cache: {e}. Proceeding with scraping...")
    
    # Create browser session if not provided
    if page is None:
        should_close_browser = True
        # Use async context manager properly - but we need to keep it alive
        playwright_context = async_playwright()
        p = await playwright_context.__aenter__()
        # Launch browser with resource optimization flags for Cloud Run
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',  # Reduces memory usage
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--disable-background-networking',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-breakpad',
                '--disable-client-side-phishing-detection',
                '--disable-component-extensions-with-background-pages',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-features=TranslateUI',
                '--disable-hang-monitor',
                '--disable-ipc-flooding-protection',
                '--disable-popup-blocking',
                '--disable-prompt-on-repost',
                '--disable-renderer-backgrounding',
                '--disable-sync',
                '--disable-web-resources',
                '--enable-features=NetworkService,NetworkServiceInProcess',
                '--force-color-profile=srgb',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-first-run',
                '--safebrowsing-disable-auto-update',
                '--enable-automation',
                '--password-store=basic',
                '--use-mock-keychain',
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            # Reduce memory usage
            ignore_https_errors=True,
            java_script_enabled=True,
        )
        page = await context.new_page()
        
        # Navigate to homepage and authenticate
        print(f"Navigating to homepage...")
        homepage_url = f"{BASE_URL}/"
        try:
            await page.goto(homepage_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Homepage navigation issue: {e}")
            await page.goto(homepage_url, timeout=60000)
        
        await page.wait_for_timeout(2000)
        
        # Attempt authentication if credentials are provided
        await authenticate(page)
    
    try:
        result = {}
        
        # Scrape search page metrics if requested
        if 'search' in pages:
            print("\n=== Scraping Search Page Metrics ===")
            search_metrics = await scrape_search_metrics(page, ticker)
            result["search"] = search_metrics
        
        # Scrape income statement metrics if requested
        if 'income_statement' in pages:
            print("\n=== Scraping Income Statement Metrics ===")
            income_statement_metrics = await scrape_income_statement_metrics(page, ticker)
            result["income_statement"] = income_statement_metrics
        
        # Scrape projections metrics if requested
        if 'projections' in pages:
            print("\n=== Scraping Projections Metrics ===")
            projections_metrics = await scrape_projections_metrics(page, ticker)
            result["projections"] = projections_metrics
        
        # Validate scraped data
        print("\n=== Validating Scraped Data ===")
        validation_result = validate_stock_data(ticker, result)
        
        if validation_result.is_valid:
            print(f"✅ Validation passed for {ticker}")
        else:
            print(f"❌ Validation failed for {ticker}")
            if validation_result.errors:
                print("Errors:")
                for error in validation_result.errors:
                    print(f"  - {error}")
        
        if validation_result.warnings:
            print("Warnings:")
            for warning in validation_result.warnings:
                print(f"  ⚠️ {warning}")
        
        # Store validation result in result dict
        result["_validation"] = {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "warnings": validation_result.warnings,
            "page_results": validation_result.page_results
        }
        
        # Close browser only if we created it
        if should_close_browser and browser:
            await browser.close()
        
        # Cache the scraped data
        if use_cache:
            try:
                upsert_stock_data(
                    ticker=ticker,
                    search_metrics=result.get('search'),
                    income_statement=result.get('income_statement'),
                    projections=result.get('projections')
                )
            except Exception as e:
                print(f"⚠️ Failed to cache data (non-fatal): {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        return result, duration
        
    except Exception as e:
        # Don't close browser here - let caller handle cleanup
        raise e

