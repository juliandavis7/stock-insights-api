"""Service for fetching stock exchange information with caching."""
import logging
from typing import Dict, Optional, List
from services.yfinance_service import YFinanceService
from services.country_code_mapper import get_country_code
from services.formatting import format_company_name
from core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def get_stock_exchange_info(tickers: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Get exchange, name, country, industry, and sector information for multiple tickers.
    
    First checks the stocks lookup table, then falls back to yfinance for missing tickers.
    Updates the lookup table with any new data fetched from yfinance.
    
    Args:
        tickers: List of ticker symbols
    
    Returns:
        Dictionary mapping ticker to {'exchange': str or None, 'name': str or None, 'country': str or None, 'country_code': str or None, 'industry': str or None, 'sector': str or None}
    """
    if not tickers:
        return {}
    
    # Normalize tickers to uppercase
    tickers_upper = [t.upper() for t in tickers]
    
    # Get cached data from stocks table
    cached_data = _get_cached_stocks(tickers_upper)
    
    # Find tickers not in cache
    missing_tickers = [t for t in tickers_upper if t not in cached_data]
    
    # Fetch missing tickers from yfinance and update cache
    if missing_tickers:
        logger.info(f"🔄 Fetching exchange info for {len(missing_tickers)} tickers from yfinance: {missing_tickers}")
        yfinance_service = YFinanceService()
        
        for ticker in missing_tickers:
            exchange_info = _fetch_exchange_from_yfinance(ticker, yfinance_service)
            if exchange_info:
                # Calculate country code from country name, with fallback to exchange
                country = exchange_info.get('country')
                exchange = exchange_info.get('exchange')
                country_code = get_country_code(country, exchange)
                
                # Format company name before storing
                raw_name = exchange_info.get('name')
                formatted_name = format_company_name(raw_name)
                
                # Get industry and sector from exchange_info
                industry = exchange_info.get('industry')
                sector = exchange_info.get('sector')
                
                # Update cache with formatted name
                _update_stocks_cache(
                    ticker=ticker,
                    name=formatted_name,  # Store formatted name
                    exchange=exchange_info.get('exchange'),
                    country=country,
                    country_code=country_code,
                    industry=industry,
                    sector=sector
                )
                # Add to cached_data for return (use formatted name)
                cached_data[ticker] = {
                    'exchange': exchange_info.get('exchange'),
                    'name': formatted_name,  # Use formatted name
                    'country': country,
                    'country_code': country_code,
                    'industry': industry,
                    'sector': sector
                }
            else:
                # Still cache None values to avoid repeated failed lookups
                _update_stocks_cache(ticker=ticker, name=None, exchange=None, country=None, country_code=None, industry=None, sector=None)
                cached_data[ticker] = {'exchange': None, 'name': None, 'country': None, 'country_code': None, 'industry': None, 'sector': None}
    
    return cached_data


def _get_cached_stocks(tickers: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Get cached stock exchange, name, country, country_code, industry, and sector data from stocks table.
    
    Args:
        tickers: List of ticker symbols
    
    Returns:
        Dict mapping ticker to {'exchange': str or None, 'name': str or None, 'country': str or None, 'country_code': str or None, 'industry': str or None, 'sector': str or None}
    """
    if not tickers:
        return {}
    
    try:
        client = get_supabase_client()
        response = client.table('stocks').select(
            'ticker, name, exchange, country, country_code, industry, sector'
        ).in_('ticker', tickers).execute()
        
        result = {}
        for row in response.data:
            result[row['ticker']] = {
                'exchange': row.get('exchange'),
                'name': row.get('name'),
                'country': row.get('country'),
                'country_code': row.get('country_code'),
                'industry': row.get('industry'),
                'sector': row.get('sector')
            }
        
        return result
    except Exception as e:
        logger.warning(f"Error fetching cached stocks: {e}")
        return {}


def _fetch_exchange_from_yfinance(ticker: str, yfinance_service: YFinanceService) -> Optional[Dict[str, Optional[str]]]:
    """
    Fetch exchange, name, country, industry, and sector information from yfinance for a single ticker.
    
    Only called when stock is not found in the stocks lookup table.
    
    Args:
        ticker: Stock ticker symbol
        yfinance_service: YFinance service instance
    
    Returns:
        Dictionary with 'exchange', 'name', 'country', 'industry', and 'sector' keys, or None if failed
    """
    try:
        stock_info = yfinance_service.fetch_stock_info(ticker)
        if not stock_info:
            return None
        
        # Extract exchange, name, country, industry, and sector from stock_info
        # The yfinance_service.fetch_stock_info already extracts exchange, country, industry, and sector
        exchange = stock_info.get('exchange')
        name = stock_info.get('company_name')
        country = stock_info.get('country')
        industry = stock_info.get('industry')
        sector = stock_info.get('sector')
        
        return {
            'exchange': exchange,
            'name': name,
            'country': country,
            'industry': industry,
            'sector': sector
        }
    except Exception as e:
        logger.warning(f"Error fetching exchange info from yfinance for {ticker}: {e}")
        return None


def _update_stocks_cache(ticker: str, name: Optional[str], exchange: Optional[str], country: Optional[str] = None, country_code: Optional[str] = None, industry: Optional[str] = None, sector: Optional[str] = None) -> None:
    """
    Update or insert a stock record in the stocks table.
    
    Args:
        ticker: Stock ticker symbol
        name: Company name (optional)
        exchange: Stock exchange (optional)
        country: Company country full name (optional)
        country_code: ISO 2-letter country code (optional, will be calculated from country if not provided)
        industry: Company industry (optional)
        sector: Company sector (optional)
    """
    try:
        client = get_supabase_client()
        from datetime import datetime, timezone
        
        # If country_code not provided but country or exchange is, calculate it with fallback
        if country_code is None:
            country_code = get_country_code(country, exchange)
        
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        stock_record = {
            'ticker': ticker,
            'name': format_company_name(name),
            'exchange': exchange,
            'country': country,
            'country_code': country_code,
            'industry': industry,
            'sector': sector,
            'updated_at': now
        }
        
        client.table('stocks').upsert(stock_record).execute()
    except Exception as e:
        logger.warning(f"Error updating stocks cache for {ticker}: {e}")

