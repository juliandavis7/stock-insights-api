"""Utility functions for formatting data before storing to Supabase."""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Common domain extensions that should remain lowercase
DOMAIN_EXTENSIONS = {'com', 'org', 'net', 'io', 'ai', 'co', 'tv', 'me', 'us', 'uk', 'ca', 'au', 'de', 'fr', 'jp', 'cn', 'edu', 'gov'}


def format_company_name(name: Optional[str]) -> Optional[str]:
    """
    Clean up company names by removing legal suffixes and converting to Title Case.
    
    Examples:
        "ADVANCED MICRO DEVICES INC COM" → "Advanced Micro Devices"
        "META PLATFORMS INC CLASS A COMMON STOCK" → "Meta Platforms"
        "AMAZON.COM INC" → "Amazon.com"
        "Amazon.Com, Inc." → "Amazon.com"
        "NIKE INC CLASS B COM" → "Nike"
    
    Args:
        name: Raw company name (can be None)
    
    Returns:
        Formatted company name or None if input was None
    """
    if not name:
        return name
    
    # Normalize to uppercase for suffix matching
    formatted = name.upper().strip()
    
    # Remove trailing punctuation before suffix matching
    formatted = formatted.rstrip('.,;')
    
    # Suffixes to remove (order matters - check longer ones first)
    # Also handle variations with commas (e.g., ", INC" from "Amazon.Com, Inc.")
    suffixes = [
        ", INC CLASS A COMMON STOCK",
        ", INC CLASS B COMMON STOCK", 
        ", INC CLASS C COMMON STOCK",
        " INC CLASS A COMMON STOCK",
        " INC CLASS B COMMON STOCK",
        " INC CLASS C COMMON STOCK",
        " CLASS A COMMON STOCK",
        " CLASS B COMMON STOCK",
        " CLASS C COMMON STOCK",
        " CLASS C CAPITAL STOCK",
        " CLASS A CAPITAL STOCK",
        " CLASS B CAPITAL STOCK",
        " CLASS B COM",
        " CLASS A COM",
        " CLASS C COM",
        " CL A",
        " CL B",
        " CL C",
        " COMMON STOCK",
        " INC COM",
        ", INC.",
        ", INC",
        " INC.",
        " COM",
        " INC",
        ", LTD.",
        ", LTD",
        " LTD.",
        " LTD",
        ", CORP.",
        ", CORP",
        " CORP.",
        " CORP",
        " CORPORATION",
        ", PLC",
        " PLC",
        ", LLC",
        " LLC",
        ", LP",
        " LP",
        " L.P.",
        " L.L.C.",
    ]
    
    # Remove suffixes - keep trying until no more suffixes are found
    # This handles cases like "ALPHABET INC CLASS C CAPITAL STOCK" 
    # where we need to remove both "CLASS C CAPITAL STOCK" and "INC"
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if formatted.endswith(suffix):
                formatted = formatted[:-len(suffix)].strip()
                changed = True
                break
    
    # Remove any trailing punctuation left over
    formatted = formatted.rstrip('.,;')
    
    # Convert to Title Case with special handling for domains
    words = formatted.split()
    result = []
    
    for word in words:
        # Check if word contains a domain-style pattern (e.g., AMAZON.COM)
        if '.' in word:
            # Handle domain names like AMAZON.COM or EXAMPLE.CO.UK
            word = _format_domain_word(word)
        else:
            word = word.capitalize()
        result.append(word)
    
    return ' '.join(result)


def _format_domain_word(word: str) -> str:
    """
    Format a word that contains dots (likely a domain name).
    
    Examples:
        "AMAZON.COM" → "Amazon.com"
        "AMAZON.COM," → "Amazon.com"
        "EXAMPLE.CO.UK" → "Example.co.uk"
    """
    # Strip trailing punctuation but remember it
    trailing_punct = ''
    while word and word[-1] in '.,;:!?':
        trailing_punct = word[-1] + trailing_punct
        word = word[:-1]
    
    parts = word.split('.')
    formatted_parts = []
    
    # Find where domain extensions start (from the end)
    # e.g., in "EXAMPLE.CO.UK" -> "co" and "uk" are both extensions
    extension_start_idx = len(parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].lower() in DOMAIN_EXTENSIONS:
            extension_start_idx = i
        else:
            break
    
    for i, part in enumerate(parts):
        if i >= extension_start_idx:
            # This is a domain extension - keep lowercase
            formatted_parts.append(part.lower())
        else:
            # Regular part - capitalize
            formatted_parts.append(part.capitalize())
    
    return '.'.join(formatted_parts)

