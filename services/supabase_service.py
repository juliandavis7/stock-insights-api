"""
Supabase service for user management and trial tracking.
"""
from supabase import create_client, Client
from typing import Optional, Dict, Tuple, List
from datetime import datetime, timezone
import os
import logging

logger = logging.getLogger(__name__)


class SupabaseService:
    """Service for interacting with Supabase for user management and trial tracking."""
    
    def __init__(self):
        """Initialize Supabase client with service role key."""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # Use service role key!
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        
        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("✅ Supabase service initialized")
    
    async def get_or_create_user(self, clerk_user_id: str, email: Optional[str] = None) -> Dict:
        """
        Get existing user or create new user with trial.
        
        Args:
            clerk_user_id: Clerk user ID from JWT 'sub' field
            email: User email from JWT (optional)
            
        Returns:
            Dict with user data and trial status
        """
        try:
            # Try to get existing user
            response = self.client.table('users').select('*').eq('clerk_user_id', clerk_user_id).execute()
            
            if response.data and len(response.data) > 0:
                user = response.data[0]
                logger.info(f"Found existing user: {clerk_user_id}")
                return user
            
            # Create new user with trial
            new_user = {
                'clerk_user_id': clerk_user_id,
                'email': email,
                'subscription_status': 'trial',
                'is_trial_active': True
            }
            
            response = self.client.table('users').insert(new_user).execute()
            user = response.data[0]
            logger.info(f"✨ Created new user with trial: {clerk_user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {str(e)}")
            raise
    
    async def check_trial_status(self, clerk_user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user's trial is still active.
        
        Returns:
            Tuple of (is_active, error_message)
        """
        try:
            response = self.client.table('users').select('*').eq('clerk_user_id', clerk_user_id).execute()
            
            if not response.data or len(response.data) == 0:
                return False, "User not found"
            
            user = response.data[0]
            
            # Check subscription status
            if user['subscription_status'] == 'active':
                return True, None  # Paid subscriber
            
            if user['subscription_status'] != 'trial':
                return False, "Trial has ended. Please subscribe to continue."
            
            # Check trial expiration
            if not user['is_trial_active']:
                return False, "Trial has ended. Please subscribe to continue."
            
            trial_ends_at = datetime.fromisoformat(user['trial_ends_at'].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            
            if now > trial_ends_at:
                # Trial expired - update user
                self.client.table('users').update({
                    'is_trial_active': False,
                    'subscription_status': 'expired'
                }).eq('clerk_user_id', clerk_user_id).execute()
                
                return False, f"Trial expired on {trial_ends_at.strftime('%Y-%m-%d')}. Please subscribe to continue."
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking trial status: {str(e)}")
            return False, f"Error checking trial status: {str(e)}"
    
    async def log_api_usage(self, clerk_user_id: str, endpoint: str, ticker: Optional[str] = None, 
                           fmp_calls: int = 0, status_code: int = 200):
        """Log API usage for analytics and potential rate limiting."""
        try:
            # Get user ID
            user_response = self.client.table('users').select('id').eq('clerk_user_id', clerk_user_id).execute()
            if not user_response.data:
                return
            
            user_id = user_response.data[0]['id']
            
            # Insert usage log
            self.client.table('api_usage').insert({
                'user_id': user_id,
                'endpoint': endpoint,
                'ticker': ticker,
                'fmp_calls_used': fmp_calls,
                'response_status': status_code
            }).execute()
            
            # Update user's last API call and total count
            self.client.table('users').update({
                'last_api_call_at': datetime.now(timezone.utc).isoformat(),
                'api_calls_count': user_response.data[0].get('api_calls_count', 0) + 1
            }).eq('clerk_user_id', clerk_user_id).execute()
            
        except Exception as e:
            logger.error(f"Error logging API usage: {str(e)}")
            # Don't raise - logging shouldn't break the API
    
    def get_all_users(self) -> List[Dict]:
        """
        Get all users from the users table.
        
        Returns:
            List of all users with their details
        """
        try:
            response = self.client.table('users').select('*').execute()
            logger.info(f"✅ Fetched {len(response.data)} users from Supabase")
            return response.data
        except Exception as e:
            logger.error(f"Error fetching all users: {str(e)}")
            raise
    
    def get_user_by_clerk_id(self, clerk_user_id: str) -> Optional[Dict]:
        """
        Get a single user by Clerk user ID.
        
        Args:
            clerk_user_id: Clerk user ID from JWT 'sub' field
            
        Returns:
            User data or None if not found
        """
        try:
            response = self.client.table('users').select('*').eq('clerk_user_id', clerk_user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching user {clerk_user_id}: {str(e)}")
            raise

