"""GraphQL service wrapper for text-to-GraphQL query execution using Hgraph API."""

import logging
import json
import httpx
from typing import Any, Dict, List, Optional
from pydantic import SecretStr

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from .vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

COLLECTION_NAME = "graphql_schema"
MAX_RETRIES = 3

class GraphQLService:
    """Service wrapper for text-to-GraphQL operations using Hgraph API."""

    def __init__(
        self, 
        hgraph_endpoint: str,
        hgraph_api_key: SecretStr,
        llm_api_key: str,
        connection_string: str,
        llm_model: str,
        llm_provider: str,
        embedding_model: str,
        schema_path: str
    ):
        """
        Initialize the GraphQL service with configuration.
        
        Args:
            hgraph_endpoint: Hgraph GraphQL endpoint URL
            hgraph_api_key: SecretStr API key for Hgraph authentication
            llm_api_key: API key for LLM
            connection_string: PostgreSQL connection string for vector store (required)
            llm_model: LLM model name for GraphQL generation
            llm_provider: LLM provider for GraphQL generation
            embedding_model: OpenAI embedding model for schema search
            schema_path: Path to the GraphQL schema JSON file
        """
        try:
            # Initialize Hgraph client configuration
            self.hgraph_endpoint = hgraph_endpoint
            self.hgraph_api_key = hgraph_api_key
            self.schema_path = schema_path
            
            # Initialize LLM for GraphQL generation
            self.llm = init_chat_model(llm_model, model_provider=llm_provider, api_key=llm_api_key)
            
            # Initialize schema vector store
            self.schema_vector_store = VectorStoreService(
                connection_string=connection_string,
                llm_api_key=llm_api_key,
                collection_name=COLLECTION_NAME,
                embedding_model=embedding_model
            )

            logger.info(f"Successfully initialized GraphQL service for endpoint: {hgraph_endpoint}")
            
        except Exception as e:
            logger.error(f"Failed to initialize GraphQL service: {e}")
            raise RuntimeError(f"Failed to initialize GraphQL service: {e}") from e
    
    def _format_schema_for_prompt(self, schema_data: Dict[str, Any]) -> str:
        """Simple schema formatting for LLM prompt."""
        name = schema_data["name"]
        kind = schema_data["kind"]
        desc = schema_data.get("description", "")
        
        lines = [f"{kind} {name}"]
        if desc:
            lines.append(f"  {desc}")
        
        if kind == "OBJECT" and schema_data.get("fields"):
            for field in schema_data["fields"][:10]:  # Limit to 10 fields
                field_type = self._format_type(field["type"])
                lines.append(f"  {field['name']}: {field_type}")
        
        return "\n".join(lines)
    
    def _format_type(self, type_info: Dict[str, Any]) -> str:
        """Format GraphQL type information for display."""
        if type_info["kind"] == "NON_NULL":
            return f"{self._format_type(type_info['ofType'])}!"
        elif type_info["kind"] == "LIST":
            return f"[{self._format_type(type_info['ofType'])}]"
        elif type_info["name"]:
            return type_info["name"]
        else:
            return "Unknown"
    
    def initialize_schema_vector_store(self):
        """Initialize GraphQL schemas vector store."""
        try:
            if not self.schema_vector_store.vector_search_service.check_collection_exists():
                logger.info("Loading GraphQL schemas into vector store")
                self.schema_vector_store.load_graphql_schemas(self.schema_path)
        except Exception as e:
            logger.error(f"Failed to initialize schema vector store: {e}")
            raise
    
    def _create_graphql_prompt_template(self, include_error_context: bool = False) -> ChatPromptTemplate:
        """
        Create the prompt template for GraphQL generation with optional error context.
        
        Args:
            include_error_context: Whether to include error context for retry attempts
        """
        if include_error_context:
            template = """
                Based on the GraphQL schema and the instructions below, write a GraphQL query that answers the user's question.
                
                Available Schema Types:
                {schema}

                SCHEMA-SPECIFIC RULES (MUST FOLLOW):
                {rules}

                Question: {question}

                PREVIOUS ATTEMPT FAILED:
                Previous GraphQL Query: {previous_query}
                Error Message: {error_message}
                Attempt: {attempt_number} of 3

                CRITICAL: Write a valid GraphQL query that fixes the above error.
                CRITICAL: Use proper GraphQL syntax with correct field names and types.
                CRITICAL: Only return clean GraphQL that can be executed directly.
                CRITICAL: Do NOT include any explanation, notes, or comments.
                CRITICAL: Return ONLY the GraphQL query, nothing else.
                CRITICAL: Ensure all required fields and arguments are included.
                CRITICAL: Use appropriate filters and pagination if needed.
                CRITICAL: Analyze the previous error and fix the specific issue mentioned.

                RELEVANT EXAMPLES:
                {examples}

                Corrected GraphQL Query:
            """
        else:
            template = """
                Based on the GraphQL schema and the instructions below, write a GraphQL query that answers the user's question.
                
                Available Schema Types:
                {schema}

                SCHEMA-SPECIFIC RULES (MUST FOLLOW):
                {rules}

                Question: {question}

                CRITICAL: Write a valid GraphQL query using proper syntax.
                CRITICAL: Use correct field names and types from the schema.
                CRITICAL: Only return clean GraphQL that can be executed directly.
                CRITICAL: Do NOT include any explanation, notes, or comments.
                CRITICAL: Return ONLY the GraphQL query, nothing else.
                CRITICAL: Always start queries at the correct root field.
                CRITICAL: Include appropriate filters (where, order_by, limit, offset), sorting, and pagination if needed.
                CRITICAL: Use the correct period for where clauses.
                CRITICAL: Focus on the most relevant data for the question.

                RELEVANT EXAMPLES:
                {examples}

                GraphQL Query:
            """
        
        return ChatPromptTemplate.from_template(template)
    
    async def generate_graphql(self, question: str, previous_query: str = None, error_message: str = None, attempt_number: int = 1) -> Dict[str, Any]:
        """
        Simple GraphQL generation: Query → Vector Search → Context → LLM → GraphQL
        """
        try:
            # Initialize if needed
            if not self.schema_vector_store.vector_search_service.check_collection_exists():
                self.initialize_schema_vector_store()
            
            # Get context from vector search
            context = self.schema_vector_store.retrieve_relevant_context(question)
            
            # Format schemas for prompt
            schemas_text = "\n\n".join([
                self._format_schema_for_prompt(schema) 
                for schema in context["schemas"]
            ])
            
            # Prepare LLM prompt
            is_retry = previous_query is not None and error_message is not None
            prompt_template = self._create_graphql_prompt_template(include_error_context=is_retry)
            
            prompt_params = {
                "question": question,
                "schema": schemas_text,
                "rules": context["rules"],
                "examples": context["examples"]
            }
            
            if is_retry:
                prompt_params.update({
                    "previous_query": previous_query,
                    "error_message": error_message,
                    "attempt_number": attempt_number
                })
            
            # Generate GraphQL with LLM
            graphql_chain = (
                RunnablePassthrough()
                | prompt_template  
                | self.llm
                | StrOutputParser()
            )
            
            logger.info(f"🔧 PROMPT PARAMS: {prompt_params}")

            graphql_query = await graphql_chain.ainvoke(prompt_params)
            
            # Simple cleanup
            graphql_query = graphql_query.strip()
            if graphql_query.startswith("```"):
                graphql_query = graphql_query.split("```")[1].strip()
            if "```" in graphql_query:
                graphql_query = graphql_query.split("```")[0].strip()
            
            logger.info(f"Generated GraphQL for: {question}")
            
            return {
                "success": True,
                "graphql_query": graphql_query,
                "question": question,
                "attempt_number": attempt_number
            }
            
        except Exception as e:
            logger.error(f"Failed to generate GraphQL: {e}")
            return {
                "success": False,
                "error": f"Failed to generate GraphQL query: {str(e)}",
                "question": question,
                "attempt_number": attempt_number
            }
    
    async def execute_graphql(self, graphql_query: str) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the Hgraph API.
        
        Args:
            graphql_query: GraphQL query to execute
            
        Returns:
            Dict containing query results or error information
        """
        try:
            logger.info(f"🌐 GRAPHQL EXECUTION: Sending query to Hgraph API Endpoint: {self.hgraph_endpoint}, query length: {len(graphql_query)} characters")
            
            # Log the actual query being sent
            logger.info("📤 GRAPHQL EXECUTION: Sending GraphQL query:")
            for i, line in enumerate(graphql_query.strip().split('\n'), 1):
                logger.info(f"    {i:2d}: {line}")
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.hgraph_api_key.get_secret_value()
            }
            
            payload = {
                "query": graphql_query
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.hgraph_endpoint,
                    headers=headers,
                    json=payload,
                )
                logger.info(f"📡 GRAPHQL EXECUTION: Received HTTP {response.status_code} response")
                response.raise_for_status()
                
                result_data = response.json()
                logger.info(f"📦 GRAPHQL EXECUTION: Response JSON parsed successfully")
                
                # Check for GraphQL errors
                if "errors" in result_data:
                    errors = result_data["errors"]
                    error_messages = [error.get("message", "Unknown error") for error in errors]
                    logger.error(f"❌ GRAPHQL EXECUTION: GraphQL API returned errors:")
                    for i, error in enumerate(errors, 1):
                        logger.error(f"  {i}. {error.get('message', 'Unknown error')}")
                        if 'locations' in error:
                            logger.error(f"     Location: {error['locations']}")
                        if 'path' in error:
                            logger.error(f"     Path: {error['path']}")
                    
                    return {
                        "success": False,
                        "error": f"GraphQL errors: {'; '.join(error_messages)}",
                        "graphql_query": graphql_query,
                        "errors": errors
                    }
                
                # Extract data
                data = result_data.get("data", {})
                logger.info(f"✅ GRAPHQL EXECUTION: Query executed successfully")
                
                # Log data structure summary
                if isinstance(data, dict) and data:
                    top_keys = list(data.keys())[:3]
                    logger.info(f"🗂️ GRAPHQL EXECUTION: Top-level response keys: {top_keys}")
                    
                    # Log sample of first key's data if it's a list
                    if top_keys and isinstance(data[top_keys[0]], list):
                        first_key_count = len(data[top_keys[0]])
                        logger.info(f"📝 GRAPHQL EXECUTION: '{top_keys[0]}' contains {first_key_count} items")
                
                return {
                    "success": True,
                    "data": data,
                    "graphql_query": graphql_query,
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"🚫 GRAPHQL EXECUTION: HTTP {e.response.status_code} error: {e}")
            logger.error(f"🚫 GRAPHQL EXECUTION: Response text: {e.response.text[:500]}{'...' if len(e.response.text) > 500 else ''}")
            return {
                "success": False,
                "error": f"HTTP error {e.response.status_code}: {e.response.text}",
                "graphql_query": graphql_query
            }
        except httpx.TimeoutException:
            logger.error(f"⏰ GRAPHQL EXECUTION: Request timed out after 30 seconds")
            return {
                "success": False,
                "error": "GraphQL query timed out after 30 seconds",
                "graphql_query": graphql_query
            }
        except Exception as e:
            logger.error(f"💥 GRAPHQL EXECUTION: Unexpected error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to execute query: {str(e)}",
                "graphql_query": graphql_query
            }
    
    async def text_to_graphql_query(self, question: str, max_retries: int = MAX_RETRIES) -> Dict[str, Any]:
        """
        Complete text-to-GraphQL pipeline with retry logic that generates GraphQL and executes it.
        
        Args:
            question: Question to convert to GraphQL
            max_retries: Maximum number of retry attempts for GraphQL generation and execution
            
        Returns:
            Dict containing query results or error information
        """
        last_error = None
        previous_query = None
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 GRAPHQL SERVICE: Starting pipeline attempt {attempt}/{max_retries}")
                logger.info(f"❓ GRAPHQL SERVICE: Question: '{question[:150]}{'...' if len(question) > 150 else ''}'")
                
                if attempt > 1:
                    logger.info(f"🔁 GRAPHQL SERVICE: Retry attempt - previous error: {last_error}")
                    if previous_query:
                        logger.info(f"📋 GRAPHQL SERVICE: Previous failed query will be provided for context")
                
                # Generate GraphQL with error context if this is a retry
                logger.info(f"⚙️ GRAPHQL SERVICE: Generating GraphQL query (attempt {attempt})")
                graphql_result = await self.generate_graphql(
                    question=question,
                    previous_query=previous_query,
                    error_message=last_error,
                    attempt_number=attempt
                )
                
                if not graphql_result.get("success"):
                    last_error = graphql_result.get("error", "Unknown GraphQL generation error")
                    logger.warning(f"❌ GRAPHQL SERVICE: Query generation failed on attempt {attempt}: {last_error}")
                    
                    if attempt < max_retries:
                        logger.info(f"🔄 GRAPHQL SERVICE: Retrying... ({attempt + 1}/{max_retries})")
                        continue
                    else:
                        logger.error(f"💥 GRAPHQL SERVICE: Query generation failed after all {max_retries} attempts")
                        return {
                            "success": False,
                            "error": f"Failed to generate GraphQL after {max_retries} attempts. Last error: {last_error}",
                            "question": question,
                            "total_attempts": attempt
                        }
                
                graphql_query = graphql_result["graphql_query"]
                previous_query = graphql_query
                
                logger.info(f"✅ GRAPHQL SERVICE: Query generated successfully on attempt {attempt}")

                # Log the generated query with line numbers for debugging
                for i, line in enumerate(graphql_query.strip().split('\n'), 1):
                    logger.info(f"    {i:2d}: {line}")
                
                # Execute GraphQL query
                execution_result = await self.execute_graphql(graphql_query)
                
                if not execution_result.get("success"):
                    execution_error = execution_result.get("error", "Query execution failed")
                    logger.error(f"❌ GRAPHQL SERVICE: Query execution failed on attempt {attempt}: {execution_error}")
                    
                    # Log additional execution details if available
                    if "errors" in execution_result:
                        logger.error(f"🔍 GRAPHQL SERVICE: GraphQL API errors: {execution_result['errors']}")
                    
                    # For execution failures, we can retry with the execution error
                    if attempt < max_retries:
                        last_error = f"Query execution failed: {execution_error}"
                        logger.info(f"🔄 GRAPHQL SERVICE: Will retry with execution error context ({attempt + 1}/{max_retries})")
                        continue
                    else:
                        logger.error(f"💥 GRAPHQL SERVICE: Query execution failed after all {max_retries} attempts")
                        return {
                            "success": False,
                            "error": f"Query execution failed after {max_retries} attempts. Last error: {execution_error}",
                            "question": question,
                            "graphql_query": graphql_query,
                            "total_attempts": attempt
                        }
                
                data = execution_result.get("data", {})
                
                logger.info(f"🎉 GRAPHQL SERVICE: Pipeline completed successfully on attempt {attempt}")
                
                # Log a summary of the returned data structure
                if isinstance(data, dict):
                    top_level_keys = list(data.keys())[:5]  # Show first 5 keys
                    logger.info(f"🗂️ GRAPHQL SERVICE: Top-level data keys: {top_level_keys}")
                
                return {
                    "success": True,
                    "question": question,
                    "graphql_query": graphql_query,
                    "data": data,
                    "total_attempts": attempt
                }
                
            except Exception as e:
                last_error = f"Pipeline error: {str(e)}"
                logger.error(f"💥 GRAPHQL SERVICE: Pipeline exception on attempt {attempt}: {str(e)}", exc_info=True)
                
                # Continue to next attempt if we haven't reached max retries
                if attempt < max_retries:
                    logger.info(f"🔄 GRAPHQL SERVICE: Retrying after exception... ({attempt + 1}/{max_retries})")
                    continue
                else:
                    logger.error(f"💥 GRAPHQL SERVICE: Pipeline failed after all {max_retries} attempts due to exceptions")
                    return {
                        "success": False,
                        "error": f"Text-to-GraphQL pipeline failed after {max_retries} attempts. Last error: {last_error}",
                        "question": question,
                        "total_attempts": attempt
                    }
        
        # This should not be reached
        return {
            "success": False,
            "error": f"Text-to-GraphQL pipeline failed after {max_retries} attempts",
            "question": question,
            "total_attempts": max_retries
        }