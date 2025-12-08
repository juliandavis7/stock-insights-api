#!/bin/bash

PROJECT_ID="stock-insights-479318"

REGION="us-central1"

JOB_NAME="stock-scraper-job"

IMAGE="gcr.io/$PROJECT_ID/$JOB_NAME"

# Build and push image for amd64 (Cloud Run architecture)
# This is required when building on Apple Silicon (arm64) Macs
docker build --platform linux/amd64 -f job/Dockerfile.job -t $IMAGE .
docker push $IMAGE

# Create or update job
CLOUDSDK_PYTHON=/usr/bin/python3 gcloud run jobs replace job/job.yaml --region $REGION

