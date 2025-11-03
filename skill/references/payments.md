# Payment Endpoints (Polar Integration)

This document describes the payment endpoints for managing subscriptions through Polar.

## Overview

The payment system uses [Polar](https://polar.sh/) for subscription management and payment processing. These endpoints handle:
- Creating checkout sessions for subscriptions
- Processing webhook events from Polar

**Note:** Subscription status is checked via your Supabase database (kept in sync by webhooks), not by querying Polar directly. This is faster and more efficient.

## Configuration

### Environment Variables

```env
POLAR_ACCESS_TOKEN=your_polar_access_token
POLAR_WEBHOOK_SECRET=your_polar_webhook_secret
FRONTEND_URL=http://localhost:5173
ENVIRONMENT=dev
```

### Service

The payment functionality is implemented in:
- **Service**: `services/polar_service.py`
- **Router**: `routers/payments.py`
- **Models**: `models/requests.py`, `models/responses.py`

## Endpoints

### 1. Create Checkout Session

**POST** `/payments/checkout`

Creates a Polar checkout session for purchasing a subscription.

#### Authentication
- **Required**: Yes (Clerk JWT token)
- **Rate Limited**: Yes (same as health endpoints)
- **Note**: User email is fetched from Supabase database using the Clerk user ID from the JWT token

#### Request Body

```json
{
  "product_id": "prod_xxxxx",
  "success_url": "https://yourapp.com/search?checkout=success",
  "cancel_url": "https://yourapp.com/pricing?checkout=cancelled"
}
```

**Fields:**
- `product_id` (required): The Polar product ID from your Polar dashboard
- `success_url` (optional): Redirect URL after successful payment (defaults to `{FRONTEND_URL}/search?checkout=success`)
- `cancel_url` (optional): Redirect URL if user cancels (defaults to `{FRONTEND_URL}/pricing?checkout=cancelled`)

#### Response

```json
{
  "checkout_url": "https://polar.sh/checkout/xxxxx",
  "checkout_id": "checkout_xxxxx",
  "status": "created"
}
```

**Fields:**
- `checkout_url`: URL to redirect user to for completing payment
- `checkout_id`: Unique identifier for this checkout session
- `status`: Status of the checkout session

#### Example Usage

```python
import httpx

# With authentication token
headers = {
    "Authorization": f"Bearer {clerk_token}"
}

response = httpx.post(
    "http://localhost:8000/payments/checkout",
    headers=headers,
    json={
        "product_id": "prod_xxxxx"
    }
)

data = response.json()
checkout_url = data["checkout_url"]
# Redirect user to checkout_url
```

#### Error Responses

- `400`: Missing user email or invalid request
- `401`: Unauthorized (invalid/missing token)
- `404`: User not found in database (user must be registered first)
- `500`: Internal server error (Polar API error)

---

### 2. Webhook Handler

**POST** `/payments/webhook`

Handles webhook events from Polar for subscription lifecycle management.

#### Authentication
- **Required**: No (uses signature verification instead)
- **Rate Limited**: No

#### Headers

```
Webhook-Signature: t=1234567890,v1=signature_hash
```

The `Webhook-Signature` header is automatically added by Polar and is used to verify the webhook authenticity.

#### Event Types Handled

1. **subscription.created**: New subscription started - grants access
2. **subscription.updated**: Subscription renewed or changed
3. **subscription.cancelled**: Subscription cancelled - revokes access

#### Response

```json
{
  "status": "success",
  "event_type": "subscription.created"
}
```

#### Webhook Configuration

Configure the webhook URL in your Polar dashboard:
```
https://your-api.com/payments/webhook
```

#### Example Event Processing

```python
# This happens automatically when Polar sends a webhook
# The endpoint will:
# 1. Verify the signature
# 2. Parse the event
# 3. Handle based on event type
# 4. Update user subscription status (TODO)
```

#### Error Responses

- `400`: Missing signature or invalid event
- `500`: Internal processing error

---

## Integration Flow

### New Subscription Flow

1. **Frontend**: User clicks "Subscribe" button
2. **Frontend**: Call `POST /payments/checkout` with product_id
3. **API**: Creates Polar checkout session
4. **API**: Returns checkout_url
5. **Frontend**: Redirect user to checkout_url
6. **User**: Completes payment on Polar
7. **Polar**: Sends webhook to `/payments/webhook`
8. **API**: Processes webhook and updates user subscription
9. **Polar**: Redirects user to success_url

### Checking Subscription Status

**Recommended:** Check user's subscription status from your Supabase database (kept in sync by webhooks)

1. **Frontend**: User loads dashboard
2. **Frontend**: Call `GET /users/{user_id}` (your existing users endpoint)
3. **API**: Returns user data including `subscription_status` from Supabase
4. **Frontend**: Show/hide features based on `subscription_status`

```javascript
// Example frontend code
const user = await getUser(userId);
if (user.subscription_status === 'active') {
  // Show paid features
}
```

### Handling Subscription Changes

All subscription lifecycle events (renewal, cancellation, etc.) are automatically handled via webhooks:

1. **Polar**: Subscription event occurs
2. **Polar**: Sends webhook to `/payments/webhook`
3. **API**: Updates user subscription in database
4. **Frontend**: Next API call reflects updated status

---

## Security

### Webhook Security

Webhooks are verified using the `Webhook-Signature` header:
- Signature includes timestamp to prevent replay attacks
- Uses HMAC with your webhook secret
- Automatically validated by `polar_service.validate_webhook()`

### User Data Linkage

The checkout session stores user metadata to link payments to your users:
```python
metadata = {
    "user_id": clerk_user_id,
    "clerk_user_id": clerk_user_id
}
```

This allows you to identify which user completed the payment when processing webhooks.

---

## Testing

### Local Development

1. Install Polar SDK: `pip install polar-sdk`
2. Set environment variables in `.env`
3. Use Polar sandbox mode for testing
4. Use ngrok or similar for webhook testing:
   ```bash
   ngrok http 8000
   # Configure webhook URL in Polar dashboard:
   # https://your-ngrok-url.ngrok.io/payments/webhook
   ```

### Test Checkout Flow

```bash
# Create checkout (requires valid Clerk token)
curl -X POST http://localhost:8000/payments/checkout \
  -H "Authorization: Bearer YOUR_CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "prod_xxxxx"
  }'
```

---

## Webhook Implementation Status

✅ **All webhook handlers are fully implemented!**

1. **subscription.created** - Grants user access
   - Updates user's subscription_status to 'active'
   - Logs successful activation

2. **subscription.updated** - Handles renewals and changes
   - Maps Polar status to your status ('active', 'expired')
   - Updates user subscription accordingly

3. **subscription.cancelled** - Revokes access
   - Updates user's subscription_status to 'expired'
   - User loses access to paid features

The webhook automatically keeps your Supabase database in sync with Polar's subscription data.

---

## Resources

- [Polar Documentation](https://docs.polar.sh/)
- [Polar Python SDK](https://github.com/polarsource/polar-python)
- [Webhook Events Reference](https://docs.polar.sh/webhooks)

