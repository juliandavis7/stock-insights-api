"""
Data validation module for stock scraping results.

Validates that all expected metrics are present and properly populated
for each page type (search, income_statement, projections).
"""

from typing import Dict, List, Any, Optional, Union


class ValidationResult:
    """Container for validation results."""
    
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.page_results: Dict[str, Dict[str, Any]] = {}
    
    def add_error(self, message: str):
        """Add an error message and mark as invalid."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
    
    def set_page_result(self, page_name: str, is_valid: bool, errors: List[str], warnings: List[str]):
        """Set validation results for a specific page."""
        self.page_results[page_name] = {
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings
        }
        if not is_valid:
            self.is_valid = False
    
    def __repr__(self):
        status = "VALID" if self.is_valid else "INVALID"
        return f"ValidationResult(ticker={self.ticker}, status={status}, errors={len(self.errors)}, warnings={len(self.warnings)})"


# Expected metrics for each page type
EXPECTED_SEARCH_METRICS = [
    "ttm_pe",
    "ttm_ps_ratio",
    "forward_pe",
    "forward_ps_ratio",
    "two_year_forward_pe",
    "ttm_eps_growth",
    "current_year_eps_growth",
    "next_year_eps_growth",
    "ttm_revenue_growth",
    "current_year_revenue_growth",
    "next_year_revenue_growth",
    "gross_margin",
    "net_margin",
    "last_year_eps_growth",
    "ttm_vs_ntm_eps_growth",
    "current_quarter_eps_growth_vs_previous_year",
    "two_year_stack_exp_eps_growth",
    "last_year_revenue_growth",
    "ttm_vs_ntm_revenue_growth",
    "current_quarter_revenue_growth_vs_previous_year",
    "two_year_stack_exp_revenue_growth",
    "peg_ratio",
    "return_on_equity",
    "price_to_book",
    "price_to_free_cash_flow",
    "free_cash_flow_yield",
    "dividend_yield",
    "dividend_payout_ratio",
]

EXPECTED_INCOME_STATEMENT_METRICS = [
    "total_revenue",
    "cost_of_revenue",
    "gross_profit",
    "sga",
    "rnd",
    "total_opex",
    "operating_income",
    "net_income",
    "basic_eps",
    "diluted_eps",
]

EXPECTED_PROJECTIONS_METRICS = [
    "revenue",
    "net_income",
    "eps",
    "net_income_margin",
    "data_year",
]


def is_numeric(value: Any) -> bool:
    """Check if a value is numeric (int or float), including infinity."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        # Accept infinity values as valid numeric
        return True
    return False


def validate_search_metrics(search_data: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
    """
    Validate search page metrics.
    
    Args:
        search_data: Dictionary containing search page metrics
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    if not isinstance(search_data, dict):
        errors.append("Search data must be a dictionary")
        return False, errors, warnings
    
    # Check for missing metrics
    missing_metrics = []
    for metric in EXPECTED_SEARCH_METRICS:
        if metric not in search_data:
            missing_metrics.append(metric)
    
    if missing_metrics:
        errors.append(f"Missing search metrics: {', '.join(missing_metrics)}")
    
    # Check for null values and type validation
    for metric in EXPECTED_SEARCH_METRICS:
        if metric not in search_data:
            continue  # Already reported as missing
        
        value = search_data[metric]
        
        if value is None:
            errors.append(f"Search metric '{metric}' is null")
        elif not is_numeric(value):
            errors.append(f"Search metric '{metric}' must be numeric, got {type(value).__name__}: {value}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_income_statement_metrics(income_statement_data: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
    """
    Validate income statement metrics.
    
    Args:
        income_statement_data: Dictionary containing income statement data with 'years' and 'metrics'
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    if not isinstance(income_statement_data, dict):
        errors.append("Income statement data must be a dictionary")
        return False, errors, warnings
    
    # Check for 'years' key
    if 'years' not in income_statement_data:
        errors.append("Income statement data missing 'years' array")
        return False, errors, warnings
    
    years = income_statement_data['years']
    if not isinstance(years, list):
        errors.append("'years' must be a list")
        return False, errors, warnings
    
    if len(years) == 0:
        errors.append("'years' array is empty")
        return False, errors, warnings
    
    # Validate years are integers
    for i, year in enumerate(years):
        if not isinstance(year, int):
            errors.append(f"'years'[{i}] must be an integer, got {type(year).__name__}: {year}")
    
    # Check for 'metrics' key
    if 'metrics' not in income_statement_data:
        errors.append("Income statement data missing 'metrics' object")
        return False, errors, warnings
    
    metrics = income_statement_data['metrics']
    if not isinstance(metrics, dict):
        errors.append("'metrics' must be a dictionary")
        return False, errors, warnings
    
    # Check for missing metrics
    missing_metrics = []
    for metric in EXPECTED_INCOME_STATEMENT_METRICS:
        if metric not in metrics:
            missing_metrics.append(metric)
    
    if missing_metrics:
        errors.append(f"Missing income statement metrics: {', '.join(missing_metrics)}")
    
    # Validate each metric array
    expected_length = len(years)
    for metric in EXPECTED_INCOME_STATEMENT_METRICS:
        if metric not in metrics:
            continue  # Already reported as missing
        
        metric_array = metrics[metric]
        
        if not isinstance(metric_array, list):
            errors.append(f"Income statement metric '{metric}' must be a list, got {type(metric_array).__name__}")
            continue
        
        # Check array length matches years length
        if len(metric_array) != expected_length:
            errors.append(
                f"Income statement metric '{metric}' array length ({len(metric_array)}) "
                f"does not match years array length ({expected_length})"
            )
            continue
        
        # Check that at least one value is non-null
        has_non_null = False
        for i, value in enumerate(metric_array):
            if value is not None:
                has_non_null = True
                # Validate non-null values are numeric
                if not is_numeric(value):
                    errors.append(
                        f"Income statement metric '{metric}'[{i}] must be numeric or null, "
                        f"got {type(value).__name__}: {value}"
                    )
        
        if not has_non_null:
            errors.append(f"Income statement metric '{metric}' has no non-null values")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_projections_metrics(projections_data: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
    """
    Validate projections page metrics.
    
    Args:
        projections_data: Dictionary containing projections page metrics
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    if not isinstance(projections_data, dict):
        errors.append("Projections data must be a dictionary")
        return False, errors, warnings
    
    # Check for missing metrics
    missing_metrics = []
    for metric in EXPECTED_PROJECTIONS_METRICS:
        if metric not in projections_data:
            missing_metrics.append(metric)
    
    if missing_metrics:
        errors.append(f"Missing projections metrics: {', '.join(missing_metrics)}")
    
    # Validate each metric
    numeric_metrics = ["revenue", "net_income", "eps", "net_income_margin"]
    
    for metric in EXPECTED_PROJECTIONS_METRICS:
        if metric not in projections_data:
            continue  # Already reported as missing
        
        value = projections_data[metric]
        
        if value is None:
            errors.append(f"Projections metric '{metric}' is null")
            continue
        
        if metric == "data_year":
            # data_year must be an integer
            if not isinstance(value, int):
                errors.append(f"Projections metric 'data_year' must be an integer, got {type(value).__name__}: {value}")
        elif metric in numeric_metrics:
            # Other metrics must be numeric
            if not is_numeric(value):
                errors.append(f"Projections metric '{metric}' must be numeric, got {type(value).__name__}: {value}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_stock_data(ticker: str, stock_data: Dict[str, Any]) -> ValidationResult:
    """
    Validate complete stock data for all pages.
    
    Args:
        ticker: Stock ticker symbol
        stock_data: Dictionary containing stock data with keys: 'search', 'income_statement', 'projections'
        
    Returns:
        ValidationResult object with validation status and details
    """
    result = ValidationResult(ticker)
    
    if not isinstance(stock_data, dict):
        result.add_error("Stock data must be a dictionary")
        return result
    
    # Validate search page if present
    if 'search' in stock_data:
        search_data = stock_data['search']
        if search_data is not None:
            is_valid, errors, warnings = validate_search_metrics(search_data)
            result.set_page_result('search', is_valid, errors, warnings)
            for error in errors:
                result.add_error(f"Search page: {error}")
            for warning in warnings:
                result.add_warning(f"Search page: {warning}")
        else:
            result.add_error("Search page data is null")
            result.set_page_result('search', False, ["Search page data is null"], [])
    else:
        result.add_warning("Search page data not present")
    
    # Validate income statement page if present
    if 'income_statement' in stock_data:
        income_statement_data = stock_data['income_statement']
        if income_statement_data is not None:
            is_valid, errors, warnings = validate_income_statement_metrics(income_statement_data)
            result.set_page_result('income_statement', is_valid, errors, warnings)
            for error in errors:
                result.add_error(f"Income statement page: {error}")
            for warning in warnings:
                result.add_warning(f"Income statement page: {warning}")
        else:
            result.add_error("Income statement page data is null")
            result.set_page_result('income_statement', False, ["Income statement page data is null"], [])
    else:
        result.add_warning("Income statement page data not present")
    
    # Validate projections page if present
    if 'projections' in stock_data:
        projections_data = stock_data['projections']
        if projections_data is not None:
            is_valid, errors, warnings = validate_projections_metrics(projections_data)
            result.set_page_result('projections', is_valid, errors, warnings)
            for error in errors:
                result.add_error(f"Projections page: {error}")
            for warning in warnings:
                result.add_warning(f"Projections page: {warning}")
        else:
            result.add_error("Projections page data is null")
            result.set_page_result('projections', False, ["Projections page data is null"], [])
    else:
        result.add_warning("Projections page data not present")
    
    return result

