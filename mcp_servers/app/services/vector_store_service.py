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

METADATA_PATH = "hgraph_graphql_metadata.json"

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
        
        # Initialize metadata cache
        self._schema_metadata_cache = None
        
        logger.info("✅ VectorStoreService initialized", extra={
            "collection_name": collection_name,
            "embedding_model": embedding_model
        })
        
    def _load_schema_metadata(self, metadata_path: str) -> Dict[str, Any]:
        """
        Load GraphQL schema metadata from JSON file.
        
        Args:
            metadata_path: Path to the GraphQL schema metadata JSON file
            
        Returns:
            Dictionary containing schema metadata with use cases and rules
        """
        try:
            if self._schema_metadata_cache is None:
                logger.info(f"Loading GraphQL schema metadata from: {metadata_path}")
                
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                self._schema_metadata_cache = metadata
                logger.info(f"✅ Loaded metadata for {len(metadata)} schema types")
                
                # Log the loaded schema types
                for schema_type in metadata.keys():
                    use_case_count = len(metadata[schema_type].get('use_cases', []))
                    rule_count = len(metadata[schema_type].get('rules', []))
                    logger.info(f"  📋 {schema_type}: {use_case_count} use cases, {rule_count} rules")
            
            return self._schema_metadata_cache
            
        except FileNotFoundError:
            logger.warning(f"Schema metadata file not found: {metadata_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in metadata file {metadata_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load schema metadata from {metadata_path}: {e}")
            return {}
    
    def get_schema_metadata(self, schema_name: str, metadata_path: str = None) -> Dict[str, Any]:
        """
        Get metadata for a specific GraphQL schema type.
        
        Args:
            schema_name: Name of the GraphQL schema type
            metadata_path: Path to metadata file (uses default if not provided)
            
        Returns:
            Dictionary containing use cases and rules for the schema type
        """
        if metadata_path is None:
            metadata_path = METADATA_PATH
            
        metadata = self._load_schema_metadata(metadata_path)
        return metadata.get(schema_name, {"use_cases": [], "rules": []})
    
    def get_relevant_rules(self, relevant_schemas: List[Dict[str, Any]], metadata_path: str = None) -> str:
        """
        Extract relevant rules from metadata for a list of schema types.
        
        Args:
            relevant_schemas: List of schema dictionaries with 'name' field
            metadata_path: Path to metadata file (uses default if not provided)
            
        Returns:
            Formatted string of relevant rules
        """
        if metadata_path is None:
            metadata_path = METADATA_PATH
            
        metadata = self._load_schema_metadata(metadata_path)
        
        all_rules = []
        for schema in relevant_schemas:
            schema_name = schema.get('name', '')
            if schema_name in metadata:
                schema_rules = metadata[schema_name].get('rules', [])
                all_rules.extend(schema_rules)
        
        if not all_rules:
            return "No specific rules found for the selected schema types."
        
        # Remove duplicates while preserving order
        unique_rules = []
        for rule in all_rules:
            if rule not in unique_rules:
                unique_rules.append(rule)
        
        formatted_rules = "\n".join(f"- {rule}" for rule in unique_rules)
        logger.info(f"📋 Extracted {len(unique_rules)} unique rules from {len(relevant_schemas)} schema types")
        
        return formatted_rules
    
    def get_relevant_examples(self, relevant_schemas: List[Dict[str, Any]], user_question: str, metadata_path: str = None, max_examples: int = 2) -> str:
        """
        Extract relevant examples from metadata for a list of schema types.
        
        Args:
            relevant_schemas: List of schema dictionaries with 'name' field
            user_question: The user's question to match against example queries
            metadata_path: Path to metadata file (uses default if not provided)
            max_examples: Maximum number of examples to return
            
        Returns:
            Formatted string of relevant examples
        """
        if metadata_path is None:
            metadata_path = METADATA_PATH
            
        metadata = self._load_schema_metadata(metadata_path)
        
        all_examples = []
        for schema in relevant_schemas:
            schema_name = schema.get('name', '')
            if schema_name in metadata:
                schema_examples = metadata[schema_name].get('examples', [])
                for example in schema_examples:
                    example['schema_type'] = schema_name  # Add schema type for context
                    all_examples.append(example)
        
        if not all_examples:
            return "No relevant examples found for the selected schema types."
        
        # Simple relevance scoring based on keyword matching
        user_question_lower = user_question.lower()
        user_words = set(user_question_lower.split())
        
        scored_examples = []
        for example in all_examples:
            example_query_lower = example.get('query', '').lower()
            example_words = set(example_query_lower.split())
            
            # Calculate relevance score
            common_words = user_words.intersection(example_words)
            relevance_score = len(common_words) / max(len(user_words), 1)
            
            scored_examples.append((relevance_score, example))
        
        # Sort by relevance score and take top examples
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        top_examples = scored_examples[:max_examples]
        
        if not top_examples or top_examples[0][0] == 0:
            # If no good matches, return first few examples
            top_examples = [(0, example) for example in all_examples[:max_examples]]
        
        # Format examples for prompt
        formatted_examples = []
        for i, (score, example) in enumerate(top_examples, 1):
            schema_type = example.get('schema_type', 'unknown')
            formatted_examples.append(f"EXAMPLE {i} ({schema_type}):")
            formatted_examples.append(f"Natural language query: '{example.get('query', '')}'")
            formatted_examples.append(f"GraphQL query:")
            formatted_examples.append(example.get('graphql', ''))
            if example.get('explanation'):
                formatted_examples.append(f"// {example['explanation']}")
            formatted_examples.append("")  # Add blank line
        
        formatted_text = "\n".join(formatted_examples)
        logger.info(f"📝 Selected {len(top_examples)} relevant examples from {len(all_examples)} available examples")
        
        return formatted_text
    
    def force_rebuild_collection(self, schema_path: str):
        """
        Force rebuild the vector store collection with enhanced embeddings.
        This deletes the existing collection and recreates it.
        """
        try:
            logger.info("🔄 FORCE REBUILD: Starting collection rebuild with enhanced embeddings")
            
            # Delete existing collection if it exists
            if self.vector_search_service.check_collection_exists():
                logger.info("🗑️ FORCE REBUILD: Deleting existing collection")
                self.vector_search_service.delete_collection()
            
            # Load with enhanced embeddings
            logger.info("🔄 FORCE REBUILD: Loading schemas with enhanced embeddings")
            self.load_graphql_schemas(schema_path)
            
            logger.info("✅ FORCE REBUILD: Collection rebuild completed")
            
        except Exception as e:
            logger.error(f"❌ FORCE REBUILD: Failed to rebuild collection: {e}")
            raise

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
    
    def _create_graphql_searchable_text(self, type_data: Dict[str, Any], metadata_path: str = None) -> str:
        """
        Create searchable text for GraphQL schema type embeddings with metadata integration.
        
        Args:
            type_data: GraphQL type data from schema
            metadata_path: Path to metadata file (uses default if not provided)
            
        Returns:
            Enhanced searchable text string with use cases and contextual information
        """
        parts = []
        
        # Type name and description
        parts.append(f"{type_data['kind']} {type_data['name']}")
        if type_data.get('description'):
            parts.append(type_data['description'])
        
        # Add use cases from external metadata
        if metadata_path is None:
            metadata_path = METADATA_PATH
        
        metadata = self._load_schema_metadata(metadata_path)
        type_name = type_data.get('name', '')
        
        if type_name in metadata:
            type_metadata = metadata[type_name]
            
            # Add use cases for better semantic understanding
            if type_metadata.get('use_cases'):
                for use_case in type_metadata['use_cases']:
                    parts.append(f"Use case: {use_case}")
            
            # Add context from rules (without CRITICAL prefixes to avoid noise)
            if type_metadata.get('rules'):
                for rule in type_metadata['rules']:
                    # Clean rule text for searchability
                    clean_rule = rule.replace('CRITICAL: ', '').replace('Use ', '').replace('Include ', '')
                    parts.append(f"Context: {clean_rule}")
        
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
                    # Create enhanced searchable text with metadata
                    searchable_text = self._create_graphql_searchable_text(type_def, "hgraph_graphql_metadata.json")
                    
                    # Log enhanced embedding for important types
                    if type_def.get('name') in ['transaction', 'crypto_transfer', 'token', 'nft']:
                        logger.info(f"🔍 ENHANCED EMBEDDING: {type_def['name']} embedding ({len(searchable_text)} chars)")
                        logger.info(f"    Preview: {searchable_text[:200]}...")
                    
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
    
    def retrieve_relevant_context(self, query: str, k: int = 3) -> Dict[str, Any]:
        """
        Simple GraphQL tool: retrieve relevant schemas and metadata based on user query.
        
        Flow: User Query → Vector Search → Schema + Metadata → Ready for LLM
        
        Args:
            query: User's natural language query
            k: Number of schemas to retrieve
            
        Returns:
            Dictionary with schemas, rules, and examples ready for LLM system prompt
        """
        try:
            if self.vector_store is None:
                self.initialize_vector_store()
            
            if not self.vector_search_service.check_collection_exists():
                logger.warning("Collection does not exist")
                return {"schemas": [], "rules": "", "examples": ""}
            
            logger.info(f"🔍 Retrieving context for: '{query}'")
            
            # Core schemas that should be prioritized
            core_schemas = {'transaction', 'crypto_transfer', 'token', 'nft', 
                          'contract_result', 'token_transfer', 'nft_transfer', 
                          'account', 'topic_message'}
            
            # Strategy: Force-include core schemas based on query keywords
            # This ensures relevant core schemas appear even if vector similarity ranks them low
            query_lower = query.lower()
            force_include_core = []
            
            # Define keyword mapping to core schemas
            keyword_mapping = {
                'transaction': ['transaction'],
                'transfer': ['crypto_transfer', 'token_transfer', 'nft_transfer'],
                'token': ['token', 'token_transfer'],
                'nft': ['nft', 'nft_transfer'],
                'contract': ['contract_result'],
                'account': ['account'],
                'topic': ['topic_message'],
                'message': ['topic_message']
            }
            
            # Check for keyword matches
            for keyword, schemas in keyword_mapping.items():
                if keyword in query_lower:
                    force_include_core.extend(schemas)
            
            # Remove duplicates while preserving order
            force_include_core = list(dict.fromkeys(force_include_core))
            
            logger.info(f"🎯 Force including core schemas based on keywords: {force_include_core}")
            
            # Get search results
            search_k = max(k * 5, 50)  # Get more results to capture everything
            results = self.vector_store.similarity_search(query=query, k=search_k)
            
            logger.info(f"📊 Found {len(results)} candidate schemas")
            
            # Separate results by category
            forced_core_results = []  # Force-included core schemas
            other_core_results = []   # Other core schemas found
            other_results = []        # Non-core results
            
            # Track which forced schemas we've found
            found_forced = set()
            
            for doc in results:
                schema_name = doc.metadata.get("name", "")
                if schema_name in force_include_core:
                    forced_core_results.append(doc)
                    found_forced.add(schema_name)
                elif schema_name in core_schemas:
                    other_core_results.append(doc)
                else:
                    other_results.append(doc)
            
            # If we didn't find a forced core schema in the results, search specifically for it
            missing_forced = set(force_include_core) - found_forced
            if missing_forced:
                logger.info(f"🔍 Searching specifically for missing core schemas: {missing_forced}")
                for schema_name in missing_forced:
                    # Search specifically for this schema
                    specific_results = self.vector_store.similarity_search(query=schema_name, k=10)
                    for doc in specific_results:
                        if doc.metadata.get("name") == schema_name:
                            forced_core_results.append(doc)
                            logger.info(f"✅ Found missing core schema: {schema_name}")
                            break
            
            logger.info(f"📈 Forced core: {len(forced_core_results)}, Other core: {len(other_core_results)}, Others: {len(other_results)}")
            
            # Priority order: forced core → other core → others
            # Ensure we always get the most relevant core schemas first
            final_results = (forced_core_results[:k] + other_core_results + other_results)[:k]
            
            # Extract schemas from final results
            schemas = []
            for i, doc in enumerate(final_results, 1):
                schema_name = doc.metadata.get("name", "unknown")
                schema_data = json.loads(doc.metadata["schema_data"])
                schemas.append(schema_data)
                is_core = schema_name in core_schemas
                logger.info(f"  {i}. {schema_name} {'(CORE)' if is_core else ''}")
            
            # Get relevant rules and examples from metadata
            rules = self.get_relevant_rules(schemas)
            examples = self.get_relevant_examples(schemas, query)
            
            context = {
                "schemas": schemas,
                "rules": rules,
                "examples": examples
            }
            
            logger.info(f"✅ Context ready: {len(schemas)} schemas with rules and examples")
            return context
            
        except Exception as e:
            logger.error(f"Failed to retrieve context for '{query}': {e}")
            return {"schemas": [], "rules": "", "examples": ""}
    
