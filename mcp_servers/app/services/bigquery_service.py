"""BigQuery service wrapper for text-to-SQL query execution."""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from google.cloud import bigquery
from google.oauth2 import service_account
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from .vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class BigQueryService:
    """Service wrapper for BigQuery text-to-SQL operations."""
    
    def __init__(
        self, 
        credentials_path: str, 
        dataset_id: str, 
        openai_api_key: str,
        connection_string: str,
        model_name: str,
        embedding_model: str
    ):
        """
        Initialize the BigQuery service with configuration.
        
        Args:
            credentials_path: Path to BigQuery service account JSON file
            dataset_id: BigQuery dataset ID (e.g., "hedera-etl-bq.hedera_restricted")
            openai_api_key: OpenAI API key for LLM
            connection_string: PostgreSQL connection string for vector store (required)
            model_name: LLM model name for SQL generation
            embedding_model: OpenAI embedding model for schema search
        """
        try:
            # Initialize BigQuery client
            self.credentials_path = credentials_path
            self.credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.client = bigquery.Client(credentials=self.credentials, project=self.credentials.project_id)
            self.dataset_id = dataset_id
            
            # Initialize LLM for SQL generation
            self.llm = init_chat_model(model_name, model_provider="openai", api_key=openai_api_key)
            
            # Initialize schema vector store (required)
            self.schema_vector_store = VectorStoreService(
                connection_string=connection_string,
                openai_api_key=openai_api_key,
                collection_name=f"bigquery_schemas_{dataset_id.replace('-', '_').replace('.', '_')}",
                embedding_model=embedding_model
            )

            
            logger.info(f"Successfully initialized BigQuery service for dataset: {dataset_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery service: {e}")
            raise RuntimeError(f"Failed to initialize BigQuery service: {e}") from e
    
    def _get_relevant_schemas(self, question: str, k: int = 3) -> tuple[str, List[Dict[str, Any]]]:
        """
        Get relevant table schemas using vector search.
        
        Args:
            question: Natural language question
            k: Number of relevant tables to retrieve
            
        Returns:
            Tuple of (formatted schema string, raw schema data)
        """
        try:
            # Use vector store for intelligent schema retrieval
            relevant_schemas = self.schema_vector_store.retrieve_bigquery_schemas(question, k=k)
            
            if not relevant_schemas:
                raise RuntimeError("No relevant schemas found for the query")
            
            # Format schemas for prompt
            formatted_schemas = []
            for schema_data in relevant_schemas:
                table_id = schema_data["table_id"]
                description = schema_data["description"]
                
                schema_lines = [f"Schema for table {table_id}:"]
                schema_lines.append(f"Description: {description}")
                
                # Add field information
                for field in schema_data["fields"]:
                    field_line = f"Name: {field['name']}, Type: {field['type']}, Mode: {field['mode']}"
                    if field.get('description') and field['description'] != f"Field {field['name']} of type {field['type']}":
                        field_line += f", Description: {field['description']}"
                    schema_lines.append(field_line)
                    
                    # Add nested fields if any
                    if 'nested_fields' in field:
                        for nested_field in field['nested_fields']:
                            nested_line = f"\tName: {nested_field['full_path']}, Type: {nested_field['type']}, Mode: {nested_field['mode']}"
                            if nested_field.get('description') and nested_field['description'] != f"Field {nested_field['name']} of type {nested_field['type']}":
                                nested_line += f", Description: {nested_field['description']}"
                            schema_lines.append(nested_line)
                
                schema_lines.append("")  # Add blank line for separation
                formatted_schemas.extend(schema_lines)
            
            logger.info(f"Retrieved {len(relevant_schemas)} relevant table schemas using vector search")
            return "\n".join(formatted_schemas), relevant_schemas
            
        except Exception as e:
            logger.error(f"Failed to retrieve relevant schemas: {e}")
            raise
    
    def _get_partition_info_from_schemas(self, schema_data_list: List[Dict[str, Any]]) -> str:
        """
        Get partition information string from schema data.
        
        Args:
            schema_data_list: List of schema data from vector store
            
        Returns:
            Formatted partition information string
        """
        partition_lines = []
        
        for schema_data in schema_data_list:
            table_id = schema_data["table_id"]
            partition_info = schema_data.get("partition_info")
            
            if partition_info and partition_info["field"]:
                partition_line = f"Table `{table_id}`: partitioned by `{partition_info['field']}` (require_partition_filter={partition_info['require_partition_filter']})"
                partition_lines.append(partition_line)
        
        return "\n".join(partition_lines)
    
    def initialize_schema_vector_store(self):
        """Initialize and load schemas into the vector store."""
        try:
            # Check if collection already exists
            if not self.schema_vector_store.check_collection_exists():
                logger.info("Schema vector store collection not found, loading schemas from BigQuery")
                self.schema_vector_store.load_bigquery_schemas(self.credentials_path, self.dataset_id)
                logger.info("Schema vector store initialized successfully")
            else:
                logger.info("Schema vector store collection already exists, skipping initialization")
        except Exception as e:
            logger.error(f"Failed to initialize schema vector store: {e}")
            raise
    
    
    def _create_sql_prompt_template(self) -> ChatPromptTemplate:
        """Create the prompt template for SQL generation."""
        template = """
            Based on the BigQuery schema below, write a SQL query that answers the user's question. Limit your responses to 10 results.

            Partitioned tables and required filters:
            {partitioned_fields_str}

            Schema:
            {schema}

            Question: {question}

            CRITICAL: Write a valid BigQuery SQL query, use aliases, and use the correct table names.
            CRITICAL: Always use `{dataset_id}` in FROM and JOIN statements as a prefix before table names.
            CRITICAL: Only return clean SQL that can be executed directly, e.g. remove ```sql <query> ```
            CRITICAL: You have context about partitioned tables, so you SHOULD use partition filters when appropriate.

            SQL Query:
        """
        
        return ChatPromptTemplate.from_template(template)
    
    async def generate_sql(self, question: str) -> Dict[str, Any]:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: Natural language question
            
        Returns:
            Dict containing the generated SQL query or error information
        """
        try:
            # Ensure schema vector store is initialized
            if not self.schema_vector_store.check_collection_exists():
                logger.info("Schema vector store not initialized, initializing now...")
                self.initialize_schema_vector_store()
            
            # Get relevant schema and partition info using vector search
            schema, relevant_schema_data = self._get_relevant_schemas(question)
            partitioned_fields_str = self._get_partition_info_from_schemas(relevant_schema_data)
            
            # Create SQL generation chain
            prompt_template = self._create_sql_prompt_template()
            
            sql_chain = (
                RunnablePassthrough()
                | prompt_template
                | self.llm.bind(stop=["\nSQLResult:"])
                | StrOutputParser()
            )
            
            # Generate SQL
            sql_query = await sql_chain.ainvoke({
                "question": question,
                "schema": schema,
                "partitioned_fields_str": partitioned_fields_str,
                "dataset_id": self.dataset_id
            })
            
            # Clean up SQL query
            sql_query = sql_query.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            sql_query = sql_query.strip()
            
            logger.info(f"Generated SQL query for question: {question[:100]}...")
            logger.debug(f"Generated SQL: {sql_query}")
            print('query is: ', sql_query)
            
            return {
                "success": True,
                "sql_query": sql_query,
                "question": question,
            }
            
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            return {
                "error": f"Failed to generate SQL query: {str(e)}",
                "question": question,
            }
    
    async def execute_query(self, sql_query: str) -> Dict[str, Any]:
        """
        Execute a BigQuery SQL query.
        
        Args:
            sql_query: SQL query to execute
            
        Returns:
            Dict containing query results or error information
        """
        try:
            logger.info("Executing BigQuery SQL query")
            logger.debug(f"SQL Query: {sql_query}")
            
            # Execute query
            job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

            query_job = self.client.query(sql_query, job_config=job_config)

            # results = query_job.result()
            
            # Convert results to list of dictionaries
            data = []
            # for row in results:
            #     row_dict = dict(row)
            #     data.append(row_dict)
            
            logger.info(f"Query executed successfully, returned {len(data)} rows")
            
            return {
                "success": True,
                "data": data,
                "row_count": len(data),
                "sql_query": sql_query,
            }
            
        except Exception as e:
            logger.error(f"Failed to execute BigQuery query: {e}")
            return {
                "error": f"Failed to execute query: {str(e)}",
                "sql_query": sql_query
            }
    
    async def text_to_sql_query(self, question: str) -> Dict[str, Any]:
        """
        Complete text-to-SQL pipeline: generate SQL from question and execute it.
        
        Args:
            question: Natural language question
            
        Returns:
            Dict containing query results or error information
        """
        try:
            # Generate SQL
            sql_result = await self.generate_sql(question)
            
            if not sql_result.get("success"):
                logger.error(f"SQL generation failed: {sql_result.get('error', 'Unknown error')}")
                return {
                    "error": sql_result.get("error", "Failed to generate SQL query"),
                    "question": question,
                }
            
            sql_query = sql_result["sql_query"]
            
            # Execute query
            execution_result = await self.execute_query(sql_query)
            
            # Combine results
            return {
                "success": execution_result.get("success", False),
                "question": question,
                "sql_query": sql_query,
                "data": execution_result.get("data", []),
                "row_count": execution_result.get("row_count", 0),
                "error": execution_result.get("error", ""),
            }
            
        except Exception as e:
            logger.error(f"Text-to-SQL pipeline failed: {e}")
            return {
                "error": f"Text-to-SQL pipeline failed: {str(e)}",
                "question": question,
            }