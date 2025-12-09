"""Service for saving and retrieving user projection inputs."""
import logging
from typing import Optional, Dict
from datetime import datetime, timezone
from core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class ProjectionsSaveService:
    """Service for managing saved user projection inputs."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.client = get_supabase_client()
    
    def save_projection(self, user_id: str, ticker: str, data: Dict) -> None:
        """
        Save or update projection inputs for a user and ticker.
        
        Args:
            user_id: User ID (Clerk user ID from JWT 'sub' field)
            ticker: Stock ticker symbol (uppercased)
            data: Dictionary with scenarios (bear_case, base_case, bull_case)
                Each scenario contains: revenue_growth, net_income_growth, pe_low_est, pe_high_est
        
        Raises:
            Exception: If database operation fails
        """
        try:
            ticker = ticker.upper()
            
            # Prepare projections JSONB with all scenarios
            projections_data = {
                'bear_case': {
                    'revenue_growth': data.get('bear_case', {}).get('revenue_growth', []),
                    'net_income_growth': data.get('bear_case', {}).get('net_income_growth', []),
                    'pe_low_est': data.get('bear_case', {}).get('pe_low_est', []),
                    'pe_high_est': data.get('bear_case', {}).get('pe_high_est', [])
                },
                'base_case': {
                    'revenue_growth': data.get('base_case', {}).get('revenue_growth', []),
                    'net_income_growth': data.get('base_case', {}).get('net_income_growth', []),
                    'pe_low_est': data.get('base_case', {}).get('pe_low_est', []),
                    'pe_high_est': data.get('base_case', {}).get('pe_high_est', [])
                },
                'bull_case': {
                    'revenue_growth': data.get('bull_case', {}).get('revenue_growth', []),
                    'net_income_growth': data.get('bull_case', {}).get('net_income_growth', []),
                    'pe_low_est': data.get('bull_case', {}).get('pe_low_est', []),
                    'pe_high_est': data.get('bull_case', {}).get('pe_high_est', [])
                }
            }
            
            # Check if projection already exists
            existing_response = self.client.table('saved_projections').select(
                'id'
            ).eq('user_id', user_id).eq('ticker', ticker).execute()
            
            if existing_response.data and len(existing_response.data) > 0:
                # Update existing record
                update_data = {
                    'projections': projections_data,
                    'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                }
                response = self.client.table('saved_projections').update(update_data).eq(
                    'user_id', user_id
                ).eq('ticker', ticker).execute()
                logger.info(f"✅ Updated projections for user {user_id}, ticker {ticker}")
            else:
                # Insert new record
                projection_data = {
                    'user_id': user_id,
                    'ticker': ticker,
                    'projections': projections_data,
                    'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                }
                response = self.client.table('saved_projections').insert(projection_data).execute()
                logger.info(f"✅ Created new projections for user {user_id}, ticker {ticker}")
            
        except Exception as e:
            logger.error(f"Error saving projection for user {user_id}, ticker {ticker}: {str(e)}")
            raise
    
    def get_projection(self, user_id: str, ticker: str) -> Optional[Dict]:
        """
        Retrieve saved projection inputs for a user and ticker.
        
        Args:
            user_id: User ID (Clerk user ID from JWT 'sub' field)
            ticker: Stock ticker symbol (uppercased)
        
        Returns:
            Dictionary with projection data and updated_at timestamp, or None if not found
            Format: {
                'data': {
                    'bear_case': {
                        'revenue_growth': [10.0, 10.0, 10.0, 10.0],
                        'net_income_growth': [6.5, 32.1, 0.0, 0.0],
                        'pe_low_est': [0.0, 0.0, 0.0, 0.0, 0.0],
                        'pe_high_est': [0.0, 0.0, 0.0, 0.0, 0.0]
                    },
                    'base_case': {...},
                    'bull_case': {...}
                },
                'updated_at': '2025-12-09T08:18:47Z'
            }
        """
        try:
            ticker = ticker.upper()
            
            # Read from projections column (source of truth)
            # Generated columns (bear_case, base_case, bull_case) are automatically available
            response = self.client.table('saved_projections').select(
                'projections, updated_at'
            ).eq('user_id', user_id).eq('ticker', ticker).execute()
            
            if not response.data or len(response.data) == 0:
                logger.info(f"No saved projections found for user {user_id}, ticker {ticker}")
                return None
            
            projection = response.data[0]
            projections = projection.get('projections')
            
            if not projections:
                return None
            
            # Helper function to convert value to list
            def to_list(value):
                """Convert dict to list if needed, or return list as-is."""
                if value is None:
                    return []
                if isinstance(value, dict):
                    # If dict has numeric keys (years), convert to sorted list
                    try:
                        sorted_items = sorted(value.items(), key=lambda x: int(x[0]))
                        return [float(v) for _, v in sorted_items]
                    except (ValueError, TypeError):
                        # If conversion fails, return empty list
                        return []
                if isinstance(value, list):
                    return value
                return []
            
            # Format scenarios from projections JSONB
            formatted_scenarios = {}
            for scenario_name in ['bear_case', 'base_case', 'bull_case']:
                scenario_data = projections.get(scenario_name)
                if scenario_data and isinstance(scenario_data, dict):
                    # Scenario data is a dict with revenue_growth, net_income_growth, etc.
                    formatted_scenarios[scenario_name] = {
                        'revenue_growth': to_list(scenario_data.get('revenue_growth')),
                        'net_income_growth': to_list(scenario_data.get('net_income_growth')),
                        'pe_low_est': to_list(scenario_data.get('pe_low_est')),
                        'pe_high_est': to_list(scenario_data.get('pe_high_est'))
                    }
                else:
                    # If scenario is missing or invalid, return empty lists
                    formatted_scenarios[scenario_name] = {
                        'revenue_growth': [],
                        'net_income_growth': [],
                        'pe_low_est': [],
                        'pe_high_est': []
                    }
            
            # Check if we have any data
            has_data = any(
                any(formatted_scenarios[scenario].values())
                for scenario in ['bear_case', 'base_case', 'bull_case']
            )
            
            if not has_data:
                return None
            
            result = {
                'data': formatted_scenarios,
                'updated_at': projection.get('updated_at')
            }
            
            logger.info(f"✅ Retrieved saved projections for user {user_id}, ticker {ticker}")
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving projection for user {user_id}, ticker {ticker}: {str(e)}")
            raise
    
    def delete_projection(self, user_id: str, ticker: str) -> bool:
        """
        Delete saved projection inputs for a user and ticker.
        
        Args:
            user_id: User ID (Clerk user ID from JWT 'sub' field)
            ticker: Stock ticker symbol (uppercased)
        
        Returns:
            True if projection was deleted, False if not found
        """
        try:
            ticker = ticker.upper()
            
            # Check if projection exists first
            check_response = self.client.table('saved_projections').select(
                'id'
            ).eq('user_id', user_id).eq('ticker', ticker).execute()
            
            if not check_response.data or len(check_response.data) == 0:
                logger.info(f"No saved projections found to delete for user {user_id}, ticker {ticker}")
                return False
            
            # Delete the projection
            delete_response = self.client.table('saved_projections').delete().eq(
                'user_id', user_id
            ).eq('ticker', ticker).execute()
            
            logger.info(f"✅ Deleted saved projections for user {user_id}, ticker {ticker}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting projection for user {user_id}, ticker {ticker}: {str(e)}")
            raise


# Create singleton instance
projections_save_service = ProjectionsSaveService()

