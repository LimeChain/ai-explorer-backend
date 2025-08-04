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

logger = logging.getLogger(__name__)


class BigQueryService:
    """Service wrapper for BigQuery text-to-SQL operations."""
    
    def __init__(self, credentials_path: str, dataset_id: str, openai_api_key: str, model_name: str = "gpt-4.1-mini"):
        """
        Initialize the BigQuery service with configuration.
        
        Args:
            credentials_path: Path to BigQuery service account JSON file
            dataset_id: BigQuery dataset ID (e.g., "hedera-etl-bq.hedera_restricted")
            openai_api_key: OpenAI API key for LLM
            model_name: LLM model name for SQL generation
        """
        try:
            # Initialize BigQuery client
            self.credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.client = bigquery.Client(credentials=self.credentials, project=self.credentials.project_id)
            self.dataset_id = dataset_id
            
            # Initialize LLM for SQL generation
            self.llm = init_chat_model(model_name, model_provider="openai", api_key=openai_api_key)
            
            # Cache for schema and partition info
            self._schema_cache = None
            self._partition_cache = None
            
            logger.info(f"Successfully initialized BigQuery service for dataset: {dataset_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery service: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize BigQuery service: {e}") from e
    
    def _build_schema_desc(self, fields, prefix=""):
        """Build schema description, including nested fields."""
        desc = []
        for f in fields:
            d = f"{prefix}Name: {f.name}, Type: {f.field_type}, Mode: {f.mode}"
            desc.append(d)
            if f.field_type == "RECORD":
                sub_desc = self._build_schema_desc(f.fields, prefix + "\t")
                desc.extend(sub_desc)
        return desc
    
    def _fetch_schema(self) -> str:
        """Fetch schema for all tables in the dataset."""
        if self._schema_cache:
            return self._schema_cache
            
        try:
            schemas = []
            tables = self.client.list_tables(self.dataset_id)
            
            for table in tables:
                ref = self.client.get_table(table)
                schema_desc = [f"Schema for table {table.table_id}:"]
                schema_desc += self._build_schema_desc(ref.schema)
                schema_desc.append("")  # Add a blank line for separation
                schemas += schema_desc
            
            self._schema_cache = "\n".join(schemas)
            logger.info(f"Fetched schema for {len(list(tables))} tables")
            return self._schema_cache
            
        except Exception as e:
            logger.error(f"Failed to fetch schema: {e}", exc_info=True)
            raise
    
    def _get_partitioned_fields(self) -> Dict[str, Dict[str, Any]]:
        """Return a dict of table_name -> (partition_field, require_partition_filter)."""
        if self._partition_cache:
            return self._partition_cache
            
        try:
            partition_info = {}
            tables = self.client.list_tables(self.dataset_id)
            
            for table in tables:
                ref = self.client.get_table(table)
                partition_field = None
                require_partition_filter = False
                
                if ref.time_partitioning:
                    partition_field = ref.time_partitioning.field or "_PARTITIONTIME"
                    require_partition_filter = getattr(ref, "require_partition_filter", False)
                
                partition_info[table.table_id] = {
                    "partition_field": partition_field,
                    "require_partition_filter": require_partition_filter
                }
            
            self._partition_cache = partition_info
            logger.info(f"Fetched partition info for {len(partition_info)} tables")
            return self._partition_cache
            
        except Exception as e:
            logger.error(f"Failed to fetch partition info: {e}", exc_info=True)
            raise
    
    def _is_historical_query(self, question: str) -> bool:
        """
        Determine if a question is asking for historical/time-based data.
        
        Args:
            question: Natural language question
            
        Returns:
            True if the query appears to be historical/time-based
        """
        historical_keywords = [
            "historical", "history", "over time", "trend", "trends", "trending",
            "in 2024", "in 2025", "last month", "last year", "past", "previous",
            "since", "between", "from", "to", "during", "period", "timeframe",
            "biggest", "largest", "top", "holders", "as of", "before", "after",
            "growth", "decline", "change", "evolution", "progression"
        ]
        
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in historical_keywords)
    
    def _create_sql_prompt_template(self) -> ChatPromptTemplate:
        """Create the prompt template for SQL generation."""
        template = """Based on the BigQuery schema below, write a SQL query that answers the user's question. Limit your responses to 10 results.

Partitioned tables and required filters:
{partitioned_fields_str}

Schema:
{schema}

Question: {question}

CRITICAL: Write a valid BigQuery SQL query, use aliases, and use the correct table names.
CRITICAL: Always use `{dataset_id}` in FROM and JOIN statements as a prefix before table names.
CRITICAL: Only return clean SQL that can be executed directly, e.g. remove ```sql <query> ```
CRITICAL: You have context about partitioned tables, so you SHOULD use partition filters when appropriate.

SQL Query:"""
        
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
            # Check if this is a historical query
            if not self._is_historical_query(question):
                return {
                    "error": "This question doesn't appear to be historical/time-based. Use real-time SDK methods instead.",
                    "is_historical": False,
                    "question": question
                }
            
            # Get schema and partition info
            schema = self._fetch_schema()
            partitioned_fields = self._get_partitioned_fields()
            
            # Create partitioned fields string
            partitioned_fields_str = "\n".join(
                f"Table `{tbl}`: partitioned by `{info['partition_field']}` (require_partition_filter={info['require_partition_filter']})"
                for tbl, info in partitioned_fields.items() if info['partition_field']
            )
            
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
                "is_historical": True
            }
            
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}", exc_info=True)
            return {
                "error": f"Failed to generate SQL query: {str(e)}",
                "question": question,
                "is_historical": True
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
            query_job = self.client.query(sql_query)
            results = query_job.result()
            
            # Convert results to list of dictionaries
            data = []
            for row in results:
                row_dict = dict(row)
                data.append(row_dict)
            
            logger.info(f"Query executed successfully, returned {len(data)} rows")
            
            return {
                "success": True,
                "data": data,
                "row_count": len(data),
                "sql_query": sql_query
            }
            
        except Exception as e:
            logger.error(f"Failed to execute BigQuery query: {e}", exc_info=True)
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
                return sql_result
            
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
                "error": execution_result.get("error"),
                "is_historical": True
            }
            
        except Exception as e:
            logger.error(f"Text-to-SQL pipeline failed: {e}", exc_info=True)
            return {
                "error": f"Text-to-SQL pipeline failed: {str(e)}",
                "question": question,
                "is_historical": True
            }