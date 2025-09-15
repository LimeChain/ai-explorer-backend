"""
Vector store service for SDK method retrieval using PostgreSQL pgVector and LangChain embeddings.
This service acts as a facade coordinating the database, text processing, and vector search components.
"""
import json
import logging
import os
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
    
    def _initialize_bigquery_client(self, credentials_path: str, dataset_id: str):
        """Initialize BigQuery client for schema operations."""
        try:
            self.bigquery_credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.bigquery_client = bigquery.Client(
                credentials=self.bigquery_credentials, 
                project=self.bigquery_credentials.project_id
            )
            self.dataset_id = dataset_id
            logger.info(f"BigQuery client initialized for dataset: {dataset_id}")
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery client: {e}")
            raise
    
    def _extract_field_info(self, field, parent_path: str = "") -> Dict[str, Any]:
        """
        Extract field information including nested fields.
        
        Args:
            field: BigQuery schema field
            parent_path: Path prefix for nested fields
            
        Returns:
            Dict containing field information
        """
        field_path = f"{parent_path}.{field.name}" if parent_path else field.name
        
        field_info = {
            "name": field.name,
            "full_path": field_path,
            "type": field.field_type,
            "mode": field.mode,
            "description": field.description or f"Field {field.name} of type {field.field_type}"
        }
        
        # Handle nested fields (RECORD type)
        if field.field_type == "RECORD" and field.fields:
            nested_fields = []
            for nested_field in field.fields:
                nested_info = self._extract_field_info(nested_field, field_path)
                nested_fields.append(nested_info)
            field_info["nested_fields"] = nested_fields
        
        return field_info
    
    def _load_table_metadata(self) -> Dict[str, Any]:
        """
        Load table metadata from JSON file.
        
        Returns:
            Dict containing table metadata with use cases
        """
        if self._table_metadata is not None:
            return self._table_metadata
            
        try:
            # Look for metadata file in app root directory
            metadata_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'bigquery_table_metadata.json')
            metadata_path = os.path.abspath(metadata_path)
            
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    self._table_metadata = json.load(f)
                logger.info(f"Loaded table metadata from: {metadata_path}")
            else:
                logger.warning(f"Table metadata file not found at: {metadata_path}")
                self._table_metadata = {}
                
            return self._table_metadata
            
        except Exception as e:
            logger.error(f"Failed to load table metadata: {e}")
            return {}
    
    def _extract_table_schema(self, table_ref) -> Dict[str, Any]:
        """
        Extract complete schema information for a BigQuery table.
        
        Args:
            table_ref: BigQuery table reference
            
        Returns:
            Dict containing structured table schema
        """
        if not self.bigquery_client:
            raise RuntimeError("BigQuery client not initialized")
            
        table = self.bigquery_client.get_table(table_ref)
        
        # Extract field information
        fields = []
        for field in table.schema:
            field_info = self._extract_field_info(field)
            fields.append(field_info)
        
        # Extract partition information
        partition_info = None
        if table.time_partitioning:
            partition_info = {
                "field": table.time_partitioning.field or "_PARTITIONTIME",
                "type": str(table.time_partitioning.type_),
                "require_partition_filter": getattr(table, "require_partition_filter", False)
            }
        
        # Create structured schema
        schema_data = {
            "table_id": table.table_id,
            "full_table_id": f"{self.dataset_id}.{table.table_id}",
            "description": table.description or f"BigQuery table {table.table_id}",
            "fields": fields,
            "partition_info": partition_info,
            "created": table.created.isoformat() if table.created else None,
            "modified": table.modified.isoformat() if table.modified else None,
            "num_rows": table.num_rows,
            "dataset_id": self.dataset_id
        }
        
        return schema_data
    
    def _create_bigquery_searchable_text(self, schema_data: Dict[str, Any]) -> str:
        """
        Create searchable text for BigQuery schema vector embeddings.
        
        Args:
            schema_data: Structured schema data
            
        Returns:
            Searchable text string
        """
        parts = []
        
        # Table name and description
        parts.append(f"Table {schema_data['table_id']}")
        parts.append(schema_data['description'])
        
        # Field information in natural language
        for field in schema_data['fields']:
            field_text = f"Field {field['name']} {field['type']} {field['description']}"
            parts.append(field_text)
            
            # Include nested fields
            if 'nested_fields' in field:
                for nested_field in field['nested_fields']:
                    nested_text = f"Nested field {nested_field['full_path']} {nested_field['type']} {nested_field['description']}"
                    parts.append(nested_text)
        
        # Partition information
        if schema_data['partition_info']:
            parts.append(f"Partitioned by {schema_data['partition_info']['field']}")
        
        # Add use cases and rules if available
        table_metadata = self._load_table_metadata()
        table_id = schema_data['table_id']
        if table_id in table_metadata:
            table_meta = table_metadata[table_id]
            # Add use cases
            if table_meta.get('use_cases'):
                parts.extend(table_meta['use_cases'])
            # Add rules
            if table_meta.get('rules'):
                parts.extend(table_meta['rules'])
        
        return " ".join(parts)
    
    def load_bigquery_schemas(self, credentials_path: str, dataset_id: str):
        """
        Load and embed all table schemas from BigQuery dataset.
        
        Args:
            credentials_path: Path to BigQuery service account JSON file
            dataset_id: BigQuery dataset ID
        """
        try:
            # Initialize BigQuery client if not already done
            if not self.bigquery_client:
                self._initialize_bigquery_client(credentials_path, dataset_id)
            
            tables = self.bigquery_client.list_tables(self.dataset_id)
            table_list = list(tables)
            logger.info(f"Loading schemas for {len(table_list)} tables from dataset: {self.dataset_id}")
            
            documents = []
            
            for table_ref in table_list:
                try:
                    # Extract schema data
                    schema_data = self._extract_table_schema(table_ref)
                    
                    # Create searchable text
                    searchable_text = self._create_bigquery_searchable_text(schema_data)
                    
                    # Load table metadata for use cases and rules
                    table_metadata = self._load_table_metadata()
                    table_use_cases = []
                    table_rules = []
                    if schema_data["table_id"] in table_metadata:
                        table_meta = table_metadata[schema_data["table_id"]]
                        table_use_cases = table_meta.get('use_cases', [])
                        table_rules = table_meta.get('rules', [])
                    
                    # Prepare metadata
                    metadata = {
                        "table_id": schema_data["table_id"],
                        "full_table_id": schema_data["full_table_id"],
                        "description": schema_data["description"],
                        "field_count": len(schema_data["fields"]),
                        "has_partition": schema_data["partition_info"] is not None,
                        "partition_field": schema_data["partition_info"]["field"] if schema_data["partition_info"] else None,
                        "dataset_id": self.dataset_id,
                        "use_cases": table_use_cases,
                        "rules": table_rules,
                        "schema_data": json.dumps(schema_data)
                    }
                    
                    # Create Document
                    doc = Document(
                        page_content=searchable_text,
                        metadata=metadata
                    )
                    documents.append(doc)
                    
                except Exception as e:
                    logger.warning(f"Failed to process table {table_ref.table_id}: {e}")
                    continue
            
            # Initialize vector store if needed
            if self.vector_store is None:
                self.initialize_vector_store()
            
            # Add documents to vector store
            self.vector_store.add_documents(documents)
            
            logger.info(f"Successfully loaded {len(documents)} table schemas into vector store")
            
        except Exception as e:
            logger.error(f"Failed to load schemas from BigQuery: {e}")
            raise
    
    def retrieve_bigquery_data(self, query: str, k: int = 3) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Retrieve most relevant BigQuery table data based on query.
        
        Args:
            query: User's natural language query
            k: Number of tables to retrieve
            
        Returns:
            Tuple of (List of relevant table data, Dictionary of relevant metadata)
        """
        try:
            if self.vector_store is None:
                logger.info("Vector store not initialized, initializing now...")
                self.initialize_vector_store()
            
            # Check if collection exists and has data
            if not self.check_collection_exists():
                logger.warning("Collection does not exist or is empty")
                return [], {}
            
            logger.info(f"Performing similarity search for query: '{query}' with k={k}")
            
            # Perform similarity search
            results = self.vector_store.similarity_search(
                query=query,
                k=k
            )
            
            logger.info(f"Similarity search returned {len(results)} documents")
            
            retrieved_schemas = []
            retrieved_metadata = {}
            
            for i, doc in enumerate(results):
                logger.info(f"Document {i+1}: page_content length={len(doc.page_content)}, metadata keys={list(doc.metadata.keys())}")
                # Parse the full schema data from metadata
                schema_data = json.loads(doc.metadata["schema_data"])
                retrieved_metadata[doc.metadata["table_id"]] = {
                    "use_cases": doc.metadata["use_cases"],
                    "rules": doc.metadata["rules"]
                }
                retrieved_schemas.append(schema_data)
                logger.info(f"  -> Table: {schema_data.get('table_id', 'unknown')}")
            
            logger.info(f"Retrieved {len(retrieved_schemas)} relevant schemas for query: '{query}'")
            return retrieved_schemas, retrieved_metadata
            
        except Exception as e:
            logger.error(f"Failed to retrieve schemas for query '{query}': {e}")
            raise
    
    def check_collection_exists(self) -> bool:
        """Check if the vector store collection exists and has documents."""
        try:
            # Check if the pgVector collection table exists
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'langchain_pg_collection');"
                ))
                collection_table_exists = result.scalar()
                logger.info(f"Collection table exists: {collection_table_exists}")
                
                if not collection_table_exists:
                    logger.info("langchain_pg_collection table does not exist")
                    return False
                
                # Check if our specific collection exists
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM langchain_pg_collection WHERE name = :collection_name);"
                ), {"collection_name": self.collection_name})
                collection_exists = result.scalar()
                logger.info(f"Collection '{self.collection_name}' exists: {collection_exists}")
                
                # If collection exists, also check if it has any documents
                if collection_exists:
                    result = conn.execute(text(
                        "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = (SELECT uuid FROM langchain_pg_collection WHERE name = :collection_name);"
                    ), {"collection_name": self.collection_name})
                    doc_count = result.scalar()
                    logger.info(f"Collection '{self.collection_name}' has {doc_count} documents")
                    return doc_count > 0
                
                return False
        except Exception as e:
            logger.error(f"Error checking schema collection existence: {e}")
            return False
    
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
            self.vector_store.add_documents(documents)
            
            logger.info(f"Successfully loaded {len(documents)} GraphQL schema types into vector store")
            
        except Exception as e:
            logger.error(f"Failed to load GraphQL schemas: {e}")
            raise
    
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
            if not self.check_collection_exists():
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
