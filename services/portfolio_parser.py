"""Portfolio CSV parser service."""
import pandas as pd
from typing import List, Tuple, Literal, Optional, Dict
from io import StringIO
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Cash equivalents to exclude from portfolio visualization
CASH_EQUIVALENTS = [
    "VMFXX",  # Vanguard Federal Money Market
    "QACDS",  # Chase Deposit Sweep
    "QDERQ",  # Chase IRA Deposit Sweep
    "SPAXX",  # Fidelity Government Money Market
    "FDRXX",  # Fidelity Money Market
    "SWVXX",  # Schwab Value Advantage Money
]

# Chase CSV column mapping
CHASE_COLUMNS = {
    "ticker": "Ticker",
    "name": "Description",
    "shares": "Quantity",
    "cost_basis": "Cost",
    "market_value": "Value",
    "gain_loss_pct": "Unrealized Gain/Loss (%)",
}

# Generic CSV column mapping (what we expect from users)
# Only requires ticker, shares, cost_basis - market_value calculated via FMP
GENERIC_COLUMNS = {
    "ticker": "ticker",
    "shares": "shares",
    "cost_basis": "cost_basis",
    # name and market_value are fetched from FMP
}

# Fidelity CSV column mapping
FIDELITY_COLUMNS = {
    "ticker": "Symbol",
    "name": "Description",
    "shares": "Quantity",
    "cost_basis": "Cost Basis Total",
    "market_value": "Current Value",
    "type": "Type",
}


def fuzzy_match_column(column_name: str, target_names: List[str], threshold: float = 0.6) -> Optional[str]:
    """
    Fuzzy match a column name to one of the target names.
    
    Args:
        column_name: The column name to match
        target_names: List of target column names to match against
        threshold: Similarity threshold (0.0 to 1.0), default 0.6
    
    Returns:
        Matched target name if similarity >= threshold, None otherwise
    """
    column_lower = column_name.lower().strip()
    
    # First try exact match (case-insensitive)
    for target in target_names:
        if column_lower == target.lower().strip():
            return target
    
    # Try partial match (contains)
    for target in target_names:
        target_lower = target.lower().strip()
        if column_lower in target_lower or target_lower in column_lower:
            return target
    
    # Try fuzzy similarity matching
    best_match = None
    best_score = 0.0
    
    for target in target_names:
        score = SequenceMatcher(None, column_lower, target.lower().strip()).ratio()
        if score > best_score:
            best_score = score
            best_match = target
    
    if best_score >= threshold:
        return best_match
    
    return None


def find_columns_fuzzy(df: pd.DataFrame, column_mapping: Dict[str, List[str]]) -> Dict[str, Optional[str]]:
    """
    Find columns in DataFrame using fuzzy matching.
    
    Args:
        df: DataFrame to search
        column_mapping: Dict mapping internal names to list of possible column names
    
    Returns:
        Dict mapping internal names to found column names (or None if not found)
    """
    found_columns = {}
    df_columns = list(df.columns)
    
    for internal_name, possible_names in column_mapping.items():
        matched_col = None
        for col in df_columns:
            # Check if this column matches any of the possible names
            matched_target = fuzzy_match_column(col, possible_names, threshold=0.5)
            if matched_target:
                matched_col = col
                break
        
        found_columns[internal_name] = matched_col
    
    return found_columns


def detect_format(df: pd.DataFrame) -> Literal["fidelity", "chase", "generic", "unknown"]:
    """Detect CSV format based on column headers using fuzzy matching."""
    columns = set(df.columns)
    columns_lower = {c.lower().strip() for c in columns}
    
    # Check for Fidelity format - look for Symbol, Quantity, Current Value, Cost Basis Total, Type
    fidelity_indicators = [
        ["symbol"],
        ["quantity", "qty", "shares"],
        ["current value", "currentvalue", "value"],
        ["cost basis total", "costbasis", "cost basis"],
        ["type"]
    ]
    fidelity_matches = sum(
        1 for indicator_list in fidelity_indicators
        if any(indicator in col_lower for col_lower in columns_lower for indicator in indicator_list)
    )
    if fidelity_matches >= 4:  # Need at least 4 out of 5 indicators
        return "fidelity"
    
    # Check for Chase format - look for Ticker, Quantity, Value, Cost
    chase_indicators = [
        ["ticker"],
        ["quantity", "qty"],
        ["value"],
        ["cost"]
    ]
    chase_matches = sum(
        1 for indicator_list in chase_indicators
        if any(indicator in col_lower for col_lower in columns_lower for indicator in indicator_list)
    )
    if chase_matches >= 3:  # Need at least 3 out of 4 indicators
        return "chase"
    
    # Check for Generic format (only needs ticker, shares, cost_basis)
    generic_required = {"ticker", "shares", "cost_basis"}
    if generic_required.issubset(columns_lower):
        return "generic"
    
    return "unknown"


def parse_numeric(value) -> float:
    """Parse numeric value, handling commas, dollar signs, and empty strings."""
    if pd.isna(value) or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    # Remove commas, dollar signs, and whitespace, then convert
    value_str = str(value).replace(",", "").replace("$", "").strip()
    if value_str == "":
        return 0.0
    return float(value_str)


def parse_chase_csv(df: pd.DataFrame) -> Tuple[List[dict], List[dict]]:
    """
    Parse Chase brokerage CSV format with fuzzy column matching.
    
    Returns:
        Tuple of (holdings, excluded_items)
    """
    holdings = []
    excluded = []
    
    # Find columns using fuzzy matching
    column_mapping = {
        "ticker": ["Ticker", "ticker", "TICKER", "Symbol", "symbol"],
        "name": ["Description", "description", "Name", "name"],
        "shares": ["Quantity", "quantity", "Shares", "shares", "Qty", "qty"],
        "cost_basis": ["Cost", "cost", "Cost Basis", "cost basis"],
        "asset_class": ["Asset Class", "asset class", "AssetClass"]
    }
    
    found_columns = find_columns_fuzzy(df, column_mapping)
    
    ticker_col = found_columns.get("ticker")
    shares_col = found_columns.get("shares")
    cost_basis_col = found_columns.get("cost_basis")
    name_col = found_columns.get("name")
    asset_class_col = found_columns.get("asset_class")
    
    if not ticker_col:
        raise ValueError(f"Chase CSV missing Ticker column. Found columns: {list(df.columns)}")
    
    for _, row in df.iterrows():
        ticker = str(row.get(ticker_col, "")).strip().upper() if ticker_col else ""
        
        # Stop at footnotes section
        if ticker == "FOOTNOTES":
            break
        if asset_class_col:
            asset_class = str(row.get(asset_class_col, "")).strip()
            if asset_class == "FOOTNOTES":
                break
        
        # Skip empty rows or rows without ticker
        if not ticker or pd.isna(row.get(ticker_col)):
            continue
        
        # Skip cash equivalents
        if ticker in CASH_EQUIVALENTS:
            excluded.append({
                "ticker": ticker,
                "reason": "cash_equivalent"
            })
            continue
        
        # Parse values
        try:
            shares = parse_numeric(row.get(shares_col, 0)) if shares_col else 0
            cost_basis = parse_numeric(row.get(cost_basis_col, 0)) if cost_basis_col else 0
            
            # Skip if no shares (invalid row)
            if shares <= 0:
                continue
            
            # Get name if available
            name = None
            if name_col:
                name = str(row.get(name_col, "")).strip()
                if name == "" or name.lower() == "nan":
                    name = None
            
            holdings.append({
                "ticker": ticker,
                "name": name,
                "shares": shares,
                "cost_basis": cost_basis,
                # market_value and gain_loss_pct removed - calculated dynamically on frontend
            })
        except (ValueError, TypeError) as e:
            # Skip malformed rows
            logger.warning(f"Skipping malformed row for ticker {ticker}: {e}")
            continue
    
    return holdings, excluded


def parse_generic_csv(df: pd.DataFrame) -> Tuple[List[dict], List[dict]]:
    """
    Parse generic CSV format with columns: ticker, shares, cost_basis
    
    Note: market_value and gain_loss_pct are calculated dynamically on the frontend.
    
    Returns:
        Tuple of (holdings, excluded_items)
    """
    # Normalize column names to lowercase
    df.columns = df.columns.str.lower().str.strip()
    
    holdings = []
    excluded = []
    
    for _, row in df.iterrows():
        ticker = str(row.get("ticker", "")).strip().upper()
        
        # Skip empty rows
        if not ticker:
            continue
        
        # Skip cash equivalents
        if ticker in CASH_EQUIVALENTS:
            excluded.append({
                "ticker": ticker,
                "reason": "cash_equivalent"
            })
            continue
        
        try:
            shares = parse_numeric(row.get("shares", 0))
            cost_basis = parse_numeric(row.get("cost_basis", 0))
            
            # Skip if no shares
            if shares <= 0:
                continue
            
            holdings.append({
                "ticker": ticker,
                "name": None,  # Optional - can be fetched separately if needed
                "shares": shares,
                "cost_basis": cost_basis,
                # market_value and gain_loss_pct removed - calculated dynamically on frontend
            })
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed row for ticker {ticker}: {e}")
            continue
    
    return holdings, excluded


def parse_fidelity_csv(df: pd.DataFrame) -> Tuple[List[dict], List[dict]]:
    """
    Parse Fidelity brokerage CSV format with fuzzy column matching.
    
    Expected columns: Symbol, Description, Quantity, Current Value, Cost Basis Total, Type
    
    Returns:
        Tuple of (holdings, excluded_items)
    """
    holdings = []
    excluded = []
    
    # Find columns using fuzzy matching
    column_mapping = {
        "ticker": ["Symbol", "symbol", "Ticker", "ticker", "SYMBOL"],
        "name": ["Description", "description", "Description", "Name", "name"],
        "shares": ["Quantity", "quantity", "Shares", "shares", "Qty", "qty"],
        "cost_basis": ["Cost Basis Total", "cost basis total", "Cost Basis", "cost basis", "Cost", "cost"],
        "market_value": ["Current Value", "current value", "CurrentValue", "Value", "value"],
        "type": ["Type", "type", "TYPE"]
    }
    
    found_columns = find_columns_fuzzy(df, column_mapping)
    
    # Check if we have minimum required columns
    if not found_columns.get("ticker") or not found_columns.get("shares"):
        raise ValueError(
            f"Fidelity CSV missing required columns. Found columns: {list(df.columns)}. "
            f"Need at least: Symbol (or similar), Quantity (or similar)"
        )
    
    ticker_col = found_columns["ticker"]
    shares_col = found_columns["shares"]
    cost_basis_col = found_columns.get("cost_basis")
    name_col = found_columns.get("name")
    type_col = found_columns.get("type")
    
    for _, row in df.iterrows():
        ticker = str(row.get(ticker_col, "")).strip().upper() if ticker_col else ""
        
        # Skip empty rows or rows without ticker
        if not ticker or pd.isna(row.get(ticker_col)):
            continue
        
        # Skip cash items - check Type column if available, or ticker in cash equivalents
        if type_col:
            row_type = str(row.get(type_col, "")).strip().lower()
            if row_type == "cash":
                excluded.append({
                    "ticker": ticker,
                    "reason": "cash_equivalent"
                })
                continue
        
        # Skip cash equivalents by ticker
        if ticker in CASH_EQUIVALENTS:
            excluded.append({
                "ticker": ticker,
                "reason": "cash_equivalent"
            })
            continue
        
        # Parse values
        try:
            shares = parse_numeric(row.get(shares_col, 0)) if shares_col else 0
            
            # Get cost basis - try Cost Basis Total first, fallback to calculating from Average Cost Basis
            if cost_basis_col:
                cost_basis = parse_numeric(row.get(cost_basis_col, 0))
            else:
                # Try to find Average Cost Basis column
                avg_cost_col = None
                for col in df.columns:
                    if fuzzy_match_column(col, ["Average Cost Basis", "average cost basis", "Avg Cost", "avg cost"], threshold=0.6):
                        avg_cost_col = col
                        break
                
                if avg_cost_col and shares > 0:
                    avg_cost = parse_numeric(row.get(avg_cost_col, 0))
                    cost_basis = avg_cost * shares
                else:
                    cost_basis = 0
            
            # Skip if no shares (invalid row)
            if shares <= 0:
                continue
            
            # Get name if available
            name = None
            if name_col:
                name = str(row.get(name_col, "")).strip()
                if name == "" or name.lower() == "nan":
                    name = None
            
            holdings.append({
                "ticker": ticker,
                "name": name,
                "shares": shares,
                "cost_basis": cost_basis,
                # market_value and gain_loss_pct removed - calculated dynamically on frontend
            })
        except (ValueError, TypeError) as e:
            # Skip malformed rows
            logger.warning(f"Skipping malformed row for ticker {ticker}: {e}")
            continue
    
    return holdings, excluded


def calculate_portfolio_percentages(holdings: List[dict]) -> List[dict]:
    """Add percent_of_portfolio to each holding."""
    total_value = sum(h["market_value"] for h in holdings if h["market_value"] is not None)
    
    if total_value <= 0:
        return holdings
    
    for holding in holdings:
        if holding["market_value"] is not None:
            holding["percent_of_portfolio"] = round(
                (holding["market_value"] / total_value) * 100, 
                2
            )
        else:
            holding["percent_of_portfolio"] = 0.0
    
    # Sort by percent_of_portfolio descending
    holdings.sort(key=lambda h: h.get("percent_of_portfolio", 0), reverse=True)
    
    return holdings


async def enrich_holdings_with_prices(
    holdings: List[dict], 
    fmp_service: "FMPService"
) -> List[dict]:
    """
    Fetch current prices from FMP and calculate market_value for each holding.
    
    Used for generic CSV format where market_value is not provided.
    
    Args:
        holdings: List of holdings with shares and cost_basis but no market_value
        fmp_service: FMP service instance for API calls
    
    Returns:
        Holdings enriched with market_value, gain_loss_pct, and name
    """
    if not holdings:
        return holdings
    
    # Get unique tickers
    tickers = list(set(h["ticker"] for h in holdings))
    
    # Batch fetch quotes from FMP (1 API call)
    # Endpoint: /quote/AMD,META,GOOGL
    ticker_string = ",".join(tickers)
    quotes = await fmp_service.get_batch_quotes(ticker_string)
    
    # Create lookup map
    price_map = {q["symbol"]: q for q in quotes}
    
    # Enrich holdings
    enriched = []
    for holding in holdings:
        ticker = holding["ticker"]
        quote = price_map.get(ticker)
        
        if not quote:
            # Skip holdings we couldn't get prices for
            logger.warning(f"Could not fetch price for ticker {ticker}")
            continue
        
        current_price = quote.get("price", 0)
        market_value = holding["shares"] * current_price
        cost_basis = holding["cost_basis"]
        
        # Calculate gain/loss
        if cost_basis > 0:
            gain_loss_pct = ((market_value - cost_basis) / cost_basis) * 100
        else:
            gain_loss_pct = 0.0
        
        enriched.append({
            "ticker": ticker,
            "name": quote.get("name", ""),
            "shares": holding["shares"],
            "cost_basis": cost_basis,
            "market_value": round(market_value, 2),
            "gain_loss_pct": round(gain_loss_pct, 2),
            "current_price": current_price,  # Bonus: include for UI
            "pe_ratio": quote.get("pe"),  # Bonus: include for UI
        })
    
    return enriched


async def enrich_chase_holdings_with_prices(
    holdings: List[dict],
    fmp_service: "FMPService"
) -> List[dict]:
    """
    Enrich Chase CSV holdings with current_price and pe_ratio from FMP.
    
    Chase CSV already has market_value, but we fetch price and P/E for UI display.
    
    Args:
        holdings: List of holdings from Chase CSV (already has market_value)
        fmp_service: FMP service instance for API calls
    
    Returns:
        Holdings enriched with current_price and pe_ratio
    """
    if not holdings:
        return holdings
    
    # Get unique tickers
    tickers = list(set(h["ticker"] for h in holdings))
    
    # Batch fetch quotes from FMP (1 API call)
    ticker_string = ",".join(tickers)
    quotes = await fmp_service.get_batch_quotes(ticker_string)
    
    # Create lookup map
    price_map = {q["symbol"]: q for q in quotes}
    
    # Enrich holdings
    enriched = []
    for holding in holdings:
        ticker = holding["ticker"]
        quote = price_map.get(ticker)
        
        if quote:
            holding["current_price"] = quote.get("price")
            holding["pe_ratio"] = quote.get("pe")
        else:
            holding["current_price"] = None
            holding["pe_ratio"] = None
        
        enriched.append(holding)
    
    return enriched


def parse_portfolio_csv(
    csv_content: str, 
    format_hint: Literal["fidelity", "chase", "generic", "auto"] = "auto"
) -> Tuple[dict, bool]:
    """
    Main entry point for parsing portfolio CSV.
    
    Args:
        csv_content: Raw CSV string content
        format_hint: Format hint or "auto" to detect (format_hint is kept for backward compatibility but ignored)
    
    Returns:
        Tuple of (parsed_data dict, needs_price_enrichment bool)
        - Fidelity format: needs_price_enrichment = False
        - Chase format: needs_price_enrichment = False
        - Generic format: needs_price_enrichment = True
    """
    # Read CSV into DataFrame
    # Handle potential BOM and encoding issues
    df = pd.read_csv(StringIO(csv_content), encoding='utf-8-sig')
    
    # Remove completely empty rows
    df = df.dropna(how='all')
    
    # Always auto-detect format (format_hint parameter kept for backward compatibility)
    detected_format = detect_format(df)
    
    # Parse based on format
    if detected_format == "fidelity":
        holdings, excluded = parse_fidelity_csv(df)
        needs_enrichment = False
    elif detected_format == "chase":
        holdings, excluded = parse_chase_csv(df)
        needs_enrichment = False
    elif detected_format == "generic":
        holdings, excluded = parse_generic_csv(df)
        needs_enrichment = True
    else:
        raise ValueError(
            f"Unknown CSV format. Could not detect Fidelity, Chase, or Generic format. "
            f"Found columns: {list(df.columns)}. "
            f"Expected columns for Fidelity: Symbol, Quantity, Current Value, Cost Basis Total, Type. "
            f"Expected columns for Chase: Ticker, Quantity, Value, Cost. "
            f"Expected columns for Generic: ticker, shares, cost_basis."
        )
    
    if not holdings:
        raise ValueError("No valid holdings found in CSV")
    
    return {
        "holdings": holdings,
        "detected_format": detected_format,
        "excluded_items": excluded,
    }, needs_enrichment


def finalize_portfolio_response(holdings: List[dict], excluded: List[dict], detected_format: str) -> dict:
    """
    Finalize portfolio response with only static data.
    
    Dynamic values (market_value, gain_loss_pct, percent_of_portfolio) are calculated on frontend.
    """
    # Calculate only total cost basis (static value)
    total_cost_basis = sum(h["cost_basis"] for h in holdings)
    
    return {
        "holdings": holdings,
        "total_cost_basis": round(total_cost_basis, 2),
        "detected_format": detected_format,
        "excluded_items": excluded,
    }

