"""Financials endpoint router."""
import logging
from typing import Dict, List
from datetime import datetime
from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from models import FinancialStatementResponse, ComprehensiveFinancialResponse, FinancialDataResponse, AnalystEstimateResponse, IncomeStatementResponse
from core.auth import verify_access
from services.validators import validate_ticker_or_raise
from services.yfinance_service import YFinanceService
from services.fmp_service import FMPService
from services.supabase_service import supabase_service
from core.rate_limit import user_limiter, global_limiter, limiter, FINANCIALS_USER_LIMIT, FINANCIALS_GLOBAL_LIMIT, MOCK_USER_LIMIT
from core.deprecation import add_deprecation_headers

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/mock-income-statement", response_model=List[FinancialStatementResponse])
@limiter.limit(MOCK_USER_LIMIT)
def get_financial_statements(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_access)):
    """
    Mock endpoint to return hardcoded financial statement data for development.
    Returns 3 years of mock data (2024, 2023, 2022) similar to FMP API response.
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        
    Returns:
        List of financial statement data for the past 3 years
    """
    # Mock financial data for different tickers
    mock_data = {
        "AAPL": [
            {
                "date": "2024-09-28",
                "symbol": "AAPL",
                "reportedCurrency": "USD",
                "cik": "0000320193",
                "filingDate": "2024-11-01",
                "acceptedDate": "2024-11-01 06:01:36",
                "fiscalYear": "2024",
                "period": "FY",
                "revenue": 391035000000,
                "costOfRevenue": 210352000000,
                "grossProfit": 180683000000,
                "researchAndDevelopmentExpenses": 31370000000,
                "generalAndAdministrativeExpenses": 0,
                "sellingAndMarketingExpenses": 0,
                "sellingGeneralAndAdministrativeExpenses": 26097000000,
                "otherExpenses": 0,
                "operatingExpenses": 57467000000,
                "costAndExpenses": 267819000000,
                "netInterestIncome": 0,
                "interestIncome": 0,
                "interestExpense": 0,
                "depreciationAndAmortization": 11445000000,
                "ebitda": 134661000000,
                "ebit": 123216000000,
                "nonOperatingIncomeExcludingInterest": 0,
                "operatingIncome": 123216000000,
                "totalOtherIncomeExpensesNet": 269000000,
                "incomeBeforeTax": 123485000000,
                "incomeTaxExpense": 29749000000,
                "netIncomeFromContinuingOperations": 93736000000,
                "netIncomeFromDiscontinuedOperations": 0,
                "otherAdjustmentsToNetIncome": 0,
                "netIncome": 93736000000,
                "netIncomeDeductions": 0,
                "bottomLineNetIncome": 93736000000,
                "eps": 6.11,
                "epsDiluted": 6.08,
                "weightedAverageShsOut": 15343783000,
                "weightedAverageShsOutDil": 15408095000
            },
            {
                "date": "2023-09-30",
                "symbol": "AAPL",
                "reportedCurrency": "USD",
                "cik": "0000320193",
                "filingDate": "2023-11-03",
                "acceptedDate": "2023-11-03 06:01:25",
                "fiscalYear": "2023",
                "period": "FY",
                "revenue": 383285000000,
                "costOfRevenue": 214137000000,
                "grossProfit": 169148000000,
                "researchAndDevelopmentExpenses": 29915000000,
                "generalAndAdministrativeExpenses": 0,
                "sellingAndMarketingExpenses": 0,
                "sellingGeneralAndAdministrativeExpenses": 24932000000,
                "otherExpenses": 0,
                "operatingExpenses": 54847000000,
                "costAndExpenses": 268984000000,
                "netInterestIncome": 0,
                "interestIncome": 0,
                "interestExpense": 0,
                "depreciationAndAmortization": 11519000000,
                "ebitda": 125820000000,
                "ebit": 114301000000,
                "nonOperatingIncomeExcludingInterest": 0,
                "operatingIncome": 114301000000,
                "totalOtherIncomeExpensesNet": -565000000,
                "incomeBeforeTax": 113736000000,
                "incomeTaxExpense": 16741000000,
                "netIncomeFromContinuingOperations": 96995000000,
                "netIncomeFromDiscontinuedOperations": 0,
                "otherAdjustmentsToNetIncome": 0,
                "netIncome": 96995000000,
                "netIncomeDeductions": 0,
                "bottomLineNetIncome": 96995000000,
                "eps": 6.16,
                "epsDiluted": 6.13,
                "weightedAverageShsOut": 15744231000,
                "weightedAverageShsOutDil": 15812547000
            },
            {
                "date": "2022-09-24",
                "symbol": "AAPL",
                "reportedCurrency": "USD",
                "cik": "0000320193",
                "filingDate": "2022-10-28",
                "acceptedDate": "2022-10-28 06:01:15",
                "fiscalYear": "2022",
                "period": "FY",
                "revenue": 394328000000,
                "costOfRevenue": 223546000000,
                "grossProfit": 170782000000,
                "researchAndDevelopmentExpenses": 26251000000,
                "generalAndAdministrativeExpenses": 0,
                "sellingAndMarketingExpenses": 0,
                "sellingGeneralAndAdministrativeExpenses": 25094000000,
                "otherExpenses": 0,
                "operatingExpenses": 51345000000,
                "costAndExpenses": 274891000000,
                "netInterestIncome": 0,
                "interestIncome": 0,
                "interestExpense": 0,
                "depreciationAndAmortization": 11104000000,
                "ebitda": 130541000000,
                "ebit": 119437000000,
                "nonOperatingIncomeExcludingInterest": 0,
                "operatingIncome": 119437000000,
                "totalOtherIncomeExpensesNet": -334000000,
                "incomeBeforeTax": 119103000000,
                "incomeTaxExpense": 19300000000,
                "netIncomeFromContinuingOperations": 99803000000,
                "netIncomeFromDiscontinuedOperations": 0,
                "otherAdjustmentsToNetIncome": 0,
                "netIncome": 99803000000,
                "netIncomeDeductions": 0,
                "bottomLineNetIncome": 99803000000,
                "eps": 6.15,
                "epsDiluted": 6.11,
                "weightedAverageShsOut": 16215963000,
                "weightedAverageShsOutDil": 16325819000
            }
        ]
    }
    
    ticker_upper = ticker.upper()
    
    # Return AAPL data for any ticker (for development purposes)
    # In a real implementation, you would have different mock data for different tickers
    if ticker_upper in mock_data:
        return JSONResponse(content=mock_data[ticker_upper])
    else:
        # Return AAPL data as default for any unknown ticker
        return JSONResponse(content=mock_data["AAPL"])


@router.get("/financials", response_model=IncomeStatementResponse)
@user_limiter.limit(FINANCIALS_USER_LIMIT)
@global_limiter.limit(FINANCIALS_GLOBAL_LIMIT)
def get_financials(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_access)):
    """
    Get financials data from cached Supabase data.
    
    Args:
        ticker: Stock ticker symbol (e.g., META)
        
    Returns:
        IncomeStatementResponse with data from income_statement column
        
    Raises:
        404: If ticker not found in cache (cache miss)
        500: If Supabase connection error
    """
    try:
        stock_data = supabase_service.get_stock_data(ticker)
        
        if not stock_data:
            logger.info(f"Cache miss for ticker {ticker} in /financials")
            raise HTTPException(status_code=404, detail=f"Financials data not found for ticker {ticker}. Cache miss - data not yet scraped.")
        
        income_statement = stock_data.get('income_statement')
        
        if not income_statement:
            logger.warning(f"No income_statement data found for ticker {ticker}")
            raise HTTPException(status_code=404, detail=f"Financials data not available for ticker {ticker}")
        
        # Map income_statement to IncomeStatementResponse format
        income_dict = dict(income_statement) if isinstance(income_statement, dict) else {}
        
        # Remove ticker if present (not needed in response)
        income_dict.pop('ticker', None)
        
        # Reorder metrics to match the order shown in the UI screenshot:
        # 1. total_revenue, 2. cost_of_revenue, 3. gross_profit, 4. sga, 5. rnd,
        # 6. total_opex, 7. operating_income, 8. net_income, 9. basic_eps, 10. diluted_eps
        if 'metrics' in income_dict and isinstance(income_dict['metrics'], dict):
            metrics_order = [
                'total_revenue',
                'cost_of_revenue',
                'gross_profit',
                'sga',
                'rnd',
                'total_opex',
                'operating_income',
                'net_income',
                'basic_eps',
                'diluted_eps'
            ]
            
            # Create ordered metrics dictionary
            ordered_metrics = {}
            metrics_dict = income_dict['metrics']
            
            # Add metrics in the specified order
            for key in metrics_order:
                if key in metrics_dict:
                    ordered_metrics[key] = metrics_dict[key]
            
            # Add any remaining metrics that weren't in the order list
            for key, value in metrics_dict.items():
                if key not in ordered_metrics:
                    ordered_metrics[key] = value
            
            income_dict['metrics'] = ordered_metrics
        
        return JSONResponse(content=income_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /financials endpoint for {ticker}: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error fetching financials data: {str(e)}")


@router.get("/v1/financials", response_model=ComprehensiveFinancialResponse, deprecated=True)
@user_limiter.limit(FINANCIALS_USER_LIMIT)
@global_limiter.limit(FINANCIALS_GLOBAL_LIMIT)
def get_financials_v1(request: Request, ticker: str = Query(..., description="Stock ticker symbol"), user: Dict = Depends(verify_access)):
    """
    [DEPRECATED] Get comprehensive financial data including historical data and analyst estimates.
    
    This endpoint is deprecated. Use /financials instead, which uses cached Supabase data.
    Returns structured financial data with key metrics for each year plus future estimates.
    
    Args:
        ticker: Stock ticker symbol (e.g., AAPL)
        
    Returns:
        Comprehensive financial data including historical and analyst estimates
    """
    try:
        yfinance_service = YFinanceService()
        fmp_service = FMPService()
        
        # Get quarterly income statement data (from FMP API or mocks)
        quarterly_data = fmp_service.fetch_quarterly_income_statement(ticker.upper())
        
        if not quarterly_data:
            logger.error(f"❌ API: No quarterly financial data available for ticker {ticker}")
            validate_ticker_or_raise(ticker)
        
        # Derive historical annual data from quarterly data (sum by calendar year)
        # This ensures consistency with the estimates approach
        historical_data = []
        current_year = datetime.now().year
        
        # Group quarterly data by calendar year
        year_data_map = {}
        for quarter in quarterly_data:
            # Extract calendar year from date (e.g., "2024-12-31" -> 2024)
            date_str = quarter.get('date', '')
            if date_str:
                year = int(date_str.split('-')[0])
                
                # Skip current and future years (only completed years)
                if year >= current_year:
                    continue
                
                if year not in year_data_map:
                    year_data_map[year] = {
                        'quarters': [],
                        'totalRevenue': 0,
                        'costOfRevenue': 0,
                        'grossProfit': 0,
                        'sellingGeneralAndAdministrative': 0,
                        'researchAndDevelopment': 0,
                        'operatingExpenses': 0,
                        'operatingIncome': 0,
                        'netIncome': 0,
                        'eps': 0,
                        'epsDiluted': 0
                    }
                
                # Accumulate quarterly values
                year_data_map[year]['quarters'].append(quarter)
                year_data_map[year]['totalRevenue'] += quarter.get('revenue', 0) or 0
                year_data_map[year]['costOfRevenue'] += quarter.get('costOfRevenue', 0) or 0
                year_data_map[year]['grossProfit'] += quarter.get('grossProfit', 0) or 0
                year_data_map[year]['sellingGeneralAndAdministrative'] += quarter.get('sellingGeneralAndAdministrativeExpenses', 0) or 0
                year_data_map[year]['researchAndDevelopment'] += quarter.get('researchAndDevelopmentExpenses', 0) or 0
                year_data_map[year]['operatingExpenses'] += quarter.get('operatingExpenses', 0) or 0
                year_data_map[year]['operatingIncome'] += quarter.get('operatingIncome', 0) or 0
                year_data_map[year]['netIncome'] += quarter.get('netIncome', 0) or 0
                year_data_map[year]['eps'] += quarter.get('eps', 0) or 0
                year_data_map[year]['epsDiluted'] += quarter.get('epsDiluted', 0) or 0
        
        # Convert to FinancialDataResponse objects (only years with 4 complete quarters)
        for year in sorted(year_data_map.keys(), reverse=True):
            year_summary = year_data_map[year]
            
            # Only include years with 4 complete quarters
            if len(year_summary['quarters']) == 4:
                processed_year = FinancialDataResponse(
                    fiscalYear=str(year),
                    totalRevenue=int(year_summary['totalRevenue']),
                    costOfRevenue=int(year_summary['costOfRevenue']),
                    grossProfit=int(year_summary['grossProfit']),
                    sellingGeneralAndAdministrative=int(year_summary['sellingGeneralAndAdministrative']),
                    researchAndDevelopment=int(year_summary['researchAndDevelopment']),
                    operatingExpenses=int(year_summary['operatingExpenses']),
                    operatingIncome=int(year_summary['operatingIncome']),
                    netIncome=int(year_summary['netIncome']),
                    eps=round(year_summary['eps'], 2),
                    dilutedEps=round(year_summary['epsDiluted'], 2)
                )
                historical_data.append(processed_year)
            else:
                logger.warning(f"Skipping year {year} - only {len(year_summary['quarters'])} quarters available")
        
        # Generate analyst estimates for 2025-2027 using GAAP-adjusted hybrid approach
        # This matches the /projections endpoint behavior
        estimates_data = []
        
        try:
            # Reuse quarterly_data already fetched above (line 357) - no need to fetch again
            # Get quarterly estimates from FMP (only new call needed)
            quarterly_estimates = fmp_service.fetch_quarterly_analyst_estimates(ticker)
            
            if quarterly_data and quarterly_estimates:
                from services.metrics_calculator import MetricsCalculator
                calculator = MetricsCalculator()
                
                # Get shares outstanding from FMP quarterly income statement (use diluted shares)
                shares_outstanding = None
                if quarterly_data and len(quarterly_data) > 0:
                    shares_outstanding = quarterly_data[0].get('weightedAverageShsOutDil')
                    # Fallback to basic shares if diluted not available
                    if not shares_outstanding:
                        shares_outstanding = quarterly_data[0].get('weightedAverageShsOut')
                    
                    if shares_outstanding:
                        logger.info(f"Using diluted shares from FMP for {ticker}: {shares_outstanding:,.0f}")
                
                # Fallback to yfinance if FMP data not available
                if not shares_outstanding:
                    stock_info = yfinance_service.fetch_stock_info(ticker)
                    shares_outstanding = stock_info.get('shares_outstanding') if stock_info else None
                    if shares_outstanding:
                        logger.warning(f"Using yfinance shares for {ticker} (FMP data unavailable): {shares_outstanding:,.0f}")
                
                for year in [2025, 2026, 2027]:
                    try:
                        if year == current_year:  # Current year (2025)
                            # Use GAAP-adjusted hybrid approach (actual quarters + adjusted estimated quarters)
                            net_income = calculator._get_median_adjusted_hybrid_current_year_net_income(
                                quarterly_data, quarterly_estimates, year
                            )
                            revenue = calculator._get_hybrid_current_year_revenue(
                                quarterly_data, quarterly_estimates, year
                            )
                        else:  # Future years (2026, 2027)
                            # Use GAAP-adjusted estimates for all 4 quarters
                            net_income = calculator._get_median_adjusted_future_year_net_income(
                                quarterly_estimates, quarterly_data, quarterly_estimates, year
                            )
                            revenue = calculator._get_quarterly_estimates_revenue(
                                quarterly_estimates, year, 4
                            )
                        
                        # Calculate EPS and diluted EPS from net income
                        eps = None
                        diluted_eps = None
                        if net_income and shares_outstanding and shares_outstanding > 0:
                            eps = net_income / shares_outstanding
                            diluted_eps = eps * 0.99  # Assume 1% dilution
                        
                        estimate = AnalystEstimateResponse(
                            fiscalYear=str(year),
                            totalRevenue=int(revenue) if revenue else None,
                            netIncome=int(net_income) if net_income else None,
                            eps=round(eps, 2) if eps else None,
                            dilutedEps=round(diluted_eps, 2) if diluted_eps else None
                        )
                        estimates_data.append(estimate)
                        
                    except Exception as e:
                        logger.error(f"Error calculating GAAP-adjusted data for {ticker} {year}: {e}")
                        raise
            else:
                logger.error(f"Insufficient FMP data for {ticker}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Insufficient data available for ticker {ticker}"
                )
                
        except Exception as e:
            logger.error(f"Error in GAAP-adjusted calculations for {ticker}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error calculating estimates: {str(e)}"
            )
        
        response_data = ComprehensiveFinancialResponse(
            historical=historical_data,
            estimates=estimates_data
        )
        response = JSONResponse(content=response_data.dict())
        return add_deprecation_headers(response, "/financials")
    
    except ValueError as e:
        # ValueError raised by FMPService when ticker not found in mocks
        logger.error(f"❌ API: Ticker {ticker} not found: {e}")
        validate_ticker_or_raise(ticker)
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a ticker not found error from FMP API
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['not found', 'invalid symbol', 'unknown symbol', 'invalid ticker']):
            logger.error(f"❌ API: Ticker {ticker} not found in FMP API: {e}")
            validate_ticker_or_raise(ticker)
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

