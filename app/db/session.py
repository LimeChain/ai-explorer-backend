"""
Database session management and configuration.
"""
import threading

from contextlib import contextmanager
from functools import wraps
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Callable, Any
from app.settings import settings


# Thread-safe lazy initialization
_engine_lock = threading.Lock()
_session_lock = threading.Lock()
_engine = None
_SessionLocal = None

def get_engine() -> Engine:
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
                    pool_recycle=settings.database_pool_recycle,
                    pool_pre_ping=settings.database_pool_pre_ping,
                    echo=settings.database_echo
                )
    return _engine

def get_session_local() -> sessionmaker[Session]:
    """Get or create SessionLocal class (thread-safe)."""
    global _SessionLocal
    if _SessionLocal is None:
        with _session_lock:
            if _SessionLocal is None:  # Double-checked locking
                _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
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


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager to get database session with automatic cleanup.
    
    This ensures proper session management and prevents connection leaks.
    The caller is responsible for committing or rolling back transactions.
    
    Yields:
        Session: Database session
    
    Example:
        with get_db_session() as db:
            # Use db here
            result = db.query(Model).all()
            db.commit()  # Caller handles commit
        # db is automatically closed
    """
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    except Exception:
        db.rollback()  # Auto-rollback on any exception
        raise
    finally:
        db.close()  # Always close the session


def with_db_session(func: Callable) -> Callable:
    """
    Decorator to automatically provide and manage database sessions.
    
    The decorated function must accept 'db' as its first or keyword argument.
    
    Example:
        @with_db_session
        def some_function(db: Session, other_param: str):
            # Use db here
            return db.query(Model).all()
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        with get_db_session() as db:
            # Inject db as the first argument or as a keyword argument
            if 'db' in kwargs:
                kwargs['db'] = db
            else:
                # Insert db as first argument
                args = (db,) + args
            return func(*args, **kwargs)
    return wrapper