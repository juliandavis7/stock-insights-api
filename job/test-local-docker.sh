#!/bin/bash
# Local Docker test script for the stock scraper job
# This builds and runs the job in Docker locally for fast testing
#
# By default, builds locally (native architecture for speed on Apple Silicon)
# Set USE_GCR=true to test with the actual GCR image (amd64, emulated on Apple Silicon)

set -e

echo "🐳 Testing Stock Scraper Job Locally with Docker"
echo "================================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found in project root"
    echo "   Please create a .env file with the following variables:"
    echo "   - SUPABASE_URL"
    echo "   - SUPABASE_SERVICE_ROLE_KEY"
    echo "   - BASE_URL"
    echo "   - STOCK_USER"
    echo "   - STOCK_PASS"
    exit 1
fi

# Use local build by default for faster testing on Apple Silicon
# Set USE_GCR=true to test with the actual GCR image (slower due to emulation)
GCR_IMAGE="gcr.io/stock-insights-479318/stock-scraper-job"
USE_GCR="${USE_GCR:-false}"

if [ "$USE_GCR" = "true" ] && docker manifest inspect "$GCR_IMAGE" >/dev/null 2>&1; then
    echo "📦 Using GCR image: $GCR_IMAGE (amd64, emulated on Apple Silicon)"
    IMAGE_NAME="$GCR_IMAGE"
else
    echo "🔨 Building Docker image locally (native architecture)..."
    docker build -f job/Dockerfile.job -t stock-scraper-job:local .
    IMAGE_NAME="stock-scraper-job:local"
fi

# Run the container
echo ""
echo "🚀 Running job container..."
echo ""

# Check if we're running a single ticker or batch mode
# With CMD (not ENTRYPOINT), we need to override the full command for single-ticker mode
if [ -n "$1" ]; then
    echo "🎯 Running in single-ticker mode for: $1"
    docker run --rm -it \
        --env-file .env \
        "$IMAGE_NAME" \
        python3 -u /app/job/main.py "$1"
else
    echo "📋 Running in batch mode (all stocks)"
    docker run --rm -it \
        --env-file .env \
        "$IMAGE_NAME"
fi

echo ""
echo "✅ Docker test completed!"
