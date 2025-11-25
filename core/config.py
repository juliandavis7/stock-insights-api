"""Logging configuration for the Stock Insights API."""
import os
import logging


def setup_logging():
    """Configure logging for the application."""
    # Check if running in Cloud Run (K_SERVICE environment variable is set)
    is_cloud_run = os.getenv('K_SERVICE') is not None
    
    if is_cloud_run:
        # Cloud Run: Only log to stdout/stderr (read-only filesystem)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ],
            force=True
        )
    else:
        # Local development: Log to both stdout and file
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('api.log')
            ],
            force=True  # Force reconfiguration even if uvicorn already initialized logging
        )
    
    # Explicitly set level for all application loggers to ensure they show INFO logs
    logging.getLogger('routers.payments').setLevel(logging.INFO)
    logging.getLogger('services').setLevel(logging.INFO)
    logging.getLogger('core').setLevel(logging.INFO)

