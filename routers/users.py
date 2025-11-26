"""Users endpoint router."""
import logging
import os
from typing import Dict, Optional
from fastapi import APIRouter, Depends, Request, HTTPException, Path, Body
from fastapi.responses import JSONResponse
import stripe

from core.auth import verify_token
from services.supabase_service import supabase_service
from core.rate_limit import user_limiter, HEALTH_USER_LIMIT
from models.requests import UpdateSubscriptionStatusRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# Ensure Stripe API key is set (needed for subscription cancellation checks)
if not stripe.api_key:
    stripe_key = os.getenv('STRIPE_SECRET_KEY')
    if stripe_key:
        stripe.api_key = stripe_key
        logger.info("✅ Stripe API key configured in users router")
    else:
        logger.warning("⚠️  STRIPE_SECRET_KEY not found - Stripe operations will fail")


def enrich_user_with_subscription_info(user_data: Dict) -> Dict:
    """
    Enrich user data with subscription end date information.
    
    Unified field structure:
    - subscription_status: 'trial' | 'active' | 'expired'
    - subscription_ends_at: Unix timestamp (null if active and not canceled)
    
    For trial users: Uses trial_ends_at from database
    For active paid users: Checks Stripe for cancellation status
    For expired users: subscription_ends_at is null
    
    Args:
        user_data: User data dictionary from Supabase
        
    Returns:
        User data dictionary with subscription_ends_at added/updated
    """
    subscription_status = user_data.get('subscription_status')
    
    # Handle trial users - use trial_ends_at from database
    if subscription_status == 'trial':
        trial_ends_at = user_data.get('trial_ends_at')
        if trial_ends_at:
            # Convert ISO datetime to Unix timestamp
            try:
                from datetime import datetime, timezone
                if isinstance(trial_ends_at, str):
                    dt = datetime.fromisoformat(trial_ends_at.replace('Z', '+00:00'))
                    user_data['subscription_ends_at'] = int(dt.timestamp())
                else:
                    user_data['subscription_ends_at'] = trial_ends_at
            except Exception as e:
                logger.warning(f"⚠️  API: Could not parse trial_ends_at: {e}")
                user_data['subscription_ends_at'] = None
        else:
            user_data['subscription_ends_at'] = None
        return user_data
    
    # Handle expired users
    if subscription_status == 'expired':
        user_data['subscription_ends_at'] = None
        return user_data
    
    # Handle active paid users - check Stripe for cancellation status
    if subscription_status == 'active':
        try:
            user_email = user_data.get('email')
            
            if not user_email:
                user_data['subscription_ends_at'] = None
                return user_data
            
            # Find Stripe customer by email
            customers = stripe.Customer.list(email=user_email, limit=1)
            
            if not customers.data:
                user_data['subscription_ends_at'] = None
                return user_data
            
            customer_id = customers.data[0].id
            
            # Get active subscriptions
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status='active',
                limit=1
            )
            
            if not subscriptions.data:
                user_data['subscription_ends_at'] = None
                return user_data
            
            subscription = subscriptions.data[0]
            cancel_at = subscription.get('cancel_at')
            cancel_at_period_end = subscription.get('cancel_at_period_end', False)
            current_period_end = subscription.get('current_period_end')
            
            # If subscription is scheduled to cancel, set subscription_ends_at
            if cancel_at or cancel_at_period_end:
                # Use cancel_at if set, otherwise use current_period_end
                user_data['subscription_ends_at'] = cancel_at if cancel_at else current_period_end
                logger.info(f"📅 User {user_data.get('clerk_user_id')} has canceled subscription ending at {user_data['subscription_ends_at']}")
            else:
                # Active subscription, not canceled - no end date
                user_data['subscription_ends_at'] = None
        
        except Exception as e:
            logger.warning(f"⚠️  API: Could not check Stripe cancellation status: {e}")
            user_data['subscription_ends_at'] = None
    
    return user_data


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
        
        # Fetch all users using the service
        users = supabase_service.get_all_users()
        
        # Remove internal fields from each user
        for user in users:
            user.pop('trial_ends_at', None)
        
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


@router.get("/users/me")
@user_limiter.limit(HEALTH_USER_LIMIT)
def get_current_user(
    request: Request,
    user: Dict = Depends(verify_token)
):
    """
    Get current authenticated user's data from Supabase.
    
    This endpoint returns the subscription status and other details
    for the currently authenticated user (from JWT token).
    
    Returns:
        User data with subscription status
        
    Raises:
        404: If user not found in database
        500: If retrieval fails
    """
    try:
        # Extract user ID from JWT token
        user_id = user.get('sub')
        
        if not user_id:
            logger.error("❌ API: User ID not found in token")
            raise HTTPException(status_code=400, detail="User ID not found in token")
        
        logger.info(f"📋 API: Fetching current user data: {user_id}")
        
        # Get the user from Supabase
        user_data = supabase_service.get_user_by_clerk_id(user_id)
        
        if not user_data:
            logger.warning(f"⚠️  API: User {user_id} not found in database")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": "User not found. Please ensure you're registered in the system."
                }
            )
        
        # Enrich user data with subscription end date info (trial or Stripe cancellation)
        user_data = enrich_user_with_subscription_info(user_data)
        
        # Remove internal field that was used for enrichment but shouldn't be in response
        user_data.pop('trial_ends_at', None)
        
        logger.info(f"✅ API: Successfully retrieved current user data for {user_id}")
        
        return JSONResponse(content={
            'success': True,
            'user': user_data
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
        logger.error(f"❌ API: Error fetching current user: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Failed to fetch user data: {str(e)}"
            }
        )


@router.get("/users/{clerk_user_id}")
@user_limiter.limit(HEALTH_USER_LIMIT)  # Reusing health endpoint rate limits
def get_user(
    request: Request,
    clerk_user_id: str = Path(..., description="Clerk user ID to retrieve"),
    user: Dict = Depends(verify_token)
):
    """
    Get a user by Clerk user ID.
    
    Args:
        clerk_user_id: The Clerk user ID to retrieve
        
    Returns:
        User data if found
        
    Raises:
        404: If user not found
        500: If retrieval fails
    """
    try:
        logger.info(f"📋 API: Fetching user: {clerk_user_id}")
        
        # Get the user
        user_data = supabase_service.get_user_by_clerk_id(clerk_user_id)
        
        if not user_data:
            logger.warning(f"⚠️  API: User {clerk_user_id} not found")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": f"User {clerk_user_id} not found"
                }
            )
        
        # Enrich user data with subscription end date info (trial or Stripe cancellation)
        user_data = enrich_user_with_subscription_info(user_data)
        
        # Remove internal field that was used for enrichment but shouldn't be in response
        user_data.pop('trial_ends_at', None)
        
        logger.info(f"✅ API: Successfully fetched user {clerk_user_id}")
        
        return JSONResponse(content={
            'success': True,
            'user': user_data
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
        logger.error(f"❌ API: Error fetching user {clerk_user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Failed to fetch user: {str(e)}"
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


@router.patch("/users/{clerk_user_id}")
@user_limiter.limit(HEALTH_USER_LIMIT)  # Reusing health endpoint rate limits
def update_user_subscription(
    request: Request,
    clerk_user_id: str = Path(..., description="Clerk user ID to update"),
    update_data: UpdateSubscriptionStatusRequest = Body(...),
    user: Dict = Depends(verify_token)
):
    """
    Update a user's subscription status.
    Supports PATCH, PUT, and POST methods.
    
    Args:
        clerk_user_id: The Clerk user ID to update
        update_data: The subscription status update data
        user: Authenticated user from JWT token
        
    Returns:
        Updated user data
        
    Raises:
        404: If user not found
        500: If update fails
    """
    try:
        logger.info(f"🔄 API: Updating subscription status for user: {clerk_user_id} to '{update_data.subscription_status}'")
        
        # Update the user's subscription status
        updated_user = supabase_service.update_subscription_status(
            clerk_user_id=clerk_user_id,
            subscription_status=update_data.subscription_status
        )
        
        if not updated_user:
            logger.warning(f"⚠️  API: User {clerk_user_id} not found for update")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": f"User not found"
                }
            )
        
        logger.info(f"✅ API: Successfully updated subscription status for user {clerk_user_id}")
        
        return JSONResponse(content={
            'success': True,
            'message': f'Subscription status updated to {update_data.subscription_status}',
            'user': updated_user
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
        logger.error(f"❌ API: Error updating user: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": f"Failed to update user: {str(e)}"
            }
        )

