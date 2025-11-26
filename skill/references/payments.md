# Payment Endpoints (Stripe Integration)

This document describes the payment endpoints for managing subscriptions through Stripe.

## Overview

The payment system uses [Stripe](https://stripe.com/) for subscription management and payment processing. These endpoints handle:
- Creating checkout sessions for subscriptions
- Processing webhook events from Stripe

**Note:** Subscription status is checked via your Supabase database (kept in sync by webhooks), not by querying Stripe directly. This is faster and more efficient.

## Configuration

### Environment Variables

```env
STRIPE_SECRET_KEY=sk_test_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
STRIPE_PRICE_ID=price_xxxxx
FRONTEND_URL=http://localhost:5173
ENVIRONMENT=dev
```

### Service

The payment functionality is implemented in:
- **Service**: `services/stripe_service.py`
- **Router**: `routers/payments.py`
- **Models**: `models/requests.py`, `models/responses.py`

## Endpoints

### 1. Create Checkout Session

**POST** `/payments/checkout`

Creates a Stripe checkout session for purchasing a subscription ($10/month).

#### Authentication
- **Required**: Yes (Clerk JWT token)
- **Rate Limited**: Yes (same as health endpoints)
- **Note**: User email is fetched from Supabase database using the Clerk user ID from the JWT token

#### Request Body

```json
{
  "price_id": "price_xxxxx",
  "success_url": "https://yourapp.com/search?checkout=success",
  "cancel_url": "https://yourapp.com/pricing?checkout=cancelled"
}
```

**Fields:**
- `price_id` (required): The Stripe price ID from your Stripe dashboard (e.g., `price_1ABC...`)
- `success_url` (optional): Redirect URL after successful payment (defaults to `{FRONTEND_URL}/subscription?checkout=success`)
- `cancel_url` (optional): Redirect URL if user cancels (defaults to `{FRONTEND_URL}/pricing?checkout=cancelled`)

#### Response

```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/xxxxx",
  "checkout_id": "cs_xxxxx",
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
        "price_id": "price_xxxxx"
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
- `500`: Internal server error (Stripe API error)

---

### 2. Webhook Handler

**POST** `/payments/webhook`

Handles webhook events from Stripe for subscription lifecycle management.

#### Authentication
- **Required**: No (uses signature verification instead)
- **Rate Limited**: No

#### Headers

```
Stripe-Signature: t=1234567890,v1=signature_hash
```

The `Stripe-Signature` header is automatically added by Stripe and is used to verify the webhook authenticity.

#### Event Types Handled

1. **customer.subscription.created**: New subscription started - grants access
2. **customer.subscription.updated**: Subscription renewed or changed
3. **customer.subscription.deleted**: Subscription cancelled - revokes access

#### Response

```json
{
  "status": "success",
  "event_type": "customer.subscription.created"
}
```

#### Webhook Configuration

Configure the webhook URL in your Stripe dashboard:
```
https://your-api.com/payments/webhook
```

Subscribe to these events:
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`

#### Error Responses

- `400`: Missing signature or invalid event
- `500`: Internal processing error

---

## Integration Flow

### New Subscription Flow

1. **Frontend**: User clicks "Subscribe" button
2. **Frontend**: Call `POST /payments/checkout` with price_id
3. **API**: Creates Stripe checkout session
4. **API**: Returns checkout_url
5. **Frontend**: Redirect user to checkout_url
6. **User**: Completes payment on Stripe
7. **Stripe**: Sends webhook to `/payments/webhook`
8. **API**: Processes webhook and updates user subscription
9. **Stripe**: Redirects user to success_url

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

1. **Stripe**: Subscription event occurs
2. **Stripe**: Sends webhook to `/payments/webhook`
3. **API**: Updates user subscription in database
4. **Frontend**: Next API call reflects updated status

---

## Security

### Webhook Security

Webhooks are verified using the `Stripe-Signature` header:
- Signature includes timestamp to prevent replay attacks
- Uses HMAC with your webhook secret
- Automatically validated by `stripe.Webhook.construct_event()`

### User Data Linkage

The checkout session stores user metadata to link payments to your users:
```python
metadata = {
    "user_id": clerk_user_id,
    "clerk_user_id": clerk_user_id
}
```

This metadata is also stored on the subscription via `subscription_data`, allowing you to identify which user completed the payment when processing webhooks.

---

## Stripe Dashboard Setup

### 1. Create a Product and Price

1. Go to Stripe Dashboard → Products
2. Click "Add product"
3. Name: "Stock Insights Pro" (or your product name)
4. Pricing: $10/month recurring
5. Save and copy the Price ID (e.g., `price_1ABC...`)

### 2. Set Up Webhooks

1. Go to Stripe Dashboard → Developers → Webhooks
2. Click "Add endpoint"
3. Endpoint URL: `https://your-api.com/payments/webhook`
4. Select events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Add endpoint
6. Copy the webhook signing secret

### 3. Get API Keys

1. Go to Stripe Dashboard → Developers → API keys
2. Copy your Secret key (starts with `sk_test_` for test mode)

---

## Testing

### Local Development

1. Install Stripe CLI: `brew install stripe/stripe-cli/stripe`
2. Login: `stripe login`
3. Forward webhooks to local: `stripe listen --forward-to localhost:8000/payments/webhook`
4. Copy the webhook signing secret from the CLI output
5. Use test mode API keys

### Test Cards

Use these test card numbers:
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Requires authentication**: `4000 0025 0000 3155`

Any future expiry date and any 3-digit CVC will work.

### Test Checkout Flow

```bash
# Create checkout (requires valid Clerk token)
curl -X POST http://localhost:8000/payments/checkout \
  -H "Authorization: Bearer YOUR_CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "price_id": "price_xxxxx"
  }'
```

---

## Webhook Implementation Status

✅ **All webhook handlers are fully implemented!**

1. **customer.subscription.created** - Grants user access
   - Updates user's subscription_status to 'active'
   - Logs successful activation

2. **customer.subscription.updated** - Handles renewals and changes
   - Maps Stripe status to your status ('active', 'expired')
   - Updates user subscription accordingly

3. **customer.subscription.deleted** - Revokes access
   - Updates user's subscription_status to 'expired'
   - User loses access to paid features

The webhook automatically keeps your Supabase database in sync with Stripe's subscription data.

---

## Resources

- [Stripe Documentation](https://stripe.com/docs)
- [Stripe Python SDK](https://github.com/stripe/stripe-python)
- [Stripe Checkout](https://stripe.com/docs/payments/checkout)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Stripe CLI](https://stripe.com/docs/stripe-cli)
