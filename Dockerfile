FROM python:3.9-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 apiuser

# Install system dependencies needed for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (as root before switching user)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY --chown=apiuser:apiuser . .

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chown apiuser:apiuser /app/logs

# Switch to non-root user
USER apiuser

# Cloud Run will set PORT environment variable
ENV PORT=8080
EXPOSE 8080

# Use the PORT environment variable
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT}