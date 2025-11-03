"""Logging configuration for the Stock Insights API."""
import logging


def setup_logging():
    """Configure logging for the application."""
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

