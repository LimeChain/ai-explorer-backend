"""
Database session management and configuration.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Global variables for lazy initialization
_engine = None
_SessionLocal = None

def get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            echo=settings.database_echo
        )
    return _engine

def get_session_local():
    """Get or create SessionLocal class."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal

# Create module-level instances for backward compatibility
engine = get_engine()
SessionLocal = get_session_local()

def get_db():
    """
    Dependency function to get database session.
    
    Yields:
        Session: Database session
    """
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()