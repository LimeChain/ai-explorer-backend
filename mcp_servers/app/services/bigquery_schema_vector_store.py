"""
BigQuery Schema Vector Store service for intelligent schema retrieval using PostgreSQL pgVector.
"""
import json
import logging
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from langchain_core.documents import Document
from google.cloud import bigquery
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class BigQuerySchemaVectorStore:
    """Service for managing BigQuery table schema embeddings in PostgreSQL with pgVector."""
    
    def __init__(
        self, 
        connection_string: str, 
        openai_api_key: str, 
        collection_name: str, 
        embedding_model: str,
        bigquery_credentials_path: str,
        dataset_id: str
    ):
        """
        Initialize the BigQuery Schema Vector Store.
        
        Args:
            connection_string: PostgreSQL connection string
            openai_api_key: OpenAI API key for embeddings
            collection_name: Name of the vector store collection
            embedding_model: OpenAI embedding model name
            bigquery_credentials_path: Path to BigQuery service account JSON
            dataset_id: BigQuery dataset ID
        """
        self.connection_string = connection_string
        self.collection_name = collection_name
        self.dataset_id = dataset_id
        self.embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key, model=embedding_model)
        self.engine = create_engine(connection_string)
        self.vector_store: Optional[PGVector] = None
        
        # Initialize BigQuery client
        self.credentials = service_account.Credentials.from_service_account_file(bigquery_credentials_path)
        self.bigquery_client = bigquery.Client(credentials=self.credentials, project=self.credentials.project_id)
        
    def initialize_vector_store(self):
        """Initialize the PostgreSQL pgVector store."""
        try:       
            self.vector_store = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=self.connection_string,
                use_jsonb=True
            )
            logger.info(f"Schema vector store initialized with collection: {self.collection_name}")
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Failed to initialize schema vector store: {e}")
            raise RuntimeError(f"Schema vector store initialization failed: {e}") from e
    
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
    
    def _extract_table_schema(self, table_ref) -> Dict[str, Any]:
        """
        Extract complete schema information for a BigQuery table.
        
        Args:
            table_ref: BigQuery table reference
            
        Returns:
            Dict containing structured table schema
        """
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
    
    def _create_searchable_text(self, schema_data: Dict[str, Any]) -> str:
        """
        Create searchable text for vector embeddings from schema data.
        
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
        
        # Join with spaces for natural language flow
        return " ".join(parts)
    
    def load_schemas_from_bigquery(self):
        """Load and embed all table schemas from BigQuery dataset."""
        try:
            tables = self.bigquery_client.list_tables(self.dataset_id)
            table_list = list(tables)
            logger.info(f"Loading schemas for {len(table_list)} tables from dataset: {self.dataset_id}")
            
            documents = []
            
            for table_ref in table_list:
                try:
                    # Extract schema data
                    schema_data = self._extract_table_schema(table_ref)
                    
                    # Create searchable text
                    searchable_text = self._create_searchable_text(schema_data)
                    
                    # Prepare metadata
                    metadata = {
                        "table_id": schema_data["table_id"],
                        "full_table_id": schema_data["full_table_id"],
                        "description": schema_data["description"],
                        "field_count": len(schema_data["fields"]),
                        "has_partition": schema_data["partition_info"] is not None,
                        "partition_field": schema_data["partition_info"]["field"] if schema_data["partition_info"] else None,
                        "dataset_id": self.dataset_id,
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
    
    def retrieve_relevant_schemas(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve most relevant table schemas based on query.
        
        Args:
            query: User's natural language query
            k: Number of tables to retrieve
            
        Returns:
            List of relevant table schema data
        """
        try:
            if self.vector_store is None:
                logger.info("Vector store not initialized, initializing now...")
                self.initialize_vector_store()
            
            # Check if collection exists and has data
            if not self.check_collection_exists():
                logger.warning("Collection does not exist, loading schemas from BigQuery...")
                self.load_schemas_from_bigquery()
            
            logger.info(f"Performing similarity search for query: '{query}' with k={k}")
            
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
                logger.info(f"  -> Table: {schema_data.get('table_id', 'unknown')}")
            
            logger.info(f"Retrieved {len(retrieved_schemas)} relevant schemas for query: '{query}'")
            return retrieved_schemas
            
        except Exception as e:
            logger.error(f"Failed to retrieve schemas for query '{query}': {e}")
            raise
    
    def check_collection_exists(self) -> bool:
        """Check if the schema vector store collection exists."""
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