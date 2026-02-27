"""Database connection factory with backend support."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from doc_healing.config import get_settings, DatabaseBackend


def get_database_url() -> str:
    """Get database URL based on configured backend.
    
    Returns:
        str: Database connection URL for SQLite or PostgreSQL
    """
    settings = get_settings()
    
    if settings.database_backend == DatabaseBackend.SQLITE:
        return f"sqlite:///{settings.sqlite_path}"
    else:
        return settings.database_url


def create_db_engine() -> Engine:
    """Create database engine with backend-specific configuration.
    
    Returns:
        Engine: SQLAlchemy engine configured for the selected backend
    """
    url = get_database_url()
    settings = get_settings()
    
    if settings.database_backend == DatabaseBackend.SQLITE:
        # SQLite-specific configuration
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
            echo=False
        )
    else:
        # PostgreSQL-specific configuration with connection pooling
        engine = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False
        )
    
    return engine


# Create engine and session factory
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Get database session dependency.
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
