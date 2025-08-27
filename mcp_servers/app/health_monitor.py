"""
Basic health monitoring for MCP server services.
Provides simple health checks and status monitoring.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import asyncio

from .logging_config import get_service_logger
from .exceptions import DatabaseError, SDKError, VectorStoreError, handle_exception

logger = get_service_logger("health_monitor")


class HealthMonitor:
    """Simple health monitoring for server dependencies."""
    
    def __init__(self):
        self.last_check_time: Optional[datetime] = None
        self.status_cache: Dict[str, Any] = {}
        self.cache_duration_seconds = 30  # Cache health status for 30 seconds
    
    async def check_health(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Check overall system health.
        
        Args:
            force_refresh: Force refresh of cached status
            
        Returns:
            Health status dictionary
        """
        now = datetime.now(timezone.utc)
        
        # Return cached status if recent and not forcing refresh
        if (not force_refresh and 
            self.last_check_time and 
            self.status_cache and 
            (now - self.last_check_time).total_seconds() < self.cache_duration_seconds):
            logger.debug("Returning cached health status")
            return self.status_cache
        
        logger.info("Performing health check")
        
        # Check all services
        checks = await asyncio.gather(
            self._check_sdk_service(),
            self._check_database(),
            self._check_vector_services(),
            return_exceptions=True
        )
        
        sdk_status, db_status, vector_status = checks
        
        # Aggregate results
        all_healthy = all([
            isinstance(sdk_status, dict) and sdk_status.get("healthy", False),
            isinstance(db_status, dict) and db_status.get("healthy", False),
            isinstance(vector_status, dict) and vector_status.get("healthy", False)
        ])
        
        health_status = {
            "healthy": all_healthy,
            "timestamp": now.isoformat(),
            "services": {
                "sdk": sdk_status if isinstance(sdk_status, dict) else {"healthy": False, "error": str(sdk_status)},
                "database": db_status if isinstance(db_status, dict) else {"healthy": False, "error": str(db_status)},
                "vector_store": vector_status if isinstance(vector_status, dict) else {"healthy": False, "error": str(vector_status)}
            },
            "summary": {
                "total_services": 3,
                "healthy_services": sum(1 for status in [sdk_status, db_status, vector_status] 
                                       if isinstance(status, dict) and status.get("healthy", False)),
                "unhealthy_services": sum(1 for status in [sdk_status, db_status, vector_status] 
                                         if not (isinstance(status, dict) and status.get("healthy", False)))
            }
        }
        
        # Cache the results
        self.status_cache = health_status
        self.last_check_time = now
        
        if all_healthy:
            logger.info("All services healthy")
        else:
            logger.warning("Some services are unhealthy", extra={
                "healthy_count": health_status["summary"]["healthy_services"],
                "unhealthy_count": health_status["summary"]["unhealthy_services"]
            })
        
        return health_status
    
    async def _check_sdk_service(self) -> Dict[str, Any]:
        """Check Hedera SDK service health."""
        try:
            from .main import get_sdk_service
            
            sdk_service = get_sdk_service()
            
            # Try to get available methods as a basic health check
            methods = sdk_service.get_available_methods()
            
            if not methods:
                return {
                    "healthy": False,
                    "error": "SDK service returned no available methods"
                }
            
            return {
                "healthy": True,
                "available_methods_count": len(methods),
                "last_check": datetime.now(timezone.utc).isoformat()
            }
            
        except SDKError as e:
            logger.warning("SDK service health check failed", exc_info=True)
            return {
                "healthy": False,
                "error": f"SDK Error: {e.message}",
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error("Unexpected error checking SDK service health", exc_info=True)
            return {
                "healthy": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            from .services.database_manager import DatabaseManager
            from .settings import settings
            
            db_manager = DatabaseManager(settings.database_url)
            engine = db_manager.get_engine()
            
            # Test connection with a simple query
            with engine.connect() as conn:
                result = conn.execute("SELECT 1 as test")
                test_value = result.scalar()
                
                if test_value != 1:
                    return {
                        "healthy": False,
                        "error": "Database test query returned unexpected result"
                    }
            
            return {
                "healthy": True,
                "last_check": datetime.now(timezone.utc).isoformat()
            }
            
        except DatabaseError as e:
            logger.warning("Database health check failed", exc_info=True)
            return {
                "healthy": False,
                "error": f"Database Error: {e.message}",
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error("Unexpected error checking database health", exc_info=True)
            return {
                "healthy": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    async def _check_vector_services(self) -> Dict[str, Any]:
        """Check vector store services health."""
        try:
            from .main import get_vector_services
            from .settings import settings
            
            vector_store_service, document_processor = get_vector_services()
            
            # Check if collection exists
            collection_exists = vector_store_service.check_index_exists()
            
            if not collection_exists:
                return {
                    "healthy": False,
                    "error": f"Vector collection '{settings.collection_name}' does not exist"
                }
            
            # Check if document processor is initialized
            if not document_processor.is_initialized:
                return {
                    "healthy": False,
                    "error": "Document processor is not initialized"
                }
            
            return {
                "healthy": True,
                "collection_exists": True,
                "document_processor_initialized": True,
                "last_check": datetime.now(timezone.utc).isoformat()
            }
            
        except VectorStoreError as e:
            logger.warning("Vector services health check failed", exc_info=True)
            return {
                "healthy": False,
                "error": f"Vector Store Error: {e.message}",
                "error_code": e.error_code
            }
        except Exception as e:
            logger.error("Unexpected error checking vector services health", exc_info=True)
            return {
                "healthy": False,
                "error": f"Unexpected error: {str(e)}"
            }

# Global health monitor instance
health_monitor = HealthMonitor()