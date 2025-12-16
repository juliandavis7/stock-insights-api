"""Service for calculating dynamic portfolio values with price caching."""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from services.yfinance_service import YFinanceService
from services.stock_exchange_service import get_stock_exchange_info
from core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# Cache TTL in minutes - prices older than this will be refreshed
CACHE_TTL_MINUTES = 60  # 1 hour


def _fetch_price_from_yfinance(ticker: str, yfinance_service: YFinanceService) -> Optional[Dict]:
    """
    Fetch price and P/E ratio from yfinance for a single ticker (synchronous).
    
    Args:
        ticker: Stock ticker symbol
        yfinance_service: YFinance service instance
    
    Returns:
        Dictionary with price, pe, and name, or None if failed
    """
    try:
        # Fetch current price
        current_price = yfinance_service.get_current_price(ticker)
        if current_price is None:
            return None
        
        # Fetch stock info for P/E ratio and company name
        stock_info = yfinance_service.fetch_stock_info(ticker)
        pe_ratio = None
        name = None
        if stock_info:
            # Try trailing PE first, then forward PE
            pe_ratio = stock_info.get('trailing_pe') or stock_info.get('forward_pe')
            name = stock_info.get('company_name')
        
        return {
            "price": current_price,
            "pe": pe_ratio,
            "name": name
        }
    except Exception as e:
        logger.warning(f"Error fetching yfinance data for {ticker}: {e}")
        return None


def _get_cached_prices(tickers: List[str]) -> Dict[str, Dict]:
    """
    Get cached prices from price_cache table.
    
    Args:
        tickers: List of ticker symbols
    
    Returns:
        Dict mapping ticker to cache entry
    """
    if not tickers:
        return {}
    
    try:
        client = get_supabase_client()
        response = client.table('price_cache').select(
            'ticker, price, pe_ratio, name, updated_at'
        ).in_('ticker', tickers).execute()
        
        return {c['ticker']: c for c in response.data}
    except Exception as e:
        logger.warning(f"Error fetching price cache: {e}")
        return {}


def _update_price_cache(ticker: str, price: float, pe_ratio: Optional[float], name: Optional[str]) -> None:
    """
    Update or insert a price cache entry.
    
    Args:
        ticker: Stock ticker symbol
        price: Current price
        pe_ratio: P/E ratio (optional)
        name: Company name (optional)
    """
    try:
        client = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        cache_record = {
            'ticker': ticker,
            'price': price,
            'pe_ratio': pe_ratio,
            'name': name,
            'updated_at': now
        }
        
        client.table('price_cache').upsert(cache_record).execute()
    except Exception as e:
        logger.warning(f"Error updating price cache for {ticker}: {e}")


def _is_cache_stale(cache_entry: Dict) -> bool:
    """
    Check if a cache entry is stale (older than CACHE_TTL_MINUTES).
    
    Args:
        cache_entry: Cache entry with updated_at field
    
    Returns:
        True if stale, False if fresh
    """
    updated_at_str = cache_entry.get('updated_at')
    if not updated_at_str:
        return True
    
    try:
        # Parse ISO timestamp
        if updated_at_str.endswith('Z'):
            updated_at_str = updated_at_str.replace('Z', '+00:00')
        updated_at = datetime.fromisoformat(updated_at_str)
        
        now = datetime.now(timezone.utc)
        cache_threshold = now - timedelta(minutes=CACHE_TTL_MINUTES)
        
        return updated_at < cache_threshold
    except Exception as e:
        logger.warning(f"Error parsing cache timestamp: {e}")
        return True


async def calculate_portfolio_values(holdings: List[Dict], force_refresh: bool = False) -> List[Dict]:
    """
    Calculate dynamic portfolio values with price caching.
    
    Prices are cached for 1 hour. Use force_refresh=True to bypass cache.
    
    Args:
        holdings: List of holdings with ticker, name, shares, cost_basis
        force_refresh: If True, bypass cache and fetch fresh prices from yfinance
    
    Returns:
        List of enriched holdings with:
        - market_value: shares × current_price
        - gain_loss_pct: ((market_value - cost_basis) / cost_basis) × 100
        - current_price: Current stock price
        - pe_ratio: P/E ratio
    """
    if not holdings:
        return holdings
    
    # Get unique tickers
    tickers = list(set(h["ticker"] for h in holdings))
    
    # Get exchange information (uses stocks lookup table with yfinance fallback)
    # This also includes formatted company names from the stocks table
    exchange_info_map = get_stock_exchange_info(tickers)
    
    # Get cached prices
    cache_map = _get_cached_prices(tickers)
    
    # Identify stale or missing tickers
    stale_tickers = []
    for ticker in tickers:
        cached = cache_map.get(ticker)
        if force_refresh or not cached or _is_cache_stale(cached):
            stale_tickers.append(ticker)
    
    # Fetch fresh prices only for stale/missing tickers
    if stale_tickers:
        logger.info(f"🔄 Fetching fresh prices for {len(stale_tickers)} stale/missing tickers: {stale_tickers}")
        yfinance_service = YFinanceService()
        
        for ticker in stale_tickers:
            yf_data = _fetch_price_from_yfinance(ticker, yfinance_service)
            if yf_data and yf_data.get('price') is not None:
                # Update cache
                _update_price_cache(
                    ticker=ticker,
                    price=yf_data['price'],
                    pe_ratio=yf_data.get('pe'),
                    name=yf_data.get('name')
                )
                # Update local cache map
                cache_map[ticker] = {
                    'ticker': ticker,
                    'price': yf_data['price'],
                    'pe_ratio': yf_data.get('pe'),
                    'name': yf_data.get('name')
                }
            else:
                logger.warning(f"Could not fetch price for ticker {ticker} from yfinance")
    else:
        logger.info(f"✅ All {len(tickers)} tickers have fresh cached prices (< {CACHE_TTL_MINUTES} mins old)")
    
    # Enrich holdings from cache
    enriched = []
    for holding in holdings:
        ticker = holding["ticker"]
        cached = cache_map.get(ticker)
        
        # Get exchange, country_code, industry, sector, and name info for this ticker from stocks table
        ticker_exchange_info = exchange_info_map.get(ticker, {})
        exchange = ticker_exchange_info.get('exchange')
        country_code = ticker_exchange_info.get('country_code')
        industry = ticker_exchange_info.get('industry')
        sector = ticker_exchange_info.get('sector')
        # Prefer formatted name from stocks table, fallback to holdings table name
        name = ticker_exchange_info.get('name') or holding.get("name")
        
        if not cached or cached.get('price') is None:
            # Include holding with null values for price-dependent fields
            # Order: ticker, name, exchange, country_code, industry, sector, shares, cost_basis, then calculated fields
            enriched.append({
                "ticker": holding["ticker"],
                "name": name,
                "exchange": exchange,
                "country_code": country_code,
                "industry": industry,
                "sector": sector,
                "shares": holding["shares"],
                "cost_basis": holding["cost_basis"],
                "market_value": None,
                "gain_loss_pct": None,
                "current_price": None,
                "pe_ratio": None,
                "percent_of_portfolio": None,
            })
            continue
        
        current_price = cached.get('price', 0)
        shares = holding["shares"]
        cost_basis = holding["cost_basis"]
        
        # Calculate market value
        market_value = shares * current_price if current_price else None
        
        # Calculate gain/loss percentage
        if market_value is not None and cost_basis > 0:
            gain_loss_pct = ((market_value - cost_basis) / cost_basis) * 100
        else:
            gain_loss_pct = None
        
        # Order: ticker, name, exchange, country_code, industry, sector, shares, cost_basis, then calculated fields
        # Prefer formatted name from stocks table, fallback to holdings table name
        name = ticker_exchange_info.get('name') or holding.get("name")
        
        enriched.append({
            "ticker": holding["ticker"],
            "name": name,
            "exchange": exchange,
            "country_code": country_code,
            "industry": industry,
            "sector": sector,
            "shares": holding["shares"],
            "cost_basis": holding["cost_basis"],
            "market_value": round(market_value, 2) if market_value is not None else None,
            "gain_loss_pct": round(gain_loss_pct, 2) if gain_loss_pct is not None else None,
            "current_price": current_price,
            "pe_ratio": cached.get('pe_ratio'),
            "percent_of_portfolio": None,  # Will be calculated after totals
        })
    
    return enriched


def calculate_portfolio_totals_and_percentages(holdings: List[Dict]) -> Dict:
    """
    Calculate portfolio totals and percentages for each holding.
    
    Args:
        holdings: List of holdings with market_value
    
    Returns:
        Dictionary with:
        - holdings: Holdings with percent_of_portfolio calculated
        - total_market_value: Sum of all market values
        - total_cost_basis: Sum of all cost bases
        - total_gain_loss_pct: Overall gain/loss percentage
    """
    # Calculate totals
    valid_market_values = [h["market_value"] for h in holdings if h.get("market_value") is not None]
    total_market_value = sum(valid_market_values) if valid_market_values else None
    total_cost_basis = sum(h["cost_basis"] for h in holdings)
    
    # Calculate overall gain/loss percentage
    if total_cost_basis > 0 and total_market_value is not None and total_market_value > 0:
        total_gain_loss_pct = ((total_market_value - total_cost_basis) / total_cost_basis) * 100
    else:
        total_gain_loss_pct = None
    
    # Calculate percent_of_portfolio for each holding
    for holding in holdings:
        market_value = holding.get("market_value")
        if market_value is not None and total_market_value is not None and total_market_value > 0:
            holding["percent_of_portfolio"] = round(
                (market_value / total_market_value) * 100, 
                2
            )
        else:
            holding["percent_of_portfolio"] = None
    
    # Sort by percent_of_portfolio descending (nulls last)
    holdings.sort(
        key=lambda h: h.get("percent_of_portfolio") if h.get("percent_of_portfolio") is not None else -1,
        reverse=True
    )
    
    return {
        "holdings": holdings,
        "total_market_value": round(total_market_value, 2) if total_market_value is not None else None,
        "total_cost_basis": round(total_cost_basis, 2),
        "total_gain_loss_pct": round(total_gain_loss_pct, 2) if total_gain_loss_pct is not None else None,
    }

