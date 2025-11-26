"""
Stripe payment integration service for subscription management.
Handles checkout creation, webhook processing, and subscription status.
"""

import os
import logging
from typing import Optional, Dict, Any
import stripe

logger = logging.getLogger(__name__)


class StripeService:
    """Service for managing Stripe payments and subscriptions."""
    
    def __init__(self):
        """Initialize Stripe client with secret key."""
        self.secret_key = os.getenv('STRIPE_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("STRIPE_SECRET_KEY environment variable is required")
        
        # Configure stripe with the secret key
        stripe.api_key = self.secret_key
        
        # Get environment for logging purposes
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        
    async def create_checkout_session(
        self,
        price_id: str,
        customer_email: str,
        user_id: str,
        success_url: str,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe checkout session for subscription.
        
        Args:
            price_id: Stripe price ID (from dashboard, e.g., price_xxxxx)
            customer_email: Customer's email address
            user_id: Your internal user ID (from Clerk)
            success_url: Redirect URL after successful payment
            cancel_url: Optional redirect URL if user cancels
            
        Returns:
            Dict containing checkout URL and session ID
        """
        try:
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url or success_url,
                # Store user_id in metadata to link payment to your user
                metadata={
                    "user_id": user_id,
                    "clerk_user_id": user_id
                },
                # Also store in subscription_data so it persists on the subscription
                subscription_data={
                    "metadata": {
                        "user_id": user_id,
                        "clerk_user_id": user_id
                    }
                }
            )
            
            return {
                "checkout_url": checkout_session.url,
                "checkout_id": checkout_session.id,
                "status": "created"
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout: {str(e)}")
            raise Exception(f"Failed to create checkout: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating checkout: {str(e)}")
            raise Exception(f"Failed to create checkout: {str(e)}")
    
    async def get_customer_subscriptions(self, customer_email: str) -> list:
        """
        Get all subscriptions for a customer by email.
        
        Args:
            customer_email: Customer's email address
            
        Returns:
            List of active subscriptions
        """
        try:
            # Search for customers by email
            customers = stripe.Customer.list(email=customer_email, limit=1)
            
            if not customers.data:
                return []
            
            customer = customers.data[0]
            
            # Get customer's subscriptions
            subscriptions = stripe.Subscription.list(
                customer=customer.id,
                status="active"
            )
            
            return subscriptions.data
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting subscriptions: {str(e)}")
            raise Exception(f"Failed to get subscriptions: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting subscriptions: {str(e)}")
            raise Exception(f"Failed to get subscriptions: {str(e)}")
    
    def validate_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Validate and parse Stripe webhook event.
        
        Args:
            payload: Raw webhook payload
            signature: Stripe-Signature header value
            
        Returns:
            Parsed webhook event
        """
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        if not webhook_secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET not configured")
        
        try:
            # Verify webhook signature and construct event
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            
            return event
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            raise Exception(f"Webhook signature verification failed: {str(e)}")
        except Exception as e:
            logger.error(f"Webhook validation failed: {str(e)}")
            raise Exception(f"Webhook validation failed: {str(e)}")


# Initialize global instance (lazy initialization to avoid startup errors if env vars missing)
_stripe_service = None


def get_stripe_service() -> StripeService:
    """Get or create the Stripe service instance."""
    global _stripe_service
    if _stripe_service is None:
        _stripe_service = StripeService()
    return _stripe_service


# For backward compatibility with import pattern
stripe_service = None
try:
    stripe_service = StripeService()
except ValueError:
    # Service will be None if env vars are missing - handle at runtime
    pass

