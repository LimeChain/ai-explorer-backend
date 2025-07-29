"""
Document processor for SDK method documentation.
Handles initialization and management of vector embeddings.
"""
import json
import logging
import os
from typing import Dict, Any, Optional
from .vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processes and manages SDK method documentation for vector search."""
    
    def __init__(self, vector_store_service: VectorStoreService):
        self.vector_store = vector_store_service
        self.documentation_path = None
        self.is_initialized = False
    
    async def initialize_from_file(self, documentation_path: str, force_rebuild: bool = False):
        """Initialize vector store from documentation file."""
        try:
            if not os.path.exists(documentation_path):
                raise FileNotFoundError(f"Documentation file not found: {documentation_path}")
            
            self.documentation_path = documentation_path
            
            # Check if we need to rebuild or if index already exists
            index_exists = await self.vector_store.check_index_exists()
            
            if force_rebuild or not index_exists:
                logger.info(f"{'Rebuilding' if force_rebuild else 'Building'} vector index from {documentation_path}")
                
                if force_rebuild:
                    await self.vector_store.rebuild_index(documentation_path)
                else:
                    await self.vector_store.load_methods_from_documentation(documentation_path)
            else:
                logger.info("Vector index already exists, skipping initialization")
            
            # Verify the index is working
            await self._verify_index()
            self.is_initialized = True
            logger.info("Document processor initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to initialize document processor: {e}")
            raise
    
    async def _verify_index(self):
        """Verify that the vector index is working properly."""
        try:
            # Test with a simple query
            test_results = await self.vector_store.retrieve_methods("get account", k=3)
            if not test_results:
                raise ValueError("Index verification failed: no results returned for test query")
            
            logger.info(f"Index verification successful. Found {len(test_results)} results for test query")
            
        except Exception as e:
            logger.error(f"Index verification failed: {e}")
            raise
    
    async def get_method_stats(self) -> Dict[str, Any]:
        """Get statistics about the loaded methods."""
        try:
            if not self.is_initialized:
                return {"error": "Document processor not initialized"}
            
            # Get health check from vector store
            health = await self.vector_store.health_check()
            
            # Load original documentation to get category stats
            category_stats = {}
            if self.documentation_path and os.path.exists(self.documentation_path):
                with open(self.documentation_path, 'r') as f:
                    doc_data = json.load(f)
                
                methods = doc_data.get("methods", [])
                for method in methods:
                    category = method.get("category", "unknown")
                    category_stats[category] = category_stats.get(category, 0) + 1
            
            return {
                "total_methods": health.get("document_count", 0),
                "categories": category_stats,
                "index_name": health.get("index_name"),
                "status": health.get("status"),
                "documentation_file": self.documentation_path
            }
            
        except Exception as e:
            logger.error(f"Failed to get method stats: {e}")
            return {"error": str(e)}
    
    async def search_methods(self, query: str, k: int = 3, category_filter: Optional[str] = None) -> Dict[str, Any]:
        """Search for methods using natural language query."""
        try:
            if not self.is_initialized:
                raise ValueError("Document processor not initialized")
            
            # Enhance query with category if specified
            enhanced_query = query
            if category_filter:
                enhanced_query = f"{query} category:{category_filter}"
            
            # Retrieve methods
            results = await self.vector_store.retrieve_methods(enhanced_query, k=k)
            print(f"Results are: {results}")
            
            # Filter by category if specified (post-processing filter as backup)
            if category_filter:
                results = [r for r in results if r.get("category", "").lower() == category_filter.lower()]
            
            return {
                "query": query,
                "category_filter": category_filter,
                "results_count": len(results),
                "methods": results
            }
            
        except Exception as e:
            logger.error(f"Method search failed for query '{query}': {e}")
            return {
                "query": query,
                "error": str(e),
                "results_count": 0,
                "methods": []
            }
    
    async def get_method_by_name(self, method_name: str) -> Optional[Dict[str, Any]]:
        """Get specific method by exact name match."""
        try:
            if not self.is_initialized:
                raise ValueError("Document processor not initialized")
            
            # Search for exact method name
            results = await self.vector_store.retrieve_methods(f"method:{method_name}", k=10)
            
            # Find exact match
            for result in results:
                if result["method_name"] == method_name:
                    return result
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get method by name '{method_name}': {e}")
            return None
    
    async def refresh_index(self) -> Dict[str, Any]:
        """Refresh the vector index from the documentation file."""
        try:
            if not self.documentation_path:
                raise ValueError("No documentation path set")
            
            await self.initialize_from_file(self.documentation_path, force_rebuild=True)
            
            stats = await self.get_method_stats()
            return {
                "status": "success",
                "message": "Index refreshed successfully",
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to refresh index: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the document processor."""
        return {
            "initialized": self.is_initialized,
            "documentation_path": self.documentation_path,
            "has_documentation_file": bool(self.documentation_path and os.path.exists(self.documentation_path))
        }