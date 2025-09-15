"""GraphQL service wrapper for text-to-GraphQL query execution using Hgraph API."""

import logging
import json
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from .vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

COLLECTION_NAME = "graphql_schemas_hgraph"
class GraphQLService:
    """Service wrapper for text-to-GraphQL operations using Hgraph API."""

    def __init__(
        self, 
        hgraph_endpoint: str,
        hgraph_api_key: str,
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
            hgraph_api_key: API key for Hgraph authentication
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
    
    def _get_relevant_schemas(self, question: str, k: int = 3) -> tuple[str, List[Dict[str, Any]]]:
        """
        Get relevant GraphQL schemas using vector search.
        
        Args:
            question: Natural language question
            k: Number of relevant schema types to retrieve
            
        Returns:
            Tuple of (formatted schema string, raw schema data)
        """
        try:
            logger.info(f"🔍 SCHEMA SEARCH: Searching for {k} relevant schema types for question")
            logger.info(f"❓ SCHEMA SEARCH: Query: '{question[:100]}{'...' if len(question) > 100 else ''}'")
            
            # Use vector store for intelligent schema retrieval
            relevant_schemas = self.schema_vector_store.retrieve_graphql_schemas(question, k=k)
            
            logger.info(f"📊 SCHEMA SEARCH: Retrieved {len(relevant_schemas)} schema types")
            
            if not relevant_schemas:
                logger.error("❌ SCHEMA SEARCH: No relevant schemas found for the query")
                raise RuntimeError("No relevant schemas found for the query")
            
            # Log the retrieved schema types
            for i, schema_data in enumerate(relevant_schemas, 1):
                type_name = schema_data.get("name", "unknown")
                kind = schema_data.get("kind", "unknown")
                description = schema_data.get("description", "No description")[:50]
                logger.info(f"  {i}. {kind} '{type_name}': {description}{'...' if len(description) == 50 else ''}")
            
            
            # Format schemas for prompt
            formatted_schemas = []
            for schema_data in relevant_schemas:
                type_name = schema_data["name"]
                description = schema_data["description"]
                kind = schema_data["kind"]
                
                schema_lines = [f"GraphQL {kind} {type_name}:"]
                if description:
                    schema_lines.append(f"Description: {description}")
                
                # Add field information for OBJECT types
                if schema_data["kind"] == "OBJECT" and schema_data.get("fields"):
                    schema_lines.append("Fields:")
                    for field in schema_data["fields"]:
                        field_line = f"  {field['name']}: {self._format_type(field['type'])}"
                        if field.get('description'):
                            field_line += f" - {field['description']}"
                        schema_lines.append(field_line)
                
                # Add input fields for INPUT_OBJECT types
                elif schema_data["kind"] == "INPUT_OBJECT" and schema_data.get("inputFields"):
                    schema_lines.append("Input Fields:")
                    for field in schema_data["inputFields"]:
                        field_line = f"  {field['name']}: {self._format_type(field['type'])}"
                        if field.get('description'):
                            field_line += f" - {field['description']}"
                        schema_lines.append(field_line)
                
                # Add enum values for ENUM types
                elif schema_data["kind"] == "ENUM" and schema_data.get("enumValues"):
                    schema_lines.append("Values:")
                    for value in schema_data["enumValues"]:
                        value_line = f"  {value['name']}"
                        if value.get('description'):
                            value_line += f" - {value['description']}"
                        schema_lines.append(value_line)
                
                schema_lines.append("")  # Add blank line for separation
                formatted_schemas.extend(schema_lines)
            
            formatted_schema_text = "\n".join(formatted_schemas)
            logger.info(f"✅ SCHEMA SEARCH: Formatted {len(relevant_schemas)} schema types into {len(formatted_schema_text)} character prompt")
            logger.info(f"📝 SCHEMA SEARCH: Schema context preview (first 200 chars):")
            logger.info(f"    {formatted_schema_text[:200]}{'...' if len(formatted_schema_text) > 200 else ''}")
            
            return formatted_schema_text, relevant_schemas
            
        except Exception as e:
            logger.error(f"Failed to retrieve relevant schemas: {e}")
            raise
    
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
        """Initialize and load GraphQL schemas into the vector store."""
        try:
            # Check if collection already exists
            if not self.schema_vector_store.vector_search_service.check_collection_exists():
                logger.info("GraphQL schema vector store collection not found, loading schemas from JSON")
                self.schema_vector_store.load_graphql_schemas(self.schema_path)
                logger.info("GraphQL schema vector store initialized successfully")
            else:
                logger.info("GraphQL schema vector store collection already exists, skipping initialization")
        except Exception as e:
            logger.error(f"Failed to initialize GraphQL schema vector store: {e}")
            raise
    
    def _create_graphql_prompt_template(self, include_error_context: bool = False) -> ChatPromptTemplate:
        """
        Create the prompt template for GraphQL generation with optional error context.
        
        Args:
            include_error_context: Whether to include error context for retry attempts
        """
        if include_error_context:
            template = """
                Based on the GraphQL schema below, write a GraphQL query that answers the user's question.
                
                Available Schema Types:
                {schema}

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

                Corrected GraphQL Query:
            """
        else:
            template = """
                Based on the GraphQL schema below, write a GraphQL query that answers the user's question.
                
                Available Schema Types:
                {schema}

                Question: {question}

                CRITICAL: Write a valid GraphQL query using proper syntax.
                CRITICAL: Use correct field names and types from the schema.
                CRITICAL: Only return clean GraphQL that can be executed directly.
                CRITICAL: Do NOT include any explanation, notes, or comments.
                CRITICAL: Return ONLY the GraphQL query, nothing else.
                CRITICAL: Include appropriate filters, sorting, and pagination if needed.
                CRITICAL: Focus on the most relevant data for the question.

                GraphQL Query:
            """
        
        return ChatPromptTemplate.from_template(template)
    
    async def generate_graphql(self, question: str, previous_query: str = None, error_message: str = None, attempt_number: int = 1) -> Dict[str, Any]:
        """
        Generate GraphQL query from natural language question with optional error context for retries.
        
        Args:
            question: Natural language question
            previous_query: Previous GraphQL query that failed (for retry attempts)
            error_message: Error message from previous attempt (for retry attempts)
            attempt_number: Current attempt number (for retry context)
            
        Returns:
            Dict containing the generated GraphQL query or error information
        """
        try:
            # Ensure schema vector store is initialized
            if not self.schema_vector_store.vector_search_service.check_collection_exists():
                logger.info("GraphQL schema vector store not initialized, initializing now...")
                self.initialize_schema_vector_store()
            
            # Get relevant schema using vector search
            schema, relevant_schema_data = self._get_relevant_schemas(question)
            
            # Create GraphQL generation chain with error context if this is a retry
            is_retry = previous_query is not None and error_message is not None
            prompt_template = self._create_graphql_prompt_template(include_error_context=is_retry)
            
            graphql_chain = (
                RunnablePassthrough()
                | prompt_template
                | self.llm.bind(stop=["\nGraphQLResult:", "\nCorrected GraphQL Query:"])
                | StrOutputParser()
            )
            
            # Prepare prompt parameters
            prompt_params = {
                "question": question,
                "schema": schema
            }
            
            # Add error context for retry attempts
            if is_retry:
                prompt_params.update({
                    "previous_query": previous_query,
                    "error_message": error_message,
                    "attempt_number": attempt_number
                })
            
            # Generate GraphQL
            graphql_query = await graphql_chain.ainvoke(prompt_params)
            
            # Clean up GraphQL query - extract only the actual GraphQL query
            graphql_query = graphql_query.strip()
            
            # Remove code block markers
            if graphql_query.startswith("```graphql"):
                graphql_query = graphql_query[10:]
            elif graphql_query.startswith("```"):
                graphql_query = graphql_query[3:]
            
            # Find the end of the GraphQL query (before any explanations)
            # Look for patterns that indicate the end of the query
            end_markers = [
                "```",
                "**Explanation:",
                "**Note:",
                "*If you need",
                "Explanation:",
                "Note:",
                "\n\n**",
                "\n\n*",
                "\n\nExplanation",
                "\n\nNote"
            ]
            
            for marker in end_markers:
                if marker in graphql_query:
                    graphql_query = graphql_query.split(marker)[0]
                    break
            
            graphql_query = graphql_query.strip()
            
            attempt_log = f" (attempt {attempt_number})" if attempt_number > 1 else ""
            logger.info(f"Generated GraphQL query for question: {question[:100]}...{attempt_log}")
            logger.debug(f"Generated GraphQL: {graphql_query}")
            
            return {
                "success": True,
                "graphql_query": graphql_query,
                "question": question,
                "attempt_number": attempt_number
            }
            
        except Exception as e:
            logger.error(f"Failed to generate GraphQL (attempt {attempt_number}): {e}")
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
                "x-api-key": self.hgraph_api_key
            }
            
            payload = {
                "query": graphql_query
            }
            
            logger.info("⏳ GRAPHQL EXECUTION: Making HTTP request...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.hgraph_endpoint,
                    headers=headers,
                    json=payload
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
                data_size = len(str(data))
                
                logger.info(f"✅ GRAPHQL EXECUTION: Query executed successfully")
                logger.info(f"📊 GRAPHQL EXECUTION: Response data size: {data_size} characters")
                
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
                    "response_size": data_size
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
    
    async def text_to_graphql_query(self, question: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Complete text-to-GraphQL pipeline with retry logic: generate GraphQL and execute.
        
        Args:
            question: Natural language question
            max_retries: Maximum number of retry attempts for GraphQL generation
            
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
                    
                    # Continue to next attempt if we haven't reached max retries
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
                previous_query = graphql_query  # Store for potential retry
                
                logger.info(f"✅ GRAPHQL SERVICE: Query generated successfully on attempt {attempt}")
                logger.info(f"📝 GRAPHQL SERVICE: Generated query:")
                # Log the generated query with line numbers for debugging
                for i, line in enumerate(graphql_query.strip().split('\n'), 1):
                    logger.info(f"    {i:2d}: {line}")
                
                # Execute GraphQL query
                logger.info(f"🌐 GRAPHQL SERVICE: Executing GraphQL query against Hgraph API")
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
                
                # Success! Return combined results
                data = execution_result.get("data", {})
                response_size = execution_result.get("response_size", 0)
                
                logger.info(f"🎉 GRAPHQL SERVICE: Pipeline completed successfully on attempt {attempt}")
                logger.info(f"📊 GRAPHQL SERVICE: Retrieved data with {response_size} response size")
                logger.info(f"📈 GRAPHQL SERVICE: Data summary: {len(str(data))} characters")
                
                # Log a brief summary of the returned data structure
                if isinstance(data, dict):
                    top_level_keys = list(data.keys())[:5]  # Show first 5 keys
                    logger.info(f"🗂️ GRAPHQL SERVICE: Top-level data keys: {top_level_keys}")
                
                return {
                    "success": True,
                    "question": question,
                    "graphql_query": graphql_query,
                    "data": data,
                    "response_size": response_size,
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
        
        # This should not be reached, but just in case
        return {
            "success": False,
            "error": f"Text-to-GraphQL pipeline failed after {max_retries} attempts",
            "question": question,
            "total_attempts": max_retries
        }