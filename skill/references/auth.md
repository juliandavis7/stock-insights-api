# Authentication Reference

Complete authentication implementation using Clerk JWT tokens with JWKS validation.

## Overview

The API uses Clerk for authentication with JWT tokens validated using JWKS public keys. Local development mode can bypass authentication for testing.

## verify_token() Function

Complete implementation from `auth.py`:

```python
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
```

## ClerkAuthValidator Class

Complete JWT validation implementation:

```python
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
        self.frontend_api = self._extract_frontend_api()
        
        # JWKS URL - Clerk's public keys endpoint
        self.jwks_url = f"https://{self.frontend_api}/.well-known/jwks.json"
        
        # Initialize JWKS client for fetching and caching public keys
        self.jwks_client = PyJWKClient(self.jwks_url)
        
        logging.info(f"🔐 Clerk Auth initialized with Frontend API: {self.frontend_api}")
        logging.info(f"📡 JWKS URL: {self.jwks_url}")
    
    def validate_token(self, token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate a Clerk JWT token.
        
        Args:
            token: The JWT token string to validate
            
        Returns:
            Tuple of (is_valid, decoded_payload, error_message)
        """
        if not token:
            return False, None, "No token provided"
        
        try:
            # First, decode without verification to get the issuer
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            
            # Get the actual issuer from the token
            token_issuer = unverified_payload.get('iss')
            
            if not token_issuer:
                return False, None, "Token missing issuer claim"
            
            # Update JWKS URL based on actual issuer if different
            if token_issuer != f"https://{self.frontend_api}":
                jwks_url = f"{token_issuer}/.well-known/jwks.json"
                jwks_client = PyJWKClient(jwks_url)
            else:
                jwks_client = self.jwks_client
            
            # Get the signing key from JWKS
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate the token
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=token_issuer,
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
```

## Using Authentication in Endpoints

### Protected Endpoint Pattern

```python
from fastapi import Depends
from typing import Dict
from auth import verify_token

@app.get("/protected-endpoint")
def protected_route(
    ticker: str = Query(...),
    user: Dict = Depends(verify_token)  # Add this dependency
):
    # user dict contains decoded JWT payload
    user_id = user.get('sub')
    user_email = user.get('email')
    
    # Your endpoint logic here
    return {"message": f"Hello {user_email}"}
```

### User Payload Structure

The `user` dict returned by `verify_token()` contains:

```python
{
    'sub': 'user_2abc123def',      # Clerk user ID
    'email': 'user@example.com',    # User email
    'iss': 'https://clerk.accounts.dev',  # Token issuer
    'exp': 1234567890,              # Expiration timestamp
    'iat': 1234567800,              # Issued at timestamp
    # ... other Clerk-specific claims
}
```

## Environment Modes

### Production/Staging Mode (Default)

```bash
# All requests must include valid JWT token
export ENVIRONMENT=production
```

Requires `Authorization: Bearer <jwt_token>` header on all protected endpoints.

### Local Development Mode

```bash
# Bypass authentication for easier development
export ENVIRONMENT=local
```

Returns mock user:
```python
{
    'sub': 'local-dev-user',
    'email': 'dev@localhost',
    'environment': 'local',
    'note': 'Mock user for local development'
}
```

## Environment Variables

Required:
```bash
# Clerk publishable key (one of these)
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...

# Optional: Clerk secret key
CLERK_SECRET_KEY=sk_test_...
```

Optional:
```bash
# Set to "local" to bypass authentication
ENVIRONMENT=local
```

## Error Responses

### 401 - Missing Credentials
```json
{
  "detail": "Missing authentication credentials"
}
```

Headers:
```
WWW-Authenticate: Bearer
```

### 401 - Invalid Token
```json
{
  "detail": "Invalid token signature"
}
```

### 401 - Expired Token
```json
{
  "detail": "Token has expired"
}
```

## Frontend Integration

### Sending Authenticated Requests

```javascript
// Get token from Clerk
const token = await clerk.session.getToken();

// Make API request
const response = await fetch('https://api.example.com/metrics?ticker=AAPL', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
```

### Handling Auth Errors

```javascript
if (response.status === 401) {
  // Token expired or invalid
  // Redirect to login or refresh token
  await clerk.session.refresh();
  // Retry request
}
```

## Security Features

1. **JWKS Validation**: Uses public keys from Clerk's JWKS endpoint
2. **Signature Verification**: Verifies token signature with RS256 algorithm
3. **Expiration Check**: Validates token hasn't expired
4. **Issuer Validation**: Ensures token comes from expected Clerk instance
5. **HTTPBearer Scheme**: Standard OAuth2 Bearer token format

## Logging

Authentication events are logged:

```python
# Successful auth
logging.info(f"Authenticated user: {user_id} ({email})")

# Failed auth
logging.warning(f"Authentication failed: {error}")

# Local mode
logging.info("🔓 Local development mode: Bypassing authentication")
```

## Testing Authentication

### With Valid Token

```bash
curl -H "Authorization: Bearer <valid_jwt>" \
  http://localhost:8000/metrics?ticker=AAPL
```

### Local Mode (No Token)

```bash
ENVIRONMENT=local uvicorn api:app --reload

curl http://localhost:8000/metrics?ticker=AAPL
# Works without token in local mode
```

### Testing Token Expiration

```bash
# Use expired token
curl -H "Authorization: Bearer <expired_jwt>" \
  http://localhost:8000/metrics?ticker=AAPL

# Returns 401 with "Token has expired"
```

## Common Issues

### Issue: "CLERK_PUBLISHABLE_KEY environment variable is required"
**Solution**: Set `CLERK_PUBLISHABLE_KEY` or `VITE_CLERK_PUBLISHABLE_KEY` in environment

### Issue: "Invalid token issuer"
**Solution**: Token was issued by different Clerk instance. Check your Clerk app configuration.

### Issue: 401 in production but works locally
**Solution**: Verify you're setting `ENVIRONMENT=local` only for local dev, not in production

### Issue: "Token missing issuer claim"
**Solution**: Token is malformed or not from Clerk. Check token generation in frontend.

## Additional Resources

- Clerk JWT documentation: https://clerk.com/docs/backend-requests/handling/manual-jwt
- PyJWT library: https://pyjwt.readthedocs.io/
- JWKS specification: https://datatracker.ietf.org/doc/html/rfc7517

