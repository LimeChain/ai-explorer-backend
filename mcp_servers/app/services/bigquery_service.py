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

COST_PER_TB_IN_USD = 6.25

class BigQueryService:
    """Service wrapper for BigQuery text-to-SQL operations."""
    
    def __init__(
        self, 
        credentials_path: str, 
        dataset_id: str, 
        llm_api_key: str,
        connection_string: str,
        llm_model: str,
        llm_provider: str,
        embedding_model: str
    ):
        """
        Initialize the BigQuery service with configuration.
        
        Args:
            credentials_path: Path to BigQuery service account JSON file
            dataset_id: BigQuery dataset ID (e.g., "hedera-etl-bq.hedera_restricted")
            llm_api_key: API key for LLM
            connection_string: PostgreSQL connection string for vector store (required)
            llm_model: LLM model name for SQL generation
            llm_provider: LLM provider for SQL generation
            embedding_model: OpenAI embedding model for schema search
        """
        try:
            # Initialize BigQuery client
            self.credentials_path = credentials_path
            self.credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.client = bigquery.Client(credentials=self.credentials, project=self.credentials.project_id)
            self.dataset_id = dataset_id
            
            # Initialize LLM for SQL generation
            self.llm = init_chat_model(llm_model, model_provider=llm_provider, api_key=llm_api_key)
            
            # Initialize schema vector store (required)
            self.schema_vector_store = VectorStoreService(
                connection_string=connection_string,
                llm_api_key=llm_api_key,
                collection_name=f"bigquery_schemas_{dataset_id.replace('-', '_').replace('.', '_')}",
                embedding_model=embedding_model
            )

            
            logger.info(f"Successfully initialized BigQuery service for dataset: {dataset_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery service: {e}")
            raise RuntimeError(f"Failed to initialize BigQuery service: {e}") from e
    
    def _extract_rules_for_relevant_tables(self, relevant_metadata: Dict[str, Any]) -> str:
        """
        Extract and format rules from all relevant tables into a coherent prompt section.
        
        Args:
            relevant_metadata: Dictionary with table_id as key and metadata as value
            
        Returns:
            Formatted string with rules for all relevant tables
        """
        if not relevant_metadata:
            logger.warning("No relevant metadata provided for rule extraction")
            return "No specific table rules available."
        
        rule_sections = []
        
        for table_name, metadata in relevant_metadata.items():
            table_rules = metadata.get("rules", [])
            
            if table_rules:
                rule_sections.append(f"Rules for {table_name} table:")
                for rule in table_rules:
                    rule_sections.append(f"- {rule}")
                rule_sections.append("")  # Add spacing between tables
            else:
                logger.debug(f"No rules found for table: {table_name}")
        
        if not rule_sections:
            logger.warning("No rules found in any relevant tables")
            return "No specific table rules available."
        
        # Remove trailing empty line
        if rule_sections and rule_sections[-1] == "":
            rule_sections.pop()
            
        formatted_rules = "\n".join(rule_sections)
        logger.debug(f"Extracted rules for {len(relevant_metadata)} tables")
        
        return formatted_rules
    
    def _get_relevant_schemas(self, relevant_schemas: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
        """
        Get relevant table schemas using vector search.
        
        Args:
            question: Natural language question
            k: Number of relevant tables to retrieve
            
        Returns:
            Tuple of (formatted schema string, raw schema data)
        """
        try:
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
        """
        Create the prompt template for SQL generation.
        """
        
        template = """
            Based on the BigQuery schema below, write a SQL query that answers the user's question. Limit your responses to 10 results.

            Partitioned tables and required filters:
            {partitioned_fields_str}

            Schema:
            {schema}

            CRITICAL QUERY RULES (MUST FOLLOW):
            {rules}

            Question: {question}

            CRITICAL: Write a valid BigQuery SQL query, use aliases, and use the correct table names.
            CRITICAL: Always use `{dataset_id}` in FROM and JOIN statements as a prefix before table names.
            CRITICAL: Only return clean SQL that can be executed directly, e.g. remove ```sql <query> ```
            CRITICAL: Follow the CRITICAL QUERY RULES above - especially about date filters.

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
            relevant_schemas, relevant_metadata = self.schema_vector_store.retrieve_bigquery_data(question, k=3)
            schema, relevant_schema_data = self._get_relevant_schemas(relevant_schemas)
            partitioned_fields_str = self._get_partition_info_from_schemas(relevant_schema_data)
            
            # Extract rules for all relevant tables dynamically
            table_rules = self._extract_rules_for_relevant_tables(relevant_metadata)
            
            # Create SQL generation chain (no retry logic)
            prompt_template = self._create_sql_prompt_template()
            
            sql_chain = (
                RunnablePassthrough()
                | prompt_template
                | self.llm.bind(stop=["\nSQLResult:", "\nSQL Query:"])
                | StrOutputParser()
            )
            
            # Prepare prompt parameters
            prompt_params = {
                "question": question,
                "schema": schema,
                "partitioned_fields_str": partitioned_fields_str,
                "dataset_id": self.dataset_id,
                "rules": table_rules
            }
            
            # Generate SQL
            sql_query = await sql_chain.ainvoke(prompt_params)
            
            # Clean up SQL query
            sql_query = sql_query.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            sql_query = sql_query.strip()
            
            logger.info(f"Generated SQL query for question: {question[:100]}...")
            logger.debug(f"Generated SQL: {sql_query}")
            
            return {
                "success": True,
                "sql_query": sql_query,
                "question": question,
                "rules": table_rules
            }
            
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            return {
                "success": False,
                "error": f"Failed to generate SQL query: {str(e)}",
                "question": question
            }

    def validate_and_estimate_cost(self, sql_query: str) -> Dict[str, Any]:
        """
        Validate SQL syntax and calculate query cost in a single dry run.
        
        Args:
            sql_query: SQL query to validate and estimate cost for
            
        Returns:
            Dict containing validation status, cost, and detailed error information
        """
        try:
            # Perform single dry run for both validation and cost estimation
            job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
            query_job = self.client.query(sql_query, job_config=job_config)
            
            # If we reach here, query syntax is valid
            bytes_to_process = query_job.total_bytes_processed
            cost = (bytes_to_process / (10**12)) * COST_PER_TB_IN_USD
            
            logger.info(f"Query validation successful. Estimated cost: ${cost:.4f}, Bytes: {bytes_to_process}")
            
            return {
                "success": True,
                "valid": True,
                "cost": cost,
                "bytes_to_process": bytes_to_process,
                "sql_query": sql_query,
                "job_id": query_job.job_id
            }
            
        except Exception as e:
            logger.error(f"Query validation/cost estimation failed: {e}")
            
            # Provide detailed error information for retry logic
            error_message = str(e)
            is_syntax_error = any(keyword in error_message.lower() for keyword in [
                'syntax error', 'invalid', 'parse error', 'unexpected', 
                'expected', 'missing', 'table not found', 'column not found'
            ])
            
            return {
                "success": False,
                "valid": False,
                "error": error_message,
                "is_syntax_error": is_syntax_error,
                "sql_query": sql_query,
                "cost": None,
                "bytes_to_process": None
            }
    
    async def execute_query(self, sql_query: str) -> Dict[str, Any]:
        """
        Execute a BigQuery SQL query and return actual results.
        
        Args:
            sql_query: SQL query to execute (should be pre-validated)
            
        Returns:
            Dict containing query results or error information
        """
        try:
            logger.info("Executing BigQuery SQL query")
            logger.debug(f"SQL Query: {sql_query}")
            
            # Execute query (not dry run - actual execution)
            job_config = bigquery.QueryJobConfig(use_query_cache=True)
            query_job = self.client.query(sql_query, job_config=job_config)
            
            # Wait for query to complete and get results
            results = query_job.result()
            
            # Convert results to list of dictionaries
            data = []
            for row in results:
                row_dict = dict(row)
                # Convert any nested/complex types to strings for JSON serialization
                for key, value in row_dict.items():
                    if value is not None and not isinstance(value, (str, int, float, bool)):
                        row_dict[key] = str(value)
                data.append(row_dict)
            
            logger.info(f"Query executed successfully, returned {len(data)} rows")
            
            return {
                "success": True,
                "data": data,
                "row_count": len(data),
                "sql_query": sql_query,
                "job_id": query_job.job_id,
                "total_bytes_processed": query_job.total_bytes_processed,
                "total_bytes_billed": query_job.total_bytes_billed
            }
            
        except Exception as e:
            logger.error(f"Failed to execute BigQuery query: {e}")
            return {
                "success": False,
                "error": f"Failed to execute query: {str(e)}",
                "sql_query": sql_query
            }
    
    async def text_to_sql_query(self, question: str, cost_threshold) -> Dict[str, Any]:
        """
        Complete text-to-SQL pipeline: generate SQL, validate, estimate cost, and execute.
        No retry logic - either succeeds or fails with clear error message.
        
        Args:
            question: Natural language question
            cost_threshold: Maximum allowed cost in USD for query execution
            
        Returns:
            Dict containing query results or error information
        """
        try:
            logger.info(f"Starting text-to-SQL pipeline for question: {question[:100]}...")
            
            # Generate SQL
            sql_result = await self.generate_sql(question=question)
            
            if not sql_result.get("success"):
                error = sql_result.get("error", "Unknown SQL generation error")
                logger.error(f"SQL generation failed: {error}")
                return {
                    "success": False,
                    "error": f"Failed to generate SQL query: {error}",
                    "question": question
                }
            
            sql_query = sql_result["sql_query"]
            
            # Validate syntax and estimate cost
            validation_result = self.validate_and_estimate_cost(sql_query)
            
            if not validation_result.get("success") or not validation_result.get("valid"):
                error = validation_result.get("error", "Query validation failed")
                logger.error(f"Query validation failed: {error}")
                return {
                    "success": False,
                    "error": f"Query validation failed: {error}",
                    "question": question,
                    "sql_query": sql_query
                }
            
            # Check cost threshold
            cost = validation_result["cost"]
            logger.info(f"Query validated successfully. Estimated cost: ${cost:.4f}")
            
            if cost > cost_threshold:
                cost_error = f"Query cost ${cost:.4f} exceeds threshold ${cost_threshold}. The query would be too expensive to execute."
                logger.warning(f"Cost threshold exceeded: ${cost:.4f} > ${cost_threshold}")
                
                return {
                    "success": False,
                    "error": cost_error,
                    "question": question,
                    "sql_query": sql_query,
                    "cost": cost,
                    "bytes_to_process": validation_result.get("bytes_to_process", 0)
                }
            
            # Execute validated query
            execution_result = await self.execute_query(sql_query)
            
            if not execution_result.get("success"):
                execution_error = execution_result.get("error", "Query execution failed")
                logger.error(f"Query execution failed: {execution_error}")
                return {
                    "success": False,
                    "error": f"Query execution failed: {execution_error}",
                    "question": question,
                    "sql_query": sql_query,
                    "cost": cost,
                    "bytes_to_process": validation_result.get("bytes_to_process", 0)
                }
            
            # Success! Return combined results
            logger.info(f"Text-to-SQL pipeline successful")
            return {
                "success": True,
                "question": question,
                "sql_query": sql_query,
                "data": execution_result.get("data", []),
                "row_count": execution_result.get("row_count", 0),
                "cost": cost,
                "bytes_to_process": validation_result.get("bytes_to_process", 0),
                "bytes_billed": execution_result.get("total_bytes_billed", 0),
                "job_id": execution_result.get("job_id")
            }
            
        except Exception as e:
            logger.error(f"Text-to-SQL pipeline error: {e}")
            return {
                "success": False,
                "error": f"Text-to-SQL pipeline failed: {str(e)}",
                "question": question
            }