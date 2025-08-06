"""
Text processor for SDK method documentation.
Handles text processing, metadata extraction, and document preparation for vector embeddings.
"""
import json
import logging
from typing import Dict, List, Any
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class TextProcessor:
    """Processes SDK method data into searchable text and structured metadata."""
    
    def __init__(self):
        """Initialize the text processor."""
        pass
    
    def create_searchable_text(self, method: Dict[str, Any]) -> str:
        """
        Create optimized searchable text for vector embeddings.
        
        Args:
            method: Dictionary containing method information
            
        Returns:
            Processed text optimized for semantic search
        """
        # Validate required fields
        if 'name' not in method or 'description' not in method:
            raise ValueError("Method must contain 'name' and 'description' fields")
            
        # Focus on natural language that will create good embeddings
        parts = []
        
        # Method name and description are most important
        parts.append(method['name'])
        parts.append(method['description'])
        
        # Add parameter information in natural language
        if method.get("parameters"):
            param_texts = []
            for param in method["parameters"]:
                # Skip malformed parameters
                if not isinstance(param, dict) or 'name' not in param or 'description' not in param:
                    logger.warning(f"Skipping malformed parameter in method '{method['name']}'")
                    continue
                # Create natural language parameter description
                param_text = f"{param['name']} parameter {param['description']}"
                param_texts.append(param_text)
            parts.extend(param_texts)
        
        # Add use cases as they provide good semantic context
        if method.get("use_cases"):
            parts.extend(method['use_cases'])
        
        # Add return information
        if method.get("returns") and method["returns"].get("type"):
            parts.append(f"returns {method['returns']['type']}")
        
        # Add category for semantic grouping
        if method.get("category"):
            parts.append(f"{method['category']} functionality")
        
        # Join with spaces for natural language flow
        searchable_text = " ".join(parts)
        logger.debug(f"Created searchable text for method '{method['name']}': {len(searchable_text)} characters")
        
        return searchable_text
    
    def prepare_metadata(self, method: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare optimized metadata structure for the method.
        
        Args:
            method: Dictionary containing method information
            
        Returns:
            Structured metadata dictionary
        """
        # Validate required fields
        if 'name' not in method or 'description' not in method:
            raise ValueError("Method must contain 'name' and 'description' fields")
        
        metadata = {
            "method_name": method["name"],
            "description": method["description"],
            "category": method.get("category", "unknown"),
            "param_names": [p["name"] for p in method.get("parameters", [])],
            # Store return type for filtering
            "return_type": method.get("returns", {}).get("type", "unknown"),
            # Keep original data as JSON only for detailed responses
            "full_data": json.dumps(method)
        }
        
        logger.debug(f"Prepared metadata for method '{method['name']}'")
        return metadata
    
    def create_documents(self, methods: List[Dict[str, Any]]) -> List[Document]:
        """
        Convert a list of method dictionaries into Document objects.
        
        Args:
            methods: List of method dictionaries from documentation
            
        Returns:
            List of Document objects ready for vector store
        """
        documents = []
        
        for method in methods:
            try:
                # Create searchable text combining all relevant information
                searchable_text = self.create_searchable_text(method)
                
                # Prepare metadata with optimized structure
                metadata = self.prepare_metadata(method)
                
                # Create Document object with content and metadata
                doc = Document(
                    page_content=searchable_text,
                    metadata=metadata
                )
                documents.append(doc)
                
            except Exception as e:
                logger.error(f"Failed to create document for method '{method.get('name', 'unknown')}': {e}")
                continue
        
        logger.info(f"Created {len(documents)} documents from {len(methods)} methods")
        return documents
    
    def load_methods_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load method data from a JSON documentation file.
        
        Args:
            file_path: Path to the JSON documentation file
            
        Returns:
            List of method dictionaries
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
            ValueError: If file structure is invalid
        """
        try:
            with open(file_path, 'r') as f:
                doc_data = json.load(f)
            
            methods = doc_data.get("methods", [])
            
            if not isinstance(methods, list):
                raise ValueError("Documentation file must contain a 'methods' array")
            
            logger.info(f"Loaded {len(methods)} methods from {file_path}")
            return methods
            
        except FileNotFoundError:
            logger.error(f"Documentation file not found: {file_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in documentation file {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading methods from {file_path}: {e}")
            raise