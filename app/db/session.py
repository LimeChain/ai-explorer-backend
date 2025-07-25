"""
Database session management and configuration.
"""
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Thread-safe lazy initialization
_engine_lock = threading.Lock()
_session_lock = threading.Lock()
_engine = None
_SessionLocal = None

def get_engine():
    """Get or create database engine (thread-safe)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:  # Double-checked locking
                _engine = create_engine(
                    settings.database_url,
                    pool_size=settings.database_pool_size,
                    max_overflow=settings.database_max_overflow,
                    pool_timeout=settings.database_pool_timeout,
                    echo=settings.database_echo
                )
    return _engine

def get_session_local():
    """Get or create SessionLocal class (thread-safe)."""
    global _SessionLocal
    if _SessionLocal is None:
        with _session_lock:
            if _SessionLocal is None:  # Double-checked locking
                _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


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