"""
Polar payment integration service for subscription management.
Handles checkout creation, webhook processing, and subscription status.
"""

from typing import Optional, Dict, Any
import os
from polar_sdk import Polar


class PolarService:
    """Service for managing Polar payments and subscriptions."""
    
    def __init__(self):
        """Initialize Polar client with access token."""
        self.access_token = os.getenv('POLAR_ACCESS_TOKEN')
        if not self.access_token:
            raise ValueError("POLAR_ACCESS_TOKEN environment variable is required")
        
        # Use sandbox for dev, production for live
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        
        # Initialize Polar SDK with appropriate server
        if self.environment == 'dev':
            self.client = Polar(access_token=self.access_token, server='sandbox')
        else:
            self.client = Polar(access_token=self.access_token)
        
    async def create_checkout(
        self,
        product_id: str,
        customer_email: str,
        user_id: str,
        success_url: str,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Polar checkout session for subscription.
        
        Args:
            product_id: Polar product ID (from dashboard)
            customer_email: Customer's email address
            user_id: Your internal user ID (from Clerk)
            success_url: Redirect URL after successful payment
            cancel_url: Optional redirect URL if user cancels
            
        Returns:
            Dict containing checkout URL and session ID
        """
        try:
            # Create checkout session
            # Note: products expects a list of product price IDs
            checkout_data = {
                "products": [product_id],  # products field expects an array
                "customer_email": customer_email,
                "success_url": success_url,
                # Store user_id in metadata to link payment to your user
                "customer_metadata": {
                    "user_id": user_id,
                    "clerk_user_id": user_id
                }
            }
            
            checkout = self.client.checkouts.create(request=checkout_data)
            
            return {
                "checkout_url": checkout.url,
                "checkout_id": checkout.id,
                "status": "created"
            }
            
        except Exception as e:
            raise Exception(f"Failed to create checkout: {str(e)}")
    
    async def get_customer_subscriptions(self, customer_email: str) -> list:
        """
        Get all subscriptions for a customer.
        
        Args:
            customer_email: Customer's email address
            
        Returns:
            List of active subscriptions
        """
        try:
            # Get customer by email
            customers_response = self.client.customers.list(email=customer_email)
            
            # Handle tuple response (result, response) from SDK
            if isinstance(customers_response, tuple):
                customers_response = customers_response[0]
            
            # Handle different response structures
            if hasattr(customers_response, 'items'):
                customers_list = customers_response.items
            elif hasattr(customers_response, 'data'):
                customers_list = customers_response.data
            elif isinstance(customers_response, list):
                customers_list = customers_response
            else:
                customers_list = list(customers_response) if customers_response else []
            
            if not customers_list:
                return []
            
            customer = customers_list[0]
            
            # Handle if customer itself is a tuple
            if isinstance(customer, tuple):
                customer = customer[0]
            
            # Extract customer ID
            if hasattr(customer, 'id'):
                customer_id = customer.id
            elif isinstance(customer, dict):
                customer_id = customer.get('id')
            else:
                # Fallback: try to get id as attribute or key
                customer_id = getattr(customer, 'id', None)
            
            # Get customer's subscriptions
            subscriptions_response = self.client.subscriptions.list(
                customer_id=customer_id
            )
            
            # Handle tuple response from SDK
            if isinstance(subscriptions_response, tuple):
                subscriptions_response = subscriptions_response[0]
            
            # Handle different response structures
            if hasattr(subscriptions_response, 'items'):
                subscriptions_list = subscriptions_response.items
            elif hasattr(subscriptions_response, 'data'):
                subscriptions_list = subscriptions_response.data
            elif isinstance(subscriptions_response, list):
                subscriptions_list = subscriptions_response
            else:
                subscriptions_list = list(subscriptions_response) if subscriptions_response else []
            
            # Return active subscriptions
            active_subs = []
            for sub in subscriptions_list:
                # Handle if subscription itself is a tuple
                if isinstance(sub, tuple):
                    sub = sub[0]
                
                # Extract status
                if hasattr(sub, 'status'):
                    status = sub.status
                elif isinstance(sub, dict):
                    status = sub.get('status')
                else:
                    status = getattr(sub, 'status', None)
                
                if status == "active":
                    active_subs.append(sub)
            
            return active_subs
            
        except Exception as e:
            raise Exception(f"Failed to get subscriptions: {str(e)}")
    
    def validate_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Validate and parse Polar webhook event.
        
        Args:
            payload: Raw webhook payload
            signature: Polar-Signature header value
            
        Returns:
            Parsed webhook event
        """
        webhook_secret = os.getenv('POLAR_WEBHOOK_SECRET')
        if not webhook_secret:
            raise ValueError("POLAR_WEBHOOK_SECRET not configured")
        
        try:
            import json
            import hmac
            import hashlib
            
            # Decode payload if it's bytes
            body_str = payload.decode('utf-8') if isinstance(payload, bytes) else payload
            
            # Parse the JSON payload
            event_data = json.loads(body_str)
            
            # Verify webhook signature manually (skip in dev mode for testing)
            environment = os.getenv('ENVIRONMENT', 'production').lower()
            
            if environment != 'dev' and webhook_secret and signature:
                # Parse the signature header (format: "t=timestamp,v1=signature")
                sig_parts = {}
                for part in signature.split(','):
                    if '=' in part:
                        key, value = part.split('=', 1)
                        sig_parts[key] = value
                
                # Get timestamp and signature
                timestamp = sig_parts.get('t', '')
                provided_signature = sig_parts.get('v1', '')
                
                if timestamp and provided_signature:
                    # Create the signed payload string
                    signed_payload = f"{timestamp}.{body_str}"
                    
                    # Compute expected signature
                    expected_signature = hmac.new(
                        webhook_secret.encode('utf-8'),
                        signed_payload.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    
                    # Compare signatures
                    if not hmac.compare_digest(expected_signature, provided_signature):
                        raise Exception("Webhook signature verification failed")
            elif environment == 'dev':
                # In dev mode, log that we're skipping verification
                import logging
                logging.warning("⚠️  DEV MODE: Skipping webhook signature verification")
            
            return event_data
            
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid webhook payload: {str(e)}")
        except Exception as e:
            raise Exception(f"Webhook validation failed: {str(e)}")


# Initialize global instance
polar_service = PolarService()

