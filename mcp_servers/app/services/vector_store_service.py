"""
Vector store service for SDK method retrieval using PostgreSQL pgVector and LangChain embeddings.
"""
import json
import logging
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing SDK method vector embeddings in PostgreSQL with pgVector."""
    
    def __init__(self, connection_string: str, openai_api_key: str, collection_name: str, embedding_model: str):
        self.connection_string = connection_string
        self.collection_name = collection_name
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key, model=embedding_model)
        self.engine = create_engine(connection_string)
        self.vector_store: Optional[PGVector] = None
        
    def initialize_vector_store(self):
        """Initialize the PostgreSQL pgVector store."""
        try:       
            # Initialize PGVector following langchain-postgres documentation
            self.vector_store = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=self.connection_string,
                use_jsonb=True
            )
            logger.info(f"Vector store initialized with collection: {self.collection_name}")
        except RuntimeError:
            # Re-raise RuntimeError with pgVector installation message
            raise
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise RuntimeError(f"Vector store initialization failed: {e}") from e
    
    def load_methods_from_documentation(self, documentation_path: str):
        """Load and embed SDK methods from documentation JSON."""
        try:
            with open(documentation_path, 'r') as f:
                doc_data = json.load(f)
            
            methods = doc_data.get("methods", [])
            logger.info(f"Loading {len(methods)} methods into vector store")
            
            documents = []
            
            for method in methods:
                # Create searchable text combining all relevant information
                searchable_text = self._create_searchable_text(method)
                
                # Prepare metadata with optimized structure
                metadata = {
                    "method_name": method["name"],
                    "description": method["description"],
                    "category": method.get("category", "unknown"),
                    "param_names": [p["name"] for p in method.get("parameters", [])],
                    # Store return type for filtering
                    "return_type": method.get("returns", {}).get("type", "unknown"),
                    # Keep original data as JSON only for detailed responses
                    "full_data": json.dumps(method)
                }
                
                # Create Document object with content and metadata
                doc = Document(
                    page_content=searchable_text,
                    metadata=metadata
                )
                documents.append(doc)
            
            # Add documents to vector store
            if self.vector_store is None:
                self.initialize_vector_store()
            
            self.vector_store.add_documents(documents)
            
            logger.info(f"Successfully loaded {len(documents)} methods into vector store")
            
        except Exception as e:
            logger.error(f"Failed to load methods from documentation: {e}")
            raise
    
    def _create_searchable_text(self, method: Dict[str, Any]) -> str:
        """Create optimized searchable text for vector embeddings."""
        # Focus on natural language that will create good embeddings
        parts = []
        
        # Method name and description are most important
        parts.append(method['name'])
        parts.append(method['description'])
        
        # Add parameter information in natural language
        if method.get("parameters"):
            param_texts = []
            for param in method["parameters"]:
                # Create natural language parameter description
                param_text = f"{param['name']} parameter {param['description']}"
                param_texts.append(param_text)
            parts.extend(param_texts)
        
        # Add use cases as they provide good semantic context
        if method.get("use_cases"):
            parts.extend(method['use_cases'])
        
        # Add return information
        if method.get("returns") and method["returns"].get("type"):
            parts.append(f"returns {method['returns']['type']}")
        
        # Add category for semantic grouping
        if method.get("category"):
            parts.append(f"{method['category']} functionality")
        
        # Join with spaces for natural language flow
        return " ".join(parts)
    
    def retrieve_methods(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve most relevant methods based on query."""
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
    
    def check_index_exists(self) -> bool:
        """Check if the vector store collection exists."""
        try:
            # Check if the pgVector collection table exists
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'langchain_pg_collection');"
                ))
                collection_table_exists = result.scalar()
                
                if not collection_table_exists:
                    return False
                
                # Check if our specific collection exists
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM langchain_pg_collection WHERE name = :collection_name);"
                ), {"collection_name": self.collection_name})
                return result.scalar()
        except Exception as e:
            logger.error(f"Error checking collection existence: {e}")
            return False
