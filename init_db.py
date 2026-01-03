#!/usr/bin/env python3
"""
Initialize database tables.

Usage:
    python init_db.py
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Initialize the database."""
    from src.database import init_database
    
    logger.info("Initializing database tables...")
    init_database()
    logger.info("Database initialization complete!")


if __name__ == "__main__":
    main()

