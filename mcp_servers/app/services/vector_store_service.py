"""
Vector store service for SDK method retrieval using PostgreSQL pgVector and LangChain embeddings.
This service acts as a facade coordinating the database, text processing, and vector search components.
"""
import logging
from typing import Dict, List, Any

from .database_manager import DatabaseManager
from .text_processor import TextProcessor
from .vector_search_service import VectorSearchService
from ..logging_config import get_service_logger

logger = get_service_logger("vector_store_service", "mcp")


class VectorStoreService:
    """
    Facade service coordinating database management, text processing, and vector search operations.
    Maintains backward compatibility while providing a cleaner separation of concerns.
    """
    
    def __init__(self, connection_string: str, llm_api_key: str, collection_name: str, embedding_model: str):
        """
        Initialize the vector store service with composed components.
        
        Args:
            connection_string: PostgreSQL connection string
            llm_api_key: OpenAI API key for embeddings
            collection_name: Name of the vector collection
            embedding_model: OpenAI embedding model to use
        """
        # Initialize composed services
        self.database_manager = DatabaseManager(connection_string)
        self.text_processor = TextProcessor()
        self.vector_search_service = VectorSearchService(
            database_manager=self.database_manager,
            text_processor=self.text_processor,
            llm_api_key=llm_api_key,
            collection_name=collection_name,
            embedding_model=embedding_model
        )
        
        # Keep these for backward compatibility
        self.connection_string = connection_string
        self.collection_name = collection_name
        
        logger.info("✅ VectorStoreService initialized", extra={
            "collection_name": collection_name,
            "embedding_model": embedding_model
        })
        
    def initialize_vector_store(self):
        """Initialize the PostgreSQL pgVector store - delegates to VectorSearchService."""
        self.vector_search_service.initialize_vector_store()
    
    def load_methods_from_documentation(self, documentation_path: str):
        """Load and embed SDK methods from documentation JSON - delegates to VectorSearchService."""
        self.vector_search_service.load_documentation(documentation_path)
    
    def retrieve_methods(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve most relevant methods based on query - delegates to VectorSearchService."""
        return self.vector_search_service.similarity_search(query, k)
    
    def check_index_exists(self) -> bool:
        """Check if the vector store collection exists - delegates to VectorSearchService."""
        return self.vector_search_service.check_collection_exists()
