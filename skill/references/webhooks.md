# Clerk Webhook Integration

## Overview

The Stock Insights API includes a webhook endpoint to handle Clerk authentication events and automatically sync users to the database.

## Endpoint

```
POST /webhooks/clerk
```

**Authentication:** Webhook signature verification using Svix

**Rate Limiting:** None (webhooks should not be rate limited)

## Setup

### 1. Install Dependencies

```bash
pip install svix>=1.0.0
```

### 2. Configure Environment Variables

Add the following to your `.env` file:

```bash
CLERK_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

To get your webhook secret:
1. Go to Clerk Dashboard → Webhooks
2. Create a new webhook endpoint
3. Add your API URL: `https://your-api.com/webhooks/clerk`
4. Subscribe to events: `user.created`
5. Copy the webhook secret

### 3. Configure Clerk Dashboard

In the Clerk Dashboard:
1. Navigate to **Webhooks** section
2. Click **Add Endpoint**
3. Enter your endpoint URL: `https://your-api-domain.com/webhooks/clerk`
4. Select events to subscribe to:
   - ✅ `user.created` (required)
   - ✅ `user.updated` (optional, not yet implemented)
   - ✅ `user.deleted` (optional, not yet implemented)
5. Save and copy the webhook secret

## How It Works

### 1. Webhook Signature Verification

The endpoint uses Svix to verify webhook signatures:

```python
wh = Webhook(CLERK_WEBHOOK_SECRET)
payload = wh.verify(body_str, {
    "svix-id": svix_id,
    "svix-timestamp": svix_timestamp,
    "svix-signature": svix_signature
})
```

This ensures webhooks are authentic and come from Clerk.

### 2. User Creation Flow

When a user signs up via Clerk:

1. **Clerk sends webhook** with `user.created` event
2. **Signature verification** ensures authenticity
3. **Extract user data** from webhook payload:
   - Clerk User ID (`id`)
   - Email address (primary email)
   - First name
   - Last name
4. **Create user in database** using `SupabaseService.get_or_create_user()`
5. **Update user profile** with first/last name if provided
6. **Return success response**

### 3. Database Schema

The webhook creates users in the `users` table with:
- `clerk_user_id`: Unique Clerk user identifier
- `email`: User's primary email address
- `first_name`: User's first name (optional)
- `last_name`: User's last name (optional)
- `subscription_status`: Set to 'trial' by default
- `is_trial_active`: Set to `true` by default
- `trial_ends_at`: Automatically set (typically 7-14 days from creation)

## Event Types

### Currently Supported

#### `user.created`
Triggered when a new user signs up in Clerk.

**Webhook Payload Example:**
```json
{
  "type": "user.created",
  "data": {
    "id": "user_2abc123xyz",
    "email_addresses": [
      {
        "id": "email_abc123",
        "email_address": "user@example.com"
      }
    ],
    "primary_email_address_id": "email_abc123",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "User created successfully",
  "user_id": "user_2abc123xyz",
  "email": "user@example.com"
}
```

### Future Events (Not Yet Implemented)

- `user.updated`: Update user profile when changed in Clerk
- `user.deleted`: Handle user deletion/cleanup
- `session.created`: Track user sessions
- `session.ended`: Log user logout events

## Error Handling

### Missing Webhook Secret (500)
```json
{
  "detail": "Webhook secret not configured"
}
```

**Solution:** Set `CLERK_WEBHOOK_SECRET` in environment variables.

### Invalid Signature (401)
```json
{
  "detail": "Webhook verification failed"
}
```

**Causes:**
- Wrong webhook secret
- Replayed/tampered webhook
- Incorrect headers

**Solution:** Verify webhook secret matches Clerk Dashboard.

### Missing Headers (400)
```json
{
  "detail": "Missing required webhook headers"
}
```

**Required Headers:**
- `svix-id`
- `svix-timestamp`
- `svix-signature`

### User Creation Error (500)
```json
{
  "detail": "Error creating user: <error message>"
}
```

**Common Causes:**
- Database connection issues
- Invalid Supabase credentials
- Missing required fields in webhook payload

## Testing

### Test with Clerk Dashboard

1. Go to Clerk Dashboard → Webhooks
2. Find your webhook endpoint
3. Click "Send Test Event"
4. Select `user.created`
5. Click "Send"

### Test Locally with Ngrok

1. Start your API locally:
   ```bash
   uvicorn api:app --reload --port 8000
   ```

2. Expose with ngrok:
   ```bash
   ngrok http 8000
   ```

3. Update webhook URL in Clerk Dashboard to ngrok URL:
   ```
   https://abc123.ngrok.io/webhooks/clerk
   ```

4. Create a test user in Clerk

5. Check API logs for webhook events

### Manual Testing with curl

```bash
# This will fail signature verification (expected)
# Use Clerk Dashboard for real testing
curl -X POST https://your-api.com/webhooks/clerk \
  -H "Content-Type: application/json" \
  -H "svix-id: msg_test123" \
  -H "svix-timestamp: 1234567890" \
  -H "svix-signature: v1,test_signature" \
  -d '{
    "type": "user.created",
    "data": {
      "id": "user_test123",
      "email_addresses": [
        {
          "id": "email_test123",
          "email_address": "test@example.com"
        }
      ],
      "primary_email_address_id": "email_test123",
      "first_name": "Test",
      "last_name": "User"
    }
  }'
```

## Monitoring

### Logs

The webhook endpoint logs all events:

```
📨 Received Clerk webhook: user.created
👤 Creating user: user_2abc123xyz (user@example.com)
✅ Successfully created/updated user user_2abc123xyz in database
```

### Common Log Messages

- `📨 Received Clerk webhook: <event_type>` - Webhook received and verified
- `👤 Creating user: <clerk_id> (<email>)` - Starting user creation
- `✅ Successfully created/updated user` - User created successfully
- `❌ Webhook verification failed` - Signature verification failed
- `❌ Error creating user from webhook` - Database error during creation
- `ℹ️ Received unhandled event type` - Event type not yet implemented

## Security Best Practices

1. **Never expose webhook secret** - Store in environment variables only
2. **Always verify signatures** - Don't trust webhook data without verification
3. **Use HTTPS** - Webhooks should only be sent over HTTPS in production
4. **Monitor for replay attacks** - Svix automatically checks timestamp freshness
5. **Rate limit user creation** - Consider adding rate limiting if abuse is detected

## Troubleshooting

### Webhook not receiving events

1. Check webhook URL is correct in Clerk Dashboard
2. Verify endpoint is publicly accessible (not localhost)
3. Check firewall/security group settings
4. Confirm webhook is enabled in Clerk Dashboard

### Signature verification fails

1. Verify `CLERK_WEBHOOK_SECRET` matches Clerk Dashboard
2. Check no proxy is modifying headers
3. Ensure webhook secret wasn't rotated in Clerk

### User not created in database

1. Check Supabase credentials are correct
2. Verify `users` table exists with correct schema
3. Check API logs for detailed error messages
4. Confirm `SUPABASE_SERVICE_ROLE_KEY` has write permissions

## Integration with Frontend

When a user signs up in your React app:

1. User completes Clerk sign-up flow
2. Clerk creates the user account
3. Clerk sends `user.created` webhook to your API
4. API creates user in Supabase database
5. User can immediately start using the API (trial period active)
6. Frontend can verify user exists via `/users` endpoint

This ensures seamless user creation without requiring the frontend to make additional API calls.

