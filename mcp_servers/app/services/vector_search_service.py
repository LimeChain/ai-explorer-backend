"""
Vector search service for SDK method retrieval using PostgreSQL pgVector and LangChain embeddings.
Handles vector store initialization, document management, and similarity searches.
"""
import json
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document

from .database_manager import DatabaseManager
from .text_processor import TextProcessor
from ..settings import settings

logger = logging.getLogger(__name__)


class VectorSearchService:
    """Service for managing vector embeddings and performing similarity searches."""
    
    def __init__(
        self, 
        database_manager: DatabaseManager,
        text_processor: TextProcessor,
        openai_api_key: str, 
        collection_name: str, 
        embedding_model: str
    ):
        """
        Initialize vector search service.
        
        Args:
            database_manager: Database manager instance
            text_processor: Text processor instance
            openai_api_key: OpenAI API key for embeddings
            collection_name: Name of the vector collection
            embedding_model: OpenAI embedding model to use
        """
        self.database_manager = database_manager
        self.text_processor = text_processor
        self.collection_name = collection_name
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key, model=embedding_model)
        self.vector_store: Optional[PGVector] = None
        
    def initialize_vector_store(self):
        """Initialize the PostgreSQL pgVector store."""
        try:       
            # Get database engine from manager
            engine = self.database_manager.get_engine()
            
            # Initialize PGVector following langchain-postgres documentation
            self.vector_store = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=self.database_manager.connection_string,
                use_jsonb=True,
                engine_args={
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow,
                    "pool_timeout": settings.database_pool_timeout,
                }
            )
            logger.info(f"Vector store initialized with collection: {self.collection_name}")
            
        except RuntimeError:
            # Re-raise RuntimeError with pgVector installation message
            logger.error("RuntimeError during vector store initialization - check pgVector installation")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise RuntimeError(f"Vector store initialization failed: {e}") from e
    
    def add_documents(self, documents: List[Document]):
        """
        Add documents to the vector store.
        
        Args:
            documents: List of Document objects to add
        """
        if self.vector_store is None:
            self.initialize_vector_store()
        
        try:
            self.vector_store.add_documents(documents)
            logger.info(f"Successfully added {len(documents)} documents to vector store")
        except Exception as e:
            logger.error(f"Failed to add documents to vector store: {e}")
            raise
    
    def load_documentation(self, documentation_path: str):
        """
        Load and embed SDK methods from documentation JSON file.
        
        Args:
            documentation_path: Path to the documentation JSON file
        """
        try:
            # Load methods from file using text processor
            methods = self.text_processor.load_methods_from_file(documentation_path)
            
            logger.info(f"Loading {len(methods)} methods into vector store")
            
            # Create documents using text processor
            documents = self.text_processor.create_documents(methods)
            
            # Add documents to vector store
            self.add_documents(documents)
            
            logger.info(f"Successfully loaded {len(documents)} methods into vector store")
            
        except Exception as e:
            logger.error(f"Failed to load methods from documentation: {e}")
            raise
    
    def similarity_search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve most relevant methods based on similarity search.
        
        Args:
            query: Search query string
            k: Number of results to return
            
        Returns:
            List of method information dictionaries
        """
        try:
            if self.vector_store is None:
                self.initialize_vector_store()
            
            # Perform similarity search
            results = self.vector_store.similarity_search(
                query=query,
                k=k
            )
            
            retrieved_methods = []
            for doc in results:
                # Parse the full method data from metadata
                full_method_data = json.loads(doc.metadata["full_data"])
                
                method_info = {
                    "method_name": doc.metadata["method_name"],
                    "description": doc.metadata["description"],
                    "parameters": full_method_data.get("parameters", []),
                    "returns": full_method_data.get("returns", {}),
                    "use_cases": full_method_data.get("use_cases", []),
                    "category": doc.metadata["category"],
                }
                retrieved_methods.append(method_info)
            
            logger.info(f"Retrieved {len(retrieved_methods)} methods for query: '{query}'")
            return retrieved_methods
            
        except Exception as e:
            logger.error(f"Failed to retrieve methods for query '{query}': {e}")
            raise
    
    def check_collection_exists(self) -> bool:
        """
        Check if the vector store collection exists.
        
        Returns:
            True if collection exists, False otherwise
        """
        return self.database_manager.check_collection_exists(self.collection_name)