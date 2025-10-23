"""
Authentication middleware for FastAPI
Provides JWT token validation using Clerk
Supports bypassing authentication in local development mode
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional, Tuple
import logging
import os
import base64
import jwt
from jwt import PyJWKClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ClerkAuthValidator:
    """Validates Clerk JWT tokens using JWKS public keys."""
    
    def __init__(self):
        """Initialize the validator with Clerk configuration."""
        # Get Clerk configuration from environment variables
        self.publishable_key = os.getenv('VITE_CLERK_PUBLISHABLE_KEY') or os.getenv('CLERK_PUBLISHABLE_KEY')
        self.secret_key = os.getenv('CLERK_SECRET_KEY')
        
        if not self.publishable_key:
            raise ValueError("VITE_CLERK_PUBLISHABLE_KEY or CLERK_PUBLISHABLE_KEY environment variable is required")
        
        # Extract the frontend API URL from the publishable key
        # Clerk publishable keys contain the instance domain
        self.frontend_api = self._extract_frontend_api()
        
        # JWKS URL - Clerk's public keys endpoint
        self.jwks_url = f"https://{self.frontend_api}/.well-known/jwks.json"
        
        # Initialize JWKS client for fetching and caching public keys
        self.jwks_client = PyJWKClient(self.jwks_url)
        
        logging.info(f"🔐 Clerk Auth initialized with Frontend API: {self.frontend_api}")
        logging.info(f"📡 JWKS URL: {self.jwks_url}")
    
    def _extract_frontend_api(self) -> str:
        """
        Extract the Clerk frontend API URL from the publishable key.
        
        Clerk publishable keys have format: pk_test_<instance> or pk_live_<instance>
        The instance portion contains base64-encoded domain information.
        """
        try:
            # Remove the pk_test_ or pk_live_ prefix
            if self.publishable_key.startswith('pk_test_'):
                key_data = self.publishable_key[8:]  # Remove 'pk_test_'
            elif self.publishable_key.startswith('pk_live_'):
                key_data = self.publishable_key[8:]  # Remove 'pk_live_'
            else:
                # If format is different, try to decode anyway
                key_data = self.publishable_key
            
            # The key contains the domain - try to decode if it's base64
            # For some Clerk instances, the domain is directly in the key
            # Format can be: domain.clerk.accounts.dev
            
            # If the key contains a dot, it might already be the domain
            if '.' in key_data:
                return key_data
            
            # Otherwise, for Clerk, the standard format is clerk.accounts.dev
            # But we can also check if there's an explicit issuer in the token
            # For now, we'll use a flexible approach
            
            # Default Clerk format based on key prefix
            if self.publishable_key.startswith('pk_test_'):
                # Test environment typically uses clerk.accounts.dev subdomain
                return f"clerk.accounts.dev"
            else:
                return f"clerk.accounts.dev"
                
        except Exception as e:
            # Fallback to default Clerk domain
            logging.warning(f"⚠️  Warning: Could not parse publishable key, using default domain: {e}")
            return "clerk.accounts.dev"
    
    def validate_token(self, token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate a Clerk JWT token.
        
        Args:
            token: The JWT token string to validate
            
        Returns:
            Tuple of (is_valid, decoded_payload, error_message)
            - is_valid: Boolean indicating if token is valid
            - decoded_payload: Decoded token payload if valid, None otherwise
            - error_message: Error message if invalid, None otherwise
        """
        if not token:
            return False, None, "No token provided"
        
        try:
            # First, decode without verification to get the issuer
            unverified_header = jwt.get_unverified_header(token)
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            
            # Get the actual issuer from the token
            token_issuer = unverified_payload.get('iss')
            
            if not token_issuer:
                return False, None, "Token missing issuer claim"
            
            # Update JWKS URL based on actual issuer if different
            if token_issuer != f"https://{self.frontend_api}":
                # Extract domain from issuer
                issuer_domain = token_issuer.replace('https://', '').replace('http://', '')
                jwks_url = f"{token_issuer}/.well-known/jwks.json"
                jwks_client = PyJWKClient(jwks_url)
            else:
                jwks_client = self.jwks_client
            
            # Get the signing key from JWKS
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate the token with the correct issuer
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=token_issuer,  # Use the issuer from the token
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                }
            )
            
            return True, decoded, None
            
        except jwt.ExpiredSignatureError:
            return False, None, "Token has expired"
        except jwt.InvalidIssuerError as e:
            return False, None, f"Invalid token issuer: {str(e)}"
        except jwt.InvalidSignatureError:
            return False, None, "Invalid token signature"
        except jwt.DecodeError as e:
            return False, None, f"Token decode error: {str(e)}"
        except Exception as e:
            return False, None, f"Token validation failed: {str(e)}"


# Get environment setting
ENVIRONMENT = os.getenv('ENVIRONMENT', 'production').lower()

# Initialize security scheme and auth validator
security = HTTPBearer(auto_error=False)  # Don't auto-error, we'll handle it manually
auth_validator = ClerkAuthValidator()


async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict:
    """
    Validates JWT token and returns user payload.
    In local development mode (ENVIRONMENT=local), authentication is bypassed.
    
    This dependency should be added to protected endpoints:
        @app.get("/protected")
        def protected_route(user: Dict = Depends(verify_token)):
            # user contains decoded JWT payload (or mock user in local mode)
            pass
    
    Args:
        credentials: HTTP Bearer token credentials (optional in local mode)
        
    Returns:
        Dict: Decoded token payload with user information
        
    Raises:
        HTTPException: 401 if token is invalid or expired (only in non-local environments)
    """
    # Bypass authentication in local development
    if ENVIRONMENT == 'local':
        logging.info("🔓 Local development mode: Bypassing authentication")
        return {
            'sub': 'local-dev-user',
            'email': 'dev@localhost',
            'environment': 'local',
            'note': 'Mock user for local development'
        }
    
    # Production/staging: require valid token
    if not credentials:
        logging.warning("Authentication failed: No credentials provided")
        raise HTTPException(
            status_code=401,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    is_valid, payload, error = auth_validator.validate_token(token)
    
    if not is_valid:
        logging.warning(f"Authentication failed: {error}")
        raise HTTPException(
            status_code=401,
            detail=error or "Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logging.info(f"Authenticated user: {payload.get('sub')} ({payload.get('email')})")
    return payload

