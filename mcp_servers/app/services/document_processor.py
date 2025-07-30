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
    
    def initialize_from_file(self, documentation_path: str, force_rebuild: bool = False):
        """Initialize vector store from documentation file."""
        try:
            if not os.path.exists(documentation_path):
                raise FileNotFoundError(f"Documentation file not found: {documentation_path}")
            
            self.documentation_path = documentation_path
            
            # Check if we need to rebuild or if collection already exists
            collection_exists = self.vector_store.check_index_exists()
            
            if force_rebuild or not collection_exists:
                logger.info(f"{'Rebuilding' if force_rebuild else 'Building'} vector collection from {documentation_path}")
                
                if force_rebuild:
                    self.vector_store.rebuild_index(documentation_path)
                else:
                    self.vector_store.load_methods_from_documentation(documentation_path)
            else:
                logger.info("Vector collection already exists, skipping initialization")
            
            self.is_initialized = True
            logger.info("Document processor initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to initialize document processor: {e}")
            raise
    
    def search_methods(self, query: str, k: int = 3, category_filter: Optional[str] = None) -> Dict[str, Any]:
        """Search for methods using natural language query."""
        try:
            if not self.is_initialized:
                raise ValueError("Document processor not initialized")
            
            # Enhance query with category if specified
            enhanced_query = query
            if category_filter:
                enhanced_query = f"{query} category:{category_filter}"
            
            # Retrieve methods
            results = self.vector_store.retrieve_methods(enhanced_query, k=k)
            
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
