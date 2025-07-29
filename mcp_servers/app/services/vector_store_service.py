"""
Vector store service for SDK method retrieval using Redis and LangChain embeddings.
"""
import json
import logging
from typing import Dict, List, Any, Optional
import redis
from langchain_openai import OpenAIEmbeddings
from langchain_redis import RedisVectorStore

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing SDK method vector embeddings in Redis."""
    
    def __init__(self, redis_url: str, openai_api_key: str, index_name: str = "sdk_methods"):
        self.redis_url = redis_url
        self.index_name = index_name
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key, model="text-embedding-3-large")
        self.redis_client = redis.from_url(redis_url)
        self.vector_store: Optional[RedisVectorStore] = None
        
    async def initialize_vector_store(self):
        """Initialize the Redis vector store."""
        try:
            self.vector_store = RedisVectorStore(
                redis_url=self.redis_url,
                index_name=self.index_name,
                embeddings=self.embeddings
            )
            logger.info(f"Vector store initialized with index: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    async def load_methods_from_documentation(self, documentation_path: str):
        """Load and embed SDK methods from documentation JSON."""
        try:
            with open(documentation_path, 'r') as f:
                doc_data = json.load(f)
            
            methods = doc_data.get("methods", [])
            logger.info(f"Loading {len(methods)} methods into vector store")
            
            documents = []
            metadatas = []
            
            for method in methods:
                # Create searchable text combining all relevant information
                searchable_text = self._create_searchable_text(method)
                
                # Prepare metadata with full method information
                metadata = {
                    "method_name": method["name"],
                    "description": method["description"],
                    "parameters": json.dumps(method.get("parameters", [])),
                    "returns": json.dumps(method.get("returns", {})),
                    "use_cases": json.dumps(method.get("use_cases", [])),
                    "category": method.get("category", "unknown")
                }
                
                documents.append(searchable_text)
                metadatas.append(metadata)
            
            # Add documents to vector store
            if self.vector_store is None:
                await self.initialize_vector_store()
            
            await self.vector_store.aadd_texts(
                texts=documents,
                metadatas=metadatas
            )
            
            logger.info(f"Successfully loaded {len(documents)} methods into vector store")
            
        except Exception as e:
            logger.error(f"Failed to load methods from documentation: {e}")
            raise
    
    def _create_searchable_text(self, method: Dict[str, Any]) -> str:
        """Create searchable text from method information."""
        parts = [
            f"Method: {method['name']}",
            f"Description: {method['description']}"
        ]
        
        # Add parameter descriptions
        if method.get("parameters"):
            param_descriptions = []
            for param in method["parameters"]:
                param_desc = f"{param['name']} ({param['type']}): {param['description']}"
                param_descriptions.append(param_desc)
            parts.append(f"Parameters: {'; '.join(param_descriptions)}")
        
        # Add use cases
        if method.get("use_cases"):
            parts.append(f"Use cases: {'; '.join(method['use_cases'])}")
        
        # Add return type info
        if method.get("returns"):
            returns = method["returns"]
            parts.append(f"Returns: {returns.get('type', 'Unknown')}")
        
        # Add category
        if method.get("category"):
            parts.append(f"Category: {method['category']}")
        
        return " | ".join(parts)
    
    async def retrieve_methods(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve most relevant methods based on query."""
        try:
            if self.vector_store is None:
                await self.initialize_vector_store()
            
            # Perform similarity search
            results = await self.vector_store.asimilarity_search(
                query=query,
                k=k
            )
            
            retrieved_methods = []
            for doc in results:
                method_info = {
                    # "method_name": doc.metadata["method_name"],
                    # "description": doc.metadata["description"],
                    # "parameters": json.loads(doc.metadata["parameters"]),
                    # "returns": json.loads(doc.metadata["returns"]),
                    # "use_cases": json.loads(doc.metadata["use_cases"]),
                    # "category": doc.metadata["category"],
                    # "similarity_score": float(score),
                    "searchable_content": doc.page_content
                }
                retrieved_methods.append(method_info)
            
            logger.info(f"Retrieved {len(retrieved_methods)} methods for query: '{query}'")
            return retrieved_methods
            
        except Exception as e:
            logger.error(f"Failed to retrieve methods for query '{query}': {e}")
            raise
    
    async def check_index_exists(self) -> bool:
        """Check if the vector store index exists."""
        try:
            # Check if index exists in Redis
            index_info = self.redis_client.ft(self.index_name).info()
            return True
        except Exception:
            return False
    
    async def rebuild_index(self, documentation_path: str):
        """Rebuild the entire vector index."""
        try:
            # Delete existing index if it exists
            if await self.check_index_exists():
                self.redis_client.ft(self.index_name).dropindex(delete_documents=True)
                logger.info(f"Dropped existing index: {self.index_name}")
            
            # Reinitialize and reload
            self.vector_store = None
            await self.load_methods_from_documentation(documentation_path)
            logger.info("Vector index rebuilt successfully")
            
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the vector store service."""
        try:
            # Check Redis connection
            self.redis_client.ping()
            
            # Check if index exists
            index_exists = await self.check_index_exists()
            
            # Get index stats if it exists
            doc_count = 0
            if index_exists:
                info = self.redis_client.ft(self.index_name).info()
                doc_count = info.get("num_docs", 0)
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "index_exists": index_exists,
                "document_count": doc_count,
                "index_name": self.index_name
            }
            
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "redis_connected": False,
                "index_exists": False,
                "document_count": 0
            }