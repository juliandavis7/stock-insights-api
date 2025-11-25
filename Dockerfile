FROM python:3.9-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 apiuser

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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