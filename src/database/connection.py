"""
Database connection and session management.
"""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool

from config.setting import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy Base - single source of truth for all models
Base = declarative_base()

# Build connection arguments
connect_args = {}
ssl_args = settings.get_ssl_args()
if ssl_args:
    connect_args.update(ssl_args)
    logger.info("SSL enabled for database connection")

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args=connect_args,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database session (for use outside FastAPI)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_database() -> None:
    """Initialize database tables."""
    from src.database.models import job  # Import to register models
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
