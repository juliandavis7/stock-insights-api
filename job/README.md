# Stock Scraper Job

Cloud Run Job for scraping stock data and storing it in Supabase.

## Prerequisites

1. **GCP Project Setup**:
   - Project ID: `stock-insights-479318`
   - Region: `us-central1`
   - Secret Manager API enabled
   - Cloud Run Jobs API enabled

2. **Secrets in Secret Manager**:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `BASE_URL`
   - `STOCK_USER`
   - `STOCK_PASS`

3. **Service Account Permissions**:
   - The Compute Engine default service account (`143767434168-compute@developer.gserviceaccount.com`) must have `roles/secretmanager.secretAccessor` role

## Deployment

### Initial Setup (One-time)

1. **Enable APIs**:
   ```bash
   gcloud services enable secretmanager.googleapis.com --project=stock-insights-479318
   gcloud services enable run.googleapis.com --project=stock-insights-479318
   ```

2. **Authenticate Docker**:
   ```bash
   gcloud auth configure-docker
   ```

3. **Grant Service Account Permissions**:
   ```bash
   # Grant at project level
   gcloud projects add-iam-policy-binding stock-insights-479318 \
     --member="serviceAccount:143767434168-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   
   # Grant at secret level (for each secret)
   gcloud secrets add-iam-policy-binding SUPABASE_URL \
     --member="serviceAccount:143767434168-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor" \
     --project=stock-insights-479318
   
   # Repeat for: SUPABASE_SERVICE_ROLE_KEY, BASE_URL, STOCK_USER, STOCK_PASS
   ```

4. **Create Secrets** (if not already created):
   - Via GCP Console: https://console.cloud.google.com/security/secret-manager?project=stock-insights-479318
   - Or via CLI:
     ```bash
     printf "your-secret-value" | gcloud secrets versions add SECRET_NAME --data-file=- --project=stock-insights-479318
     ```

### Deploy the Job

Run the deployment script from the repository root:

```bash
./job/deploy-job.sh
```

This will:
1. Build the Docker image
2. Push it to GCR (`gcr.io/stock-insights-479318/stock-scraper-job`)
3. Create or update the Cloud Run Job

## Running the Job

### Execute the Deployed Job

To run the job manually:

```bash
gcloud run jobs execute stock-scraper-job --region=us-central1 --project=stock-insights-479318
```

### Local Testing

Before deploying to GCP, test the job locally using Docker to match the production environment exactly.

**Prerequisites:**
- Make sure you have a `.env` file in the project root with:
  ```
  SUPABASE_URL=your-supabase-url
  SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
  BASE_URL=your-base-url
  STOCK_USER=your-username
  STOCK_PASS=your-password
  ```

**Run the local Docker test:**
```bash
# Single stock test (recommended for quick validation)
./job/test-local-docker.sh AAPL

# Batch mode (processes all stocks from Supabase)
./job/test-local-docker.sh
```

This builds and runs the exact same Docker image that will run in GCP, ensuring your local test matches the production environment.

## Job Behavior

The job will:

1. **Fetch stocks** from Supabase `stock_data` table
2. **Check each stock**:
   - If `search_metrics` or `income_statement` is `NULL` → scrape immediately
   - If data exists but `updated_at < earnings_date` → scrape (stale data)
   - Otherwise → skip (cache is fresh)
3. **Scrape** missing/stale stocks using Playwright
4. **Store** results back in Supabase

## Scheduling (Optional)

To run the job automatically on a schedule, use Cloud Scheduler:

```bash
gcloud scheduler jobs create http stock-scraper-schedule \
  --location=us-central1 \
  --schedule="0 2 * * *" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/stock-insights-479318/jobs/stock-scraper-job:run" \
  --http-method=POST \
  --oauth-service-account-email=143767434168-compute@developer.gserviceaccount.com \
  --project=stock-insights-479318
```

This example runs daily at 2 AM UTC. Adjust the schedule as needed.

## Monitoring

View job executions:

```bash
gcloud run jobs executions list --job=stock-scraper-job --region=us-central1 --project=stock-insights-479318
```

View logs:

```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=stock-scraper-job" --limit=50 --project=stock-insights-479318
```

## Troubleshooting

- **Permission errors**: Ensure service account has `roles/secretmanager.secretAccessor`
- **Secret not found**: Verify secrets exist in Secret Manager
- **Build failures**: Check Docker authentication with `gcloud auth configure-docker`
- **Job failures**: Check logs using the monitoring commands above
