"""
Authentication middleware for FastAPI
Provides JWT token validation using Clerk
Supports bypassing authentication in local development mode
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
import logging
import os
from dotenv import load_dotenv
from scripts.auth import ClerkAuthValidator

# Load environment variables
load_dotenv()

# Get environment setting
ENVIRONMENT = os.getenv('ENVIRONMENT', 'prod').lower()

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

