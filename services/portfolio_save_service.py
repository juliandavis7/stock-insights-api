"""Service for saving and retrieving user portfolios."""
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
from core.supabase_client import get_supabase_client
from services.formatting import format_company_name

logger = logging.getLogger(__name__)


class PortfolioSaveService:
    """Service for managing saved user portfolios."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.client = get_supabase_client()
    
    def save_portfolio(self, user_id: str, portfolio_data: Dict) -> None:
        """
        Save or update portfolio for a user (one portfolio per user).
        Replaces all existing holdings with new ones from CSV upload.
        
        Args:
            user_id: User ID (Clerk user ID from JWT 'sub' field)
            portfolio_data: Dictionary with:
                - holdings: List of holdings (ticker, name, shares, cost_basis)
                - excluded_items: List of excluded items (not stored, only for response)
                - detected_format: "chase" or "generic"
                - total_cost_basis: Total cost basis
        
        Raises:
            Exception: If database operation fails
        """
        try:
            holdings = portfolio_data.get('holdings', [])
            detected_format = portfolio_data.get('detected_format', 'generic')
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            
            # Get or create portfolio
            existing_response = self.client.table('portfolios').select(
                'id'
            ).eq('user_id', user_id).execute()
            
            if existing_response.data and len(existing_response.data) > 0:
                # Update existing portfolio
                portfolio_id = existing_response.data[0]['id']
                self.client.table('portfolios').update({
                    'detected_format': detected_format,
                    'updated_at': now
                }).eq('user_id', user_id).execute()
                logger.info(f"✅ Updated portfolio for user {user_id}")
            else:
                # Create new portfolio
                portfolio_response = self.client.table('portfolios').insert({
                    'user_id': user_id,
                    'detected_format': detected_format,
                    'created_at': now,
                    'updated_at': now
                }).execute()
                portfolio_id = portfolio_response.data[0]['id']
                logger.info(f"✅ Created new portfolio for user {user_id}")
            
            # Delete all existing holdings for this portfolio
            self.client.table('holdings').delete().eq(
                'portfolio_id', portfolio_id
            ).execute()
            
            # Insert new holdings
            if holdings:
                holdings_to_insert = []
                for holding in holdings:
                    holdings_to_insert.append({
                        'portfolio_id': portfolio_id,
                        'user_id': user_id,
                        'ticker': holding['ticker'].upper(),
                        'name': format_company_name(holding.get('name')),
                        'shares': float(holding['shares']),
                        'cost_basis': float(holding['cost_basis']),
                        'created_at': now,
                        'updated_at': now
                    })
                
                self.client.table('holdings').insert(holdings_to_insert).execute()
                logger.info(f"✅ Inserted {len(holdings_to_insert)} holdings for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error saving portfolio for user {user_id}: {str(e)}")
            raise
    
    def get_portfolio(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve saved portfolio for a user.
        
        Args:
            user_id: User ID (Clerk user ID from JWT 'sub' field)
        
        Returns:
            Dictionary with portfolio data or None if not found
            Format: {
                'holdings': [...],
                'excluded_items': [],  # Always empty (not stored in new schema)
                'detected_format': 'chase' or 'generic',
                'total_cost_basis': 12345.67,  # Calculated from holdings
                'updated_at': '2025-01-01T00:00:00Z'
            }
        """
        try:
            # Get portfolio metadata
            portfolio_response = self.client.table('portfolios').select(
                'id, detected_format, updated_at'
            ).eq('user_id', user_id).execute()
            
            if not portfolio_response.data or len(portfolio_response.data) == 0:
                logger.info(f"No saved portfolio found for user {user_id}")
                return None
            
            portfolio = portfolio_response.data[0]
            portfolio_id = portfolio['id']
            
            # Get all holdings for this portfolio
            holdings_response = self.client.table('holdings').select(
                'ticker, name, shares, cost_basis'
            ).eq('portfolio_id', portfolio_id).execute()
            
            # Convert holdings to the expected format
            holdings = []
            total_cost_basis = 0.0
            
            for holding in holdings_response.data:
                holdings.append({
                    'ticker': holding['ticker'],
                    'name': holding.get('name'),
                    'shares': float(holding['shares']),
                    'cost_basis': float(holding['cost_basis'])
                })
                total_cost_basis += float(holding['cost_basis'])
            
            result = {
                'holdings': holdings,
                'excluded_items': [],  # Not stored in new schema
                'detected_format': portfolio.get('detected_format', 'generic'),
                'total_cost_basis': round(total_cost_basis, 2),
                'updated_at': portfolio.get('updated_at')
            }
            
            logger.info(f"✅ Retrieved saved portfolio for user {user_id} with {len(holdings)} holdings")
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving portfolio for user {user_id}: {str(e)}")
            raise
    
    def delete_portfolio(self, user_id: str) -> bool:
        """
        Delete saved portfolio for a user.
        Holdings are automatically deleted via CASCADE foreign key.
        
        Args:
            user_id: User ID (Clerk user ID from JWT 'sub' field)
        
        Returns:
            True if portfolio was deleted, False if not found
        """
        try:
            # Check if portfolio exists first
            check_response = self.client.table('portfolios').select(
                'id'
            ).eq('user_id', user_id).execute()
            
            if not check_response.data or len(check_response.data) == 0:
                logger.info(f"No saved portfolio found to delete for user {user_id}")
                return False
            
            # Delete the portfolio (holdings will be cascade deleted)
            delete_response = self.client.table('portfolios').delete().eq(
                'user_id', user_id
            ).execute()
            
            logger.info(f"✅ Deleted saved portfolio for user {user_id} (holdings cascade deleted)")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting portfolio for user {user_id}: {str(e)}")
            raise
    
    def _get_or_create_portfolio(self, user_id: str) -> str:
        """
        Get or create portfolio for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Portfolio ID (UUID string)
        """
        existing_response = self.client.table('portfolios').select(
            'id'
        ).eq('user_id', user_id).execute()
        
        if existing_response.data and len(existing_response.data) > 0:
            return existing_response.data[0]['id']
        
        # Create new portfolio
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        portfolio_response = self.client.table('portfolios').insert({
            'user_id': user_id,
            'detected_format': 'manual',  # Manual additions
            'created_at': now,
            'updated_at': now
        }).execute()
        
        return portfolio_response.data[0]['id']
    
    def get_holding(self, user_id: str, ticker: str) -> Optional[Dict]:
        """
        Get a single holding for a user.
        
        Args:
            user_id: User ID
            ticker: Ticker symbol
        
        Returns:
            Holding dict or None if not found
        """
        try:
            response = self.client.table('holdings').select(
                'ticker, name, shares, cost_basis'
            ).eq('user_id', user_id).eq('ticker', ticker.upper()).execute()
            
            if not response.data or len(response.data) == 0:
                return None
            
            holding = response.data[0]
            return {
                'ticker': holding['ticker'],
                'name': holding.get('name'),
                'shares': float(holding['shares']),
                'cost_basis': float(holding['cost_basis'])
            }
        except Exception as e:
            logger.error(f"Error getting holding {ticker} for user {user_id}: {str(e)}")
            raise
    
    def add_holding(self, user_id: str, holding_data: Dict) -> Dict:
        """
        Add a new holding to user's portfolio.
        Creates portfolio if it doesn't exist.
        
        Args:
            user_id: User ID
            holding_data: Dict with ticker, name (optional), shares (optional), cost_basis (optional)
        
        Returns:
            Created holding dict
        
        Raises:
            ValueError: If holding already exists
        """
        try:
            ticker = holding_data['ticker'].upper()
            
            # Check if holding already exists
            existing = self.get_holding(user_id, ticker)
            if existing:
                raise ValueError(f"Holding with ticker {ticker} already exists. Use PUT to update.")
            
            # Get or create portfolio
            portfolio_id = self._get_or_create_portfolio(user_id)
            
            # Insert holding
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            shares = float(holding_data.get('shares', 0.0))
            cost_basis = float(holding_data.get('cost_basis', 0.0))
            
            # Validate shares and cost_basis
            # Allow 0 for initial addition, but must be >= 0
            if shares < 0:
                raise ValueError("Shares cannot be negative")
            if cost_basis < 0:
                raise ValueError("Cost basis cannot be negative")
            
            response = self.client.table('holdings').insert({
                'portfolio_id': portfolio_id,
                'user_id': user_id,
                'ticker': ticker,
                'name': format_company_name(holding_data.get('name')),
                'shares': shares,
                'cost_basis': cost_basis,
                'created_at': now,
                'updated_at': now
            }).execute()
            
            # Update portfolio updated_at
            self.client.table('portfolios').update({
                'updated_at': now
            }).eq('id', portfolio_id).execute()
            
            logger.info(f"✅ Added holding {ticker} for user {user_id}")
            
            return {
                'ticker': ticker,
                'name': format_company_name(holding_data.get('name')),
                'shares': shares,
                'cost_basis': cost_basis
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error adding holding for user {user_id}: {str(e)}")
            raise
    
    def update_holding(self, user_id: str, ticker: str, updates: Dict) -> Dict:
        """
        Update an existing holding in user's portfolio.
        
        Args:
            user_id: User ID
            ticker: Ticker symbol to update
            updates: Dict with shares, cost_basis, name (all optional)
        
        Returns:
            Updated holding dict
        
        Raises:
            ValueError: If holding not found
        """
        try:
            ticker_upper = ticker.upper()
            
            # Check if holding exists
            existing = self.get_holding(user_id, ticker_upper)
            if not existing:
                raise ValueError(f"Holding with ticker {ticker} not found.")
            
            # Build update dict
            update_data = {}
            if 'shares' in updates:
                shares = float(updates['shares'])
                if shares < 0:
                    raise ValueError("Shares cannot be negative")
                update_data['shares'] = shares
            if 'cost_basis' in updates:
                cost_basis = float(updates['cost_basis'])
                if cost_basis < 0:
                    raise ValueError("Cost basis cannot be negative")
                update_data['cost_basis'] = cost_basis
            if 'name' in updates:
                update_data['name'] = format_company_name(updates['name'])
            
            if not update_data:
                raise ValueError("No fields provided to update")
            
            # Update holding
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            update_data['updated_at'] = now
            
            self.client.table('holdings').update(update_data).eq(
                'user_id', user_id
            ).eq('ticker', ticker_upper).execute()
            
            # Update portfolio updated_at
            portfolio_response = self.client.table('holdings').select(
                'portfolio_id'
            ).eq('user_id', user_id).eq('ticker', ticker_upper).execute()
            
            if portfolio_response.data:
                portfolio_id = portfolio_response.data[0]['portfolio_id']
                self.client.table('portfolios').update({
                    'updated_at': now
                }).eq('id', portfolio_id).execute()
            
            logger.info(f"✅ Updated holding {ticker_upper} for user {user_id}")
            
            # Return updated holding
            return self.get_holding(user_id, ticker_upper)
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating holding {ticker} for user {user_id}: {str(e)}")
            raise
    
    def delete_holding(self, user_id: str, ticker: str) -> bool:
        """
        Delete a holding from user's portfolio.
        
        Args:
            user_id: User ID
            ticker: Ticker symbol to delete
        
        Returns:
            True if deleted, False if not found
        """
        try:
            ticker_upper = ticker.upper()
            
            # Check if holding exists
            existing = self.get_holding(user_id, ticker_upper)
            if not existing:
                return False
            
            # Delete holding
            self.client.table('holdings').delete().eq(
                'user_id', user_id
            ).eq('ticker', ticker_upper).execute()
            
            # Update portfolio updated_at
            portfolio_response = self.client.table('portfolios').select(
                'id'
            ).eq('user_id', user_id).execute()
            
            if portfolio_response.data:
                portfolio_id = portfolio_response.data[0]['id']
                now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                self.client.table('portfolios').update({
                    'updated_at': now
                }).eq('id', portfolio_id).execute()
            
            logger.info(f"✅ Deleted holding {ticker_upper} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting holding {ticker} for user {user_id}: {str(e)}")
            raise


# Create singleton instance
portfolio_save_service = PortfolioSaveService()

