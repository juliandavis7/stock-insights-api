#!/usr/bin/env python3
"""
Cloud Run Job script to scrape stock data.

This script fetches a list of stocks from Supabase and scrapes data for each one,
checking cache and only scraping when necessary.
"""

# IMMEDIATE OUTPUT - This should appear in logs if Python is running
import sys
import os
from datetime import datetime

# Log container and Python startup immediately
print("=" * 80, file=sys.stdout, flush=True)
print("PYTHON PROCESS STARTED", file=sys.stdout, flush=True)
print(f"Startup timestamp: {datetime.utcnow().isoformat()}Z", file=sys.stdout, flush=True)
print(f"Python version: {sys.version}", file=sys.stdout, flush=True)
print(f"Python executable: {sys.executable}", file=sys.stdout, flush=True)
print(f"Current directory: {os.getcwd()}", file=sys.stdout, flush=True)
print(f"Script file: {__file__}", file=sys.stdout, flush=True)
print(f"Script exists: {os.path.exists(__file__)}", file=sys.stdout, flush=True)
print(f"Command line args: {sys.argv}", file=sys.stdout, flush=True)
print(f"Process ID: {os.getpid()}", file=sys.stdout, flush=True)
print("=" * 80, file=sys.stdout, flush=True)

import asyncio
import sys
import os
import traceback
import json
import logging
from datetime import datetime
from typing import List

# Configure logging immediately for GCP Cloud Logging
# Cloud Run Jobs automatically captures stdout/stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]  # Explicitly use stdout
)
logger = logging.getLogger(__name__)

# Force stdout/stderr to be unbuffered for immediate log visibility
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
sys.stderr.reconfigure(line_buffering=True) if hasattr(sys.stderr, 'reconfigure') else None

# Log startup information immediately
logger.info("=" * 80)
logger.info("STOCK SCRAPER JOB - STARTING")
logger.info("=" * 80)
logger.info(f"Python version: {sys.version}")
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Script location: {__file__}")
logger.info(f"Command line args: {sys.argv}")

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger.info(f"Python path: {sys.path}")

# Log environment variable status (without exposing secrets)
logger.info("Checking environment variables...")
env_vars_to_check = ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY', 'BASE_URL', 'STOCK_USER', 'STOCK_PASS']
for var in env_vars_to_check:
    value = os.getenv(var)
    if value:
        # Mask secrets but show length
        if 'KEY' in var or 'PASS' in var:
            logger.info(f"  ✓ {var}: Set (length: {len(value)})")
        else:
            logger.info(f"  ✓ {var}: {value}")
    else:
        logger.warning(f"  ✗ {var}: Not set")

# Load environment variables first (before other imports that might need them)
try:
    logger.info("Loading dotenv...")
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("✓ dotenv loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️ Could not load dotenv: {e}")
    logger.info("Continuing with environment variables from container...")

# Import with error handling
try:
    logger.info("Importing core modules...")
    from core.supabase_client import get_supabase_client
    logger.info("✓ core.supabase_client imported")
    
    logger.info("Importing scraper module...")
    from services.scraper import scrape_stock, get_last_earnings_date, upsert_stock_data, get_cached_data
    logger.info("✓ services.scraper imported")
    logger.info("✓ All imports successful")
except ImportError as e:
    logger.error(f"❌ CRITICAL: Failed to import required modules: {e}")
    logger.error(f"Python path: {sys.path}")
    logger.error(f"Current directory: {os.getcwd()}")
    logger.error(f"Script location: {__file__}")
    logger.error("Full traceback:", exc_info=True)
    sys.exit(1)
except Exception as e:
    logger.error(f"❌ CRITICAL: Unexpected error during imports: {e}")
    logger.error("Full traceback:", exc_info=True)
    sys.exit(1)


async def fetch_stock_list():
    """
    Fetch list of stocks with full data from Supabase.
    
    Returns:
        List of stock dictionaries with ticker and data fields
    """
    try:
        logger.info("Connecting to Supabase...")
        supabase = get_supabase_client()
        logger.info("✓ Supabase client created")
        
        # Try to fetch from a 'stocks' table first
        try:
            logger.info("Attempting to fetch from 'stocks' table...")
            result = supabase.table('stocks').select('ticker').execute()
            if result.data:
                tickers = [row['ticker'] for row in result.data]
                logger.info(f"Found {len(tickers)} tickers in 'stocks' table")
                # Fetch full stock_data for these tickers
                stocks_result = supabase.table('stock_data').select('*').in_('ticker', tickers).execute()
                if stocks_result.data:
                    logger.info(f"✅ Fetched {len(stocks_result.data)} stocks from 'stock_data' table")
                    return stocks_result.data
                # If no stock_data entries, return tickers as dicts
                logger.info("No stock_data entries found, creating empty entries")
                return [{'ticker': t, 'search_metrics': None, 'income_statement': None, 'projections': None, 'updated_at': None} for t in tickers]
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch from 'stocks' table: {e}")
        
        # Fallback: get all stocks from stock_data table
        try:
            logger.info("Fetching all stocks from 'stock_data' table...")
            result = supabase.table('stock_data').select('*').execute()
            if result.data:
                logger.info(f"✅ Fetched {len(result.data)} stocks from 'stock_data' table")
                return result.data
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch from 'stock_data' table: {e}")
        
        # If both fail, return empty list
        logger.warning("⚠️ Could not fetch stock list from Supabase")
        return []
    except Exception as e:
        logger.error(f"❌ Error fetching stock list: {e}", exc_info=True)
        return []


def should_scrape(stock_data: dict) -> tuple[bool, str]:
    """
    Check if a stock should be scraped based on cache status.
    
    Args:
        stock_data: Stock data dictionary with ticker, search_metrics, income_statement, updated_at
        
    Returns:
        Tuple of (should_scrape: bool, reason: str)
    """
    ticker = stock_data.get('ticker')
    
    # Check if data is missing (never scraped)
    if stock_data.get('search_metrics') is None or stock_data.get('income_statement') is None:
        return True, "no data (never scraped)"
    
    # Check if cache is stale based on earnings date
    try:
        last_earnings_date = get_last_earnings_date(ticker)
        
        if last_earnings_date:
            # Parse cached updated_at timestamp
            cached_updated_at = None
            if stock_data.get('updated_at'):
                try:
                    cached_updated_at = datetime.fromisoformat(
                        stock_data['updated_at'].replace('Z', '+00:00')
                    )
                except:
                    try:
                        cached_updated_at = datetime.fromisoformat(stock_data['updated_at'])
                    except:
                        pass
            
            if cached_updated_at:
                # Normalize timezones for comparison
                earnings_date_naive = (
                    last_earnings_date.replace(tzinfo=None) 
                    if last_earnings_date.tzinfo 
                    else last_earnings_date
                )
                cached_date_naive = (
                    cached_updated_at.replace(tzinfo=None) 
                    if cached_updated_at.tzinfo 
                    else cached_updated_at
                )
                
                if cached_date_naive < earnings_date_naive:
                    return True, f"cache stale (updated: {cached_date_naive}, earnings: {earnings_date_naive})"
                else:
                    return False, "cache is fresh"
            else:
                # Can't parse updated_at, but we have data, assume cache is valid
                return False, "cache exists (could not parse updated_at)"
        else:
            # Can't get earnings date, assume cache is valid if less than 90 days old
            cached_updated_at = None
            if stock_data.get('updated_at'):
                try:
                    cached_updated_at = datetime.fromisoformat(
                        stock_data['updated_at'].replace('Z', '+00:00')
                    )
                except:
                    try:
                        cached_updated_at = datetime.fromisoformat(stock_data['updated_at'])
                    except:
                        pass
            
            if cached_updated_at:
                cached_date_naive = (
                    cached_updated_at.replace(tzinfo=None) 
                    if cached_updated_at.tzinfo 
                    else cached_updated_at
                )
                days_old = (datetime.now() - cached_date_naive).days
                if days_old > 90:
                    return True, f"cache is old ({days_old} days)"
                else:
                    return False, f"cache is fresh ({days_old} days old)"
            else:
                # Can't determine age, but we have data, assume cache is valid
                return False, "cache exists (could not determine age)"
    except Exception as e:
        logger.warning(f"⚠️ Error checking cache for {ticker}: {e}")
        # On error, assume cache is valid to avoid unnecessary scraping
        return False, f"error checking cache: {e}"


async def main():
    """Main async function to run the job."""
    logger.info("Starting main() function...")
    
    # Verify environment variables are set
    logger.info("Verifying required environment variables...")
    required_env_vars = ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"❌ CRITICAL: Missing required environment variables: {', '.join(missing_vars)}")
        logger.info("Available environment variables:")
        for key in sorted(os.environ.keys()):
            if 'SUPABASE' in key or 'STOCK' in key or 'BASE_URL' in key:
                masked_value = '*' * len(os.environ[key]) if 'KEY' in key or 'PASS' in key else os.environ[key]
                logger.info(f"  {key}={masked_value}")
        sys.exit(1)
    logger.info("✓ All required environment variables are set")
    
    # Check if ticker provided as command-line argument
    if len(sys.argv) > 1:
        # Single ticker mode
        ticker = sys.argv[1].upper()
        logger.info("=" * 80)
        logger.info(f"MODE: Single ticker scraping for {ticker}")
        logger.info("=" * 80)
        
        try:
            logger.info(f"Starting scrape for {ticker}...")
            result = await scrape_stock(ticker)
            logger.info(f"✓ Scraping completed for {ticker}")
            
            logger.info(f"Storing results in Supabase for {ticker}...")
            upsert_stock_data(
                ticker=ticker,
                search_metrics=result.get('search'),
                income_statement=result.get('income_statement'),
                projections=result.get('projections')
            )
            logger.info(f"✅ Successfully scraped and cached {ticker}")
            
            logger.info("=" * 80)
            logger.info("RESULTS")
            logger.info("=" * 80)
            logger.info(json.dumps(result, indent=2))
        except Exception as e:
            logger.error(f"\n❌ Failed to scrape {ticker}: {e}", exc_info=True)
            sys.exit(1)
        return
    
    # Batch mode: fetch stocks from Supabase
    logger.info("=" * 80)
    logger.info("MODE: Batch processing (all stocks)")
    logger.info("=" * 80)
    
    # Fetch stock list with full data
    logger.info("📋 Fetching stock list from Supabase...")
    stocks = await fetch_stock_list()
    
    if not stocks:
        logger.error("❌ No stocks to process. Exiting.")
        sys.exit(1)
    
    logger.info(f"✅ Found {len(stocks)} stocks to process")
    
    # Process each stock
    scraped_count = 0
    skipped_count = 0
    failed_count = 0
    
    for i, stock in enumerate(stocks, 1):
        ticker = stock.get('ticker')
        logger.info(f"[{i}/{len(stocks)}] Processing {ticker}...")
        
        try:
            # Check if data is missing (never scraped)
            if stock.get('search_metrics') is None or stock.get('income_statement') is None:
                logger.info(f"  🔄 No data for {ticker}, scraping...")
                try:
                    # Scrape the stock
                    result = await scrape_stock(ticker)
                    
                    # Store result in Supabase
                    upsert_stock_data(
                        ticker=ticker,
                        search_metrics=result.get('search'),
                        income_statement=result.get('income_statement'),
                        projections=result.get('projections')
                    )
                    
                    scraped_count += 1
                    logger.info(f"  ✅ Successfully scraped and cached {ticker}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"  ❌ Failed to scrape {ticker}: {e}", exc_info=True)
                continue
            
            # Check if we should scrape (stale data)
            should_scrape_flag, reason = should_scrape(stock)
            
            if should_scrape_flag:
                logger.info(f"  🔄 Stale data for {ticker}, scraping... ({reason})")
                try:
                    # Scrape the stock
                    result = await scrape_stock(ticker)
                    
                    # Store result in Supabase
                    upsert_stock_data(
                        ticker=ticker,
                        search_metrics=result.get('search'),
                        income_statement=result.get('income_statement'),
                        projections=result.get('projections')
                    )
                    
                    scraped_count += 1
                    logger.info(f"  ✅ Successfully scraped and cached {ticker}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"  ❌ Failed to scrape {ticker}: {e}", exc_info=True)
            else:
                skipped_count += 1
                logger.info(f"  ⏭️  Skipping {ticker}, cache is fresh ({reason})")
        except Exception as e:
            failed_count += 1
            logger.error(f"  ❌ Error processing {ticker}: {e}", exc_info=True)
        
        # Log progress
        logger.info(f"  📊 Progress: {scraped_count} scraped, {skipped_count} skipped, {failed_count} failed")
    
    # Final summary
    logger.info("=" * 80)
    logger.info("JOB COMPLETED")
    logger.info("=" * 80)
    logger.info(f"Total stocks processed: {len(stocks)}")
    logger.info(f"  ✅ Scraped: {scraped_count}")
    logger.info(f"  ⏭️  Skipped: {skipped_count}")
    logger.info(f"  ❌ Failed: {failed_count}")
    logger.info("=" * 80)
    
    # Exit with error code if any failures
    if failed_count > 0:
        logger.error(f"Job completed with {failed_count} failures")
        sys.exit(1)
    else:
        logger.info("Job completed successfully")


if __name__ == "__main__":
    try:
        logger.info("Starting asyncio event loop...")
        asyncio.run(main())
        logger.info("Job execution completed")
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Job interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"\n❌ CRITICAL: Job failed with unexpected error: {e}", exc_info=True)
        sys.exit(1)

