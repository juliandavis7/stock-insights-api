# Polar Payment Testing Guide

This guide explains how to test the Polar payment integration in local development using Polar's sandbox environment.

## 🏗️ Setup Polar Sandbox

### 1. Access Sandbox Environment

1. Go to [sandbox.polar.sh](https://sandbox.polar.sh)
2. Create a new account (separate from production)
3. Create an organization for testing

### 2. Create a Test Product

1. In the sandbox dashboard, go to **Products**
2. Click **Create Product**
3. Fill in product details:
   - **Name**: Test Pro Subscription
   - **Description**: Pro subscription for testing
   - **Price**: $9.99/month (or any test amount)
   - **Type**: Subscription
4. Save the product
5. **Copy the Product Price ID** - it will look like: `price_xxxxxxxxxxxxx` or `prod_xxxxxxxxxxxxx`

### 3. Get Sandbox API Credentials

1. Go to **Settings** → **Developers** in sandbox dashboard
2. Click **Create Token** or **New Token**
3. Select required scopes:
   - `checkouts:write`
   - `customers:read`
   - `subscriptions:read`
4. Copy the generated access token

### 4. Create Webhook (Optional)

1. Go to **Settings** → **Developers** → **Webhooks**
2. Click **Create Webhook**
3. Set webhook URL (use ngrok for local testing):
   ```
   https://your-ngrok-url.ngrok.io/payments/webhook
   ```
4. Select events:
   - `subscription.created`
   - `subscription.updated`
   - `subscription.cancelled`
5. Copy the **Webhook Secret**

---

## ⚙️ Configure Your Application

### Environment Variables

Update your `.env` file:

```env
# Polar Sandbox Credentials
POLAR_ACCESS_TOKEN=polar_pat_sandbox_xxxxxxxxxxxxx
POLAR_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx

# Set to dev to use sandbox
ENVIRONMENT=dev

# Frontend URL for redirects
FRONTEND_URL=http://localhost:5173

# Supabase (make sure user exists with email)
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
```

### Important Notes

- When `ENVIRONMENT=dev`, the SDK automatically uses Polar's sandbox server
- Use the **sandbox access token**, not your production token
- Sandbox and production environments are completely isolated

---

## 🧪 Testing the Happy Path

### Step 1: Start Your API

```bash
cd /Users/juliandavis/dev/stock-insights-api
uvicorn api:app --reload
```

### Step 2: Get Your Test User Ready

Make sure you have a user in Supabase with an email address:

```sql
-- Check your users table
SELECT clerk_user_id, email, subscription_status FROM users;
```

If no user exists, create one or trigger user creation via your app's normal flow.

### Step 3: Get a Valid JWT Token

**Option A: From Your Frontend**
```javascript
import { useAuth } from '@clerk/clerk-react';

const { getToken } = useAuth();
const token = await getToken();
console.log('Token:', token);
```

**Option B: From Clerk Dashboard**
- Go to Clerk Dashboard → Users
- Click on a user → Sessions
- Copy the session token

### Step 4: Create Checkout Session

```bash
# Replace with your actual values
CLERK_TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
PRODUCT_ID="price_xxxxxxxxxxxxx"  # From Polar sandbox dashboard

curl -X POST http://localhost:8000/payments/checkout \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"product_id\": \"$PRODUCT_ID\"
  }"
```

**Expected Response:**
```json
{
  "checkout_url": "https://sandbox.polar.sh/checkout/ch_xxxxxxxxxxxxx",
  "checkout_id": "ch_xxxxxxxxxxxxx",
  "status": "created"
}
```

### Step 5: Complete Payment

1. Copy the `checkout_url` from the response
2. Open it in your browser
3. Use Stripe's test card:
   - **Card Number**: `4242 4242 4242 4242`
   - **Expiration**: Any future date (e.g., `12/25`)
   - **CVC**: Any 3 digits (e.g., `123`)
   - **ZIP**: Any 5 digits (e.g., `12345`)
4. Complete the checkout
5. You should be redirected to: `http://localhost:5173/search?checkout=success`

### Step 6: Verify Subscription

Check user's subscription status in Supabase (updated by webhook):

```bash
curl -X GET http://localhost:8000/users/$USER_ID \
  -H "Authorization: Bearer $CLERK_TOKEN"
```

**Expected Response:**
```json
{
  "success": true,
  "user": {
    "clerk_user_id": "user_xxxxxxxxxxxxx",
    "email": "user@example.com",
    "subscription_status": "active",
    "trial_ends_at": "2025-12-01T00:00:00Z",
    "created_at": "2025-01-01T00:00:00Z"
  }
}
```

**Note:** The webhook automatically updated `subscription_status` to `'active'` when payment completed!

---

## 🔍 Testing Webhooks (Optional)

### Setup ngrok for Local Webhook Testing

1. **Install ngrok** (if not already installed):
   ```bash
   brew install ngrok  # macOS
   # or download from https://ngrok.com
   ```

2. **Start ngrok tunnel**:
   ```bash
   ngrok http 8000
   ```
   
   Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

3. **Configure webhook in Polar sandbox**:
   - Go to Settings → Developers → Webhooks
   - Set URL to: `https://abc123.ngrok.io/payments/webhook`

4. **Test webhook manually**:
   ```bash
   # Polar will send webhooks automatically when events occur
   # Check your API logs for webhook events:
   # 🔔 Webhook: Received event type: subscription.created
   ```

---

## 📝 Test Scenarios

### ✅ Happy Path Test Cases

1. **Create Checkout**
   - ✅ Valid product ID
   - ✅ User exists in Supabase
   - ✅ Valid JWT token
   - ✅ Returns checkout URL

2. **Complete Payment**
   - ✅ Use test card `4242 4242 4242 4242`
   - ✅ Redirects to success URL
   - ✅ Webhook received (if configured)

3. **Check Subscription**
   - ✅ Check user in Supabase
   - ✅ `subscription_status: 'active'`
   - ✅ Webhook updated database automatically

### ❌ Error Test Cases

1. **Invalid Product ID**
   ```bash
   curl -X POST http://localhost:8000/payments/checkout \
     -H "Authorization: Bearer $CLERK_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"product_id": "invalid_id"}'
   ```
   Expected: 500 error from Polar

2. **No JWT Token**
   ```bash
   curl -X POST http://localhost:8000/payments/checkout \
     -H "Content-Type: application/json" \
     -d '{"product_id": "price_xxxxx"}'
   ```
   Expected: 401 Unauthorized

3. **User Not in Database**
   - Use a valid JWT token for a user that doesn't exist in Supabase
   - Expected: 404 User not found

4. **User Has No Email**
   - User exists in Supabase but email is NULL
   - Expected: 400 User email not found

---

## 🎯 Sample Product IDs

After creating products in your Polar sandbox, you'll have IDs like:

- **Product ID**: `prod_2a1b3c4d5e6f7g8h`
- **Price ID**: `price_2a1b3c4d5e6f7g8h` (use this one)

**How to find them:**
1. Go to sandbox.polar.sh → Products
2. Click on your product
3. Copy the **Price ID** from the product details

---

## 🐛 Troubleshooting

### "POLAR_ACCESS_TOKEN environment variable is required"

- Make sure your `.env` file has `POLAR_ACCESS_TOKEN`
- Restart your uvicorn server after changing `.env`

### "User email not found in token"

- ✅ **FIXED**: Email is now fetched from Supabase database
- Make sure the user exists in your Supabase users table with an email

### "Failed to create checkout: products field required"

- ✅ **FIXED**: Now using `products=[product_id]` instead of `product_id=product_id`

### "Checkout URL doesn't work"

- Make sure you're using the sandbox URL (starts with `sandbox.polar.sh`)
- Check that `ENVIRONMENT=dev` in your `.env`

### "Webhook signature validation failed"

- Make sure `POLAR_WEBHOOK_SECRET` matches the secret from your webhook configuration
- Check that you're using the webhook secret from the **sandbox** environment

---

## 🔗 Useful Links

- **Polar Sandbox Dashboard**: https://sandbox.polar.sh
- **Polar API Docs**: https://docs.polar.sh
- **Stripe Test Cards**: https://stripe.com/docs/testing#cards
- **Webhook Testing Tool**: https://ngrok.com

---

## 📊 Monitoring

Check your API logs for payment flow:

```
💳 API: Creating checkout for user user_xxxxx (test@example.com)
✅ API: Checkout created successfully: ch_xxxxxxxxxxxxx
🔔 Webhook: Received event type: subscription.created
✅ Webhook: Subscription created: sub_xxxxx
✅ Webhook: User user_xxxxx subscription updated to 'active'
```

---

## ⚠️ Important Reminders

1. **Always use sandbox for development** - set `ENVIRONMENT=dev`
2. **Never commit API tokens** - keep them in `.env` (which is gitignored)
3. **Use test card numbers** - never use real cards in sandbox
4. **Sandbox subscriptions are auto-cancelled after 90 days**
5. **Production tokens don't work in sandbox** - use separate credentials

---

## 🚀 Moving to Production

When ready to go live:

1. Create a product in **production** Polar dashboard (polar.sh)
2. Get production API token and webhook secret
3. Update environment variables:
   ```env
   ENVIRONMENT=production
   POLAR_ACCESS_TOKEN=polar_pat_live_xxxxxxxxxxxxx
   POLAR_WEBHOOK_SECRET=whsec_live_xxxxxxxxxxxxx
   ```
4. Configure production webhook URL (no ngrok needed)
5. Test thoroughly with real payment methods

Remember: Production charges real money! Test everything in sandbox first. 🎯

