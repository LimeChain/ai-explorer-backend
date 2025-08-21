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
    
    def _create_sql_prompt_template(self, include_error_context: bool = False) -> ChatPromptTemplate:
        """
        Create the prompt template for SQL generation with optional error context.
        
        Args:
            include_error_context: Whether to include error context for retry attempts
        """
        if include_error_context:
            template = """
                Based on the BigQuery schema below, write a SQL query that answers the user's question. Limit your responses to 10 results.

                Partitioned tables and required filters:
                {partitioned_fields_str}

                Schema:
                {schema}

                Question: {question}

                PREVIOUS ATTEMPT FAILED:
                Previous SQL Query: {previous_sql}
                Error Message: {error_message}
                Attempt: {attempt_number} of 3

                CRITICAL: Write a valid BigQuery SQL query that fixes the above error.
                CRITICAL: Always use `{dataset_id}` in FROM and JOIN statements as a prefix before table names.
                CRITICAL: Only return clean SQL that can be executed directly, e.g. remove ```sql <query> ```
                CRITICAL: You have context about partitioned tables, so you SHOULD use partition filters when appropriate.
                CRITICAL: Analyze the previous error and fix the specific issue mentioned.
                CRITICAL: If the error mentions missing columns, check the schema carefully for correct column names.
                CRITICAL: If the error mentions table not found, ensure you're using the correct table name with dataset prefix.
                CRITICAL: If the error mentions syntax issues, fix the SQL syntax according to BigQuery standards.

                Corrected SQL Query:
            """
        else:
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
    
    async def generate_sql(self, question: str, previous_sql: str = None, error_message: str = None, attempt_number: int = 1) -> Dict[str, Any]:
        """
        Generate SQL query from natural language question with optional error context for retries.
        
        Args:
            question: Natural language question
            previous_sql: Previous SQL query that failed (for retry attempts)
            error_message: Error message from previous attempt (for retry attempts)
            attempt_number: Current attempt number (for retry context)
            
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
            
            # Create SQL generation chain with error context if this is a retry
            is_retry = previous_sql is not None and error_message is not None
            prompt_template = self._create_sql_prompt_template(include_error_context=is_retry)
            
            sql_chain = (
                RunnablePassthrough()
                | prompt_template
                | self.llm.bind(stop=["\nSQLResult:", "\nCorrected SQL Query:"])
                | StrOutputParser()
            )
            
            # Prepare prompt parameters
            prompt_params = {
                "question": question,
                "schema": schema,
                "partitioned_fields_str": partitioned_fields_str,
                "dataset_id": self.dataset_id
            }
            
            # Add error context for retry attempts
            if is_retry:
                prompt_params.update({
                    "previous_sql": previous_sql,
                    "error_message": error_message,
                    "attempt_number": attempt_number
                })
            
            # Generate SQL
            sql_query = await sql_chain.ainvoke(prompt_params)
            
            # Clean up SQL query
            sql_query = sql_query.strip()
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            sql_query = sql_query.strip()
            
            attempt_log = f" (attempt {attempt_number})" if attempt_number > 1 else ""
            logger.info(f"Generated SQL query for question: {question[:100]}...{attempt_log}")
            logger.debug(f"Generated SQL: {sql_query}")
            
            return {
                "success": True,
                "sql_query": sql_query,
                "question": question,
                "attempt_number": attempt_number
            }
            
        except Exception as e:
            logger.error(f"Failed to generate SQL (attempt {attempt_number}): {e}")
            return {
                "success": False,
                "error": f"Failed to generate SQL query: {str(e)}",
                "question": question,
                "attempt_number": attempt_number
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
    
    async def text_to_sql_query(self, question: str, cost_threshold, max_retries: int = 3) -> Dict[str, Any]:
        """
        Complete text-to-SQL pipeline with retry logic: generate SQL, validate, estimate cost, and execute.
        
        Args:
            question: Natural language question
            max_retries: Maximum number of retry attempts for SQL generation
            cost_threshold: Maximum allowed cost in USD for query execution
            
        Returns:
            Dict containing query results or error information
        """
        last_error = None
        previous_sql = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Starting text-to-SQL pipeline attempt {attempt} for question: {question[:100]}...")
                
                # Generate SQL with error context if this is a retry
                sql_result = await self.generate_sql(
                    question=question,
                    previous_sql=previous_sql,
                    error_message=last_error,
                    attempt_number=attempt
                )
                
                if not sql_result.get("success"):
                    last_error = sql_result.get("error", "Unknown SQL generation error")
                    logger.warning(f"SQL generation failed on attempt {attempt}: {last_error}")
                    
                    # Continue to next attempt if we haven't reached max retries
                    if attempt < max_retries:
                        continue
                    else:
                        return {
                            "success": False,
                            "error": f"Failed to generate SQL after {max_retries} attempts. Last error: {last_error}",
                            "question": question,
                            "total_attempts": attempt
                        }
                
                sql_query = sql_result["sql_query"]
                previous_sql = sql_query  # Store for potential retry
                
                # Validate syntax and estimate cost in single operation
                validation_result = self.validate_and_estimate_cost(sql_query)
                
                if not validation_result.get("success") or not validation_result.get("valid"):
                    last_error = validation_result.get("error", "Query validation failed")
                    logger.warning(f"Query validation failed on attempt {attempt}: {last_error}")
                    
                    # Continue to next attempt if we haven't reached max retries
                    if attempt < max_retries:
                        continue
                    else:
                        return {
                            "success": False,
                            "error": f"Query validation failed after {max_retries} attempts. Last error: {last_error}",
                            "question": question,
                            "sql_query": sql_query,
                            "total_attempts": attempt
                        }
                
                # Check cost threshold
                cost = validation_result["cost"]
                logger.info(f"Query validated successfully. Estimated cost: ${cost:.4f}")
                
                if cost > cost_threshold:
                    cost_error = f"Query cost ${cost:.4f} exceeds threshold ${cost_threshold}. Please simplify the query, add more filters, or limit the time range."
                    logger.warning(f"Cost threshold exceeded.")
                    
                    return {
                        "success": False,
                        "error": cost_error,
                        "question": question,
                        "sql_query": sql_query,
                        "cost": cost,
                        "bytes_to_process": validation_result.get("bytes_to_process", 0),
                        "total_attempts": attempt
                    }
                
                # Execute validated query
                execution_result = await self.execute_query(sql_query)
                
                if not execution_result.get("success"):
                    execution_error = execution_result.get("error", "Query execution failed")
                    logger.error(f"Query execution failed on attempt {attempt}: {execution_error}")
                    
                    # For execution failures, we can retry with the execution error
                    if attempt < max_retries:
                        last_error = f"Query execution failed: {execution_error}"
                        continue
                    else:
                        return {
                            "success": False,
                            "error": f"Query execution failed after {max_retries} attempts. Last error: {execution_error}",
                            "question": question,
                            "sql_query": sql_query,
                            "cost": cost,
                            "bytes_to_process": validation_result.get("bytes_to_process", 0),
                            "total_attempts": attempt
                        }
                
                # Success! Return combined results
                logger.info(f"Text-to-SQL pipeline successful on attempt {attempt}")
                return {
                    "success": True,
                    "question": question,
                    "sql_query": sql_query,
                    "data": execution_result.get("data", []),
                    "row_count": execution_result.get("row_count", 0),
                    "cost": cost,
                    "bytes_to_process": validation_result.get("bytes_to_process", 0),
                    "bytes_billed": execution_result.get("total_bytes_billed", 0),
                    "job_id": execution_result.get("job_id"),
                    "total_attempts": attempt
                }
                
            except Exception as e:
                last_error = f"Pipeline error: {str(e)}"
                logger.error(f"Text-to-SQL pipeline error on attempt {attempt}: {e}")
                
                # Continue to next attempt if we haven't reached max retries
                if attempt < max_retries:
                    continue
                else:
                    return {
                        "success": False,
                        "error": f"Text-to-SQL pipeline failed after {max_retries} attempts. Last error: {last_error}",
                        "question": question,
                        "total_attempts": attempt
                    }
        
        # This should not be reached, but just in case
        return {
            "success": False,
            "error": f"Text-to-SQL pipeline failed after {max_retries} attempts",
            "question": question,
            "total_attempts": max_retries
        }