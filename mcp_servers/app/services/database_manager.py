"""
Database manager for PostgreSQL connections and collection management.
Handles database connections, engine creation, and collection existence checks.
"""
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ..settings import settings
from ..logging_config import get_service_logger
from ..exceptions import DatabaseConnectionError, DatabaseOperationError

logger = get_service_logger("database_manager")


class DatabaseManager:
    """Manages database connections and collection operations for vector store."""
    
    def __init__(self, connection_string: str):
        """
        Initialize database manager with connection string.
        
        Args:
            connection_string: PostgreSQL connection string
        """
        self.connection_string = connection_string
        self._engine: Optional[Engine] = None
        
    def get_engine(self) -> Engine:
        """
        Get or create SQLAlchemy engine with optimized settings.
        
        Returns:
            SQLAlchemy Engine instance
            
        Raises:
            DatabaseConnectionError: If engine creation fails
        """
        if self._engine is None:
            try:
                self._engine = create_engine(
                    self.connection_string,
                    pool_size=settings.database_pool_size,
                    max_overflow=settings.database_max_overflow,
                    pool_timeout=settings.database_pool_timeout,
                    echo=settings.database_echo
                )
                logger.info("Database engine created successfully", extra={
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow,
                    "pool_timeout": settings.database_pool_timeout
                })
            except Exception as e:
                logger.error("Failed to create database engine", exc_info=True, extra={
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow
                })
                raise DatabaseConnectionError(str(e), self.connection_string, e)
            
        return self._engine
    
    def check_collection_exists(self, collection_name: str) -> bool:
        """
        Check if the specified vector store collection exists.
        
        Args:
            collection_name: Name of the collection to check
            
        Returns:
            True if collection exists, False otherwise
        """
        try:
            engine = self.get_engine()
            
            with engine.connect() as conn:
                # Check if the pgVector collection table exists
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'langchain_pg_collection');"
                ))
                collection_table_exists = result.scalar()
                
                if not collection_table_exists:
                    logger.info("Collection table does not exist", extra={
                        "table_name": "langchain_pg_collection",
                        "collection_name": collection_name
                    })
                    return False
                
                # Check if our specific collection exists
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM langchain_pg_collection WHERE name = :collection_name);"
                ), {"collection_name": collection_name})
                
                exists = result.scalar()
                logger.info("Collection existence check completed", extra={
                    "collection_name": collection_name,
                    "exists": exists
                })
                return exists
                
        except SQLAlchemyError as e:
            logger.error("Database error checking collection existence", exc_info=True, extra={
                "collection_name": collection_name,
                "error_type": type(e).__name__
            })
            raise DatabaseOperationError("check_collection_exists", str(e), e)
        except Exception as e:
            logger.error("Unexpected error checking collection existence", exc_info=True, extra={
                "collection_name": collection_name
            })
            raise DatabaseOperationError("check_collection_exists", str(e), e)
    
    def create_collection(self, collection_name: str) -> bool:
        """
        Create a new collection in the database.
        Note: This is typically handled by PGVector initialization,
        but provided for completeness.
        
        Args:
            collection_name: Name of the collection to create
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Collection creation is typically handled by PGVector
            # during vector store initialization. This method is a placeholder
            # for future manual collection management if needed.
            logger.info(f"Collection creation for '{collection_name}' delegated to PGVector")
            return True
            
        except Exception as e:
            logger.error(f"Error creating collection '{collection_name}': {e}")
            return False