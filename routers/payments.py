"""Payment endpoint router for Stripe subscription management."""
import logging
import os
from typing import Dict
import stripe
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Response
from fastapi.responses import JSONResponse

from core.auth import verify_token
from services.stripe_service import stripe_service
from services.supabase_service import supabase_service
from core.rate_limit import user_limiter, HEALTH_USER_LIMIT
from models.requests import CreateCheckoutRequest
from models.responses import CheckoutResponse, PortalResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Ensure Stripe API key is set (fallback in case stripe_service didn't initialize)
if not stripe.api_key:
    stripe_key = os.getenv('STRIPE_SECRET_KEY')
    if stripe_key:
        stripe.api_key = stripe_key
        logger.info("✅ Stripe API key configured in payments router")
    else:
        logger.warning("⚠️  STRIPE_SECRET_KEY not found - Stripe operations will fail")


@router.post("/payments/checkout", response_model=CheckoutResponse)
@user_limiter.limit(HEALTH_USER_LIMIT)
async def create_checkout(
    request: Request,
    response: Response,
    request_body: CreateCheckoutRequest,
    user: Dict = Depends(verify_token)
):
    """
    Create a Stripe checkout session for subscription.
    
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
        
        # Check if user already has an active subscription
        subscription_status = user_data.get('subscription_status')
        if subscription_status == 'active':
            logger.warning(f"⚠️ API: User {user_id} already has active subscription")
            raise HTTPException(
                status_code=400,
                detail="You already have an active subscription."
            )
        
        # Set default URLs if not provided
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        success_url = request_body.success_url or f"{frontend_url}/subscription?checkout=success"
        cancel_url = request_body.cancel_url or f"{frontend_url}/pricing?checkout=cancelled"
        
        logger.info(f"💳 API: Creating checkout for user {user_id} ({user_email})")
        
        # Create checkout session
        result = await stripe_service.create_checkout_session(
            price_id=request_body.price_id,
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


@router.post("/payments/portal", response_model=PortalResponse)
@user_limiter.limit(HEALTH_USER_LIMIT)
async def create_portal_session(
    request: Request,
    response: Response,
    user: Dict = Depends(verify_token)
):
    """
    Create a Stripe Customer Portal session for subscription management.
    
    The portal allows users to:
    - View their subscription details
    - Cancel their subscription
    - Update payment method
    - View billing history
    
    Protected endpoint - requires Clerk authentication.
    
    Returns:
        PortalResponse with portal URL to redirect user to
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
        
        logger.info(f"🔧 API: Creating portal session for user {user_id}")
        
        # Find Stripe customer by email
        customers = stripe.Customer.list(email=user_email, limit=1)
        
        if not customers.data:
            logger.error(f"❌ API: No Stripe customer found for {user_id}")
            raise HTTPException(
                status_code=404,
                detail="No subscription found. Please subscribe first."
            )
        
        customer_id = customers.data[0].id
        
        # Create portal session
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{frontend_url}/subscription"
        )
        
        logger.info(f"✅ API: Portal session created for user {user_id}")
        
        return PortalResponse(portal_url=portal_session.url)
        
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"❌ API: Stripe error creating portal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API: Failed to create portal session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payments/webhook")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """
    Handle Stripe webhook events.
    
    This endpoint is called by Stripe when subscription events occur:
    - customer.subscription.created: New subscription started - grants access
    - customer.subscription.updated: Subscription renewed or changed
    - customer.subscription.deleted: Subscription cancelled - revokes access
    
    Args:
        request: FastAPI request object
        stripe_signature: Stripe-Signature header from Stripe for verification
        
    Returns:
        JSON response indicating webhook processing status
    """
    if not stripe_signature:
        logger.error("❌ Webhook: Missing Stripe-Signature header")
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")
    
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Validate webhook signature and parse event
        event = stripe_service.validate_webhook(body, stripe_signature)
        
        # Handle different event types
        event_type = event.get('type')
        
        logger.info(f"🔔 Webhook: Received event type: {event_type}")
        
        # Get subscription data from the event
        subscription_data = event.get('data', {}).get('object', {})
        subscription_id = subscription_data.get('id', 'unknown')
        status = subscription_data.get('status', 'unknown')
        
        # Log full subscription data for debugging cancellation
        logger.info(f"📦 Webhook: Subscription {subscription_id} - Status: {status}")
        logger.debug(f"📋 Full subscription data: {subscription_data}")
        
        if event_type == 'customer.subscription.created':
            # New subscription started
            logger.info(f"✅ Webhook: Subscription created: {subscription_id}")
            
            # Get user ID from subscription metadata
            metadata = subscription_data.get('metadata', {})
            user_id = metadata.get('user_id') or metadata.get('clerk_user_id')
            
            # If no metadata, try to get customer email for fallback lookup
            customer_id = subscription_data.get('customer')
            customer_email = None
            
            if not user_id and customer_id:
                # Fetch customer to get email
                try:
                    import stripe
                    customer = stripe.Customer.retrieve(customer_id)
                    customer_email = customer.get('email')
                except Exception as e:
                    logger.warning(f"⚠️  Webhook: Could not fetch customer: {e}")
            
            if user_id:
                logger.info(f"🔍 Webhook: User ID found in metadata")
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
            
        elif event_type == 'customer.subscription.updated':
            # Subscription updated (renewed, changed plan, etc.)
            cancel_at_period_end = subscription_data.get('cancel_at_period_end', False)
            canceled_at = subscription_data.get('canceled_at')
            cancel_at = subscription_data.get('cancel_at')
            ended_at = subscription_data.get('ended_at')
            
            logger.info(f"🔄 Webhook: Subscription updated: {subscription_id}")
            logger.info(f"   Status: {status}")
            logger.info(f"   cancel_at_period_end: {cancel_at_period_end}")
            logger.info(f"   canceled_at: {canceled_at}")
            logger.info(f"   cancel_at: {cancel_at}")
            logger.info(f"   ended_at: {ended_at}")
            logger.info(f"   Full subscription keys: {list(subscription_data.keys())[:20]}...")  # First 20 keys
            
            # Get user ID from subscription metadata
            metadata = subscription_data.get('metadata', {})
            user_id = metadata.get('user_id') or metadata.get('clerk_user_id')
            
            # If no metadata, try to get customer email for fallback lookup
            customer_id = subscription_data.get('customer')
            customer_email = None
            
            if not user_id and customer_id:
                try:
                    import stripe
                    customer = stripe.Customer.retrieve(customer_id)
                    customer_email = customer.get('email')
                except Exception as e:
                    logger.warning(f"⚠️  Webhook: Could not fetch customer: {e}")
            
            if user_id and status:
                logger.info(f"🔍 Webhook: User ID found in metadata")
                # Map Stripe status to our status
                # Keep user active even if they've scheduled cancellation - they stay active until billing period ends
                if status in ['active', 'trialing']:
                    new_status = 'active'
                elif status in ['canceled', 'incomplete_expired', 'unpaid', 'past_due']:
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
                    
                    # Map Stripe status to our status
                    # Keep user active even if they've scheduled cancellation - they stay active until billing period ends
                    if status in ['active', 'trialing']:
                        new_status = 'active'
                    elif status in ['canceled', 'incomplete_expired', 'unpaid', 'past_due']:
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
            
        elif event_type == 'customer.subscription.deleted':
            # Subscription cancelled - revoke access
            logger.warning(f"❌ Webhook: Subscription deleted: {subscription_id}")
            logger.info(f"📋 Deleted subscription data: cancel_at_period_end={subscription_data.get('cancel_at_period_end')}, canceled_at={subscription_data.get('canceled_at')}, status={subscription_data.get('status')}")
            
            # Get user ID from subscription metadata
            metadata = subscription_data.get('metadata', {})
            user_id = metadata.get('user_id') or metadata.get('clerk_user_id')
            logger.info(f"🔍 Webhook: Looking for user_id in metadata: {metadata}")
            
            # If no metadata, try to get customer email for fallback lookup
            customer_id = subscription_data.get('customer')
            customer_email = None
            
            if not user_id and customer_id:
                try:
                    import stripe
                    customer = stripe.Customer.retrieve(customer_id)
                    customer_email = customer.get('email')
                except Exception as e:
                    logger.warning(f"⚠️  Webhook: Could not fetch customer: {e}")
            
            if user_id:
                logger.info(f"🔍 Webhook: User ID found in metadata")
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
