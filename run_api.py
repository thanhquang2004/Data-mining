#!/usr/bin/env python3
"""
Start the Job Crawler API server.

Usage:
    python run_api.py
    python run_api.py --reload  # Development mode
    python run_api.py --host 0.0.0.0 --port 8000
"""
import argparse
import logging

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Start the API server."""
    parser = argparse.ArgumentParser(description="Run the Job Crawler API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    
    args = parser.parse_args()
    
    logger.info(f"Starting Job Crawler API on {args.host}:{args.port}")
    if args.reload:
        logger.info("Development mode with auto-reload enabled")
    
    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=1 if args.reload else args.workers,
        log_level="info"
    )


if __name__ == "__main__":
    main()
