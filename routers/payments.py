"""Payment endpoint router for Polar subscription management."""
import logging
import os
import json
from typing import Dict
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Response
from fastapi.responses import JSONResponse

from core.auth import verify_token
from services.polar_service import polar_service
from services.supabase_service import supabase_service
from core.rate_limit import user_limiter, HEALTH_USER_LIMIT
from models.requests import CreateCheckoutRequest
from models.responses import CheckoutResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/payments/checkout", response_model=CheckoutResponse)
@user_limiter.limit(HEALTH_USER_LIMIT)
async def create_checkout(
    request: Request,
    response: Response,
    request_body: CreateCheckoutRequest,
    user: Dict = Depends(verify_token)
):
    """
    Create a Polar checkout session for subscription.
    
    Protected endpoint - requires Clerk authentication.
    
    Args:
        request_body: Checkout creation parameters
        user: Authenticated user from JWT token
        
    Returns:
        CheckoutResponse with checkout URL and session ID
    """
    try:
        # Get user ID from Clerk token
        user_id = user.get('sub')
        
        if not user_id:
            logger.error(f"❌ API: User ID not found in token")
            raise HTTPException(status_code=400, detail="User ID not found in token")
        
        # Fetch user data from Supabase to get email
        user_data = supabase_service.get_user_by_clerk_id(user_id)
        
        if not user_data:
            logger.error(f"❌ API: User {user_id} not found in database")
            raise HTTPException(
                status_code=404,
                detail="User not found. Please ensure you're registered in the system."
            )
        
        user_email = user_data.get('email')
        
        if not user_email:
            logger.error(f"❌ API: User {user_id} has no email in database")
            raise HTTPException(
                status_code=400,
                detail="User email not found. Please update your profile."
            )
        
        # Set default URLs if not provided
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        success_url = request_body.success_url or f"{frontend_url}/search?checkout=success"
        cancel_url = request_body.cancel_url or f"{frontend_url}/pricing?checkout=cancelled"
        
        logger.info(f"💳 API: Creating checkout for user {user_id} ({user_email})")
        
        # Create checkout session
        result = await polar_service.create_checkout(
            product_id=request_body.product_id,
            customer_email=user_email,
            user_id=user_id,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        logger.info(f"✅ API: Checkout created successfully: {result['checkout_id']}")
        
        return CheckoutResponse(**result)
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ API: Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API: Failed to create checkout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payments/webhook")
async def handle_polar_webhook(
    request: Request,
    webhook_signature: str = Header(None, alias="Webhook-Signature")
):
    """
    Handle Polar webhook events.
    
    This endpoint is called by Polar when subscription events occur:
    - subscription.created: New subscription started - grants access
    - subscription.updated: Subscription renewed or changed
    - subscription.cancelled: Subscription cancelled - revokes access
    
    Args:
        request: FastAPI request object
        webhook_signature: Webhook-Signature header from Polar for verification
        
    Returns:
        JSON response indicating webhook processing status
    """
    if not webhook_signature:
        logger.error("❌ Webhook: Missing Webhook-Signature header")
        raise HTTPException(status_code=400, detail="Missing Webhook-Signature header")
    
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Validate webhook signature and parse event
        event = polar_service.validate_webhook(body, webhook_signature)
        
        # Handle different event types
        event_type = event.get('type')
        
        logger.info(f"🔔 Webhook: Received event type: {event_type}")
        
        # Log minimal event info (avoid logging PII like emails, addresses, names)
        subscription_data = event.get('data', {})
        subscription_id = subscription_data.get('id', 'unknown')
        status = subscription_data.get('status', 'unknown')
        logger.info(f"📦 Webhook: Subscription {subscription_id} - Status: {status}")
        
        if event_type == 'subscription.created':
            # New subscription started
            subscription_data = event.get('data', {})
            subscription_id = subscription_data.get('id')
            
            logger.info(f"✅ Webhook: Subscription created: {subscription_id}")
            
            # Get customer data (Polar nests metadata inside customer object)
            customer_data = subscription_data.get('customer', {})
            customer_metadata = customer_data.get('metadata', {})
            
            # Try multiple fields to find user ID (check nested customer.metadata first)
            user_id = (
                customer_metadata.get('user_id') or 
                customer_metadata.get('clerk_user_id') or
                subscription_data.get('metadata', {}).get('user_id') or
                subscription_data.get('metadata', {}).get('clerk_user_id')
            )
            
            # Get customer email from nested customer object (for fallback only, don't log it)
            customer_email = customer_data.get('email')
            
            # Log only if user_id was found or not (don't log actual values for privacy)
            if user_id:
                logger.info(f"🔍 Webhook: User ID found in metadata")
            else:
                logger.warning(f"⚠️  Webhook: No user_id in metadata, will attempt email lookup")
            
            if user_id:
                # Update user's subscription status to active
                updated_user = supabase_service.update_subscription_status(
                    clerk_user_id=user_id,
                    subscription_status='active'
                )
                
                if updated_user:
                    logger.info(f"✅ Webhook: User subscription updated to 'active'")
            elif customer_email:
                # Try to find user by email if metadata is missing
                logger.warning(f"⚠️  Webhook: No user_id in metadata, attempting lookup by email")
                user_data = supabase_service.get_user_by_email(customer_email)
                if user_data:
                    clerk_user_id = user_data.get('clerk_user_id')
                    updated_user = supabase_service.update_subscription_status(
                        clerk_user_id=clerk_user_id,
                        subscription_status='active'
                    )
                    if updated_user:
                        logger.info(f"✅ Webhook: User subscription updated to 'active' (via email lookup)")
                else:
                    logger.error(f"❌ Webhook: Could not find user by email lookup")
            else:
                logger.error(f"❌ Webhook: No user_id or customer_email found in subscription data!")
            
        elif event_type == 'subscription.updated':
            # Subscription updated (renewed, changed plan, etc.)
            subscription_data = event.get('data', {})
            subscription_id = subscription_data.get('id')
            status = subscription_data.get('status')
            
            logger.info(f"🔄 Webhook: Subscription updated: {subscription_id} - Status: {status}")
            
            # Get customer data (Polar nests metadata inside customer object)
            customer_data = subscription_data.get('customer', {})
            customer_metadata = customer_data.get('metadata', {})
            
            user_id = (
                customer_metadata.get('user_id') or 
                customer_metadata.get('clerk_user_id') or
                subscription_data.get('metadata', {}).get('user_id') or
                subscription_data.get('metadata', {}).get('clerk_user_id')
            )
            
            customer_email = customer_data.get('email')
            
            # Log only if user_id was found or not (don't log actual values for privacy)
            if user_id:
                logger.info(f"🔍 Webhook: User ID found in metadata")
            else:
                logger.warning(f"⚠️  Webhook: No user_id in metadata, will attempt email lookup")
            
            if user_id and status:
                # Map Polar status to our status
                if status in ['active', 'trialing']:
                    new_status = 'active'
                elif status in ['canceled', 'incomplete_expired', 'unpaid']:
                    new_status = 'expired'
                else:
                    new_status = 'expired'  # Default to expired for unknown statuses
                
                # Update user's subscription status
                updated_user = supabase_service.update_subscription_status(
                    clerk_user_id=user_id,
                    subscription_status=new_status
                )
                
                if updated_user:
                    logger.info(f"✅ Webhook: User subscription updated to '{new_status}'")
            elif customer_email and status:
                # Try to find user by email if metadata is missing
                logger.warning(f"⚠️  Webhook: No user_id in metadata, attempting lookup by email")
                user_data = supabase_service.get_user_by_email(customer_email)
                if user_data:
                    clerk_user_id = user_data.get('clerk_user_id')
                    
                    # Map Polar status to our status
                    if status in ['active', 'trialing']:
                        new_status = 'active'
                    elif status in ['canceled', 'incomplete_expired', 'unpaid']:
                        new_status = 'expired'
                    else:
                        new_status = 'expired'
                    
                    updated_user = supabase_service.update_subscription_status(
                        clerk_user_id=clerk_user_id,
                        subscription_status=new_status
                    )
                    if updated_user:
                        logger.info(f"✅ Webhook: User subscription updated to '{new_status}' (via email lookup)")
                else:
                    logger.error(f"❌ Webhook: Could not find user by email lookup")
            else:
                logger.error(f"❌ Webhook: No user_id or customer_email found in subscription data!")
            
        elif event_type == 'subscription.cancelled':
            # Subscription cancelled - revoke access
            subscription_data = event.get('data', {})
            subscription_id = subscription_data.get('id')
            
            logger.warning(f"❌ Webhook: Subscription cancelled: {subscription_id}")
            
            # Get customer data (Polar nests metadata inside customer object)
            customer_data = subscription_data.get('customer', {})
            customer_metadata = customer_data.get('metadata', {})
            
            user_id = (
                customer_metadata.get('user_id') or 
                customer_metadata.get('clerk_user_id') or
                subscription_data.get('metadata', {}).get('user_id') or
                subscription_data.get('metadata', {}).get('clerk_user_id')
            )
            
            customer_email = customer_data.get('email')
            
            # Log only if user_id was found or not (don't log actual values for privacy)
            if user_id:
                logger.info(f"🔍 Webhook: User ID found in metadata")
            else:
                logger.warning(f"⚠️  Webhook: No user_id in metadata, will attempt email lookup")
            
            if user_id:
                # Update user's subscription status to expired
                updated_user = supabase_service.update_subscription_status(
                    clerk_user_id=user_id,
                    subscription_status='expired'
                )
                
                if updated_user:
                    logger.info(f"✅ Webhook: User subscription updated to 'expired'")
            elif customer_email:
                # Try to find user by email if metadata is missing
                logger.warning(f"⚠️  Webhook: No user_id in metadata, attempting lookup by email")
                user_data = supabase_service.get_user_by_email(customer_email)
                if user_data:
                    clerk_user_id = user_data.get('clerk_user_id')
                    updated_user = supabase_service.update_subscription_status(
                        clerk_user_id=clerk_user_id,
                        subscription_status='expired'
                    )
                    if updated_user:
                        logger.info(f"✅ Webhook: User subscription updated to 'expired' (via email lookup)")
                else:
                    logger.error(f"❌ Webhook: Could not find user by email lookup")
            else:
                logger.error(f"❌ Webhook: No user_id or customer_email found in subscription data!")
        
        else:
            logger.info(f"ℹ️  Webhook: Unhandled event type: {event_type}")
        
        return JSONResponse(content={
            "status": "success",
            "event_type": event_type
        })
        
    except ValueError as e:
        logger.error(f"❌ Webhook: Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Webhook: Processing error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

