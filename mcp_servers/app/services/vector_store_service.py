"""
Vector store service for SDK method retrieval using PostgreSQL pgVector and LangChain embeddings.
This service acts as a facade coordinating the database, text processing, and vector search components.
"""
import json
import logging
from typing import Dict, List, Any, Tuple
from sqlalchemy import create_engine, text
from langchain_core.documents import Document


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
        
        # Initialize engine for direct database access
        self.engine = create_engine(connection_string)
        
        # Initialize vector store attribute (will be set by initialize_vector_store)
        self.vector_store = None
        
        logger.info("✅ VectorStoreService initialized", extra={
            "collection_name": collection_name,
            "embedding_model": embedding_model
        })
        
    def initialize_vector_store(self):
        """Initialize the PostgreSQL pgVector store - delegates to VectorSearchService."""
        self.vector_search_service.initialize_vector_store()
        # Set the vector_store attribute to match the search service's vector store
        self.vector_store = self.vector_search_service.vector_store
    
    def load_methods_from_documentation(self, documentation_path: str):
        """Load and embed SDK methods from documentation JSON - delegates to VectorSearchService."""
        self.vector_search_service.load_documentation(documentation_path)
    
    def retrieve_methods(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve most relevant methods based on query - delegates to VectorSearchService."""
        return self.vector_search_service.similarity_search(query, k)
    
    def _create_graphql_searchable_text(self, type_data: Dict[str, Any]) -> str:
        """
        Create searchable text for GraphQL schema type embeddings.
        
        Args:
            type_data: GraphQL type data from schema
            
        Returns:
            Searchable text string
        """
        parts = []
        
        # Type name and description
        parts.append(f"{type_data['kind']} {type_data['name']}")
        if type_data.get('description'):
            parts.append(type_data['description'])
        
        # Field information for OBJECT types
        if type_data['kind'] == 'OBJECT' and type_data.get('fields'):
            for field in type_data['fields']:
                field_text = f"Field {field['name']} {self._format_graphql_type_for_search(field['type'])}"
                if field.get('description'):
                    field_text += f" {field['description']}"
                parts.append(field_text)
                
                # Include args information
                if field.get('args'):
                    for arg in field['args']:
                        arg_text = f"Argument {arg['name']} {self._format_graphql_type_for_search(arg['type'])}"
                        if arg.get('description'):
                            arg_text += f" {arg['description']}"
                        parts.append(arg_text)
        
        # Input fields for INPUT_OBJECT types
        elif type_data['kind'] == 'INPUT_OBJECT' and type_data.get('inputFields'):
            for field in type_data['inputFields']:
                field_text = f"Input field {field['name']} {self._format_graphql_type_for_search(field['type'])}"
                if field.get('description'):
                    field_text += f" {field['description']}"
                parts.append(field_text)
        
        # Enum values for ENUM types
        elif type_data['kind'] == 'ENUM' and type_data.get('enumValues'):
            for value in type_data['enumValues']:
                value_text = f"Enum value {value['name']}"
                if value.get('description'):
                    value_text += f" {value['description']}"
                parts.append(value_text)
        
        return " ".join(parts)
    
    def _format_graphql_type_for_search(self, type_info: Dict[str, Any]) -> str:
        """Format GraphQL type information for searchable text."""
        if type_info.get('kind') == 'NON_NULL':
            return f"{self._format_graphql_type_for_search(type_info['ofType'])} required"
        elif type_info.get('kind') == 'LIST':
            return f"list of {self._format_graphql_type_for_search(type_info['ofType'])}"
        elif type_info.get('name'):
            return type_info['name']
        else:
            return "unknown type"
    
    def load_graphql_schemas(self, schema_path: str):
        """
        Load and embed GraphQL schema types from JSON file.
        
        Args:
            schema_path: Path to the GraphQL schema introspection JSON file
        """
        try:
            with open(schema_path, 'r') as f:
                schema_data = json.load(f)
            
            # Extract types from introspection schema
            types = schema_data.get("data", {}).get("__schema", {}).get("types", [])
            
            # Filter out built-in GraphQL types and focus on custom types
            custom_types = []
            builtin_prefixes = ('__', 'Boolean', 'String', 'Int', 'Float', 'ID')
            
            for type_def in types:
                type_name = type_def.get("name", "")
                # Skip built-in types and comparison types
                if (not type_name.startswith(builtin_prefixes) and 
                    not type_name.endswith('_comparison_exp') and
                    not type_name.endswith('_order_by') and
                    type_name not in ['Boolean', 'String', 'Int', 'Float', 'ID']):
                    custom_types.append(type_def)
            
            logger.info(f"Loading {len(custom_types)} GraphQL schema types from {schema_path}")
            
            documents = []
            
            for type_def in custom_types:
                try:
                    # Create searchable text
                    searchable_text = self._create_graphql_searchable_text(type_def)
                    
                    # Prepare metadata
                    metadata = {
                        "name": type_def["name"],
                        "kind": type_def["kind"],
                        "description": type_def.get("description", ""),
                        "field_count": len(type_def.get("fields", [])) if type_def.get("fields") else 0,
                        "input_field_count": len(type_def.get("inputFields", [])) if type_def.get("inputFields") else 0,
                        "enum_value_count": len(type_def.get("enumValues", [])) if type_def.get("enumValues") else 0,
                        "schema_data": json.dumps(type_def)
                    }
                    
                    # Create Document
                    doc = Document(
                        page_content=searchable_text,
                        metadata=metadata
                    )
                    documents.append(doc)
                    
                except Exception as e:
                    logger.warning(f"Failed to process GraphQL type {type_def.get('name', 'unknown')}: {e}")
                    continue
            
            # Initialize vector store if needed
            if self.vector_store is None:
                self.initialize_vector_store()
            
            # Add documents to vector store
            self.vector_search_service.add_documents(documents)
            
            logger.info(f"Successfully loaded {len(documents)} GraphQL schema types into vector store")
            
        except Exception as e:
            logger.error(f"Failed to load GraphQL schemas: {e}")
            raise
    
    def check_index_exists(self) -> bool:
        """
        Check if the vector store collection/index exists.
        Delegates to VectorSearchService.
        
        Returns:
            True if collection exists, False otherwise
        """
        return self.vector_search_service.check_collection_exists()
    
    def retrieve_graphql_schemas(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve most relevant GraphQL schema types based on query.
        
        Args:
            query: User's natural language query
            k: Number of types to retrieve
            
        Returns:
            List of relevant GraphQL schema type data
        """
        try:
            if self.vector_store is None:
                logger.info("Vector store not initialized, initializing now...")
                self.initialize_vector_store()
            
            # Check if collection exists and has data
            if not self.vector_search_service.check_collection_exists():
                logger.warning("Collection does not exist or is empty")
                return []
            
            logger.info(f"Performing similarity search for GraphQL query: '{query}' with k={k}")
            
            # Perform similarity search
            results = self.vector_store.similarity_search(
                query=query,
                k=k
            )
            
            logger.info(f"Similarity search returned {len(results)} documents")
            
            retrieved_schemas = []
            for i, doc in enumerate(results):
                logger.info(f"Document {i+1}: page_content length={len(doc.page_content)}, metadata keys={list(doc.metadata.keys())}")
                # Parse the full schema data from metadata
                schema_data = json.loads(doc.metadata["schema_data"])
                retrieved_schemas.append(schema_data)
                logger.info(f"  -> Type: {schema_data.get('name', 'unknown')} ({schema_data.get('kind', 'unknown')})")
            
            logger.info(f"Retrieved {len(retrieved_schemas)} relevant GraphQL schemas for query: '{query}'")
            return retrieved_schemas
            
        except Exception as e:
            logger.error(f"Failed to retrieve GraphQL schemas for query '{query}': {e}")
            raise
