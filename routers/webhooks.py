"""Clerk webhook endpoint router."""
import logging
import os
from typing import Dict
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from svix.webhooks import Webhook, WebhookVerificationError

from services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)
router = APIRouter()

# Get Clerk webhook secret from environment
CLERK_WEBHOOK_SECRET = os.getenv('CLERK_WEBHOOK_SECRET')


@router.post("/webhooks/clerk")
async def clerk_webhook(
    request: Request,
    svix_id: str = Header(None, alias="svix-id"),
    svix_timestamp: str = Header(None, alias="svix-timestamp"),
    svix_signature: str = Header(None, alias="svix-signature")
):
    """
    Handle Clerk webhook events.
    
    Verifies webhook signature and processes user.created events to sync users to database.
    
    Args:
        request: FastAPI request object
        svix_id: Svix message ID header
        svix_timestamp: Svix timestamp header
        svix_signature: Svix signature header
        
    Returns:
        JSONResponse with status of webhook processing
    """
    
    # Check if webhook secret is configured
    if not CLERK_WEBHOOK_SECRET:
        logger.error("❌ CLERK_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=500,
            detail="Webhook secret not configured"
        )
    
    # Verify required headers are present
    if not svix_id or not svix_timestamp or not svix_signature:
        logger.error("❌ Missing required Svix headers")
        raise HTTPException(
            status_code=400,
            detail="Missing required webhook headers"
        )
    
    # Get the raw body
    try:
        body = await request.body()
        body_str = body.decode('utf-8')
    except Exception as e:
        logger.error(f"❌ Error reading request body: {e}")
        raise HTTPException(
            status_code=400,
            detail="Invalid request body"
        )
    
    # Verify webhook signature using svix
    try:
        wh = Webhook(CLERK_WEBHOOK_SECRET)
        payload = wh.verify(body_str, {
            "svix-id": svix_id,
            "svix-timestamp": svix_timestamp,
            "svix-signature": svix_signature
        })
    except WebhookVerificationError as e:
        logger.error(f"❌ Webhook verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Webhook verification failed"
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error during webhook verification: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error verifying webhook"
        )
    
    # Parse the event
    event_type = payload.get('type')
    event_data = payload.get('data', {})
    
    logger.info(f"📨 Received Clerk webhook: {event_type}")
    logger.debug(f"Webhook payload: {payload}")
    
    # Handle user.created event
    if event_type == 'user.created':
        try:
            # Extract user information from webhook payload
            clerk_user_id = event_data.get('id')
            email_addresses = event_data.get('email_addresses', [])
            first_name = event_data.get('first_name')
            last_name = event_data.get('last_name')
            
            # Get primary email
            primary_email = None
            for email_obj in email_addresses:
                if email_obj.get('id') == event_data.get('primary_email_address_id'):
                    primary_email = email_obj.get('email_address')
                    break
            
            # Fallback to first email if primary not found
            if not primary_email and email_addresses:
                primary_email = email_addresses[0].get('email_address')
            
            # Validate required data
            if not clerk_user_id:
                logger.error("❌ Missing Clerk user ID in webhook payload")
                raise HTTPException(
                    status_code=400,
                    detail="Missing user ID in webhook payload"
                )
            
            logger.info(f"👤 Creating user: {clerk_user_id} ({primary_email})")
            
            # Create user in database using SupabaseService
            supabase_service = SupabaseService()
            user = await supabase_service.get_or_create_user(
                clerk_user_id=clerk_user_id,
                email=primary_email
            )
            
            # Optionally update first/last name if provided
            if first_name or last_name:
                try:
                    update_data = {}
                    if first_name:
                        update_data['first_name'] = first_name
                    if last_name:
                        update_data['last_name'] = last_name
                    
                    supabase_service.client.table('users').update(update_data).eq(
                        'clerk_user_id', clerk_user_id
                    ).execute()
                    
                    logger.info(f"✅ Updated user name: {first_name} {last_name}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not update user name: {e}")
                    # Don't fail the webhook if name update fails
            
            logger.info(f"✅ Successfully created/updated user {clerk_user_id} in database")
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "User created successfully",
                    "user_id": clerk_user_id,
                    "email": primary_email
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error creating user from webhook: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating user: {str(e)}"
            )
    
    # Handle other event types (log but don't process)
    else:
        logger.info(f"ℹ️  Received unhandled event type: {event_type}")
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Event {event_type} received but not processed"
            }
        )

