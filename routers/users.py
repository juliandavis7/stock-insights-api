"""Users endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse

from auth import verify_token
from services.supabase_service import SupabaseService
from rate_limit import user_limiter, HEALTH_USER_LIMIT

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/users")
@user_limiter.limit(HEALTH_USER_LIMIT)  # Reusing health endpoint rate limits
def get_users(
    request: Request,
    user: Dict = Depends(verify_token)
):
    """
    Get all users from the Supabase users table.
    
    Returns:
        List of all users with their details
    """
    try:
        logger.info(f"📊 API: Fetching all users from Supabase")
        
        # Initialize Supabase service
        supabase_service = SupabaseService()
        
        # Fetch all users using the service
        users = supabase_service.get_all_users()
        
        logger.info(f"✅ API: Successfully fetched {len(users)} users")
        
        return JSONResponse(content={
            'success': True,
            'count': len(users),
            'users': users
        })
    
    except ValueError as e:
        # Handle missing Supabase credentials
        logger.error(f"❌ API: Supabase configuration error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "Supabase is not configured properly. Please check your environment variables."
            }
        )
    except Exception as e:
        logger.error(f"❌ API: Error fetching users: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Failed to fetch users: {str(e)}"
            }
        )

