"""Users endpoint router."""
import logging
from typing import Dict
from fastapi import APIRouter, Depends, Request, HTTPException, Path
from fastapi.responses import JSONResponse

from core.auth import verify_token
from services.supabase_service import SupabaseService
from core.rate_limit import user_limiter, HEALTH_USER_LIMIT

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


@router.delete("/users/{clerk_user_id}")
@user_limiter.limit(HEALTH_USER_LIMIT)  # Reusing health endpoint rate limits
def delete_user(
    request: Request,
    clerk_user_id: str = Path(..., description="Clerk user ID to delete"),
    user: Dict = Depends(verify_token)
):
    """
    Delete a user by Clerk user ID.
    
    Args:
        clerk_user_id: The Clerk user ID to delete
        
    Returns:
        Success message if user was deleted
        
    Raises:
        404: If user not found
        500: If deletion fails
    """
    try:
        logger.info(f"🗑️  API: Deleting user: {clerk_user_id}")
        
        # Initialize Supabase service
        supabase_service = SupabaseService()
        
        # Delete the user
        deleted = supabase_service.delete_user(clerk_user_id)
        
        if not deleted:
            logger.warning(f"⚠️  API: User {clerk_user_id} not found for deletion")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": f"User {clerk_user_id} not found"
                }
            )
        
        logger.info(f"✅ API: Successfully deleted user {clerk_user_id}")
        
        return JSONResponse(content={
            'success': True,
            'message': f'User {clerk_user_id} deleted successfully',
            'clerk_user_id': clerk_user_id
        })
    
    except HTTPException:
        raise
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
        logger.error(f"❌ API: Error deleting user {clerk_user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Failed to delete user: {str(e)}"
            }
        )

