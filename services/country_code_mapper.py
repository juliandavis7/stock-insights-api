"""Mapping utility to convert full country names to ISO 2-letter country codes."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Exchange to country code mapping (fallback when yfinance doesn't provide country)
EXCHANGE_TO_COUNTRY: dict[str, str] = {
    # United States
    "NASDAQ": "us",
    "NYSE": "us",
    "AMEX": "us",
    "BTS": "us",      # BATS Global Markets
    "BATS": "us",
    "CBOE": "us",
    "ARCA": "us",     # NYSE Arca
    "OTC": "us",
    "PINK": "us",     # Pink Sheets
    "NYSEAMERICAN": "us",
    
    # Canada
    "TSX": "ca",
    "TSXV": "ca",     # TSX Venture
    "CSE": "ca",      # Canadian Securities Exchange
    "NEO": "ca",
    
    # United Kingdom
    "LSE": "gb",
    "LON": "gb",
    "AIM": "gb",      # Alternative Investment Market
    
    # Germany
    "XETRA": "de",
    "FRA": "de",      # Frankfurt
    
    # France
    "EPA": "fr",      # Euronext Paris
    
    # Netherlands
    "AMS": "nl",      # Euronext Amsterdam
    
    # Pan-European
    "EURONEXT": "eu",
    
    # Japan
    "JPX": "jp",
    "TYO": "jp",      # Tokyo
    
    # Hong Kong
    "HKEX": "hk",
    "HKG": "hk",
    
    # China
    "SSE": "cn",      # Shanghai
    "SZSE": "cn",     # Shenzhen
    "SHH": "cn",
    "SHZ": "cn",
    
    # India
    "NSE": "in",
    "BSE": "in",
    
    # Australia
    "ASX": "au",
    
    # South Korea
    "KRX": "kr",
    "KSC": "kr",
    
    # Brazil
    "SAO": "br",
    "BVMF": "br",
    
    # Mexico
    "BMV": "mx",
    
    # Switzerland
    "SWX": "ch",
    "VTX": "ch",
    
    # Sweden
    "STO": "se",
    
    # Norway
    "OSL": "no",
    
    # Denmark
    "CPH": "dk",
    
    # Finland
    "HEL": "fi",
    
    # Spain
    "BME": "es",
    
    # Italy
    "MIL": "it",
    
    # Singapore
    "SGX": "sg",
    
    # Taiwan
    "TAI": "tw",
    "TWSE": "tw",
    
    # Israel
    "TLV": "il",
    
    # South Africa
    "JSE": "za",
    
    # New Zealand
    "NZX": "nz",
}

# Mapping of common country names to ISO 2-letter codes
# This covers the most common countries for stock exchanges
COUNTRY_CODE_MAP = {
    # United States variations
    "united states": "us",
    "united states of america": "us",
    "usa": "us",
    "u.s.": "us",
    "u.s.a.": "us",
    
    # Canada
    "canada": "ca",
    
    # United Kingdom variations
    "united kingdom": "gb",
    "uk": "gb",
    "u.k.": "gb",
    "great britain": "gb",
    "england": "gb",
    
    # Other common countries
    "australia": "au",
    "germany": "de",
    "france": "fr",
    "japan": "jp",
    "china": "cn",
    "south korea": "kr",
    "korea": "kr",
    "india": "in",
    "brazil": "br",
    "mexico": "mx",
    "spain": "es",
    "italy": "it",
    "netherlands": "nl",
    "switzerland": "ch",
    "sweden": "se",
    "norway": "no",
    "denmark": "dk",
    "finland": "fi",
    "belgium": "be",
    "austria": "at",
    "ireland": "ie",
    "portugal": "pt",
    "poland": "pl",
    "russia": "ru",
    "south africa": "za",
    "singapore": "sg",
    "hong kong": "hk",
    "taiwan": "tw",
    "thailand": "th",
    "indonesia": "id",
    "malaysia": "my",
    "philippines": "ph",
    "new zealand": "nz",
    "israel": "il",
    "turkey": "tr",
    "saudi arabia": "sa",
    "uae": "ae",
    "united arab emirates": "ae",
    "argentina": "ar",
    "chile": "cl",
    "colombia": "co",
    "peru": "pe",
    "venezuela": "ve",
    "egypt": "eg",
    "nigeria": "ng",
    "kenya": "ke",
    "greece": "gr",
    "czech republic": "cz",
    "hungary": "hu",
    "romania": "ro",
    "ukraine": "ua",
}


def get_country_code_from_name(country_name: Optional[str]) -> Optional[str]:
    """
    Convert full country name to ISO 2-letter country code.
    
    Args:
        country_name: Full country name (e.g., "United States", "Canada")
    
    Returns:
        ISO 2-letter country code in lowercase (e.g., "us", "ca"), or None if not found
    """
    if not country_name:
        return None
    
    # Normalize: lowercase and strip whitespace
    normalized = country_name.lower().strip()
    
    # Direct lookup
    if normalized in COUNTRY_CODE_MAP:
        return COUNTRY_CODE_MAP[normalized]
    
    # Try partial matches for compound names
    # e.g., "United States" might come through as "United States" or variations
    for key, code in COUNTRY_CODE_MAP.items():
        if key in normalized or normalized in key:
            return code
    
    # If still not found, log a warning and return None
    logger.warning(f"Country code not found for: {country_name}")
    return None


def get_country_code(yfinance_country: Optional[str], exchange: Optional[str] = None) -> Optional[str]:
    """
    Get country code from yfinance data, with fallback to exchange mapping.
    
    Args:
        yfinance_country: Country name from yfinance (may be None)
        exchange: Exchange code (e.g., "NASDAQ", "BTS")
    
    Returns:
        Two-letter lowercase country code, or None if cannot be determined
    """
    # If yfinance provides country name, convert it to code
    if yfinance_country:
        country_code = get_country_code_from_name(yfinance_country)
        if country_code:
            return country_code
    
    # Fallback to exchange mapping
    if exchange:
        exchange_upper = exchange.upper()
        country_code = EXCHANGE_TO_COUNTRY.get(exchange_upper)
        if country_code:
            logger.debug(f"Using exchange-based country code for {exchange}: {country_code}")
            return country_code
    
    return None

