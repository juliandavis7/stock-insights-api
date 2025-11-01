# Update User Subscription Status API

## Endpoint

```
PATCH /users/{clerk_user_id}/subscription
PUT /users/{clerk_user_id}/subscription
POST /users/{clerk_user_id}/subscription
```

Updates a user's subscription status in the Supabase database.
The endpoint accepts PATCH, PUT, or POST methods.

## Authentication

Requires valid JWT token in Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

## Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `clerk_user_id` | string | The Clerk user ID to update |

## Request Body

```json
{
  "subscription_status": "active"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `subscription_status` | string | Yes | Must be one of: `'trial'`, `'active'`, or `'expired'` |

## Response

### Success (200)

```json
{
  "success": true,
  "message": "Subscription status updated to active",
  "user": {
    "id": 123,
    "clerk_user_id": "user_2abc123xyz",
    "email": "user@example.com",
    "subscription_status": "active",
    "created_at": "2025-10-15T10:30:00Z",
    "trial_ends_at": "2025-10-22T10:30:00Z"
  }
}
```

### Error Responses

#### 404 - User Not Found

```json
{
  "success": false,
  "error": "User not found"
}
```

#### 401 - Unauthorized

```json
{
  "detail": "Invalid token"
}
```

or

```json
{
  "success": false,
  "error": "Invalid token: missing user ID"
}
```

#### 500 - Server Error

```json
{
  "success": false,
  "error": "Supabase is not configured properly. Please check your environment variables."
}
```

## Usage Examples

### 1. Upgrade User to Paid Subscription

Using PATCH:
```bash
curl -X PATCH "http://localhost:8000/users/user_2abc123xyz/subscription" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_status": "active"
  }'
```

Using POST:
```bash
curl -X POST "http://localhost:8000/users/user_2abc123xyz/subscription" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_status": "active"
  }'
```

Using PUT:
```bash
curl -X PUT "http://localhost:8000/users/user_2abc123xyz/subscription" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_status": "active"
  }'
```

### 2. Mark Trial as Expired

```bash
curl -X POST "http://localhost:8000/users/user_2abc123xyz/subscription" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_status": "expired"
  }'
```

### 3. Reset User to Trial

```bash
curl -X POST "http://localhost:8000/users/user_2abc123xyz/subscription" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_status": "trial"
  }'
```

## Subscription Status Values

| Status | Description |
|--------|-------------|
| `trial` | User is in their free trial period |
| `active` | User has an active paid subscription |
| `expired` | User's trial has ended and they haven't subscribed |

## Rate Limiting

This endpoint uses the same rate limits as the health endpoint (HEALTH_USER_LIMIT).

## Implementation Details

### Files Modified

1. **`models/requests.py`** - Added `UpdateSubscriptionStatusRequest` model
2. **`services/supabase_service.py`** - Added `update_subscription_status()` method
3. **`routers/users.py`** - Added PATCH endpoint handler

### Service Method

The `update_subscription_status()` method in `SupabaseService`:
- Checks if user exists before updating
- Updates the `subscription_status` field
- Returns the updated user data
- Logs all operations

## Notes

- The endpoint requires authentication (JWT token)
- The user is identified by the `clerk_user_id` path parameter
- The user must exist in the database before updating
- Only the `subscription_status` field is updated (`'trial'`, `'active'`, or `'expired'`)

