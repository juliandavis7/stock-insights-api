# Stock Insights API

This is the FastAPI backend for the Stock Insights application.

## Environment Setup

1. Create a `.env` file in the `api` directory with your API keys:

```env
# External APIs
FMP_API_KEY=your_fmp_api_key_here

# Clerk Authentication
VITE_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
CLERK_SECRET_KEY=your_clerk_secret_key

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key

# Stripe Payments (optional - for subscription management)
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
STRIPE_PRICE_ID=your_stripe_price_id

# Frontend URL (for payment redirects)
FRONTEND_URL=http://localhost:5173

# Environment
ENVIRONMENT=dev
```

2. Install dependencies:

```bash
pip3 install -r requirements.txt
```

3. Run the API:

```bash
uvicorn api:app --reload
```

## API Keys Required

- **FMP_API_KEY**: Financial Modeling Prep API key for stock data
- **VITE_CLERK_PUBLISHABLE_KEY**: Clerk authentication publishable key
- **CLERK_SECRET_KEY**: Clerk authentication secret key
- **SUPABASE_URL**: Supabase project URL
- **SUPABASE_KEY**: Supabase anonymous/public key
- **STRIPE_SECRET_KEY** (Optional): Stripe secret key for payment processing
- **STRIPE_WEBHOOK_SECRET** (Optional): Stripe webhook secret for event verification
- **STRIPE_PRICE_ID** (Optional): Stripe price ID for the $10/month subscription

## Security Notes

- Never commit API keys to version control
- The `.env` file is already in `.gitignore`
- API keys are loaded from environment variables at runtime
